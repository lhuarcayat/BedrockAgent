import json
import os
import sys
from unittest.mock import Mock, patch
from datetime import datetime, timezone

# Add the fallback processing source to the path
sys.path.insert(0, '../../functions/fallback-processing/src')
sys.path.insert(0, '../../functions/shared')

# Import the fallback processing functions
from index import (
    handler, 
    process_fallback_message,
    create_manual_review_record,
    extract_document_number_from_path,
    extract_category_from_payload,
    extract_error_information,
    extract_models_used
)

def create_sample_extraction_failure_payload():
    """Create a sample payload that would be sent to the fallback queue."""
    return {
        "path": "s3://par-servicios-poc-dev-filling-desk/par-servicios-poc/CERL/890915475/test-document.pdf",
        "result": {
            "category": "CERL",
            "document_type": "NIT",
            "document_number": "890915475-1",
            "status": "parse_error",
            "error_message": "Failed to parse model response as valid JSON",
            "model_used": "us.amazon.nova-pro-v1:0",
            "fallback_used": True,
            "fallback_model": "us.anthropic.claude-sonnet-4-20250514-v1:0",
            "processing_failed": True
        },
        "document_type": "NIT",
        "document_number": "890915475-1",
        "category": "CERL",
        "fallback_used": True
    }

def create_sample_sqs_event():
    """Create a sample SQS event with fallback messages."""
    payload = create_sample_extraction_failure_payload()
    
    return {
        "Records": [
            {
                "messageId": "test-message-id-1",
                "receiptHandle": "test-receipt-handle",
                "body": json.dumps(payload),
                "attributes": {
                    "ApproximateReceiveCount": "1",
                    "SentTimestamp": "1634567890000",
                    "SenderId": "AIDAIENQZJOLO23YVJ4VO",
                    "ApproximateFirstReceiveTimestamp": "1634567890000"
                },
                "messageAttributes": {},
                "md5OfBody": "test-md5-hash",
                "eventSource": "aws:sqs",
                "eventSourceARN": "arn:aws:sqs:us-east-2:123456789012:fallback-queue",
                "awsRegion": "us-east-2"
            }
        ]
    }

def test_extract_document_number():
    """Test document number extraction from S3 paths."""
    test_cases = [
        ("s3://bucket/par-servicios-poc/CERL/890915475/document.pdf", "890915475"),
        ("s3://bucket/folder/123456789/file.pdf", "123456789"),
        ("s3://bucket/invalid/path.pdf", None),
        ("s3://bucket/short/12345/file.pdf", None)  # Less than 6 digits
    ]
    
    for path, expected in test_cases:
        result = extract_document_number_from_path(path)
        print(f"Path: {path}")
        print(f"Expected: {expected}, Got: {result}")
        assert result == expected, f"Failed for path {path}: expected {expected}, got {result}"
    
    print("✅ Document number extraction tests passed")

def test_extract_category():
    """Test category extraction from payload."""
    # Test direct category field
    payload1 = {"category": "CERL"}
    assert extract_category_from_payload(payload1) == "CERL"
    
    # Test category from result object
    payload2 = {"result": {"category": "RUT"}}
    assert extract_category_from_payload(payload2) == "RUT"
    
    # Test category from path
    payload3 = {"path": "s3://bucket/par-servicios-poc/CECRL/123456/file.pdf"}
    assert extract_category_from_payload(payload3) == "CECRL"
    
    # Test unknown category
    payload4 = {"path": "s3://bucket/unknown/path.pdf"}
    assert extract_category_from_payload(payload4) == "UNKNOWN"
    
    print("✅ Category extraction tests passed")

def test_extract_error_information():
    """Test error information extraction."""
    payload = {
        "result": {
            "status": "parse_error",
            "error_message": "Failed to parse JSON response",
            "processing_failed": True
        }
    }
    
    error_info = extract_error_information(payload)
    
    assert error_info["error_type"] == "parse_error"
    assert "Failed to parse model response as valid JSON" in error_info["error_message"]
    assert error_info["raw_error_message"] == "Failed to parse JSON response"
    assert error_info["processing_failed"] == True
    
    print("✅ Error information extraction tests passed")

