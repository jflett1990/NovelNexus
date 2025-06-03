"""
Core application factory and initialization.

This module provides the main Flask application factory and handles
application-wide initialization, including extensions, blueprints,
and error handlers.
"""

import logging
from collections import deque
from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix
from typing import Optional, Dict, Any

from config import config, setup_logging, get_celery_config
from core.extensions import init_extensions
from core.error_handlers import register_error_handlers
from core.middleware import register_middleware
from api import api_bp
from web import web_bp

# Global log buffer for capturing application logs
log_buffer = deque(maxlen=config.logging.buffer_size)

class BufferLogHandler(logging.Handler):
    """Custom log handler to capture logs in a buffer for real-time access."""
    
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

def create_app(config_name: Optional[str] = None) -> Flask:
    """
    Application factory pattern implementation.
    
    Args:
        config_name: Configuration environment name
        
    Returns:
        Configured Flask application instance
    """
    app = Flask(__name__)
    
    # Load configuration
    if config_name:
        from config import get_config
        app_config = get_config(config_name)
    else:
        app_config = config
    
    # Configure Flask app
    app.secret_key = app_config.security.secret_key
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
    
    # Setup logging first
    setup_logging(app_config)
    
    # Add buffer handler to capture logs
    buffer_handler = BufferLogHandler()
    buffer_handler.setFormatter(logging.Formatter(app_config.logging.format))
    logging.getLogger().addHandler(buffer_handler)
    
    logger = logging.getLogger(__name__)
    logger.info(f"Starting {app_config.app_name} v{app_config.app_version}")
    
    # Initialize extensions
    init_extensions(app, app_config)
    
    # Register middleware
    register_middleware(app)
    
    # Add proxy fix for reverse proxy setups
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    
    # Register blueprints
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(web_bp)
    
    # Register error handlers
    register_error_handlers(app)
    
    # Store config in app for access in views
    app.config['APP_CONFIG'] = app_config
    
    logger.info("Application initialization completed successfully")
    
    return app

def create_celery_app(app: Optional[Flask] = None) -> 'Celery':
    """
    Create and configure Celery application.
    
    Args:
        app: Flask application instance
        
    Returns:
        Configured Celery application
    """
    try:
        from celery import Celery
        
        celery = Celery('novelNexus')
        celery.conf.update(get_celery_config())
        
        if app:
            # Update task base classes for Flask application context
            class ContextTask(celery.Task):
                """Make celery tasks work with Flask app context."""
                def __call__(self, *args, **kwargs):
                    with app.app_context():
                        return self.run(*args, **kwargs)
            
            celery.Task = ContextTask
            
        logger = logging.getLogger(__name__)
        logger.info(f"Celery initialized with broker: {config.celery.broker_url}")
        
        return celery
        
    except ImportError:
        logger = logging.getLogger(__name__)
        logger.warning("Celery not installed. Async processing will be disabled.")
        return None

def get_log_buffer() -> deque:
    """Get the current log buffer for real-time log access."""
    return log_buffer

# Create default app instance
app = create_app()
celery_app = create_celery_app(app)
