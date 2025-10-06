# PAR Servicios POC - Bedrock Document Processing System

A serverless document processing system using AWS services and Amazon Bedrock for AI-powered document classification and data extraction. The system processes 5 types of documents: CERL, CECRL, RUT, RUB, and ACC.

## Architecture Overview

- **Lambda Functions**: Classification, extraction-scoring, and fallback processing
- **AI Models**: Amazon Bedrock (Nova Pro + Claude Sonnet fallback)
- **Storage**: S3 buckets for input/output documents and results
- **Queuing**: SQS for reliable message processing
- **Database**: DynamoDB for idempotency and manual review tracking
- **Infrastructure**: Terraform for deployment automation

## Prerequisites

### Option 1: mise + uv (Recommended)

- [mise](https://mise.jdx.dev/) - Development environment manager
- Python 3.12 (managed by mise)
- uv package manager (managed by mise)
- AWS CLI configured with appropriate credentials

### Option 2: conda (Windows/Alternative)

- [Anaconda](https://www.anaconda.com/) or [Miniconda](https://docs.conda.io/en/latest/miniconda.html)
- Python 3.12
- AWS CLI configured with appropriate credentials

## Development Setup

### Using mise + uv (Linux/macOS)

1. **Install mise** (if not already installed):

   ```bash
   curl https://mise.jdx.dev/install.sh | sh
   ```

2. **Clone and setup the project**:

   ```bash
   git clone <repository-url>
   cd poc_bedrock

   # Install Python 3.12 and uv
   mise install

   # Install dependencies and setup terraform compatibility
   mise run install
   # or using the alias:
   mise run i
   ```

3. **Verify setup**:

   ```bash
   # Check Python version
   python --version  # Should show Python 3.12.x

   # Check that both uv and pip are available
   uv --version
   python -m pip --version
   ```

### Using conda (Windows/Alternative)

1. **Create conda environment**:

   ```bash
   conda create -n par-servicios python=3.12
   conda activate par-servicios
   ```

2. **Install dependencies**:

   ```bash
   # Install pip in conda environment (required for terraform-aws-lambda)
   conda install pip

   # Install project dependencies
   pip install -r requirements.txt
   ```

3. **Verify setup**:

   ```bash
   # Ensure both conda and pip are working
   python --version
   python -m pip --version
   conda list
   ```

### Why Both Package Managers?

This project uses **uv** for development (faster, better dependency resolution) but requires **standard pip** for terraform-aws-lambda compatibility during deployment. The `mise run install` command automatically ensures both are available.

**For conda users**: You need both conda and pip because terraform-aws-lambda specifically looks for `python -m pip` during Lambda packaging.

## Deployment

### Environment Configuration

The project supports multiple environments (dev, qa, prod) with workspace-based deployments:

```bash
cd terraform

# Switch to desired environment
python tf-scripts/tf_env.py switch qa

# Create new workspace (optional)
python tf-scripts/tf_env.py create qa-your-name

# Deploy infrastructure
python tf-scripts/tf_env.py deploy qa-your-name

# Destroy when done (optional)
python tf-scripts/tf_env.py destroy qa-your-name
```

### Available Commands

- `python tf_env.py switch <env>` - Switch to environment configuration
- `python tf_env.py create <env>` - Create new Terraform workspace
- `python tf_env.py plan <env>` - Plan infrastructure changes
- `python tf_env.py deploy <env>` - Deploy infrastructure
- `python tf_env.py destroy <env>` - Destroy infrastructure
- Add `-y` flag for auto-approval: `python tf_env.py deploy -y <env>`

### Deployment Requirements

- **AWS Credentials**: Configured via AWS CLI or environment variables
- **Terraform**: Installed and accessible in PATH
- **Python Environment**: Either mise+uv or conda with pip available
- **Permissions**: AWS IAM permissions for Lambda, S3, SQS, DynamoDB, and Bedrock

## Troubleshooting

### Common Issues

#### 1. "No module named pip" during deployment

**Issue**: terraform-aws-lambda can't find pip module

``` Bash
python3.12: No module named pip
```

**Solution for mise users**:

```bash
# This should already be handled by mise run install, but if needed:
python -m ensurepip --upgrade
```

**Solution for conda users**:

```bash
# Make sure pip is installed in your conda environment
conda install pip
# or
python -m ensurepip --upgrade
```

#### 2. Windows Path Issues

**Issue**: terraform-aws-lambda has trouble with Windows paths

**Solutions**:

- **Option A**: Use WSL2 (Windows Subsystem for Linux)
- **Option B**: Use Docker for Lambda packaging:

  ```hcl
  # Add to terraform configuration
  docker_build_args = { "--platform" = "linux/amd64" }
  ```

- **Option C**: Use conda with proper PATH setup

#### 3. Package Installation Conflicts

**Issue**: Conflicts between conda/pip/uv package installations

**Solutions**:

- Keep development and deployment package managers separate
- Use virtual environments consistently
- For conda: Install development packages via conda, let terraform use pip for Lambda packaging

### Development vs Deployment Environments

| Environment | Development | Lambda Packaging |
|-------------|-------------|------------------|
| **mise+uv** | `uv pip install` | `python -m pip install` |
| **conda** | `conda install` | `python -m pip install` |

Both approaches work, but terraform-aws-lambda always requires standard pip for Lambda packaging.

## Project Structure

```Bash
poc_bedrock/
├── functions/                  # Lambda function source code
│   ├── classification/         # Document classification Lambda
│   ├── extraction-scoring/     # Data extraction Lambda
│   ├── fallback-processing/    # Failed processing Lambda
│   └── shared/                 # Shared utilities and models
├── terraform/                  # Infrastructure as code
│   ├── modules/lambda-wrapper/ # Reusable Lambda module
│   ├── tf-scripts/            # Deployment automation
│   └── environments/          # Environment configurations
├── test/                      # Development tests
├── notebook-test/             # CECRL prompt testing framework
├── documentation/             # Technical documentation
└── CLAUDE.md                  # Development guidelines
```

## Testing

### Lambda Function Tests

```bash
# Individual function tests
cd test/classification && python test_lambda.py
cd test/extraction && python test_lambda_ext.py
cd test/fallback && python test_fallback_lambda.py

# All tests
cd test && python run_tests.py
```

### CECRL Prompt Testing

```bash
cd notebook-test

# Test specific document
python run.py <document_key>

# Test all documents
python -c "from run import run_all_tests; run_all_tests()"
```

## Contributing

1. Follow the development guidelines in `CLAUDE.md`
2. Test changes locally before deployment
3. Use environment-specific workspaces for testing
4. Update documentation for any architectural changes

## Environment Variables

Key environment variables used by Lambda functions:

- `S3_ORIGIN_BUCKET` - Source documents bucket
- `DESTINATION_BUCKET` - Processed results bucket
- `EXTRACTION_SQS` - SQS queue for extraction pipeline
- `FALLBACK_SQS` - SQS queue for failed processing
- `BEDROCK_MODEL` - Primary AI model identifier
- `FALLBACK_MODEL` - Secondary AI model identifier
- `MANUAL_REVIEW_TABLE` - DynamoDB table for failed cases

These are automatically configured by Terraform during deployment.
