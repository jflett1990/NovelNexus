import os
import logging
import json
import dotenv
from typing import Dict, Any, List, Optional, Union

from openai import OpenAI
from models.openai_models import AGENT_MODELS, EMBEDDING_MODEL, get_agent_model

logger = logging.getLogger(__name__)

# Update the default model to gpt-4o
DEFAULT_MODEL = "gpt-4o"

class OpenAIClient:
    """Client for interacting with the OpenAI API."""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the OpenAI client.
        
        Args:
            api_key: Optional API key. If not provided, will look in environment variables.
        """
        # Make sure environment variables are loaded
        dotenv.load_dotenv(override=True)
        
        # Get API key with explicit fallbacks
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        
        if not self.api_key:
            logger.warning("OpenAI API key not found. OpenAI features will not be available.")
            self.client = None
            self._is_available = False
            return
        
        logger.info("Initializing OpenAI client with API key")
        try:
            self.client = OpenAI(api_key=self.api_key, timeout=30.0)
            # Test with a simple API call that doesn't cost tokens
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": "Say hello"}],
                max_tokens=1
            )
            logger.info("OpenAI API key is valid")
            self._is_available = True
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {e}")
            self.client = None
            self._is_available = False

        # Load available models
        self.available_models = []
        try:
            if self._is_available:
                # We don't actually query available models since it requires additional permissions
                # Instead, we just list the models we know about
                self.available_models = [
                    "gpt-4o", "gpt-4.1", "gpt-3.5-turbo-1106", 
                    "text-embedding-3-small", "text-embedding-3-large"
                ]
                logger.info(f"OpenAI initialized with available models: {', '.join(self.available_models)}")
        except Exception as e:
            logger.warning(f"Could not retrieve OpenAI models: {e}")
    
    def is_available(self) -> bool:
        """Check if the OpenAI client is available."""
        return self._is_available
    
    def get_available_models(self) -> List[str]:
        """Get list of available models."""
        return self.available_models
    
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: str = DEFAULT_MODEL,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        json_mode: bool = False,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        agent_name: Optional[str] = None
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
            agent_name: Optional agent name to select appropriate model
            
        Returns:
            Dictionary with generation results
        """
        if not self.is_available():
            raise Exception("OpenAI client not available.")
        
        # If agent_name is provided, use the appropriate model
        if agent_name:
            model = get_agent_model(agent_name)
        
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
            
            logger.info(f"Generating with OpenAI model: {model}")
            response = self.client.chat.completions.create(**kwargs)
            
            content = response.choices[0].message.content
            
            # Structure the response
            result = {
                "text": content,
                "response": content,
                "parsed_json": json.loads(content) if json_mode else None,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                }
            }
            
            return result
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            # Try with fallback model if agent_name is provided
            if agent_name:
                fallback_model = get_agent_model(agent_name, use_fallback=True)
                if fallback_model != model:
                    logger.info(f"Trying fallback model {fallback_model} for agent {agent_name}")
                    return self.generate(
                        prompt=prompt,
                        system_prompt=system_prompt,
                        model=fallback_model,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        json_mode=json_mode,
                        conversation_history=conversation_history
                    )
            
            raise Exception(f"OpenAI API error: {e}")
    
    def get_embeddings(
        self,
        text: Union[str, List[str]],
        model: str = EMBEDDING_MODEL
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
        
        # Truncate long texts to avoid token limits
        max_text_length = 8000  # Approximate character limit
        truncated_texts = []
        for t in texts:
            if len(t) > max_text_length:
                logger.warning(f"Text too long ({len(t)} chars), truncating to {max_text_length} chars")
                truncated_texts.append(t[:max_text_length])
            else:
                truncated_texts.append(t)
        
        try:
            response = self.client.embeddings.create(
                model=model,
                input=truncated_texts
            )
            
            embeddings = [item.embedding for item in response.data]
            return embeddings if is_batch else embeddings[0]
        except Exception as e:
            logger.error(f"OpenAI API error getting embeddings: {e}")
            # Try with fallback embedding model
            if model != "text-embedding-3-small" and model == EMBEDDING_MODEL:
                logger.info(f"Trying fallback embedding model text-embedding-3-small")
                try:
                    response = self.client.embeddings.create(
                        model="text-embedding-3-small",
                        input=truncated_texts
                    )
                    embeddings = [item.embedding for item in response.data]
                    return embeddings if is_batch else embeddings[0]
                except Exception as fallback_error:
                    logger.error(f"Fallback embedding also failed: {fallback_error}")
            
            # If we can't get embeddings, return empty vectors of appropriate dimension
            # Most OpenAI embedding models use 1536 dimensions
            logger.warning("Returning zero vector as embedding placeholder")
            fallback_dimension = 1536
            zero_vectors = [[0.0] * fallback_dimension for _ in range(len(texts))]
            return zero_vectors if is_batch else zero_vectors[0]

# Reset the singleton to ensure we get a fresh instance
_openai_client = None

def get_openai_client() -> OpenAIClient:
    """Get the OpenAI client singleton."""
    global _openai_client
    if _openai_client is None:
        _openai_client = OpenAIClient()
    return _openai_client

def initialize_openai() -> None:
    """Initialize the OpenAI client and validate the connection."""
    # Force a new instance to be created
    global _openai_client
    _openai_client = None
    
    client = get_openai_client()
    
    if not client.is_available():
        logger.warning("OpenAI client initialization skipped: API key not available")
        return
    
    try:
        # Test API connection with a simple completion
        result = client.generate(
            prompt="Test connection",
            max_tokens=5
        )
        logger.info("OpenAI client initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize OpenAI client: {e}")
