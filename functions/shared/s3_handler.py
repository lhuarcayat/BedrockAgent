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
        s3_client = boto3.client('s3', region_name=os.environ.get("REGION", "us-east-2"))
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
