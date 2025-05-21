#!/usr/bin/env python3
"""
Dashboard script to automatically display the latest generated content.
No need to manually enter project IDs - just run this script.
"""

import os
import json
import time
from datetime import datetime
import sys
from tabulate import tabulate

# Try to import from the app's modules
try:
    from models.openai_client import initialize_openai, get_openai_client
    from models.openai_models import EMBEDDING_MODEL
    from memory.dynamic_memory import DynamicMemory
    is_app_available = True
except ImportError:
    is_app_available = False

def get_latest_project_id():
    """Find the most recently modified project directory in memory_data."""
    memory_dir = "memory_data"
    if not os.path.exists(memory_dir):
        print(f"Error: Memory directory '{memory_dir}' not found!")
        return None
    
    projects = []
    for item in os.listdir(memory_dir):
        item_path = os.path.join(memory_dir, item)
        if os.path.isdir(item_path):
            try:
                # Get the modification time
                mod_time = os.path.getmtime(item_path)
                projects.append((item, mod_time))
            except Exception as e:
                print(f"Error accessing {item_path}: {e}")
    
    if not projects:
        print(f"No projects found in '{memory_dir}'!")
        return None
    
    # Sort by modification time (newest first)
    projects.sort(key=lambda x: x[1], reverse=True)
    return projects[0][0]  # Return the newest project ID

def display_memory_contents(project_id):
    """Display memory contents for a project without using the app modules."""
    memory_path = os.path.join("memory_data", project_id, "memory.pkl")
    if not os.path.exists(memory_path):
        print(f"Error: Memory file not found for project {project_id}!")
        return False
    
    print(f"\n===== Raw Content for Project {project_id} =====\n")
    
    # Use the show_project_content.py script if it exists
    if os.path.exists("show_project_content.py"):
        os.system(f"python show_project_content.py {project_id}")
        return True
    
    print("Manual inspection required: Use 'python show_project_content.py {project_id}' to see contents")
    return False

def display_project_list():
    """Display a list of all available projects sorted by last modified time."""
    memory_dir = "memory_data"
    if not os.path.exists(memory_dir):
        print(f"Error: Memory directory '{memory_dir}' not found!")
        return
    
    projects = []
    for item in os.listdir(memory_dir):
        item_path = os.path.join(memory_dir, item)
        if os.path.isdir(item_path):
            try:
                # Get the modification time
                mod_time = os.path.getmtime(item_path)
                mod_time_str = datetime.fromtimestamp(mod_time).strftime('%Y-%m-%d %H:%M:%S')
                projects.append([item, mod_time_str])
            except Exception as e:
                print(f"Error accessing {item_path}: {e}")
    
    if not projects:
        print(f"No projects found in '{memory_dir}'!")
        return
    
    # Sort by modification time (newest first)
    projects.sort(key=lambda x: datetime.strptime(x[1], '%Y-%m-%d %H:%M:%S'), reverse=True)
    
    print("\n===== Available Projects =====\n")
    print(tabulate(projects, headers=["Project ID", "Last Modified"], tablefmt="grid"))
    print("\nTo view a specific project: python view_latest_content.py <project_id>\n")

def main():
    # Check if a specific project ID was provided
    if len(sys.argv) > 1:
        project_id = sys.argv[1]
        print(f"Displaying content for specified project: {project_id}")
    else:
        # Find the latest project
        project_id = get_latest_project_id()
        if not project_id:
            display_project_list()
            return
        print(f"Auto-detected latest project: {project_id}")
    
    # Display the content
    success = display_memory_contents(project_id)
    
    if not success:
        print("\nAlternatively, use one of these commands to see the content:")
        print(f"1. Run the web app: ./run_app.sh")
        print(f"   Then visit: http://localhost:8080/view-generated-text/{project_id}")
        print(f"2. Use the content viewer script: python show_project_content.py {project_id}")
        
    # Always show the project list at the end
    display_project_list()

if __name__ == "__main__":
    main() 