"""
Centralized error handling for the Flask application.

This module provides error handlers for different HTTP status codes
and exception types, with appropriate logging and user-friendly responses.
"""

import logging
import traceback
from flask import Flask, request, jsonify, render_template_string
from werkzeug.exceptions import HTTPException

logger = logging.getLogger(__name__)

def register_error_handlers(app: Flask) -> None:
    """
    Register error handlers for the Flask application.
    
    Args:
        app: Flask application instance
    """
    
    @app.errorhandler(404)
    def not_found_error(error):
        """Handle 404 Not Found errors."""
        logger.warning(f"404 error for {request.url}")
        
        if request.is_json or request.path.startswith('/api/'):
            return jsonify({
                'error': 'Not Found',
                'message': 'The requested resource was not found',
                'status_code': 404
            }), 404
        
        return render_template_string(ERROR_404_TEMPLATE), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        """Handle 500 Internal Server errors."""
        logger.error(f"500 error: {str(error)}", exc_info=True)
        
        if request.is_json or request.path.startswith('/api/'):
            return jsonify({
                'error': 'Internal Server Error',
                'message': 'An unexpected error occurred',
                'status_code': 500
            }), 500
        
        return render_template_string(ERROR_500_TEMPLATE), 500
    
    @app.errorhandler(400)
    def bad_request_error(error):
        """Handle 400 Bad Request errors."""
        logger.warning(f"400 error for {request.url}: {str(error)}")
        
        if request.is_json or request.path.startswith('/api/'):
            return jsonify({
                'error': 'Bad Request',
                'message': 'The request was invalid or malformed',
                'status_code': 400
            }), 400
        
        return render_template_string(ERROR_400_TEMPLATE), 400
    
    @app.errorhandler(403)
    def forbidden_error(error):
        """Handle 403 Forbidden errors."""
        logger.warning(f"403 error for {request.url}")
        
        if request.is_json or request.path.startswith('/api/'):
            return jsonify({
                'error': 'Forbidden',
                'message': 'You do not have permission to access this resource',
                'status_code': 403
            }), 403
        
        return render_template_string(ERROR_403_TEMPLATE), 403
    
    @app.errorhandler(HTTPException)
    def handle_http_exception(error):
        """Handle all other HTTP exceptions."""
        logger.warning(f"HTTP {error.code} error for {request.url}: {error.description}")
        
        if request.is_json or request.path.startswith('/api/'):
            return jsonify({
                'error': error.name,
                'message': error.description,
                'status_code': error.code
            }), error.code
        
        return render_template_string(
            GENERIC_ERROR_TEMPLATE.format(
                code=error.code,
                name=error.name,
                description=error.description
            )
        ), error.code
    
    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        """Handle unexpected non-HTTP exceptions."""
        logger.error(f"Unexpected error: {str(error)}", exc_info=True)
        
        # Store detailed error info for debugging
        error_details = {
            'type': type(error).__name__,
            'message': str(error),
            'traceback': traceback.format_exc(),
            'url': request.url,
            'method': request.method,
            'user_agent': request.headers.get('User-Agent', 'Unknown')
        }
        
        if request.is_json or request.path.startswith('/api/'):
            return jsonify({
                'error': 'Unexpected Error',
                'message': 'An unexpected error occurred while processing your request',
                'status_code': 500,
                'debug': error_details if app.debug else None
            }), 500
        
        return render_template_string(
            ERROR_500_TEMPLATE + (
                f"<div style='margin-top: 20px; padding: 10px; background: #f5f5f5; border-radius: 5px;'>"
                f"<h3>Debug Information:</h3><pre>{traceback.format_exc()}</pre></div>"
                if app.debug else ""
            )
        ), 500

# Error page templates
ERROR_404_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Page Not Found</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
        .error { border: 1px solid #ddd; padding: 20px; border-radius: 5px; background-color: #f9f9f9; }
        .error h1 { color: #d32f2f; margin-top: 0; }
        .error p { margin-bottom: 20px; }
        .back-link { color: #1976d2; text-decoration: none; }
        .back-link:hover { text-decoration: underline; }
    </style>
</head>
<body>
    <div class="error">
        <h1>Page Not Found</h1>
        <p>The page you requested could not be found. This might be because:</p>
        <ul>
            <li>The URL is incorrect</li>
            <li>The page has been moved or deleted</li>
            <li>You don't have permission to access this page</li>
        </ul>
        <p><a href="/" class="back-link">← Return to Home</a></p>
    </div>
</body>
</html>
"""

ERROR_500_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Server Error</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
        .error { border: 1px solid #d32f2f; padding: 20px; border-radius: 5px; background-color: #ffebee; }
        .error h1 { color: #d32f2f; margin-top: 0; }
        .error p { margin-bottom: 20px; }
        .back-link { color: #1976d2; text-decoration: none; }
        .back-link:hover { text-decoration: underline; }
    </style>
</head>
<body>
    <div class="error">
        <h1>Server Error</h1>
        <p>We're sorry, but something went wrong on our end. Our team has been notified and is working to fix the issue.</p>
        <p>You can try:</p>
        <ul>
            <li>Refreshing the page</li>
            <li>Going back to the previous page</li>
            <li>Returning to the home page</li>
        </ul>
        <p><a href="/" class="back-link">← Return to Home</a></p>
    </div>
</body>
</html>
"""

ERROR_400_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Bad Request</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
        .error { border: 1px solid #ff9800; padding: 20px; border-radius: 5px; background-color: #fff3e0; }
        .error h1 { color: #ff9800; margin-top: 0; }
        .error p { margin-bottom: 20px; }
        .back-link { color: #1976d2; text-decoration: none; }
        .back-link:hover { text-decoration: underline; }
    </style>
</head>
<body>
    <div class="error">
        <h1>Bad Request</h1>
        <p>The request you sent was invalid or malformed. Please check your input and try again.</p>
        <p><a href="/" class="back-link">← Return to Home</a></p>
    </div>
</body>
</html>
"""

ERROR_403_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Access Forbidden</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
        .error { border: 1px solid #f44336; padding: 20px; border-radius: 5px; background-color: #ffebee; }
        .error h1 { color: #f44336; margin-top: 0; }
        .error p { margin-bottom: 20px; }
        .back-link { color: #1976d2; text-decoration: none; }
        .back-link:hover { text-decoration: underline; }
    </style>
</head>
<body>
    <div class="error">
        <h1>Access Forbidden</h1>
        <p>You do not have permission to access this resource.</p>
        <p><a href="/" class="back-link">← Return to Home</a></p>
    </div>
</body>
</html>
"""

GENERIC_ERROR_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Error {code}</title>
    <style>
        body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }}
        .error {{ border: 1px solid #ddd; padding: 20px; border-radius: 5px; background-color: #f9f9f9; }}
        .error h1 {{ color: #d32f2f; margin-top: 0; }}
        .error p {{ margin-bottom: 20px; }}
        .back-link {{ color: #1976d2; text-decoration: none; }}
        .back-link:hover {{ text-decoration: underline; }}
    </style>
</head>
<body>
    <div class="error">
        <h1>Error {code}: {name}</h1>
        <p>{description}</p>
        <p><a href="/" class="back-link">← Return to Home</a></p>
    </div>
</body>
</html>
"""
