import logging
import json
from typing import Dict, Any, List, Optional

from models.ollama_client import get_ollama_client
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
        use_openai: bool = True,
        use_ollama: bool = True
    ):
        """
        Initialize the Outline Agent.
        
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
                    logger.warning(f"OpenAI outline generation failed: {e}, falling back to Ollama")
            
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
                    outline = json.loads(json_str)
                else:
                    raise ValueError("Could not extract valid JSON from Ollama response")
                
                logger.info(f"Generated outline with {len(outline.get('chapters', []))} chapters using Ollama")
                
                # Store in memory
                self._store_in_memory(outline)
                
                return outline
            
            raise Exception("No available AI service (OpenAI or Ollama) to generate outline")
            
        except Exception as e:
            logger.error(f"Outline generation error: {e}")
            raise Exception(f"Failed to generate outline: {e}")
    
    def revise_chapter(
        self,
        chapter_id: str,
        revision_instructions: str
    ) -> Dict[str, Any]:
        """
        Revise a specific chapter in the outline.
        
        Args:
            chapter_id: ID of the chapter to revise
            revision_instructions: Instructions for the revision
            
        Returns:
            Dictionary with the revised chapter
        """
        # Get the original outline
        outline_docs = self.memory.get_agent_memory(self.name)
        
        original_outline = None
        original_chapter = None
        
        for doc in outline_docs:
            metadata = doc.get('metadata', {})
            
            if metadata.get('type') == 'outline':
                try:
                    outline_data = json.loads(doc['text'])
                    original_outline = outline_data
                    
                    # Find the chapter
                    if 'chapters' in outline_data:
                        for chapter in outline_data['chapters']:
                            if chapter.get('id') == chapter_id:
                                original_chapter = chapter
                                break
                    
                    if original_chapter:
                        break
                except json.JSONDecodeError:
                    continue
        
        if not original_outline or not original_chapter:
            raise ValueError(f"Chapter with ID {chapter_id} not found in outline")
        
        # Build the system prompt
        system_prompt = """You are an expert book outliner and story structure specialist.
Your task is to revise a specific chapter in a book outline based on provided instructions.
Maintain consistency with the overall book structure while implementing the requested changes.
Provide output in JSON format."""
        
        # Build the user prompt
        user_prompt = f"""Revise the following chapter in a book outline based on these instructions: {revision_instructions}

Original Chapter:
{json.dumps(original_chapter, indent=2)}

Context from Overall Outline:
Title: {original_outline.get('title', '')}
Genre: {original_outline.get('genre', '')}
Structure: {original_outline.get('structure', {}).get('description', '')}

Revise the chapter to address the instructions while maintaining consistency with the book's overall structure, themes, and character arcs.
Make the chapter stronger, more cohesive, and better aligned with the book's goals.

