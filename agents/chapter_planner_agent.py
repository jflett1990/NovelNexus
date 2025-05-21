import logging
import json
from typing import List, Dict, Any, Optional

from models.openai_client import get_openai_client
from memory.dynamic_memory import DynamicMemory
from utils.json_utils import parse_json_safely

logger = logging.getLogger(__name__)

class ChapterPlannerAgent:
    """
    Agent responsible for planning and structuring chapters in a manuscript.
    This helps break down large manuscripts into manageable segments.
    """
    
    def __init__(self, project_id: str, memory: DynamicMemory, use_openai: bool = True):
        """
        Initialize the chapter planner agent.
        
        Args:
            project_id: Unique identifier for the project
            memory: Memory interface
            use_openai: Whether to use OpenAI (default) or another model
        """
        self.project_id = project_id
        self.memory = memory
        self.name = "chapter_planner_agent"
        
        if use_openai:
            # Use OpenAI
            from models.openai_client import get_openai_client
            self.openai_client = get_openai_client()
            self.model_name = "gpt-4o"
            self.provider = "openai"
            logger.info(f"Initialized chapter planner agent with model {self.model_name}")
        else:
            # Fallback to OpenAI anyway
            from models.openai_client import get_openai_client
            self.openai_client = get_openai_client()
            self.model_name = "gpt-4o"
            self.provider = "openai"
            logger.info(f"Initialized chapter planner agent with model {self.model_name}")
    
    def plan_chapters(self, manuscript_outline: Dict[str, Any], previous_chapters: List[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Generate a detailed chapter plan based on manuscript outline.
        
        Args:
            manuscript_outline: The complete outline of the manuscript
            previous_chapters: Optional list of already completed chapters
            
        Returns:
            List of chapter plans with details
        """
        if not manuscript_outline:
            logger.error("Cannot plan chapters without manuscript outline")
            return self._create_fallback_chapter_plan(12)
            
        # Format the outline for the prompt
        outline_text = self._format_outline_for_prompt(manuscript_outline)
        
        # Include information about previous chapters if available
        previous_chapters_text = ""
        if previous_chapters and len(previous_chapters) > 0:
            previous_chapters_text = "Previously completed chapters:\n"
            for chapter in previous_chapters:
                previous_chapters_text += f"Chapter {chapter.get('number')}: {chapter.get('title')} - {chapter.get('summary', 'No summary')}\n"
        
        # Target number of chapters based on the outline
        target_chapters = len(manuscript_outline.get("chapters", [])) if "chapters" in manuscript_outline else 0
        if target_chapters == 0:
            # Set a reasonable default for target chapters
            target_chapters = 12
            logger.warning(f"No chapters found in outline, defaulting to {target_chapters} chapters")
        
        # Build the planning prompt
        prompt = f"""As a literary chapter planner, create detailed chapter plans for a novel based on this outline:

{outline_text}

{previous_chapters_text}

Plan the next {target_chapters} chapters (or remaining chapters if less). For each chapter, provide:
1. Chapter number
2. Title
3. POV character (if applicable)
4. Location/setting
5. Time frame
6. Key plot points
7. Character development goals
8. Themes to emphasize
9. Important revelations or turning points
10. Brief scene-by-scene breakdown
11. Writing objectives
12. Approximate target word count
13. Chapter summary (100-200 words)

Format your response as a valid JSON array of chapter objects, with each chapter containing these fields.
Follow this exact JSON structure:
[
  {{
    "number": 1,
    "title": "Chapter Title",
    "pov": "Character Name",
    "setting": "Location",
    "timeframe": "When this occurs",
    "plot_points": ["Point 1", "Point 2"...],
    "character_development": ["Goal 1", "Goal 2"...],
    "themes": ["Theme 1", "Theme 2"...],
    "revelations": ["Revelation 1", "Revelation 2"...],
    "scenes": ["Scene 1", "Scene 2"...],
    "objectives": ["Objective 1", "Objective 2"...],
    "word_count": 3000,
    "summary": "Detailed summary of the chapter"
  }},
  ...
]"""

        try:
            response = self.openai_client.generate(
                prompt=prompt,
                model=self.model_name
            )
            
            if self.provider == "openai":
                chapters_json = response.get("content", "").strip()
            else:
                chapters_json = response.get("content", "").strip()
            
            # Extract JSON array from response
            chapters_json = self._extract_json(chapters_json)
            
            # Parse chapter plans
            try:
                chapter_plans = json.loads(chapters_json)
                
                # Ensure it's a list - if it's an object with a chapters key, extract that
                if isinstance(chapter_plans, dict) and "chapters" in chapter_plans:
                    chapter_plans = chapter_plans["chapters"]
                
                if not isinstance(chapter_plans, list):
                    logger.error("JSON response is not a list or object with chapters key")
                    return self._create_fallback_chapter_plan(target_chapters)
                
                # Validate structure
                for chapter in chapter_plans:
                    required_fields = ["number", "title", "summary"]
                    for field in required_fields:
                        if field not in chapter:
                            chapter[field] = f"Missing {field}"
                
                logger.info(f"Successfully created {len(chapter_plans)} chapter plans")
                return chapter_plans
            except json.JSONDecodeError as e:
                logger.error(f"Error parsing JSON from chapter planning: {str(e)}")
                # Use fallback plan
                return self._create_fallback_chapter_plan(target_chapters)
            
        except Exception as e:
            logger.error(f"Error planning chapters: {str(e)}")
            # Use fallback plan
            return self._create_fallback_chapter_plan(target_chapters)
    
    def _create_chapter_planning_prompt(self, outline, genre, target_chapter_count, previous_chapters=None) -> str:
        """Create a prompt for chapter planning."""
        previous_chapters_text = ""
        if previous_chapters and len(previous_chapters) > 0:
            previous_chapters_text = "PREVIOUSLY WRITTEN CHAPTERS:\n"
            for chapter in previous_chapters:
                previous_chapters_text += f"Chapter {chapter.get('number')}: {chapter.get('title')}\n"
                previous_chapters_text += f"Summary: {chapter.get('summary')}\n\n"
        
        next_chapter_number = 1
        if previous_chapters and len(previous_chapters) > 0:
            next_chapter_number = max([ch.get("number", 0) for ch in previous_chapters]) + 1
        
        remaining_chapters = target_chapter_count - (next_chapter_number - 1)
        
        return f"""You are a professional novelist and chapter planner. 
Your task is to create a detailed chapter plan for a {genre} novel.

NOVEL OUTLINE:
{json.dumps(outline, indent=2)}

{previous_chapters_text}

Please create a plan for {remaining_chapters} more chapters, starting with Chapter {next_chapter_number}.
For each chapter, provide:
1. Chapter number
2. A compelling title that fits the genre
3. A summary of events that will occur in the chapter (250-300 words)

Make sure the chapters follow a coherent narrative arc and provide a satisfying progression.
Each chapter should move the story forward with clear stakes and purpose.

Respond with ONLY a JSON object in this exact format:
{{
  "chapters": [
    {{
      "number": (chapter number),
      "title": "(chapter title)",
      "summary": "(detailed chapter summary)"
    }},
    ...
  ]
}}"""
    
    def _create_fallback_chapter_plan(self, target_chapter_count) -> List[Dict[str, Any]]:
        """Create a fallback chapter plan if generation fails."""
        chapters = []
        for i in range(1, target_chapter_count + 1):
            if i == 1:
                chapter = {
                    "number": i,
                    "title": "The Beginning",
                    "summary": "Introduction of the main characters and the initial problem or goal."
                }
            elif i == target_chapter_count:
                chapter = {
                    "number": i,
                    "title": "Resolution",
                    "summary": "The final resolution of the main conflict and conclusion of character arcs."
                }
            else:
                # Calculate if this is early, middle, or late in the story
                progress = i / target_chapter_count
                if progress < 0.3:
                    phase = "early"
                    summary = "Building the world and establishing character relationships. The main conflict becomes more defined."
                elif progress < 0.7:
                    phase = "middle"
                    summary = "Complications arise and characters face increasingly difficult challenges. Stakes are raised."
                else:
                    phase = "late"
                    summary = "Major turning points occur as the story builds toward its climax. Character arcs reach critical moments."
                
                chapter = {
                    "number": i,
                    "title": f"Chapter {i}",
                    "summary": summary
                }
            
            chapters.append(chapter)
        
        return chapters

    def _format_outline_for_prompt(self, manuscript_outline: Dict[str, Any]) -> str:
        """
        Format the manuscript outline for inclusion in a prompt.
        
        Args:
            manuscript_outline: The complete outline of the manuscript
            
        Returns:
            Formatted outline text
        """
        try:
            # Extract key elements from the outline
            title = manuscript_outline.get("title", "Untitled")
            genre = manuscript_outline.get("genre", "Unknown")
            target_length = manuscript_outline.get("target_length", "medium")
            
            # Extract characters
            characters_text = ""
            characters = manuscript_outline.get("characters", [])
            if characters:
                characters_text = "CHARACTERS:\n"
                for idx, character in enumerate(characters):
                    name = character.get("name", f"Character {idx+1}")
                    role = character.get("role", "")
                    desc = character.get("description", "")
                    characters_text += f"- {name} ({role}): {desc}\n"
            
            # Extract world building
            world_text = ""
            world = manuscript_outline.get("world", {})
            if world:
                world_text = "WORLD:\n"
                world_name = world.get("name", "")
                world_desc = world.get("description", "")
                world_text += f"{world_name}: {world_desc}\n"
                
                # Include locations if available
                locations = world.get("locations", [])
                if locations:
                    world_text += "LOCATIONS:\n"
                    for location in locations:
                        loc_name = location.get("name", "")
                        loc_desc = location.get("description", "")
                        world_text += f"- {loc_name}: {loc_desc}\n"
            
            # Extract plot
            plot_text = ""
            plot = manuscript_outline.get("plot", {})
            if plot:
                plot_text = "PLOT STRUCTURE:\n"
                
                # Add plot points if available
                plot_points = plot.get("plot_points", [])
                if plot_points:
                    plot_text += "Plot Points:\n"
                    for point in plot_points:
                        plot_text += f"- {point}\n"
                
                # Add arcs if available
                arcs = plot.get("arcs", [])
                if arcs:
                    plot_text += "Character Arcs:\n"
                    for arc in arcs:
                        plot_text += f"- {arc}\n"
                
                # Add scenes if available
                scenes = plot.get("scenes", [])
                if scenes:
                    plot_text += "Key Scenes:\n"
                    for scene in scenes:
                        plot_text += f"- {scene}\n"
            
            # Extract main idea
            idea_text = ""
            idea = manuscript_outline.get("idea", {})
            if idea:
                idea_text = "MAIN CONCEPT:\n"
                idea_text += f"{idea.get('concept', '')}\n\n"
                idea_text += f"THEMES: {', '.join(idea.get('themes', []))}\n"
            
            # Combine all elements
            outline_text = f"""TITLE: {title}
GENRE: {genre}
TARGET LENGTH: {target_length}

{idea_text}

{characters_text}

{world_text}

{plot_text}
"""
            return outline_text
            
        except Exception as e:
            logger.error(f"Error formatting outline for prompt: {str(e)}")
            # Return a simplified version if parsing fails
            return json.dumps(manuscript_outline, indent=2)
            
    def _extract_json(self, text: str) -> str:
        """Extract JSON content from the text response."""
        try:
            # Try to parse as is first (might be valid JSON already)
            json.loads(text)
            return text
        except json.JSONDecodeError:
            # Look for JSON array start/end if not valid
            start_idx = text.find('[')
            end_idx = text.rfind(']')
            
            if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
                json_str = text[start_idx:end_idx+1]
                try:
                    # Validate the extracted JSON
                    json.loads(json_str)
                    return json_str
                except json.JSONDecodeError:
                    pass
            
            # Try another approach - look for JSON object with chapters array
            start_idx = text.find('{')
            end_idx = text.rfind('}')
            
            if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
                json_str = text[start_idx:end_idx+1]
                try:
                    # Validate the extracted JSON
                    json_obj = json.loads(json_str)
                    # If it has chapters array, return that
                    if "chapters" in json_obj and isinstance(json_obj["chapters"], list):
                        return json.dumps(json_obj["chapters"])
                    return json_str
                except json.JSONDecodeError:
                    pass
            
            # If all else fails, return empty array
            logger.error(f"Could not extract valid JSON from response: {text[:100]}...")
            return "[]" 