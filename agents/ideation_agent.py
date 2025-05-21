import logging
import json
from typing import Dict, Any, List, Optional
import uuid

from agents.agent_prototype import AbstractAgent
from models.openai_client import get_openai_client
from memory.dynamic_memory import DynamicMemory
from schemas.ideation_schema import IDEATION_SCHEMA
from utils.model_utils import select_model
from utils.validation_utils import validate_ideas

logger = logging.getLogger(__name__)

class IdeationAgent(AbstractAgent):
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
        super().__init__(
            project_id=project_id,
            memory=memory,
            use_openai=use_openai,
            name="ideation_agent",
            stage="ideation"
        )
    
    def execute(
        self,
        title: Optional[str] = None,
        genre: Optional[str] = None,
        initial_prompt: Optional[str] = None,
        complexity: str = "medium",
        num_ideas: int = 3
    ) -> Dict[str, Any]:
        """
        Main execution method - generates book ideas based on input parameters.
        
        Args:
            title: Optional book title
            genre: Optional book genre
            initial_prompt: Optional initial prompt with ideas
            complexity: Complexity level (low, medium, high)
            num_ideas: Number of ideas to generate
            
        Returns:
            Dictionary with generated ideas
        """
        return self.generate_ideas(
            title=title,
            genre=genre,
            initial_prompt=initial_prompt,
            complexity=complexity,
            num_ideas=num_ideas
        )
    
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
            # Use the parent class generate method with proper error handling
            response = self.generate(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=0.8,
                json_format=True
            )
            
            raw_ideas = response["parsed_json"]
            
            # Validate and fix ideas using our validation utility
            validated_ideas = validate_ideas(raw_ideas)
            
            logger.info(f"Generated {len(validated_ideas.get('ideas', []))} ideas for project {self.project_id}")
            
            # Store in memory
            logger.debug(f"Storing validated ideas in memory for project {self.project_id}")
            self._store_in_memory(validated_ideas)
            logger.info(f"Successfully stored ideas in memory for project {self.project_id}")
            
            return validated_ideas
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
        original_ideas = self.get_memory(f"idea_id:{idea_id}")
        
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
            # Use the parent class generate method
            response = self.generate(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=0.7,
                json_format=True
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
            
            # Store in memory using parent class method
            self.add_to_memory(
                json.dumps(refined_idea),
                metadata={"type": "refined_idea", "original_id": idea_id}
            )
            
            return refined_idea
        except Exception as e:
            logger.error(f"Idea refinement error: {e}", exc_info=True)
            raise Exception(f"Failed to refine idea: {e}")
    
    def _store_in_memory(self, ideas: Dict[str, Any]) -> None:
        """
        Store ideas in memory.
        
        Args:
            ideas: Dictionary with ideas to store
        """
        # Store the complete ideas collection
        self.add_to_memory(
            json.dumps(ideas),
            metadata={"type": "ideation_results"}
        )
        
        # Also store each idea individually for easier retrieval
        if "ideas" in ideas and isinstance(ideas["ideas"], list):
            for idea in ideas["ideas"]:
                # Ensure the idea has an ID
                if "id" not in idea:
                    idea["id"] = str(uuid.uuid4())
                
                # Store individual idea
                self.add_to_memory(
                    json.dumps(idea),
                    metadata={
                        "type": "idea",
                        "idea_id": idea["id"],
                        "title": idea.get("title", "Untitled"),
                        "score": idea.get("score", 0)
                    }
                )
    
    def get_best_idea(self) -> Dict[str, Any]:
        """
        Get the highest-rated idea.
        
        Returns:
            Dictionary with the best idea
        """
        ideas = self.get_all_memory()
        
        if not ideas:
            raise ValueError("No ideas found in memory")
        
        best_idea = None
        highest_score = -1
        
        for doc in ideas:
            try:
                idea = json.loads(doc["text"])
                if "score" in idea and float(idea["score"]) > highest_score:
                    highest_score = float(idea["score"])
                    best_idea = idea
            except (json.JSONDecodeError, ValueError):
                continue
        
        if not best_idea:
            # Try to get any idea if scoring fails
            for doc in ideas:
                try:
                    idea = json.loads(doc["text"])
                    if "title" in idea and "id" in idea:
                        return idea
                except json.JSONDecodeError:
                    continue
            
            raise ValueError("No valid ideas found in memory")
        
        return best_idea
