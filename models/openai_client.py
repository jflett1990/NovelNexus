import os
import logging
import json
from typing import Dict, Any, List, Optional, Union

from openai import OpenAI

logger = logging.getLogger(__name__)

# the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
# do not change this unless explicitly requested by the user
DEFAULT_MODEL = "gpt-4o"

class OpenAIClient:
    """Client for interacting with the OpenAI API."""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            logger.warning("OpenAI API key not found. OpenAI features will not be available.")
        
        self.client = OpenAI(api_key=self.api_key) if self.api_key else None
    
    def is_available(self) -> bool:
        """Check if the OpenAI client is available."""
        return self.client is not None
    
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: str = DEFAULT_MODEL,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        json_mode: bool = False,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        Generate text using OpenAI.
        
        Args:
            prompt: The user prompt
            system_prompt: Optional system prompt
            model: The model to use
            temperature: Controls randomness (0-1)
            max_tokens: Maximum tokens to generate
            json_mode: Whether to request JSON output
            conversation_history: Optional conversation history
            
        Returns:
            Dictionary with generation results
        """
        if not self.is_available():
            raise Exception("OpenAI client not available.")
        
        messages = []
        
        # Add system message if provided
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        # Add conversation history if provided
        if conversation_history:
            messages.extend(conversation_history)
        
        # Add the user prompt
        messages.append({"role": "user", "content": prompt})
        
        try:
            kwargs = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}
            
            response = self.client.chat.completions.create(**kwargs)
            
            content = response.choices[0].message.content
            
            return {
                "text": content,
                "parsed_json": json.loads(content) if json_mode else None,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                }
            }
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise Exception(f"OpenAI API error: {e}")
    
    def get_embeddings(
        self,
        text: Union[str, List[str]],
        model: str = "text-embedding-3-small"
    ) -> Union[List[float], List[List[float]]]:
        """
        Get embeddings for text using OpenAI.
        
        Args:
            text: The text to embed, can be a string or list of strings
            model: The embedding model to use
            
        Returns:
            List of floats (embedding vector) or list of embedding vectors
        """
        if not self.is_available():
            raise Exception("OpenAI client not available.")
        
        is_batch = isinstance(text, list)
        texts = text if is_batch else [text]
        
        try:
            response = self.client.embeddings.create(
                model=model,
                input=texts
            )
            
            embeddings = [item.embedding for item in response.data]
            return embeddings if is_batch else embeddings[0]
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise Exception(f"OpenAI API error: {e}")

# Singleton client instance
_openai_client = None

def get_openai_client() -> OpenAIClient:
    """Get the OpenAI client singleton."""
    global _openai_client
    if _openai_client is None:
        _openai_client = OpenAIClient()
    return _openai_client

def initialize_openai() -> None:
    """Initialize the OpenAI client and validate the connection."""
    client = get_openai_client()
    
    if not client.is_available():
        logger.warning("OpenAI client initialization skipped: API key not available")
        return
    
    try:
        # Test API connection with a minimal request
        result = client.get_embeddings("Test connection", model="text-embedding-3-small")
        if result and len(result) > 0:
            logger.info("OpenAI client initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize OpenAI client: {e}")
