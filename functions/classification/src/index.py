import json, logging, os, re
from urllib.parse import unquote_plus
from collections import namedtuple
from datetime import datetime, timezone
from typing import List, Dict, Any, Tuple
from pathlib import Path
import time

from shared.sqs_handler import build_payload, send_to_extraction_queue
from shared.s3_handler import save_to_s3
from shared.processing_result import save_processing_to_s3
from shared.idempotency_handler import acquire_processing_lock, release_processing_lock
from shared.aws_clients import create_s3_client, create_dynamodb_client
from shared.result_builder import result_to_dict, build_document_info, build_model_info
from shared.bedrock_client import (
    create_bedrock_client, set_model_params_anthropic,set_model_params_converse, call_bedrock_unified, 
    parse_classification, BedrockRequest, is_anthropic_model
)
from shared.pdf_processor import get_first_pdf_page, detect_scanned_pdf, create_message, download_pdf_from_s3
from shared.prompt_loader import prompt_loader
from shared.report_generator import report_generator

# Categories that require extraction processing
EXTRACTABLE_CATEGORIES = {'CERL', 'CECRL', 'RUT', 'RUB', 'ACC'}
FOLDER_PREFIX = os.environ.get("FOLDER_PREFIX", "par-servicios-poc")
DESTINATION_BUCKET = os.environ.get("DESTINATION_BUCKET")
# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Result Pattern - Explicit handling of all classification outcomes
ClassificationResult = namedtuple('ClassificationResult', [
    'is_success',        # bool - True if we got a valid classification
    'data',              # dict | None - parsed classification data
    'status',            # str - 'success' | 'content_filtered' | 'parse_error' | 'model_error'
    'error_message',     # str | None - error details for logging
    'model_used'         # str - which model was used
])

def _save_successful_classification(classification_data: Dict[str, Any], 
                                   source_key: str, category: str, 
                                   document_number: str, model_used: str,
                                   raw_response: Dict[str, Any] = None,
                                   processing_time: float = None) -> None:
    """
    Save successful classification results to S3 - FORMATO LIMPIO similar a extraction.
    """
    try:
        # Extract filename from the path to create a unique identifier
        filename = Path(source_key).name
        file_id = Path(filename).stem
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Create folder path para classification
        classification_folder = f"{FOLDER_PREFIX}/classification/{category}/{document_number}"
        raw_folder = f"RAW/{category}/{document_number}"
        
        # Crear estructura limpia similar a extraction meta
        clean_classification = {
            "result": {
                "DocumentCategory": classification_data.get('category', 'UNKNOWN'),
                "DocumentType": "document",  # o el tipo específico si lo tienes
                "DocumentNumber": document_number,
                "OriginalCategory": category,
                "ProcessingStatus": "success",
                "RequiresExtraction": classification_data.get('requires_extraction', False),
                "Text": classification_data.get('text', '')  # ✅ SÍ incluir el texto del LLM
            },
            # ✅ Eliminar campos redundantes fuera de result
            "classification_model_used": model_used,
            "method_used": f"pdf_claude_{model_used}",
            "processing_time_seconds": processing_time,
            "classification_timestamp": raw_response.get('ResponseMetadata', {}).get('HTTPHeaders', {}).get('date') if raw_response else None,
            "file_info": {
                "source_key": source_key,
                "category": category,
                "document_number": document_number,
                "file_id": file_id
            }
        }
        # Crear raw response mejorado con metadata
        enhanced_raw = raw_response.copy() if raw_response else {}
        enhanced_raw['classification_model_used'] = model_used
        enhanced_raw['method_used'] = f"pdf_claude_{model_used}"
        enhanced_raw['processing_time_seconds'] = processing_time
        enhanced_raw['file_info'] = {
            'source_key': source_key,
            'category': category,
            'document_number': document_number,
            'file_id': file_id
        }

        # Guardar solo el archivo limpio de classification
        classification_destination_key = f"{classification_folder}/classification_{file_id}_{timestamp}.json"
        save_to_s3(clean_classification, DESTINATION_BUCKET, classification_destination_key)
        raw_destination_key = f"{raw_folder}/raw_classification_{file_id}_{timestamp}.json"
        save_to_s3(enhanced_raw, DESTINATION_BUCKET, raw_destination_key)
        
        logger.info(f"Successfully saved clean classification to S3:")
        logger.info(f"  - Classification: classification/{category}/{document_number}/classification_{file_id}.json")
        logger.info(f"  - Raw Response: RAW/{category}/{document_number}/raw_response_{file_id}.json")
    except Exception as e:
        logger.warning(f"S3 save failed for {model_used} but classification succeeded: {str(e)}")



