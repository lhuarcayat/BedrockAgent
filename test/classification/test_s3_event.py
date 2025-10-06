import json
import os
import sys
import boto3
from unittest.mock import MagicMock, patch
import pytest

# Add the parent directory to the Python path to import the Lambda function
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.index import handler

# Sample S3 event
s3_event = {
    "Records": [
        {
            "eventVersion": "2.1",
            "eventSource": "aws:s3",
            "awsRegion": "us-east-2",
            "eventTime": "2025-06-07T16:29:12.931Z",
            "eventName": "ObjectCreated:Put",
            "userIdentity": {
                "principalId": "AWS:AIDARUONPFJF5YEWRXODZ"
            },
            "requestParameters": {
                "sourceIPAddress": "200.215.228.182"
            },
            "responseElements": {
                "x-amz-request-id": "NHX4Z688QGVTYAXJ",
                "x-amz-id-2": "kTAG8Lb3h9E2C3KAg91VFbprizrUvZWkHP3gZkrAqqVc1GZMfDOPWGNVIQAP/kg8Kf2HCwDDTGdhq08Wq9mETkjBDfF8iGt7C0Sj5HmhYgo="
            },
            "s3": {
                "s3SchemaVersion": "1.0",
                "configurationId": "desk-ACC",
                "bucket": {
                    "name": "par-servicios-poc-dev-filling-desk",
                    "ownerIdentity": {
                        "principalId": "AUJEICOR8PAOU"
                    },
                    "arn": "arn:aws:s3:::par-servicios-poc-dev-filling-desk"
                },
                "object": {
                    "key": "par-servicios-poc/ACC/800216686/231_CA_2020-02-29.pdf",
                    "size": 3030,
                    "eTag": "a41b7f1a4f2f38be67dcce498fb5529e",
                    "versionId": "ZObgG9N8xcscvrloeLjI.xvjxXBtsuJs",
                    "sequencer": "00684468D8E5096FE8"
                }
            }
        }
    ]
}

# Sample invalid S3 event (not a PDF)
invalid_s3_event = {
    "Records": [
        {
            "eventVersion": "2.1",
            "eventSource": "aws:s3",
            "awsRegion": "us-east-2",
            "eventTime": "2025-06-07T16:29:12.931Z",
            "eventName": "ObjectCreated:Put",
            "s3": {
                "bucket": {
                    "name": "par-servicios-poc-dev-filling-desk"
                },
                "object": {
                    "key": "par-servicios-poc/ACC/ACC_extractor_prompt_v2.md"
                }
            }
        }
    ]
}

# Sample invalid S3 event (no document number)
no_docnum_s3_event = {
    "Records": [
        {
            "eventVersion": "2.1",
            "eventSource": "aws:s3",
            "awsRegion": "us-east-2",
            "eventTime": "2025-06-07T16:29:12.931Z",
            "eventName": "ObjectCreated:Put",
            "s3": {
                "bucket": {
                    "name": "par-servicios-poc-dev-filling-desk"
                },
                "object": {
                    "key": "par-servicios-poc/ACC/document.pdf"
                }
            }
        }
    ]
}

# Sample multiple records S3 event
multiple_records_s3_event = {
    "Records": [
        {
            "eventVersion": "2.1",
            "eventSource": "aws:s3",
            "awsRegion": "us-east-2",
            "eventTime": "2025-06-07T16:29:12.931Z",
            "eventName": "ObjectCreated:Put",
            "s3": {
                "bucket": {
                    "name": "par-servicios-poc-dev-filling-desk"
                },
                "object": {
                    "key": "par-servicios-poc/ACC/800216686/231_CA_2020-02-29.pdf"
                }
            }
        },
        {
            "eventVersion": "2.1",
            "eventSource": "aws:s3",
            "awsRegion": "us-east-2",
            "eventTime": "2025-06-07T16:30:15.123Z",
            "eventName": "ObjectCreated:Put",
            "s3": {
                "bucket": {
                    "name": "par-servicios-poc-dev-filling-desk"
                },
                "object": {
                    "key": "par-servicios-poc/CERL/860006752/22_CamCom_2020-02-28.pdf"
                }
            }
        }
    ]
}

@pytest.fixture
def mock_env_variables():
    """Set up environment variables for testing."""
    os.environ["S3_ORIGIN_BUCKET"] = "par-servicios-poc-dev-filling-desk"
    os.environ["EXTRACTION_SQS"] = "https://sqs.us-east-2.amazonaws.com/123456789012/extraction-queue"
    os.environ["BEDROCK_MODEL"] = "us.amazon.nova-pro-v1:0"
    os.environ["FALLBACK_MODEL"] = "us.meta.llama4-maverick-17b-instruct-v1:0"
    os.environ["REGION"] = "us-east-2"
    yield
    # Clean up
    for key in ["S3_ORIGIN_BUCKET", "EXTRACTION_SQS", "BEDROCK_MODEL", "FALLBACK_MODEL", "REGION"]:
        if key in os.environ:
            del os.environ[key]

