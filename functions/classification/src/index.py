import json, base64, logging
from models import ClassMeta
from pdf_processor import get_first_pdf_page, create_message
from bedrock_client import create_bedrock_client, set_model_params, converse_with_nova, parse_classification, NovaRequest
from sqs_handler import get_instructions, build_payload

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def handler(event, context):
    """
    Lambda handler function.
    """
    try:
        logger.info(f"Received event: {json.dumps(event)}")

        # Extract PDF content and folder path from the event
        pdf_content = event.get('pdf_content')
        folder_path = event.get('folder_path')

        if not pdf_content or not folder_path:
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'error': 'Missing required parameters: pdf_content or folder_path'
                })
            }

        # Decode base64 PDF content if needed
        if isinstance(pdf_content, str):
            pdf_bytes = base64.b64decode(pdf_content)
        else:
            pdf_bytes = pdf_content

        # Extract the first page of the PDF
        first_page = get_first_pdf_page(pdf_bytes)

        # Initialize Bedrock client
        bedrock = create_bedrock_client()

        # Get instructions
        user_prompt = get_instructions("user")
        system_prompt = get_instructions("system")
        system_parameter = [{"text": system_prompt}]

        # Create message for Bedrock
        message_created = create_message(user_prompt, "user", first_page, folder_path)
        messages = [message_created]

        # Set model parameters
        modelId = "us.amazon.nova-pro-v1:0"
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

        # Return the result
        return {
            'statusCode': 200,
            'body': json.dumps(payload)
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
