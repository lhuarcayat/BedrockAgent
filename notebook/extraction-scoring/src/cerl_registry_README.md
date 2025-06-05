# CERL Registry Implementation

## Overview

This repository contains an implementation of the registry pattern for CERL document extraction. The implementation includes:

1. A registry pattern for model-specific parsers
2. Date validation and correction functions
3. Schema validation functions
4. Batch processing capabilities

## Files

- `cerl_registry_implementation.py`: The main implementation of the registry pattern and related functions
- `cerl_v1_integration_guide.md`: A guide for integrating the registry pattern into the `extraction_CERL_v1.ipynb` notebook

## Key Features

### Registry Pattern

The registry pattern allows for easy registration and retrieval of model-specific parsers. This makes it easy to add support for new models without modifying the core extraction logic.

```python
@register_parser('model_name')
def parse_model(response):
    # Parse the response
    return result
```

### Model-Specific Parsers

The implementation includes parsers for several models:

- vLLAMA
- Claude
- Bedrock

Each parser is designed to handle the specific response format of its model.

### Date Validation and Correction

The implementation includes functions for validating and correcting dates:

- `validate_date_format`: Validates that a date string is in the format YYYY-MM-DD
- `correct_future_date`: Corrects future dates by checking for common OCR errors like year transposition

### Schema Validation

The implementation includes functions for validating data against the CERL schema:

- `load_cerl_schema`: Loads the CERL schema from the schema.json file
- `validate_against_schema`: Validates data against the CERL schema

### Batch Processing

The implementation includes functions for batch processing:

- `batch_process_directory`: Processes all JSON files in a directory
- `extract_from_file`: Extracts data from a response file

## Integration with v1 Notebook

To integrate the registry pattern into the `extraction_CERL_v1.ipynb` notebook, follow the instructions in the `cerl_v1_integration_guide.md` file.

## Key Improvements

1. **Registry Pattern**: Makes it easy to add support for new models without modifying the core extraction logic
2. **Date Validation and Correction**: Automatically detects and corrects common OCR errors in dates
3. **Schema Validation**: Validates extracted data against the CERL schema
4. **Confidence Scoring**: Adjusts confidence scores for fields that were corrected
5. **Manual Page Counting**: Counts pages based on document structure analysis rather than metadata
6. **Error Handling**: Improved error handling for JSON parsing and other operations

## Usage Examples

### Basic Usage

```python
# Import the registry implementation
from cerl_registry_implementation import (
    register_parser, get_parser, list_registered_parsers,
    validate_against_schema, validate_date_format, correct_future_date,
    process_extraction_result, parse_vllama, parse_claude, parse_bedrock,
    add_parser, load_test_response, test_parser, process_model_response,
    extract_from_file, batch_process_directory
)

# Display available parsers
print(f"Available parsers: {list_registered_parsers()}")

# Extract data from a file
result = extract_from_file("path/to/response.json", "vllama")

# Process the result
processed_result = process_extraction_result(result)

# Validate against schema
is_valid, error = validate_against_schema(processed_result)
if not is_valid:
    print(f"Warning: Validation error: {error}")
```

### Adding a Custom Parser

```python
# Add a custom parser for a new model
add_parser(
    model_name="custom_model",
    content_path=["response", "generated_text"],
    json_patterns=[
        r'```json\s*(.*?)\s*```',
        r'{[\s\S]*}'
    ]
)

# Test the custom parser
result = test_parser("custom_model", "path/to/custom_response.json")
```

### Batch Processing

```python
# Process all JSON files in a directory
results = batch_process_directory("path/to/responses", "vllama", "path/to/output")
```

## Conclusion

The registry pattern implementation provides a flexible and extensible framework for CERL document extraction. It makes it easy to add support for new models and provides robust error handling and validation capabilities.
