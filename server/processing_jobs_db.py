#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
processing_jobs_db.py

Database for tracking PDF processing jobs with real-time progress.
Enables users to monitor long-running PDF processing operations.
"""

import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, List
import json


class ProcessingJobsDB:
    """Manages PDF processing job tracking database."""

    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            db_path = Path(__file__).parent / "processing_jobs.db"

        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_database()

    def _init_database(self):
        """Create processing jobs database schema."""
        cursor = self.conn.cursor()

        # Processing jobs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS processing_jobs (
                job_id TEXT PRIMARY KEY,
                pdf_id TEXT NOT NULL,
                pdf_filename TEXT NOT NULL,
                pdf_path TEXT NOT NULL,
                source TEXT NOT NULL,
                week TEXT NOT NULL,
                status TEXT NOT NULL,  -- 'queued', 'processing', 'completed', 'failed'
                progress_percentage INTEGER DEFAULT 0,
                current_step TEXT,
                total_chunks INTEGER,
                completed_chunks INTEGER DEFAULT 0,
                total_cards INTEGER DEFAULT 0,
                log_file TEXT,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                error_message TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create index for faster queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_jobs_status
            ON processing_jobs(status, started_at DESC)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_jobs_pdf
            ON processing_jobs(pdf_id)
        """)

        self.conn.commit()

    def create_job(self, pdf_id: str, pdf_filename: str, pdf_path: str,
                   source: str, week: str, total_chunks: int) -> str:
        """Create a new processing job."""
        # Generate unique job ID
        timestamp = int(datetime.now().timestamp())
        job_id = f"proc_{pdf_id.replace('-', '')}_{timestamp}"

        # Create log file path
        log_file = f"logs/processing_{job_id}.log"

        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO processing_jobs
            (job_id, pdf_id, pdf_filename, pdf_path, source, week, status,
             total_chunks, log_file, started_at)
            VALUES (?, ?, ?, ?, ?, ?, 'queued', ?, ?, ?)
        """, (job_id, pdf_id, pdf_filename, pdf_path, source, week,
              total_chunks, log_file, datetime.now().isoformat()))

        self.conn.commit()
        return job_id

    def update_status(self, job_id: str, status: str):
        """Update job status."""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE processing_jobs
            SET status = ?
            WHERE job_id = ?
        """, (status, job_id))
        self.conn.commit()

    def update_progress(self, job_id: str, completed_chunks: int,
                       current_step: str, cards_count: int = 0):
        """Update job progress."""
        cursor = self.conn.cursor()

        # Get total chunks
        cursor.execute("""
            SELECT total_chunks FROM processing_jobs WHERE job_id = ?
        """, (job_id,))
        row = cursor.fetchone()

        if not row:
            return

        total_chunks = row['total_chunks']
        progress = int((completed_chunks / total_chunks) * 100) if total_chunks > 0 else 0

        cursor.execute("""
            UPDATE processing_jobs
            SET completed_chunks = ?,
                progress_percentage = ?,
                current_step = ?,
                total_cards = total_cards + ?,
                status = 'processing'
            WHERE job_id = ?
        """, (completed_chunks, progress, current_step, cards_count, job_id))

        self.conn.commit()

    def mark_completed(self, job_id: str):
        """Mark job as completed."""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE processing_jobs
            SET status = 'completed',
                progress_percentage = 100,
                completed_at = ?,
                current_step = 'Processing complete'
            WHERE job_id = ?
        """, (datetime.now().isoformat(), job_id))

        self.conn.commit()

    def mark_failed(self, job_id: str, error_message: str):
        """Mark job as failed."""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE processing_jobs
            SET status = 'failed',
                error_message = ?,
                completed_at = ?,
                current_step = 'Failed'
            WHERE job_id = ?
        """, (error_message, datetime.now().isoformat(), job_id))

        self.conn.commit()

    def get_job(self, job_id: str) -> Optional[Dict]:
        """Get job details by ID."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM processing_jobs WHERE job_id = ?
        """, (job_id,))

        row = cursor.fetchone()
        if not row:
            return None

        job = dict(row)

        # Calculate duration if completed
        if job['completed_at']:
            started = datetime.fromisoformat(job['started_at'])
            completed = datetime.fromisoformat(job['completed_at'])
            duration = (completed - started).total_seconds()
            job['duration_seconds'] = int(duration)
        else:
            job['duration_seconds'] = None

        # Estimate remaining time
        if job['status'] == 'processing' and job['completed_chunks'] > 0:
            started = datetime.fromisoformat(job['started_at'])
            elapsed = (datetime.now() - started).total_seconds()
            avg_time_per_chunk = elapsed / job['completed_chunks']
            remaining_chunks = job['total_chunks'] - job['completed_chunks']
            estimated_remaining = int(avg_time_per_chunk * remaining_chunks)
            job['estimated_time_remaining_seconds'] = estimated_remaining
        else:
            job['estimated_time_remaining_seconds'] = None

        return job

    def get_recent_jobs(self, limit: int = 20) -> List[Dict]:
        """Get recent processing jobs."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM processing_jobs
            ORDER BY started_at DESC
            LIMIT ?
        """, (limit,))

        jobs = []
        for row in cursor.fetchall():
            job = dict(row)

            # Calculate duration if completed
            if job['completed_at']:
                started = datetime.fromisoformat(job['started_at'])
                completed = datetime.fromisoformat(job['completed_at'])
                duration = (completed - started).total_seconds()
                job['duration_seconds'] = int(duration)
            else:
                job['duration_seconds'] = None

            jobs.append(job)

        return jobs

    def get_jobs_by_status(self, status: str) -> List[Dict]:
        """Get jobs by status."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM processing_jobs
            WHERE status = ?
            ORDER BY started_at DESC
        """, (status,))

        return [dict(row) for row in cursor.fetchall()]

    def cleanup_old_jobs(self, days: int = 7):
        """Delete jobs older than specified days."""
        cursor = self.conn.cursor()
        cutoff_date = datetime.now().timestamp() - (days * 24 * 3600)

        cursor.execute("""
            DELETE FROM processing_jobs
            WHERE datetime(started_at) < datetime(?, 'unixepoch')
            AND status IN ('completed', 'failed')
        """, (cutoff_date,))

        deleted = cursor.rowcount
        self.conn.commit()
        return deleted

    def close(self):
        """Close database connection."""
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


if __name__ == '__main__':
    # Test database creation
    db = ProcessingJobsDB()
    print(f"✅ Processing jobs database created at: {db.db_path}")

    # Test job creation
    job_id = db.create_job(
        pdf_id="2025-12-26",
        pdf_filename="test.pdf",
        pdf_path="/path/to/test.pdf",
        source="test",
        week="2025_Dec_W2",
        total_chunks=4
    )
    print(f"✅ Test job created: {job_id}")

    # Test progress update
    db.update_progress(job_id, 1, "Processing chunk 1/4", 87)
    print(f"✅ Progress updated")

    # Test job retrieval
    job = db.get_job(job_id)
    print(f"✅ Job retrieved: {job['status']}, {job['progress_percentage']}%")

    # Cleanup
    db.mark_completed(job_id)
    print(f"✅ Job marked as completed")

    db.close()
    print(f"✅ Database tests passed!")
