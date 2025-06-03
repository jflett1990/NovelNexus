import logging
import json
from typing import Dict, Any, List, Optional
from datetime import datetime


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
            use_openai: Whether to use OpenAI API
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
        
        # Build user prompt
        user_prompt = f"Edit Chapter {chapter_number}: {chapter_title} for publication:\n\n"
        user_prompt += f"{edit_instructions}\n\n"
        
        if style_text:
            user_prompt += f"Style Guidelines:\n{style_text}\n\n"
            
        user_prompt += f"Original Chapter Content:\n{chapter_content}\n\n"
        user_prompt += "Provide the complete edited text, maintaining the author's voice and style while improving technical quality.\n"
        user_prompt += "Your edits should be professional and subtle, focusing on making the text ready for publication."
        
        try:
            # Generate edited content
            response = self.openai_client.generate(
                prompt=user_prompt,
                system_prompt=system_prompt,
                model="gpt-4o",
                temperature=0.4  # Lower temperature for more precise editing
            )
            
            edited_content = response.get("content", "")
            logger.info(f"Edited chapter {chapter_id} using OpenAI")
            
            # Create the edited chapter
            edited_chapter = chapter_data.copy()
            edited_chapter["content"] = edited_content
            edited_chapter["word_count"] = len(edited_content.split())
            edited_chapter["edit_notes"] = {
                "edit_date": datetime.now().isoformat(),
                "edits_performed": edits_requested or ["comprehensive_edit"]
            }
            
            self._store_in_memory(edited_chapter)
            
            return edited_chapter
            
        except Exception as e:
            logger.error(f"Error editing chapter: {str(e)}")
            # Return original chapter with error info
            chapter_data["edit_error"] = str(e)
            return chapter_data
    
    def create_front_matter(
        self,
        book_info: Dict[str, Any],
        outline: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create front matter for the book, including title page, copyright, dedication, etc.
        
        Args:
            book_info: Dictionary with book information
            outline: Optional outline of the book
            
        Returns:
            Dictionary with generated front matter
        """
        logger.info(f"Creating front matter for project {self.project_id}")
        
        # Extract key information
        title = book_info.get("title", "")
        genre = book_info.get("genre", "")
        author = book_info.get("author", "Anonymous")
        
        # Get the current year for copyright
        current_year = datetime.now().year
        
        # Build the system prompt
        system_prompt = """You are an expert literary editor specializing in creating professional front matter for books.
Your task is to create all the standard front matter elements for a book, including title page, 
copyright notice, dedication, table of contents, and any other appropriate elements.
The front matter should be professional, complete, and appropriate for the book's genre and style.
Provide output in JSON format according to the specified schema."""
        
        # Build the user prompt
        user_prompt = f"""Create complete front matter for a book with the following details:

Title: {title}
Genre: {genre}
Author: {author}
Year: {current_year}

Include these standard front matter elements:
1. Title page
2. Copyright page
3. Dedication (create an appropriate placeholder)
4. Table of contents (use chapter titles from outline if available, or create generic chapter titles)
5. Epigraph (create an appropriate quote related to the book's theme or genre)
6. Author's note (create a brief placeholder)

Format the response as a JSON object with these fields:
- title_page: Text for the title page
- copyright_page: Full copyright text
- dedication: Dedication text
- table_of_contents: Table of contents as text
- epigraph: Epigraph text and attribution
- authors_note: Brief author's note text
- other_elements: Array of any other elements you think should be included

Be creative but professional, and make all elements appropriate for the book's genre.
"""
        
        try:
            # Generate front matter
            response = self.openai_client.generate(
                prompt=user_prompt,
                system_prompt=system_prompt,
                json_mode=True,
                model="gpt-4o"
            )
            
            front_matter = response["parsed_json"]
            logger.info(f"Created front matter for project {self.project_id} using OpenAI")
            
            # Store in memory
            self.memory.add_document(
                json.dumps(front_matter),
                self.name,
                metadata={"type": "front_matter"}
            )
            
            return front_matter
            
        except Exception as e:
            logger.error(f"Error creating front matter: {str(e)}")
            # Generate fallback front matter
            fallback_front_matter = self._generate_fallback_front_matter(book_info)
            self.memory.add_document(
                json.dumps(fallback_front_matter),
                self.name,
                metadata={"type": "front_matter", "is_fallback": True}
            )
            return fallback_front_matter
    
    def create_back_matter(
        self,
        book_info: Dict[str, Any],
        outline: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create back matter for the book, including author bio, acknowledgments, etc.
        
        Args:
            book_info: Dictionary with book information
            outline: Optional outline of the book
            
        Returns:
            Dictionary with generated back matter
        """
        logger.info(f"Creating back matter for project {self.project_id}")
        
        # Extract key information
        title = book_info.get("title", "")
        genre = book_info.get("genre", "")
        author = book_info.get("author", "Anonymous")
        
        # Build the system prompt
        system_prompt = """You are an expert literary editor specializing in creating professional back matter for books.
Your task is to create standard back matter elements for a book, including acknowledgments, 
author biography, and other appropriate elements.
The back matter should be professional and appropriate for the book's genre and style.
Provide output in JSON format according to the specified schema."""
        
        # Build the user prompt
        user_prompt = f"""Create complete back matter for a book with the following details:

Title: {title}
Genre: {genre}
Author: {author}

Include the following standard back matter elements:
1. About the Author page with a generic biography
2. Acknowledgments page with generic acknowledgments
3. Any other back matter typically included in a {genre} book

Format the back matter professionally, using proper spacing and layout conventions.
The elements should be ready to insert into a manuscript without further formatting.

Respond with the back matter elements in this JSON format:
{{
  "about_author": "Text content for the about the author page",
  "acknowledgments": "Text content for the acknowledgments page",
  "other_back_matter": [
    {{
      "name": "Name of additional back matter element",
      "content": "Text content for that element"
    }}
  ]
}}
"""
        
        try:
            # Try OpenAI if enabled
            if self.use_openai and self.openai_client:
                try:
                    response = self.openai_client.generate(
                        prompt=user_prompt,
                        system_prompt=system_prompt,
                        json_mode=True,
                        temperature=0.7,
                        max_tokens=1500
                    )
                    
                    back_matter = response.get("parsed_json", {})
                    logger.info(f"Created back matter using OpenAI")
                    
                    # Store in memory
                    self.memory.add_document(
                        json.dumps(back_matter),
                        self.name,
                        metadata={"type": "back_matter"}
                    )
                    
                    return back_matter
                except Exception as e:
                    logger.warning(f"OpenAI back matter creation failed: {e}, using fallback")
            
            # If OpenAI is not enabled or failed, use fallback
            return self._generate_fallback_back_matter(book_info)
            
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

    def _generate_fallback_front_matter(self, book_info: Dict[str, Any]) -> Dict[str, Any]:
        """Generate fallback front matter when API calls fail."""
        title = book_info.get("title", "Untitled")
        author = book_info.get("author", "Anonymous")
        current_year = datetime.now().year
        
        front_matter = {
            "title_page": f"{title}\n\nBy {author}",
            "copyright_page": f"Copyright © {current_year} by {author}\nAll rights reserved.",
            "dedication_page": "To the readers who bring these words to life.",
            "table_of_contents": "Table of Contents\n\n[Generated upon final manuscript assembly]",
            "other_front_matter": []
        }
        
        # Store in memory
        self.memory.add_document(
            json.dumps(front_matter),
            self.name,
            metadata={"type": "front_matter"}
        )
        
        logger.info(f"Created fallback front matter")
        return front_matter

    def _generate_fallback_back_matter(self, book_info: Dict[str, Any]) -> Dict[str, Any]:
        """Generate fallback back matter when API calls fail."""
        author = book_info.get("author", "Anonymous")
        
        back_matter = {
            "about_author": f"About the Author\n\n{author} is a passionate writer dedicated to crafting stories that resonate with readers.",
            "acknowledgments": "Acknowledgments\n\nThe author would like to thank everyone who supported the creation of this book.",
            "other_back_matter": []
        }
        
        # Store in memory
        self.memory.add_document(
            json.dumps(back_matter),
            self.name,
            metadata={"type": "back_matter"}
        )
        
        logger.info(f"Created fallback back matter")
        return back_matter
