#!/usr/bin/env python
"""Test script to debug OpenAI API connection."""

import os
import logging
import dotenv
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
logger.info("Loading environment variables...")
dotenv.load_dotenv()

# Check if API key is set
api_key = os.environ.get("OPENAI_API_KEY")
logger.info(f"API key found: {api_key is not None}")
if api_key:
    # We'll show just the first and last few characters for security
    masked_key = f"{api_key[:8]}...{api_key[-4:]}"
    logger.info(f"API key (masked): {masked_key}")

# Try to initialize OpenAI client directly
try:
    from openai import OpenAI
    client = OpenAI(api_key=api_key)
    logger.info("OpenAI client initialized directly")
    
    # Try a simple API call
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": "Say hello"}],
        max_tokens=10
    )
    
    logger.info(f"OpenAI API response: {response.choices[0].message.content}")
    logger.info("OpenAI API call successful!")
except Exception as e:
    logger.error(f"Error with direct OpenAI API call: {e}")

# Try to initialize our OpenAI client
try:
    from models.openai_client import get_openai_client, initialize_openai
    
    # Print the current value of the openai_client singleton
    logger.info("Testing OpenAI client singleton...")
    from models.openai_client import _openai_client
    logger.info(f"Current _openai_client value: {_openai_client}")
    
    # Get a fresh client and check availability
    openai_client = get_openai_client()
    logger.info(f"Is client available: {openai_client.is_available()}")
    logger.info(f"API key in client: {openai_client.api_key is not None}")
    
    # Try to initialize
    logger.info("Initializing OpenAI client...")
    initialize_openai()
    
except Exception as e:
    logger.error(f"Error with our OpenAI client: {e}")

logger.info("OpenAI test completed.") 