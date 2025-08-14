# CECRL Prompt Testing Framework

## 🎯 Purpose

Test CECRL extraction prompt changes (v2.0.0 → v2.1.0) to validate fixes for:

1. **Nationality Logic**: Should use place of birth, not document issuer country
2. **Name Field Parsing**: Colombian documents should respect APELLIDOS/NOMBRES labels

## 🏗️ Architecture

- **No Downloads**: Uses S3 → Bedrock pattern (same as Lambda functions)  
- **Full PDF Processing**: Bedrock processes complete document (all pages)
- **Version Controlled Prompts**: Clear v2.0.0 vs v2.1.0 comparison
- **Structured Output**: JSON results + comparison reports

## 📁 Files

```
notebook-test/
├── config.py                 # Configuration & AWS setup (CHANGE DOCUMENTS HERE)
├── utils.py                  # S3, prompts, Bedrock utilities  
├── engine.py                 # Core testing logic
├── run.py                    # Main execution script (RUN THIS)
├── notebook.ipynb            # Jupyter notebook interface
├── prompts/
│   ├── v2.0.0/               # Original prompts
│   └── v2.1.0/               # Fixed prompts
├── shared/                   # Lambda function utilities
└── outputs/                  # Test results
    ├── comparison/           # Comparison reports
    ├── before/               # v2.0.0 results  
    └── after/                # v2.1.0 results
```

## 🚀 Quick Start

### Option 1: Command Line
```bash
cd notebook-test

# Run all tests
python run.py

# Test single document  
python run.py us_passport_venezuela
python run.py colombian_cedula
```

### Option 2: Jupyter Notebook
```bash
jupyter notebook notebook.ipynb
# Then run cells sequentially
```

### Option 3: Interactive Python
```python
from run import *

# Quick test first document
quick_test()

# Show configured documents
list_documents()

# Run complete suite
run_all_tests()
```

## 📋 Test Documents

### Currently Configured:

1. **us_passport_venezuela**
   - S3: `s3://par-servicios-poc-qa-filling-desk/par-servicios-poc/CECRL/984174004/_2022-01-06.pdf`
   - Fix: nationality should be "Venezuela" (not "Estados Unidos")

2. **colombian_cedula** 
   - S3: `s3://par-servicios-poc-qa-filling-desk/par-servicios-poc/CECRL/900397317/19200964_2020-02-29.pdf`
   - Fix: firstName="Luis Ignacio", lastName="Hernández Díaz" (was swapped)

### Adding New Documents:

Edit `TEST_DOCUMENTS` in `config.py`:

```python
TEST_DOCUMENTS["new_doc"] = {
    "name": "Document Name",
    "description": "What should be fixed", 
    "s3_path": "s3://bucket/path/file.pdf",
    "expected_fixes": {"field": "expected_value"}
}
```

## 📊 Output Files

- **`outputs/comparison_report.json`** - Main comparison report
- **`outputs/batch_results.json`** - Raw test results  
- **`outputs/before/`** - v2.0.0 extraction results
- **`outputs/after/`** - v2.1.0 extraction results
- **`outputs/test_log.txt`** - Execution logs

## 🔧 Configuration

### AWS Settings (modify in `config.py`):
```python
AWS_PROFILE = "par_servicios"  
AWS_REGION = "us-east-2"
BEDROCK_MODEL = "us.amazon.nova-pro-v1:0"
```

### S3 Paths:
Change document paths in `TEST_DOCUMENTS` as needed.

## 📈 Expected Results

### US Passport Test:
```json
{
  "nationality": {
    "old_value": "Estados Unidos",
    "new_value": "Venezuela",  
    "changed": true
  }
}
```

### Colombian Cédula Test:
```json
{
  "firstName": {
    "old_value": "Hernández Díaz",
    "new_value": "Luis Ignacio",
    "changed": true
  },
  "lastName": {
    "old_value": "Luis Ignacio", 
    "new_value": "Hernández Díaz",
    "changed": true
  }
}
```

## 🐛 Troubleshooting

- **AWS Credentials**: Ensure `par_servicios` profile exists in `~/.aws/credentials`
- **S3 Access**: Verify access to `par-servicios-poc-qa-filling-desk` bucket
- **Bedrock Access**: Ensure Bedrock permissions in `us-east-2` region
- **Missing Files**: Run from `notebook-test/` directory

## 🔄 Workflow

1. **Modify** document paths in configuration if needed
2. **Run tests** using any method above  
3. **Check** `outputs/comparison_report.json` for results
4. **Validate** fixes match expected changes
5. **Deploy** new prompts to production if tests pass

## 📝 Notes

- Tests use same S3 → Bedrock pattern as production Lambda functions
- No local PDF downloads - all processing via Bedrock API
- Full document processing (all pages) during extraction
- Version headers track prompt changes for future reference