import logging
import json
from typing import Dict, Any, List, Optional

from models.ollama_client import get_ollama_client
from models.openai_client import get_openai_client
from memory.dynamic_memory import DynamicMemory

logger = logging.getLogger(__name__)

class RevisionAgent:
    """
    Agent responsible for revising chapters based on review feedback.
    """
    
    def __init__(
        self,
        project_id: str,
        memory: DynamicMemory,
        use_openai: bool = True,
        use_ollama: bool = True
    ):
        """
        Initialize the Revision Agent.
        
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
        
        self.name = "revision_agent"
        self.stage = "revision"
    
    def revise_chapter(
        self,
        chapter_data: Dict[str, Any],
        review_data: Dict[str, Any],
        revision_focus: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Revise a chapter based on review feedback.
        
        Args:
            chapter_data: Dictionary containing the written chapter
            review_data: Dictionary containing the review feedback
            revision_focus: Optional list of specific aspects to focus on
            
        Returns:
            Dictionary with the revised chapter
        """
        logger.info(f"Revising chapter {chapter_data.get('id', 'unknown')} for project {self.project_id}")
        
        # Extract key information from chapter data
        chapter_id = chapter_data.get("id", "unknown")
        chapter_number = chapter_data.get("number", 0)
        chapter_title = chapter_data.get("title", "Untitled Chapter")
        chapter_content = chapter_data.get("content", "")
        
        # Extract key feedback from review
        overall_assessment = review_data.get("overall_assessment", {})
        overall_rating = overall_assessment.get("rating", 0)
        strengths = overall_assessment.get("strengths", [])
        weaknesses = overall_assessment.get("weaknesses", [])
        
        # Extract detailed feedback by category
        detailed_feedback = {}
        focus_categories = revision_focus or ["plot_structure", "character_development", "setting_atmosphere", 
                                             "dialogue", "pacing_flow", "prose_quality", "style_consistency"]
        
        for category in focus_categories:
            if category in review_data:
                category_data = review_data[category]
                detailed_feedback[category] = {
                    "rating": category_data.get("rating", 0),
                    "issues": category_data.get("issues", []),
                    "strengths": category_data.get("strengths", [])
                }
        
        # Format feedback for the prompt
        feedback_sections = []
        for category, data in detailed_feedback.items():
            category_name = category.replace("_", " ").title()
            issues = data.get("issues", [])
            
            issues_text = ""
            if issues:
                issues_list = []
                for issue in issues:
                    desc = issue.get("description", "")
                    example = issue.get("example", "")
                    suggestion = issue.get("suggestion", "")
                    issues_list.append(f"- Issue: {desc}\n  Example: {example}\n  Suggestion: {suggestion}")
                
                issues_text = "\n".join(issues_list)
            
            category_text = f"{category_name} (Rating: {data.get('rating', 0)}/10):\n{issues_text}"
            feedback_sections.append(category_text)
        
        formatted_feedback = "\n\n".join(feedback_sections)
        
        # Build the system prompt
        system_prompt = """You are an expert author and editor specializing in revising manuscripts.
Your task is to revise a book chapter based on detailed review feedback.
Implement the suggested changes while preserving the original chapter's core elements and strengths.
Your goal is to address all identified issues while maintaining the author's voice and the chapter's purpose.
The revised chapter should be a complete, polished version ready for final editing."""
        
        # Build the user prompt
        # Build user prompt in parts to avoid f-string backslash issues
        user_prompt = f"Revise Chapter {chapter_number}: {chapter_title} based on the following review feedback:\n\n"
        user_prompt += "Overall Assessment:\n"
        user_prompt += f"- Rating: {overall_rating}/10\n"
        user_prompt += f"- Strengths: {', '.join(strengths)}\n"
        user_prompt += f"- Weaknesses: {', '.join(weaknesses)}\n\n"
        
        user_prompt += "Detailed Feedback:\n"
        user_prompt += f"{formatted_feedback}\n\n"
        
        user_prompt += "Original Chapter Content:\n"
        user_prompt += f"{chapter_content}\n\n"
        
        user_prompt += "Revise this chapter to address all the identified issues while preserving its strengths and core elements.\n"
        user_prompt += "Make specific improvements to the text based on the feedback.\n"
        user_prompt += "The revised chapter should maintain the same general plot points and character development,\n"
        user_prompt += "but with improved prose, dialogue, pacing, and other elements as identified in the feedback.\n\n"
        
        user_prompt += "Provide the complete revised chapter text, ready for final editing."
        
        try:
            # Try OpenAI first if enabled
            if self.use_openai and self.openai_client:
                try:
                    response = self.openai_client.generate(
                        prompt=user_prompt,
                        system_prompt=system_prompt,
                        temperature=0.7,
                        max_tokens=4000
                    )
                    
                    revised_content = response["text"]
                    logger.info(f"Revised chapter {chapter_id} using OpenAI")
                    
                    # Create the revised chapter
                    revised_chapter = chapter_data.copy()
                    revised_chapter["content"] = revised_content
                    revised_chapter["word_count"] = len(revised_content.split())
                    revised_chapter["revision_notes"] = {
                        "revision_date": self.memory.metadata.get('timestamp', ''),
                        "based_on_review": review_data.get("id", "unknown"),
                        "focus_areas": focus_categories
                    }
                    
                    self._store_in_memory(revised_chapter)
                    
                    return revised_chapter
                except Exception as e:
                    logger.warning(f"OpenAI chapter revision failed: {e}, falling back to Ollama")
            
            # Fall back to Ollama if OpenAI failed or is not enabled
            if self.use_ollama and self.ollama_client:
                response = self.ollama_client.generate(
                    prompt=user_prompt,
                    system=system_prompt
                )
                
                revised_content = response.get("response", "")
                logger.info(f"Revised chapter {chapter_id} using Ollama")
                
                # Create the revised chapter
                revised_chapter = chapter_data.copy()
                revised_chapter["content"] = revised_content
                revised_chapter["word_count"] = len(revised_content.split())
                revised_chapter["revision_notes"] = {
                    "revision_date": self.memory.metadata.get('timestamp', ''),
                    "based_on_review": review_data.get("id", "unknown"),
                    "focus_areas": focus_categories
                }
                
                self._store_in_memory(revised_chapter)
                
                return revised_chapter
            
            raise Exception("No available AI service (OpenAI or Ollama) to revise chapter")
            
        except Exception as e:
            logger.error(f"Chapter revision error: {e}")
            raise Exception(f"Failed to revise chapter: {e}")
    
    def revise_specific_elements(
        self,
        chapter_data: Dict[str, Any],
        element_type: str,
        specific_instructions: str,
        examples: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Revise specific elements of a chapter.
        
        Args:
            chapter_data: Dictionary containing the written chapter
            element_type: Type of element to revise (e.g., 'dialogue', 'description', 'pacing')
            specific_instructions: Specific instructions for revision
            examples: Optional examples to guide the revision
            
        Returns:
            Dictionary with the revised chapter
        """
        logger.info(f"Revising {element_type} in chapter {chapter_data.get('id', 'unknown')}")
        
        # Extract key information from chapter data
        chapter_id = chapter_data.get("id", "unknown")
        chapter_number = chapter_data.get("number", 0)
        chapter_title = chapter_data.get("title", "Untitled Chapter")
        chapter_content = chapter_data.get("content", "")
        
        # Format examples if provided
        examples_text = ""
        if examples and len(examples) > 0:
            examples_list = [f"Example {i+1}: {example}" for i, example in enumerate(examples)]
            examples_text = "\n".join(examples_list)
        
        # Build the system prompt
        system_prompt = f"""You are an expert author and editor specializing in revising {element_type} in manuscripts.
Your task is to revise the {element_type} in a book chapter based on specific instructions.
Implement the suggested changes while preserving the chapter's overall structure and other elements.
Your goal is to improve the {element_type} while maintaining the author's voice and the chapter's purpose.
The revised chapter should be a complete, polished version ready for final editing."""
        
        # Build the user prompt
        # Build the user prompt in parts to avoid f-string backslash issues
        user_prompt = f"Revise the {element_type} in Chapter {chapter_number}: {chapter_title} based on these instructions:\n\n"
        user_prompt += f"Revision Instructions:\n{specific_instructions}\n\n"
        
        if examples_text:
            user_prompt += f"Examples:\n{examples_text}\n\n"
            
        user_prompt += f"Original Chapter Content:\n{chapter_content}\n\n"
        user_prompt += f"Revise this chapter to improve the {element_type} as specified, while preserving all other elements.\n"
        user_prompt += "The revised chapter should maintain the same plot points, character development, and other elements\n"
        user_prompt += f"not related to {element_type}.\n\n"
        user_prompt += "Provide the complete revised chapter text, ready for final editing."
        
        try:
            # Try OpenAI first if enabled
            if self.use_openai and self.openai_client:
                try:
                    response = self.openai_client.generate(
                        prompt=user_prompt,
                        system_prompt=system_prompt,
                        temperature=0.7,
                        max_tokens=4000
                    )
                    
                    revised_content = response["text"]
                    logger.info(f"Revised {element_type} in chapter {chapter_id} using OpenAI")
                    
                    # Create the revised chapter
                    revised_chapter = chapter_data.copy()
                    revised_chapter["content"] = revised_content
                    revised_chapter["word_count"] = len(revised_content.split())
                    revised_chapter["revision_notes"] = {
                        "revision_date": self.memory.metadata.get('timestamp', ''),
                        "revision_type": f"{element_type}_revision",
                        "instructions": specific_instructions
                    }
                    
                    self._store_in_memory(revised_chapter)
                    
                    return revised_chapter
                except Exception as e:
                    logger.warning(f"OpenAI {element_type} revision failed: {e}, falling back to Ollama")
            
            # Fall back to Ollama if OpenAI failed or is not enabled
            if self.use_ollama and self.ollama_client:
                response = self.ollama_client.generate(
                    prompt=user_prompt,
                    system=system_prompt
                )
                
                revised_content = response.get("response", "")
                logger.info(f"Revised {element_type} in chapter {chapter_id} using Ollama")
                
                # Create the revised chapter
                revised_chapter = chapter_data.copy()
                revised_chapter["content"] = revised_content
                revised_chapter["word_count"] = len(revised_content.split())
                revised_chapter["revision_notes"] = {
                    "revision_date": self.memory.metadata.get('timestamp', ''),
                    "revision_type": f"{element_type}_revision",
                    "instructions": specific_instructions
                }
                
                self._store_in_memory(revised_chapter)
                
                return revised_chapter
            
            raise Exception(f"No available AI service (OpenAI or Ollama) to revise {element_type}")
            
        except Exception as e:
            logger.error(f"{element_type} revision error: {e}")
            raise Exception(f"Failed to revise {element_type}: {e}")
    
    def revise_consistency_issues(
        self,
        chapters: List[Dict[str, Any]],
        consistency_analysis: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Revise multiple chapters to address consistency issues.
        
        Args:
            chapters: List of chapter dictionaries
            consistency_analysis: Dictionary with consistency analysis
            
        Returns:
            List of dictionaries with revised chapters
        """
        logger.info(f"Revising consistency issues for project {self.project_id}")
        
        # Extract priority issues from consistency analysis
        priority_recommendations = consistency_analysis.get("priority_recommendations", [])
        
        # Extract issues by category
        issues_by_category = {}
        categories = ["character_consistency", "plot_continuity", "setting_consistency", 
                     "style_tone_consistency", "theme_consistency", "timeline_consistency"]
        
        for category in categories:
            if category in consistency_analysis:
                category_data = consistency_analysis[category]
                issues_by_category[category] = category_data.get("issues", [])
        
        # Prioritize a few chapters that need the most work
        chapters_to_revise = []
        for chapter in chapters:
            chapter_id = chapter.get("id", "unknown")
            
            # Check if chapter is mentioned in issues
            mentioned_count = 0
            for category, issues in issues_by_category.items():
                for issue in issues:
                    example = issue.get("example", "").lower()
                    chapter_title = chapter.get('title', '').lower()
                    if f"chapter {chapter.get('number', 0)}" in example or (chapter_title and chapter_title in example):
                        mentioned_count += 1
            
            if mentioned_count > 0:
                chapters_to_revise.append({
                    "chapter": chapter,
                    "priority": mentioned_count
                })
        
        # Sort by priority and limit to top 3
        chapters_to_revise.sort(key=lambda x: x["priority"], reverse=True)
        chapters_to_revise = chapters_to_revise[:3]
        
        revised_chapters = []
        
        # Revise each prioritized chapter
        for chapter_info in chapters_to_revise:
            chapter = chapter_info["chapter"]
            chapter_id = chapter.get("id", "unknown")
            chapter_number = chapter.get("number", 0)
            chapter_title = chapter.get("title", "Untitled Chapter")
            chapter_content = chapter.get("content", "")
            
            # Collect relevant issues for this chapter
            relevant_issues = []
            for category, issues in issues_by_category.items():
                category_name = category.replace("_", " ").title()
                for issue in issues:
                    example = issue.get("example", "")
                    if f"chapter {chapter_number}" in example.lower() or chapter_title.lower() in example.lower():
                        relevant_issues.append({
                            "category": category_name,
                            "description": issue.get("description", ""),
                            "example": example,
                            "suggestion": issue.get("suggestion", "")
                        })
            
            # If no specific issues identified, use general recommendations
            if not relevant_issues:
                for category, issues in issues_by_category.items():
                    category_name = category.replace("_", " ").title()
                    for issue in issues[:1]:  # Take just the first issue from each category
                        relevant_issues.append({
                            "category": category_name,
                            "description": issue.get("description", ""),
                            "example": issue.get("example", ""),
                            "suggestion": issue.get("suggestion", "")
                        })
            
            # Format issues for the prompt
            issues_text = ""
            if relevant_issues:
                issues_list = []
                for issue in relevant_issues:
                    category = issue.get("category", "")
                    desc = issue.get("description", "")
                    example = issue.get("example", "")
                    suggestion = issue.get("suggestion", "")
                    issues_list.append(f"- {category}: {desc}\n  Example: {example}\n  Suggestion: {suggestion}")
                
                issues_text = "\n".join(issues_list)
            
            # Build the system prompt
            system_prompt = """You are an expert author and editor specializing in manuscript consistency.
Your task is to revise a book chapter to address consistency issues across the entire manuscript.
Implement changes to improve character consistency, plot continuity, setting consistency, style/tone, and timeline accuracy.
Your goal is to make this chapter work seamlessly with the rest of the book.
The revised chapter should be a complete, polished version ready for final editing."""
            
            # Build the user prompt
            user_prompt = f"""Revise Chapter {chapter_number}: {chapter_title} to address these consistency issues:

Consistency Issues to Address:
{issues_text}

Original Chapter Content:
{chapter_content}

Revise this chapter to resolve the identified consistency issues while preserving its strengths and core elements.
Make specific changes to align this chapter with the rest of the manuscript for improved consistency.
The revised chapter should maintain the same general plot points but with corrections to characters, settings,
timeline, and style to ensure consistency across the entire book.

Provide the complete revised chapter text, ready for final editing.
"""
            
            try:
                # Try OpenAI first if enabled
                if self.use_openai and self.openai_client:
                    try:
                        response = self.openai_client.generate(
                            prompt=user_prompt,
                            system_prompt=system_prompt,
                            temperature=0.7,
                            max_tokens=4000
                        )
                        
                        revised_content = response["text"]
                        logger.info(f"Revised consistency issues in chapter {chapter_id} using OpenAI")
                        
                        # Create the revised chapter
                        revised_chapter = chapter.copy()
                        revised_chapter["content"] = revised_content
                        revised_chapter["word_count"] = len(revised_content.split())
                        revised_chapter["revision_notes"] = {
                            "revision_date": self.memory.metadata.get('timestamp', ''),
                            "revision_type": "consistency_revision",
                            "addressed_issues": [issue.get("description", "") for issue in relevant_issues]
                        }
                        
                        self._store_in_memory(revised_chapter)
                        revised_chapters.append(revised_chapter)
                        
                    except Exception as e:
                        logger.warning(f"OpenAI consistency revision failed: {e}, falling back to Ollama")
                
                # Fall back to Ollama if OpenAI failed or is not enabled
                if (len(revised_chapters) < len(chapters_to_revise)) and self.use_ollama and self.ollama_client:
                    response = self.ollama_client.generate(
                        prompt=user_prompt,
                        system=system_prompt
                    )
                    
                    revised_content = response.get("response", "")
                    logger.info(f"Revised consistency issues in chapter {chapter_id} using Ollama")
                    
                    # Create the revised chapter
                    revised_chapter = chapter.copy()
                    revised_chapter["content"] = revised_content
                    revised_chapter["word_count"] = len(revised_content.split())
                    revised_chapter["revision_notes"] = {
                        "revision_date": self.memory.metadata.get('timestamp', ''),
                        "revision_type": "consistency_revision",
                        "addressed_issues": [issue.get("description", "") for issue in relevant_issues]
                    }
                    
                    self._store_in_memory(revised_chapter)
                    revised_chapters.append(revised_chapter)
                
            except Exception as e:
                logger.error(f"Consistency revision error for chapter {chapter_id}: {e}")
                continue
        
        return revised_chapters
    
    def _store_in_memory(self, chapter: Dict[str, Any]) -> None:
        """
        Store revised chapter in memory.
        
        Args:
            chapter: Dictionary with revised chapter
        """
        # Store chapter
        self.memory.add_document(
            json.dumps(chapter),
            self.name,
            metadata={
                "type": "revised_chapter",
                "id": chapter.get("id", "unknown"),
                "number": chapter.get("number", 0),
                "title": chapter.get("title", "Untitled")
            }
        )
    
    def get_all_revised_chapters(self) -> List[Dict[str, Any]]:
        """
        Get all revised chapters from memory.
        
        Returns:
            List of dictionaries with revised chapters
        """
        # Query for all chapters in memory
        chapter_docs = self.memory.get_agent_memory(self.name)
        
        if not chapter_docs:
            return []
        
        # Filter for revised chapters
        chapters = []
        
        for doc in chapter_docs:
            metadata = doc.get('metadata', {})
            if metadata.get('type') == 'revised_chapter':
                try:
                    chapter = json.loads(doc['text'])
                    chapters.append(chapter)
                except json.JSONDecodeError:
                    continue
        
        # Sort by chapter number
        chapters.sort(key=lambda x: x.get("number", 0))
        
        return chapters
