import logging
from typing import Dict, Any, List, Optional
import json

from models.openai_client import get_openai_client

logger = logging.getLogger(__name__)

class ManuscriptRefiner:
    """
    Agent for refining and polishing manuscript text to improve quality and readability.
    Handles stylistic improvements, clarity enhancements, and consistency checks.
    """
    
    def __init__(
        self,
        project_id: str,
        model_name: str = "gpt-4o"
    ):
        """
        Initialize the manuscript refiner with configuration.
        
        Args:
            project_id: Unique identifier for the project
            model_name: OpenAI model to use for refinement
        """
        self.project_id = project_id
        self.model_name = model_name
        self.openai_client = get_openai_client()
        logger.info(f"Initialized manuscript refiner with model {model_name}")
    
    def polish_text(self, text: str, style_guide: Optional[Dict[str, Any]] = None) -> str:
        """
        Polish and refine text according to style guidelines.
        
        Args:
            text: Text to refine
            style_guide: Optional style guide parameters
            
        Returns:
            Refined text
        """
        if not text:
            return ""
            
        # Use style guide if provided
        style_instructions = ""
        if style_guide:
            style_instructions = f"Apply these style guidelines: {json.dumps(style_guide)}\n\n"
            
        prompt = f"""{style_instructions}Polish and refine the following text. Improve:
1. Flow and readability
2. Word choice and variation
3. Sentence structure variety
4. Stylistic consistency
5. Grammar and punctuation

Do not change the fundamental meaning or content. Maintain the author's voice.

TEXT TO REFINE:
{text}

REFINED VERSION:"""

        try:
            response = self.openai_client.generate(
                prompt=prompt,
                model=self.model_name
            )
            
            refined_text = response.get("content", "").strip()
            
            if not refined_text:
                logger.warning("Failed to generate refined text")
                return text
                
            return refined_text
            
        except Exception as e:
            logger.error(f"Error refining text: {str(e)}")
            return text
    
    def improve_readability(self, text: str, target_audience: str = "general") -> str:
        """
        Improve text readability for target audience.
        
        Args:
            text: Text to improve
            target_audience: Target audience description
            
        Returns:
            More readable text
        """
        if not text:
            return ""
            
        prompt = f"""Improve the readability of the following text for a {target_audience} audience.
Make it clearer and more engaging while preserving meaning and style.

TEXT:
{text}

IMPROVED VERSION:"""

        try:
            response = self.openai_client.generate(
                prompt=prompt,
                model=self.model_name
            )
            
            improved_text = response.get("content", "").strip()
            
            if not improved_text:
                logger.warning("Failed to improve readability")
                return text
                
            return improved_text
            
        except Exception as e:
            logger.error(f"Error improving readability: {str(e)}")
            return text


# Add missing import
import re 