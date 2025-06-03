"""
Celery configuration for NovelNexus.
"""

import os
from celery import Celery
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure Celery application
celery_app = Celery('novelNexus')

# Default configuration
default_config = {
    'broker_url': os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
    'result_backend': os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0'),
    'task_serializer': 'json',
    'accept_content': ['json'],
    'result_serializer': 'json',
    'enable_utc': True,
    'task_track_started': True,
    'task_time_limit': 18000,  # 5 hours max task time
    'worker_max_tasks_per_child': 1,  # Avoid memory leaks
    # Redis visibility timeout (how long tasks are claimed by workers)
    'broker_transport_options': {'visibility_timeout': 21600},  # 6 hours
    # Task routing (can be extended for different worker types)
    'task_routes': {
        'app.run_workflow_task': {'queue': 'workflow_queue'},
        'app.run_agent_task': {'queue': 'agent_queue'}
    }
}

# Apply configuration
celery_app.conf.update(default_config)

# Import tasks to ensure they're registered with Celery
from app import run_workflow_task

# Define startup command for Celery workers
# Run with: celery -A celery_config.celery_app worker --loglevel=info -Q workflow_queue,agent_queue 