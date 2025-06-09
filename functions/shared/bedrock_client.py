import boto3, json, re, logging, os
from botocore.config import Config
from typing import Dict, Any, Union, List, Optional
from dataclasses import dataclass
import re

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Bedrock client configuration
cfg = Config(connect_timeout=30, read_timeout=300)
region = os.environ.get("REGION", "us-east-1")

@dataclass
class NovaRequest:
    model_id: str
    messages: List[Dict[str, Any]]
    params: Dict[str, Any]
    system: Optional[List] = None
    toolConfig: Optional[Dict[str, Any]] = None

def create_bedrock_client():
    """
    Create and return a Bedrock client with the configured settings.
    """
    session = boto3.Session()
    return session.client(
        "bedrock-runtime",
        region_name=region,
        config=cfg
    )

def set_model_params(model_id: str,
                     max_tokens: int = 300,
                     top_p: float = 0.9,
                     temperature: float = 0.3):
    """
    Build the provider-specific sampling config.
    """
    if ".meta." in model_id:           # Meta Llama / Scout / Maverick
        return {
            "max_gen_len": max_tokens,
            "top_p": top_p,
            "temperature": temperature,
        }
    elif ".anthropic." in model_id:    # Claude 3
        return {
            "max_tokens": max_tokens,
            "top_p": top_p,
            "temperature": temperature,
        }
    # Default for Nova / Titan / Amazon models
    return {
        "maxTokens": max_tokens,
        "topP": top_p,
        "temperature": temperature,
    }

def converse_with_nova(req: Union[NovaRequest, Dict[str, Any]], bedrock_client):
    """
    Send a request to Bedrock's converse API.
    """
    # Accept dict or dataclass
    if isinstance(req, dict):
        req = NovaRequest(**req)

    payload = {
        "modelId": req.model_id,
        "messages": req.messages,
    }

    # 1) Provider routing: decide where to place the knobs
    if ".meta." in req.model_id or ".anthropic." in req.model_id \
       or ".mistral." in req.model_id:
        payload["additionalModelRequestFields"] = req.params
    else:
        payload["inferenceConfig"] = req.params

    # 2) Optionals
    if req.system:
        payload["system"] = req.system
    if req.toolConfig:
        payload["toolConfig"] = req.toolConfig

    # 3) Call Bedrock
    logger.info(f"Sending request to Bedrock: ")
    return bedrock_client.converse(**payload)

def _extract_text(resp_json: dict) -> str:
    """
    Bedrock Nova returns:
        {"output":{"message":{"content":[{"text":"..."}]}}}
    """
    try:
        return resp_json["output"]["message"]["content"][0]["text"].strip()
    except (KeyError, IndexError, TypeError):
        raise RuntimeError("Unexpected response shape from Bedrock") from None

def _strip_fences(text: str) -> str:
    """
    Removes ```json ... ``` or ``` ... ``` even if the opening fence is
    immediately followed by '{'.
    """
    text = text.strip()

    # opening fence
    text = re.sub(r'^```(?:json)?', '', text, flags=re.IGNORECASE).lstrip()
    # closing fence
    text = re.sub(r'```$', '', text).rstrip()
    return text

def _normalise(raw_obj: dict, *, file_path: str | None = None) -> dict:
    """
    • rename documenttype → document_type (case-insensitive)
    • ensure document_number and path exist (fallbacks)
    • keep snippet only if present
    """
    norm = {k.lower(): v for k, v in raw_obj.items()}          # case-fold keys

    # key mapping
    if "documenttype" in norm and "document_type" not in norm:
        norm["document_type"] = norm.pop("documenttype")

    # fallback values
    if "document_number" not in norm:
        # try to derive from the file path    e.g.  .../800035887/...
        if file_path:
            m = re.search(r"/(\d{6,})/", file_path)
            norm["document_number"] = m.group(1) if m else "UNKNOWN"
        else:
            norm["document_number"] = "UNKNOWN"

    if "path" not in norm and file_path:
        norm["path"] = file_path
    elif "path" not in norm:
        norm["path"] = "UNKNOWN"

    return norm

def parse_classification(resp_json: dict, *, pdf_path: str | None = None) -> dict:
    """
    Parse the classification response from Bedrock.
    """
    raw_text = _extract_text(resp_json)
    raw_text = _strip_fences(raw_text)          # remove ```json … ```

    try:
        raw_obj = json.loads(raw_text)
    except json.JSONDecodeError as e:
        # last-chance: grab first '{' … last '}'
        m1, m2 = raw_text.find("{"), raw_text.rfind("}")
        if m1 != -1 and m2 != -1:
            raw_obj = json.loads(raw_text[m1:m2+1])
        else:
            raise RuntimeError(f"Assistant did not return JSON: {e}") from None

    return _normalise(raw_obj, file_path=pdf_path)

def parse_extraction_response(resp: dict) -> dict:
    """
    Parse a Bedrock response dict and extract data for extraction.

    Args:
        resp: The Bedrock response

    Returns:
        dict: The extracted data
    """
    # Extract the text from the response
    text = resp["output"]["message"]["content"][0]["text"]

    # Extract the JSON snippet between ```json and ```
    match = re.search(r"```json\s*(\{[\s\S]*?\})\s*```", text)
    if not match:
        raise ValueError("Embedded JSON not found in Bedrock response")

    raw = match.group(1)

    # Parse it
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse embedded JSON: {e}")

    return data

def create_payload_data_extraction(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract payload data from the response for extraction.

    Args:
        data: The response data

    Returns:
        dict: The payload data
    """
    # The payload might sit under "result" or at the top level
    payload = data.get("result", data)

    # Return all fields
    response = {key: value for key, value in payload.items()}

    return response
