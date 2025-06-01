"""
Stage management for workflow orchestration.

Handles workflow stage transitions, progress tracking, and status updates.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class StageManager:
    """Manages workflow stages, progress tracking, and status updates."""
    
    def __init__(self, project_id: str, central_hub):
        self.project_id = project_id
        self.central_hub = central_hub
        
        # Stage tracking
        self.current_stage: Optional[str] = None
        self.completed_stages: List[str] = []
        self.last_progress_time: Optional[str] = None
        self.agent_start_time: Optional[str] = None
        self.current_agent: Optional[str] = None
        
        # Stage progress mapping
        self.progress_map = {
            "ideation": 5,
            "research": 15,
            "character_development": 25,
            "world_building": 40,
            "plot_development": 55,
            "chapter_planning": 70,
            "manuscript_assembly": 95,
            "completed": 100
        }
    
    def update_stage(self, stage: str) -> None:
        """Update the current workflow stage."""
        self.current_stage = stage
        self.last_progress_time = datetime.now().isoformat()
        
        # Calculate progress based on stage
        progress = self._calculate_stage_progress(stage)
        self._update_progress(progress)
        
        logger.info(f"Project {self.project_id} moved to stage: {stage} (progress: {progress}%)")
    
    def complete_stage(self, stage: str) -> None:
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
    
    def _calculate_stage_progress(self, stage: str) -> int:
        """Calculate progress percentage for a given stage."""
        # For chapter writing stages, interpolate between 70 and 95
        if stage.startswith("writing_chapter_"):
            try:
                chapter_num = int(stage.split("_")[-1])
                total_chapters = self._get_total_chapters()
                
                if total_chapters == 0:
                    total_chapters = 10  # Default fallback
                
                # Calculate progress (70% base + up to 25% for chapters)
                chapter_progress = int(70 + ((chapter_num - 1) / total_chapters) * 25)
                return min(95, chapter_progress)
            except:
                return 70
        else:
            return self.progress_map.get(stage, self.get_progress())
    
    def _get_total_chapters(self) -> int:
        """Get total number of chapters from chapter plan."""
        try:
            from memory.dynamic_memory import DynamicMemory
            chapter_docs = self.central_hub.memory.query_memory(
                "type:chapter_plan", agent_name="chapter_planner_agent"
            )
            if chapter_docs:
                import json
                chapter_plan = json.loads(chapter_docs[0].get("text", "{}"))
                return len(chapter_plan.get("chapters", []))
        except:
            pass
        return 0
    
    def _update_progress(self, progress: int) -> None:
        """Update the progress percentage."""
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
    
    def save_workflow_state(self, memory) -> None:
        """Save the current workflow state to memory."""
        state = {
            "current_stage": self.current_stage,
            "completed_stages": self.completed_stages,
            "last_progress_time": self.last_progress_time,
            "agent_start_time": self.agent_start_time,
            "current_agent": self.current_agent,
            "timestamp": datetime.now().isoformat()
        }
        
        import json
        memory.add_document(
            json.dumps(state),
            "workflow",
            metadata={"type": "workflow_state"}
        )
