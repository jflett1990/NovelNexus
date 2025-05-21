#!/usr/bin/env python3
"""
Script to search for final manuscript content in memory files.
"""

import os
import sys
import json
import pickle

def find_manuscript(project_id):
    memory_path = os.path.join("memory_data", project_id, "memory.pkl")
    if not os.path.exists(memory_path):
        print(f"Error: Memory file not found for project {project_id}!")
        return
    
    try:
        with open(memory_path, 'rb') as f:
            memory_data = pickle.load(f)
        
        print(f"Searching project {project_id} for manuscript content...")
        
        # Search in documents array
        if "documents" in memory_data and isinstance(memory_data["documents"], list):
            docs = memory_data["documents"]
            print(f"Found {len(docs)} documents")
            
            # Keywords to look for in document content
            manuscript_keywords = [
                "chapter", "story", "manuscript", "novel", "narrative", 
                "plot", "character", "setting", "scene"
            ]
            
            # Search for documents that might be manuscript content
            potential_manuscripts = []
            
            for i, doc in enumerate(docs):
                if isinstance(doc, dict) and "content" in doc:
                    content = doc["content"]
                    metadata = doc.get("metadata", {})
                    
                    # If metadata suggests it's manuscript content
                    if metadata and isinstance(metadata, dict):
                        doc_type = metadata.get("type", "").lower()
                        if any(keyword in doc_type for keyword in ["chapter", "manuscript", "story"]):
                            potential_manuscripts.append((i, doc, "metadata type match"))
                            continue
                    
                    # If content is a string and looks like manuscript
                    if isinstance(content, str):
                        content_lower = content.lower()
                        if any(keyword in content_lower for keyword in manuscript_keywords) and len(content) > 500:
                            potential_manuscripts.append((i, doc, "content keyword match"))
                            continue
                    
                    # If content is a dict with manuscript-like structure
                    if isinstance(content, dict):
                        if "content" in content and isinstance(content["content"], str) and len(content["content"]) > 500:
                            potential_manuscripts.append((i, doc, "nested content match"))
                            continue
                        
                        # Look for any key that might contain the manuscript
                        for key, value in content.items():
                            if isinstance(value, str) and any(keyword in key.lower() for keyword in manuscript_keywords) and len(value) > 500:
                                potential_manuscripts.append((i, doc, f"content.{key} match"))
                                continue
            
            # Display potential manuscripts
            if potential_manuscripts:
                print(f"Found {len(potential_manuscripts)} potential manuscript documents")
                
                for i, (doc_index, doc, match_reason) in enumerate(potential_manuscripts):
                    print(f"\n--- Potential manuscript #{i+1} (document #{doc_index}, {match_reason}) ---")
                    print(f"Metadata: {doc.get('metadata', {})}")
                    
                    content = doc["content"]
                    if isinstance(content, dict) and "content" in content:
                        print("\nContent preview:")
                        print(content["content"][:1000])
                        print("...")
                    elif isinstance(content, str):
                        print("\nContent preview:")
                        print(content[:1000])
                        print("...")
                    else:
                        content_keys = list(content.keys()) if isinstance(content, dict) else "N/A"
                        print(f"Content type: {type(content)}, keys: {content_keys}")
            else:
                print("No manuscript content found in documents.")
        
        # Try looking in agent_memories
        if "agent_memories" in memory_data:
            print("\nChecking agent_memories...")
            agent_memories = memory_data["agent_memories"]
            
            # Check the manuscript_agent first
            if "manuscript_agent" in agent_memories:
                print("Found manuscript_agent memory")
                manuscripts = []
                
                memory = agent_memories["manuscript_agent"]
                if isinstance(memory, list):
                    for item in memory:
                        if isinstance(item, dict) and "content" in item:
                            content = item["content"]
                            if isinstance(content, str) and len(content) > 500:
                                manuscripts.append(item)
                            elif isinstance(content, dict) and "text" in content and isinstance(content["text"], str) and len(content["text"]) > 500:
                                manuscripts.append(item)
                
                if manuscripts:
                    print(f"Found {len(manuscripts)} manuscript entries in manuscript_agent memory")
                    for i, manuscript in enumerate(manuscripts):
                        print(f"\n--- Manuscript #{i+1} ---")
                        content = manuscript["content"]
                        
                        if isinstance(content, str):
                            print(content[:1000])
                            print("...")
                        elif isinstance(content, dict) and "text" in content:
                            print(content["text"][:1000])
                            print("...")
            
            # Check chapter_writer_agent memories
            if "chapter_writer_agent" in agent_memories:
                print("\nFound chapter_writer_agent memory")
                chapters = []
                
                memory = agent_memories["chapter_writer_agent"]
                if isinstance(memory, list):
                    for item in memory:
                        if isinstance(item, dict) and "content" in item:
                            content = item["content"]
                            if isinstance(content, str) and len(content) > 500:
                                chapters.append(item)
                            elif isinstance(content, dict) and "text" in content and isinstance(content["text"], str) and len(content["text"]) > 500:
                                chapters.append(item)
                
                if chapters:
                    print(f"Found {len(chapters)} chapter entries in chapter_writer_agent memory")
                    for i, chapter in enumerate(chapters):
                        print(f"\n--- Chapter #{i+1} ---")
                        content = chapter["content"]
                        
                        if isinstance(content, str):
                            print(content[:1000])
                            print("...")
                        elif isinstance(content, dict) and "text" in content:
                            print(content["text"][:1000])
                            print("...")
        
    except Exception as e:
        print(f"Error processing memory file: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        project_id = sys.argv[1]
    else:
        print("Usage: python find_manuscript.py <project_id>")
        sys.exit(1)
    
    find_manuscript(project_id) 