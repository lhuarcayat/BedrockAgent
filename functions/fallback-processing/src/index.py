"""
Enhanced Fallback processing Lambda for documents that failed in classification or extraction.
SIMPLIFIED VERSION - Only uses fallback model, saves to extraction/ folder.

This module handles fallback processing using PyPDF/Textract + Fallback Model for intelligent processing,
with comprehensive error handling and manual review records.

SIMPLIFIED FLOW:
1. handler() - Main entry point with batch processing
2. Determine if classification or extraction based on payload
3. PHASE 1: PyPDF text extraction → Fallback Model processing
4. PHASE 2: If failed, Textract text extraction → Fallback Model processing  
5. PHASE 3: If both failed, save for manual review
6. SUCCESS: Save results in extraction/ folder with same format as normal extraction

Architecture: Follows SOLID principles with intelligent fallback processing
"""

import json
import logging
import os
import re
import boto3
from boto3.dynamodb.conditions import Key
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path

from shared.aws_clients import create_dynamodb_client, create_s3_client
from shared.pdf_processor import extract_pdf_text_with_pypdf, extract_pdf_text_with_textract
from shared.s3_handler import extract_s3_path, save_to_s3
from shared.result_builder import build_document_info, extract_document_number_from_path, extract_original_category_from_path
from shared.bedrock_client import (
    create_bedrock_client, set_model_params_anthropic, set_model_params_converse,
    call_bedrock_unified, BedrockRequest, is_anthropic_model,
    parse_classification, parse_extraction_response, create_payload_data_extraction
)
from shared.prompt_loader import prompt_loader
from shared.processing_result import ProcessingResult
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()
logger.setLevel(logging.INFO)

FOLDER_PREFIX = os.environ.get("FOLDER_PREFIX", "par-servicios-poc")
DESTINATION_BUCKET = os.environ.get("DESTINATION_BUCKET")

def determine_process_type_and_prompts(payload: Dict[str, Any]) -> Tuple[str, str, str]:
    """
    Determine if this is classification or extraction based on payload and get appropriate prompts.
    
    Args:
        payload: The payload from failed processing
        
    Returns:
        tuple: (process_type, system_prompt, user_prompt)
    """
    # Check if this came from extraction queue (has 'result' with classification data)
    result = payload.get('result', {})
    
    if 'category' in result and result.get('category') not in ['UNKNOWN', 'BLANK', 'LINK_ONLY']:
        # This is an extraction failure - we have a classified category
        process_type = 'extraction'
        category = result['category']
        try:
            system_prompt, user_prompt = prompt_loader.get_extraction_prompts(category)
            logger.info(f"Loaded extraction prompts for category: {category}")
        except Exception as e:
            logger.error(f"Failed to load extraction prompts for {category}: {e}")
            # Fallback to classification
            process_type = 'classification'
            system_prompt, user_prompt = prompt_loader.get_classification_prompts()
    else:
        # This is a classification failure
        process_type = 'classification'
        system_prompt, user_prompt = prompt_loader.get_classification_prompts()
        logger.info("Loaded classification prompts")
    
    return process_type, system_prompt, user_prompt

def create_text_message_for_claude(user_prompt: str, extracted_text: str) -> List[Dict[str, Any]]:
    """
    Create message for Claude using extracted text instead of PDF bytes.
    
    Args:
        user_prompt: The original user prompt
        extracted_text: Text extracted from PyPDF or Textract
        
    Returns:
        list: Messages for Claude
    """
    return [{
        "role": "user",
        "content": [
            {
                "type": "text",
                "text": user_prompt,
                "cache_control": {"type": "ephemeral"}
            },
            {
                "type": "text", 
                "text": f"\n\n--- CONTENIDO DEL DOCUMENTO ---\n{extracted_text}"
            }
        ]
    }]

