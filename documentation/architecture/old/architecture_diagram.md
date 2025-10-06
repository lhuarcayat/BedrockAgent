# AWS Architecture: Par Servicios Document Processing with Amazon Bedrock

This document presents the architecture diagram for the Par Servicios document processing system using AWS serverless services and Amazon Bedrock.

## Architecture Overview

The system processes different types of documents (CERL, CECRL, RUT, RUB, ACC) through a serverless event-driven architecture. Documents are uploaded to an S3 bucket, processed by Lambda functions using Amazon Bedrock models, and results are stored in another S3 bucket.

```mermaid
%%{init: {"theme": "neutral", "flowchart": {"htmlLabels": true}} }%%
flowchart TD
    subgraph AWS["AWS Cloud"]
        subgraph ClassificationPhase["Classification Phase"]
            S3FilingDesk[(S3 - Document Filing Desk)]
            LambdaClassification["Lambda - Verification\nand Categorization"]
            ModelCheck["Model\nCheck\nEmpty Files\nand set\ninitial score"]

            S3FilingDesk -->|"ObjectCreated event"| LambdaClassification
            LambdaClassification --- ModelCheck
        end

        SQSExtraction[("SQS ExtractionQueue")]
        ClassificationPhase -->|"Only Files\nwith data"| SQSExtraction

        subgraph ExtractionPhase["Extraction and Scoring Phase"]
            LambdaExtraction["Lambda - Extraction\nand Scoring\nby document type"]
            ModelExtract["Model\nExtract\nInformation"]

            SQSExtraction --> LambdaExtraction
            LambdaExtraction --- ModelExtract
        end

        S3Results[(S3 - Bucket Json Results)]
        ExtractionPhase -->|"Alto Scoring"| S3Results

        SQSFallback[("SQS FallbackQueue")]
        ExtractionPhase -->|"Bajo Scoring"| SQSFallback

        subgraph FallbackPhase["Fallback Phase - Re Scoring"]
            LambdaFallback["Lambda - Textract OCR\nNova Re-Extraction"]
            TextractService["Textract"]
            ModelFallback["Model\nExtract\nInformation"]

            SQSFallback --> LambdaFallback
            LambdaFallback --- TextractService
            LambdaFallback --- ModelFallback
        end

        FallbackPhase -->|"Alto Scoring"| S3Results

        subgraph LowSuccess["Low Success"]
            S3ResultsLow[(S3 - Bucket\nJson Results)]
            LambdaNotification["Lambda - Notification\nManual Review"]
            SNSTopic[("SNS")]

            S3ResultsLow --- LambdaNotification
            LambdaNotification --- SNSTopic
        end

        FallbackPhase -->|"Bajo Scoring"| LowSuccess

        %% Legend
        CloudWatch[("CloudWatch")]
        IAMRole["Role"]
    end

    classDef s3 fill:#3F8624,color:white,stroke:#294D1A,stroke-width:2px
    classDef lambda fill:#F58536,color:white,stroke:#9E5624,stroke-width:2px
    classDef sqs fill:#CC2264,color:white,stroke:#7A1A3C,stroke-width:2px
    classDef model fill:#3B48CC,color:white,stroke:#232A7A,stroke-width:2px
    classDef textract fill:#CC2264,color:white,stroke:#7A1A3C,stroke-width:2px
    classDef sns fill:#CC2264,color:white,stroke:#7A1A3C,stroke-width:2px
    classDef cloudwatch fill:#3B48CC,color:white,stroke:#232A7A,stroke-width:2px
    classDef role fill:#D86613,color:white,stroke:#824013,stroke-width:2px

    class S3FilingDesk,S3Results,S3ResultsLow s3
    class LambdaClassification,LambdaExtraction,LambdaFallback,LambdaNotification lambda
    class SQSExtraction,SQSFallback,SNSTopic sqs
    class ModelCheck,ModelExtract,ModelFallback model
    class TextractService textract
    class CloudWatch cloudwatch
    class IAMRole role
```

## Components Description

### 1. Document Filing Desk (S3 Bucket)
- **Purpose**: Entry point for document processing
- **Structure**:
  ```
  s3://par-servicios-poc-[env]-filling-desk/
  ├── par-servicios-poc/CERL/     # Certificados de Existencia y Representación Legal
  ├── par-servicios-poc/CECRL/    # Copia de cédulas de ciudadadanía del Representante Legal
  ├── par-servicios-poc/RUT/      # Registro Único Tributario
  ├── par-servicios-poc/RUB/      # Registro Único de Beneficiarios
  └── par-servicios-poc/ACC/      # Composiciones Accionarias
  ```

### 2. Classification Phase
- **Lambda Function**: Verifies and categorizes documents
- **Trigger**: S3 ObjectCreated events
- **Process**: Checks if documents are not empty, assigns initial score
- **Output**: Sends message to SQS Extraction Queue

### 3. Extraction and Scoring Phase
- **Lambda Function**: Extracts information based on document type
- **Trigger**: Messages from SQS Extraction Queue
- **Process**: Uses Amazon Bedrock models to extract data
- **Output**:
  - High score: Saves JSON results to S3 bucket
  - Low score: Sends to SQS Fallback Queue

### 4. Fallback Phase
- **Lambda Function**: Re-processes documents using Textract and Bedrock
- **Trigger**: Messages from SQS Fallback Queue
- **Process**: Uses Amazon Textract OCR and Bedrock models
- **Output**:
  - Success: Saves to S3 JSON Results bucket
  - Failure: Sends to Notification Lambda

### 5. JSON Results Bucket
- **Purpose**: Stores extraction results
- **Structure**: Same folder structure as Filing Desk bucket

### 6. Notification System
- **Lambda Function**: Handles failed extractions
- **Process**: Saves information and sends notification
- **Output**: SNS notification for manual review

## Environment Configuration

The architecture is deployed in two environments:

| Environment | Resource Prefix | Region |
|-------------|----------------|--------|
| DEV | par-servicios-poc-dev | us-east-2 |
| QA | par-servicios-poc-qa | us-east-2 |

## AWS Services Used

- **S3**: Document storage and results
- **Lambda**: Serverless compute for document processing
- **SQS**: Asynchronous message queuing
- **Amazon Bedrock**: AI models for document understanding
- **Amazon Textract**: OCR and document analysis
- **SNS**: Notifications for manual review
- **IAM**: Security and access control
- **CloudWatch**: Monitoring and logging
