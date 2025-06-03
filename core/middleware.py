"""
Flask middleware and request processing utilities.

This module provides custom middleware, request/response processors,
and other utilities that operate on the Flask request cycle.
"""

import logging
import time
from flask import Flask, request, session, g
from functools import wraps
from typing import Callable, Any

logger = logging.getLogger(__name__)

def register_middleware(app: Flask) -> None:
    """
    Register middleware and request processors for the Flask application.
    
    Args:
        app: Flask application instance
    """
    
    @app.before_request
    def before_request():
        """Process requests before they reach route handlers."""
        # Record request start time for performance monitoring
        g.start_time = time.time()
        
        # Initialize session data if needed
        if 'projects' not in session:
            session['projects'] = []
        
        # Log request details for debugging
        logger.debug(f"Request: {request.method} {request.url}")
    
    @app.after_request
    def after_request(response):
        """Process responses after route handlers complete."""
        # Add security headers
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        
        # Add CORS headers if needed
        if request.origin:
            response.headers['Access-Control-Allow-Origin'] = request.origin
            response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
            response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
            response.headers['Access-Control-Allow-Credentials'] = 'true'
        
        # Log response time
        if hasattr(g, 'start_time'):
            duration = time.time() - g.start_time
            logger.debug(f"Request completed in {duration:.3f}s - {response.status_code}")
        
        return response
    
    @app.teardown_request
    def teardown_request(exception):
        """Clean up after request processing."""
        if exception:
            logger.error(f"Request teardown with exception: {str(exception)}")

def require_project_id(f: Callable) -> Callable:
    """
    Decorator to ensure a valid project_id is provided in the request.
    
    Args:
        f: Function to decorate
        
    Returns:
        Decorated function
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from flask import jsonify
        
        project_id = kwargs.get('project_id')
        if not project_id:
            return jsonify({'error': 'Project ID is required'}), 400
        
        # Store project_id in request context for easy access
        g.project_id = project_id
        
        return f(*args, **kwargs)
    
    return decorated_function

def validate_json_request(required_fields: list = None) -> Callable:
    """
    Decorator to validate JSON request data.
    
    Args:
        required_fields: List of required field names
        
    Returns:
        Decorator function
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            from flask import jsonify
            
            if not request.is_json:
                return jsonify({'error': 'Request must be JSON'}), 400
            
            data = request.get_json()
            if not data:
                return jsonify({'error': 'Invalid JSON data'}), 400
            
            # Check required fields
            if required_fields:
                missing_fields = [field for field in required_fields if field not in data]
                if missing_fields:
                    return jsonify({
                        'error': 'Missing required fields',
                        'missing_fields': missing_fields
                    }), 400
            
            # Store validated data in request context
            g.json_data = data
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator

def rate_limit(max_requests: int = 100, window_seconds: int = 3600) -> Callable:
    """
    Simple rate limiting decorator.
    
    Args:
        max_requests: Maximum number of requests allowed
        window_seconds: Time window in seconds
        
    Returns:
        Decorator function
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            from flask import jsonify
            import time
            
            # Simple in-memory rate limiting (would use Redis in production)
            client_ip = request.environ.get('REMOTE_ADDR', 'unknown')
            current_time = int(time.time())
            window_start = current_time - window_seconds
            
            # This is a simplified implementation
            # In production, you'd want to use Redis or similar
            if not hasattr(g, 'rate_limit_store'):
                g.rate_limit_store = {}
            
            if client_ip not in g.rate_limit_store:
                g.rate_limit_store[client_ip] = []
            
            # Clean old requests
            g.rate_limit_store[client_ip] = [
                req_time for req_time in g.rate_limit_store[client_ip]
                if req_time > window_start
            ]
            
            # Check rate limit
            if len(g.rate_limit_store[client_ip]) >= max_requests:
                return jsonify({
                    'error': 'Rate limit exceeded',
                    'retry_after': window_seconds
                }), 429
            
            # Record this request
            g.rate_limit_store[client_ip].append(current_time)
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator

def log_performance(threshold_seconds: float = 1.0) -> Callable:
    """
    Decorator to log slow requests.
    
    Args:
        threshold_seconds: Log requests slower than this threshold
        
    Returns:
        Decorator function
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            start_time = time.time()
            result = f(*args, **kwargs)
            duration = time.time() - start_time
            
            if duration > threshold_seconds:
                logger.warning(
                    f"Slow request: {request.method} {request.url} "
                    f"took {duration:.3f}s (threshold: {threshold_seconds}s)"
                )
            
            return result
        
        return decorated_function
    return decorator

class RequestIDMiddleware:
    """Middleware to add unique request IDs for tracing."""
    
    def __init__(self, app: Flask):
        self.app = app
        self.init_app(app)
    
    def init_app(self, app: Flask):
        app.before_request(self.before_request)
        app.after_request(self.after_request)
    
    def before_request(self):
        """Generate and store request ID."""
        import uuid
        g.request_id = str(uuid.uuid4())[:8]
    
    def after_request(self, response):
        """Add request ID to response headers."""
        if hasattr(g, 'request_id'):
            response.headers['X-Request-ID'] = g.request_id
        return response

def setup_security_middleware(app: Flask) -> None:
    """
    Setup security-related middleware.
    
    Args:
        app: Flask application instance
    """
    
    @app.before_request
    def security_checks():
        """Perform security checks on incoming requests."""
        # Block requests with suspicious patterns
        suspicious_patterns = [
            '../', '..\\', '<script>', 'javascript:', 'data:',
            'vbscript:', 'onload=', 'onerror='
        ]
        
        request_data = str(request.url) + str(request.get_data(as_text=True))
        for pattern in suspicious_patterns:
            if pattern in request_data.lower():
                logger.warning(f"Suspicious request blocked: {request.url}")
                from flask import abort
                abort(400)
        
        # Check for overly large requests
        if request.content_length and request.content_length > 50 * 1024 * 1024:  # 50MB
            logger.warning(f"Large request blocked: {request.content_length} bytes")
            from flask import abort
            abort(413)

def init_request_logging(app: Flask) -> None:
    """
    Initialize detailed request logging.
    
    Args:
        app: Flask application instance
    """
    
    @app.before_request
    def log_request_info():
        """Log detailed request information."""
        if app.debug:
            logger.debug(f"Request Headers: {dict(request.headers)}")
            if request.is_json:
                logger.debug(f"Request JSON: {request.get_json()}")
    
    @app.after_request
    def log_response_info(response):
        """Log response information."""
        if app.debug:
            logger.debug(f"Response Status: {response.status_code}")
            logger.debug(f"Response Headers: {dict(response.headers)}")
        return response
