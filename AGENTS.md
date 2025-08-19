# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Python Environment

- **Setup:** `mise install` - Installs Python 3.12 and uv package manager
- **Install dependencies:** `mise run install` (alias: `mise run i`) - Installs from requirements.txt using uv AND ensures pip compatibility for terraform-aws-lambda
- **Add dependencies:** `mise run dep` - Installs specific packages (PyPDF2, pydantic, python-dotenv)
- **Freeze dependencies:** `mise run freeze` - Updates requirements.txt with current installed packages

### Package Manager Compatibility

This project uses **uv** for development and **pip** for Lambda packaging:

- **Development**: `uv pip install` (faster, better dependency resolution)
- **Lambda Packaging**: `python -m pip install` (required by terraform-aws-lambda)

**Key Points:**

- The `mise run install` task automatically installs both uv and standard pip
- This ensures terraform-aws-lambda can package Lambda functions with dependencies
- No manual intervention needed - the setup handles compatibility automatically

**Alternative Environments:**

- **conda users**: Must install pip in conda environment (`conda install pip`)
- **Windows users**: Consider WSL2 for better terraform-aws-lambda compatibility
- **Docker option**: Use Docker-based packaging for cross-platform reliability

### Terraform Infrastructure

Use the unified Terraform helper script `terraform/tf-scripts/tf_env.py`:

- **Switch environment:** `python tf_env.py switch dev`
- **Create new workspace:** `python tf_env.py create dev-rolando`
- **Plan infrastructure:** `python tf_env.py plan dev-rolando`
- **Deploy infrastructure:** `python tf_env.py deploy dev-rolando`
- **Destroy infrastructure:** `python tf_env.py destroy dev-rolando`
- **Auto-approve mode:** Add `-y` flag (e.g., `python tf_env.py deploy -y dev-rolando`)

### Testing

- **Lambda function tests:** Located in `functions/*/src/test_*.py`
- **Development tests:** Located in `test/` directory (excluded from Lambda deployments)
- **Test organization:** `test/classification/`, `test/extraction/`, `test/fallback/`, `test/shared/`
- **Run specific tests:**
  - Classification: `cd test/classification && python test_lambda.py`
  - Extraction: `cd test/extraction && python test_lambda_ext.py`
  - Fallback: `cd test/fallback && python test_fallback_lambda.py`
- **Run all tests:** `cd test && python run_tests.py`

### CECRL Prompt Testing Framework

- **Location:** `notebook-test/` directory
- **Purpose:** Version-controlled prompt testing with S3 document validation
- **Test specific document:** `python run.py <document_key>`
- **Test all documents:** `python -c "from run import run_all_tests; run_all_tests()"`
- **Configuration:** Modify `TEST_DOCUMENTS` in `notebook-test/config.py`
- **Prompt versions:** Stored in `notebook-test/prompts/v2.x.x/`
- **Results:** Saved to `notebook-test/outputs/` with comparison reports

## Architecture Overview

### High-Level Structure

This is a **serverless document processing system** using AWS services and Amazon Bedrock for AI-powered document classification and data extraction. The system processes 5 types of documents: CERL, CECRL, RUT, RUB, and ACC.

### Key Components

**Lambda Functions:**

- `functions/classification/` - Classifies uploaded PDF documents using Bedrock models
- `functions/extraction-scoring/` - Extracts structured data from classified documents
- `functions/fallback-processing/` - Processes failed extractions for manual review tracking
- `functions/shared/` - Shared utilities including Bedrock client, PDF processing, and models

**Infrastructure (Terraform):**

- `terraform/main.tf` - Primary infrastructure: S3 buckets, Lambda functions, SQS queues, DynamoDB tables
- `terraform/modules/lambda-wrapper/` - Reusable Lambda deployment module
- `terraform/modules/s3/` - S3 bucket configuration module
- Environment-specific configs in `terraform/config/` and `terraform/environments/`

**DynamoDB Tables:**

- `idempotency_table` - Atomic locking for exactly-once processing (SQS deduplication)
- `manual_review_table` - Failed extraction tracking for manual review and debugging

**Documentation & Research:**

- `notebook/` - Jupyter notebooks for model testing and prompt engineering
- `notebook-test/` - Version-controlled CECRL prompt testing framework with S3 validation
- `documentation/` - Technical and operational documentation
- `test/` - Development tests and validation scripts (excluded from Lambda ZIP)
- `checkpoints/` - Development checkpoints, debug files, and implementation history

### Data Flow

