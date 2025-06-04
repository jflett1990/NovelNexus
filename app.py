import os
import logging
import json
import argparse
import traceback
import uuid
import sys
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, make_response

print("DEBUG: app.py is being loaded/reloaded")
from werkzeug.middleware.proxy_fix import ProxyFix
from orchestration.workflow import ManuscriptWorkflow
from orchestration.workflow_enhanced import EnhancedManuscriptWorkflow
from models.openai_client import initialize_openai, get_openai_client
from models.openai_models import EMBEDDING_MODEL
from memory.dynamic_memory import DynamicMemory
from hubs.central_hub import CentralHub
from interfaces.human_loop import HumanLoopInterface, ReviewStatus
from collections import deque
from datetime import datetime
import dotenv
from memory.openmemory_mcp import OpenMemoryMCP

# Configure Celery for background tasks
try:
    from celery import Celery
    
    # Initialize Celery
    celery_enabled = True
    celery_app = Celery('novelNexus')
    
    # Configure Celery - using Redis as a broker by default
    celery_broker = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0')
    celery_backend = os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
    
    celery_app.conf.update({
        'broker_url': celery_broker,
        'result_backend': celery_backend,
        'task_serializer': 'json',
        'accept_content': ['json'],
        'result_serializer': 'json',
        'enable_utc': True,
        'task_track_started': True,
        'task_time_limit': 18000,  # 5 hours max task time
        'worker_max_tasks_per_child': 1  # Avoid memory leaks
    })
    
    logger = logging.getLogger(__name__)
    logger.info(f"Celery initialized with broker: {celery_broker}")
    
    @celery_app.task(bind=True)
    def run_workflow_task(self, project_id, **config):
        """Celery task to run the manuscript workflow asynchronously."""
        try:
            logger.info(f"Starting async workflow for project {project_id}")
            # Initialize logging for this task
            task_logger = logging.getLogger(f"workflow.task.{project_id}")
            
            # Initialize and run workflow
            workflow = ManuscriptWorkflow(project_id=project_id, **config)
            workflow.execute()
            
            task_logger.info(f"Completed async workflow for project {project_id}")
            return {"status": "success", "project_id": project_id}
        except Exception as e:
            logger.error(f"Error in async workflow for project {project_id}: {str(e)}", exc_info=True)
            return {
                "status": "error", 
                "project_id": project_id,
                "error": str(e),
                "traceback": traceback.format_exc()
            }
            
except ImportError:
    logger = logging.getLogger(__name__)
    logger.warning("Celery not installed. Async processing will be disabled.")
    celery_enabled = False
    celery_app = None
    run_workflow_task = None

# Configure logging first
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()  # Add console output
    ]
)

logger = logging.getLogger(__name__)

# More verbose logging for key components
logging.getLogger('orchestration.workflow').setLevel(logging.DEBUG)
logging.getLogger('agents').setLevel(logging.DEBUG)
logging.getLogger('hubs.central_hub').setLevel(logging.DEBUG)
logging.getLogger('memory.dynamic_memory').setLevel(logging.DEBUG)

# Dictionary to store recent logs
log_buffer = deque(maxlen=500)

# Custom log handler to capture logs in buffer
class BufferLogHandler(logging.Handler):
    def emit(self, record):
        try:
            log_entry = {
                'timestamp': self.formatter.formatTime(record),
                'level': record.levelname,
                'module': record.name,
                'message': record.getMessage()
            }
            log_buffer.append(log_entry)
        except Exception:
            self.handleError(record)

# Add the buffer handler to the root logger
buffer_handler = BufferLogHandler()
buffer_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logging.getLogger().addHandler(buffer_handler)

# Load environment variables with better error handling
try:
    dotenv.load_dotenv(override=True)
    logger.info("Successfully loaded .env file")
except Exception as e:
    logger.warning(f"Could not load .env file: {str(e)}")
    # Create default environment variables if .env fails to load
    default_env = {
        "SECRET_KEY": "novelNexusSecretKey12345"
    }
    for key, value in default_env.items():
        if key not in os.environ:
            os.environ[key] = value
    logger.info("Using default environment variables")

# Create Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "novelNexusSecretKey12345")

# Dictionary to store active workflows
active_workflows = {}

# Initialize OpenAI client
logger.info("Initializing OpenAI client...")
initialize_openai()
logger.info("OpenAI client initialized successfully")

# Add proxy fix for reverse proxy setups
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

# Request handlers
@app.before_request
def before_request():
    """Prepare session data before each request."""
    if 'projects' not in session:
        session['projects'] = []

@app.after_request
def add_header(response):
    """Add headers to prevent caching for dynamic content."""
    response.headers['Cache-Control'] = 'no-store'
    return response

# Home page
@app.route('/')
def home():
    """Home page with form to generate new manuscript."""
    projects = session.get('projects', [])
    return render_template('index.html', projects=projects)

# Dashboard page
@app.route('/dashboard/<project_id>')
def dashboard(project_id):
    """Dashboard to monitor generation progress."""
    try:
        # Get status from central hub
        
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

# API endpoint to get project status
@app.route('/api/project/<project_id>/status', methods=['GET'])
def get_project_status(project_id):
    """API endpoint to get current project status."""
    try:
        # Get status from active workflow
        if project_id in active_workflows:
            workflow = active_workflows[project_id]
            status = {
                "project_id": project_id,
                "status": "running" if workflow.is_running and not workflow.is_complete else "complete" if workflow.is_complete else "not_started",
                "progress": workflow.get_progress(),
                "current_stage": workflow.current_stage,
                "current_agent": workflow.current_agent if hasattr(workflow, 'current_agent') else workflow.current_stage + "_agent" if workflow.current_stage else None,
                "completed_stages": workflow.completed_stages,
                "is_running": workflow.is_running,
                "is_complete": workflow.is_complete,
                "threads_alive": workflow.thread_health(),
                "errors": []
            }
        else:
            # Try to get status from central hub
            
            # Initialize memory with embedding function using OpenAI
            openai_client = get_openai_client()
            embedding_function = lambda text: openai_client.get_embeddings(text, model=EMBEDDING_MODEL)
            memory = DynamicMemory(project_id, embedding_function)
            
            # Initialize hub with memory
            hub = CentralHub(project_id, memory)
            status = hub.get_project_status()
            
            # Add current_agent based on current_stage if not present
            if 'current_agent' not in status and 'current_stage' in status and status['current_stage']:
                status['current_agent'] = status['current_stage'] + "_agent"
            
        logger.debug(f"Retrieved status for project {project_id}: {json.dumps(status)}")
        return jsonify(status)
    except Exception as e:
        logger.error(f"Error getting project status: {str(e)}")
        return jsonify({
            "project_id": project_id,
            "status": "error",
            "message": str(e),
            "error_details": traceback.format_exc()
        }), 500

