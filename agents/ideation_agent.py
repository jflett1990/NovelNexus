import logging
import json
from typing import Dict, Any, List, Optional

from models.ollama_client import get_ollama_client
from models.openai_client import get_openai_client
from memory.dynamic_memory import DynamicMemory
from schemas.ideation_schema import IDEATION_SCHEMA

logger = logging.getLogger(__name__)

class IdeationAgent:
    """
    Agent responsible for generating initial book ideas, themes, and concepts.
    """
    
    def __init__(
        self,
        project_id: str,
        memory: DynamicMemory,
        use_openai: bool = True,
        use_ollama: bool = True
    ):
        """
        Initialize the Ideation Agent.
        
        Args:
            project_id: Unique identifier for the project
            memory: Dynamic memory instance
            use_openai: Whether to use OpenAI models
            use_ollama: Whether to use Ollama models
        """
        self.project_id = project_id
        self.memory = memory
        self.use_openai = use_openai
        self.use_ollama = use_ollama
        
        self.ollama_client = get_ollama_client() if use_ollama else None
        self.openai_client = get_openai_client() if use_openai else None
        
        self.name = "ideation_agent"
        self.stage = "ideation"
    
    def generate_ideas(
        self,
        title: Optional[str] = None,
        genre: Optional[str] = None,
        initial_prompt: Optional[str] = None,
        complexity: str = "medium",
        num_ideas: int = 3
    ) -> Dict[str, Any]:
        """
        Generate book ideas based on input parameters.
        
        Args:
            title: Optional book title
            genre: Optional book genre
            initial_prompt: Optional initial prompt with ideas
            complexity: Complexity level (low, medium, high)
            num_ideas: Number of ideas to generate
            
        Returns:
            Dictionary with generated ideas
        """
        logger.info(f"Generating {num_ideas} ideas for project {self.project_id}")
        
        # Build the system prompt
        system_prompt = """You are an expert literary idea generator, specializing in creating rich, unique, and engaging book concepts. 
Your task is to create compelling book ideas that include key themes, high-level plot concepts, and emotional tones.
Each idea should be distinct and fully developed with market potential.
Provide output in JSON format according to the provided schema."""
        
        # Build the user prompt
        user_prompt = f"Generate {num_ideas} unique book ideas"
        
        if title:
            user_prompt += f" related to the title: '{title}'"
        
        if genre:
            user_prompt += f" in the {genre} genre"
        
        if initial_prompt:
            user_prompt += f"\n\nConsider these initial thoughts as inspiration: {initial_prompt}"
        
        user_prompt += f"\n\nThe ideas should have {complexity} complexity."
        user_prompt += f"\n\nRespond with ideas formatted according to this JSON schema: {json.dumps(IDEATION_SCHEMA)}"
        
        try:
            # Try OpenAI first if enabled
            if self.use_openai and self.openai_client:
                try:
                    response = self.openai_client.generate(
                        prompt=user_prompt,
                        system_prompt=system_prompt,
                        json_mode=True,
                        temperature=0.8
                    )
                    
                    ideas = response["parsed_json"]
                    logger.info(f"Generated {len(ideas.get('ideas', []))} ideas using OpenAI")
                    
                    # Store in memory
                    self._store_in_memory(ideas)
                    
                    return ideas
                except Exception as e:
                    logger.warning(f"OpenAI ideation failed: {e}, falling back to Ollama")
            
            # Fall back to Ollama if OpenAI failed or is not enabled
            if self.use_ollama and self.ollama_client:
                response = self.ollama_client.generate(
                    prompt=user_prompt,
                    system=system_prompt,
                    format="json"
                )
                
                # Extract and parse JSON from response
                text_response = response.get("response", "{}")
                
                # Extracting the JSON part from the response
                json_start = text_response.find("{")
                json_end = text_response.rfind("}") + 1
                
                if json_start >= 0 and json_end > json_start:
                    json_str = text_response[json_start:json_end]
                    ideas = json.loads(json_str)
                else:
                    raise ValueError("Could not extract valid JSON from Ollama response")
                
                logger.info(f"Generated {len(ideas.get('ideas', []))} ideas using Ollama")
                
                # Store in memory
                self._store_in_memory(ideas)
                
                return ideas
            
            raise Exception("No available AI service (OpenAI or Ollama) to generate ideas")
            
        except Exception as e:
            logger.error(f"Ideation error: {e}")
            raise Exception(f"Failed to generate ideas: {e}")
    
    def refine_idea(self, idea_id: str, feedback: str) -> Dict[str, Any]:
        """
        Refine a specific idea based on feedback.
        
        Args:
            idea_id: ID of the idea to refine
            feedback: Feedback for refinement
            
        Returns:
            Dictionary with refined idea
        """
        # Retrieve the original idea from memory
        original_ideas = self.memory.query_memory(f"idea_id:{idea_id}", agent_name=self.name)
        
        if not original_ideas:
            raise ValueError(f"Idea with ID {idea_id} not found in memory")
        
        original_idea_doc = original_ideas[0]
        original_idea_text = original_idea_doc['text']
        
        # Build the system prompt
        system_prompt = """You are an expert literary idea refiner. Your task is to refine an existing book idea based on feedback.
Preserve what works in the original idea while incorporating the feedback to improve it.
Provide output in JSON format according to the provided schema."""
        
        # Build the user prompt
        user_prompt = f"""Refine the following book idea based on this feedback: {feedback}

Original idea:
{original_idea_text}

Respond with the refined idea formatted according to this JSON schema: {json.dumps(IDEATION_SCHEMA['properties']['ideas']['items'])}
"""
        
        try:
            # Try OpenAI first if enabled
            if self.use_openai and self.openai_client:
                try:
                    response = self.openai_client.generate(
                        prompt=user_prompt,
                        system_prompt=system_prompt,
                        json_mode=True,
                        temperature=0.7
                    )
                    
                    refined_idea = response["parsed_json"]
                    logger.info(f"Refined idea {idea_id} using OpenAI")
                    
                    # Update the idea ID if it changed
                    if "id" in refined_idea and refined_idea["id"] != idea_id:
                        refined_idea["id"] = idea_id
                    
                    # Store in memory
                    self.memory.add_document(
                        json.dumps(refined_idea),
                        self.name,
                        metadata={"type": "refined_idea", "original_id": idea_id}
                    )
                    
                    return refined_idea
                except Exception as e:
                    logger.warning(f"OpenAI idea refinement failed: {e}, falling back to Ollama")
            
            # Fall back to Ollama if OpenAI failed or is not enabled
            if self.use_ollama and self.ollama_client:
                response = self.ollama_client.generate(
                    prompt=user_prompt,
                    system=system_prompt,
                    format="json"
                )
                
                # Extract and parse JSON from response
                text_response = response.get("response", "{}")
                
                # Extracting the JSON part from the response
                json_start = text_response.find("{")
                json_end = text_response.rfind("}") + 1
                
                if json_start >= 0 and json_end > json_start:
                    json_str = text_response[json_start:json_end]
                    refined_idea = json.loads(json_str)
                else:
                    raise ValueError("Could not extract valid JSON from Ollama response")
                
                logger.info(f"Refined idea {idea_id} using Ollama")
                
                # Update the idea ID if it changed
                if "id" in refined_idea and refined_idea["id"] != idea_id:
                    refined_idea["id"] = idea_id
                
                # Store in memory
                self.memory.add_document(
                    json.dumps(refined_idea),
                    self.name,
                    metadata={"type": "refined_idea", "original_id": idea_id}
                )
                
                return refined_idea
            
            raise Exception("No available AI service (OpenAI or Ollama) to refine idea")
            
        except Exception as e:
            logger.error(f"Idea refinement error: {e}")
            raise Exception(f"Failed to refine idea: {e}")
    
    def _store_in_memory(self, ideas: Dict[str, Any]) -> None:
        """
        Store generated ideas in memory.
        
        Args:
            ideas: Dictionary with generated ideas
        """
        if "ideas" not in ideas or not isinstance(ideas["ideas"], list):
            logger.warning("Invalid ideas format for memory storage")
            return
        
        # Store the entire ideas dict
        self.memory.add_document(
            json.dumps(ideas),
            self.name,
            metadata={"type": "ideation_results"}
        )
        
        # Store each individual idea for easier retrieval
        for idea in ideas["ideas"]:
            idea_id = idea.get("id")
            if not idea_id:
                continue
                
            self.memory.add_document(
                json.dumps(idea),
                self.name,
                metadata={"type": "idea", "idea_id": idea_id}
            )
    
    def get_best_idea(self) -> Dict[str, Any]:
        """
        Get the best idea from memory.
        
        Returns:
            Dictionary with the best idea
        """
        # Query for all ideas in memory
        idea_docs = self.memory.get_agent_memory(self.name)
        
        if not idea_docs:
            raise ValueError("No ideas found in memory")
        
        # Filter for individual ideas (not idea sets)
        individual_ideas = []
        
        for doc in idea_docs:
            metadata = doc.get('metadata', {})
            if metadata.get('type') == 'idea' or metadata.get('type') == 'refined_idea':
                try:
                    idea = json.loads(doc['text'])
                    individual_ideas.append(idea)
                except json.JSONDecodeError:
                    continue
        
        if not individual_ideas:
            raise ValueError("No valid individual ideas found in memory")
        
        # Get the most recent refined idea, or the highest-rated idea
        refined_ideas = [idea for idea in individual_ideas 
                        if idea.get('metadata', {}).get('type') == 'refined_idea']
        
        if refined_ideas:
            # Sort by timestamp and return the most recent
            sorted_refined = sorted(
                refined_ideas,
                key=lambda x: x.get('metadata', {}).get('timestamp', ''),
                reverse=True
            )
            return sorted_refined[0]
        
        # If no refined ideas, return the highest score idea
        sorted_ideas = sorted(
            individual_ideas,
            key=lambda x: float(x.get('score', 0)),
            reverse=True
        )
        
        return sorted_ideas[0]
