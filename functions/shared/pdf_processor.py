import io, base64, logging, os, boto3, time
from pathlib import Path
from PyPDF2 import PdfReader, PdfWriter
from botocore.config import Config
from typing import Dict, Any
from .text_utils import clean_text_for_json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def sanitize_name(raw_name: str) -> str:
    """
    Strip off any disallowed characters (including periods) from a filename.
    We'll just keep the stem (no extension) and remove anything but
    alphanumerics, spaces, hyphens, parentheses, and brackets.
    """
    stem = Path(raw_name).stem  # e.g. "231_CA_2020-02-29"
    # Remove underscores and periods, keep only allowed chars
    safe = "".join(ch for ch in stem
                   if ch.isalnum()
                   or ch in " -()[]")
    # Collapse multiple spaces or hyphens if you like
    return safe or "document"  # fallback if everything got stripped


def extract_pdf_text_with_pypdf(pdf_bytes: bytes) -> str:
    """
    Extract text from PDF using PyPDF2 as fallback when PDF is too large.
    """
    try:
        text_content = ""
        
        reader = PdfReader(io.BytesIO(pdf_bytes))
        logger.info(f"Extracting text with PyPDF2 - {len(reader.pages)} pages")
        
        for i, page in enumerate(reader.pages, 1):
            page_text = page.extract_text()
            if page_text:
                text_content += f"--- PÁGINA {i} ---\n"
                text_content += page_text + "\n\n"
        
        # Clean the extracted text
        text_content = clean_text_for_json(text_content.strip())
        
        logger.info(f"Text extracted successfully: {len(text_content)} characters")
        return text_content
        
    except Exception as e:
        logger.error(f"Error extracting text with PyPDF2: {e}")
        return f"[ERROR EXTRACTING TEXT: {str(e)}]"

def extract_pdf_text_with_textract(pdf_bytes: bytes, s3_bucket: str, s3_key: str, region: str = None) -> str:
    """
    Extract text from PDF using AWS Textract - PRODUCTION FLOW
    """
    try:
        # Use configured region or environment default
        region = region or os.environ.get("REGION", "us-east-2")
        
        # Create Textract client
        config = Config(read_timeout=1000)
        textract_client = boto3.client(
            service_name='textract',
            region_name=region,
            config=config
        )
        
        logger.info(f"Extracting text with AWS Textract - PDF in s3://{s3_bucket}/{s3_key}")
        
        # Call Textract to detect text using S3 location
        response = textract_client.start_document_text_detection(
            DocumentLocation={
                'S3Object': {
                    'Bucket': s3_bucket,
                    'Name': s3_key
                }
            }
        )
        
        job_id = response['JobId']
        logger.info(f"Textract job started: {job_id}")

        # STEP 1: WAIT FOR JOB TO COMPLETE
        max_wait_time = 300  # 5 minutes maximum
        wait_interval = 10   # Check every 10 seconds
        elapsed_time = 0
        
        while elapsed_time < max_wait_time:
            logger.info(f"Checking job status... ({elapsed_time}s elapsed)")
                
            job_response = textract_client.get_document_text_detection(JobId=job_id)
            job_status = job_response['JobStatus']
                
            if job_status == 'SUCCEEDED':
                logger.info("Job completed successfully!")
                break
            elif job_status == 'FAILED':
                error_msg = job_response.get('StatusMessage', 'Unknown error')
                raise RuntimeError(f"Textract job failed: {error_msg}")
            elif job_status in ['IN_PROGRESS', 'PARTIAL_SUCCESS']:
                logger.info(f"Job status: {job_status}, waiting...")
                time.sleep(wait_interval)
                elapsed_time += wait_interval
            else:
                raise RuntimeError(f"Unexpected job status: {job_status}")
        
        # Check timeout OUTSIDE the loop
        if elapsed_time >= max_wait_time:
            raise RuntimeError("Textract job timed out after 5 minutes")
        
        # STEP 2: GET RESULTS (ONLY AFTER COMPLETION)
        logger.info("Getting job results...")
        text_content = ""
        next_token = None
        all_lines = []  # Collect all lines
        
        # Process all result pages
        while True:
            if next_token:
                result_response = textract_client.get_document_text_detection(
                    JobId=job_id,
                    NextToken=next_token
                )
            else:
                result_response = textract_client.get_document_text_detection(JobId=job_id)
            
            # Extract lines from blocks
            blocks = result_response.get('Blocks', [])
            logger.info(f"Processing {len(blocks)} blocks")
            
            # Collect only LINE blocks (simpler)
            page_lines = {}
            for block in blocks:
                if block['BlockType'] == 'LINE':
                    page_num = block.get('Page', 1)
                    line_text = block.get('Text', '').strip()
                    
                    if line_text:  # Only non-empty lines
                        if page_num not in page_lines:
                            page_lines[page_num] = []
                        page_lines[page_num].append(line_text)
            
            # Add lines by page to total collection
            for page_num in sorted(page_lines.keys()):
                if page_num not in [item for item in all_lines if item.startswith("--- PÁGINA")]:
                    all_lines.append(f"--- PÁGINA {page_num} ---")
                
                for line in page_lines[page_num]:
                    all_lines.append(line)
            
            # Check if there are more result pages
            next_token = result_response.get('NextToken')
            if not next_token:
                break
                
            logger.info("Getting next page of results...")
        
        # STEP 3: BUILD FINAL TEXT
        if all_lines:
            text_content = '\n'.join(all_lines)
        else:
            logger.warning("No text lines found in Textract response")
            text_content = "[NO CONTENT DETECTED BY TEXTRACT]"
        
        # Clean the extracted text
        text_content = clean_text_for_json(text_content.strip())
        
        logger.info(f"Text extracted with Textract successfully: {len(text_content)} characters")
        logger.info(f"First 200 characters: {text_content[:200]}...")
        
        return text_content
        
    except Exception as e:
        logger.error(f"Error extracting text with AWS Textract: {e}")
        return f"[ERROR EXTRACTING TEXT WITH TEXTRACT: {str(e)}]"

