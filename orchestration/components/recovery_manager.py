"""
Recovery management for workflow orchestration.

Handles error recovery, fallback creation, and workflow continuation strategies.
"""

import logging
import json
from datetime import datetime
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class RecoveryManager:
    """Manages error recovery and fallback strategies for workflow continuation."""
    
    def __init__(self, project_id: str, memory, stage_manager):
        self.project_id = project_id
        self.memory = memory
        self.stage_manager = stage_manager
    
    def attempt_recovery(self, agent_key: str, error_details: Dict[str, Any]) -> None:
        """
        Attempt to recover from an agent failure.
        
        Args:
            agent_key: The key of the failed agent
            error_details: Details about the error
        """
        logger.info(f"Attempting to recover from {agent_key} failure")
        
        # Different recovery strategies based on agent
        if agent_key == "ideation":
            self._recover_ideation(error_details)
        elif agent_key in ["character", "world_building", "research"]:
            self._recover_with_minimal_output(agent_key, error_details)
        else:
            logger.warning(f"No specific recovery strategy for {agent_key}")
    
    def _recover_ideation(self, error_details: Dict[str, Any]) -> None:
        """Create fallback idea for ideation agent failure."""
        try:
            fallback_idea = {
                "ideas": [{
                    "id": "fallback_idea",
                    "title": "Untitled Project",
                    "premise": "A compelling story that overcomes challenges and transforms lives.",
                    "themes": ["resilience", "transformation"],
                    "genre": "general",
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
            self.stage_manager.complete_stage("ideation")
            
        except Exception as e:
            logger.error(f"Failed to create fallback idea: {e}")
            raise
    
    def _recover_with_minimal_output(self, agent_key: str, error_details: Dict[str, Any]) -> None:
        """Create minimal viable output for an agent to allow pipeline continuation."""
        try:
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
            self.stage_manager.complete_stage(agent_key)
            
        except Exception as e:
            logger.error(f"Failed to create minimal {agent_key} output: {e}")
            raise
    
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
    
    def create_fallback_chapter(self, chapter_number: int = 1) -> Dict[str, Any]:
        """Create a fallback chapter for chapter writing failures."""
        return {
            "number": chapter_number,
            "title": f"Chapter {chapter_number}",
            "summary": "Introduction to the story and characters",
            "content": f"This is Chapter {chapter_number} of the story. It introduces the main characters and sets up the central conflict.",
            "word_count": 50,
            "recovery": True
        }
    
    def assess_recovery_success(self, agent_key: str) -> bool:
        """
        Assess whether recovery was successful for an agent.
        
        Args:
            agent_key: The agent that underwent recovery
            
        Returns:
            True if recovery appears successful, False otherwise
        """
        try:
            # Check if the agent's output exists in memory with recovery flag
            docs = self.memory.query_memory(f"type:{agent_key}", agent_name=f"{agent_key}_agent")
            if docs:
                for doc in docs:
                    metadata = doc.get("metadata", {})
                    if metadata.get("recovery", False):
                        return True
            return False
        except Exception as e:
            logger.error(f"Failed to assess recovery success for {agent_key}: {e}")
            return False
