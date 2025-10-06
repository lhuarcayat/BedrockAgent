"""
Extraction-scoring Lambda for document data extraction using Bedrock models.
SIMPLIFIED VERSION - Only uses primary model with PDF.

This module processes documents from SQS queue, extracts structured data using AI models,
and saves results to S3. Implements 2-phase batch processing and unified API support.

Flow:
1. handler() - Main entry point with 2-phase batch processing
2. Event validation and SQS record parsing
3. PHASE 1: Extract from ALL documents in batch using PRIMARY MODEL ONLY
4. PHASE 2: Save ALL results to S3
5. Error handling and fallback queue

Architecture: Follows SOLID principles with single-responsibility functions
"""

import json
import logging
import os
import boto3
import re
from pathlib import Path
from typing import Dict, Any, Tuple, List
from datetime import datetime, timezone
from shared.aws_clients import create_s3_client
from datetime import datetime, timezone
import time

from shared.bedrock_client import (
    create_bedrock_client, set_model_params_anthropic,set_model_params_converse, parse_extraction_response, create_payload_data_extraction,
    is_anthropic_model, call_bedrock_unified, BedrockRequest
)
from shared.pdf_processor import create_message
from shared.sqs_handler import send_to_fallback_queue_extraction
from shared.s3_handler import save_to_s3, extract_s3_path
from shared.processing_result import ProcessingResult, save_processing_to_s3
from shared.prompt_loader import prompt_loader
from shared.report_generator import report_generator
from shared.result_builder import build_document_info, build_model_info

# =============================================================================
# CONFIGURATION & SETUP
# =============================================================================

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables
primary_model = os.environ.get("BEDROCK_MODEL")
S3_ORIGIN_BUCKET = os.environ.get("S3_ORIGIN_BUCKET")
FALLBACK_SQS = os.environ.get("FALLBACK_SQS")
DESTINATION_BUCKET = os.environ.get("DESTINATION_BUCKET")
REGION = os.environ.get("REGION", "us-east-2")
FOLDER_PREFIX = os.environ.get("FOLDER_PREFIX")

# Create clients
bedrock_client = create_bedrock_client()

# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def handler(event, context):
    """
    Lambda handler for extraction-scoring service with 2-phase batch processing.
    Simplified version - only uses primary model.

    Args:
        event: The event dict containing the SQS message
        context: Lambda context object

    Returns:
        dict: Response with status code and message
    """
    try:
        logger.info(f"Received SQS batch event with {len(event.get('Records', []))} messages")
        
        # Validate event and extract records
        records = _validate_sqs_event(event)
        
        # Process batch in 2 phases
        results, failed_message_ids = process_batch_extraction(records)
        
        # Calculate statistics
        total_messages = len(records)
        successful_processing = len([r for r in results if r.get('success', False)])
        failed_processing = len(failed_message_ids)
        
        stats = {
            'totalMessages': total_messages,
            'successfulProcessing': successful_processing,
            'failedProcessing': failed_processing,
            'processingMode': 'simplified_primary_model_only'
        }
        
        # Build response
        response = {
            "statusCode": 200,
            "body": json.dumps({
                "results": results,
                "summary": stats
            })
        }
        
        # Add batch item failures for SQS retry
        if failed_message_ids:
            response['batchItemFailures'] = [{'itemIdentifier': msg_id} for msg_id in failed_message_ids]
            logger.warning(f"Batch processing completed with {failed_processing} failed messages")
        
        logger.info(f"Batch processing summary: {successful_processing} successful, {failed_processing} failed")
        
        return response

    except ValueError as ve:
        logger.warning(f"Event validation error: {str(ve)}")
        return {
            "statusCode": 400,
            "body": json.dumps({"error": str(ve)})
        }
    except Exception as e:
        logger.error(f"Error processing event: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }

# =============================================================================
# BATCH PROCESSING - 2 PHASE IMPLEMENTATION
# =============================================================================

def process_batch_extraction(records: List[Dict[str, Any]]) -> Tuple[List[Dict], List[str]]:
    """Process extraction batch with throttling control"""
    batch_delay = float(os.environ.get('BATCH_PROCESSING_DELAY', '5.0'))
    
    # PHASE 1: Collect requests
    all_extraction_requests = []
    message_map = {}
    
    for record in records:
        message_id = record.get('messageId', 'unknown')
        try:
            payload = _extract_payload_from_record(record)
            all_extraction_requests.append(payload)
            message_map[id(payload)] = message_id
        except Exception as e:
            logger.error(f"Error extracting payload from message {message_id}: {str(e)}")
    
    logger.info(f"PHASE 1: Processing {len(all_extraction_requests)} extractions with {batch_delay}s delays")
    
    # PHASE 2: Extract with delays
    extraction_results = []
    for i, request in enumerate(all_extraction_requests):
        if i > 0:
            logger.info(f"Adding {batch_delay}s delay before extraction {i+1}")
            time.sleep(batch_delay)
        
        message_id = message_map.get(id(request), 'unknown')
        result = extract_single_document(request, message_id)
        extraction_results.append(result)
    
    # PHASE 3: Handle failures (existing logic)
    failed_message_ids = []
    
    for result in extraction_results:
        if not result.get('success'):
            try:
                original_payload = result.get('original_payload', {})
                if original_payload:
                    send_to_fallback_queue_extraction(original_payload)
            except Exception as e:
                logger.error(f"Failed to send to fallback queue: {str(e)}")
                if 'messageId' in result:
                    failed_message_ids.append(result['messageId'])
    
    # Convert results
    results = []
    for result in extraction_results:
        results.append({
            'messageId': result.get('messageId', 'unknown'),
            'document_number': result['document_info'].get('document_number', 'unknown'),
            'category': result.get('category', 'unknown'),
            'success': result.get('success', False),
            'extraction_data': result.get('extraction_result') if result.get('success') else None,
            'error': result.get('error') if not result.get('success') else None
        })
    
    return results, failed_message_ids

# =============================================================================
# SINGLE DOCUMENT EXTRACTION
# =============================================================================

def extract_single_document(payload: Dict[str, Any], message_id: str) -> Dict[str, Any]:
    """
    Extract data from a single document using only primary model.
    MODIFIED: No guarda errores a S3 - solo envía a fallback queue
    """
    start_time = time.time()
    pdf_path = payload.get('path')
    document_number = payload.get('document_number')
    document_type = payload.get('document_type')
    category = payload.get('category')
    
    logger.info(f"Extracting: {category}/{document_number}")
    
    try:
        # Skip non-extractable categories
        if category in ["BLANK", "LINK_ONLY"]:
            logger.info(f"Skipping extraction for non-extractable category: {category}")
            return {
                'success': True,
                'document_info': build_document_info(pdf_path),
                'category': category,
                'skipped': True,
                'reason': 'Non-extractable category',
                'messageId': message_id
            }
        
        # Build extraction request
        request_data = _build_extraction_request(payload)
        
        # Try extraction with primary model only
        extraction_result, raw_response = _extract_with_single_model(primary_model, request_data['req_params'])
        
        processing_time = time.time() - start_time
        
        # Build document and model info
        document_info = build_document_info(pdf_path)
        model_info = build_model_info(
            extraction_result.model_used,
            'converse' if not is_anthropic_model(extraction_result.model_used) else 'invoke_model',
            raw_response,
            {'processing_time': processing_time}
        )
        
        # Save results
        if extraction_result.is_success:
            # Save successful extraction
            data = extraction_result.data
            _save_successful_extraction(
                data['raw_response'], data['meta'], data['payload_data'],
                request_data['source_key'], category, document_number, extraction_result.model_used,
                processing_time
            )
        else:
            # ✅ CAMBIO: NO guardar error a S3 aquí - solo log para debugging
            logger.info(f"Extraction failed for {category}/{document_number} - will be sent to fallback queue")
            logger.info(f"Failure reason: {extraction_result.status} - {extraction_result.error_message}")
            
            # El fallback lambda se encargará de crear error/ solo si todo falla
        
        return {
            'success': extraction_result.is_success,
            'document_info': document_info,
            'extraction_result': extraction_result.data if extraction_result.is_success else None,
            'model_info': model_info,
            'category': category,
            'error': extraction_result.error_message if not extraction_result.is_success else None,
            'messageId': message_id,
            'original_payload': payload,
            # ✅ Añadir info del fallo para el fallback
            'primary_failure_info': {
                'status': extraction_result.status,
                'error_message': extraction_result.error_message,
                'model_used': extraction_result.model_used,
                'processing_time': processing_time
            } if not extraction_result.is_success else None
        }
        
    except Exception as e:
        logger.error(f"Error in extraction: {str(e)}")
        return {
            'success': False,
            'document_info': build_document_info(pdf_path),
            'category': category,
            'error': str(e),
            'messageId': message_id,
            'original_payload': payload
        }

# =============================================================================
# EVENT PROCESSING - HELPER FUNCTIONS
# =============================================================================

def _validate_sqs_event(event: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Validate SQS event and extract records.
    SRP: Single responsibility for event validation.
    """
    if 'Records' not in event or len(event['Records']) == 0:
        raise ValueError("No records found in event")
    return event['Records']

def _extract_payload_from_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract and validate payload from SQS record.
    SRP: Single responsibility for record parsing.
    """
    if 'body' not in record:
        raise ValueError("SQS record missing body")

    payload = json.loads(record['body'])

    # Extract required fields
    pdf_path = payload.get('path')
    document_number = payload.get('document_number')
    document_type = payload.get('document_type')
    category = payload.get('category')

    if not all([pdf_path, document_number, document_type, category]):
        raise ValueError("Missing required fields in payload")

    return payload

# =============================================================================
# REQUEST BUILDING - PREPARE DATA FOR PROCESSING
# =============================================================================

def _build_extraction_request(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build extraction request from payload.
    SRP: Single responsibility for request preparation.
    """
    pdf_path = payload['path']
    document_number = payload['document_number']
    document_type = payload['document_type']
    category = payload['category']
    model_id = primary_model
    
    # Extract bucket and key from S3 URI
    source_bucket, source_key = extract_s3_path(pdf_path)
    logger.info(f"Building extraction request for {pdf_path}")
    
    # Build the prompts using prompt loader
    system_prompt, user_prompt = prompt_loader.get_extraction_prompts(category)
    
    # Download PDF explicitly for Anthropic models
    pdf_bytes = None
    if is_anthropic_model(model_id):
        logger.info(f"Downloading PDF for Anthropic model: {model_id}")
        try:
            from shared.aws_clients import create_s3_client
            s3_client = create_s3_client()
            response = s3_client.get_object(Bucket=source_bucket, Key=source_key)
            pdf_bytes = response['Body'].read()
            logger.info(f"PDF downloaded successfully: {len(pdf_bytes)} bytes")
        except Exception as e:
            logger.error(f"CRITICAL: Failed to download PDF for Anthropic model: {e}")
            raise RuntimeError(f"Cannot process document - PDF download failed: {e}")
    
    # Create request parameters
    if is_anthropic_model(model_id):
        # Pass downloaded pdf_bytes for Anthropic
        messages = [create_message(user_prompt, "user", pdf_bytes=pdf_bytes, pdf_path=pdf_path, model_id=model_id)]
        params = set_model_params_anthropic(9000, 1, 1)
        req_params = {
            "model_id": model_id,
            "messages": messages,
            "params": params,
        }
    else:
        # For other models (Nova, etc.) use S3 direct access
        messages = [create_message(user_prompt, "user", pdf_path=pdf_path, model_id=model_id)]
        params = set_model_params_converse(2500, 1, 0)
        system = [
            {"text": system_prompt},
            {"cachePoint": {"type": "default"}}
        ]
        req_params = {
            "model_id": model_id,
            "messages": messages,
            "params": params,
            "system": system
        }

    return {
        'req_params': req_params,
        'source_key': source_key,
        'category': category,
        'document_number': document_number,
        'pdf_path': pdf_path
    }


# =============================================================================
# MODEL PROCESSING - CORE EXTRACTION LOGIC
# =============================================================================

def _extract_with_single_model(model_id: str, req_params: Dict[str, Any]) -> tuple[ProcessingResult, dict]:
    """
    Pure function - call Bedrock and parse response with single model.
    SRP: Single responsibility for Bedrock interaction and parsing.
    """
    raw_response = None
    try:
        # Call unified Bedrock API
        resp_json = call_bedrock_unified(BedrockRequest(**req_params), bedrock_client)
        logger.info(f"Received response from Bedrock: stopReason={resp_json.get('stopReason')}")

        # Enhance response with model metadata
        raw_response = _enhance_raw_response(resp_json, model_id, req_params)

        # Handle content filtering as business outcome
        if resp_json.get('stopReason') == 'content_filtered':
            return ProcessingResult(
                is_success=False,
                data=None,
                status='content_filtered',
                error_message=f"Content filtered by guardrails in model {model_id}",
                model_used=model_id
            ), raw_response

        # Try to parse extraction response
        try:
            meta = parse_extraction_response(resp_json)
            logger.info(f"Successfully parsed response: {json.dumps(meta, indent=2)}")
            payload_data = create_payload_data_extraction(meta)

            return ProcessingResult(
                is_success=True,
                data={'meta': meta, 'payload_data': payload_data, 'raw_response': resp_json},
                status='success',
                error_message=None,
                model_used=model_id
            ), raw_response

        except Exception as parse_error:
            return ProcessingResult(
                is_success=False,
                data=None,
                status='parse_error',
                error_message=f"Failed to parse response from {model_id}: {str(parse_error)}",
                model_used=model_id
            ), raw_response

    except Exception as model_error:
        logger.error(f"Model {model_id} failed: {str(model_error)}")
        return ProcessingResult(
            is_success=False,
            data=None,
            status='model_error',
            error_message=f"Model {model_id} failed: {str(model_error)}",
            model_used=model_id
        ), raw_response

def _enhance_raw_response(resp_json: Dict[str, Any], model_id: str, req_params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enhance raw response with model metadata for S3 persistence.
    SRP: Single responsibility for response enhancement.
    """
    enhanced_response = resp_json.copy() if resp_json else {}
    enhanced_response['model_id'] = model_id
    enhanced_response['api_used'] = 'invoke_model' if is_anthropic_model(model_id) else 'converse'
    enhanced_response['model_params'] = req_params.get('params', {})
    return enhanced_response

# =============================================================================
# S3 PERSISTENCE - SUCCESS & FAILURE HANDLING
# =============================================================================

def _save_successful_extraction(resp_json: Dict[str, Any], meta: Dict[str, Any], 
                              payload_data: Dict[str, Any], source_key: str, 
                              category: str, document_number: str, model_used: str,
                              processing_time: float) -> None:
    """
    Save successful extraction results to S3.
    SRP: Single responsibility for S3 persistence of successful extractions.
    """
    try:
        # Extract filename from the path to create a unique identifier
        filename = Path(source_key).name
        file_id = Path(filename).stem
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Create folder paths
        meta_folder = f"{FOLDER_PREFIX}/extraction/{category}/{document_number}"
        raw_folder = f"RAW/{category}/{document_number}"

        # Add model information to meta
        enhanced_meta = meta.copy()
        enhanced_meta['extraction_model_used'] = model_used
        enhanced_meta['method_used'] = f"pdf_claude_{model_used}"
        enhanced_meta['processing_time_seconds'] = processing_time
        enhanced_meta['extraction_timestamp'] = resp_json.get('ResponseMetadata', {}).get('HTTPHeaders', {}).get('date')
        enhanced_meta['file_info'] = {
            'source_key': source_key,
            'category': category,
            'document_number': document_number,
            'file_id': file_id
        }

        # Add model information to raw response
        enhanced_raw = resp_json.copy()
        enhanced_raw['extraction_model_used'] = model_used
        enhanced_raw['method_used'] = f"pdf_claude_{model_used}"
        enhanced_raw['processing_time_seconds'] = processing_time
        enhanced_raw['file_info'] = {
            'source_key': source_key,
            'category': category,
            'document_number': document_number,
            'file_id': file_id
        }

        # Save meta in main location: par-servicios-poc/{category}/{document_number}/
        meta_destination_key = f"{meta_folder}/extraction_{file_id}_{timestamp}.json"
        save_to_s3(enhanced_meta, DESTINATION_BUCKET, meta_destination_key)

        # Save raw_response in RAW folder: RAW/{category}/{document_number}/
        resp_json_destination_key = f"{raw_folder}/raw_extraction_{file_id}_{timestamp}.json"
        save_to_s3(enhanced_raw, DESTINATION_BUCKET, resp_json_destination_key)

        logger.info(f"Successfully saved extraction results to S3:")
        logger.info(f"  - Meta: {category}/{document_number}/extraction_{file_id}.json")
        logger.info(f"  - Raw: RAW/{category}/{document_number}/raw_extraction_{file_id}.json")

    except Exception as e:
        logger.warning(f"S3 save failed for {model_used} but extraction succeeded: {str(e)}")
