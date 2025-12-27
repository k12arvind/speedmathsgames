#!/usr/bin/env python3
"""
Assessment Jobs Database
Tracks assessment creation jobs with detailed progress for frontend polling.
"""

import sqlite3
import uuid
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime


class AssessmentJobsDB:
    """Database for tracking assessment creation jobs."""

    def __init__(self, db_path: str = None):
        """Initialize with database path."""
        if db_path is None:
            db_path = str(Path.home() / 'clat_preparation' / 'revision_tracker.db')
        self.db_path = db_path

    def create_job(self, parent_pdf_id: str, total_chunks: int) -> str:
        """
        Create a new assessment job.

        Args:
            parent_pdf_id: Parent PDF filename
            total_chunks: Total number of chunks to process

        Returns:
            Job ID (UUID)
        """
        job_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO assessment_jobs
                (job_id, parent_pdf_id, status, current_chunk, total_chunks,
                 current_batch, total_batches, status_message, total_cards,
                 progress_percentage, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                job_id,
                parent_pdf_id,
                'queued',
                0,
                total_chunks,
                0,
                0,
                'Job created, starting soon...',
                0,
                0,
                now,
                now
            ))

            conn.commit()
            return job_id

        except Exception as e:
            conn.rollback()
            raise RuntimeError(f"Failed to create job: {e}")

        finally:
            conn.close()

    def update_progress(
        self,
        job_id: str,
        status: Optional[str] = None,
        current_chunk: Optional[int] = None,
        total_chunks: Optional[int] = None,
        total_batches: Optional[int] = None,
        current_batch: Optional[int] = None,
        status_message: Optional[str] = None,
        total_cards: Optional[int] = None,
        progress_percentage: Optional[int] = None,
        error_message: Optional[str] = None
    ):
        """
        Update job progress with fine-grained details.

        Args:
            job_id: Job ID
            status: Job status (queued/processing/completed/failed)
            current_chunk: Current chunk being processed
            total_chunks: Total chunks to process (can be updated)
            total_batches: Total batches in current chunk
            current_batch: Current batch being processed
            status_message: Human-readable status message
            total_cards: Total cards generated so far
            progress_percentage: Overall progress (0-100)
            error_message: Error message if failed
        """
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        cursor = conn.cursor()

        try:
            # Build update query dynamically
            updates = []
            params = []

            if status is not None:
                updates.append("status = ?")
                params.append(status)

            if current_chunk is not None:
                updates.append("current_chunk = ?")
                params.append(current_chunk)

            if total_chunks is not None:
                updates.append("total_chunks = ?")
                params.append(total_chunks)

            if total_batches is not None:
                updates.append("total_batches = ?")
                params.append(total_batches)

            if current_batch is not None:
                updates.append("current_batch = ?")
                params.append(current_batch)

            if status_message is not None:
                updates.append("status_message = ?")
                params.append(status_message)

            if total_cards is not None:
                updates.append("total_cards = ?")
                params.append(total_cards)

            if progress_percentage is not None:
                updates.append("progress_percentage = ?")
                params.append(progress_percentage)

            if error_message is not None:
                updates.append("error_message = ?")
                params.append(error_message)

            # Always update timestamp
            updates.append("updated_at = ?")
            params.append(datetime.now().isoformat())

            # Add job_id for WHERE clause
            params.append(job_id)

            if updates:
                query = f"UPDATE assessment_jobs SET {', '.join(updates)} WHERE job_id = ?"
                cursor.execute(query, params)
                conn.commit()

        except Exception as e:
            conn.rollback()
            raise RuntimeError(f"Failed to update job progress: {e}")

        finally:
            conn.close()

    def get_status(self, job_id: str) -> Optional[Dict]:
        """
        Get current job status for frontend polling.

        Args:
            job_id: Job ID

        Returns:
            Dict with job status or None if not found
        """
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT * FROM assessment_jobs
                WHERE job_id = ?
            """, (job_id,))

            row = cursor.fetchone()

            if row:
                return dict(row)
            else:
                return None

        finally:
            conn.close()

    def mark_complete(self, job_id: str, total_cards: int):
        """Mark job as completed."""
        self.update_progress(
            job_id,
            status='completed',
            status_message=f'Assessment creation complete! Generated {total_cards} flashcards.',
            total_cards=total_cards,
            progress_percentage=100
        )

    def mark_failed(self, job_id: str, error_message: str):
        """Mark job as failed."""
        self.update_progress(
            job_id,
            status='failed',
            status_message=f'Assessment creation failed: {error_message}',
            error_message=error_message,
            progress_percentage=0
        )

    def get_jobs_for_pdf(self, parent_pdf_id: str) -> list:
        """Get all jobs for a PDF."""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT * FROM assessment_jobs
                WHERE parent_pdf_id = ?
                ORDER BY created_at DESC
            """, (parent_pdf_id,))

            jobs = [dict(row) for row in cursor.fetchall()]
            return jobs

        finally:
            conn.close()

    def get_active_jobs(self) -> list:
        """Get all active (processing or queued) jobs."""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT * FROM assessment_jobs
                WHERE status IN ('queued', 'processing')
                ORDER BY created_at ASC
            """, ())

            jobs = [dict(row) for row in cursor.fetchall()]
            return jobs

        finally:
            conn.close()


if __name__ == "__main__":
    # Test job tracking
    import time

    db = AssessmentJobsDB()

    print("Creating test job...")
    job_id = db.create_job("test.pdf", total_chunks=3)
    print(f"Created job: {job_id}")

    # Simulate progress updates
    print("\nSimulating progress updates...")

    # Start processing
    db.update_progress(
        job_id,
        status='processing',
        current_chunk=1,
        total_batches=10,
        current_batch=0,
        status_message='Starting chunk 1...',
        progress_percentage=5
    )

    time.sleep(1)

    # Batch progress
    for batch in range(1, 4):
        db.update_progress(
            job_id,
            current_batch=batch,
            status_message=f'Processing batch {batch}/10 in chunk 1...',
            total_cards=batch * 15,
            progress_percentage=10 + (batch * 3)
        )
        time.sleep(0.5)

    # Complete
    db.mark_complete(job_id, total_cards=150)

    # Show final status
    status = db.get_status(job_id)
    print("\nFinal status:")
    print(f"  Status: {status['status']}")
    print(f"  Message: {status['status_message']}")
    print(f"  Cards: {status['total_cards']}")
    print(f"  Progress: {status['progress_percentage']}%")
