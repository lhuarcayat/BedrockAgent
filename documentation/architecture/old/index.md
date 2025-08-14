# Par Servicios Document Processing Architecture

## Introduction

This document serves as the main index for the architecture documentation of the Par Servicios document processing system. The system is designed to process various types of documents using AWS serverless services and Amazon Bedrock AI models.

## Architecture Documents

- [**High-Level Architecture**](./architecture_diagram.md) - Visual representation of the system workflow and components
- [**Detailed Architecture**](./detailed_architecture.md) - Comprehensive documentation with environment-specific details
- [**README**](./README.md) - Overview of the architecture documentation

## System Overview

The Par Servicios document processing system is a serverless, event-driven architecture built on AWS that processes different types of business documents. The system extracts structured information from these documents using Amazon Bedrock AI models and stores the results in JSON format.

### Key Components

1. **S3 Buckets**
   - Document Filing Desk: Entry point for document processing
   - JSON Results: Storage for extraction results

2. **Lambda Functions**
   - Classification: Verifies and categorizes documents
   - Extraction and Scoring: Extracts information from documents
   - Fallback Processing: Handles low-confidence extractions
   - Notification: Manages manual review process

3. **SQS Queues**
   - Extraction Queue: Passes messages from classification to extraction
   - Fallback Queue: Handles documents requiring additional processing

4. **AI/ML Services**
   - Amazon Bedrock: Primary and fallback models for document understanding
   - Amazon Textract: OCR and document analysis for fallback processing

### Document Types

The system processes five types of documents:

| Document Type | Description | Key Information Extracted |
|---------------|-------------|---------------------------|
| CERL | Certificados de Existencia y Representación Legal | Company information, registration details, related parties |
| CECRL | Copia de cédulas de ciudadanía del Representante Legal | Legal representative identification information |
| RUT | Registro Único Tributario | Tax identification, company type, address |
| RUB | Registro Único de Beneficiarios | Beneficial owners, participation percentages |
| ACC | Composiciones Accionarias | Shareholder information, ownership structure |

### Environments

The architecture is deployed in two environments:

| Environment | Purpose | Resource Prefix |
|-------------|---------|----------------|
| DEV | Development and testing | par-servicios-poc-dev |
| QA | Quality assurance and validation | par-servicios-poc-qa |

## Process Flow

1. **Document Upload**
   - Documents are uploaded to the Filing Desk S3 bucket in the appropriate folder based on document type

2. **Classification Phase**
   - S3 ObjectCreated events trigger the Classification Lambda function
   - The function verifies the document and assigns an initial score
   - Valid documents trigger a message sent to the Extraction SQS Queue

3. **Extraction and Scoring Phase**
   - The Extraction Lambda function processes messages from the Extraction Queue
   - It uses Amazon Bedrock models to extract information based on document type
   - High-scoring results are saved directly to the JSON Results S3 bucket
   - Low-scoring results are sent to the Fallback Queue for additional processing

4. **Fallback Phase**
   - For documents with low extraction confidence, additional processing is performed
   - This includes using Amazon Textract for OCR and the fallback Bedrock model
   - Successful extractions are saved to the JSON Results bucket
   - Failed extractions trigger notifications for manual review

5. **Manual Review**
   - Documents that fail automated extraction are flagged for manual review
   - Notifications are sent via SNS to alert reviewers

## Architecture Diagrams

### High-Level Architecture

The high-level architecture diagram provides a visual representation of the main components and data flow of the system. It shows how documents move through the different phases of processing and how the components interact with each other.

### Detailed Architecture

The detailed architecture diagram includes environment-specific information, showing the exact resources deployed in both DEV and QA environments. It provides a comprehensive view of all components, their relationships, and their configurations.

## Implementation Details

The infrastructure is defined as code using Terraform modules:
- SQS queues are created using the `terraform-aws-modules/sqs/aws` module
- Lambda functions are created using a custom `lambda-wrapper` module
- S3 buckets are created using a custom `s3` module
- Event mappings connect the components together

The Terraform code creates all necessary resources, configures permissions, and sets up event triggers to enable the serverless event-driven architecture.
