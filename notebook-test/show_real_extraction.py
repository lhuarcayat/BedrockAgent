#!/usr/bin/env python3
"""Show real extraction data from Bedrock"""

from src.document_extractor import DocumentExtractor
import logging

logging.basicConfig(level=logging.INFO)

def show_extraction_example():
    """Show one real extraction example"""
    
    print("🔍 Testing real Bedrock extraction...")
    
    try:
        extractor = DocumentExtractor()
        
        # Test with US passport (Venezuela birth) document
        result = extractor.extract_from_document(
            s3_path="s3://par-servicios-poc-qa-filling-desk/par-servicios-poc/CECRL/984174004/_2022-01-06.pdf",
            prompt_version="v2.2.1",
            document_type="CECRL",
            model_id="us.amazon.nova-pro-v1:0"
        )
        
        print(f"\n📊 Extraction Result:")
        print(f"Status: {result.get('status')}")
        
        if result.get('status') == 'success':
            data = result.get('extracted_data', {})
            print(f"\n🎯 Extracted Fields:")
            for field, value in data.items():
                print(f"  {field}: {value}")
            
            print(f"\n📈 Expected vs Actual (for validation):")
            print(f"  Expected nationality: Venezuela (birth place)")
            print(f"  Actual nationality: {data.get('nationality', 'NOT_FOUND')}")
            
            print(f"\n  Expected firstName: RICARDO")
            print(f"  Actual firstName: {data.get('firstName', 'NOT_FOUND')}")
            
            print(f"\n  Expected lastName: EIKE")
            print(f"  Actual lastName: {data.get('lastName', 'NOT_FOUND')}")
            
        else:
            print(f"❌ Error: {result.get('error')}")
        
        return result
        
    except Exception as e:
        print(f"❌ Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    show_extraction_example()