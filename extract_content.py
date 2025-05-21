#!/usr/bin/env python3
"""
Extract and display useful generated content from a NovelNexus project.
This script finds and shows the most interesting parts of the generated content,
such as chapter content, character descriptions, plot summaries, etc.
"""

import os
import sys
import json
import pickle
from tabulate import tabulate
from datetime import datetime

def load_memory(project_id):
    """Load memory data for a project."""
    memory_path = os.path.join("memory_data", project_id, "memory.pkl")
    if not os.path.exists(memory_path):
        print(f"Error: Memory file not found for project {project_id}!")
        return None
    
    try:
        with open(memory_path, 'rb') as f:
            return pickle.load(f)
    except Exception as e:
        print(f"Error loading memory file: {e}")
        return None

def extract_document_content(doc):
    """Extract content from a document."""
    if not isinstance(doc, dict):
        return None
    
    content = doc.get("content")
    
    # Handle different content formats
    if isinstance(content, str):
        return content
    elif isinstance(content, dict):
        # Try various keys that might contain content
        for key in ["content", "text", "value", "description"]:
            if key in content and isinstance(content[key], str):
                return content[key]
    
    return None

def get_document_metadata(doc):
    """Get metadata from a document."""
    if not isinstance(doc, dict):
        return {}
    
    return doc.get("metadata", {})

def extract_content(memory_data):
    """Extract useful content from memory data."""
    if not memory_data or not isinstance(memory_data, dict):
        return {}
    
    extracted = {
        "character_descriptions": [],
        "chapters": [],
        "plot_summary": [],
        "world_building": [],
        "research": [],
        "ideas": [],
        "outlines": [],
        "other": []
    }
    
    # Process documents
    if "documents" in memory_data and isinstance(memory_data["documents"], list):
        docs = memory_data["documents"]
        
        for doc in docs:
            content = extract_document_content(doc)
            if not content:
                continue
            
            metadata = get_document_metadata(doc)
            doc_type = metadata.get("type", "").lower()
            timestamp = metadata.get("timestamp", "")
            
            item = {
                "content": content,
                "metadata": metadata,
                "timestamp": timestamp
            }
            
            # Categorize by type
            if "character" in doc_type:
                extracted["character_descriptions"].append(item)
            elif "chapter" in doc_type:
                extracted["chapters"].append(item)
            elif "plot_summary" in doc_type or "plot summary" in doc_type:
                extracted["plot_summary"].append(item)
            elif "world_building" in doc_type or "worldbuilding" in doc_type or "setting" in doc_type:
                extracted["world_building"].append(item)
            elif "research" in doc_type:
                extracted["research"].append(item)
            elif "idea" in doc_type or "brainstorm" in doc_type:
                extracted["ideas"].append(item)
            elif "outline" in doc_type:
                extracted["outlines"].append(item)
            else:
                # Check content keywords for categorization
                content_lower = content.lower()
                if any(kw in content_lower for kw in ["character", "protagonist", "antagonist", "personality"]):
                    extracted["character_descriptions"].append(item)
                elif any(kw in content_lower for kw in ["chapter", "scene"]) and len(content) > 500:
                    extracted["chapters"].append(item)
                elif any(kw in content_lower for kw in ["plot summary", "story summary"]):
                    extracted["plot_summary"].append(item)
                elif any(kw in content_lower for kw in ["world", "setting", "place", "location"]):
                    extracted["world_building"].append(item)
                elif len(content) > 100:  # If it's substantial content
                    extracted["other"].append(item)
    
    # Sort each category by timestamp if available
    for category in extracted:
        if extracted[category]:
            try:
                extracted[category].sort(key=lambda x: x.get("timestamp", ""), reverse=True)
            except Exception:
                pass  # If sorting fails, keep original order
    
    return extracted

