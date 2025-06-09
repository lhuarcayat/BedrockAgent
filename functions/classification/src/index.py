import json, base64, logging, os, re, boto3
from urllib.parse import unquote_plus
from shared.models import ClassMeta
from shared.pdf_processor import detect_scanned_pdf, get_first_pdf_page, create_message
from shared.bedrock_client import create_bedrock_client, set_model_params, converse_with_nova, parse_classification, NovaRequest
from shared.sqs_handler import build_payload, send_to_extraction_queue
from shared.prompts import get_instructions, add_now_process
from shared.helper import load_env

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()
logger.setLevel(logging.INFO)
load_env()

def process_pdf(pdf_bytes, folder_path):
    """
    Process a PDF file and classify it.
    """
    # Extract the first page of the PDF
    first_page = get_first_pdf_page(pdf_bytes)
    is_scanned = detect_scanned_pdf(pdf_bytes)
    logger.info(f"PDF type detected: {'scanned image' if is_scanned else 'has text'}")

    # Initialize Bedrock client
    bedrock = create_bedrock_client()

    # Get instructions
    user_prompt = get_instructions("user") + add_now_process(folder_path)
    logger.info(f"User prompt: {user_prompt}")
    system_prompt = get_instructions("system")
    system_parameter = [{"text": system_prompt}]

    # Create message for Bedrock
    message_created = create_message(user_prompt, "user", first_page, folder_path)
    messages = [message_created]

    # Set model parameters
    modelId = os.environ.get("BEDROCK_MODEL")
    fallback_model = os.environ.get("FALLBACK_MODEL")
    temperature = 0.1
    top_p = 0.9
    max_tokens = 8192
    cfg_params = set_model_params(modelId, max_tokens, top_p, temperature)

    # Create request parameters
    req_params = {
        "model_id": modelId,
        "messages": messages,
        "params": {**cfg_params},
        "system": system_parameter,
    }

    # Call Bedrock
    resp_json = converse_with_nova(NovaRequest(**req_params), bedrock)

    # Parse the response
    meta_dict = parse_classification(resp_json, pdf_path=folder_path)
    meta = ClassMeta.model_validate(meta_dict)
    payload = build_payload(meta_dict)
    payload['path'] = folder_path

    # Send to extraction queue
    try:
        send_to_extraction_queue(payload)
        logger.info(f"Sent payload to extraction queue for {folder_path}")
    except Exception as e:
        logger.error(f"Failed to send to extraction queue: {str(e)}")
        # Continue processing even if SQS send fails

    return payload

def validate_s3_key(key):
    """
    Validate that the S3 key follows the expected pattern.
    Expected pattern: path/to/document_number/filename.pdf
    """
    # Check if it's a PDF file
    if not key.lower().endswith('.pdf'):
        return False, "Not a PDF file"

    # Check if it contains a document number folder (6+ digits)
    match = re.search(r'/(\d{6,})/', key)
    if not match:
        return False, "No document number folder found in path"

    return True, match.group(1)  # Return document number

def handler(event, context):
    """
    Lambda handler function for S3 events.
    """
    try:
        logger.info(f"Received event: {json.dumps(event)}")

        # Handle S3 event
        if 'Records' not in event:
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'error': 'Not an S3 event or missing Records'
                })
            }

        results = []
        s3_client = boto3.client('s3', region_name=os.environ.get('REGION', 'us-east-1'))
        s3_bucket = os.environ.get('S3_ORIGIN_BUCKET')

        for record in event['Records']:
            if record.get('eventSource') != 'aws:s3':
                logger.warning(f"Skipping non-S3 event: {record.get('eventSource')}")
                continue

            # Extract bucket and key
            bucket = record['s3']['bucket']['name']
            key = unquote_plus(record['s3']['object']['key'])
            logger.info(f"Processing S3 object: s3://{bucket}/{key}")

            # Validate the key structure
            is_valid, doc_number_or_error = validate_s3_key(key)
            if not is_valid:
                logger.error(f"Invalid S3 key: {key}. Error: {doc_number_or_error}")
                results.append({
                    'key': key,
                    'status': 'error',
                    'error': doc_number_or_error
                })
                continue

            try:
                # Get the PDF from S3
                response = s3_client.get_object(Bucket=bucket, Key=key)
                pdf_bytes = response['Body'].read()

                # Use the S3 key as the folder path
                folder_path = f"s3://{bucket}/{key}"

                # Process the PDF
                payload = process_pdf(pdf_bytes, folder_path)
                results.append({
                    'key': key,
                    'status': 'success',
                    'payload': payload
                })
                logger.info(f"Successfully processed S3 object: {results}")

            except Exception as e:
                logger.error(f"Error processing S3 object {key}: {str(e)}")
                results.append({
                    'key': key,
                    'status': 'error',
                    'error': str(e)
                })

        # Return the results
        return {
            'statusCode': 200,
            'body': json.dumps({
                'results': results
            })
        }

    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e)
            })
        }
