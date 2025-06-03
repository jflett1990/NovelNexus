"""
Script to display the generated content for any project ID.
"""

import sys
import json
from models.openai_client import initialize_openai, get_openai_client
from models.openai_models import EMBEDDING_MODEL
from memory.dynamic_memory import DynamicMemory

def main():
    # Check for project ID argument
    if len(sys.argv) < 2:
        print("Usage: python show_project_content.py <project_id>")
        return
    
    project_id = sys.argv[1]
    print(f"Fetching content for project: {project_id}")
    
    # Initialize OpenAI client for embeddings
    initialize_openai()
    openai_client = get_openai_client()
    embedding_function = lambda text: openai_client.get_embeddings(text, model=EMBEDDING_MODEL)
    
    # Initialize memory with the project ID
    memory = DynamicMemory(project_id, embedding_function)
    
    # Query all content for this project
    print("Querying memory for all content...")
    
    # List of content types to look for
    content_types = [
        {"name": "Manuscript", "query": "type:manuscript", "agent": None},
        {"name": "Final Manuscript", "query": "type:final_manuscript", "agent": None},
        {"name": "Chapter Content", "query": "type:chapter_content", "agent": "writing_agent"},
        {"name": "Edited Chapter", "query": "type:edited_chapter", "agent": "editorial_agent"},
        {"name": "Story Outline", "query": "type:outline", "agent": "outlining_agent"},
        {"name": "Character Development", "query": "type:character", "agent": "character_agent"},
        {"name": "Ideas", "query": "type:idea", "agent": "ideation_agent"},
        {"name": "Project Status", "query": "type:project_status", "agent": None},
        {"name": "Project Config", "query": "type:project_config", "agent": None}
    ]
    
    found_content = False
    
    # Check each content type
    for content_type in content_types:
        agent_name = content_type.get("agent")
        query = content_type.get("query")
        name = content_type.get("name")
        
        if agent_name:
            docs = memory.query_memory(query, agent_name=agent_name, top_k=10, threshold=0.1)
        else:
            docs = memory.query_memory(query, top_k=10, threshold=0.1)
        
        if docs and len(docs) > 0:
            found_content = True
            print(f"\n===== {name} =====")
            print(f"Found {len(docs)} document(s)")
            
            for i, doc in enumerate(docs):
                print(f"\n--- Document {i+1} ---")
                metadata = doc.get('metadata', {})
                print(f"Metadata: {json.dumps(metadata, indent=2)}")
                
                text = doc.get('text', '')
                # Try to parse as JSON for better formatting
                try:
                    parsed = json.loads(text)
                    print(f"Content:\n{json.dumps(parsed, indent=2)}")
                except:
                    # Not JSON, just print raw text with newlines preserved
                    print(f"Content:\n{text}")
    
    if not found_content:
        print("\nNo content found for this project. It might not exist or content generation hasn't started yet.")
        print("\nCheck the active projects in the database or try again later.")

if __name__ == "__main__":
    main() 