#!/usr/bin/env python3
"""
Test script to show detailed extraction results
"""

import logging
import json
from src.test_manager import TestManager

logging.basicConfig(level=logging.INFO)

def test_detailed_extraction():
    """Test and show detailed extraction results"""
    
    print("🧪 Testing detailed extraction results...")
    
    try:
        # Initialize test manager
        tm = TestManager()
        
        # Run field accuracy test to get real extraction data
        print("\n=== RUNNING EXTRACTION TEST ===")
        results = tm.run_test_case("field_accuracy_test")
        
        # Show detailed extracted data
        print("\n=== DETAILED EXTRACTION RESULTS ===")
        
        for document_key, doc_results in results.get("results", {}).items():
            print(f"\n📄 {document_key}:")
            
            for prompt_version, test_result in doc_results.items():
                print(f"\n  📝 Prompt Version: {prompt_version}")
                print(f"  📊 Status: {test_result.get('status')}")
                
                if test_result.get('status') == 'success':
                    extracted_data = test_result.get('extracted_data', {})
                    print("  🔍 Extracted Fields:")
                    for field, value in extracted_data.items():
                        print(f"    {field}: {value}")
                    
                    # Show validation details if available
                    validation = test_result.get('validation', {})
                    if validation.get('checks'):
                        print("  ✅ Validation Checks:")
                        for check in validation['checks']:
                            print(f"    {check}")
                
                elif 'error' in test_result:
                    print(f"  ❌ Error: {test_result['error']}")
                
                print("  " + "-" * 50)
        
        return results
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    test_detailed_extraction()