# API endpoint to get dashboard data
@app.route('/api/dashboard-data/<project_id>', methods=['GET'])
def get_dashboard_data(project_id):
    """API endpoint to get all data needed for dashboard."""
    logger.info(f"DEBUG: Dashboard API called for project {project_id}")
    try:
        # Get status from central hub
        
        # Initialize memory with embedding function using OpenAI
        openai_client = get_openai_client()
        embedding_function = lambda text: openai_client.get_embeddings(text, model=EMBEDDING_MODEL)
        memory = DynamicMemory(project_id, embedding_function)
        
        # Initialize hub with memory
        hub = CentralHub(project_id, memory)
        
        # Initialize default project status
        project_status = {
            "status": "not_started",
            "current_stage": "not_started",
            "progress": 0,
            "completed_stages": [],
            "is_running": False,
            "is_complete": False,
            "current_agent": None,
            "project_id": project_id
        }

        # Try to get timeline, handle if method doesn't exist
        try:
            timeline = hub.get_timeline()
        except (AttributeError, Exception) as e:
            logger.warning(f"Error getting timeline: {str(e)}")
            timeline = []

        # Check if we need to load active workflow data (this takes precedence)
        logger.info(f"Dashboard API: Checking for active workflow {project_id}")
        logger.info(f"Dashboard API: Active workflows keys: {list(active_workflows.keys())}")
        print(f"DEBUG: Dashboard API called for {project_id}, active_workflows has keys: {list(active_workflows.keys())}")

        # Try to get workflow status directly (same as debug endpoint)
        workflow = active_workflows.get(project_id)
        print(f"DEBUG: workflow = {workflow}, type = {type(workflow)}")
        logger.info(f"Dashboard API: workflow = {workflow}, type = {type(workflow)}")
        if workflow:
            logger.info(f"Dashboard API: Found active workflow for {project_id}")
            print(f"DEBUG: Found active workflow for {project_id}")

            # Calculate progress based on completed stages
            total_stages = 9  # Total number of stages in the workflow
            completed_count = len(workflow.completed_stages)
            progress_percentage = min(int((completed_count / total_stages) * 100), 100)

            # Get current agent name from current stage
            current_agent = None
            if workflow.current_stage:
                stage_to_agent = {
                    'ideation': 'Ideation Agent',
                    'research': 'Research Agent',
                    'character_development': 'Character Agent',
                    'world_building': 'World Building Agent',
                    'plot_development': 'Plot Agent',
                    'chapter_planning': 'Chapter Planner Agent',
                    'writing_chapter_1': 'Chapter Writer Agent (Chapter 1)',
                    'writing_chapter_2': 'Chapter Writer Agent (Chapter 2)',
                    'writing_chapter_3': 'Chapter Writer Agent (Chapter 3)',
                    'writing_chapter_4': 'Chapter Writer Agent (Chapter 4)',
                    'writing_chapter_5': 'Chapter Writer Agent (Chapter 5)',
                    'writing_chapter_6': 'Chapter Writer Agent (Chapter 6)',
                    'writing_chapter_7': 'Chapter Writer Agent (Chapter 7)',
                    'writing_chapter_8': 'Chapter Writer Agent (Chapter 8)',
                    'writing_chapter_9': 'Chapter Writer Agent (Chapter 9)',
                    'review': 'Review Agent',
                    'revision': 'Revision Agent',
                    'editorial': 'Editorial Agent'
                }
                current_agent = stage_to_agent.get(workflow.current_stage, f"Agent ({workflow.current_stage})")

            # Log for debugging
            logger.info(f"Dashboard update: {workflow.current_stage}, {completed_count}/{total_stages} stages, {progress_percentage}% progress, agent: {current_agent}")

            # Completely replace project_status with workflow data
            project_status = {
                'is_running': workflow.is_running,
                'is_complete': workflow.is_complete,
                'current_agent': current_agent,
                'current_stage': workflow.current_stage,
                'completed_stages': workflow.completed_stages,
                'progress': progress_percentage,
                'thread_health': workflow.thread_health() if hasattr(workflow, 'thread_health') else None,
                'project_id': project_id,
                'status': 'running' if workflow.is_running else ('complete' if workflow.is_complete else 'stopped'),
                # Keep some original fields
                'title': project_status.get('title', ''),
                'genre': project_status.get('genre', ''),
                'target_length': project_status.get('target_length', ''),
                'complexity': project_status.get('complexity', ''),
                'created_at': project_status.get('created_at', ''),
                'last_updated': datetime.now().isoformat()
            }
        else:
            # No active workflow found, but check if there's workflow data in memory
            logger.info(f"Dashboard API: No active workflow found for {project_id}, checking memory for workflow data")
            print(f"DEBUG: No active workflow found for {project_id}, checking memory for workflow data")

            # Try to reconstruct workflow status from memory data
            try:
                # First, let's see what agents are available in memory
                memory_summary = memory.summarize_memory()
                available_agents = list(memory_summary.get('agent_memories', {}).keys())
                print(f"DEBUG: Available agents in memory: {available_agents}")
                logger.info(f"Dashboard API: Available agents in memory: {available_agents}")

                # Look for workflow status documents in memory (try multiple agents)
                workflow_status_docs = []

                # First try 'workflow' agent
                workflow_docs = memory.get_agent_memory("workflow")
                print(f"DEBUG: Found {len(workflow_docs)} documents from 'workflow' agent")
                logger.info(f"Dashboard API: Found {len(workflow_docs)} documents from 'workflow' agent")

                # Then try 'central_hub' agent (likely to have workflow status)
                hub_docs = memory.get_agent_memory("central_hub")
                print(f"DEBUG: Found {len(hub_docs)} documents from 'central_hub' agent")
                logger.info(f"Dashboard API: Found {len(hub_docs)} documents from 'central_hub' agent")

                # Combine all documents and look for workflow status
                all_docs = workflow_docs + hub_docs

                # Filter for documents that look like workflow status (contain current_stage, completed_stages, etc.)
                for doc in all_docs:
                    try:
                        doc_data = json.loads(doc['text'])
                        if 'current_stage' in doc_data or 'completed_stages' in doc_data:
                            workflow_status_docs.append(doc)
                            print(f"DEBUG: Found potential workflow status document: {doc['text'][:100]}...")
                    except (json.JSONDecodeError, KeyError):
                        continue

                print(f"DEBUG: Found {len(workflow_status_docs)} workflow status documents")
                logger.info(f"Dashboard API: Found {len(workflow_status_docs)} workflow status documents")

                if workflow_status_docs:
                    # Get the most recent workflow status
                    latest_status_doc = max(workflow_status_docs, key=lambda x: x.get('metadata', {}).get('timestamp', ''))
                    workflow_data = json.loads(latest_status_doc['text'])

                    print(f"DEBUG: Found workflow document with text: {latest_status_doc['text'][:200]}...")
                    logger.info(f"Dashboard API: Found workflow document with {len(latest_status_doc['text'])} characters")

                    logger.info(f"Dashboard API: Found workflow status in memory for {project_id}")
                    print(f"DEBUG: Found workflow status in memory: {workflow_data.get('current_stage')}")

                    # Map current stage to agent name
                    stage_to_agent = {
                        'ideation': 'Ideation Agent',
                        'research': 'Research Agent',
                        'character_development': 'Character Agent',
                        'world_building': 'World Building Agent',
                        'plot_development': 'Plot Agent',
                        'chapter_planning': 'Chapter Planner Agent',
                        'writing_chapter_1': 'Chapter Writer Agent (Chapter 1)',
                        'writing_chapter_2': 'Chapter Writer Agent (Chapter 2)',
                        'writing_chapter_3': 'Chapter Writer Agent (Chapter 3)',
                        'writing_chapter_4': 'Chapter Writer Agent (Chapter 4)',
                        'writing_chapter_5': 'Chapter Writer Agent (Chapter 5)',
                        'writing_chapter_6': 'Chapter Writer Agent (Chapter 6)',
                        'writing_chapter_7': 'Chapter Writer Agent (Chapter 7)',
                        'writing_chapter_8': 'Chapter Writer Agent (Chapter 8)',
                        'writing_chapter_9': 'Chapter Writer Agent (Chapter 9)',
                        'writing_chapter_10': 'Chapter Writer Agent (Chapter 10)',
                        'writing_chapter_11': 'Chapter Writer Agent (Chapter 11)',
                        'writing_chapter_12': 'Chapter Writer Agent (Chapter 12)',
                        'longform_expansion': 'Longform Expander',
                        'manuscript_refinement': 'Manuscript Refiner'
                    }

                    current_stage = workflow_data.get('current_stage', 'not_started')
                    completed_stages = workflow_data.get('completed_stages', [])
                    current_agent = stage_to_agent.get(current_stage, f"Agent ({current_stage})")

                    # Calculate progress based on completed stages
                    total_stages = 15  # Total number of stages in the workflow
                    completed_count = len(completed_stages)
                    progress_percentage = min(int((completed_count / total_stages) * 100), 100)

                    # Override project_status with memory workflow data
                    project_status.update({
                        'status': 'running' if workflow_data.get('is_running', False) else 'completed',
                        'current_stage': current_stage,
                        'current_agent': current_agent,
                        'progress': progress_percentage,
                        'is_running': workflow_data.get('is_running', False),
                        'is_complete': workflow_data.get('is_complete', False),
                        'completed_stages': completed_stages,
                        'thread_health': True,  # Assume healthy since we found data
                        'last_updated': datetime.now().isoformat()
                    })

                    logger.info(f"Dashboard API: Reconstructed workflow status from memory - Stage: {current_stage}, Progress: {progress_percentage}%")
                    print(f"DEBUG: Reconstructed workflow status - Stage: {current_stage}, Progress: {progress_percentage}%")
                else:
                    logger.info(f"Dashboard API: No workflow status found in memory for {project_id}")
                    print(f"DEBUG: No workflow status found in memory for {project_id}")

                    # Fallback to hub status if no workflow status in memory
                    try:
                        hub_status = hub.get_project_status()
                        if hub_status:
                            project_status.update(hub_status)
                    except Exception as e:
                        logger.warning(f"Error getting hub status: {str(e)}")

            except Exception as e:
                logger.error(f"Dashboard API: Error reconstructing workflow status from memory: {str(e)}")
                print(f"DEBUG: Error reconstructing workflow status from memory: {str(e)}")

                # Fallback to hub status if memory reconstruction fails
                try:
                    hub_status = hub.get_project_status()
                    if hub_status:
                        project_status.update(hub_status)
                except Exception as e:
                    logger.warning(f"Error getting hub status: {str(e)}")

        # Try to get ideas, handle if method doesn't exist
        try:
            ideas = hub.get_top_ideas(3)
        except (AttributeError, Exception) as e:
            logger.warning(f"Error getting ideas: {str(e)}")
            ideas = []
        
        # Assemble dashboard data
        dashboard_data = {
            "project_id": project_id,
            "status": project_status,
            "timeline": timeline,
            "ideas": ideas,
        }
        
        return jsonify(dashboard_data)
    except Exception as e:
        logger.error(f"Error getting dashboard data: {str(e)}")
        return jsonify({
            "project_id": project_id,
            "status": {
                "status": "not_started",
                "current_stage": "not_started",
                "progress": 0,
                "completed_stages": []
            },
            "timeline": [],
            "ideas": []
        })

