import logging
import json
import time
import threading
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable, Union
import os
import traceback

# Custom graph implementation to avoid LangChain dependency issues
class Node:
    def __init__(self, id, label, type):
        self.id = id
        self.label = label
        self.type = type

class Edge:
    def __init__(self, source, target, label):
        self.source = source
        self.target = target
        self.label = label

class Graph:
    def __init__(self):
        self.nodes = {}
        self.edges = []
    
    def add_node(self, node):
        self.nodes[node.id] = node
    
    def add_edge(self, edge):
        self.edges.append(edge)
    
    def add_graph_documents(self, documents):
        for doc in documents:
            for node in doc.nodes:
                self.add_node(node)
            for edge in doc.edges:
                self.add_edge(edge)
    
    def get_node_ids(self):
        return list(self.nodes.keys())
    
    def get_node(self, node_id):
        return self.nodes.get(node_id)
    
    def get_edge_ids(self):
        return [i for i in range(len(self.edges))]
    
    def get_edge(self, edge_id):
        if edge_id < len(self.edges):
            return self.edges[edge_id]
        return None

class GraphDocument:
    def __init__(self, nodes=None, edges=None):
        self.nodes = nodes or []
        self.edges = edges or []

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
        self.last_progress_time = None
        self.agent_start_time = None
        self.current_stage = None
        self.current_agent = None
        self.completed_stages = []
        self.errors = []
        
        # Create memory directory if it doesn't exist
        os.makedirs(f"memory_data/{project_id}", exist_ok=True)
        
        # Initialize memory with OpenAI embeddings
        self.openai_client = get_openai_client()
        embedding_function = lambda text: self.openai_client.get_embeddings(text, model=embedding_model)
        self.memory = DynamicMemory(project_id, embedding_function)
        self.central_hub = CentralHub(project_id, self.memory)
        
        # Create all agents
        self.agents = {
            "ideation": IdeationAgent(
                project_id=project_id,
                memory=self.memory,
                use_openai=use_openai
            ),
            "character": CharacterAgent(
                project_id=project_id,
                memory=self.memory,
                use_openai=use_openai
            ),
            "world_building": WorldBuildingAgent(
                project_id=project_id,
                memory=self.memory,
                use_openai=use_openai
            ),
            "research": ResearchAgent(
                project_id=project_id,
                memory=self.memory,
                use_openai=use_openai
            ),
            "outline": OutlineAgent(
                project_id=project_id,
                memory=self.memory,
                use_openai=use_openai
            ),
            "chapter_planner": ChapterPlannerAgent(
                project_id=project_id,
                memory=self.memory,
                use_openai=use_openai
            ),
            "chapter_writer": ChapterWriterAgent(
                project_id=project_id,
                memory=self.memory,
                use_openai=use_openai
            ),
            "review": ReviewAgent(
                project_id=project_id,
                memory=self.memory,
                use_openai=use_openai
            ),
            "revision": RevisionAgent(
                project_id=project_id,
                memory=self.memory,
                use_openai=use_openai
            ),
            "plot": PlotAgent(
                project_id=project_id,
                memory=self.memory,
                use_openai=use_openai
            ),
            "editorial": EditorialAgent(
                project_id=project_id,
                memory=self.memory,
                use_openai=use_openai
            ),
            "expander": LongformExpander(
                model_name="gpt-4o"
            ),
            "manuscript": ManuscriptAgent(
                project_id=project_id,
                memory=self.memory,
                use_openai=use_openai
            ),
            "refiner": ManuscriptRefiner(
                project_id=project_id,
                model_name="gpt-4o"
            )
        }
        
        # Initialize workflow data
        self._initialize_data()
        self.config = {}
    
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
        self.current_stage = "starting"
        
        # Update status
        status_data = {
            "status": "running",
            "progress": 0,
            "current_stage": self.current_stage,
            "completed_stages": self.completed_stages,
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
            self._update_stage("ideation")
            ideation_result = self.agents["ideation"].generate_ideas(
                title=self.title,
                genre=self.genre,
                initial_prompt=self.initial_prompt
            )
            self._complete_stage("ideation")
            
            # STAGE 2: Research
            self._update_stage("research")
            ideation_data = self.central_hub.aggregate_ideation_data()
            research_result = self.agents["research"].generate_research(
                book_idea=ideation_data.get("selected_idea", {}),
                num_topics=5,
                complexity=self.complexity
            )
            self._complete_stage("research")
            
            # STAGE 3: Character Development
            self._update_stage("character_development")
            ideation_data = self.central_hub.aggregate_ideation_data()
            character_result = self.agents["character"].generate_characters(
                idea=ideation_data.get("selected_idea", {}),
                world_context={},
                num_characters=5,
                user_prompt=None,
                system_prompt=None
            )
            self._complete_stage("character_development")
            
            # STAGE 4: World Building
            self._update_stage("world_building")
            world_building_result = self.agents["world_building"].generate_world(
                book_idea=ideation_data.get("selected_idea", {}),
                complexity=self.complexity
            )
            self._complete_stage("world_building")
            
            # STAGE 5: Plot Development
            self._update_stage("plot_development")
            character_data = character_result
            world_data = world_building_result
            plot_result = self.agents["plot"].generate_plot(
                book_idea=ideation_data.get("selected_idea", {}),
                characters=character_data,
                world_data=world_data,
                complexity=self.complexity
            )
            self._complete_stage("plot_development")
            
            # Integrate all data so far
            integrated_data = self.central_hub.integrate_all_data()
            
            # STAGE 6: Chapter Planning
            self._update_stage("chapter_planning")
            
            # Assemble manuscript outline for chapter planning
            manuscript_outline = {
                "title": self.title or integrated_data.get("selected_idea", {}).get("title", "Untitled"),
                "genre": self.genre,
                "target_length": self.target_length,
                "plot": plot_result,
                "characters": character_data,
                "world": world_data,
                "idea": integrated_data.get("selected_idea", {})
            }
            
            chapter_plan = self.agents["chapter_planner"].plan_chapters(manuscript_outline)
            self._complete_stage("chapter_planning")
            
            # STAGE 7: Chapter Writing
            total_chapters = len(chapter_plan)
            previous_chapter_content = None
            chapters = []
            
            # If chapter planning gave no chapters, create at least one fallback chapter
            if total_chapters == 0:
                logger.warning("No chapters in chapter plan, creating fallback chapter")
                fallback_chapter = {
                    "number": 1,
                    "title": "Chapter 1",
                    "summary": "Introduction to the story and characters"
                }
                chapter_plan = [fallback_chapter]
                total_chapters = 1
            
            for i, chapter in enumerate(chapter_plan):
                chapter_number = chapter.get("number", i + 1)
                self._update_stage(f"writing_chapter_{chapter_number}")
                
                try:
                    logger.info(f"Writing chapter {chapter_number} of {total_chapters}")
                    chapter_data = self.agents["chapter_writer"].write_chapter(
                        chapter_plan=chapter,
                        previous_chapter_content=previous_chapter_content
                    )
                    chapters.append(chapter_data)
                    
                    # Update for next chapter
                    previous_chapter_content = chapter_data.get("content", "")
                    
                    self._complete_stage(f"writing_chapter_{chapter_number}")
                    
                    # Update progress based on chapters completed
                    progress = int(80 + ((i + 1) / total_chapters) * 20)  # 80% base progress + up to 20% for chapters
                    self._update_progress(progress)
                    
                except Exception as e:
                    logger.error(f"Error writing chapter {chapter_number}: {str(e)}")
                    self.errors.append({
                        "stage": f"writing_chapter_{chapter_number}",
                        "error": str(e),
                        "traceback": traceback.format_exc()
                    })
                    # Continue with next chapter despite the error
            
            # STAGE 8: Final Manuscript Assembly
            self._update_stage("manuscript_assembly")
            
            # If we have no chapters at all by this point, create a single fallback chapter
            if len(chapters) == 0:
                logger.warning("No chapters generated, creating a fallback chapter for manuscript assembly")
                fallback_chapter_data = self.agents["chapter_writer"].write_chapter(
                    chapter_plan={
                        "number": 1,
                        "title": "Chapter 1",
                        "summary": "Introduction to the story and characters"
                    },
                    previous_chapter_content=None
                )
                chapters.append(fallback_chapter_data)
            
            manuscript_result = self.agents["manuscript"].assemble_manuscript(chapters=chapters)
            self._complete_stage("manuscript_assembly")
            
            # Complete workflow
            self._update_stage("completed")
            self.is_complete = True
            self.is_running = False
            
            # Update final status
            status_data = {
                "status": "complete",
                "progress": 100,
                "current_stage": self.current_stage,
                "completed_stages": self.completed_stages,
                "completion_time": datetime.now().isoformat(),
                "word_count": manuscript_result.get("word_count", 0),
                "chapter_count": len(chapters)
            }
            self.central_hub.update_project_status(status_data)
            
            logger.info(f"Completed workflow for project {self.project_id}")
            
        except Exception as e:
            logger.error(f"Error in workflow: {str(e)}", exc_info=True)
            self.errors.append({
                "stage": self.current_stage,
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            
            # Update status to error
            status_data = {
                "status": "error",
                "progress": self.get_progress(),
                "current_stage": self.current_stage,
                "completed_stages": self.completed_stages,
                "error": str(e),
                "error_time": datetime.now().isoformat()
            }
            self.central_hub.update_project_status(status_data)
            
            self.is_running = False
    
    def _update_stage(self, stage: str):
        """Update the current stage."""
        self.current_stage = stage
        self.last_progress_time = datetime.now().isoformat()
        
        # Calculate progress based on stage
        progress_map = {
            "ideation": 5,
            "research": 15,
            "character_development": 25,
            "world_building": 40,
            "plot_development": 55,
            "chapter_planning": 70,
            # Chapter writing stages are calculated dynamically
            "manuscript_assembly": 95,
            "completed": 100
        }
        
        # For chapter writing stages, interpolate between 70 and 95
        if stage.startswith("writing_chapter_"):
            try:
                chapter_num = int(stage.split("_")[-1])
                total_chapters = 0
                # Try to get total chapters from chapter plan
                try:
                    chapter_docs = self.memory.query_memory("type:chapter_plan", agent_name="chapter_planner_agent")
                    if chapter_docs:
                        chapter_plan = json.loads(chapter_docs[0].get("text", "{}"))
                        total_chapters = len(chapter_plan.get("chapters", []))
                except:
                    pass
                
                # Default to 10 if we can't determine
                if total_chapters == 0:
                    total_chapters = 10
                
                # Calculate progress (70% base + up to 25% for chapters)
                chapter_progress = int(70 + ((chapter_num - 1) / total_chapters) * 25)
                progress = min(95, chapter_progress)
            except:
                progress = 70
        else:
            progress = progress_map.get(stage, self.get_progress())
        
        self._update_progress(progress)
        
        logger.info(f"Project {self.project_id} moved to stage: {stage} (progress: {progress}%)")
    
    def _complete_stage(self, stage: str):
        """Mark a stage as completed."""
        if stage not in self.completed_stages:
            self.completed_stages.append(stage)
        
        # Update status
        status_data = {
            "status": "running",
            "progress": self.get_progress(),
            "current_stage": self.current_stage,
            "completed_stages": self.completed_stages,
            "last_update": datetime.now().isoformat()
        }
        self.central_hub.update_project_status(status_data)
        
        logger.info(f"Project {self.project_id} completed stage: {stage}")
    
    def _update_progress(self, progress: int):
        """Update the progress percentage."""
        # Update status
        status_data = {
            "status": "running",
            "progress": progress,
            "current_stage": self.current_stage,
            "completed_stages": self.completed_stages,
            "last_update": datetime.now().isoformat()
        }
        self.central_hub.update_project_status(status_data)
    
    def get_progress(self) -> int:
        """Get current progress percentage."""
        status = self.central_hub.get_project_status()
        return status.get("progress", 0)
    
    def thread_health(self) -> bool:
        """Check if the workflow thread is still alive."""
        if self.thread:
            return self.thread.is_alive()
        return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get the current status of the workflow."""
        return self.central_hub.get_project_status()

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
        # Create a simplified workflow visualization
        nodes = [
            {"id": "ideation", "label": "Ideation", "status": "completed" if "ideation" in self.completed_stages else "pending"},
            {"id": "research", "label": "Research", "status": "completed" if "research" in self.completed_stages else "pending"},
            {"id": "character_development", "label": "Character Development", "status": "completed" if "character_development" in self.completed_stages else "pending"},
            {"id": "world_building", "label": "World Building", "status": "completed" if "world_building" in self.completed_stages else "pending"},
            {"id": "plot_development", "label": "Plot Development", "status": "completed" if "plot_development" in self.completed_stages else "pending"},
            {"id": "chapter_planning", "label": "Chapter Planning", "status": "completed" if "chapter_planning" in self.completed_stages else "pending"},
            {"id": "chapter_writing", "label": "Chapter Writing", "status": "completed" if any(s.startswith("writing_chapter_") for s in self.completed_stages) else "pending"},
            {"id": "manuscript_assembly", "label": "Manuscript Assembly", "status": "completed" if "manuscript_assembly" in self.completed_stages else "pending"}
        ]
        
        # Mark current stage
        for node in nodes:
            if node["id"] == self.current_stage:
                node["status"] = "current"
        
        # Define edges
        edges = [
            {"source": "ideation", "target": "research", "label": "Follows"},
            {"source": "research", "target": "character_development", "label": "Follows"},
            {"source": "character_development", "target": "world_building", "label": "Follows"},
            {"source": "world_building", "target": "plot_development", "label": "Follows"},
            {"source": "plot_development", "target": "chapter_planning", "label": "Follows"},
            {"source": "chapter_planning", "target": "chapter_writing", "label": "Follows"},
            {"source": "chapter_writing", "target": "manuscript_assembly", "label": "Follows"}
        ]
        
        return {
            "nodes": nodes,
            "edges": edges,
            "progress": self.get_progress(),
            "current_stage": self.current_stage,
            "completed_stages": self.completed_stages
        }

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

    def _save_workflow_state(self):
        """Save the current workflow state to memory."""
        state = {
            "current_stage": self.current_stage,
            "completed_stages": self.completed_stages,
            "is_running": self.is_running,
            "is_complete": self.is_complete,
            "errors": self.errors,
            "timestamp": datetime.now().isoformat()
        }
        self.memory.add_document(
            json.dumps(state),
            "workflow",
            metadata={"type": "workflow_state"}
        )
        
    def _run_agent(self, agent_key: str):
        """
        Run an agent with proper error handling and recovery.
        
        Args:
            agent_key: Key of the agent in the agents dictionary
        """
        try:
            # Record the start time for this agent
            self.agent_start_time = datetime.now().isoformat()
            
            # Update current agent
            self.current_agent = agent_key
            logger.info(f"Running agent {agent_key} for project {self.project_id}")
            
            # Call appropriate method based on agent key
            if agent_key == "ideation":
                self.agents[agent_key].generate_ideas(
                    title=self.title,
                    genre=self.genre,
                    initial_prompt=self.initial_prompt,
                    complexity=self.complexity
                )
                # Mark stage as completed
                self._complete_stage("ideation")
            
            elif agent_key == "character":
                # Get integrated data from central hub
                integrated_data = self.central_hub.aggregate_ideation_data()
                self.agents[agent_key].create_characters(
                    title=self.title,
                    genre=self.genre,
                    idea=integrated_data
                )
                # Mark stage as completed
                self._complete_stage("character")
            
            elif agent_key == "world_building":
                # Get ideation and character data
                idea_data = self.central_hub.get_aggregated_data("ideation")
                character_data = self.central_hub.get_aggregated_data("character")
                
                self.agents[agent_key].create_world(
                    idea_data=idea_data,
                    character_data=character_data,
                    genre=self.genre
                )
                # Mark stage as completed
                self._complete_stage("world_building")
                
            elif agent_key == "research":
                # Get existing data
                integrated_data = self.central_hub.integrate_all_data()
                
                self.agents[agent_key].conduct_research(
                    integrated_data=integrated_data,
                    genre=self.genre
                )
                # Mark stage as completed
                self._complete_stage("research")
                
            elif agent_key == "outline":
                # Get all data so far
                integrated_data = self.central_hub.integrate_all_data()
                
                self.agents[agent_key].create_outline(
                    integrated_data=integrated_data,
                    genre=self.genre,
                    target_length=self.target_length,
                    complexity=self.complexity
                )
                # Mark stage as completed
                self._complete_stage("outline")
            
            # Additional stages run in similar patterns
            # More agent execution branches...
                
            else:
                logger.warning(f"Unknown agent key: {agent_key}")
                
        except Exception as e:
            error_details = {
                "agent": agent_key,
                "error": str(e),
                "traceback": traceback.format_exc(),
                "timestamp": datetime.now().isoformat()
            }
            
            # Log detailed error
            logger.error(f"Agent {agent_key} failed: {str(e)}", exc_info=True)
            
            # Store error in memory for user visibility
            self.memory.add_document(
                json.dumps(error_details),
                "workflow",
                metadata={"type": "error", "agent": agent_key, "stage": self.current_stage}
            )
            
            # Update workflow status
            self.errors.append(error_details)
            self._update_stage(f"error_{agent_key}")
            
            # Notify through central hub
            self.central_hub.update_project_status({
                "status": "error",
                "current_stage": self.current_stage,
                "error": error_details
            })
            
            # Attempt recovery based on agent type
            try:
                self._attempt_recovery(agent_key, error_details)
            except Exception as recovery_error:
                logger.error(f"Recovery attempt failed for {agent_key}: {str(recovery_error)}")
    
    def _attempt_recovery(self, agent_key: str, error_details: Dict[str, Any]) -> None:
        """
        Attempt to recover from an agent failure.
        
        Args:
            agent_key: The key of the failed agent
            error_details: Details about the error
        """
        logger.info(f"Attempting to recover from {agent_key} failure")
        
        # Different recovery strategies based on agent
        if agent_key == "ideation":
            # For ideation, we can try to generate at least one fallback idea
            try:
                fallback_idea = {
                    "ideas": [{
                        "id": "fallback_idea",
                        "title": self.title or "Untitled Project",
                        "premise": "A compelling story that overcomes challenges and transforms lives.",
                        "themes": ["resilience", "transformation"],
                        "genre": self.genre or "general",
                        "target_audience": "general",
                        "score": 8.0
                    }]
                }
                
                # Store fallback idea in memory
                self.memory.add_document(
                    json.dumps(fallback_idea),
                    "ideation_agent",
                    metadata={
                        "type": "ideation_results", 
                        "recovery": True,
                        "original_error": str(error_details["error"])
                    }
                )
                
                logger.info("Successfully created fallback idea during recovery")
                self._complete_stage("ideation")
                
            except Exception as e:
                logger.error(f"Failed to create fallback idea: {e}")
                raise
                
        elif agent_key in ["character", "world_building", "research"]:
            # For these agents, we can try to create minimal viable output
            try:
                # Create minimal output based on agent type
                minimal_output = self._create_minimal_output(agent_key)
                
                # Store in memory with recovery flag
                self.memory.add_document(
                    json.dumps(minimal_output),
                    f"{agent_key}_agent",
                    metadata={
                        "type": agent_key, 
                        "recovery": True,
                        "original_error": str(error_details["error"])
                    }
                )
                
                logger.info(f"Successfully created minimal {agent_key} output during recovery")
                self._complete_stage(agent_key)
                
            except Exception as e:
                logger.error(f"Failed to create minimal {agent_key} output: {e}")
                raise
        
        # For other agents, we currently don't have specific recovery strategies
        # and will rely on manual intervention
    
    def _create_minimal_output(self, agent_key: str) -> Dict[str, Any]:
        """
        Create minimal viable output for an agent to allow the pipeline to continue.
        
        Args:
            agent_key: The agent key
            
        Returns:
            Dictionary with minimal viable output
        """
        if agent_key == "character":
            return {
                "characters": [
                    {
                        "id": "protagonist",
                        "name": "Main Character",
                        "role": "protagonist",
                        "description": "A compelling protagonist with a clear motivation.",
                        "background": "Background relevant to the story premise.",
                        "goals": ["To overcome the main conflict"],
                        "traits": ["determined", "resourceful"]
                    },
                    {
                        "id": "antagonist",
                        "name": "Opposing Force",
                        "role": "antagonist",
                        "description": "A challenging antagonist with opposing goals.",
                        "background": "Background that puts them in conflict with the protagonist.",
                        "goals": ["To prevent the protagonist from succeeding"],
                        "traits": ["persistent", "clever"]
                    }
                ],
                "relationships": [
                    {
                        "character1_id": "protagonist",
                        "character2_id": "antagonist",
                        "relationship_type": "opposition",
                        "description": "Clear conflict between main character and antagonistic force."
                    }
                ]
            }
        elif agent_key == "world_building":
            return {
                "setting": {
                    "name": "Story World",
                    "description": "A richly detailed world where the story unfolds.",
                    "time_period": "Contemporary or appropriate for the genre",
                    "locations": [
                        {
                            "name": "Primary Location",
                            "description": "The main setting where much of the action takes place."
                        },
                        {
                            "name": "Secondary Location",
                            "description": "An additional important location in the story."
                        }
                    ]
                },
                "rules": [
                    "The world operates according to consistent internal logic.",
                    "The setting creates natural conflicts and opportunities for the characters."
                ]
            }
        elif agent_key == "research":
            return {
                "research_topics": [
                    {
                        "topic": "Main Subject",
                        "summary": "Key information about the main subject of the story.",
                        "relevance": "Forms the factual foundation of the narrative.",
                        "sources": ["Generated as part of error recovery"]
                    }
                ],
                "insights": [
                    "The story will benefit from authentic details about the main subject.",
                    "Character motivations should align with realistic expectations."
                ]
            }
        else:
            # Generic minimal output for other agents
            return {
                "recovery": True,
                "minimal_data": {
                    "description": f"Minimal data for {agent_key} to allow workflow to continue",
                    "timestamp": datetime.now().isoformat()
                }
            }

    def execute(self, **config):
        """Execute the workflow stages sequentially."""
        # Initialize state
        self.is_running = True
        self.is_complete = False
        self.current_stage = "start"
        
        # Set config
        self.config = config
        
        try:
            # Start workflow
            logger.info(f"Starting manuscript workflow for project {self.project_id}")
            self.current_stage = "ideation"
            self._save_workflow_state()
            
            # Stage 1: Ideation - Generate book ideas
            self._run_agent("ideation")
            
            # Stage 2: Research - Generate research topics
            self.current_stage = "research"
            self._save_workflow_state()
            self._run_agent("research")
            
            # Stage 3: World Building - Generate world setting
            self.current_stage = "world_building"
            self._save_workflow_state()
            self._run_agent("world")
            
            # Stage 4: Character - Generate characters
            self.current_stage = "character"
            self._save_workflow_state()
            self._run_agent("character")
            
            # Stage 5: Plot Development
            self.current_stage = "plot"
            self._save_workflow_state()
            self._run_agent("plot")
            
            # Stage 6: Chapter Planning
            self.current_stage = "chapter_planning"
            self._save_workflow_state()
            self._run_agent("chapter_planning")
            
            # Stage 7: Chapter Writing
            self.current_stage = "chapter_writing"
            self._save_workflow_state()
            self._run_agent("writing")
            
            # Stage 8: Manuscript Assembly
            self.current_stage = "manuscript"
            self._save_workflow_state()
            self._run_agent("manuscript")
            
            # Workflow completed successfully
            self.is_complete = True
            self.end_time = datetime.now()
            self.current_stage = "complete"
            self._save_workflow_state()
            
            logger.info(f"Workflow completed successfully for project {self.project_id}")
            return self.get_final_manuscript()
            
        except Exception as e:
            self.is_running = False
            self.error = str(e)
            self._save_workflow_state()
            logger.error(f"Workflow error in stage {self.current_stage}: {str(e)}")
            raise
