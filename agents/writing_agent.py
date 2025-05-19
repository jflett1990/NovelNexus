import logging
import json
from typing import Dict, Any, List, Optional, Tuple
import time

from models.ollama_client import get_ollama_client
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
        use_openai: bool = True,
        use_ollama: bool = True
    ):
        """
        Initialize the Writing Agent.
        
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
        
        self.name = "writing_agent"
        self.stage = "writing"
    
    def write_chapter(
        self,
        chapter_data: Dict[str, Any],
        characters: List[Dict[str, Any]],
        world_data: Dict[str, Any],
        previously_written_chapters: Optional[List[Dict[str, Any]]] = None,
        style_guide: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Write a complete chapter based on the outline and related information.
        
        Args:
            chapter_data: Dictionary containing the chapter outline
            characters: List of character dictionaries
            world_data: Dictionary with world building data
            previously_written_chapters: Optional list of previously written chapters
            style_guide: Optional style guide for writing
            
        Returns:
            Dictionary with the written chapter
        """
        logger.info(f"Writing chapter {chapter_data.get('id', 'unknown')} for project {self.project_id}")
        
        # Extract key information from chapter data
        chapter_id = chapter_data.get("id", "unknown")
        chapter_number = chapter_data.get("number", 0)
        chapter_title = chapter_data.get("title", "Untitled Chapter")
        chapter_summary = chapter_data.get("summary", "")
        
        # Extract scenes if available
        scenes = chapter_data.get("scenes", [])
        scenes_text = ""
        if scenes:
            scenes_text = "\n\n".join([
                f"Scene {i+1}: {scene.get('summary', '')}" for i, scene in enumerate(scenes)
            ])
        
        # Prepare character information
        characters_text = ""
        featured_characters = chapter_data.get("featured_characters", [])
        if featured_characters and characters:
            # Filter to just featured characters
            relevant_characters = [char for char in characters if char.get("name", "") in featured_characters]
            
            if relevant_characters:
                char_summaries = []
                for char in relevant_characters:
                    name = char.get("name", "Unknown")
                    desc = char.get("brief_description", "")
                    voice = char.get("voice", "")
                    char_summaries.append(f"- {name}: {desc}" + "\n" + f"Voice: {voice}")
                
                characters_text = "\n".join(char_summaries)
        
        # Extract previous chapter summaries if available
        previous_chapters_text = ""
        if previously_written_chapters:
            # Only include the last 3 chapters to avoid overwhelming the model
            recent_chapters = previously_written_chapters[-3:]
            summaries = []
            for i, prev_chapter in enumerate(recent_chapters):
                prev_num = prev_chapter.get("number", 0)
                prev_title = prev_chapter.get("title", "Untitled")
                prev_summary = prev_chapter.get("summary", "")
                summaries.append(f"Chapter {prev_num}: {prev_title}" + "\n" + f"{prev_summary}")
            
            previous_chapters_text = "\n\n".join(summaries)
        
        # Extract style information if available
        style_text = ""
        if style_guide:
            voice = style_guide.get("voice", "")
            tone = style_guide.get("tone", "")
            pov = style_guide.get("point_of_view", "")
            tense = style_guide.get("tense", "")
            
            style_text = f"Voice: {voice}\nTone: {tone}\nPoint of View: {pov}\nTense: {tense}"
            
            if "examples" in style_guide:
                style_text += "\n\nStyle Examples:\n" + "\n".join(style_guide["examples"])
        
        # Build the system prompt
        system_prompt = """You are an expert author capable of writing engaging, high-quality book chapters.
Your task is to write a complete chapter based on the provided outline, characters, and world details.
The writing should be professional quality, with natural dialogue, vivid descriptions, and compelling narrative.
Match any specified style guidelines and maintain consistency with previously written chapters.
Your output should be ready-to-read prose that requires minimal editing."""
        
        # Build the user prompt
        # Build the prompt in parts to avoid f-string backslash issues
        user_prompt = f"Write Chapter {chapter_number}: {chapter_title} based on the following outline:\n\n"
        user_prompt += f"Chapter Summary:\n{chapter_summary}\n\n"
        
        if scenes_text:
            user_prompt += f"Scenes:\n{scenes_text}\n\n"
            
        if characters_text:
            user_prompt += f"Featured Characters:\n{characters_text}\n\n"
            
        if previous_chapters_text:
            user_prompt += f"Previously Written Chapters:\n{previous_chapters_text}\n\n"
            
        if style_text:
            user_prompt += f"Style Guidelines:\n{style_text}\n\n"
            
        user_prompt += f"World/Setting Context:\n{world_data.get('primary_setting', 'Unknown setting')}, {world_data.get('time_period', 'Unknown time period')}\n\n"
        user_prompt += "Write a complete, engaging chapter that follows this outline.\n"
        user_prompt += "Include natural dialogue, vivid descriptions, and compelling narrative development.\n"
        user_prompt += "The chapter should advance the plot while developing characters and themes."
        
        try:
            # Generate chapter in parts if needed
            if scenes and len(scenes) > 3:
                # For chapters with many scenes, generate each scene separately
                return self._write_chapter_by_scenes(
                    chapter_data, characters, world_data, previously_written_chapters, style_guide
                )
            
            # Try OpenAI first if enabled
            if self.use_openai and self.openai_client:
                try:
                    response = self.openai_client.generate(
                        prompt=user_prompt,
                        system_prompt=system_prompt,
                        temperature=0.7,
                        max_tokens=4000
                    )
                    
                    chapter_text = response["text"]
                    logger.info(f"Generated chapter {chapter_id} using OpenAI")
                    
                    # Store the complete chapter
                    written_chapter = {
                        "id": chapter_id,
                        "number": chapter_number,
                        "title": chapter_title,
                        "content": chapter_text,
                        "word_count": len(chapter_text.split()),
                        "summary": chapter_summary
                    }
                    
                    self._store_in_memory(written_chapter)
                    
                    return written_chapter
                except Exception as e:
                    logger.warning(f"OpenAI chapter writing failed: {e}, falling back to Ollama")
            
            # Fall back to Ollama if OpenAI failed or is not enabled
            if self.use_ollama and self.ollama_client:
                response = self.ollama_client.generate(
                    prompt=user_prompt,
                    system=system_prompt
                )
                
                chapter_text = response.get("response", "")
                logger.info(f"Generated chapter {chapter_id} using Ollama")
                
                # Store the complete chapter
                written_chapter = {
                    "id": chapter_id,
                    "number": chapter_number,
                    "title": chapter_title,
                    "content": chapter_text,
                    "word_count": len(chapter_text.split()),
                    "summary": chapter_summary
                }
                
                self._store_in_memory(written_chapter)
                
                return written_chapter
            
            raise Exception("No available AI service (OpenAI or Ollama) to write chapter")
            
        except Exception as e:
            logger.error(f"Chapter writing error: {e}")
            raise Exception(f"Failed to write chapter: {e}")
    
    def _write_chapter_by_scenes(
        self,
        chapter_data: Dict[str, Any],
        characters: List[Dict[str, Any]],
        world_data: Dict[str, Any],
        previously_written_chapters: Optional[List[Dict[str, Any]]] = None,
        style_guide: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Write a chapter by generating each scene separately and combining them.
        
        Args:
            chapter_data: Dictionary containing the chapter outline
            characters: List of character dictionaries
            world_data: Dictionary with world building data
            previously_written_chapters: Optional list of previously written chapters
            style_guide: Optional style guide for writing
            
        Returns:
            Dictionary with the written chapter
        """
        chapter_id = chapter_data.get("id", "unknown")
        chapter_number = chapter_data.get("number", 0)
        chapter_title = chapter_data.get("title", "Untitled Chapter")
        chapter_summary = chapter_data.get("summary", "")
        scenes = chapter_data.get("scenes", [])
        
        logger.info(f"Writing chapter {chapter_id} by scenes (total: {len(scenes)} scenes)")
        
        # Extract style information if available
        style_text = ""
        if style_guide:
            voice = style_guide.get("voice", "")
            tone = style_guide.get("tone", "")
            pov = style_guide.get("point_of_view", "")
            tense = style_guide.get("tense", "")
            
            style_text = f"Voice: {voice}\nTone: {tone}\nPoint of View: {pov}\nTense: {tense}"
        
        # Generate each scene
        scene_contents = []
        for i, scene in enumerate(scenes):
            scene_summary = scene.get("summary", "")
            scene_characters = scene.get("characters", [])
            scene_location = scene.get("location", "")
            
            # Get character information for this scene
            scene_character_text = ""
            if scene_characters and characters:
                relevant_characters = [char for char in characters if char.get("name", "") in scene_characters]
                
                if relevant_characters:
                    char_summaries = []
                    for char in relevant_characters:
                        name = char.get("name", "Unknown")
                        desc = char.get("brief_description", "")
                        char_summaries.append(f"- {name}: {desc}")
                    
                    scene_character_text = "\n".join(char_summaries)
            
            # Build the system prompt for this scene
            system_prompt = """You are an expert author writing a scene for a book chapter.
Write a vivid, engaging scene that follows the provided scene outline and fits within the larger chapter context.
Include natural dialogue, rich descriptions, and compelling character interactions.
Match the specified style guidelines and maintain narrative consistency."""
            
            # Build the user prompt for this scene in parts to avoid f-string backslash issues
            user_prompt = f"Write Scene {i+1} for Chapter {chapter_number}: {chapter_title}\n\n"
            user_prompt += f"Chapter Context:\n{chapter_summary}\n\n"
            user_prompt += f"Scene Summary:\n{scene_summary}\n\n"
            
            if scene_location:
                user_prompt += f"Scene Location: {scene_location}\n\n"
                
            if scene_character_text:
                user_prompt += f"Characters in this scene:\n{scene_character_text}\n\n"
                
            if style_text:
                user_prompt += f"Style Guidelines:\n{style_text}\n\n"
                
            user_prompt += "Write this scene with natural dialogue, vivid descriptions, and compelling narrative.\n"
            user_prompt += "The scene should flow naturally and advance the chapter's goals."
            
            try:
                scene_text = ""
                
                # Try OpenAI first if enabled
                if self.use_openai and self.openai_client:
                    try:
                        response = self.openai_client.generate(
                            prompt=user_prompt,
                            system_prompt=system_prompt,
                            temperature=0.7,
                            max_tokens=3000
                        )
                        
                        scene_text = response["text"]
                        logger.info(f"Generated scene {i+1} for chapter {chapter_id} using OpenAI")
                    except Exception as e:
                        logger.warning(f"OpenAI scene writing failed: {e}, falling back to Ollama")
                
                # Fall back to Ollama if OpenAI failed or is not enabled
                if (not scene_text) and self.use_ollama and self.ollama_client:
                    response = self.ollama_client.generate(
                        prompt=user_prompt,
                        system=system_prompt
                    )
                    
                    scene_text = response.get("response", "")
                    logger.info(f"Generated scene {i+1} for chapter {chapter_id} using Ollama")
                
                if scene_text:
                    scene_contents.append(scene_text)
                else:
                    raise Exception("No available AI service to write scene")
                
                # Small delay to avoid rate limits
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Scene writing error for scene {i+1}: {e}")
                scene_contents.append(f"[Error generating scene {i+1}: {str(e)}]")
        
        # Combine all scenes into a complete chapter
        chapter_text = "\n\n".join(scene_contents)
        
        # Add transitions if needed
        if len(scene_contents) > 1:
            transition_prompt = f"""I have written Chapter {chapter_number}: {chapter_title} as separate scenes.
Please create smooth transitions between these scenes to make the chapter flow naturally as a cohesive whole.
Return ONLY the transitions text, numbered by which scenes they connect (e.g., "1-2: [transition text]")."""
            
            try:
                transitions = {}
                
                if self.use_openai and self.openai_client:
                    response = self.openai_client.generate(
                        prompt=transition_prompt + "\n\n" + chapter_text,
                        system_prompt="You are an expert editor who creates smooth transitions between scenes in a book chapter.",
                        temperature=0.7,
                        max_tokens=1500
                    )
                    
                    transition_text = response["text"]
                    
                    # Parse transitions
                    for line in transition_text.split("\n"):
                        if ":" in line and "-" in line.split(":")[0]:
                            try:
                                key, value = line.split(":", 1)
                                scene_nums = key.strip().split("-")
                                if len(scene_nums) == 2:
                                    start = int(scene_nums[0]) - 1
                                    transitions[start] = value.strip()
                            except (ValueError, IndexError):
                                continue
                
                # Apply transitions to the chapter
                if transitions:
                    new_scene_contents = []
                    for i, scene in enumerate(scene_contents):
                        new_scene_contents.append(scene)
                        if i in transitions:
                            new_scene_contents.append(transitions[i])
                    
                    chapter_text = "\n\n".join(new_scene_contents)
            except Exception as e:
                logger.warning(f"Failed to create transitions: {e}")
        
        # Store the complete chapter
        written_chapter = {
            "id": chapter_id,
            "number": chapter_number,
            "title": chapter_title,
            "content": chapter_text,
            "word_count": len(chapter_text.split()),
            "summary": chapter_summary
        }
        
        self._store_in_memory(written_chapter)
        
        return written_chapter
    
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
