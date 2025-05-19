import logging
import json
from typing import Dict, Any, List, Optional

from models.ollama_client import get_ollama_client
from models.openai_client import get_openai_client
from memory.dynamic_memory import DynamicMemory
from schemas.character_schema import CHARACTER_SCHEMA

logger = logging.getLogger(__name__)

class CharacterAgent:
    """
    Agent responsible for generating and developing characters for the book.
    """
    
    def __init__(
        self,
        project_id: str,
        memory: DynamicMemory,
        use_openai: bool = True,
        use_ollama: bool = True
    ):
        """
        Initialize the Character Agent.
        
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
        
        self.name = "character_agent"
        self.stage = "character_development"
    
    def generate_characters(
        self,
        book_idea: Dict[str, Any],
        num_characters: int = 5,
        complexity: str = "medium"
    ) -> Dict[str, Any]:
        """
        Generate characters for the book based on the book idea.
        
        Args:
            book_idea: Dictionary containing the book idea
            num_characters: Number of characters to generate
            complexity: Complexity level (low, medium, high)
            
        Returns:
            Dictionary with generated characters
        """
        logger.info(f"Generating {num_characters} characters for project {self.project_id}")
        
        # Extract key information from book idea
        title = book_idea.get("title", "")
        genre = book_idea.get("genre", "")
        themes = book_idea.get("themes", [])
        themes_str = ", ".join(themes) if isinstance(themes, list) else themes
        plot_summary = book_idea.get("plot_summary", "")
        
        # Build the system prompt
        system_prompt = """You are an expert character developer for novels and stories. 
Your task is to create compelling, multi-dimensional characters with distinct personalities, backgrounds, motivations, and arcs.
Each character should be unique and well-suited to the story concept.
Provide output in JSON format according to the provided schema."""
        
        # Build the user prompt
        user_prompt = f"""Create {num_characters} compelling characters for a book with the following details:

Title: {title}
Genre: {genre}
Themes: {themes_str}
Plot Summary: {plot_summary}

The characters should have {complexity} complexity level of development.
Include a mix of protagonist(s), antagonist(s), and supporting characters.
Each character should have distinct traits, backgrounds, motivations, and arcs that fit the story.

Respond with characters formatted according to this JSON schema: {json.dumps(CHARACTER_SCHEMA)}
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
                    
                    characters = response["parsed_json"]
                    logger.info(f"Generated {len(characters.get('characters', []))} characters using OpenAI")
                    
                    # Store in memory
                    self._store_in_memory(characters)
                    
                    return characters
                except Exception as e:
                    logger.warning(f"OpenAI character generation failed: {e}, falling back to Ollama")
            
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
                    characters = json.loads(json_str)
                else:
                    raise ValueError("Could not extract valid JSON from Ollama response")
                
                logger.info(f"Generated {len(characters.get('characters', []))} characters using Ollama")
                
                # Store in memory
                self._store_in_memory(characters)
                
                return characters
            
            raise Exception("No available AI service (OpenAI or Ollama) to generate characters")
            
        except Exception as e:
            logger.error(f"Character generation error: {e}")
            raise Exception(f"Failed to generate characters: {e}")
    
    def develop_character(
        self,
        character_id: str,
        development_prompt: str
    ) -> Dict[str, Any]:
        """
        Develop a specific character with more details.
        
        Args:
            character_id: ID of the character to develop
            development_prompt: Specific directions for character development
            
        Returns:
            Dictionary with developed character
        """
        # Retrieve the original character from memory
        original_characters = self.memory.query_memory(f"character_id:{character_id}", agent_name=self.name)
        
        if not original_characters:
            raise ValueError(f"Character with ID {character_id} not found in memory")
        
        original_character_doc = original_characters[0]
        original_character_text = original_character_doc['text']
        
        try:
            original_character = json.loads(original_character_text)
        except json.JSONDecodeError:
            raise ValueError(f"Invalid character data for ID {character_id}")
        
        # Build the system prompt
        system_prompt = """You are an expert character developer for novels and stories. 
Your task is to add depth and detail to an existing character based on specific development directions.
Enhance the character while maintaining consistency with their core traits.
Provide output in JSON format according to the provided schema."""
        
        # Build the user prompt
        user_prompt = f"""Develop the following character with more depth and detail based on these directions: {development_prompt}

Original character:
{original_character_text}

Enhance this character by adding more details to their background, personality, motivations, relationships, and arc.
Maintain consistency with their core identity while adding complexity and nuance.

Respond with the developed character formatted according to this JSON schema: {json.dumps(CHARACTER_SCHEMA['properties']['characters']['items'])}
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
                        max_tokens=2500
                    )
                    
                    developed_character = response["parsed_json"]
                    logger.info(f"Developed character {character_id} using OpenAI")
                    
                    # Update the character ID if it changed
                    if "id" in developed_character and developed_character["id"] != character_id:
                        developed_character["id"] = character_id
                    
                    # Store in memory
                    self.memory.add_document(
                        json.dumps(developed_character),
                        self.name,
                        metadata={"type": "developed_character", "character_id": character_id}
                    )
                    
                    return developed_character
                except Exception as e:
                    logger.warning(f"OpenAI character development failed: {e}, falling back to Ollama")
            
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
                    developed_character = json.loads(json_str)
                else:
                    raise ValueError("Could not extract valid JSON from Ollama response")
                
                logger.info(f"Developed character {character_id} using Ollama")
                
                # Update the character ID if it changed
                if "id" in developed_character and developed_character["id"] != character_id:
                    developed_character["id"] = character_id
                
                # Store in memory
                self.memory.add_document(
                    json.dumps(developed_character),
                    self.name,
                    metadata={"type": "developed_character", "character_id": character_id}
                )
                
                return developed_character
            
            raise Exception("No available AI service (OpenAI or Ollama) to develop character")
            
        except Exception as e:
            logger.error(f"Character development error: {e}")
            raise Exception(f"Failed to develop character: {e}")
    
    def generate_character_relationships(
        self,
        character_ids: List[str]
    ) -> Dict[str, Any]:
        """
        Generate relationships between characters.
        
        Args:
            character_ids: List of character IDs to establish relationships
            
        Returns:
            Dictionary with character relationships
        """
        # Retrieve all specified characters from memory
        characters = []
        for character_id in character_ids:
            character_docs = self.memory.query_memory(f"character_id:{character_id}", agent_name=self.name)
            if character_docs:
                try:
                    character = json.loads(character_docs[0]['text'])
                    characters.append(character)
                except json.JSONDecodeError:
                    logger.warning(f"Invalid character data for ID {character_id}")
        
        if not characters:
            raise ValueError("No valid characters found in memory")
        
        # Build the system prompt
        system_prompt = """You are an expert in developing complex character relationships for novels and stories. 
