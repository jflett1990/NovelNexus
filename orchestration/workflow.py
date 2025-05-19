import logging
import json
import time
import threading
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable, Union

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

# Import integration hub
from hubs.central_hub import CentralHub

# Import memory system
from memory.dynamic_memory import DynamicMemory

# Import embedding functionality
from models.ollama_client import get_ollama_client
from models.openai_client import get_openai_client

logger = logging.getLogger(__name__)

class ManuscriptWorkflow:
    """
    Main workflow orchestration for the manuscript generation process.
    
    This class implements a non-linear, agent-based workflow for generating
    a complete manuscript, managing the interactions between specialized agents
    and providing a central orchestration point.
    """
    
    def __init__(self, project_id: str, config: Dict[str, Any]):
        """
        Initialize the manuscript workflow.
        
        Args:
            project_id: Unique identifier for the project
            config: Configuration dictionary with workflow parameters
        """
        self.project_id = project_id
        self.config = config
        
        # Extract key configuration
        self.title = config.get("title", "Untitled Book")
        self.genre = config.get("genre", "")
        self.target_length = config.get("target_length", "novel")
        self.complexity = config.get("complexity", "medium")
        self.use_openai = config.get("use_openai", True)
        self.use_ollama = config.get("use_ollama", True)
        self.initial_prompt = config.get("initial_prompt", "")
        
        # Determine target word count based on target_length
        self.target_word_count = self._get_target_word_count(self.target_length)
        
        # Set up dynamic memory with appropriate embedding function
        self.memory = self._initialize_memory()
        
        # Initialize the central hub
        self.central_hub = CentralHub(project_id, self.memory)
        
        # Initialize agents
        self.agents = self._initialize_agents()
        
        # Initialize workflow state
        self.is_running = False
        self.is_complete = False
        self.current_stage = None
        self.status = "initialized"
        self.progress = 0
        self.start_time = None
        self.end_time = None
        self.completed_stages = []
        self.errors = []
        
        # Initialize workflow thread
        self.workflow_thread = None
        
        # Initialize workflow graph for visualization
        self.graph = self._initialize_workflow_graph()
    
    def _initialize_memory(self) -> DynamicMemory:
        """Initialize the dynamic memory system with the appropriate embedding function."""
        # Set up the embedding function based on configuration
        if self.use_openai:
            openai_client = get_openai_client()
            if openai_client.is_available():
                embedding_function = lambda text: openai_client.get_embeddings(text, model="text-embedding-3-small")
                vector_dimension = 1536  # OpenAI embedding dimension
                logger.info(f"Using OpenAI embeddings for project {self.project_id}")
                return DynamicMemory(self.project_id, embedding_function, vector_dimension=vector_dimension)
        
        if self.use_ollama:
            ollama_client = get_ollama_client()
            embedding_function = lambda text: ollama_client.get_embeddings(text, model="snowflake-arctic-embed:335m")
            vector_dimension = 384  # snowflake-arctic-embed dimension
            logger.info(f"Using Ollama embeddings for project {self.project_id}")
            return DynamicMemory(self.project_id, embedding_function, vector_dimension=vector_dimension)
        
        # Fallback to Ollama if nothing else is available
        ollama_client = get_ollama_client()
        embedding_function = lambda text: ollama_client.get_embeddings(text, model="snowflake-arctic-embed:335m")
        vector_dimension = 384
        logger.info(f"Falling back to Ollama embeddings for project {self.project_id}")
        return DynamicMemory(self.project_id, embedding_function, vector_dimension=vector_dimension)
    
    def _initialize_agents(self) -> Dict[str, Any]:
        """Initialize all agents needed for the workflow."""
        return {
            "ideation": IdeationAgent(self.project_id, self.memory, self.use_openai, self.use_ollama),
            "character": CharacterAgent(self.project_id, self.memory, self.use_openai, self.use_ollama),
            "world_building": WorldBuildingAgent(self.project_id, self.memory, self.use_openai, self.use_ollama),
            "research": ResearchAgent(self.project_id, self.memory, self.use_openai, self.use_ollama),
            "outline": OutlineAgent(self.project_id, self.memory, self.use_openai, self.use_ollama),
            "writing": WritingAgent(self.project_id, self.memory, self.use_openai, self.use_ollama),
            "review": ReviewAgent(self.project_id, self.memory, self.use_openai, self.use_ollama),
            "revision": RevisionAgent(self.project_id, self.memory, self.use_openai, self.use_ollama),
            "editorial": EditorialAgent(self.project_id, self.memory, self.use_openai, self.use_ollama)
        }
    
    def _initialize_workflow_graph(self) -> Graph:
        """Initialize the workflow graph for visualization."""
        graph = Graph()
        
        # Add nodes for each stage
        nodes = [
            Node(id="ideation", label="Ideation", type="stage"),
            Node(id="character", label="Character Development", type="stage"),
            Node(id="world_building", label="World Building", type="stage"),
            Node(id="research", label="Research", type="stage"),
            Node(id="central_integration", label="Central Integration", type="hub"),
            Node(id="outline", label="Outlining", type="stage"),
            Node(id="writing", label="Writing", type="stage"),
            Node(id="review", label="Iterative Review", type="stage"),
            Node(id="revision", label="Revision", type="stage"),
            Node(id="editorial", label="Editorial", type="stage"),
            Node(id="final_manuscript", label="Final Manuscript", type="output")
        ]
        
        # Add edges for workflow connections
        edges = [
            Edge(source="ideation", target="character", label="ideas"),
            Edge(source="ideation", target="world_building", label="ideas"),
            Edge(source="ideation", target="research", label="ideas"),
            Edge(source="character", target="central_integration", label="characters"),
            Edge(source="world_building", target="central_integration", label="world"),
            Edge(source="research", target="central_integration", label="research"),
            Edge(source="central_integration", target="outline", label="integrated_data"),
            Edge(source="outline", target="writing", label="outline"),
            Edge(source="writing", target="review", label="chapters"),
            Edge(source="review", target="revision", label="feedback"),
            Edge(source="revision", target="writing", label="revision_requests"),
            Edge(source="revision", target="editorial", label="revised_chapters"),
            Edge(source="editorial", target="final_manuscript", label="edited_manuscript")
        ]
        
        # Create graph document and add to graph
        graph_document = GraphDocument(nodes=nodes, edges=edges)
        graph.add_graph_documents([graph_document])
        
        return graph
    
    def _get_target_word_count(self, target_length: str) -> int:
        """Determine target word count based on selected format."""
        word_count_map = {
            "short_story": 7500,
            "novella": 30000,
            "novel": 80000,
            "epic_novel": 120000
        }
        return word_count_map.get(target_length, 80000)
    
    def start(self) -> None:
        """Start the manuscript generation workflow in a separate thread."""
        if self.is_running:
            logger.warning(f"Workflow for project {self.project_id} is already running")
            return
        
        self.is_running = True
        self.start_time = datetime.now()
        self.status = "running"
        self.progress = 0
        
        # Update project status
        self._update_status()
        
        # Start the workflow in a separate thread
        self.workflow_thread = threading.Thread(target=self._run_workflow)
        self.workflow_thread.daemon = True
        self.workflow_thread.start()
        
        logger.info(f"Started workflow for project {self.project_id}")
    
    def _run_workflow(self) -> None:
        """Run the complete manuscript generation workflow."""
        try:
            # Phase 1: Parallel ideation, character, world-building, and research
            self._execute_ideation_phase()
            self._execute_development_phase()
            
            # Phase 2: Integration and outlining
            self._execute_outline_phase()
            
            # Phase 3: Writing and iterative review
            self._execute_writing_phase()
            
            # Phase 4: Final revisions and editorial
            self._execute_editorial_phase()
            
            # Complete the workflow
            self.is_complete = True
            self.status = "completed"
            self.progress = 100
            self.end_time = datetime.now()
            
        except Exception as e:
            logger.error(f"Workflow error for project {self.project_id}: {str(e)}")
            self.status = "error"
            self.errors.append(str(e))
        
        finally:
            self.is_running = False
            self._update_status()
    
    def _execute_ideation_phase(self) -> None:
        """Execute the ideation phase of the workflow."""
        self.current_stage = "ideation"
        self._update_status()
        
        try:
            # Generate initial ideas
            ideation_agent = self.agents["ideation"]
            ideas = ideation_agent.generate_ideas(
                title=self.title,
                genre=self.genre,
                initial_prompt=self.initial_prompt,
                complexity=self.complexity
            )
            
            # If title was not provided, use the title from the best idea
            if not self.title and ideas and "ideas" in ideas and ideas["ideas"]:
                best_idea = max(ideas["ideas"], key=lambda x: x.get("score", 0))
                self.title = best_idea.get("title", "Untitled Book")
                
                # Update configuration
                self.config["title"] = self.title
            
            # Aggregate ideation data in the central hub
            self.central_hub.aggregate_ideation_data()
            
            # Mark stage as completed
            self.completed_stages.append("ideation")
            self.progress = 10
            
        except Exception as e:
            logger.error(f"Ideation phase error: {str(e)}")
            self.errors.append(f"Ideation phase: {str(e)}")
            raise
        
        finally:
            self._update_status()
    
    def _execute_development_phase(self) -> None:
        """Execute the parallel development phase (character, world, research)."""
        # Get the selected book idea from the central hub
        try:
            ideation_data = self.central_hub.get_aggregated_data("ideation")
            selected_idea = ideation_data.get("selected_idea", {})
            
            # Execute character development
            self._execute_character_development(selected_idea)
            
            # Execute world building
            self._execute_world_building(selected_idea)
            
            # Execute research
            self._execute_research(selected_idea)
            
            # Integrate all data in the central hub
            self.central_hub.integrate_all_data()
            
            self.progress = 30
            self._update_status()
            
        except Exception as e:
            logger.error(f"Development phase error: {str(e)}")
            self.errors.append(f"Development phase: {str(e)}")
            raise
    
    def _execute_character_development(self, book_idea: Dict[str, Any]) -> None:
        """Execute the character development stage."""
        self.current_stage = "character_development"
        self._update_status()
        
        try:
            # Generate characters
            character_agent = self.agents["character"]
            characters = character_agent.generate_characters(
                book_idea=book_idea,
                complexity=self.complexity
            )
            
            # If enough characters were generated, create relationships
            if "characters" in characters and len(characters["characters"]) >= 2:
                character_ids = [char.get("id") for char in characters["characters"] if "id" in char]
                character_agent.generate_character_relationships(character_ids)
            
            # Aggregate character data in the central hub
            self.central_hub.aggregate_character_data()
            
            # Mark stage as completed
            self.completed_stages.append("character_development")
            
        except Exception as e:
            logger.error(f"Character development error: {str(e)}")
            self.errors.append(f"Character development: {str(e)}")
            raise
        
        finally:
            self._update_status()
    
    def _execute_world_building(self, book_idea: Dict[str, Any]) -> None:
        """Execute the world building stage."""
        self.current_stage = "world_building"
        self._update_status()
        
        try:
            # Generate world
            world_agent = self.agents["world_building"]
            world = world_agent.generate_world(
                book_idea=book_idea,
                complexity=self.complexity
            )
            
            # Develop a few key locations if they exist
            if "locations" in world and isinstance(world["locations"], list) and len(world["locations"]) > 0:
                # Select up to 2 locations to develop further
                locations_to_develop = world["locations"][:min(2, len(world["locations"]))]
                
                for location in locations_to_develop:
                    location_name = location.get("name", "")
                    if location_name:
                        world_agent.develop_location(
                            location_name=location_name,
                            development_prompt=f"Develop the location '{location_name}' in more detail, focusing on its significance to the story."
                        )
            
            # Aggregate world data in the central hub
            self.central_hub.aggregate_world_data()
            
            # Mark stage as completed
            self.completed_stages.append("world_building")
            
        except Exception as e:
            logger.error(f"World building error: {str(e)}")
            self.errors.append(f"World building: {str(e)}")
            raise
        
        finally:
            self._update_status()
    
    def _execute_research(self, book_idea: Dict[str, Any]) -> None:
        """Execute the research stage."""
        self.current_stage = "research"
        self._update_status()
        
        try:
            # Get world data if available
            world_data = None
            try:
                world_data = self.central_hub.get_aggregated_data("world")
            except ValueError:
                # World data might not be available yet, which is okay
                pass
            
            # Generate research topics
            research_agent = self.agents["research"]
            research = research_agent.generate_research(
                book_idea=book_idea,
                world_data=world_data,
                complexity=self.complexity
            )
            
            # Research a few high-priority topics in more detail
            if "topics" in research and isinstance(research["topics"], list) and len(research["topics"]) > 0:
                # Sort topics by priority and select top 2
                topics_to_research = sorted(
                    research["topics"], 
                    key=lambda x: x.get("priority", 5), 
                    reverse=True
                )[:min(2, len(research["topics"]))]
                
                for topic in topics_to_research:
                    topic_id = topic.get("id", "")
                    if topic_id:
                        research_agent.research_topic(topic_id=topic_id)
            
            # Synthesize research
            research_agent.synthesize_research()
            
            # Aggregate research data in the central hub
            self.central_hub.aggregate_research_data()
            
            # Mark stage as completed
            self.completed_stages.append("research")
            
        except Exception as e:
            logger.error(f"Research error: {str(e)}")
            self.errors.append(f"Research: {str(e)}")
            raise
        
        finally:
            self._update_status()
    
    def _execute_outline_phase(self) -> None:
        """Execute the outline phase of the workflow."""
        self.current_stage = "outlining"
        self._update_status()
        
        try:
            # Get integrated data from the central hub
            integrated_data = self.central_hub.get_integrated_data()
            
            # Generate outline
            outline_agent = self.agents["outline"]
            outline = outline_agent.generate_outline(
                book_idea=integrated_data["book_idea"],
                characters=integrated_data["characters"],
                world_data=integrated_data["world"],
                research_data=integrated_data["research"],
                complexity=self.complexity,
                target_word_count=self.target_word_count
            )
            
            # Enhance a few key chapters with more details
            if "chapters" in outline and isinstance(outline["chapters"], list) and len(outline["chapters"]) > 0:
                # Select a few chapters to enhance (first, middle, and climax chapters)
                chapters_to_enhance = []
                if len(outline["chapters"]) > 0:
                    chapters_to_enhance.append(outline["chapters"][0])  # First chapter
                
                if len(outline["chapters"]) > 2:
                    middle_idx = len(outline["chapters"]) // 2
                    chapters_to_enhance.append(outline["chapters"][middle_idx])  # Middle chapter
                
                if len(outline["chapters"]) > 3:
                    climax_idx = max(0, len(outline["chapters"]) - 3)  # Third from last (likely climax)
                    chapters_to_enhance.append(outline["chapters"][climax_idx])
                
                for chapter in chapters_to_enhance:
                    chapter_id = chapter.get("id", "")
                    if chapter_id:
                        outline_agent.add_chapter_details(
                            chapter_id=chapter_id,
                            detail_type="scenes",
                            detail_instructions="Add detailed scene breakdowns including setting, characters, conflict, and resolution."
                        )
            
            # Mark stage as completed
            self.completed_stages.append("outlining")
            self.progress = 40
            
        except Exception as e:
            logger.error(f"Outline phase error: {str(e)}")
            self.errors.append(f"Outline phase: {str(e)}")
            raise
        
        finally:
            self._update_status()
    
    def _execute_writing_phase(self) -> None:
        """Execute the writing and review phase of the workflow."""
        try:
            # Get the outline
            outline_agent = self.agents["outline"]
            outline = outline_agent.get_complete_outline()
            
            # Get integrated data for reference
            integrated_data = self.central_hub.get_integrated_data()
            
            # Generate style guide
            writing_agent = self.agents["writing"]
            style_guide = writing_agent.generate_style_guide(integrated_data["book_idea"])
            
            # Determine how many chapters to write
            if "chapters" in outline and isinstance(outline["chapters"], list):
                chapters_to_write = outline["chapters"]
                
                # Limit number of chapters for demo purposes if needed
                if len(chapters_to_write) > 3 and self.target_length == "short_story":
                    chapters_to_write = chapters_to_write[:3]
                
                # Write the chapters one by one with review and revision
                for i, chapter_outline in enumerate(chapters_to_write):
                    if i == 0:
                        # First chapter - full process
                        self._write_review_revise_chapter(
                            chapter_outline=chapter_outline,
                            outline=outline,
                            integrated_data=integrated_data,
                            style_guide=style_guide,
                            previously_written_chapters=None
                        )
                    else:
                        # Subsequent chapters - get previously written chapters
                        previously_written = writing_agent.get_all_written_chapters()
                        self._write_review_revise_chapter(
                            chapter_outline=chapter_outline,
                            outline=outline,
                            integrated_data=integrated_data,
                            style_guide=style_guide,
                            previously_written_chapters=previously_written
                        )
                    
                    # Update progress based on how many chapters we've written
                    chapters_progress = min(90, 40 + (50 * (i + 1) // max(1, len(chapters_to_write))))
                    self.progress = chapters_progress
                    self._update_status()
            
            # Check for consistency across chapters
            written_chapters = writing_agent.get_all_written_chapters()
            if len(written_chapters) > 1:
                review_agent = self.agents["review"]
                consistency_analysis = review_agent.analyze_manuscript_consistency(written_chapters)
                
                # Revise chapters to address consistency issues
                revision_agent = self.agents["revision"]
                revision_agent.revise_consistency_issues(written_chapters, consistency_analysis)
            
            # Mark stage as completed
            self.completed_stages.append("writing")
            self.completed_stages.append("review")
            self.completed_stages.append("revision")
            self.progress = 90
            
        except Exception as e:
            logger.error(f"Writing phase error: {str(e)}")
            self.errors.append(f"Writing phase: {str(e)}")
            raise
        
        finally:
            self._update_status()
    
    def _write_review_revise_chapter(
        self,
        chapter_outline: Dict[str, Any],
        outline: Dict[str, Any],
        integrated_data: Dict[str, Any],
        style_guide: Dict[str, Any],
        previously_written_chapters: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Write, review, and revise a single chapter."""
        chapter_id = chapter_outline.get("id", "")
        
        try:
            # Set current stage to writing
            self.current_stage = "writing"
            self._update_status()
            
            # Write the chapter
            writing_agent = self.agents["writing"]
            chapter = writing_agent.write_chapter(
                chapter_data=chapter_outline,
                characters=integrated_data["characters"],
                world_data=integrated_data["world"],
                previously_written_chapters=previously_written_chapters,
                style_guide=style_guide
            )
            
            # Set current stage to review
            self.current_stage = "review"
            self._update_status()
            
            # Review the chapter
            review_agent = self.agents["review"]
            review = review_agent.review_chapter(
                chapter_data=chapter,
                chapter_outline=chapter_outline,
                style_guide=style_guide
            )
            
            # Also do a readability analysis
            readability = review_agent.analyze_chapter_readability(chapter)
            
            # Set current stage to revision
            self.current_stage = "revision"
            self._update_status()
            
            # Revise the chapter based on the review
            revision_agent = self.agents["revision"]
            revised_chapter = revision_agent.revise_chapter(
                chapter_data=chapter,
                review_data=review
            )
            
            return revised_chapter
            
        except Exception as e:
            logger.error(f"Error processing chapter {chapter_id}: {str(e)}")
            self.errors.append(f"Chapter {chapter_id}: {str(e)}")
            raise
    
    def _execute_editorial_phase(self) -> None:
        """Execute the editorial phase of the workflow."""
        self.current_stage = "editorial"
        self._update_status()
        
        try:
            # Get all revised chapters
            revision_agent = self.agents["revision"]
            revised_chapters = revision_agent.get_all_revised_chapters()
            
            # If no revised chapters available, get the written chapters
            if not revised_chapters:
                writing_agent = self.agents["writing"]
                revised_chapters = writing_agent.get_all_written_chapters()
            
            # Get style guide if available
            writing_agent = self.agents["writing"]
            style_guide = writing_agent.get_style_guide()
            
            # Edit each chapter
            editorial_agent = self.agents["editorial"]
            edited_chapters = []
            
            for chapter in revised_chapters:
                edited_chapter = editorial_agent.edit_chapter(
                    chapter_data=chapter,
                    style_guide=style_guide
                )
                edited_chapters.append(edited_chapter)
            
            # Get the outline for structure reference
            outline_agent = self.agents["outline"]
            outline = outline_agent.get_complete_outline()
            
            # Create front and back matter
            book_info = {
                "title": self.title,
                "author": "AI Author",  # Placeholder
                "genre": self.genre
            }
            
            front_matter = editorial_agent.create_front_matter(book_info, outline)
            
            # Get character and world data for back matter
            integrated_data = self.central_hub.get_integrated_data()
            
            back_matter = editorial_agent.create_back_matter(
                book_info,
                characters=integrated_data["characters"],
                world_data=integrated_data["world"]
            )
            
            # Assemble final manuscript
            manuscript = editorial_agent.assemble_manuscript(
                book_info=book_info,
                chapters=edited_chapters,
                front_matter=front_matter,
                back_matter=back_matter
            )
            
            # Mark stage as completed
            self.completed_stages.append("editorial")
            self.progress = 100
            
        except Exception as e:
            logger.error(f"Editorial phase error: {str(e)}")
            self.errors.append(f"Editorial phase: {str(e)}")
            raise
        
        finally:
            self._update_status()
    
    def _update_status(self) -> None:
        """Update the project status in the central hub."""
        status = {
            "project_id": self.project_id,
            "status": self.status,
            "progress": self.progress,
            "current_stage": self.current_stage,
            "completed_stages": self.completed_stages,
            "is_running": self.is_running,
            "is_complete": self.is_complete,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "last_updated": datetime.now().isoformat(),
            "errors": self.errors
        }
        
        self.central_hub.update_project_status(status)
    
    def get_status(self) -> Dict[str, Any]:
        """Get the current workflow status."""
        status = self.central_hub.get_project_status()
        return status
    
    def get_final_manuscript(self) -> Optional[Dict[str, Any]]:
        """Get the final manuscript if available."""
        if not self.is_complete:
            return None
        
        editorial_agent = self.agents["editorial"]
        return editorial_agent.get_final_manuscript()
    
    def get_agent(self, agent_name: str) -> Any:
        """Get a specific agent by name."""
        if agent_name in self.agents:
            return self.agents[agent_name]
        return None
    
    def visualize_workflow(self) -> Dict[str, Any]:
        """Get a visualization of the workflow state."""
        # Update node status based on completed stages
        nodes = []
        for node_id, node_data in self.graph.nodes.items():
            node_status = "completed" if node_id in self.completed_stages else "pending"
            
            if node_id == self.current_stage:
                node_status = "current"
            
            nodes.append({
                "id": node_id,
                "label": node_data.label,
                "type": node_data.type,
                "status": node_status
            })
        
        # Get edges
        edges = []
        for edge in self.graph.edges:
            edges.append({
                "source": edge.source,
                "target": edge.target,
                "label": edge.label
            })
        
        return {
            "nodes": nodes,
            "edges": edges,
            "progress": self.progress,
            "current_stage": self.current_stage,
            "completed_stages": self.completed_stages
        }
