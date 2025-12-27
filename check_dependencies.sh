#!/bin/bash

echo "=== Checking Python Dependencies ==="
echo

cd /Users/arvind/clat_preparation
source venv_clat/bin/activate

deps=("anthropic" "requests" "PyPDF2" "PyMuPDF")

all_installed=true

for dep in "${deps[@]}"; do
    if python3 -c "import $dep" 2>/dev/null; then
        echo "✅ $dep"
    else
        echo "❌ $dep - MISSING"
        all_installed=false
    fi
done

echo

if [ "$all_installed" = true ]; then
    echo "✅ All dependencies installed"
    exit 0
else
    echo "❌ Some dependencies missing"
    echo "Run: source venv_clat/bin/activate && pip install anthropic requests PyPDF2 PyMuPDF"
    exit 1
fi
