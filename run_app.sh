#!/bin/bash

# Check if Redis is installed
if ! command -v redis-server &> /dev/null; then
    echo "WARNING: Redis server not found. Celery background processing will be disabled."
    echo "Install Redis to enable background processing: https://redis.io/download"
    USE_CELERY=false
else
    USE_CELERY=true
fi

# Check if Celery is installed
if ! command -v celery &> /dev/null; then
    echo "WARNING: Celery not found. Background processing will be disabled."
    echo "Install Celery with: pip install celery redis"
    USE_CELERY=false
fi

# Kill any existing Python processes and Celery workers
echo "Checking for existing Flask servers and Celery workers..."
pkill -f "python app.py" || echo "No existing Flask servers found"
pkill -f "celery.*worker" || echo "No existing Celery workers found"

# Wait a moment for ports to be released
sleep 1

# Start Redis if available but not running
if [ "$USE_CELERY" = true ]; then
    if ! pgrep redis-server > /dev/null; then
        echo "Starting Redis server..."
        redis-server --daemonize yes
        sleep 1
    fi
    
    # Start Celery worker in the background
    echo "Starting Celery workers..."
    celery -A celery_config.celery_app worker --loglevel=info -Q workflow_queue,agent_queue --concurrency=2 &
    CELERY_PID=$!
    echo "Celery workers started with PID: $CELERY_PID"
    
    # Export the Celery worker PID to make it easier to kill later
    export NOVELAI_CELERY_PID=$CELERY_PID
    
    echo "You can stop Celery workers with: kill $CELERY_PID"
fi

# Try different ports if default is taken
for port in 5000 5001 5002 5003 5004 5005; do
  echo "Attempting to start server on port $port..."
  python app.py --port $port
  
  # If server started successfully, exit the loop
  if [ $? -eq 0 ]; then
    break
  fi
  
  echo "Port $port is in use, trying next port..."
  sleep 1
done

# Function to clean up processes on exit
cleanup() {
    echo "Shutting down services..."
    if [ "$USE_CELERY" = true ]; then
        echo "Stopping Celery workers..."
        kill $CELERY_PID 2>/dev/null || echo "Celery workers already stopped"
    fi
    echo "Cleanup complete."
}

# Register the cleanup function to run on script exit
trap cleanup EXIT 