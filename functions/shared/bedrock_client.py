"""
AWS Bedrock client utilities - MODIFIED VERSION
- Eliminada función handle_pypdf_fallback()
- Mantenidos retry mechanisms para throttling
- Conservadas todas las demás funcionalidades
"""

import boto3, json, re, logging, os, base64, time, random
from botocore.config import Config
from botocore.exceptions import ClientError
from typing import Dict, Any, Union, List, Optional
from dataclasses import dataclass
from .text_utils import clean_text_for_json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Enhanced Bedrock client configuration with retry settings
cfg = Config(
    connect_timeout=30, 
    read_timeout=300,
    retries={
        'max_attempts': 8,   # Optimized for low volume scenarios
        'mode': 'adaptive'   # Adaptive retry mode for better throttling handling
    }
)
region = os.environ.get("REGION", "us-east-2")

@dataclass
class BedrockRequest:
    model_id: str
    messages: List[Dict[str, Any]]
    params: Dict[str, Any]
    system: Optional[List] = None
    toolConfig: Optional[Dict[str, Any]] = None

def create_bedrock_client():
    """
    Create and return a Bedrock client with enhanced retry configuration.
    """
    session = boto3.Session()
    return session.client(
        "bedrock-runtime",
        region_name=region,
        config=cfg
    )

def is_throttling_error(error) -> bool:
    """Check if the error is a throttling-related error"""
    error_str = str(error)
    throttling_indicators = [
        'ThrottlingException',
        'TooManyRequestsException', 
        'Too many tokens',
        'Rate exceeded',
        'Throttled',
        'throttling'
    ]
    return any(indicator in error_str for indicator in throttling_indicators)

def calculate_backoff_delay(attempt: int, base_delay: float = 2.0, max_delay: float = 120.0) -> float:
    """Calculate exponential backoff delay with jitter"""
    # Exponential backoff: base_delay * (2^attempt) + random jitter
    delay = min(base_delay * (2 ** attempt), max_delay)
    # Add random jitter (±25% of delay)
    jitter = delay * 0.25 * (2 * random.random() - 1)
    final_delay = max(0.5, delay + jitter)  # Minimum 0.1 seconds
    return final_delay

def call_bedrock_with_retry(bedrock_client, api_call, request_params: dict, max_retries: int = 8) -> Dict[str, Any]:
    """
    Call Bedrock API with exponential backoff retry for throttling errors.
    
    Args:
        bedrock_client: Bedrock client instance
        api_call: Function to call (converse or invoke_model)
        request_params: Parameters for the API call
        max_retries: Maximum number of retry attempts
        
    Returns:
        dict: API response
    """
    if max_retries is None:
        max_retries = int(os.environ.get('BEDROCK_RETRY_ATTEMPTS', '8'))
    
    logger.info(f"Starting Bedrock call with max {max_retries} retries")
    last_exception = None
    
    for attempt in range(max_retries + 1):
        try:
            logger.info(f"Bedrock API call attempt {attempt + 1}/{max_retries + 1}")
            
            # Call the API
            response = api_call(**request_params)
            
            # Success - log and return
            if attempt > 0:
                logger.info(f"Bedrock call succeeded on attempt {attempt + 1}")
            
            return response
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            error_message = str(e)
            last_exception = e
            
            # Check if it's a throttling error
            if is_throttling_error(error_message) or error_code in ['ThrottlingException', 'TooManyRequestsException']:
                if attempt < max_retries:
                    delay = calculate_backoff_delay(attempt)
                    logger.warning(f"Throttling detected (attempt {attempt + 1}). Retrying in {delay:.2f} seconds. Error: {error_message}")
                    time.sleep(delay)
                    continue
                else:
                    logger.error(f"Max retries reached for throttling error: {error_message}")
                    raise e
            else:
                # Non-throttling error - don't retry
                logger.error(f"Non-throttling error, not retrying: {error_message}")
                raise e
                
        except Exception as e:
            last_exception = e
            # For non-ClientError exceptions, only retry if it looks like throttling
            if is_throttling_error(str(e)) and attempt < max_retries:
                delay = calculate_backoff_delay(attempt)
                logger.warning(f"Potential throttling error (attempt {attempt + 1}). Retrying in {delay:.2f} seconds. Error: {str(e)}")
                time.sleep(delay)
                continue
            else:
                logger.error(f"Non-throttling exception, not retrying: {str(e)}")
                raise e
    
    # If we get here, all retries failed
    logger.error(f"All retry attempts failed. Last exception: {str(last_exception)}")
    raise last_exception

