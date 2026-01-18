#!/bin/bash
# Script to run Playwright tests with Chrome profile
# Requires Chrome to be closed first

echo "═══════════════════════════════════════════════════════════════"
echo "  Chrome Profile Tests for Active Time Tracking"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# Check if Chrome is running
if pgrep -x "Google Chrome" > /dev/null; then
    echo "⚠️  Chrome is currently running!"
    echo ""
    echo "To run tests with your authenticated session, please:"
    echo "1. Close Chrome (Cmd+Q)"
    echo "2. Run this script again"
    echo ""
    echo "Alternatively, you can test manually by:"
    echo "- Hard refresh the page (Cmd+Shift+R)"
    echo "- Check the GK Practice History section"
    echo "- Verify you see separate '📖 View' and '⏱️ Test' time columns"
    echo ""
    exit 1
fi

echo "✅ Chrome is closed. Starting tests..."
echo ""

cd /Users/arvind/clat_preparation
node tests/test_with_chrome_profile.js

echo ""
echo "Tests complete!"
