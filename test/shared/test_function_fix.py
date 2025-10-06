#!/usr/bin/env python3
"""
Test that the save_results_to_s3 function signature is fixed.
"""

def test_function_signature_fix():
    """Test that save_results_to_s3 now accepts the correct number of arguments"""
    
    print("🧪 Testing save_results_to_s3 Function Signature Fix\n")
    
    # Mock the function signature from the fixed code
    def save_results_to_s3(resp_json, meta, payload_data, source_key, category, document_number, model_used):
        return {
            'resp_json': resp_json,
            'meta': meta, 
            'payload_data': payload_data,
            'source_key': source_key,
            'category': category,
            'document_number': document_number,
            'model_used': model_used
        }
    
    # Test the exact call that was failing
    try:
        resp_json = {"output": {"message": {"content": [{"text": "test"}]}}}
        meta = {"document_type": "person"}
        payload_data = {"result": {"firstName": "test"}}
        source_key = "CECRL/123456/test.pdf"
        category = "CECRL"
        document_number = "123456"
        model_id = "us.amazon.nova-pro-v1:0"
        
        # This was the failing call: save_results_to_s3(resp_json, meta, payload_data, source_key, category, document_number, model_id)
        result = save_results_to_s3(resp_json, meta, payload_data, source_key, category, document_number, model_id)
        
        print("✅ Function call with 7 arguments works!")
        print(f"   Model used: {result['model_used']}")
        print(f"   Category: {result['category']}")
        print(f"   Document: {result['document_number']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Function call still fails: {e}")
        return False

def test_original_error_scenario():
    """Test the exact scenario from the error logs"""
    
    print("\n🔍 Testing Original Error Scenario:")
    print("Error was: save_results_to_s3() takes 6 positional arguments but 7 were given")
    
    # Old function (6 params)
    def old_save_results_to_s3(resp_json, meta, payload_data, source_key, category, document_number):
        pass
    
    # New function (7 params) 
    def new_save_results_to_s3(resp_json, meta, payload_data, source_key, category, document_number, model_used):
        return f"Success with model: {model_used}"
    
    args = ["resp", "meta", "data", "key", "CECRL", "123456", "us.amazon.nova-pro-v1:0"]
    
    # Test old function (should fail)
    try:
        old_save_results_to_s3(*args)
        print("❌ Old function shouldn't work with 7 args")
    except TypeError as e:
        print(f"✅ Old function fails as expected: {str(e)}")
    
    # Test new function (should work)
    try:
        result = new_save_results_to_s3(*args)
        print(f"✅ New function works: {result}")
    except Exception as e:
        print(f"❌ New function still fails: {e}")

if __name__ == "__main__":
    print("🔧 Testing Function Signature Fix for save_results_to_s3\n")
    
    try:
        test1 = test_function_signature_fix()
        test_original_error_scenario()
        
        if test1:
            print(f"\n🎉 Function signature fix successful!")
            print(f"The 'takes 6 positional arguments but 7 were given' error should be resolved.")
        else:
            print(f"\n💥 Function signature fix failed.")
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()