1. PDFs uploaded to S3 trigger classification Lambda via SQS batching
2. Classification uses DynamoDB atomic locking for exactly-once processing
3. Successful classifications sent to SQS extraction queue
4. Extraction-scoring Lambda processes queue messages with inline model fallback
5. Successful extractions stored in destination S3 bucket
6. Failed extractions (both models failed) sent to fallback SQS queue
7. Fallback-processing Lambda stores failed cases in DynamoDB for manual review

### Environment Configuration

- **Project prefix:** `par-servicios-poc`
- **Environments:** dev, qa (configured via tfvars)
- **AWS Region:** us-east-2 (Ohio)
- **Bedrock Models (Production - Cross-Region Inference Profiles):**
  - Primary: `us.amazon.nova-pro-v1:0` (supports on-demand throughput, uses bytes approach)
  - Fallback: `us.anthropic.claude-sonnet-4-20250514-v1:0` (supports on-demand throughput, uses bytes approach)
- **Development/Testing Models (Local Environment Only):**
  - Primary: `amazon.nova-pro-v1:0` (works with S3 direct access locally)
  - Fallback: `anthropic.claude-sonnet-4-20250514-v1:0` (works with S3 direct access locally)

### Key Files to Understand

**Core Logic:**

- `functions/shared/bedrock_client.py` - Bedrock API client and response parsing
- `functions/shared/pdf_processor.py` - PDF text extraction and image handling
- `functions/shared/models.py` - Pydantic models for structured data
- `functions/shared/prompts.py` - System and user prompts for AI models
- `functions/shared/processing_result.py` - Result Pattern utilities and S3 persistence

**Configuration:**

- `mise.toml` - Development environment and task definitions
- `requirements.txt` - Python dependencies
- `terraform/locals.tf` - Terraform local values and computed configurations

### Document Processing Types

Each document type (CERL, CECRL, RUT, RUB, ACC) has:

- Specific extraction schemas in `functions/shared/evaluation_type/`
- Tailored prompts in `functions/*/src/instructions/`
- Example outputs in notebook experiments

**CECRL Prompt Versions:**

- **v2.0.0** - Original prompts (nationality vs place of birth issues, name swapping)
- **v2.1.0** - Fixed nationality logic to use place of birth
- **v2.2.0** - Universal language support with pattern detection (regression introduced)
- **v2.2.1** - Fixed field label interpretation, clearer extraction logic (current production)

### Development Practices

- **SOLID Principles:** Both classification and extraction Lambdas follow SOLID architecture
- **Result Pattern:** Explicit success/failure handling via ProcessingResult namedtuple
- **Model Fallback:** Automatic fallback between primary and secondary Bedrock models
- **S3 Persistence:** Comprehensive error and success tracking with model metadata
- **Clean Architecture:** Organized code sections with single-responsibility functions
- Environment variables for configuration (loaded via `shared.helper.load_env()`)
- All Lambda functions follow the same structure: handler.py → index.py → shared modules
- Terraform modules provide reusable infrastructure patterns
- Extensive prompt engineering documented in notebook/ directory
- **Version-controlled prompt testing:** Use `notebook-test/` framework before deploying prompt changes
- "Always plan how to tackle the task before change any code."

### Key Architectural Patterns

- **Hybrid S3 Access Pattern:** S3 direct access in development, bytes approach in production
- **Cross-Region Inference Profiles:** Production uses `us.*` model IDs for on-demand throughput compatibility
- **Parameter Handling:** Automatic format conversion for different Bedrock models (Nova/Claude/Mistral)
- **API Routing:** Converse API for all models with provider-specific parameter placement
- **Exception Separation:** Parse errors vs S3 save errors handled independently
- **Fallback-First Processing:** When classification uses fallback, extraction tries fallback first
- **SQS Batch Processing:** Optimized Lambda invocations via message batching (3-second windows)
- **DynamoDB Atomic Locking:** Exactly-once processing guarantees using conditional writes
- **Environment-Specific Models:** Region-specific models for local testing, inference profiles for production

### Manual Review System

**DynamoDB Schema (manual_review_table):**

```Bash
Main Table:
  PK: FAILED#{category}                           # "FAILED#CERL"
  SK: {YYYY#MM#DD}#{document_number}#{timestamp}  # "2024#12#15#890915475#1734285600"

GSI (DocumentIndex):
  GSI1PK: DOC#{document_number}     # "DOC#890915475"
  GSI1SK: {category}#{YYYY#MM#DD}   # "CERL#2024#12#15"
```

**Query Patterns:**

