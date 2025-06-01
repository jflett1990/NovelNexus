"""
Error handling for workflow orchestration.

Provides centralized error handling, logging, and status management.
"""

import logging
import traceback
import json
from datetime import datetime
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class WorkflowErrorHandler:
    """Handles errors, logging, and status updates during workflow execution."""
    
    def __init__(self, project_id: str, central_hub, memory):
        self.project_id = project_id
        self.central_hub = central_hub
        self.memory = memory
        self.errors: List[Dict[str, Any]] = []
    
    def handle_agent_error(self, agent_key: str, error: Exception, current_stage: str) -> Dict[str, Any]:
        """
        Handle an error that occurred during agent execution.
        
        Args:
            agent_key: The key of the agent that failed
            error: The exception that occurred
            current_stage: The current workflow stage
            
        Returns:
            Dictionary containing error details
        """
        error_details = {
            "agent": agent_key,
            "error": str(error),
            "traceback": traceback.format_exc(),
            "timestamp": datetime.now().isoformat(),
            "stage": current_stage
        }
        
        # Log detailed error
        logger.error(f"Agent {agent_key} failed: {str(error)}", exc_info=True)
        
        # Store error in memory for user visibility
        self.memory.add_document(
            json.dumps(error_details),
            "workflow",
            metadata={"type": "error", "agent": agent_key, "stage": current_stage}
        )
        
        # Update workflow status
        self.errors.append(error_details)
        
        # Notify through central hub
        self.central_hub.update_project_status({
            "status": "error",
            "current_stage": current_stage,
            "error": error_details
        })
        
        return error_details
    
    def handle_workflow_error(self, error: Exception, current_stage: str, is_running: bool = True) -> None:
        """
        Handle a general workflow error.
        
        Args:
            error: The exception that occurred
            current_stage: The current workflow stage
            is_running: Whether the workflow is currently running
        """
        logger.error(f"Workflow error in stage {current_stage}: {str(error)}")
        
        error_details = {
            "stage": current_stage,
            "error": str(error),
            "traceback": traceback.format_exc(),
            "timestamp": datetime.now().isoformat()
        }
        
        self.errors.append(error_details)
        
        # Update status to error
        status_data = {
            "status": "error",
            "progress": self._get_current_progress(),
            "current_stage": current_stage,
            "error": str(error),
            "error_time": datetime.now().isoformat()
        }
        self.central_hub.update_project_status(status_data)
    
    def log_stage_error(self, stage: str, error_message: str) -> None:
        """Log an error for a specific stage."""
        error_details = {
            "stage": stage,
            "error": error_message,
            "timestamp": datetime.now().isoformat()
        }
        
        self.errors.append(error_details)
        logger.error(f"Stage {stage} error: {error_message}")
    
    def get_errors(self) -> List[Dict[str, Any]]:
        """Get all recorded errors."""
        return self.errors.copy()
    
    def has_errors(self) -> bool:
        """Check if any errors have been recorded."""
        return len(self.errors) > 0
    
    def clear_errors(self) -> None:
        """Clear all recorded errors."""
        self.errors.clear()
    
    def _get_current_progress(self) -> int:
        """Get the current progress from the central hub."""
        try:
            status = self.central_hub.get_project_status()
            return status.get("progress", 0)
        except:
            return 0
    
    def create_error_summary(self) -> Dict[str, Any]:
        """Create a summary of all errors for reporting."""
        if not self.errors:
            return {"has_errors": False, "error_count": 0}
        
        return {
            "has_errors": True,
            "error_count": len(self.errors),
            "errors": self.errors,
            "most_recent_error": self.errors[-1] if self.errors else None,
            "affected_stages": list(set(error.get("stage", "unknown") for error in self.errors)),
            "affected_agents": list(set(error.get("agent", "unknown") for error in self.errors if "agent" in error))
        }