Respond with the revised chapter formatted as a JSON object matching the structure of the original chapter.
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
                    
                    revised_chapter = response["parsed_json"]
                    logger.info(f"Revised chapter {chapter_id} using OpenAI")
                    
                    # Update the chapter ID if it changed
                    if "id" in revised_chapter and revised_chapter["id"] != chapter_id:
                        revised_chapter["id"] = chapter_id
                    
                    # Store in memory
                    self.memory.add_document(
                        json.dumps(revised_chapter),
                        self.name,
                        metadata={"type": "revised_chapter", "chapter_id": chapter_id}
                    )
                    
                    return revised_chapter
                except Exception as e:
                    logger.warning(f"OpenAI chapter revision failed: {e}, falling back to Ollama")
            
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
                    revised_chapter = json.loads(json_str)
                else:
                    raise ValueError("Could not extract valid JSON from Ollama response")
                
                logger.info(f"Revised chapter {chapter_id} using Ollama")
                
                # Update the chapter ID if it changed
                if "id" in revised_chapter and revised_chapter["id"] != chapter_id:
                    revised_chapter["id"] = chapter_id
                
                # Store in memory
                self.memory.add_document(
                    json.dumps(revised_chapter),
                    self.name,
                    metadata={"type": "revised_chapter", "chapter_id": chapter_id}
                )
                
                return revised_chapter
            
            raise Exception("No available AI service (OpenAI or Ollama) to revise chapter")
            
        except Exception as e:
            logger.error(f"Chapter revision error: {e}")
            raise Exception(f"Failed to revise chapter: {e}")
    
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
            detail_type: Type of details to add (e.g., 'scenes', 'character_development', 'setting')
            detail_instructions: Instructions for adding details
            
        Returns:
            Dictionary with the enhanced chapter
        """
        # Get the original chapter
        chapter_docs = self.memory.query_memory(f"chapter_id:{chapter_id}", agent_name=self.name)
        
        # If no specific chapter, get from the outline
        if not chapter_docs:
            outline_docs = self.memory.get_agent_memory(self.name)
            
            for doc in outline_docs:
                metadata = doc.get('metadata', {})
                
                if metadata.get('type') == 'outline':
                    try:
                        outline_data = json.loads(doc['text'])
                        
                        # Find the chapter
                        if 'chapters' in outline_data:
                            for chapter in outline_data['chapters']:
                                if chapter.get('id') == chapter_id:
                                    # Found the chapter, create a memory doc for it
                                    self.memory.add_document(
                                        json.dumps(chapter),
                                        self.name,
                                        metadata={"type": "chapter", "chapter_id": chapter_id}
                                    )
                                    
                                    chapter_docs = [{"text": json.dumps(chapter)}]
                                    break
                    except json.JSONDecodeError:
                        continue
        
        if not chapter_docs:
            raise ValueError(f"Chapter with ID {chapter_id} not found")
        
        original_chapter_text = chapter_docs[0]['text']
        
        try:
            original_chapter = json.loads(original_chapter_text)
        except json.JSONDecodeError:
            raise ValueError(f"Invalid chapter data for ID {chapter_id}")
        
        # Build the system prompt
        system_prompt = f"""You are an expert book outliner specializing in adding detailed {detail_type} to chapter outlines.
Your task is to enhance a chapter outline by adding rich, specific {detail_type} details that improve the narrative quality.
Maintain consistency with the existing chapter while adding depth and clarity.
Provide output in JSON format."""
        
        # Build the user prompt
        user_prompt = f"""Enhance the following chapter outline by adding detailed {detail_type} based on these instructions: {detail_instructions}

Original Chapter:
{original_chapter_text}

Add rich {detail_type} details to this chapter that:
1. Enhance the narrative flow and pacing
2. Develop the characters and their arcs
3. Create vivid settings and atmosphere
4. Strengthen the themes and motifs
5. Maintain consistency with the existing chapter elements

Respond with the enhanced chapter formatted as a JSON object matching the structure of the original chapter,
but with additional {detail_type} details incorporated.
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
                    
                    enhanced_chapter = response["parsed_json"]
                    logger.info(f"Added {detail_type} details to chapter {chapter_id} using OpenAI")
                    
                    # Update the chapter ID if it changed
                    if "id" in enhanced_chapter and enhanced_chapter["id"] != chapter_id:
                        enhanced_chapter["id"] = chapter_id
                    
                    # Store in memory
                    self.memory.add_document(
                        json.dumps(enhanced_chapter),
                        self.name,
                        metadata={"type": "enhanced_chapter", "chapter_id": chapter_id, "detail_type": detail_type}
                    )
                    
                    return enhanced_chapter
                except Exception as e:
                    logger.warning(f"OpenAI chapter enhancement failed: {e}, falling back to Ollama")
            
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
                    enhanced_chapter = json.loads(json_str)
                else:
                    raise ValueError("Could not extract valid JSON from Ollama response")
                
                logger.info(f"Added {detail_type} details to chapter {chapter_id} using Ollama")
                
                # Update the chapter ID if it changed
                if "id" in enhanced_chapter and enhanced_chapter["id"] != chapter_id:
                    enhanced_chapter["id"] = chapter_id
                
                # Store in memory
                self.memory.add_document(
                    json.dumps(enhanced_chapter),
                    self.name,
                    metadata={"type": "enhanced_chapter", "chapter_id": chapter_id, "detail_type": detail_type}
                )
                
                return enhanced_chapter
            
            raise Exception(f"No available AI service (OpenAI or Ollama) to add {detail_type} details")
            
        except Exception as e:
            logger.error(f"Chapter enhancement error: {e}")
            raise Exception(f"Failed to add {detail_type} details to chapter: {e}")
    
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
