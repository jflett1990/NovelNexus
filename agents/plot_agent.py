import logging
import json
from typing import Dict, Any, List, Optional
from datetime import datetime


from models.openai_client import get_openai_client
from memory.dynamic_memory import DynamicMemory
from utils.json_utils import verify_memory_write
from utils.validation_utils import validate_plot

logger = logging.getLogger(__name__)

class PlotAgent:
    """
    Agent responsible for developing the plot structure of the book.
    """
    
    def __init__(
        self,
        project_id: str,
        memory: DynamicMemory,
        use_openai: bool = True
    ):
        """
        Initialize the Plot Agent.
        
        Args:
            project_id: Unique identifier for the project
            memory: Dynamic memory instance
            use_openai: Whether to use OpenAI models
        """
        self.project_id = project_id
        self.memory = memory
        self.use_openai = use_openai
        
        self.openai_client = get_openai_client() if use_openai else None
        
        self.name = "plot_agent"
        self.stage = "plot_development"
    
    def generate_plot(
        self,
        book_idea: Dict[str, Any],
        world_data: Optional[Dict[str, Any]] = None,
        characters: Optional[List[Dict[str, Any]]] = None,
        complexity: str = "medium"
    ) -> Dict[str, Any]:
        """
        Generate a detailed plot structure for the book.
        
        Args:
            book_idea: Dictionary containing the book idea
            world_data: Optional dictionary with world building data
            characters: Optional list of character dictionaries
            complexity: Complexity level (low, medium, high)
            
        Returns:
            Dictionary with the generated plot structure
        """
        logger.info(f"Generating plot for project {self.project_id}")
        
        # Protect against empty inputs
        if not book_idea or not isinstance(book_idea, dict):
            logger.warning(f"Empty or invalid book_idea provided, using minimal default")
            book_idea = {"title": "Untitled", "genre": "fiction", "themes": [], "plot_summary": ""}
        
        # Extract key information from book idea
        title = book_idea.get("title", "")
        genre = book_idea.get("genre", "")
        themes = book_idea.get("themes", [])
        themes_str = ", ".join(themes) if isinstance(themes, list) else themes
        plot_summary = book_idea.get("plot_summary", "")
        
        # Extract character information if available
        character_info = ""
        if characters and isinstance(characters, list):
            character_info = "\n\nCharacters:\n"
            for char in characters:
                if isinstance(char, dict):
                    name = char.get("name", "")
                    role = char.get("role", "")
                    background = char.get("background", "")
                    
                    if name:
                        character_info += f"- {name}"
                        if role:
                            character_info += f" ({role})"
                        character_info += ": "
                        if background:
                            character_info += f"{background[:100]}..."
                        character_info += "\n"
        
        # Extract world information if available
        world_info = ""
        if world_data and isinstance(world_data, dict):
            world_name = world_data.get("name", "")
            world_desc = world_data.get("description", "")
            
            if world_name or world_desc:
                world_info = f"\n\nWorld: {world_name}\n{world_desc}\n"
                
                # Include locations if available
                locations = world_data.get("locations", [])
                if locations and isinstance(locations, list):
                    world_info += "\nLocations:\n"
                    for loc in locations[:3]:  # Limit to 3 locations to keep prompt length reasonable
                        if isinstance(loc, dict):
                            loc_name = loc.get("name", "")
                            loc_desc = loc.get("description", "")
                            
                            if loc_name:
                                world_info += f"- {loc_name}: {loc_desc[:100]}...\n"
        
        # Build the system prompt
        system_prompt = """You are an expert plot developer for novels and stories.
Your task is to create a compelling plot structure with multiple chapters or scenes.
This plot should have a clear beginning, middle, and end, with appropriate rising action, climax, and resolution.
Focus on creating narrative tension, character arcs, and thematic resonance.

IMPORTANT: Your response MUST be valid JSON following the schema specified.
Do not include any text or markdown outside the JSON structure."""
        
        # Build the user prompt
        user_prompt = f"""Create a detailed plot for a {genre} book titled "{title}".

Main Concept: {plot_summary}
Themes: {themes_str}
{character_info}
{world_info}

The plot should have {complexity} complexity level of development.
Create a chapter-by-chapter breakdown with clear narrative progression.

YOUR RESPONSE MUST BE VALID JSON. Follow this schema:
{{
  "chapters": [
    {{
      "number": 1,
      "title": "Chapter title",
      "summary": "Detailed description of what happens in the chapter",
      "pov_character": "Name of the POV character (if applicable)",
      "settings": ["List of locations where the chapter takes place"],
      "plot_points": ["Key plot developments in this chapter"]
    }}
  ],
  "arcs": [
    {{
      "name": "Name of story arc",
      "description": "Description of the story arc",
      "chapters": [1, 2, 3]
    }}
  ],
  "themes": ["Major themes developed in the plot"]
}}

Create approximately 8-15 chapters depending on complexity.
Include 2-4 major story arcs that develop throughout these chapters."""
        
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
                    
                    raw_plot = response["parsed_json"]
                    
                    # Use our validation utility to validate and fix the plot data
                    validated_plot = validate_plot(raw_plot)
                    
                    logger.info(f"Generated plot with {len(validated_plot.get('chapters', []))} chapters using OpenAI")
                    
                    # Store in memory with verification
                    self._store_in_memory(validated_plot)
                    
                    return validated_plot
                except Exception as e:
                    logger.warning(f"OpenAI plot generation failed: {str(e)}")
            
            # Create fallback plot if OpenAI failed
            fallback_plot = self._create_fallback_plot(book_idea)
            
            # Validate fallback plot too
            validated_fallback = validate_plot(fallback_plot)
            
            logger.warning(f"Using fallback plot with {len(validated_fallback.get('chapters', []))} chapters")
            
            # Store in memory
            self._store_in_memory(validated_fallback)
            
            return validated_fallback
            
        except Exception as e:
            logger.error(f"Plot generation error: {str(e)}")
            fallback_plot = self._create_fallback_plot(book_idea)
            
            # Validate fallback plot
            validated_fallback = validate_plot(fallback_plot)
            
            self._store_in_memory(validated_fallback)
            return validated_fallback
    
    def _create_fallback_plot(self, book_idea: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a minimal fallback plot when generation fails.
        
        Args:
            book_idea: Book idea to base the fallback plot on
            
        Returns:
            Minimal valid plot data
        """
        title = book_idea.get("title", "Untitled")
        genre = book_idea.get("genre", "fiction")
        
        # Create a minimal three-act structure
        return {
            "chapters": [
                {
                    "number": 1,
                    "title": "Introduction",
                    "summary": "Introduce the main characters and setting.",
                    "pov_character": "Protagonist",
                    "settings": ["Main Setting"],
                    "plot_points": ["Establish normal world", "Introduce protagonist"]
                },
                {
                    "number": 2,
                    "title": "Inciting Incident",
                    "summary": "The event that sets the story in motion.",
                    "pov_character": "Protagonist",
                    "settings": ["Main Setting"],
                    "plot_points": ["Inciting incident", "Call to adventure"]
                },
                {
                    "number": 3,
                    "title": "Rising Action",
                    "summary": "The protagonist faces initial obstacles.",
                    "pov_character": "Protagonist",
                    "settings": ["Secondary Location"],
                    "plot_points": ["First challenge", "Meet allies or enemies"]
                },
                {
                    "number": 4,
                    "title": "Midpoint",
                    "summary": "A significant turning point in the story.",
                    "pov_character": "Protagonist",
                    "settings": ["New Location"],
                    "plot_points": ["Major revelation", "Raises stakes"]
                },
                {
                    "number": 5,
                    "title": "Complications",
                    "summary": "Situations become more complex and challenging.",
                    "pov_character": "Protagonist",
                    "settings": ["Various Locations"],
                    "plot_points": ["New obstacles", "Relationships tested"]
                },
                {
                    "number": 6,
                    "title": "Climax",
                    "summary": "The final confrontation or resolution of the main conflict.",
                    "pov_character": "Protagonist",
                    "settings": ["Dramatic Location"],
                    "plot_points": ["Final battle", "Highest stakes"]
                },
                {
                    "number": 7,
                    "title": "Resolution",
                    "summary": "The aftermath and conclusion of the story.",
                    "pov_character": "Protagonist",
                    "settings": ["Main Setting"],
                    "plot_points": ["Wrap up loose ends", "Character growth confirmed"]
                }
            ],
            "arcs": [
                {
                    "name": "Main Plot",
                    "description": "The primary storyline of the novel.",
                    "chapters": [1, 2, 3, 4, 5, 6, 7]
                },
                {
                    "name": "Character Development",
                    "description": "The protagonist's internal journey and growth.",
                    "chapters": [1, 3, 5, 7]
                }
            ],
            "themes": ["Growth", "Conflict", "Resolution"]
        }
    
    def _store_in_memory(self, plot: Dict[str, Any]) -> bool:
        """
        Store plot data in memory with verification.
        
        Args:
            plot: Plot data to store
            
        Returns:
            True if storage succeeded, False otherwise
        """
        # Store the entire plot
        plot_stored = verify_memory_write(
            self.memory,
            json.dumps(plot),
            self.name,
            metadata={"type": "plot"}
        )
        
        if not plot_stored:
            logger.error(f"Failed to store plot data in memory for project {self.project_id}")
            return False
        
        # Store individual chapters if present
        chapters_stored = True
        if "chapters" in plot and isinstance(plot["chapters"], list):
            for chapter in plot["chapters"]:
                chapter_number = chapter.get("number")
                chapter_title = chapter.get("title")
                
                if not chapter_number or not chapter_title:
                    continue
                    
                result = verify_memory_write(
                    self.memory,
                    json.dumps(chapter),
                    self.name,
                    metadata={
                        "type": "chapter_outline", 
                        "number": chapter_number,
                        "title": chapter_title
                    }
                )
                
                if not result:
                    chapters_stored = False
                    logger.warning(f"Failed to store chapter {chapter_number} in memory")
        
        # Store plot arcs if present
        arcs_stored = True
        if "arcs" in plot and isinstance(plot["arcs"], list):
            for arc in plot["arcs"]:
                arc_name = arc.get("name")
                
                if not arc_name:
                    continue
                    
                result = verify_memory_write(
                    self.memory,
                    json.dumps(arc),
                    self.name,
                    metadata={
                        "type": "plot_arc", 
                        "name": arc_name
                    }
                )
                
                if not result:
                    arcs_stored = False
                    logger.warning(f"Failed to store plot arc '{arc_name}' in memory")
        
        return plot_stored and chapters_stored and arcs_stored
    
    def get_plot(self) -> Dict[str, Any]:
        """
        Retrieve the complete plot from memory.
        
        Returns:
            Dictionary with complete plot data
        """
        plot_docs = self.memory.query_memory(f"type:plot", agent_name=self.name)
        
        if not plot_docs:
            logger.warning(f"No plot found for project {self.project_id}")
            return {"chapters": [], "arcs": [], "themes": []}
        
        try:
            # Get the most recent plot document
            plot_doc = plot_docs[0]
            plot = json.loads(plot_doc["text"])
            
            # Ensure we have a valid structure
            if not isinstance(plot, dict):
                logger.warning(f"Invalid plot data structure for project {self.project_id}")
                return {"chapters": [], "arcs": [], "themes": []}
            
            # Ensure required keys exist
            for key in ["chapters", "arcs", "themes"]:
                if key not in plot:
                    plot[key] = []
            
            return plot
        
        except Exception as e:
            logger.error(f"Error retrieving plot: {str(e)}")
            return {"chapters": [], "arcs": [], "themes": []} 