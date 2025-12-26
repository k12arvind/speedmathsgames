#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
process_pdf_with_progress.py

Process PDFs with real-time progress tracking and logging.
Integrates with processing_jobs_db for progress monitoring.
"""

import sys
import os
import logging
import time
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List
import fitz  # PyMuPDF

# Add parent directory to path to import processing_jobs_db
sys.path.insert(0, str(Path(__file__).parent))
from processing_jobs_db import ProcessingJobsDB


class ProgressLogger:
    """Custom logger that writes to both file and updates database."""

    def __init__(self, log_file: str, job_id: str, db: ProcessingJobsDB):
        self.job_id = job_id
        self.db = db
        self.log_file = Path(log_file)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

        # Setup file logging
        self.logger = logging.getLogger(f"progress_{job_id}")
        self.logger.setLevel(logging.INFO)

        # File handler
        file_handler = logging.FileHandler(str(self.log_file))
        file_handler.setLevel(logging.INFO)

        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)

        # Formatter
        formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s',
                                     datefmt='%H:%M:%S')
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

    def info(self, message: str):
        """Log info message."""
        self.logger.info(message)

    def success(self, message: str):
        """Log success message."""
        self.logger.info(f"✓ {message}")

    def error(self, message: str):
        """Log error message."""
        self.logger.error(f"✗ {message}")

    def warning(self, message: str):
        """Log warning message."""
        self.logger.warning(f"⚠ {message}")


def split_pdf_by_pages(pdf_path: Path, pages_per_chunk: int = 10) -> List[Dict]:
    """Split PDF into smaller chunks by pages."""
    doc = fitz.open(str(pdf_path))
    total_pages = len(doc)

    chunks = []
    chunk_num = 1

    for start_page in range(0, total_pages, pages_per_chunk):
        end_page = min(start_page + pages_per_chunk, total_pages)

        # Create new PDF with this chunk
        chunk_doc = fitz.open()
        chunk_doc.insert_pdf(doc, from_page=start_page, to_page=end_page-1)

        # Save chunk
        chunk_filename = f"{pdf_path.stem}_part{chunk_num}.pdf"
        chunk_path = pdf_path.parent / chunk_filename
        chunk_doc.save(str(chunk_path))
        chunk_doc.close()

        chunks.append({
            'path': chunk_path,
            'pages': f"{start_page+1}-{end_page}",
            'num': chunk_num,
            'start_page': start_page + 1,
            'end_page': end_page
        })

        chunk_num += 1

    doc.close()
    return chunks


def extract_text_length(pdf_path: Path) -> int:
    """Get text length from PDF."""
    doc = fitz.open(str(pdf_path))
    text = ""
    for page in doc:
        text += page.get_text("text")
    doc.close()
    return len(text)


def count_cards_in_json(json_path: Path) -> int:
    """Count cards in the generated JSON file."""
    try:
        import json
        with open(json_path) as f:
            data = json.load(f)
            # Try both 'cards' and 'flashcards' keys for compatibility
            return len(data.get('cards', data.get('flashcards', [])))
    except Exception:
        return 0


def process_chunk_with_progress(chunk_path: Path, source: str, week: str,
                                chunk_num: int, total_chunks: int,
                                automation_dir: Path, logger: ProgressLogger,
                                job_id: str, db: ProcessingJobsDB) -> int:
    """Process a single PDF chunk with progress tracking."""
    logger.info(f"")
    logger.info(f"{'='*60}")
    logger.info(f"Processing Chunk {chunk_num}/{total_chunks}")
    logger.info(f"File: {chunk_path.name}")
    logger.info(f"Pages: {chunk_path.stem.split('_')[-1]}")
    logger.info(f"{'='*60}")

    # Update progress
    db.update_progress(
        job_id,
        completed_chunks=chunk_num-1,
        current_step=f"Processing chunk {chunk_num}/{total_chunks}"
    )

    # Modify week tag to include chunk number
    week_with_chunk = f"{week}_p{chunk_num}"

    # Get API key from environment or .zshrc
    env = os.environ.copy()
    if 'ANTHROPIC_API_KEY' not in env:
        try:
            zshrc_path = Path.home() / ".zshrc"
            if zshrc_path.exists():
                with open(zshrc_path) as f:
                    for line in f:
                        if "ANTHROPIC_API_KEY" in line and "export" in line:
                            key = line.split("=", 1)[1].strip().strip('"').strip("'")
                            env["ANTHROPIC_API_KEY"] = key
                            break
        except Exception as e:
            logger.warning(f"Could not load API key from .zshrc: {e}")

    # Generate flashcards
    logger.info("Generating flashcards with Claude AI...")
    db.update_progress(
        job_id,
        completed_chunks=chunk_num-1,
        current_step=f"Generating cards for chunk {chunk_num}/{total_chunks}"
    )

    cmd = [
        "python3", "generate_flashcards.py",
        str(chunk_path),
        source,
        week_with_chunk
    ]

    try:
        result = subprocess.run(
            cmd,
            check=True,
            cwd=str(automation_dir),
            capture_output=True,
            text=True,
            env=env
        )

        # Count cards generated
        json_path = automation_dir / "inbox" / "week_cards.json"
        cards_count = count_cards_in_json(json_path)
        logger.success(f"Generated {cards_count} flashcards")

        # Import to Anki
        logger.info("Importing to Anki...")
        db.update_progress(
            job_id,
            completed_chunks=chunk_num-1,
            current_step=f"Importing chunk {chunk_num}/{total_chunks} to Anki"
        )

        import_cmd = ["python3", "import_to_anki.py", "inbox/week_cards.json"]
        subprocess.run(import_cmd, check=True, cwd=str(automation_dir), env=env)

        logger.success(f"Chunk {chunk_num}/{total_chunks} complete: {cards_count} cards imported")

        # Update progress with cards count
        db.update_progress(
            job_id,
            completed_chunks=chunk_num,
            current_step=f"Completed chunk {chunk_num}/{total_chunks}",
            cards_count=cards_count
        )

        return cards_count

    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to process chunk {chunk_num}: {e}")
        logger.error(f"Output: {e.stderr if hasattr(e, 'stderr') else 'No output'}")
        raise


def process_pdf_with_progress(job_id: str):
    """Main processing function with progress tracking."""
    # Connect to database
    db = ProcessingJobsDB()
    job = db.get_job(job_id)

    if not job:
        print(f"❌ Job {job_id} not found")
        sys.exit(1)

    # Setup logger
    logger = ProgressLogger(job['log_file'], job_id, db)

    try:
        # Update status to processing
        db.update_status(job_id, 'processing')

        logger.info(f"Starting PDF processing")
        logger.info(f"PDF: {job['pdf_filename']}")
        logger.info(f"Source: {job['source']}")
        logger.info(f"Week: {job['week']}")

        pdf_path = Path(job['pdf_path'])
        source = job['source']
        week = job['week']
        total_chunks = job['total_chunks']

        # Determine automation directory (where generate_flashcards.py is)
        automation_dir = Path.home() / "Desktop" / "anki_automation"
        if not automation_dir.exists():
            raise FileNotFoundError(f"Automation directory not found: {automation_dir}")

        # Check PDF exists
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        # Check text length
        logger.info("Analyzing PDF...")
        text_length = extract_text_length(pdf_path)
        logger.info(f"Text length: {text_length:,} characters")

        if total_chunks > 1:
            # Split and process chunks
            logger.info(f"Splitting PDF into {total_chunks} chunks...")
            pages_per_chunk = 10  # Default

            chunks = split_pdf_by_pages(pdf_path, pages_per_chunk)
            logger.success(f"Created {len(chunks)} chunks")

            for chunk in chunks:
                chunk_text_len = extract_text_length(chunk['path'])
                logger.info(f"  Chunk {chunk['num']}: Pages {chunk['pages']} ({chunk_text_len:,} chars)")

            # Process each chunk
            total_cards = 0

            for chunk in chunks:
                cards_count = process_chunk_with_progress(
                    chunk['path'],
                    source,
                    week,
                    chunk['num'],
                    len(chunks),
                    automation_dir,
                    logger,
                    job_id,
                    db
                )

                total_cards += cards_count

                # Cleanup chunk file
                chunk['path'].unlink()

                # Wait between chunks
                if chunk['num'] < len(chunks):
                    logger.info("Waiting 5 seconds before next chunk...")
                    time.sleep(5)

            logger.info(f"")
            logger.info(f"{'='*60}")
            logger.success(f"Processing complete!")
            logger.success(f"Total cards generated: {total_cards}")
            logger.info(f"{'='*60}")

        else:
            # Process single file without splitting
            logger.info("Processing PDF directly (no splitting needed)...")

            # Update progress: starting
            db.update_progress(job_id, 0, "Generating flashcards with Claude AI...")

            env = os.environ.copy()
            if 'ANTHROPIC_API_KEY' not in env:
                try:
                    zshrc_path = Path.home() / ".zshrc"
                    if zshrc_path.exists():
                        with open(zshrc_path) as f:
                            for line in f:
                                if "ANTHROPIC_API_KEY" in line and "export" in line:
                                    key = line.split("=", 1)[1].strip().strip('"').strip("'")
                                    env["ANTHROPIC_API_KEY"] = key
                                    break
                except Exception as e:
                    logger.warning(f"Could not load API key: {e}")

            # Generate flashcards
            logger.info("Generating flashcards with Claude AI...")
            db.update_progress(job_id, 0, "Calling Claude API (this may take 60-90 seconds)...")
            cmd = ["python3", "generate_flashcards.py", str(pdf_path), source, week]
            subprocess.run(cmd, check=True, cwd=str(automation_dir), env=env)

            # Count cards generated
            json_path = automation_dir / "inbox" / "week_cards.json"
            cards_count = count_cards_in_json(json_path)
            logger.success(f"Generated {cards_count} flashcards")

            # Import to Anki
            logger.info("Importing to Anki...")
            db.update_progress(job_id, 0, f"Importing {cards_count} cards to Anki...", cards_count)
            import_cmd = ["python3", "import_to_anki.py", "inbox/week_cards.json"]
            subprocess.run(import_cmd, check=True, cwd=str(automation_dir), env=env)

            db.update_progress(job_id, 1, "Processing complete", cards_count)
            logger.success(f"Processing complete: {cards_count} cards imported to Anki")

        # Mark as completed
        db.mark_completed(job_id)

    except Exception as e:
        logger.error(f"Processing failed: {str(e)}")
        db.mark_failed(job_id, str(e))
        raise

    finally:
        db.close()


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python process_pdf_with_progress.py <job_id>")
        sys.exit(1)

    job_id = sys.argv[1]
    process_pdf_with_progress(job_id)
