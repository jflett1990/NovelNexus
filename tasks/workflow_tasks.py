"""
Celery task definitions for NovelNexus.

This module contains all background task definitions that can be
executed asynchronously using Celery workers.
"""

import logging
import json
import traceback
from datetime import datetime
from core.app import celery_app

logger = logging.getLogger(__name__)

@celery_app.task(bind=True)
def run_workflow_task(self, project_id, **config):
    """
    Celery task to run the manuscript workflow asynchronously.
    
    Args:
        project_id: Unique ID for the project
        **config: Configuration parameters for the workflow
        
    Returns:
        Dict with task results
    """
    try:
        logger.info(f"Starting async workflow for project {project_id}")
        
        # Initialize logging for this task
        task_logger = logging.getLogger(f"workflow.task.{project_id}")
        
        # Initialize and run workflow
        from orchestration.workflow import ManuscriptWorkflow
        
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

@celery_app.task(bind=True)
def refine_manuscript_task(self, project_id, **options):
    """
    Celery task to refine a manuscript asynchronously.
    
    Args:
        project_id: Unique ID for the project
        **options: Refinement options
        
    Returns:
        Dict with refinement results
    """
    try:
        logger.info(f"Starting manuscript refinement for project {project_id}")
        
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
            model_name="gpt-4o"
        )
        
        # Start refinement
        result = refiner.refine_manuscript(
            target_chapters=options.get("chapters"),
            overwrite=options.get("overwrite", True),
            style=options.get("style", "literary"),
            max_chunks=options.get("max_chunks", 5)
        )
        
        logger.info(f"Completed manuscript refinement for project {project_id}: {result['refined_count']} chapters refined")
        
        return {
            "status": "success",
            "project_id": project_id,
            "result": result
        }
        
    except Exception as e:
        logger.error(f"Error in manuscript refinement for project {project_id}: {str(e)}", exc_info=True)
        return {
            "status": "error",
            "project_id": project_id,
            "error": str(e),
            "traceback": traceback.format_exc()
        }

@celery_app.task(bind=True)
def cleanup_old_projects_task(self, days_old=30):
    """
    Celery task to cleanup old project data.
    
    Args:
        days_old: Number of days after which projects are considered old
        
    Returns:
        Dict with cleanup results
    """
    try:
        import os
        from pathlib import Path
        from datetime import datetime, timedelta
        
        logger.info(f"Starting cleanup of projects older than {days_old} days")
        
        memory_base_dir = Path("memory_data")
        cutoff_date = datetime.now() - timedelta(days=days_old)
        
        cleaned_projects = []
        total_size_freed = 0
        
        if memory_base_dir.exists():
            for project_dir in memory_base_dir.iterdir():
                if project_dir.is_dir():
                    # Check directory modification time
                    mod_time = datetime.fromtimestamp(project_dir.stat().st_mtime)
                    
                    if mod_time < cutoff_date:
                        # Calculate size before deletion
                        dir_size = sum(f.stat().st_size for f in project_dir.rglob('*') if f.is_file())
                        total_size_freed += dir_size
                        
                        # Remove the project directory
                        import shutil
                        shutil.rmtree(project_dir)
                        
                        cleaned_projects.append({
                            "project_id": project_dir.name,
                            "last_modified": mod_time.isoformat(),
                            "size_freed": dir_size
                        })
        
        logger.info(f"Cleanup completed: {len(cleaned_projects)} projects removed, {total_size_freed} bytes freed")
        
        return {
            "status": "success",
            "cleaned_projects": len(cleaned_projects),
            "total_size_freed": total_size_freed,
            "projects": cleaned_projects
        }
        
    except Exception as e:
        logger.error(f"Error in cleanup task: {str(e)}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "traceback": traceback.format_exc()
        }

@celery_app.task(bind=True)
def health_check_task(self):
    """
    Celery task for health checking the worker system.
    
    Returns:
        Dict with health check results
    """
    try:
        # Perform various health checks
        health_data = {
            "timestamp": datetime.now().isoformat(),
            "worker_id": self.request.id,
            "status": "healthy"
        }
        
        # Check OpenAI connectivity
        try:
            from models.openai_client import get_openai_client
            openai_client = get_openai_client()
            if openai_client and openai_client.is_available():
                health_data["openai_status"] = "available"
            else:
                health_data["openai_status"] = "unavailable"
        except Exception as e:
            health_data["openai_status"] = f"error: {str(e)}"
        
        # Check memory system
        try:
            from pathlib import Path
            memory_dir = Path("memory_data")
            if memory_dir.exists():
                health_data["memory_system"] = "available"
                health_data["memory_projects"] = len([d for d in memory_dir.iterdir() if d.is_dir()])
            else:
                health_data["memory_system"] = "directory_missing"
        except Exception as e:
            health_data["memory_system"] = f"error: {str(e)}"
        
        # Check disk space
        try:
            import shutil
            total, used, free = shutil.disk_usage(".")
            health_data["disk_space"] = {
                "total_gb": round(total / (1024**3), 2),
                "used_gb": round(used / (1024**3), 2),
                "free_gb": round(free / (1024**3), 2),
                "usage_percent": round((used / total) * 100, 2)
            }
        except Exception as e:
            health_data["disk_space"] = f"error: {str(e)}"
        
        return health_data
        
    except Exception as e:
        logger.error(f"Error in health check task: {str(e)}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "traceback": traceback.format_exc()
        }