def try_claude_with_extracted_text(model_id: str, user_prompt: str, system_prompt: str, 
                                   extracted_text: str, process_type: str) -> ProcessingResult:
    """
    Attempt processing with Claude using extracted text.
    
    Args:
        model_id: Claude model to use
        user_prompt: User prompt
        system_prompt: System prompt  
        extracted_text: Extracted text from PDF
        process_type: 'classification' or 'extraction'
        
    Returns:
        ProcessingResult: Result of Claude processing
    """
    try:
        bedrock_client = create_bedrock_client()
        
        # Create messages with extracted text
        messages = create_text_message_for_claude(user_prompt, extracted_text)
        
        # Configure parameters based on model type
        if is_anthropic_model(model_id):
            params = set_model_params_anthropic(9000, 1, 1)
            request = BedrockRequest(
                model_id=model_id,
                messages=messages,
                params=params
            )
        else:
            params = set_model_params_converse(8000, 1, 0)
            system = [
                {"text": system_prompt},
                {"cachePoint": {"type": "default"}}
            ]
            request = BedrockRequest(
                model_id=model_id,
                messages=messages,
                params=params,
                system=system
            )
        
        # Call Claude
        logger.info(f"Calling Claude {model_id} with extracted text ({len(extracted_text)} chars)")
        raw_response = call_bedrock_unified(request, bedrock_client)
        
        # Handle content filtering
        if raw_response.get('stopReason') == 'content_filtered':
            return ProcessingResult(
                is_success=False,
                data=None,
                status='content_filtered',
                error_message=f"Content filtered by {model_id}",
                model_used=model_id
            )
        
        # Parse response based on process type
        try:
            if process_type == 'classification':
                data = parse_classification(raw_response)
                logger.info(f"Successfully parsed classification: {data.get('category', 'UNKNOWN')}")
            else:  # extraction
                data = parse_extraction_response(raw_response)
                payload_data = create_payload_data_extraction(data)
                data = {'meta': data, 'payload_data': payload_data, 'raw_response': raw_response}
                logger.info(f"Successfully parsed extraction")
            
            return ProcessingResult(
                is_success=True,
                data=data,
                status='success',
                error_message=None,
                model_used=model_id
            )
            
        except Exception as parse_error:
            logger.error(f"Parse error with {model_id}: {parse_error}")
            return ProcessingResult(
                is_success=False,
                data=None,
                status='parse_error',
                error_message=f"Failed to parse {model_id} response: {str(parse_error)}",
                model_used=model_id
            )
            
    except Exception as model_error:
        logger.error(f"Model error with {model_id}: {model_error}")
        return ProcessingResult(
            is_success=False,
            data=None,
            status='model_error',
            error_message=f"Model {model_id} failed: {str(model_error)}",
            model_used=model_id
        )

