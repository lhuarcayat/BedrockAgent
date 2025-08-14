import json
import logging
import os
import re
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from shared.helper import load_env
from shared.aws_clients import create_dynamodb_client

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()
logger.setLevel(logging.INFO)
load_env()

def extract_document_number_from_path(s3_path: str) -> Optional[str]:
    """
    Extract document number from S3 path.
    Expected pattern: s3://bucket/path/document_number/filename.pdf
    """
    try:
        # Extract path after bucket name
        path_parts = s3_path.replace('s3://', '').split('/')
        if len(path_parts) >= 3:
            # Look for document number pattern (6+ digits)
            for part in path_parts:
                if re.match(r'^\d{6,}$', part):
                    return part
        logger.warning(f"Could not extract document number from path: {s3_path}")
        return None
    except Exception as e:
        logger.error(f"Error extracting document number from {s3_path}: {str(e)}")
        return None

def extract_category_from_payload(payload: Dict[str, Any]) -> str:
    """
    Extract category from payload, fallback to parsing from path.
    """
    # Try direct category field
    category = payload.get('category')
    if category and category in ['CERL', 'CECRL', 'RUT', 'RUB', 'ACC']:
        return category
    
    # Try from result object
    result = payload.get('result', {})
    category = result.get('category')
    if category and category in ['CERL', 'CECRL', 'RUT', 'RUB', 'ACC']:
        return category
    
    # Parse from path
    path = payload.get('path', '')
    for cat in ['CERL', 'CECRL', 'RUT', 'RUB', 'ACC']:
        if cat in path:
            return cat
    
    logger.warning(f"Could not determine category from payload: {payload}")
    return 'UNKNOWN'

