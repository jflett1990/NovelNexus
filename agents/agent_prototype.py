"""
Prototype agent implementation that demonstrates how to use the model selection utility.
This can be used as a reference for updating other agents.
"""

import logging
import json
import re
import time
from datetime import datetime
from typing import Dict, Any, List, Optional, Union

from models.openai_client import get_openai_client
from models.openai_models import get_agent_model
from memory.dynamic_memory import DynamicMemory
from utils.model_utils import select_model

logger = logging.getLogger(__name__)

class AgentPrototype:
    """Base class for all agents in the system."""
    
    def __init__(
        self,
        project_id: str,
        memory,
        name: str = "agent",
        use_openai: bool = True
    ):
        """
        Initialize the agent.
        
        Args:
            project_id: Project identifier
            memory: Dynamic memory instance
            name: Agent name for logging
            use_openai: Whether to use OpenAI models
        """
        self.project_id = project_id
        self.memory = memory
        self.name = name
        self.use_openai = use_openai
        
        # Initialize clients
        self.openai_client = get_openai_client() if use_openai else None
    
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        json_format: bool = False,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        Generate text using available models.
        
        Args:
            prompt: The user prompt
            system_prompt: Optional system prompt
            temperature: Controls randomness (0-1)
            json_format: Whether to request JSON output
            conversation_history: Optional conversation history
            
        Returns:
            Dictionary with generation results
        """
        # Try OpenAI first if enabled
        if self.use_openai and self.openai_client:
            try:
                return self._generate_with_openai(prompt, system_prompt, temperature, json_format, conversation_history)
            except Exception as e:
                logger.error(f"OpenAI generation failed: {e}")
                raise Exception(f"No available AI service - OpenAI failed: {e}")
        else:
            logger.error("No available AI service (OpenAI)")
            raise Exception("No available AI service (OpenAI)")
    
    def _generate_with_openai(
        self, 
        prompt: str, 
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        json_format: bool = False,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """Generate content using OpenAI."""
        # Get the right model for this agent
        model_info = get_agent_model(self.name)
        logger.info(f"Using OpenAI model {model_info} for {self.name}")
        
        return self.openai_client.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            model=model_info,
            temperature=temperature,
            json_mode=json_format,
            conversation_history=conversation_history,
            agent_name=self.name
        )
    
    def parse_json_response(self, response: Dict[str, Any]) -> Any:
        """
        Parse JSON from response.
        
        Args:
            response: Response dictionary
            
        Returns:
            Parsed JSON object or None if parsing fails
        """
        # Get the response text
        text = response.get("text") or response.get("response", "")
        
        # If the response already has parsed_json, use it
        if "parsed_json" in response and response["parsed_json"]:
            return response["parsed_json"]
        
        # Try to parse JSON from the text
        try:
            # First try direct JSON parsing
            return json.loads(text)
        except json.JSONDecodeError:
            # Try to extract JSON from Markdown or surrounding text
            try:
                # Look for JSON in Markdown code blocks
                json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
                if json_match:
                    json_str = json_match.group(1)
                    return json.loads(json_str)
                
                # Try to find JSON object in the response
                json_match = re.search(r'({[\s\S]*})', text)
                if json_match:
                    json_str = json_match.group(1)
                    return json.loads(json_str)
            except (json.JSONDecodeError, AttributeError):
                logger.warning(f"Failed to extract JSON from response")
                return None
    
    def add_to_memory(self, text: str, metadata: Dict[str, Any] = None) -> bool:
        """
        Add content to the agent's memory.
        
        Args:
            text: Text content to add
            metadata: Optional metadata dictionary
            
        Returns:
            True if successfully added, False otherwise
        """
        metadata = metadata or {}
        metadata["agent"] = self.name
        metadata["timestamp"] = datetime.now().isoformat()
        
        try:
            self.memory.add_document(text, self.name, metadata)
            return True
        except Exception as e:
            logger.error(f"Error adding to memory: {e}")
            return False 