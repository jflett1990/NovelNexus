#!/usr/bin/env python3
"""
Script to display the final generated manuscript from a project.
"""

import os
import json
import sys
import pickle
from datetime import datetime
from tabulate import tabulate

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

def load_memory(project_id):
    """Load the memory pickle file for a project."""
    memory_path = os.path.join("memory_data", project_id, "memory.pkl")
    if not os.path.exists(memory_path):
        print(f"Error: Memory file not found for project {project_id}!")
        return None
    
    try:
        with open(memory_path, 'rb') as f:
            memory_data = pickle.load(f)
        return memory_data
    except Exception as e:
        print(f"Error loading memory file: {e}")
        return None

def get_document_content(doc):
    """Extract content from a document, handling different formats."""
    if isinstance(doc, dict):
        content = doc.get("content", {})
        if content:
            return content
    elif isinstance(doc, str):
        # Try to parse as JSON
        try:
            content = json.loads(doc)
            return content
        except:
            # If it's just a string, return it as is
            return doc
    
    return None

def print_content(content):
    """Print content in a readable format."""
    if isinstance(content, dict):
        if "content" in content:
            print(content["content"])
        elif "text" in content:
            print(content["text"])
        else:
            print(json.dumps(content, indent=2))
    elif isinstance(content, str):
        print(content)
    else:
        print(json.dumps(content, indent=2))

def extract_manuscript_content(memory_data):
    """Extract manuscript content from memory data."""
    # Check if we're working with a dictionary
    if not isinstance(memory_data, dict):
        print(f"Unexpected memory data format: {type(memory_data)}")
        return False
    
    # First try to find chapter content in a collection
    if "chapter_1_content" in memory_data:
        print("\n===== Chapter 1 Content =====")
        print_content(memory_data["chapter_1_content"])
        return True
    
    # Look for any manuscript content
    manuscript_keys = ["manuscript", "final_manuscript", "chapter_content"]
    for key in manuscript_keys:
        if key in memory_data:
            print(f"\n===== {key.replace('_', ' ').title()} =====")
            print_content(memory_data[key])
            return True
    
    # Look for documents
    if "documents" in memory_data:
        documents = memory_data["documents"]
        
        if not isinstance(documents, list):
            print(f"Unexpected documents format: {type(documents)}")
            return False
            
        # Try to find chapter documents
        chapter_documents = []
        
        for i, doc in enumerate(documents):
            if isinstance(doc, dict) and "metadata" in doc:
                metadata = doc["metadata"]
                doc_type = metadata.get("type", "").lower()
                if "chapter" in doc_type:
                    chapter_documents.append(doc)
            elif isinstance(doc, str):
                # Try to find chapter indicators in string
                if "chapter" in doc.lower():
                    try:
                        content = json.loads(doc)
                        chapter_documents.append({"content": content, "index": i})
                    except:
                        chapter_documents.append({"content": doc, "index": i})
        
        if chapter_documents:
            print("\n===== Chapter Content =====")
            for i, doc in enumerate(chapter_documents):
                print(f"\n--- Chapter {i+1} ---")
                if isinstance(doc, dict) and "content" in doc:
                    print_content(doc["content"])
                else:
                    print_content(doc)
            return True
    
    # Alternative approach for dictionary-based structure
    # Try looking directly in the root of the memory data for document types
    manuscript_types = ["chapter", "manuscript", "chapter_content", "story", "novel"]
    for key in memory_data.keys():
        for m_type in manuscript_types:
            if m_type in key.lower():
                print(f"\n===== {key} =====")
                print_content(memory_data[key])
                return True
    
    print("\nNo manuscript content found. The project may still be in progress.")
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
                
                # Check if it has a project status
                status = "Unknown"
                memory_data = load_memory(item)
                if memory_data and isinstance(memory_data, dict):
                    if "project_status" in memory_data:
                        status_data = memory_data["project_status"]
                        if isinstance(status_data, dict):
                            if "status" in status_data:
                                status = status_data["status"]
                                if "progress" in status_data:
                                    status += f" ({status_data['progress']}%)"
                
                projects.append([item, mod_time_str, status])
            except Exception as e:
                print(f"Error accessing {item_path}: {e}")
    
    if not projects:
        print(f"No projects found in '{memory_dir}'!")
        return
    
    # Sort by modification time (newest first)
    projects.sort(key=lambda x: datetime.strptime(x[1], '%Y-%m-%d %H:%M:%S'), reverse=True)
    
    print("\n===== Available Projects =====\n")
    print(tabulate(projects, headers=["Project ID", "Last Modified", "Status"], tablefmt="grid"))
    print("\nTo view a specific project's manuscript: python view_manuscript.py <project_id>\n")

def main():
    # Check if a specific project ID was provided
    if len(sys.argv) > 1:
        project_id = sys.argv[1]
        print(f"Looking for manuscript in project: {project_id}")
    else:
        # Find the latest project
        project_id = get_latest_project_id()
        if not project_id:
            display_project_list()
            return
        print(f"Auto-detected latest project: {project_id}")
    
    # Load the memory data
    memory_data = load_memory(project_id)
    if not memory_data:
        return
    
    # Extract and display manuscript content
    found_manuscript = extract_manuscript_content(memory_data)
    if not found_manuscript:
        # Try to find project config to show what was being generated
        if isinstance(memory_data, dict):
            if "project_config" in memory_data:
                config = memory_data["project_config"]
                print("\n===== Project Details =====\n")
                if isinstance(config, dict):
                    if "title" in config:
                        print(f"Title: {config['title']}")
                    if "genre" in config:
                        print(f"Genre: {config['genre']}")
                    if "initial_prompt" in config:
                        print(f"\nInitial Prompt: {config['initial_prompt']}")
    
    # Always show the project list at the end
    display_project_list()

if __name__ == "__main__":
    main() 