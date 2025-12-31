#!/bin/bash
# =============================================================================
# Health Monitor for speedmathsgames.com
# 
# This script runs every 2 minutes via launchd to ensure:
# 1. Network is available
# 2. Python server is running and responding
# 3. Cloudflared tunnel is connected
#
# After power cuts, it waits for network and restarts services if needed
# =============================================================================

LOG_FILE="/Users/arvindkumar/clat_preparation/logs/health_monitor.log"
SITE_URL="http://localhost:8001/api/stats"
EXTERNAL_URL="https://speedmathsgames.com"
MAX_RETRIES=3

# Ensure log directory exists
mkdir -p "$(dirname "$LOG_FILE")"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

# Rotate log if > 1MB
if [ -f "$LOG_FILE" ] && [ $(stat -f%z "$LOG_FILE" 2>/dev/null || echo 0) -gt 1048576 ]; then
    mv "$LOG_FILE" "${LOG_FILE}.old"
fi

# =============================================================================
# STEP 1: Wait for network to be available (important after power cut)
# =============================================================================
wait_for_network() {
    local retries=0
    local max_wait=30  # Wait up to 30 attempts (60 seconds)
    
    while [ $retries -lt $max_wait ]; do
        # Try to ping Google DNS
        if ping -c 1 -W 2 8.8.8.8 > /dev/null 2>&1; then
            return 0
        fi
        retries=$((retries + 1))
        sleep 2
    done
    
    log "ERROR: Network not available after 60 seconds"
    return 1
}

# =============================================================================
# STEP 2: Check if local server is responding
# =============================================================================
check_local_server() {
    local response=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 "$SITE_URL" 2>/dev/null)
    if [ "$response" = "200" ]; then
        return 0
    fi
    return 1
}

# =============================================================================
# STEP 3: Check if external site is accessible via Cloudflare
# =============================================================================
check_external_site() {
    local response=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 10 "$EXTERNAL_URL" 2>/dev/null)
    if [ "$response" = "200" ] || [ "$response" = "302" ]; then
        return 0
    fi
    return 1
}

# =============================================================================
# STEP 4: Restart services if needed
# =============================================================================
restart_server() {
    log "Restarting Python server..."
    launchctl kickstart -k gui/$(id -u)/com.clatprep.server 2>/dev/null || \
    launchctl stop com.clatprep.server 2>/dev/null
    sleep 2
    launchctl start com.clatprep.server 2>/dev/null
    sleep 3
}

restart_cloudflared() {
    log "Restarting Cloudflared tunnel..."
    # Kill any stuck processes
    pkill -f cloudflared 2>/dev/null
    sleep 2
    # Restart via launchctl
    launchctl start com.cloudflare.tunnel 2>/dev/null
    sleep 5
}

# =============================================================================
# MAIN HEALTH CHECK
# =============================================================================
main() {
    # Wait for network first (handles power cut recovery)
    if ! wait_for_network; then
        exit 1
    fi
    
    # Check local server
    if ! check_local_server; then
        log "WARNING: Local server not responding"
        restart_server
        sleep 5
        
        # Retry check
        if ! check_local_server; then
            log "ERROR: Server still not responding after restart"
        else
            log "SUCCESS: Server recovered after restart"
        fi
    fi
    
    # Check external site (Cloudflare tunnel)
    if ! check_external_site; then
        log "WARNING: External site not accessible (Cloudflare tunnel issue)"
        restart_cloudflared
        sleep 10
        
        # Retry check
        if ! check_external_site; then
            log "ERROR: External site still not accessible after cloudflared restart"
        else
            log "SUCCESS: Cloudflare tunnel recovered after restart"
        fi
    fi
}

# Run main function
main

