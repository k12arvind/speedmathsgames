#!/usr/bin/env python3
"""
Batch question generator — processes all PDFs that have zero questions.

Usage (run on GCP VM):
  cd /opt/speedmathsgames
  sudo -u www-data nohup venv/bin/python scripts/batch_generate_questions.py \
      > logs/batch_generate.log 2>&1 &

Processes each PDF serially via assessment_processor.py to avoid overwhelming
the Claude API. Logs progress to stdout.
"""

import os
import sys
import re
import time
import uuid
import sqlite3
import subprocess
from pathlib import Path
from datetime import datetime

# ── Setup paths ──────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DB_PATH = ROOT / "revision_tracker.db"
PROCESSOR = ROOT / "server" / "assessment_processor.py"

# Prefer the venv python; fall back to current interpreter
VENV_PYTHON = ROOT / "venv" / "bin" / "python"
if not VENV_PYTHON.exists():
    VENV_PYTHON = ROOT / "venv_clat" / "bin" / "python3"
PYTHON_EXE = str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable

from server.pdf_scanner import relative_to_absolute
from server.pdf_chunker import PdfChunker
from server.assessment_jobs_db import AssessmentJobsDB

import PyPDF2


def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def derive_source_week(source_type: str, filename: str):
    """Derive (source, week_tag) from source_type + filename."""
    fn = filename.lower()

    # Source
    if "career" in fn or "manthan" in fn or "5070" in fn:
        source = "career_launcher"
    else:
        source = "legaledge"

    # Week tag
    # Monthly: monthly-current-affairs-february-2026-…
    m = re.search(
        r"(january|february|march|april|may|june|july|august|september|"
        r"october|november|december)[-_ ]*(\d{4})", fn
    )
    if m:
        month, year = m.group(1), m.group(2)
        if source_type == "monthly":
            week = f"monthly-{year}-{month}"
        else:
            week = f"{year}-{month}"
    else:
        # Try date pattern: 2026_april_1
        m2 = re.search(r"(\d{4})_(\w+?)_(\d+)", fn)
        if m2:
            year, month, day = m2.groups()
            week = f"{year}-{month}-{day}"
        else:
            # Weekly range: march_22_to_march_28
            m3 = re.search(r"(\w+?)_(\d+)_to_(\w+?)_(\d+)", fn)
            if m3:
                week = f"{m3.group(1)}-{m3.group(2)}-to-{m3.group(3)}-{m3.group(4)}"
            else:
                week = "unknown"

    return source, week


def get_page_count(filepath: str) -> int:
    try:
        with open(filepath, "rb") as f:
            return len(PyPDF2.PdfReader(f).pages)
    except Exception:
        return -1


