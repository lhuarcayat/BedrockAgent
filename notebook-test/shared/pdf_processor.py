import io, base64, logging
from pathlib import Path
from PyPDF2 import PdfReader, PdfWriter

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

def create_message(prompt: str,
                   role: str,
                   pdf_bytes: bytes | None = None,
                   pdf_path: str | None = None,
                   s3_uri: str | None = None,
                   s3_bucket_owner: str | None = None):
    """
    Build a single Bedrock message that contains:
        • main prompt (instructions + result envelope)
        • optional PDF document block
    
    Args:
        prompt: Text prompt for the message
        role: Message role (user, assistant, etc.)
        pdf_bytes: PDF content as bytes (legacy approach)
        pdf_path: Path/name for the PDF (for naming)
        s3_uri: S3 URI for direct access (e.g., "s3://bucket/path/file.pdf")
        s3_bucket_owner: AWS account ID that owns the S3 bucket (optional if same account)
    
    Note: If both pdf_bytes and s3_uri are provided, s3_uri takes precedence for efficiency.
    """
    content = []
    content.append({"text": prompt})

    # Optional PDF document - prefer S3 direct access over bytes
    if s3_uri or pdf_bytes is not None:
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
        if s3_uri:
            document_block["document"]["source"]["s3Location"] = {
                "uri": s3_uri
            }
            # Add bucket owner if specified (required for cross-account access)
            if s3_bucket_owner:
                document_block["document"]["source"]["s3Location"]["bucketOwner"] = s3_bucket_owner
        else:
            # Fallback to bytes approach (maintains backward compatibility)
            document_block["document"]["source"]["bytes"] = pdf_bytes

        content.append(document_block)

    # Assemble the message envelope Bedrock expects
    msg = {"role": role, "content": content}
    return msg

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
    Returns True if the PDF appears to be a scanned/image‐only PDF.
    We consider it scanned if no page yields more than text_threshold chars.
    """
    reader = PdfReader(io.BytesIO(pdf_bytes))
    for page in reader.pages:
        text = page.extract_text() or ""
        if len(text.strip()) > text_threshold:
            # Found enough text to call it “generated”
            return False
    # No substantial text on any page → likely scanned
    return True