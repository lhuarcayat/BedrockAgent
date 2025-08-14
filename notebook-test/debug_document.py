#!/usr/bin/env python3
"""
Debug script to extract and display document text to understand the v2.2.0 regression
"""

import json
import sys
sys.path.append('shared')

from shared.pdf_processor import PDFProcessor

# Add notebook-test to path for config
sys.path.append('/home/lannister-applying/projects/applying/par_servicios/poc_bedrock/notebook-test')
from config import setup_aws_clients

def debug_document(s3_path):
    """Extract and display document text to understand the issue."""
    
    # Setup AWS clients
    bedrock_client, s3_client = setup_aws_clients()
    
    # Initialize PDF processor
    pdf_processor = PDFProcessor(s3_client)
    
    # Extract PDF text
    bucket = s3_path.replace('s3://', '').split('/')[0]
    key = '/'.join(s3_path.replace('s3://', '').split('/')[1:])
    
    result = pdf_processor.extract_text_from_s3(bucket, key)
    
    if result.success:
        print("=" * 60)
        print("DOCUMENT TEXT EXTRACTION")
        print("=" * 60)
        print(f"S3 Path: {s3_path}")
        print(f"Text Length: {len(result.data['text'])} characters")
        print("-" * 60)
        print("EXTRACTED TEXT:")
        print("-" * 60)
        print(result.data['text'])
        print("-" * 60)
        print("ANALYSIS:")
        print("-" * 60)
        
        text = result.data['text']
        
        # Look for APELLIDOS pattern
        if 'APELLIDOS' in text:
            lines = text.split('\n')
            for i, line in enumerate(lines):
                if 'APELLIDOS' in line:
                    print(f"Line {i+1}: {line.strip()}")
        
        # Look for NOMBRES pattern  
        if 'NOMBRES' in text:
            lines = text.split('\n')
            for i, line in enumerate(lines):
                if 'NOMBRES' in line:
                    print(f"Line {i+1}: {line.strip()}")
                    
        # Look for the specific names mentioned
        if 'HERNANDEZ' in text:
            print(f"Found 'HERNANDEZ' in text")
        if 'LUIS' in text:
            print(f"Found 'LUIS' in text")
        if 'DARIO' in text:
            print(f"Found 'DARIO' in text")
            
    else:
        print(f"Failed to extract text: {result.error}")

if __name__ == "__main__":
    # Debug the problematic document
    s3_path = "s3://par-servicios-poc-qa-filling-desk/par-servicios-poc/CECRL/900397317/80163642_2020-02-29.pdf"
    debug_document(s3_path)