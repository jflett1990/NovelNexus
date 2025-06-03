"""
Web Blueprint for NovelNexus.

This module contains all web interface routes that serve HTML pages,
separated from the API endpoints.
"""

import logging
import json
import uuid
import traceback
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, make_response
from core.middleware import log_performance
from core.extensions import get_active_workflows, get_openai_client

logger = logging.getLogger(__name__)

# Create web blueprint
web_bp = Blueprint('web', __name__)

@web_bp.route('/')
def home():
    """Home page with form to generate new manuscript."""
    projects = session.get('projects', [])
    return render_template('index.html', projects=projects)

@web_bp.route('/dashboard/<project_id>')
@log_performance()
def dashboard(project_id):
    """Dashboard to monitor generation progress."""
    try:
        # Get status from central hub
        from hubs.central_hub import CentralHub
        from memory.dynamic_memory import DynamicMemory
        from models.openai_client import get_openai_client
        from models.openai_models import EMBEDDING_MODEL
        
        # Initialize memory with embedding function using OpenAI
        openai_client = get_openai_client()
        embedding_function = lambda text: openai_client.get_embeddings(text, model=EMBEDDING_MODEL)
        memory = DynamicMemory(project_id, embedding_function)
        
        # Initialize hub with memory
        hub = CentralHub(project_id, memory)
        status = hub.get_project_status()
        
        # Initialize empty data structures for template
        logs = []
        stage_outputs = {}
        chapters = []
        
        return render_template(
            'dashboard.html', 
            title=f"Project {project_id}", 
            project_id=project_id,
            status=status,
            logs=logs,
            stage_outputs=stage_outputs,
            chapters=chapters
        )
        
    except Exception as e:
        logger.error(f"Error loading dashboard: {str(e)}")
        status = {
            "status": "unknown",
            "current_stage": "not_started",
            "progress": 0,
            "completed_stages": []
        }
        return render_template(
            'dashboard.html', 
            title=f"Project {project_id}", 
            project_id=project_id,
            status=status,
            logs=[],
            stage_outputs={},
            chapters=[]
        )

@web_bp.route('/generate', methods=['GET', 'POST'])
@log_performance()
def generate():
    """Generate a new manuscript."""
    if request.method == 'POST':
        try:
            # Get form data
            title = request.form.get('title', '')
            genre = request.form.get('genre', '')
            target_length = request.form.get('target_length', 'medium')
            complexity = request.form.get('complexity', 'medium')
            initial_prompt = request.form.get('initial_prompt', '')
            
            # Generate a unique project ID if not provided
            project_id = request.form.get('project_id')
            if not project_id:
                project_id = str(uuid.uuid4())
            
            logger.info(f"Creating new project {project_id} with title: {title}, genre: {genre}")
            
            # Store in session if not already there
            projects = session.get('projects', [])
            if project_id not in [p.get('project_id') for p in projects]:
                projects.append({
                    'project_id': project_id,
                    'title': title or f"Project {project_id[:8]}",
                    'genre': genre,
                    'created_at': datetime.now().isoformat()
                })
                session['projects'] = projects
            
            # Configuration for the manuscript workflow
            config = {
                'project_id': project_id,
                'title': title,
                'genre': genre,
                'target_length': target_length,
                'complexity': complexity,
                'initial_prompt': initial_prompt,
                'use_openai': True
            }
            
            # Status to store in the central hub
            status = {
                "status": "initialized",
                "created_at": datetime.now().isoformat(),
                "title": title,
                "genre": genre,
                "target_length": target_length,
                "complexity": complexity
            }
            
            # Initialize memory and hub to store initial status
            from hubs.central_hub import CentralHub
            from memory.dynamic_memory import DynamicMemory
            from models.openai_client import get_openai_client
            from models.openai_models import EMBEDDING_MODEL
            
            openai_client = get_openai_client()
            embedding_function = lambda text: openai_client.get_embeddings(text, model=EMBEDDING_MODEL)
            memory = DynamicMemory(project_id, embedding_function)
            hub = CentralHub(project_id, memory)
            
            # Store initial status
            hub.update_project_status(status)
            
            # Initialize process for manuscript generation
            try:
                from core.app import celery_app
                
                if celery_app:
                    # Run asynchronously using Celery
                    logger.info(f"Starting async workflow for project {project_id}")
                    from tasks.workflow_tasks import run_workflow_task
                    task = run_workflow_task.delay(project_id=project_id, **config)
                    
                    # Store task ID in memory for tracking
                    task_data = {
                        "task_id": task.id,
                        "status": "started",
                        "timestamp": datetime.now().isoformat()
                    }
                    memory.add_document(
                        json.dumps(task_data),
                        "workflow",
                        metadata={"type": "task_info"}
                    )
                    
                    flash(f'Starting manuscript generation with Celery task ID: {task.id}')
                else:
                    raise ImportError("Celery not available")
                    
            except (ImportError, Exception):
                # Fall back to direct execution in a thread
                logger.info(f"Starting threaded workflow for project {project_id}")
                from orchestration.workflow import ManuscriptWorkflow
                
                workflow = ManuscriptWorkflow(**config)
                active_workflows = get_active_workflows()
                active_workflows[project_id] = workflow
                workflow.start()
                flash('Starting manuscript generation in a background thread')
            
            return redirect(url_for('web.dashboard', project_id=project_id))
            
        except Exception as e:
            logger.error(f"Error starting generation: {str(e)}", exc_info=True)
            flash(f'Error starting generation: {str(e)}', 'error')
            return redirect(url_for('web.home'))
    
    # GET method - render the form
    return render_template('generate.html')