- **By category**: `PK = "FAILED#CERL"`
- **By category + date**: `PK = "FAILED#CERL" AND SK begins_with "2024#12#15"`
- **By document number**: `GSI1PK = "DOC#890915475"`

**Stored Data:**

- S3 path, bucket, key information
- Error messages and types (mapped to classification patterns)
- Models attempted (primary + fallback)
- Document metadata (number, category)
- Full SQS payload for debugging
- 90-day TTL for automatic cleanup

**Error Types Tracked:**

- `content_filtered` - Model safety systems blocked content
- `parse_error` - Failed to parse model response as valid JSON
- `model_error` - Model request failed or returned error

## Recent Changes & Fixes

### CECRL Extraction Improvements (2025-08-12)

**Issues Fixed:**

1. **Nationality vs Place of Birth Confusion** - Fixed prompts to use place of birth for nationality field instead of document issuer country
2. **firstName/lastName Field Swapping** - Fixed Colombian documents where name fields were incorrectly mapped
3. **v2.2.0 Regression** - Fixed field label misinterpretation where model confused "APELLIDOS:" and "NOMBRES:" labels

**Production Status:**

- **Current Version:** v2.2.1 CECRL extraction prompts
- **Testing Framework:** `notebook-test/` directory with version-controlled prompts
- **Validation:** All test documents pass with correct field mappings

**Key Test Documents:**

- Colombian Cédula with explicit labels: `s3://par-servicios-poc-qa-filling-desk/par-servicios-poc/CECRL/900397317/19200964_2020-02-29.pdf`
- Colombian Cédula without explicit labels: `s3://par-servicios-poc-qa-filling-desk/par-servicios-poc/CECRL/900397317/80163642_2020-02-29.pdf`
- US Passport with Venezuela birth: `s3://par-servicios-poc-qa-filling-desk/par-servicios-poc/CECRL/984174004/_2022-01-06.pdf`

## Common Deployment Issues & Solutions

### "No module named pip" during terraform deployment

**Error:**

```bash
python3.12: No module named pip
subprocess.CalledProcessError: Command '['python3.12', '-m', 'pip', 'install'...
```

**Root Cause:** terraform-aws-lambda requires standard pip module, but mise+uv or conda environments may not have it installed.

**Solutions:**

**For mise users:**

- Should be automatically handled by `mise run install`
- If still occurs: `python -m ensurepip --upgrade`

**For conda users:**

- `conda install pip`
- Or: `python -m ensurepip --upgrade`

**For Windows users:**

- Use WSL2 for better compatibility
- Or ensure conda environment has pip: `conda install pip python=3.12`

### Lambda Dependencies Not Installing

**Symptoms:** Lambda ZIP files are small (~100KB instead of ~2-7MB) and runtime shows import errors.

**Root Cause:** Missing `pip_requirements = true` in Lambda module configuration.

**Solution:** Ensure all Lambda modules in `terraform/main.tf` have:

```hcl
module "classification_lambda" {
  source = "./modules/lambda-wrapper"
  # ... other config ...
  pip_requirements = true  # This line is required
}
```

### Windows Path Issues with terraform-aws-lambda

**Symptoms:** Path-related errors during Lambda packaging on Windows.

**Solutions:**

1. **WSL2 (Recommended):** Use Windows Subsystem for Linux
2. **Docker packaging:** Add Docker build args to Lambda config
3. **Conda with proper PATH:** Ensure conda environment is properly activated

### Package Manager Conflicts

**Issue:** Conflicts between development packages (uv/conda) and deployment packaging (pip).

**Best Practices:**

- Keep development and deployment package managers separate
- Use virtual environments consistently
- Let terraform-aws-lambda use its own pip installation process
- Don't manually install packages in both uv and pip simultaneously

### Debug Lambda Packaging Issues

**Enable debug logging:**

```bash
export TF_LAMBDA_PACKAGE_LOG_LEVEL=DEBUG2
terraform plan  # Will show detailed packaging logs
```

**Check build artifacts:**

```bash
# Examine build plans and ZIP contents
ls terraform/builds/
unzip -l terraform/builds/<hash>.zip | head -20
```

### Development Environment Setup Verification

**Quick verification script:**

```bash
# Verify all components are working
python --version          # Should show 3.12.x
uv --version             # Should show uv version
python -m pip --version  # Should show pip version
mise run install         # Should complete without errors
```

**If any component fails:**

1. Run `mise doctor` to check mise setup
2. Run `mise install` to reinstall tools
3. Run `python -m ensurepip --upgrade` if pip is missing
