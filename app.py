import os
import logging
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from werkzeug.middleware.proxy_fix import ProxyFix
from orchestration.workflow import ManuscriptWorkflow
from models.ollama_client import initialize_ollama
from models.openai_client import initialize_openai

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "default-dev-secret")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Initialize models
initialize_ollama()
initialize_openai()

# Store active workflows
active_workflows = {}

@app.route('/')
def index():
    """Render the home page."""
    return render_template('index.html')

@app.route('/project', methods=['GET'])
def project():
    """Render the project page with the current manuscript project status."""
    project_id = session.get('project_id')
    
    if not project_id or project_id not in active_workflows:
        return redirect(url_for('index'))
    
    workflow = active_workflows[project_id]
    project_data = {
        'id': project_id,
        'status': workflow.status,
        'current_stage': workflow.current_stage,
        'progress': workflow.progress
    }
    
    return render_template('project.html', project=project_data)

@app.route('/generate', methods=['GET', 'POST'])
def generate():
    """Start a new manuscript generation project."""
    if request.method == 'POST':
        try:
            # Create a new workflow instance
            project_id = str(hash(f"{request.form.get('title')}-{os.urandom(8).hex()}"))
            
            workflow_config = {
                'title': request.form.get('title'),
                'genre': request.form.get('genre'),
                'target_length': request.form.get('target_length'),
                'complexity': request.form.get('complexity', 'medium'),
                'use_openai': request.form.get('use_openai') == 'on',
                'use_ollama': request.form.get('use_ollama') == 'on',
                'initial_prompt': request.form.get('initial_prompt', '')
            }
            
            # Initialize the workflow
            workflow = ManuscriptWorkflow(project_id, workflow_config)
            active_workflows[project_id] = workflow
            
            # Start the workflow asynchronously
            workflow.start()
            
            # Store project ID in session
            session['project_id'] = project_id
            
            flash('Manuscript generation started successfully!', 'success')
            return redirect(url_for('project'))
        except Exception as e:
            logger.error(f"Error starting generation: {str(e)}")
            flash(f'Error starting generation: {str(e)}', 'danger')
    
    return render_template('generate.html')

@app.route('/api/project/<project_id>/status', methods=['GET'])
def project_status(project_id):
    """Get the current status of a project."""
    if project_id not in active_workflows:
        return jsonify({'error': 'Project not found'}), 404
    
    workflow = active_workflows[project_id]
    return jsonify({
        'id': project_id,
        'status': workflow.status,
        'current_stage': workflow.current_stage,
        'progress': workflow.progress,
        'completed_stages': workflow.completed_stages
    })

@app.route('/api/project/<project_id>/manuscript', methods=['GET'])
def get_manuscript(project_id):
    """Get the current manuscript for a project."""
    if project_id not in active_workflows:
        return jsonify({'error': 'Project not found'}), 404
    
    workflow = active_workflows[project_id]
    if not workflow.is_complete:
        return jsonify({'error': 'Manuscript not yet complete'}), 400
    
    return jsonify({
        'id': project_id,
        'title': workflow.config['title'],
        'manuscript': workflow.get_final_manuscript()
    })

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(error):
    """Handle 500 errors."""
    logger.error(f"Server error: {str(error)}")
    return render_template('500.html'), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
