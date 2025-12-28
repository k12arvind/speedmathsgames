#!/bin/bash

# automate_html.sh
#
# Complete automation: TopRankers HTML → Flashcards → Anki
# Handles both URLs and local HTML files

cd "$(dirname "$0")"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found. Please run setup first:"
    echo "   python3 -m venv venv"
    echo "   source venv/bin/activate"
    echo "   pip install -r requirements.txt"
    exit 1
fi

# Activate virtual environment
source venv/bin/activate

# Check for API key
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "❌ ANTHROPIC_API_KEY not set!"
    echo ""
    echo "Please set your API key:"
    echo "   export ANTHROPIC_API_KEY='your-api-key-here'"
    echo ""
    echo "Get your API key from: https://console.anthropic.com/"
    exit 1
fi

# Check for URL/file argument
if [ -z "$1" ]; then
    echo "❌ No URL or HTML file provided!"
    echo ""
    echo "Usage: ./automate_html.sh <url_or_file> [source] [week]"
    echo ""
    echo "Examples:"
    echo "  ./automate_html.sh https://www.toprankers.com/current-affairs-19th-december-2025"
    echo "  ./automate_html.sh inbox/page.html"
    echo "  ./automate_html.sh inbox/page.html toprankers 2025_Dec_D19"
    exit 1
fi

URL_OR_FILE="$1"
SOURCE="${2:-toprankers}"
WEEK="$3"

echo ""
echo "======================================================================"
echo "    CLAT GK: TopRankers HTML → Anki Automation"
echo "======================================================================"
echo ""
echo "📄 Input:  $URL_OR_FILE"
echo "📚 Source: $SOURCE"
if [ -n "$WEEK" ]; then
    echo "📅 Week:   $WEEK"
fi
echo ""

# Step 1: Generate flashcards from HTML
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 1: Generating Flashcards from HTML"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [ -n "$WEEK" ]; then
    python generate_flashcards_from_html.py "$URL_OR_FILE" "$SOURCE" "$WEEK"
else
    python generate_flashcards_from_html.py "$URL_OR_FILE" "$SOURCE"
fi

if [ $? -ne 0 ]; then
    echo ""
    echo "❌ Flashcard generation failed!"
    exit 1
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 2: Importing to Anki"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

python import_to_anki.py inbox/daily_cards.json

if [ $? -ne 0 ]; then
    echo ""
    echo "❌ Anki import failed!"
    echo ""
    echo "Troubleshooting:"
    echo "  1. Make sure Anki is running"
    echo "  2. Check AnkiConnect is installed (code: 2055492159)"
    echo "  3. Close any dialog boxes in Anki"
    exit 1
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ SUCCESS! Cards imported to Anki"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "💡 Tips:"
echo "   • Press 'Y' in Anki to sync to AnkiWeb"
echo "   • Check your daily study schedule"
echo "   • Review new cards today for best retention"
echo ""
