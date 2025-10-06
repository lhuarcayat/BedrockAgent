#!/usr/bin/env python3
"""
Test runner for POC Bedrock tests.
Runs tests with proper Python path configuration.
"""

import os
import sys
import subprocess
from pathlib import Path

def setup_python_path():
    """Set up Python path for imports."""
    base_dir = Path(__file__).parent
    python_path = [
        str(base_dir / "functions"),
        str(base_dir / "functions" / "classification" / "src"),
        str(base_dir / "functions" / "extraction-scoring" / "src"),
    ]
    
    # Add to PYTHONPATH environment variable
    existing_path = os.environ.get('PYTHONPATH', '')
    if existing_path:
        python_path.append(existing_path)
    
    os.environ['PYTHONPATH'] = ':'.join(python_path)
    print(f"Set PYTHONPATH: {os.environ['PYTHONPATH']}")

def run_command(cmd, description):
    """Run a command and return success status."""
    print(f"\n🧪 {description}")
    print(f"Running: {' '.join(cmd)}")
    print("-" * 50)
    
    try:
        result = subprocess.run(cmd, check=True, text=True, capture_output=False)
        print(f"✅ {description} - PASSED")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} - FAILED (exit code: {e.returncode})")
        return False

def main():
    """Main test runner."""
    setup_python_path()
    
    tests = [
        # Shared tests
        (["python", "test/shared/test_param_fix.py"], "Parameter Fix Test"),
        (["python", "test/shared/test_function_fix.py"], "Function Fix Test"),
        
        # Classification tests
        (["python", "test/classification/test_refactored_functions.py"], "Refactored Functions Test"),
        
        # Extraction tests
        (["python", "test/extraction/test_fallback_logic_ext.py"], "Fallback Logic Test"),
        (["python", "test/extraction/test_model_tracking.py"], "Model Tracking Test"),
    ]
    
    print("🚀 Starting POC Bedrock test suite...")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    for cmd, description in tests:
        if run_command(cmd, description):
            passed += 1
        else:
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"📊 TEST SUMMARY:")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"📋 Total:  {passed + failed}")
    
    if failed == 0:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n⚠️  {failed} test(s) failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())