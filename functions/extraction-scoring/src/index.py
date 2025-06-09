import json
import logging
import os
import boto3

from shared.helper import load_env
from shared.bedrock_client import create_bedrock_client, set_model_params, converse_with_nova, NovaRequest, parse_extraction_response, create_payload_data_extraction
from shared.pdf_processor import create_message
from shared.sqs_handler import build_folder_path, send_to_fallback_queue_extraction
from shared.prompts import get_instructions_extraction, build_user_prompt_extraction, build_system_prompt_extraction
from shared.s3_handler import save_to_s3, get_pdf_from_s3, extract_s3_path

# Configure logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Load environment variables
load_env()

# Environment variables
S3_ORIGIN_BUCKET = os.environ.get("S3_ORIGIN_BUCKET")
FALLBACK_SQS = os.environ.get("FALLBACK_SQS")
DESTINATION_BUCKET = os.environ.get("DESTINATION_BUCKET")
BEDROCK_MODEL = os.environ.get("BEDROCK_MODEL")
FALLBACK_MODEL = os.environ.get("FALLBACK_MODEL")
REGION = os.environ.get("REGION", "us-east-1")
FOLDER_PREFIX = os.environ.get("FOLDER_PREFIX")
# Create clients
bedrock_client = create_bedrock_client()

def handler(event, context):
    """
    Lambda handler for extraction-scoring service.
    Processes PDF documents using Bedrock models and saves results to S3.

    Args:
        event: The event dict containing the SQS message
        context: Lambda context object

    Returns:
        dict: Response with status code and message
    """
    try:
        logger.info(f"Received extraction-scoring event: {json.dumps(event)}")

        # For SQS events, the actual payload is in the Records array
        if 'Records' not in event or len(event['Records']) == 0:
            logger.warning("No records found in event")
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "No records found in event"})
            }

        # Process each record
        for record in event['Records']:
            if 'body' not in record:
                logger.warning(f"SQS record missing body: {json.dumps(record, indent=2)}")
                continue

            # Parse the SQS message body
            try:
                payload = json.loads(record['body'])
                logger.info(f"Processing payload: {json.dumps(payload, indent=2)}")

                # Extract document information
                pdf_path = payload.get('path')
                document_number = payload.get('document_number')
                document_type = payload.get('document_type')
                category = payload.get('category')

                if not all([pdf_path, document_number, document_type, category]):
                    logger.warning(f"Missing required fields in payload: {json.dumps(payload, indent=2)}")
                    continue

                # Extract bucket and key from S3 URI
                source_bucket, source_key = extract_s3_path(pdf_path)

                # Get the PDF from S3
                pdf_bytes = get_pdf_from_s3(source_bucket, source_key)

                # Set up prompt parameters
                system_p = "system"
                user_p = "user"

                # Build the prompts
                task_root = os.environ.get("LAMBDA_TASK_ROOT", os.getcwd())
                schema_path = os.path.join(task_root, f"shared/evaluation_type/{category}/schema.json")
                examples_dir = os.path.join(task_root, f"shared/evaluation_type/{category}/examples")

                user_message = build_user_prompt_extraction(
                    pdf_path=pdf_path,
                    document_number=document_number,
                    document_type=document_type,
                    category=category,
                    system_p=system_p,
                    user_p=user_p
                )

                system_message = build_system_prompt_extraction(
                    schema_path=schema_path,
                    examples_dir=examples_dir,
                    system_p=system_p,
                    user_p=user_p,
                    category=category
                )

                # Set up model parameters
                model_id = BEDROCK_MODEL
                temperature = 0.1
                top_p = 0.9
                max_tokens = 8192

                # Create the message
                messages = [
                    create_message(user_message, "user", pdf_bytes, pdf_path),
                ]
                system_parameter = [{"text": system_message}]

                # Set up model parameters
                cfg = set_model_params(model_id, max_tokens, top_p, temperature)

                # Call Bedrock
                req_params = {
                    "model_id": model_id,
                    "messages": messages,
                    "params": {**cfg},
                    "system": system_parameter,
                }

                try:
                    resp_json = converse_with_nova(NovaRequest(**req_params), bedrock_client)

                    # Parse the response
                    meta = parse_extraction_response(resp_json)
                    payload_data = create_payload_data_extraction(meta)

                    # Save to S3
                    destination_key = f"{FOLDER_PREFIX}/{category}/{document_number}/{category}_{document_number}.json"
                    save_to_s3(payload_data, DESTINATION_BUCKET, destination_key)

                    logger.info(f"Successfully processed document: {pdf_path}")

                except Exception as e:
                    logger.error(f"Error processing with primary model: {str(e)}")

                    # Try fallback model if available
                    if FALLBACK_MODEL:
                        try:
                            logger.info(f"Trying fallback model: {FALLBACK_MODEL}")

                            # Update model ID and retry
                            req_params["model_id"] = FALLBACK_MODEL
                            resp_json = converse_with_nova(NovaRequest(**req_params), bedrock_client)

                            # Parse the response
                            meta = parse_extraction_response(resp_json)
                            payload_data = create_payload_data_extraction(meta)

                            # Save to S3
                            destination_key = f"{category}/{document_number}/{category}_{document_number}.json"
                            save_to_s3(payload_data, DESTINATION_BUCKET, destination_key)

                            logger.info(f"Successfully processed document with fallback model: {pdf_path}")

                        except Exception as fallback_error:
                            logger.error(f"Error processing with fallback model: {str(fallback_error)}")
                            # Send to fallback queue
                            send_to_fallback_queue_extraction(payload)
                    else:
                        # Send to fallback queue
                        send_to_fallback_queue_extraction(payload)

            except json.JSONDecodeError:
                logger.warning(f"Non-JSON payload received: {record['body']}")
            except Exception as e:
                logger.error(f"Error processing record: {str(e)}")
                # Send to fallback queue if possible
                try:
                    send_to_fallback_queue_extraction(json.loads(record['body']))
                except:
                    pass

        return {
            "statusCode": 200,
            "body": json.dumps({"message": "Processing completed"})
        }

    except Exception as e:
        logger.error(f"Error processing event: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }
