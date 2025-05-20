import logging
import re
from typing import List, Dict, Any, Optional

from agents.style_priming_agent import prime_prompt
from models.openai_client import get_openai_client

logger = logging.getLogger(__name__)

class LongformExpander:
    """
    Module for expanding and enriching narrative prose.
    Supports expansion of short outputs by generating depth in prose.
    """
    
    def __init__(self, model_name: str = "gpt-4o"):
        """
        Initialize the longform expander.
        
        Args:
            model_name: The LLM model to use for expansions
        """
        
        self.model_name = model_name
        self.openai_client = get_openai_client()
        logger.info(f"Initialized longform expander with model {model_name}")
    
    def expand_paragraph(self, text: str, style: str = "literary", themes: Optional[List[str]] = None) -> str:
        """
        Enriches a single paragraph with internal thoughts, sensory detail, and more vivid description.
        
        Args:
            text: Original paragraph text
            style: Literary style to apply
            themes: Optional themes to emphasize
            
        Returns:
            Expanded paragraph text
        """
        if not text or len(text.strip()) < 20:
            logger.warning("Paragraph too short to expand meaningfully")
            return text
        
        # Build prompt for paragraph expansion
        prompt = f"""Expand the following paragraph. Make it more immersive by adding:
- Internal monologue
- Subtle tension
- Ambient sensory detail
- Deeper characterization
- Richer setting description

Text:
{text}

Expanded version:"""
        
        # Apply style priming if specified
        if style:
            prompt = prime_prompt(prompt, style, themes)
        
        try:
            response = self.openai_client.generate(
                prompt=prompt,
                model=self.model_name
            )
            
            expanded_text = response.get("content", text).strip()
            
            # Verify the expansion is actually longer
            if len(expanded_text) <= len(text):
                logger.warning("Expansion failed to increase text length")
                return text
                
            return expanded_text
            
        except Exception as e:
            logger.error(f"Error expanding paragraph: {str(e)}")
            return text
    
    def progressive_expand(self, text: str, max_chunks: int = 5, style: str = "literary", themes: Optional[List[str]] = None) -> str:
        """
        Takes the first N paragraphs and expands them recursively.
        
        Args:
            text: Original text containing multiple paragraphs
            max_chunks: Maximum number of chunks/paragraphs to expand
            style: Literary style to apply
            themes: Optional themes to emphasize
            
        Returns:
            Expanded text
        """
        if not text:
            return text
            
        # Split text into paragraphs (respecting various newline patterns)
        paragraphs = re.split(r'\n\s*\n', text)
        
        expanded_paragraphs = []
        expansion_count = min(max_chunks, len(paragraphs))
        
        logger.info(f"Expanding {expansion_count} paragraphs progressively")
        
        for i in range(len(paragraphs)):
            if i < expansion_count:
                # Expand this paragraph
                expanded_para = self.expand_paragraph(paragraphs[i], style, themes)
                expanded_paragraphs.append(expanded_para)
            else:
                # Keep the rest as is
                expanded_paragraphs.append(paragraphs[i])
        
        # Recombine with double newlines
        return "\n\n".join(expanded_paragraphs)
    
    def longform_continue(self, last_lines: str, style: str = "literary", themes: Optional[List[str]] = None) -> str:
        """
        Continues a scene by using the last few lines as a seed.
        
        Args:
            last_lines: The last few lines of existing text
            style: Literary style to apply
            themes: Optional themes to emphasize
            
        Returns:
            Generated continuation text
        """
        if not last_lines or len(last_lines.strip()) < 50:
            logger.warning("Not enough context for meaningful continuation")
            return ""
        
        # Build prompt for continuation
        prompt = f"""Continue the narrative from these last lines. Maintain the tone, 
style, and character voices while developing the scene further.

Last lines:
{last_lines}

Continue the scene with at least 3 paragraphs:"""
        
        # Apply style priming
        prompt = prime_prompt(prompt, style, themes)
        
        try:
            response = self.openai_client.generate(
                prompt=prompt,
                model=self.model_name
            )
            
            continuation = response.get("content", "").strip()
            
            # Basic validation - should have produced something substantial
            if len(continuation.split()) < 50:
                logger.warning("Continuation too short, may not be helpful")
            
            return continuation
            
        except Exception as e:
            logger.error(f"Error generating continuation: {str(e)}")
            return ""

    def enhance_dialogue(self, text: str, style: str = "literary", themes: Optional[List[str]] = None) -> str:
        """
        Enhances dialogue passages with beats, reactions, and subtext.
        
        Args:
            text: Text containing dialogue to enhance
            style: Literary style to apply
            themes: Optional themes to emphasize
            
        Returns:
            Enhanced text with richer dialogue
        """
        # Check if the text has dialogue (basic check for quotation marks)
        if '"' not in text and "'" not in text:
            logger.info("No dialogue detected in text, skipping enhancement")
            return text
            
        # Build prompt for dialogue enhancement
        prompt = f"""Enhance the following dialogue passage by adding:
- Dialogue beats (small actions during conversation)
- Character reactions and micro-expressions
- Subtext and underlying tensions
- Sensory details of the conversation setting

Keep all existing dialogue intact. Only add elements around the dialogue.

Text:
{text}

Enhanced version:"""
        
        # Apply style priming
        prompt = prime_prompt(prompt, style, themes)
        
        try:
            response = self.openai_client.generate(
                prompt=prompt,
                model=self.model_name
            )
            
            enhanced_text = response.get("content", text).strip()
            
            # Verify the enhancement is actually longer
            if len(enhanced_text) <= len(text):
                logger.warning("Dialogue enhancement failed to increase text quality")
                return text
                
            return enhanced_text
            
        except Exception as e:
            logger.error(f"Error enhancing dialogue: {str(e)}")
            return text 