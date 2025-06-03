"""
Human-in-the-Loop interface for NovelNexus.
Provides checkpoints for human review and approval during manuscript generation.
"""

import json
import logging
import asyncio
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime
from enum import Enum
import uuid

logger = logging.getLogger(__name__)

class ReviewStatus(Enum):
    """Status of human review."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    MODIFIED = "modified"
    SKIPPED = "skipped"

class CheckpointType(Enum):
    """Types of human review checkpoints."""
    CHAPTER_OUTLINE = "chapter_outline"
    CHAPTER_DRAFT = "chapter_draft"
    CHARACTER_PROFILE = "character_profile"
    PLOT_DEVELOPMENT = "plot_development"
    WORLD_BUILDING = "world_building"
    STYLE_REVIEW = "style_review"
    QUALITY_GATE = "quality_gate"

class HumanLoopInterface:
    """
    Interface for human-in-the-loop manuscript generation.
    Manages review checkpoints, feedback collection, and workflow pausing.
    """
    
    def __init__(
        self,
        project_id: str,
        memory_system: Any,
        notification_callback: Optional[Callable] = None
    ):
        """
        Initialize human loop interface.
        
        Args:
            project_id: Unique project identifier
            memory_system: Memory system for storing reviews
            notification_callback: Optional callback for notifications
        """
        self.project_id = project_id
        self.memory = memory_system
        self.notification_callback = notification_callback
        
        # Active review sessions
        self.pending_reviews = {}  # review_id -> review_data
        self.review_history = []
        
        # Configuration
        self.auto_approve_timeout = 3600  # 1 hour default
        self.quality_thresholds = {
            "min_word_count": 500,
            "max_placeholder_ratio": 0.1,
            "min_dialogue_ratio": 0.15
        }
    
    async def create_review_checkpoint(
        self,
        checkpoint_type: CheckpointType,
        content: Dict[str, Any],
        context: Dict[str, Any] = None,
        auto_approve: bool = False,
        timeout_seconds: int = None
    ) -> str:
        """
        Create a human review checkpoint.
        
        Args:
            checkpoint_type: Type of review checkpoint
            content: Content to be reviewed
            context: Additional context for the review
            auto_approve: Whether to auto-approve after timeout
            timeout_seconds: Custom timeout (uses default if None)
            
        Returns:
            Review ID for tracking
        """
        review_id = str(uuid.uuid4())
        timeout = timeout_seconds or self.auto_approve_timeout
        
        review_data = {
            "id": review_id,
            "project_id": self.project_id,
            "type": checkpoint_type.value,
            "content": content,
            "context": context or {},
            "status": ReviewStatus.PENDING.value,
            "created_at": datetime.now().isoformat(),
            "timeout_at": datetime.now().timestamp() + timeout,
            "auto_approve": auto_approve,
            "feedback": {},
            "modifications": {}
        }
        
        # Store in pending reviews
        self.pending_reviews[review_id] = review_data
        
        # Store in memory for persistence
        await self._store_review(review_data)
        
        # Send notification
        if self.notification_callback:
            await self.notification_callback(
                "review_created",
                {
                    "review_id": review_id,
                    "type": checkpoint_type.value,
                    "project_id": self.project_id
                }
            )
        
        logger.info(f"Created review checkpoint {review_id} for {checkpoint_type.value}")
        return review_id
    
    async def submit_review(
        self,
        review_id: str,
        status: ReviewStatus,
        feedback: Dict[str, Any] = None,
        modifications: Dict[str, Any] = None
    ) -> bool:
        """
        Submit human review for a checkpoint.
        
        Args:
            review_id: Review identifier
            status: Review status (approved, rejected, modified)
            feedback: Human feedback
            modifications: Content modifications
            
        Returns:
            True if review was successfully submitted
        """
        if review_id not in self.pending_reviews:
            logger.error(f"Review {review_id} not found in pending reviews")
            return False
        
        review_data = self.pending_reviews[review_id]
        
        # Update review data
        review_data.update({
            "status": status.value,
            "feedback": feedback or {},
            "modifications": modifications or {},
            "reviewed_at": datetime.now().isoformat()
        })
        
        # Move to history
        self.review_history.append(review_data)
        del self.pending_reviews[review_id]
        
        # Store updated review
        await self._store_review(review_data)
        
        # Send notification
        if self.notification_callback:
            await self.notification_callback(
                "review_completed",
                {
                    "review_id": review_id,
                    "status": status.value,
                    "project_id": self.project_id
                }
            )
        
        logger.info(f"Review {review_id} completed with status: {status.value}")
        return True
    
    async def wait_for_review(
        self,
        review_id: str,
        check_interval: int = 5
    ) -> Dict[str, Any]:
        """
        Wait for human review to be completed.
        
        Args:
            review_id: Review identifier
            check_interval: How often to check (seconds)
            
        Returns:
            Completed review data
        """
        while review_id in self.pending_reviews:
            review_data = self.pending_reviews[review_id]
            
            # Check for timeout
            if (review_data["auto_approve"] and 
                datetime.now().timestamp() > review_data["timeout_at"]):
                
                logger.info(f"Auto-approving review {review_id} due to timeout")
                await self.submit_review(
                    review_id,
                    ReviewStatus.APPROVED,
                    {"note": "Auto-approved due to timeout"}
                )
                break
            
            # Wait before checking again
            await asyncio.sleep(check_interval)
        
        # Find in history
        for review in self.review_history:
            if review["id"] == review_id:
                return review
        
        raise ValueError(f"Review {review_id} not found")
    
    async def check_quality_gate(
        self,
        content: str,
        content_type: str = "chapter"
    ) -> Dict[str, Any]:
        """
        Automated quality check before human review.
        
        Args:
            content: Content to check
            content_type: Type of content
            
        Returns:
            Quality assessment results
        """
        issues = []
        metrics = {}
        
        # Word count check
        word_count = len(content.split())
        metrics["word_count"] = word_count
        
        if word_count < self.quality_thresholds["min_word_count"]:
            issues.append(f"Word count too low: {word_count} < {self.quality_thresholds['min_word_count']}")
        
        # Placeholder content check
        placeholder_indicators = [
            "[Note:", "placeholder", "TODO", "FIXME",
            "This is a story-specific placeholder"
        ]
        
        placeholder_count = sum(1 for indicator in placeholder_indicators if indicator.lower() in content.lower())
        placeholder_ratio = placeholder_count / max(word_count, 1)
        metrics["placeholder_ratio"] = placeholder_ratio
        
        if placeholder_ratio > self.quality_thresholds["max_placeholder_ratio"]:
            issues.append(f"Too much placeholder content: {placeholder_ratio:.2%}")
        
        # Dialogue ratio check (for chapters)
        if content_type == "chapter":
            dialogue_chars = len([c for c in content if c in '"\''])
            total_chars = len(content)
            dialogue_ratio = dialogue_chars / max(total_chars, 1)
            metrics["dialogue_ratio"] = dialogue_ratio
            
            if dialogue_ratio < self.quality_thresholds["min_dialogue_ratio"]:
                issues.append(f"Low dialogue ratio: {dialogue_ratio:.2%}")
        
        # Character consistency check
        if "Lila Trent" in content:
            # Check for character name consistency
            variations = ["Lila", "Trent", "Lila Trent"]
            for variation in variations:
                if variation in content and variation != "Lila Trent":
                    # This is a simplified check - in practice, you'd use more sophisticated NLP
                    pass
        
        quality_score = max(0, 100 - len(issues) * 20)
        
        return {
            "quality_score": quality_score,
            "metrics": metrics,
            "issues": issues,
            "passed": len(issues) == 0
        }
    
    async def get_review_status(self, review_id: str) -> Optional[Dict[str, Any]]:
        """Get current status of a review."""
        if review_id in self.pending_reviews:
            return self.pending_reviews[review_id]
        
        for review in self.review_history:
            if review["id"] == review_id:
                return review
        
        return None
    
    async def get_pending_reviews(self) -> List[Dict[str, Any]]:
        """Get all pending reviews for the project."""
        return list(self.pending_reviews.values())
    
    async def get_review_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get review history for the project."""
        return self.review_history[-limit:]
    
    async def _store_review(self, review_data: Dict[str, Any]):
        """Store review data in memory system."""
        try:
            if hasattr(self.memory, 'add_document'):
                # Traditional memory system
                self.memory.add_document(
                    json.dumps(review_data),
                    "human_loop_interface",
                    metadata={
                        "type": "review",
                        "review_id": review_data["id"],
                        "status": review_data["status"],
                        "checkpoint_type": review_data["type"]
                    }
                )
            elif hasattr(self.memory, 'add_memory'):
                # OpenMemory MCP system
                await self.memory.add_memory(
                    f"Review {review_data['type']}: {review_data['status']}",
                    review_data
                )
        except Exception as e:
            logger.error(f"Failed to store review data: {e}")
    
    def configure_quality_thresholds(self, thresholds: Dict[str, Any]):
        """Update quality check thresholds."""
        self.quality_thresholds.update(thresholds)
        logger.info(f"Updated quality thresholds: {self.quality_thresholds}")
    
    def set_auto_approve_timeout(self, seconds: int):
        """Set default auto-approve timeout."""
        self.auto_approve_timeout = seconds
        logger.info(f"Set auto-approve timeout to {seconds} seconds")