def classify_single_document(s3_record: Dict[str, Any], message_id: str, 
                           s3_client, dynamodb_client, bedrock_client) -> Dict[str, Any]:
    """
    Classify a single document using only primary model with PDF.
    Simplified version - no fallback models or PyPDF fallback.
    
    Args:
        s3_record: S3 event record
        message_id: SQS message ID
        s3_client: S3 client
        dynamodb_client: DynamoDB client
        bedrock_client: Bedrock client
        
    Returns:
        dict: Classification result with metadata
    """
    start_time = time.time()
    bucket = s3_record['s3']['bucket']['name']
    key = unquote_plus(s3_record['s3']['object']['key'])
    pdf_path = f"s3://{bucket}/{key}"
    
    logger.info(f"Classifying document: {pdf_path}")
    
    # Validate S3 key structure
    is_valid, doc_number_or_error = validate_s3_key(key)
    if not is_valid:
        logger.error(f"Invalid S3 key: {key}. Error: {doc_number_or_error}")
        return {
            'success': False,
            'document_info': build_document_info(pdf_path, s3_record),
            'error': doc_number_or_error,
            'status': 'invalid_key'
        }
    
    # DynamoDB-based exactly-once processing
    lock_acquired, lock_reason = acquire_processing_lock(dynamodb_client, pdf_path, s3_client)
    if not lock_acquired:
        logger.info(f"Skipping file (lock not acquired): {key} - {lock_reason}")
        return {
            'success': False,
            'document_info': build_document_info(pdf_path, s3_record),
            'status': 'lock_not_acquired',
            'reason': lock_reason
        }
    
    processing_success = False
    try:
        # Load prompts
        system_prompt, user_prompt = prompt_loader.get_classification_prompts()
        
        # Get only primary model
        primary_model = os.environ.get("BEDROCK_MODEL")
        logger.info(f"Using primary model: {primary_model}")
        
        # Try classification with primary model only
        classification_result, raw_response = try_single_model_classification(
            bedrock_client, primary_model, user_prompt, system_prompt, pdf_path
        )
        
        processing_time = time.time() - start_time
        
        # Build document and model info
        document_info = build_document_info(pdf_path, s3_record)
        model_info = build_model_info(
            classification_result.model_used, 
            'converse' if not is_anthropic_model(classification_result.model_used) else 'invoke_model',
            raw_response,
            {'processing_time': processing_time}
        )
        
        # Convert result to dict for backward compatibility
        meta_dict = result_to_dict(classification_result, pdf_path, [raw_response] if raw_response else [], EXTRACTABLE_CATEGORIES)
        
        # Add method_used and processing_time to meta_dict
        meta_dict['method_used'] = f"pdf_claude_{classification_result.model_used}"
        meta_dict['processing_time_seconds'] = processing_time
        
        # Save detailed result to S3
        if classification_result.is_success:
            _save_successful_classification(
                meta_dict, 
                document_info['s3_key'], 
                meta_dict.get('category', 'UNKNOWN'),
                meta_dict.get('document_number', 'UNKNOWN'),
                classification_result.model_used,
                raw_response,
                processing_time
            )
        else:
            # Save failed classification using existing processing result system
            save_processing_to_s3(classification_result, pdf_path, meta_dict, [raw_response] if raw_response else [], "classification")
        
        processing_success = classification_result.is_success
        
        return {
            'success': classification_result.is_success,
            'messageId': message_id,
            'document_info': document_info,
            'classification_result': meta_dict,
            'model_info': model_info,
            'requires_extraction': meta_dict.get('requires_extraction', False),
            'category': meta_dict.get('category', 'UNKNOWN')
        }
        
    except Exception as e:
        logger.error(f"Error classifying document {key}: {str(e)}")
        return {
            'success': False,
            'document_info': build_document_info(pdf_path, s3_record),
            'error': str(e),
            'status': 'processing_error'
        }
    
    finally:
        # Always release the lock
        try:
            release_processing_lock(dynamodb_client, pdf_path, s3_client, processing_success)
        except Exception as lock_error:
            logger.warning(f"Failed to release processing lock for {key}: {str(lock_error)}")

