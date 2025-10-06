# Test Suite for POC Bedrock

This directory contains all test files for the document processing system organized by component. Tests are kept outside the `functions/` directory to prevent them from being included in Lambda deployment packages.

## Test Organization

### Classification Tests (`classification/`)
- `test_lambda.py` - Tests classification Lambda handler with sample PDF files
- `test_s3_event.py` - Tests S3 event processing and classification workflow
- `test_refactored_functions.py` - Tests refactored classification helper functions

### Extraction Tests (`extraction/`)
- `test_lambda_ext.py` - Tests extraction Lambda handler with SQS events
- `test_fallback_logic_ext.py` - Tests fallback logic and S3 persistence in extraction
- `test_model_tracking.py` - Tests model information tracking in extraction results

### Shared/General Tests (`shared/`)
- `test_param_fix.py` - Tests parameter recalculation fix for Mistral model switching
- `test_function_fix.py` - Tests save_results_to_s3 function signature fix

## Running Tests

```bash
# Set Python path for imports
export PYTHONPATH="functions:functions/classification/src:functions/extraction-scoring/src"

# Run individual tests
python test/classification/test_lambda.py
python test/extraction/test_lambda_ext.py
python test/shared/test_param_fix.py

# Run all tests in a category
python -m pytest test/classification/ -v
python -m pytest test/extraction/ -v
python -m pytest test/shared/ -v

# Run all tests
python -m pytest test/ -v
```

## Test Categories

### Classification Tests
Validate the document classification workflow:
- PDF processing and text extraction
- Bedrock model integration and fallback logic
- S3 event handling and SQS message creation
- Exactly-once processing with DynamoDB locks

### Extraction Tests  
Validate the data extraction workflow:
- SQS message processing from classification
- Structured data extraction using Bedrock models
- Fallback-first model selection logic
- S3 persistence and error handling

### Shared Tests
Validate common functionality:
- Parameter format conversion between model types
- Function signature compatibility fixes
- Model tracking across processing stages

## Purpose

These tests validate critical functionality including:
1. Bedrock model parameter compatibility across Nova, Claude, and Mistral
2. SQS batch processing and exactly-once semantics
3. S3 event handling and result persistence
4. Fallback model logic and error handling
5. Refactored function behavior and API contracts

By organizing tests by component and keeping them outside the `functions/` directory, we ensure clean Lambda deployments while maintaining comprehensive test coverage.