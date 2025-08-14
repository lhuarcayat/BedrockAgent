"""
Result building utilities for processing results.

This module handles building comprehensive metadata and converting results
to different formats for backward compatibility.
"""

import re
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from .s3_handler import extract_s3_path

logger = logging.getLogger(__name__)

def build_combined_metadata_and_raw(result, folder_path, meta_dict, raw_responses):
    """
    Build combined metadata with raw responses for single file storage.
    
    Args:
        result: ClassificationResult
        folder_path: Original S3 path
        meta_dict: Processed classification dict
        raw_responses: List of raw Bedrock responses
        
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

        # Processing results
        'classification_status': result.status,
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

def result_to_dict(result, folder_path, raw_responses=None, extractable_categories=None):
    """
    Convert ClassificationResult to existing dict format for backward compatibility.
    
    Args:
        result: ClassificationResult
        folder_path: Original S3 path
        raw_responses: List of raw Bedrock responses for fallback tracking
        extractable_categories: Set of categories that require extraction
        
    Returns:
        dict: Converted result dictionary
    """
    extractable_categories = extractable_categories or set()
    
    if result.is_success:
        # Success case - return the classification data
        meta_dict = result.data.copy()
        meta_dict['model_used'] = result.model_used

        # Determine if this category requires extraction
        category = meta_dict.get('category', 'UNKNOWN')
        meta_dict['requires_extraction'] = category in extractable_categories

        # Add fallback model information if applicable
        if raw_responses and len(raw_responses) > 1:
            primary_model = raw_responses[0].get('model_id', 'unknown')
            meta_dict['fallback_used'] = True
            meta_dict['primary_model'] = primary_model
            meta_dict['successful_model'] = result.model_used
        else:
            meta_dict['fallback_used'] = False

        return meta_dict
    else:
        # Failure case - create fallback classification
        doc_number = "UNKNOWN"
        if folder_path:
            match = re.search(r'/(\d{6,})/', folder_path)
            if match:
                doc_number = match.group(1)

        fallback_dict = {
            'document_type': 'UNKNOWN',
            'document_number': doc_number,
            'path': folder_path,
            'error': result.error_message,
            'confidence_score': 0.0,
            'model_used': result.model_used,
            'status': result.status,
            'processing_failed': True,
            'requires_extraction': False
        }

        # Add fallback information even for failures
        if raw_responses and len(raw_responses) > 1:
            primary_model = raw_responses[0].get('model_id', 'unknown')
            fallback_dict['fallback_used'] = True
            fallback_dict['primary_model'] = primary_model
            fallback_dict['final_model'] = result.model_used
        else:
            fallback_dict['fallback_used'] = False

        return fallback_dict