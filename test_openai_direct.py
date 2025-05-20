#!/usr/bin/env python
"""Direct OpenAI API test script."""

import os
import sys
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Log the current working directory
logger.info(f"Current working directory: {os.getcwd()}")
logger.info(f".env file exists: {os.path.exists('.env')}")

# Try different dotenv loading methods
try:
    import dotenv
    logger.info("Loading environment variables with python-dotenv...")
    
    # Make sure we're using the right working directory
    env_path = os.path.join(os.getcwd(), '.env')
    logger.info(f"Full .env path: {env_path}")
    logger.info(f"Exists: {os.path.exists(env_path)}")
    
    # Load with explicit path
    result = dotenv.load_dotenv(dotenv_path=env_path, override=True, verbose=True)
    logger.info(f"dotenv.load_dotenv result: {result}")
    
    # Try another method if needed
    if not result:
        logger.info("Trying alternative method: dotenv.main.load_dotenv")
        result = dotenv.main.load_dotenv(env_path, override=True, verbose=True)
        logger.info(f"Alternative load result: {result}")
except ImportError:
    logger.error("python-dotenv not installed")
except Exception as e:
    logger.error(f"Error loading dotenv: {e}")

# Check if API key is set - NOW should be set if dotenv worked
api_key = os.environ.get("OPENAI_API_KEY")
logger.info(f"API key found: {api_key is not None}")

# If still no API key, try to read and set manually
if not api_key:
    logger.info("No API key in environment, trying to read .env manually")
    try:
        with open('.env', 'r') as f:
            for line in f:
                if line.startswith('OPENAI_API_KEY='):
                    # Extract the key and set it
                    key = line.strip().split('=', 1)[1]
                    os.environ["OPENAI_API_KEY"] = key
                    logger.info(f"Manually set API key from .env")
                    api_key = os.environ.get("OPENAI_API_KEY")
                    break
    except Exception as e:
        logger.error(f"Error reading .env manually: {e}")

if not api_key:
    logger.error("No OpenAI API key found in environment. Please set OPENAI_API_KEY.")
    sys.exit(1)

# Mask the key for logging
masked_key = f"{api_key[:8]}...{api_key[-4:]}"
logger.info(f"API key (masked): {masked_key}")

try:
    from openai import OpenAI
    
    # Initialize with explicit timeout settings
    logger.info("Initializing OpenAI client...")
    client = OpenAI(
        api_key=api_key,
        timeout=30.0  # 30 second timeout
    )
    logger.info("OpenAI client initialized")
    
    # Try a simple API call with error handling
    try:
        logger.info("Testing model list endpoint...")
        models = client.models.list(limit=5)
        logger.info(f"Available models: {', '.join([model.id for model in models.data[:5]])}")
    except Exception as model_error:
        logger.error(f"Error listing models: {model_error}")
    
    try:
        logger.info("Testing completion endpoint...")
        completion = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Say hello in one word."}
            ],
            max_tokens=10
        )
        
        logger.info(f"Response: {completion.choices[0].message.content}")
        logger.info("OpenAI API test successful!")
    except Exception as completion_error:
        logger.error(f"Error with completion: {completion_error}")
        
except Exception as e:
    logger.error(f"Error: {e}", exc_info=True)
    sys.exit(1) 