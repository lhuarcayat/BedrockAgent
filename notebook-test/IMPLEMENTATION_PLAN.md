# notebook-test Refactoring Implementation Plan

## 🎯 Goal
Create a YAML-only configuration system for testing document extraction with 3 core test cases, supporting multiple prompt versions, with granular enable/disable controls.

## 📋 Current Status
The existing notebook-test framework is tightly coupled to CECRL documents and hardcoded for specific prompt versions (v2.0.0, v2.1.0, etc.). We need to generalize it for all document types while keeping the notebook interface unchanged.

## 🔧 Target Architecture

### Configuration Structure
- **Single file**: `test_config.yaml` - Everything configured here
- **Notebook stays generic**: Just loads YAML and runs tests
- **Schema integration**: Used only for blank detection validation
- **Multiple prompt support**: Test any number of versions

### Control Hierarchy
```
settings.CERL: false → Skip ALL CERL documents
├── categories.field_accuracy: false → Skip ALL field accuracy tests
  ├── test_case.enabled: false → Skip this test case
    └── document.enabled: false → Skip this document
```

## 🧪 3 Core Test Cases

### Test Case 1: Wrong Data in Fields
- **Purpose**: Test specific field values that are wrong/incomplete/swapped
- **Validation**: Compare actual vs expected specific values
- **Example**: nationality should be "Venezuela" not "Estados Unidos"

### Test Case 2: Blank Document Detection
- **Purpose**: Document has data but model returns blank/empty
- **Validation**: Uses schema to check minimum required fields extracted
- **Schema Integration**: Only used here to determine required fields

### Test Case 4: Wrong Data Count
- **Purpose**: Should find N entities but finds different count
- **Validation**: Count items in arrays (like relatedParties)
- **Example**: Should find 5 representatives, found 3

## 📝 Implementation Checklist

### Phase 1: Configuration Foundation ✅ COMPLETED
- [x] **1.1** Create `config/` directory structure
- [x] **1.2** Design `test_config.yaml` schema with all document types
- [x] **1.3** Add schema-based required fields for blank detection
- [x] **1.4** Add specific expected values for field accuracy tests
- [x] **1.5** Implement hierarchical enable/disable logic
- [x] **1.6** Create validation rules for the 3 core test cases

### Phase 2: Core Testing Framework ✅ COMPLETED
- [x] **2.1** Create `src/config_loader.py` - Load and validate YAML
- [x] **2.2** Create `src/test_manager.py` - Main test orchestration
- [x] **2.3** Create `src/document_extractor.py` - Generic extraction logic
- [x] **2.4** Create `src/validation_engine.py` - Test case validation (integrated in test_manager)
- [x] **2.5** Create `src/result_handler.py` - Results processing and reporting (integrated in test_manager)

### Phase 3: Test Case Implementation ✅ COMPLETED
- [x] **3.1** Implement Field Accuracy Test logic
- [x] **3.2** Implement Blank Detection Test logic  
- [x] **3.3** Implement Count Validation Test logic
- [x] **3.4** Add prompt version comparison capabilities
- [x] **3.5** Add schema-based validation for blank detection
- [x] **3.6** Connect to real S3 document download
- [x] **3.7** Connect to real prompt loading system

### Phase 4: Integration & Migration ✅ COMPLETED
- [x] **4.1** Update existing notebook to use new framework
- [x] **4.2** Migrate existing CECRL test data to new configuration
- [x] **4.3** Add expected values to configuration for proper validation
- [x] **4.4** Test backward compatibility with current workflow
- [x] **4.5** Update documentation and usage examples

### Phase 5: Testing & Validation ✅ COMPLETED
- [x] **5.1** Test all 3 core test cases with sample data
- [x] **5.2** Test multiple prompt version scenarios  
- [x] **5.3** Test hierarchical enable/disable controls
- [x] **5.4** Test configuration flexibility scenarios
- [x] **5.5** Performance testing and optimization strategies

## 🎮 Usage Examples

### Test only CECRL nationality fix
```yaml
settings: {CERL: false, CECRL: true, RUT: false, ACC: false}
categories: {field_accuracy: true, blank_detection: false, count_validation: false}
```

### Test new prompt version
```yaml
test_cases:
  field_accuracy_test:
    prompts_to_test: ["v2.2.1", "v2.3.0"]  # Compare old vs new
```

### Quick single document test
```yaml
documents:
  us_passport_venezuela: {enabled: true}
  others: {enabled: false}
```

## 📓 Notebook Interface
```python
# Completely generic - no hardcoded values
runner = TestRunner("test_config.yaml")
results = runner.run_all_enabled()

# Run specific combinations  
results = runner.run_filtered(document_types=["CECRL"], categories=["field_accuracy"])
```

## 🔑 Key Design Principles
1. **YAML-Only Configuration**: Everything defined in YAML, notebook stays generic
2. **Schema for Blank Detection Only**: Schema used to determine minimum required fields
3. **Specific Expected Values**: For field accuracy, specify exact expected values
4. **Multiple Prompt Support**: Test any number of versions
5. **Granular Control**: Enable/disable at all levels
6. **Minimal Configuration**: Focus only on 3 core test cases

## 📊 Success Criteria ✅ ALL ACHIEVED
- [x] Notebook requires zero changes for new document types
- [x] All 3 test cases work with any document type
- [x] Support testing unlimited prompt versions
- [x] Complete enable/disable control at all levels
- [x] Schema integration for blank detection only
- [x] Backward compatibility with existing CECRL tests
- [x] Easy to add new documents via YAML only

---

## 🎉 **IMPLEMENTATION COMPLETE!**

**Status**: All phases completed successfully. Framework is production-ready for document extraction testing with real Bedrock integration and YAML-only configuration.