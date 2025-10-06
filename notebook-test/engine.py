# =============================================================================
# MAIN TESTING FUNCTIONS
# =============================================================================
# Core testing logic for comparing prompt versions

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List
from utils import (
    get_pdf_bytes_from_s3_path, 
    load_prompt_files,
    build_extraction_prompts,
    run_extraction_with_prompts
)

logger = logging.getLogger(__name__)

# =============================================================================
# SINGLE DOCUMENT TESTING
# =============================================================================

def test_document_with_both_versions(document_key: str, document_info: Dict[str, Any],
                                   bedrock_client, s3_client, model_id: str) -> Dict[str, Any]:
    """
    Test a single document with both prompt versions.
    
    Args:
        document_key: Document identifier
        document_info: Document configuration
        bedrock_client: Bedrock client
        s3_client: S3 client
        model_id: Model to use
        
    Returns:
        Dict with comparison results
    """
    logger.info(f"Testing document: {document_key}")
    
    try:
        # Get PDF bytes from S3
        pdf_bytes = get_pdf_bytes_from_s3_path(document_info['s3_path'], s3_client)
        
        results = {
            "document_key": document_key,
            "document_info": document_info,
            "timestamp": datetime.now().isoformat(),
            "versions": {}
        }
        
        # Test all versions
        for version in ["v2.0.0", "v2.1.0", "v2.2.0", "v2.2.1"]:
            logger.info(f"Testing with prompts {version}")
            
            try:
                # Load prompts
                system_template, user_template = load_prompt_files(version)
                
                # Build final prompts
                system_prompt, user_prompt = build_extraction_prompts(
                    system_template, user_template, document_info
                )
                
                # Run extraction
                result = run_extraction_with_prompts(
                    pdf_bytes, system_prompt, user_prompt, 
                    document_info['s3_path'], bedrock_client, model_id
                )
                
                results["versions"][version] = result
                logger.info(f"✅ {version} completed")
                
            except Exception as e:
                logger.error(f"❌ {version} failed: {e}")
                results["versions"][version] = {
                    "success": False,
                    "error": str(e)
                }
        
        return results
        
    except Exception as e:
        logger.error(f"Document test failed: {e}")
        return {
            "document_key": document_key,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

# =============================================================================
# BATCH TESTING
# =============================================================================

def test_all_documents(test_documents: Dict[str, Any], bedrock_client, 
                      s3_client, model_id: str) -> Dict[str, Any]:
    """
    Test all configured documents.
    
    Args:
        test_documents: Document configurations
        bedrock_client: Bedrock client
        s3_client: S3 client
        model_id: Model to use
        
    Returns:
        Dict with all test results
    """
    logger.info(f"Starting batch test of {len(test_documents)} documents")
    
    batch_results = {
        "timestamp": datetime.now().isoformat(),
        "model_used": model_id,
        "total_documents": len(test_documents),
        "results": {}
    }
    
    for doc_key, doc_info in test_documents.items():
        try:
            result = test_document_with_both_versions(
                doc_key, doc_info, bedrock_client, s3_client, model_id
            )
            batch_results["results"][doc_key] = result
            
        except Exception as e:
            logger.error(f"Failed to test {doc_key}: {e}")
            batch_results["results"][doc_key] = {"error": str(e)}
    
    logger.info("✅ Batch testing completed")
    return batch_results

# =============================================================================
# RESULTS ANALYSIS
# =============================================================================

def analyze_field_changes(old_result: Dict[str, Any], new_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compare extraction results field by field.
    
    Args:
        old_result: v2.0.0 extraction result
        new_result: v2.1.0 extraction result
        
    Returns:
        Dict with field-by-field comparison
    """
    if not (old_result.get("success") and new_result.get("success")):
        return {"error": "Cannot compare - one or both extractions failed"}
    
    old_data = old_result.get("data", {})
    new_data = new_result.get("data", {})
    
    field_changes = {}
    all_fields = set(old_data.keys()) | set(new_data.keys())
    
    for field in all_fields:
        old_val = old_data.get(field)
        new_val = new_data.get(field)
        
        if old_val != new_val:
            field_changes[field] = {
                "changed": True,
                "old_value": old_val,
                "new_value": new_val
            }
        else:
            field_changes[field] = {
                "changed": False,
                "value": old_val
            }
    
    return field_changes

def generate_comparison_report(batch_results: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate a human-readable comparison report.
    
    Args:
        batch_results: Results from test_all_documents
        
    Returns:
        Dict with formatted comparison report
    """
    report = {
        "summary": {
            "total_documents": batch_results["total_documents"],
            "timestamp": batch_results["timestamp"],
            "model_used": batch_results["model_used"]
        },
        "document_comparisons": {}
    }
    
    for doc_key, doc_result in batch_results["results"].items():
        if "error" in doc_result:
            report["document_comparisons"][doc_key] = {"error": doc_result["error"]}
            continue
        
        versions = doc_result.get("versions", {})
        old_result = versions.get("v2.0.0", {})
        new_result = versions.get("v2.1.0", {})
        
        comparison = {
            "document_name": doc_result["document_info"]["name"],
            "description": doc_result["document_info"]["description"],
            "expected_fixes": doc_result["document_info"]["expected_fixes"],
            "field_changes": analyze_field_changes(old_result, new_result),
            "success_status": {
                "v2.0.0": old_result.get("success", False),
                "v2.1.0": new_result.get("success", False)
            }
        }
        
        report["document_comparisons"][doc_key] = comparison
    
    return report

print("✅ Testing functions loaded")