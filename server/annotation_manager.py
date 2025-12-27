"""
PDF Annotation Manager
Handles CRUD operations for PDF annotations, revision tracking, and access logging.
"""

import sqlite3
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime


class AnnotationManager:
    """Manages PDF annotations, revisions, and access logs."""

    def __init__(self, db_path: str = None):
        """Initialize with database path."""
        if db_path is None:
            db_path = str(Path.home() / 'clat_preparation' / 'revision_tracker.db')
        self.db_path = db_path
        self._ensure_tables()

    def _ensure_tables(self):
        """Verify annotation tables exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Check if pdf_annotations table exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='pdf_annotations'
        """)

        if not cursor.fetchone():
            raise RuntimeError(
                "Annotation tables not found. "
                "Run migrations/add_annotation_tables.sql first."
            )

        conn.close()

    def _get_connection(self):
        """Get database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def save_annotation(
        self,
        pdf_id: str,
        page_number: int,
        annotation_type: str,
        annotation_data: dict,
        created_by: str = 'system'
    ) -> int:
        """
        Save a new annotation to the database.

        Args:
            pdf_id: PDF filename
            page_number: Page number (1-indexed)
            annotation_type: One of: 'highlight', 'underline', 'shape', 'pen'
            annotation_data: JSON-serializable dict with annotation details
            created_by: User identifier

        Returns:
            annotation_id: ID of created annotation
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Insert annotation
            cursor.execute("""
                INSERT INTO pdf_annotations
                (pdf_id, page_number, annotation_type, annotation_data, created_by)
                VALUES (?, ?, ?, ?, ?)
            """, (
                pdf_id,
                page_number,
                annotation_type,
                json.dumps(annotation_data),
                created_by
            ))

            annotation_id = cursor.lastrowid

            # Update annotation count in pdfs table
            cursor.execute("""
                UPDATE pdfs
                SET annotation_count = annotation_count + 1,
                    edit_count = edit_count + 1,
                    last_accessed = CURRENT_TIMESTAMP,
                    last_modified = CURRENT_TIMESTAMP
                WHERE filename = ?
            """, (pdf_id,))

            # Create revision record
            self._create_revision_record_internal(
                cursor,
                pdf_id,
                'annotation_added',
                f'Added {annotation_type} annotation to page {page_number}',
                {
                    'annotation_id': annotation_id,
                    'page_number': page_number,
                    'type': annotation_type
                },
                created_by
            )

            conn.commit()
            return annotation_id

        except Exception as e:
            conn.rollback()
            raise RuntimeError(f"Failed to save annotation: {e}")
        finally:
            conn.close()

    def get_annotations(
        self,
        pdf_id: str,
        page_number: Optional[int] = None,
        include_inactive: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Retrieve annotations for a PDF.

        Args:
            pdf_id: PDF filename
            page_number: Optional page number filter
            include_inactive: Include soft-deleted annotations

        Returns:
            List of annotation dicts
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            query = """
                SELECT
                    annotation_id,
                    pdf_id,
                    page_number,
                    annotation_type,
                    annotation_data,
                    created_by,
                    created_at,
                    updated_at,
                    is_active
                FROM pdf_annotations
                WHERE pdf_id = ?
            """
            params = [pdf_id]

            if page_number is not None:
                query += " AND page_number = ?"
                params.append(page_number)

            if not include_inactive:
                query += " AND is_active = 1"

            query += " ORDER BY page_number, created_at"

            cursor.execute(query, params)
            rows = cursor.fetchall()

            annotations = []
            for row in rows:
                annotation = dict(row)
                # Parse JSON data
                annotation['annotation_data'] = json.loads(annotation['annotation_data'])
                annotations.append(annotation)

            return annotations

        finally:
            conn.close()

    def update_annotation(
        self,
        annotation_id: int,
        annotation_data: dict,
        updated_by: str = 'system'
    ) -> bool:
        """
        Update an existing annotation.

        Args:
            annotation_id: Annotation ID
            annotation_data: New annotation data
            updated_by: User identifier

        Returns:
            True if updated successfully
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Get current annotation for revision tracking
            cursor.execute("""
                SELECT pdf_id, page_number, annotation_type
                FROM pdf_annotations
                WHERE annotation_id = ?
            """, (annotation_id,))

            row = cursor.fetchone()
            if not row:
                return False

            pdf_id, page_number, annotation_type = row

            # Update annotation
            cursor.execute("""
                UPDATE pdf_annotations
                SET annotation_data = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE annotation_id = ?
            """, (json.dumps(annotation_data), annotation_id))

            # Update edit count
            cursor.execute("""
                UPDATE pdfs
                SET edit_count = edit_count + 1,
                    last_accessed = CURRENT_TIMESTAMP,
                    last_modified = CURRENT_TIMESTAMP
                WHERE filename = ?
            """, (pdf_id,))

            # Create revision record
            self._create_revision_record_internal(
                cursor,
                pdf_id,
                'annotation_modified',
                f'Modified {annotation_type} annotation on page {page_number}',
                {
                    'annotation_id': annotation_id,
                    'page_number': page_number,
                    'type': annotation_type
                },
                updated_by
            )

            conn.commit()
            return True

        except Exception as e:
            conn.rollback()
            raise RuntimeError(f"Failed to update annotation: {e}")
        finally:
            conn.close()

    def delete_annotation(
        self,
        annotation_id: int,
        deleted_by: str = 'system',
        hard_delete: bool = False
    ) -> bool:
        """
        Delete an annotation (soft delete by default).

        Args:
            annotation_id: Annotation ID
            deleted_by: User identifier
            hard_delete: If True, permanently delete from database

        Returns:
            True if deleted successfully
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Get annotation details for revision tracking
            cursor.execute("""
                SELECT pdf_id, page_number, annotation_type
                FROM pdf_annotations
                WHERE annotation_id = ?
            """, (annotation_id,))

            row = cursor.fetchone()
            if not row:
                return False

            pdf_id, page_number, annotation_type = row

            if hard_delete:
                # Permanently delete
                cursor.execute("""
                    DELETE FROM pdf_annotations
                    WHERE annotation_id = ?
                """, (annotation_id,))
            else:
                # Soft delete
                cursor.execute("""
                    UPDATE pdf_annotations
                    SET is_active = 0,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE annotation_id = ?
                """, (annotation_id,))

            # Update annotation count
            cursor.execute("""
                UPDATE pdfs
                SET annotation_count = annotation_count - 1,
                    edit_count = edit_count + 1,
                    last_accessed = CURRENT_TIMESTAMP,
                    last_modified = CURRENT_TIMESTAMP
                WHERE filename = ?
            """, (pdf_id,))

            # Create revision record
            self._create_revision_record_internal(
                cursor,
                pdf_id,
                'annotation_deleted',
                f'Deleted {annotation_type} annotation from page {page_number}',
                {
                    'annotation_id': annotation_id,
                    'page_number': page_number,
                    'type': annotation_type,
                    'hard_delete': hard_delete
                },
                deleted_by
            )

            conn.commit()
            return True

        except Exception as e:
            conn.rollback()
            raise RuntimeError(f"Failed to delete annotation: {e}")
        finally:
            conn.close()

    def log_access(
        self,
        pdf_id: str,
        access_type: str = 'view',
        user_id: str = 'system',
        duration_seconds: Optional[int] = None
    ):
        """
        Log PDF access for analytics.

        Args:
            pdf_id: PDF filename
            access_type: One of: 'view', 'annotate', 'export', 'view_annotations'
            user_id: User identifier
            duration_seconds: Optional session duration
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Insert access log
            cursor.execute("""
                INSERT INTO pdf_access_log
                (pdf_id, user_id, access_type, duration_seconds)
                VALUES (?, ?, ?, ?)
            """, (pdf_id, user_id, access_type, duration_seconds))

            # Update access count and last_accessed timestamp
            cursor.execute("""
                UPDATE pdfs
                SET access_count = access_count + 1,
                    last_accessed = CURRENT_TIMESTAMP
                WHERE filename = ?
            """, (pdf_id,))

            conn.commit()

        except Exception as e:
            conn.rollback()
            raise RuntimeError(f"Failed to log access: {e}")
        finally:
            conn.close()

    def create_revision_record(
        self,
        pdf_id: str,
        revision_type: str,
        change_summary: str,
        change_details: Optional[dict] = None,
        changed_by: str = 'system'
    ) -> int:
        """
        Create a revision history record (public method).

        Args:
            pdf_id: PDF filename
            revision_type: Type of change
            change_summary: Brief description
            change_details: Optional detailed info
            changed_by: User identifier

        Returns:
            revision_id: ID of created revision record
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            revision_id = self._create_revision_record_internal(
                cursor,
                pdf_id,
                revision_type,
                change_summary,
                change_details,
                changed_by
            )
            conn.commit()
            return revision_id
        except Exception as e:
            conn.rollback()
            raise RuntimeError(f"Failed to create revision record: {e}")
        finally:
            conn.close()

    def _create_revision_record_internal(
        self,
        cursor,
        pdf_id: str,
        revision_type: str,
        change_summary: str,
        change_details: Optional[dict],
        changed_by: str
    ) -> int:
        """Internal method to create revision record (reusable in transactions)."""
        # Get next revision number
        cursor.execute("""
            SELECT COALESCE(MAX(revision_number), 0) + 1
            FROM pdf_revision_records
            WHERE pdf_id = ?
        """, (pdf_id,))

        revision_number = cursor.fetchone()[0]

        # Insert revision record
        cursor.execute("""
            INSERT INTO pdf_revision_records
            (pdf_id, revision_number, revision_type, changed_by,
             change_summary, change_details)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            pdf_id,
            revision_number,
            revision_type,
            changed_by,
            change_summary,
            json.dumps(change_details) if change_details else None
        ))

        return cursor.lastrowid

    def get_revision_history(
        self,
        pdf_id: str,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get revision history for a PDF.

        Args:
            pdf_id: PDF filename
            limit: Optional limit on number of records

        Returns:
            List of revision records
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            query = """
                SELECT
                    revision_id,
                    pdf_id,
                    revision_number,
                    revision_type,
                    timestamp,
                    changed_by,
                    change_summary,
                    change_details
                FROM pdf_revision_records
                WHERE pdf_id = ?
                ORDER BY revision_number DESC
            """

            params = [pdf_id]

            if limit:
                query += " LIMIT ?"
                params.append(limit)

            cursor.execute(query, params)
            rows = cursor.fetchall()

            revisions = []
            for row in rows:
                revision = dict(row)
                # Parse JSON details if present
                if revision['change_details']:
                    revision['change_details'] = json.loads(revision['change_details'])
                revisions.append(revision)

            return revisions

        finally:
            conn.close()

    def get_pdf_stats(self, pdf_id: str) -> Dict[str, Any]:
        """
        Get statistics for a PDF.

        Args:
            pdf_id: PDF filename

        Returns:
            Dict with access_count, edit_count, annotation_count, last_accessed
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT
                    access_count,
                    edit_count,
                    annotation_count,
                    last_accessed
                FROM pdfs
                WHERE filename = ?
            """, (pdf_id,))

            row = cursor.fetchone()
            if not row:
                return None

            return dict(row)

        finally:
            conn.close()
