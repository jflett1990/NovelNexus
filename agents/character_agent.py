import logging
import json
import re
from typing import Dict, Any, List, Optional
from datetime import datetime

from models.openai_client import get_openai_client
from memory.dynamic_memory import DynamicMemory
from schemas.character_schema import CHARACTER_SCHEMA
from utils.json_utils import robust_json_parse, with_retries, verify_memory_write
from utils.validation_utils import validate_characters, validate_character_relationships

logger = logging.getLogger(__name__)

# Regular expressions for robust JSON extraction
JSON_PATTERN = r'(\{[\s\S]*\})'
JSON_ARRAY_PATTERN = r'(\[[\s\S]*\])'

class CharacterAgent:
    def __init__(self, memory: DynamicMemory, use_openai=True, openai_client=None, project_id=None):
        self.memory = memory
        self.use_openai = use_openai
        self.openai_client = openai_client or (get_openai_client() if use_openai else None)
        self.project_id = project_id
        self.name = "character_agent"

    def sanitize_json(self, json_str: str) -> str:
        """
        RESPOND ONLY WITH A VALID JSON ARRAY of character objects with this exact schema:
        """
        pass

    def generate_characters(self, idea: Dict[str, Any], world_context: Dict[str, Any], num_characters: int = 5, user_prompt: str = None, system_prompt: str = None):
        characters = []
        try:
            # Set default prompts if not provided
            if system_prompt is None:
                system_prompt = """You are an expert in character development for novels.
Your task is to create compelling, realistic, and well-rounded fictional characters.
Focus on creating depth, internal conflicts, and interesting relationships.

IMPORTANT: Your output MUST be valid JSON following the exact schema specified.
Do not include any text or markdown outside the JSON array."""

            if user_prompt is None:
                genre = idea.get("genre", "fiction")
                title = idea.get("title", "Story")
                user_prompt = f"""Create {num_characters} unique characters for a {genre} novel titled "{title}".

For each character, include:
1. Name and role in the story
2. Personality traits, strengths, and flaws
3. Background and backstory relevant to the plot
4. Goals, motivations, and conflicts
5. Physical description
6. Character arc - how they might change throughout the story

RESPOND ONLY WITH A VALID JSON ARRAY of character objects with this exact schema:
[
  {{
    "name": "Character's name",
    "role": "Protagonist/Antagonist/Supporting Character/etc.",
    "personality": "Description of personality traits, strengths, flaws",
    "background": "Character's backstory and history",
    "goals": "Character's motivations and objectives",
    "conflicts": "Internal and external challenges the character faces",
    "arc": "How the character changes throughout the story",
    "relationships": [],
    "physical_description": "Character's appearance"
  }}
]"""

            if self.use_openai and self.openai_client:
                try:
                    response = self.openai_client.generate(
                        prompt=user_prompt,
                        system_prompt=system_prompt,
                        json_mode=True,
                        temperature=0.8,
                        max_tokens=3000
                    )
                    
                    parsed_characters = response.get("parsed_json", [])
                    
                    # Validate and fix character data using our validation utility
                    validated_data = validate_characters(parsed_characters)
                    characters = validated_data.get("characters", [])
                    
                    logger.info(f"Generated {len(characters)} characters using OpenAI")
                except Exception as e:
                    logger.warning(f"OpenAI character generation failed: {str(e)}")

            if not characters:
                logger.warning(f"Using fallback character generation for project {self.project_id}")
                fallback_chars = self._create_fallback_characters(num_characters, idea, world_context)
                # Even validate our fallback characters
                validated_data = validate_characters(fallback_chars)
                characters = validated_data.get("characters", [])

            successful_chars = []
            for char in characters:
                char_name = char.get("name", "Unnamed")
                success = verify_memory_write(
                    self.memory,
                    json.dumps(char),
                    self.name,
                    metadata={"type": "character", "name": char_name}
                )
                if success:
                    successful_chars.append(char)
                    logger.debug(f"Successfully stored character '{char_name}' in memory")
                else:
                    logger.warning(f"Failed to store character '{char_name}' in memory")

            logger.info(f"Successfully stored {len(successful_chars)} characters in memory")

            if len(successful_chars) >= 2:
                try:
                    self._generate_character_relationships(successful_chars)
                except Exception as e:
                    logger.error(f"Error generating character relationships: {str(e)}")

            return successful_chars

        except Exception as e:
            logger.error(f"Error in character generation: {str(e)}")
            fallback_chars = self._create_fallback_characters(num_characters, idea, world_context)
            # Validate fallback characters
            validated_data = validate_characters(fallback_chars)
            validated_chars = validated_data.get("characters", [])

            for char in validated_chars:
                try:
                    self.memory.add_document(
                        json.dumps(char),
                        self.name,
                        metadata={"type": "character", "name": char.get("name", "Unnamed")}
                    )
                except Exception:
                    pass

            return validated_chars

    def _create_fallback_characters(self, num_chars: int, idea: Dict[str, Any], world: Dict[str, Any]) -> List[Dict[str, Any]]:
        genre = idea.get("genre", "fiction")

        fallback_roles = [
            "Protagonist",
            "Antagonist", 
            "Supporting Character",
            "Mentor",
            "Ally"
        ]

        characters = []
        for i in range(min(num_chars, len(fallback_roles))):
            char = {
                "name": f"Character {i+1}",
                "role": fallback_roles[i],
                "personality": "Complex personality appropriate for their role in the story",
                "background": "Background appropriate for the genre and setting", 
                "goals": f"Goals aligned with their role as {fallback_roles[i]}",
                "conflicts": "Internal and external conflicts driving character development",
                "arc": "Character growth throughout the story",
                "relationships": [],
                "physical_description": f"Appearance appropriate for a {genre} {fallback_roles[i].lower()}"
            }
            characters.append(char)

        return characters

    def _generate_character_relationships(self, characters: List[Dict[str, Any]]) -> None:
        if not characters or len(characters) < 2:
            logger.warning("Cannot generate relationships: No valid characters found in memory")
            return

        char_info = []
        for char in characters:
            name = char.get("name", "")
            role = char.get("role", "")
            if name:
                char_info.append(f"{name} ({role})")

        system_prompt = """You are an expert in character relationships for stories.
Your task is to create realistic, interesting relationships between characters.
These relationships should create narrative tension, emotional depth, and story opportunities.

IMPORTANT: Your output MUST be valid JSON following the exact schema specified.
Do not include any text or markdown outside the JSON array."""

        char_list = "\n".join([f"- {info}" for info in char_info])
        user_prompt = f"""Create relationships between the following characters in a {characters[0].get('genre', '')} story:

{char_list}

For each pair of characters that have a significant relationship, define:
1. The nature of their relationship 
2. The history between them
3. The current dynamics and tensions
4. How their relationship affects the story

RESPOND ONLY WITH A VALID JSON ARRAY of relationship objects with this exact schema:
[
  {{
    "character1": "Name of first character",
    "character2": "Name of second character",
    "relationship_type": "Description of relationship (allies, rivals, family, etc.)",
    "dynamics": "Description of the relationship dynamics",
    "history": "Brief history between the characters",
    "story_impact": "How this relationship affects the story"
  }}
]

Important reminders:
1. All keys must be in quotes
2. No trailing commas in arrays or objects
3. Use double quotes for strings, not single quotes
4. Output must be a JSON array of relationship objects
5. Do not include any explanatory text outside the JSON"""

        try:
            relationships = []

            if self.use_openai and self.openai_client:
                try:
                    response = self.openai_client.generate(
                        prompt=user_prompt,
                        system_prompt=system_prompt,
                        json_mode=True,
                        temperature=0.7,
                        max_tokens=3000
                    )

                    parsed_rels = response.get("parsed_json", [])
                    
                    # Validate the relationships
                    validated_rels = validate_character_relationships(parsed_rels, characters)
                    relationships = validated_rels
                    
                    logger.info(f"Generated {len(relationships)} character relationships using OpenAI")
                except Exception as e:
                    logger.warning(f"OpenAI relationship generation failed: {str(e)}, falling back to Ollama")

            if not relationships:
                # Generate fallback relationships if OpenAI fails
                logger.warning("No valid relationships generated, creating fallbacks")
                fallback_rels = self._create_fallback_relationships(characters)
                # Validate the fallback relationships
                validated_rels = validate_character_relationships(fallback_rels, characters)
                relationships = validated_rels
                
            # Store the relationships in memory
            successful_rels = []
            for rel in relationships:
                rel_key = f"{rel.get('character1', 'Unknown')}-{rel.get('character2', 'Unknown')}"
                success = verify_memory_write(
                    self.memory,
                    json.dumps(rel),
                    self.name,
                    metadata={"type": "character_relationship", "key": rel_key}
                )
                if success:
                    successful_rels.append(rel)
                    logger.debug(f"Successfully stored relationship '{rel_key}' in memory")
                else:
                    logger.warning(f"Failed to store relationship '{rel_key}' in memory")

            logger.info(f"Successfully stored {len(successful_rels)} character relationships in memory")

        except Exception as e:
            logger.error(f"Error in generating character relationships: {str(e)}")
            # If there's an error, generate and store fallback relationships
            fallback_rels = self._create_fallback_relationships(characters)
            for rel in fallback_rels:
                try:
                    rel_key = f"{rel.get('character1', 'Unknown')}-{rel.get('character2', 'Unknown')}"
                    self.memory.add_document(
                        json.dumps(rel),
                        self.name,
                        metadata={"type": "character_relationship", "key": rel_key}
                    )
                except Exception:
                    pass

    def _create_fallback_relationships(self, characters: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        # Implementation of _create_fallback_relationships method
        pass

    def get_characters(self) -> List[Dict[str, Any]]:
        try:
            docs = self.memory.get_agent_memory(self.name)

            if not docs:
                logger.warning(f"No character data found in memory for project {self.project_id}")
                return []

            characters = []
            for doc in docs:
                metadata = doc.get('metadata', {})
                if metadata.get('type') != 'character':
                    continue

                try:
                    char_data = robust_json_parse(doc['text'])
                    if char_data and isinstance(char_data, dict) and "name" in char_data:
                        characters.append(char_data)
                except Exception as e:
                    logger.warning(f"Error parsing character document: {str(e)}")

            if not characters:
                logger.warning(f"No valid character data found in memory for project {self.project_id}")
            else:
                logger.info(f"Retrieved {len(characters)} characters from memory")

            return characters
        except Exception as e:
            logger.error(f"Error retrieving characters from memory: {str(e)}")
            return []

    def get_character_relationships(self) -> List[Dict[str, Any]]:
        try:
            docs = self.memory.query_memory("type:character_relationships", agent_name=self.name)

            if not docs:
                characters = self.get_characters()
                relationships = self._extract_relationships_from_characters(characters)
                if relationships:
                    logger.info(f"Extracted {len(relationships)} implied relationships from character data")
                    return relationships

                logger.warning(f"No relationship data found in memory for project {self.project_id}")
                return []

            for doc in docs:
                try:
                    rel_data = robust_json_parse(doc['text'])
                    if isinstance(rel_data, list) and rel_data:
                        logger.info(f"Retrieved {len(rel_data)} character relationships from memory")
                        return rel_data
                    elif isinstance(rel_data, dict) and "relationships" in rel_data:
                        rels = rel_data["relationships"]
                        if isinstance(rels, list):
                            logger.info(f"Retrieved {len(rels)} character relationships from memory")
                            return rels
                except Exception as e:
                    logger.warning(f"Error parsing relationship document: {str(e)}")

            logger.warning("No valid relationship data found in memory")
            return []
        except Exception as e:
            logger.error(f"Error retrieving character relationships from memory: {str(e)}")
            return []

    def _extract_relationships_from_characters(self, characters: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        extracted_rels = []
        processed_pairs = set()

        for char in characters:
            char_name = char.get("name")
            if not char_name or "relationships" not in char:
                continue

            for rel in char.get("relationships", []):
                other_name = rel.get("with")
                if not other_name:
                    continue

                pair = tuple(sorted([char_name, other_name]))
                if pair in processed_pairs:
                    continue

                processed_pairs.add(pair)

                rel_obj = {
                    "character1": char_name,
                    "character2": other_name,
                    "relationship_type": rel.get("type", "Connection"),
                    "dynamics": rel.get("dynamics", "Complex relationship"),
                    "history": rel.get("history", "Shared history relevant to the story"),
                    "story_impact": rel.get("story_impact", "Impacts the narrative in meaningful ways")
                }

                extracted_rels.append(rel_obj)

        return extracted_rels

    # Additional methods such as develop_character, _get_world_context etc. can be added similarly
