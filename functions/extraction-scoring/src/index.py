"""
Extraction-scoring Lambda for document data extraction using Bedrock models.

This module processes documents from SQS queue, extracts structured data using AI models,
and saves results to S3. Implements fallback-first processing and SOLID principles.

Flow:
1. handler() - Main entry point
2. Event validation and SQS record parsing
3. Request building (prompts, S3 access, parameters)
4. Model processing with fallback logic
5. S3 persistence (success or failure)
6. Error handling and fallback queue

Architecture: Follows SOLID principles with single-responsibility functions
"""

import json
import logging
import os
import boto3
import re
from pathlib import Path
from typing import Dict, Any, Tuple, List

from shared.helper import load_env
from shared.bedrock_client import create_bedrock_client, set_model_params, converse_with_nova, NovaRequest, parse_extraction_response, create_payload_data_extraction
from shared.pdf_processor import create_message
from shared.sqs_handler import build_folder_path, send_to_fallback_queue_extraction
from shared.prompts import get_instructions_extraction, build_user_prompt_extraction, build_system_prompt_extraction
from shared.s3_handler import save_to_s3, get_pdf_from_s3, extract_s3_path
from shared.processing_result import ProcessingResult, save_processing_to_s3, extract_original_category_from_path

# =============================================================================
# CONFIGURATION & SETUP
# =============================================================================

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Load environment variables
load_env()

# Environment variables
S3_ORIGIN_BUCKET = os.environ.get("S3_ORIGIN_BUCKET")
FALLBACK_SQS = os.environ.get("FALLBACK_SQS")
DESTINATION_BUCKET = os.environ.get("DESTINATION_BUCKET")
BEDROCK_MODEL = os.environ.get("BEDROCK_MODEL")
FALLBACK_MODEL = os.environ.get("FALLBACK_MODEL")
REGION = os.environ.get("REGION", "us-east-1")
FOLDER_PREFIX = os.environ.get("FOLDER_PREFIX")

# Create clients
bedrock_client = create_bedrock_client()

# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def handler(event, context):
    """
    Lambda handler for extraction-scoring service.
    SRP: Single responsibility for event orchestration and error handling.

    Args:
        event: The event dict containing the SQS message
        context: Lambda context object

    Returns:
        dict: Response with status code and message
    """
    try:
        logger.info(f"Received SQS batch event with {len(event.get('Records', []))} messages")
        logger.info(f"Received extraction-scoring event: {json.dumps(event)}")

        # Validate event and extract records
        records = _validate_sqs_event(event)

        # Process each record
        for record in records:
            try:
                # Extract payload from record
                payload = _extract_payload_from_record(record)
                logger.info(f"Processing payload: {json.dumps(payload, indent=2)}")

                # Process the extraction request
                _process_single_extraction_request(payload)

            except json.JSONDecodeError:
                logger.warning(f"Non-JSON payload received: {record['body']}")
            except ValueError as ve:
                logger.warning(f"Invalid record: {str(ve)}")
            except Exception as e:
                logger.error(f"Error processing record: {str(e)}")
                # Send to fallback queue if possible
                try:
                    payload = json.loads(record['body'])
                    send_to_fallback_queue_extraction(payload)
                except:
                    pass

        return {
            "statusCode": 200,
            "body": json.dumps({"message": "Processing completed"})
        }

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
# EVENT PROCESSING - HIGH LEVEL ORCHESTRATION
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

