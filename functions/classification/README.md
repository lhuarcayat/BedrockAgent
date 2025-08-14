# Document Classification Lambda Function

This Lambda function uses Amazon Bedrock to classify PDF documents into different legal document categories.

## Overview

The function takes a PDF document and a folder path as input, extracts the first page of the PDF, and uses Amazon Bedrock's Nova Pro model to classify the document into one of the following categories:

- CERL: Certificados de Existencia y Representación Legal
- CECRL: Copia de cédulas de ciudadanía del Representante Legal
- RUT: Registro Único Tributario
- RUB: Registro Único de Beneficiarios
- ACC: Composiciones Accionarias
- BLANK: Empty documents or those with only whitespace
- LINK_ONLY: Documents containing only a hyperlink with no other meaningful text

## Input Format

The Lambda function expects an event with the following structure:

```json
{
  "pdf_content": "base64-encoded-pdf-content",
  "folder_path": "CATEGORY/DOCUMENT_NUMBER/FILENAME.pdf"
}
```

- `pdf_content`: The PDF content encoded as a base64 string
- `folder_path`: The path to the PDF file, following the pattern `CATEGORY/DOCUMENT_NUMBER/FILENAME.pdf`

## Output Format

The function returns a response with the following structure:

```json
{
  "statusCode": 200,
  "body": {
    "path": "file_examples/CATEGORY/DOCUMENT_NUMBER",
    "result": {
      "document_number": "DOCUMENT_NUMBER",
      "document_type": "person|company",
      "category": "CERL|CECRL|RUT|RUB|ACC|BLANK|LINK_ONLY",
      "text": "extracted text from the PDF",
      "path": "file_examples/CATEGORY/DOCUMENT_NUMBER"
    },
    "document_type": "person|company",
    "document_number": "DOCUMENT_NUMBER",
    "category": "CERL|CECRL|RUT|RUB|ACC|BLANK|LINK_ONLY"
  }
}
```

## Dependencies

The function requires the following dependencies:

- boto3
- PyPDF2
- pydantic

These dependencies are listed in the `requirements.txt` file.

## Testing

You can test the function locally using the `test_lambda.py` script:

```bash
cd functions/classification/src
python test_lambda.py
```

Make sure to adjust the PDF file path in the script to point to an actual PDF file in your project.

## Deployment

The function is designed to be deployed as an AWS Lambda function. You can deploy it using the Terraform configuration in the `terraform` directory.

## Prompt Files

The function uses two prompt files to guide the Bedrock model:

- `instructions/user.txt`: Contains the user prompt that describes the task and expected output format
- `instructions/system.txt`: Contains the system prompt that sets the behavior and guidelines for the model

These files are loaded at runtime and sent to the Bedrock model along with the PDF content.
