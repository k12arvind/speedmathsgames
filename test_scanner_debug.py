#!/usr/bin/env python3
"""
Debug script to test PDF scanner with verbose logging.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from server.pdf_scanner import PDFScanner
import time

print("Creating scanner...")
scanner = PDFScanner()

print("Starting scan_all_folders()...")
start = time.time()
results = scanner.scan_all_folders()
elapsed = time.time() - start
print(f"scan_all_folders() completed in {elapsed:.3f}s")
print(f"Total PDFs: {results['total_count']}")

print("\nStarting get_statistics()...")
start = time.time()
stats = scanner.get_statistics()
elapsed = time.time() - start
print(f"get_statistics() completed in {elapsed:.3f}s")
print(f"Stats: {stats}")

print("\nTesting JSON serialization...")
import json
data = {
    'pdfs': results,
    'statistics': stats
}
json_str = json.dumps(data)
print(f"JSON length: {len(json_str)} chars")

print("\n✅ All tests passed!")
