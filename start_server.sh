#!/bin/bash
# Start CLAT Preparation Server
# This script launches the unified server from the reorganized structure

cd "$(dirname "$0")"

echo "Starting CLAT Preparation Server..."
echo "Server directory: $(pwd)"
echo ""

# Check if running with authentication or not
if [ "$1" = "--no-auth" ]; then
    echo "⚠️  Starting WITHOUT authentication"
    python3 server/unified_server.py --port 8001 --no-auth
else
    echo "🔒 Starting WITH Google OAuth authentication"
    python3 server/unified_server.py --port 8001
fi
