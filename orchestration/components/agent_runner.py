"""
Agent execution management for workflow orchestration.

Handles individual agent execution, error handling, and coordination.
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class AgentRunner:
    """Manages execution of individual agents within the workflow."""
    
    def __init__(self, project_id: str, agents: Dict[str, Any], central_hub, stage_manager, error_handler, recovery_manager):
        self.project_id = project_id
        self.agents = agents
        self.central_hub = central_hub
        self.stage_manager = stage_manager
        self.error_handler = error_handler
        self.recovery_manager = recovery_manager
        
        # Agent execution tracking
        self.current_agent: Optional[str] = None
        self.agent_start_time: Optional[str] = None
    
    def run_agent(self, agent_key: str, **kwargs) -> Any:
        """
        Run an agent with proper error handling and recovery.
        
        Args:
            agent_key: Key of the agent in the agents dictionary
            **kwargs: Additional arguments to pass to the agent
            
        Returns:
            Result from the agent execution
        """
        try:
            # Record the start time for this agent
            self.agent_start_time = datetime.now().isoformat()
            self.current_agent = agent_key
            
            logger.info(f"Running agent {agent_key} for project {self.project_id}")
            
            # Call appropriate method based on agent key
            result = self._execute_agent_method(agent_key, **kwargs)
            
            # Mark stage as completed
            self.stage_manager.complete_stage(agent_key)
            
            return result
            
        except Exception as e:
            # Handle the error
            error_details = self.error_handler.handle_agent_error(
                agent_key, e, self.stage_manager.current_stage
            )
            
            # Attempt recovery
            try:
                self.recovery_manager.attempt_recovery(agent_key, error_details)
            except Exception as recovery_error:
                logger.error(f"Recovery attempt failed for {agent_key}: {str(recovery_error)}")
                raise e  # Re-raise original error if recovery fails
    
    def _execute_agent_method(self, agent_key: str, **kwargs) -> Any:
        """Execute the appropriate method for the given agent."""
        if agent_key == "ideation":
            return self.agents[agent_key].generate_ideas(
                title=kwargs.get('title', ''),
                genre=kwargs.get('genre', ''),
                initial_prompt=kwargs.get('initial_prompt', ''),
                complexity=kwargs.get('complexity', 'medium')
            )
        
        elif agent_key == "character":
            integrated_data = self.central_hub.aggregate_ideation_data()
            return self.agents[agent_key].generate_characters(
                idea=integrated_data.get("selected_idea", {}),
                world_context={},
                num_characters=5,
                user_prompt=kwargs.get('user_prompt'),
                system_prompt=kwargs.get('system_prompt')
            )
        
        elif agent_key == "world_building":
            idea_data = self.central_hub.aggregate_ideation_data()
            return self.agents[agent_key].generate_world(
                book_idea=idea_data.get("selected_idea", {}),
                complexity=kwargs.get('complexity', 'medium')
            )
        
        elif agent_key == "research":
            integrated_data = self.central_hub.aggregate_ideation_data()
            return self.agents[agent_key].generate_research(
                book_idea=integrated_data.get("selected_idea", {}),
                num_topics=5,
                complexity=kwargs.get('complexity', 'medium')
            )
        
        elif agent_key == "plot":
            # Get all necessary data for plot development
            idea_data = self.central_hub.aggregate_ideation_data()
            character_data = self._get_stage_data("character")
            world_data = self._get_stage_data("world")
            
            return self.agents[agent_key].generate_plot(
                book_idea=idea_data.get("selected_idea", {}),
                characters=character_data,
                world_data=world_data,
                complexity=kwargs.get('complexity', 'medium')
            )
        
        elif agent_key == "chapter_planner":
            integrated_data = self.central_hub.integrate_all_data()
            
            manuscript_outline = {
                "title": kwargs.get('title') or integrated_data.get("selected_idea", {}).get("title", "Untitled"),
                "genre": kwargs.get('genre', ''),
                "target_length": kwargs.get('target_length', 'medium'),
                "plot": self._get_stage_data("plot"),
                "characters": self._get_stage_data("character"),
                "world": self._get_stage_data("world"),
                "idea": integrated_data.get("selected_idea", {})
            }
            
            return self.agents[agent_key].plan_chapters(manuscript_outline)
        
        elif agent_key == "chapter_writer":
            # This is handled differently as it involves multiple chapter writing operations
            return self._handle_chapter_writing(**kwargs)
        
        elif agent_key == "manuscript":
            chapters = kwargs.get('chapters', [])
            return self.agents[agent_key].assemble_manuscript(chapters=chapters)
        
        else:
            logger.warning(f"Unknown agent key: {agent_key}")
            return None
    
    def _handle_chapter_writing(self, **kwargs) -> list:
        """Handle the chapter writing process for multiple chapters."""
        chapter_plan = kwargs.get('chapter_plan', [])
        previous_chapter_content = None
        chapters = []
        
        # If chapter planning gave no chapters, create at least one fallback chapter
        if not chapter_plan:
            logger.warning("No chapters in chapter plan, creating fallback chapter")
            fallback_chapter = {
                "number": 1,
                "title": "Chapter 1",
                "summary": "Introduction to the story and characters"
            }
            chapter_plan = [fallback_chapter]
        
        total_chapters = len(chapter_plan)
        
        for i, chapter in enumerate(chapter_plan):
            chapter_number = chapter.get("number", i + 1)
            self.stage_manager.update_stage(f"writing_chapter_{chapter_number}")
            
            try:
                logger.info(f"Writing chapter {chapter_number} of {total_chapters}")
                chapter_data = self.agents["chapter_writer"].write_chapter(
                    chapter_plan=chapter,
                    previous_chapter_content=previous_chapter_content
                )
                chapters.append(chapter_data)
                
                # Update for next chapter
                previous_chapter_content = chapter_data.get("content", "")
                
                self.stage_manager.complete_stage(f"writing_chapter_{chapter_number}")
                
                # Update progress based on chapters completed
                progress = int(80 + ((i + 1) / total_chapters) * 20)  # 80% base progress + up to 20% for chapters
                self.stage_manager._update_progress(progress)
                
            except Exception as e:
                logger.error(f"Error writing chapter {chapter_number}: {str(e)}")
                # Create fallback chapter and continue
                fallback_chapter = self.recovery_manager.create_fallback_chapter(chapter_number)
                chapters.append(fallback_chapter)
                self.error_handler.log_stage_error(f"writing_chapter_{chapter_number}", str(e))
        
        return chapters
    
    def _get_stage_data(self, stage: str) -> Optional[Dict[str, Any]]:
        """Get data from a specific workflow stage."""
        try:
            import json
            if stage == "character":
                data = self.central_hub.memory.query_memory("type:characters", agent_name="character_agent")
            elif stage == "world":
                data = self.central_hub.memory.query_memory("type:world", agent_name="world_building_agent")
            elif stage == "plot":
                data = self.central_hub.memory.query_memory("type:plot", agent_name="plot_agent")
            else:
                return None
            
            if data:
                return json.loads(data[0]["text"])
        except:
            pass
        return None
    
    def get_available_agents(self) -> list:
        """Get list of available agent keys."""
        return list(self.agents.keys())
    
    def get_current_agent(self) -> Optional[str]:
        """Get the currently executing agent."""
        return self.current_agent
