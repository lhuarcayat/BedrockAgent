import json
import os
import sys
from index import handler

def test_extraction_scoring_lambda():
    """
    Test the extraction-scoring Lambda function with a sample SQS event.
    This simulates receiving a message from the classification Lambda.
    """
    # Sample classification payload that would be sent to SQS
    classification_result = {
        "document_id": "test-doc-123",
        "classification": "ACC",  # Example classification type
        "confidence": 0.95,
        "metadata": {
            "filename": "example.pdf",
            "timestamp": "2025-06-06T12:00:00Z",
            "pages": 5
        }
    }

    # Create a sample SQS event structure
    sqs_event = {
        "Records": [
            {
                "messageId": "19dd0b57-b21e-4ac1-bd88-01bbb068cb78",
                "receiptHandle": "MessageReceiptHandle",
                "body": json.dumps(classification_result),
                "attributes": {
                    "ApproximateReceiveCount": "1",
                    "SentTimestamp": "1523232000000",
                    "SenderId": "123456789012",
                    "ApproximateFirstReceiveTimestamp": "1523232000001"
                },
                "messageAttributes": {},
                "md5OfBody": "7b270e59b47ff90a553787216d55d91d",
                "eventSource": "aws:sqs",
                "eventSourceARN": "arn:aws:sqs:us-west-2:123456789012:extraction-queue",
                "awsRegion": "us-west-2"
            }
        ]
    }

    # Call the Lambda handler with the test event
    print("Testing extraction-scoring Lambda with sample SQS event...")
    response = handler(sqs_event, None)

    print(f"\nLambda Response:")
    print(json.dumps(response, indent=2))

    print("\nTest completed. Check the logs above to verify the Lambda processed the event correctly.")

    return response

if __name__ == "__main__":
    test_extraction_scoring_lambda()