# API endpoint to check workflow state
@app.route('/api/project/<project_id>/debug', methods=['GET'])
def debug_workflow(project_id):
    """Debug endpoint to check workflow state."""
    if project_id not in active_workflows:
        logger.warning(f"Debug requested for non-existent project {project_id}")
        return jsonify({'error': 'Project not found'}), 404
    
    workflow = active_workflows[project_id]
    
    try:
        # Collect detailed information about the workflow
        debug_info = {
            'project_id': project_id,
            'workflow_state': {
                'is_running': workflow.is_running,
                'is_complete': workflow.is_complete,
                'is_thread_alive': workflow.thread and workflow.thread.is_alive(),
                'current_stage': workflow.current_stage,
                'completed_stages': workflow.completed_stages,
                'progress': workflow.get_progress(),
                'start_time': workflow.start_time,
                'last_progress_time': workflow.last_progress_time
            },
            'memory_status': {
                'memory_path': f"memory_data/{project_id}/memory.pkl",
                'memory_exists': os.path.exists(f"memory_data/{project_id}/memory.pkl")
            },
            'errors': workflow.errors,
            'agents': list(workflow.agents.keys()),
            'embedding_model_status': {
                'model': workflow.embedding_model,
                'openai_available': get_openai_client().is_available(),
                'available_models': get_openai_client().get_available_models()
            }
        }
        
        return jsonify(debug_info)
    except Exception as e:
        logger.error(f"Error debugging workflow: {e}")
        return jsonify({
            'error': f"Failed to debug workflow: {e}",
            'traceback': traceback.format_exc()
        }), 500

# API endpoint to get project logs
@app.route('/api/project/<project_id>/logs', methods=['GET'])
def get_project_logs(project_id):
    """API endpoint to get the latest logs for a project."""
    try:
        # Convert log buffer to a list of formatted strings
        all_logs = list(log_buffer)
        # Filter logs that contain the project ID or are general system logs
        project_logs = [log for log in all_logs if project_id in str(log['message']) or log['module'] == '__main__']
        return jsonify({"logs": project_logs})
    except Exception as e:
        logger.error(f"Error getting logs: {str(e)}")
        return jsonify({"error": str(e)}), 500

# SSE endpoint for streaming logs
@app.route('/api/stream-logs/<project_id>', methods=['GET'])
def stream_logs(project_id):
    """Server-Sent Events endpoint for streaming logs."""
    def stream_generate():
        # Stream logs with SSE format
        last_sent_idx = 0
        while True:
            if len(log_buffer) > last_sent_idx:
                for i in range(last_sent_idx, len(log_buffer)):
                    log = log_buffer[i]
                    # Only send logs related to this project
                    if project_id in str(log['message']) or log['module'] == '__main__':
                        log_str = f"{log['timestamp']} - {log['module']} - {log['level']} - {log['message']}"
                        yield f"data: {json.dumps({'log': log_str})}\n\n"
                last_sent_idx = len(log_buffer)
            yield f"data: {json.dumps({'keepalive': True})}\n\n"
            import time
            time.sleep(1)
    
    response = app.response_class(
        stream_generate(),
        mimetype='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'Connection': 'keep-alive'}
    )
    return response

# Add new manuscript refinement API endpoint
@app.route("/api/refine", methods=["POST"])
def trigger_refinement():
    """API endpoint to trigger manuscript refinement."""
    try:
        # Get request data
        data = request.json
        project_id = data.get("project_id")
        
        if not project_id:
            return jsonify({"error": "project_id is required"}), 400
            
        # Initialize components
        from memory.dynamic_memory import DynamicMemory
        from agents.manuscript_refiner import ManuscriptRefiner
        from models.openai_client import get_openai_client
        
        # Initialize memory with embedding function using OpenAI
        openai_client = get_openai_client()
        embedding_function = lambda text: openai_client.get_embeddings(text, model=EMBEDDING_MODEL)
        memory = DynamicMemory(project_id, embedding_function)
        
        # Initialize manuscript refiner
        refiner = ManuscriptRefiner(
            project_id=project_id,
            memory=memory,
            model_name="gpt-4o"  # Use OpenAI model
        )
        
        # Start refinement
        result = refiner.refine_manuscript(
            target_chapters=data.get("chapters"),
            overwrite=data.get("overwrite", True),
            style=data.get("style", "literary"),
            max_chunks=data.get("max_chunks", 5)
        )
        
        logger.info(f"Refinement complete for project {project_id}: {result['refined_count']} chapters refined")
        
        return jsonify({
            "status": "refinement complete", 
            "result": result
        })
        
    except Exception as e:
        logger.error(f"Error in refinement: {str(e)}", exc_info=True)
        return jsonify({
            "status": "error",
            "error": str(e),
            "details": traceback.format_exc()
        }), 500

# Generate manuscript endpoint
@app.route('/generate', methods=['GET', 'POST'])
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
            openai_client = get_openai_client()
            embedding_function = lambda text: openai_client.get_embeddings(text, model=EMBEDDING_MODEL)
            memory = DynamicMemory(project_id, embedding_function)
            hub = CentralHub(project_id, memory)
            
            # Store initial status
            hub.update_project_status(status)
            
            # Initialize process for manuscript generation
            if celery_enabled and run_workflow_task:
                # Run asynchronously using Celery
                logger.info(f"Starting async workflow for project {project_id}")
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
                # Fall back to direct execution in a thread
                logger.info(f"Starting threaded workflow for project {project_id}")
                workflow = ManuscriptWorkflow(**config)
                active_workflows[project_id] = workflow
                print(f"DEBUG: Stored workflow in active_workflows for {project_id}, keys now: {list(active_workflows.keys())}")
                logger.info(f"Stored workflow in active_workflows for {project_id}, keys now: {list(active_workflows.keys())}")
                workflow.start()
                flash('Starting manuscript generation in a background thread')
            
            return redirect(url_for('dashboard', project_id=project_id))
            
        except Exception as e:
            logger.error(f"Error starting generation: {str(e)}", exc_info=True)
            flash(f'Error starting generation: {str(e)}', 'error')
            return redirect(url_for('home'))
    
    # GET method - render the form
    return render_template('generate.html')

