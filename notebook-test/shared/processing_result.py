"""
Shared processing result utilities for both classification and extraction Lambdas.
Implements Result Pattern with SOLID principles for consistent error handling and S3 persistence.
"""

import os
import logging
import re
from collections import namedtuple
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta

from .s3_handler import save_to_s3, extract_s3_path

# Configure logging
logger = logging.getLogger(__name__)

# Result Pattern - Explicit handling of all processing outcomes
ProcessingResult = namedtuple('ProcessingResult', [
    'is_success',        # bool - True if we got a valid result
    'data',              # dict | None - parsed result data
    'status',            # str - 'success' | 'content_filtered' | 'parse_error' | 'model_error'
    'error_message',     # str | None - error details for logging
    'model_used'         # str - which model was used
])

def extract_original_category_from_path(folder_path: str) -> str:
    """
    Extract the original category from S3 folder path.
    SRP: Single responsibility for path parsing.
    
    Args:
        folder_path: Original S3 path like "s3://bucket/CECRL/984174004/file.pdf"
        
    Returns:
        str: Original category (CECRL, RUT, etc.) or 'UNKNOWN'
    """
    try:
        # Extract path from S3 URI: s3://bucket/par-servicios-poc/CECRL/984174004/_2022-01-06.pdf
        if folder_path.startswith('s3://'):
            # Remove s3:// and split by /
            path_parts = folder_path[5:].split('/')
            # Find the category part - usually after bucket/prefix
            for i, part in enumerate(path_parts):
                # Look for known categories
                if part in ['CECRL', 'CERL', 'RUT', 'RUB', 'ACC']:
                    return part
        return 'UNKNOWN'
    except:
        return 'UNKNOWN'

def build_s3_folder_structure(result: ProcessingResult, original_category: str, doc_number: str, process_type: str = "classification") -> str:
    """
    Build S3 folder structure based on processing result using original category.
    SRP: Single responsibility for S3 path generation logic.
    OCP: Open for extension (new categories/processes), closed for modification.

    Args:
        result: ProcessingResult
        original_category: Original document category from S3 path (for user identification)
        doc_number: Document number
        process_type: "classification" or "extraction"

    Returns:
        str: folder path for saving files
    """
    if result.is_success:
        # Non-extractable successful documents (BLANK, LINK_ONLY) or successful extractions
        # Use original category so users can identify which folder had the issue
        return f"non_extractable/{process_type}/{original_category}/{doc_number}"
    else:
        # Failed processing (content_filtered, parse_error, model_error)
        # Use original category so users can identify which folder had the issue  
        return f"errors/{process_type}/{original_category}/{doc_number}"

def build_combined_metadata_and_raw(
    result: ProcessingResult, 
    folder_path: str, 
    meta_dict: Dict[str, Any], 
    raw_responses: List[Dict[str, Any]], 
    process_type: str = "classification"
) -> Dict[str, Any]:
    """
    Build combined metadata with raw responses for single file storage.
    SRP: Single responsibility for combined data structure.

    Args:
        result: ProcessingResult
        folder_path: Original S3 path
        meta_dict: Processed result dict
        raw_responses: List of raw Bedrock responses
        process_type: "classification" or "extraction"

    Returns:
        dict: Combined metadata and raw response data
    """
    # Extract document info
    doc_number = meta_dict.get('document_number', 'UNKNOWN')
    category = meta_dict.get('category', 'UNKNOWN')

    # Extract source file info
    try:
        source_bucket, source_key = extract_s3_path(folder_path)
        filename = Path(source_key).name
        file_id = Path(filename).stem
    except:
        file_id = f"unknown_{doc_number}"

    # Build model information from responses
    models_attempted = []
    raw_responses_data = []

    if raw_responses:
        for i, resp in enumerate(raw_responses):
            # Model info for metadata
            model_info = {
                'attempt_order': i + 1,
                'model_id': resp.get('model_id', 'unknown'),
                'api_used': resp.get('api_used', 'unknown'),
                'status': resp.get('stopReason', 'unknown'),
                'tokens_used': resp.get('usage', {})
            }
            models_attempted.append(model_info)

            # Raw response data
            enhanced_resp = resp.copy() if resp else {}
            enhanced_resp['attempt_number'] = i + 1
            enhanced_resp['is_successful_attempt'] = (i == len(raw_responses) - 1 and result.is_success)
            raw_responses_data.append(enhanced_resp)

    # Determine if fallback was used
    fallback_used = len(raw_responses) > 1 if raw_responses else False
    primary_model = raw_responses[0].get('model_id', 'unknown') if raw_responses else 'unknown'
    successful_model = result.model_used

    return {
        # Document identification
        'document_number': doc_number,
        'category': category,
        'file_id': file_id,
        'source_path': folder_path,
        'process_type': process_type,

        # Processing results
        'processing_status': result.status,
        'is_success': result.is_success,
        'processing_failed': not result.is_success,
        'requires_extraction': meta_dict.get('requires_extraction', False),
        'error_message': result.error_message,

        # Model information
        'successful_model': successful_model,
        'primary_model': primary_model,
        'fallback_used': fallback_used,
        'models_attempted': models_attempted,
        'total_models_tried': len(models_attempted),

        # Raw responses embedded
        'raw_responses': raw_responses_data,
        'total_attempts': len(raw_responses_data),
        'has_raw_data': len(raw_responses_data) > 0,

        # Timestamps
        'timestamp': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        'processing_date': datetime.now(timezone(timedelta(hours=-5))).strftime('%Y-%m-%d'),
    }

