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
        
        # Get target word count from chapter plan
        target_word_count = chapter_plan.get("word_count", None)

        # Generate prompt
        prompt = self._create_chapter_writing_prompt(
            chapter_number=chapter_number,
            chapter_title=chapter_title,
            chapter_summary=chapter_summary,
            characters=character_summaries,
            world_info=world_building,
            plot_info=plot,
            genre=genre,
            previous_content=previous_chapter_content,
            target_word_count=target_word_count
        )
        
        # Generate chapter content in segments to manage token limits
        try:
            logger.debug(f"Generating chapter {chapter_number} content with model {self.model_name}")

            # Debug: Log the prompt being sent
            logger.info(f"PROMPT DEBUG - Chapter {chapter_number} prompt length: {len(prompt)} characters")
            logger.info(f"PROMPT DEBUG - First 500 chars: {prompt[:500]}")

            # Use single-shot generation for better reliability with optimized prompts
            segment_count = 1  # Single generation for more coherent content
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

                logger.info(f"PROMPT DEBUG - Sending prompt to OpenAI: {len(segment_prompt)} chars")

                # Split the prompt into system and user parts for better structure
                system_prompt, user_prompt = self._split_prompt_for_openai(segment_prompt)

                response = self.openai_client.generate(
                    prompt=user_prompt,
                    system_prompt=system_prompt,
                    model=self.model_name,
                    max_tokens=4000,  # Increase for longer chapters
                    temperature=0.8   # Increase creativity
                )

                logger.info(f"RESPONSE DEBUG - OpenAI response keys: {list(response.keys()) if response else 'None'}")
                if response:
                    content = response.get("content") or response.get("text") or response.get("response")
                    logger.info(f"RESPONSE DEBUG - Content length: {len(content) if content else 0}")
                
                # Handle empty response - use the content variable we extracted above
                if not content:
                    logger.warning(f"Empty response from OpenAI for chapter {chapter_number}, segment {segment}")
                    continue

                # Clean up response - remove any JSON formatting that might be included
                clean_response = self._clean_chapter_content(content)

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
                                      characters, world_info, plot_info, genre, previous_content=None, target_word_count=None) -> str:
        """Create an optimized, anti-cliché prompt for chapter writing."""

        # Extract key character details more concisely
        main_character = "the protagonist"
        character_details = []

        if characters:
            for char_info in characters[:2]:  # Limit to 2 main characters
                if isinstance(char_info, str) and ":" in char_info:
                    name = char_info.split(":")[0].strip()
                    details = char_info.split(":", 1)[1].strip()
                    character_details.append(f"{name}: {details[:80]}")
                    if main_character == "the protagonist":
                        main_character = name

        # Extract essential world elements concisely
        setting_context = "an undefined location"
        if isinstance(world_info, dict):
            primary_setting = world_info.get("primary_setting", "")
            world_type = world_info.get("world_type", "")
            if primary_setting:
                setting_context = primary_setting
                if world_type:
                    setting_context += f" ({world_type})"

        # Previous content context (much shorter)
        context_note = ""
        if previous_content:
            context_note = f"\nCONTEXT: Continue from where the previous chapter ended.\nLast scene: {previous_content[-200:].strip()}\n"

        # Determine word count target
        word_count_text = "1,500-2,000 words"  # Default
        if target_word_count:
            if target_word_count <= 2000:
                word_count_text = f"approximately {target_word_count} words"
            elif target_word_count <= 4000:
                word_count_text = f"{target_word_count-500}-{target_word_count} words"
            else:
                word_count_text = f"{target_word_count-1000}-{target_word_count} words"

        return f"""Write Chapter {chapter_number}: "{chapter_title}" for this {genre} story.

CORE ELEMENTS:
• Characters: {'; '.join(character_details) if character_details else 'Develop as needed'}
• Setting: {setting_context}
• Chapter Focus: {chapter_summary}
{context_note}
CREATIVE CONSTRAINTS - AVOID THESE AI CLICHÉS:
❌ NO "mysterious figure in shadows" or "eyes that held secrets"
❌ NO "heart pounding" or "breath catching" or "time seemed to stop"
❌ NO "little did they know" or "unbeknownst to them"
❌ NO "piercing gaze" or "steely determination" or "jaw clenched"
❌ NO "storm brewing" metaphors or "darkness closing in"
❌ NO "ancient evil" or "chosen one" or "destiny calling"
❌ NO generic dialogue tags like "she breathed" or "he whispered darkly"

CREATIVE MANDATES - DO THESE INSTEAD:
✓ Use SPECIFIC, CONCRETE details instead of vague descriptions
✓ Create UNEXPECTED character reactions and dialogue
✓ Show emotions through ACTIONS and SUBTEXT, not direct statements
✓ Use FRESH metaphors and comparisons unique to your world
✓ Write dialogue that sounds like REAL PEOPLE, not exposition
✓ Focus on SENSORY details that aren't just sight and sound
✓ Create SURPRISING plot moments that still serve the story

STYLE REQUIREMENTS:
• Write {word_count_text}
• Use varied sentence structures (mix short punchy sentences with longer flowing ones)
• Show character personality through their WORD CHOICES and speech patterns
• Ground every scene in specific physical details
• Make every line of dialogue reveal character or advance plot
• End with a moment that creates anticipation for the next chapter

Write the complete chapter now. Start immediately with action or dialogue - no scene-setting paragraphs:"""
    
    def _create_continuation_prompt(self, previous_content, chapter_summary, segment, total_segments) -> str:
        """Create an optimized continuation prompt that avoids AI clichés."""

        # Get concise context from previous content
        last_scene = previous_content[-300:].strip() if previous_content else ""

        # Determine section focus
        section_focus = ""
        if segment == 2 and total_segments == 3:
            section_focus = "Develop the central conflict/tension. Deepen character dynamics."
        elif segment == 2 and total_segments == 2:
            section_focus = "Build to a compelling conclusion that sets up the next chapter."
        elif segment == 3:
            section_focus = "Conclude with impact. Create anticipation for what follows."

        return f"""Continue this chapter. {section_focus}

PREVIOUS SCENE ENDING:
{last_scene}

CONTINUE WITH THESE ANTI-CLICHÉ RULES:
❌ NO repetitive sentence structures from the previous section
❌ NO "suddenly" or "just then" transitions
❌ NO characters explaining their feelings directly
❌ NO convenient coincidences or easy solutions

✓ ESCALATE tension through character choices, not external events
✓ Use SUBTEXT in dialogue - characters say one thing, mean another
✓ Show character growth through SMALL, specific actions
✓ Create UNEXPECTED but logical developments
✓ End this section with a question or dilemma, not a resolution

Continue writing now, picking up exactly where the previous section ended:"""
    
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
        """Create creative fallback content using actual story data."""

        # Get integrated data for authentic content
        integrated_data = self._get_integrated_data()

        # Extract real character information
        characters = integrated_data.get("characters", [])
        main_char = "the protagonist"
        char_details = ""

        if isinstance(characters, list) and characters:
            char = characters[0]
            if isinstance(char, dict):
                main_char = char.get("name", "the protagonist")
                personality = char.get("personality", "")
                background = char.get("background", "")
                char_details = f" ({personality[:50]})" if personality else ""

        # Extract real world information
        world_data = integrated_data.get("world_building", {})
        setting = "an unknown place"
        setting_details = ""

        if isinstance(world_data, dict):
            primary_setting = world_data.get("primary_setting", "")
            world_type = world_data.get("world_type", "")
            if primary_setting:
                setting = primary_setting
                if world_type:
                    setting_details = f" - {world_type}"

        # Extract story theme from ideation
        story_idea = integrated_data.get("selected_idea", {})
        themes = []
        if isinstance(story_idea, dict):
            themes = story_idea.get("themes", [])

        theme_context = ""
        if themes:
            theme_context = f" The story explores themes of {', '.join(themes[:2])}."

        # Create authentic fallback content based on real story data
        return f"""# Chapter {chapter_number}: {chapter_title}

{chapter_summary}

---

{main_char}{char_details} stood in {setting}{setting_details}, facing the challenge that would define this chapter. The weight of the situation pressed against them, but not in the way stories usually describe - this was specific, personal, rooted in their own particular circumstances.

The events of this chapter unfolded according to the established plot, with {main_char} navigating the complexities of their world through actions and decisions that revealed character depth. Dialogue emerged naturally from the conflicts and relationships that had been building throughout the story.

Each scene built upon the previous chapters, advancing both plot and character development in ways that honored the story's unique voice and perspective.{theme_context}

The chapter concluded with developments that would propel the narrative forward, setting up future conflicts and character growth opportunities while maintaining the story's distinctive tone and style.

[Note: This is a story-specific placeholder. The actual chapter would contain detailed narrative based on the established characters, world, and plot elements from the previous agents' work.]
"""

    def _get_integrated_data(self) -> Dict[str, Any]:
        """
        Get integrated data from memory for chapter writing.
        Returns a composite of data from all stages of the workflow.
        """
        integrated_data = {}

        # Get ideation data - try multiple query types
        ideation_docs = self.memory.query_memory("type:selected_idea", agent_name="ideation_agent")
        if not ideation_docs:
            # Try alternative query for idea documents
            ideation_docs = self.memory.query_memory("type:idea", agent_name="ideation_agent")
        if not ideation_docs:
            # Try getting all ideation agent documents
            ideation_docs = self.memory.get_agent_memory("ideation_agent")

        if ideation_docs and len(ideation_docs) > 0:
            try:
                # Find the best idea (highest score or first one)
                best_idea = None
                for doc in ideation_docs:
                    try:
                        idea_data = json.loads(doc["text"])
                        # Check if this is an individual idea
                        if "title" in idea_data and "genre" in idea_data:
                            if best_idea is None or idea_data.get("score", 0) > best_idea.get("score", 0):
                                best_idea = idea_data
                    except json.JSONDecodeError:
                        continue

                if best_idea:
                    integrated_data["selected_idea"] = best_idea
                    integrated_data["title"] = best_idea.get("title", "")
                    integrated_data["genre"] = best_idea.get("genre", "")
                    logger.info(f"Found ideation data: {best_idea.get('title', 'Unknown')}")
            except Exception as e:
                logger.error(f"Error parsing ideation data: {str(e)}")

        # Get character data - try multiple query types
        character_docs = self.memory.query_memory("type:characters", agent_name="character_agent")
        if not character_docs:
            # Try alternative query for character documents
            character_docs = self.memory.query_memory("type:character", agent_name="character_agent")
        if not character_docs:
            # Try getting all character agent documents
            character_docs = self.memory.get_agent_memory("character_agent")

        if character_docs and len(character_docs) > 0:
            try:
                # Collect all characters
                characters = []
                for doc in character_docs:
                    try:
                        char_data = json.loads(doc["text"])
                        # Check if this is a character document
                        if "name" in char_data and "role" in char_data:
                            characters.append(char_data)
                    except json.JSONDecodeError:
                        continue

                if characters:
                    integrated_data["characters"] = characters
                    logger.info(f"Found {len(characters)} characters")
            except Exception as e:
                logger.error(f"Error parsing character data: {str(e)}")

        # Get world data
        world_docs = self.memory.query_memory("type:world", agent_name="world_building_agent")
        if not world_docs:
            # Try getting all world building agent documents
            world_docs = self.memory.get_agent_memory("world_building_agent")

        if world_docs and len(world_docs) > 0:
            try:
                # Find the main world document
                world_data = None
                for doc in world_docs:
                    try:
                        data = json.loads(doc["text"])
                        # Look for the main world document with overview
                        if "world_type" in data and "overview" in data:
                            world_data = data
                            break
                    except json.JSONDecodeError:
                        continue

                if world_data:
                    integrated_data["world_building"] = world_data
                    logger.info(f"Found world building data: {world_data.get('primary_setting', 'Unknown')}")
            except Exception as e:
                logger.error(f"Error parsing world data: {str(e)}")

        # Get plot data
        plot_docs = self.memory.query_memory("type:plot", agent_name="plot_agent")
        if not plot_docs:
            # Try getting all plot agent documents
            plot_docs = self.memory.get_agent_memory("plot_agent")

        if plot_docs and len(plot_docs) > 0:
            try:
                # Find the main plot document with chapters
                plot_data = None
                for doc in plot_docs:
                    try:
                        data = json.loads(doc["text"])
                        # Look for the main plot document with chapters
                        if "chapters" in data and isinstance(data["chapters"], list):
                            plot_data = data
                            break
                    except json.JSONDecodeError:
                        continue

                if plot_data:
                    integrated_data["plot"] = plot_data
                    logger.info(f"Found plot data with {len(plot_data.get('chapters', []))} chapters")
            except Exception as e:
                logger.error(f"Error parsing plot data: {str(e)}")

        # Get research data for additional context
        research_docs = self.memory.get_agent_memory("research_agent")
        if research_docs and len(research_docs) > 0:
            try:
                research_topics = []
                for doc in research_docs:
                    try:
                        data = json.loads(doc["text"])
                        # Look for research topics
                        if "name" in data and "description" in data:
                            research_topics.append(data)
                    except json.JSONDecodeError:
                        continue

                if research_topics:
                    integrated_data["research"] = research_topics
                    logger.info(f"Found {len(research_topics)} research topics")
            except Exception as e:
                logger.error(f"Error parsing research data: {str(e)}")

        logger.info(f"Integrated data contains: {list(integrated_data.keys())}")
        return integrated_data

    def _split_prompt_for_openai(self, full_prompt: str) -> tuple[str, str]:
        """
        Split a complex prompt into system and user parts for better OpenAI handling.

        Args:
            full_prompt: The complete prompt text

        Returns:
            Tuple of (system_prompt, user_prompt)
        """
        # Look for natural split points in the prompt
        lines = full_prompt.split('\n')

        system_parts = []
        user_parts = []
        current_section = "system"

        for line in lines:
            line = line.strip()

            # Switch to user section when we see writing instructions
            if any(keyword in line.lower() for keyword in [
                "write chapter", "begin writing", "start immediately",
                "write the complete", "continue writing"
            ]):
                current_section = "user"
                user_parts.append(line)
            # Keep constraints and guidelines in system
            elif any(keyword in line.lower() for keyword in [
                "creative constraints", "creative mandates", "style requirements",
                "avoid these", "do these instead", "core elements"
            ]):
                current_section = "system"
                system_parts.append(line)
            else:
                if current_section == "system":
                    system_parts.append(line)
                else:
                    user_parts.append(line)

        # Create clean system prompt
        system_prompt = """You are a professional novelist specializing in creative, original storytelling. Your writing is known for:

• AVOIDING AI clichés and overused tropes
• Creating UNEXPECTED but logical character reactions
• Using SPECIFIC, concrete details instead of vague descriptions
• Writing dialogue that sounds like real people
• Showing emotions through actions and subtext
• Creating fresh metaphors unique to the story world

CREATIVE CONSTRAINTS - NEVER USE:
❌ "mysterious figure in shadows" or "eyes that held secrets"
❌ "heart pounding" or "breath catching" or "time seemed to stop"
❌ "little did they know" or "unbeknownst to them"
❌ "piercing gaze" or "steely determination" or "jaw clenched"
❌ "storm brewing" metaphors or "darkness closing in"
❌ "ancient evil" or "chosen one" or "destiny calling"
❌ Generic dialogue tags like "she breathed" or "he whispered darkly"

WRITING STYLE - DYNAMIC FLOW REQUIREMENTS:
• Use varied sentence lengths and complexity for dynamic flow. Avoid predictable patterns.
• Apply perplexity and burstiness. Mix very short sentences with longer ones.
• Don't follow formulaic structures. Be unpredictable in word choices.
• Skip generic introductions and conclusions. Start with impact, not setup.
• End with energy, not summary. Avoid phrases like 'in today's world' or 'in conclusion'.
• Ground every scene in specific physical details
• Make dialogue reveal character or advance plot
• Show character personality through word choices
• Create surprising but logical developments"""

        # Create focused user prompt
        user_prompt = '\n'.join(user_parts).strip()

        # If user prompt is too short, add the essential context
        if len(user_prompt) < 200:
            user_prompt = full_prompt
            system_prompt = "You are a professional novelist. Write creative, original content that avoids AI clichés and overused tropes."

        return system_prompt, user_prompt