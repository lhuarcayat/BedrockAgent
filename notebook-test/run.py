# =============================================================================
# MAIN EXECUTION SCRIPT
# =============================================================================
# Run this script to execute the CECRL prompt comparison tests

import json
import sys
from pathlib import Path

# Import our modules
from config import (
    TEST_DOCUMENTS, BEDROCK_MODEL, OUTPUT_DIR, 
    COMPARISON_DIR, BEFORE_DIR, AFTER_DIR,
    setup_aws_clients, logger
)
from engine import test_all_documents, generate_comparison_report

# =============================================================================
# MAIN EXECUTION FUNCTIONS
# =============================================================================

def save_results(results: dict, filename: str, directory: Path = OUTPUT_DIR):
    """Save results to JSON file with pretty formatting."""
    filepath = directory / filename
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    logger.info(f"Results saved to: {filepath}")

def print_summary(report: dict):
    """Print a quick summary of test results."""
    print("\n" + "="*60)
    print("🧪 CECRL PROMPT TESTING SUMMARY")
    print("="*60)
    
    summary = report["summary"]
    print(f"📅 Timestamp: {summary['timestamp']}")
    print(f"🤖 Model: {summary['model_used']}")
    print(f"📄 Documents tested: {summary['total_documents']}")
    
    print("\n📋 RESULTS BY DOCUMENT:")
    print("-" * 40)
    
    for doc_key, comparison in report["document_comparisons"].items():
        if "error" in comparison:
            print(f"❌ {doc_key}: ERROR - {comparison['error']}")
            continue
            
        print(f"\n📄 {comparison['document_name']}")
        print(f"   Description: {comparison['description']}")
        
        # Check success status
        success = comparison["success_status"]
        v20_ok = "✅" if success["v2.0.0"] else "❌"
        v21_ok = "✅" if success["v2.1.0"] else "❌"
        print(f"   v2.0.0: {v20_ok}  |  v2.1.0: {v21_ok}")
        
        # Show field changes
        field_changes = comparison["field_changes"]
        changed_fields = [f for f, data in field_changes.items() if data.get("changed", False)]
        
        if changed_fields:
            print(f"   🔄 Changed fields: {', '.join(changed_fields)}")
            for field in changed_fields:
                change = field_changes[field]
                print(f"      {field}: '{change['old_value']}' → '{change['new_value']}'")
        else:
            print("   📋 No field changes detected")
    
    print("\n" + "="*60)


def run_single_document_test(document_key: str):
    """Run test for a single document (useful for debugging)."""
    if document_key not in TEST_DOCUMENTS:
        print(f"❌ Document '{document_key}' not found in TEST_DOCUMENTS")
        print(f"Available documents: {list(TEST_DOCUMENTS.keys())}")
        return
    
    logger.info(f"Running single document test: {document_key}")
    
    # Setup clients
    bedrock_client, s3_client = setup_aws_clients()
    
    # Import test function
    from engine import test_document_with_both_versions
    
    # Run test
    result = test_document_with_both_versions(
        document_key, 
        TEST_DOCUMENTS[document_key],
        bedrock_client, 
        s3_client, 
        BEDROCK_MODEL
    )
    
    # Save results
    save_results(result, f"single_test_{document_key}.json")
    
    # Generate mini-report
    batch_results = {
        "timestamp": result["timestamp"],
        "model_used": BEDROCK_MODEL,
        "total_documents": 1,
        "results": {document_key: result}
    }
    
    report = generate_comparison_report(batch_results)
    save_results(report, f"single_report_{document_key}.json", COMPARISON_DIR)
    
    print_summary(report)


def run_all_tests():
    """Run the complete test suite."""
    logger.info("Starting complete CECRL prompt comparison test")
    
    # Setup AWS clients
    bedrock_client, s3_client = setup_aws_clients()
    
    # Run all tests
    batch_results = test_all_documents(
        TEST_DOCUMENTS, bedrock_client, s3_client, BEDROCK_MODEL
    )
    
    # Save raw results
    save_results(batch_results, "batch_results.json")
    
    # Generate comparison report
    report = generate_comparison_report(batch_results)
    save_results(report, "comparison_report.json", COMPARISON_DIR)
    
    # Save individual version results for easy access
    for doc_key, doc_result in batch_results["results"].items():
        if "versions" in doc_result:
            versions = doc_result["versions"]
            
            # Save v2.0.0 results
            if "v2.0.0" in versions:
                save_results(versions["v2.0.0"], f"{doc_key}_v2.0.0.json", BEFORE_DIR)
            
            # Save v2.1.0 results  
            if "v2.1.0" in versions:
                save_results(versions["v2.1.0"], f"{doc_key}_v2.1.0.json", AFTER_DIR)
    
    # Print summary
    print_summary(report)
    
    logger.info("✅ Complete test suite finished")


# =============================================================================
# COMMAND LINE INTERFACE
# =============================================================================

if __name__ == "__main__":
    if len(sys.argv) == 1:
        # No arguments - run all tests
        print("🚀 Running all CECRL prompt tests...")
        run_all_tests()
        
    elif len(sys.argv) == 2:
        # Single document test
        document_key = sys.argv[1]
        print(f"🎯 Running single document test: {document_key}")
        run_single_document_test(document_key)
        
    else:
        print("Usage:")
        print("  python run_tests.py                    # Run all tests")
        print("  python run_tests.py <document_key>     # Test single document")
        print(f"\nAvailable documents: {list(TEST_DOCUMENTS.keys())}")


# =============================================================================
# JUPYTER/INTERACTIVE USAGE FUNCTIONS
# =============================================================================

def quick_test():
    """Quick function for interactive testing."""
    print("🧪 Running quick test on first document...")
    first_key = list(TEST_DOCUMENTS.keys())[0]
    run_single_document_test(first_key)

def list_documents():
    """Show configured test documents."""
    print("📋 Configured Test Documents:")
    print("-" * 40)
    for key, info in TEST_DOCUMENTS.items():
        print(f"🔑 {key}")
        print(f"   Name: {info['name']}")
        print(f"   Path: {info['s3_path']}")
        print(f"   Expected fixes: {info['expected_fixes']}")
        print()

print("✅ Execution script loaded")
print("\nQuick usage:")
print("  quick_test()        # Test first document")  
print("  list_documents()    # Show all test documents")
print("  run_all_tests()     # Run complete suite")