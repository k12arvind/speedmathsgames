#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
pdf_scanner.py

Scans multiple PDF folders and builds a unified view for the dashboard.
Works with actual PDF files in ~/Desktop/saanvi/ folders.
"""

import os
import sqlite3
from pathlib import Path
from datetime import datetime
import re
from typing import List, Dict, Optional
import json


class PDFScanner:
    """Scans PDF folders and syncs with database."""

    # Define folder locations - same structure on both MacBook Pro and Mac Mini
    BASE_PATH = Path.home() / "saanvi"

    FOLDERS = {
        'legaledge_daily': {
            'path': BASE_PATH / 'Legaledgedailygk',
            'type': 'daily',
            'source': 'legaledge'
        },
        'legaledge_weekly': {
            'path': BASE_PATH / 'LegalEdgeweeklyGK',
            'type': 'weekly',
            'source': 'legaledge'
        },
        'career_launcher_weekly': {
            'path': BASE_PATH / 'weeklyGKCareerLauncher',
            'type': 'weekly',
            'source': 'career_launcher'
        }
    }

    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            db_path = Path(__file__).parent / "revision_tracker.db"
        self.db_path = db_path

    def scan_all_folders(self) -> Dict:
        """Scan all PDF folders and return organized data."""
        results = {
            'daily': [],
            'weekly': {
                'legaledge': [],
                'career_launcher': []
            },
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

            # Check if this PDF's topics are in database
            source_date = date_match if date_match else pdf_file.stem

            cursor.execute("""
                SELECT COUNT(*) as topic_count FROM topics WHERE source_date = ?
            """, (source_date,))
            topic_count = cursor.fetchone()['topic_count']

            # Get revision stats for this PDF's topics
            cursor.execute("""
                SELECT
                    COUNT(DISTINCT t.topic_id) as total_topics,
                    COUNT(DISTINCT rs.topic_id) as revised_topics,
                    MAX(rs.last_revised) as last_revised,
                    SUM(COALESCE(rs.revision_count, 0)) as total_revisions
                FROM topics t
                LEFT JOIN revision_schedule rs ON t.topic_id = rs.topic_id
                WHERE t.source_date = ?
            """, (source_date,))

            stats = cursor.fetchone()

            # Get categories
            cursor.execute("""
                SELECT DISTINCT category FROM topics WHERE source_date = ?
            """, (source_date,))
            categories = [row['category'] for row in cursor.fetchall()]

            # Calculate revision count per topic
            total_topics = stats['total_topics'] or topic_count or 0
            total_revisions = stats['total_revisions'] or 0
            avg_revision_count = total_revisions // max(total_topics, 1) if total_topics > 0 else 0

            # Calculate days since last revision
            days_since_revision = None
            if stats['last_revised']:
                last_rev = datetime.fromisoformat(stats['last_revised'])
                days_since_revision = (datetime.now() - last_rev).days

            pdf_data = {
                'pdf_id': source_date,
                'filename': pdf_file.name,
                'filepath': str(pdf_file),
                'source_type': source_type,
                'source_name': source_name,
                'date_published': date_match or source_date,
                'total_topics': total_topics,
                'revised_topics': stats['revised_topics'] or 0,
                'categories': categories,
                'categories_list': categories,
                'revision_count': avg_revision_count,
                'total_revisions': total_revisions,
                'last_revised': stats['last_revised'],
                'last_modified': last_modified,
                'file_size_kb': round(file_size_kb, 2),
                'days_since_revision': days_since_revision,
                'exists_in_db': total_topics > 0
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

        # Calculate completion rate
        completion_rate = round((total_pdfs - never_revised) / max(total_pdfs, 1) * 100, 1)

        return {
            'total_pdfs': total_pdfs,
            'daily_pdfs': len(all_pdfs['daily']),
            'weekly_pdfs': sum(len(pdfs) for pdfs in all_pdfs['weekly'].values()),
            'never_revised': never_revised,
            'completion_rate': completion_rate,
            'folders': {
                'legaledge_daily': len(all_pdfs['daily']),
                'legaledge_weekly': len(all_pdfs['weekly']['legaledge']),
                'career_launcher_weekly': len(all_pdfs['weekly']['career_launcher'])
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

    print("\n📊 Statistics:")
    stats = scanner.get_statistics()
    print(json.dumps(stats, indent=2))