@patch('boto3.client')
@patch('src.index.get_first_pdf_page')
@patch('src.index.create_bedrock_client')
@patch('src.index.converse_with_nova')
@patch('src.index.parse_classification')
@patch('src.index.send_to_extraction_queue')
def test_handler_with_s3_event(mock_send_to_sqs, mock_parse, mock_converse, mock_bedrock_client,
                              mock_get_first_page, mock_boto3, mock_env_variables):
    """Test the handler function with an S3 event."""
    # Mock S3 client
    mock_s3 = MagicMock()
    mock_boto3.return_value = mock_s3

    # Mock S3 get_object response
    mock_s3.get_object.return_value = {
        'Body': MagicMock(read=lambda: b'mock pdf content')
    }

    # Mock Bedrock client and response
    mock_bedrock = MagicMock()
    mock_bedrock_client.return_value = mock_bedrock

    # Mock PDF processing
    mock_get_first_page.return_value = b'mock first page'

    # Mock Bedrock response
    mock_converse.return_value = {"output": {"message": {"content": [{"text": "mock response"}]}}}

    # Mock classification parsing
    mock_parse.return_value = {
        "document_number": "800216686",
        "document_type": "company",
        "category": "ACC",
        "path": "s3://par-servicios-poc-dev-filling-desk/par-servicios-poc/ACC/800216686/231_CA_2020-02-29.pdf"
    }

    # Call the handler
    response = handler(s3_event, {})

    # Assertions
    assert response['statusCode'] == 200
    results = json.loads(response['body'])['results']
    assert len(results) == 1
    assert results[0]['status'] == 'success'
    assert results[0]['key'] == 'par-servicios-poc/ACC/800216686/231_CA_2020-02-29.pdf'

    # Verify S3 client was called correctly
    mock_boto3.assert_called_with('s3', region_name='us-east-2')
    mock_s3.get_object.assert_called_with(
        Bucket='par-servicios-poc-dev-filling-desk',
        Key='par-servicios-poc/ACC/800216686/231_CA_2020-02-29.pdf'
    )

    # Verify SQS message was sent
    mock_send_to_sqs.assert_called_once()

@patch('boto3.client')
def test_handler_with_invalid_pdf(mock_boto3, mock_env_variables):
    """Test the handler function with an invalid PDF file."""
    # Call the handler with invalid event
    response = handler(invalid_s3_event, {})

    # Assertions
    assert response['statusCode'] == 200
    results = json.loads(response['body'])['results']
    assert len(results) == 1
    assert results[0]['status'] == 'error'
    assert "Not a PDF file" in results[0]['error']

@patch('boto3.client')
def test_handler_with_no_document_number(mock_boto3, mock_env_variables):
    """Test the handler function with a PDF that has no document number in the path."""
    # Call the handler with invalid event
    response = handler(no_docnum_s3_event, {})

    # Assertions
    assert response['statusCode'] == 200
    results = json.loads(response['body'])['results']
    assert len(results) == 1
    assert results[0]['status'] == 'error'
    assert "No document number folder found in path" in results[0]['error']

@patch('boto3.client')
@patch('src.index.get_first_pdf_page')
@patch('src.index.create_bedrock_client')
@patch('src.index.converse_with_nova')
@patch('src.index.parse_classification')
@patch('src.index.send_to_extraction_queue')
def test_handler_with_multiple_records(mock_send_to_sqs, mock_parse, mock_converse, mock_bedrock_client,
                                     mock_get_first_page, mock_boto3, mock_env_variables):
    """Test the handler function with multiple records in the S3 event."""
    # Mock S3 client
    mock_s3 = MagicMock()
    mock_boto3.return_value = mock_s3

    # Mock S3 get_object response
    mock_s3.get_object.return_value = {
        'Body': MagicMock(read=lambda: b'mock pdf content')
    }

    # Mock Bedrock client and response
    mock_bedrock = MagicMock()
    mock_bedrock_client.return_value = mock_bedrock

    # Mock PDF processing
    mock_get_first_page.return_value = b'mock first page'

    # Mock Bedrock response
    mock_converse.return_value = {"output": {"message": {"content": [{"text": "mock response"}]}}}

    # Mock classification parsing
    mock_parse.return_value = {
        "document_number": "800216686",
        "document_type": "company",
        "category": "ACC",
        "path": "s3://par-servicios-poc-dev-filling-desk/par-servicios-poc/ACC/800216686/231_CA_2020-02-29.pdf"
    }

    # Call the handler
    response = handler(multiple_records_s3_event, {})

    # Assertions
    assert response['statusCode'] == 200
    results = json.loads(response['body'])['results']
    assert len(results) == 2
    assert results[0]['status'] == 'success'
    assert results[1]['status'] == 'success'

    # Verify S3 client was called correctly for both records
    assert mock_s3.get_object.call_count == 2

    # Verify SQS message was sent for both records
    assert mock_send_to_sqs.call_count == 2

if __name__ == "__main__":
    # Set up environment variables
    os.environ["S3_ORIGIN_BUCKET"] = "par-servicios-poc-dev-filling-desk"
    os.environ["EXTRACTION_SQS"] = "https://sqs.us-east-2.amazonaws.com/123456789012/extraction-queue"
    os.environ["BEDROCK_MODEL"] = "us.amazon.nova-pro-v1:0"
    os.environ["FALLBACK_MODEL"] = "us.meta.llama4-maverick-17b-instruct-v1:0"
    os.environ["REGION"] = "us-east-2"

    # Print the event for manual testing
    print("S3 Event:")
    print(json.dumps(s3_event, indent=2))

    # To run this test manually, uncomment the following line:
    # response = handler(s3_event, {})
    # print(json.dumps(response, indent=2))
