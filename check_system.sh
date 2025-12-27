#!/bin/bash

echo "=== CLAT Assessment System Status Check ==="
echo

# Check if server is running
echo "1. Checking if server is running..."
if curl -s http://localhost:8001/api/test >/dev/null 2>&1; then
    echo "   ✅ Server is running on port 8001"
else
    echo "   ❌ Server is NOT running"
    echo "   Run: ./start_server.sh"
    exit 1
fi
echo

# Check if venv exists
echo "2. Checking virtual environment..."
if [ -d "venv_clat" ]; then
    echo "   ✅ Virtual environment exists"
else
    echo "   ❌ Virtual environment not found"
    exit 1
fi
echo

# Check cache-busting headers
echo "3. Checking cache-busting headers..."
headers=$(curl -sI http://localhost:8001/assessment.html | grep -i "cache-control")
if [[ $headers == *"no-cache"* ]]; then
    echo "   ✅ Cache-busting headers present"
else
    echo "   ⚠️  Cache-busting headers missing"
fi
echo

# Check recent assessment jobs
echo "4. Checking recent assessment jobs..."
source venv_clat/bin/activate
python3 << 'PYTHON'
import sqlite3
from pathlib import Path

db_path = str(Path.home() / 'clat_preparation' / 'revision_tracker.db')
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

cursor.execute("""
    SELECT status, COUNT(*) as count
    FROM assessment_jobs
    GROUP BY status
""")

for row in cursor.fetchall():
    status_emoji = {
        'completed': '✅',
        'failed': '❌',
        'processing': '⏳',
        'queued': '📋'
    }.get(row['status'], '❓')
    print(f"   {status_emoji} {row['status']}: {row['count']} jobs")

conn.close()
PYTHON
echo

# Check assessment status for recent PDFs
echo "5. Checking assessment status for recent PDFs..."
for pdf in "current_affairs_2025_december_24.pdf" "current_affairs_2025_december_25.pdf"; do
    status=$(curl -s "http://localhost:8001/api/assessment-status/$pdf" | python3 -c "import sys, json; data=json.load(sys.stdin); print(f\"{data['all_complete']},{data['total_cards']}\")")
    IFS=',' read complete cards <<< "$status"
    if [ "$complete" = "True" ]; then
        echo "   ✅ $pdf: $cards cards"
    else
        echo "   ⚠️  $pdf: Not complete"
    fi
done
echo

echo "=== System Check Complete ==="
echo
echo "Next steps:"
echo "1. Hard refresh your browser (Cmd+Shift+R or Ctrl+Shift+F5)"
echo "2. Open: http://localhost:8001/comprehensive_dashboard.html"
echo "3. Try creating assessments for a new PDF"
