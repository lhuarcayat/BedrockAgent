"""
Test Manager for Notebook-Test Framework
Main orchestration of test execution using YAML configuration
"""

import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
import sys

# Add paths for shared modules
sys.path.append('../shared')
sys.path.append('shared')

from config_loader import ConfigLoader
from document_extractor import DocumentExtractor

logger = logging.getLogger(__name__)

class TestManager:
    """Main test orchestration class"""
    
    def __init__(self, config_path: str = "config/documents"):
        self.config_loader = ConfigLoader(config_path)
        self.results = {}
        
        # Initialize document extractor
        self.document_extractor = DocumentExtractor(config_loader=self.config_loader)
        
        logger.info("TestManager initialized with document extractor")
    
    def initialize_aws_clients(self):
        """Initialize AWS clients from configuration"""
        try:
            settings = self.config_loader.get_settings()
            # This will use existing AWS setup logic
            # TODO: Import and use setup_aws_clients from current config.py
            logger.info(f"AWS clients initialized with profile: {settings.get('aws_profile')}")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize AWS clients: {e}")
            return False
    
    def show_execution_plan(self):
        """Display what tests will be executed"""
        self.config_loader.show_execution_plan()
    
    def get_enabled_tests(self) -> Dict[str, List[str]]:
        """Get all enabled test combinations"""
        return self.config_loader.get_enabled_documents()
    
    def run_test_case(self, test_case_key: str) -> Dict[str, Any]:
        """
        Run a specific test case
        
        Args:
            test_case_key: Key of test case to run
            
        Returns:
            Dictionary with test results
        """
        logger.info(f"Running test case: {test_case_key}")
        
        test_case_info = self.config_loader.get_test_case_info(test_case_key)
        if not test_case_info:
            logger.error(f"Test case not found: {test_case_key}")
            return {"error": f"Test case not found: {test_case_key}"}
        
        if not test_case_info.get('enabled', False):
            logger.info(f"Test case {test_case_key} is disabled")
            return {"status": "disabled", "test_case": test_case_key}
        
        # Get documents to test
        enabled_docs = self.config_loader.get_enabled_documents()
        documents_to_test = enabled_docs.get(test_case_key, [])
        
        if not documents_to_test:
            logger.info(f"No enabled documents for test case: {test_case_key}")
            return {"status": "no_documents", "test_case": test_case_key}
        
        # Get prompts to test
        prompts_to_test = test_case_info.get('prompts_to_test', [])
        
        results = {
            "test_case": test_case_key,
            "category": test_case_info.get('category'),
            "description": test_case_info.get('description'),
            "timestamp": datetime.now().isoformat(),
            "documents_tested": documents_to_test,
            "prompts_tested": prompts_to_test,
            "results": {},
            "summary": {
                "total_executions": len(documents_to_test) * len(prompts_to_test),
                "successful": 0,
                "failed": 0,
                "errors": []
            }
        }
        
        # Run tests for each document and prompt combination
        for document_key in documents_to_test:
            document_info = self.config_loader.get_document_info(document_key)
            results["results"][document_key] = {}
            
            for prompt_version in prompts_to_test:
                logger.info(f"Testing {document_key} with {prompt_version}")
                
                try:
                    # Run single test
                    test_result = self._run_single_test(
                        document_key, 
                        document_info, 
                        prompt_version, 
                        test_case_info
                    )
                    
                    results["results"][document_key][prompt_version] = test_result
                    
                    if test_result.get("status") == "success":
                        results["summary"]["successful"] += 1
                    else:
                        results["summary"]["failed"] += 1
                        
                except Exception as e:
                    error_msg = f"Error testing {document_key} with {prompt_version}: {str(e)}"
                    logger.error(error_msg)
                    results["summary"]["errors"].append(error_msg)
                    results["summary"]["failed"] += 1
                    
                    results["results"][document_key][prompt_version] = {
                        "status": "error",
                        "error": str(e),
                        "timestamp": datetime.now().isoformat()
                    }
        
        # Store results
        self.results[test_case_key] = results
        
        logger.info(f"Test case {test_case_key} completed: {results['summary']['successful']}/{results['summary']['total_executions']} successful")
        
        return results
    
    def _run_single_test(self, document_key: str, document_info: Dict, 
                        prompt_version: str, test_case_info: Dict) -> Dict[str, Any]:
        """
        Run a single test (one document, one prompt version)
        
        Args:
            document_key: Document identifier
            document_info: Document configuration
            prompt_version: Prompt version to use
            test_case_info: Test case configuration
            
        Returns:
            Dictionary with test result
        """
        result = {
            "document": document_key,
            "prompt_version": prompt_version,
            "timestamp": datetime.now().isoformat(),
            "status": "pending"
        }
        
        try:
            # Use real document extractor
            settings = self.config_loader.get_settings()
            
            extraction_result = self.document_extractor.extract_from_document(
                s3_path=document_info['s3_path'],
                prompt_version=prompt_version,
                document_type=document_info['type'],
                model_id=settings.get('bedrock_model', 'us.amazon.nova-pro-v1:0')
            )
            
            if extraction_result.get('status') == 'success':
                result["extracted_data"] = extraction_result.get('extracted_data', {})
                result["extraction_info"] = {
                    "pdf_size_bytes": extraction_result.get('pdf_size_bytes'),
                    "note": extraction_result.get('note')
                }
            else:
                result["status"] = "extraction_failed"
                result["error"] = extraction_result.get('error', 'Unknown extraction error')
                return result
            
            # Run validation based on test case type
            validation_result = self._validate_test_result(
                result["extracted_data"], 
                document_key,
                prompt_version,
                test_case_info
            )
            
            result["validation"] = validation_result
            result["status"] = "success" if validation_result.get("passed", False) else "failed"
            
            return result
            
        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)
            return result
    
    def _validate_test_result(self, extracted_data: Dict, document_key: str, 
                            prompt_version: str, test_case_info: Dict) -> Dict[str, Any]:
        """
        Validate test result based on test case type
        
        Args:
            extracted_data: Data extracted from document
            document_key: Document identifier  
            prompt_version: Prompt version used
            test_case_info: Test case configuration
            
        Returns:
            Dictionary with validation results
        """
        validation_result = {
            "passed": False,
            "checks": [],
            "errors": []
        }
        
        category = test_case_info.get('category')
        
        if category == 'field_accuracy':
            return self._validate_field_accuracy(
                extracted_data, document_key, prompt_version, test_case_info
            )
        elif category == 'blank_detection':
            return self._validate_blank_detection(
                extracted_data, document_key, test_case_info
            )
        elif category == 'count_validation':
            return self._validate_count_validation(
                extracted_data, document_key, test_case_info
            )
        else:
            validation_result["errors"].append(f"Unknown test category: {category}")
            
        return validation_result
    
    def _validate_field_accuracy(self, extracted_data: Dict, document_key: str, 
                                prompt_version: str, test_case_info: Dict) -> Dict[str, Any]:
        """Validate field accuracy test case"""
        validation_result = {
            "type": "field_accuracy",
            "passed": True,
            "checks": [],
            "field_results": {}
        }
        
        # Get expected values for this document and prompt version
        documents_config = test_case_info.get('documents', {})
        document_config = documents_config.get(document_key, {})
        
        expected_fixes = document_config.get('expected_fixes', {})
        expected_results = document_config.get('expected_results', {})
        
        # Check expected fixes for this prompt version
        expected_for_version = expected_fixes.get(prompt_version, {})
        if not expected_for_version and expected_results:
            expected_for_version = expected_results
        
        if not expected_for_version:
            validation_result["checks"].append(f"No expected values configured for {document_key} with {prompt_version}")
            return validation_result
        
        # Validate each expected field
        for field_name, expected_value in expected_for_version.items():
            actual_value = extracted_data.get(field_name)
            
            field_check = {
                "field": field_name,
                "expected": expected_value,
                "actual": actual_value,
                "passed": actual_value == expected_value
            }
            
            validation_result["field_results"][field_name] = field_check
            validation_result["checks"].append(
                f"{field_name}: {'✅ PASS' if field_check['passed'] else '❌ FAIL'} "
                f"(expected: {expected_value}, got: {actual_value})"
            )
            
            if not field_check["passed"]:
                validation_result["passed"] = False
        
        return validation_result
    
    def _validate_blank_detection(self, extracted_data: Dict, document_key: str, 
                                test_case_info: Dict) -> Dict[str, Any]:
        """Validate blank detection test case"""
        validation_result = {
            "type": "blank_detection",
            "passed": False,
            "checks": [],
            "required_fields_found": 0,
            "total_required_fields": 0
        }
        
        # Get document info to determine type
        document_info = self.config_loader.get_document_info(document_key)
        document_type = document_info.get('type')
        
        # Get schema required fields
        required_fields = self.config_loader.get_schema_required_fields(document_type)
        validation_result["total_required_fields"] = len(required_fields)
        
        # Check how many required fields are present and not empty
        for field in required_fields:
            field_value = extracted_data.get(field)
            has_value = field_value is not None and field_value != "" and field_value != {}
            
            if has_value:
                validation_result["required_fields_found"] += 1
                validation_result["checks"].append(f"✅ {field}: has value")
            else:
                validation_result["checks"].append(f"❌ {field}: missing or empty")
        
        # Document passes if it extracts at least some required fields (not completely blank)
        validation_result["passed"] = validation_result["required_fields_found"] > 0
        
        return validation_result
    
    def _validate_count_validation(self, extracted_data: Dict, document_key: str, 
                                 test_case_info: Dict) -> Dict[str, Any]:
        """Validate count validation test case"""
        validation_result = {
            "type": "count_validation",
            "passed": False,
            "checks": []
        }
        
        # Get expected count configuration
        documents_config = test_case_info.get('documents', {})
        document_config = documents_config.get(document_key, {})
        
        expected_count = document_config.get('expected_count', 0)
        count_field = document_config.get('count_field', 'relatedParties')
        tolerance = document_config.get('tolerance', 0)
        
        # Get actual count
        array_data = extracted_data.get(count_field, [])
        actual_count = len(array_data) if isinstance(array_data, list) else 0
        
        # Check if count is within tolerance
        min_acceptable = expected_count - tolerance
        max_acceptable = expected_count + tolerance
        count_ok = min_acceptable <= actual_count <= max_acceptable
        
        validation_result["passed"] = count_ok
        validation_result["expected_count"] = expected_count
        validation_result["actual_count"] = actual_count
        validation_result["tolerance"] = tolerance
        validation_result["acceptable_range"] = f"{min_acceptable}-{max_acceptable}"
        
        validation_result["checks"].append(
            f"Count check: {'✅ PASS' if count_ok else '❌ FAIL'} "
            f"(expected: {expected_count} ±{tolerance}, got: {actual_count})"
        )
        
        return validation_result
    
    def run_all_enabled(self) -> Dict[str, Any]:
        """Run all enabled test cases"""
        logger.info("Running all enabled test cases")
        
        enabled_tests = self.get_enabled_tests()
        all_results = {}
        
        for test_case_key in enabled_tests.keys():
            if enabled_tests[test_case_key]:  # Has enabled documents
                test_result = self.run_test_case(test_case_key)
                all_results[test_case_key] = test_result
        
        return all_results
    
    def show_results_summary(self, results: Dict[str, Any]):
        """Display results summary"""
        if isinstance(results, dict) and "test_case" in results:
            # Single test case result
            self._show_single_test_summary(results)
        else:
            # Multiple test case results
            print("\\n=== TEST RESULTS SUMMARY ===")
            total_successful = 0
            total_executed = 0
            
            for test_case_key, result in results.items():
                if isinstance(result, dict) and "summary" in result:
                    summary = result["summary"]
                    successful = summary.get("successful", 0)
                    total = summary.get("total_executions", 0)
                    
                    print(f"\\n{test_case_key}:")
                    print(f"  ✅ {successful}/{total} tests passed")
                    
                    total_successful += successful
                    total_executed += total
                    
                    if summary.get("errors"):
                        print(f"  ❌ Errors: {len(summary['errors'])}")
            
            print(f"\\n📊 OVERALL: {total_successful}/{total_executed} tests successful")
    
    def _show_single_test_summary(self, result: Dict[str, Any]):
        """Show summary for single test case"""
        print(f"\\n=== {result.get('test_case', 'TEST')} RESULTS ===")
        print(f"Description: {result.get('description', '')}")
        
        summary = result.get("summary", {})
        print(f"Status: ✅ {summary.get('successful', 0)}/{summary.get('total_executions', 0)} tests passed")
        
        if summary.get("errors"):
            print("\\nErrors:")
            for error in summary["errors"]:
                print(f"  ❌ {error}")
        
        # Show detailed results
        results_data = result.get("results", {})
        for document_key, doc_results in results_data.items():
            print(f"\\n📄 {document_key}:")
            for prompt_version, test_result in doc_results.items():
                status = test_result.get("status", "unknown")
                status_icon = "✅" if status == "success" else "❌"
                print(f"  {status_icon} {prompt_version}: {status}")
                
                # Show validation details for successful tests
                if status == "success" and "validation" in test_result:
                    validation = test_result["validation"]
                    for check in validation.get("checks", []):
                        print(f"    {check}")


# Simple test function
def test_cecrl_only():
    """Test function to run only CECRL tests"""
    logging.basicConfig(level=logging.INFO)
    
    print("🧪 Testing CECRL-only configuration...")
    
    try:
        # Initialize test manager
        tm = TestManager()
        
        # Show what will be executed
        print("\\n=== EXECUTION PLAN ===")
        tm.show_execution_plan()
        
        # Run field accuracy test (the only enabled test case)
        print("\\n=== RUNNING FIELD ACCURACY TEST ===")
        results = tm.run_test_case("field_accuracy_test")
        
        # Show results
        tm.show_results_summary(results)
        
        return results
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    test_cecrl_only()