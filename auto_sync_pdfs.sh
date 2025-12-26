#!/bin/bash
# Automatic PDF sync: MacBook Pro → Mac Mini
# Run this after downloading new PDFs from LegalEdge

set -e

echo "======================================================================"
echo "  📄 Auto-Syncing PDFs: MacBook Pro → Mac Mini"
echo "======================================================================"
echo ""

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Function to create directory on Mac Mini if needed
ensure_directory() {
    local dir=$1
    ssh mac-mini "mkdir -p '$dir'" 2>/dev/null || true
}

# Ensure directories exist on Mac Mini
echo -e "${YELLOW}Creating directories on Mac Mini if needed...${NC}"
ensure_directory "~/saanvi/Legaledgedailygk"
ensure_directory "~/saanvi/LegalEdgeweeklyGK"
ensure_directory "~/saanvi/weeklyGKCareerLauncher"
echo -e "${GREEN}✓ Directories ready${NC}"
echo ""

# Count files before sync
DAILY_COUNT_BEFORE=$(ssh mac-mini "ls ~/saanvi/Legaledgedailygk/*.pdf 2>/dev/null | wc -l" || echo "0")
WEEKLY_LEGALEDGE_BEFORE=$(ssh mac-mini "ls ~/saanvi/LegalEdgeweeklyGK/*.pdf 2>/dev/null | wc -l" || echo "0")
WEEKLY_CL_BEFORE=$(ssh mac-mini "ls ~/saanvi/weeklyGKCareerLauncher/*.pdf 2>/dev/null | wc -l" || echo "0")

# Sync Daily PDFs
echo -e "${YELLOW}Syncing Daily PDFs...${NC}"
if [ -d ~/saanvi/Legaledgedailygk ]; then
    rsync -avz --update ~/saanvi/Legaledgedailygk/*.pdf \
        mac-mini:~/saanvi/Legaledgedailygk/ 2>/dev/null && \
        echo -e "${GREEN}✓ Daily PDFs synced${NC}" || \
        echo -e "${RED}✗ Failed to sync daily PDFs${NC}"
else
    echo -e "${RED}✗ Daily PDF directory not found on MacBook Pro${NC}"
fi
echo ""

# Sync Weekly PDFs (LegalEdge)
echo -e "${YELLOW}Syncing Weekly PDFs (LegalEdge)...${NC}"
if [ -d ~/saanvi/LegalEdgeweeklyGK ]; then
    rsync -avz --update ~/saanvi/LegalEdgeweeklyGK/*.pdf \
        mac-mini:~/saanvi/LegalEdgeweeklyGK/ 2>/dev/null && \
        echo -e "${GREEN}✓ Weekly LegalEdge PDFs synced${NC}" || \
        echo -e "${RED}✗ Failed to sync weekly LegalEdge PDFs${NC}"
else
    echo -e "${RED}✗ Weekly LegalEdge PDF directory not found on MacBook Pro${NC}"
fi
echo ""

# Sync Weekly PDFs (Career Launcher)
echo -e "${YELLOW}Syncing Weekly PDFs (Career Launcher)...${NC}"
if [ -d ~/saanvi/weeklyGKCareerLauncher ]; then
    rsync -avz --update ~/saanvi/weeklyGKCareerLauncher/*.pdf \
        mac-mini:~/saanvi/weeklyGKCareerLauncher/ 2>/dev/null && \
        echo -e "${GREEN}✓ Weekly Career Launcher PDFs synced${NC}" || \
        echo -e "${RED}✗ Failed to sync weekly Career Launcher PDFs${NC}"
else
    echo -e "${RED}✗ Weekly Career Launcher PDF directory not found on MacBook Pro${NC}"
fi
echo ""

# Count files after sync
DAILY_COUNT_AFTER=$(ssh mac-mini "ls ~/saanvi/Legaledgedailygk/*.pdf 2>/dev/null | wc -l" || echo "0")
WEEKLY_LEGALEDGE_AFTER=$(ssh mac-mini "ls ~/saanvi/LegalEdgeweeklyGK/*.pdf 2>/dev/null | wc -l" || echo "0")
WEEKLY_CL_AFTER=$(ssh mac-mini "ls ~/saanvi/weeklyGKCareerLauncher/*.pdf 2>/dev/null | wc -l" || echo "0")

# Calculate new files
DAILY_NEW=$((DAILY_COUNT_AFTER - DAILY_COUNT_BEFORE))
WEEKLY_LEGALEDGE_NEW=$((WEEKLY_LEGALEDGE_AFTER - WEEKLY_LEGALEDGE_BEFORE))
WEEKLY_CL_NEW=$((WEEKLY_CL_AFTER - WEEKLY_CL_BEFORE))
TOTAL_NEW=$((DAILY_NEW + WEEKLY_LEGALEDGE_NEW + WEEKLY_CL_NEW))

# Trigger database refresh on Mac Mini
echo -e "${YELLOW}Refreshing PDF database on Mac Mini...${NC}"
curl -s "http://mac-mini:8001/api/dashboard" > /dev/null && \
    echo -e "${GREEN}✓ Database refreshed${NC}" || \
    echo -e "${RED}✗ Could not refresh database${NC}"
echo ""

echo "======================================================================"
echo -e "${GREEN}✅ Sync Complete!${NC}"
echo "======================================================================"
echo ""
echo "📊 Summary:"
echo "   Daily PDFs:              $DAILY_COUNT_AFTER total ($DAILY_NEW new)"
echo "   Weekly PDFs (LegalEdge): $WEEKLY_LEGALEDGE_AFTER total ($WEEKLY_LEGALEDGE_NEW new)"
echo "   Weekly PDFs (Career L):  $WEEKLY_CL_AFTER total ($WEEKLY_CL_NEW new)"
echo "   ─────────────────────────────────────"
echo "   Total:                   $((DAILY_COUNT_AFTER + WEEKLY_LEGALEDGE_AFTER + WEEKLY_CL_AFTER)) PDFs ($TOTAL_NEW new)"
echo ""
if [ $TOTAL_NEW -gt 0 ]; then
    echo "🆕 New PDFs synced! Check the dashboard:"
    echo "   https://speedmathsgames.com/comprehensive_dashboard.html"
else
    echo "ℹ️  No new PDFs to sync"
fi
echo ""
