import logging
import json
from typing import Dict, Any, List, Optional

from models.openai_client import get_openai_client
from memory.dynamic_memory import DynamicMemory
from datetime import datetime
from agents.style_priming_agent import prime_prompt

logger = logging.getLogger(__name__)

class ManuscriptAgent:
    """
    Agent responsible for assembling the final manuscript from individual chapters.
    """
    
    def __init__(
        self,
        project_id: str,
        memory: DynamicMemory,
        use_openai: bool = True
    ):
        """
        Initialize the Manuscript Agent.
        
        Args:
            project_id: Unique identifier for the project
            memory: Dynamic memory instance
            use_openai: Whether to use OpenAI models
        """
        self.project_id = project_id
        self.memory = memory
        self.use_openai = use_openai
        
        self.openai_client = get_openai_client() if use_openai else None
        
        self.name = "manuscript_agent"
        self.stage = "manuscript"
    
    def assemble_manuscript(self, chapters: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Assemble the final manuscript from chapters.
        
        Args:
            chapters: List of chapter data dictionaries
            
        Returns:
            Dictionary with assembled manuscript data
        """
        logger.info("Assembling final manuscript from chapters")
        
        # Sort chapters by number if needed
        sorted_chapters = sorted(chapters, key=lambda x: x.get("number", 1))
        
        # Get integrated data for metadata
        integrated_data = self._get_integrated_data()
        
        # Extract manuscript title
        title = integrated_data.get("title", "")
        if not title:
            title = integrated_data.get("selected_idea", {}).get("title", "Untitled Manuscript")
        
        # Extract author (placeholder)
        author = "AI Author"
        
        # Create front matter
        front_matter = self._create_front_matter(title, author)
        
        # Create table of contents
        toc = self._create_table_of_contents(sorted_chapters)
        
        # Assemble chapter content
        chapters_content = ""
        total_word_count = 0
        
        for chapter in sorted_chapters:
            chapter_title = chapter.get("title", f"Chapter {chapter.get('number', '?')}")
            chapter_content = chapter.get("content", "")
            chapter_word_count = chapter.get("word_count", len(chapter_content.split()))
            
            # Format chapter for manuscript
            chapters_content += f"\n\n# {chapter_title}\n\n{chapter_content}\n\n"
            total_word_count += chapter_word_count
        
        # Create back matter
        back_matter = self._create_back_matter(integrated_data)
        
        # Assemble full manuscript
        full_manuscript = f"{front_matter}\n\n{toc}\n\n{chapters_content}\n\n{back_matter}"
        
        # Create manuscript data structure
        manuscript_data = {
            "title": title,
            "author": author,
            "word_count": total_word_count,
            "chapter_count": len(sorted_chapters),
            "front_matter": front_matter,
            "toc": toc,
            "chapters": sorted_chapters,
            "back_matter": back_matter,
            "full_text": full_manuscript
        }
        
        # Save the final manuscript to memory
        self.memory.add_document(
            json.dumps(manuscript_data),
            self.name,
            metadata={
                "type": "final_manuscript",
                "title": manuscript_data["title"],
                "word_count": manuscript_data["word_count"]
            }
        )
        
        # Store an additional copy with type:manuscript for easier retrieval
        self.memory.add_document(
            json.dumps(manuscript_data),
            self.name,
            metadata={
                "type": "manuscript",
                "title": manuscript_data["title"],
                "word_count": manuscript_data["word_count"]
            }
        )
        
        # Also save just the full manuscript text for semantic search
        self.memory.add_document(
            full_manuscript,
            self.name,
            metadata={"type": "final_manuscript_text"}
        )
        
        logger.info(f"Successfully assembled final manuscript with {len(sorted_chapters)} chapters and {total_word_count} words")
        return manuscript_data

    def build_chapter_prompt(self, chapter: Dict[str, Any], context: Dict[str, Any]) -> str:
        """
        Builds a rich, styled prompt for chapter generation.
        
        Args:
            chapter: The chapter data including number, title, and goals
            context: Context data including title, genre, themes, characters
            
        Returns:
            A fully formed prompt for chapter generation
        """
        base = f"""You are continuing a literary novel.

Title: {context.get('title')}
Genre: {context.get('genre')}
Themes: {', '.join(context.get('themes', []))}

Chapter {chapter['number']}: {chapter['title']}
Goals: {chapter.get('goals', 'Advance plot and deepen characters')}

Story So Far:
{context.get('summary_so_far', 'This is the beginning of the story.')}

Characters In Focus:
{', '.join(context.get('characters', []))}

Instructions:
- Write 2000-2500 words.
- Emphasize character interiority, ambiguity, and unique metaphor.
- Avoid clichés and simplistic resolution.
- Maintain consistent voice and stylistic tone.

Generate the full chapter as compelling prose. Do not return JSON, just the story text.
"""
        return prime_prompt(base, style="atwood", themes=context.get("themes", []))
    
    def _create_front_matter(self, title: str, author: str) -> str:
        """Create front matter for the manuscript."""
        return f"""# {title}

By {author}

---

Copyright © {author}

All rights reserved.

---"""
    
    def _create_table_of_contents(self, chapters: List[Dict[str, Any]]) -> str:
        """Create a table of contents from chapters."""
        toc = "# Table of Contents\n\n"
        
        for chapter in chapters:
            chapter_number = chapter.get("number", "?")
            chapter_title = chapter.get("title", f"Chapter {chapter_number}")
            toc += f"Chapter {chapter_number}: {chapter_title}\n"
        
        return toc
    
    def _create_back_matter(self, integrated_data: Dict[str, Any]) -> str:
        """Create back matter for the manuscript."""
        # Create character appendix if characters exist
        character_appendix = ""
        characters = integrated_data.get("characters", [])
        
        if characters and len(characters) > 0:
            character_appendix = "# Character Appendix\n\n"
            
            for character in characters:
                name = character.get("name", "Unknown")
                role = character.get("role", "")
                description = character.get("description", "")
                personality = character.get("personality", "")
                
                character_appendix += f"## {name}\n\n"
                if role:
                    character_appendix += f"Role: {role}\n\n"
                if description:
                    character_appendix += f"{description}\n\n"
                if personality:
                    character_appendix += f"Personality: {personality}\n\n"
        
        # Create world appendix if world data exists
        world_appendix = ""
        world_data = integrated_data.get("world_building", {})
        
        if world_data and len(world_data) > 0:
            world_appendix = "# World Appendix\n\n"
            
            # Extract key world elements
            for key, value in world_data.items():
                if isinstance(value, str) and value:
                    world_appendix += f"## {key.replace('_', ' ').title()}\n\n{value}\n\n"
        
        # Create author's note
        authors_note = f"""# Author's Note

Thank you for reading this AI-generated novel. This manuscript was created using language models to explore creative storytelling possibilities.

Generated on: {self._get_project_status().get("completion_time", "Unknown date")}"""
        
        # Combine back matter elements
        back_matter = ""
        if character_appendix:
            back_matter += character_appendix + "\n\n"
        if world_appendix:
            back_matter += world_appendix + "\n\n"
        back_matter += authors_note
        
        return back_matter
    
    def get_final_manuscript(self) -> Optional[Dict[str, Any]]:
        """Get the final manuscript if available."""
        manuscript_docs = self.memory.query_memory("type:final_manuscript", agent_name=self.name)
        
        if manuscript_docs and len(manuscript_docs) > 0:
            try:
                manuscript_data = json.loads(manuscript_docs[0]["text"])
                return manuscript_data
            except json.JSONDecodeError:
                logger.error("Failed to parse manuscript JSON")
                return None
            except Exception as e:
                logger.error(f"Error retrieving final manuscript: {str(e)}")
                return None
        
        logger.warning("No final manuscript found")
        return None
    
    def _get_integrated_data(self) -> Dict[str, Any]:
        """
        Get integrated data from memory for manuscript assembly.
        Returns a composite of data from all stages of the workflow.
        """
        integrated_data = {}
        
        # Get ideation data
        ideation_docs = self.memory.query_memory("type:selected_idea", agent_name="ideation_agent")
        if ideation_docs and len(ideation_docs) > 0:
            try:
                selected_idea = json.loads(ideation_docs[0]["text"])
                integrated_data["selected_idea"] = selected_idea
                integrated_data["title"] = selected_idea.get("title", "")
                integrated_data["genre"] = selected_idea.get("genre", "")
                integrated_data["themes"] = selected_idea.get("themes", [])
                if isinstance(integrated_data["themes"], str):
                    integrated_data["themes"] = [t.strip() for t in integrated_data["themes"].split(",")]
            except Exception as e:
                logger.error(f"Error parsing ideation data: {str(e)}")
        
        # Get character data
        character_docs = self.memory.query_memory("type:characters", agent_name="character_agent")
        if character_docs and len(character_docs) > 0:
            try:
                characters = json.loads(character_docs[0]["text"])
                integrated_data["characters"] = characters
                
                # Extract character names for easier access
                character_names = [character.get("name", "Unknown") for character in characters]
                integrated_data["character_names"] = character_names
            except Exception as e:
                logger.error(f"Error parsing character data: {str(e)}")
        
        # Get world data
        world_docs = self.memory.query_memory("type:world", agent_name="world_building_agent")
        if world_docs and len(world_docs) > 0:
            try:
                world_data = json.loads(world_docs[0]["text"])
                integrated_data["world_building"] = world_data
            except Exception as e:
                logger.error(f"Error parsing world data: {str(e)}")
        
        # Get plot data
        plot_docs = self.memory.query_memory("type:plot", agent_name="plot_agent")
        if plot_docs and len(plot_docs) > 0:
            try:
                plot_data = json.loads(plot_docs[0]["text"])
                integrated_data["plot"] = plot_data
                
                # Create a summary for context
                plot_summary = plot_data.get("summary", "")
                if not plot_summary and "overview" in plot_data:
                    plot_summary = plot_data["overview"]
                
                integrated_data["plot_summary"] = plot_summary
            except Exception as e:
                logger.error(f"Error parsing plot data: {str(e)}")
        
        # Get research data
        research_docs = self.memory.query_memory("type:research", agent_name="research_agent")
        if research_docs and len(research_docs) > 0:
            try:
                research_data = json.loads(research_docs[0]["text"])
                integrated_data["research"] = research_data
            except Exception as e:
                logger.error(f"Error parsing research data: {str(e)}")
        
        return integrated_data
    
    def _get_project_status(self) -> Dict[str, Any]:
        """Get current project status."""
        status = {
            "completion_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        return status 