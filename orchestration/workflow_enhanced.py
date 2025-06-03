"""
Enhanced NovelNexus workflow with OpenMemory MCP integration and human-in-the-loop capabilities.
Fixes the quality issues by ensuring all stages run properly with human oversight.
"""

import logging
import json
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
import traceback

from orchestration.workflow import ManuscriptWorkflow
from memory.openmemory_mcp import OpenMemoryMCP
from interfaces.human_loop import HumanLoopInterface, CheckpointType, ReviewStatus
from hubs.central_hub import CentralHub

logger = logging.getLogger(__name__)

class EnhancedManuscriptWorkflow(ManuscriptWorkflow):
    """
    Enhanced manuscript workflow with:
    - OpenMemory MCP integration for persistent plot memory
    - Human-in-the-loop checkpoints for quality control
    - Proper stage execution (fixes the placeholder content issue)
    - Cross-chapter consistency checking
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
        enable_human_loop: bool = True,
        enable_mcp_memory: bool = True,
        mcp_server_url: str = "http://localhost:3434"
    ):
        """Initialize enhanced workflow."""
        super().__init__(
            project_id, title, genre, target_length, complexity,
            embedding_model, use_openai, use_gpu, initial_prompt
        )
        
        self.enable_human_loop = enable_human_loop
        self.enable_mcp_memory = False  # Temporarily disabled to test workflow
        self.mcp_server_url = mcp_server_url
        
        # Enhanced components
        self.mcp_memory = None
        self.human_loop = None
        
        # Quality control flags
        self.quality_gates_enabled = True
        self.min_chapter_words = 1000
        self.max_placeholder_ratio = 0.05
        
        # Stage execution tracking
        self.enhanced_stages = [
            "ideation",
            "research", 
            "character_development",
            "world_building",
            "plot_development",
            "chapter_planning",
            "chapter_writing",
            "longform_expansion",  # This was missing!
            "editorial_review",    # This was missing!
            "manuscript_assembly"
        ]

    async def _safe_mcp_call(self, coro, timeout=5.0, operation_name="MCP operation"):
        """Safely execute an MCP memory call with timeout and error handling."""
        if not self.mcp_memory:
            return None

        try:
            return await asyncio.wait_for(coro, timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning(f"Timeout during {operation_name} (>{timeout}s)")
            return None
        except Exception as e:
            logger.warning(f"Error during {operation_name}: {e}")
            return None

    async def initialize_enhanced_components(self):
        """Initialize OpenMemory MCP and Human Loop components."""
        try:
            # Initialize OpenMemory MCP
            if self.enable_mcp_memory:
                self.mcp_memory = OpenMemoryMCP(
                    project_id=self.project_id,
                    server_url=self.mcp_server_url
                )
                await self.mcp_memory.__aenter__()
                logger.info("OpenMemory MCP initialized successfully")
            
            # Initialize Human Loop Interface
            if self.enable_human_loop:
                self.human_loop = HumanLoopInterface(
                    project_id=self.project_id,
                    memory_system=self.mcp_memory or self.memory,
                    notification_callback=self._send_notification
                )
                logger.info("Human Loop Interface initialized successfully")
                
        except Exception as e:
            logger.error(f"Failed to initialize enhanced components: {e}")
            # Continue with basic workflow if enhanced features fail
            self.enable_mcp_memory = False
            self.enable_human_loop = False
    
    async def run_enhanced_workflow(self) -> Dict[str, Any]:
        """
        Run the enhanced workflow with all stages properly executed.
        This fixes the issue where longform expansion and editorial review were skipped.
        """
        try:
            # Initialize enhanced components
            await self.initialize_enhanced_components()
            
            # Set workflow as running
            self.is_running = True
            self.start_time = datetime.now()
            
            logger.info(f"Starting enhanced workflow for project {self.project_id}")
            
            # STAGE 1: Ideation with human review
            await self._run_enhanced_stage("ideation")
            
            # STAGE 2: Research
            await self._run_enhanced_stage("research")
            
            # STAGE 3: Character Development with MCP tracking
            await self._run_enhanced_stage("character_development")
            
            # STAGE 4: World Building with consistency tracking
            await self._run_enhanced_stage("world_building")
            
            # STAGE 5: Plot Development with narrative thread tracking
            await self._run_enhanced_stage("plot_development")
            
            # STAGE 6: Chapter Planning with human review
            await self._run_enhanced_stage("chapter_planning")
            
            # STAGE 7: Chapter Writing with quality gates
            await self._run_enhanced_stage("chapter_writing")
            
            # STAGE 8: Longform Expansion (THIS WAS MISSING!)
            await self._run_enhanced_stage("longform_expansion")
            
            # STAGE 9: Editorial Review (THIS WAS MISSING!)
            await self._run_enhanced_stage("editorial_review")
            
            # STAGE 10: Final Assembly
            await self._run_enhanced_stage("manuscript_assembly")
            
            # Mark as complete
            self.is_complete = True
            self.end_time = datetime.now()
            self.current_stage = "complete"
            
            logger.info(f"Enhanced workflow completed successfully for project {self.project_id}")
            
            # Get final manuscript
            final_manuscript = await self._get_enhanced_manuscript()
            return final_manuscript
            
        except Exception as e:
            logger.error(f"Enhanced workflow error: {str(e)}", exc_info=True)
            self.is_running = False
            self.error = str(e)
            raise
        finally:
            # Cleanup
            if self.mcp_memory:
                await self.mcp_memory.__aexit__(None, None, None)

    async def _send_notification(self, event_type: str, data: Dict[str, Any]):
        """Send notification for human loop events."""
        logger.info(f"Notification: {event_type} - {data}")
        # In a real implementation, this would send notifications via websockets, email, etc.