def get_pending_pdfs():
    """Return list of (source_type, filename, filepath, pages) for PDFs with 0 questions."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Questions already generated
    c.execute("SELECT pdf_filename, COUNT(*) as cnt FROM questions GROUP BY pdf_filename")
    q_counts = {r["pdf_filename"]: r["cnt"] for r in c.fetchall()}

    # All leaf PDFs (not chunked-parents)
    c.execute("""
        SELECT filename, filepath, source_type
        FROM pdfs
        WHERE is_chunked = 0
        ORDER BY source_type, filename
    """)
    pending = []
    for r in c.fetchall():
        fn = r["filename"]
        if q_counts.get(fn, 0) > 0:
            continue
        if fn.startswith("._"):
            continue
        fp = relative_to_absolute(r["filepath"])
        if not os.path.exists(fp):
            continue
        pages = get_page_count(fp)
        if pages <= 0:
            continue
        pending.append((r["source_type"], fn, fp, pages))

    conn.close()
    return pending


def chunk_pdf_if_needed(filename: str, filepath: str, source_type: str) -> bool:
    """Chunk a large PDF. Returns True if chunking happened."""
    chunker = PdfChunker(str(DB_PATH))
    if chunker.is_chunked(filename):
        log(f"  Already chunked: {filename}")
        return True

    output_dir = str(Path(filepath).parent)
    log(f"  Chunking {filename} ({source_type}) into {output_dir} ...")
    for update in chunker.chunk_pdf(
        filepath, output_dir,
        max_pages=25,
        naming_pattern="{basename}_part{num}",
        source_type=source_type,
    ):
        if update.get("type") == "error":
            log(f"  CHUNK ERROR: {update.get('message')}")
            return False
        if update.get("type") == "chunk_created":
            log(f"    Created chunk: {update['filename']} ({update['total_pages']} pages)")
        if update.get("type") == "complete":
            log(f"  Chunking complete: {update['total_chunks']} chunks")
    return True


def run_assessment(pdf_id: str, source: str, week: str):
    """Run assessment_processor.py synchronously for one PDF. Returns question count or -1 on error."""
    jobs_db = AssessmentJobsDB(str(DB_PATH))

    # Determine chunk count
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM pdf_chunks WHERE parent_pdf_id = ?", (pdf_id,))
    chunk_count = c.fetchone()[0] or 1
    conn.close()

    job_id = jobs_db.create_job(pdf_id, chunk_count)
    log(f"  Job {job_id[:8]}… — {chunk_count} chunk(s), source={source}, week={week}")

    log_file = f"/tmp/assessment_job_{job_id[:8]}.log"
    result = subprocess.run(
        [PYTHON_EXE, str(PROCESSOR), job_id, pdf_id, source, week],
        capture_output=True, text=True,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
        timeout=600,  # 10 min max per PDF
    )

    if result.returncode != 0:
        log(f"  PROCESSOR ERROR (exit {result.returncode})")
        stderr_tail = (result.stderr or "")[-500:]
        if stderr_tail:
            log(f"  stderr: {stderr_tail}")
        return -1

    # Count questions generated
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM questions WHERE pdf_filename = ?", (pdf_id,))
    count = c.fetchone()[0]
    conn.close()

    # Also check chunks
    if count == 0:
        conn = sqlite3.connect(str(DB_PATH))
        c = conn.cursor()
        c.execute("SELECT chunk_filename FROM pdf_chunks WHERE parent_pdf_id = ?", (pdf_id,))
        for row in c.fetchall():
            c2 = conn.cursor()
            c2.execute("SELECT COUNT(*) FROM questions WHERE pdf_filename = ?", (row[0],))
            count += c2.fetchone()[0]
        conn.close()

    return count


def main():
    log("=" * 60)
    log("BATCH QUESTION GENERATOR — starting")
    log(f"DB: {DB_PATH}")
    log(f"Processor: {PROCESSOR}")
    log(f"Python: {PYTHON_EXE}")
    log("=" * 60)

    pending = get_pending_pdfs()
    log(f"Found {len(pending)} PDFs without questions")

    # Separate large PDFs (need chunking) from direct-processable
    large = [(t, fn, fp, pg) for t, fn, fp, pg in pending if pg > 25]
    direct = [(t, fn, fp, pg) for t, fn, fp, pg in pending if pg <= 25]

    log(f"  Direct (≤25 pg): {len(direct)}")
    log(f"  Needs chunking (>25 pg): {len(large)}")
    log("")

    total_qs = 0
    success = 0
    failed = 0

    # ── Phase 1: Chunk large PDFs ────────────────────────────────────
    for stype, fn, fp, pg in large:
        log(f"[CHUNK] {fn} ({pg} pages)")
        ok = chunk_pdf_if_needed(fn, fp, stype)
        if not ok:
            log(f"  SKIPPING — chunk failed")
            failed += 1
            continue

        source, week = derive_source_week(stype, fn)
        qs = run_assessment(fn, source, week)
        if qs < 0:
            failed += 1
        else:
            total_qs += qs
            success += 1
        log(f"  → {qs} questions generated")
        log("")

    # ── Phase 2: Direct PDFs ─────────────────────────────────────────
    for i, (stype, fn, fp, pg) in enumerate(direct, 1):
        log(f"[{i}/{len(direct)}] {fn} ({pg} pg, {stype})")
        source, week = derive_source_week(stype, fn)
        qs = run_assessment(fn, source, week)
        if qs < 0:
            failed += 1
        else:
            total_qs += qs
            success += 1
        log(f"  → {qs} questions generated")
        log("")

    log("=" * 60)
    log(f"DONE — {success} succeeded, {failed} failed, {total_qs} total questions generated")
    log("=" * 60)


if __name__ == "__main__":
    main()