def save_successful_fallback_to_extraction_folder(result_data: Dict[str, Any], s3_info: Dict[str, str], 
                                                 category: str, document_number: str, 
                                                 method_used: str, processing_time: float,
                                                 process_type: str, raw_response: Dict[str, Any]) -> None:
    """
    Save successful fallback results to extraction/ folder with same format as normal extraction.
    NO longer creates fallback/ folder.
    
    Args:
        result_data: Parsed result data
        s3_info: S3 bucket and key info
        category: Document category
        document_number: Document number
        method_used: Method that succeeded (e.g., "textract_claude_...")
        processing_time: Time taken to process
        process_type: "classification" or "extraction"
        raw_response: Raw Bedrock response
    """
    try:
        # Extract filename for unique identifier
        filename = Path(s3_info['s3_key']).name
        file_id = Path(filename).stem
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if process_type == 'extraction':
            # Save to extraction/ folder with same format as normal extraction
            meta_folder = f"{FOLDER_PREFIX}/extraction/{category}/{document_number}"
            raw_folder = f"RAW/{category}/{document_number}"
            
            # Build meta structure similar to normal extraction
            enhanced_meta = result_data['meta'].copy()
            enhanced_meta['extraction_model_used'] = raw_response.get('model_id', 'unknown')
            enhanced_meta['method_used'] = method_used
            enhanced_meta['processing_time_seconds'] = processing_time
            enhanced_meta['came_from_fallback'] = True  # Only difference to indicate origin
            enhanced_meta['extraction_timestamp'] = raw_response.get('ResponseMetadata', {}).get('HTTPHeaders', {}).get('date')
            enhanced_meta['file_info'] = {
                'source_key': s3_info['s3_key'],
                'category': category,
                'document_number': document_number,
                'file_id': file_id
            }
            
            # Build raw response
            enhanced_raw = raw_response.copy()
            enhanced_raw['extraction_model_used'] = raw_response.get('model_id', 'unknown')
            enhanced_raw['method_used'] = method_used
            enhanced_raw['processing_time_seconds'] = processing_time
            enhanced_raw['came_from_fallback'] = True
            enhanced_raw['file_info'] = {
                'source_key': s3_info['s3_key'],
                'category': category,
                'document_number': document_number,
                'file_id': file_id
            }
            
            # Save with same naming as normal extraction
            meta_destination_key = f"{meta_folder}/extraction_{file_id}_{timestamp}.json"
            save_to_s3(enhanced_meta, DESTINATION_BUCKET, meta_destination_key)
            
            raw_destination_key = f"{raw_folder}/raw_extraction_{file_id}_{timestamp}.json"
            save_to_s3(enhanced_raw, DESTINATION_BUCKET, raw_destination_key)
            
            logger.info(f"Successfully saved fallback extraction results to extraction/ folder:")
            logger.info(f"  - Meta: extraction/{category}/{document_number}/extraction_{file_id}.json")
            logger.info(f"  - Raw: RAW/{category}/{document_number}/raw_extraction_{file_id}.json")
            
        else:  # classification
            # Save to classification/ folder
            classification_folder = f"{FOLDER_PREFIX}/classification/{category}/{document_number}"
            raw_folder = f"RAW/{category}/{document_number}"
            
            # Build classification structure
            clean_classification = {
                "result": {
                    "DocumentCategory": result_data.get('category', 'UNKNOWN'),
                    "DocumentType": "document",
                    "DocumentNumber": document_number,
                    "OriginalCategory": category,
                    "ProcessingStatus": "success",
                    "RequiresExtraction": result_data.get('requires_extraction', False),
                    "Text": result_data.get('text', '')
                },
                "classification_model_used": raw_response.get('model_id', 'unknown'),
                "method_used": method_used,
                "processing_time_seconds": processing_time,
                "came_from_fallback": True,
                "classification_timestamp": raw_response.get('ResponseMetadata', {}).get('HTTPHeaders', {}).get('date'),
                "file_info": {
                    "source_key": s3_info['s3_key'],
                    "category": category,
                    "document_number": document_number,
                    "file_id": file_id
                }
            }
            
            enhanced_raw = raw_response.copy()
            enhanced_raw['classification_model_used'] = raw_response.get('model_id', 'unknown')
            enhanced_raw['method_used'] = method_used
            enhanced_raw['processing_time_seconds'] = processing_time
            enhanced_raw['came_from_fallback'] = True
            enhanced_raw['file_info'] = {
                'source_key': s3_info['s3_key'],
                'category': category,
                'document_number': document_number,
                'file_id': file_id
            }
            
            classification_destination_key = f"{classification_folder}/classification_{file_id}_{timestamp}.json"
            save_to_s3(clean_classification, DESTINATION_BUCKET, classification_destination_key)
            
            raw_destination_key = f"{raw_folder}/raw_classification_{file_id}_{timestamp}.json"
            save_to_s3(enhanced_raw, DESTINATION_BUCKET, raw_destination_key)
            
            logger.info(f"Successfully saved fallback classification results:")
            logger.info(f"  - Classification: classification/{category}/{document_number}/classification_{file_id}.json")
            logger.info(f"  - Raw: RAW/{category}/{document_number}/raw_classification_{file_id}.json")
        
    except Exception as e:
        logger.error(f"Failed to save fallback results to extraction folder: {e}")

