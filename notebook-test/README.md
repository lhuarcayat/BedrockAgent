# Notebook-Test Framework

Version-controlled prompt testing framework for CECRL document extraction validation using AWS Bedrock.

## 🚀 Quick Start

```bash
# Test single document
python run.py us_passport_venezuela

# Run all tests
python run.py
```

**See [QUICK_START.md](QUICK_START.md) for detailed getting started guide.**

## 📋 Overview

This framework provides systematic testing of document extraction prompts with:

- **Real S3 Integration**: Tests with actual documents from S3 buckets
- **AWS Bedrock Integration**: Uses optimized models with S3 direct access  
- **Version-Controlled Prompts**: Compare multiple prompt versions (v2.0.0, v2.1.0, v2.2.1)
- **YAML-Only Configuration**: No code changes needed for testing different scenarios
- **Split Configuration**: Organized, maintainable configuration files
- **Multiple Interfaces**: Command-line and Jupyter notebook execution

## 🏗️ Architecture

### Current Setup (Optimized)
- **Local Development**: Region-specific models (`amazon.nova-pro-v1:0`) with S3 direct access
- **Performance**: ~40% faster than bytes-based approach  
- **Models**: Nova Pro (primary) + Claude Sonnet 4 (fallback)
- **Document Types**: Currently focuses on CECRL documents

### Test Categories
1. **Field Accuracy**: Wrong/swapped field data (nationality, names)
2. **Blank Detection**: Documents with data but model returns blank
3. **Count Validation**: Wrong count of people/entities

## 📁 File Structure

```
notebook-test/
├── run.py                    # Command-line test runner
├── QUICK_START.md           # Getting started guide
├── config/                  # Split configuration (recommended)
│   ├── README.md           # Configuration documentation
│   ├── main.yaml           # Core settings & controls
│   ├── schemas.yaml        # Document schemas for validation
│   ├── validation_rules.yaml # Test validation logic
│   ├── documents/          # Document definitions by type
│   │   ├── cecrl.yaml     #   CECRL documents
│   │   ├── cerl.yaml      #   CERL documents
│   │   ├── rut.yaml       #   RUT documents
│   │   ├── rub.yaml       #   RUB documents
│   │   └── acc.yaml       #   ACC documents
│   └── test_cases/         # Test case configurations
│       ├── field_accuracy.yaml    # Field accuracy tests
│       ├── blank_detection.yaml   # Blank detection tests
│       └── count_validation.yaml  # Count validation tests
├── test_config.yaml        # Legacy monolithic config (backup)
├── src/                    # Framework source code
│   ├── config_loader.py   # Configuration management
│   ├── test_manager.py    # Test orchestration
│   └── document_extractor.py # Bedrock integration
├── shared/                 # Shared utilities  
├── utils.py               # Test utilities
├── outputs/               # Test results
├── prompts/CECRL/         # Versioned prompts
│   ├── v2.0.0/           # Original prompts
│   ├── v2.1.0/           # Nationality fixes
│   ├── v2.2.0/           # Universal language support
│   └── v2.2.1/           # Current production prompts
├── notebook.ipynb        # Full Jupyter framework
└── test_runner_demo.ipynb # Quick demo notebook
```

## 🧪 Test Documents

### Available Test Cases

| Document Key | Description | Test Focus |
|-------------|-------------|------------|
| `us_passport_venezuela` | US passport, born in Venezuela | Nationality should be "Venezuela" (birth place) not "Estados Unidos" (issuer) |
| `colombian_cedula` | Colombian cédula with name swapping | firstName/lastName should not be swapped |
| `colombian_cedula_no_labels` | Colombian cédula without explicit labels | Should extract names without "APELLIDOS:"/"NOMBRES:" labels |

### Document Sources
- **S3 Bucket**: `par-servicios-poc-qa-filling-desk`
- **Document Types**: CECRL (Cédula de Ciudadanía, Pasaporte)
- **Test Coverage**: Nationality extraction, name field parsing, label detection

## ⚙️ Configuration

### Split Configuration (Current)
- **Benefits**: Organized files, dynamic loading, easy maintenance
- **Detection**: Automatic if `config/main.yaml` exists
- **Loading**: Only loads enabled document types and test categories

