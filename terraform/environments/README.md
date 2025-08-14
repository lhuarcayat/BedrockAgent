# Terraform Environment Configuration

This directory contains environment-specific Terraform variable files for the PAR Servicios POC Bedrock project.

## Variables

Based on `terraform/variables.tf`, the following variables are required:

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `aws_region` | string | "us-east-2" | AWS region for deployment |
| `stage_name` | string | "dev" | Stage name (dev, qa, prod) |
| `service_name` | string | "par-servicios-poc-bedrock" | Service name |
| `project_prefix` | string | "par-servicios-poc" | Project prefix for resource naming |
| `cost_component` | string | "agents-bedrock" | Cost identification component |
| `bedrock_model` | string | *required* | Primary Bedrock model ID |
| `fallback_model` | string | *required* | Fallback Bedrock model ID |

## Usage

1. Copy the appropriate `.tfvars.example` file to `.tfvars`
2. Replace placeholder values with your actual configuration
3. Ensure `.tfvars` files are in `.gitignore` for security

## Example Files

- `dev.tfvars.example` - Development environment template
- `qa.tfvars.example` - QA environment template  
- `prod.tfvars.example` - Production environment template

## Required Models

The `bedrock_model` and `fallback_model` variables must be set to valid AWS Bedrock model IDs, such as:
- `us.amazon.nova-pro-v1:0`
- `us.mistral.pixtral-large-2502-v1:0`
- `us.anthropic.claude-sonnet-4-20250514-v1:0`