#!/usr/bin/env python3
"""
Test various configuration scenarios for the framework
"""

import logging
import sys
import os
import shutil

# Add src to path for imports
sys.path.append('src')
from test_manager import TestManager

logging.basicConfig(level=logging.INFO)

def test_scenario_single_prompt():
    """Test single prompt version scenario"""
    
    print("📝 Scenario 1: Test Only Latest Prompt Version")
    print("=" * 60)
    
    # Create temporary config for single prompt test
    original_config = "config/test_config.yaml"
    temp_config = "config/test_config_single_prompt.yaml"
    
    # Read original config
    with open(original_config, 'r') as f:
        config_content = f.read()
    
    # Modify prompts_to_test to only v2.2.1
    modified_config = config_content.replace(
        'prompts_to_test: ["v2.0.0", "v2.1.0", "v2.2.1"]',
        'prompts_to_test: ["v2.2.1"]'
    )
    
    # Write temporary config
    with open(temp_config, 'w') as f:
        f.write(modified_config)
    
    # Test with single prompt
    print("🧪 Testing with only v2.2.1 prompt:")
    tm = TestManager(temp_config)
    tm.show_execution_plan()
    
    # Cleanup
    os.remove(temp_config)
    
    return True

def test_scenario_single_document():
    """Test single document scenario"""
    
    print("\n\n📄 Scenario 2: Test Single Document")
    print("=" * 60)
    
    # Create temporary config for single document test
    original_config = "config/test_config.yaml"
    temp_config = "config/test_config_single_doc.yaml"
    
    # Read original config
    with open(original_config, 'r') as f:
        config_content = f.read()
    
    # Modify to disable other documents
    modified_config = config_content.replace(
        'colombian_cedula_name_swap:\n        enabled: true',
        'colombian_cedula_name_swap:\n        enabled: false'
    ).replace(
        'colombian_cedula_no_labels:\n        enabled: true', 
        'colombian_cedula_no_labels:\n        enabled: false'
    )
    
    # Write temporary config
    with open(temp_config, 'w') as f:
        f.write(modified_config)
    
    # Test with single document
    print("🧪 Testing with only us_passport_venezuela:")
    tm = TestManager(temp_config)
    tm.show_execution_plan()
    
    # Cleanup
    os.remove(temp_config)
    
    return True

def test_scenario_category_isolation():
    """Test category isolation scenario"""
    
    print("\n\n📂 Scenario 3: Test Category Isolation")
    print("=" * 60)
    
    print("🧪 Current all-categories-enabled config:")
    tm = TestManager()
    
    enabled_docs = tm.get_enabled_tests()
    for test_case, docs in enabled_docs.items():
        test_info = tm.config_loader.get_test_case_info(test_case)
        category = test_info.get('category', 'unknown') if test_info else 'unknown'
        print(f"   {category}: {len(docs)} documents")
    
    print("\n💡 To isolate field_accuracy category:")
    print("   Set blank_detection.enabled: false")
    print("   Set count_validation.enabled: false")
    print("   Keep field_accuracy.enabled: true")

def test_scenario_multiple_document_types():
    """Test multiple document types scenario"""
    
    print("\n\n🏢 Scenario 4: Multiple Document Types")
    print("=" * 60)
    
    print("🧪 Current document type settings:")
    tm = TestManager()
    settings = tm.config_loader.get_settings()
    
    for doc_type in ['CECRL', 'CERL', 'RUT', 'RUB', 'ACC']:
        status = "✅ ENABLED" if settings.get(doc_type, False) else "❌ DISABLED"
        print(f"   {doc_type}: {status}")
    
    print("\n💡 When CERL documents become available:")
    print("   Set CERL: true in settings")
    print("   Add CERL documents to documents section")
    print("   Add CERL schema to schema_required_fields")
    print("   Framework will automatically test both CECRL + CERL!")

def test_scenario_prompt_comparison():
    """Test prompt version comparison scenario"""
    
    print("\n\n🔄 Scenario 5: Prompt Version Comparison")
    print("=" * 60)
    
    print("🧪 Current prompt versions being tested:")
    tm = TestManager()
    
    # Get field accuracy test case info
    test_info = tm.config_loader.get_test_case_info('field_accuracy_test')
    if test_info:
        prompts = test_info.get('prompts_to_test', [])
        print(f"   Versions: {prompts}")
        print(f"   Total combinations: 3 documents × {len(prompts)} prompts = {3 * len(prompts)} tests")
    
    print("\n💡 To compare v2.2.1 vs new v2.3.0:")
    print("   prompts_to_test: ['v2.2.1', 'v2.3.0']")
    print("   Add prompts/CECRL/v2.3.0/ directory with new prompts")
    print("   Framework will automatically compare both versions!")

def test_scenario_performance_optimization():
    """Test performance optimization scenarios"""
    
    print("\n\n⚡ Scenario 6: Performance Optimization")
    print("=" * 60)
    
    print("🧪 Current execution load:")
    tm = TestManager()
    tm.show_execution_plan()
    
    print("\n💡 Performance optimization strategies:")
    print("   📝 Reduce prompts: ['v2.2.1'] for quick testing")
    print("   📄 Reduce documents: Enable only problematic ones") 
    print("   📂 Reduce categories: Enable only relevant test case")
    print("   🏢 Reduce doc types: Test CECRL first, then others")
    
    print("\n⏱️ Estimated times (with real Bedrock):")
    print("   Single test: ~3-5 seconds (S3 download + Bedrock call)")
    print("   Current 9 tests: ~30-45 seconds total")
    print("   Full scale (5 doc types × 10 docs × 3 prompts): ~7-10 minutes")

if __name__ == "__main__":
    print("🧪 Testing Configuration Flexibility Scenarios")
    print("=" * 80)
    
    test_scenario_single_prompt()
    test_scenario_single_document()
    test_scenario_category_isolation()
    test_scenario_multiple_document_types()
    test_scenario_prompt_comparison()
    test_scenario_performance_optimization()
    
    print("\n\n🎯 Configuration Flexibility Summary:")
    print("=" * 60)
    print("✅ Single Prompt Testing: prompts_to_test configuration")
    print("✅ Single Document Testing: document-level enabled flags")
    print("✅ Category Isolation: category-level enabled flags")
    print("✅ Multiple Document Types: settings-level type controls")
    print("✅ Version Comparison: flexible prompt version lists")
    print("✅ Performance Optimization: granular enable/disable controls")
    
    print("\n🎮 All scenarios controlled by YAML-only configuration!")
    print("📝 No notebook code changes needed for any scenario!")