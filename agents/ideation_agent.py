import logging
import json
from typing import Dict, Any, List, Optional
import uuid


from models.openai_client import get_openai_client
from memory.dynamic_memory import DynamicMemory
from schemas.ideation_schema import IDEATION_SCHEMA
from utils.model_utils import select_model
from utils.validation_utils import validate_ideas

logger = logging.getLogger(__name__)

class IdeationAgent:
    """
    Agent responsible for generating initial book ideas, themes, and concepts.
    """
    
    def __init__(
        self,
        project_id: str,
        memory: DynamicMemory,
        use_openai: bool = True
    ):
        """
        Initialize the Ideation Agent.
        
        Args:
            project_id: Unique identifier for the project
            memory: Dynamic memory instance
            use_openai: Whether to use OpenAI models
        """
        self.project_id = project_id
        self.memory = memory
        self.use_openai = use_openai
        
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
        
        logger.debug(f"Built ideation prompt for project {self.project_id}. Using OpenAI: {self.use_openai}")
        
        try:
            # Try OpenAI for generation
            if self.use_openai and self.openai_client:
                try:
                    logger.info(f"Attempting to generate ideas using OpenAI for project {self.project_id}")
                    response = self.openai_client.generate(
                        prompt=user_prompt,
                        system_prompt=system_prompt,
                        json_mode=True,
                        temperature=0.8,
                        agent_name=self.name
                    )
                    
                    raw_ideas = response["parsed_json"]
                    
                    # Validate and fix ideas using our validation utility
                    validated_ideas = validate_ideas(raw_ideas)
                    
                    logger.info(f"Generated {len(validated_ideas.get('ideas', []))} ideas using OpenAI for project {self.project_id}")
                    
                    # Store in memory
                    logger.debug(f"Storing validated ideas in memory for project {self.project_id}")
                    self._store_in_memory(validated_ideas)
                    logger.info(f"Successfully stored ideas in memory for project {self.project_id}")
                    
                    return validated_ideas
                except Exception as e:
                    logger.warning(f"OpenAI ideation failed: {e}")
                    raise Exception(f"Failed to generate ideas: {e}")
            
            logger.error(f"No available AI service (OpenAI) to generate ideas for project {self.project_id}")
            raise Exception("No available AI service (OpenAI) to generate ideas")
            
        except Exception as e:
            logger.error(f"Ideation error: {e}", exc_info=True)
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
            # Use OpenAI for refinement
            if self.use_openai and self.openai_client:
                try:
                    response = self.openai_client.generate(
                        prompt=user_prompt,
                        system_prompt=system_prompt,
                        json_mode=True,
                        temperature=0.7,
                        agent_name=self.name
                    )
                    
                    raw_refined_idea = response["parsed_json"]
                    
                    # Wrap the single idea in a structure for validation
                    idea_wrapper = {"ideas": [raw_refined_idea]}
                    validated_wrapper = validate_ideas(idea_wrapper)
                    
                    # Extract the validated idea
                    refined_idea = validated_wrapper["ideas"][0] if validated_wrapper["ideas"] else {}
                    
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
                    logger.warning(f"OpenAI idea refinement failed: {e}")
            
            logger.error(f"No available AI service (OpenAI) to refine ideas for project {self.project_id}")
            raise Exception("No available AI service (OpenAI) to refine ideas")
            
        except Exception as e:
            logger.error(f"Idea refinement error: {e}", exc_info=True)
            raise Exception(f"Failed to refine idea: {e}")
    
    def _store_in_memory(self, ideas: Dict[str, Any]) -> None:
        """
        Store generated ideas in memory.
        
        Args:
            ideas: Dictionary with ideas to store
        """
        if not ideas or 'ideas' not in ideas:
            logger.warning(f"No ideas to store for project {self.project_id}")
            return
        
        try:
            # Store the full ideas collection
            ideas_json = json.dumps(ideas)
            self.memory.add_document(
                ideas_json,
                self.name,
                metadata={"type": "ideas_collection"}
            )
            
            # Store each individual idea
            for idea in ideas['ideas']:
                # Ensure each idea has an ID
                if 'id' not in idea or not idea['id']:
                    idea['id'] = str(uuid.uuid4())
                
                idea_json = json.dumps(idea)
                self.memory.add_document(
                    idea_json,
                    self.name,
                    metadata={
                        "type": "idea", 
                        "idea_id": idea['id'],
                        "title": idea.get('title', 'Untitled'),
                        "score": idea.get('score', 0)
                    }
                )
                
            logger.debug(f"Stored {len(ideas['ideas'])} ideas in memory for project {self.project_id}")
        except Exception as e:
            logger.error(f"Error storing ideas in memory: {e}")
            raise
    
    def get_best_idea(self) -> Dict[str, Any]:
        """
        Get the best idea for the project.
        
        Returns:
            Dictionary with the best idea
        """
        # Query memory for all ideas
        ideas = self.memory.query_memory("type:idea", agent_name=self.name)
        
        if not ideas:
            raise ValueError(f"No ideas found for project {self.project_id}")
        
        # For now, just return the first idea (most recent)
        # In a future version, we could implement more sophisticated selection
        best_idea_doc = ideas[0]
        return json.loads(best_idea_doc['text'])
