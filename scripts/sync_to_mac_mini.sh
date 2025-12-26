#!/bin/bash
# Sync CLAT preparation files from MacBook Pro to Mac Mini
# This maintains a single source of truth on the MacBook Pro

set -e

echo "======================================================================"
echo "  Syncing CLAT Preparation: MacBook Pro → Mac Mini"
echo "======================================================================"
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 1. Sync all code directories
echo -e "${YELLOW}Step 1: Syncing code directories...${NC}"
rsync -avz --exclude='__pycache__' --exclude='*.pyc' --exclude='.git' \
    --exclude='venv' --exclude='*.db' --exclude='logs' --exclude='processing_status' \
    ~/clat_preparation/server/ \
    mac-mini:~/clat_preparation/server/
rsync -avz ~/clat_preparation/pdf_generation/ \
    mac-mini:~/clat_preparation/pdf_generation/
rsync -avz ~/clat_preparation/utils/ \
    mac-mini:~/clat_preparation/utils/
rsync -avz ~/clat_preparation/scripts/ \
    mac-mini:~/clat_preparation/scripts/
echo -e "${GREEN}✓ Code synced${NC}"
echo ""

# 2. Sync dashboard
echo -e "${YELLOW}Step 2: Syncing dashboard files...${NC}"
rsync -avz ~/clat_preparation/dashboard/ \
    mac-mini:~/clat_preparation/dashboard/
echo -e "${GREEN}✓ Dashboard synced${NC}"
echo ""

# 3. Sync Math module
echo -e "${YELLOW}Step 3: Syncing math module...${NC}"
rsync -avz ~/clat_preparation/math/*.py \
    mac-mini:~/clat_preparation/math/
echo -e "${GREEN}✓ Math module synced${NC}"
echo ""

# 4. Sync PDFs (same folder structure on both machines: ~/saanvi/)
echo -e "${YELLOW}Step 4: Syncing PDF files...${NC}"

# Ensure directories exist on Mac Mini
ssh mac-mini "mkdir -p ~/saanvi/Legaledgedailygk ~/saanvi/LegalEdgeweeklyGK ~/saanvi/weeklyGKCareerLauncher" 2>/dev/null

# Daily PDFs
echo "  → Daily PDFs..."
rsync -avz --ignore-existing ~/saanvi/Legaledgedailygk/ \
    mac-mini:~/saanvi/Legaledgedailygk/

# Weekly PDFs (LegalEdge)
echo "  → Weekly PDFs (LegalEdge)..."
rsync -avz --ignore-existing ~/saanvi/LegalEdgeweeklyGK/ \
    mac-mini:~/saanvi/LegalEdgeweeklyGK/

# Weekly PDFs (Career Launcher)
echo "  → Weekly PDFs (Career Launcher)..."
rsync -avz --ignore-existing ~/saanvi/weeklyGKCareerLauncher/ \
    mac-mini:~/saanvi/weeklyGKCareerLauncher/

echo -e "${GREEN}✓ PDFs synced (new files only)${NC}"
echo ""

# 5. Restart Mac Mini server
echo -e "${YELLOW}Step 5: Restarting Mac Mini server...${NC}"
ssh mac-mini "launchctl stop com.clatprep.server && sleep 2 && launchctl start com.clatprep.server"
echo -e "${GREEN}✓ Server restarted${NC}"
echo ""

# 6. Verify
echo -e "${YELLOW}Step 6: Verifying sync...${NC}"
sleep 3
STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://mac-mini:8001/api/dashboard)
if [ "$STATUS" = "200" ]; then
    echo -e "${GREEN}✓ Mac Mini server is responding${NC}"
else
    echo -e "${RED}✗ Mac Mini server not responding (HTTP $STATUS)${NC}"
fi

echo ""
echo "======================================================================"
echo -e "${GREEN}✅ Sync complete!${NC}"
echo "======================================================================"
echo ""
echo "📝 What was synced:"
echo "   • Server code (server/)"
echo "   • PDF generation (pdf_generation/)"
echo "   • Scripts (scripts/)"
echo "   • Dashboard files (HTML/CSS/JS)"
echo "   • Math module"
echo "   • New PDF files (existing files preserved)"
echo ""
echo "🔗 Test the server:"
echo "   • Local: http://mac-mini:8001/"
echo "   • Public: https://speedmathsgames.com/"
echo ""
