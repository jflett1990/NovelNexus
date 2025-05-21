import logging
import json
from typing import Dict, Any, List, Optional

from models.openai_client import get_openai_client
from memory.dynamic_memory import DynamicMemory
from utils.json_utils import parse_json_safely

logger = logging.getLogger(__name__)

class ChapterWriterAgent:
    """
    Agent responsible for writing individual chapters based on the chapter plan.
    """
    
    def __init__(
        self,
        project_id: str,
        memory: DynamicMemory,
        use_openai: bool = True
    ):
        """
        Initialize the Chapter Writer Agent.
        
        Args:
            project_id: Unique identifier for the project
            memory: Dynamic memory instance
            use_openai: Whether to use OpenAI models
        """
        self.project_id = project_id
        self.memory = memory
        self.use_openai = use_openai
        
        self.openai_client = get_openai_client() if use_openai else None
        
        self.name = "chapter_writer_agent"
        self.stage = "chapter_writing"
        self.model_name = "gpt-4o"
        logger.info(f"Initialized chapter writer agent with model {self.model_name}")
    
    def write_chapter(self, chapter_plan: Dict[str, Any], previous_chapter_content: Optional[str] = None) -> Dict[str, Any]:
        """
        Write a chapter based on the chapter plan and previous content.
        
        Args:
            chapter_plan: The plan for this chapter
            previous_chapter_content: Content of the previous chapter (optional)
            
        Returns:
            Dictionary with chapter content and metadata
        """
        # Handle empty or invalid chapter plan
        if not chapter_plan or not isinstance(chapter_plan, dict):
            logger.warning("Received empty or invalid chapter plan, using fallback chapter")
            chapter_number = 1
            chapter_title = "Chapter 1"
            chapter_summary = "Introduction to the story and characters"
            
            # Create fallback chapter content
            fallback_content = self._create_fallback_chapter_content(
                chapter_number=chapter_number,
                chapter_title=chapter_title,
                chapter_summary=chapter_summary
            )
            
            fallback_chapter = {
                "number": chapter_number,
                "title": chapter_title,
                "summary": chapter_summary,
                "content": fallback_content,
                "word_count": len(fallback_content.split()),
                "is_fallback": True
            }
            
            return fallback_chapter
        
        chapter_number = chapter_plan.get("number", 1)
        chapter_title = chapter_plan.get("title", f"Chapter {chapter_number}")
        chapter_summary = chapter_plan.get("summary", "")
        
        logger.info(f"Writing chapter {chapter_number}: {chapter_title}")
        
        # Get integrated data for context
        integrated_data = self._get_integrated_data()
        
        # Extract relevant information
        characters = integrated_data.get("characters", [])
        world_building = integrated_data.get("world_building", {})
        plot = integrated_data.get("plot", {})
        genre = integrated_data.get("genre", "")
        
        # Prepare character summaries - simplified for prompt length
        character_summaries = []
        for character in characters[:5]:  # Limit to top 5 characters
            if not isinstance(character, dict):
                continue
            name = character.get('name', 'Unknown')
            role = character.get('role', 'character')
            personality = character.get('personality', '')
            motivation = character.get('motivation', '')
            summary = f"{name}: {role} - {personality} {motivation}"
            character_summaries.append(summary)
        
        # Generate prompt
        prompt = self._create_chapter_writing_prompt(
            chapter_number=chapter_number,
            chapter_title=chapter_title,
            chapter_summary=chapter_summary,
            characters=character_summaries,
            world_info=world_building,
            plot_info=plot,
            genre=genre,
            previous_content=previous_chapter_content
        )
        
        # Generate chapter content in segments to manage token limits
        try:
            logger.debug(f"Generating chapter {chapter_number} content with model {self.model_name}")
            
            # We'll generate the chapter in 2-3 segments to manage token limits
            segment_count = 3 if chapter_number == 1 else 2  # First chapter may need more context
            full_content = ""
            
            for segment in range(1, segment_count + 1):
                segment_prompt = prompt
                if segment > 1 and full_content:
                    # For subsequent segments, include previous content
                    segment_prompt = self._create_continuation_prompt(
                        previous_content=full_content,
                        chapter_summary=chapter_summary,
                        segment=segment,
                        total_segments=segment_count
                    )
                
                response = self.openai_client.generate(
                    prompt=segment_prompt,
                    model=self.model_name
                )
                
                # Handle empty response
                if not response or not response.get("content"):
                    logger.warning(f"Empty response from OpenAI for chapter {chapter_number}, segment {segment}")
                    continue
                
                # Clean up response - remove any JSON formatting that might be included
                clean_response = self._clean_chapter_content(response.get("content", ""))
                
                # Add to full content
                full_content += clean_response
                
                # If this isn't the last segment, add a section break
                if segment < segment_count:
                    full_content += "\n\n* * *\n\n"
            
            # If we didn't get any content, use fallback
            if not full_content:
                logger.warning(f"Failed to generate content for chapter {chapter_number}, using fallback")
                full_content = self._create_fallback_chapter_content(
                    chapter_number=chapter_number,
                    chapter_title=chapter_title,
                    chapter_summary=chapter_summary
                )
            
            # Create chapter data structure
            chapter_data = {
                "number": chapter_number,
                "title": chapter_title,
                "summary": chapter_summary,
                "content": full_content,
                "word_count": len(full_content.split())
            }
            
            # Save to memory
            self.memory.add_document(
                json.dumps(chapter_data),
                self.name,
                metadata={
                    "type": "chapter",
                    "chapter_number": chapter_number,
                    "chapter_title": chapter_title
                }
            )
            
            # Also save just the content as a separate document for semantic search
            self.memory.add_document(
                full_content,
                self.name,
                metadata={
                    "type": "chapter_content",
                    "chapter_number": chapter_number,
                    "chapter_title": chapter_title
                }
            )
            
            logger.info(f"Successfully wrote chapter {chapter_number} with {chapter_data['word_count']} words")
            return chapter_data
            
        except Exception as e:
            logger.error(f"Error writing chapter {chapter_number}: {str(e)}")
            
            # Create fallback chapter content
            fallback_content = self._create_fallback_chapter_content(
                chapter_number=chapter_number,
                chapter_title=chapter_title,
                chapter_summary=chapter_summary
            )
            
            fallback_chapter = {
                "number": chapter_number,
                "title": chapter_title,
                "summary": chapter_summary,
                "content": fallback_content,
                "word_count": len(fallback_content.split()),
                "is_fallback": True
            }
            
            # Save to memory
            self.memory.add_document(
                json.dumps(fallback_chapter),
                self.name,
                metadata={
                    "type": "chapter",
                    "chapter_number": chapter_number,
                    "chapter_title": chapter_title,
                    "is_fallback": True
                }
            )
            
            logger.info(f"Created fallback content for chapter {chapter_number}")
            return fallback_chapter
    
    def _create_chapter_writing_prompt(self, chapter_number, chapter_title, chapter_summary, 
                                      characters, world_info, plot_info, genre, previous_content=None) -> str:
        """Create a prompt for chapter writing."""
        previous_text = ""
        if previous_content:
            previous_text = f"""PREVIOUS CHAPTER ENDING:
{previous_content[-1000:]}

"""
        
        # Simplify world info to reduce token usage
        world_summary = ""
        if isinstance(world_info, dict):
            for key, value in world_info.items():
                if isinstance(value, str) and len(value) > 0:
                    world_summary += f"- {key}: {value[:100]}...\n"
        
        # Format character information
        characters_text = "\n".join(characters)
        
        return f"""You are a professional novelist writing a {genre} novel. 
Your task is to write Chapter {chapter_number}: "{chapter_title}".

CHAPTER SUMMARY:
{chapter_summary}

KEY CHARACTERS:
{characters_text}

WORLD BUILDING ELEMENTS:
{world_summary}

{previous_text}
WRITING INSTRUCTIONS:
1. Write a complete chapter with engaging scenes, dialogue, and description.
2. Maintain a consistent tone and style appropriate for a {genre} novel.
3. Show character emotions and development through actions and dialogue.
4. Include sensory details to bring the world to life.
5. Follow the chapter summary but feel free to add details and expand scenes.
6. Write in third-person limited perspective, focusing on the main character(s) of this chapter.
7. Aim for approximately 2,000-3,000 words.

Begin writing Chapter {chapter_number}: "{chapter_title}" now:
"""
    
    def _create_continuation_prompt(self, previous_content, chapter_summary, segment, total_segments) -> str:
        """Create a prompt for continuing chapter generation."""
        # Extract the last 1000 characters to provide context
        continuation_context = previous_content[-1000:]
        
        progress_description = ""
        if segment == 2 and total_segments == 3:
            progress_description = "middle section"
        elif segment == 2 and total_segments == 2:
            progress_description = "conclusion"
        elif segment == 3:
            progress_description = "conclusion"
        
        return f"""Continue writing the {progress_description} of this chapter.

CHAPTER SUMMARY:
{chapter_summary}

PREVIOUS CONTENT ENDING:
{continuation_context}

Continue the chapter, maintaining the same style, tone, and narrative flow:
"""
    
    def _clean_chapter_content(self, content: str) -> str:
        """Clean up the generated chapter content."""
        # Remove any JSON formatting artifacts
        if content.startswith('```') and '```' in content[3:]:
            # Extract content between triple backticks
            start = content.find('```') + 3
            end = content.find('```', start)
            if 'json' in content[3:start].lower():
                # It's a JSON code block, so parse it
                try:
                    json_str = content[start:end].strip()
                    data = json.loads(json_str)
                    if isinstance(data, dict) and "content" in data:
                        return data["content"]
                    elif isinstance(data, dict) and "chapter" in data:
                        return data["chapter"]
                    else:
                        # Return all text values concatenated
                        if isinstance(data, dict):
                            return ' '.join([v for v in data.values() if isinstance(v, str)])
                except:
                    # If parsing fails, just return the content between backticks
                    return content[start:end].strip()
            else:
                # Non-JSON code block, just extract the content
                return content[start:end].strip()
        
        # If it looks like JSON but doesn't have code blocks
        if content.startswith('{') and content.endswith('}'):
            try:
                data = json.loads(content)
                if isinstance(data, dict) and "content" in data:
                    return data["content"]
                elif isinstance(data, dict) and "chapter" in data:
                    return data["chapter"]
                else:
                    # Return all text values concatenated
                    if isinstance(data, dict):
                        return ' '.join([v for v in data.values() if isinstance(v, str)])
            except:
                # If parsing fails, return the original content
                pass
        
        return content
    
    def _create_fallback_chapter_content(self, chapter_number, chapter_title, chapter_summary) -> str:
        """Create fallback content for a chapter if generation fails."""
        return f"""# Chapter {chapter_number}: {chapter_title}

{chapter_summary}

[Note: This is placeholder content generated due to an error in chapter generation. The chapter would typically contain approximately 2,500 words of narrative content based on the summary above.]

The chapter would develop the plot points mentioned in the summary, with dialogue between characters, descriptive scenes, and narrative advancement. Character development would occur through actions and interactions, moving the overall story forward.

Key scenes would include:
- Opening scene establishing the chapter's setting and mood
- Character interactions that reveal motivations and conflicts
- Rising action that builds tension
- A pivotal moment that advances the plot
- Closing scene that transitions to the next chapter

The full chapter would be written in a style consistent with the genre and overall narrative voice of the manuscript.
"""

    def _get_integrated_data(self) -> Dict[str, Any]:
        """
        Get integrated data from memory for chapter writing.
        Returns a composite of data from all stages of the workflow.
        """
        integrated_data = {}
        
        # Get ideation data
        ideation_docs = self.memory.query_memory("type:selected_idea", agent_name="ideation_agent")
        if ideation_docs and len(ideation_docs) > 0:
            try:
                selected_idea = json.loads(ideation_docs[0]["text"])
                integrated_data["selected_idea"] = selected_idea
                integrated_data["title"] = selected_idea.get("title", "")
                integrated_data["genre"] = selected_idea.get("genre", "")
            except Exception as e:
                logger.error(f"Error parsing ideation data: {str(e)}")
        
        # Get character data
        character_docs = self.memory.query_memory("type:characters", agent_name="character_agent")
        if character_docs and len(character_docs) > 0:
            try:
                characters = json.loads(character_docs[0]["text"])
                integrated_data["characters"] = characters
            except Exception as e:
                logger.error(f"Error parsing character data: {str(e)}")
        
        # Get world data
        world_docs = self.memory.query_memory("type:world", agent_name="world_building_agent")
        if world_docs and len(world_docs) > 0:
            try:
                world_data = json.loads(world_docs[0]["text"])
                integrated_data["world_building"] = world_data
            except Exception as e:
                logger.error(f"Error parsing world data: {str(e)}")
        
        # Get plot data
        plot_docs = self.memory.query_memory("type:plot", agent_name="plot_agent") 
        if plot_docs and len(plot_docs) > 0:
            try:
                plot_data = json.loads(plot_docs[0]["text"])
                integrated_data["plot"] = plot_data
            except Exception as e:
                logger.error(f"Error parsing plot data: {str(e)}")
        
        return integrated_data 