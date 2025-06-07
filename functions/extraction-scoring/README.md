# Extraction-Scoring Lambda

This Lambda function is part of the document processing pipeline. It receives classification results from the classification Lambda via SQS and logs the payload for further processing.

## Overview

The extraction-scoring Lambda is triggered by messages in the SQS queue that contains classification results. It logs the incoming payload, which can be used for monitoring, debugging, and as a foundation for future extraction and scoring functionality.

## Function Structure

- `index.py`: Contains the Lambda handler function that processes SQS messages
- `test_lambda.py`: Test script to simulate SQS events locally
- `requirements.txt`: Lists dependencies (currently none required)

## Input Format

The Lambda expects SQS events with the following structure:

```json
{
  "Records": [
    {
      "messageId": "19dd0b57-b21e-4ac1-bd88-01bbb068cb78",
      "body": "{\"document_id\":\"test-doc-123\",\"classification\":\"ACC\",\"confidence\":0.95,...}"
    }
  ]
}
```

The `body` field contains a JSON string with the classification results.

## Output

The Lambda logs the received payload to CloudWatch Logs and returns a success response:

```json
{
  "statusCode": 200,
  "body": "{\"message\":\"Payload logged successfully\"}"
}
```

## Testing Locally

To test the Lambda function locally:

1. Navigate to the `functions/extraction-scoring/src` directory
2. Run the test script:

```bash
python test_lambda.py
```

This will simulate an SQS event with sample classification data and show the Lambda's response.

## Deployment

The Lambda is deployed using Terraform. The configuration is in `terraform/main.tf` and includes:

- Function definition
- IAM permissions
- SQS trigger configuration
- Environment variables

## Integration

This Lambda is part of a pipeline:

1. Classification Lambda processes documents and sends results to SQS
2. SQS triggers this Extraction-Scoring Lambda
3. This Lambda logs the payload (and will be extended for extraction and scoring in the future)

## Environment Variables

- `S3_ORIGIN_BUCKET`: Source bucket for documents
- `FALLBACK_SQS`: Queue for fallback processing
- `DESTINATION_BUCKET`: Bucket for storing results
- `BEDROCK_MODEL`: Primary Bedrock model to use
- `FALLBACK_MODEL`: Backup model if primary fails
- `REGION`: AWS region
