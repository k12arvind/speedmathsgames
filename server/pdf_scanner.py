#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
pdf_scanner.py

Scans multiple PDF folders and builds a unified view for the dashboard.
Works with actual PDF files in ~/saanvi/ folders.

CROSS-MACHINE COMPATIBILITY:
- Paths are stored RELATIVE to home directory (e.g., "saanvi/Legaledgedailygk/file.pdf")
- This allows the same database to work on both MacBook Pro (/Users/arvind) 
  and Mac Mini (/Users/arvindkumar) without path conflicts.
"""

import os
import sqlite3
from pathlib import Path
from datetime import datetime
import re
from typing import List, Dict, Optional
import json


def path_to_relative(absolute_path: str) -> str:
    """
    Convert absolute path to relative path (relative to home directory).
    
    Example: /Users/arvind/saanvi/file.pdf -> saanvi/file.pdf
    """
    path = Path(absolute_path)
    home = Path.home()
    try:
        return str(path.relative_to(home))
    except ValueError:
        # Path is not relative to home, return as-is
        return str(path)


def relative_to_absolute(relative_path: str) -> str:
    """
    Convert relative path back to absolute path (using current home directory).
    
    Example: saanvi/file.pdf -> /Users/arvindkumar/saanvi/file.pdf (on Mac Mini)
             saanvi/file.pdf -> /Users/arvind/saanvi/file.pdf (on MacBook Pro)
    """
    if not relative_path:
        return relative_path
    
    # If already absolute, fix any wrong username
    if relative_path.startswith('/'):
        path = Path(relative_path)
        # Extract the relative part after /Users/*/
        parts = path.parts
        if len(parts) > 2 and parts[0] == '/' and parts[1] == 'Users':
            # Skip /Users/username and rebuild with current home
            relative_parts = parts[3:]  # Everything after /Users/username/
            return str(Path.home().joinpath(*relative_parts))
        return relative_path
    
    # Relative path - expand with current home
    return str(Path.home() / relative_path)


class PDFScanner:
    """Scans PDF folders and syncs with database."""

    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            # Database is in parent directory (clat_preparation/)
            db_path = Path(__file__).parent.parent / "revision_tracker.db"
        self.db_path = db_path

        # IMPORTANT: Define paths as INSTANCE attributes, not CLASS attributes
        # This ensures Path.home() is evaluated at instantiation time, not at import time.
        # When the server is started by launchd at boot, Path.home() may return wrong values
        # if evaluated too early. Evaluating here guarantees correct paths.
        self.BASE_PATH = Path.home() / "saanvi"

        self.FOLDERS = {
            'legaledge_daily': {
                'path': self.BASE_PATH / 'Legaledgedailygk',
                'type': 'daily',
                'source': 'legaledge'
            },
            'legaledge_weekly': {
                'path': self.BASE_PATH / 'LegalEdgeweeklyGK',
                'type': 'weekly',
                'source': 'legaledge'
            },
            'career_launcher_weekly': {
                'path': self.BASE_PATH / 'weeklyGKCareerLauncher',
                'type': 'weekly',
                'source': 'career_launcher'
            },
            'monthly_legaledge': {
                'path': self.BASE_PATH / 'Monthly-CLATPOST-LegalEdge',
                'type': 'monthly',
                'source': 'legaledge'
            }
        }

        # Log paths at initialization for debugging
        print(f"📁 PDFScanner initialized: BASE_PATH={self.BASE_PATH} (exists={self.BASE_PATH.exists()})")

    def scan_all_folders(self) -> Dict:
        """Scan all PDF folders and return organized data."""
        results = {
            'daily': [],
            'weekly': {
                'legaledge': [],
                'career_launcher': []
            },
            'monthly': [],
            'total_count': 0,
            'scan_time': datetime.now().isoformat()
        }

        for folder_key, folder_info in self.FOLDERS.items():
            folder_path = folder_info['path']

            if not folder_path.exists():
                print(f"Warning: Folder not found: {folder_path}")
                continue

            pdfs = self.scan_folder(folder_path, folder_info['type'], folder_info['source'])

            if folder_info['type'] == 'daily':
                results['daily'].extend(pdfs)
            elif folder_info['type'] == 'monthly':
                results['monthly'].extend(pdfs)
            else:
                results['weekly'][folder_info['source']].extend(pdfs)

            results['total_count'] += len(pdfs)

        return results

    def scan_folder(self, folder_path: Path, source_type: str, source_name: str) -> List[Dict]:
        """Scan a single folder for PDFs."""
        pdfs = []

        # Get all PDF files
        pdf_files = list(folder_path.glob('*.pdf'))

        # Get database connection for existing revision data
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        for pdf_file in pdf_files:
            # Skip tracked versions
            if '_tracked' in pdf_file.name:
                continue

            # Extract date from filename
            date_match = self.extract_date_from_filename(pdf_file.name)

            # Get file stats
            stat = pdf_file.stat()
            file_size_kb = stat.st_size / 1024
            last_modified = datetime.fromtimestamp(stat.st_mtime).isoformat()

            # For date_published, use extracted date or file creation date
            file_date = datetime.fromtimestamp(stat.st_ctime).strftime('%Y-%m-%d')

            # Check if this PDF's topics are in database
            source_date = date_match if date_match else pdf_file.stem

            cursor.execute("""
                SELECT COUNT(*) as topic_count FROM topics WHERE source_date = ?
            """, (source_date,))
            topic_count = cursor.fetchone()['topic_count']

            # Get topic count and categories
            cursor.execute("""
                SELECT COUNT(*) as total_topics FROM topics WHERE source_date = ?
            """, (source_date,))
            total_topics = cursor.fetchone()['total_topics'] or topic_count or 0

            # Get categories
            cursor.execute("""
                SELECT DISTINCT category FROM topics WHERE source_date = ?
            """, (source_date,))
            categories = [row['category'] for row in cursor.fetchall()]

            # Track file modification-based revisions
            # Check if we have tracked this PDF before
            cursor.execute("""
                SELECT last_modified, file_edit_count, view_count, date_added, extraction_attempted FROM pdfs WHERE filename = ?
            """, (pdf_file.name,))
            pdf_record = cursor.fetchone()

            file_edit_count = 0
            view_count = 0
            date_added = None
            extraction_attempted = False
            if pdf_record:
                # Compare stored modification time with current
                stored_mtime = pdf_record['last_modified']
                if stored_mtime != last_modified:
                    # File was edited! Increment count
                    file_edit_count = (pdf_record['file_edit_count'] or 0) + 1
                    # Update the database
                    cursor.execute("""
                        UPDATE pdfs
                        SET last_modified = ?, file_edit_count = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE filename = ?
                    """, (last_modified, file_edit_count, pdf_file.name))
                    conn.commit()
                else:
                    file_edit_count = pdf_record['file_edit_count'] or 0
                # Get view count (scroll-through completions)
                view_count = pdf_record['view_count'] or 0
                # Get date when PDF was first added
                date_added = pdf_record['date_added']
                # Check if extraction was attempted (for monthly PDFs)
                extraction_attempted = bool(pdf_record['extraction_attempted'])
            else:
                # First time seeing this PDF, insert it
                # Store RELATIVE path for cross-machine compatibility
                relative_filepath = path_to_relative(str(pdf_file))
                date_added = datetime.now().isoformat()
                cursor.execute("""
                    INSERT INTO pdfs (filename, filepath, source_type, source_name, date_published,
                                     date_added, total_topics, last_modified, file_edit_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
                """, (pdf_file.name, relative_filepath, source_type, source_name,
                      date_match or file_date, date_added,
                      total_topics, last_modified))
                conn.commit()

            # Get assessment attempts count for this PDF
            # Need to query assessment database
            assessment_attempts = 0
            try:
                assessment_conn = sqlite3.connect(Path(__file__).parent / "assessment_tracker.db")
                assessment_cursor = assessment_conn.cursor()
                # Match on source_date (date format), pdf_id, or pdf_filename
                assessment_cursor.execute("""
                    SELECT COUNT(DISTINCT qa.session_id) as attempt_count
                    FROM question_attempts qa
                    JOIN test_sessions ts ON qa.session_id = ts.session_id
                    WHERE ts.source_date = ? OR ts.pdf_id = ? OR ts.pdf_filename = ? OR ts.source_date = ?
                """, (source_date, source_date, pdf_file.name, pdf_file.name))
                result = assessment_cursor.fetchone()
                if result:
                    assessment_attempts = result[0] or 0
                assessment_conn.close()
            except:
                # Assessment database might not exist yet
                pass

            # Days since last file edit
            days_since_revision = None
            file_mtime = datetime.fromtimestamp(stat.st_mtime)
            days_since_revision = (datetime.now() - file_mtime).days if file_edit_count > 0 else None

            # Get last viewed timestamp from view sessions
            last_viewed = None
            days_since_view = None
            cursor.execute("""
                SELECT completed_at FROM pdf_view_sessions
                WHERE pdf_id = ? AND is_complete = 1
                ORDER BY completed_at DESC LIMIT 1
            """, (pdf_file.name,))
            view_result = cursor.fetchone()
            if view_result and view_result['completed_at']:
                last_viewed = view_result['completed_at']
                try:
                    view_dt = datetime.fromisoformat(last_viewed.replace('Z', '+00:00').split('+')[0])
                    days_since_view = (datetime.now() - view_dt).days
                except:
                    pass

            pdf_data = {
                'pdf_id': source_date,
                'filename': pdf_file.name,
                'filepath': str(pdf_file),
                'source_type': source_type,
                'source_name': source_name,
                'date_published': date_match or file_date,
                'date_added': date_added,  # When PDF was first added to system
                'total_topics': total_topics,
                'revised_topics': 0,  # Not used anymore
                'categories': categories,
                'categories_list': categories,
                'revision_count': view_count,  # Changed: Now shows complete view count
                'total_revisions': view_count,  # Changed: Same as revision_count
                'view_count': view_count,  # Scroll-through completions
                'last_viewed': last_viewed,  # Last complete scroll-through timestamp
                'days_since_view': days_since_view,  # Days since last view
                'assessment_attempts': assessment_attempts,  # NEW: Test attempts
                'last_revised': last_modified if file_edit_count > 0 else None,
                'last_modified': last_modified,
                'file_size_kb': round(file_size_kb, 2),
                'days_since_revision': days_since_revision,
                'exists_in_db': total_topics > 0,
                'extraction_attempted': extraction_attempted  # For monthly PDFs
            }

            pdfs.append(pdf_data)

        conn.close()

        # Sort by date (newest first)
        pdfs.sort(key=lambda x: x['date_published'], reverse=True)

        return pdfs

    def extract_date_from_filename(self, filename: str) -> Optional[str]:
        """Extract date from PDF filename."""
        # Pattern: current_affairs_2025_december_19.pdf
        # or: current_affairs_2025-12-19.pdf

        # Try YYYY-MM-DD format
        match = re.search(r'(\d{4})-(\d{2})-(\d{2})', filename)
        if match:
            return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"

        # Try YYYY_month_DD format
        match = re.search(r'(\d{4})_(\w+)_(\d{1,2})', filename)
        if match:
            year = match.group(1)
            month = match.group(2).lower()
            day = match.group(3).zfill(2)

            month_map = {
                'january': '01', 'february': '02', 'march': '03', 'april': '04',
                'may': '05', 'june': '06', 'july': '07', 'august': '08',
                'september': '09', 'october': '10', 'november': '11', 'december': '12'
            }

            month_num = month_map.get(month, '01')
            return f"{year}-{month_num}-{day}"

        # Try to extract just date from source_date in topics table
        match = re.search(r'(\d{4}-\d{2}-\d{2})', filename)
        if match:
            return match.group(1)

        return None

    def get_statistics(self) -> Dict:
        """Get overall statistics across all folders."""
        all_pdfs = self.scan_all_folders()

        total_pdfs = all_pdfs['total_count']

        # Count never revised
        never_revised = 0
        for pdf in all_pdfs['daily']:
            if pdf['revision_count'] == 0:
                never_revised += 1

        for source in all_pdfs['weekly'].values():
            for pdf in source:
                if pdf['revision_count'] == 0:
                    never_revised += 1

        for pdf in all_pdfs['monthly']:
            if pdf['revision_count'] == 0:
                never_revised += 1

        # Calculate completion rate
        completion_rate = round((total_pdfs - never_revised) / max(total_pdfs, 1) * 100, 1)

        return {
            'total_pdfs': total_pdfs,
            'daily_pdfs': len(all_pdfs['daily']),
            'weekly_pdfs': sum(len(pdfs) for pdfs in all_pdfs['weekly'].values()),
            'monthly_pdfs': len(all_pdfs['monthly']),
            'never_revised': never_revised,
            'completion_rate': completion_rate,
            'folders': {
                'legaledge_daily': len(all_pdfs['daily']),
                'legaledge_weekly': len(all_pdfs['weekly']['legaledge']),
                'career_launcher_weekly': len(all_pdfs['weekly']['career_launcher']),
                'monthly_legaledge': len(all_pdfs['monthly'])
            }
        }

    def filter_by_untouched_weeks(self, weeks: int) -> List[Dict]:
        """Get PDFs not touched in X weeks."""
        from datetime import timedelta

        all_pdfs = self.scan_all_folders()
        cutoff_date = datetime.now() - timedelta(weeks=weeks)

        filtered = []

        # Check daily
        for pdf in all_pdfs['daily']:
            if pdf['last_revised']:
                last_rev = datetime.fromisoformat(pdf['last_revised'])
                if last_rev < cutoff_date:
                    filtered.append(pdf)
            else:
                # Never revised
                filtered.append(pdf)

        # Check weekly
        for source_pdfs in all_pdfs['weekly'].values():
            for pdf in source_pdfs:
                if pdf['last_revised']:
                    last_rev = datetime.fromisoformat(pdf['last_revised'])
                    if last_rev < cutoff_date:
                        filtered.append(pdf)
                else:
                    filtered.append(pdf)

        # Check monthly
        for pdf in all_pdfs['monthly']:
            if pdf['last_revised']:
                last_rev = datetime.fromisoformat(pdf['last_revised'])
                if last_rev < cutoff_date:
                    filtered.append(pdf)
            else:
                filtered.append(pdf)

        return filtered

    def filter_by_revision_count(self, min_count: int, max_count: Optional[int] = None) -> List[Dict]:
        """Get PDFs with specific revision count range."""
        all_pdfs = self.scan_all_folders()

        filtered = []

        # Check daily
        for pdf in all_pdfs['daily']:
            rev_count = pdf['revision_count']
            if max_count is None:
                if rev_count >= min_count:
                    filtered.append(pdf)
            else:
                if min_count <= rev_count <= max_count:
                    filtered.append(pdf)

        # Check weekly
        for source_pdfs in all_pdfs['weekly'].values():
            for pdf in source_pdfs:
                rev_count = pdf['revision_count']
                if max_count is None:
                    if rev_count >= min_count:
                        filtered.append(pdf)
                else:
                    if min_count <= rev_count <= max_count:
                        filtered.append(pdf)

        # Check monthly
        for pdf in all_pdfs['monthly']:
            rev_count = pdf['revision_count']
            if max_count is None:
                if rev_count >= min_count:
                    filtered.append(pdf)
            else:
                if min_count <= rev_count <= max_count:
                    filtered.append(pdf)

        return filtered


if __name__ == '__main__':
    # Test scanner
    scanner = PDFScanner()

    print("Scanning all folders...")
    results = scanner.scan_all_folders()

    print(f"\n✅ Scan Complete!")
    print(f"Total PDFs: {results['total_count']}")
    print(f"Daily PDFs: {len(results['daily'])}")
    print(f"Weekly PDFs (LegalEdge): {len(results['weekly']['legaledge'])}")
    print(f"Weekly PDFs (Career Launcher): {len(results['weekly']['career_launcher'])}")
    print(f"Monthly PDFs: {len(results['monthly'])}")

    print("\n📊 Statistics:")
    stats = scanner.get_statistics()
    print(json.dumps(stats, indent=2))