def test_extract_models_used():
    """Test models used extraction."""
    payload = {
        "result": {
            "model_used": "us.amazon.nova-pro-v1:0",
            "fallback_used": True,
            "fallback_model": "us.anthropic.claude-sonnet-4-20250514-v1:0"
        }
    }
    
    models = extract_models_used(payload)
    
    assert len(models) == 2
    assert "us.amazon.nova-pro-v1:0" in models
    assert "us.anthropic.claude-sonnet-4-20250514-v1:0" in models
    
    print("✅ Models used extraction tests passed")

def test_create_manual_review_record():
    """Test manual review record creation."""
    payload = create_sample_extraction_failure_payload()
    record_id = "test-record-123"
    
    # Mock environment variables
    with patch.dict(os.environ, {
        'BEDROCK_MODEL': 'us.amazon.nova-pro-v1:0',
        'FALLBACK_MODEL': 'us.anthropic.claude-sonnet-4-20250514-v1:0',
        'S3_ORIGIN_BUCKET': 'test-bucket'
    }):
        record = create_manual_review_record(payload, record_id)
    
    # Verify record structure
    assert record["pk"].startswith("FAILED#CERL")
    assert record["gsi1pk"] == "DOC#890915475"
    assert record["category"] == "CERL"
    assert record["document_number"] == "890915475"
    assert record["error_type"] == "parse_error"
    assert record["record_id"] == record_id
    assert "models_used" in record
    assert record["fallback_used"] == True
    assert "ttl" in record
    
    print("✅ Manual review record creation tests passed")

@patch('index.create_dynamodb_client')
@patch.dict(os.environ, {'MANUAL_REVIEW_TABLE': 'test-table'})
def test_process_fallback_message(mock_dynamodb):
    """Test processing a single fallback message."""
    # Mock DynamoDB client
    mock_client = Mock()
    mock_dynamodb.return_value = mock_client
    
    # Create test SQS record
    payload = create_sample_extraction_failure_payload()
    sqs_record = {
        "messageId": "test-message-123",
        "body": json.dumps(payload)
    }
    
    # Process the message
    result = process_fallback_message(sqs_record)
    
    # Verify result
    assert result["messageId"] == "test-message-123"
    assert result["status"] == "success"
    assert result["category"] == "CERL"
    assert result["document_number"] == "890915475"
    assert result["error_type"] == "parse_error"
    
    # Verify DynamoDB was called
    mock_client.put_item.assert_called_once()
    
    print("✅ Process fallback message tests passed")

@patch('index.create_dynamodb_client')
@patch.dict(os.environ, {'MANUAL_REVIEW_TABLE': 'test-table'})
def test_lambda_handler(mock_dynamodb):
    """Test the complete Lambda handler."""
    # Mock DynamoDB client
    mock_client = Mock()
    mock_dynamodb.return_value = mock_client
    
    # Create test event
    event = create_sample_sqs_event()
    context = None
    
    # Call handler
    response = handler(event, context)
    
    # Verify response
    assert response["statusCode"] == 200
    
    # Parse response body
    body = json.loads(response["body"])
    assert body["summary"]["totalMessages"] == 1
    assert body["summary"]["successfulProcessing"] == 1
    assert body["summary"]["failedProcessing"] == 0
    
    # Verify no batch failures
    assert "batchItemFailures" not in response
    
    # Verify DynamoDB was called
    mock_client.put_item.assert_called_once()
    
    print("✅ Lambda handler tests passed")

def test_invalid_json_message():
    """Test handling of invalid JSON in SQS message."""
    sqs_record = {
        "messageId": "test-invalid-json",
        "body": "invalid json content"
    }
    
    result = process_fallback_message(sqs_record)
    
    assert result["messageId"] == "test-invalid-json"
    assert result["status"] == "error"
    assert "Invalid JSON" in result["error"]
    
    print("✅ Invalid JSON handling tests passed")

def run_all_tests():
    """Run all fallback processing tests."""
    print("🧪 Running Fallback Processing Lambda Tests")
    print("=" * 50)
    
    try:
        test_extract_document_number()
        test_extract_category()
        test_extract_error_information()
        test_extract_models_used()
        test_create_manual_review_record()
        test_process_fallback_message()
        test_lambda_handler()
        test_invalid_json_message()
        
        print("\n" + "=" * 50)
        print("🎉 All fallback processing tests passed!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {str(e)}")
        raise

if __name__ == "__main__":
    run_all_tests()