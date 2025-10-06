import json, logging, os, boto3
from typing import Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()
logger.setLevel(logging.INFO)

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

    sqs_client = boto3.client('sqs', region_name=os.environ.get("REGION", "us-east-2"))

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

def send_to_fallback_queue_extraction(payload: Dict[str, Any]) -> None:
    """
    Send a message to the fallback SQS queue for extraction.

    Args:
        payload: The payload to send to the queue

    Returns:
        None
    """
    fallback_sqs = os.environ.get("FALLBACK_SQS")
    if not fallback_sqs:
        logger.error("FALLBACK_SQS environment variable not set")
        return

    try:
        sqs_client = boto3.client('sqs', region_name=os.environ.get("REGION", "us-east-2"))
        response = sqs_client.send_message(
            QueueUrl=fallback_sqs,
            MessageBody=json.dumps(payload)
        )
        logger.info(f"Message sent to fallback SQS: {response['MessageId']}")
    except Exception as e:
        logger.error(f"Error sending message to fallback SQS: {str(e)}")