def try_single_model_classification(bedrock_client, model_id: str, user_prompt: str, 
                                  system_prompt: str, pdf_path: str) -> Tuple[ClassificationResult, Dict]:
    """
    Attempt classification with a single model using unified API.
    Simplified version - no PyPDF fallback.
    
    Args:
        bedrock_client: Bedrock client
        model_id: Model ID to use
        user_prompt: User prompt text
        system_prompt: System prompt text
        pdf_path: S3 folder path
        
    Returns:
        tuple: (ClassificationResult, raw_response_dict)
    """
    raw_response = None
    try:
        # Create messages using S3 direct access (optimized)
        pdf_bytes = download_pdf_from_s3(pdf_path)
        if pdf_bytes is None:
            logger.error(f"Failed to download PDF: {pdf_path}")
            return ClassificationResult(
                is_success=False,
                data=None,
                status='model_error',
                error_message="Failed to download PDF from S3",
                model_used=model_id
            ), None
            
        pdf_bytes = get_first_pdf_page(pdf_bytes)
        messages = [create_message(user_prompt, "user", pdf_bytes=pdf_bytes, pdf_path=pdf_path, model_id=model_id)]

        if is_anthropic_model(model_id):
            params = set_model_params_anthropic(9000, 1, 1)
            request = BedrockRequest(
                model_id= model_id,
                messages=messages,
                params=params,
            )
        else:
            params = set_model_params_converse(8000, 1, 0)
            request = BedrockRequest(
                model_id=model_id,
                messages=messages,
                params=params,
                system=[
                    {"text": system_prompt},
                    {"cachePoint": {"type": "default"}}
                ]
            )
        # Call unified Bedrock API
        raw_response = call_bedrock_unified(request, bedrock_client)
        logger.info(f"Response from Bedrock ({model_id}): stopReason={raw_response.get('stopReason')}")
        
        # Handle content filtering as business outcome
        if raw_response.get('stopReason') == 'content_filtered':
            return ClassificationResult(
                is_success=False,
                data=None,
                status='content_filtered',
                error_message=f"Content filtered by guardrails in model {model_id}",
                model_used=model_id
            ), raw_response
        
        # Try to parse classification
        try:
            data = parse_classification(raw_response, pdf_path=pdf_path)
            return ClassificationResult(
                is_success=True,
                data=data,
                status='success',
                error_message=None,
                model_used=model_id
            ), raw_response
        except Exception as parse_error:
            return ClassificationResult(
                is_success=False,
                data=None,
                status='parse_error',
                error_message=f"Failed to parse response from {model_id}: {str(parse_error)}",
                model_used=model_id
            ), raw_response
            
    except Exception as model_error:
        logger.error(f"Model {model_id} failed: {str(model_error)}")
        return ClassificationResult(
            is_success=False,
            data=None,
            status='model_error',
            error_message=f"Model {model_id} failed: {str(model_error)}",
            model_used=model_id
        ), raw_response

def validate_s3_key(key):
    """Validate that the S3 key follows the expected pattern."""
    if not key.lower().endswith('.pdf'):
        return False, "Not a PDF file"
    
    match = re.search(r'/(\d{6,})/', key)
    if not match:
        return False, "No document number folder found in path"
    
    return True, match.group(1)

