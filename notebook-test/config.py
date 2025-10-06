# =============================================================================
# CECRL Prompt Testing Framework
# =============================================================================
# Purpose: Test v2.0.0 vs v2.1.0 prompt changes locally using S3 + Bedrock
# Usage: Change TEST_DOCUMENTS paths below, then run each section

import boto3
import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple
from datetime import datetime
from botocore.config import Config

# Add shared modules to path
sys.path.append('shared')

# =============================================================================
# CONFIGURATION - CHANGE THESE PATHS AS NEEDED
# =============================================================================

# Test document S3 paths - MODIFY THESE AS NEEDED
TEST_DOCUMENTS = {
    "us_passport_venezuela": {
        "name": "US Passport - Venezuela Birth",
        "description": "Should fix nationality: Venezuela (not Estados Unidos)",
        "s3_path": "s3://par-servicios-poc-qa-filling-desk/par-servicios-poc/CECRL/984174004/_2022-01-06.pdf",
        "expected_fixes": {
            "nationality": "Venezuela"  # Was: "Estados Unidos"
        }
    },
    "colombian_cedula": {
        "name": "Colombian Cédula - Name Swap", 
        "description": "Should fix firstName/lastName parsing",
        "s3_path": "s3://par-servicios-poc-qa-filling-desk/par-servicios-poc/CECRL/900397317/19200964_2020-02-29.pdf",
        "expected_fixes": {
            "firstName": "Luis Ignacio",      # Was: "Hernández Díaz"
            "lastName": "Hernández Díaz"      # Was: "Luis Ignacio"
        }
    },
    "colombian_cedula_no_labels": {
        "name": "Colombian Cédula - No Explicit Labels",
        "description": "Document without explicit APELLIDOS:/NOMBRES: labels causing extraction errors",
        "s3_path": "s3://par-servicios-poc-qa-filling-desk/par-servicios-poc/CECRL/900397317/80163642_2020-02-29.pdf",
        "expected_fixes": {
            "firstName": "LUIS DARIO",          # Currently getting: "HERNANDEZ RAMIREZ"
            "lastName": "HERNANDEZ RAMIREZ"     # Currently getting: "HERNANDEZ RAMIREZ LUIS DARIO"
        }
    }
    # ADD MORE DOCUMENTS HERE AS NEEDED:
    # "new_document": {
    #     "name": "Description",
    #     "s3_path": "s3://bucket/path/file.pdf",
    #     "expected_fixes": {"field": "expected_value"}
    # }
}

# Model configuration
BEDROCK_MODEL = "us.amazon.nova-pro-v1:0"
FALLBACK_MODEL = "us.anthropic.claude-sonnet-4-20250514-v1:0"
AWS_REGION = "us-east-2"
AWS_PROFILE = "par_servicios"  # Change if different

# Output directories
OUTPUT_DIR = Path("outputs")
COMPARISON_DIR = OUTPUT_DIR / "comparison"
BEFORE_DIR = OUTPUT_DIR / "before" 
AFTER_DIR = OUTPUT_DIR / "after"

# Create output directories
for dir_path in [OUTPUT_DIR, COMPARISON_DIR, BEFORE_DIR, AFTER_DIR]:
    dir_path.mkdir(exist_ok=True)

# =============================================================================
# LOGGING SETUP
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(OUTPUT_DIR / 'test_log.txt'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# =============================================================================
# AWS CLIENTS SETUP  
# =============================================================================

def setup_aws_clients():
    """Initialize AWS clients with proper configuration."""
    try:
        # Use specified profile
        session = boto3.Session(profile_name=AWS_PROFILE)
        
        # Create clients
        bedrock_client = session.client(
            "bedrock-runtime",
            region_name=AWS_REGION,
            config=Config(
                connect_timeout=30,
                read_timeout=300
            )
        )
        
        s3_client = session.client('s3', region_name=AWS_REGION)
        
        logger.info(f"AWS clients initialized with profile: {AWS_PROFILE}, region: {AWS_REGION}")
        return bedrock_client, s3_client
        
    except Exception as e:
        logger.error(f"Failed to setup AWS clients: {e}")
        raise

print("✅ Configuration loaded")
print(f"📋 Test documents configured: {len(TEST_DOCUMENTS)}")
print(f"🎯 Model: {BEDROCK_MODEL}")
print(f"📁 Output directory: {OUTPUT_DIR}")