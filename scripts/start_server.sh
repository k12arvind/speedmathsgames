#!/bin/bash
# =============================================================================
# Python Server Starter with Network Wait
# 
# This wrapper script ensures network is available before starting the server.
# Uses the venv_clat virtual environment for proper dependencies.
# =============================================================================

LOG_FILE="/Users/arvindkumar/clat_preparation/logs/server_startup.log"
PYTHON="/Users/arvindkumar/clat_preparation/venv_clat/bin/python"
SERVER="/Users/arvindkumar/clat_preparation/server/unified_server.py"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

# Wait for network (up to 2 minutes)
wait_for_network() {
    local retries=0
    local max_wait=60  # 60 x 2s = 120 seconds
    
    log "Waiting for network..."
    
    while [ $retries -lt $max_wait ]; do
        if ping -c 1 -W 2 8.8.8.8 > /dev/null 2>&1; then
            log "Network is available"
            return 0
        fi
        retries=$((retries + 1))
        sleep 2
    done
    
    log "ERROR: Network not available after 2 minutes"
    return 1
}

# Kill any existing server processes
cleanup_old_processes() {
    if pgrep -f "unified_server.py" > /dev/null 2>&1; then
        log "Killing old server processes..."
        pkill -f "unified_server.py" 2>/dev/null
        sleep 2
    fi
}

# Check if venv exists, create if not
ensure_venv() {
    if [ ! -f "$PYTHON" ]; then
        log "Virtual environment not found, creating..."
        cd /Users/arvindkumar/clat_preparation
        python3 -m venv venv_clat
        $PYTHON -m pip install --upgrade pip
        $PYTHON -m pip install anthropic requests PyPDF2 PyMuPDF python-dotenv beautifulsoup4 reportlab Pillow google-auth google-auth-oauthlib google-auth-httplib2 pyotp pandas
        log "Virtual environment created and packages installed"
    fi
}

# Load API key from .env file
load_api_key() {
    ENV_FILE="/Users/arvindkumar/clat_preparation/.env"
    if [ -f "$ENV_FILE" ]; then
        # Source the .env file to load environment variables
        set -a
        source "$ENV_FILE"
        set +a
        if [ -n "$ANTHROPIC_API_KEY" ]; then
            log "API key loaded from .env"
        else
            log "WARNING: ANTHROPIC_API_KEY not found in .env"
        fi
    else
        log "WARNING: .env file not found at $ENV_FILE"
    fi
}

# Main
log "=========================================="
log "Starting unified server..."

# Load API key
load_api_key

# Wait for network (optional - server can work offline for local access)
# Uncomment if you want to wait: wait_for_network

# Ensure venv exists
ensure_venv

# Clean up old processes
cleanup_old_processes

# Set working directory
cd /Users/arvindkumar/clat_preparation

# Set HOME explicitly (may not be set during early boot)
export HOME="/Users/arvindkumar"

# Disable user site-packages to ensure only venv packages are used
export PYTHONNOUSERSITE=1

# Set VIRTUAL_ENV and update PATH to ensure proper venv activation
export VIRTUAL_ENV="/Users/arvindkumar/clat_preparation/venv_clat"
export PATH="$VIRTUAL_ENV/bin:$PATH"

# DEBUG: Log which Python will be used
log "VIRTUAL_ENV: $VIRTUAL_ENV"
log "PYTHONNOUSERSITE: $PYTHONNOUSERSITE"
log "PYTHON variable: $PYTHON"
log "Python exists: $(test -f $PYTHON && echo 'yes' || echo 'no')"
log "Which python3: $(which python3)"

# Start server using explicit venv python path (with unbuffered output)
log "Starting Python server daemon with $PYTHON..."
export PYTHONUNBUFFERED=1
exec "$PYTHON" "$SERVER"

