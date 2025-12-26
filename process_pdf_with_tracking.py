#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
process_pdf_with_tracking.py

Complete PDF processing pipeline:
1. Chunk PDF if large (using intelligent chunking)
2. Generate MCQs for each PDF/chunk
3. Generate and import Anki flashcards
4. Update database with processing status
"""

import sys
import os
import json
import subprocess
import sqlite3
import time
from pathlib import Path
from typing import List, Dict, Tuple
import fitz

DB_PATH = Path.home() / "clat_preparation" / "revision_tracker.db"
STATUS_DIR = Path.home() / "clat_preparation" / "processing_status"

# Create status directory if it doesn't exist
STATUS_DIR.mkdir(parents=True, exist_ok=True)


def update_status(pdf_id: str, status: str, progress: int = 0):
    """Write status update to file for frontend to read."""
    try:
        status_file = STATUS_DIR / f"{pdf_id}.json"
        data = {
            'status': status,
            'progress': progress,
            'timestamp': time.time(),
            'pdf_id': pdf_id
        }
        with open(status_file, 'w') as f:
            json.dump(data, f)
    except Exception as e:
        print(f"⚠️ Could not write status: {e}")


def should_chunk_pdf(pdf_path: str) -> Tuple[bool, int]:
    """Determine if PDF needs chunking based on page count."""
    try:
        doc = fitz.open(pdf_path)
        total_pages = len(doc)
        doc.close()
        return (total_pages > 12, total_pages)
    except Exception as e:
        print(f"Error checking PDF: {e}")
        return (False, 0)


def chunk_pdf_if_needed(pdf_path: str) -> List[str]:
    """Chunk PDF if large, return list of PDF files to process."""
    should_chunk, total_pages = should_chunk_pdf(pdf_path)

    if not should_chunk:
        print(f"✅ PDF is small ({total_pages} pages) - no chunking needed")
        return [pdf_path]

    print(f"📄 PDF has {total_pages} pages - chunking...")

    # Run intelligent chunking
    script_dir = Path(__file__).parent
    result = subprocess.run(
        ['python3', str(script_dir / 'intelligent_chunk_pdf.py'), pdf_path, '8', '15'],
        capture_output=True,
        text=True,
        cwd=str(script_dir)
    )

    if result.returncode != 0:
        print(f"❌ Chunking failed: {result.stderr}")
        return [pdf_path]

    # Parse JSON output to get chunk files
    try:
        # Get last line which should be JSON
        output_lines = result.stdout.strip().split('\n')
        json_line = output_lines[-1]
        chunk_info = json.loads(json_line)

        if chunk_info.get('chunk_count', 0) == 0:
            return [pdf_path]

        print(f"✅ Created {chunk_info['chunk_count']} chunks")
        return chunk_info['chunk_files']
    except (json.JSONDecodeError, KeyError, IndexError) as e:
        print(f"⚠️  Could not parse chunking output: {e}")
        print(f"Output: {result.stdout}")
        return [pdf_path]


def generate_anki_cards_for_pdf(pdf_path: str, source: str, week: str) -> int:
    """Generate and import Anki flashcards."""
    script_dir = Path(__file__).parent
    venv_python = Path.home() / 'Desktop' / 'anki_automation' / 'venv' / 'bin' / 'python3'
    python_exe = str(venv_python) if venv_python.exists() else 'python3'

    print(f"  🎴 Generating Anki flashcards...")

    # Generate flashcards
    result = subprocess.run(
        [python_exe, str(script_dir / 'generate_flashcards.py'), pdf_path, source, week],
        capture_output=True,
        text=True,
        cwd=str(script_dir)
    )

    if result.returncode != 0:
        print(f"  ⚠️  Flashcard generation had issues: {result.stderr[:200]}")
        return 0

    # Import to Anki
    print(f"  📥 Importing to Anki...")
    result = subprocess.run(
        [python_exe, str(script_dir / 'import_to_anki.py')],
        capture_output=True,
        text=True,
        cwd=str(script_dir)
    )

    if result.returncode != 0:
        print(f"  ⚠️  Anki import had issues: {result.stderr[:200]}")
        return 0

    # Try to parse card count from output
    try:
        for line in result.stdout.split('\n'):
            if 'Successfully imported:' in line:
                count = int(line.split(':')[1].strip().split()[0])
                return count
    except:
        pass

    return 0


def update_processing_status(pdf_id: str, status_data: Dict):
    """Update pdf_processing_status table."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT OR REPLACE INTO pdf_processing_status
        (pdf_id, original_filename, original_filepath, is_processed, is_chunked,
         chunk_count, chunk_files, mcq_count, anki_card_count, processed_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    """, (
        pdf_id,
        status_data['filename'],
        status_data['filepath'],
        1,  # is_processed
        status_data['is_chunked'],
        status_data['chunk_count'],
        json.dumps(status_data['chunk_files']),
        status_data['mcq_count'],
        status_data['anki_card_count'],
    ))

    conn.commit()
    conn.close()
    print(f"\n✅ Database updated for {pdf_id}")


def process_pdf_complete(pdf_path: str, source: str, week: str):
    """Main processing function."""
    print("="*60)
    print("PDF Processing Pipeline with Tracking")
    print("="*60)
    print(f"📄 PDF: {Path(pdf_path).name}")
    print(f"📌 Source: {source}")
    print(f"📌 Week: {week}")
    print()

    if not Path(pdf_path).exists():
        print(f"❌ File not found: {pdf_path}")
        sys.exit(1)

    # Step 1: Chunk if needed
    update_status(week, "Analyzing PDF size...", 10)
    print("Step 1: Analyzing PDF size and chunking if needed...")
    pdf_files = chunk_pdf_if_needed(pdf_path)
    is_chunked = len(pdf_files) > 1

    if is_chunked:
        update_status(week, f"PDF split into {len(pdf_files)} chunks", 20)
    else:
        update_status(week, "PDF ready for processing", 20)

    total_cards = 0

    # Step 2: Process each PDF/chunk
    update_status(week, f"Processing {len(pdf_files)} file(s)...", 30)
    print(f"\nStep 2: Processing {len(pdf_files)} file(s)...")
    for i, pdf_file in enumerate(pdf_files):
        if is_chunked:
            pdf_id = f"{week}_part{i+1}"
        else:
            pdf_id = week

        print(f"\n{'='*60}")
        update_status(week, f"Processing chunk {i+1}/{len(pdf_files)}: {pdf_id}", 30 + (i * 40 // len(pdf_files)))
        print(f"Processing: {pdf_id}")
        print(f"File: {Path(pdf_file).name}")
        print(f"{'='*60}")

        # Generate Anki cards
        update_status(week, f"Generating flashcards for chunk {i+1}...", 40 + (i * 40 // len(pdf_files)))
        card_count = generate_anki_cards_for_pdf(pdf_file, source, pdf_id)
        total_cards += card_count
        print(f"  ✅ Generated {card_count} Anki cards")

    # Step 3: Update database
    update_status(week, "Importing to database...", 90)
    print(f"\nStep 3: Updating database...")
    update_processing_status(week, {
        'filename': Path(pdf_path).name if not is_chunked else f"{Path(pdf_path).stem} (chunked)",
        'filepath': pdf_path,
        'is_chunked': is_chunked,
        'chunk_count': len(pdf_files),
        'chunk_files': pdf_files,
        'mcq_count': 0,  # MCQs generated separately
        'anki_card_count': total_cards
    })

    update_status(week, "Complete!", 100)

    print("\n" + "="*60)
    print("✅ Processing Complete!")
    print("="*60)
    print(f"Total Anki Cards: {total_cards}")
    print(f"Chunks Created: {len(pdf_files)}")
    print()

    # Output JSON for API consumption
    result = {
        'success': True,
        'pdf_id': week,
        'anki_card_count': total_cards,
        'chunk_count': len(pdf_files),
        'is_chunked': is_chunked
    }
    print("JSON_RESULT:", json.dumps(result))


def main():
    if len(sys.argv) < 4:
        print("Usage: python process_pdf_with_tracking.py <pdf_path> <source> <week>")
        print()
        print("Examples:")
        print("  python process_pdf_with_tracking.py weekly.pdf careerlauncher 2025_Dec_W2")
        print("  python process_pdf_with_tracking.py daily.pdf legaledge 2025-12-23")
        sys.exit(1)

    pdf_path = sys.argv[1]
    source = sys.argv[2]
    week = sys.argv[3]

    process_pdf_complete(pdf_path, source, week)


if __name__ == "__main__":
    main()
