"""
CERL Registry Implementation

This module provides a registry pattern implementation for CERL document extraction.
It includes model-specific parsers, schema validation, and date handling functions.
"""

import json
import re
import os
from pathlib import Path
from datetime import datetime, timedelta
from functools import lru_cache, wraps
from typing import Dict, Any, Callable, Optional, Union, List, Tuple

import jsonschema
from jsonschema import validate, ValidationError

# Dictionary to store registered parsers
_parsers = {}

def register_parser(model_name: str):
    """
    Decorator to register a parser function for a specific model.

    Args:
        model_name: The name of the model this parser is for
    """
    def decorator(func):
        _parsers[model_name.lower()] = func
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        return wrapper
    return decorator

@lru_cache(maxsize=8)
def get_parser(model_name: str) -> Optional[Callable]:
    """
    Get a parser function for a specific model.

    Args:
        model_name: The name of the model to get a parser for

    Returns:
        The parser function or None if not found
    """
    return _parsers.get(model_name.lower())

def list_registered_parsers() -> List[str]:
    """
    List all registered parser names.

    Returns:
        A list of registered parser names
    """
    return list(_parsers.keys())

@lru_cache(maxsize=1)
def load_cerl_schema() -> Dict[str, Any]:
    """
    Load the CERL schema from the schema.json file.

    Returns:
        The CERL schema as a dictionary
    """
    schema_path = Path("../shared/evaluation_type/CERL/schema.json")
    with open(schema_path, "r") as f:
        return json.load(f)

