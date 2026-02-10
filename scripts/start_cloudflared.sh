#!/bin/bash
# =============================================================================
# Cloudflared Tunnel Starter with Network Wait
#
# This wrapper script ensures network is available before starting cloudflared.
# Important for recovery after power cuts when router takes time to boot.
#
# NOTE: Do NOT kill existing processes here - launchd manages process lifecycle.
# Killing processes causes restart loops.
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

# Main
log "=========================================="
log "Starting cloudflared tunnel..."

# Wait for network
if ! wait_for_network; then
    exit 1
fi

# Start cloudflared (exec replaces this script with cloudflared)
log "Starting cloudflared tunnel daemon..."
exec /opt/homebrew/bin/cloudflared tunnel \
    --config /Users/arvindkumar/.cloudflared/config.yml \
    run speedmathsgames-tunnel