@web_bp.route('/project-status/<project_id>')
@log_performance()
def project_status(project_id):
    """Show status of a project without using the dashboard."""
    try:
        active_workflows = get_active_workflows()
        
        if project_id in active_workflows:
            workflow = active_workflows[project_id]
            
            # Get status directly from the workflow
            status = {
                "is_running": workflow.is_running,
                "is_complete": workflow.is_complete,
                "current_stage": workflow.current_stage,
                "completed_stages": workflow.completed_stages,
                "errors": workflow.errors
            }
            
            # Get any available content from the workflow
            content = ""
            if workflow.is_complete:
                try:
                    # If the workflow is complete, try to get the final manuscript
                    manuscript = workflow.get_final_manuscript()
                    if manuscript and "content" in manuscript:
                        content = manuscript["content"]
                except Exception as e:
                    logger.error(f"Error getting manuscript: {str(e)}")
                    content = f"Error getting manuscript: {str(e)}"
            
            # Get all relevant logs for this project
            from core.app import get_log_buffer
            log_buffer = get_log_buffer()
            project_logs = [log for log in log_buffer if project_id in str(log['message'])]
            log_entries = [f"{log['timestamp']} - {log['level']} - {log['message']}" for log in project_logs]
            
            # Render a simple status page
            return _render_project_status_page(project_id, status, log_entries, content)
        else:
            return _render_project_not_found_page(project_id)
            
    except Exception as e:
        logger.error(f"Error displaying project status: {str(e)}", exc_info=True)
        return _render_error_page(project_id, str(e), traceback.format_exc())

@web_bp.route('/view-manuscript/<project_id>')
@log_performance()
def view_manuscript(project_id):
    """View the manuscript in a nice format."""
    try:
        # Try to get the workflow from active workflows
        manuscript = None
        title = "Untitled"
        
        active_workflows = get_active_workflows()
        if project_id in active_workflows:
            workflow = active_workflows[project_id]
            
            # Check if the workflow is complete
            if not workflow.is_complete:
                return _render_manuscript_not_ready_page(project_id, workflow)
            
            # Get the manuscript
            manuscript = workflow.get_final_manuscript()
            if manuscript:
                title = manuscript.get("title", "Untitled")
        
        # If not found in active workflows or no manuscript, try to retrieve from memory
        if not manuscript:
            manuscript, title = _get_manuscript_from_memory(project_id)
            
        if not manuscript:
            return _render_manuscript_not_found_page(project_id)
        
        # Format the manuscript content
        content = manuscript.get("content", "")
        chapters = manuscript.get("chapters", [])
        word_count = manuscript.get("word_count", len(content.split()))
        
        # Render the manuscript
        return _render_manuscript_page(project_id, title, content, word_count)
        
    except Exception as e:
        logger.error(f"Error viewing manuscript: {str(e)}", exc_info=True)
        return _render_error_page(project_id, str(e), traceback.format_exc())

