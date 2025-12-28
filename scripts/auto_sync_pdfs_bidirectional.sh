#!/bin/bash
#
# auto_sync_pdfs_bidirectional.sh
# 
# Bidirectional sync of ~/saanvi PDF folders between MacBook Pro and Mac Mini
# This handles:
# - New PDFs added on MacBook Pro → sync to Mac Mini
# - PDF edits made on Mac Mini (via web app) → sync back to MacBook Pro
#
# Usage: 
#   ./auto_sync_pdfs_bidirectional.sh           # Interactive mode
#   ./auto_sync_pdfs_bidirectional.sh --quiet   # Quiet mode for cron
#
# To set up automatic sync (every 30 minutes), add to crontab:
#   crontab -e
#   */30 * * * * $HOME/clat_preparation/scripts/auto_sync_pdfs_bidirectional.sh --quiet >> /tmp/pdf_sync.log 2>&1
#

set -e

QUIET=${1:-""}
REMOTE="mac-mini"
LOCAL_BASE="$HOME/saanvi"
REMOTE_BASE="~/saanvi"
FOLDERS=("Legaledgedailygk" "LegalEdgeweeklyGK" "weeklyGKCareerLauncher")
LOCK_FILE="/tmp/pdf_sync.lock"

log() {
    if [ "$QUIET" != "--quiet" ]; then
        echo "$1"
    fi
}

# Prevent concurrent runs
if [ -f "$LOCK_FILE" ]; then
    log "⚠️  Sync already in progress (lock file exists)"
    exit 0
fi

trap "rm -f $LOCK_FILE" EXIT
touch "$LOCK_FILE"

log "🔄 Starting bidirectional PDF sync..."
log "   Local:  $LOCAL_BASE"
log "   Remote: $REMOTE:$REMOTE_BASE"
log ""

SYNC_COUNT=0
ERROR_COUNT=0

for folder in "${FOLDERS[@]}"; do
    log "📁 Syncing $folder..."
    
    LOCAL_PATH="$LOCAL_BASE/$folder/"
    REMOTE_PATH="$REMOTE:$REMOTE_BASE/$folder/"
    
    # Check if local folder exists
    if [ ! -d "$LOCAL_BASE/$folder" ]; then
        log "   ⚠️  Local folder doesn't exist, skipping"
        continue
    fi
    
    # Step 1: Local → Remote (send new/updated files)
    # -a: archive mode (preserves permissions, timestamps)
    # -v: verbose
    # -z: compress during transfer
    # -u: update only (skip newer files on receiver)
    if rsync -avzu --timeout=30 "$LOCAL_PATH" "$REMOTE_PATH" 2>/dev/null; then
        log "   ✅ Local → Remote: OK"
    else
        log "   ❌ Local → Remote: FAILED"
        ((ERROR_COUNT++))
    fi
    
    # Step 2: Remote → Local (receive edits from Mac Mini)
    if rsync -avzu --timeout=30 "$REMOTE_PATH" "$LOCAL_PATH" 2>/dev/null; then
        log "   ✅ Remote → Local: OK"
    else
        log "   ❌ Remote → Local: FAILED"
        ((ERROR_COUNT++))
    fi
    
    ((SYNC_COUNT++))
done

log ""
if [ $ERROR_COUNT -eq 0 ]; then
    log "✅ Sync complete! $SYNC_COUNT folders synced."
else
    log "⚠️  Sync completed with $ERROR_COUNT errors"
fi

# Timestamp for logging
if [ "$QUIET" == "--quiet" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Sync complete: $SYNC_COUNT folders, $ERROR_COUNT errors"
fi

