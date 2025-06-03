#!/usr/bin/env python
"""
Script to test the agent model selection in NovelNexus.
This will verify that each agent uses the correct OpenAI model.
"""

import os
import logging
import dotenv
import json
from typing import Dict, Any

# Load environment variables
dotenv.load_dotenv(override=True)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import agent model selection utilities
from utils.model_utils import select_model
from models.openai_models import AGENT_MODELS, get_agent_model

# Print configuration
logger.info("=== NovelNexus Agent Model Test ===")
logger.info(f"OpenAI API key available: {os.environ.get('OPENAI_API_KEY') is not None}")

# Test model selection
for agent_name in AGENT_MODELS.keys():
    # Get model info
    preferred_model = get_agent_model(agent_name)
    fallback_model = get_agent_model(agent_name, use_fallback=True)
    
    # Get full model selection
    model_info = select_model(agent_name, use_openai=True)
    fallback_info = select_model(agent_name, use_openai=True, use_fallback=True)
    ollama_info = select_model(agent_name, use_openai=False)
    
    # Print results
    logger.info(f"\nAgent: {agent_name}")
    logger.info(f"  Preferred OpenAI model: {preferred_model}")
    logger.info(f"  Fallback OpenAI model: {fallback_model}")
    logger.info(f"  Model info with select_model(): {json.dumps(model_info)}")
    logger.info(f"  Fallback info: {json.dumps(fallback_info)}")
    logger.info(f"  Ollama info: {json.dumps(ollama_info)}")

# Try to initialize the OpenAI client to verify it works
try:
    from models.openai_client import get_openai_client
    client = get_openai_client()
    logger.info(f"\nOpenAI client available: {client.is_available()}")
    
    if client.is_available():
        # Try a simple generation call
        response = client.generate(
            prompt="Say hello in one word",
            max_tokens=10,
            temperature=0.7
        )
        logger.info(f"Test generation response: {response['text']}")
except Exception as e:
    logger.error(f"Error testing OpenAI client: {e}")

logger.info("\n=== Test Complete ===") 