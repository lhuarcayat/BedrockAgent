import json, logging, os, re
from urllib.parse import unquote_plus
from collections import namedtuple
from shared.models import ClassMeta
from shared.sqs_handler import build_payload, send_to_extraction_queue
from shared.helper import load_env
from shared.processing_result import save_processing_to_s3
from shared.idempotency_handler import acquire_processing_lock, release_processing_lock
from shared.aws_clients import create_s3_client, create_dynamodb_client
from shared.result_builder import result_to_dict
from shared.bedrock_classification import setup_classification_request, classify_with_fallback

# Categories that require extraction processing
EXTRACTABLE_CATEGORIES = {'CERL', 'CECRL', 'RUT', 'RUB', 'ACC'}

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()
logger.setLevel(logging.INFO)
load_env()

# Result Pattern - Explicit handling of all classification outcomes
ClassificationResult = namedtuple('ClassificationResult', [
    'is_success',        # bool - True if we got a valid classification
    'data',              # dict | None - parsed classification data
    'status',            # str - 'success' | 'content_filtered' | 'parse_error' | 'model_error'
    'error_message',     # str | None - error details for logging
    'model_used'         # str - which model was used
])


def process_pdf(pdf_bytes, folder_path):
    """
    Main orchestrator - coordinates the classification workflow.
    """
    # 1. Setup classification request
    bedrock, messages, system_parameter, models = setup_classification_request(pdf_bytes, folder_path)

    # 2. Classify with fallback
    classification_result, raw_responses = classify_with_fallback(bedrock, messages, system_parameter, models, folder_path, ClassificationResult)

    # 3. Convert result to dict for backward compatibility
    meta_dict = result_to_dict(classification_result, folder_path, raw_responses, EXTRACTABLE_CATEGORIES)

    # 4. Validate with Pydantic if classification succeeded
    if not meta_dict.get('processing_failed', False):
        try:
            ClassMeta.model_validate(meta_dict)
        except Exception as validation_error:
            logger.warning(f"Pydantic validation failed: {validation_error}, proceeding with raw dict")
            meta_dict['validation_error'] = str(validation_error)

    # 5. Build payload with fallback information
    payload = build_payload(meta_dict)
    payload['path'] = folder_path
    payload['fallback_used'] = meta_dict.get('fallback_used', False)

    if payload['fallback_used']:
        logger.info(f"Fallback model used for {folder_path}: {meta_dict.get('model_used', 'unknown')}")

    # 6. Send to extraction queue - only for extractable categories and successful classifications
    if meta_dict.get('requires_extraction', False) and not meta_dict.get('processing_failed', False):
        try:
            send_to_extraction_queue(payload)
            logger.info(f"Sent payload to extraction queue for {folder_path}")
        except Exception as e:
            logger.error(f"Failed to send to extraction queue: {str(e)}")
            payload['sqs_send_failed'] = True
            payload['sqs_error'] = str(e)
    else:
        # Skip SQS for: failures, BLANK, LINK_ONLY, or non-extractable categories
        if meta_dict.get('processing_failed', False):
            logger.warning(f"Skipping SQS send for {folder_path} due to classification failure")
            payload['sqs_skipped'] = True
        else:
            category = meta_dict.get('category', 'UNKNOWN')
            logger.info(f"Skipping SQS send for {folder_path} - category {category} doesn't require extraction")
            payload['sqs_skipped_no_extraction'] = True

        # 7. Save to S3: failures + non-extractable valid documents
        save_processing_to_s3(classification_result, folder_path, meta_dict, raw_responses, "classification")

    return payload

def validate_s3_key(key):
    """
    Validate that the S3 key follows the expected pattern.
    Expected pattern: path/to/document_number/filename.pdf
    """
    # Check if it's a PDF file
    if not key.lower().endswith('.pdf'):
        return False, "Not a PDF file"

    # Check if it contains a document number folder (6+ digits)
    match = re.search(r'/(\d{6,})/', key)
    if not match:
        return False, "No document number folder found in path"

    return True, match.group(1)  # Return document number

