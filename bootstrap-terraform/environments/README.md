# Environment Configuration Files

This directory contains environment-specific Terraform variable files for the PAR Servicios POC Bedrock project.

## File Structure

- `*.tfvars.example` - Template files showing required variables
- `*.tfvars` - Actual environment configuration files (git-ignored for security)

## Required Variables

Each environment file should contain the following variables:

### Core Infrastructure
- `aws_region` - AWS region for deployment (e.g., "us-east-1")
- `environment` - Environment name (dev, qa, prod)
- `project_prefix` - Project prefix for resource naming
- `account_id` - AWS account ID for cross-account operations

### Bedrock Configuration
- `bedrock_model` - Primary model ID (e.g., "us.amazon.nova-pro-v1:0")
- `fallback_model` - Fallback model ID (e.g., "us.mistral.pixtral-large-2502-v1:0")

### S3 Configuration
- `source_bucket_suffix` - Suffix for source document bucket
- `destination_bucket_suffix` - Suffix for processed results bucket

### Lambda Configuration
- `lambda_timeout` - Function timeout in seconds (default: 300)
- `lambda_memory` - Function memory in MB (default: 1024)

## Usage

1. Copy the appropriate `.tfvars.example` file to `.tfvars`
2. Fill in the actual values for your environment
3. The `.tfvars` files are git-ignored for security

## Examples

See the example files for reference configurations:
- `dev.tfvars.example` - Development environment
- `qa.tfvars.example` - QA environment  
- `prod.tfvars.example` - Production environment