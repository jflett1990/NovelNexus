#!/usr/bin/env python3
"""
Script to view chapter content from memory
"""

import sys
import json
import pickle
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from memory.dynamic_memory import DynamicMemory
from models.openai_client import get_openai_client

def view_chapters():
    """View chapter content from memory."""
    project_id = "174cf9b5-1f0b-46a5-9cd7-0e6b086b2ff3"
    
    # Initialize memory
    openai_client = get_openai_client()
    embedding_function = lambda text: openai_client.get_embeddings(text, model="text-embedding-3-small")
    memory = DynamicMemory(project_id, embedding_function)
    
    print(f"Memory loaded. Total documents: {memory.get_document_count()}")
    
    # Get chapter plan
    chapter_plan_docs = memory.query_memory("type:chapter_plan", agent_name="chapter_planner_agent")
    print(f"\nFound {len(chapter_plan_docs)} chapter plan documents")
    
    if chapter_plan_docs:
        print("\n=== CHAPTER PLAN ===")
        try:
            plan = json.loads(chapter_plan_docs[0]['text'])
            print(f"Number of chapters planned: {len(plan)}")
            for i, chapter in enumerate(plan):
                print(f"\nChapter {i+1}:")
                print(f"  Title: {chapter.get('title', 'N/A')}")
                print(f"  POV: {chapter.get('pov_character', 'N/A')}")
                print(f"  Setting: {chapter.get('setting', 'N/A')}")
                print(f"  Plot points: {chapter.get('plot_points', ['N/A'])[:2]}")  # Show first 2
        except Exception as e:
            print(f"Error parsing chapter plan: {e}")
            print(f"Raw text: {chapter_plan_docs[0]['text'][:500]}...")
    
    # Look for actual chapters
    print("\n\n=== LOOKING FOR WRITTEN CHAPTERS ===")
    
    # Check different agents that might have chapters
    agents_to_check = [
        "chapter_writer_agent",
        "longform_expander", 
        "editorial_agent",
        "manuscript_refiner"
    ]
    
    for agent in agents_to_check:
        docs = memory.get_agent_memory(agent)
        if docs:
            print(f"\n{agent}: {len(docs)} documents")
            for doc in docs[:2]:  # Show first 2
                print(f"  Type: {doc.get('metadata', {}).get('type', 'unknown')}")
                print(f"  Text preview: {doc['text'][:100]}...")
    
    # Search for any chapter content
    chapter_docs = memory.query_memory("type:chapter")
    expanded_docs = memory.query_memory("type:expanded_chapter")
    reviewed_docs = memory.query_memory("type:reviewed_chapter")
    
    print(f"\n\nChapter documents found:")
    print(f"  Regular chapters: {len(chapter_docs)}")
    print(f"  Expanded chapters: {len(expanded_docs)}")
    print(f"  Reviewed chapters: {len(reviewed_docs)}")
    
    # Display any found chapters
    all_chapter_docs = chapter_docs + expanded_docs + reviewed_docs
    if all_chapter_docs:
        print("\n=== CHAPTER CONTENT ===")
        for doc in all_chapter_docs[:2]:  # Show first 2
            try:
                chapter_data = json.loads(doc['text'])
                print(f"\nChapter {chapter_data.get('number', 'N/A')}: {chapter_data.get('title', 'N/A')}")
                print(f"Word count: {chapter_data.get('word_count', 'N/A')}")
                content = chapter_data.get('content', '')
                if content:
                    print(f"Content preview: {content[:300]}...")
                else:
                    print("No content in chapter data")
            except:
                print(f"Raw text: {doc['text'][:300]}...")

if __name__ == "__main__":
    view_chapters() 