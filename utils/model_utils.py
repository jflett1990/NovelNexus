# Model selection utilities for NovelNexus
import logging
from typing import Dict, Any, Optional
from models.openai_models import get_agent_model

logger = logging.getLogger(__name__)

def select_model(agent_name: str, use_openai: bool, use_fallback: bool = False) -> Dict[str, Any]:
    """
    Select the appropriate model for an agent based on configuration.
    
    Args:
        agent_name: Name of the agent
        use_openai: Whether to use OpenAI (True) or Ollama (False)
        use_fallback: Whether to use fallback models if available
        
    Returns:
        Dictionary with model information
    """
    model_info = {}
    
    # Always use OpenAI regardless of use_openai parameter
    # Get the OpenAI model for this agent
    model_name = get_agent_model(agent_name, use_fallback)
    logger.info(f"Selected OpenAI model for {agent_name}: {model_name}")
    model_info["provider"] = "openai"
    model_info["model"] = model_name
    
    return model_info