def create_anthropic_message(prompt: str, role: str, pdf_bytes: bytes = None, pdf_path: str = None) -> Dict[str, Any]:
    """Create message for Anthropic InvokeModel API"""
    if pdf_bytes is not None:
        # Convert PDF to base64 for Anthropic
        pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
        
        return {
            "role": role,
            "content": [
                {
                    "type": "text",
                    "text": prompt,
                    "cache_control": {"type": "ephemeral"}
                },
                {
                    "type": "document",
                    "source": {
                        "type": "base64",
                        "media_type": "application/pdf",
                        "data": pdf_base64
                    },
                }
            ]
        }
    else:
        return {
            "role": role,
            "content": [
                {
                    "type": "text",
                    "text": prompt
                }
            ]
        }

def create_converse_message(prompt: str, role: str, pdf_bytes: bytes = None, pdf_path: str = None, s3_bucket_owner: str = None) -> Dict[str, Any]:
    """Create message for Converse API"""
    content = [{"text": prompt}]
    
    # Optional PDF document - prefer S3 direct access over bytes
    if pdf_path or pdf_bytes is not None:
        raw_name = pdf_path or "document.pdf"
        name = sanitize_name(raw_name)

        document_block = {
            "document": {
                "name": name,
                "format": "pdf",
                "source": {}
            }
        }

        # Use S3 direct access if URI provided (more efficient)
        if pdf_path:
            document_block["document"]["source"]["s3Location"] = {
                "uri": pdf_path
            }
            # Add bucket owner if specified (required for cross-account access)
            if s3_bucket_owner:
                document_block["document"]["source"]["s3Location"]["bucketOwner"] = s3_bucket_owner
        else:
            # Fallback to bytes approach (maintains backward compatibility)
            document_block["document"]["source"]["bytes"] = pdf_bytes

        content.append(document_block)
    
    return {"role": role, "content": content}

def download_pdf_from_s3(pdf_path):
    """
    Download PDF from S3 for Anthropic models.
    Fixed: Initialize pdf_bytes before try block to avoid NameError.
    """
    from .aws_clients import create_s3_client
    import re
    
    # Initialize pdf_bytes to avoid NameError on exception
    pdf_bytes = None
    
    try:
        logger.info(f"Downloading PDF from S3 for Anthropic model: {pdf_path}")
        
        # Parse S3 URI
        s3_match = re.match(r's3://([^/]+)/(.+)', pdf_path)
        if not s3_match:
            raise ValueError(f"Invalid S3 URI format: {pdf_path}")
        
        bucket_name = s3_match.group(1)
        object_key = s3_match.group(2)
        
        # Download from S3
        s3_client = create_s3_client()
        response = s3_client.get_object(Bucket=bucket_name, Key=object_key)
        pdf_bytes = response['Body'].read()
        
        logger.info(f"Downloaded PDF: {len(pdf_bytes)} bytes")
        
    except Exception as e:
        logger.error(f"Failed to download PDF from S3 for Anthropic model: {e}")
        # pdf_bytes is already None from initialization
        
    return pdf_bytes

def create_message(prompt: str,
                   role: str,
                   pdf_bytes: bytes | None = None,
                   pdf_path: str | None = None,
                   s3_bucket_owner: str | None = None,
                   model_id: str = None):
    """
    Build a single Bedrock message that contains:
        main prompt (instructions + result envelope)
        optional PDF document block
    
    Args:
        prompt: Text prompt for the message
        role: Message role (user, assistant, etc.)
        pdf_bytes: PDF content as bytes (legacy approach)
        pdf_path: Path/name for the PDF (for naming)
        s3_uri: S3 URI for direct access (e.g., "s3://bucket/path/file.pdf")
        s3_bucket_owner: AWS account ID that owns the S3 bucket (optional if same account)
        model_id: Model ID to determine which API to use
    
    Note: If both pdf_bytes and s3_uri are provided, s3_uri takes precedence for efficiency.
    For Anthropic models, S3 content will be automatically downloaded if needed.
    """
    from .bedrock_client import is_anthropic_model  
    # Determine model type if provided
    if model_id and is_anthropic_model(model_id):
        return create_anthropic_message(prompt, role, pdf_bytes, pdf_path)
    else:
        return create_converse_message(prompt, role, pdf_bytes, pdf_path, s3_bucket_owner)

def get_first_pdf_page(pdf_bytes):
    """
    Extract the first page from a PDF.
    """
    try:
        inputpdf = PdfReader(io.BytesIO(pdf_bytes))
        if len(inputpdf.pages) > 0:
            first_page = inputpdf.pages[0]
            writer = io.BytesIO()
            pdf_writer = PdfWriter()
            pdf_writer.add_page(first_page)
            pdf_writer.write(writer)
            return writer.getvalue()
        else:
            logger.warning("PDF has no pages")
            return pdf_bytes
    except Exception as e:
        logger.error(f"Error extracting first page: {str(e)}")
        return pdf_bytes

def detect_scanned_pdf(pdf_bytes: bytes, text_threshold: int = 20) -> bool:
    """
    Returns True if the PDF appears to be a scanned/image - only PDF.
    We consider it scanned if no page yields more than text_threshold chars.
    """
    reader = PdfReader(io.BytesIO(pdf_bytes))
    for page in reader.pages:
        text = page.extract_text() or ""
        if len(text.strip()) > text_threshold:
            # Found enough text to call it "generated"
            return False
    # No substantial text on any page → likely scanned
    return True