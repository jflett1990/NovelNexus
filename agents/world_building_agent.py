import logging
import json
from typing import Dict, Any, List, Optional

from models.ollama_client import get_ollama_client
from models.openai_client import get_openai_client
from memory.dynamic_memory import DynamicMemory
from schemas.world_building_schema import WORLD_BUILDING_SCHEMA

logger = logging.getLogger(__name__)

class WorldBuildingAgent:
    """
    Agent responsible for generating and developing the world/setting of the book.
    """
    
    def __init__(
        self,
        project_id: str,
        memory: DynamicMemory,
        use_openai: bool = True,
        use_ollama: bool = True
    ):
        """
        Initialize the World Building Agent.
        
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
Provide output in JSON format according to the provided schema."""
        
        # Build the user prompt
        user_prompt = f"""Create a detailed world for a book with the following details:

Title: {title}
Genre: {genre}
Themes: {themes_str}
Plot Summary: {plot_summary}

The world should have {complexity} complexity level of development.
Include physical settings, cultural elements, historical context, and any rules or systems specific to this world.
If the story is set in a real-world location, provide rich details about that location and how it's portrayed in the story.

Respond with the world details formatted according to this JSON schema: {json.dumps(WORLD_BUILDING_SCHEMA)}
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
                    
                    world = response["parsed_json"]
                    logger.info(f"Generated world using OpenAI")
                    
                    # Store in memory
                    self._store_in_memory(world)
                    
                    return world
                except Exception as e:
                    logger.warning(f"OpenAI world generation failed: {e}, falling back to Ollama")
            
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
                    world = json.loads(json_str)
                else:
                    raise ValueError("Could not extract valid JSON from Ollama response")
                
                logger.info(f"Generated world using Ollama")
                
                # Store in memory
                self._store_in_memory(world)
                
                return world
            
            raise Exception("No available AI service (OpenAI or Ollama) to generate world")
            
        except Exception as e:
            logger.error(f"World generation error: {e}")
            raise Exception(f"Failed to generate world: {e}")
    
    def develop_location(
        self,
        location_name: str,
        development_prompt: str
    ) -> Dict[str, Any]:
        """
        Develop a specific location with more details.
        
        Args:
            location_name: Name of the location to develop
            development_prompt: Specific directions for location development
            
        Returns:
            Dictionary with the developed location
        """
        # Retrieve the original world from memory
        world_docs = self.memory.get_agent_memory(self.name)
        
        original_world = None
        for doc in world_docs:
            metadata = doc.get('metadata', {})
            if metadata.get('type') == 'world':
                try:
                    world_data = json.loads(doc['text'])
                    original_world = world_data
                    break
                except json.JSONDecodeError:
                    continue
        
        if not original_world:
            raise ValueError("World data not found in memory")
        
        # Build the system prompt
        system_prompt = """You are an expert location developer for fictional worlds. 
Your task is to create a richly detailed location within a broader world context.
This includes physical description, history, culture, inhabitants, and significance to the story.
Provide output in JSON format."""
        
        # Build the user prompt
        user_prompt = f"""Develop the location '{location_name}' with rich detail based on these directions: {development_prompt}

World context:
{json.dumps(original_world, indent=2)}

Create a detailed description of this location including:
1. Physical appearance and geography
2. History and background
3. Cultural significance
4. Notable inhabitants or frequent visitors
5. Unique features or landmarks
6. Atmosphere and mood
7. Role in the overall story