def _process_single_extraction_request(payload: Dict[str, Any]) -> None:
    """
    Process a single extraction request with fallback logic.
    SRP: Single responsibility for single document extraction orchestration.
    """
    # Build extraction request
    request_data = _build_extraction_request(payload)
    fallback_used_in_classification = payload.get('fallback_used', False)

    # Determine model order
    first_model, second_model = _determine_model_order(fallback_used_in_classification)

    # Try with first model
    first_result, first_raw = process_document_with_model(
        model_id=first_model,
        req_params=request_data['req_params'],
        source_key=request_data['source_key'],
        category=request_data['category'],
        document_number=request_data['document_number'],
        pdf_path=request_data['pdf_path']
    )

    # Collect raw responses
    raw_responses = [first_raw] if first_raw else []

    # If first model succeeds, we're done
    if first_result.is_success:
        logger.info(f"Successfully processed with first model: {first_result.model_used}")
        return

    # Try second model if available
    if second_model:
        logger.info(f"Trying second model: {second_model} due to: {first_result.status}")
        second_result, second_raw = process_document_with_model(
            model_id=second_model,
            req_params=request_data['req_params'],
            source_key=request_data['source_key'],
            category=request_data['category'],
            document_number=request_data['document_number'],
            pdf_path=request_data['pdf_path']
        )

        if second_raw:
            raw_responses.append(second_raw)

        if second_result.is_success:
            logger.info(f"Successfully processed with second model: {second_result.model_used}")
            return
    else:
        second_result = None

    # Both models failed
    _handle_extraction_failure(first_result, second_result, payload, raw_responses)

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

    # Extract bucket and key from S3 URI (no download needed with S3 direct access)
    source_bucket, source_key = extract_s3_path(pdf_path)
    logger.info(f"Using S3 direct access for {pdf_path} (optimized - no download needed)")

    # Build the prompts
    task_root = os.environ.get("LAMBDA_TASK_ROOT", os.getcwd())
    schema_path = os.path.join(task_root, f"shared/evaluation_type/{category}/schema.json")
    examples_dir = os.path.join(task_root, f"shared/evaluation_type/{category}/examples")

    user_message = build_user_prompt_extraction(
        pdf_path=pdf_path,
        document_number=document_number,
        document_type=document_type,
        category=category,
        system_p="system",
        user_p="user"
    )

    system_message = build_system_prompt_extraction(
        schema_path=schema_path,
        examples_dir=examples_dir,
        system_p="system",
        user_p="user",
        category=category
    )

    # Create request parameters using S3 direct access (optimized)
    messages = [create_message(user_message, "user", pdf_path=pdf_path, s3_uri=pdf_path)]
    system_parameter = [{"text": system_message}]
    cfg = set_model_params(BEDROCK_MODEL, 8192, 0.9, 0.1)

    req_params = {
        "model_id": BEDROCK_MODEL,
        "messages": messages,
        "params": {**cfg},
        "system": system_parameter,
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

def _determine_model_order(fallback_used_in_classification: bool) -> tuple[str, str]:
    """
    Determine model processing order based on classification results.
    SRP: Single responsibility for model ordering logic.

    Args:
        fallback_used_in_classification: True if classification used fallback model

    Returns:
        tuple: (first_model, second_model)
    """
    if fallback_used_in_classification and FALLBACK_MODEL:
        # Classification used fallback, try fallback first for extraction
        first_model, second_model = FALLBACK_MODEL, BEDROCK_MODEL
        logger.info(f"Classification used fallback model, trying fallback first for extraction: {first_model}")
    else:
        # Normal order: primary first, then fallback
        first_model, second_model = BEDROCK_MODEL, FALLBACK_MODEL
        logger.info(f"Using normal model order for extraction: {first_model} then {second_model}")

    return first_model, second_model

def process_document_with_model(
    model_id: str,
    req_params: Dict[str, Any],
    source_key: str,
    category: str,
    document_number: str,
    pdf_path: str
) -> tuple[ProcessingResult, dict]:
    """
    Process a document with the specified model.
    SRP: Single responsibility for orchestrating extraction and S3 save.

    Args:
        model_id: The Bedrock model ID to use
        req_params: The request parameters for Bedrock
        source_key: The S3 key of the source PDF
        category: The document category
        document_number: The document number
        pdf_path: The full S3 path to the PDF

    Returns:
        tuple: (ProcessingResult, raw_response_dict)
    """
    # Extract with model
    result, raw_response = _extract_with_single_model(model_id, req_params)

    # If extraction succeeded, save to S3
    if result.is_success:
        _save_successful_extraction(result, source_key, category, document_number)

        # Log success
        model_type = "primary" if model_id == BEDROCK_MODEL else "fallback"
        logger.info(f"Successfully processed document with {model_type} model: {pdf_path}")

    return result, raw_response

def _extract_with_single_model(model_id: str, req_params: Dict[str, Any]) -> tuple[ProcessingResult, Dict[str, Any]]:
    """
    Pure function - call Bedrock and parse response with single model.
    SRP: Single responsibility for Bedrock interaction and parsing.

    Args:
        model_id: The model to use
        req_params: Request parameters (will be modified for this model)

    Returns:
        tuple: (ProcessingResult, raw_response_dict)
    """
    raw_response = None
    try:
        # Recalculate parameters for this specific model
        _recalculate_model_params(req_params, model_id)

        # Call Bedrock
        resp_json = converse_with_nova(NovaRequest(**req_params), bedrock_client)
        logger.info(f"Received response from Bedrock: {json.dumps(resp_json, indent=2)}")

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

# =============================================================================
# MODEL UTILITIES - PARAMETER HANDLING & RESPONSE ENHANCEMENT
# =============================================================================

def _recalculate_model_params(req_params: Dict[str, Any], model_id: str) -> None:
    """
    Recalculate request parameters for a specific model.
    SRP: Single responsibility for parameter format conversion.

    Args:
        req_params: Request parameters dict to modify in-place
        model_id: Target model ID for parameter format
    """
    req_params["model_id"] = model_id

    # Extract parameter values (handle both camelCase and snake_case)
    original_params = req_params.get("params", {})
    max_tokens = original_params.get("maxTokens") or original_params.get("max_tokens", 8192)
    top_p = original_params.get("topP") or original_params.get("top_p", 0.9)
    temperature = original_params.get("temperature", 0.1)

    # Get correct parameter format for this model
    req_params["params"] = set_model_params(model_id, max_tokens, top_p, temperature)

def _enhance_raw_response(resp_json: Dict[str, Any], model_id: str, req_params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enhance raw response with model metadata for S3 persistence.
    SRP: Single responsibility for response enhancement.

    Args:
        resp_json: Original Bedrock response
        model_id: Model that generated the response
        req_params: Request parameters used

    Returns:
        Enhanced response dict with metadata
    """
    enhanced_response = resp_json.copy() if resp_json else {}
    enhanced_response['model_id'] = model_id
    enhanced_response['api_used'] = 'converse'
    enhanced_response['model_params'] = req_params.get('params', {})
    return enhanced_response

# =============================================================================
# S3 PERSISTENCE - SUCCESS & FAILURE HANDLING
# =============================================================================

def _save_successful_extraction(result: ProcessingResult, source_key: str, category: str, document_number: str) -> None:
    """
    Save successful extraction results to S3.
    SRP: Single responsibility for S3 persistence of successful extractions.

    Args:
        result: Successful ProcessingResult with extracted data
        source_key: S3 key of source PDF
        category: Document category
        document_number: Document number
    """
    try:
        data = result.data
        save_results_to_s3(
            data['raw_response'],
            data['meta'],
            data['payload_data'],
            source_key,
            category,
            document_number,
            result.model_used
        )
    except Exception as s3_error:
        logger.warning(f"S3 save failed for {result.model_used} but extraction succeeded: {str(s3_error)}")

def save_results_to_s3(
    resp_json: Dict[str, Any],
    meta: Dict[str, Any],
    payload_data: Dict[str, Any],
    source_key: str,
    category: str,
    document_number: str,
    model_used: str
) -> None:
    """
    Save successful extraction results to S3.

    Args:
        resp_json: The raw response from Bedrock
        meta: The extracted metadata
        payload_data: The processed payload data
        source_key: The S3 key of the source PDF
        category: The document category
        document_number: The document number
        model_used: The model that succeeded
    """
    # Extract filename from the path to create a unique identifier
    filename = Path(source_key).name
    # Remove extension and use as unique identifier
    file_id = Path(filename).stem

    # Create folder paths
    processed_folder = f"{FOLDER_PREFIX}/{category}/{document_number}"
    raw_folder = f"RAW/{category}/{document_number}"

    # Add model information to payload
    enhanced_payload = payload_data.copy()
    enhanced_payload['extraction_model_used'] = model_used
    enhanced_payload['extraction_timestamp'] = resp_json.get('ResponseMetadata', {}).get('HTTPHeaders', {}).get('date')

    # Add model information to raw response
    enhanced_raw = resp_json.copy()
    enhanced_raw['extraction_model_used'] = model_used
    enhanced_raw['file_info'] = {
        'source_key': source_key,
        'category': category,
        'document_number': document_number,
        'file_id': file_id
    }

    # Add model information to meta
    enhanced_meta = meta.copy()
    enhanced_meta['extraction_model_used'] = model_used

    # Save enhanced payload_data to S3 in the processed folder
    payload_destination_key = f"{processed_folder}/{category}_{document_number}_{file_id}.json"
    save_to_s3(enhanced_payload, DESTINATION_BUCKET, payload_destination_key)

    # Save enhanced raw response to S3 in the RAW folder
    resp_json_destination_key = f"{raw_folder}/raw_response_{file_id}.json"
    save_to_s3(enhanced_raw, DESTINATION_BUCKET, resp_json_destination_key)

    # Save enhanced meta data to S3 in the RAW folder
    meta_destination_key = f"{raw_folder}/meta_{file_id}.json"
    save_to_s3(enhanced_meta, DESTINATION_BUCKET, meta_destination_key)

# =============================================================================
# ERROR HANDLING - FAILURE PROCESSING & RECOVERY
# =============================================================================

def _handle_extraction_failure(
    first_result: ProcessingResult,
    second_result: ProcessingResult,
    payload: dict,
    raw_responses: list = None
) -> None:
    """
    Handle extraction failure by logging details, saving to S3, and sending to fallback queue.
    SRP: Single responsibility for failure handling.

    Args:
        first_result: Result from first model attempt
        second_result: Result from second model attempt (or None if not tried)
        payload: Original SQS payload for fallback queue
        raw_responses: List of raw Bedrock responses for S3 persistence
    """
    if second_result:
        # Both models failed - choose better error to report
        better_result = _choose_better_failure_result(first_result, second_result)
        logger.error(f"Both models failed. First: {first_result.status}, Second: {second_result.status}")
        logger.error(f"First error: {first_result.error_message}")
        logger.error(f"Second error: {second_result.error_message}")
        final_result = better_result
    else:
        # Single model failed
        logger.error(f"Extraction failed with {first_result.model_used}: {first_result.status} - {first_result.error_message}")
        final_result = first_result

    # Save extraction failure to S3 using same pattern as classification
    _save_extraction_failure_to_s3(final_result, payload, raw_responses or [])

    # Send to fallback queue
    send_to_fallback_queue_extraction(payload)

def _choose_better_failure_result(result1: ProcessingResult, result2: ProcessingResult) -> ProcessingResult:
    """
    Business rule: which extraction failure is "better" to report.
    SRP: Single responsibility for failure result selection.
    """
    # Same priority as classification: content_filtered > parse_error > model_error
    priority = {'content_filtered': 3, 'parse_error': 2, 'model_error': 1}
    return result2 if priority.get(result2.status, 0) > priority.get(result1.status, 0) else result1

def _save_extraction_failure_to_s3(result: ProcessingResult, payload: dict, raw_responses: list) -> None:
    """
    Save extraction failure to S3 using same pattern as classification.
    SRP: Single responsibility for S3 persistence of extraction failures.

    Args:
        result: Failed ProcessingResult
        payload: Original SQS payload containing document info
        raw_responses: List of raw Bedrock responses
    """
    try:
        # Extract document info from payload
        pdf_path = payload.get('path', 'UNKNOWN')
        document_number = payload.get('document_number', 'UNKNOWN')
        category = payload.get('category', 'UNKNOWN')

        # Build metadata dict for S3 persistence (same format as classification)
        meta_dict = {
            'document_number': document_number,
            'category': category,
            'path': pdf_path,
            'error': result.error_message,
            'status': result.status,
            'processing_failed': True,
            'model_used': result.model_used,
            'process_type': 'extraction'  # Key difference from classification
        }

        # Save to S3 - this will create: /errors/extraction/{category}/{document_number}/
        save_processing_to_s3(
            result=result,
            folder_path=pdf_path,
            meta_dict=meta_dict,
            raw_bedrock_responses=raw_responses,
            process_type="extraction"  # This creates extraction error folders
        )

        logger.info(f"Saved extraction failure to S3: {category}/{document_number} (model: {result.model_used}, status: {result.status})")

    except Exception as e:
        logger.error(f"Failed to save extraction failure to S3: {str(e)}")
        # Don't re-raise - S3 persistence failure shouldn't break the main flow