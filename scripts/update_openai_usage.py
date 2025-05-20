#!/usr/bin/env python
"""
Script to update the NovelNexus application to prioritize OpenAI models over Ollama.
This script:
1. Updates app.py to set use_openai=True by default
2. Creates a function to add model selection to agent files
"""

import os
import re
import fileinput
from pathlib import Path

NOVELNEXUS_ROOT = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def update_app_config():
    """Update app.py to use OpenAI as the primary model service."""
    app_py_path = NOVELNEXUS_ROOT / 'app.py'
    
    if not app_py_path.exists():
        print(f"Could not find app.py at {app_py_path}")
        return False
    
    print(f"Updating {app_py_path}")
    updated = False
    
    # Define the pattern to look for
    pattern = re.compile(r'^\s*"use_openai":\s*False,.*?# Set to True to use OpenAI', re.MULTILINE)
    
    with open(app_py_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if pattern.search(content):
        # Replace the pattern
        updated_content = pattern.sub('"use_openai": True,   # Using OpenAI as primary service', content)
        
        # Write the updated content
        with open(app_py_path, 'w', encoding='utf-8') as f:
            f.write(updated_content)
        
        updated = True
    
    return updated

def update_workflow_default():
    """Update workflow.py to use OpenAI as the default."""
    workflow_py_path = NOVELNEXUS_ROOT / 'orchestration' / 'workflow.py'
    
    if not workflow_py_path.exists():
        print(f"Could not find workflow.py at {workflow_py_path}")
        return False
    
    print(f"Updating {workflow_py_path}")
    updated = False
    
    # Define the pattern to look for in the ManuscriptWorkflow.__init__ method
    pattern = re.compile(r'(\s+use_openai:\s*bool\s*=\s*)False,', re.MULTILINE)
    
    with open(workflow_py_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if pattern.search(content):
        # Replace the pattern
        updated_content = pattern.sub(r'\1True,', content)
        
        # Write the updated content
        with open(workflow_py_path, 'w', encoding='utf-8') as f:
            f.write(updated_content)
        
        updated = True
    
    return updated

def add_model_selection_utils():
    """Create a utility module for model selection."""
    utils_dir = NOVELNEXUS_ROOT / 'utils'
    utils_dir.mkdir(exist_ok=True)
    
    model_utils_path = utils_dir / 'model_utils.py'
    
    content = """# Model selection utilities for NovelNexus
import logging
from typing import Dict, Any, Optional
from models.openai_models import get_agent_model

logger = logging.getLogger(__name__)

def select_model(agent_name: str, use_openai: bool, use_fallback: bool = False) -> Dict[str, Any]:
    \"\"\"
    Select the appropriate model for an agent based on configuration.
    
    Args:
        agent_name: Name of the agent
        use_openai: Whether to use OpenAI (True) or Ollama (False)
        use_fallback: Whether to use fallback models if available
        
    Returns:
        Dictionary with model information
    \"\"\"
    model_info = {}
    
    if use_openai:
        # Get the OpenAI model for this agent
        model_name = get_agent_model(agent_name, use_fallback)
        logger.info(f"Selected OpenAI model for {agent_name}: {model_name}")
        model_info["provider"] = "openai"
        model_info["model"] = model_name
    else:
        # Default Ollama models based on agent type
        ollama_models = {
            "ideation": "llama3:8b-instruct-q4_0",
            "manuscript": "deepseek-v2:16b",
            "character": "llama3:8b-instruct-q4_0",
            "world_building": "llama3:8b-instruct-q4_0",
            "research": "llama3:8b-instruct-q4_0",
            "outline": "deepseek-v2:16b",
            "review": "deepseek-v2:16b",
            "editorial": "deepseek-v2:16b",
            "revision": "llama3:8b-instruct-q4_0",
            "plot": "llama3:8b-instruct-q4_0",
            "chapter_planner": "llama3:8b-instruct-q4_0",
            "chapter_writer": "deepseek-v2:16b",
        }
        
        # Get default model or use a standard default
        model_name = ollama_models.get(agent_name, "llama3:8b-instruct-q4_0")
        logger.info(f"Selected Ollama model for {agent_name}: {model_name}")
        model_info["provider"] = "ollama"
        model_info["model"] = model_name
    
    return model_info
"""
    
    with open(model_utils_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"Created {model_utils_path}")
    return True

def main():
    """Main function to update the NovelNexus application."""
    print("Updating NovelNexus to use OpenAI models...")
    
    # Update app.py
    if update_app_config():
        print("Successfully updated app.py to use OpenAI as the primary model service")
    else:
        print("No changes needed for app.py")
    
    # Update workflow.py
    if update_workflow_default():
        print("Successfully updated workflow.py to use OpenAI as the default")
    else:
        print("No changes needed for workflow.py")
    
    # Add model selection utils
    if add_model_selection_utils():
        print("Successfully added model selection utilities")
    
    print("\nUpdates complete!")
    print("\nNext steps:")
    print("1. Make sure to set your OPENAI_API_KEY in the .env file")
    print("2. Update agent implementations to use the model_utils.select_model function")
    print("3. Restart the application to apply the changes")

if __name__ == "__main__":
    main() 