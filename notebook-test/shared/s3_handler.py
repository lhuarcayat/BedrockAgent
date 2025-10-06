import json
import logging
import os
import boto3
from typing import Dict, Any, Tuple

# Configure logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def save_to_s3(data: Dict[str, Any], bucket: str, key: str) -> None:
    """
    Save data to S3 as JSON.

    Args:
        data: The data to save
        bucket: The S3 bucket name
        key: The S3 key

    Returns:
        None
    """
    try:
        s3_client = boto3.client('s3', region_name=os.environ.get("REGION", "us-east-1"))
        s3_client.put_object(
            Bucket=bucket,
            Key=key,
            Body=json.dumps(data, indent=2, ensure_ascii=False),
            ContentType='application/json'
        )
        logger.info(f"Saved JSON to s3://{bucket}/{key}")
    except Exception as e:
        logger.error(f"Error saving to S3: {str(e)}")
        raise

def get_pdf_from_s3(bucket: str, key: str) -> bytes:
    """
    Get a PDF file from S3.

    Args:
        bucket: The S3 bucket name
        key: The S3 key

    Returns:
        bytes: The PDF file content
    """
    try:
        s3_client = boto3.client('s3', region_name=os.environ.get("REGION", "us-east-1"))
        response = s3_client.get_object(Bucket=bucket, Key=key)
        return response['Body'].read()
    except Exception as e:
        logger.error(f"Error getting PDF from S3: {str(e)}")
        raise

def extract_s3_path(s3_uri: str) -> Tuple[str, str]:
    """
    Extract bucket and key from an S3 URI.
    Format: s3://bucket-name/path/to/file.pdf

    Args:
        s3_uri: The S3 URI

    Returns:
        tuple: The bucket and key
    """
    default_bucket = os.environ.get("S3_ORIGIN_BUCKET", "")

    if s3_uri.startswith('s3://'):
        parts = s3_uri[5:].split('/', 1)
        if len(parts) == 2:
            return parts[0], parts[1]

    # If not a valid S3 URI, return the original values
    return default_bucket, s3_uri

def build_s3_result_folder_path(classification_result, original_category, doc_number, processing_type="classification"):
    """
    Build S3 folder structure based on classification result using original category.
    
    This function creates consistent S3 paths for storing processing results,
    organizing them by processing outcome and original document category.
    
    Args:
        classification_result: ClassificationResult namedtuple
        original_category: Original document category from S3 path (for user identification)
        doc_number: Document number extracted from path
        processing_type: Type of processing ("classification" or "extraction")
    
    Returns:
        str: S3 folder path for saving result files
        
    Examples:
        Success (extractable): "extraction/CERL/123456/" 
        Success (non-extractable): "non_extractable/classification/CERL/123456/"
        Failed: "errors/classification/CERL/123456/"
    """
    if hasattr(classification_result, 'is_success') and classification_result.is_success:
        # Successful classifications
        if processing_type == "extraction":
            # This is for extraction results
            return f"extraction/{original_category}/{doc_number}"
        else:
            # Non-extractable successful documents (BLANK, LINK_ONLY)
            # Use original category so users can identify which folder had the issue
            return f"non_extractable/{processing_type}/{original_category}/{doc_number}"
    else:
        # Failed classifications (content_filtered, parse_error, model_error)
        # Use original category so users can identify which folder had the issue  
        return f"errors/{processing_type}/{original_category}/{doc_number}"

def build_s3_result_key(folder_path, file_id, processing_type="classification", suffix="result"):
    """
    Build complete S3 key for result files.
    
    Args:
        folder_path: Base folder path from build_s3_result_folder_path()
        file_id: File identifier (filename without extension)
        processing_type: Type of processing ("classification" or "extraction")
        suffix: File suffix (default: "result")
        
    Returns:
        str: Complete S3 key
        
    Examples:
        "extraction/CERL/123456/document_001_extraction_result.json"
        "errors/classification/RUT/789012/invoice_002_classification_result.json"
    """
    return f"{folder_path}/{file_id}_{processing_type}_{suffix}.json"
