# Quick Start Guide

## 🚀 Get Started in 3 Steps

### 1. Setup Environment
```bash
# Install dependencies
mise run install

# Configure AWS (if not already done)
aws configure --profile par_servicios
```

### 2. Run a Test
```bash
# Test single document
python run.py us_passport_venezuela

# Run all enabled tests  
python run.py
```

### 3. View Results
Results are saved to `outputs/` directory. Check:
- `single_test_*.json` - Raw test data
- `comparison/single_report_*.json` - Formatted comparison

## 📋 Common Commands

```bash
# Quick test - US passport nationality fix
python run.py us_passport_venezuela

# Quick test - Colombian cédula name swapping
python run.py colombian_cedula

# Run all tests (takes ~2-3 minutes)
python run.py

# Available document keys
python run.py --help
```

## ⚙️ Quick Configuration

### Test Only CECRL Documents
Edit `config/main.yaml`:
```yaml
settings:
  CECRL: true    # ✅ Enabled
  CERL: false    # ❌ Disabled  
  RUT: false     # ❌ Disabled
  RUB: false     # ❌ Disabled
  ACC: false     # ❌ Disabled
```

### Test Specific Prompt Versions
Edit `config/test_cases/field_accuracy.yaml`:
```yaml
field_accuracy_test:
  prompts_to_test: ["v2.2.1"]  # Test only latest version
```

### Skip Slow Tests
Edit `config/main.yaml`:
```yaml
categories:
  field_accuracy:
    enabled: true    # ✅ Main test (fast)
  blank_detection:
    enabled: false   # ❌ Skip this one
  count_validation:
    enabled: false   # ❌ Skip this one
```

## 🔧 Jupyter Notebooks

### Quick Demo
1. Open `test_runner_demo.ipynb`
2. Run all cells
3. See results instantly

### Full Framework
1. Open `notebook.ipynb` 
2. Modify configuration as needed
3. Re-run cells to test changes

## 📊 What Each Test Does

| Test | Purpose | Expected Fix |
|------|---------|-------------|
| `us_passport_venezuela` | Nationality extraction | Should extract "Venezuela" from birth place, not "Estados Unidos" from issuer |
| `colombian_cedula` | Name field swapping | firstName/lastName should not be swapped |
| `colombian_cedula_no_labels` | Label-less extraction | Should extract names without explicit "APELLIDOS:" labels |

## 🎯 Expected Results

**✅ Success:** All prompt versions complete and nationality fix works  
**📋 Output:** Shows field changes between prompt versions  
**⚡ Performance:** ~6-15 seconds per document with S3 direct access

## 🐛 Quick Troubleshooting

| Error | Quick Fix |
|-------|-----------|
| "Document not found" | Check spelling: `us_passport_venezuela` not `us-passport-venezuela` |
| "AWS credentials" | Run: `aws configure --profile par_servicios` |
| "S3 access denied" | Verify AWS profile has S3 read permissions |
| "No documents to test" | Enable CECRL in `config/main.yaml` |
| Tests too slow | Disable unused categories in `config/main.yaml` |

## 💡 Pro Tips

- **Fast iteration:** Use single document testing during development
- **Focused testing:** Enable only needed document types for faster loading
- **Version comparison:** Compare prompt versions by checking field changes in output
- **Configuration:** No code changes needed - everything controlled by YAML files
- **Performance:** Split configuration loads only enabled documents (3x faster)

## 📁 File Organization

```
notebook-test/
├── run.py                    # ← Main command-line entry point
├── config/
│   ├── main.yaml            # ← Core settings (enable/disable document types)
│   ├── documents/cecrl.yaml # ← CECRL document definitions
│   └── test_cases/          # ← Test case configurations
├── outputs/                 # ← Test results go here
├── notebook.ipynb          # ← Full Jupyter framework
└── test_runner_demo.ipynb  # ← Quick demo notebook
```

Ready to test? Start with:
```bash
python run.py us_passport_venezuela
```