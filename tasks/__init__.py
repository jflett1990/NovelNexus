"""
Tasks package for NovelNexus.

This package contains Celery task definitions for background processing.
"""

from .workflow_tasks import (
    run_workflow_task,
    refine_manuscript_task,
    cleanup_old_projects_task,
    health_check_task,
    generate_embeddings_task,
    backup_project_task,
    daily_cleanup_task,
    hourly_health_check
)

__all__ = [
    'run_workflow_task',
    'refine_manuscript_task',
    'cleanup_old_projects_task',
    'health_check_task',
    'generate_embeddings_task',
    'backup_project_task',
    'daily_cleanup_task',
    'hourly_health_check'
]
