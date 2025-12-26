#!/bin/bash
# Setup Git on Mac Mini and pull latest code
# Run this script ON the Mac Mini

set -e

echo "======================================================================"
echo "  Setting up Git repository on Mac Mini"
echo "======================================================================"
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if we're in the right directory
if [ ! -d ~/clat_preparation ]; then
    echo -e "${RED}Error: ~/clat_preparation does not exist${NC}"
    echo "Please create the directory first"
    exit 1
fi

cd ~/clat_preparation

# Check if .git exists
if [ -d .git ]; then
    echo -e "${YELLOW}Git repository already exists${NC}"
    echo "Fetching latest changes..."
    git fetch origin
    echo -e "${GREEN}✓ Fetched latest changes${NC}"
else
    echo -e "${YELLOW}Initializing Git repository...${NC}"
    git init
    git remote add origin https://github.com/k12arvind/speedmathsgames.git
    echo -e "${GREEN}✓ Git initialized and remote added${NC}"
fi

# Configure git user (required for merge operations)
echo -e "${YELLOW}Configuring Git user...${NC}"
git config user.email "k12arvind@gmail.com"
git config user.name "Arvind K"
echo -e "${GREEN}✓ Git user configured${NC}"
echo ""

# Pull latest code
echo -e "${YELLOW}Pulling latest code from GitHub...${NC}"
git fetch origin main
git reset --hard origin/main
echo -e "${GREEN}✓ Code updated to latest version${NC}"
echo ""

# Show what was pulled
echo -e "${YELLOW}Latest commit:${NC}"
git log -1 --oneline
echo ""

echo "======================================================================"
echo -e "${GREEN}✅ Mac Mini is now synced with GitHub!${NC}"
echo "======================================================================"
echo ""
echo "📝 Files synced:"
echo "   • Python server code"
echo "   • Dashboard HTML/CSS/JS"
echo "   • Databases (assessment_tracker.db, etc.)"
echo "   • Scripts and utilities"
echo ""
echo "🔄 To update Mac Mini in the future, run:"
echo "   cd ~/clat_preparation && git pull origin main"
echo ""