def validate_against_schema(data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Validate data against the CERL schema.

    Args:
        data: The data to validate

    Returns:
        A tuple of (is_valid, error_message)
    """
    try:
        schema = load_cerl_schema()
        validate(instance=data, schema=schema)
        return True, None
    except ValidationError as e:
        return False, str(e)

def validate_date_format(date_str: str) -> bool:
    """
    Validate that a date string is in the format YYYY-MM-DD.

    Args:
        date_str: The date string to validate

    Returns:
        True if the date is valid, False otherwise
    """
    if not date_str:
        return False

    pattern = r"^\d{4}-\d{2}-\d{2}$"
    if not re.match(pattern, date_str):
        return False

    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except ValueError:
        return False

def correct_future_date(date_str: str) -> Tuple[str, bool]:
    """
    Correct a future date by checking for common OCR errors like year transposition.

    Args:
        date_str: The date string to check and potentially correct

    Returns:
        A tuple of (corrected_date, was_corrected)
    """
    if not validate_date_format(date_str):
        return date_str, False

    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        current_year = datetime.now().year

        # Check if date is more than 70 years in the future (likely an OCR error)
        if date_obj.year > current_year + 70:
            # Common error: First two digits of year swapped (e.g., 2062 instead of 2026)
            year_str = str(date_obj.year)
            if len(year_str) == 4:
                # Try swapping first two digits
                swapped_year = year_str[1] + year_str[0] + year_str[2:]
                corrected_date = f"{swapped_year}-{date_obj.month:02d}-{date_obj.day:02d}"

                # Verify the corrected date is valid and not in the future
                if validate_date_format(corrected_date):
                    corrected_date_obj = datetime.strptime(corrected_date, "%Y-%m-%d")
                    if corrected_date_obj.year <= current_year + 5:  # Allow a small buffer for future dates
                        return corrected_date, True

        return date_str, False
    except ValueError:
        return date_str, False

def extract_json_with_regex(text: str, pattern: str) -> Dict[str, Any]:
    """
    Extract JSON from text using a regex pattern.

    Args:
        text: The text to extract JSON from
        pattern: The regex pattern to use

    Returns:
        The extracted JSON as a dictionary
    """
    match = re.search(pattern, text, re.DOTALL)
    if match:
        try:
            json_str = match.group(1).strip()
            # Handle potential trailing commas which are invalid in JSON
            json_str = re.sub(r',\s*}', '}', json_str)
            json_str = re.sub(r',\s*]', ']', json_str)
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass
    return {}

def process_extraction_result(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process an extraction result by validating and correcting dates.

    Args:
        data: The extraction result to process

    Returns:
        The processed extraction result
    """
    # Create a copy to avoid modifying the original
    result = data.copy()

    # Track if any corrections were made
    corrections_made = False

    # Process dates in the result
    if "constitutionDate" in result:
        corrected_date, was_corrected = correct_future_date(result["constitutionDate"])
        if was_corrected:
            result["constitutionDate"] = corrected_date
            # Adjust confidence if a correction was made
            if "confidence" in result:
                result["confidence"] = max(0.0, result["confidence"] - 0.2)
            corrections_made = True

    # Process dates in related parties
    if "relatedParties" in result and isinstance(result["relatedParties"], list):
        for party in result["relatedParties"]:
            if "startDate" in party:
                corrected_date, was_corrected = correct_future_date(party["startDate"])
                if was_corrected:
                    party["startDate"] = corrected_date
                    # Adjust confidence if a correction was made
                    if "confidence" in party:
                        party["confidence"] = max(0.0, party["confidence"] - 0.2)
                    corrections_made = True

    # Add a flag indicating if corrections were made
    result["_corrections_applied"] = corrections_made

    return result

@register_parser('vllama')
def parse_vllama(response: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse a vLLAMA response.

    Args:
        response: The vLLAMA response to parse

    Returns:
        The extracted data as a dictionary
    """
    try:
        # Extract content from vLLAMA response structure
        content = response['output']['message']['content'][0]['text']

        # Try different JSON patterns
        patterns = [
            r'```json\s*(.*?)\s*```',  # Code block with json
            r'```\s*(.*?)\s*```',      # Code block without language
            r'{[\s\S]*}',              # Just find a JSON object
        ]

        for pattern in patterns:
            result = extract_json_with_regex(content, pattern)
            if result:
                return process_extraction_result(result)

        # If we get here, none of the patterns worked
        raise ValueError("Could not extract valid JSON from vLLAMA response")
    except (KeyError, IndexError, ValueError) as e:
        raise ValueError(f"Error parsing vLLAMA response: {str(e)}")

@register_parser('claude')
def parse_claude(response: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse a Claude response.

    Args:
        response: The Claude response to parse

    Returns:
        The extracted data as a dictionary
    """
    try:
        # Extract content from Claude response structure
        content = response['content'][0]['text']

        # Try different JSON patterns
        patterns = [
            r'```json\s*(.*?)\s*```',  # Code block with json
            r'```\s*(.*?)\s*```',      # Code block without language
            r'{[\s\S]*}',              # Just find a JSON object
        ]

        for pattern in patterns:
            result = extract_json_with_regex(content, pattern)
            if result:
                return process_extraction_result(result)

        # If we get here, none of the patterns worked
        raise ValueError("Could not extract valid JSON from Claude response")
    except (KeyError, IndexError, ValueError) as e:
        raise ValueError(f"Error parsing Claude response: {str(e)}")

@register_parser('bedrock')
def parse_bedrock(response: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse a Bedrock response.

    Args:
        response: The Bedrock response to parse

    Returns:
        The extracted data as a dictionary
    """
    try:
        # Extract content from Bedrock response structure
        content = response['completion']

        # Try different JSON patterns
        patterns = [
            r'```json\s*(.*?)\s*```',  # Code block with json
            r'```\s*(.*?)\s*```',      # Code block without language
            r'{[\s\S]*}',              # Just find a JSON object
        ]

        for pattern in patterns:
            result = extract_json_with_regex(content, pattern)
            if result:
                return process_extraction_result(result)

        # If we get here, none of the patterns worked
        raise ValueError("Could not extract valid JSON from Bedrock response")
    except (KeyError, IndexError, ValueError) as e:
        raise ValueError(f"Error parsing Bedrock response: {str(e)}")

# Function to add a new parser dynamically
def add_parser(model_name: str, content_path: List[str], json_patterns: List[str] = None):
    """
    Add a new parser dynamically.

    Args:
        model_name: The name of the model to add a parser for
        content_path: The path to the content in the response
        json_patterns: The JSON patterns to try
    """
    if json_patterns is None:
        json_patterns = [
            r'```json\s*(.*?)\s*```',  # Code block with json
            r'```\s*(.*?)\s*```',      # Code block without language
            r'{[\s\S]*}',              # Just find a JSON object
        ]

    @register_parser(model_name)
    def parser(response: Dict[str, Any]) -> Dict[str, Any]:
        try:
            # Navigate to the content using the provided path
            content = response
            for key in content_path:
                content = content[key]

            # Try different JSON patterns
            for pattern in json_patterns:
                result = extract_json_with_regex(content, pattern)
                if result:
                    return process_extraction_result(result)

            # If we get here, none of the patterns worked
            raise ValueError(f"Could not extract valid JSON from {model_name} response")
        except (KeyError, IndexError, ValueError) as e:
            raise ValueError(f"Error parsing {model_name} response: {str(e)}")

    return parser

def load_test_response(file_path: str) -> Dict[str, Any]:
    """
    Load a test response from a file.

    Args:
        file_path: The path to the file to load

    Returns:
        The loaded response as a dictionary
    """
    with open(file_path, "r") as f:
        return json.load(f)

def test_parser(model_name: str, response_file: str) -> Dict[str, Any]:
    """
    Test a parser with a response file.

    Args:
        model_name: The name of the model to test
        response_file: The path to the response file

    Returns:
        The parsed response as a dictionary
    """
    response = load_test_response(response_file)
    parser = get_parser(model_name.lower())
    if not parser:
        raise ValueError(f"No parser registered for model: {model_name}")

    return parser(response)

def process_model_response(response: Dict[str, Any], model_name: str) -> Dict[str, Any]:
    """
    Process a model response using the appropriate parser.

    Args:
        response: The model response to process
        model_name: The name of the model

    Returns:
        The processed response as a dictionary
    """
    parser = get_parser(model_name.lower())
    if not parser:
        raise ValueError(f"No parser registered for model: {model_name}")

    result = parser(response)

    # Validate against schema
    is_valid, error = validate_against_schema(result)
    if not is_valid:
        print(f"Warning: Validation error: {error}")

    return result

def extract_from_file(file_path: str, model_name: str) -> Dict[str, Any]:
    """
    Extract data from a response file.

    Args:
        file_path: The path to the file to extract from
        model_name: The name of the model

    Returns:
        The extracted data as a dictionary
    """
    response = load_test_response(file_path)
    return process_model_response(response, model_name)

def batch_process_directory(directory: str, model_name: str, output_dir: str = None) -> List[Dict[str, Any]]:
    """
    Process all JSON files in a directory.

    Args:
        directory: The directory to process
        model_name: The name of the model
        output_dir: The directory to save results to

    Returns:
        A list of processed responses
    """
    results = []

    # Create output directory if specified
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    # Process each JSON file in the directory
    for file_name in os.listdir(directory):
        if file_name.endswith(".json"):
            file_path = os.path.join(directory, file_name)
            try:
                result = extract_from_file(file_path, model_name)
                results.append(result)

                # Save result to output directory if specified
                if output_dir:
                    output_path = os.path.join(output_dir, f"processed_{file_name}")
                    with open(output_path, "w") as f:
                        json.dump(result, f, indent=2)
            except Exception as e:
                print(f"Error processing {file_name}: {str(e)}")

    return results

# Example usage
if __name__ == "__main__":
    # Register parsers
    print(f"Registered parsers: {list_registered_parsers()}")

    # Test a parser
    # result = test_parser("vllama", "path/to/response.json")
    # print(json.dumps(result, indent=2))
