"""
Configuration Loader for Notebook-Test Framework
Loads and validates YAML configuration with hierarchical enable/disable logic
"""

import yaml
import logging
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
import os
from glob import glob

logger = logging.getLogger(__name__)

class ConfigLoader:
    """Loads and validates test configuration from YAML"""
    
    def __init__(self, config_path: str = "config/documents"):
        self.config_path = Path(config_path)
        self.config = None
        self.load_config()
    
    def load_config(self) -> Dict[str, Any]:
        """Load document-centric configuration"""
        try:
            self.config = self._load_document_centric_config()
            logger.info(f"Document-centric configuration loaded from {self.config_path}")
            self._validate_config()
            return self.config
            
        except FileNotFoundError:
            logger.error(f"Configuration directory not found: {self.config_path}")
            raise
        except yaml.YAMLError as e:
            logger.error(f"YAML parsing error: {e}")
            raise
    
    def _load_document_centric_config(self) -> Dict[str, Any]:
        """Load document-centric configuration from documents directory"""
        config = {
            'settings': {
                'aws_profile': 'par_servicios',
                'aws_region': 'us-east-2',
                'bedrock_model': 'amazon.nova-pro-v1:0',
                'fallback_model': 'us.anthropic.claude-sonnet-4-20250514-v1:0',
                'output_dir': 'outputs',
                'CECRL': True,  # Enable all document types since we have examples
                'CERL': True,
                'RUT': True,
                'RUB': True,
                'ACC': True
            },
            'categories': {
                'field_accuracy': {'enabled': True, 'description': 'Test wrong/swapped field data'},
                'blank_detection': {'enabled': True, 'description': 'Test blank detection'},
                'count_validation': {'enabled': True, 'description': 'Test entity counting'}
            }
        }
        
        documents = {}
        test_cases = {}
        
        # Load all document files in the documents directory
        if self.config_path.exists():
            for doc_file in self.config_path.glob("*.yaml"):
                with open(doc_file, 'r', encoding='utf-8') as f:
                    doc_config = yaml.safe_load(f)
                    if 'documents' in doc_config:
                        loaded_docs = doc_config['documents']
                        documents.update(loaded_docs)
                        
                        # Generate test cases from document configs
                        for doc_key, doc_data in loaded_docs.items():
                            if 'test_config' in doc_data:
                                test_type = doc_data.get('test_type', 'field_accuracy')
                                test_case_key = f"{test_type}_test"
                                
                                if test_case_key not in test_cases:
                                    test_cases[test_case_key] = {
                                        'category': test_type,
                                        'enabled': True,
                                        'documents': {}
                                    }
                                
                                # Convert document-centric config to test case format
                                test_cases[test_case_key]['documents'][doc_key] = {
                                    'enabled': doc_data.get('enabled', True),
                                    'expected_fixes': doc_data['test_config'].get('expected_results', {}),
                                    'issue_result': doc_data['test_config'].get('issue_result', {}),
                                    'prompts_to_test': doc_data['test_config'].get('prompts_to_test', [])
                                }
                        
                        logger.info(f"Loaded {doc_file.stem} documents: {len(loaded_docs)}")
        
        config['documents'] = documents
        config['test_cases'] = test_cases
        
        return config
    
    def _validate_config(self):
        """Validate configuration structure"""
        required_sections = ['settings', 'categories', 'documents', 'test_cases']
        
        for section in required_sections:
            if section not in self.config:
                raise ValueError(f"Missing required configuration section: {section}")
        
        # Validate document types in settings
        doc_types = ['CERL', 'CECRL', 'RUT', 'RUB', 'ACC']
        for doc_type in doc_types:
            if doc_type not in self.config['settings']:
                logger.warning(f"Document type {doc_type} not found in settings, defaulting to false")
                self.config['settings'][doc_type] = False
        
        logger.info("Configuration validation passed")
    
    def should_run_document(self, document_key: str, test_case_key: str) -> Tuple[bool, str]:
        """
        Determine if a document should be tested based on hierarchical enable/disable logic
        
        Hierarchy:
        1. settings.{DOC_TYPE}: false → Skip ALL documents of this type
        2. categories.{CATEGORY}.enabled: false → Skip ALL tests in this category  
        3. test_case.enabled: false → Skip this specific test case
        4. document.enabled: false → Skip this specific document in this test case
        
        Returns:
            Tuple[bool, str]: (should_run, reason)
        """
        try:
            document = self.config['documents'][document_key]
            test_case = self.config['test_cases'][test_case_key]
            
            # 1. Check document type enabled in settings
            doc_type = document['type']
            if not self.config['settings'].get(doc_type, False):
                return False, f"Document type {doc_type} disabled in settings"
            
            # 2. Check category enabled
            category = test_case['category']
            if not self.config['categories'].get(category, {}).get('enabled', False):
                return False, f"Category {category} disabled"
                
            # 3. Check test case enabled
            if not test_case.get('enabled', False):
                return False, f"Test case {test_case_key} disabled"
                
            # 4. Check document enabled in test case
            test_case_documents = test_case.get('documents', {})
            if document_key in test_case_documents:
                if not test_case_documents[document_key].get('enabled', False):
                    return False, f"Document {document_key} disabled in test case {test_case_key}"
            else:
                # Document not explicitly defined in test case
                return False, f"Document {document_key} not configured for test case {test_case_key}"
                
            return True, "Should run"
            
        except KeyError as e:
            return False, f"Configuration error: {e}"
    
    def get_enabled_documents(self) -> Dict[str, List[str]]:
        """
        Get all enabled documents organized by test case
        
        Returns:
            Dict[test_case_key, List[document_keys]]
        """
        enabled_docs = {}
        
        for test_case_key, test_case in self.config['test_cases'].items():
            enabled_docs[test_case_key] = []
            
            if not test_case.get('enabled', False):
                continue
                
            for document_key in self.config['documents'].keys():
                should_run, reason = self.should_run_document(document_key, test_case_key)
                if should_run:
                    enabled_docs[test_case_key].append(document_key)
        
        return enabled_docs
    
    def get_execution_plan(self) -> Dict[str, Any]:
        """
        Generate execution plan showing what will be tested
        
        Returns:
            Dictionary with execution plan details
        """
        plan = {
            'document_types': {},
            'categories': {},
            'test_cases': {},
            'total_executions': 0
        }
        
        # Document types status
        for doc_type in ['CERL', 'CECRL', 'RUT', 'RUB', 'ACC']:
            plan['document_types'][doc_type] = self.config['settings'].get(doc_type, False)
        
        # Categories status
        for category_key, category in self.config['categories'].items():
            plan['categories'][category_key] = {
                'enabled': category.get('enabled', False),
                'description': category.get('description', ''),
                'documents': []
            }
        
        # Test cases and documents
        enabled_docs = self.get_enabled_documents()
        
        for test_case_key, document_list in enabled_docs.items():
            test_case = self.config['test_cases'][test_case_key]
            prompts = test_case.get('prompts_to_test', [])
            
            plan['test_cases'][test_case_key] = {
                'enabled': len(document_list) > 0,
                'category': test_case.get('category', ''),
                'description': test_case.get('description', ''),
                'documents': document_list,
                'prompts': prompts,
                'executions': len(document_list) * len(prompts)
            }
            
            plan['total_executions'] += len(document_list) * len(prompts)
            
            # Add documents to category plan
            category = test_case.get('category', '')
            if category in plan['categories']:
                plan['categories'][category]['documents'].extend(document_list)
        
        return plan
    
    def show_execution_plan(self):
        """Print execution plan to console"""
        plan = self.get_execution_plan()
        
        print("\\n=== EXECUTION PLAN ===")
        
        # Document Types
        print("\\nDocument Types:")
        for doc_type, enabled in plan['document_types'].items():
            status = "✅" if enabled else "❌"
            print(f"  {status} {doc_type}")
        
        # Categories
        print("\\nTest Categories:")
        for category, info in plan['categories'].items():
            status = "✅" if info['enabled'] else "❌"
            doc_count = len(set(info['documents']))  # Remove duplicates
            print(f"  {status} {category}: {doc_count} documents")
            print(f"      {info['description']}")
        
        # Test Cases
        print("\\nTest Cases:")
        for test_case, info in plan['test_cases'].items():
            if info['enabled']:
                print(f"  ✅ {test_case}: {len(info['documents'])} docs × {len(info['prompts'])} prompts = {info['executions']} executions")
            else:
                print(f"  ❌ {test_case}: disabled")
        
        print(f"\\nTotal Test Executions: {plan['total_executions']}")
    
    def get_schema_required_fields(self, document_type: str) -> List[str]:
        """Get schema-required fields for a document type (used for blank detection)"""
        return self.config.get('schema_required_fields', {}).get(document_type, [])
    
    def get_document_info(self, document_key: str) -> Optional[Dict[str, Any]]:
        """Get document configuration"""
        return self.config['documents'].get(document_key)
    
    def get_test_case_info(self, test_case_key: str) -> Optional[Dict[str, Any]]:
        """Get test case configuration"""
        return self.config['test_cases'].get(test_case_key)
    
    def get_settings(self) -> Dict[str, Any]:
        """Get global settings"""
        return self.config.get('settings', {})
    
    def get_validation_rules(self) -> Dict[str, Any]:
        """Get validation rules"""
        return self.config.get('validation_rules', {})

# Usage example and testing
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Test configuration loading
    try:
        config = ConfigLoader("config/test_config.yaml")
        
        # Show execution plan
        config.show_execution_plan()
        
        # Test document enabling logic
        print("\\n=== DOCUMENT ENABLING TESTS ===")
        test_cases = ["field_accuracy_test", "blank_detection_test", "count_validation_test"]
        documents = ["us_passport_venezuela", "empaquetaduras_company", "rut_basic_extraction"]
        
        for test_case in test_cases:
            print(f"\\nTest Case: {test_case}")
            for doc in documents:
                should_run, reason = config.should_run_document(doc, test_case)
                status = "✅ RUN" if should_run else "❌ SKIP"
                print(f"  {status} {doc}: {reason}")
                
    except Exception as e:
        print(f"Configuration error: {e}")
        import traceback
        traceback.print_exc()