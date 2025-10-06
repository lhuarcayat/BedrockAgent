#!/usr/bin/env python3
"""
CERL Registry Example

This script demonstrates how to use the CERL registry implementation.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any

from cerl_registry_implementation import (
    register_parser, get_parser, list_registered_parsers,
    validate_against_schema, validate_date_format, correct_future_date,
    process_extraction_result, parse_vllama, parse_claude, parse_bedrock,
    add_parser, load_test_response, test_parser, process_model_response,
    extract_from_file, batch_process_directory
)

def main():
    """Main function to demonstrate the CERL registry implementation."""
    print("CERL Registry Example")
    print("====================")

    # Display available parsers
    print(f"\nAvailable parsers: {list_registered_parsers()}")

    # Example: Test date validation and correction
    test_date_validation()

    # Example: Add a custom parser
    add_custom_parser()

    # Example: Process a test file
    process_test_file()

    # Example: Batch process a directory
    # batch_process_example()

def test_date_validation():
    """Test date validation and correction."""
    print("\nTesting Date Validation and Correction")
    print("------------------------------------")

    test_dates = [
        "2023-01-01",  # Valid date
        "2023-13-01",  # Invalid month
        "2023-01-32",  # Invalid day
        "2062-01-01",  # Future date (likely OCR error)
        "2026-01-01",  # Near future date (might be valid)
    ]

    for date in test_dates:
        print(f"\nDate: {date}")
        print(f"  Valid format: {validate_date_format(date)}")
        corrected, was_corrected = correct_future_date(date)
        if was_corrected:
            print(f"  Corrected to: {corrected}")
        else:
            print("  No correction needed or possible")

def add_custom_parser():
    """Add a custom parser for a new model."""
    print("\nAdding Custom Parser")
    print("-------------------")

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

def process_test_file():
    """Process a test file."""
    print("\nProcessing Test File")
    print("------------------")

    # Create a test directory if it doesn't exist
    test_dir = Path("test_files")
    test_dir.mkdir(exist_ok=True)

    # Create a test file
    test_file = test_dir / "test_vllama_response.json"

    # Sample vLLAMA response
    sample_response = {
        "output": {
            "message": {
                "content": [
                    {
                        "text": """Here's the extracted information in JSON format:

```json
{
  "companyName": "Example Company",
  "taxId": "123456789",
  "documentType": "Certificate of Incorporation",
  "constitutionDate": "2062-05-15",
  "relatedParties": [
    {
      "name": "John Doe",
      "role": "Director",
      "startDate": "2023-01-01",
      "confidence": 0.95
    },
    {
      "name": "Jane Smith",
      "role": "Secretary",
      "startDate": "2023-01-01",
      "confidence": 0.9
    }
  ],
  "confidence": 0.85
}
```

I've extracted all the required information from the document."""
                    }
                ]
            }
        }
    }

    # Save the sample response to the test file
    with open(test_file, "w") as f:
        json.dump(sample_response, f, indent=2)

    print(f"Created test file: {test_file}")

    try:
        # Process the test file
        result = test_parser("vllama", str(test_file))
        print("\nExtraction successful!")
        print(json.dumps(result, indent=2))

        # Validate against schema
        is_valid, error = validate_against_schema(result)
        if is_valid:
            print("\nValidation successful!")
        else:
            print(f"\nValidation error: {error}")

        # Check if any corrections were made
        if result.get("_corrections_applied", False):
            print("\nCorrections were applied to the data.")

            # Check specific corrections
            if "constitutionDate" in result:
                original_date = "2062-05-15"  # From the sample response
                corrected_date = result["constitutionDate"]
                if original_date != corrected_date:
                    print(f"  - Constitution date corrected: {original_date} -> {corrected_date}")

            # Check confidence adjustments
            if "confidence" in result:
                original_confidence = 0.85  # From the sample response
                adjusted_confidence = result["confidence"]
                if original_confidence != adjusted_confidence:
                    print(f"  - Confidence adjusted: {original_confidence} -> {adjusted_confidence}")
        else:
            print("\nNo corrections were needed.")

    except Exception as e:
        print(f"\nError: {str(e)}")

def batch_process_example():
    """Example of batch processing a directory."""
    print("\nBatch Processing Example")
    print("----------------------")

    # Create a test directory if it doesn't exist
    test_dir = Path("test_files")
    test_dir.mkdir(exist_ok=True)

    # Create an output directory
    output_dir = Path("test_output")
    output_dir.mkdir(exist_ok=True)

    # Create multiple test files
    for i in range(3):
        # Sample response with different dates
        sample_response = {
            "output": {
                "message": {
                    "content": [
                        {
                            "text": f"""```json
{{
  "companyName": "Company {i+1}",
  "taxId": "12345678{i}",
  "documentType": "Certificate of Incorporation",
  "constitutionDate": "206{i}-05-15",
  "relatedParties": [
    {{
      "name": "Person {i+1}",
      "role": "Director",
      "startDate": "2023-01-01",
      "confidence": 0.9
    }}
  ],
  "confidence": 0.8
}}
```"""
                        }
                    ]
                }
            }
        }

        # Save the sample response to a test file
        test_file = test_dir / f"test_response_{i+1}.json"
        with open(test_file, "w") as f:
            json.dump(sample_response, f, indent=2)

        print(f"Created test file: {test_file}")

    try:
        # Batch process the directory
        results = batch_process_directory(str(test_dir), "vllama", str(output_dir))
        print(f"\nProcessed {len(results)} files.")
        print(f"Results saved to: {output_dir}")

        # Display the first result
        if results:
            print("\nFirst result:")
            print(json.dumps(results[0], indent=2))
    except Exception as e:
        print(f"\nError: {str(e)}")

if __name__ == "__main__":
    main()
