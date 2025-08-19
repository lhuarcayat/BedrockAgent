"""
Bedrock model classification logic.

This module handles all AI model interactions for document classification,
including setup, API calls, fallback logic, and result processing.
"""

import os
import logging
from shared.pdf_processor import detect_scanned_pdf, get_first_pdf_page, create_message
from shared.bedrock_client import create_bedrock_client, set_model_params, converse_with_nova, parse_classification, NovaRequest
from shared.prompts import get_instructions, add_now_process

logger = logging.getLogger(__name__)

def setup_classification_request(pdf_bytes=None, folder_path=None, s3_uri=None):
    """
    Prepare everything needed for classification.
    Returns bedrock client, messages, system parameter, and model config.
    
    Args:
        pdf_bytes: PDF content as bytes (legacy approach)
        folder_path: S3 folder path for naming
        s3_uri: S3 URI for direct access (preferred)
    """
    # Bedrock setup
    bedrock = create_bedrock_client()

    # Prompts and messages
    user_prompt = get_instructions("user") + add_now_process(folder_path)
    logger.info(f"User prompt: {user_prompt}")
    system_prompt = get_instructions("system")

    # Debug system prompt
    logger.info(f"System prompt type: {type(system_prompt)}, length: {len(system_prompt) if system_prompt else 0}")
    logger.info(f"System prompt preview: {system_prompt[:100] if system_prompt else 'None'}...")

    system_parameter = [{"text": system_prompt}]
    logger.info(f"System parameter structure: {system_parameter}")

    # Create messages with S3 direct access support
    if s3_uri:
        # Optimized: use S3 direct access (no PDF processing needed)
        messages = [create_message(user_prompt, "user", pdf_path=folder_path, s3_uri=s3_uri)]
        logger.info(f"Using S3 direct access for classification: {s3_uri} (optimized)")
    else:
        # Fallback: use bytes with PDF processing
        first_page = get_first_pdf_page(pdf_bytes)
        is_scanned = detect_scanned_pdf(pdf_bytes)
        logger.info(f"PDF type detected: {'scanned image' if is_scanned else 'has text'}")
        messages = [create_message(user_prompt, "user", first_page, folder_path)]
        logger.info(f"Using bytes approach with first page extraction (fallback)")
    
    # Model configuration
    models = {
        'primary': os.environ.get("BEDROCK_MODEL"),
        'fallback': os.environ.get("FALLBACK_MODEL"),
        'params': {'temperature': 0.1, 'top_p': 0.9, 'max_tokens': 8192}
    }

    return bedrock, messages, system_parameter, models

def call_bedrock_model(bedrock, model_id, messages, system_parameter, cfg_params):
    """
    Call Bedrock Converse API for any model.
    Returns raw response with enhanced metadata.
    """
    req_params = NovaRequest(
        model_id=model_id,
        messages=messages,
        params=cfg_params,
        system=system_parameter
    )

    logger.info(f"Using Converse API for model: {model_id}")
    response = converse_with_nova(req_params, bedrock)

    # Enhance response with model and API metadata
    if response and isinstance(response, dict):
        response['model_id'] = model_id
        response['api_used'] = 'converse'
        response['model_params'] = cfg_params

    return response

def try_single_model(bedrock, model_id, messages, system_parameter, params, folder_path, ClassificationResult):
    """
    Attempt classification with a single model.
    Returns (ClassificationResult, raw_response_dict).
    """
    raw_response = None
    try:
        cfg_params = set_model_params(model_id, **params)
        logger.info(f"Attempting classification with model: {model_id} (params: {cfg_params})")
        
        raw_response = call_bedrock_model(bedrock, model_id, messages, system_parameter, cfg_params)
        logger.info(f"Response from Bedrock ({model_id}): {raw_response}")

        # Handle stopReason as business outcomes, not exceptions
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
            data = parse_classification(raw_response, pdf_path=folder_path)
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
        return ClassificationResult(
            is_success=False,
            data=None,
            status='model_error',
            error_message=f"Model {model_id} failed: {str(model_error)}",
            model_used=model_id
        ), raw_response

def should_retry_with_fallback(result):
    """
    Business rule: when to try fallback model.
    """
    return result.status in {'content_filtered', 'parse_error', 'model_error'}

def choose_better_result(result1, result2):
    """
    Business rule: which failure is "better" to report.
    Preference order: content_filtered > parse_error > model_error
    """
    priority = {'content_filtered': 3, 'parse_error': 2, 'model_error': 1}
    return result2 if priority.get(result2.status, 0) > priority.get(result1.status, 0) else result1

def log_classification_result(result, attempt_type):
    """
    Log classification result with appropriate log level.
    """
    model_info = f"{attempt_type} model ({result.model_used})"

    if result.is_success:
        logger.info(f"{model_info} succeeded")
    elif result.status == 'content_filtered':
        logger.info(f"{model_info} content filtered: {result.error_message}")
    elif result.status == 'parse_error':
        logger.warning(f"{model_info} parse error: {result.error_message}")
    elif result.status == 'model_error':
        logger.error(f"{model_info} model error: {result.error_message}")

def classify_with_fallback(bedrock, messages, system_parameter, models, folder_path, ClassificationResult):
    """
    Handle classification with fallback logic.
    Returns (ClassificationResult, list_of_raw_responses).
    """
    raw_responses = []

    # Try primary model first
    primary_result, primary_raw = try_single_model(
        bedrock, models['primary'], messages, system_parameter, models['params'], folder_path, ClassificationResult
    )

    if primary_raw:
        raw_responses.append(primary_raw)

    log_classification_result(primary_result, "Primary")

    if primary_result.is_success:
        return primary_result, raw_responses

    # Decide if we should try fallback based on error type
    if should_retry_with_fallback(primary_result):
        logger.info(f"Trying fallback model {models['fallback']} due to: {primary_result.status}")

        fallback_result, fallback_raw = try_single_model(
            bedrock, models['fallback'], messages, system_parameter, models['params'], folder_path, ClassificationResult
        )

        if fallback_raw:
            raw_responses.append(fallback_raw)

        log_classification_result(fallback_result, "Fallback")

        # Return best result
        if fallback_result.is_success:
            return fallback_result, raw_responses
        else:
            better_result = choose_better_result(primary_result, fallback_result)
            return better_result, raw_responses

    return primary_result, raw_responses