import os
import logging
import httpx
from typing import Dict, Any, Optional, List, Union

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
DEFAULT_MODEL = "deepseek-v2:16b"
EMBEDDING_MODEL = "snowflake-arctic-embed:335m"

class OllamaClient:
    """Client for interacting with the Ollama API."""
    
    def __init__(self, base_url: str = OLLAMA_BASE_URL):
        self.base_url = base_url
        self.client = httpx.Client(timeout=120.0)  # 2-minute timeout for generation
    
    def generate(
        self, 
        prompt: str, 
        model: str = DEFAULT_MODEL,
        system: Optional[str] = None,
        format: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate a completion using Ollama.
        
        Args:
            prompt: The user prompt
            model: Model name (default: deepseek-v2:16b)
            system: Optional system prompt
            format: Optional response format (e.g., "json")
            options: Additional options for the model
            
        Returns:
            Dict containing the response
        """
        url = f"{self.base_url}/api/generate"
        
        payload = {
            "model": model,
            "prompt": prompt,
        }
        
        if system:
            payload["system"] = system
        
        if format:
            payload["format"] = format
            
        if options:
            payload["options"] = options
            
        try:
            response = self.client.post(url, json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Ollama API error: {e}")
            raise Exception(f"Ollama API error: {e}")
        except Exception as e:
            logger.error(f"Error calling Ollama: {e}")
            raise Exception(f"Error calling Ollama: {e}")
    
    def get_embeddings(
        self, 
        text: Union[str, List[str]], 
        model: str = EMBEDDING_MODEL
    ) -> Union[List[float], List[List[float]]]:
        """
        Get embeddings for text using Ollama.
        
        Args:
            text: The text to embed, can be a string or list of strings
            model: Model name (default: snowflake-arctic-embed:335m)
            
        Returns:
            List of floats (embedding vector) or list of embedding vectors
        """
        url = f"{self.base_url}/api/embeddings"
        
        is_batch = isinstance(text, list)
        texts = text if is_batch else [text]
        
        all_embeddings = []
        
        for single_text in texts:
            payload = {
                "model": model,
                "prompt": single_text
            }
            
            try:
                response = self.client.post(url, json=payload)
                response.raise_for_status()
                embedding = response.json().get("embedding", [])
                all_embeddings.append(embedding)
            except httpx.HTTPStatusError as e:
                logger.error(f"Ollama API error: {e}")
                raise Exception(f"Ollama API error: {e}")
            except Exception as e:
                logger.error(f"Error calling Ollama: {e}")
                raise Exception(f"Error calling Ollama: {e}")
        
        return all_embeddings if is_batch else all_embeddings[0]
    
    def get_available_models(self) -> List[str]:
        """
        Get list of available models from Ollama.
        
        Returns:
            List of model names
        """
        url = f"{self.base_url}/api/tags"
        
        try:
            response = self.client.get(url)
            response.raise_for_status()
            models = [model["name"] for model in response.json().get("models", [])]
            return models
        except httpx.HTTPStatusError as e:
            logger.error(f"Ollama API error: {e}")
            return []
        except Exception as e:
            logger.error(f"Error calling Ollama: {e}")
            return []

# Singleton client instance
_ollama_client = None

def get_ollama_client() -> OllamaClient:
    """Get the Ollama client singleton."""
    global _ollama_client
    if _ollama_client is None:
        _ollama_client = OllamaClient()
    return _ollama_client

def initialize_ollama() -> None:
    """Initialize the Ollama client and validate the connection."""
    client = get_ollama_client()
    
    try:
        available_models = client.get_available_models()
        logger.info(f"Ollama initialized with available models: {available_models}")
        
        # Check if our required models are available
        required_models = [DEFAULT_MODEL, EMBEDDING_MODEL]
        missing_models = [model for model in required_models if model not in available_models]
        
        if missing_models:
            logger.warning(f"Required models not found in Ollama: {missing_models}")
            logger.warning("Please pull the missing models using 'ollama pull <model>'")
    except Exception as e:
        logger.warning(f"Ollama not available in this environment: {e}")
        logger.info("The application is configured to use Ollama models when run locally:")
        logger.info(f"  - Main model: {DEFAULT_MODEL}")
        logger.info(f"  - Embedding model: {EMBEDDING_MODEL}")
        logger.info("Please ensure Ollama is installed and these models are pulled when running locally.")
