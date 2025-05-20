# AI Manuscript Generator

A modular, agent-based AI framework for generating full-length manuscripts using Ollama models with dynamic memory implementation.

## Overview

This application provides a comprehensive framework for generating complete manuscripts using specialized AI agents for different stages of the writing process.

### Key Features

- **Agent-Based Architecture**: Specialized agents for ideation, character development, world-building, outlining, writing, revision, and editorial tasks
- **Ollama Integration**: Uses Ollama models for text generation and embeddings
  - `deepseek-v2:16b` for primary text generation
  - `snowflake-arctic-embed:335m` for embeddings
- **Dynamic Memory**: Maintains context across long-form content generation
- **Flexible Workflow**: Non-linear workflow with feedback loops between stages
- **Web Interface**: User-friendly interface for configuring and monitoring manuscript generation

## Getting Started

See [INSTALL.md](INSTALL.md) for detailed setup instructions.

### Quick Start

1. Install Ollama and pull required models:
   ```
   ollama pull deepseek-v2:16b
   ollama pull snowflake-arctic-embed:335m
   ```

2. Run the application:
   ```
   python -m gunicorn --bind 0.0.0.0:5000 --reuse-port --reload main:app
   ```

3. Visit http://localhost:5000 in your browser

## Architecture

The application uses a modular agent architecture:

- **Ideation Agent**: Generates initial book concepts and themes
- **Character Agent**: Creates and develops characters with personalities and arcs
- **World Building Agent**: Constructs the setting and environment for the story
- **Research Agent**: Gathers and organizes relevant information for the manuscript
- **Outline Agent**: Creates detailed chapter outlines and plot structures
- **Writing Agent**: Generates the actual prose content of chapters
- **Review Agent**: Analyzes and critiques written content
- **Revision Agent**: Improves content based on review feedback
- **Editorial Agent**: Handles final refinements and assembles the complete manuscript

All agents are connected through a central hub and dynamic memory system to maintain consistency across the manuscript.

## License

This project is licensed under the MIT License - see the LICENSE file for details.# NovelNexus
