#!/bin/bash

echo "🌟 Starting NovelNexus Enhanced Workflow"
echo "========================================"

# Check if MCP server is running
echo "🔍 Checking OpenMemory MCP Server..."
if curl -s http://localhost:3434/health > /dev/null 2>&1; then
    echo "✅ OpenMemory MCP Server is running"
else
    echo "⚠️  OpenMemory MCP Server not detected"
    echo "   Starting MCP server in background..."
    
    # Start MCP server in background
    ./start_mcp_server.sh &
    MCP_PID=$!
    
    # Wait for server to start
    echo "   Waiting for MCP server to start..."
    sleep 5
    
    # Check again
    if curl -s http://localhost:3434/health > /dev/null 2>&1; then
        echo "✅ OpenMemory MCP Server started successfully"
    else
        echo "❌ Failed to start OpenMemory MCP Server"
        echo "   Please start it manually: ./start_mcp_server.sh"
        exit 1
    fi
fi

echo ""
echo "🎯 Starting NovelNexus with Enhanced Features..."
echo "Enhanced features enabled:"
echo "  ✅ Human-in-the-Loop Reviews"
echo "  ✅ OpenMemory MCP Integration"
echo "  ✅ Quality Control Gates"
echo "  ✅ Plot Consistency Checking"
echo ""
echo "Access the application at: http://localhost:5000"
echo "Access review interface at: http://localhost:5000/review/<project_id>"
echo "Access MCP dashboard at: http://localhost:3434/dashboard"
echo ""

# Start the main application
python app.py --debug
