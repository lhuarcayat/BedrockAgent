"""
Result building utilities for processing results.

This module handles building comprehensive metadata and converting results
to different formats for backward compatibility. Updated with notebook functionality.
"""

import re
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from .s3_handler import extract_s3_path

logger = logging.getLogger(__name__)

def extract_document_number_from_path(s3_path: str) -> str:
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
        return "UNKNOWN"
    except Exception as e:
        logger.error(f"Error extracting document number from {s3_path}: {str(e)}")
        return "UNKNOWN"

def extract_original_category_from_path(folder_path: str) -> str:
    """
    Extract the original category from S3 folder path.
    
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

def result_to_dict(result, folder_path, raw_responses=None, extractable_categories=None):
    """
    Convert ClassificationResult to existing dict format for backward compatibility.
    Enhanced with notebook functionality.
    
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

        # Add enhanced tracking information
        meta_dict['timestamp'] = datetime.now(timezone.utc).isoformat()
        meta_dict['original_category'] = extract_original_category_from_path(folder_path)
        meta_dict['processing_status'] = 'success'

        # Add fallback model information if applicable
        if raw_responses and len(raw_responses) > 1:
            primary_model = raw_responses[0].get('model_id', 'unknown')
            meta_dict['fallback_used'] = True
            meta_dict['primary_model'] = primary_model
            meta_dict['successful_model'] = result.model_used
            meta_dict['total_attempts'] = len(raw_responses)
        else:
            meta_dict['fallback_used'] = False
            meta_dict['total_attempts'] = 1

        return meta_dict
    else:
        # Failure case - create fallback classification
        doc_number = extract_document_number_from_path(folder_path)
        original_category = extract_original_category_from_path(folder_path)

        fallback_dict = {
            'document_type': 'UNKNOWN',
            'document_number': doc_number,
            'path': folder_path,
            'error': result.error_message,
            'confidence_score': 0.0,
            'model_used': result.model_used,
            'status': result.status,
            'processing_failed': True,
            'requires_extraction': False,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'original_category': original_category,
            'processing_status': 'failed'
        }

        # Add fallback information even for failures
        if raw_responses and len(raw_responses) > 1:
            primary_model = raw_responses[0].get('model_id', 'unknown')
            fallback_dict['fallback_used'] = True
            fallback_dict['primary_model'] = primary_model
            fallback_dict['final_model'] = result.model_used
            fallback_dict['total_attempts'] = len(raw_responses)
        else:
            fallback_dict['fallback_used'] = False
            fallback_dict['total_attempts'] = 1

        return fallback_dict

def build_document_info(folder_path: str, s3_record: dict = None) -> dict:
    """
    Build standardized document information from S3 path and record.
    
    Args:
        folder_path: S3 path to the document
        s3_record: Optional S3 event record
        
    Returns:
        dict: Standardized document information
    """
    try:
        bucket, key = extract_s3_path(folder_path)
        filename = Path(key).name
        file_id = Path(filename).stem
        
        return {
            'path': folder_path,
            's3_bucket': bucket,
            's3_key': key,
            'filename': filename,
            'file_id': file_id,
            'document_number': extract_document_number_from_path(folder_path),
            'category': extract_original_category_from_path(folder_path),
            'size': s3_record.get('s3', {}).get('object', {}).get('size') if s3_record else None,
            'etag': s3_record.get('s3', {}).get('object', {}).get('eTag') if s3_record else None
        }
    except Exception as e:
        logger.error(f"Error building document info: {e}")
        return {
            'path': folder_path,
            'document_number': 'UNKNOWN',
            'category': 'UNKNOWN',
            'error': str(e)
        }

def build_model_info(model_id: str, api_used: str, response_data: dict = None, fallback_info: dict = None) -> dict:
    """
    Build standardized model information.
    
    Args:
        model_id: Model identifier used
        api_used: API used (converse or invoke_model)
        response_data: Response data from Bedrock
        fallback_info: Information about fallback usage
        
    Returns:
        dict: Standardized model information
    """
    model_info = {
        'model_id': model_id,
        'api_used': api_used,
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'usage': response_data.get('usage', {}) if response_data else {},
        'stop_reason': response_data.get('stopReason') if response_data else None
    }
    
    if fallback_info:
        model_info.update(fallback_info)
    
    return model_info