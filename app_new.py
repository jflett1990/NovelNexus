"""
Main application entry point for NovelNexus.

This is the new, refactored main application file that uses the modular
architecture with proper separation of concerns.
"""

import argparse
import logging
from core import create_app, create_celery_app, cleanup_extensions
from config import config

# Create application instances
app = create_app()
celery_app = create_celery_app(app)

logger = logging.getLogger(__name__)

def main():
    """Main application entry point."""
    parser = argparse.ArgumentParser(description='AI Manuscript Generator')
    parser.add_argument('--port', type=int, default=config.flask_port, help='Port to run the server on')
    parser.add_argument('--host', type=str, default=config.flask_host, help='Host to run the server on')
    parser.add_argument('--debug', action='store_true', default=config.flask_debug, help='Run in debug mode')
    args = parser.parse_args()
    
    try:
        print(f"Starting {config.app_name} v{config.app_version}")
        print(f"Server running on {args.host}:{args.port} with debug={args.debug}")
        print(f"Environment: {config.__class__.__name__}")
        
        # Run the Flask application
        app.run(host=args.host, port=args.port, debug=args.debug)
        
    except KeyboardInterrupt:
        print("\nShutting down gracefully...")
        cleanup_extensions()
    except Exception as e:
        logger.error(f"Application startup failed: {str(e)}", exc_info=True)
        cleanup_extensions()
        raise

if __name__ == "__main__":
    main()