def call_converse_api(request: BedrockRequest, bedrock_client) -> Dict[str, Any]:
    """
    Call Bedrock Converse API with retry logic
    """
    payload = {
        "modelId": request.model_id,
        "messages": request.messages,
    }

    if request.params:
        payload["inferenceConfig"] = request.params
    if request.system:
        payload["system"] = request.system
    if request.toolConfig:
        payload["toolConfig"] = request.toolConfig

    logger.info(f"Calling Converse API for model: {request.model_id}")
    
    # Use retry wrapper
    return call_bedrock_with_retry(
        bedrock_client, 
        bedrock_client.converse, 
        payload
    )

def call_invoke_model_api(request: BedrockRequest, bedrock_client) -> Dict[str, Any]:
    """
    Call Bedrock InvokeModel API with retry logic
    """
    # Build Anthropic-specific payload
    payload = {
        "anthropic_version": "bedrock-2023-05-31",
        "messages": request.messages,
        **request.params
    }
    
    logger.info(f"Calling InvokeModel API for model: {request.model_id}")
    
    # Use retry wrapper for invoke_model
    response = call_bedrock_with_retry(
        bedrock_client,
        lambda **kwargs: bedrock_client.invoke_model(**kwargs),
        {
            "modelId": request.model_id,
            "body": json.dumps(payload),
            "contentType": "application/json"
        }
    )
    
    # Parse InvokeModel response
    response_body = json.loads(response['body'].read())

    text_content = ""
    content_blocks = response_body.get('content', [])
        
    # Find the text content block
    for block in content_blocks:
        if block.get('type') == 'text':
            text_content = block.get('text', '')
            break
        
    if not text_content:
        raise ValueError(f"No text content found in response. Content blocks: {content_blocks}")
        
    logger.info(f"Successfully extracted text content ({len(text_content)} characters)")

    # Convert to Converse API format for consistency
    return {
        "output": {
            "message": {
                "content": [
                    {
                        "text": text_content
                    }
                ]
            }
        },
        "stopReason": response_body.get("stop_reason", "end_turn"),
        "usage": response_body.get("usage", {}),
        "ResponseMetadata": response.get('ResponseMetadata', {}),
        "raw_anthropic_response": response_body
    }

# Add rate limiting between calls
def add_inter_call_delay():
    """Add delay between Bedrock calls to avoid hitting rate limits"""
    delay_seconds = float(os.environ.get('INTER_CALL_DELAY', '5.0'))
    if delay_seconds > 0:
        logger.debug(f"Adding {delay_seconds}s delay between Bedrock calls")
        time.sleep(delay_seconds)

# Keep existing functions with enhanced error handling...
def is_nova_model(model_id: str) -> bool:
    """Check if the model is a Nova model"""
    return "nova" in model_id.lower()

def is_anthropic_model(model_id: str) -> bool:
    """Check if the model is an Anthropic model"""
    return "anthropic" in model_id.lower()

def set_model_params_anthropic(max_tokens, top_p, temperature) -> Dict[str, Any]:
    """Set model parameters for Anthropic models"""
    return {
        "max_tokens": max_tokens,
        "top_p": top_p,
        "temperature": temperature,
        "thinking": {
            "type": "enabled",
            "budget_tokens": 4096, #doble de tokens
        },
    }

def set_model_params_converse(max_tokens, top_p, temperature) -> Dict[str, Any]:
    """Set model parameters for Converse API"""
    return {
        "maxTokens": max_tokens,
        "topP": top_p,
        "temperature": temperature,
    }

def call_bedrock_unified(req: Union[BedrockRequest, Dict[str, Any]], bedrock_client):
    """
    Unified function to call appropriate Bedrock API based on model type with enhanced retry logic
    """
    # Accept dict or dataclass
    if isinstance(req, dict):
        req = BedrockRequest(**req)

    # Add small delay between calls to avoid rate limiting
    add_inter_call_delay()
    
    # Route to appropriate API based on model type
    if is_anthropic_model(req.model_id):
        response = call_invoke_model_api(req, bedrock_client)
    else:
        response = call_converse_api(req, bedrock_client)
    
    # Add metadata for tracking
    if isinstance(response, dict):
        response['model_id'] = req.model_id
        response['api_used'] = 'invoke_model' if is_anthropic_model(req.model_id) else 'converse'
        response['model_params'] = req.params
    
    return response

