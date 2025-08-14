# =============================================================================
# TEST UTILITY FUNCTIONS
# =============================================================================
# Supporting functions for CECRL prompt testing

import json
import re
from pathlib import Path
from typing import Dict, Any, Tuple
import logging

# Import shared modules
from bedrock_client import set_model_params, converse_with_nova, NovaRequest, parse_extraction_response
from pdf_processor import create_message
from s3_handler import get_pdf_from_s3, extract_s3_path

logger = logging.getLogger(__name__)

# =============================================================================
# S3 AND PDF HANDLING
# =============================================================================

def get_pdf_bytes_from_s3_path(s3_path: str, s3_client) -> bytes:
    """
    Extract PDF bytes from S3 path (same as Lambda functions).
    
    Args:
        s3_path: Full S3 URI like s3://bucket/key
        s3_client: Boto3 S3 client
        
    Returns:
        bytes: PDF content
    """
    try:
        # Parse S3 path
        bucket, key = extract_s3_path(s3_path)
        logger.info(f"Extracting PDF from s3://{bucket}/{key}")
        
        # Get PDF bytes (no local download)
        response = s3_client.get_object(Bucket=bucket, Key=key)
        pdf_bytes = response['Body'].read()
        
        logger.info(f"PDF retrieved: {len(pdf_bytes)} bytes")
        return pdf_bytes
        
    except Exception as e:
        logger.error(f"Failed to get PDF from {s3_path}: {e}")
        raise

# =============================================================================
# PROMPT LOADING
# =============================================================================

def load_prompt_files(version: str) -> Tuple[str, str]:
    """
    Load system and user prompts for specified version.
    
    Args:
        version: "v2.0.0" or "v2.1.0"
        
    Returns:
        Tuple[system_prompt, user_prompt]
    """
    try:
        base_path = Path(f"prompts/{version}")
        
        system_path = base_path / "system.txt"
        user_path = base_path / "user.txt"
        
        if not system_path.exists() or not user_path.exists():
            raise FileNotFoundError(f"Prompt files not found for {version}")
            
        system_prompt = system_path.read_text(encoding='utf-8')
        user_prompt = user_path.read_text(encoding='utf-8')
        
        logger.info(f"Loaded prompts for {version}")
        return system_prompt, user_prompt
        
    except Exception as e:
        logger.error(f"Failed to load prompts for {version}: {e}")
        raise

def build_extraction_prompts(system_template: str, user_template: str, 
                           document_info: Dict[str, Any]) -> Tuple[str, str]:
    """
    Build the final prompts with schema and examples injected.
    
    Args:
        system_template: Raw system prompt template
        user_template: Raw user prompt template  
        document_info: Document metadata
        
    Returns:
        Tuple[final_system_prompt, final_user_prompt]
    """
    try:
        # Load schema and examples
        schema_path = Path("shared/evaluation_type/CECRL/schema.json")
        examples_dir = Path("shared/evaluation_type/CECRL/examples")
        
        # Read schema
        schema_content = schema_path.read_text().strip()
        
        # Read all examples
        example_blocks = []
        for example_file in examples_dir.glob("*.json"):
            content = example_file.read_text().strip()
            example_blocks.append(f"```json\n{content}\n```")
        
        examples_section = "\n\n".join(example_blocks)
        
        # Inject into system prompt
        final_system = system_template.replace("$schema", schema_content)
        final_system = final_system.replace("$examples_section", examples_section)
        
        # Build user prompt (basic substitution)
        final_user = user_template.replace("$pdf_path", document_info.get('s3_path', ''))
        final_user = final_user.replace("$document_type", "person")
        final_user = final_user.replace("$document_number", "test")
        final_user = final_user.replace("$category", "CECRL")
        
        logger.info("Extraction prompts built successfully")
        return final_system, final_user
        
    except Exception as e:
        logger.error(f"Failed to build extraction prompts: {e}")
        raise

# =============================================================================
# BEDROCK INTERACTION
# =============================================================================

def run_extraction_with_prompts(pdf_bytes: bytes, system_prompt: str, 
                               user_prompt: str, document_path: str,
                               bedrock_client, model_id: str) -> Dict[str, Any]:
    """
    Run extraction using specified prompts (same pattern as Lambda).
    
    Args:
        pdf_bytes: PDF content bytes
        system_prompt: System prompt text
        user_prompt: User prompt text  
        document_path: S3 path for context
        bedrock_client: Bedrock client
        model_id: Model identifier
        
    Returns:
        Dict with extraction results
    """
    try:
        # Create Bedrock message (same as Lambda)
        messages = [create_message(user_prompt, "user", pdf_bytes, document_path)]
        system_parameter = [{"text": system_prompt}]
        
        # Model configuration
        cfg = set_model_params(model_id, 8192, 0.9, 0.1)
        
        # Request parameters
        req_params = {
            "model_id": model_id,
            "messages": messages,
            "params": {**cfg},
            "system": system_parameter
        }
        
        logger.info(f"Calling Bedrock with model: {model_id}")
        
        # Call Bedrock
        response = converse_with_nova(NovaRequest(**req_params), bedrock_client)
        
        # Parse response
        extracted_data = parse_extraction_response(response)
        
        logger.info("Extraction completed successfully")
        return {
            "success": True,
            "data": extracted_data,
            "raw_response": response,
            "model_used": model_id
        }
        
    except Exception as e:
        logger.error(f"Extraction failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "model_used": model_id
        }

print("✅ Utility functions loaded")