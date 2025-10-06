#!/usr/bin/env python3
"""
Debug Mistral Pixtral parameter handling to fix the ValidationException.
"""

import json
import sys
import os
sys.path.append('functions/shared')

def debug_mistral_params():
    """Debug what parameters Mistral models receive"""
    
    # Import the functions we're testing
    from bedrock_client import set_model_params, NovaRequest
    
    print("🔧 Debugging Mistral Pixtral Parameter Handling\n")
    
    # Test model ID
    mistral_model = "us.mistral.pixtral-large-2502-v1:0"
    
    # Test parameters
    max_tokens = 8192
    top_p = 0.9
    temperature = 0.1
    
    print(f"Model: {mistral_model}")
    print(f"Input params: max_tokens={max_tokens}, top_p={top_p}, temperature={temperature}")
    
    # Test set_model_params
    params = set_model_params(mistral_model, max_tokens, top_p, temperature)
    print(f"\nset_model_params() output:")
    print(json.dumps(params, indent=2))
    
    # Test NovaRequest creation
    req = NovaRequest(
        model_id=mistral_model,
        messages=[{"role": "user", "content": [{"text": "test"}]}],
        params=params,
        system=[{"text": "test system"}]
    )
    
    # Test payload creation (simulate converse_with_nova logic)
    payload = {
        "modelId": req.model_id,
        "messages": req.messages,
    }
    
    # Provider routing logic
    if ".meta." in req.model_id or ".anthropic." in req.model_id or ".mistral." in req.model_id:
        payload["additionalModelRequestFields"] = req.params
        routing = "additionalModelRequestFields"
    else:
        payload["inferenceConfig"] = req.params
        routing = "inferenceConfig"
    
    if req.system:
        payload["system"] = req.system
    
    print(f"\nConverse API payload:")
    print(f"Parameters routed to: {routing}")
    print(json.dumps(payload, indent=2))
    
    # Check for issues
    issues = []
    if routing == "additionalModelRequestFields":
        expected_keys = ["max_tokens", "top_p", "temperature"]
        actual_keys = list(req.params.keys())
        for key in expected_keys:
            if key not in actual_keys:
                issues.append(f"Missing expected key: {key}")
        for key in actual_keys:
            if key not in expected_keys:
                issues.append(f"Unexpected key: {key}")
    
    if issues:
        print(f"\n❌ Issues found:")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print(f"\n✅ Parameters look correct for Mistral!")
    
    return payload

def compare_with_nova():
    """Compare with Nova parameters to see the difference"""
    
    from bedrock_client import set_model_params
    
    print(f"\n📊 Comparing parameter formats:\n")
    
    models = [
        "us.amazon.nova-pro-v1:0",
        "us.mistral.pixtral-large-2502-v1:0", 
        "us.anthropic.claude-sonnet-4-20250514-v1:0"
    ]
    
    for model in models:
        params = set_model_params(model, 8192, 0.9, 0.1)
        routing = "inferenceConfig" if "amazon.nova" in model else "additionalModelRequestFields"
        print(f"{model}:")
        print(f"  Routing: {routing}")
        print(f"  Params: {params}")
        print()

if __name__ == "__main__":
    try:
        payload = debug_mistral_params()
        compare_with_nova()
        
        print("🧪 Test Summary:")
        print("1. Check if Mistral receives correct parameter names (max_tokens, top_p)")
        print("2. Check if parameters go to additionalModelRequestFields") 
        print("3. Compare with working Nova model parameters")
        print("\n💡 If this debug shows correct parameters but Lambda still fails,")
        print("   the issue might be in the actual Bedrock API call or message format.")
        
    except Exception as e:
        print(f"❌ Debug failed: {e}")
        import traceback
        traceback.print_exc()