def _extract_text(resp_json: dict) -> str:
    """
    Bedrock Nova returns:
        {"output":{"message":{"content":[{"text":"..."}]}}}
    """
    try:
        text = resp_json["output"]["message"]["content"][0]["text"].strip()
        return clean_text_for_json(text)
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
    text = clean_text_for_json(text)
    return text

def _normalise(raw_obj: dict, *, file_path: str | None = None) -> dict:
    """
    rename documenttype - document_type (case-insensitive)
    ensure document_number and path exist (fallbacks)
    keep snippet only if present
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

def parse_classification_response_fallback(response: Dict[str, Any], folder_path: str = None) -> Dict[str, Any]:
    """
    Alternative parsing method that identifies and corrects specific corrupt characters
    that cause JSON parsing errors, without guessing content
    """
    try:
        # Extract raw text from response
        raw_text = _extract_text(response)
        logger.info("Attempting alternative parsing to correct corrupt JSON characters")
        
        # Remove code fences
        cleaned_text = _strip_fences(raw_text)
        
        # STEP 1: Identify and correct specific malformed escapes that cause JSON errors
        
        # Fix malformed quote escapes:
        cleaned_text = re.sub(r'\\{2,}"', r'"', cleaned_text)  # \\\" or \\\\" -> "
        
        # Fix multiple escape sequences: \\\\n -> \n, \\\\t -> \t
        cleaned_text = re.sub(r'\\{2,}n', r'\\n', cleaned_text)  # \\\\n -> \n
        cleaned_text = re.sub(r'\\{2,}t', r'\\t', cleaned_text)  # \\\\t -> \t
        
        # Fix malformed backslash escapes: 
        cleaned_text = re.sub(r'\\{3,}', r'\\\\', cleaned_text)  # \\\\\ -> \\
        
        # STEP 2: Try to parse the corrected JSON
        try:
            raw_obj = json.loads(cleaned_text)
            logger.info("Corrected JSON parsed successfully")
        except json.JSONDecodeError as json_error:
            logger.info(f"JSON still invalid after basic corrections: {json_error}")
            
            # STEP 3: If still failing, apply more aggressive corrections only to "text" field
            # Extract category (which is usually not corrupted)
            category_match = re.search(r'"category"\s*:\s*"([^"]+)"', cleaned_text)
            category = category_match.group(1) if category_match else "UNKNOWN"
            
            # For text field, extract only content between last valid quotes
            # Look for pattern: "text": "..." 
            text_match = re.search(r'"text"\s*:\s*"(.*)"(?:\s*}?\s*$)', cleaned_text, re.DOTALL)
            
            if text_match:
                text_content = text_match.group(1)
                
                # Clean problematic escape characters ONLY in text content
                text_content = text_content.replace('\\"', '"')  #
                text_content = re.sub(r'\\+$', '', text_content)  # Remove backslashes at end
                
                # Reconstruct valid JSON
                reconstructed_json = f'{{"category": "{category}", "text": "{text_content}"}}'
                
                try:
                    raw_obj = json.loads(reconstructed_json)
                    logger.info("Reconstructed JSON parsed successfully")
                except json.JSONDecodeError:
                    # If reconstruction fails, use basic values
                    raw_obj = {
                        "category": category,
                        "text": text_content[:500] + "..." if len(text_content) > 500 else text_content
                    }
                    logger.info("Using simplified JSON with truncated content")
            else:
                # If we can't extract text, use default values
                raw_obj = {
                    "category": category,
                    "text": "[UNPARSEABLE CONTENT - CORRUPT CHARACTERS]"
                }
                logger.warning("Could not extract text field, using placeholder")
        
        # STEP 4: Use _normalise to add document_number and path
        result = _normalise(raw_obj, file_path=folder_path)
        
        logger.info("Alternative parsing successful")
        logger.info(f"    Category: {result.get('category', 'UNKNOWN')}")
        logger.info(f"    Text: {len(result.get('text', ''))} characters")
        
        return result
        
    except Exception as e:
        logger.error(f"Error in alternative parsing: {e}")
        # If everything fails, return minimal structure for _normalise
        raw_obj = {
            "category": "UNKNOWN", 
            "text": f"ERROR_FALLBACK_PARSING: {str(e)}"
        }
        return _normalise(raw_obj, file_path=folder_path)

def parse_classification(resp_json: dict, *, pdf_path: str | None = None) -> dict:
    """
    Parse the classification response from Bedrock with robust error handling.
    """
    try:
        raw_text = _extract_text(resp_json)
        raw_text = _strip_fences(raw_text)          

        try:
            raw_obj = json.loads(raw_text)
            logger.debug(f"Raw JSON: {raw_obj}")  # Debugging output
        except json.JSONDecodeError as e:
            # last-chance: grab first '{' … last '}'
            m1, m2 = raw_text.find("{"), raw_text.rfind("}")
            if m1 != -1 and m2 != -1:
                raw_obj = json.loads(raw_text[m1:m2+1])
            else:
                logger.warning(f"Standard JSON parsing failed: {e}")
                # Try alternative parsing method
                return parse_classification_response_fallback(resp_json, pdf_path)

        return _normalise(raw_obj, file_path=pdf_path)
        
    except Exception as e:
        logger.error(f"Error in standard classification parsing: {e}")
        # Fallback to alternative parsing
        return parse_classification_response_fallback(resp_json, pdf_path)

def parse_extraction_response(resp: dict) -> dict:
    """
    Parse a Bedrock response dict and extract data for extraction.
    Handles JSON, text responses, and creates structured data from natural language.

    Args:
        resp: The Bedrock response

    Returns:
        dict: The extracted data
    """
    # Extract the text from the response
    text = resp["output"]["message"]["content"][0]["text"]
    logger.info(f"Parsing extraction response ({len(text)} characters)")
    
    # MÉTODO 1: Buscar JSON envuelto en markdown
    match = re.search(r"```json\s*(\{[\s\S]*?\})\s*```", text)
    if match:
        try:
            raw = match.group(1)
            data = json.loads(raw)
            logger.info("Successfully parsed JSON from markdown code block")
            return data
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON from markdown: {e}")
    
    # MÉTODO 2: Buscar JSON directo
    try:
        start_idx = text.find('{')
        if start_idx != -1:
            brace_count = 0
            end_idx = -1
            
            for i in range(start_idx, len(text)):
                if text[i] == '{':
                    brace_count += 1
                elif text[i] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        end_idx = i
                        break
            
            if end_idx != -1:
                raw = text[start_idx:end_idx + 1]
                data = json.loads(raw)
                logger.info("Successfully parsed raw JSON from response text")
                return data
    except (json.JSONDecodeError, ValueError) as e:
        logger.debug(f"Raw JSON parsing failed: {e}")
    
    # MÉTODO 3: Buscar múltiples objetos JSON
    try:
        json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
        matches = re.findall(json_pattern, text, re.DOTALL)
        
        for match_text in matches:
            try:
                data = json.loads(match_text)
                logger.info("Successfully parsed JSON using flexible regex")
                return data
            except json.JSONDecodeError:
                continue
    except Exception as e:
        logger.debug(f"Flexible regex parsing failed: {e}")
    
    # MÉTODO 4: Analizar respuestas especiales
    if "ForReview" in text or "no document" in text.lower() or "not see any PDF" in text:
        logger.info("Model indicated document cannot be processed, creating ForReview response")
        return {
            "result": {
                "PrincipalCompanyName": "ForReview",
                "DocumentCategory": "ForReview", 
                "TaxId": "ForReview",
                "IdentificationType": "ForReview",
                "Country": "ForReview",
                "IdentificationDetails": {
                    "Source": "ForReview",
                    "Indicators": [],
                    "ConflictingSources": ["Model indicated no document provided"],
                    "RequiresReview": "true"
                },
                "RelatedParties": []
            },
            "DocumentType": "unknown",
            "Category": "ForReview"
        }
    
    # MÉTODO 5: Extraer información de texto natural (NUEVO)
    logger.info("Attempting to parse structured information from natural text response")
    try:
        return parse_natural_language_response(text)
    except Exception as e:
        logger.warning(f"Natural language parsing failed: {e}")
    
    # MÉTODO 6: Crear respuesta de error estructurada
    logger.error(f"All parsing methods failed. Creating error response.")
    logger.error(f"Response text (first 500 chars): {text[:500]}...")
    
    return {
        "result": {
            "error_type": "parsing_failed",
            "error_message": "Could not parse response as JSON or extract structured data",
            "raw_response_snippet": text[:500],
            "requires_manual_review": True
        },
        "DocumentType": "unknown",
        "Category": "unknown"
    }

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

def parse_natural_language_response(text: str) -> dict:
    """
    Parse natural language response to extract structured data.
    Handles cases where the model returns useful information but not in JSON format.
    """
    logger.info("Parsing natural language response for structured data")
    
    # Patrones para extraer información específica
    extracted_data = {
        "result": {
            "parsing_method": "natural_language_extraction",
            "original_response": text[:1000]  # Primeros 1000 caracteres
        },
        "DocumentType": "company",
        "Category": "unknown"
    }
    
    # Extraer NIT/Identificación fiscal
    nit_patterns = [
        r"NIT[:\s]*\.?(\d+[\.\-]\d+[\.\-]\d+)",
        r"NIT[:\s]*(\d+[\.\-]\d+[\.\-]\d+)",
        r"NIT[:\s]*(\d+)",
        r"identificación[:\s]+(\d+[\.\-]\d+[\.\-]\d+)",
        r"número[:\s]+(\d+[\.\-]\d+[\.\-]\d+)"
    ]
    
    for pattern in nit_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            extracted_data["result"]["TaxId"] = match.group(1).strip()
            break
    
    # Extraer nombre de empresa
    company_patterns = [
        r"sociedad\s+([^\n]+?)(?:\s+NIT|\s+de|\n)",
        r"empresa\s+([^\n]+?)(?:\s+NIT|\s+de|\n)",
        r"compañía\s+([^\n]+?)(?:\s+NIT|\s+de|\n)",
        r"([A-Z][A-Z\s]+S\.A\.S?)",
        r"([A-Z][A-Z\s]+LTDA)",
        r"([A-Z][A-Z\s]+S\.A)"
    ]
    
    for pattern in company_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            company_name = match.group(1).strip()
            if len(company_name) > 3:  # Evitar coincidencias muy cortas
                extracted_data["result"]["PrincipalCompanyName"] = company_name
                break
    
    # Buscar tabla de accionistas o socios
    related_parties = []
    
    # Patrón para encontrar información de accionistas
    shareholder_patterns = [
        r"(\w+(?:\s+\w+)*)\s*\|\s*(\d+[\.\,\d]*)\s*\|\s*(\d+[\.\,\d]*)\s*\|\s*(\d+%?)",
        r"(\w+(?:\s+\w+)*)\s+(\d+[\.\,\d]+)\s+(\d+[\.\,\d]+)\s+(\d+%?)",
    ]
    
    for pattern in shareholder_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            name, doc, shares, percentage = match
            if len(name.strip()) > 2:  # Nombres válidos
                related_parties.append({
                    "name": name.strip(),
                    "identification": doc.strip(),
                    "shares": shares.strip(),
                    "percentage": percentage.strip()
                })
    
    if related_parties:
        extracted_data["result"]["RelatedParties"] = related_parties
    
    # Determinar categoría basada en contenido
    if "accionista" in text.lower() or "acciones" in text.lower():
        extracted_data["result"]["DocumentCategory"] = "Shareholder Information"
        extracted_data["Category"] = "ACC"
    elif "representante" in text.lower() or "legal" in text.lower():
        extracted_data["result"]["DocumentCategory"] = "Legal Representative"
        extracted_data["Category"] = "CERL"
    
    # Marcar campos faltantes como ForReview
    required_fields = ["PrincipalCompanyName", "TaxId", "DocumentCategory"]
    for field in required_fields:
        if field not in extracted_data["result"]:
            extracted_data["result"][field] = "ForReview"
    
    # Agregar metadatos de extracción
    extracted_data["result"]["extraction_confidence"] = "medium"
    extracted_data["result"]["requires_verification"] = True
    
    logger.info(f"Natural language extraction completed. Found: Company={extracted_data['result'].get('PrincipalCompanyName', 'N/A')}, TaxId={extracted_data['result'].get('TaxId', 'N/A')}, Parties={len(related_parties)}")
    
    return extracted_data