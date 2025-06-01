"""
Flask extensions initialization.

This module handles the initialization of Flask extensions and 
third-party integrations used throughout the application.
"""

import logging
from flask import Flask
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from config.settings import BaseConfig

logger = logging.getLogger(__name__)

# Global extension instances
openai_client = None
active_workflows = {}

def init_extensions(app: Flask, config: 'BaseConfig') -> None:
    """
    Initialize all Flask extensions and integrations.
    
    Args:
        app: Flask application instance
        config: Application configuration
    """
    # Initialize OpenAI client if enabled
    if config.use_openai:
        init_openai(config)
    
    # Initialize workflow tracking
    init_workflow_tracking(app)
    
    # Initialize memory system directories
    init_memory_system(config)
    
    logger.info("All extensions initialized successfully")

def init_openai(config: 'BaseConfig') -> None:
    """Initialize OpenAI client with configuration."""
    global openai_client
    
    try:
        from models.openai_client import initialize_openai, get_openai_client
        
        # Initialize OpenAI with configuration
        initialize_openai()
        openai_client = get_openai_client()
        
        if openai_client and openai_client.is_available():
            logger.info("OpenAI client initialized successfully")
        else:
            logger.warning("OpenAI client initialized but not available")
            
    except ImportError:
        logger.error("OpenAI client module not found")
    except Exception as e:
        logger.error(f"Failed to initialize OpenAI client: {str(e)}")

def init_workflow_tracking(app: Flask) -> None:
    """Initialize workflow tracking system."""
    global active_workflows
    
    # Initialize empty workflow dictionary
    active_workflows.clear()
    
    # Store reference in app context
    app.config['ACTIVE_WORKFLOWS'] = active_workflows
    
    logger.info("Workflow tracking system initialized")

def init_memory_system(config: 'BaseConfig') -> None:
    """Initialize memory system directories and configuration."""
    import os
    from pathlib import Path
    
    # Ensure memory directories exist
    memory_base_dir = Path(config.memory_data_dir)
    memory_base_dir.mkdir(parents=True, exist_ok=True)
    
    # Create subdirectories for different types of memory data
    subdirs = ['projects', 'embeddings', 'cache', 'temp']
    for subdir in subdirs:
        (memory_base_dir / subdir).mkdir(exist_ok=True)
    
    logger.info(f"Memory system initialized at {memory_base_dir}")

def get_openai_client():
    """Get the global OpenAI client instance."""
    return openai_client

def get_active_workflows():
    """Get the active workflows dictionary."""
    return active_workflows

def cleanup_extensions() -> None:
    """Cleanup extensions on application shutdown."""
    global active_workflows, openai_client
    
    # Cleanup active workflows
    if active_workflows:
        logger.info(f"Cleaning up {len(active_workflows)} active workflows")
        for project_id, workflow in active_workflows.items():
            try:
                if hasattr(workflow, 'cleanup'):
                    workflow.cleanup()
            except Exception as e:
                logger.error(f"Error cleaning up workflow {project_id}: {str(e)}")
        
        active_workflows.clear()
    
    # Cleanup OpenAI client
    if openai_client:
        try:
            if hasattr(openai_client, 'close'):
                openai_client.close()
        except Exception as e:
            logger.error(f"Error closing OpenAI client: {str(e)}")
        
        openai_client = None
    
    logger.info("Extension cleanup completed")
