#!/bin/bash
# =============================================================================
# Deploy Resilient Services on Mac Mini
# 
# This script sets up:
# 1. Health monitor (runs every 2 minutes)
# 2. Cloudflared with network wait
# 3. Python server with auto-restart
# 4. Configures Mac Mini to auto-start after power loss
# =============================================================================

echo "=========================================="
echo "Deploying Resilient Services"
echo "=========================================="

SCRIPTS_DIR="$HOME/clat_preparation/scripts"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
LOGS_DIR="$HOME/clat_preparation/logs"

# Create logs directory
mkdir -p "$LOGS_DIR"

# Make scripts executable
echo ""
echo "1. Making scripts executable..."
chmod +x "$SCRIPTS_DIR/health_monitor.sh"
chmod +x "$SCRIPTS_DIR/start_cloudflared.sh"
chmod +x "$SCRIPTS_DIR/start_server.sh"

# Stop existing services
echo ""
echo "2. Stopping existing services..."
launchctl unload "$LAUNCH_AGENTS_DIR/com.clatprep.healthmonitor.plist" 2>/dev/null
launchctl unload "$LAUNCH_AGENTS_DIR/com.cloudflare.tunnel.plist" 2>/dev/null
launchctl unload "$LAUNCH_AGENTS_DIR/com.clatprep.server.plist" 2>/dev/null
launchctl unload "$LAUNCH_AGENTS_DIR/com.clatprep.dailysummary.plist" 2>/dev/null
pkill -f unified_server.py 2>/dev/null
pkill -f cloudflared 2>/dev/null
sleep 3

# Copy LaunchAgent plists
echo ""
echo "3. Installing LaunchAgent configurations..."
cp "$SCRIPTS_DIR/com.clatprep.healthmonitor.plist" "$LAUNCH_AGENTS_DIR/"
cp "$SCRIPTS_DIR/com.cloudflare.tunnel.plist" "$LAUNCH_AGENTS_DIR/"
cp "$SCRIPTS_DIR/com.clatprep.server.plist" "$LAUNCH_AGENTS_DIR/"
cp "$SCRIPTS_DIR/com.clatprep.dailysummary.plist" "$LAUNCH_AGENTS_DIR/"

# Load services
echo ""
echo "4. Loading services..."
launchctl load "$LAUNCH_AGENTS_DIR/com.clatprep.server.plist"
sleep 3
launchctl load "$LAUNCH_AGENTS_DIR/com.cloudflare.tunnel.plist"
sleep 5
launchctl load "$LAUNCH_AGENTS_DIR/com.clatprep.healthmonitor.plist"
launchctl load "$LAUNCH_AGENTS_DIR/com.clatprep.dailysummary.plist"

# Verify services
echo ""
echo "5. Verifying services..."
sleep 3

echo ""
echo "=== Service Status ==="
if pgrep -f "unified_server.py" > /dev/null; then
    echo "✅ Python Server: Running"
else
    echo "❌ Python Server: NOT running"
fi

if pgrep -f "cloudflared" > /dev/null; then
    echo "✅ Cloudflared: Running"
else
    echo "❌ Cloudflared: NOT running"
fi

# Check local server
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/api/stats 2>/dev/null)
if [ "$HTTP_CODE" = "200" ]; then
    echo "✅ Local API: Responding (HTTP 200)"
else
    echo "⚠️  Local API: HTTP $HTTP_CODE"
fi

echo ""
echo "=== LaunchAgents Loaded ==="
launchctl list | grep -E "clatprep|cloudflare"

echo ""
echo "=========================================="
echo "Deployment Complete!"
echo ""
echo "Services will now:"
echo "  • Auto-start on boot"
echo "  • Auto-restart if they crash"
echo "  • Wait for network after power cuts"
echo "  • Health monitor runs every 2 minutes"
echo ""
echo "Logs are in: $LOGS_DIR"
echo "=========================================="

# Reminder about auto-boot
echo ""
echo "📋 IMPORTANT: To enable Mac Mini auto-boot after power loss:"
echo "   System Settings > Energy Saver > 'Start up automatically after a power failure'"
echo ""

