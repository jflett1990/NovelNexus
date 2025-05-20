# Installation Instructions

This document provides instructions for setting up and running the AI Manuscript Generator locally.

## Prerequisites

1. Python 3.11 or higher
2. Ollama installed and running (https://ollama.ai)
3. Required Ollama models pulled locally

## Setup

1. Clone this repository:
```
git clone <repository-url>
cd manuscript-generator
```

2. Create a virtual environment and activate it:
```
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install the required packages:
```
pip install flask flask-sqlalchemy gunicorn httpx langchain langchain-community langsmith openai psycopg2-binary python-dotenv werkzeug email-validator
```

4. Pull the required Ollama models:
```
ollama pull deepseek-v2:16b
ollama pull snowflake-arctic-embed:335m
```

5. Start the Ollama service:
```
ollama serve
```

6. Start the application:
```
python -m gunicorn --bind 0.0.0.0:5000 --reuse-port --reload main:app
```

## Configuration

The application can be configured using environment variables:

- `OLLAMA_BASE_URL`: URL for the Ollama API (default: http://localhost:11434)
- `SESSION_SECRET`: Secret key for session management (default: a development key)

You can create a `.env` file in the project root with these variables.

## Usage

1. Navigate to http://localhost:5000 in your web browser
2. Click "Start New Project" to begin generating a manuscript
3. Fill in the form with your desired parameters
4. Click "Start Generation" to begin the process

## Troubleshooting

- If you encounter connection issues with Ollama, make sure the Ollama service is running (`ollama serve`)
- If models are not available, make sure you've pulled them with the commands above
- Check the console logs for detailed error messages