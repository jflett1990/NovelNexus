#!/bin/bash

# Kill any existing Python processes running app.py
echo "Checking for existing Flask servers..."
pkill -f "python app.py" || echo "No existing Flask servers found"

# Wait a moment for ports to be released
sleep 1

# Try different ports if default is taken
for port in 5001 5002 5003 5004 5005; do
  echo "Attempting to start server on port $port..."
  python app.py --port $port
  
  # If server started successfully, exit the loop
  if [ $? -eq 0 ]; then
    break
  fi
  
  echo "Port $port is in use, trying next port..."
  sleep 1
done 