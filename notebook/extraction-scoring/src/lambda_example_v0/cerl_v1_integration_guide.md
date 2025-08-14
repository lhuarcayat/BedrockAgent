# CERL v1 Integration Guide

This guide provides instructions for integrating the registry pattern implementation into the `extraction_CERL_v1.ipynb` notebook.

## Step 1: Import the Registry Implementation

Add a new cell at the beginning of the notebook (after the imports) with the following code:

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
```

## Step 2: Replace the Existing Parse Function

Replace the existing `parse_bedrock_response` function with the registry-based approach:

```python
def parse_response(response: Dict[str, Any], model_name: str) -> Dict[str, Any]:
    """
    Parse a model response using the appropriate parser.

    Args:
        response: The model response to parse
        model_name: The name of the model

    Returns:
        The parsed response as a dictionary
    """
    return process_model_response(response, model_name)
```

## Step 3: Update the Extraction Function

Update the extraction function to use the registry pattern:

```python
def extract_from_response(response_file: str, model_name: str) -> Dict[str, Any]:
    """
    Extract data from a response file.

    Args:
        response_file: The path to the response file
        model_name: The name of the model

    Returns:
        The extracted data as a dictionary
    """
    return extract_from_file(response_file, model_name)
```

## Step 4: Add a Batch Processing Cell

Add a new cell for batch processing:

```python
def process_directory(directory: str, model_name: str, output_dir: str = None) -> List[Dict[str, Any]]:
    """
    Process all JSON files in a directory.

    Args:
        directory: The directory to process
        model_name: The name of the model
        output_dir: The directory to save results to

    Returns:
        A list of processed responses
    """
    return batch_process_directory(directory, model_name, output_dir)

# Example usage
# results = process_directory("path/to/responses", "vllama", "path/to/output")
```

## Step 5: Add a Testing Cell

Add a new cell for testing the parsers:

```python
# Test the vLLAMA parser
test_file = "path/to/vllama_response.json"
try:
    result = test_parser("vllama", test_file)
    print("Extraction successful!")
    print(json.dumps(result, indent=2))

    # Validate against schema
    is_valid, error = validate_against_schema(result)
    if is_valid:
        print("Validation successful!")
    else:
        print(f"Validation error: {error}")
except Exception as e:
    print(f"Error: {str(e)}")
```

## Step 6: Add Date Validation and Correction

Add a new cell for demonstrating date validation and correction:

```python
# Test date validation and correction
test_dates = [
    "2023-01-01",  # Valid date
    "2023-13-01",  # Invalid month
    "2023-01-32",  # Invalid day
    "2062-01-01",  # Future date (likely OCR error)
    "2026-01-01",  # Near future date (might be valid)
]

for date in test_dates:
    print(f"Date: {date}")
    print(f"  Valid format: {validate_date_format(date)}")
    corrected, was_corrected = correct_future_date(date)
    if was_corrected:
        print(f"  Corrected to: {corrected}")
    else:
        print("  No correction needed or possible")
    print()
```

## Step 7: Update the Main Extraction Workflow

Update the main extraction workflow to use the registry pattern:

```python
# Example workflow
def extract_and_validate(file_path: str, model_name: str) -> Dict[str, Any]:
    """
    Extract data from a file and validate it.

    Args:
        file_path: The path to the file
        model_name: The name of the model

    Returns:
        The extracted and validated data
    """
    # Extract data
    result = extract_from_file(file_path, model_name)

    # Process the result (date correction, etc.)
    processed_result = process_extraction_result(result)

    # Validate against schema
    is_valid, error = validate_against_schema(processed_result)
    if not is_valid:
        print(f"Warning: Validation error: {error}")

    return processed_result

# Example usage
# data = extract_and_validate("path/to/response.json", "vllama")
# print(json.dumps(data, indent=2))
```

## Step 8: Add a Custom Parser (Optional)

Add a new cell for demonstrating how to add a custom parser:

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

print(f"Updated parsers: {list_registered_parsers()}")

# Example usage
# result = test_parser("custom_model", "path/to/custom_response.json")
```

## Step 9: Update the Confidence Scoring

Add a new cell for demonstrating confidence score adjustment:

```python
def adjust_confidence_for_corrections(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Adjust confidence scores for fields that were corrected.

    Args:
        data: The data to adjust

    Returns:
        The adjusted data
    """
    # This functionality is already included in process_extraction_result
    return process_extraction_result(data)

# Example usage
# adjusted_data = adjust_confidence_for_corrections(data)
```

## Step 10: Manual Page Counting Implementation

Add a new cell for implementing manual page counting:

```python
def count_pages_from_structure(content: str) -> int:
    """
    Count pages based on document structure analysis rather than metadata.

    Args:
        content: The document content

    Returns:
        The estimated number of pages
    """
    # Look for page indicators in the text
    page_indicators = re.findall(r'Page\s+(\d+)\s+of\s+(\d+)', content, re.IGNORECASE)
    if page_indicators:
        # Use the highest "of X" value
        return max(int(total) for _, total in page_indicators)

    # Look for page breaks or section markers
    page_breaks = re.findall(r'----+\s*Page\s+\d+\s*----+', content, re.IGNORECASE)
    if page_breaks:
        return len(page_breaks)

    # Fall back to estimating based on content length
    # Assuming average page has about 3000 characters
    return max(1, len(content) // 3000)

# Example usage
# page_count = count_pages_from_structure(document_content)
# print(f"Estimated page count: {page_count}")
```

## Complete Integration

After implementing these changes, the notebook will use the registry pattern for parsing model responses, with improved error handling, date validation, and schema validation. The registry pattern makes it easy to add new parsers for different models without modifying the core extraction logic.
