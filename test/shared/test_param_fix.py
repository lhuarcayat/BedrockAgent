#!/usr/bin/env python3
"""
Test the parameter recalculation fix for model switching.
"""

import sys
sys.path.append('functions/shared')

def test_param_recalculation():
    """Test that parameters are correctly recalculated when model changes"""
    
    from bedrock_client import set_model_params
    
    print("🧪 Testing Parameter Recalculation Fix\n")
    
    # Simulate initial request params (built for Nova)
    initial_model = "us.amazon.nova-pro-v1:0"
    initial_params = set_model_params(initial_model, 8192, 0.9, 0.1)
    
    req_params = {
        "model_id": initial_model,
        "messages": [],
        "params": initial_params,
        "system": []
    }
    
    print("Initial request (Nova):")
    print(f"  Model: {req_params['model_id']}")
    print(f"  Params: {req_params['params']}")
    
    # Simulate model switch to Mistral (the problematic case)
    new_model = "us.mistral.pixtral-large-2502-v1:0"
    
    # Apply our fix logic
    req_params["model_id"] = new_model
    
    # Recalculate params for this specific model (different models need different param formats)
    original_params = req_params.get("params", {})
    max_tokens = original_params.get("maxTokens") or original_params.get("max_tokens", 8192)
    top_p = original_params.get("topP") or original_params.get("top_p", 0.9)
    temperature = original_params.get("temperature", 0.1)
    
    # Get correct parameter format for this model
    req_params["params"] = set_model_params(new_model, max_tokens, top_p, temperature)
    
    print("\nAfter model switch (Mistral):")
    print(f"  Model: {req_params['model_id']}")
    print(f"  Params: {req_params['params']}")
    
    # Verify the fix
    mistral_params = req_params["params"]
    expected_keys = ["max_tokens", "top_p", "temperature"]
    actual_keys = list(mistral_params.keys())
    
    print(f"\nVerification:")
    print(f"  Expected keys: {expected_keys}")
    print(f"  Actual keys: {actual_keys}")
    
    # Check values
    print(f"  max_tokens: {mistral_params.get('max_tokens')} (expected: 8192)")
    print(f"  top_p: {mistral_params.get('top_p')} (expected: 0.9)")
    print(f"  temperature: {mistral_params.get('temperature')} (expected: 0.1)")
    
    # Check for wrong format
    wrong_keys = ["maxTokens", "topP"]
    has_wrong_keys = any(key in mistral_params for key in wrong_keys)
    
    if has_wrong_keys:
        print("❌ Still has camelCase keys - fix didn't work!")
        return False
    elif set(actual_keys) == set(expected_keys):
        print("✅ Parameter recalculation fix works correctly!")
        return True
    else:
        print(f"❌ Keys don't match. Missing: {set(expected_keys) - set(actual_keys)}")
        return False

def test_reverse_case():
    """Test switching from Mistral to Nova"""
    
    from bedrock_client import set_model_params
    
    print("\n🔄 Testing Reverse Case (Mistral → Nova):\n")
    
    # Start with Mistral params
    initial_model = "us.mistral.pixtral-large-2502-v1:0"
    initial_params = set_model_params(initial_model, 4096, 0.8, 0.2)
    
    req_params = {
        "model_id": initial_model,
        "params": initial_params,
    }
    
    print("Initial request (Mistral):")
    print(f"  Model: {req_params['model_id']}")
    print(f"  Params: {req_params['params']}")
    
    # Switch to Nova
    new_model = "us.amazon.nova-pro-v1:0"
    req_params["model_id"] = new_model
    
    # Apply fix logic
    original_params = req_params.get("params", {})
    max_tokens = original_params.get("maxTokens") or original_params.get("max_tokens", 4096)
    top_p = original_params.get("topP") or original_params.get("top_p", 0.8)
    temperature = original_params.get("temperature", 0.2)
    
    req_params["params"] = set_model_params(new_model, max_tokens, top_p, temperature)
    
    print("\nAfter model switch (Nova):")
    print(f"  Model: {req_params['model_id']}")
    print(f"  Params: {req_params['params']}")
    
    # Verify Nova gets camelCase
    nova_params = req_params["params"]
    expected_keys = ["maxTokens", "topP", "temperature"]
    actual_keys = list(nova_params.keys())
    
    success = set(actual_keys) == set(expected_keys)
    status = "✅" if success else "❌"
    print(f"{status} Nova parameters: {success}")
    
    return success

if __name__ == "__main__":
    try:
        test1 = test_param_recalculation()
        test2 = test_reverse_case()
        
        if test1 and test2:
            print("\n🎉 All tests passed! The parameter fix should resolve the Mistral validation error.")
        else:
            print("\n💥 Some tests failed. Need to investigate further.")
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()