# API endpoint to reset a stalled or dead workflow thread
@app.route('/api/project/<project_id>/reset-thread', methods=['POST'])
def reset_thread(project_id):
    """Reset a stalled or dead workflow thread."""
    try:
        if project_id in active_workflows:
            workflow = active_workflows[project_id]
            
            # Check if the workflow is still running but the thread is dead
            if workflow.is_running and not workflow.thread_health():
                # Start a new thread
                workflow.thread = None
                workflow.start()
                logger.info(f"Reset workflow thread for project {project_id}")
                
                return jsonify({
                    "success": True,
                    "message": "Thread reset successfully"
                })
            else:
                # If the workflow is not running or the thread is healthy
                return jsonify({
                    "success": False,
                    "error": "Thread is not eligible for reset"
                })
        else:
            # Try to get a new instance from memory
            from orchestration.workflow import ManuscriptWorkflow
            from memory.dynamic_memory import DynamicMemory
            from models.openai_client import get_openai_client
            
            try:
                # Initialize memory with embedding function using OpenAI
                openai_client = get_openai_client()
                embedding_function = lambda text: openai_client.get_embeddings(text, model=EMBEDDING_MODEL)
                memory = DynamicMemory(project_id, embedding_function)
                
                # Create new workflow instance
                workflow = ManuscriptWorkflow(
                    project_id=project_id,
                    title="",
                    genre="",
                    target_length="medium",
                    complexity="medium",
                    embedding_model=EMBEDDING_MODEL,
                    use_openai=True,
                    use_gpu=False,
                    initial_prompt=""
                )
                
                # Store in active workflows
                active_workflows[project_id] = workflow
                
                # Start the workflow
                workflow.start()
                logger.info(f"Created and started new workflow for project {project_id}")
                
                return jsonify({
                    "success": True,
                    "message": "New workflow thread created and started"
                })
            except Exception as e:
                logger.error(f"Error creating new workflow: {e}")
                return jsonify({
                    "success": False,
                    "error": f"Failed to create new workflow: {str(e)}"
                })
    except Exception as e:
        logger.error(f"Error resetting thread: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        })

# Add after the generate function

@app.route('/project-status/<project_id>')
def project_status(project_id):
    """Show status of a project without using the dashboard."""
    try:
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
            project_logs = [log for log in log_buffer if project_id in str(log['message'])]
            log_entries = [f"{log['timestamp']} - {log['level']} - {log['message']}" for log in project_logs]
            
            # Render a simple status page
            return f"""
            <html>
            <head>
                <title>Project Status</title>
                <style>
                    body {{ font-family: Arial, sans-serif; max-width: 1000px; margin: 0 auto; padding: 20px; }}
                    .container {{ border: 1px solid #ddd; padding: 20px; border-radius: 5px; margin-bottom: 20px; }}
                    pre {{ background-color: #f5f5f5; padding: 10px; border-radius: 5px; overflow-x: auto; }}
                    .logs {{ max-height: 400px; overflow-y: auto; }}
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
                    
                    <p>This page will refresh automatically every 10 seconds.</p>
                    <p>
                        <a href="/view-generated-text/{project_id}">View All Generated Text</a> | 
                        <a href="/generate">Start New Project</a> | 
                        <a href="/">Home</a>
                    </p>
                    {f'<p><a href="/view-manuscript/{project_id}">View Full Manuscript</a></p>' if status['is_complete'] else ''}
                </div>
            </body>
            </html>
            """
        else:
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
    except Exception as e:
        logger.error(f"Error displaying project status: {str(e)}", exc_info=True)
        return f"""
        <html>
        <head>
            <title>Error</title>
            <style>
                body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }}
                .container {{ border: 1px solid #ddd; padding: 20px; border-radius: 5px; }}
                .error {{ color: red; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Error Displaying Project Status</h1>
                <p class="error">{str(e)}</p>
                <pre>{traceback.format_exc()}</pre>
                <p><a href="/view-generated-text/{project_id}">View Generated Text</a> | <a href="/generate">Start New Project</a> | <a href="/">Home</a></p>
            </div>
        </body>
        </html>
        """

# Add API endpoint to view the manuscript
@app.route('/api/manuscript/<project_id>', methods=['GET'])
def get_manuscript(project_id):
    """Retrieve the manuscript for a given project."""
    try:
        # Try to get the workflow from active workflows
        if project_id in active_workflows:
            workflow = active_workflows[project_id]
            
            # Check if the workflow is complete
            if not workflow.is_complete:
                return jsonify({
                    "success": False,
                    "error": "Manuscript generation is still in progress",
                    "status": workflow.current_stage,
                    "progress": workflow.get_progress()
                }), 400
            
            # Get the manuscript
            manuscript = workflow.get_final_manuscript()
            if not manuscript:
                return jsonify({
                    "success": False,
                    "error": "Manuscript not found or not yet generated"
                }), 404
            
            # Return the manuscript
            return jsonify({
                "success": True,
                "title": manuscript.get("title", "Untitled"),
                "chapters": manuscript.get("chapters", []),
                "word_count": manuscript.get("word_count", 0),
                "content": manuscript.get("content", "")
            })
        
        # If not in active workflows, try to retrieve from memory
        from memory.dynamic_memory import DynamicMemory
        from models.openai_client import get_openai_client
        
        # Initialize memory with embedding function using OpenAI
        openai_client = get_openai_client()
        embedding_function = lambda text: openai_client.get_embeddings(text, model=EMBEDDING_MODEL)
        memory = DynamicMemory(project_id, embedding_function)
        
        # Query memory for manuscript using multiple approaches
        manuscript_docs = []

        # Try different search queries
        search_queries = [
            "type:manuscript",
            "type:final_manuscript",
            "manuscript",
            "chapter",
            "content"
        ]

        for query in search_queries:
            docs = memory.query_memory(query, top_k=5)
            if docs:
                manuscript_docs.extend(docs)
                break  # Stop at first successful query

        # If still not found, try getting documents from chapter_writer_agent
        if not manuscript_docs:
            chapter_docs = memory.get_agent_memory("chapter_writer_agent")
            if chapter_docs:
                manuscript_docs = chapter_docs

        # If still not found, try getting all documents and filter
        if not manuscript_docs:
            all_docs = memory.get_all_documents()
            # Look for documents that might contain manuscript content
            for doc in all_docs:
                text = doc.get('text', '')
                if len(text) > 1000:  # Assume manuscript content is substantial
                    try:
                        # Try to parse as JSON to see if it contains chapters or content
                        json_data = json.loads(text)
                        if ('chapters' in json_data or 'content' in json_data or
                            'title' in json_data or 'manuscript' in text.lower()):
                            manuscript_docs.append(doc)
                    except json.JSONDecodeError:
                        # If it's not JSON but substantial text, it might be manuscript content
                        if 'chapter' in text.lower() or len(text) > 5000:
                            manuscript_docs.append(doc)

        if not manuscript_docs:
            return jsonify({
                "success": False,
                "error": "Manuscript not found in memory"
            }), 404
        
        # Parse the manuscript data - try to find the best document or combine them
        manuscript_data = None
        combined_content = ""
        combined_chapters = []
        title = "Untitled"

        # Look for a complete manuscript first
        for doc in manuscript_docs:
            try:
                json_data = json.loads(doc['text'])
                if 'chapters' in json_data and len(json_data['chapters']) > 1:
                    # This looks like a complete manuscript
                    manuscript_data = json_data
                    break
                elif 'content' in json_data and len(json_data['content']) > 1000:
                    # This looks like substantial content
                    manuscript_data = json_data
                    break
            except json.JSONDecodeError:
                # Not JSON, check if it's substantial text content
                if len(doc['text']) > 5000:
                    manuscript_data = {
                        "content": doc['text'],
                        "title": "Untitled",
                        "chapters": [],
                        "word_count": len(doc['text'].split())
                    }
                    break

        # If no complete manuscript found, try to combine chapter documents
        if not manuscript_data:
            for doc in manuscript_docs:
                try:
                    json_data = json.loads(doc['text'])
                    if 'title' in json_data and not title or title == "Untitled":
                        title = json_data.get('title', 'Untitled')

                    if 'content' in json_data:
                        combined_content += json_data['content'] + "\n\n"

                    if 'chapters' in json_data:
                        combined_chapters.extend(json_data['chapters'])

                except json.JSONDecodeError:
                    # Raw text content
                    combined_content += doc['text'] + "\n\n"

            if combined_content or combined_chapters:
                manuscript_data = {
                    "title": title,
                    "content": combined_content.strip(),
                    "chapters": combined_chapters,
                    "word_count": len(combined_content.split()) if combined_content else 0
                }

        if not manuscript_data:
            return jsonify({
                "success": False,
                "error": "Could not parse manuscript data"
            }), 404

        # Return the manuscript
        return jsonify({
            "success": True,
            "title": manuscript_data.get("title", "Untitled"),
            "chapters": manuscript_data.get("chapters", []),
            "word_count": manuscript_data.get("word_count", 0),
            "content": manuscript_data.get("content", "")
        })
        
    except Exception as e:
        logger.error(f"Error retrieving manuscript: {str(e)}", exc_info=True)
        return jsonify({
            "success": False, 
            "error": str(e)
        }), 500

# Add a route to download the manuscript as a file
@app.route('/api/project/<project_id>/manuscript/download', methods=['GET'])
def download_manuscript(project_id):
    """Download the manuscript as a text file."""
    try:
        # Get the manuscript data using the existing endpoint logic
        from memory.dynamic_memory import DynamicMemory
        from models.openai_client import get_openai_client

        # Initialize memory with embedding function using OpenAI
        openai_client = get_openai_client()
        embedding_function = lambda text: openai_client.get_embeddings(text, model=EMBEDDING_MODEL)
        memory = DynamicMemory(project_id, embedding_function)

        # Query memory for manuscript using multiple approaches
        manuscript_docs = []

        # Try different search queries
        search_queries = [
            "type:manuscript",
            "type:final_manuscript",
            "manuscript",
            "chapter",
            "content"
        ]

        for query in search_queries:
            docs = memory.query_memory(query, top_k=5)
            if docs:
                manuscript_docs.extend(docs)
                break  # Stop at first successful query

        # If still not found, try getting documents from chapter_writer_agent
        if not manuscript_docs:
            chapter_docs = memory.get_agent_memory("chapter_writer_agent")
            if chapter_docs:
                manuscript_docs = chapter_docs

        if not manuscript_docs:
            return jsonify({
                "success": False,
                "error": "Manuscript not found in memory"
            }), 404

        # Parse the manuscript data - try to find the best document or combine them
        manuscript_data = None
        combined_content = ""
        title = "Untitled"

        # Look for a complete manuscript first
        for doc in manuscript_docs:
            try:
                json_data = json.loads(doc['text'])
                if 'chapters' in json_data and len(json_data['chapters']) > 1:
                    # This looks like a complete manuscript
                    manuscript_data = json_data
                    break
                elif 'content' in json_data and len(json_data['content']) > 1000:
                    # This looks like substantial content
                    manuscript_data = json_data
                    break
            except json.JSONDecodeError:
                # Not JSON, check if it's substantial text content
                if len(doc['text']) > 5000:
                    manuscript_data = {
                        "content": doc['text'],
                        "title": "Untitled",
                        "chapters": [],
                        "word_count": len(doc['text'].split())
                    }
                    break

        # If no complete manuscript found, try to combine chapter documents
        if not manuscript_data:
            for doc in manuscript_docs:
                try:
                    json_data = json.loads(doc['text'])
                    if 'title' in json_data and (not title or title == "Untitled"):
                        title = json_data.get('title', 'Untitled')

                    if 'content' in json_data:
                        combined_content += json_data['content'] + "\n\n"

                except json.JSONDecodeError:
                    # Raw text content
                    combined_content += doc['text'] + "\n\n"

            if combined_content:
                manuscript_data = {
                    "title": title,
                    "content": combined_content.strip(),
                    "chapters": [],
                    "word_count": len(combined_content.split()) if combined_content else 0
                }

        if not manuscript_data:
            return jsonify({
                "success": False,
                "error": "Could not parse manuscript data"
            }), 404

        # Create the file content
        title = manuscript_data.get("title", "Untitled")
        content = manuscript_data.get("content", "")
        word_count = manuscript_data.get("word_count", 0)

        # Format the manuscript for download
        file_content = f"{title}\n"
        file_content += "=" * len(title) + "\n\n"
        file_content += f"Word Count: {word_count}\n"
        file_content += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        file_content += content

        # Create response with file download
        from flask import make_response
        response = make_response(file_content)
        response.headers['Content-Type'] = 'text/plain; charset=utf-8'
        response.headers['Content-Disposition'] = f'attachment; filename="{title.replace(" ", "_")}.txt"'

        return response

    except Exception as e:
        logger.error(f"Error downloading manuscript: {str(e)}", exc_info=True)
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

# Add a debug route to inspect memory contents
@app.route('/api/debug/memory/<project_id>', methods=['GET'])
def debug_memory(project_id):
    """Debug endpoint to inspect memory contents."""
    try:
        from memory.dynamic_memory import DynamicMemory
        from models.openai_client import get_openai_client

        # Initialize memory
        openai_client = get_openai_client()
        embedding_function = lambda text: openai_client.get_embeddings(text, model=EMBEDDING_MODEL)
        memory = DynamicMemory(project_id, embedding_function)

        # Get memory summary
        summary = memory.summarize_memory()

        # Get documents by agent
        agent_data = {}
        for agent_name in summary.get('agent_memories', {}):
            agent_docs = memory.get_agent_memory(agent_name)
            agent_data[agent_name] = {
                'count': len(agent_docs),
                'documents': []
            }

            # Get first few documents for inspection
            for i, doc in enumerate(agent_docs[:3]):  # Only first 3 docs per agent
                doc_preview = {
                    'text_preview': doc['text'][:200] + '...' if len(doc['text']) > 200 else doc['text'],
                    'metadata': doc.get('metadata', {}),
                    'text_length': len(doc['text'])
                }
                agent_data[agent_name]['documents'].append(doc_preview)

        return jsonify({
            "success": True,
            "project_id": project_id,
            "summary": summary,
            "agent_data": agent_data
        })

    except Exception as e:
        logger.error(f"Error debugging memory: {str(e)}", exc_info=True)
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

# Add a test route to verify chapter writer data access
@app.route('/api/test/chapter-writer-data/<project_id>', methods=['GET'])
def test_chapter_writer_data(project_id):
    """Test endpoint to verify chapter writer can access previous agents' data."""
    try:
        from memory.dynamic_memory import DynamicMemory
        from models.openai_client import get_openai_client
        from agents.chapter_writer_agent import ChapterWriterAgent

        # Initialize memory
        openai_client = get_openai_client()
        embedding_function = lambda text: openai_client.get_embeddings(text, model=EMBEDDING_MODEL)
        memory = DynamicMemory(project_id, embedding_function)

        # Initialize chapter writer
        chapter_writer = ChapterWriterAgent(project_id, memory, use_openai=True)

        # Test data access
        integrated_data = chapter_writer._get_integrated_data()

        return jsonify({
            "success": True,
            "project_id": project_id,
            "integrated_data_keys": list(integrated_data.keys()),
            "data_summary": {
                "selected_idea": {
                    "title": integrated_data.get("selected_idea", {}).get("title", "Not found"),
                    "genre": integrated_data.get("selected_idea", {}).get("genre", "Not found")
                } if "selected_idea" in integrated_data else "Not found",
                "characters": [
                    {"name": char.get("name"), "role": char.get("role")}
                    for char in integrated_data.get("characters", [])
                ] if "characters" in integrated_data else "Not found",
                "world_building": {
                    "primary_setting": integrated_data.get("world_building", {}).get("primary_setting", "Not found"),
                    "world_type": integrated_data.get("world_building", {}).get("world_type", "Not found")
                } if "world_building" in integrated_data else "Not found",
                "plot": {
                    "chapter_count": len(integrated_data.get("plot", {}).get("chapters", [])),
                    "first_chapter_title": integrated_data.get("plot", {}).get("chapters", [{}])[0].get("title", "Not found") if integrated_data.get("plot", {}).get("chapters") else "Not found"
                } if "plot" in integrated_data else "Not found",
                "research": {
                    "topic_count": len(integrated_data.get("research", [])),
                    "first_topic": integrated_data.get("research", [{}])[0].get("name", "Not found") if integrated_data.get("research") else "Not found"
                } if "research" in integrated_data else "Not found"
            }
        })

    except Exception as e:
        logger.error(f"Error testing chapter writer data access: {str(e)}", exc_info=True)
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

# Add a route to regenerate a single chapter with proper data
@app.route('/api/regenerate-chapter/<project_id>/<int:chapter_number>', methods=['POST'])
def regenerate_chapter(project_id, chapter_number):
    """Regenerate a single chapter with proper data access."""
    try:
        from memory.dynamic_memory import DynamicMemory
        from models.openai_client import get_openai_client
        from agents.chapter_writer_agent import ChapterWriterAgent

        # Initialize memory
        openai_client = get_openai_client()
        embedding_function = lambda text: openai_client.get_embeddings(text, model=EMBEDDING_MODEL)
        memory = DynamicMemory(project_id, embedding_function)

        # Initialize chapter writer
        chapter_writer = ChapterWriterAgent(project_id, memory, use_openai=True)

        # Get integrated data
        integrated_data = chapter_writer._get_integrated_data()

        # Get the chapter plan from plot data
        plot_data = integrated_data.get("plot", {})
        chapters = plot_data.get("chapters", [])

        if not chapters or chapter_number < 1 or chapter_number > len(chapters):
            return jsonify({
                "success": False,
                "error": f"Chapter {chapter_number} not found in plot. Available chapters: 1-{len(chapters)}"
            }), 404

        # Get the specific chapter plan
        chapter_plan = chapters[chapter_number - 1]  # 0-indexed

        # Write the chapter
        logger.info(f"Regenerating chapter {chapter_number} with proper data access")
        chapter_result = chapter_writer.write_chapter(chapter_plan)

        return jsonify({
            "success": True,
            "project_id": project_id,
            "chapter_number": chapter_number,
            "chapter": chapter_result,
            "integrated_data_used": {
                "idea_title": integrated_data.get("selected_idea", {}).get("title", "None"),
                "character_count": len(integrated_data.get("characters", [])),
                "world_setting": integrated_data.get("world_building", {}).get("primary_setting", "None"),
                "plot_chapters": len(chapters)
            }
        })

    except Exception as e:
        logger.error(f"Error regenerating chapter: {str(e)}", exc_info=True)
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

# Add a route to view the complete plot outline
@app.route('/api/plot-outline/<project_id>', methods=['GET'])
def get_plot_outline(project_id):
    """Get the complete plot outline created by the plot agent."""
    try:
        from memory.dynamic_memory import DynamicMemory
        from models.openai_client import get_openai_client
        from agents.chapter_writer_agent import ChapterWriterAgent

        # Initialize memory
        openai_client = get_openai_client()
        embedding_function = lambda text: openai_client.get_embeddings(text, model=EMBEDDING_MODEL)
        memory = DynamicMemory(project_id, embedding_function)

        # Initialize chapter writer to access integrated data
        chapter_writer = ChapterWriterAgent(project_id, memory, use_openai=True)

        # Get integrated data which includes the plot
        integrated_data = chapter_writer._get_integrated_data()

        # Extract plot information
        plot_data = integrated_data.get("plot", {})

        if not plot_data:
            return jsonify({
                "success": False,
                "error": "No plot data found"
            }), 404

        # Format the plot outline nicely
        chapters = plot_data.get("chapters", [])

        return jsonify({
            "success": True,
            "project_id": project_id,
            "plot_overview": {
                "total_chapters": len(chapters),
                "story_arc": plot_data.get("story_arc", "Not specified"),
                "themes": plot_data.get("themes", []),
                "genre": integrated_data.get("genre", "Unknown")
            },
            "chapters": chapters,
            "story_context": {
                "title": integrated_data.get("title", "Unknown"),
                "main_character": integrated_data.get("characters", [{}])[0].get("name", "Unknown") if integrated_data.get("characters") else "Unknown",
                "setting": integrated_data.get("world_building", {}).get("primary_setting", "Unknown")
            }
        })

    except Exception as e:
        logger.error(f"Error getting plot outline: {str(e)}", exc_info=True)
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

# Add a route to show the enhanced workflow stages
@app.route('/api/enhanced-workflow-info', methods=['GET'])
def get_enhanced_workflow_info():
    """Get information about the enhanced workflow for long novels."""
    try:
        workflow_info = {
            "enhanced_workflow": {
                "description": "Full pipeline for professional novel generation",
                "stages": [
                    {
                        "stage": 1,
                        "name": "Ideation",
                        "description": "Generate and select story ideas",
                        "agent": "ideation_agent",
                        "output": "Selected story concept with themes and genre"
                    },
                    {
                        "stage": 2,
                        "name": "Research",
                        "description": "Research relevant topics for authenticity",
                        "agent": "research_agent",
                        "output": "Research topics and insights"
                    },
                    {
                        "stage": 3,
                        "name": "Character Development",
                        "description": "Create detailed character profiles",
                        "agent": "character_agent",
                        "output": "Character profiles with personalities and backgrounds"
                    },
                    {
                        "stage": 4,
                        "name": "World Building",
                        "description": "Develop story settings and world details",
                        "agent": "world_building_agent",
                        "output": "Detailed world settings and locations"
                    },
                    {
                        "stage": 5,
                        "name": "Plot Development",
                        "description": "Create chapter-by-chapter plot outline",
                        "agent": "plot_agent",
                        "output": "Complete plot structure with chapter summaries"
                    },
                    {
                        "stage": 6,
                        "name": "Chapter Planning",
                        "description": "Plan individual chapter details",
                        "agent": "chapter_planner_agent",
                        "output": "Detailed chapter plans and goals"
                    },
                    {
                        "stage": 7,
                        "name": "Chapter Writing",
                        "description": "Write initial chapter drafts",
                        "agent": "chapter_writer_agent",
                        "output": "Initial chapter content (1000-2000 words each)"
                    },
                    {
                        "stage": 8,
                        "name": "Longform Expansion",
                        "description": "Expand and enrich chapter content",
                        "agent": "longform_expander",
                        "output": "Expanded chapters with richer prose and dialogue"
                    },
                    {
                        "stage": 9,
                        "name": "Editorial Review",
                        "description": "Professional editorial review for continuity",
                        "agent": "editorial_agent",
                        "output": "Professionally edited chapters with consistency"
                    },
                    {
                        "stage": 10,
                        "name": "Manuscript Assembly",
                        "description": "Assemble final manuscript with front/back matter",
                        "agent": "manuscript_agent",
                        "output": "Complete, publication-ready manuscript"
                    }
                ]
            },
            "long_novel_features": {
                "memory_continuity": "Semantic search across all content for character/plot consistency",
                "content_expansion": "Progressive expansion from 1000 to 2500+ words per chapter",
                "editorial_oversight": "Professional editing for style, grammar, and continuity",
                "integrated_data": "All agents share data for cohesive storytelling",
                "professional_formatting": "Front matter, table of contents, back matter included"
            },
            "quality_improvements": [
                "Anti-cliché prompting to avoid AI writing patterns",
                "Character voice consistency across chapters",
                "Plot thread continuity tracking",
                "Professional manuscript formatting",
                "Rich sensory details and dialogue enhancement",
                "Thematic consistency throughout the novel"
            ]
        }

        return jsonify({
            "success": True,
            "workflow_info": workflow_info
        })

    except Exception as e:
        logger.error(f"Error getting enhanced workflow info: {str(e)}", exc_info=True)
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

def get_manuscript_data(project_id):
    """Helper function to get manuscript data from memory or active workflows."""
    try:
        # Try to get from active workflows first
        if project_id in active_workflows:
            workflow = active_workflows[project_id]
            if workflow.is_complete:
                manuscript = workflow.get_final_manuscript()
                if manuscript and manuscript.get('chapters'):
                    return {
                        "success": True,
                        "chapters": manuscript.get('chapters', []),
                        "word_count": manuscript.get('word_count', 0),
                        "title": manuscript.get('title', 'Digital Requiem')
                    }

        # If not found in active workflows, try memory
        from memory.dynamic_memory import DynamicMemory
        from models.openai_client import get_openai_client

        # Initialize memory with embedding function using OpenAI
        openai_client = get_openai_client()
        embedding_function = lambda text: openai_client.get_embeddings(text, model=EMBEDDING_MODEL)
        memory = DynamicMemory(project_id, embedding_function)

        # Query memory for manuscript
        manuscript_docs = memory.query_memory("type:manuscript", top_k=1)

        # If not found, try with final_manuscript type
        if not manuscript_docs or len(manuscript_docs) == 0:
            manuscript_docs = memory.query_memory("type:final_manuscript", top_k=1)

        if manuscript_docs and len(manuscript_docs) > 0:
            try:
                manuscript = json.loads(manuscript_docs[0]['text'])
                return {
                    "success": True,
                    "chapters": manuscript.get('chapters', []),
                    "word_count": manuscript.get('word_count', 0),
                    "title": manuscript.get('title', 'Digital Requiem')
                }
            except json.JSONDecodeError:
                # If not JSON, try to parse as simple content
                content = manuscript_docs[0]['text']
                return {
                    "success": True,
                    "chapters": [{"title": "Complete Manuscript", "content": content, "word_count": len(content.split())}],
                    "word_count": len(content.split()),
                    "title": "Digital Requiem"
                }

        return {
            "success": False,
            "error": "No manuscript found for this project"
        }

    except Exception as e:
        logger.error(f"Error getting manuscript data: {str(e)}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }

# Add a route to download the manuscript as a file
@app.route('/api/download-manuscript/<project_id>')
def download_manuscript_file(project_id):
    """Download the complete manuscript as a text file."""
    try:
        # Get the manuscript data
        manuscript_data = get_manuscript_data(project_id)

        if not manuscript_data.get('success'):
            return jsonify({
                "success": False,
                "error": manuscript_data.get('error', 'Failed to get manuscript data')
            }), 404

        chapters = manuscript_data.get('chapters', [])
        total_words = manuscript_data.get('word_count', 0)

        if not chapters:
            return jsonify({
                "success": False,
                "error": "No chapters found for this project"
            }), 404

        # Create the manuscript content
        manuscript_content = []
        manuscript_content.append("=" * 60)
        manuscript_content.append("DIGITAL REQUIEM")
        manuscript_content.append("Generated by NovelNexus Enhanced Workflow")
        manuscript_content.append("=" * 60)
        manuscript_content.append("")
        manuscript_content.append(f"Total Chapters: {len(chapters)}")
        manuscript_content.append(f"Total Words: {total_words}")
        manuscript_content.append("")
        manuscript_content.append("=" * 60)
        manuscript_content.append("")

        # Add each chapter
        for i, chapter in enumerate(chapters, 1):
            title = chapter.get('title', f'Chapter {i}')
            content = chapter.get('content', '')
            word_count = chapter.get('word_count', 0)

            manuscript_content.append(f"CHAPTER {i}: {title.upper()}")
            manuscript_content.append(f"Word Count: {word_count}")
            manuscript_content.append("-" * 40)
            manuscript_content.append("")
            manuscript_content.append(content)
            manuscript_content.append("")
            manuscript_content.append("=" * 60)
            manuscript_content.append("")

        # Join all content
        full_manuscript = "\n".join(manuscript_content)

        # Create response with file download
        from flask import Response

        response = Response(
            full_manuscript,
            mimetype='text/plain',
            headers={
                'Content-Disposition': f'attachment; filename=digital_requiem_{project_id[:8]}.txt'
            }
        )

        return response

    except Exception as e:
        logger.error(f"Error downloading manuscript: {str(e)}", exc_info=True)
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

# Add a route to save manuscript to local file
@app.route('/api/save-manuscript/<project_id>')
def save_manuscript_file(project_id):
    """Save the complete manuscript to a local file."""
    try:
        # Get the manuscript data
        manuscript_data = get_manuscript_data(project_id)

        if not manuscript_data.get('success'):
            return jsonify({
                "success": False,
                "error": manuscript_data.get('error', 'Failed to get manuscript data')
            })

        chapters = manuscript_data.get('chapters', [])
        total_words = manuscript_data.get('word_count', 0)

        if not chapters:
            return jsonify({
                "success": False,
                "error": "No chapters found for this project"
            })

        # Create the manuscript content
        manuscript_content = []
        manuscript_content.append("=" * 60)
        manuscript_content.append("DIGITAL REQUIEM")
        manuscript_content.append("Generated by NovelNexus Enhanced Workflow")
        manuscript_content.append("=" * 60)
        manuscript_content.append("")
        manuscript_content.append(f"Total Chapters: {len(chapters)}")
        manuscript_content.append(f"Total Words: {total_words}")
        manuscript_content.append(f"Project ID: {project_id}")
        manuscript_content.append("")
        manuscript_content.append("=" * 60)
        manuscript_content.append("")

        # Add each chapter
        for i, chapter in enumerate(chapters, 1):
            title = chapter.get('title', f'Chapter {i}')
            content = chapter.get('content', '')
            word_count = chapter.get('word_count', 0)

            manuscript_content.append(f"CHAPTER {i}: {title.upper()}")
            manuscript_content.append(f"Word Count: {word_count}")
            manuscript_content.append("-" * 40)
            manuscript_content.append("")
            manuscript_content.append(content)
            manuscript_content.append("")
            manuscript_content.append("=" * 60)
            manuscript_content.append("")

        # Join all content
        full_manuscript = "\n".join(manuscript_content)

        # Save to file
        import os
        filename = f"digital_requiem_{project_id[:8]}.txt"
        filepath = os.path.join(os.getcwd(), filename)

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(full_manuscript)

        return jsonify({
            "success": True,
            "message": f"Manuscript saved successfully",
            "filename": filename,
            "filepath": filepath,
            "word_count": total_words,
            "chapter_count": len(chapters)
        })

    except Exception as e:
        logger.error(f"Error saving manuscript to file: {str(e)}", exc_info=True)
        return jsonify({
            "success": False,
            "error": str(e)
        })

# Add a route to view the manuscript in a nice format
@app.route('/view-manuscript/<project_id>')
def view_manuscript(project_id):
    """View the manuscript in a nice format."""
    try:
        # Try to get the workflow from active workflows
        manuscript = None
        title = "Untitled"
        
        if project_id in active_workflows:
            workflow = active_workflows[project_id]
            
            # Check if the workflow is complete
            if not workflow.is_complete:
                return f"""
                <html>
                <head>
                    <title>Manuscript Not Ready</title>
                    <style>
                        body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }}
                        .container {{ border: 1px solid #ddd; padding: 20px; border-radius: 5px; }}
                    </style>
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
            
            # Get the manuscript
            manuscript = workflow.get_final_manuscript()
            if manuscript:
                title = manuscript.get("title", "Untitled")
        
        # If not found in active workflows or no manuscript, try to retrieve from memory
        if not manuscript:
            from memory.dynamic_memory import DynamicMemory
            from models.openai_client import get_openai_client
            
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
            
            # Parse the manuscript data
            try:
                manuscript = json.loads(manuscript_docs[0]['text'])
                title = manuscript.get("title", "Untitled")
            except json.JSONDecodeError:
                # If not JSON, create a simple manuscript object
                manuscript = {
                    "content": manuscript_docs[0]['text'],
                    "title": "Untitled",
                    "chapters": []
                }
        
        # Format the manuscript content
        content = manuscript.get("content", "")
        chapters = manuscript.get("chapters", [])
        word_count = manuscript.get("word_count", len(content.split()))
        
        # Render the manuscript
        return f"""
        <html>
        <head>
            <title>{title}</title>
            <style>
                body {{ font-family: Georgia, serif; max-width: 800px; margin: 0 auto; padding: 20px; line-height: 1.6; }}
                .container {{ padding: 20px; }}
                h1 {{ text-align: center; margin-bottom: 30px; }}
                h2 {{ text-align: center; margin-top: 40px; }}
                .chapter {{ margin-bottom: 40px; }}
                .chapter-title {{ text-align: center; margin-bottom: 20px; }}
                .manuscript {{ white-space: pre-wrap; }}
                .meta {{ text-align: center; color: #666; margin-bottom: 30px; }}
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
        
    except Exception as e:
        logger.error(f"Error viewing manuscript: {str(e)}", exc_info=True)
        return f"""
        <html>
        <head>
            <title>Error</title>
            <style>
                body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }}
                .container {{ border: 1px solid #ddd; padding: 20px; border-radius: 5px; }}
                .error {{ color: red; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Error Viewing Manuscript</h1>
                <p class="error">{str(e)}</p>
                <pre>{traceback.format_exc()}</pre>
                <p><a href="/project-status/{project_id}">Back to Project Status</a> | <a href="/">Home</a></p>
            </div>
        </body>
        </html>
        """

# Add a route to view the generated text in a simple format
@app.route('/view-generated-text/<project_id>')
def view_generated_text(project_id):
    """View all generated text for a specific project in a simple format."""
    try:
        # Initialize memory with embedding function using OpenAI
        from memory.dynamic_memory import DynamicMemory
        from models.openai_client import get_openai_client
        
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
        error_html = f"""
        <html>
        <head>
            <title>Error</title>
            <style>
                body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }}
                .error {{ border: 1px solid #ff0000; padding: 20px; border-radius: 5px; background-color: #ffeeee; }}
                pre {{ white-space: pre-wrap; background-color: #f5f5f5; padding: 10px; }}
            </style>
        </head>
        <body>
            <div class="error">
                <h1>Error Viewing Generated Text</h1>
                <p>{str(e)}</p>
                <h2>Stack Trace:</h2>
                <pre>{traceback.format_exc()}</pre>
                <p><a href="/">Return to Home</a></p>
            </div>
        </body>
        </html>
        """
        return error_html

# Human Review Interface API Endpoints
@app.route('/review/<project_id>')
def review_interface(project_id):
    """Human review interface page."""
    return render_template('review_interface.html', project_id=project_id)

@app.route('/api/reviews/<project_id>/pending', methods=['GET'])
def get_pending_reviews(project_id):
    """Get pending reviews for a project."""
    try:
        # Try to use OpenMemoryMCP if available
        mcp_server_url = "http://localhost:3434"
        try:
            memory = OpenMemoryMCP(project_id, server_url=mcp_server_url)
            import asyncio
            loop = asyncio.get_event_loop()
            loop.run_until_complete(memory.__aenter__())
        except Exception:
            # Fallback to DynamicMemory
            openai_client = get_openai_client()
            embedding_function = lambda text: openai_client.get_embeddings(text, model=EMBEDDING_MODEL)
            memory = DynamicMemory(project_id, embedding_function)
        human_loop = HumanLoopInterface(project_id, memory)
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        pending_reviews = loop.run_until_complete(human_loop.get_pending_reviews())
        return jsonify(pending_reviews)
    except Exception as e:
        logger.error(f"Error getting pending reviews: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/reviews/<review_id>', methods=['GET'])
def get_review_details(review_id):
    """Get details for a specific review."""
    try:
        project_id = request.args.get('project_id')
        if not project_id:
            return jsonify({"error": "project_id required"}), 400
        mcp_server_url = "http://localhost:3434"
        try:
            memory = OpenMemoryMCP(project_id, server_url=mcp_server_url)
            import asyncio
            loop = asyncio.get_event_loop()
            loop.run_until_complete(memory.__aenter__())
        except Exception:
            openai_client = get_openai_client()
            embedding_function = lambda text: openai_client.get_embeddings(text, model=EMBEDDING_MODEL)
            memory = DynamicMemory(project_id, embedding_function)
        human_loop = HumanLoopInterface(project_id, memory)
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        review_data = loop.run_until_complete(human_loop.get_review_status(review_id))
        if not review_data:
            return jsonify({"error": "Review not found"}), 404
        return jsonify(review_data)
    except Exception as e:
        logger.error(f"Error getting review details: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/reviews/<review_id>/submit', methods=['POST'])
def submit_review(review_id):
    """Submit a human review."""
    try:
        data = request.get_json()
        status = data.get('status')
        feedback = data.get('feedback', {})
        modifications = data.get('modifications', {})
        project_id = request.args.get('project_id')
        if not project_id:
            return jsonify({"error": "project_id required"}), 400
        mcp_server_url = "http://localhost:3434"
        try:
            memory = OpenMemoryMCP(project_id, server_url=mcp_server_url)
            import asyncio
            loop = asyncio.get_event_loop()
            loop.run_until_complete(memory.__aenter__())
        except Exception:
            openai_client = get_openai_client()
            embedding_function = lambda text: openai_client.get_embeddings(text, model=EMBEDDING_MODEL)
            memory = DynamicMemory(project_id, embedding_function)
        human_loop = HumanLoopInterface(project_id, memory)
        review_status = ReviewStatus(status)
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        success = loop.run_until_complete(human_loop.submit_review(
            review_id, review_status, feedback, modifications
        ))
        if success:
            return jsonify({"status": "success"})
        else:
            return jsonify({"error": "Failed to submit review"}), 500
    except Exception as e:
        logger.error(f"Error submitting review: {e}")
        return jsonify({"error": str(e)}), 500

# Enhanced workflow generation endpoint
@app.route('/generate-enhanced', methods=['POST'])
def generate_enhanced():
    """Generate manuscript using enhanced workflow with MCP and human-in-the-loop."""
    try:
        # Get form data
        title = request.form.get('title', '').strip()
        genre = request.form.get('genre', 'fiction')
        target_length = request.form.get('target_length', 'medium')
        complexity = request.form.get('complexity', 'medium')
        initial_prompt = request.form.get('initial_prompt', '').strip()

        # Enhanced workflow options
        enable_human_loop = request.form.get('enable_human_loop') == 'on'
        enable_mcp_memory = request.form.get('enable_mcp_memory') == 'on'

        # Generate unique project ID
        project_id = str(uuid.uuid4())

        # Add to session
        if 'projects' not in session:
            session['projects'] = []
        session['projects'].append({
            'id': project_id,
            'title': title or f"Project {project_id[:8]}",
            'created_at': datetime.now().isoformat(),
            'workflow_type': 'enhanced'
        })

        # Create enhanced workflow
        workflow = EnhancedManuscriptWorkflow(
            project_id=project_id,
            title=title,
            genre=genre,
            target_length=target_length,
            complexity=complexity,
            initial_prompt=initial_prompt,
            enable_human_loop=enable_human_loop,
            enable_mcp_memory=enable_mcp_memory
        )

        # Store in active workflows
        active_workflows[project_id] = workflow

        # Start workflow in background
        import threading
        def run_enhanced_workflow():
            try:
                import asyncio
                # Create new event loop for this thread
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    result = loop.run_until_complete(workflow.run_enhanced_workflow())
                    logger.info(f"Enhanced workflow completed successfully for {project_id}")
                    logger.info(f"Result keys: {list(result.keys()) if isinstance(result, dict) else 'Not a dict'}")
                finally:
                    loop.close()
            except Exception as e:
                logger.error(f"Enhanced workflow error for {project_id}: {e}", exc_info=True)
                # Mark workflow as failed
                if project_id in active_workflows:
                    active_workflows[project_id].is_running = False
                    active_workflows[project_id].error = str(e)

        workflow_thread = threading.Thread(target=run_enhanced_workflow)
        workflow_thread.daemon = True
        workflow_thread.start()

        flash(f'Enhanced manuscript generation started! Project ID: {project_id}', 'success')
        return redirect(url_for('dashboard', project_id=project_id))

    except Exception as e:
        logger.error(f"Error starting enhanced generation: {str(e)}")
        flash(f'Error starting enhanced generation: {str(e)}', 'error')
        return redirect(url_for('home'))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='AI Manuscript Generator')
    parser.add_argument('--port', type=int, default=int(os.environ.get("PORT", 5000)), help='Port to run the server on')
    parser.add_argument('--host', type=str, default=os.environ.get("HOST", "0.0.0.0"), help='Host to run the server on')
    parser.add_argument('--debug', action='store_true', help='Run in debug mode')
    args = parser.parse_args()

    print(f"Starting server on {args.host}:{args.port} with debug={args.debug}")
    app.run(host=args.host, port=args.port, debug=args.debug)
