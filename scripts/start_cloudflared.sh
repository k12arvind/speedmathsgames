#!/bin/bash
# =============================================================================
# Cloudflared Tunnel Starter with Network Wait
# 
# This wrapper script ensures network is available before starting cloudflared.
# Important for recovery after power cuts when router takes time to boot.
# =============================================================================

LOG_FILE="/Users/arvindkumar/clat_preparation/logs/cloudflared_startup.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

# Wait for network (up to 2 minutes)
wait_for_network() {
    local retries=0
    local max_wait=60  # 60 x 2s = 120 seconds
    
    log "Waiting for network..."
    
    while [ $retries -lt $max_wait ]; do
        # Check if we can reach Cloudflare
        if ping -c 1 -W 2 1.1.1.1 > /dev/null 2>&1; then
            log "Network is available"
            return 0
        fi
        retries=$((retries + 1))
        sleep 2
    done
    
    log "ERROR: Network not available after 2 minutes"
    return 1
}

# Kill any existing cloudflared processes to avoid conflicts
cleanup_old_processes() {
    if pgrep -f "cloudflared.*tunnel" > /dev/null 2>&1; then
        log "Killing old cloudflared processes..."
        pkill -f "cloudflared.*tunnel" 2>/dev/null
        sleep 3
    fi
}

# Main
log "=========================================="
log "Starting cloudflared tunnel..."

# Wait for network
if ! wait_for_network; then
    exit 1
fi

# Clean up old processes
cleanup_old_processes

# Start cloudflared (exec replaces this script with cloudflared)
log "Starting cloudflared tunnel daemon..."
exec /opt/homebrew/bin/cloudflared tunnel \
    --config /Users/arvindkumar/.cloudflared/config.yml \
    run speedmathsgames-tunnel

