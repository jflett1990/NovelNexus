"""
Context Manager for Inter-Agent Communication

This module provides utilities for agents to retrieve and share context
from previous workflow stages, ensuring proper context handoff and
eliminating disconnected content generation.
"""

import logging
import json
from typing import Dict, Any, List, Optional
from memory.dynamic_memory import DynamicMemory

logger = logging.getLogger(__name__)


class WorkflowContextManager:
    """
    Manages context retrieval and sharing between workflow stages.
    
    This class provides a centralized way for agents to access context
    from previous workflow stages, ensuring proper context handoff and
    coherent narrative generation.
    """
    
    def __init__(self, memory: DynamicMemory, project_id: str):
        """
        Initialize the context manager.
        
        Args:
            memory: Dynamic memory instance for the project
            project_id: Unique identifier for the project
        """
        self.memory = memory
        self.project_id = project_id
    
    def get_comprehensive_context(self, current_stage: str) -> Dict[str, Any]:
        """
        Retrieve comprehensive context from all previous workflow stages.
        
        Args:
            current_stage: The current workflow stage requesting context
            
        Returns:
            Dictionary containing context from all relevant previous stages
        """
        context = {
            "ideation": {},
            "research": {},
            "characters": [],
            "world_building": {},
            "plot": {},
            "chapter_plans": [],
            "previous_chapters": []
        }
        
        try:
            # Get ideation context
            context["ideation"] = self._get_ideation_context()
            
            # Get research context
            context["research"] = self._get_research_context()
            
            # Get character context
            context["characters"] = self._get_character_context()
            
            # Get world-building context
            context["world_building"] = self._get_world_building_context()
            
            # Get plot context
            context["plot"] = self._get_plot_context()
            
            # Get chapter planning context (if applicable)
            if current_stage in ["chapter_writing", "longform_expansion", "editorial_review"]:
                context["chapter_plans"] = self._get_chapter_plans_context()
                context["previous_chapters"] = self._get_previous_chapters_context()
            
            logger.info(f"Retrieved comprehensive context for {current_stage} stage")
            
        except Exception as e:
            logger.error(f"Error retrieving comprehensive context: {str(e)}")
        
        return context
    
    def _get_ideation_context(self) -> Dict[str, Any]:
        """Retrieve ideation context from memory."""
        try:
            # Try to get selected idea first
            docs = self.memory.query_memory("type:selected_idea", agent_name="ideation_agent")
            if not docs:
                # Fall back to any idea
                docs = self.memory.query_memory("type:idea", agent_name="ideation_agent")
            
            if docs:
                ideation_data = json.loads(docs[0]["text"])
                logger.debug("Retrieved ideation context from memory")
                return ideation_data
                
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            logger.warning(f"Failed to parse ideation context: {str(e)}")
        
        return {}
    
    def _get_research_context(self) -> Dict[str, Any]:
        """Retrieve research context from memory."""
        try:
            docs = self.memory.query_memory("type:research", agent_name="research_agent")
            if docs:
                research_data = json.loads(docs[0]["text"])
                logger.debug("Retrieved research context from memory")
                return research_data
                
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            logger.warning(f"Failed to parse research context: {str(e)}")
        
        return {}
    
    def _get_character_context(self) -> List[Dict[str, Any]]:
        """Retrieve character context from memory."""
        try:
            docs = self.memory.query_memory("type:character", agent_name="character_agent")
            characters = []
            
            for doc in docs:
                try:
                    char_data = json.loads(doc["text"])
                    if isinstance(char_data, dict) and "name" in char_data:
                        characters.append(char_data)
                except json.JSONDecodeError:
                    continue
            
            if characters:
                logger.debug(f"Retrieved {len(characters)} characters from memory")
            
            return characters
            
        except Exception as e:
            logger.warning(f"Failed to retrieve character context: {str(e)}")
        
        return []
    
    def _get_world_building_context(self) -> Dict[str, Any]:
        """Retrieve world-building context from memory."""
        try:
            docs = self.memory.query_memory("type:world", agent_name="world_building_agent")
            if docs:
                world_data = json.loads(docs[0]["text"])
                logger.debug("Retrieved world-building context from memory")
                return world_data
                
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            logger.warning(f"Failed to parse world-building context: {str(e)}")
        
        return {}
    
    def _get_plot_context(self) -> Dict[str, Any]:
        """Retrieve plot context from memory."""
        try:
            docs = self.memory.query_memory("type:plot", agent_name="plot_agent")
            if docs:
                plot_data = json.loads(docs[0]["text"])
                logger.debug("Retrieved plot context from memory")
                return plot_data
                
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            logger.warning(f"Failed to parse plot context: {str(e)}")
        
        return {}
    
    def _get_chapter_plans_context(self) -> List[Dict[str, Any]]:
        """Retrieve chapter plans context from memory."""
        try:
            docs = self.memory.query_memory("type:chapter_plan", agent_name="chapter_planner_agent")
            chapter_plans = []
            
            for doc in docs:
                try:
                    plan_data = json.loads(doc["text"])
                    if isinstance(plan_data, dict):
                        chapter_plans.append(plan_data)
                    elif isinstance(plan_data, list):
                        chapter_plans.extend(plan_data)
                except json.JSONDecodeError:
                    continue
            
            if chapter_plans:
                logger.debug(f"Retrieved {len(chapter_plans)} chapter plans from memory")
            
            return chapter_plans
            
        except Exception as e:
            logger.warning(f"Failed to retrieve chapter plans context: {str(e)}")
        
        return []
    
    def _get_previous_chapters_context(self) -> List[Dict[str, Any]]:
        """Retrieve previous chapters context from memory."""
        try:
            docs = self.memory.query_memory("type:chapter", agent_name="chapter_writer_agent")
            chapters = []
            
            for doc in docs:
                try:
                    chapter_data = json.loads(doc["text"])
                    if isinstance(chapter_data, dict) and "number" in chapter_data:
                        chapters.append(chapter_data)
                except json.JSONDecodeError:
                    continue
            
            # Sort chapters by number
            chapters.sort(key=lambda x: x.get("number", 0))
            
            if chapters:
                logger.debug(f"Retrieved {len(chapters)} previous chapters from memory")
            
            return chapters
            
        except Exception as e:
            logger.warning(f"Failed to retrieve previous chapters context: {str(e)}")
        
        return []
    
    def build_context_prompt(self, context: Dict[str, Any], focus_areas: List[str] = None) -> str:
        """
        Build a formatted context prompt for AI generation.
        
        Args:
            context: Context dictionary from get_comprehensive_context()
            focus_areas: List of context areas to focus on (optional)
            
        Returns:
            Formatted context string for inclusion in prompts
        """
        if not focus_areas:
            focus_areas = ["ideation", "characters", "world_building", "plot"]
        
        prompt_parts = []
        
        # Add ideation context
        if "ideation" in focus_areas and context.get("ideation"):
            idea = context["ideation"]
            prompt_parts.append(f"""
STORY CONCEPT:
- Title: {idea.get('title', 'Untitled')}
- Genre: {idea.get('genre', 'Fiction')}
- Plot Summary: {idea.get('plot_summary', 'Not specified')}
- Themes: {', '.join(idea.get('themes', []))}
- Target Audience: {idea.get('target_audience', 'General')}""")
        
        # Add character context
        if "characters" in focus_areas and context.get("characters"):
            characters = context["characters"]
            char_info = []
            for char in characters[:5]:  # Limit to top 5 characters
                char_info.append(f"- {char.get('name', 'Unknown')} ({char.get('role', 'Character')}): {char.get('personality', 'Complex personality')}")
            
            if char_info:
                prompt_parts.append(f"""
MAIN CHARACTERS:
{chr(10).join(char_info)}""")
        
        # Add world-building context
        if "world_building" in focus_areas and context.get("world_building"):
            world = context["world_building"]
            prompt_parts.append(f"""
WORLD SETTING:
- Setting: {world.get('setting', 'Not specified')}
- Time Period: {world.get('time_period', 'Not specified')}
- Key Locations: {', '.join([loc.get('name', 'Unknown') for loc in world.get('locations', [])[:3]])}""")
        
        # Add plot context
        if "plot" in focus_areas and context.get("plot"):
            plot = context["plot"]
            prompt_parts.append(f"""
PLOT STRUCTURE:
- Main Conflict: {plot.get('main_conflict', 'Not specified')}
- Story Arcs: {len(plot.get('arcs', []))} major arcs
- Planned Chapters: {len(plot.get('chapters', []))} chapters""")
        
        return "\n".join(prompt_parts) if prompt_parts else ""


def create_context_manager(memory: DynamicMemory, project_id: str) -> WorkflowContextManager:
    """
    Factory function to create a WorkflowContextManager instance.
    
    Args:
        memory: Dynamic memory instance
        project_id: Project identifier
        
    Returns:
        Configured WorkflowContextManager instance
    """
    return WorkflowContextManager(memory, project_id)