def process_document_with_enhanced_fallback(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enhanced fallback processing: PyPDF→Fallback Model, then Textract→Fallback Model, then manual review.
    Results are saved in extraction/ folder, NOT fallback/ folder.
    
    Args:
        payload: Document payload from failed processing
        
    Returns:
        dict: Processing result with extracted data or error info
    """
    start_time = time.time()
    path = payload.get('path', '')
    document_number = extract_document_number_from_path(path)
    category = extract_original_category_from_path(path)
    
    logger.info(f"Enhanced fallback processing for: {category}/{document_number}")
    
    try:
        # Determine process type and load prompts
        process_type, system_prompt, user_prompt = determine_process_type_and_prompts(payload)
        logger.info(f"Process type determined: {process_type}")
        
        # Get ONLY fallback model
        fallback_model = os.environ.get("FALLBACK_MODEL")
        logger.info(f"Using fallback model: {fallback_model}")
        
        # Extract S3 info and download PDF
        s3_info = extract_s3_info(payload)
        s3_client = create_s3_client()
        response = s3_client.get_object(Bucket=s3_info['s3_bucket'], Key=s3_info['s3_key'])
        pdf_bytes = response['Body'].read()
        
        # PHASE 1: PyPDF text extraction + Fallback Model
        logger.info("PHASE 1: PyPDF text extraction + Fallback Model processing")
        try:
            pypdf_text = extract_pdf_text_with_pypdf(pdf_bytes)
            
            if pypdf_text and not pypdf_text.startswith("[ERROR"):
                logger.info(f"PyPDF extraction successful: {len(pypdf_text)} characters")
                
                # Try fallback model with PyPDF text
                pypdf_result = try_claude_with_extracted_text(
                    fallback_model, user_prompt, system_prompt, pypdf_text, process_type
                )
                
                if pypdf_result.is_success:
                    processing_time = time.time() - start_time
                    method_used = f"pypdf_claude_{fallback_model}"
                    
                    logger.info(f"SUCCESS: {process_type} completed with PyPDF + {fallback_model}")
                    
                    # Save to extraction/ folder (NOT fallback/ folder)
                    save_successful_fallback_to_extraction_folder(
                        pypdf_result.data, s3_info, category, document_number,
                        method_used, processing_time, process_type, 
                        pypdf_result.data.get('raw_response', {}) if process_type == 'extraction' else {}
                    )
                    
                    return {
                        'success': True,
                        'method_used': method_used,
                        'process_type': process_type,
                        'extracted_text': pypdf_text,
                        'processed_data': pypdf_result.data,
                        'text_length': len(pypdf_text),
                        'document_info': build_document_info(path),
                        'processing_metadata': {
                            'fallback_method': 'pypdf_claude',
                            'model_used': pypdf_result.model_used,
                            'timestamp': datetime.now(timezone.utc).isoformat(),
                            'pdf_size_bytes': len(pdf_bytes),
                            'processing_time_seconds': processing_time
                        }
                    }
                
                logger.warning(f"PyPDF text extraction successful but Fallback Model processing failed")
            else:
                logger.warning("PyPDF text extraction failed")
        except Exception as pypdf_error:
            logger.error(f"PyPDF processing failed: {pypdf_error}")
        
        # PHASE 2: Textract text extraction + Fallback Model
        logger.info("PHASE 2: Textract text extraction + Fallback Model processing")
        try:
            textract_text = extract_pdf_text_with_textract(
                pdf_bytes, s3_info['s3_bucket'], s3_info['s3_key'], os.environ.get("REGION")
            )
            
            if textract_text and not textract_text.startswith("[ERROR"):
                logger.info(f"Textract extraction successful: {len(textract_text)} characters")
                
                # Try fallback model with Textract text
                textract_result = try_claude_with_extracted_text(
                    fallback_model, user_prompt, system_prompt, textract_text, process_type
                )
                
                if textract_result.is_success:
                    processing_time = time.time() - start_time
                    method_used = f"textract_claude_{fallback_model}"
                    
                    logger.info(f"SUCCESS: {process_type} completed with Textract + {fallback_model}")
                    
                    # Save to extraction/ folder (NOT fallback/ folder)
                    save_successful_fallback_to_extraction_folder(
                        textract_result.data, s3_info, category, document_number,
                        method_used, processing_time, process_type,
                        textract_result.data.get('raw_response', {}) if process_type == 'extraction' else {}
                    )
                    
                    return {
                        'success': True,
                        'method_used': method_used,
                        'process_type': process_type,
                        'extracted_text': textract_text,
                        'processed_data': textract_result.data,
                        'text_length': len(textract_text),
                        'document_info': build_document_info(path),
                        'processing_metadata': {
                            'fallback_method': 'textract_claude',
                            'model_used': textract_result.model_used,
                            'pypdf_failed': True,
                            'timestamp': datetime.now(timezone.utc).isoformat(),
                            'pdf_size_bytes': len(pdf_bytes),
                            'processing_time_seconds': processing_time
                        }
                    }
                
                logger.error("Textract text extraction successful but Fallback Model processing failed")
            else:
                logger.error("Textract text extraction failed")
        except Exception as textract_error:
            logger.error(f"Textract processing failed: {textract_error}")
        
        # PHASE 3: All methods failed - prepare for manual review
        processing_time = time.time() - start_time
        logger.error("All fallback methods failed - preparing for manual review")
        return {
            'success': False,
            'method_used': 'none',
            'process_type': process_type,
            'error': 'All fallback methods failed (PyPDF+FallbackModel, Textract+FallbackModel)',
            'document_info': build_document_info(path),
            'processing_metadata': {
                'fallback_method': 'failed',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'pypdf_failed': True,
                'textract_failed': True,
                'claude_processing_failed': True,
                'models_attempted': [fallback_model],
                'processing_time_seconds': processing_time
            }
        }
        
    except Exception as e:
        processing_time = time.time() - start_time
        logger.error(f"Error in enhanced fallback processing: {str(e)}")
        return {
            'success': False,
            'method_used': 'none',
            'process_type': 'unknown',
            'error': str(e),
            'document_info': build_document_info(path),
            'processing_metadata': {
                'fallback_method': 'error',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'processing_error': str(e),
                'processing_time_seconds': processing_time
            }
        }

# Keep existing helper functions
def extract_error_information(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Extract error information from the payload."""
    result = payload.get('result', {})
    
    error_patterns = {
        'content_filtered': 'Content filtered by model safety systems',
        'parse_error': 'Failed to parse model response as valid JSON',
        'model_error': 'Model request failed or returned error'
    }
    
    error_type = result.get('status', 'unknown_error')
    error_message = result.get('error_message', 'No error message provided')
    
    if error_type in error_patterns:
        mapped_error = error_patterns[error_type]
    else:
        mapped_error = error_message
    
    return {
        'error_type': error_type,
        'error_message': mapped_error,
        'raw_error_message': error_message,
        'processing_failed': result.get('processing_failed', True)
    }

def extract_models_used(payload: Dict[str, Any]) -> List[str]:
    """Extract the models that were attempted from the payload."""
    result = payload.get('result', {})
    models = []
    
    if 'model_used' in result:
        models.append(result['model_used'])
    
    if result.get('fallback_used', False) and 'fallback_model' in result:
        fallback_model = result['fallback_model']
        if fallback_model not in models:
            models.append(fallback_model)
    
    if not models:
        models = [
            os.environ.get('FALLBACK_MODEL', 'us.anthropic.claude-sonnet-4-20250514-v1:0')
        ]
    
    return models

def extract_s3_info(payload: Dict[str, Any]) -> Dict[str, str]:
    """Extract S3 bucket and key from payload path."""
    path = payload.get('path', '')
    
    if path.startswith('s3://'):
        path_without_protocol = path[5:]
        parts = path_without_protocol.split('/', 1)
        if len(parts) == 2:
            return {
                's3_bucket': parts[0],
                's3_key': parts[1]
            }
    
    bucket = os.environ.get('S3_ORIGIN_BUCKET', 'unknown-bucket')
    key = path.replace('s3://', '').replace(bucket + '/', '') if bucket != 'unknown-bucket' else path
    
    return {
        's3_bucket': bucket,
        's3_key': key
    }

def create_manual_review_record(payload: Dict[str, Any], record_id: str, 
                              fallback_result: Dict[str, Any] = None) -> Dict[str, Any]:
    """Create a DynamoDB record for manual review tracking with enhanced fallback info."""
    now = datetime.now(timezone.utc)
    
    category = extract_original_category_from_path(payload.get('path', ''))
    document_number = extract_document_number_from_path(payload.get('path', ''))
    error_info = extract_error_information(payload)
    models_used = extract_models_used(payload)
    s3_info = extract_s3_info(payload)
    
    timestamp = str(int(now.timestamp() * 1000))
    date_str = now.strftime('%Y#%m#%d')
    
    pk = f"FAILED#{category}"
    sk = f"{date_str}#{document_number or 'UNKNOWN'}#{timestamp}"
    gsi1pk = f"DOC#{document_number or 'UNKNOWN'}"
    gsi1sk = f"{category}#{date_str}"
    
    ttl = int((now + timedelta(days=90)).timestamp())
    
    record = {
        'pk': pk,
        'sk': sk,
        'gsi1pk': gsi1pk,
        'gsi1sk': gsi1sk,
        'record_id': record_id,
        'category': category,
        'document_number': document_number or 'UNKNOWN',
        'failed_at': now.isoformat(),
        'date': now.strftime('%Y-%m-%d'),
        's3_bucket': s3_info['s3_bucket'],
        's3_key': s3_info['s3_key'],
        's3_path': payload.get('path', ''),
        'error_type': error_info['error_type'],
        'error_message': error_info['error_message'],
        'raw_error_message': error_info['raw_error_message'],
        'processing_failed': error_info['processing_failed'],
        'models_used': models_used,
        'primary_model': models_used[0] if models_used else 'unknown',
        'fallback_used': len(models_used) > 1,
        'enhanced_fallback_attempted': fallback_result is not None,
        'enhanced_fallback_success': fallback_result.get('success', False) if fallback_result else False,
        'fallback_method_used': fallback_result.get('method_used', 'none') if fallback_result else 'none',
        'claude_processing_attempted': 'claude' in fallback_result.get('method_used', '') if fallback_result else False,
        'extracted_text_available': fallback_result.get('success', False) if fallback_result else False,
        'extracted_text_length': fallback_result.get('text_length', 0) if fallback_result else 0,
        'process_type': fallback_result.get('process_type', 'unknown') if fallback_result else 'unknown',
        'raw_payload': json.dumps(payload, default=str),
        'created_at': now.isoformat(),
        'ttl': ttl
    }
    
    if fallback_result:
        record['enhanced_fallback_details'] = json.dumps(fallback_result, default=str)
    
    return record

def save_to_dynamodb(record: Dict[str, Any]) -> bool:
    """Save the manual review record to DynamoDB."""
    try:
        table_name = os.environ.get('MANUAL_REVIEW_TABLE')
        if not table_name:
            logger.error("MANUAL_REVIEW_TABLE environment variable not set")
            return False
        
        dynamodb_client = create_dynamodb_client()
        
        item = {}
        for key, value in record.items():
            if isinstance(value, str):
                item[key] = {'S': value}
            elif isinstance(value, bool):
                item[key] = {'BOOL': value}
            elif isinstance(value, (int, float)):
                item[key] = {'N': str(value)}
            elif isinstance(value, list):
                if value:
                    item[key] = {'SS': [str(v) for v in value]}
                else:
                    item[key] = {'S': '[]'}
            elif value is None:
                continue
            else:
                item[key] = {'S': str(value)}
        
        dynamodb_client.put_item(
            TableName=table_name,
            Item=item
        )
        
        logger.info(f"Successfully saved manual review record: {record['record_id']}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to save record to DynamoDB: {str(e)}")
        return False

def process_fallback_message(sqs_record: Dict[str, Any]) -> Dict[str, Any]:
    """Process a single SQS message with enhanced fallback processing."""
    message_id = sqs_record.get('messageId', 'unknown')
    
    try:
        payload = json.loads(sqs_record['body'])
        
        logger.info(f"Processing enhanced fallback message {message_id}")
        logger.info(f"Document: {payload.get('category', 'UNKNOWN')}/{payload.get('document_number', 'UNKNOWN')}")
        
        # Attempt enhanced fallback processing
        fallback_result = process_document_with_enhanced_fallback(payload)
        
        if fallback_result.get('success', False):
            # SUCCESS: Document was processed successfully
            logger.info(f"Successfully processed enhanced fallback message {message_id} - NO manual review needed")
            return {
                'messageId': message_id,
                'status': 'success',
                'category': extract_original_category_from_path(payload.get('path', '')),
                'document_number': extract_document_number_from_path(payload.get('path', '')),
                'enhanced_fallback_success': True,
                'fallback_method': fallback_result.get('method_used', 'none'),
                'claude_processing_used': 'claude' in fallback_result.get('method_used', ''),
                'data_extracted': True,
                'saved_to_extraction_folder': True
            }
        else:
            # FAILURE: Create manual review record ONLY when everything fails
            record = create_manual_review_record(payload, message_id, fallback_result)
            dynamodb_success = save_to_dynamodb(record)
            
            # Also save to error/ folder for comprehensive failure tracking
            from shared.processing_result import save_processing_to_s3, ProcessingResult
            
            error_result = ProcessingResult(
                is_success=False,
                data=None,
                status='model_error',
                error_message=fallback_result.get('error', 'All fallback methods failed'),
                model_used=os.environ.get('FALLBACK_MODEL', 'unknown')
            )
            
            meta_dict = {
                'document_number': extract_document_number_from_path(payload.get('path', '')),
                'category': extract_original_category_from_path(payload.get('path', '')),
                'path': payload.get('path', ''),
                'error': fallback_result.get('error', 'All fallback methods failed'),
                'status': 'model_error',
                'processing_failed': True,
                'model_used': os.environ.get('FALLBACK_MODEL', 'unknown'),
                'process_type': fallback_result.get('process_type', 'unknown'),
                'method_used': 'fallback_failed',
                'processing_time_seconds': fallback_result.get('processing_metadata', {}).get('processing_time_seconds', 0)
            }
            
            # This will create error/ folder ONLY when manual review is needed
            save_processing_to_s3(
                result=error_result,
                folder_path=payload.get('path', ''),
                meta_dict=meta_dict,
                raw_bedrock_responses=[],
                process_type=fallback_result.get('process_type', 'unknown')
            )
            
            if dynamodb_success:
                logger.info(f"Enhanced fallback failed - saved for manual review: {message_id}")
                return {
                    'messageId': message_id,
                    'status': 'success',  # Successfully saved for manual review
                    'category': record['category'],
                    'document_number': record['document_number'],
                    'error_type': record['error_type'],
                    'enhanced_fallback_success': False,
                    'fallback_method': fallback_result.get('method_used', 'none'),
                    'requires_manual_review': True
                }
            else:
                logger.error(f"Failed to save enhanced fallback message {message_id} to DynamoDB")
                return {
                    'messageId': message_id,
                    'status': 'error',
                    'error': 'Failed to save to DynamoDB',
                    'enhanced_fallback_success': False
                }
            
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse SQS message body as JSON: {str(e)}")
        return {
            'messageId': message_id,
            'status': 'error',
            'error': f'Invalid JSON in message body: {str(e)}'
        }
    except Exception as e:
        logger.error(f"Error processing enhanced fallback message {message_id}: {str(e)}")
        return {
            'messageId': message_id,
            'status': 'error',
            'error': str(e)
        }

def process_batch_fallback(records: List[Dict[str, Any]]) -> Tuple[List[Dict], List[str]]:
    """Process enhanced fallback batch."""
    logger.info(f"PHASE 1: Processing {len(records)} enhanced fallback messages")
    
    fallback_results = []
    for sqs_record in records:
        if sqs_record.get('eventSource') != 'aws:sqs':
            logger.warning(f"Skipping non-SQS event: {sqs_record.get('eventSource')}")
            continue
        
        result = process_fallback_message(sqs_record)
        fallback_results.append(result)
    
    logger.info(f"PHASE 2: Completed processing of {len(fallback_results)} enhanced fallback messages")
    
    failed_message_ids = []
    successful_claude_processing = 0
    saved_to_extraction_folder = 0
    
    for result in fallback_results:
        if result['status'] == 'error':
            failed_message_ids.append(result['messageId'])
        elif result.get('enhanced_fallback_success', False):
            successful_claude_processing += 1
            if result.get('saved_to_extraction_folder', False):
                saved_to_extraction_folder += 1
    
    logger.info(f"Enhanced fallback summary: {successful_claude_processing} successful (saved to extraction/), {len(failed_message_ids)} failed")
    
    return fallback_results, failed_message_ids

def handler(event, context):
    """
    Lambda handler for enhanced fallback processing.
    Successful results go to extraction/ folder, failed ones go to manual review.
    """
    try:
        logger.info(f"Received enhanced fallback event with {len(event.get('Records', []))} messages")
        
        if 'Records' not in event:
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'error': 'Not an SQS batch event or missing Records'
                })
            }
        
        # Process batch with enhanced fallback
        results, failed_message_ids = process_batch_fallback(event['Records'])
        
        # Calculate summary statistics
        total_messages = len(event['Records'])
        successful_processing = len([r for r in results if r['status'] == 'success'])
        failed_processing = len(failed_message_ids)
        successful_claude_extractions = len([r for r in results if r.get('enhanced_fallback_success', False)])
        manual_review_required = len([r for r in results if r.get('requires_manual_review', False)])
        
        summary = {
            'totalMessages': total_messages,
            'successfulProcessing': successful_processing,
            'failedProcessing': failed_processing,
            'successfulClaudeExtractions': successful_claude_extractions,
            'savedToExtractionFolder': successful_claude_extractions,
            'manualReviewRequired': manual_review_required,
            'processingMode': 'enhanced_fallback_with_extraction_folder'
        }
        
        # Build response
        response = {
            'statusCode': 200,
            'body': json.dumps({
                'results': results,
                'summary': summary
            })
        }
        
        # Add batch item failures for SQS retry
        if failed_message_ids:
            response['batchItemFailures'] = [
                {'itemIdentifier': msg_id} for msg_id in failed_message_ids
            ]
            logger.warning(f"Enhanced fallback completed with {failed_processing} failed messages")
        
        logger.info(f"Enhanced fallback summary: {successful_processing} successful, {successful_claude_extractions} saved to extraction/, {manual_review_required} manual review")
        
        return response
        
    except Exception as e:
        logger.error(f"Error in enhanced fallback handler: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e)
            })
        }