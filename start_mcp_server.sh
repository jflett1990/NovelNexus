#!/bin/bash

# Start OpenMemory MCP Server for NovelNexus
echo "🧠 Starting OpenMemory MCP Server..."
echo "Server will be available at: http://localhost:3434"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Check if mem0-repo exists and try to run from there
if [ -d "mem0-repo/openmemory" ]; then
    echo "📁 Using local mem0 repository..."
    cd mem0-repo/openmemory

    # Install dependencies if needed
    if [ ! -d "node_modules" ]; then
        echo "📦 Installing dependencies..."
        npm install
    fi

    # Start the server
    npm start
else
    echo "⚠️  OpenMemory MCP Server not available"
    echo "   Running NovelNexus with basic memory instead"
    echo "   Enhanced features will use fallback memory system"

    # Create a simple mock server for testing
    python3 -c "
import http.server
import socketserver
import json

class MockMCPHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'status': 'ok', 'mock': True}).encode())
        else:
            super().do_GET()

PORT = 3434
with socketserver.TCPServer(('', PORT), MockMCPHandler) as httpd:
    print(f'Mock MCP server running on port {PORT}')
    httpd.serve_forever()
"
fi