def extract_error_information(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract error information from the payload.
    Maps to classification error patterns when possible.
    """
    result = payload.get('result', {})
    
    # Standard error patterns from classification
    error_patterns = {
        'content_filtered': 'Content filtered by model safety systems',
        'parse_error': 'Failed to parse model response as valid JSON',
        'model_error': 'Model request failed or returned error'
    }
    
    error_type = result.get('status', 'unknown_error')
    error_message = result.get('error_message', 'No error message provided')
    
    # Map to standard patterns if possible
    if error_type in error_patterns:
        mapped_error = error_patterns[error_type]
    else:
        mapped_error = error_message
    
    return {
        'error_type': error_type,
        'error_message': mapped_error,
        'raw_error_message': error_message,
        'processing_failed': result.get('processing_failed', True)
    }

def extract_models_used(payload: Dict[str, Any]) -> List[str]:
    """
    Extract the models that were attempted from the payload.
    """
    result = payload.get('result', {})
    models = []
    
    # Primary model
    if 'model_used' in result:
        models.append(result['model_used'])
    
    # Fallback model if used
    if result.get('fallback_used', False) and 'fallback_model' in result:
        fallback_model = result['fallback_model']
        if fallback_model not in models:
            models.append(fallback_model)
    
    # Default models if none found
    if not models:
        models = [
            os.environ.get('BEDROCK_MODEL', 'us.amazon.nova-pro-v1:0'),
            os.environ.get('FALLBACK_MODEL', 'us.anthropic.claude-sonnet-4-20250514-v1:0')
        ]
    
    return models

def extract_s3_info(payload: Dict[str, Any]) -> Dict[str, str]:
    """
    Extract S3 bucket and key from payload path.
    """
    path = payload.get('path', '')
    
    if path.startswith('s3://'):
        # Parse s3:// URL
        path_without_protocol = path[5:]  # Remove 's3://'
        parts = path_without_protocol.split('/', 1)
        if len(parts) == 2:
            return {
                's3_bucket': parts[0],
                's3_key': parts[1]
            }
    
    # Fallback: try to construct from environment and payload
    bucket = os.environ.get('S3_ORIGIN_BUCKET', 'unknown-bucket')
    key = path.replace('s3://', '').replace(bucket + '/', '') if bucket != 'unknown-bucket' else path
    
    return {
        's3_bucket': bucket,
        's3_key': key
    }

def create_manual_review_record(payload: Dict[str, Any], record_id: str) -> Dict[str, Any]:
    """
    Create a DynamoDB record for manual review tracking using Option C schema.
    
    Schema:
    PK: FAILED#{category}
    SK: {YYYY#MM#DD}#{document_number}#{timestamp}
    GSI1PK: DOC#{document_number} 
    GSI1SK: {category}#{YYYY#MM#DD}
    """
    now = datetime.now(timezone.utc)
    
    # Extract information from payload
    category = extract_category_from_payload(payload)
    document_number = extract_document_number_from_path(payload.get('path', ''))
    error_info = extract_error_information(payload)
    models_used = extract_models_used(payload)
    s3_info = extract_s3_info(payload)
    
    # Create timestamp for sorting
    timestamp = str(int(now.timestamp() * 1000))  # milliseconds for uniqueness
    
    # Format date components
    date_str = now.strftime('%Y#%m#%d')
    date_simple = now.strftime('%Y#%m#%d')
    
    # Construct keys according to Option C schema
    pk = f"FAILED#{category}"
    sk = f"{date_str}#{document_number or 'UNKNOWN'}#{timestamp}"
    
    # GSI keys for document lookup
    gsi1pk = f"DOC#{document_number or 'UNKNOWN'}"
    gsi1sk = f"{category}#{date_simple}"
    
    # TTL: 90 days from now
    ttl = int((now + timedelta(days=90)).timestamp())
    
    record = {
        # Primary keys
        'pk': pk,
        'sk': sk,
        
        # GSI keys
        'gsi1pk': gsi1pk,
        'gsi1sk': gsi1sk,
        
        # Core data
        'record_id': record_id,
        'category': category,
        'document_number': document_number or 'UNKNOWN',
        'failed_at': now.isoformat(),
        'date': now.strftime('%Y-%m-%d'),
        
        # S3 information
        's3_bucket': s3_info['s3_bucket'],
        's3_key': s3_info['s3_key'],
        's3_path': payload.get('path', ''),
        
        # Error information
        'error_type': error_info['error_type'],
        'error_message': error_info['error_message'],
        'raw_error_message': error_info['raw_error_message'],
        'processing_failed': error_info['processing_failed'],
        
        # Model information
        'models_used': models_used,
        'primary_model': models_used[0] if models_used else 'unknown',
        'fallback_used': len(models_used) > 1,
        
        # Full payload for debugging
        'raw_payload': json.dumps(payload, default=str),
        
        # Metadata
        'created_at': now.isoformat(),
        'ttl': ttl
    }
    
    return record

def save_to_dynamodb(record: Dict[str, Any]) -> bool:
    """
    Save the manual review record to DynamoDB.
    """
    try:
        table_name = os.environ.get('MANUAL_REVIEW_TABLE')
        if not table_name:
            logger.error("MANUAL_REVIEW_TABLE environment variable not set")
            return False
        
        dynamodb_client = create_dynamodb_client()
        
        # Convert Python dict to DynamoDB format
        item = {}
        for key, value in record.items():
            if isinstance(value, str):
                item[key] = {'S': value}
            elif isinstance(value, (int, float)):
                item[key] = {'N': str(value)}
            elif isinstance(value, bool):
                item[key] = {'BOOL': value}
            elif isinstance(value, list):
                item[key] = {'SS': [str(v) for v in value]}
            else:
                item[key] = {'S': str(value)}
        
        dynamodb_client.put_item(
            TableName=table_name,
            Item=item
        )
        
        logger.info(f"Successfully saved manual review record: {record['record_id']}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to save record to DynamoDB: {str(e)}")
        return False

def process_fallback_message(sqs_record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process a single SQS message from the fallback queue.
    """
    message_id = sqs_record.get('messageId', 'unknown')
    
    try:
        # Parse the payload from SQS message body
        payload = json.loads(sqs_record['body'])
        
        # Log full event details for debugging
        logger.info(f"Processing fallback message {message_id}")
        logger.info(f"Full payload: {json.dumps(payload, indent=2, default=str)}")
        
        # Create manual review record
        record = create_manual_review_record(payload, message_id)
        
        # Save to DynamoDB
        success = save_to_dynamodb(record)
        
        if success:
            logger.info(f"Successfully processed fallback message {message_id}")
            return {
                'messageId': message_id,
                'status': 'success',
                'category': record['category'],
                'document_number': record['document_number'],
                'error_type': record['error_type']
            }
        else:
            logger.error(f"Failed to save fallback message {message_id} to DynamoDB")
            return {
                'messageId': message_id,
                'status': 'error',
                'error': 'Failed to save to DynamoDB'
            }
            
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse SQS message body as JSON: {str(e)}")
        return {
            'messageId': message_id,
            'status': 'error',
            'error': f'Invalid JSON in message body: {str(e)}'
        }
    except Exception as e:
        logger.error(f"Error processing fallback message {message_id}: {str(e)}")
        return {
            'messageId': message_id,
            'status': 'error',
            'error': str(e)
        }

def handler(event, context):
    """
    Lambda handler for fallback processing.
    Processes SQS messages containing failed extraction records.
    """
    try:
        logger.info(f"Received fallback event with {len(event.get('Records', []))} messages")
        logger.info(f"Full event: {json.dumps(event, indent=2, default=str)}")
        
        if 'Records' not in event:
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'error': 'Not an SQS batch event or missing Records'
                })
            }
        
        results = []
        failed_message_ids = []
        
        # Process each SQS record
        for sqs_record in event['Records']:
            if sqs_record.get('eventSource') != 'aws:sqs':
                logger.warning(f"Skipping non-SQS event: {sqs_record.get('eventSource')}")
                continue
            
            result = process_fallback_message(sqs_record)
            results.append(result)
            
            # Track failed messages for SQS retry
            if result['status'] == 'error':
                failed_message_ids.append(result['messageId'])
        
        # Calculate summary statistics
        total_messages = len(event['Records'])
        successful_processing = len([r for r in results if r['status'] == 'success'])
        failed_processing = len(failed_message_ids)
        
        summary = {
            'totalMessages': total_messages,
            'successfulProcessing': successful_processing,
            'failedProcessing': failed_processing
        }
        
        # Build response
        response = {
            'statusCode': 200,
            'body': json.dumps({
                'results': results,
                'summary': summary
            })
        }
        
        # Add batch item failures for SQS retry
        if failed_message_ids:
            response['batchItemFailures'] = [
                {'itemIdentifier': msg_id} for msg_id in failed_message_ids
            ]
            logger.warning(f"Fallback processing completed with {failed_processing} failed messages")
        
        logger.info(f"Fallback processing summary: {successful_processing} successful, {failed_processing} failed")
        
        return response
        
    except Exception as e:
        logger.error(f"Error in fallback handler: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e)
            })
        }