def process_single_s3_record(s3_record, message_id, s3_client, dynamodb_client):
    """
    Process a single S3 record from SQS message.
    Returns result dict and whether message should be marked as failed.
    """
    bucket = s3_record['s3']['bucket']['name']
    key = unquote_plus(s3_record['s3']['object']['key'])
    logger.info(f"Processing S3 object: s3://{bucket}/{key}")

    # Validate the key structure
    is_valid, doc_number_or_error = validate_s3_key(key)
    if not is_valid:
        logger.error(f"Invalid S3 key: {key}. Error: {doc_number_or_error}")
        return {
            'messageId': message_id,
            'key': key,
            'status': 'error',
            'error': doc_number_or_error
        }, True

    # Use the S3 key as the folder path
    folder_path = f"s3://{bucket}/{key}"

    # DynamoDB-based exactly-once processing: Attempt to acquire atomic lock
    lock_acquired, lock_reason = acquire_processing_lock(dynamodb_client, folder_path, s3_client)
    if not lock_acquired:
        logger.info(f"Skipping file (lock not acquired): {key} - {lock_reason}")
        return {
            'messageId': message_id,
            'key': key,
            'status': 'skipped',
            'reason': 'lock_not_acquired',
            'details': lock_reason
        }, False

    processing_success = False
    try:
        # Get the PDF from S3
        response = s3_client.get_object(Bucket=bucket, Key=key)
        pdf_bytes = response['Body'].read()

        # Process the PDF
        payload = process_pdf(pdf_bytes, folder_path)
        result = {
            'messageId': message_id,
            'key': key,
            'status': 'success',
            'payload': payload
        }
        processing_success = True
        logger.info(f"Successfully processed S3 object: {key}")
        return result, False

    except Exception as e:
        logger.error(f"Error processing S3 object {key}: {str(e)}")
        result = {
            'messageId': message_id,
            'key': key,
            'status': 'error',
            'error': str(e)
        }
        processing_success = False
        return result, True

    finally:
        # Always release the lock, regardless of processing outcome
        try:
            release_processing_lock(dynamodb_client, folder_path, s3_client, processing_success)
        except Exception as lock_error:
            logger.warning(f"Failed to release processing lock for {key}: {str(lock_error)}")

def process_sqs_message(sqs_record, s3_client, dynamodb_client):
    """
    Process a single SQS message containing S3 events.
    Returns list of results and list of failed message IDs.
    """
    message_id = sqs_record.get('messageId', 'unknown')
    results = []
    failed_message_ids = []

    try:
        # Parse S3 event from SQS message body
        s3_event = json.loads(sqs_record['body'])
        logger.info(f"Processing SQS message {message_id} containing S3 event")

        # Process each S3 record within the message
        for s3_record in s3_event.get('Records', []):
            if s3_record.get('eventSource') != 'aws:s3':
                logger.warning(f"Skipping non-S3 record in message {message_id}")
                continue

            result, should_fail = process_single_s3_record(s3_record, message_id, s3_client, dynamodb_client)
            results.append(result)

            if should_fail:
                failed_message_ids.append(message_id)

    except Exception as e:
        logger.error(f"Error processing SQS message {message_id}: {str(e)}")
        results.append({
            'messageId': message_id,
            'status': 'error',
            'error': f"Failed to parse SQS message: {str(e)}"
        })
        failed_message_ids.append(message_id)

    return results, failed_message_ids

def calculate_processing_stats(results, failed_message_ids, total_messages):
    """Calculate processing statistics."""
    successful_processing = len([r for r in results if r.get('status') == 'success'])
    skipped_lock_not_acquired = len([r for r in results if r.get('status') == 'skipped'])
    failed_processing = len(failed_message_ids)

    return {
        'totalMessages': total_messages,
        'successfulProcessing': successful_processing,
        'skippedLockNotAcquired': skipped_lock_not_acquired,
        'failedProcessing': failed_processing,
        'exactlyOnceEffective': skipped_lock_not_acquired > 0
    }

def handler(event, context):
    """
    Lambda handler function for SQS batch processing of S3 events.
    """
    try:
        logger.info(f"Received SQS batch event with {len(event.get('Records', []))} messages")
        logger.info(f"Event details: {json.dumps(event, indent=2)}")

        # Handle SQS batch event
        if 'Records' not in event:
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'error': 'Not an SQS batch event or missing Records'
                })
            }

        # Create AWS clients
        s3_client = create_s3_client()
        dynamodb_client = create_dynamodb_client()

        # Process all SQS messages
        all_results = []
        all_failed_message_ids = []

        for sqs_record in event['Records']:
            if sqs_record.get('eventSource') != 'aws:sqs':
                logger.warning(f"Skipping non-SQS event: {sqs_record.get('eventSource')}")
                continue

            results, failed_message_ids = process_sqs_message(sqs_record, s3_client, dynamodb_client)
            all_results.extend(results)
            all_failed_message_ids.extend(failed_message_ids)

        # Calculate processing statistics
        total_messages = len(event['Records'])
        stats = calculate_processing_stats(all_results, all_failed_message_ids, total_messages)

        # Build response
        response = {
            'statusCode': 200,
            'body': json.dumps({
                'results': all_results,
                'summary': stats
            })
        }

        # Add batch item failures for SQS to retry failed messages
        if all_failed_message_ids:
            response['batchItemFailures'] = [{'itemIdentifier': msg_id} for msg_id in all_failed_message_ids]
            logger.warning(f"Batch processing completed with {stats['failedProcessing']} failed messages")

        # Log processing summary
        logger.info(f"Batch processing summary: {stats['totalMessages']} total, {stats['successfulProcessing']} processed, {stats['skippedLockNotAcquired']} skipped (lock not acquired), {stats['failedProcessing']} failed")

        if stats['skippedLockNotAcquired'] > 0:
            logger.info(f"DynamoDB-based exactly-once processing was effective: {stats['skippedLockNotAcquired']} files skipped (already being processed)")

        if stats['failedProcessing'] == 0:
            logger.info(f"Batch processing completed successfully for all {stats['totalMessages']} messages")

        return response

    except Exception as e:
        logger.error(f"Error processing SQS batch: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e)
            })
        }