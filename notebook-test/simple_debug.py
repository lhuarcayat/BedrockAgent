#!/usr/bin/env python3
"""
Simple debug script to see what's in the JSON payload sent to the model
"""

import json
import sys
sys.path.append('/home/lannister-applying/projects/applying/par_servicios/poc_bedrock/notebook-test')
from run import *

# Extract the document data that would be sent to the model
def debug_document_json():
    """Show the JSON data that gets sent to the model."""
    print("=" * 60)
    print("DEBUGGING DOCUMENT JSON PAYLOAD")
    print("=" * 60)
    
    # Test the problematic document
    document_key = "colombian_cedula_no_labels"
    
    # Get the document config
    test_config = TEST_DOCUMENTS[document_key]
    print(f"Document: {test_config['name']}")
    print(f"S3 Path: {test_config['s3_path']}")
    print()
    
    try:
        # Setup AWS clients
        bedrock_client, s3_client = setup_aws_clients()
        
        # Extract PDF  
        bucket = test_config['s3_path'].replace('s3://', '').split('/')[0]
        key = '/'.join(test_config['s3_path'].replace('s3://', '').split('/')[1:])
        
        print(f"Extracting from bucket: {bucket}, key: {key}")
        
        # Get PDF bytes
        response = s3_client.get_object(Bucket=bucket, Key=key)
        pdf_bytes = response['Body'].read()
        
        print(f"PDF size: {len(pdf_bytes)} bytes")
        
        # Create the JSON document that gets sent to the model
        document_json = {
            "document_number": "test",
            "document_type": "person", 
            "category": "CECRL",
            "text": "PDF content processed by Bedrock",  # This gets replaced by Bedrock
            "path": test_config['s3_path']
        }
        
        print("JSON Document Structure:")
        print(json.dumps(document_json, indent=2))
        
        print("\n" + "=" * 60)
        print("This JSON + PDF bytes gets sent to Bedrock Nova")
        print("Nova processes the PDF and extracts text internally")
        print("=" * 60)
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    debug_document_json()