Your task is to create meaningful, nuanced relationships between a set of characters.
These relationships should create narrative tension and opportunities for character development.
Provide output in JSON format."""
        
        # Build the user prompt
        character_summaries = "\n\n".join([
            f"Character: {char.get('name', 'Unknown')}\n"
            f"Role: {char.get('role', 'Unknown')}\n"
            f"Brief Description: {char.get('brief_description', 'Unknown')}"
            for char in characters
        ])
        
        user_prompt = f"""Develop meaningful relationships between the following characters:

{character_summaries}

For each relationship, specify:
1. The characters involved (by ID)
2. The type of relationship (family, friends, rivals, enemies, romantic, professional, etc.)
3. The history of their relationship
4. The current state of their relationship
5. Potential areas of conflict or development in their relationship

Respond with a JSON object in this format:
{{
  "relationships": [
    {{
      "character1_id": "char_001",
      "character2_id": "char_002",
      "relationship_type": "string",
      "history": "string",
      "current_state": "string",
      "tension_points": ["string"],
      "development_opportunities": ["string"]
    }}
  ]
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
                        max_tokens=2500
                    )
                    
                    relationships = response["parsed_json"]
                    logger.info(f"Generated relationships for {len(character_ids)} characters using OpenAI")
                    
                    # Store in memory
                    self.memory.add_document(
                        json.dumps(relationships),
                        self.name,
                        metadata={"type": "character_relationships"}
                    )
                    
                    return relationships
                except Exception as e:
                    logger.warning(f"OpenAI relationship generation failed: {e}, falling back to Ollama")
            
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
                    relationships = json.loads(json_str)
                else:
                    raise ValueError("Could not extract valid JSON from Ollama response")
                
                logger.info(f"Generated relationships for {len(character_ids)} characters using Ollama")
                
                # Store in memory
                self.memory.add_document(
                    json.dumps(relationships),
                    self.name,
                    metadata={"type": "character_relationships"}
                )
                
                return relationships
            
            raise Exception("No available AI service (OpenAI or Ollama) to generate character relationships")
            
        except Exception as e:
            logger.error(f"Character relationship generation error: {e}")
            raise Exception(f"Failed to generate character relationships: {e}")
    
    def _store_in_memory(self, characters: Dict[str, Any]) -> None:
        """
        Store generated characters in memory.
        
        Args:
            characters: Dictionary with generated characters
        """
        if "characters" not in characters or not isinstance(characters["characters"], list):
            logger.warning("Invalid characters format for memory storage")
            return
        
        # Store the entire characters dict
        self.memory.add_document(
            json.dumps(characters),
            self.name,
            metadata={"type": "character_results"}
        )
        
        # Store each individual character for easier retrieval
        for character in characters["characters"]:
            character_id = character.get("id")
            if not character_id:
                continue
                
            self.memory.add_document(
                json.dumps(character),
                self.name,
                metadata={"type": "character", "character_id": character_id}
            )
    
    def get_all_characters(self) -> List[Dict[str, Any]]:
        """
        Get all characters from memory.
        
        Returns:
            List of character dictionaries
        """
        # Query for all characters in memory
        character_docs = self.memory.get_agent_memory(self.name)
        
        if not character_docs:
            raise ValueError("No characters found in memory")
        
        # Filter for individual characters (not sets)
        individual_characters = []
        
        for doc in character_docs:
            metadata = doc.get('metadata', {})
            if metadata.get('type') in ['character', 'developed_character']:
                try:
                    character = json.loads(doc['text'])
                    individual_characters.append(character)
                except json.JSONDecodeError:
                    continue
        
        # Deduplicate characters by ID
        # If there are multiple versions of a character, keep the developed version
        character_map = {}
        for character in individual_characters:
            character_id = character.get('id')
            if character_id:
                if character_id not in character_map or metadata.get('type') == 'developed_character':
                    character_map[character_id] = character
        
        return list(character_map.values())
