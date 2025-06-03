import logging
import json
from typing import Dict, Any, List, Optional


from models.openai_client import get_openai_client
from memory.dynamic_memory import DynamicMemory
from schemas.world_building_schema import WORLD_BUILDING_SCHEMA
from utils.json_utils import robust_json_parse, with_retries, verify_memory_write, validate_schema
from utils.validation_utils import validate_world

logger = logging.getLogger(__name__)

class WorldBuildingAgent:
    """
    Agent responsible for generating and developing the world/setting of the book.
    """
    
    def __init__(
        self,
        project_id: str,
        memory: DynamicMemory,
        use_openai: bool = True
    ):
        """
        Initialize the World Building Agent.
        
        Args:
            project_id: Unique identifier for the project
            memory: Dynamic memory instance
            use_openai: Whether to use OpenAI models
        """
        self.project_id = project_id
        self.memory = memory
        self.use_openai = use_openai
        
        self.openai_client = get_openai_client() if use_openai else None
        
        self.name = "world_building_agent"
        self.stage = "world_building"
    
    def generate_world(
        self,
        book_idea: Dict[str, Any],
        complexity: str = "medium"
    ) -> Dict[str, Any]:
        """
        Generate the world/setting for the book based on the book idea.
        
        Args:
            book_idea: Dictionary containing the book idea
            complexity: Complexity level (low, medium, high)
            
        Returns:
            Dictionary with the generated world
        """
        logger.info(f"Generating world for project {self.project_id}")
        
        # Protect against empty book_idea
        if not book_idea or not isinstance(book_idea, dict):
            logger.warning(f"Empty or invalid book_idea provided, using minimal default")
            book_idea = {"title": "Untitled", "genre": "fiction", "themes": [], "plot_summary": ""}
        
        # Extract key information from book idea
        title = book_idea.get("title", "")
        genre = book_idea.get("genre", "")
        themes = book_idea.get("themes", [])
        themes_str = ", ".join(themes) if isinstance(themes, list) else themes
        plot_summary = book_idea.get("plot_summary", "")
        
        # Build the system prompt
        system_prompt = """You are an expert world-builder for novels and stories. 
Your task is to create a rich, immersive, and consistent world for a story to take place in.
This includes physical settings, cultural contexts, historical background, and the rules that govern the world.

IMPORTANT: Your response MUST be valid JSON following the provided schema exactly.
Do not add any text, explanations, or markdown outside of the JSON structure.
"""
        
        # Build the user prompt
        user_prompt = f"""Create a detailed world for a book with the following details:

Title: {title}
Genre: {genre}
Themes: {themes_str}
Plot Summary: {plot_summary}

The world should have {complexity} complexity level of development.
Include physical settings, cultural elements, historical context, and any rules or systems specific to this world.
If the story is set in a real-world location, provide rich details about that location and how it's portrayed in the story.

YOUR RESPONSE MUST BE VALID JSON. Follow this schema exactly:
{json.dumps(WORLD_BUILDING_SCHEMA, indent=2)}

Remember:
1. All keys must be in quotes
2. No trailing commas in arrays or objects
3. Use double quotes for strings, not single quotes
4. Do not include any markdown formatting or explanations outside the JSON structure
"""
        
        try:
            # Try OpenAI first if enabled
            if self.use_openai and self.openai_client:
                try:
                    response = self.openai_client.generate(
                        prompt=user_prompt,
                        system_prompt=system_prompt,
                        json_mode=True,
                        temperature=0.8,
                        max_tokens=3000
                    )
                    
                    raw_world = response["parsed_json"]
                    
                    # Use our validation utility to validate and fix the world data
                    world = validate_world(raw_world)
                    
                    logger.info(f"Generated world using OpenAI with {len(world.get('locations', []))} locations")
                    
                    # Store in memory with verification
                    self._store_in_memory_verified(world)
                    
                    return world
                except Exception as e:
                    logger.warning(f"OpenAI world generation failed: {str(e)}")
            
            # Create fallback world if OpenAI failed
            fallback_world = self._create_fallback_world(book_idea)
            
            # Validate fallback world too
            validated_fallback = validate_world(fallback_world)
            
            logger.warning(f"Using fallback world with {len(validated_fallback.get('locations', []))} locations")
            
            # Store fallback in memory
            self._store_in_memory_verified(validated_fallback)
            
            return validated_fallback
            
        except Exception as e:
            logger.error(f"World generation error: {str(e)}")
            fallback_world = self._create_fallback_world(book_idea)
            
            # Validate fallback world
            validated_fallback = validate_world(fallback_world)
            
            self._store_in_memory_verified(validated_fallback)
            return validated_fallback
    
    def _validate_world(self, world: Dict[str, Any]) -> Dict[str, Any]:
        """
        Legacy validation - now we use the validation_utils.validate_world method instead.
        Kept for backward compatibility.
        
        Args:
            world: World data to validate
            
        Returns:
            Validated world data with all required fields
        """
        return validate_world(world)
    
    def _create_fallback_world(self, book_idea: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a minimal fallback world when generation fails.
        
        Args:
            book_idea: Book idea to base the fallback world on
            
        Returns:
            Minimal valid world data
        """
        title = book_idea.get("title", "Untitled")
        genre = book_idea.get("genre", "fiction")
        
        # Create a minimal but valid world
        return {
            "name": f"World of {title}",
            "description": f"A {genre} setting with basic elements necessary for the story.",
            "physical_characteristics": "Standard environment appropriate for the genre.",
            "rules": "Normal rules of reality unless specified by the genre.",
            "history": "History developed as needed for the story.",
            "locations": [
                {
                    "name": "Main Setting",
                    "description": "The primary location where the story unfolds.",
                    "significance": "Central to the plot."
                },
                {
                    "name": "Secondary Location",
                    "description": "An additional important setting in the story.",
                    "significance": "Provides contrast and additional story opportunities."
                }
            ],
            "cultural_elements": [
                {
                    "name": "Dominant Culture",
                    "type": "society",
                    "description": "The primary cultural backdrop for the story."
                }
            ]
        }
    
    def _store_in_memory_verified(self, world: Dict[str, Any]) -> bool:
        """
        Store world data in memory with verification.
        
        Args:
            world: World data to store
            
        Returns:
            True if storage and verification succeeded, False otherwise
        """
        # Store the entire world
        world_stored = verify_memory_write(
            self.memory,
            json.dumps(world),
            self.name,
            metadata={"type": "world"}
        )
        
        if not world_stored:
            logger.error(f"Failed to store world data in memory for project {self.project_id}")
            return False
        
        # Store individual locations if present
        locations_stored = True
        if "locations" in world and isinstance(world["locations"], list):
            for location in world["locations"]:
                location_name = location.get("name")
                if not location_name:
                    continue
                    
                result = verify_memory_write(
                    self.memory,
                    json.dumps(location),
                    self.name,
                    metadata={"type": "location", "name": location_name}
                )
                
                if not result:
                    locations_stored = False
                    logger.warning(f"Failed to store location '{location_name}' in memory")
        
        # Store cultural elements if present
        elements_stored = True
        if "cultural_elements" in world and isinstance(world["cultural_elements"], list):
            for element in world["cultural_elements"]:
                element_type = element.get("type")
                element_name = element.get("name")
                if not element_type or not element_name:
                    continue
                    
                result = verify_memory_write(
                    self.memory,
                    json.dumps(element),
                    self.name,
                    metadata={"type": "cultural_element", "element_type": element_type, "name": element_name}
                )
                
                if not result:
                    elements_stored = False
                    logger.warning(f"Failed to store cultural element '{element_name}' in memory")
        
        return world_stored and locations_stored and elements_stored
    
    def _store_in_memory(self, world: Dict[str, Any]) -> None:
        """
        Legacy method for storing generated world in memory (now replaced by verified version).
        
        Args:
            world: Dictionary with generated world details
        """
        # Store the entire world
        self.memory.add_document(
            json.dumps(world),
            self.name,
            metadata={"type": "world"}
        )
        
        # Store individual locations if present
        if "locations" in world and isinstance(world["locations"], list):
            for location in world["locations"]:
                location_name = location.get("name")
                if location_name:
                    self.memory.add_document(
                        json.dumps(location),
                        self.name,
                        metadata={"type": "location", "name": location_name}
                    )
        
        # Store cultural elements if present
        if "cultural_elements" in world and isinstance(world["cultural_elements"], list):
            for element in world["cultural_elements"]:
                element_type = element.get("type")
                element_name = element.get("name")
                if element_type and element_name:
                    self.memory.add_document(
                        json.dumps(element),
                        self.name,
                        metadata={"type": "cultural_element", "element_type": element_type, "name": element_name}
                    )
    
    def get_world(self) -> Dict[str, Any]:
        """
        Get the complete world from memory with improved error handling.
        
        Returns:
            Dictionary with world data and all related elements
        """
        # Query for the main world data in memory
        world_docs = self.memory.get_agent_memory(self.name)
        
        if not world_docs:
            logger.error(f"No world data found in memory for project {self.project_id}")
            return self._create_fallback_world({"title": f"Project {self.project_id}"})
        
        main_world = None
        locations = []
        cultural_elements = []
        
        for doc in world_docs:
            metadata = doc.get('metadata', {})
            try:
                # Use robust parsing for all JSON data
                data = robust_json_parse(doc['text'])
                
                if not data:
                    logger.warning(f"Empty or invalid JSON data for document with metadata: {metadata}")
                    continue
                
                if metadata.get('type') == 'world':
                    main_world = data
                elif metadata.get('type') == 'location':
                    locations.append(data)
                elif metadata.get('type') == 'cultural_element':
                    cultural_elements.append(data)
            except Exception as e:
                logger.warning(f"Error parsing document: {str(e)}")
                continue
        
        if not main_world:
            logger.error(f"Main world data not found in memory for project {self.project_id}")
            return self._create_fallback_world({"title": f"Project {self.project_id}"})
        
        # Merge all data into a complete world
        complete_world = main_world.copy()
        
        # Add or merge locations
        if locations:
            if "locations" not in complete_world:
                complete_world["locations"] = []
            
            # Map existing locations by name
            existing_locations = {loc.get("name"): idx for idx, loc in enumerate(complete_world["locations"])}
            
            for location in locations:
                location_name = location.get("name")
                if not location_name:
                    continue
                    
                if location_name in existing_locations:
                    # Update existing location
                    complete_world["locations"][existing_locations[location_name]] = location
                else:
                    # Add new location
                    complete_world["locations"].append(location)
        
        # Add or merge cultural elements
        if cultural_elements:
            if "cultural_elements" not in complete_world:
                complete_world["cultural_elements"] = []
            
            # Map existing elements by name
            existing_elements = {elem.get("name"): idx for idx, elem in enumerate(complete_world["cultural_elements"])}
            
            for element in cultural_elements:
                element_name = element.get("name")
                if not element_name:
                    continue
                    
                if element_name in existing_elements:
                    # Update existing element
                    complete_world["cultural_elements"][existing_elements[element_name]] = element
                else:
                    # Add new element
                    complete_world["cultural_elements"].append(element)
        
        # Final validation to ensure the world data is complete
        return self._validate_world(complete_world)
