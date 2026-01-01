#!/bin/bash
# safe_pull.sh - Safe deployment script that backs up databases before git pull
#
# Usage: ./scripts/safe_pull.sh
#
# This script:
# 1. Backs up all .db files before pulling
# 2. Runs git pull
# 3. Restarts the server
# 4. Verifies database health
#
# Created to prevent data loss after root cause analysis (Jan 2026)

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="$PROJECT_DIR/backups/pre-pull"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo ""
echo "=============================================="
echo "   SAFE PULL - Database-Protected Deployment"
echo "=============================================="
echo ""

cd "$PROJECT_DIR"

# Step 1: Create backup directory
mkdir -p "$BACKUP_DIR"
echo -e "${YELLOW}Step 1: Backing up databases...${NC}"

BACKUP_COUNT=0
for db in *.db; do
    if [ -f "$db" ]; then
        cp "$db" "$BACKUP_DIR/${db}.${TIMESTAMP}"
        echo "  ✅ Backed up: $db"
        BACKUP_COUNT=$((BACKUP_COUNT + 1))
    fi
done

# Also backup server/*.db if exists
for db in server/*.db; do
    if [ -f "$db" ]; then
        mkdir -p "$BACKUP_DIR/server"
        cp "$db" "$BACKUP_DIR/server/$(basename $db).${TIMESTAMP}"
        echo "  ✅ Backed up: $db"
        BACKUP_COUNT=$((BACKUP_COUNT + 1))
    fi
done

echo "  📦 Total backups: $BACKUP_COUNT"
echo ""

# Step 2: Show current database stats
echo -e "${YELLOW}Step 2: Current database stats...${NC}"
if [ -f "math_tracker.db" ]; then
    MATH_COUNT=$(sqlite3 math_tracker.db 'SELECT COUNT(*) FROM math_questions;' 2>/dev/null || echo "0")
    echo "  📊 Math questions: $MATH_COUNT"
fi
if [ -f "revision_tracker.db" ]; then
    PDF_COUNT=$(sqlite3 revision_tracker.db 'SELECT COUNT(*) FROM pdfs;' 2>/dev/null || echo "0")
    echo "  📊 GK PDFs: $PDF_COUNT"
fi
echo ""

# Step 3: Git pull
echo -e "${YELLOW}Step 3: Pulling latest code...${NC}"
git pull
echo ""

# Step 4: Verify databases still have data
echo -e "${YELLOW}Step 4: Verifying databases...${NC}"
HEALTHY=true

if [ -f "math_tracker.db" ]; then
    NEW_MATH_COUNT=$(sqlite3 math_tracker.db 'SELECT COUNT(*) FROM math_questions;' 2>/dev/null || echo "0")
    if [ "$NEW_MATH_COUNT" -lt 300 ]; then
        echo -e "  ${RED}⚠️  Math questions: $NEW_MATH_COUNT (was $MATH_COUNT)${NC}"
        HEALTHY=false
    else
        echo -e "  ${GREEN}✅ Math questions: $NEW_MATH_COUNT${NC}"
    fi
else
    echo -e "  ${RED}❌ math_tracker.db not found!${NC}"
    HEALTHY=false
fi

if [ -f "revision_tracker.db" ]; then
    NEW_PDF_COUNT=$(sqlite3 revision_tracker.db 'SELECT COUNT(*) FROM pdfs;' 2>/dev/null || echo "0")
    if [ "$NEW_PDF_COUNT" -lt 10 ]; then
        echo -e "  ${RED}⚠️  GK PDFs: $NEW_PDF_COUNT (was $PDF_COUNT)${NC}"
        HEALTHY=false
    else
        echo -e "  ${GREEN}✅ GK PDFs: $NEW_PDF_COUNT${NC}"
    fi
fi
echo ""

# Step 5: Restart server
echo -e "${YELLOW}Step 5: Restarting server...${NC}"
pkill -f unified_server.py 2>/dev/null || true
sleep 2

# Start server
VENV_PYTHON="$PROJECT_DIR/venv_clat/bin/python"
if [ -f "$VENV_PYTHON" ]; then
    nohup "$VENV_PYTHON" "$PROJECT_DIR/server/unified_server.py" > "$PROJECT_DIR/logs/server.log" 2>&1 &
    echo "  ✅ Server started with venv Python"
else
    nohup python3 "$PROJECT_DIR/server/unified_server.py" > "$PROJECT_DIR/logs/server.log" 2>&1 &
    echo "  ✅ Server started with system Python"
fi

sleep 3

# Verify server is running
if pgrep -f unified_server.py > /dev/null; then
    echo -e "  ${GREEN}✅ Server is running${NC}"
else
    echo -e "  ${RED}❌ Server failed to start! Check logs/server.log${NC}"
fi
echo ""

# Final summary
echo "=============================================="
if [ "$HEALTHY" = true ]; then
    echo -e "${GREEN}✅ DEPLOYMENT SUCCESSFUL${NC}"
else
    echo -e "${YELLOW}⚠️  DEPLOYMENT COMPLETE WITH WARNINGS${NC}"
    echo ""
    echo "Backups available at: $BACKUP_DIR"
    echo "To restore: cp $BACKUP_DIR/<file>.${TIMESTAMP} ./<file>"
fi
echo "=============================================="
echo ""

# Cleanup old backups (keep last 10)
echo "Cleaning up old backups (keeping last 10)..."
cd "$BACKUP_DIR"
ls -t *.db.* 2>/dev/null | tail -n +11 | xargs rm -f 2>/dev/null || true
echo "Done."

