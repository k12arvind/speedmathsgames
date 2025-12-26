#!/bin/bash
# Start CLAT Preparation Server
# This script launches the unified server from the reorganized structure

cd "$(dirname "$0")"

echo "Starting CLAT Preparation Server..."
echo "Server directory: $(pwd)"
echo ""

# Activate virtual environment
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found. Please create it first:"
    echo "   python3 -m venv venv"
    echo "   source venv/bin/activate"
    echo "   pip install -r requirements.txt"
    exit 1
fi

source venv/bin/activate
echo "✅ Virtual environment activated"
echo ""

# Check if running with authentication or not
if [ "$1" = "--no-auth" ]; then
    echo "⚠️  Starting WITHOUT authentication"
    python3 server/unified_server.py --port 8001 --no-auth
else
    echo "🔒 Starting WITH Google OAuth authentication"
    python3 server/unified_server.py --port 8001
fi
