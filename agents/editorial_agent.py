import logging
import json
from typing import Dict, Any, List, Optional


from models.openai_client import get_openai_client
from memory.dynamic_memory import DynamicMemory

logger = logging.getLogger(__name__)

class EditorialAgent:
    """
    Agent responsible for final editorial refinement and manuscript assembly.
    """
    
    def __init__(
        self,
        project_id: str,
        memory: DynamicMemory,
        use_openai: bool = True
    ):
        """
        Initialize the Editorial Agent.
        
        Args:
            project_id: Unique identifier for the project
            memory: Dynamic memory instance
            use_openai: Whether to use OpenAI models
        """
        self.project_id = project_id
        self.memory = memory
        self.use_openai = use_openai
        
        self.openai_client = get_openai_client() if use_openai else None
        
        self.name = "editorial_agent"
        self.stage = "editorial"
    
    def edit_chapter(
        self,
        chapter_data: Dict[str, Any],
        style_guide: Optional[Dict[str, Any]] = None,
        edits_requested: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Perform editorial edits on a chapter.
        
        Args:
            chapter_data: Dictionary containing the chapter
            style_guide: Optional style guide for consistency
            edits_requested: Optional list of specific edits to make
            
        Returns:
            Dictionary with the edited chapter
        """
        logger.info(f"Editing chapter {chapter_data.get('id', 'unknown')} for project {self.project_id}")
        
        # Extract key information from chapter data
        chapter_id = chapter_data.get("id", "unknown")
        chapter_number = chapter_data.get("number", 0)
        chapter_title = chapter_data.get("title", "Untitled Chapter")
        chapter_content = chapter_data.get("content", "")
        
        # Extract style guide information if available
        style_text = ""
        if style_guide:
            style_text = json.dumps(style_guide, indent=2)
        
        # Build the system prompt
        system_prompt = """You are an expert editorial professional with years of experience in book editing.
Your task is to perform a final editorial pass on a book chapter, polishing the prose, fixing grammar and style issues,
and ensuring the chapter meets professional publishing standards.
Your edits should be subtle and respectful of the author's voice, focusing on clarity, correctness, and consistency.
Provide the complete edited text, ready for publication."""
        
        # Build the user prompt based on requested edits
        edit_instructions = "Perform a comprehensive final edit, focusing on:"
        
        if edits_requested:
            edit_list = [f"- {edit}" for edit in edits_requested]
            edit_instructions = "Perform the following specific edits:\n" + "\n".join(edit_list)
        else:
            edit_instructions += """
- Grammar and punctuation
- Sentence structure and flow
- Word choice and clarity
- Consistency in style and tone
- Removal of redundancies and awkward phrasing
- Appropriate paragraph breaks
- Dialogue formatting and punctuation"""
        
        # Build user prompt in parts to avoid f-string backslash issues
        user_prompt = f"Edit Chapter {chapter_number}: {chapter_title} for publication:\n\n"
        user_prompt += f"{edit_instructions}\n\n"
        
        if style_text:
            user_prompt += f"Style Guidelines:\n{style_text}\n\n"
            
        user_prompt += f"Original Chapter Content:\n{chapter_content}\n\n"
        user_prompt += "Provide the complete edited text, maintaining the author's voice and style while improving technical quality.\n"
        user_prompt += "Your edits should be professional and subtle, focusing on making the text ready for publication."
        
        try:
            # Try OpenAI first if enabled
            if self.use_openai and self.openai_client:
                try:
                    response = self.openai_client.generate(
                        prompt=user_prompt,
                        system_prompt=system_prompt,
                        temperature=0.4,  # Lower temperature for more precise editing
                        max_tokens=4000
                    )
                    
                    edited_content = response["text"]
                    logger.info(f"Edited chapter {chapter_id} using OpenAI")
                    
                    # Create the edited chapter
                    edited_chapter = chapter_data.copy()
                    edited_chapter["content"] = edited_content
                    edited_chapter["word_count"] = len(edited_content.split())
                    edited_chapter["edit_notes"] = {
                        "edit_date": self.memory.metadata.get('timestamp', ''),
                        "edits_performed": edits_requested or ["comprehensive_edit"]
                    }
                    
                    self._store_in_memory(edited_chapter)
                    
                    return edited_chapter
                except Exception as e:
                    logger.warning(f"OpenAI chapter editing failed: {e}, falling back to Ollama")
            
            # Fall back to Ollama if OpenAI failed or is not enabled
            if self.use_ollama and self.ollama_client:
                response = self.ollama_client.generate(
                    prompt=user_prompt,
                    system=system_prompt
                )
                
                edited_content = response.get("response", "")
                logger.info(f"Edited chapter {chapter_id} using Ollama")
                
                # Create the edited chapter
                edited_chapter = chapter_data.copy()
                edited_chapter["content"] = edited_content
                edited_chapter["word_count"] = len(edited_content.split())
                edited_chapter["edit_notes"] = {
                    "edit_date": self.memory.metadata.get('timestamp', ''),
                    "edits_performed": edits_requested or ["comprehensive_edit"]
                }
                
                self._store_in_memory(edited_chapter)
                
                return edited_chapter
            
            raise Exception("No available AI service (OpenAI or Ollama) to edit chapter")
            
        except Exception as e:
            logger.error(f"Chapter editing error: {e}")
            raise Exception(f"Failed to edit chapter: {e}")
    
    def create_front_matter(
        self,
        book_info: Dict[str, Any],
        outline: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create front matter for the book (title page, TOC, etc.).
        
        Args:
            book_info: Dictionary with book information
            outline: Optional outline of the book
            
        Returns:
            Dictionary with the front matter
        """
        logger.info(f"Creating front matter for project {self.project_id}")
        
        # Extract key information
        title = book_info.get("title", "Untitled Book")
        author = book_info.get("author", "Unknown Author")
        genre = book_info.get("genre", "")
        
        # Build the system prompt
        system_prompt = """You are an expert book designer specializing in creating professional front matter for books.
Your task is to create comprehensive front matter including title page, copyright page, table of contents, and dedication.
The front matter should be professionally formatted and ready for publication.
Provide output in JSON format with each element of the front matter as a separate section."""
        
        # Prepare chapter information for table of contents
        toc_info = ""
        if outline and "chapters" in outline:
            chapters = outline["chapters"]
            chapter_list = []
            for chapter in chapters:
                number = chapter.get("number", 0)
                title = chapter.get("title", "Untitled Chapter")
                chapter_list.append(f"Chapter {number}: {title}")
            
            toc_info = "\n".join(chapter_list)
        
        # Build the user prompt
        # Build the user prompt in parts to avoid f-string backslash issues
        user_prompt = f"Create professional front matter for the following book:\n\n"
        user_prompt += f"Title: {title}\n"
        user_prompt += f"Author: {author}\n"
        user_prompt += f"Genre: {genre}\n\n"
        
        if toc_info:
            user_prompt += f"Chapters for Table of Contents:\n{toc_info}\n\n"
            
        user_prompt += "Create the following front matter elements:\n"
        user_prompt += "1. Title Page\n"
        user_prompt += "2. Copyright Page\n"
        user_prompt += "3. Dedication Page\n"
        user_prompt += "4. Table of Contents\n"
        user_prompt += "5. Epigraph (optional)\n\n"
        user_prompt += "Make the front matter professional, properly formatted, and ready for publication.\n"
        user_prompt += "Use appropriate placeholder text where necessary (e.g., for copyright information, ISBN, etc.)\n\n"
        
        user_prompt += "Respond with the front matter formatted as a JSON object in this format:\n"
        user_prompt += "{\n"
        user_prompt += '  "title_page": {\n'
        user_prompt += '    "title": "string",\n'
        user_prompt += '    "subtitle": "string (if applicable)",\n'
        user_prompt += '    "author": "string",\n'
        user_prompt += '    "publisher": "string (if applicable)"\n'
        user_prompt += "  },\n"
        user_prompt += '  "copyright_page": "string (full formatted text)",\n'
        user_prompt += '  "dedication_page": "string (full formatted text)",\n'
        user_prompt += '  "epigraph": "string (full formatted text, if applicable)",\n'
        user_prompt += '  "table_of_contents": [\n'
        user_prompt += "    {\n"
        user_prompt += '      "title": "string",\n'
        user_prompt += '      "page": "string (if applicable)"\n'
        user_prompt += "    }\n"
        user_prompt += "  ]\n"
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
                    
                    front_matter = response["parsed_json"]
                    logger.info(f"Created front matter using OpenAI")
                    
                    # Store in memory
                    self.memory.add_document(
                        json.dumps(front_matter),
                        self.name,
                        metadata={"type": "front_matter"}
                    )
                    
                    return front_matter
                except Exception as e:
                    logger.warning(f"OpenAI front matter creation failed: {e}, falling back to Ollama")
            
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
                    front_matter = json.loads(json_str)
                else:
                    raise ValueError("Could not extract valid JSON from Ollama response")
                
                logger.info(f"Created front matter using Ollama")
                
                # Store in memory
                self.memory.add_document(
                    json.dumps(front_matter),
                    self.name,
                    metadata={"type": "front_matter"}
                )
                
                return front_matter
            
            raise Exception("No available AI service (OpenAI or Ollama) to create front matter")
            
        except Exception as e:
            logger.error(f"Front matter creation error: {e}")
            raise Exception(f"Failed to create front matter: {e}")
    
    def create_back_matter(
        self,
        book_info: Dict[str, Any],
        characters: Optional[List[Dict[str, Any]]] = None,
        world_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create back matter for the book (glossary, character list, etc.).
        
        Args:
            book_info: Dictionary with book information
            characters: Optional list of character dictionaries
            world_data: Optional world building data
            
        Returns:
            Dictionary with the back matter
        """
        logger.info(f"Creating back matter for project {self.project_id}")
        
        # Extract key information
        title = book_info.get("title", "Untitled Book")
        author = book_info.get("author", "Unknown Author")
        genre = book_info.get("genre", "")
        
        # Prepare character information
        character_info = ""
        if characters:
            char_list = []
            for char in characters:
                name = char.get("name", "Unknown")
                desc = char.get("brief_description", "")
                char_list.append(f"{name}: {desc}")
            
            character_info = "\n".join(char_list)
        
        # Prepare world information
        world_info = ""
        if world_data:
            world_type = world_data.get("world_type", "")
            setting = world_data.get("primary_setting", "")
            time_period = world_data.get("time_period", "")
            
            world_info = f"World Type: {world_type}\nPrimary Setting: {setting}\nTime Period: {time_period}"
            
            # Add locations if available
            if "locations" in world_data:
                locations = world_data["locations"]
                loc_list = []
                for loc in locations:
                    name = loc.get("name", "Unknown")
                    desc = loc.get("description", "")
                    loc_list.append(f"{name}: {desc}")
                
                world_info += "\n\nLocations:\n" + "\n".join(loc_list)
        
        # Build the system prompt
        system_prompt = """You are an expert book designer specializing in creating professional back matter for books.
Your task is to create comprehensive back matter including an about the author section, glossary, character list, and appendices as appropriate.
The back matter should be professionally formatted and ready for publication.
Provide output in JSON format with each element of the back matter as a separate section."""
        
        # Build the user prompt
        # Build user prompt in parts to avoid f-string backslash issues
        user_prompt = f"Create professional back matter for the following book:\n\n"
        user_prompt += f"Title: {title}\n"
        user_prompt += f"Author: {author}\n"
        user_prompt += f"Genre: {genre}\n\n"
        
        if character_info:
            user_prompt += f"Characters:\n{character_info}\n\n"
            
        if world_info:
            user_prompt += f"World Information:\n{world_info}\n\n"
            
        user_prompt += "Create the following back matter elements as appropriate for this book:\n"
        user_prompt += "1. About the Author\n"
        user_prompt += "2. Glossary of Terms\n"
        user_prompt += "3. Character List\n"
        user_prompt += "4. Map/World Description\n"
        user_prompt += "5. Appendices (if needed)\n\n"
        
        user_prompt += "Make the back matter professional, properly formatted, and ready for publication.\n"
        user_prompt += "Use appropriate placeholder text where necessary (e.g., for author biography).\n\n"
        
        user_prompt += "Respond with the back matter formatted as a JSON object in this format:\n"
        user_prompt += "{\n"
        user_prompt += '  "about_the_author": "string (full formatted text)",\n'
        user_prompt += '  "glossary": [\n'
        user_prompt += "    {\n"
        user_prompt += '      "term": "string",\n'
        user_prompt += '      "definition": "string"\n'
        user_prompt += "    }\n"
        user_prompt += "  ],\n"
        user_prompt += '  "character_list": [\n'
        user_prompt += "    {\n"
        user_prompt += '      "name": "string",\n'
        user_prompt += '      "description": "string"\n'
        user_prompt += "    }\n"
        user_prompt += "  ],\n"
        user_prompt += '  "world_description": "string (full formatted text)",\n'
        user_prompt += '  "appendices": [\n'
        user_prompt += "    {\n"
        user_prompt += '      "title": "string",\n'
        user_prompt += '      "content": "string"\n'
        user_prompt += "    }\n"
        user_prompt += "  ]\n"
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
                        max_tokens=3000
                    )
                    
                    back_matter = response["parsed_json"]
                    logger.info(f"Created back matter using OpenAI")
                    
                    # Store in memory
                    self.memory.add_document(
                        json.dumps(back_matter),
                        self.name,
                        metadata={"type": "back_matter"}
                    )
                    
                    return back_matter
                except Exception as e:
                    logger.warning(f"OpenAI back matter creation failed: {e}, falling back to Ollama")
            
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
                    back_matter = json.loads(json_str)
                else:
                    raise ValueError("Could not extract valid JSON from Ollama response")
                
                logger.info(f"Created back matter using Ollama")
                
                # Store in memory
                self.memory.add_document(
                    json.dumps(back_matter),
                    self.name,
                    metadata={"type": "back_matter"}
                )
                
                return back_matter
            
            raise Exception("No available AI service (OpenAI or Ollama) to create back matter")
            
        except Exception as e:
            logger.error(f"Back matter creation error: {e}")
            raise Exception(f"Failed to create back matter: {e}")
    
    def assemble_manuscript(
        self,
        book_info: Dict[str, Any],
        chapters: List[Dict[str, Any]],
        front_matter: Optional[Dict[str, Any]] = None,
        back_matter: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Assemble the complete manuscript from all components.
        
        Args:
            book_info: Dictionary with book information
            chapters: List of chapter dictionaries
            front_matter: Optional front matter
            back_matter: Optional back matter
            
        Returns:
            Dictionary with the complete manuscript
        """
        logger.info(f"Assembling manuscript for project {self.project_id}")
        
        # Sort chapters by number
        sorted_chapters = sorted(chapters, key=lambda x: x.get("number", 0))
        
        # Check if we have all required elements
        if not front_matter:
            logger.warning("Front matter not provided, generating basic front matter")
            front_matter = self.create_front_matter(book_info)
        
        if not back_matter:
            logger.warning("Back matter not provided, generating basic back matter")
            back_matter = self.create_back_matter(book_info)
        
        # Assemble the manuscript
        manuscript = {
            "title": book_info.get("title", "Untitled Book"),
            "author": book_info.get("author", "Unknown Author"),
            "genre": book_info.get("genre", ""),
            "front_matter": front_matter,
            "chapters": sorted_chapters,
            "back_matter": back_matter,
            "metadata": {
                "creation_date": self.memory.metadata.get('timestamp', ''),
                "word_count": sum(chapter.get("word_count", 0) for chapter in sorted_chapters),
                "chapter_count": len(sorted_chapters)
            }
        }
        
        # Store in memory
        self.memory.add_document(
            json.dumps(manuscript),
            self.name,
            metadata={"type": "complete_manuscript"}
        )
        
        return manuscript
    
    def _store_in_memory(self, chapter: Dict[str, Any]) -> None:
        """
        Store edited chapter in memory.
        
        Args:
            chapter: Dictionary with edited chapter
        """
        # Store chapter
        self.memory.add_document(
            json.dumps(chapter),
            self.name,
            metadata={
                "type": "edited_chapter",
                "id": chapter.get("id", "unknown"),
                "number": chapter.get("number", 0),
                "title": chapter.get("title", "Untitled")
            }
        )
    
    def get_final_manuscript(self) -> Optional[Dict[str, Any]]:
        """
        Get the final manuscript from memory.
        
        Returns:
            Dictionary with the complete manuscript or None if not found
        """
        # Query for manuscript in memory
        manuscript_docs = self.memory.query_memory("type:complete_manuscript", agent_name=self.name)
        
        if not manuscript_docs:
            return None
        
        try:
            return json.loads(manuscript_docs[0]['text'])
        except (json.JSONDecodeError, IndexError):
            return None
    
    def get_all_edited_chapters(self) -> List[Dict[str, Any]]:
        """
        Get all edited chapters from memory.
        
        Returns:
            List of dictionaries with edited chapters
        """
        # Query for all edited chapters in memory
        chapter_docs = self.memory.get_agent_memory(self.name)
        
        if not chapter_docs:
            return []
        
        # Filter for edited chapters
        chapters = []
        
        for doc in chapter_docs:
            metadata = doc.get('metadata', {})
            if metadata.get('type') == 'edited_chapter':
                try:
                    chapter = json.loads(doc['text'])
                    chapters.append(chapter)
                except json.JSONDecodeError:
                    continue
        
        # Sort by chapter number
        chapters.sort(key=lambda x: x.get("number", 0))
        
        return chapters
