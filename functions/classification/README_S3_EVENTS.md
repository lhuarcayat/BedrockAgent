# S3 Event Processing for Classification Lambda

This document describes how the Classification Lambda function processes S3 events when PDF files are uploaded to the S3 bucket.

## Overview

The Lambda function is triggered when a PDF file is uploaded to the S3 bucket. It processes the PDF file, classifies it using Amazon Bedrock, and sends the classification result to an SQS queue for further processing.

## Environment Variables

The Lambda function uses the following environment variables:

- `S3_ORIGIN_BUCKET`: The name of the S3 bucket where PDF files are uploaded
- `EXTRACTION_SQS`: The URL of the SQS queue where classification results are sent
- `BEDROCK_MODEL`: The ID of the Amazon Bedrock model to use for classification (default: "us.amazon.nova-pro-v1:0")
- `FALLBACK_MODEL`: The ID of the fallback model to use if the primary model is unavailable (default: "us.meta.llama4-maverick-17b-instruct-v1:0")
- `REGION`: The AWS region where the Lambda function and other resources are deployed (default: "us-east-1")

## S3 Event Structure

The Lambda function expects S3 events with the following structure:

```json
{
  "Records": [
    {
      "eventSource": "aws:s3",
      "s3": {
        "bucket": {
          "name": "bucket-name"
        },
        "object": {
          "key": "path/to/document_number/filename.pdf"
        }
      }
    }
  ]
}
```

## Path Validation

The Lambda function validates the S3 object key to ensure it follows the expected pattern:

1. The file must be a PDF file (ends with `.pdf`)
2. The path must contain a document number folder (6+ digits)

Example of a valid path: `par-servicios-poc/ACC/800216686/231_CA_2020-02-29.pdf`

## Processing Flow

1. The Lambda function is triggered by an S3 event
2. For each record in the event:
   - Extract the bucket name and object key
   - Validate the object key
   - Download the PDF file from S3
   - Extract the first page of the PDF
   - Send the PDF to Amazon Bedrock for classification
   - Parse the classification result
   - Send the result to the SQS queue
   - Return the result to the caller

## Testing

You can test the Lambda function using the provided `test_s3_event.py` file:

```bash
cd functions/classification/src
python -m pytest test_s3_event.py -v
```

Or you can manually test the function by uploading a PDF file to the S3 bucket and checking the CloudWatch logs.

## Error Handling

The Lambda function handles the following error cases:

- Invalid S3 event structure
- Invalid object key (not a PDF file or missing document number folder)
- Error downloading the PDF file from S3
- Error processing the PDF file
- Error sending the result to the SQS queue

In all cases, the Lambda function logs the error and returns an appropriate error response.