def process_batch_classification(sqs_records: List[Dict], s3_client, dynamodb_client, bedrock_client) -> Tuple[List[Dict], List[str]]:
    """Process SQS batch with throttling control"""
    batch_delay = float(os.environ.get('BATCH_PROCESSING_DELAY', '2.0'))
    
    # PHASE 1: Collect documents
    all_documents = []
    message_map = {}
    
    for sqs_record in sqs_records:
        message_id = sqs_record.get('messageId', 'unknown')
        if sqs_record.get('eventSource') != 'aws:sqs':
            continue
        
        try:
            s3_event = json.loads(sqs_record['body'])
            for s3_record in s3_event.get('Records', []):
                if s3_record.get('eventSource') == 'aws:s3':
                    all_documents.append(s3_record)
                    message_map[id(s3_record)] = message_id
        except Exception as e:
            logger.error(f"Error parsing SQS message {message_id}: {str(e)}")
    
    logger.info(f"PHASE 1: Processing {len(all_documents)} documents with {batch_delay}s delays")
    
    # PHASE 2: Classify with delays
    classification_results = []
    for i, doc in enumerate(all_documents):
        if i > 0:
            logger.info(f"Adding {batch_delay}s delay before document {i+1}")
            time.sleep(batch_delay)
        
        message_id = message_map.get(id(doc), 'unknown')
        result = classify_single_document(doc, message_id, s3_client, dynamodb_client, bedrock_client)
        classification_results.append(result)
    
    # PHASE 3: Send to extraction (existing logic)
    successful_extractions = 0
    failed_message_ids = []
    
    for result in classification_results:
        if result.get('success') and result.get('requires_extraction'):
            try:
                payload = build_payload(result['classification_result'])
                payload['path'] = result['document_info']['path']
                payload['fallback_used'] = result['classification_result'].get('fallback_used', False)
                
                send_to_extraction_queue(payload)
                successful_extractions += 1
            except Exception as e:
                logger.error(f"Failed to send to extraction queue: {str(e)}")
                if 'messageId' in result:
                    failed_message_ids.append(result['messageId'])
    
    # Convert results
    results = []
    for result in classification_results:
        results.append({
            'messageId': result.get('messageId', 'unknown'),
            'key': result['document_info'].get('s3_key', 'unknown'),
            'status': 'success' if result.get('success') else 'error',
            'payload': result.get('classification_result') if result.get('success') else None,
            'error': result.get('error') if not result.get('success') else None
        })
    
    return results, failed_message_ids

def handler(event, context):
    """
    Lambda handler function for SQS batch processing of S3 events with simplified processing.
    Only uses primary model - no fallback models or PyPDF fallback.
    """
    try:
        logger.info(f"Received SQS batch event with {len(event.get('Records', []))} messages")
        
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
        bedrock_client = create_bedrock_client()
        
        # Process batch in 2 phases
        results, failed_message_ids = process_batch_classification(
            event['Records'], s3_client, dynamodb_client, bedrock_client
        )
        
        # Calculate statistics
        total_messages = len(event['Records'])
        successful_processing = len([r for r in results if r.get('status') == 'success'])
        skipped_lock_not_acquired = len([r for r in results if r.get('status') == 'skipped'])
        failed_processing = len(failed_message_ids)
        
        stats = {
            'totalMessages': total_messages,
            'successfulProcessing': successful_processing,
            'skippedLockNotAcquired': skipped_lock_not_acquired,
            'failedProcessing': failed_processing,
            'exactlyOnceEffective': skipped_lock_not_acquired > 0,
            'processingMode': 'simplified_primary_model_only'
        }
        
        # Build response
        response = {
            'statusCode': 200,
            'body': json.dumps({
                'results': results,
                'summary': stats
            })
        }
        
        # Add batch item failures for SQS retry
        if failed_message_ids:
            response['batchItemFailures'] = [{'itemIdentifier': msg_id} for msg_id in failed_message_ids]
            logger.warning(f"Batch processing completed with {failed_processing} failed messages")
        
        logger.info(f"Batch processing summary: {successful_processing} successful, {failed_processing} failed")
        
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