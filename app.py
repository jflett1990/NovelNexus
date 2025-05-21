import os
import logging
import json
import argparse
import traceback
import uuid
import sys
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, make_response
from werkzeug.middleware.proxy_fix import ProxyFix
from orchestration.workflow import ManuscriptWorkflow
from models.openai_client import initialize_openai, get_openai_client
from models.openai_models import EMBEDDING_MODEL
from collections import deque
from datetime import datetime
import dotenv

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
        from hubs.central_hub import CentralHub
        from memory.dynamic_memory import DynamicMemory
        from models.openai_client import get_openai_client
        
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
            from hubs.central_hub import CentralHub
            from memory.dynamic_memory import DynamicMemory
            from models.openai_client import get_openai_client
            
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
    try:
        # Get status from central hub
        from hubs.central_hub import CentralHub
        from memory.dynamic_memory import DynamicMemory
        from models.openai_client import get_openai_client
        
        # Initialize memory with embedding function using OpenAI
        openai_client = get_openai_client()
        embedding_function = lambda text: openai_client.get_embeddings(text, model=EMBEDDING_MODEL)
        memory = DynamicMemory(project_id, embedding_function)
        
        # Initialize hub with memory
        hub = CentralHub(project_id, memory)
        
        # Get various dashboard components from central hub
        project_status = hub.get_project_status()
        
        # Try to get timeline, handle if method doesn't exist
        try:
            timeline = hub.get_timeline()
        except (AttributeError, Exception) as e:
            logger.warning(f"Error getting timeline: {str(e)}")
            timeline = []
            
        # Check if we need to load active workflow data
        if project_id in active_workflows:
            workflow = active_workflows[project_id]
            project_status.update({
                'is_running': workflow.is_running,
                'is_complete': workflow.is_complete,
                'current_agent': workflow.current_agent if hasattr(workflow, 'current_agent') else None,
                'current_stage': workflow.current_stage,
                'completed_stages': workflow.completed_stages,
                'progress': workflow.get_progress(),
                'thread_health': workflow.thread_health() if hasattr(workflow, 'thread_health') else None,
                'project_id': project_id
            })
            
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

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='AI Manuscript Generator')
    parser.add_argument('--port', type=int, default=int(os.environ.get("PORT", 5000)), help='Port to run the server on')
    parser.add_argument('--host', type=str, default=os.environ.get("HOST", "0.0.0.0"), help='Host to run the server on')
    parser.add_argument('--debug', action='store_true', help='Run in debug mode')
    args = parser.parse_args()
    
    print(f"Starting server on {args.host}:{args.port} with debug={args.debug}")
    app.run(host=args.host, port=args.port, debug=args.debug)

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
        
        # Query memory for manuscript
        manuscript_docs = memory.query_memory("type:manuscript", top_k=1)
        
        # If not found, try with final_manuscript type
        if not manuscript_docs or len(manuscript_docs) == 0:
            manuscript_docs = memory.query_memory("type:final_manuscript", top_k=1)
            
        if not manuscript_docs or len(manuscript_docs) == 0:
            return jsonify({
                "success": False,
                "error": "Manuscript not found in memory"
            }), 404
        
        # Parse the manuscript data
        try:
            manuscript_data = json.loads(manuscript_docs[0]['text'])
            
            # Return the manuscript
            return jsonify({
                "success": True,
                "title": manuscript_data.get("title", "Untitled"),
                "chapters": manuscript_data.get("chapters", []),
                "word_count": manuscript_data.get("word_count", 0),
                "content": manuscript_data.get("content", "")
            })
        except json.JSONDecodeError:
            # If not JSON, return the raw document
            return jsonify({
                "success": True,
                "content": manuscript_docs[0]['text'],
                "title": "Untitled",
                "chapters": [],
                "word_count": len(manuscript_docs[0]['text'].split())
            })
        
    except Exception as e:
        logger.error(f"Error retrieving manuscript: {str(e)}", exc_info=True)
        return jsonify({
            "success": False, 
            "error": str(e)
        }), 500

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
