import os
import logging
import json
import argparse
import traceback
import sys
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, make_response
from werkzeug.middleware.proxy_fix import ProxyFix
from orchestration.workflow import ManuscriptWorkflow
from models.openai_client import initialize_openai, get_openai_client
from models.openai_models import EMBEDDING_MODEL
from collections import deque
from datetime import datetime
import dotenv

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
    return render_template('index.html')

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
                'current_agent': workflow.current_agent,
                'current_stage': workflow.current_stage,
                'completed_stages': workflow.completed_stages,
                'progress': workflow.get_progress(),
                'thread_health': workflow.get_thread_health(),
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
    def generate():
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
        generate(),
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
    # For GET requests, render the form
    if request.method == 'GET':
        return render_template('generate.html')
        
    # For POST requests, process the form
    try:
        # Get form data
        title = request.form.get('title', '')
        genre = request.form.get('genre', '')
        target_length = request.form.get('target_length', 'medium')
        complexity = request.form.get('complexity', 'medium')
        initial_prompt = request.form.get('initial_prompt', '')
        
        logger.info(f"Received generation request - Title: {title}, Genre: {genre}, Length: {target_length}")
        
        # Generate unique project ID
        import random
        project_id = str(random.getrandbits(64) - 2**63)
        logger.info(f"Generated project ID: {project_id}")
        
        # Configure workflow
        config = {
            "title": title,
            "genre": genre,
            "target_length": target_length,
            "complexity": complexity,
            "use_openai": True,   # Using OpenAI as primary service
            "use_ollama": False,  # Disable Ollama
            "initial_prompt": initial_prompt
        }
        
        logger.debug(f"Initializing workflow with config: {json.dumps(config)}")
        
        # Create workflow
        workflow = ManuscriptWorkflow(
            project_id=project_id,
            **config
        )
        logger.info(f"Workflow initialized for project {project_id}")
        
        # Store workflow in active workflows
        active_workflows[project_id] = workflow
        logger.info(f"{project_id}: Project initialized with title: {title}, genre: {genre}")
        
        # Start the workflow
        workflow.start()
        logger.info(f"Workflow started for project {project_id}")
        
        # Add to session
        if 'projects' in session:
            projects = session['projects']
            projects.append({
                "id": project_id,
                "title": title or "Untitled",
                "genre": genre,
                "date": datetime.now().strftime("%Y-%m-%d %H:%M")
            })
            session['projects'] = projects
        
        logger.info(f"{project_id}: Manuscript generation started")
        
        # Redirect to dashboard
        return redirect(url_for('dashboard', project_id=project_id))
    except Exception as e:
        logger.error(f"Error starting generation: {str(e)}", exc_info=True)
        flash(f"Error: {str(e)}", 'error')
        return redirect(url_for('home'))

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
                    embedding_model=EMBEDDING_MODEL,
                    use_openai=True
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

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='AI Manuscript Generator')
    parser.add_argument('--port', type=int, default=int(os.environ.get("PORT", 5000)), help='Port to run the server on')
    parser.add_argument('--host', type=str, default=os.environ.get("HOST", "0.0.0.0"), help='Host to run the server on')
    parser.add_argument('--debug', action='store_true', help='Run in debug mode')
    args = parser.parse_args()
    
    print(f"Starting server on {args.host}:{args.port} with debug={args.debug}")
    app.run(host=args.host, port=args.port, debug=args.debug)