@web_bp.route('/view-generated-text/<project_id>')
@log_performance()
def view_generated_text(project_id):
    """View all generated text for a specific project in a simple format."""
    try:
        # Initialize memory with embedding function using OpenAI
        from memory.dynamic_memory import DynamicMemory
        from models.openai_client import get_openai_client
        from models.openai_models import EMBEDDING_MODEL
        
        openai_client = get_openai_client()
        embedding_function = lambda text: openai_client.get_embeddings(text, model=EMBEDDING_MODEL)
        memory = DynamicMemory(project_id, embedding_function)
        
        # Collect all generated content from various stages
        generated_content = []
        
        # Get various types of generated content
        stages = [
            {"name": "Manuscript", "query": "type:manuscript", "agent": None},
            {"name": "Final Manuscript", "query": "type:final_manuscript", "agent": None},
            {"name": "Chapter Content", "query": "type:chapter_content", "agent": "writing_agent"},
            {"name": "Edited Chapter", "query": "type:edited_chapter", "agent": "editorial_agent"},
            {"name": "Story Outline", "query": "type:outline", "agent": "outlining_agent"},
            {"name": "Character Development", "query": "type:character", "agent": "character_agent"},
            {"name": "Ideas", "query": "type:idea", "agent": "ideation_agent"}
        ]
        
        for stage in stages:
            agent_name = stage.get("agent")
            query = stage.get("query")
            name = stage.get("name")
            
            if agent_name:
                docs = memory.query_memory(query, agent_name=agent_name, top_k=10, threshold=0.1)
            else:
                docs = memory.query_memory(query, top_k=10, threshold=0.1)
            
            if docs:
                for doc in docs:
                    try:
                        content = doc['text']
                        # If it's JSON, try to parse it for better display
                        try:
                            json_content = json.loads(content)
                            if isinstance(json_content, dict) and "content" in json_content:
                                content = json_content["content"]
                            elif isinstance(json_content, dict) and "chapters" in json_content:
                                chapters_content = ""
                                for chapter in json_content.get("chapters", []):
                                    chapter_title = chapter.get("title", "")
                                    chapter_content = chapter.get("content", "")
                                    chapters_content += f"## {chapter_title}\n\n{chapter_content}\n\n"
                                content = chapters_content
                        except json.JSONDecodeError:
                            # Not JSON, use as is
                            pass
                        
                        metadata = doc.get('metadata', {})
                        timestamp = metadata.get('timestamp', 'Unknown time')
                        
                        generated_content.append({
                            "name": name,
                            "content": content,
                            "metadata": metadata,
                            "timestamp": timestamp
                        })
                    except Exception as e:
                        logger.error(f"Error processing document: {str(e)}")
                        continue
        
        # Sort by timestamp if available
        generated_content.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        
        # Render the content
        return render_template(
            'generated_text.html',
            title=f"Generated Text for Project {project_id}",
            project_id=project_id,
            content=generated_content
        )
    
    except Exception as e:
        logger.error(f"Error viewing generated text: {str(e)}", exc_info=True)
        return _render_error_page(project_id, str(e), traceback.format_exc())

# Helper functions for rendering pages
def _render_project_status_page(project_id, status, log_entries, content=""):
    """Render project status page."""
    return f"""
    <html>
    <head>
        <title>Project Status</title>
        <style>
            body {{ font-family: Arial, sans-serif; max-width: 1000px; margin: 0 auto; padding: 20px; }}
            .container {{ border: 1px solid #ddd; padding: 20px; border-radius: 5px; margin-bottom: 20px; }}
            h1 {{ text-align: center; margin-bottom: 30px; }}
            h2 {{ text-align: center; margin-top: 40px; }}
            .logs {{ max-height: 400px; overflow-y: auto; }}
            .nav {{ margin-top: 30px; text-align: center; }}
        </style>
        <meta http-equiv="refresh" content="10">
    </head>
    <body>
        <div class="container">
            <h1>Project Status: {project_id}</h1>
            <h2>Status</h2>
            <ul>
                <li><strong>Running:</strong> {status['is_running']}</li>
                <li><strong>Complete:</strong> {status['is_complete']}</li>
                <li><strong>Current Stage:</strong> {status['current_stage'] or 'None'}</li>
                <li><strong>Completed Stages:</strong> {', '.join(status['completed_stages'])}</li>
            </ul>
            
            <h2>Errors</h2>
            <pre>{json.dumps(status['errors'], indent=2) if status['errors'] else 'No errors'}</pre>
            
            <h2>Recent Logs</h2>
            <div class="logs">
                <pre>{'\\n'.join(log_entries[-50:])}</pre>
            </div>
            
            {f'<h2>Final Manuscript</h2><pre>{content}</pre>' if content else ''}
            
            <div class="nav">
                <p><a href="/view-generated-text/{project_id}">View All Generated Text</a> | 
                <a href="/generate">Start New Project</a> | 
                <a href="/">Home</a></p>
            </div>
            {f'<p><a href="/view-manuscript/{project_id}">View Full Manuscript</a></p>' if status['is_complete'] else ''}
        </div>
    </body>
    </html>
    """

def _render_project_not_found_page(project_id):
    """Render project not found page."""
    return f"""
    <html>
    <head>
        <title>Project Not Found</title>
        <style>
            body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }}
            .container {{ border: 1px solid #ddd; padding: 20px; border-radius: 5px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Project Not Found</h1>
            <p>The project with ID {project_id} was not found in active workflows.</p>
            <p>This could be because:</p>
            <ul>
                <li>The server was restarted and active workflows were cleared</li>
                <li>The project ID is incorrect</li>
                <li>The project has been completed and removed from active workflows</li>
            </ul>
            <p><a href="/view-generated-text/{project_id}">View Generated Text</a> | <a href="/generate">Start New Project</a> | <a href="/">Home</a></p>
        </div>
    </body>
    </html>
    """