@celery_app.task(bind=True)
def generate_embeddings_task(self, project_id, texts, batch_size=50):
    """
    Celery task to generate embeddings for a batch of texts.
    
    Args:
        project_id: Project ID for context
        texts: List of texts to generate embeddings for
        batch_size: Number of texts to process in each batch
        
    Returns:
        Dict with embedding results
    """
    try:
        logger.info(f"Starting embedding generation for project {project_id}: {len(texts)} texts")
        
        from models.openai_client import get_openai_client
        from models.openai_models import EMBEDDING_MODEL
        
        openai_client = get_openai_client()
        if not openai_client or not openai_client.is_available():
            raise ValueError("OpenAI client not available for embedding generation")
        
        embeddings = []
        total_tokens = 0
        
        # Process texts in batches
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            
            try:
                # Generate embeddings for this batch
                batch_embeddings = []
                for text in batch:
                    embedding = openai_client.get_embeddings(text, model=EMBEDDING_MODEL)
                    batch_embeddings.append(embedding)
                    total_tokens += len(text.split())  # Rough token estimate
                
                embeddings.extend(batch_embeddings)
                
                # Log progress
                logger.info(f"Processed batch {i//batch_size + 1}/{(len(texts) + batch_size - 1)//batch_size}")
                
            except Exception as e:
                logger.error(f"Error processing batch {i//batch_size + 1}: {str(e)}")
                # Add None for failed embeddings
                embeddings.extend([None] * len(batch))
        
        success_count = sum(1 for e in embeddings if e is not None)
        
        logger.info(f"Completed embedding generation for project {project_id}: {success_count}/{len(texts)} successful")
        
        return {
            "status": "success",
            "project_id": project_id,
            "total_texts": len(texts),
            "successful_embeddings": success_count,
            "failed_embeddings": len(texts) - success_count,
            "total_tokens": total_tokens,
            "embeddings": embeddings
        }
        
    except Exception as e:
        logger.error(f"Error in embedding generation task for project {project_id}: {str(e)}", exc_info=True)
        return {
            "status": "error",
            "project_id": project_id,
            "error": str(e),
            "traceback": traceback.format_exc()
        }

@celery_app.task(bind=True)
def backup_project_task(self, project_id, backup_location="backups"):
    """
    Celery task to backup a project's data.
    
    Args:
        project_id: Project ID to backup
        backup_location: Directory to store backups
        
    Returns:
        Dict with backup results
    """
    try:
        import os
        import shutil
        import zipfile
        from pathlib import Path
        
        logger.info(f"Starting backup for project {project_id}")
        
        # Create backup directory
        backup_dir = Path(backup_location)
        backup_dir.mkdir(exist_ok=True)
        
        # Source project directory
        source_dir = Path(f"memory_data/{project_id}")
        if not source_dir.exists():
            raise ValueError(f"Project directory not found: {source_dir}")
        
        # Create backup filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"{project_id}_{timestamp}.zip"
        backup_path = backup_dir / backup_filename
        
        # Create zip backup
        with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in source_dir.rglob('*'):
                if file_path.is_file():
                    # Add file to zip with relative path
                    arcname = file_path.relative_to(source_dir.parent)
                    zipf.write(file_path, arcname)
        
        # Get backup size
        backup_size = backup_path.stat().st_size
        
        logger.info(f"Completed backup for project {project_id}: {backup_filename} ({backup_size} bytes)")
        
        return {
            "status": "success",
            "project_id": project_id,
            "backup_filename": backup_filename,
            "backup_path": str(backup_path),
            "backup_size": backup_size,
            "timestamp": timestamp
        }
        
    except Exception as e:
        logger.error(f"Error in backup task for project {project_id}: {str(e)}", exc_info=True)
        return {
            "status": "error",
            "project_id": project_id,
            "error": str(e),
            "traceback": traceback.format_exc()
        }

# Periodic tasks can be defined here and scheduled with Celery Beat
@celery_app.task
def daily_cleanup_task():
    """Daily cleanup task to be run via Celery Beat."""
    return cleanup_old_projects_task.delay(days_old=30)

@celery_app.task
def hourly_health_check():
    """Hourly health check task to be run via Celery Beat."""
    return health_check_task.delay()
