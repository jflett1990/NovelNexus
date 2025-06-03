#!/usr/bin/env python3
"""
Script to inspect a memory file to find any manuscript or chapter data.
"""

import os
import sys
import json
import pickle

def inspect_memory(project_id):
    memory_path = os.path.join("memory_data", project_id, "memory.pkl")
    if not os.path.exists(memory_path):
        print(f"Error: Memory file not found for project {project_id}!")
        return
    
    try:
        with open(memory_path, 'rb') as f:
            memory_data = pickle.load(f)
        
        print(f"Memory data type: {type(memory_data)}")
        
        if isinstance(memory_data, dict):
            print(f"Keys: {list(memory_data.keys())}")
            
            # Check for chapter content or manuscript directly in the memory data
            for key in memory_data.keys():
                if "chapter" in key.lower() or "manuscript" in key.lower():
                    print(f"\nFound key: {key}")
                    content = memory_data[key]
                    if isinstance(content, dict):
                        print(f"Content type: {type(content)}")
                        print(f"Content keys: {list(content.keys())}")
                        if "content" in content:
                            print("\nContent:")
                            print(content["content"][:1000])
                    elif isinstance(content, str):
                        print("\nContent:")
                        print(content[:1000])
                    else:
                        print(f"Content type: {type(content)}")
            
            # Check documents
            if "documents" in memory_data:
                documents = memory_data["documents"]
                print(f"\nFound {len(documents)} documents")
                
                chapter_docs = []
                manuscript_docs = []
                
                for doc in documents:
                    if isinstance(doc, dict) and "metadata" in doc:
                        metadata = doc["metadata"]
                        doc_type = metadata.get("type", "").lower()
                        
                        if "chapter" in doc_type:
                            chapter_docs.append(doc)
                        elif "manuscript" in doc_type:
                            manuscript_docs.append(doc)
                
                print(f"Found {len(chapter_docs)} chapter documents")
                print(f"Found {len(manuscript_docs)} manuscript documents")
                
                if chapter_docs:
                    print("\nFirst chapter document:")
                    chapter = chapter_docs[0]
                    print(f"Metadata: {chapter.get('metadata', {})}")
                    content = chapter.get("content", {})
                    if isinstance(content, dict) and "content" in content:
                        print("\nContent:")
                        print(content["content"][:1000])
                    elif isinstance(content, str):
                        print("\nContent:")
                        print(content[:1000])
                
                if manuscript_docs:
                    print("\nFirst manuscript document:")
                    manuscript = manuscript_docs[0]
                    print(f"Metadata: {manuscript.get('metadata', {})}")
                    content = manuscript.get("content", {})
                    if isinstance(content, dict) and "content" in content:
                        print("\nContent:")
                        print(content["content"][:1000])
                    elif isinstance(content, str):
                        print("\nContent:")
                        print(content[:1000])
            
            # Check agent_memories
            if "agent_memories" in memory_data:
                agent_memories = memory_data["agent_memories"]
                print(f"\nFound agent_memories: {list(agent_memories.keys())}")
                
                for agent, memory in agent_memories.items():
                    print(f"\nAgent: {agent}")
                    print(f"Memory type: {type(memory)}")
                    
                    if hasattr(memory, "get_all_documents"):
                        docs = memory.get_all_documents()
                        print(f"Found {len(docs)} documents")
                        
                        for doc in docs:
                            if "chapter" in doc.metadata.get("type", "").lower() or "manuscript" in doc.metadata.get("type", "").lower():
                                print(f"\nMetadata: {doc.metadata}")
                                print("\nContent:")
                                if isinstance(doc.content, dict) and "content" in doc.content:
                                    print(doc.content["content"][:1000])
                                elif isinstance(doc.content, str):
                                    print(doc.content[:1000])
    
    except Exception as e:
        print(f"Error loading memory file: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        project_id = sys.argv[1]
    else:
        print("Usage: python inspect_memory.py <project_id>")
        sys.exit(1)
    
    inspect_memory(project_id) 