from orchestration.workflow import ManuscriptWorkflow
from models.openai_client import initialize_openai, get_openai_client
from models.openai_models import EMBEDDING_MODEL
from datetime import datetime
import uuid
import time
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize OpenAI client
print("Initializing OpenAI client...")
initialize_openai()
openai_client = get_openai_client()

# Generate a unique project ID
project_id = str(uuid.uuid4())
print(f"Project ID: {project_id}")

# Create basic project parameters
title = "Test Project"
genre = "Horror"
initial_prompt = "Write a short horror story about a haunted forest."

print(f"Creating workflow with title: {title}, genre: {genre}")
print(f"Initial prompt: {initial_prompt}")

try:
    # Initialize embedding function
    print("Initializing embedding function...")
    embedding_function = lambda text: openai_client.get_embeddings(text, model=EMBEDDING_MODEL)
    
    # Create workflow
    print("Creating workflow...")
    workflow = ManuscriptWorkflow(
        project_id=project_id,
        title=title,
        genre=genre,
        target_length="short",  # Make it short for faster generation
        complexity="simple",    # Make it simple for faster generation
        initial_prompt=initial_prompt
    )
    
    # Start workflow but don't wait for it to finish
    print("Starting workflow...")
    workflow.start()
    
    # Wait for 30 seconds to give it time to generate initial content
    print("Waiting 30 seconds for initial content generation...")
    time.sleep(30)
    
    # Print status
    print(f"Workflow status: {workflow.current_stage}")
    print(f"Progress: {workflow.get_progress()}%")
    
    # Try to retrieve any generated content
    print("\nChecking for generated content...")
    memory = workflow.central_hub.memory
    
    # Query for any content
    content_docs = memory.query_memory("type:*", top_k=10, threshold=0.1)
    
    print(f"Found {len(content_docs)} documents")
    if len(content_docs) > 0:
        for i, doc in enumerate(content_docs):
            print(f"\nDocument {i+1}:")
            print(f"Type: {doc.get('metadata', {}).get('type', 'unknown')}")
            text = doc.get('text', '')
            # Try to parse as JSON if possible
            try:
                parsed = json.loads(text)
                print(f"Content (JSON): {json.dumps(parsed, indent=2)[:300]}...")
            except:
                print(f"Content (text): {text[:300]}...")  # Print first 300 chars
    else:
        print("No documents found. The workflow might still be initializing.")
        
    print("\nYou can view this project's content at:")
    print(f"http://localhost:8080/view-generated-text/{project_id}")
        
except Exception as e:
    print(f"Error: {str(e)}") 