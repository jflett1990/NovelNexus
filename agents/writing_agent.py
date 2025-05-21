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
        Write a chapter by breaking it into scenes.
        
        Args:
            chapter_data: Information about the chapter
            characters: List of character information
            world: World building information
            story_context: Structured context for the chapter
            style_guide: Writing style guidelines
            
        Returns:
            Dictionary containing the chapter content
        """
        # Extract necessary info
        chapter_id = chapter_data.get("id", str(uuid.uuid4()))
        chapter_title = chapter_data.get("title", f"Chapter {chapter_id}")
        chapter_events = chapter_data.get("events", [])
        num_scenes = chapter_data.get("num_scenes", 3)
        
        # Use events to determine scenes if available, otherwise use num_scenes
        scenes = []
        if chapter_events:
            # Create a scene for each event or group of events
            # Split events into num_scenes scenes
            events_per_scene = max(1, len(chapter_events) // num_scenes)
            for i in range(0, len(chapter_events), events_per_scene):
                scene_events = chapter_events[i:i+events_per_scene]
                scenes.append({
                    "scene_index": i // events_per_scene,
                    "events": scene_events
                })
        else:
            # If no events specified, create empty scenes
            for i in range(num_scenes):
                scenes.append({
                    "scene_index": i,
                    "events": []
                })
        
        # Generate each scene
        scene_texts = []
        scene_descriptions = []
        for i, scene in enumerate(scenes):
            try:
                # Create scene context
                scene_context = story_context.copy()
                scene_context["scene"] = {
                    "index": i + 1,
                    "events": scene.get("events", []),
                    "total_scenes": len(scenes)
                }
                
                # Create the prompt
                scene_prompt = self._create_scene_writing_prompt(
                    story_context=scene_context,
                    characters=characters,
                    world=world,
                    style_guide=style_guide,
                    scene_index=i,
                    total_scenes=len(scenes)
                )
                
                # Generate the scene text
                try:
                    response = self.openai_client.generate(
                        prompt=scene_prompt,
                        model="gpt-4o"
                    )
                    
                    scene_text = response.get("content", "").strip()
                    logger.info(f"Generated scene {i+1} for chapter {chapter_id} using OpenAI")
                except Exception as e:
                    logger.error(f"Error generating scene with OpenAI: {str(e)}")
                    scene_text = f"[Scene {i+1} content placeholder]"
                    
                # Add scene to the list
                if scene_text:
                    scene_texts.append(scene_text)
                    scene_descriptions.append(f"Scene {i+1}: {scene.get('events', [])}")
                
            except Exception as e:
                logger.error(f"Error generating scene {i+1}: {str(e)}")
                scene_texts.append(f"[Error generating scene {i+1}]")
        
        # Combine all scenes into the full chapter
        chapter_content = "\n\n".join(scene_texts)
        
        # Build chapter metadata
        chapter_result = {
            "id": chapter_id,
            "title": chapter_title,
            "content": chapter_content,
            "scenes": scene_descriptions,
            "metadata": {
                "approach": "scene_based",
                "scene_count": len(scenes),
                "wordcount": len(chapter_content.split())
            }
        }
        
        # Store in memory
        self._store_in_memory(chapter_result)
        
        return chapter_result
    
    def _write_chapter_as_unit(
        self,
        chapter_data: Dict[str, Any],
        characters: List[Dict[str, Any]],
        world: Dict[str, Any],
        story_context: Dict[str, Any],
        style_guide: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Write a chapter as a single unit without breaking into scenes.
        
        Args:
            chapter_data: Information about the chapter
            characters: List of character information
            world: World building information
            story_context: Structured context for the chapter
            style_guide: Writing style guidelines
            
        Returns:
            Dictionary containing the chapter content
        """
        # Extract chapter information
        chapter_id = chapter_data.get("id", str(uuid.uuid4()))
        chapter_title = chapter_data.get("title", f"Chapter {chapter_id}")
        
        # Create the prompt
        chapter_prompt = self._create_chapter_writing_prompt(
            story_context=story_context,
            characters=characters,
            world=world,
            style_guide=style_guide
        )
        
        # Generate the chapter content
        try:
            response = self.openai_client.generate(
                prompt=chapter_prompt,
                model="gpt-4o"
            )
            
            chapter_content = response.get("content", "").strip()
            logger.info(f"Generated chapter {chapter_id} using OpenAI")
        except Exception as e:
            logger.error(f"Error generating chapter with OpenAI: {str(e)}")
            chapter_content = f"[Chapter {chapter_title} content placeholder]"
        
        # Build chapter metadata
        chapter_result = {
            "id": chapter_id,
            "title": chapter_title,
            "content": chapter_content,
            "metadata": {
                "approach": "single_unit",
                "wordcount": len(chapter_content.split())
            }
        }
        
        # Store in memory
        self._store_in_memory(chapter_result)
        
        return chapter_result
    
    def rewrite_section(
        self,
        chapter_id: str,
        section_identifier: str,
        rewrite_instructions: str
    ) -> Dict[str, Any]:
        """
        Rewrite a specific section of a chapter based on instructions.
        
        Args:
            chapter_id: ID of the chapter to rewrite
            section_identifier: Text identifier for the section (e.g., first paragraph or specific text)
            rewrite_instructions: Instructions for the rewrite
            
        Returns:
            Dictionary with the rewritten section and metadata
        """
        logger.info(f"Rewriting section in chapter {chapter_id}")
        
        # Fetch the chapter from memory
        chapter_documents = self.memory.query(
            f"chapter_id:{chapter_id}",
            collection=self.name,
            limit=1
        )
        
        if not chapter_documents:
            logger.error(f"Chapter {chapter_id} not found in memory")
            return {"error": f"Chapter {chapter_id} not found"}
        
        try:
            # Get the chapter content
            chapter_data = json.loads(chapter_documents[0].page_content)
            chapter_content = chapter_data.get("content", "")
            chapter_title = chapter_data.get("title", f"Chapter {chapter_id}")
            
            # Build the prompt for rewriting
            rewrite_prompt = f"""You are a skilled editor and creative writer working on a manuscript revision.

ORIGINAL CHAPTER: {chapter_title}

SECTION TO REVISE: {section_identifier}

REVISION INSTRUCTIONS: {rewrite_instructions}

CURRENT TEXT:
{chapter_content}

Please revise the specific section identified above according to the revision instructions. Return only the revised text for that section, maintaining the style and flow of the rest of the chapter.

REVISED SECTION:"""
            
            try:
                # Generate the rewritten section
                response = self.openai_client.generate(
                    prompt=rewrite_prompt,
                    model="gpt-4o"
                )
                
                rewritten_section = response.get("content", "").strip()
                logger.info(f"Rewrote section in chapter {chapter_id} using OpenAI")
            except Exception as e:
                logger.error(f"Error rewriting section with OpenAI: {str(e)}")
                return {"error": f"Error rewriting section: {str(e)}"}
            
            # Return the rewritten section
            return {
                "chapter_id": chapter_id,
                "original_section": section_identifier,
                "rewritten_section": rewritten_section,
                "instructions": rewrite_instructions
            }
            
        except Exception as e:
            logger.error(f"Error processing chapter for rewriting: {str(e)}")
            return {"error": f"Error processing chapter: {str(e)}"}
    
    def generate_style_guide(
        self,
        book_idea: Dict[str, Any],
        sample_text: Optional[str] = None,
        style_preferences: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate a style guide for the book with consistent guidelines.
        
        Args:
            book_idea: Basic information about the book
            sample_text: Optional sample text to base style on
            style_preferences: Optional user preferences for style
            
        Returns:
            Dictionary with style guidelines
        """
        # Create the style guide generation prompt
        genre = book_idea.get("genre", "")
        audience = book_idea.get("target_audience", "general")
        title = book_idea.get("title", "")
        setting = book_idea.get("setting", "")
        era = book_idea.get("era", "contemporary")
        
        # Additional style preferences
        preferences = {}
        if style_preferences:
            preferences = style_preferences
        
        style_prompt = f"""Generate a comprehensive style guide for a {genre} book titled "{title}".

BOOK DETAILS:
- Genre: {genre}
- Target audience: {audience}
- Setting: {setting}
- Era: {era}

STYLE PREFERENCES:
{json.dumps(preferences, indent=2) if preferences else "No specific preferences provided."}

{"SAMPLE TEXT (maintain similar style):" + sample_text if sample_text else ""}

Create a detailed style guide with these sections:
1. Voice and Tone
2. Point of View (First person, third person, etc.)
3. Tense (Past, present)
4. Dialogue Style
5. Description Style
6. Pacing Guidelines
7. Language Formality
8. Vocabulary Range

FORMAT THE RESPONSE AS VALID JSON with the following structure:
{{
  "voice_and_tone": "Description of the overall voice and tone",
  "point_of_view": "Recommended POV",
  "tense": "Recommended tense",
  "dialogue_style": "Guidelines for dialogue",
  "description_style": "Guidelines for descriptive passages",
  "pacing": "Pacing recommendations",
  "language_formality": "Level of formality",
  "vocabulary_range": "Vocabulary guidelines"
}}"""

        try:
            # Generate the style guide
            response = self.openai_client.generate(
                prompt=style_prompt,
                model="gpt-4o",
                format="json"
            )
            
            # Extract the style guide content
            try:
                content = response.get("content", "{}")
                style_guide = json.loads(content)
                logger.info(f"Generated style guide for project {self.project_id}")
            except json.JSONDecodeError:
                logger.error(f"Error parsing style guide JSON response")
                # Create a minimal style guide
                style_guide = {
                    "voice_and_tone": "Balanced and natural",
                    "point_of_view": "Third person limited",
                    "tense": "Past tense",
                    "dialogue_style": "Natural and character-appropriate",
                    "description_style": "Vivid but concise",
                    "pacing": "Varied based on scene tension",
                    "language_formality": "Moderately formal",
                    "vocabulary_range": "Accessible with occasional specialized terms"
                }
            
            # Store the style guide in memory
            self.memory.add_document(
                json.dumps(style_guide),
                self.name,
                metadata={
                    "type": "style_guide", 
                    "project_id": self.project_id
                }
            )
            
            return style_guide
            
        except Exception as e:
            logger.error(f"Error generating style guide: {str(e)}")
            # Return a default style guide
            default_style = {
                "voice_and_tone": "Balanced and natural",
                "point_of_view": "Third person limited",
                "tense": "Past tense",
                "dialogue_style": "Natural and character-appropriate",
                "description_style": "Vivid but concise",
                "pacing": "Varied based on scene tension",
                "language_formality": "Moderately formal",
                "vocabulary_range": "Accessible with occasional specialized terms"
            }
            return default_style
    
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