def display_content(extracted, max_preview_length=500):
    """Display extracted content with nice formatting."""
    for category, items in extracted.items():
        if not items:
            continue
        
        # Format category name nicely
        category_display = category.replace("_", " ").title()
        print(f"\n{'=' * 80}")
        print(f" {category_display} ({len(items)} items)")
        print(f"{'=' * 80}")
        
        for i, item in enumerate(items):
            content = item["content"]
            metadata = item["metadata"]
            
            # Get type and timestamp for display
            item_type = metadata.get("type", "Unknown")
            timestamp = metadata.get("timestamp", "")
            if timestamp:
                try:
                    # Try to format timestamp nicely if it's a valid date
                    timestamp = datetime.fromisoformat(timestamp).strftime("%Y-%m-%d %H:%M:%S")
                except (ValueError, TypeError):
                    pass
            
            print(f"\n--- Item #{i+1} ({item_type}) {timestamp} ---")
            
            # Display preview of content
            preview = content[:max_preview_length]
            if len(content) > max_preview_length:
                preview += "..."
            
            print(preview)
            print("-" * 80)
            
            # Option to see full content
            if len(content) > max_preview_length and i < len(items) - 1:
                try:
                    show_full = input("Show full content? (y/N): ").strip().lower() == 'y'
                    if show_full:
                        print("\nFull content:")
                        print(content)
                        print("-" * 80)
                        input("Press Enter to continue...")
                except KeyboardInterrupt:
                    print("\nSkipping...")

def main():
    if len(sys.argv) < 2:
        # If no project ID is provided, list all projects and ask the user to select one
        memory_dir = "memory_data"
        if not os.path.exists(memory_dir):
            print(f"Error: Memory directory '{memory_dir}' not found!")
            return
        
        projects = []
        for item in os.listdir(memory_dir):
            item_path = os.path.join(memory_dir, item)
            if os.path.isdir(item_path):
                try:
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
        
        print("Available Projects:\n")
        projects_table = []
        for i, (project_id, mod_time) in enumerate(projects):
            projects_table.append([i+1, project_id, mod_time])
        
        print(tabulate(projects_table, headers=["#", "Project ID", "Last Modified"], tablefmt="grid"))
        
        try:
            selection = int(input("\nEnter the number of the project to view (or 0 to quit): "))
            if selection < 1 or selection > len(projects):
                print("Invalid selection. Exiting.")
                return
            
            project_id = projects[selection-1][0]
        except (ValueError, KeyboardInterrupt):
            print("Invalid selection. Exiting.")
            return
    else:
        project_id = sys.argv[1]
    
    # Load memory data
    print(f"Loading project {project_id}...")
    memory_data = load_memory(project_id)
    
    if not memory_data:
        return
    
    # Extract and display content
    print(f"Extracting content from project {project_id}...")
    extracted = extract_content(memory_data)
    
    # Display stats
    total_items = sum(len(items) for items in extracted.values())
    print(f"\nFound {total_items} content items:")
    for category, items in extracted.items():
        if items:
            print(f"- {category.replace('_', ' ').title()}: {len(items)} items")
    
    # Ask whether to display content
    try:
        selection = input("\nWhat would you like to view? (all/characters/chapters/plot/world/research/ideas/outlines/other): ").strip().lower()
        
        if selection == "all":
            display_content(extracted)
        else:
            # Map selection to category keys
            category_map = {
                "characters": "character_descriptions",
                "chapters": "chapters",
                "plot": "plot_summary",
                "world": "world_building",
                "research": "research",
                "ideas": "ideas",
                "outlines": "outlines",
                "other": "other"
            }
            
            # Find matching category
            matching_categories = {}
            for key, value in category_map.items():
                if key in selection or selection in key:
                    matching_categories[value] = extracted[value]
            
            # Display matching categories
            if matching_categories:
                for category, items in matching_categories.items():
                    if items:
                        display_content({category: items})
            else:
                print("No matching content found.")
    except KeyboardInterrupt:
        print("\nExiting...")

if __name__ == "__main__":
    main() 