def save_processing_to_s3(
    result: ProcessingResult, 
    folder_path: str, 
    meta_dict: Dict[str, Any], 
    raw_bedrock_responses: Optional[List[Dict[str, Any]]] = None,
    process_type: str = "classification"
) -> None:
    """
    Save processing results to S3 for persistence.
    Used for: failures + non-extractable documents (BLANK, LINK_ONLY).
    Saves combined metadata and raw responses in single file.
    SRP: Single responsibility for persisting processing data.

    Args:
        result: ProcessingResult
        folder_path: Original S3 path to the PDF
        meta_dict: Processed result dict (for extracting category)
        raw_bedrock_responses: List of raw Bedrock responses (if any)
        process_type: "classification" or "extraction"
    """
    try:
        # Get environment variables
        destination_bucket = os.environ.get("DESTINATION_BUCKET")

        if not destination_bucket:
            logger.warning("DESTINATION_BUCKET not configured, skipping S3 persistence")
            return

        # Extract basic info
        doc_number = meta_dict.get('document_number', 'UNKNOWN')
        classified_category = meta_dict.get('category', 'UNKNOWN')
        
        # Extract original category from S3 path for folder structure
        original_category = extract_original_category_from_path(folder_path)

        # Extract file identifier
        try:
            source_bucket, source_key = extract_s3_path(folder_path)
            filename = Path(source_key).name
            file_id = Path(filename).stem
        except:
            file_id = f"unknown_{doc_number}"

        # Build folder structure using original category (returns single path)
        folder = build_s3_folder_structure(result, original_category, doc_number, process_type)

        # Build combined metadata and raw responses
        combined_data = build_combined_metadata_and_raw(result, folder_path, meta_dict, raw_bedrock_responses or [], process_type)

        # Save single combined file
        file_key = f"{folder}/{process_type}_result_{file_id}.json"
        save_to_s3(combined_data, destination_bucket, file_key)

        # Log results
        if result.is_success:
            logger.info(f"Saved non-extractable {process_type}: {original_category}/{doc_number} (classified as: {classified_category}, model: {result.model_used})")
        else:
            logger.info(f"Saved failed {process_type}: {original_category}/{doc_number} (status: {result.status}, model: {result.model_used})")

    except Exception as e:
        logger.error(f"Failed to save {process_type} to S3: {str(e)}")
        # Don't re-raise - S3 persistence failure shouldn't break the main flow

def should_retry_with_fallback(result: ProcessingResult) -> bool:
    """
    Business rule: when to try fallback model.
    SRP: Single responsibility for retry decision logic.
    """
    return result.status in {'content_filtered', 'parse_error', 'model_error'}

def choose_better_result(result1: ProcessingResult, result2: ProcessingResult) -> ProcessingResult:
    """
    Business rule: which failure is "better" to report.
    SRP: Single responsibility for failure result selection.
    """
    # Preference order: content_filtered > parse_error > model_error
    # Content filtered is "better" because it means the model understood but was blocked
    priority = {'content_filtered': 3, 'parse_error': 2, 'model_error': 1}
    return result2 if priority.get(result2.status, 0) > priority.get(result1.status, 0) else result1

def log_processing_result(result: ProcessingResult, attempt_type: str, process_type: str = "processing") -> None:
    """
    Log processing result with appropriate log level.
    SRP: Single responsibility for logging processing results.
    """
    model_info = f"{attempt_type} model ({result.model_used})"

    if result.is_success:
        logger.info(f"{model_info} succeeded in {process_type}")
    elif result.status == 'content_filtered':
        # Content filtering is INFO level - it's a valid business outcome
        logger.info(f"{model_info} content filtered in {process_type}: {result.error_message}")
    elif result.status == 'parse_error':
        # Parse errors are WARNING - model responded but we couldn't understand it
        logger.warning(f"{model_info} parse error in {process_type}: {result.error_message}")
    elif result.status == 'model_error':
        # Model errors are ERROR - infrastructure/service issues
        logger.error(f"{model_info} model error in {process_type}: {result.error_message}")