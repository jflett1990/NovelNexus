"""
Refactored Manuscript Workflow - Modular Architecture

Main workflow orchestration using modular components for better maintainability
and separation of concerns.
"""

import logging
import threading
import os
import json
from datetime import datetime
from typing import Dict, Any, Optional

# Import workflow components
from .components import (
    StageManager, WorkflowErrorHandler, RecoveryManager, AgentRunner
)

# Import agents
from agents.ideation_agent import IdeationAgent
from agents.character_agent import CharacterAgent
from agents.world_building_agent import WorldBuildingAgent
from agents.research_agent import ResearchAgent
from agents.outline_agent import OutlineAgent
from agents.writing_agent import WritingAgent
from agents.review_agent import ReviewAgent
from agents.revision_agent import RevisionAgent
from agents.editorial_agent import EditorialAgent
from agents.plot_agent import PlotAgent
from agents.manuscript_agent import ManuscriptAgent
from agents.chapter_planner_agent import ChapterPlannerAgent
from agents.chapter_writer_agent import ChapterWriterAgent
from agents.longform_expander import LongformExpander
from agents.manuscript_refiner import ManuscriptRefiner

# Import integration hub
from hubs.central_hub import CentralHub

# Import memory system
from memory.dynamic_memory import DynamicMemory

# Import embedding functionality
from models.openai_client import get_openai_client

logger = logging.getLogger(__name__)


