"""
Core package for NovelNexus application.

This package contains the foundational components for the Flask application
including the application factory, extensions, error handlers, and middleware.
"""

from .app import create_app, create_celery_app, get_log_buffer
from .extensions import get_openai_client, get_active_workflows, cleanup_extensions
from .middleware import (
    require_project_id, 
    validate_json_request, 
    rate_limit, 
    log_performance
)

__all__ = [
    'create_app',
    'create_celery_app', 
    'get_log_buffer',
    'get_openai_client',
    'get_active_workflows',
    'cleanup_extensions',
    'require_project_id',
    'validate_json_request',
    'rate_limit',
    'log_performance'
]
