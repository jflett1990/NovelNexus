#!/usr/bin/env python
"""Script to check environment variables and test different loading methods."""

import os
import sys
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info("=== Environment Variable Tests ===")

# Check direct environment variable
api_key = os.environ.get("OPENAI_API_KEY")
logger.info(f"Direct environment check: OPENAI_API_KEY exists: {api_key is not None}")

# Try loading with dotenv
try:
    import dotenv
    logger.info("Testing python-dotenv loading...")
    
    # Try different methods
    logger.info("Method 1: dotenv.load_dotenv()")
    result1 = dotenv.load_dotenv()
    logger.info(f"Result: {result1}")
    api_key1 = os.environ.get("OPENAI_API_KEY")
    logger.info(f"OPENAI_API_KEY exists: {api_key1 is not None}")
    
    logger.info("Method 2: dotenv.load_dotenv(override=True)")
    result2 = dotenv.load_dotenv(override=True)
    logger.info(f"Result: {result2}")
    api_key2 = os.environ.get("OPENAI_API_KEY")
    logger.info(f"OPENAI_API_KEY exists: {api_key2 is not None}")
    
    logger.info("Method 3: dotenv.load_dotenv(dotenv_path='.env', override=True)")
    result3 = dotenv.load_dotenv(dotenv_path='.env', override=True)
    logger.info(f"Result: {result3}")
    api_key3 = os.environ.get("OPENAI_API_KEY")
    logger.info(f"OPENAI_API_KEY exists: {api_key3 is not None}")
    
    # Check the .env file's content directly
    logger.info("Reading .env file directly...")
    try:
        with open('.env', 'r') as f:
            env_content = f.read()
            # Show first 10 chars of OPENAI_API_KEY if found
            import re
            key_match = re.search(r'OPENAI_API_KEY=([^\n%]+)', env_content)
            if key_match:
                key_value = key_match.group(1)
                logger.info(f"Found API key in .env file: {key_value[:10]}...{key_value[-4:] if len(key_value) > 4 else ''}")
                logger.info(f"Key length: {len(key_value)}")
                logger.info(f"Last 5 characters: '{key_value[-5:]}' (to check for unexpected characters)")
            else:
                logger.info("Could not find OPENAI_API_KEY in .env file")
    except Exception as e:
        logger.error(f"Error reading .env file: {e}")
        
except ImportError:
    logger.error("python-dotenv not installed")
except Exception as e:
    logger.error(f"Error with dotenv: {e}")

# Try manual environment setting for testing
try:
    logger.info("Setting environment variable manually...")
    # Set a truncated key just for testing purposes
    os.environ["OPENAI_API_KEY_TEST"] = "sk-test123456"
    test_key = os.environ.get("OPENAI_API_KEY_TEST")
    logger.info(f"Manual test key exists: {test_key is not None}")
    logger.info(f"Manual test key value: {test_key}")
except Exception as e:
    logger.error(f"Error setting manual environment variable: {e}")

logger.info("=== Test Complete ===") 