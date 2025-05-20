import logging
import json
from typing import Dict, Any, List, Optional, Tuple
import time
import uuid


from models.openai_client import get_openai_client
from memory.dynamic_memory import DynamicMemory
from schemas.writing_schema import WRITING_SCHEMA

logger = logging.getLogger(__name__)

class WritingAgent:
    """
    Agent responsible for generating the actual text content of the book.
    """
    
    def __init__(
        self,
        project_id: str,
        memory: DynamicMemory,
        use_openai: bool = True
    ):
        """
        Initialize the Writing Agent.
        
        Args:
            project_id: Unique identifier for the project
            memory: Dynamic memory instance
            use_openai: Whether to use OpenAI models
        """
        self.project_id = project_id
        self.memory = memory
        self.use_openai = use_openai
        
        self.openai_client = get_openai_client() if use_openai else None
        
        self.name = "writing_agent"
        self.stage = "writing"
    
    def write_chapter(
        self,
        chapter_data: Dict[str, Any],
        characters: List[Dict[str, Any]],
        world: Dict[str, Any] = None,
        research: List[Dict[str, Any]] = None,
        outline: Dict[str, Any] = None,
        previously_written_chapters: Optional[List[Dict[str, Any]]] = None,
        style_guide: Optional[Dict[str, Any]] = None,
        fallback_title: str = "Untitled Chapter"
    ) -> Dict[str, Any]:
        """
        Write a complete chapter based on the provided data.
        
        Args:
            chapter_data: Information about the chapter to write
            characters: List of character information
            world: World building information (optional)
            research: Research information (optional)
            outline: Complete story outline (optional)
            previously_written_chapters: List of previously written chapters (optional)
            style_guide: Writing style guidelines (optional)
            fallback_title: Title to use if not provided in chapter_data
            
        Returns:
            Dictionary containing the chapter content
        """
        # Set up fallbacks for optional parameters
        world = world or {}
        research = research or []
        outline = outline or {}
        previously_written_chapters = previously_written_chapters or []
        style_guide = style_guide or {}
        
        # Extract chapter information
        chapter_id = chapter_data.get("id", str(uuid.uuid4()))
        chapter_title = chapter_data.get("title", fallback_title)
        
        # Generate story context for continuity
        try:
            story_context = self._generate_story_context(
                chapter_data=chapter_data,
                characters=characters,
                world=world,
                research=research,
                outline=outline,
                previously_written_chapters=previously_written_chapters
            )
        except Exception as e:
            logger.error(f"Error generating story context: {str(e)}")
            story_context = {
                "chapter": {"id": chapter_id, "title": chapter_title},
                "book": {"title": outline.get("title", "Untitled")}
            }
            
        # Determine writing approach based on chapter complexity
        if chapter_data.get("is_complex", False) or len(characters) > 5:
            logger.info(f"Writing complex chapter {chapter_id} by scenes")
            return self._write_chapter_by_scenes(chapter_data, characters, world, story_context, style_guide)
        else:
            logger.info(f"Writing chapter {chapter_id} as single unit")
            return self._write_chapter_as_unit(chapter_data, characters, world, story_context, style_guide)
    
    def _generate_story_context(
        self, 
        chapter_data: Dict[str, Any],
        characters: List[Dict[str, Any]],
        world: Dict[str, Any],
        research: List[Dict[str, Any]],
        outline: Dict[str, Any],
        previously_written_chapters: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Generate a structured context for the current chapter to assist the writing model.
        
        Args:
            chapter_data: Information about the current chapter
            characters: List of character data
            world: World building information
            research: Research information
            outline: Complete story outline
            previously_written_chapters: Previously written chapters
            
        Returns:
            A dictionary containing structured context information
        """
        # Extract chapter information
        chapter_id = chapter_data.get("id", "")
        chapter_title = chapter_data.get("title", f"Chapter {chapter_id}")
        chapter_summary = chapter_data.get("summary", "")
        chapter_events = chapter_data.get("events", [])
        
        # Get book title and overall summary
        book_title = outline.get("title", "Untitled")
        book_summary = outline.get("summary", "")
        
        # Get previous chapter information if available
        previous_chapter_summary = ""
        if previously_written_chapters:
            # Find the most recently written chapter
            previous_chapters = [c for c in previously_written_chapters if c.get("id") != chapter_id]
            if previous_chapters:
                latest_chapter = previous_chapters[-1]
                latest_content = latest_chapter.get("content", "")
                # Create a brief summary of the last chapter - first 150 chars and last 150 chars
                if latest_content:
                    start = latest_content[:150] if len(latest_content) > 150 else latest_content
                    end = latest_content[-150:] if len(latest_content) > 150 else ""
                    previous_chapter_summary = f"Previous chapter: {latest_chapter.get('title', '')}\n\nStarting with: {start}...\n\nEnding with: {end}"
        
        # Extract relevant character information
        characters_in_chapter = []
        for character in characters:
            char_name = character.get("name", "")
            char_role = character.get("role", "")
            char_description = character.get("description", "")
            if char_name:
                # Create a condensed character description
                char_info = {
                    "name": char_name,
                    "role": char_role,
                    "description": char_description[:300] if len(char_description) > 300 else char_description
                }
                characters_in_chapter.append(char_info)
        
        # Extract relevant world information
        relevant_world_info = {}
        if isinstance(world, dict):
            # Get information about settings relevant to this chapter
            settings = world.get("settings", {})
            if settings:
                relevant_world_info["settings"] = settings
            
            # Get information about the culture and society
            culture = world.get("culture", {})
            if culture:
                relevant_world_info["culture"] = culture
            
            # Get specific environment details
            environment = world.get("environment", {})
            if environment:
                relevant_world_info["environment"] = environment
        
        # Create research information
        relevant_research = []
        if research:
            # Take the first 5 research items or fewer
            for item in research[:5]:
                topic = item.get("topic", "")
                summary = item.get("summary", "")
                if topic and summary:
                    relevant_research.append({
                        "topic": topic,
                        "summary": summary[:200] if len(summary) > 200 else summary
                    })
        
        # Create full context
        context = {
            "chapter": {
                "id": chapter_id,
                "title": chapter_title,
                "summary": chapter_summary,
                "events": chapter_events
            },
            "book": {
                "title": book_title,
                "summary": book_summary
            },
            "characters": characters_in_chapter,
            "world": relevant_world_info,
            "research": relevant_research,
            "previous_chapter": previous_chapter_summary
        }
        
        return context
    
    def _write_chapter_by_scenes(
        self,
        chapter_data: Dict[str, Any],
        characters: List[Dict[str, Any]],
        world: Dict[str, Any],
        story_context: Dict[str, Any],
        style_guide: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Write a chapter by breaking it down into individual scenes.
        
        Args:
            chapter_data: Information about the chapter
            characters: List of character data
            world: World building information
            story_context: Context information for the chapter
            style_guide: Style guidelines
            
        Returns:
            Dictionary containing the completed chapter
        """
        logger.info(f"Writing chapter {chapter_data.get('id', 'unknown')} by scenes")
        
        # Extract chapter information
        chapter_id = chapter_data.get("id", str(uuid.uuid4()))
        chapter_title = chapter_data.get("title", f"Chapter {chapter_id}")
        chapter_summary = chapter_data.get("summary", "")
        
        # Get scenes from chapter data
        scenes = chapter_data.get("scenes", [])
        
        # If no scenes are defined, create a default scene structure
        if not scenes:
            logger.warning(f"No scenes defined for chapter {chapter_id}, creating default scene structure")
            scenes = [
                {"id": f"{chapter_id}-scene-1", "description": "Opening scene of the chapter"},
                {"id": f"{chapter_id}-scene-2", "description": "Middle scene with rising action"},
                {"id": f"{chapter_id}-scene-3", "description": "Closing scene with resolution or cliffhanger"}
            ]
        
        # Write each scene
        scene_contents = []
        for i, scene in enumerate(scenes):
            scene_id = scene.get("id", f"{chapter_id}-scene-{i+1}")
            scene_description = scene.get("description", "")
            
            logger.info(f"Writing scene {i+1}/{len(scenes)} for chapter {chapter_id}")
            
            # Build the system prompt for this scene
            system_prompt = """You are an expert creative writer crafting a scene within a book chapter.
Write engaging, vivid prose that advances the story and develops characters.
Focus on 'showing, not telling' with descriptive language, authentic dialogue, and sensory details.
The scene should have a clear purpose, emotional arc, and connection to the overall chapter goal."""
            
            if style_guide:
                # Add style guide information
                tone = style_guide.get("tone", "")
                perspective = style_guide.get("perspective", "")
                tense = style_guide.get("tense", "")
                
                style_notes = f"Tone: {tone}\nPerspective: {perspective}\nTense: {tense}"
                system_prompt += f"\n\nFollow these style guidelines:\n{style_notes}"
            
            # Build the user prompt
            user_prompt = f"""Write scene {i+1} of {len(scenes)} for Chapter: {chapter_title}

Chapter Summary:
{chapter_summary}

Scene Description:
{scene_description}

Context for this scene:
- Book title: {story_context.get('book', {}).get('title', 'Untitled')}
- Previous events: {story_context.get('previous_chapter', 'No previous context')}

Characters in this scene:
{json.dumps([c for c in characters[:3]], indent=2)}

Write only this scene as polished prose, focusing on the described events and character interactions.
Do not include scene numbers, headers, or meta-information - write just the scene content.
"""
            
            try:
                # Try OpenAI first if available
                if self.use_openai and self.openai_client and self.openai_client.is_available():
                    try:
                        response = self.openai_client.generate(
                            prompt=user_prompt,
                            system_prompt=system_prompt,
                            temperature=0.7,
                            max_tokens=2000
                        )
                        
                        scene_content = response["content"]
                        logger.info(f"Generated scene {i+1} for chapter {chapter_id} using OpenAI")
                        scene_contents.append(scene_content)
                        continue
                    except Exception as e:
                        logger.warning(f"OpenAI scene generation failed: {e}, falling back to Ollama")
                
                # Fall back to Ollama
                if self.use_ollama and self.ollama_client:
                    response = self.ollama_client.generate(
                        prompt=user_prompt,
                        system=system_prompt,
                        model="deepseek-v2:16b",
                        temperature=0.7
                    )
                    
                    scene_content = response.get("response", "")
                    logger.info(f"Generated scene {i+1} for chapter {chapter_id} using Ollama")
                    scene_contents.append(scene_content)
                    continue
                
                raise Exception("No available AI service (OpenAI or Ollama) to generate scene")
                
            except Exception as e:
                logger.error(f"Scene generation error: {str(e)}")
                # Add an error placeholder for this scene
                scene_contents.append(f"[Scene {i+1} could not be generated due to an error: {str(e)}]")
        
        # Combine scenes into a full chapter
        chapter_content = "\n\n" + "\n\n".join(scene_contents)
        
        # Create the chapter object
        chapter = {
            "id": chapter_id,
            "title": chapter_title,
            "content": chapter_content,
            "scenes": scenes
        }
        
        # Store in memory
        self.memory.add_document(
            json.dumps(chapter),
            self.name,
            metadata={"type": "chapter", "chapter_id": chapter_id}
        )
        
        return chapter
    
    def _write_chapter_as_unit(
        self,
        chapter_data: Dict[str, Any],
        characters: List[Dict[str, Any]],
        world: Dict[str, Any],
        story_context: Dict[str, Any],
        style_guide: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Write a chapter as a single unit (for less complex chapters).
        
        Args:
            chapter_data: Information about the chapter
            characters: List of character data
            world: World building information
            story_context: Context information for the chapter
            style_guide: Style guidelines
            
        Returns:
            Dictionary containing the completed chapter
        """
        logger.info(f"Writing chapter {chapter_data.get('id', 'unknown')} as a single unit")
        
        # Extract chapter information
        chapter_id = chapter_data.get("id", str(uuid.uuid4()))
        chapter_title = chapter_data.get("title", f"Chapter {chapter_id}")
        chapter_summary = chapter_data.get("summary", "")
        
        # Build the system prompt
        system_prompt = """You are an expert creative writer crafting a book chapter.
Write an engaging, well-structured chapter that advances the story and develops characters.
Focus on 'showing, not telling' with descriptive language, authentic dialogue, and sensory details.
The chapter should have a clear beginning, middle, and end with proper flow and pacing."""
        
        if style_guide:
            # Add style guide information
            tone = style_guide.get("tone", "")
            perspective = style_guide.get("perspective", "")
            tense = style_guide.get("tense", "")
            
            style_notes = f"Tone: {tone}\nPerspective: {perspective}\nTense: {tense}"
            system_prompt += f"\n\nFollow these style guidelines:\n{style_notes}"
        
        # Get character information (limit to 3 most important characters)
        main_characters = characters[:3] if characters else []
        
        # Build the user prompt
        user_prompt = f"""Write Chapter: {chapter_title}

Chapter Summary:
{chapter_summary}

Story Context:
- Book title: {story_context.get('book', {}).get('title', 'Untitled')}
- Book summary: {story_context.get('book', {}).get('summary', 'No summary available')}
- Previous events: {story_context.get('previous_chapter', 'No previous context')}

Characters in this chapter:
{json.dumps(main_characters, indent=2)}

Write a complete, engaging chapter that follows this outline. Include:
1. Vivid descriptions of settings and characters
2. Meaningful dialogue that advances plot and reveals character
3. Internal thoughts and emotions where appropriate
4. Clear narrative flow
5. Pacing appropriate to the events described

The chapter should be well-structured prose with proper paragraphing.
Do not include any meta-text or explanations - write only the chapter content.
"""
        
        try:
            # Try OpenAI first if available
            if self.use_openai and self.openai_client and self.openai_client.is_available():
                try:
                    response = self.openai_client.generate(
                        prompt=user_prompt,
                        system_prompt=system_prompt,
                        temperature=0.7,
                        max_tokens=4000
                    )
                    
                    chapter_content = response["content"]
                    logger.info(f"Generated chapter {chapter_id} using OpenAI")
                    
                    # Create the chapter object
                    chapter = {
                        "id": chapter_id,
                        "title": chapter_title,
                        "content": chapter_content
                    }
                    
                    # Store in memory
                    self.memory.add_document(
                        json.dumps(chapter),
                        self.name,
                        metadata={"type": "chapter", "chapter_id": chapter_id}
                    )
                    
                    return chapter
                except Exception as e:
                    logger.warning(f"OpenAI chapter generation failed: {e}, falling back to Ollama")
            
            # Fall back to Ollama
            if self.use_ollama and self.ollama_client:
                response = self.ollama_client.generate(
                    prompt=user_prompt,
                    system=system_prompt,
                    model="deepseek-v2:16b",
                    temperature=0.7,
                    context_window=24000
                )
                
                chapter_content = response.get("response", "")
                logger.info(f"Generated chapter {chapter_id} using Ollama")
                
                # Create the chapter object
                chapter = {
                    "id": chapter_id,
                    "title": chapter_title,
                    "content": chapter_content
                }
                
                # Store in memory
                self.memory.add_document(
                    json.dumps(chapter),
                    self.name,
                    metadata={"type": "chapter", "chapter_id": chapter_id}
                )
                
                return chapter
            
            raise Exception("No available AI service (OpenAI or Ollama) to generate chapter")
            
        except Exception as e:
            logger.error(f"Chapter generation error: {str(e)}")
            
            # Create a minimal chapter structure with error message
            chapter = {
                "id": chapter_id,
                "title": chapter_title,
                "content": f"[This chapter could not be generated due to an error: {str(e)}]\n\nPlaceholder content based on the outline:\n\n{chapter_summary}"
            }
            
            # Still store this placeholder in memory
            self.memory.add_document(
                json.dumps(chapter),
                self.name,
                metadata={"type": "chapter", "chapter_id": chapter_id, "is_error_placeholder": True}
            )
            
            return chapter
    
    def rewrite_section(
        self,
        chapter_id: str,
        section_identifier: str,
        rewrite_instructions: str
    ) -> Dict[str, Any]:
        """
        Rewrite a specific section within a chapter.
        
        Args:
            chapter_id: ID of the chapter containing the section
            section_identifier: Description or excerpt identifying the section
            rewrite_instructions: Instructions for the rewrite
            
        Returns:
            Dictionary with the updated chapter
        """
        # Get the original chapter
        chapter_docs = self.memory.query_memory(f"id:{chapter_id}", agent_name=self.name)
        
        if not chapter_docs:
            raise ValueError(f"Chapter with ID {chapter_id} not found in memory")
        
        chapter_doc = chapter_docs[0]
        
        try:
            chapter_data = json.loads(chapter_doc['text'])
        except json.JSONDecodeError:
            chapter_data = {
                "id": chapter_id,
                "content": chapter_doc['text']
            }
        
        chapter_content = chapter_data.get("content", "")
        chapter_title = chapter_data.get("title", "Untitled Chapter")
        chapter_number = chapter_data.get("number", 0)
        
        # Build the system prompt
        system_prompt = """You are an expert author and editor specializing in rewriting sections of text.
Your task is to rewrite a specific section of a chapter based on the provided instructions.
The rewritten section should blend seamlessly with the rest of the chapter and maintain the same style and tone.
Your output should include only the rewritten section, not the entire chapter."""
        
        # Build the user prompt
        user_prompt = f"""Rewrite the following section of Chapter {chapter_number}: {chapter_title} according to these instructions:

{rewrite_instructions}

Section to rewrite:
{section_identifier}

Current chapter content:
{chapter_content}

Provide ONLY the rewritten section that should replace the identified section.
Ensure the rewritten section maintains consistency with the overall style and flows naturally within the chapter.
"""
        
        try:
            # Try OpenAI first if enabled
            if self.use_openai and self.openai_client:
                try:
                    response = self.openai_client.generate(
                        prompt=user_prompt,
                        system_prompt=system_prompt,
                        temperature=0.7,
                        max_tokens=2000
                    )
                    
                    rewritten_section = response["text"]
                    logger.info(f"Rewrote section in chapter {chapter_id} using OpenAI")
                    
                    # Now get instructions for integrating the section
                    integration_prompt = f"""I need to replace a section in a chapter with a rewritten version.

Original chapter:
{chapter_content}

Section to replace:
{section_identifier}

Rewritten section:
{rewritten_section}

Give me the full updated chapter content with the rewritten section properly integrated.
Just provide the full text without explanation."""
                    
                    integration_response = self.openai_client.generate(
                        prompt=integration_prompt,
                        system_prompt="You are an expert editor who helps integrate rewrites into existing text.",
                        temperature=0.3,
                        max_tokens=4000
                    )
                    
                    updated_content = integration_response["text"]
                    
                    # Update and store the chapter
                    updated_chapter = chapter_data.copy()
                    updated_chapter["content"] = updated_content
                    updated_chapter["word_count"] = len(updated_content.split())
                    
                    self._store_in_memory(updated_chapter)
                    
                    return updated_chapter
                except Exception as e:
                    logger.warning(f"OpenAI section rewrite failed: {e}, falling back to Ollama")
            
            # Fall back to Ollama if OpenAI failed or is not enabled
            if self.use_ollama and self.ollama_client:
                response = self.ollama_client.generate(
                    prompt=user_prompt,
                    system=system_prompt
                )
                
                rewritten_section = response.get("response", "")
                logger.info(f"Rewrote section in chapter {chapter_id} using Ollama")
                
                # Now get instructions for integrating the section
                integration_prompt = f"""I need to replace a section in a chapter with a rewritten version.

Original chapter:
{chapter_content}

Section to replace:
{section_identifier}

Rewritten section:
{rewritten_section}

Give me the full updated chapter content with the rewritten section properly integrated.
Just provide the full text without explanation."""
                
                integration_response = self.ollama_client.generate(
                    prompt=integration_prompt,
                    system="You are an expert editor who helps integrate rewrites into existing text."
                )
                
                updated_content = integration_response.get("response", "")
                
                # Update and store the chapter
                updated_chapter = chapter_data.copy()
                updated_chapter["content"] = updated_content
                updated_chapter["word_count"] = len(updated_content.split())
                
                self._store_in_memory(updated_chapter)
                
                return updated_chapter
            
            raise Exception("No available AI service (OpenAI or Ollama) to rewrite section")
            
        except Exception as e:
            logger.error(f"Section rewrite error: {e}")
            raise Exception(f"Failed to rewrite section: {e}")
    
    def generate_style_guide(
        self,
        book_idea: Dict[str, Any],
        sample_text: Optional[str] = None,
        style_preferences: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate a style guide for consistent writing.
        
        Args:
            book_idea: Dictionary containing the book idea
            sample_text: Optional sample text demonstrating the desired style
            style_preferences: Optional preferences for style elements
            
        Returns:
            Dictionary with the style guide
        """
        # Extract key information from book idea
        title = book_idea.get("title", "")
        genre = book_idea.get("genre", "")
        themes = book_idea.get("themes", [])
        themes_str = ", ".join(themes) if isinstance(themes, list) else themes
        
        # Build the system prompt
        system_prompt = """You are an expert literary stylist and editor.
Your task is to create a comprehensive style guide for writing a book that will maintain consistent voice, tone, and stylistic elements.
This guide will be used by AI systems to generate text with a consistent style throughout the book.
Provide output in JSON format."""
        
        # Build the user prompt in parts to avoid f-string backslash issues
        user_prompt = f"Create a detailed style guide for writing a book with the following details:\n\n"
        user_prompt += f"Title: {title}\n"
        user_prompt += f"Genre: {genre}\n"
        user_prompt += f"Themes: {themes_str}\n\n"
        
        if style_preferences:
            user_prompt += f"Style preferences:\n{json.dumps(style_preferences, indent=2)}\n\n"
            
        if sample_text:
            user_prompt += f"Sample text demonstrating the desired style:\n{sample_text}\n\n"
            
        user_prompt += "The style guide should include:\n"
        user_prompt += "1. Voice (e.g., formal, conversational, literary)\n"
        user_prompt += "2. Tone (e.g., serious, humorous, melancholic)\n"
        user_prompt += "3. Point of view (first person, third person limited, omniscient)\n"
        user_prompt += "4. Tense (past, present)\n"
        user_prompt += "5. Sentence structure preferences (e.g., varied, short and punchy, complex and flowing)\n"
        user_prompt += "6. Description style (e.g., sparse, vivid, metaphorical)\n"
        user_prompt += "7. Dialogue style (e.g., realistic, stylized, minimal)\n"
        user_prompt += "8. Specific word choices or phrases to use\n"
        user_prompt += "9. Specific word choices or phrases to avoid\n"
        user_prompt += "10. 3-5 short paragraphs exemplifying the style\n\n"
        
        user_prompt += "Respond with the style guide formatted as a JSON object in this format:\n"
        user_prompt += "{\n"
        user_prompt += '  "voice": "string",\n'
        user_prompt += '  "tone": "string",\n'
        user_prompt += '  "point_of_view": "string",\n'
        user_prompt += '  "tense": "string",\n'
        user_prompt += '  "sentence_structure": "string",\n'
        user_prompt += '  "description_style": "string",\n'
        user_prompt += '  "dialogue_style": "string",\n'
        user_prompt += '  "preferred_words": ["string"],\n'
        user_prompt += '  "avoided_words": ["string"],\n'
        user_prompt += '  "examples": ["string"],\n'
        user_prompt += '  "notes": "string"\n'
        user_prompt += "}"
        
        try:
            # Try OpenAI first if enabled
            if self.use_openai and self.openai_client:
                try:
                    response = self.openai_client.generate(
                        prompt=user_prompt,
                        system_prompt=system_prompt,
                        json_mode=True,
                        temperature=0.7,
                        max_tokens=2500
                    )
                    
                    style_guide = response["parsed_json"]
                    logger.info(f"Generated style guide using OpenAI")
                    
                    # Store in memory
                    self.memory.add_document(
                        json.dumps(style_guide),
                        self.name,
                        metadata={"type": "style_guide"}
                    )
                    
                    return style_guide
                except Exception as e:
                    logger.warning(f"OpenAI style guide generation failed: {e}, falling back to Ollama")
            
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
                    style_guide = json.loads(json_str)
                else:
                    raise ValueError("Could not extract valid JSON from Ollama response")
                
                logger.info(f"Generated style guide using Ollama")
                
                # Store in memory
                self.memory.add_document(
                    json.dumps(style_guide),
                    self.name,
                    metadata={"type": "style_guide"}
                )
                
                return style_guide
            
            raise Exception("No available AI service (OpenAI or Ollama) to generate style guide")
            
        except Exception as e:
            logger.error(f"Style guide generation error: {e}")
            raise Exception(f"Failed to generate style guide: {e}")
    
    def _store_in_memory(self, chapter: Dict[str, Any]) -> None:
        """
        Store written chapter in memory.
        
        Args:
            chapter: Dictionary with written chapter
        """
        # Store chapter
        self.memory.add_document(
            json.dumps(chapter),
            self.name,
            metadata={
                "type": "chapter",
                "id": chapter.get("id", "unknown"),
                "number": chapter.get("number", 0),
                "title": chapter.get("title", "Untitled")
            }
        )
    
    def get_all_written_chapters(self) -> List[Dict[str, Any]]:
        """
        Get all written chapters from memory.
        
        Returns:
            List of dictionaries with written chapters
        """
        # Query for all chapters in memory
        chapter_docs = self.memory.get_agent_memory(self.name)
        
        if not chapter_docs:
            return []
        
        # Filter for chapters
        chapters = []
        
        for doc in chapter_docs:
            metadata = doc.get('metadata', {})
            if metadata.get('type') == 'chapter':
                try:
                    chapter = json.loads(doc['text'])
                    chapters.append(chapter)
                except json.JSONDecodeError:
                    continue
        
        # Sort by chapter number
        chapters.sort(key=lambda x: x.get("number", 0))
        
        return chapters
    
    def get_style_guide(self) -> Optional[Dict[str, Any]]:
        """
        Get the style guide from memory.
        
        Returns:
            Dictionary with style guide or None if not found
        """
        # Query for style guide in memory
        style_docs = self.memory.query_memory("type:style_guide", agent_name=self.name)
        
        if not style_docs:
            return None
        
        try:
            return json.loads(style_docs[0]['text'])
        except (json.JSONDecodeError, IndexError):
            return None