def _render_manuscript_not_ready_page(project_id, workflow):
    """Render manuscript not ready page."""
    return f"""
    <html>
    <head>
        <title>Manuscript Not Ready</title>
        <style>
            body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }}
            .container {{ border: 1px solid #ddd; padding: 20px; border-radius: 5px; }}
        </style>
        <meta http-equiv="refresh" content="10">
    </head>
    <body>
        <div class="container">
            <h1>Manuscript Not Ready</h1>
            <p>The manuscript generation is still in progress.</p>
            <p>Current stage: {workflow.current_stage}</p>
            <p>Progress: {workflow.get_progress()}%</p>
            <p><a href="/project-status/{project_id}">View Project Status</a></p>
        </div>
    </body>
    </html>
    """

def _render_manuscript_not_found_page(project_id):
    """Render manuscript not found page."""
    return f"""
    <html>
    <head>
        <title>Manuscript Not Found</title>
        <style>
            body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }}
            .container {{ border: 1px solid #ddd; padding: 20px; border-radius: 5px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Manuscript Not Found</h1>
            <p>The manuscript for project {project_id} was not found.</p>
            <p><a href="/project-status/{project_id}">View Project Status</a></p>
        </div>
    </body>
    </html>
    """

def _render_manuscript_page(project_id, title, content, word_count):
    """Render the manuscript page."""
    return f"""
    <html>
    <head>
        <title>{title}</title>
        <style>
            body {{ font-family: Georgia, serif; max-width: 800px; margin: 0 auto; padding: 20px; line-height: 1.6; }}
            .container {{ padding: 20px; }}
            h1 {{ text-align: center; margin-bottom: 30px; }}
            h2 {{ text-align: center; margin-top: 40px; }}
            .meta {{ text-align: center; color: #666; margin-bottom: 30px; }}
            .manuscript {{ white-space: pre-wrap; }}
            .nav {{ margin-top: 30px; text-align: center; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>{title}</h1>
            <div class="meta">Word Count: {word_count}</div>
            
            <div class="manuscript">
{content}
            </div>
            
            <div class="nav">
                <p><a href="/project-status/{project_id}">Back to Project Status</a> | <a href="/">Home</a></p>
            </div>
        </div>
    </body>
    </html>
    """

def _render_error_page(project_id, error_message, traceback_text):
    """Render error page."""
    return f"""
    <html>
    <head>
        <title>Error</title>
        <style>
            body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }}
            .error {{ border: 1px solid #d32f2f; padding: 20px; border-radius: 5px; background-color: #ffebee; }}
            .error h1 {{ color: #d32f2f; margin-top: 0; }}
            .error p {{ margin-bottom: 20px; }}
            pre {{ white-space: pre-wrap; background-color: #f5f5f5; padding: 10px; }}
        </style>
    </head>
    <body>
        <div class="error">
            <h1>Error Viewing Project</h1>
            <p>{error_message}</p>
            <h3>Debug Information:</h3><pre>{traceback_text}</pre>
            <p><a href="/project-status/{project_id}">Back to Project Status</a> | <a href="/">Home</a></p>
        </div>
    </body>
    </html>
    """

def _get_manuscript_from_memory(project_id):
    """Get manuscript from memory storage."""
    try:
        from memory.dynamic_memory import DynamicMemory
        from models.openai_client import get_openai_client
        from models.openai_models import EMBEDDING_MODEL
        
        # Initialize memory with embedding function using OpenAI
        openai_client = get_openai_client()
        embedding_function = lambda text: openai_client.get_embeddings(text, model=EMBEDDING_MODEL)
        memory = DynamicMemory(project_id, embedding_function)
        
        # Query memory for manuscript
        manuscript_docs = memory.query_memory("type:manuscript", top_k=1)
        
        # If not found, try with final_manuscript type
        if not manuscript_docs or len(manuscript_docs) == 0:
            manuscript_docs = memory.query_memory("type:final_manuscript", top_k=1)
            
        if not manuscript_docs or len(manuscript_docs) == 0:
            return None, "Untitled"
        
        # Parse the manuscript data
        try:
            manuscript_data = json.loads(manuscript_docs[0]['text'])
            title = manuscript_data.get("title", "Untitled")
            return manuscript_data, title
        except json.JSONDecodeError:
            # If not JSON, create a simple manuscript object
            manuscript = {
                "content": manuscript_docs[0]['text'],
                "title": "Untitled",
                "chapters": []
            }
            return manuscript, "Untitled"
            
    except Exception as e:
        logger.error(f"Error getting manuscript from memory: {str(e)}")
        return None, "Untitled"
