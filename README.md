# NovelNexus - AI Manuscript Generator

A modular, agent-based AI framework for generating full-length manuscripts using a sophisticated memory system and specialized writing agents.

## Overview

NovelNexus is a comprehensive platform for generating complete manuscripts using specialized AI agents for different stages of the writing process. The system uses LLM-powered agents to handle discrete aspects of manuscript creation while maintaining consistency through a central memory system.

### Key Features

- **Agent-Based Architecture**: Specialized agents for ideation, character development, world-building, outlining, writing, revision, and editorial tasks
- **OpenAI Integration**: Primary support for OpenAI models with fallback capabilities
- **Dynamic Memory System**: Semantic vector search for context consistency across the entire manuscript development process
- **Flexible Workflow**: Non-linear workflow with recovery mechanisms and feedback loops
- **Web Interface**: User-friendly dashboard for configuring and monitoring manuscript generation
- **Asynchronous Processing**: Background task handling for long-running generations

## Getting Started

See [INSTALL.md](INSTALL.md) for detailed setup instructions.

### Quick Start

1. Install dependencies:
   ```
   pip install -r dependencies.txt
   ```

2. Set up environment variables:
   ```
   cp .env.example .env
   # Edit .env with your API keys
   ```

3. Run the application:
   ```
   bash run_app.sh
   ```

4. Visit http://localhost:5000 in your browser

## System Architecture

NovelNexus uses a modular architecture with several key components:

### Agent Layer

Specialized agents that perform discrete tasks in the manuscript generation pipeline:

- **Ideation Agent**: Generates initial book concepts and themes
- **Character Agent**: Creates and develops characters with personalities and arcs
- **World Building Agent**: Constructs the setting and environment for the story
- **Research Agent**: Gathers and organizes relevant information for the manuscript
- **Outline Agent**: Creates detailed chapter outlines and plot structures
- **Chapter Planner Agent**: Plans individual chapters with scene breakdown
- **Chapter Writer Agent**: Generates the actual prose content of chapters
- **Review Agent**: Analyzes and critiques written content
- **Revision Agent**: Improves content based on review feedback
- **Editorial Agent**: Handles final refinements and assembles the complete manuscript

### Memory Layer

The Dynamic Memory system provides:

- Semantic search capabilities using vector embeddings
- Context recall across the entire generation process
- Thread-safe data persistence
- Automatic embedding model versioning

### Orchestration Layer

Components that manage workflow and data flow:

- **Central Hub**: Aggregates and manages data flow between agents
- **Manuscript Workflow**: Controls the pipeline execution and error handling
- **Recovery Mechanisms**: Ensures graceful failure handling

### Web Interface

Flask-based web application providing:

- Project configuration
- Real-time progress monitoring
- Manuscript viewing and export
- Error reporting and debugging

## Manuscript Generation Pipeline

The manuscript generation pipeline follows these key stages:

1. **Ideation**: Generate initial book concepts
2. **Character Development**: Create characters and relationships
3. **World Building**: Define the setting and world rules
4. **Research**: Gather relevant factual information
5. **Outlining**: Create a structural outline
6. **Chapter Planning**: Plan individual chapters
7. **Writing**: Generate the manuscript content
8. **Review & Revision**: Polish and improve the content
9. **Editorial**: Finalize the manuscript

## Error Handling and Recovery

NovelNexus includes sophisticated error handling:

- Systematic error capturing and reporting
- Agent-specific recovery strategies
- Fallback content generation for failed stages
- Detailed error logging and diagnostics

## API Documentation

### Main Endpoints

- `GET /` - Home page 
- `GET /dashboard/<project_id>` - Project dashboard
- `POST /generate` - Start manuscript generation
- `GET /api/project/<project_id>/status` - Get project status
- `GET /api/dashboard-data/<project_id>` - Get dashboard data
- `GET /api/manuscript/<project_id>` - Get manuscript content
- `GET /view-manuscript/<project_id>` - View manuscript in browser

### Status Monitoring

- `GET /api/project/<project_id>/logs` - Get project logs
- `GET /api/stream-logs/<project_id>` - Stream logs with SSE
- `POST /api/project/<project_id>/reset-thread` - Reset workflow thread

## Advanced Features

### Asynchronous Processing

NovelNexus supports Celery for asynchronous processing:

```python
# Start an async task
task = run_workflow_task.delay(project_id=project_id, **config)
```

### Memory Persistence

Data is stored in a thread-safe manner:

```python
# Access data from memory
data = memory.query_memory("type:character", agent_name="character_agent")
```

### Custom Agent Development

Create custom agents by extending the AbstractAgent class:

```python
from agents.agent_prototype import AbstractAgent

class CustomAgent(AbstractAgent):
    def execute(self, **kwargs):
        # Implementation goes here
        pass
```

## Testing

Run the test suite:

```
python -m unittest discover tests
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.
