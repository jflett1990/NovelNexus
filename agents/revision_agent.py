import logging
import json
from typing import Dict, Any, List, Optional
from datetime import datetime


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
        use_openai: bool = True
    ):
        """
        Initialize the Revision Agent.
        
        Args:
            project_id: Unique identifier for the project
            memory: Dynamic memory instance
            use_openai: Whether to use OpenAI models
        """
        self.project_id = project_id
        self.memory = memory
        self.use_openai = use_openai
        
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
            # Generate revised chapter content
            response = self.openai_client.generate(
                prompt=user_prompt,
                system_prompt=system_prompt,
                model="gpt-4o"
            )
            
            revised_content = response.get("content", "")
            logger.info(f"Revised chapter {chapter_id} using OpenAI")
            
            # Create the revised chapter
            revised_chapter = chapter_data.copy()
            revised_chapter["content"] = revised_content
            revised_chapter["word_count"] = len(revised_content.split())
            revised_chapter["revision_notes"] = {
                "revision_date": self.memory.get_current_timestamp(),
                "based_on_review": review_data.get("id", "unknown"),
                "focus_areas": focus_categories
            }
            
            self._store_in_memory(revised_chapter)
            
            return revised_chapter
            
        except Exception as e:
            logger.error(f"Error revising chapter: {str(e)}")
            # Return original chapter with error note
            error_chapter = chapter_data.copy()
            error_chapter["revision_error"] = str(e)
            return error_chapter
    
    def revise_specific_elements(
        self,
        chapter_data: Dict[str, Any],
        element_type: str,
        specific_instructions: str,
        examples: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Revise specific elements within a chapter (e.g., dialogue, descriptions).
        
        Args:
            chapter_data: Dictionary containing the chapter
            element_type: Type of element to revise (e.g., 'dialogue', 'descriptions')
            specific_instructions: Specific instructions for the revision
            examples: Optional examples for clarity
            
        Returns:
            Dictionary with the revised chapter
        """
        logger.info(f"Revising {element_type} in chapter {chapter_data.get('id', 'unknown')}")
        
        # Extract key information from chapter data
        chapter_id = chapter_data.get("id", "unknown")
        chapter_number = chapter_data.get("number", 0)
        chapter_title = chapter_data.get("title", "Untitled Chapter")
        chapter_content = chapter_data.get("content", "")
        
        # Build the system prompt
        system_prompt = f"""You are an expert literary editor specializing in revising {element_type} in fiction.
Your task is to revise the {element_type} in a book chapter according to specific instructions.
Your revisions should enhance the quality of the {element_type} while preserving the overall 
flow and style of the chapter. Focus only on the {element_type}, leave other elements unchanged.
Provide the complete revised chapter text."""
        
        # Build the user prompt
        user_prompt = f"""Revise the {element_type} in Chapter {chapter_number}: {chapter_title} according to these instructions:

{specific_instructions}

{"Examples to consider:" if examples else ""}
{chr(10).join([f"- {ex}" for ex in examples]) if examples else ""}

Original Chapter Content:
{chapter_content}

Provide the complete revised chapter text, focusing only on improving the {element_type}.
Maintain the same overall story, structure, and style, changing only what is necessary to address the instructions.
"""
        
        try:
            # Generate revised chapter 
            response = self.openai_client.generate(
                prompt=user_prompt,
                system_prompt=system_prompt,
                model="gpt-4o"
            )
            
            revised_content = response.get("content", "")
            logger.info(f"Revised {element_type} in chapter {chapter_id} using OpenAI")
            
            # Create the revised chapter
            revised_chapter = chapter_data.copy()
            revised_chapter["content"] = revised_content
            revised_chapter["word_count"] = len(revised_content.split())
            revised_chapter["revision_notes"] = {
                "revision_date": datetime.now().isoformat(),
                "revision_type": f"{element_type}_revision",
                "instructions": specific_instructions
            }
            
            self._store_in_memory(revised_chapter)
            
            return revised_chapter
            
        except Exception as e:
            logger.error(f"Error revising {element_type}: {str(e)}")
            # Return original chapter with error info
            chapter_data["revision_error"] = str(e)
            return chapter_data
    
    def revise_consistency_issues(
        self,
        chapters: List[Dict[str, Any]],
        consistency_analysis: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Revise chapters to fix consistency issues.
        
        Args:
            chapters: List of chapter dictionaries
            consistency_analysis: Dictionary with consistency analysis
            
        Returns:
            List of revised chapter dictionaries
        """
        logger.info(f"Revising consistency issues across {len(chapters)} chapters")
        
        # Extract consistency issues
        issues = consistency_analysis.get("issues", [])
        if not issues:
            logger.info("No consistency issues to revise")
            return chapters
        
        # Organize chapters by number for easier reference
        chapters_to_revise = sorted(chapters, key=lambda x: x.get("number", 0))
        
        # Format the consistency issues for the prompt
        issues_text = ""
        for i, issue in enumerate(issues):
            issue_type = issue.get("type", "Unknown")
            description = issue.get("description", "")
            affected_chapters = issue.get("affected_chapters", [])
            
            affected_str = "All chapters" if not affected_chapters else f"Chapters {', '.join(map(str, affected_chapters))}"
            issues_text += f"{i+1}. {issue_type}: {description}\n   Affects: {affected_str}\n\n"
        
        # Revise each chapter
        revised_chapters = []
        
        for chapter in chapters_to_revise:
            chapter_id = chapter.get("id", "unknown")
            chapter_number = chapter.get("number", 0)
            chapter_title = chapter.get("title", f"Chapter {chapter_number}")
            chapter_content = chapter.get("content", "")
            
            # Build system prompt
            system_prompt = """You are an expert literary editor specializing in maintaining consistency across a manuscript.
Your task is to revise a chapter to fix consistency issues identified in a manuscript-wide analysis.
Your revisions should address only the consistency issues, while preserving the chapter's original style, 
structure, and content as much as possible. Focus on making the minimal necessary changes to resolve the issues.
Provide the complete revised chapter text."""
            
            # Build user prompt
            user_prompt = f"""Revise Chapter {chapter_number}: {chapter_title} to fix the following consistency issues identified across the manuscript:

CONSISTENCY ISSUES:
{issues_text}

ORIGINAL CHAPTER CONTENT:
{chapter_content}

Revise this chapter to fix any relevant consistency issues while preserving its original structure and style.
Focus only on the consistency issues mentioned - do not make other editorial changes.
Provide the complete revised text of the chapter.
"""
            
            try:
                # Generate revised chapter
                response = self.openai_client.generate(
                    prompt=user_prompt,
                    system_prompt=system_prompt,
                    model="gpt-4o"
                )
                
                revised_content = response.get("content", "")
                logger.info(f"Revised consistency issues in chapter {chapter_id} using OpenAI")
                
                # Create the revised chapter
                revised_chapter = chapter.copy()
                revised_chapter["content"] = revised_content
                revised_chapter["word_count"] = len(revised_content.split())
                revised_chapter["revision_notes"] = {
                    "revision_date": datetime.now().isoformat(),
                    "revision_type": "consistency_revision",
                    "consistency_issues": issues
                }
                
                self._store_in_memory(revised_chapter)
                revised_chapters.append(revised_chapter)
                
            except Exception as e:
                logger.error(f"Error revising consistency in chapter {chapter_id}: {str(e)}")
                # Add the original chapter with error info
                error_chapter = chapter.copy()
                error_chapter["revision_error"] = str(e)
                revised_chapters.append(error_chapter)
        
        logger.info(f"Completed consistency revisions for {len(revised_chapters)} chapters")
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
