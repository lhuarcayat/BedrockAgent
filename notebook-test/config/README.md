# Document-Centric Configuration

## 🎯 Simple, Clear Structure

Each document defines its **own test problem, expected results, and prompt versions** in one place:

```yaml
# config/documents/cecrl.yaml
documents:
  us_passport_venezuela:
    name: "US Passport Venezuela Birth"
    s3_path: "s3://bucket/passport.pdf"
    test_type: "field_accuracy"
    enabled: true
    
    test_config:
      prompts_to_test: ["v2.0.0", "v2.1.0", "v2.2.1"]
      description: "Nationality should be birth place not issuer country"
      
      expected_results:
        nationality: "Venezuela"        # CORRECT: Birth place
        firstName: "Dirk Elric"
        
      issue_result:
        nationality: "Estados Unidos"   # WRONG: Gets issuer instead
        firstName: "Dirk Elric"
```

## Benefits

### ✅ **Everything in One Place**
- Document location + test expectations + prompt versions
- No hunting across multiple files
- Clear what each document tests

### ✅ **Flexible Prompt Testing**
Different documents can test different prompt versions:
```yaml
us_passport_venezuela:
  prompts_to_test: ["v2.0.0", "v2.1.0", "v2.2.1"]  # Test nationality fix
  
colombian_cedula_name_swap:
  prompts_to_test: ["v2.2.0", "v2.2.1"]            # Test name swap fix
```

### ✅ **Clear Problem Definition**
Each document shows:
- **What problem** it tests (`description`)
- **What should happen** (`expected_results`)
- **What goes wrong** (`issue_result`)

## Document Types & Test Problems

### Field Accuracy Tests
**Problem**: Wrong or swapped field values
```yaml
new_document:
  test_type: "field_accuracy"
  test_config:
    expected_results:
      firstName: "John"           # Should extract this
      lastName: "Doe"
    issue_result:
      firstName: "Doe"            # But gets this (swapped)
      lastName: "John"
```

### Blank Detection Tests  
**Problem**: Document has data but model returns blank
```yaml
blank_document:
  test_type: "blank_detection"
  test_config:
    expected_behavior: "extract_data"  # Should extract fields
    actual_behavior: "blank"           # But returns empty
```

### Count Validation Tests
**Problem**: Wrong count of entities/people
```yaml
count_document:
  test_type: "count_validation"
  test_config:
    expected_count: 5              # Should find 5 people
    actual_count: 3                # But finds only 3
    count_field: "relatedParties"
```

## Adding New Documents

Simply add to the appropriate document file:

```yaml
# config/documents/cecrl.yaml
documents:
  new_passport_test:
    name: "New Passport Test Case"
    s3_path: "s3://bucket/new-passport.pdf"
    test_type: "field_accuracy"
    enabled: true
    
    test_config:
      prompts_to_test: ["v2.2.1"]  # Test only latest
      description: "Tests specific field extraction issue"
      
      expected_results:
        someField: "correct_value"
        
      issue_result:
        someField: "wrong_value"
```

**That's it!** The framework automatically:
- Loads the document 
- Generates the appropriate test case
- Runs the specified prompt versions
- Compares results against expectations

## How to Execute Tests

### Command Line
```bash
# Test single document
python run.py us_passport_venezuela

# Run all tests
python run.py
```

### Interactive Python
```python
from test_manager import TestManager

tm = TestManager()
results = tm.run_test_case("field_accuracy_test")
```

### Jupyter Notebooks
- **`notebook.ipynb`**: Full framework with analysis
- **`test_runner_demo.ipynb`**: Quick demo

## Current Configuration

**File Structure:**
```
config/
├── README.md           # This file
└── documents/
    ├── cecrl.yaml     # CECRL document definitions
    ├── cerl.yaml      # CERL document definitions  
    ├── rut.yaml       # RUT document definitions
    ├── rub.yaml       # RUB document definitions
    └── acc.yaml       # ACC document definitions
```

**Settings (built-in):**
- AWS Profile: `par_servicios`
- AWS Region: `us-east-2`
- Model: `amazon.nova-pro-v1:0` (optimized S3 direct access)
- Fallback: `us.anthropic.claude-sonnet-4-20250514-v1:0`

## Document Types & Examples

### CECRL (Foreign Identity Documents)
- `us_passport_venezuela` - Nationality extraction issue (birth place vs issuer)
- `colombian_cedula_name_swap` - Name field swapping issue  
- `colombian_cedula_no_labels` - Label-less extraction issue

### CERL (Colombian Identity Documents)
- `colombian_cedula_basic` - Basic Colombian cédula extraction
- `colombian_cedula_special_chars` - Special characters (ñ, ü, accents)
- `foreign_resident_card` - Foreign resident in Colombia nationality issue

### RUT (Colombian Tax Registry)
- `rut_empresa_basica` - Basic company registration
- `rut_persona_natural` - Individual person registration
- `rut_multiple_activities` - Multiple economic activities count validation

### RUB (Colombian Beneficial Ownership)
- `rub_sociedad_anonima` - Corporate structure with beneficial owners
- `rub_beneficiarios_extranjeros` - Foreign beneficial owners
- `rub_estructura_compleja` - Complex nested ownership structures

### ACC (Colombian Corporate Governance)
- `acc_junta_directiva` - Board of directors member counting
- `acc_accionistas_mayoritarios` - Major shareholders identification
- `acc_cambios_control` - Corporate control changes and transactions

## Adding New Document Types

The framework automatically loads any `.yaml` files in the `config/documents/` directory. Each document type has its own file with specific test cases that reflect real-world extraction challenges.

## Migration from Legacy

**Old (confusing):** Multiple files with split definitions
**New (simple):** One file per document type with everything together

No migration needed - the framework only uses the new document-centric approach.

## Performance Benefits

- **Dynamic Loading**: Only loads documents that exist
- **Focused Configuration**: Small, targeted files
- **No Legacy Complexity**: Clean, single approach
- **Fast Startup**: Minimal configuration parsing

**Example**: CECRL file is only 104 lines vs 287 in old monolithic config