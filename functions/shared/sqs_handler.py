import json, logging, os, boto3
from typing import Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def build_folder_path(folder_path: str) -> str:
    """
    Extract folder path from the input path.
    """
    parts = folder_path.split('/')
    if len(parts) >= 2:
        return f"file_examples/{parts[0]}/{parts[1]}"
    return folder_path

def build_payload(meta: Dict[str, Any]) -> dict:
    """
    Build the payload that Phase-2 expects.
    """
    return {
        "path": meta.get("path", "UNKNOWN"),
        "result": meta,   # dict
        "document_type": meta.get("document_type", "UNKNOWN"),
        "document_number": meta.get("document_number", "UNKNOWN"),
        "category": meta.get("category", "UNKNOWN")
    }

def send_to_extraction_queue(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Send a message to the extraction SQS queue.

    Args:
        payload: The payload to send to the queue

    Returns:
        The SQS response
    """
    queue_url = os.environ.get("EXTRACTION_SQS")
    if not queue_url:
        logger.error("EXTRACTION_SQS environment variable not set")
        raise ValueError("EXTRACTION_SQS environment variable not set")

    sqs_client = boto3.client('sqs', region_name=os.environ.get("REGION", "us-east-1"))

    try:
        response = sqs_client.send_message(
            QueueUrl=queue_url,
            MessageBody=json.dumps(payload)
        )
        logger.info(f"Message sent to SQS: {response['MessageId']}")
        return response
    except Exception as e:
        logger.error(f"Error sending message to SQS: {str(e)}")
        raise
