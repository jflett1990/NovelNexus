# OpenAI Integration for NovelNexus

This document summarizes the implementation of OpenAI models into the NovelNexus manuscript generation system.

## Summary of Changes

1. Created `models/openai_models.py` - Configuration file for OpenAI model preferences by agent
2. Updated `models/openai_client.py` - Improved OpenAI client with better error handling and fallbacks
3. Created `utils/model_utils.py` - Utility for model selection based on agent and availability
4. Modified `app.py` and `workflow.py` - Updated to use OpenAI as the primary model source
5. Updated agent files - Added support for agent-specific model selection

## Model Preferences

The system now uses dedicated OpenAI models for each agent:

| Agent | Preferred Model | Fallback Model | Notes |
|-------|----------------|---------------|-------|
| ideation | gpt-4.1 | gpt-4o | High creativity, divergent thinking |
| manuscript | gpt-4.1 | gpt-4o | Longform capability, deep stylistic fidelity |
| character | gpt-4.1 | gpt-4o | Semantic nuance, relationship mapping |
| world_building | gpt-4.1 | gpt-4o | Spatial logic, lore continuity |
| research | gpt-3.5-turbo-1106 | gpt-4o | Factual reasoning over narrative |
| outline | gpt-4.1 | gpt-3.5-turbo-1106 | Logical structure, instruction-following |
| review | gpt-4.1 | gpt-4o | Strong editing logic, tone sensitivity |
| editorial | gpt-4.1 | gpt-4o | Precision editing, clarity enforcement |
| revision | gpt-4.1 | gpt-4o | Change tracking, stylistic reflow |

## Fallback Mechanism

The system implements a robust fallback mechanism:

1. First attempts to use the preferred OpenAI model
2. If that fails, tries the fallback OpenAI model
3. If OpenAI completely fails, falls back to local Ollama models

## Configuration

To use the OpenAI integration:

1. Ensure the `.env` file contains a valid OpenAI API key:
   ```
   OPENAI_API_KEY=sk-your-api-key
   ```

2. The application is now configured to use OpenAI as the primary model source by default.

## Testing

Test scripts are provided to verify the OpenAI integration:

- `test_openai.py` - Tests the OpenAI client
- `test_openai_direct.py` - Tests direct OpenAI API calls
- `test_agent_models.py` - Tests agent-specific model selection

## Implementation Details

### Model Selection

The `utils/model_utils.py` module provides a unified approach to model selection:

```python
# Get model info based on agent name and availability
model_info = select_model(agent_name, use_openai=True)
```

This returns a dictionary with the provider and model name to use.

### OpenAI Client

The enhanced OpenAI client provides:

- Improved error handling
- Proper environment variable loading
- Fallback mechanisms
- Compatible response format with Ollama

### API Usage

For optimal results, consider:

1. Setting appropriate rate limits to avoid API throttling
2. Monitoring token usage for cost control
3. Testing with cheaper models (e.g., gpt-3.5-turbo) during development 