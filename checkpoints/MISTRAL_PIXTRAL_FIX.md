# Mistral Pixtral ValidationException Fix

## Problem Identified ❌

**Error:** `ValidationException: The model returned the following errors: "Extra inputs are not permitted" for maxTokens, topP`

**Root Cause:** Parameter format mismatch when switching models in extraction Lambda.

```python
# BROKEN CODE - What was happening:
req_params = {
    "model_id": "us.amazon.nova-pro-v1:0",          # Initially Nova  
    "params": {"maxTokens": 8192, "topP": 0.9}     # Nova format (camelCase)
}

# Later when switching to Mistral:
req_params["model_id"] = "us.mistral.pixtral-large-2502-v1:0"  # Change model
# BUT params still contain Nova format! ❌
# Mistral expects: {"max_tokens": 8192, "top_p": 0.9}
```

## Solution Applied ✅

**Fixed in:** `functions/extraction-scoring/src/index.py:168-178`

```python
# FIXED CODE - Parameter recalculation:
def process_document_with_model(...):
    try:
        # Update model ID and recalculate parameters for the specific model
        req_params["model_id"] = model_id
        
        # Recalculate params for this specific model (different models need different param formats)
        original_params = req_params.get("params", {})
        max_tokens = original_params.get("maxTokens") or original_params.get("max_tokens", 8192)
        top_p = original_params.get("topP") or original_params.get("top_p", 0.9)
        temperature = original_params.get("temperature", 0.1)
        
        # Get correct parameter format for this model
        req_params["params"] = set_model_params(model_id, max_tokens, top_p, temperature)
```

## How It Works 🔧

1. **Extract Values:** Safely get parameter values from either camelCase or snake_case
2. **Recalculate Format:** Call `set_model_params()` with the correct model_id
3. **Apply Routing:** Converse API automatically routes to correct location:
   - **Nova:** `inferenceConfig: {"maxTokens": 8192, "topP": 0.9}`
   - **Mistral:** `additionalModelRequestFields: {"max_tokens": 8192, "top_p": 0.9}`

## Testing Results ✅

```bash
🧪 Testing Parameter Recalculation Fix

Initial request (Nova):
  Model: us.amazon.nova-pro-v1:0
  Params: {'maxTokens': 8192, 'topP': 0.9, 'temperature': 0.1}

After model switch (Mistral):
  Model: us.mistral.pixtral-large-2502-v1:0
  Params: {'max_tokens': 8192, 'top_p': 0.9, 'temperature': 0.1}

✅ Parameter recalculation fix works correctly!
✅ Nova parameters: True
🎉 All tests passed!
```

## Why Classification Lambda Wasn't Affected ✅

Classification Lambda uses a different approach:
```python
# Classification builds NovaRequest directly - no parameter reuse
req_params = NovaRequest(
    model_id=model_id,  # Correct model from start
    messages=messages,
    params=cfg_params,  # Calculated for this specific model
    system=system_parameter
)
```

## Impact 🎯

- ✅ **Mistral Pixtral models** now work correctly in extraction Lambda
- ✅ **Fallback-first logic** works with Mistral models  
- ✅ **Parameter consistency** across all model types
- ✅ **No breaking changes** to existing functionality

## Follow-up Actions

1. **Test with real documents** to ensure Mistral extractions work
2. **Monitor logs** for any other parameter-related issues
3. **Consider** applying similar fix if other Lambdas have model switching logic