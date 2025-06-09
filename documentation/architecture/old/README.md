# Architecture Documentation

This folder contains architecture diagrams and detailed documentation for the Par Servicios document processing system built on AWS using serverless services and Amazon Bedrock.

## Contents

1. [**architecture_diagram.md**](./architecture_diagram.md) - High-level architecture diagram showing the main components and data flow of the system.
   - Provides a visual representation of the document processing workflow
   - Includes descriptions of each component and its purpose
   - Shows the relationships between different AWS services

2. [**detailed_architecture.md**](./detailed_architecture.md) - Detailed architecture documentation with environment-specific information.
   - Contains a comprehensive diagram showing both DEV and QA environments
   - Lists all resources with their exact names and ARNs
   - Provides detailed configuration information for each component
   - Includes security considerations and implementation details

## Diagram Legend

The architecture diagrams use the following color coding for AWS services:

- **Green** (🟢): S3 Buckets
- **Orange** (🟠): Lambda Functions
- **Purple** (🟣): SQS Queues and SNS Topics
- **Blue** (🔵): AI/ML Services (Bedrock, Textract)
- **Brown** (🟤): IAM Roles

## System Overview

The Par Servicios document processing system is designed to:

1. Receive documents in an S3 bucket organized by document type
2. Classify and verify documents using Lambda functions
3. Extract information using Amazon Bedrock models
4. Store results in JSON format
5. Provide fallback mechanisms for low-confidence extractions
6. Enable manual review for failed extractions

The system processes five types of documents:
- CERL: Certificados de Existencia y Representación Legal
- CECRL: Copia de cédulas de ciudadanía del Representante Legal
- RUT: Registro Único Tributario
- RUB: Registro Único de Beneficiarios
- ACC: Composiciones Accionarias

## Viewing the Diagrams

The diagrams are created using Mermaid, which is supported by many Markdown viewers including GitHub and VS Code. To view the diagrams:

1. Open the .md files in a Markdown viewer that supports Mermaid
2. Alternatively, copy the Mermaid code and paste it into the [Mermaid Live Editor](https://mermaid.live/)

## Updating the Diagrams

If you need to update the architecture diagrams:

1. Edit the Mermaid code in the respective .md files
2. Test your changes in the [Mermaid Live Editor](https://mermaid.live/)
3. Update the component descriptions if necessary
4. Commit your changes to the repository
