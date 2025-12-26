#!/bin/bash
# Pull latest code from GitHub on Mac Mini
# Run this script ON the Mac Mini to get latest updates

set -e

echo "======================================================================"
echo "  Updating Mac Mini from GitHub"
echo "======================================================================"
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

cd ~/clat_preparation

# Check if git is initialized
if [ ! -d .git ]; then
    echo -e "${RED}Error: Git not initialized. Run setup_mac_mini_git.sh first${NC}"
    exit 1
fi

# Stop server before updating
echo -e "${YELLOW}Step 1: Stopping server...${NC}"
launchctl stop com.clatprep.server 2>/dev/null || echo "Server not running"
sleep 2
echo -e "${GREEN}✓ Server stopped${NC}"
echo ""

# Pull latest code
echo -e "${YELLOW}Step 2: Pulling latest code from GitHub...${NC}"
git fetch origin main
git reset --hard origin/main
echo -e "${GREEN}✓ Code updated${NC}"
echo ""

# Show what changed
echo -e "${YELLOW}Latest changes:${NC}"
git log -3 --oneline
echo ""

# Restart server
echo -e "${YELLOW}Step 3: Starting server...${NC}"
launchctl start com.clatprep.server
sleep 3
echo -e "${GREEN}✓ Server started${NC}"
echo ""

# Verify server is running
echo -e "${YELLOW}Step 4: Verifying server...${NC}"
STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/api/dashboard)
if [ "$STATUS" = "200" ]; then
    echo -e "${GREEN}✓ Server is responding${NC}"
else
    echo -e "${RED}✗ Server not responding (HTTP $STATUS)${NC}"
fi

echo ""
echo "======================================================================"
echo -e "${GREEN}✅ Mac Mini updated successfully!${NC}"
echo "======================================================================"
echo ""
echo "🔗 Test the server:"
echo "   • Local: http://localhost:8001/"
echo "   • Public: https://speedmathsgames.com/"
echo ""