Respond with the developed location formatted as a JSON object in this format:
{{
  "name": "string",
  "type": "string",
  "physical_description": "string",
  "history": "string",
  "cultural_significance": "string",
  "inhabitants": ["string"],
  "notable_features": ["string"],
  "atmosphere": "string",
  "story_significance": "string",
  "connections": ["string"]
}}
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
                        max_tokens=2000
                    )
                    
                    location = response["parsed_json"]
                    logger.info(f"Developed location '{location_name}' using OpenAI")
                    
                    # Store in memory
                    self.memory.add_document(
                        json.dumps(location),
                        self.name,
                        metadata={"type": "location", "name": location_name}
                    )
                    
                    return location
                except Exception as e:
                    logger.warning(f"OpenAI location development failed: {e}, falling back to Ollama")
            
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
                    location = json.loads(json_str)
                else:
                    raise ValueError("Could not extract valid JSON from Ollama response")
                
                logger.info(f"Developed location '{location_name}' using Ollama")
                
                # Store in memory
                self.memory.add_document(
                    json.dumps(location),
                    self.name,
                    metadata={"type": "location", "name": location_name}
                )
                
                return location
            
            raise Exception("No available AI service (OpenAI or Ollama) to develop location")
            
        except Exception as e:
            logger.error(f"Location development error: {e}")
            raise Exception(f"Failed to develop location: {e}")
    
    def create_cultural_element(
        self,
        element_type: str,
        description: str
    ) -> Dict[str, Any]:
        """
        Create a cultural element for the world.
        
        Args:
            element_type: Type of cultural element (e.g., 'custom', 'religion', 'language')
            description: Brief description of what to create
            
        Returns:
            Dictionary with the created cultural element
        """
        # Retrieve the original world from memory
        world_docs = self.memory.get_agent_memory(self.name)
        
        original_world = None
        for doc in world_docs:
            metadata = doc.get('metadata', {})
            if metadata.get('type') == 'world':
                try:
                    world_data = json.loads(doc['text'])
                    original_world = world_data
                    break
                except json.JSONDecodeError:
                    continue
        
        if not original_world:
            raise ValueError("World data not found in memory")
        
        # Build the system prompt
        system_prompt = f"""You are an expert creator of {element_type}s for fictional worlds. 
Your task is to create a richly detailed {element_type} within a broader world context.
The {element_type} should be unique, culturally consistent, and add depth to the world.
Provide output in JSON format."""
        
        # Build the user prompt
        user_prompt = f"""Create a detailed {element_type} for this world based on this description: {description}

World context:
{json.dumps(original_world, indent=2)}

Develop this {element_type} with:
1. Name and basic description
2. Historical origins
3. Cultural significance
4. Current practice or manifestation
5. Variations or regional differences
6. Impact on daily life
7. Role in the story

Respond with the developed {element_type} formatted as a JSON object in this format:
{{
  "name": "string",
  "type": "{element_type}",
  "description": "string",
  "origin": "string",
  "significance": "string",
  "current_practice": "string",
  "variations": ["string"],
  "daily_impact": "string",
  "story_role": "string"
}}
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
                        max_tokens=2000
                    )
                    
                    cultural_element = response["parsed_json"]
                    logger.info(f"Created {element_type} using OpenAI")
                    
                    # Store in memory
                    self.memory.add_document(
                        json.dumps(cultural_element),
                        self.name,
                        metadata={"type": "cultural_element", "element_type": element_type}
                    )
                    
                    return cultural_element
                except Exception as e:
                    logger.warning(f"OpenAI cultural element creation failed: {e}, falling back to Ollama")
            
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
                    cultural_element = json.loads(json_str)
                else:
                    raise ValueError("Could not extract valid JSON from Ollama response")
                
                logger.info(f"Created {element_type} using Ollama")
                
                # Store in memory
                self.memory.add_document(
                    json.dumps(cultural_element),
                    self.name,
                    metadata={"type": "cultural_element", "element_type": element_type}
                )
                
                return cultural_element
            
            raise Exception(f"No available AI service (OpenAI or Ollama) to create {element_type}")
            
        except Exception as e:
            logger.error(f"Cultural element creation error: {e}")
            raise Exception(f"Failed to create {element_type}: {e}")
    
    def _store_in_memory(self, world: Dict[str, Any]) -> None:
        """
        Store generated world in memory.
        
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
        Get the complete world from memory.
        
        Returns:
            Dictionary with world data and all related elements
        """
        # Query for the main world data in memory
        world_docs = self.memory.get_agent_memory(self.name)
        
        if not world_docs:
            raise ValueError("No world data found in memory")
        
        main_world = None
        locations = []
        cultural_elements = []
        
        for doc in world_docs:
            metadata = doc.get('metadata', {})
            try:
                data = json.loads(doc['text'])
                
                if metadata.get('type') == 'world':
                    main_world = data
                elif metadata.get('type') == 'location':
                    locations.append(data)
                elif metadata.get('type') == 'cultural_element':
                    cultural_elements.append(data)
            except json.JSONDecodeError:
                continue
        
        if not main_world:
            raise ValueError("Main world data not found in memory")
        
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
                if element_name in existing_elements:
                    # Update existing element
                    complete_world["cultural_elements"][existing_elements[element_name]] = element
                else:
                    # Add new element
                    complete_world["cultural_elements"].append(element)
        
        return complete_world
