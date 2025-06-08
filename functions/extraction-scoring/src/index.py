import json
import logging
from shared.helper import load_env

# Configure logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Load environment variables
load_env()

def handler(event, context):
    """
    Lambda handler for extraction-scoring service.
    Logs the classification payload received from SQS.

    Args:
        event: The event dict containing the SQS message
        context: Lambda context object

    Returns:
        dict: Response with status code and message
    """
    try:
        logger.info("Received classification payload:")

        # For SQS events, the actual payload is in the Records array
        if 'Records' in event and len(event['Records']) > 0:
            for record in event['Records']:
                if 'body' in record:
                    # Parse the SQS message body
                    try:
                        payload = json.loads(record['body'])
                        logger.info(f"Processing classification payload: {json.dumps(payload, indent=2)}")
                    except json.JSONDecodeError:
                        logger.warning(f"Non-JSON payload received: {record['body']}")
                        logger.info(record['body'])
                else:
                    logger.warning(f"SQS record missing body: {json.dumps(record, indent=2)}")
        else:
            # Direct invocation case
            logger.info(f"Direct invocation payload: {json.dumps(event, indent=2)}")

        return {
            "statusCode": 200,
            "body": json.dumps({"message": "Payload logged successfully"})
        }

    except Exception as e:
        logger.error(f"Error processing event: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }
