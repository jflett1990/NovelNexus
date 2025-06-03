"""
Base agent implementation that all agents should inherit from.
Provides common functionality and required interface.
"""

import logging
import json
import re
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Any, List, Optional, Union

from models.openai_client import get_openai_client
from models.openai_models import get_agent_model
from memory.dynamic_memory import DynamicMemory
from utils.model_utils import select_model

logger = logging.getLogger(__name__)

class AbstractAgent(ABC):
    """
    Base abstract class for all agents in the system.
    All agent classes should inherit from this class.
    """
    
    def __init__(
        self,
        project_id: str,
        memory: DynamicMemory,
        use_openai: bool = True,
        name: Optional[str] = None,
        stage: Optional[str] = None
    ):
        """
        Initialize the agent.
        
        Args:
            project_id: Project identifier
            memory: Dynamic memory instance
            use_openai: Whether to use OpenAI models
            name: Agent name (defaults to class name in lowercase)
            stage: Pipeline stage name (defaults to name without "_agent")
        """
        self.project_id = project_id
        self.memory = memory
        self.use_openai = use_openai
        
        # Set agent name (default to class name if not provided)
        self.name = name if name else self.__class__.__name__.lower()
        
        # Set stage name (default to agent name without "_agent")
        self.stage = stage if stage else self.name.replace("_agent", "")
        
        # Initialize clients
        self.openai_client = get_openai_client() if use_openai else None
    
    @abstractmethod
    def execute(self, **kwargs) -> Dict[str, Any]:
        """
        Main execution method that all agents must implement.
        This is the primary entry point for running the agent.
        
        Args:
            **kwargs: Agent-specific parameters
            
        Returns:
            Dictionary with execution results
        """
        pass
    
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        json_format: bool = False,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        max_retries: int = 3,
        retry_delay: int = 2
    ) -> Dict[str, Any]:
        """
        Generate text using available models.
        
        Args:
            prompt: The user prompt
            system_prompt: Optional system prompt
            temperature: Controls randomness (0-1)
            json_format: Whether to request JSON output
            conversation_history: Optional conversation history
            max_retries: Maximum number of retry attempts
            retry_delay: Delay between retries in seconds
            
        Returns:
            Dictionary with generation results
        """
        for attempt in range(max_retries):
            try:
                # Try OpenAI if enabled
                if self.use_openai and self.openai_client:
                    return self._generate_with_openai(prompt, system_prompt, temperature, json_format, conversation_history)
                else:
                    logger.error(f"No available AI service (OpenAI disabled)")
                    raise Exception("No available AI service (OpenAI disabled)")
            except Exception as e:
                logger.warning(f"Generation attempt {attempt+1} failed: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                else:
                    logger.error(f"All generation attempts failed: {str(e)}")
                    raise Exception(f"Failed to generate content after {max_retries} attempts: {str(e)}")
    
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
    
    def add_to_memory(
        self, 
        text: str, 
        metadata: Optional[Dict[str, Any]] = None, 
        doc_id: Optional[str] = None
    ) -> Optional[str]:
        """
        Add content to the agent's memory.
        
        Args:
            text: Text content to add
            metadata: Optional metadata dictionary
            doc_id: Optional document ID
            
        Returns:
            Document ID if successfully added, None otherwise
        """
        metadata = metadata or {}
        metadata["agent"] = self.name
        metadata["timestamp"] = datetime.now().isoformat()
        
        try:
            return self.memory.add_document(text, self.name, metadata, doc_id)
        except Exception as e:
            logger.error(f"Error adding to memory: {e}")
            return None
            
    def get_memory(self, query: str, top_k: int = 5, threshold: float = 0.7) -> List[Dict[str, Any]]:
        """
        Query the agent's memory.
        
        Args:
            query: Search query
            top_k: Maximum number of results
            threshold: Similarity threshold (0-1)
            
        Returns:
            List of matching documents
        """
        try:
            return self.memory.query_memory(query, self.name, top_k, threshold)
        except Exception as e:
            logger.error(f"Error querying memory: {e}")
            return []
            
    def get_all_memory(self) -> List[Dict[str, Any]]:
        """
        Get all documents from this agent's memory.
        
        Returns:
            List of all documents
        """
        try:
            return self.memory.get_agent_memory(self.name)
        except Exception as e:
            logger.error(f"Error getting all memory: {e}")
            return [] 