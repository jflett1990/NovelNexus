import logging
import json
from typing import Dict, Any, List, Optional


from models.openai_client import get_openai_client
from memory.dynamic_memory import DynamicMemory
from schemas.outline_schema import OUTLINE_SCHEMA

logger = logging.getLogger(__name__)

class OutlineAgent:
    """
    Agent responsible for creating a detailed outline of the book.
    """
    
    def __init__(
        self,
        project_id: str,
        memory: DynamicMemory,
        use_openai: bool = True
    ):
        """
        Initialize the Outline Agent.
        
        Args:
            project_id: Unique identifier for the project
            memory: Dynamic memory instance
            use_openai: Whether to use OpenAI models
        """
        self.project_id = project_id
        self.memory = memory
        self.use_openai = use_openai
        
        self.openai_client = get_openai_client() if use_openai else None
        
        self.name = "outline_agent"
        self.stage = "outlining"
    
    def generate_outline(
        self,
        book_idea: Dict[str, Any],
        characters: List[Dict[str, Any]],
        world_data: Dict[str, Any],
        research_data: Optional[Dict[str, Any]] = None,
        complexity: str = "medium",
        target_word_count: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Generate a detailed outline for the book.
        
        Args:
            book_idea: Dictionary containing the book idea
            characters: List of character dictionaries
            world_data: Dictionary with world building data
            research_data: Optional dictionary with research data
            complexity: Complexity level (low, medium, high)
            target_word_count: Optional target word count for the book
            
        Returns:
            Dictionary with the generated outline
        """
        logger.info(f"Generating outline for project {self.project_id}")
        
        # Extract key information from book idea
        title = book_idea.get("title", "")
        genre = book_idea.get("genre", "")
        themes = book_idea.get("themes", [])
        themes_str = ", ".join(themes) if isinstance(themes, list) else themes
        plot_summary = book_idea.get("plot_summary", "")
        
        # Build the system prompt
        system_prompt = """You are an expert book outliner and story structure specialist.
Your task is to create a detailed, comprehensive outline for a book that includes the overall structure, chapters, scenes,
character arcs, and narrative progression from beginning to end.
The outline should balance creativity and structural soundness, providing a solid foundation for writing.
Provide output in JSON format according to the provided schema."""
        
        # Build information for the prompt
        chars_summary = []
        for char in characters[:5]:  # Limit to top 5 characters to avoid overloading
            name = char.get("name", "Unknown")
            role = char.get("role", "Unknown")
            brief = char.get("brief_description", "")
            chars_summary.append(f"- {name} ({role}): {brief}")
        
        chars_text = "\n".join(chars_summary)
        
        # World data summary
        world_type = world_data.get("world_type", "")
        setting = world_data.get("primary_setting", "")
        time_period = world_data.get("time_period", "")
        
        world_text = f"World Type: {world_type}\nPrimary Setting: {setting}\nTime Period: {time_period}"
        
        # Research summary
        research_text = ""
        if research_data and "topics" in research_data:
            research_topics = []
            for topic in research_data["topics"][:5]:  # Limit to top 5 topics
                name = topic.get("name", "Unknown")
                desc = topic.get("description", "")
                research_topics.append(f"- {name}: {desc}")
            
            research_text = "\n".join(research_topics)
        
        # Target word count info
        word_count_text = ""
        if target_word_count:
            word_count_text = f"\nThe target word count is approximately {target_word_count} words."
        
        # Build the user prompt
        user_prompt = f"""Create a detailed book outline for a work with the following details:

Title: {title}
Genre: {genre}
Themes: {themes_str}
Plot Summary: {plot_summary}
{word_count_text}

Key Characters:
{chars_text}

World/Setting:
{world_text}

Research Topics:
{research_text}

The outline should have {complexity} complexity level of detail.
Structure the book with a clear beginning, middle, and end, with well-defined acts and chapters.
Include character arcs, plot progression, key scenes, and important story beats.
Ensure the outline is comprehensive enough to guide the writing process from start to finish.

Respond with the outline formatted according to this JSON schema: {json.dumps(OUTLINE_SCHEMA)}
"""
        
        try:
            # Try OpenAI first if enabled
            if self.use_openai and self.openai_client:
                try:
                    response = self.openai_client.generate(
                        prompt=user_prompt,
                        system_prompt=system_prompt,
                        json_mode=True,
                        temperature=0.7,
                        max_tokens=4000
                    )
                    
                    outline = response["parsed_json"]
                    logger.info(f"Generated outline with {len(outline.get('chapters', []))} chapters using OpenAI")
                    
                    # Store in memory
                    self._store_in_memory(outline)
                    
                    return outline
                except Exception as e:
                    logger.warning(f"OpenAI outline generation failed: {e}")
            
            # If the OpenAI API call failed or isn't available, generate a fallback outline
            logger.warning("Using fallback outline generation")
            fallback_outline = self._generate_fallback_outline(book_idea, characters, world_data)
            
            # Store in memory
            self._store_in_memory(fallback_outline)
            
            return fallback_outline
            
        except Exception as e:
            logger.error(f"Outline generation error: {e}")
            # Generate fallback outline as a last resort
            fallback_outline = self._generate_fallback_outline(book_idea, characters, world_data)
            
            # Store in memory
            self._store_in_memory(fallback_outline)
            
            return fallback_outline
    
    def _generate_fallback_outline(
        self, 
        book_idea: Dict[str, Any],
        characters: List[Dict[str, Any]],
        world_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate a fallback outline when API calls fail.
        
        Args:
            book_idea: Dictionary containing the book idea
            characters: List of character dictionaries
            world_data: Dictionary with world building data
            
        Returns:
            Dictionary with a basic outline structure
        """
        title = book_idea.get("title", "Untitled Book")
        genre = book_idea.get("genre", "fiction").lower()
        plot_summary = book_idea.get("plot_summary", "A compelling story of transformation and discovery.")
        
        # Create a standard three-act structure
        act1_desc = "Introduction of characters and setting. Establishes the normal world before disruption."
        act2_desc = "Characters face challenges and grow. Raises the stakes and develops relationships."
        act3_desc = "Climactic resolution of conflicts. Characters achieve transformation and resolution."
        
        # Create a simple chapter structure based on genre
        chapter_count = 5  # Default for a short story
        
        chapters = []
        character_names = []
        
        # Get main character names if available
        for char in characters[:3]:
            if "name" in char and char["name"]:
                character_names.append(char["name"])
        
        # If no character names available, use generic placeholders
        if not character_names:
            character_names = ["Protagonist", "Supporting Character", "Antagonist"]
        
        main_character = character_names[0] if character_names else "Protagonist"
        
        # Simple setting description
        setting = world_data.get("primary_setting", "the story world")
        
        # Create genre-specific chapter outlines
        if "fantasy" in genre:
            chapters = [
                {
                    "id": "chapter_1",
                    "title": "The Ordinary World",
                    "summary": f"Introduction to {main_character} and {setting}. Establishes the normal life before adventure begins.",
                    "pov_character": main_character,
                    "scenes": [
                        {"description": f"{main_character}'s daily life and routine.", "purpose": "Character introduction"},
                        {"description": "First hints of the magical elements or coming adventure.", "purpose": "Foreshadowing"}
                    ]
                },
                {
                    "id": "chapter_2",
                    "title": "The Call to Adventure",
                    "summary": f"{main_character} encounters something unusual that disrupts normal life.",
                    "pov_character": main_character,
                    "scenes": [
                        {"description": "Inciting incident that changes everything.", "purpose": "Plot catalyst"},
                        {"description": "Character's reaction to the new situation.", "purpose": "Character development"}
                    ]
                },
                {
                    "id": "chapter_3",
                    "title": "Entering the Unknown",
                    "summary": f"{main_character} ventures into new territory, facing initial challenges.",
                    "pov_character": main_character,
                    "scenes": [
                        {"description": "First real challenge or obstacle.", "purpose": "Rising action"},
                        {"description": "Meeting allies or mentors.", "purpose": "Expanding cast"}
                    ]
                },
                {
                    "id": "chapter_4",
                    "title": "Confrontation",
                    "summary": "Major confrontation with antagonistic forces.",
                    "pov_character": main_character,
                    "scenes": [
                        {"description": "Building tension toward climactic moment.", "purpose": "Raising stakes"},
                        {"description": "Critical choice or battle.", "purpose": "Climax preparation"}
                    ]
                },
                {
                    "id": "chapter_5",
                    "title": "Resolution",
                    "summary": f"{main_character} resolves the central conflict and undergoes transformation.",
                    "pov_character": main_character,
                    "scenes": [
                        {"description": "Final confrontation or resolution.", "purpose": "Climax"},
                        {"description": "Return to a new normal.", "purpose": "Denouement"}
                    ]
                }
            ]
        elif "sci-fi" in genre or "science fiction" in genre:
            chapters = [
                {
                    "id": "chapter_1",
                    "title": "The System",
                    "summary": f"Introduction to {main_character} and the technological aspects of {setting}.",
                    "pov_character": main_character,
                    "scenes": [
                        {"description": "Establishing the rules and technology of the world.", "purpose": "World-building"},
                        {"description": f"{main_character}'s place in this technological system.", "purpose": "Character introduction"}
                    ]
                },
                {
                    "id": "chapter_2",
                    "title": "Disruption",
                    "summary": "A technological anomaly or discovery disrupts the established order.",
                    "pov_character": main_character,
                    "scenes": [
                        {"description": "Discovery or malfunction that changes everything.", "purpose": "Inciting incident"},
                        {"description": "Initial response to the new development.", "purpose": "Character reaction"}
                    ]
                },
                {
                    "id": "chapter_3",
                    "title": "Exploration",
                    "summary": f"{main_character} investigates the implications of the new development.",
                    "pov_character": main_character,
                    "scenes": [
                        {"description": "Deeper exploration of the technological mystery.", "purpose": "Plot development"},
                        {"description": "Consequences begin to manifest.", "purpose": "Rising action"}
                    ]
                },
                {
                    "id": "chapter_4",
                    "title": "System Failure",
                    "summary": "The technological challenge reaches a critical point.",
                    "pov_character": main_character,
                    "scenes": [
                        {"description": "Crisis point where systems or assumptions break down.", "purpose": "Rising tension"},
                        {"description": "Preparation for the final solution.", "purpose": "Pre-climax"}
                    ]
                },
                {
                    "id": "chapter_5",
                    "title": "Reconfiguration",
                    "summary": f"{main_character} resolves the technological crisis and adapts to a new reality.",
                    "pov_character": main_character,
                    "scenes": [
                        {"description": "Implementation of the solution.", "purpose": "Climax"},
                        {"description": "Adaptation to the new technological paradigm.", "purpose": "Resolution"}
                    ]
                }
            ]
        else:
            # Generic structure for any genre
            chapters = [
                {
                    "id": "chapter_1",
                    "title": "Beginnings",
                    "summary": f"Introduction to {main_character} and the world of the story.",
                    "pov_character": main_character,
                    "scenes": [
                        {"description": "Establishing the character and setting.", "purpose": "Introduction"},
                        {"description": "Hints of the coming conflict.", "purpose": "Foreshadowing"}
                    ]
                },
                {
                    "id": "chapter_2",
                    "title": "Inciting Incident",
                    "summary": "The event that sets the story in motion.",
                    "pov_character": main_character,
                    "scenes": [
                        {"description": "The key event that disrupts normal life.", "purpose": "Plot catalyst"},
                        {"description": "Character's initial reaction.", "purpose": "Character development"}
                    ]
                },
                {
                    "id": "chapter_3",
                    "title": "Complications",
                    "summary": "Obstacles arise as the character pursues their goal.",
                    "pov_character": main_character,
                    "scenes": [
                        {"description": "First major obstacle.", "purpose": "Conflict development"},
                        {"description": "Character growth through challenge.", "purpose": "Character arc"}
                    ]
                },
                {
                    "id": "chapter_4",
                    "title": "Crisis Point",
                    "summary": "The situation reaches a critical juncture.",
                    "pov_character": main_character,
                    "scenes": [
                        {"description": "Maximum tension before resolution.", "purpose": "Rising action"},
                        {"description": "Character faces their greatest challenge.", "purpose": "Pre-climax"}
                    ]
                },
                {
                    "id": "chapter_5",
                    "title": "Resolution",
                    "summary": "The story reaches its conclusion with character transformation.",
                    "pov_character": main_character,
                    "scenes": [
                        {"description": "Final confrontation or decision.", "purpose": "Climax"},
                        {"description": "Aftermath and new equilibrium.", "purpose": "Denouement"}
                    ]
                }
            ]
        
        # Create the complete outline structure
        fallback_outline = {
            "title": title,
            "genre": genre,
            "summary": plot_summary,
            "structure": {
                "acts": [
                    {"number": 1, "description": act1_desc},
                    {"number": 2, "description": act2_desc},
                    {"number": 3, "description": act3_desc}
                ]
            },
            "chapters": chapters,
            "character_arcs": [
                {
                    "character": main_character,
                    "arc_type": "Growth",
                    "description": f"{main_character} evolves from initial state to a transformed state through the story's challenges."
                }
            ],
            "themes": [
                {"name": "Transformation", "development": "Explored through character growth across chapters."}
            ]
        }
        
        return fallback_outline
    
    def revise_chapter(
        self,
        chapter_id: str,
        revision_instructions: str
    ) -> Dict[str, Any]:
        """
        Revise a specific chapter in the outline based on instructions.
        
        Args:
            chapter_id: ID of the chapter to revise
            revision_instructions: Instructions for the revision
            
        Returns:
            Dictionary with the updated chapter
        """
        logger.info(f"Revising chapter {chapter_id} with instructions: {revision_instructions}")
        
        # Get the current outline
        outline = self.get_complete_outline()
        
        # Find the chapter
        chapter_to_revise = None
        for chapter in outline.get("chapters", []):
            if str(chapter.get("id", "")) == str(chapter_id):
                chapter_to_revise = chapter
                break
        
        if not chapter_to_revise:
            logger.error(f"Chapter {chapter_id} not found in outline")
            return {"error": f"Chapter {chapter_id} not found"}
        
        # Build the system prompt
        system_prompt = """You are an expert book outliner and editor.
Your task is to revise a chapter outline according to the provided instructions.
The revised chapter should maintain consistency with the overall book structure.
Provide output in JSON format."""
        
        # Build the user prompt
        user_prompt = f"""Revise the following chapter outline according to these instructions:

{revision_instructions}

Current chapter outline:
{json.dumps(chapter_to_revise, indent=2)}

Respond with the revised chapter as a valid JSON object that maintains the same structure as the original.
Include all the original fields (id, title, etc.) but with updated content according to the instructions.
"""
        
        try:
            # Revise the chapter
            response = self.openai_client.generate(
                prompt=user_prompt,
                system_prompt=system_prompt,
                json_mode=True
            )
            
            updated_chapter = response["parsed_json"]
            logger.info(f"Revised chapter {chapter_id} using OpenAI")
            
            # Update the chapter in the outline
            for i, chapter in enumerate(outline.get("chapters", [])):
                if str(chapter.get("id", "")) == str(chapter_id):
                    outline["chapters"][i] = updated_chapter
                    break
            
            # Store updated outline in memory
            self._store_in_memory(outline)
            
            return updated_chapter
            
        except Exception as e:
            logger.error(f"Error revising chapter {chapter_id}: {str(e)}")
            return {
                "error": f"Failed to revise chapter: {str(e)}",
                "original_chapter": chapter_to_revise
            }
    
    def add_chapter_details(
        self,
        chapter_id: str,
        detail_type: str,
        detail_instructions: str
    ) -> Dict[str, Any]:
        """
        Add specific details to a chapter in the outline.
        
        Args:
            chapter_id: ID of the chapter to enhance
            detail_type: Type of details to add (e.g., "scenes", "character_arcs")
            detail_instructions: Instructions for the details to add
            
        Returns:
            Dictionary with the updated chapter
        """
        logger.info(f"Adding {detail_type} details to chapter {chapter_id}")
        
        # Get the current outline
        outline = self.get_complete_outline()
        
        # Find the chapter
        chapter_to_enhance = None
        for chapter in outline.get("chapters", []):
            if str(chapter.get("id", "")) == str(chapter_id):
                chapter_to_enhance = chapter
                break
        
        if not chapter_to_enhance:
            logger.error(f"Chapter {chapter_id} not found in outline")
            return {"error": f"Chapter {chapter_id} not found"}
        
        # Build the system prompt
        system_prompt = """You are an expert book outliner and editor.
Your task is to add specific details to a chapter outline according to the provided instructions.
The enhanced chapter should maintain consistency with the overall book structure.
Provide output in JSON format."""
        
        # Build the user prompt
        user_prompt = f"""Add {detail_type} details to the following chapter outline according to these instructions:

{detail_instructions}

Current chapter outline:
{json.dumps(chapter_to_enhance, indent=2)}

Full book outline context (summary):
Title: {outline.get("title", "Untitled")}
Genre: {outline.get("genre", "Unknown")}
Overall Structure: {outline.get("structure", {}).get("overview", "Standard structure")}

Respond with the enhanced chapter as a valid JSON object that maintains the same structure as the original,
but with additional details for the {detail_type} aspect.
"""
        
        try:
            # Add the details
            response = self.openai_client.generate(
                prompt=user_prompt,
                system_prompt=system_prompt,
                json_mode=True
            )
            
            updated_chapter = response["parsed_json"]
            logger.info(f"Added {detail_type} details to chapter {chapter_id} using OpenAI")
            
            # Update the chapter in the outline
            for i, chapter in enumerate(outline.get("chapters", [])):
                if str(chapter.get("id", "")) == str(chapter_id):
                    outline["chapters"][i] = updated_chapter
                    break
            
            # Store updated outline in memory
            self._store_in_memory(outline)
            
            return updated_chapter
            
        except Exception as e:
            logger.error(f"Error adding {detail_type} details to chapter {chapter_id}: {str(e)}")
            return {
                "error": f"Failed to add {detail_type} details: {str(e)}",
                "original_chapter": chapter_to_enhance
            }
    
    def _store_in_memory(self, outline: Dict[str, Any]) -> None:
        """
        Store generated outline in memory.
        
        Args:
            outline: Dictionary with generated outline
        """
        # Store the entire outline
        self.memory.add_document(
            json.dumps(outline),
            self.name,
            metadata={"type": "outline"}
        )
        
        # Store each chapter individually for easier access
        if "chapters" in outline and isinstance(outline["chapters"], list):
            for chapter in outline["chapters"]:
                chapter_id = chapter.get("id")
                if not chapter_id:
                    continue
                    
                self.memory.add_document(
                    json.dumps(chapter),
                    self.name,
                    metadata={"type": "chapter", "chapter_id": chapter_id}
                )
    
    def get_complete_outline(self) -> Dict[str, Any]:
        """
        Get the complete and most up-to-date outline.
        
        Returns:
            Dictionary with the complete outline
        """
        # Get the base outline
        outline_docs = [doc for doc in self.memory.get_agent_memory(self.name)
                        if doc.get('metadata', {}).get('type') == 'outline']
        
        if not outline_docs:
            raise ValueError("No outline found in memory")
        
        # Get the most recent outline
        latest_outline_doc = max(outline_docs, key=lambda x: x.get('metadata', {}).get('timestamp', ''))
        
        try:
            outline = json.loads(latest_outline_doc['text'])
        except json.JSONDecodeError:
            raise ValueError("Invalid outline data")
        
        # Get all chapter documents
        chapter_docs = [doc for doc in self.memory.get_agent_memory(self.name)
                       if doc.get('metadata', {}).get('type') in ['chapter', 'revised_chapter', 'enhanced_chapter']]
        
        # Create a mapping of the latest version of each chapter
        chapter_map = {}
        
        for doc in chapter_docs:
            metadata = doc.get('metadata', {})
            chapter_id = metadata.get('chapter_id')
            
            if not chapter_id:
                continue
                
            timestamp = metadata.get('timestamp', '')
            
            # Only keep the latest version of each chapter
            if chapter_id not in chapter_map or timestamp > chapter_map[chapter_id]['timestamp']:
                try:
                    chapter_data = json.loads(doc['text'])
                    chapter_map[chapter_id] = {
                        'data': chapter_data,
                        'timestamp': timestamp
                    }
                except json.JSONDecodeError:
                    continue
        
        # Update the chapters in the outline with their latest versions
        if 'chapters' in outline and isinstance(outline['chapters'], list):
            for i, chapter in enumerate(outline['chapters']):
                chapter_id = chapter.get('id')
                
                if chapter_id and chapter_id in chapter_map:
                    outline['chapters'][i] = chapter_map[chapter_id]['data']
        
        return outline