class ManuscriptWorkflow:
    """
    Main workflow orchestration for the manuscript generation process.
    
    This class implements a non-linear, agent-based workflow for generating
    a complete manuscript, managing the interactions between specialized agents
    and providing a central orchestration point.
    
    Refactored to use modular components for better maintainability.
    """
    
    def __init__(
        self,
        project_id: str,
        title: str = "",
        genre: str = "",
        target_length: str = "medium",
        complexity: str = "medium",
        embedding_model: str = "text-embedding-3-large",
        use_openai: bool = True,
        use_gpu: bool = False,
        initial_prompt: str = "",
    ):
        """
        Initialize the manuscript workflow.
        
        Args:
            project_id: Unique ID for the project
            title: Title for the book
            genre: Genre of the book
            target_length: Target length (short, medium, long)
            complexity: Complexity level (simple, medium, complex)
            embedding_model: Model to use for embeddings
            use_openai: Whether to use OpenAI for generation
            use_gpu: Whether to use GPU for generation
            initial_prompt: Initial prompt to seed the workflow
        """
        self.project_id = project_id
        self.title = title
        self.genre = genre
        self.target_length = target_length
        self.complexity = complexity
        self.embedding_model = embedding_model
        self.use_openai = use_openai
        self.use_gpu = use_gpu
        self.initial_prompt = initial_prompt
        
        # Status tracking
        self.is_running = False
        self.is_complete = False
        self.thread = None
        self.start_time = None
        
        # Create memory directory if it doesn't exist
        os.makedirs(f"memory_data/{project_id}", exist_ok=True)
        
        # Initialize memory with OpenAI embeddings
        self.openai_client = get_openai_client()
        embedding_function = lambda text: self.openai_client.get_embeddings(text, model=embedding_model)
        self.memory = DynamicMemory(project_id, embedding_function)
        self.central_hub = CentralHub(project_id, self.memory)
        
        # Initialize workflow components
        self.stage_manager = StageManager(project_id, self.central_hub)
        self.error_handler = WorkflowErrorHandler(project_id, self.central_hub, self.memory)
        self.recovery_manager = RecoveryManager(project_id, self.memory, self.stage_manager)
        
        # Create all agents
        self.agents = self._create_agents()
        
        # Initialize agent runner
        self.agent_runner = AgentRunner(
            project_id, self.agents, self.central_hub,
            self.stage_manager, self.error_handler, self.recovery_manager
        )
        
        # Initialize workflow data
        self._initialize_data()
        self.config = {}
    
    def _create_agents(self) -> Dict[str, Any]:
        """Create and return all workflow agents."""
        return {
            "ideation": IdeationAgent(
                project_id=self.project_id,
                memory=self.memory,
                use_openai=self.use_openai
            ),
            "character": CharacterAgent(
                project_id=self.project_id,
                memory=self.memory,
                use_openai=self.use_openai
            ),
            "world_building": WorldBuildingAgent(
                project_id=self.project_id,
                memory=self.memory,
                use_openai=self.use_openai
            ),
            "research": ResearchAgent(
                project_id=self.project_id,
                memory=self.memory,
                use_openai=self.use_openai
            ),
            "outline": OutlineAgent(
                project_id=self.project_id,
                memory=self.memory,
                use_openai=self.use_openai
            ),
            "chapter_planner": ChapterPlannerAgent(
                project_id=self.project_id,
                memory=self.memory,
                use_openai=self.use_openai
            ),
            "chapter_writer": ChapterWriterAgent(
                project_id=self.project_id,
                memory=self.memory,
                use_openai=self.use_openai
            ),
            "review": ReviewAgent(
                project_id=self.project_id,
                memory=self.memory,
                use_openai=self.use_openai
            ),
            "revision": RevisionAgent(
                project_id=self.project_id,
                memory=self.memory,
                use_openai=self.use_openai
            ),
            "plot": PlotAgent(
                project_id=self.project_id,
                memory=self.memory,
                use_openai=self.use_openai
            ),
            "editorial": EditorialAgent(
                project_id=self.project_id,
                memory=self.memory,
                use_openai=self.use_openai
            ),
            "expander": LongformExpander(
                model_name="gpt-4o"
            ),
            "manuscript": ManuscriptAgent(
                project_id=self.project_id,
                memory=self.memory,
                use_openai=self.use_openai
            ),
            "refiner": ManuscriptRefiner(
                project_id=self.project_id,
                model_name="gpt-4o"
            )
        }
    
    def _initialize_data(self):
        """Initialize workflow data in memory."""        
        # Store initial configuration
        initial_data = {
            "title": self.title,
            "genre": self.genre,
            "target_length": self.target_length,
            "complexity": self.complexity,
            "initial_prompt": self.initial_prompt,
            "creation_time": datetime.now().isoformat()
        }
        
        self.memory.add_document(
            json.dumps(initial_data),
            "workflow",
            metadata={"type": "project_config"}
        )
        
        # Store project status
        status_data = {
            "status": "not_started",
            "progress": 0,
            "current_stage": "not_started",
            "completed_stages": [],
            "start_time": None,
            "last_update": datetime.now().isoformat()
        }
        
        self.central_hub.update_project_status(status_data)
    
    def start(self):
        """Start the manuscript generation workflow in a separate thread."""
        if self.is_running:
            logger.warning(f"Workflow for project {self.project_id} is already running")
            return
        
        self.start_time = datetime.now().isoformat()
        self.is_running = True
        self.stage_manager.update_stage("starting")
        
        # Update status
        status_data = {
            "status": "running",
            "progress": 0,
            "current_stage": self.stage_manager.current_stage,
            "completed_stages": self.stage_manager.completed_stages,
            "start_time": self.start_time,
            "last_update": datetime.now().isoformat()
        }
        self.central_hub.update_project_status(status_data)
        
        # Start the workflow in a new thread
        self.thread = threading.Thread(target=self._run_workflow)
        self.thread.daemon = True
        self.thread.start()
        
        logger.info(f"Started workflow for project {self.project_id}")
    
    def _run_workflow(self):
        """Run the manuscript generation workflow."""
        try:
            # STAGE 1: Ideation
            self.stage_manager.update_stage("ideation")
            self.agent_runner.run_agent(
                "ideation",
                title=self.title,
                genre=self.genre,
                initial_prompt=self.initial_prompt,
                complexity=self.complexity
            )
            
            # STAGE 2: Research
            self.stage_manager.update_stage("research")
            self.agent_runner.run_agent(
                "research",
                complexity=self.complexity
            )
            
            # STAGE 3: Character Development
            self.stage_manager.update_stage("character_development")
            self.agent_runner.run_agent("character")
            
            # STAGE 4: World Building
            self.stage_manager.update_stage("world_building")
            self.agent_runner.run_agent("world_building")
            
            # STAGE 5: Plot Development
            self.stage_manager.update_stage("plot_development")
            self.agent_runner.run_agent("plot", complexity=self.complexity)
            
            # STAGE 6: Chapter Planning
            self.stage_manager.update_stage("chapter_planning")
            chapter_plan = self.agent_runner.run_agent(
                "chapter_planner",
                title=self.title,
                genre=self.genre,
                target_length=self.target_length
            )
            
            # STAGE 7: Chapter Writing
            chapters = self.agent_runner.run_agent(
                "chapter_writer",
                chapter_plan=chapter_plan
            )
            
            # STAGE 8: Final Manuscript Assembly
            self.stage_manager.update_stage("manuscript_assembly")
            manuscript_result = self.agent_runner.run_agent(
                "manuscript",
                chapters=chapters
            )
            
            # Complete workflow
            self.stage_manager.update_stage("completed")
            self.is_complete = True
            self.is_running = False
            
            # Update final status
            status_data = {
                "status": "complete",
                "progress": 100,
                "current_stage": self.stage_manager.current_stage,
                "completed_stages": self.stage_manager.completed_stages,
                "completion_time": datetime.now().isoformat(),
                "word_count": manuscript_result.get("word_count", 0) if manuscript_result else 0,
                "chapter_count": len(chapters) if chapters else 0
            }
            self.central_hub.update_project_status(status_data)
            
            logger.info(f"Completed workflow for project {self.project_id}")
            
        except Exception as e:
            self.error_handler.handle_workflow_error(e, self.stage_manager.current_stage)
            self.is_running = False
    
    def get_status(self) -> Dict[str, Any]:
        """Get the current status of the workflow."""
        return self.central_hub.get_project_status()
    
    def get_progress(self) -> int:
        """Get current progress percentage."""
        return self.stage_manager.get_progress()
    
    def thread_health(self) -> bool:
        """Check if the workflow thread is still alive."""
        if self.thread:
            return self.thread.is_alive()
        return False
    
    def get_final_manuscript(self) -> Optional[Dict[str, Any]]:
        """Get the final manuscript if available."""
        if not self.is_complete:
            return None
        
        # First try with manuscript type
        manuscripts = self.memory.query_memory("type:manuscript", agent_name="manuscript_agent")
        
        # If not found, try with final_manuscript type
        if not manuscripts or len(manuscripts) == 0:
            manuscripts = self.memory.query_memory("type:final_manuscript", agent_name="manuscript_agent")
            
        if manuscripts and len(manuscripts) > 0:
            try:
                manuscript_data = json.loads(manuscripts[0]["text"])
                return manuscript_data
            except:
                return None
        return None
    
    def get_agent(self, agent_name: str) -> Any:
        """Get a specific agent by name."""
        if agent_name in self.agents:
            return self.agents[agent_name]
        return None
    
    def visualize_workflow(self) -> Dict[str, Any]:
        """Get a visualization of the workflow state."""
        return self.stage_manager.visualize_workflow()
    
    def get_stage_data(self, stage: str) -> Optional[Dict[str, Any]]:
        """
        Get the data generated by a specific stage.
        
        Args:
            stage: The stage name to get data for
            
        Returns:
            Dictionary containing the stage data if available, None otherwise
        """
        if stage == "ideation":
            data = self.memory.query_memory("type:selected_idea", agent_name="ideation_agent")
            if data:
                try:
                    return json.loads(data[0]["text"])
                except:
                    return None
        elif stage == "character":
            data = self.memory.query_memory("type:characters", agent_name="character_agent")
            if data:
                try:
                    return json.loads(data[0]["text"])
                except:
                    return None
        elif stage == "world":
            data = self.memory.query_memory("type:world", agent_name="world_building_agent")
            if data:
                try:
                    return json.loads(data[0]["text"])
                except:
                    return None
        elif stage == "research":
            data = self.memory.query_memory("type:research", agent_name="research_agent")
            if data:
                try:
                    return json.loads(data[0]["text"])
                except:
                    return None
        elif stage == "plot":
            data = self.memory.query_memory("type:plot", agent_name="plot_agent")
            if data:
                try:
                    return json.loads(data[0]["text"])
                except:
                    return None
        elif stage == "chapter_plan":
            data = self.memory.query_memory("type:chapter_plan", agent_name="chapter_planner_agent")
            if data:
                try:
                    return json.loads(data[0]["text"])
                except:
                    return None
        return None
    
    def execute(self, **config):
        """Execute the workflow stages sequentially."""
        # Initialize state
        self.is_running = True
        self.is_complete = False
        self.stage_manager.update_stage("start")
        
        # Set config
        self.config = config
        
        try:
            # Start workflow
            logger.info(f"Starting manuscript workflow for project {self.project_id}")
            self.stage_manager.update_stage("ideation")
            self.stage_manager.save_workflow_state(self.memory)
            
            # Stage 1: Ideation - Generate book ideas
            self.agent_runner.run_agent("ideation")
            
            # Stage 2: Research - Generate research topics
            self.stage_manager.update_stage("research")
            self.stage_manager.save_workflow_state(self.memory)
            self.agent_runner.run_agent("research")
            
            # Stage 3: World Building - Generate world setting
            self.stage_manager.update_stage("world_building")
            self.stage_manager.save_workflow_state(self.memory)
            self.agent_runner.run_agent("world_building")
            
            # Stage 4: Character - Generate characters
            self.stage_manager.update_stage("character")
            self.stage_manager.save_workflow_state(self.memory)
            self.agent_runner.run_agent("character")
            
            # Stage 5: Plot Development
            self.stage_manager.update_stage("plot")
            self.stage_manager.save_workflow_state(self.memory)
            self.agent_runner.run_agent("plot")
            
            # Stage 6: Chapter Planning
            self.stage_manager.update_stage("chapter_planning")
            self.stage_manager.save_workflow_state(self.memory)
            self.agent_runner.run_agent("chapter_planner")
            
            # Stage 7: Chapter Writing
            self.stage_manager.update_stage("chapter_writing")
            self.stage_manager.save_workflow_state(self.memory)
            self.agent_runner.run_agent("chapter_writer")
            
            # Stage 8: Manuscript Assembly
            self.stage_manager.update_stage("manuscript")
            self.stage_manager.save_workflow_state(self.memory)
            self.agent_runner.run_agent("manuscript")
            
            # Workflow completed successfully
            self.is_complete = True
            self.end_time = datetime.now()
            self.stage_manager.update_stage("complete")
            self.stage_manager.save_workflow_state(self.memory)
            
            logger.info(f"Workflow completed successfully for project {self.project_id}")
            return self.get_final_manuscript()
            
        except Exception as e:
            self.is_running = False
            self.error_handler.handle_workflow_error(e, self.stage_manager.current_stage)
            self.stage_manager.save_workflow_state(self.memory)
            logger.error(f"Workflow error in stage {self.stage_manager.current_stage}: {str(e)}")
            raise
