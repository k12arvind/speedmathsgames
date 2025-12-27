#!/bin/bash

# Start unified server with venv

cd /Users/arvind/clat_preparation

# Kill any existing server process
lsof -ti:8001 | xargs kill -9 2>/dev/null

# Activate venv and start server
source venv_clat/bin/activate
nohup python3 server/unified_server.py > /tmp/server.log 2>&1 &

sleep 2

# Check if server started
if curl -s http://localhost:8001/api/test >/dev/null 2>&1; then
    echo "✅ Server started successfully on http://localhost:8001"
    echo "📋 Logs: tail -f /tmp/server.log"
else
    echo "❌ Server failed to start. Check logs:"
    tail -20 /tmp/server.log
    exit 1
fi
