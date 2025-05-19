# Project Scaffolding Plan

This document provides step-by-step instructions for creating a new project with the same structure as the reference implementation, focusing on the `functions`, `terraform`, and `terraform-bootstrap` directories.

## Table of Contents

1. [Project Structure Overview](#project-structure-overview)
2. [Step 1: Create Base Directory Structure](#step-1-create-base-directory-structure)
3. [Step 2: Set Up Lambda Functions](#step-2-set-up-lambda-functions)
4. [Step 3: Configure Terraform Core](#step-3-configure-terraform-core)
5. [Step 4: Create Terraform Modules](#step-4-create-terraform-modules)
6. [Step 5: Set Up Terraform Scripts](#step-5-set-up-terraform-scripts)
7. [Step 6: Configure Terraform Bootstrap](#step-6-configure-terraform-bootstrap)
8. [Step 7: Create Configuration Files](#step-7-create-configuration-files)
9. [Step 8: Set Up .gitignore](#step-8-set-up-gitignore)

## Project Structure Overview

```bash
project-root/
├── functions/                    # Lambda function code
│   ├── ${LAMBDA_NAME_1}/         # Each lambda in its own directory
│   └── ${LAMBDA_NAME_2}/
├── terraform/                    # Main Terraform configuration
│   ├── modules/                  # Reusable Terraform modules
│   ├── tf-scripts/               # Environment management scripts
│   ├── config/                   # Backend configuration
│   └── environments/             # Environment-specific variables
└── terraform-bootstrap/          # Initial infrastructure setup
    ├── config/                   # Bootstrap backend configuration
    └── environments/             # Bootstrap environment variables
```

## Step 1: Create Base Directory Structure

Create the following directory structure:

```bash
mkdir -p functions
mkdir -p terraform/modules/lambda-wrapper
mkdir -p terraform/tf-scripts
mkdir -p terraform/config
mkdir -p terraform/environments
mkdir -p terraform/builds
mkdir -p terraform-bootstrap/config
mkdir -p terraform-bootstrap/environments
```

## Step 2: Set Up Lambda Functions

For each Lambda function, create a directory structure as follows:

```bash
# Replace ${LAMBDA_NAME} with the actual name of your Lambda function
mkdir -p functions/${LAMBDA_NAME}/src
mkdir -p functions/${LAMBDA_NAME}/test
```

Create a README.md in each Lambda function directory:

```markdown
# ${LAMBDA_NAME} Lambda Function

## Overview
Brief description of the Lambda function's purpose.

## Structure
- `src/`: Contains the handler code
- `test/`: Contains test files

## Runtime Configuration
- Runtime: ${RUNTIME} (e.g., nodejs18.x, python3.9, etc.)
- Handler: ${HANDLER_PATH} (e.g., src/index.handler)

## Dependencies
List of dependencies required by this Lambda function.

## Deployment
Instructions for building and deploying this Lambda function.
```

## Step 3: Configure Terraform Core

Create the following core Terraform files in the `terraform/` directory:

### main.tf

```hcl
# Main Terraform configuration file
# Contains the core infrastructure resources

provider "aws" {
  region = var.region
}

# Reference to your modules
module "lambda_wrapper" {
  source = "./modules/lambda-wrapper"

  # Module parameters
  function_name = "${var.project_prefix}-${var.environment}-function"
  handler       = var.lambda_handler
  runtime       = var.lambda_runtime
  # Add other parameters as needed
}

# Other resources
# ...
```

### variables.tf

```hcl
# Input variables for the Terraform configuration

variable "region" {
  description = "AWS region to deploy resources"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Deployment environment (dev, staging, prod)"
  type        = string
}

variable "project_prefix" {
  description = "Prefix for resource names"
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9-]+$", var.project_prefix))
    error_message = "Project prefix must contain only lowercase alphanumeric characters and hyphens."
  }
}

variable "account_id" {
  description = "AWS account ID for cross-account operations"
  type        = string

  validation {
    condition     = can(regex("^\\d{12}$", var.account_id))
    error_message = "Account ID must be a 12-digit number."
  }
}

variable "lambda_runtime" {
  description = "Runtime for Lambda functions"
  type        = string
}

variable "lambda_handler" {
  description = "Handler for Lambda functions"
  type        = string
}

# Add other variables as needed
```

### outputs.tf

```hcl
# Output values from the Terraform configuration

output "api_endpoint" {
  description = "API Gateway endpoint URL"
  value       = aws_apigatewayv2_api.main.api_endpoint
}

output "lambda_function_name" {
  description = "Name of the deployed Lambda function"
  value       = module.lambda_wrapper.function_name
}

# Add other outputs as needed
```

### providers.tf

```hcl
# Provider configuration

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 4.0"
    }
  }
}
```

### versions.tf

```hcl
# Terraform version constraints

terraform {
  required_version = ">= 1.0.0"
}
```

### backend.tf

```hcl
# Backend configuration for storing Terraform state

terraform {
  backend "s3" {
    # These values will be filled by the backend config file
    # specified with -backend-config option
  }
}
```

### api.tf

```hcl
# API Gateway configuration

resource "aws_apigatewayv2_api" "main" {
  name          = "${var.project_prefix}-${var.environment}-api"
  protocol_type = "HTTP"
}

resource "aws_apigatewayv2_stage" "main" {
  api_id      = aws_apigatewayv2_api.main.id
  name        = var.environment
  auto_deploy = true
}

# API routes and integrations
# ...
```

### lambda.tf

```hcl
# Lambda function configurations

# Lambda permissions
resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = module.lambda_wrapper.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.main.execution_arn}/*/*"
}

# Additional Lambda configurations
# ...
```

## Step 4: Create Terraform Modules

Create the Lambda wrapper module files:

### terraform/modules/lambda-wrapper/main.tf

```hcl
# Lambda wrapper module main configuration

resource "aws_lambda_function" "function" {
  function_name = var.function_name
  handler       = var.handler
  runtime       = var.runtime

  role          = aws_iam_role.lambda_role.arn

  filename      = var.zip_file

  environment {
    variables = var.environment_variables
  }

  timeout     = var.timeout
  memory_size = var.memory_size
}

resource "aws_iam_role" "lambda_role" {
  name = "${var.function_name}-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

# Add IAM policies as needed
```

### terraform/modules/lambda-wrapper/variables.tf

```hcl
# Lambda wrapper module variables

variable "function_name" {
  description = "Name of the Lambda function"
  type        = string
}

variable "handler" {
  description = "Handler for the Lambda function"
  type        = string
}

variable "runtime" {
  description = "Runtime for the Lambda function"
  type        = string
}

variable "zip_file" {
  description = "Path to the Lambda deployment package"
  type        = string
}

variable "environment_variables" {
  description = "Environment variables for the Lambda function"
  type        = map(string)
  default     = {}
}

variable "timeout" {
  description = "Lambda function timeout in seconds"
  type        = number
  default     = 30
}

variable "memory_size" {
  description = "Lambda function memory size in MB"
  type        = number
  default     = 128
}
```

### terraform/modules/lambda-wrapper/outputs.tf

```hcl
# Lambda wrapper module outputs

output "function_name" {
  description = "Name of the Lambda function"
  value       = aws_lambda_function.function.function_name
}

output "function_arn" {
  description = "ARN of the Lambda function"
  value       = aws_lambda_function.function.arn
}

output "invoke_arn" {
  description = "Invoke ARN of the Lambda function"
  value       = aws_lambda_function.function.invoke_arn
}

output "role_arn" {
  description = "ARN of the Lambda execution role"
  value       = aws_iam_role.lambda_role.arn
}
```

## Step 5: Set Up Terraform Scripts

On this step, you can select on either create bash scripts or a python script.
If you choose to go with bash scripts, you have to create the following scripts in the `terraform/tf-scripts/` directory:

### script-create-temp-env.sh

```bash
#!/bin/bash
# This script asume a working dev environment
if [ $# -ne 1 ]; then
    echo "Usage: $0 <environment>"
    echo "Example: $0 dev-env"
    exit 1
fi

env=$1

# ephemeral envs are always created in the dev environment
./script-switch-env.sh dev

echo "Creating ephemeral environment $env"
cd ..
terraform workspace new $env
```

### script-plan-temp-env.sh

```bash
#!/bin/bash

if [ $# -ne 1 ]; then
    echo "Usage: $0 <environment>"
    echo "Example: $0 dev-rolando"
    exit 1
fi

env=$1

# ephemeral envs are always created in the dev environment
./script-switch-env.sh dev

echo "Planning updates to ephemeral environment $env"

cd ..
terraform workspace select $env
terraform plan -var-file=environments/dev.tfvars -var "stage_name=$env"

echo "Plan complete data for ephemeral environment $env"

terraform output > ../.env
```

### script-deploy-temp-env.sh

```bash
#!/bin/bash

if [ $# -ne 1 ]; then
    echo "Usage: $0 <environment>"
    echo "Example: $0 dev-rolando"
    exit 1
fi

env=$1

# ephemeral envs are always created in the dev environment
./script-switch-env.sh dev
cd ..
echo "Deploying updates to ephemeral environment $env"

terraform workspace select $env
terraform apply -var-file=environments/dev.tfvars -var "stage_name=$env"

echo "Seeding data for ephemeral environment $env"

terraform output > ../.env

cd ..
node seed-restaurants.mjs
```

### script-destroy-temp-env.sh

```bash
#!/bin/bash

if [ $# -ne 1 ]; then
    echo "Usage: $0 <environment>"
    echo "Example: $0 dev-rolando"
    exit 1
fi

env=$1

# ephemeral envs are always created in the dev environment
./script-switch-env.sh dev

echo "Destroying ephemeral environment $env"

cd ..
terraform workspace select $env
terraform destroy -var-file=environments/dev.tfvars -var "stage_name=$env"

terraform workspace select default
terraform workspace delete $env
```

### script-switch-env.sh

```bash
#!/bin/bash

if [ $# -ne 1 ]; then
    echo "Usage: $0 <environment>"
    echo "Example: $0 dev"
    exit 1
fi

env=$1

cd ..
if [ ! -f "config/${env}.backend.hcl" ]; then
    echo "Error: Backend config file config/${env}.backend.hcl does not exist"
    exit 1
fi

terraform init -backend-config=config/${env}.backend.hcl -reconfigure

echo "Switched to environment $env successfully"
```

If you choose python, you have to create this script in the in the `terraform/tf-scripts/` directory:

### tf_env.py

Python script handling environment configuration and validation for Terraform deployments. Provides a unified interface for:

- Environment switching
- Workspace management
- Plan/apply/destroy operations
- Environment variable generation

```python
#!/usr/bin/env python3
"""
Unified Terraform helper for ephemeral environments.
Usage examples:
    python tf_env.py switch dev
    python tf_env.py create dev-rolando
    python tf_env.py plan   dev-rolando
    python tf_env.py deploy dev-rolando
    python tf_env.py destroy dev-rolando

if you want to autoapprove or ci/cd purposes you can add the flag -y to autoapprove:
    python tf_env.py deploy -y dev-rolando
    python tf_env.py destroy -y dev-rolando
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from subprocess import run, CalledProcessError, PIPE

# ─────────────────────────── Configuration ────────────────────────────
ROOT = Path(__file__).resolve().parents[1]  # .../terraform
LOG   = logging.getLogger("tf-env")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
)

# Helper to run shell commands and bubble up failures
def sh(cmd: list[str], cwd: Path | None = None, capture: bool = False) -> str:
    """
    Run *cmd* in *cwd*.
    • When capture=False (default) the command inherits the parent console,
      so you see Terraform’s coloured output live.
    • When capture=True the output is captured and returned (used for
      `terraform output` that you want to save to .env).
    """
    LOG.debug("Running: %s", " ".join(cmd))
    try:
        if capture:
            completed = run(
                cmd,
                cwd=cwd,
                text=True,
                stdout=PIPE,
                stderr=PIPE,
                check=True,
            )
            return completed.stdout
        else:
            run(cmd, cwd=cwd, check=True)      # ↞ streams directly
            return ""
    except CalledProcessError as exc:
        LOG.error("Command failed (exit %s)", exc.returncode)
        sys.exit(exc.returncode)

# ───────────────────────── Terraform wrappers ─────────────────────────
def switch_env(env: str):
    backend_file = ROOT / f"config/{env}.backend.hcl"
    if not backend_file.exists():
        LOG.error("Backend config %s not found", backend_file)
        sys.exit(1)
    sh(["terraform", "init", f"-backend-config={backend_file}", "-reconfigure"], cwd=ROOT)
    LOG.info("Switched to environment %s successfully", env)

def create_env(env: str):
    switch_env("dev")
    sh(["terraform", "workspace", "new", env], cwd=ROOT)
    LOG.info("Created workspace %s", env)

def plan_env(env: str):
    switch_env("dev")
    sh(["terraform", "workspace", "select", env], cwd=ROOT)
    sh([
        "terraform", "plan",
        "-var-file=environments/dev.tfvars",
        f"-var=stage_name={env}"
    ], cwd=ROOT)
    (ROOT / ".env").write_text(sh(["terraform", "output", "-json"], cwd=ROOT, capture=True))
    LOG.info("Plan complete for %s (outputs written to .env)", env)

def deploy_env(env: str, auto_approve: bool = False):
    switch_env("dev")
    sh(["terraform", "workspace", "select", env], cwd=ROOT)
    cmd = ["terraform",
            "apply",
            "-var-file=environments/dev.tfvars",
            f"-var=stage_name={env}"]
    if auto_approve:
        cmd.append("-auto-approve")
    sh(cmd, cwd=ROOT)

    # ---- 1️⃣ capture outputs as JSON  ---------------------------------
    outputs_json = sh(["terraform", "output", "-json"], cwd=ROOT, capture=True)

    # ---- 2️⃣ convert to KEY=val lines (dotenv-friendly) ---------------
    outputs = json.loads(outputs_json)
    lines = [f"{k}={v['value']}" for k, v in outputs.items()]

    # ---- 3️⃣ write to *project-root*/.env exactly like the Bash script
    env_file = ROOT.parent / ".env"
    if not env_file.exists():
        LOG.error(".env file not found at %s – aborting seed", env_file)
        sys.exit(1)
    (env_file).write_text("\n".join(lines) + "\n")

    LOG.info("Deploy succeeded for %s – seeding data", env)
    sh(["node", "seed-restaurants.mjs"], cwd=ROOT.parent)

def destroy_env(env: str, auto_approve: bool = False):
    switch_env("dev")
    sh(["terraform", "workspace", "select", env], cwd=ROOT)
    cmd = ["terraform",
            "destroy",
            "-var-file=environments/dev.tfvars",
            f"-var=stage_name={env}"]
    if auto_approve:
        # Running as a PyInstaller executable
        cmd.append("-auto-approve")
    sh(cmd, cwd=ROOT)
    sh(["terraform", "workspace", "select", "default"], cwd=ROOT)
    sh(["terraform", "workspace", "delete", env], cwd=ROOT)
    LOG.info("Environment %s destroyed and workspace removed", env)

# ────────────────────────────── CLI glue ──────────────────────────────
def build_cli() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="tf_env", description="Terraform env helper")
    sub = p.add_subparsers(dest="cmd", required=True)
    p.add_argument("-y", "--auto-approve",
              action="store_true",
              help="Skip prompts (passes -auto-approve to apply/destroy)")
    for action in ("switch", "create", "plan", "deploy", "destroy"):
        s = sub.add_parser(action)
        s.add_argument("env", help="Environment name (e.g. dev-rolando)")
    return p

def main():
    args = build_cli().parse_args()
    fn = {
        "switch":  switch_env,
        "create":  create_env,
        "plan":    plan_env,
        "deploy":  deploy_env,
        "destroy": destroy_env,
    }[args.cmd]
    if args.cmd in ("deploy", "destroy"):
        fn(args.env, auto_approve=args.auto_approve)
    else:
        fn(args.env)

if __name__ == "__main__":
    main()
```

## Step 6: Configure Terraform Bootstrap

Create the following files in the `terraform-bootstrap/` directory:

### bootstrap.tf

```hcl
# Bootstrap Terraform configuration

provider "aws" {
  region = var.region
}

# S3 bucket for Terraform state
resource "aws_s3_bucket" "terraform_state" {
  bucket = "${var.project_prefix}-${var.environment}-terraform-state"

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_versioning" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id

  versioning_configuration {
    status = "Enabled"
  }
}

# DynamoDB table for state locking
resource "aws_dynamodb_table" "terraform_locks" {
  name         = "${var.project_prefix}-${var.environment}-terraform-locks"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"

  attribute {
    name = "LockID"
    type = "S"
  }
}

# Outputs
output "s3_bucket_name" {
  value = aws_s3_bucket.terraform_state.bucket
}

output "dynamodb_table_name" {
  value = aws_dynamodb_table.terraform_locks.name
}
```

### variables.tf

```hcl
# Bootstrap variables

variable "region" {
  description = "AWS region to deploy resources"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Deployment environment (dev, staging, prod)"
  type        = string
}

variable "project_prefix" {
  description = "Prefix for resource names"
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9-]+$", var.project_prefix))
    error_message = "Project prefix must contain only lowercase alphanumeric characters and hyphens."
  }
}

variable "account_id" {
  description = "AWS account ID for cross-account operations"
  type        = string

  validation {
    condition     = can(regex("^\\d{12}$", var.account_id))
    error_message = "Account ID must be a 12-digit number."
  }
}
```

### providers.tf

```hcl
# Provider configuration for bootstrap

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 4.0"
    }
  }

  required_version = ">= 1.0.0"
}
```

### backend.tf

```hcl
# Backend configuration for bootstrap
# Initially, this will use local state
# After the first apply, you can migrate to S3

terraform {
  backend "local" {
    path = "terraform.tfstate"
  }

  # Uncomment after first apply and update with actual values
  # backend "s3" {
  #   # These values will be filled by the backend config file
  # }
}
```

## Step 7: Create Configuration Files

Create the following configuration files:

### terraform-bootstrap/environments/dev.tfvars.example

```hcl
environment     = "dev"
region          = "us-east-1"
project_prefix  = "your-project"
account_id      = "123456789012"  # AWS account ID for cross-account operations
```

### terraform-bootstrap/environments/prod.tfvars.example

```hcl
environment     = "prod"
region          = "us-east-1"
project_prefix  = "your-project"
account_id      = "123456789012"  # AWS account ID for cross-account operations
```

### terraform/config/dev.backend.hcl.example

```hcl
bucket          = "your-project-dev-terraform-state"
key             = "terraform/dev/state"
region          = "us-east-1"
dynamodb_table  = "your-project-dev-terraform-locks"
encrypt         = true
role_arn        = "arn:aws:iam::ACCOUNT_ID:role/TerraformRole"  # Optional: For cross-account access
```

### terraform/config/prod.backend.hcl.example

```hcl
bucket          = "your-project-prod-terraform-state"
key             = "terraform/prod/state"
region          = "us-east-1"
dynamodb_table  = "your-project-prod-terraform-locks"
encrypt         = true
role_arn        = "arn:aws:iam::ACCOUNT_ID:role/TerraformRole"  # Optional: For cross-account access
```

### terraform/environments/dev.tfvars.example

```hcl
environment     = "dev"
region          = "us-east-1"
project_prefix  = "your-project"
lambda_runtime  = "nodejs18.x"
lambda_handler  = "index.handler"
account_id      = "123456789012"  # AWS account ID for cross-account operations
# Add other variables as needed
```

### terraform/environments/prod.tfvars.example

```hcl
environment     = "prod"
region          = "us-east-1"
project_prefix  = "your-project"
lambda_runtime  = "nodejs18.x"
lambda_handler  = "index.handler"
account_id      = "123456789012"  # AWS account ID for cross-account operations
# Add other variables as needed
```

### terraform-bootstrap/config/dev.backend.hcl.example

```hcl
bucket          = "your-project-bootstrap-dev-terraform-state"
key             = "terraform-bootstrap/dev/state"
region          = "us-east-1"
dynamodb_table  = "your-project-bootstrap-dev-terraform-locks"
encrypt         = true
role_arn        = "arn:aws:iam::ACCOUNT_ID:role/TerraformRole"  # Optional: For cross-account access
```

### terraform-bootstrap/config/prod.backend.hcl.example

```hcl
bucket          = "your-project-bootstrap-prod-terraform-state"
key             = "terraform-bootstrap/prod/state"
region          = "us-east-1"
dynamodb_table  = "your-project-bootstrap-prod-terraform-locks"
encrypt         = true
role_arn        = "arn:aws:iam::ACCOUNT_ID:role/TerraformRole"  # Optional: For cross-account access
```

## Step 8: Set Up .gitignore

Create a `.gitignore` file in the project root:

```
# Terraform
**/.terraform/*
*.tfstate
*.tfstate.*
*.tfplan
*.tfvars
!*.tfvars.example
.terraform.lock.hcl

# Backend configs
**/config/*.backend.hcl
!**/config/*.backend.hcl.example

# Lambda build artifacts
**/builds/*
**/node_modules/*
**/.serverless/*

# IDE files
.vscode/
.idea/
*.swp
*.swo

# OS files
.DS_Store
Thumbs.db
```

## Variable Usage Examples

This section demonstrates how the variables defined in the configuration files are used throughout the Terraform code.

### Project Prefix Usage

The `project_prefix` variable is used to create consistent resource naming across your infrastructure:

```hcl
# In terraform/main.tf
module "lambda_wrapper" {
  function_name = "${var.project_prefix}-${var.environment}-function"
  # ...
}

# In terraform/api.tf
resource "aws_apigatewayv2_api" "main" {
  name = "${var.project_prefix}-${var.environment}-api"
  # ...
}

# In terraform-bootstrap/bootstrap.tf
resource "aws_s3_bucket" "terraform_state" {
  bucket = "${var.project_prefix}-${var.environment}-terraform-state"
  # ...
}
```

### Lambda Configuration Usage

The Lambda runtime and handler variables are used in the Lambda wrapper module:

```hcl
# In terraform/main.tf
module "lambda_wrapper" {
  source = "./modules/lambda-wrapper"

  function_name = "${var.project_prefix}-${var.environment}-function"
  handler       = var.lambda_handler
  runtime       = var.lambda_runtime
  # ...
}

# In terraform/modules/lambda-wrapper/main.tf
resource "aws_lambda_function" "function" {
  function_name = var.function_name
  handler       = var.handler
  runtime       = var.runtime
  # ...
}
```

### Account ID Usage

The `account_id` variable is used for cross-account operations and resource policies:

```hcl
# In terraform/main.tf
provider "aws" {
  region = var.region
  assume_role {
    role_arn = "arn:aws:iam::${var.account_id}:role/TerraformExecutionRole"
  }
}

# In IAM policies for cross-account access
resource "aws_iam_policy" "lambda_policy" {
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action   = "s3:GetObject"
        Effect   = "Allow"
        Resource = "arn:aws:s3:::${var.project_prefix}-${var.environment}-bucket/*"
        Condition = {
          StringEquals = {
            "aws:SourceAccount" = var.account_id
          }
        }
      }
    ]
  })
}
```

### Backend Configuration Usage

The backend configuration parameters are used when initializing Terraform:

```bash
# Command line usage
terraform init -backend-config=config/dev.backend.hcl

# The backend.hcl file provides these values to the S3 backend in terraform/backend.tf
terraform {
  backend "s3" {
    # Values from backend.hcl:
    # - bucket
    # - key
    # - region
    # - dynamodb_table
    # - encrypt
    # - role_arn (optional)
  }
}
```

## Usage Instructions

1. **Initialize the Project**:

   ```bash
   # Clone this repository or create the directory structure as outlined
   mkdir my-new-project
   cd my-new-project
   # Follow the steps above to create the directory structure and files
   ```

2. **Bootstrap the Infrastructure**:

   ```bash
   cd terraform-bootstrap
   cp config/dev.backend.hcl.example config/dev.backend.hcl
   # Edit config/dev.backend.hcl with your values
   terraform init
   terraform apply -var-file=environments/dev.tfvars
   ```

3. **Configure the Main Terraform**:

   ```bash
   cd ../terraform
   cp config/dev.backend.hcl.example config/dev.backend.hcl
   cp environments/dev.tfvars.example environments/dev.tfvars
   # Edit config/dev.backend.hcl and environments/dev.tfvars with your values
   ```

4. **Create Lambda Functions**:

   ```bash
   # For each Lambda function
   mkdir -p functions/my-lambda-function/src
   # Add your Lambda code to the src directory
   ```

5. **Deploy the Infrastructure**:

   ```bash
   cd terraform
   ./tf-scripts/script-create-temp-env.sh dev
   ./tf-scripts/script-plan-temp-env.sh dev
   ./tf-scripts/script-deploy-temp-env.sh dev
   ```

6. **Clean Up**:

   ```bash
   cd terraform
   ./tf-scripts/script-destroy-temp-env.sh dev
   ```

Remember to replace placeholder values like `your-project`, `${LAMBDA_NAME}`, etc., with your actual project-specific values.
