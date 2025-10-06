"""
Report generation and persistence utilities for production environment.

This module handles saving detailed processing results to S3, adapted from
the notebook's ReportGeneratorOptimized for production use.

MODIFIED VERSION:
- save_fallback_result function ELIMINADA
- Fallback results se guardan directamente en extraction/ folder usando mismo formato
- Agregado soporte para method_used y processing_time_seconds
"""

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List
from .s3_handler import save_to_s3, extract_s3_path
from .text_utils import clean_text_for_json

logger = logging.getLogger(__name__)

def clean_dict_for_json(obj):
    """
    Recursively clean all string values in a dictionary/list structure
    to ensure JSON compatibility.
    """
    if isinstance(obj, dict):
        return {key: clean_dict_for_json(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [clean_dict_for_json(item) for item in obj]
    elif isinstance(obj, str):
        # Clean text for JSON compatibility
        return clean_text_for_json(obj)
    else:
        return obj

class ReportGenerator:
    """
    Production report generator that saves results to S3.
    Adapted from notebook's ReportGeneratorOptimized.
    
    MODIFIED VERSION:
    - save_fallback_result method ELIMINADA
    - Fallback results ahora se manejan directamente por el fallback lambda
    - Agregado soporte para nuevos campos method_used y processing_time_seconds
    """
    
    def __init__(self):
        self.destination_bucket = os.environ.get("DESTINATION_BUCKET")
        self.folder_prefix = os.environ.get("FOLDER_PREFIX", "par-servicios-poc")
        
        if not self.destination_bucket:
            logger.warning("DESTINATION_BUCKET not configured")
    
    def save_classification_result(self, classification_result: Dict[str, Any], 
                                 document_info: Dict[str, Any], 
                                 model_info: Dict[str, Any]) -> None:
        """
        Save classification result to S3.
        
        Args:
            classification_result: The classification result data
            document_info: Document metadata (path, category, document_number, etc.)
            model_info: Model usage information
        """
        if not self.destination_bucket:
            logger.warning("Cannot save classification result - DESTINATION_BUCKET not configured")
            return
        
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Extract document info
            document_number = document_info.get('document_number', 'UNKNOWN')
            original_category = document_info.get('category', 'UNKNOWN')
            pdf_path = document_info.get('path', 'UNKNOWN')
            
            # Extract filename for unique identifier
            try:
                _, source_key = extract_s3_path(pdf_path)
                filename = Path(source_key).name
                file_id = Path(filename).stem
            except:
                file_id = f"unknown_{document_number}"
            
            # Build comprehensive result
            complete_result = {
                "document_info": document_info,
                "classification_result": classification_result,
                "model_info": model_info,
                "processing_metadata": {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "process_type": "classification",
                    "file_id": file_id,
                    "lambda_request_id": os.environ.get('AWS_REQUEST_ID', 'unknown'),
                    "method_used": classification_result.get('method_used', 'unknown'),
                    "processing_time_seconds": classification_result.get('processing_time_seconds', 0)
                }
            }
            
            # Clean data before saving
            cleaned_result = clean_dict_for_json(complete_result)
            
            # Build S3 key
            classification_folder = f"{self.folder_prefix}/classification/{original_category}/{document_number}"
            safe_filename = re.sub(r'[^\w\-_.]', '_', filename) if 'filename' in locals() else 'document'
            classification_key = f"{classification_folder}/classification_{original_category}_{safe_filename}_{timestamp}.json"
            
            # Save to S3
            save_to_s3(cleaned_result, self.destination_bucket, classification_key)
            
            logger.info(f"Classification result saved: {classification_key}")
            
        except Exception as e:
            logger.error(f"Error saving classification result: {e}")
    
    def save_extraction_result(self, extraction_result: Dict[str, Any], 
                             document_info: Dict[str, Any], 
                             model_info: Dict[str, Any],
                             category: str) -> None:
        """
        Save extraction result to S3.
        
        Args:
            extraction_result: The extraction result data
            document_info: Document metadata
            model_info: Model usage information
            category: Classified category for the document
        """
        if not self.destination_bucket:
            logger.warning("Cannot save extraction result - DESTINATION_BUCKET not configured")
            return
        
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Extract document info
            document_number = document_info.get('document_number', 'UNKNOWN')
            pdf_path = document_info.get('path', 'UNKNOWN')
            
            # Extract filename for unique identifier
            try:
                _, source_key = extract_s3_path(pdf_path)
                filename = Path(source_key).name
                file_id = Path(filename).stem
            except:
                file_id = f"unknown_{document_number}"
            
            # Build comprehensive result
            complete_result = {
                "document_info": document_info,
                "extraction_result": extraction_result,
                "model_info": model_info,
                "processing_metadata": {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "process_type": "extraction",
                    "category": category,
                    "file_id": file_id,
                    "lambda_request_id": os.environ.get('AWS_REQUEST_ID', 'unknown'),
                    "method_used": model_info.get('method_used', 'unknown'),
                    "processing_time_seconds": model_info.get('processing_time', 0)
                }
            }
            
            # Clean data before saving
            cleaned_result = clean_dict_for_json(complete_result)
            
            # Build S3 key
            extraction_folder = f"{self.folder_prefix}/extraction/{category}/{document_number}"
            safe_filename = re.sub(r'[^\w\-_.]', '_', filename) if 'filename' in locals() else 'document'
            extraction_key = f"{extraction_folder}/extraction_{category}_{safe_filename}_{timestamp}.json"
            
            # Save to S3
            save_to_s3(cleaned_result, self.destination_bucket, extraction_key)
            
            logger.info(f"Extraction result saved: {extraction_key}")
            
        except Exception as e:
            logger.error(f"Error saving extraction result: {e}")
    
    def save_batch_summary(self, batch_results: List[Dict[str, Any]], 
                          process_type: str,
                          batch_metadata: Dict[str, Any] = None) -> None:
        """
        Save batch processing summary to S3.
        
        Args:
            batch_results: List of individual results from the batch
            process_type: "classification", "extraction", or "enhanced_fallback"
            batch_metadata: Additional metadata about the batch
        """
        if not self.destination_bucket:
            logger.warning("Cannot save batch summary - DESTINATION_BUCKET not configured")
            return
        
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Calculate batch statistics
            total_documents = len(batch_results)
            successful_documents = sum(1 for r in batch_results if r.get("success", False))
            failed_documents = total_documents - successful_documents
            
            # Group by category
            by_category = {}
            for result in batch_results:
                category = result.get("category", "UNKNOWN")
                if category not in by_category:
                    by_category[category] = {"total": 0, "successful": 0, "failed": 0}
                by_category[category]["total"] += 1
                if result.get("success", False):
                    by_category[category]["successful"] += 1
                else:
                    by_category[category]["failed"] += 1
            
            # Build summary
            summary = {
                "batch_summary": {
                    "process_type": process_type,
                    "total_documents": total_documents,
                    "successful_documents": successful_documents,
                    "failed_documents": failed_documents,
                    "success_rate": successful_documents / total_documents if total_documents > 0 else 0,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "processing_mode": batch_metadata.get('processing_mode', 'simplified_processing') if batch_metadata else 'simplified_processing'
                },
                "by_category": by_category,
                "batch_metadata": batch_metadata or {},
                "detailed_results": batch_results
            }
            
            # Add enhanced fallback specific metrics if applicable
            if process_type == 'enhanced_fallback' and batch_metadata:
                summary["batch_summary"]["saved_to_extraction_folder"] = batch_metadata.get('saved_to_extraction_folder', 0)
                summary["batch_summary"]["manual_review_required"] = batch_metadata.get('manual_review_required', 0)
                summary["batch_summary"]["successful_claude_extractions"] = batch_metadata.get('successful_claude_extractions', 0)
            
            # Clean data before saving
            cleaned_summary = clean_dict_for_json(summary)
            
            # Build S3 key
            summary_key = f"{self.folder_prefix}/batch_summaries/{process_type}/batch_summary_{timestamp}.json"
            
            # Save to S3
            save_to_s3(cleaned_summary, self.destination_bucket, summary_key)
            
            logger.info(f"Batch summary saved: {summary_key}")
            logger.info(f"Batch stats: {successful_documents}/{total_documents} successful ({summary['batch_summary']['success_rate']:.1%})")
            
        except Exception as e:
            logger.error(f"Error saving batch summary: {e}")

# Global instance for Lambda usage
report_generator = ReportGenerator()