### Configuration Controls

**Enable/Disable Document Types:**
```yaml
# config/main.yaml
settings:
  CECRL: true     # Enable CECRL documents
  CERL: false     # Disable CERL documents
```

**Enable/Disable Test Categories:**
```yaml
categories:
  field_accuracy:
    enabled: true   # Test field accuracy
  blank_detection:
    enabled: false  # Skip blank detection
```

**Select Prompt Versions:**
```yaml
# config/test_cases/field_accuracy.yaml
field_accuracy_test:
  prompts_to_test: ["v2.1.0", "v2.2.1"]
```

## 🔧 Execution Methods

### 1. Command Line
```bash
# Single document test
python run.py us_passport_venezuela

# All enabled tests  
python run.py

# Show available documents
python run.py --help
```

### 2. Interactive Python
```python
from test_manager import TestManager

tm = TestManager()
tm.show_execution_plan()

# Run specific test case
results = tm.run_test_case("field_accuracy_test")

# Run all enabled tests
all_results = tm.run_all_enabled()
```

### 3. Jupyter Notebooks
- **`notebook.ipynb`**: Full framework with analysis
- **`test_runner_demo.ipynb`**: Quick demo and testing

## 📊 Output & Results

### Generated Files
```
outputs/
├── single_test_<document>.json          # Raw single test results
├── batch_results.json                   # Raw batch test results
├── comparison/
│   ├── single_report_<document>.json   # Single test comparison
│   └── comparison_report.json          # Batch comparison report
├── before/                              # v2.0.0 results by document
└── after/                               # v2.1.0 results by document
```

### Result Analysis
- **Field Changes**: Compare extracted values between prompt versions
- **Success Status**: Track which prompts succeeded/failed
- **Performance Metrics**: Execution time and token usage
- **Model Metadata**: Which models were used (primary/fallback)

## 🎯 Key Features

### Prompt Version Testing
- **v2.0.0**: Original prompts (nationality issues)
- **v2.1.0**: Fixed nationality extraction logic  
- **v2.2.0**: Universal language support (regression)
- **v2.2.1**: Current production (fixed field interpretation)

### Model Optimization
- **S3 Direct Access**: No PDF downloads, ~40% faster execution
- **Region-Specific Models**: `amazon.nova-pro-v1:0` for local development
- **Fallback Strategy**: Automatic Claude Sonnet 4 fallback if Nova fails

### Validation Framework
- **Schema-Based**: Required fields validation for blank detection
- **Expected Values**: Compare against known correct extractions
- **Count Validation**: Verify entity counting (relatedParties arrays)

## 🐛 Troubleshooting

| Issue | Solution |
|-------|----------|
| Document not found | Check spelling and document enabled in config |
| AWS credentials | Configure `par_servicios` profile |
| S3 access denied | Verify S3 read permissions for test buckets |
| No documents to test | Enable CECRL in `config/main.yaml` |
| Slow execution | Disable unused categories and document types |

## 📈 Performance

**Current Optimized Setup:**
- **Execution Time**: 6-15 seconds per document
- **Model**: Region-specific Nova Pro with S3 direct access
- **Loading**: Only enabled document types (3x faster config loading)
- **Parallel Processing**: Multiple prompt versions tested concurrently

**Optimization Benefits:**
- **vs Bytes Approach**: ~40% faster execution
- **vs Full Loading**: Only loads CECRL when CECRL enabled  
- **vs Monolithic Config**: Smaller, focused configuration files

## 🔗 Related Documentation

- **[QUICK_START.md](QUICK_START.md)**: Get started in 3 steps
- **[config/README.md](config/README.md)**: Detailed configuration guide
- **[CLAUDE.md](../CLAUDE.md)**: Project architecture and setup
- **[terraform/environments/README.md](../terraform/environments/README.md)**: AWS environment configuration

## 🏷️ Version History

- **v1.0**: Initial CECRL testing framework
- **v2.0**: Split configuration implementation  
- **v2.1**: S3 direct access optimization
- **v2.2**: Production stability with hybrid model approach

**Current Status**: Production-ready with optimized local development and stable Lambda deployment.