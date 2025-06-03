"""
API Blueprint for NovelNexus.

This module contains all API endpoints that return JSON responses,
separated from the web interface routes.
"""

import logging
import json
import traceback
import os
from datetime import datetime
from flask import Blueprint, request, jsonify, g
from core.middleware import require_project_id, validate_json_request, log_performance
from core.extensions import get_active_workflows, get_openai_client

logger = logging.getLogger(__name__)

# Create API blueprint
api_bp = Blueprint('api', __name__)

@api_bp.route('/health', methods=['GET'])
def health_check():
    """API health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': '1.0.0'
    })

@api_bp.route('/project/<project_id>/status', methods=['GET'])
@require_project_id
@log_performance()
def get_project_status(project_id):
    """Get current project status."""
    try:
        active_workflows = get_active_workflows()
        
        # Get status from active workflow
        if project_id in active_workflows:
            workflow = active_workflows[project_id]
            status = {
                "project_id": project_id,
                "status": "running" if workflow.is_running and not workflow.is_complete else "complete" if workflow.is_complete else "not_started",
                "progress": workflow.get_progress(),
                "current_stage": workflow.current_stage,
                "current_agent": getattr(workflow, 'current_agent', None) or (workflow.current_stage + "_agent" if workflow.current_stage else None),
                "completed_stages": workflow.completed_stages,
                "is_running": workflow.is_running,
                "is_complete": workflow.is_complete,
                "threads_alive": workflow.thread_health(),
                "errors": []
            }
        else:
            # Try to get status from central hub
            try:
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
                
                # Add current_agent based on current_stage if not present
                if 'current_agent' not in status and 'current_stage' in status and status['current_stage']:
                    status['current_agent'] = status['current_stage'] + "_agent"
                    
            except Exception as e:
                logger.warning(f"Could not get status from central hub: {str(e)}")
                status = {
                    "project_id": project_id,
                    "status": "unknown",
                    "current_stage": "not_started",
                    "progress": 0,
                    "completed_stages": [],
                    "error": "Could not retrieve project status"
                }
        
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

@api_bp.route('/dashboard-data/<project_id>', methods=['GET'])
@require_project_id
@log_performance()
def get_dashboard_data(project_id):
    """Get all data needed for dashboard."""
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
        
        # Get various dashboard components from central hub
        project_status = hub.get_project_status()
        
        # Try to get timeline, handle if method doesn't exist
        try:
            timeline = hub.get_timeline()
        except (AttributeError, Exception) as e:
            logger.warning(f"Error getting timeline: {str(e)}")
            timeline = []
            
        # Check if we need to load active workflow data
        active_workflows = get_active_workflows()
        if project_id in active_workflows:
            workflow = active_workflows[project_id]
            project_status.update({
                'is_running': workflow.is_running,
                'is_complete': workflow.is_complete,
                'current_agent': getattr(workflow, 'current_agent', None),
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

@api_bp.route('/project/<project_id>/debug', methods=['GET'])
@require_project_id
def debug_workflow(project_id):
    """Debug endpoint to check workflow state."""
    active_workflows = get_active_workflows()
    
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

@api_bp.route('/project/<project_id>/logs', methods=['GET'])
@require_project_id
def get_project_logs(project_id):
    """Get the latest logs for a project."""
    try:
        from core.app import get_log_buffer
        
        # Convert log buffer to a list of formatted strings
        all_logs = list(get_log_buffer())
        # Filter logs that contain the project ID or are general system logs
        project_logs = [log for log in all_logs if project_id in str(log['message']) or log['module'] == '__main__']
        return jsonify({"logs": project_logs})
        
    except Exception as e:
        logger.error(f"Error getting logs: {str(e)}")
        return jsonify({"error": str(e)}), 500

@api_bp.route('/project/<project_id>/reset-thread', methods=['POST'])
@require_project_id
def reset_thread(project_id):
    """Reset a stalled or dead workflow thread."""
    try:
        active_workflows = get_active_workflows()
        
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
            try:
                from orchestration.workflow import ManuscriptWorkflow
                from memory.dynamic_memory import DynamicMemory
                from models.openai_client import get_openai_client
                from models.openai_models import EMBEDDING_MODEL
                
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

@api_bp.route('/manuscript/<project_id>', methods=['GET'])
@require_project_id
def get_manuscript(project_id):
    """Retrieve the manuscript for a given project."""
    try:
        active_workflows = get_active_workflows()
        
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

@api_bp.route('/refine', methods=['POST'])
@validate_json_request(['project_id'])
def trigger_refinement():
    """API endpoint to trigger manuscript refinement."""
    try:
        # Get request data
        data = g.json_data
        project_id = data.get("project_id")
        
        # Initialize components
        from memory.dynamic_memory import DynamicMemory
        from agents.manuscript_refiner import ManuscriptRefiner
        from models.openai_client import get_openai_client
        from models.openai_models import EMBEDDING_MODEL
        
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

# SSE endpoint for streaming logs
@api_bp.route('/stream-logs/<project_id>', methods=['GET'])
@require_project_id
def stream_logs(project_id):
    """Server-Sent Events endpoint for streaming logs."""
    def stream_generate():
        from core.app import get_log_buffer
        import time
        
        # Stream logs with SSE format
        last_sent_idx = 0
        while True:
            log_buffer = get_log_buffer()
            if len(log_buffer) > last_sent_idx:
                for i in range(last_sent_idx, len(log_buffer)):
                    log = log_buffer[i]
                    # Only send logs related to this project
                    if project_id in str(log['message']) or log['module'] == '__main__':
                        log_str = f"{log['timestamp']} - {log['module']} - {log['level']} - {log['message']}"
                        yield f"data: {json.dumps({'log': log_str})}\n\n"
                last_sent_idx = len(log_buffer)
            yield f"data: {json.dumps({'keepalive': True})}\n\n"
            time.sleep(1)
    
    response = jsonify()
    response.mimetype = 'text/event-stream'
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['Connection'] = 'keep-alive'
    response.data = stream_generate()
    
    return response
