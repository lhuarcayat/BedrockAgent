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
                   pdf_path: str | None = None):
    """
    Build a single Bedrock message that contains:
        • main prompt (instructions + result envelope)
        • optional PDF document block
    """
    content = []
    content.append({"text": prompt})

    # Optional PDF document
    if pdf_bytes is not None:
        raw_name = pdf_path or "document.pdf"
        name = sanitize_name(raw_name)

        content.append({
            "document": {
                "name": name,
                "format": "pdf",
                "source": {
                    "bytes": pdf_bytes
                }
            }
        })

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
