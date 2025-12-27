#!/usr/bin/env python3
"""
Topic Extractor
Extracts topics from PDF text, calculates hashes for duplicate detection, and batches for processing.
"""

import hashlib
import re
import sqlite3
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
import fitz  # PyMuPDF


class TopicExtractor:
    """Handles topic extraction and batching with duplicate detection."""

    def __init__(self, db_path: str = None):
        """Initialize with database path."""
        if db_path is None:
            db_path = str(Path.home() / 'clat_preparation' / 'revision_tracker.db')
        self.db_path = db_path

    def extract_pdf_text(self, pdf_path: str) -> str:
        """Extract text from PDF with page markers (same as generate_flashcards.py)."""
        doc = fitz.open(pdf_path)
        parts = []
        for i, page in enumerate(doc):
            txt = page.get_text("text")
            if txt and txt.strip():
                parts.append(f"\n\n=== PAGE {i+1} ===\n")
                parts.append(txt)

        text = "".join(parts)
        # Clean up text
        text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)  # Join hyphenated words
        text = re.sub(r"[ \t]+", " ", text)  # Collapse spaces
        return text.strip()

    def extract_topics_from_text(self, pdf_text: str) -> List[Dict]:
        """
        Extract topics from PDF text.

        Topics are typically separated by:
        - Numbered headings (1., 2., 3. or 1. Topic Name)
        - ALL CAPS HEADINGS
        - === PAGE markers (we'll keep pages together as topics for now)

        Returns list of topic dicts with title, content, hash, page_range.
        """
        topics = []

        # Split by page markers
        page_pattern = r'=== PAGE (\d+) ==='
        pages = re.split(page_pattern, pdf_text)

        # pages will be: ['', '1', 'content1', '2', 'content2', ...]
        # So we pair them up
        current_topic_content = []
        current_page_start = None
        current_page_end = None

        i = 1  # Skip first empty element
        while i < len(pages):
            if i < len(pages) - 1:
                page_num = int(pages[i])
                page_content = pages[i + 1].strip()

                if page_content:
                    # Check for topic boundaries within the page
                    # Look for patterns like:
                    # - "1. Topic Name" or "Topic Name:" at start of line
                    # - ALL CAPS lines (likely topic headers)

                    # For now, use a simple heuristic: split by major topic markers
                    topic_splits = re.split(
                        r'\n(?=\d+\.\s+[A-Z]|\n[A-Z\s]{10,}\n)',  # Numbered or ALL CAPS headers
                        page_content
                    )

                    for split_content in topic_splits:
                        if len(split_content.strip()) > 50:  # Minimum topic size
                            # Extract title (first line or first sentence)
                            lines = split_content.strip().split('\n')
                            title = lines[0][:100] if lines else f"Page {page_num} Content"

                            # Normalize content for hashing (remove extra whitespace, lowercase)
                            normalized = re.sub(r'\s+', ' ', split_content.strip().lower())
                            topic_hash = hashlib.sha256(normalized.encode('utf-8')).hexdigest()

                            topics.append({
                                'title': title.strip(),
                                'content': split_content.strip(),
                                'hash': topic_hash,
                                'page_range': [page_num, page_num]
                            })

                i += 2
            else:
                break

        # If no topics found (PDF has no clear structure), treat whole pages as topics
        if not topics and pages:
            i = 1
            while i < len(pages):
                if i < len(pages) - 1:
                    page_num = int(pages[i])
                    page_content = pages[i + 1].strip()

                    if page_content and len(page_content) > 50:
                        normalized = re.sub(r'\s+', ' ', page_content.lower())
                        topic_hash = hashlib.sha256(normalized.encode('utf-8')).hexdigest()

                        topics.append({
                            'title': f"Page {page_num}",
                            'content': page_content,
                            'hash': topic_hash,
                            'page_range': [page_num, page_num]
                        })

                    i += 2
                else:
                    break

        return topics

    def extract_topics_from_pdf(self, pdf_path: str) -> List[Dict]:
        """Extract topics from a PDF file."""
        pdf_text = self.extract_pdf_text(pdf_path)
        return self.extract_topics_from_text(pdf_text)

    def batch_topics(self, topics: List[Dict], batch_size: int = 3) -> List[List[Dict]]:
        """
        Group topics into batches for processing.

        Args:
            topics: List of topic dicts
            batch_size: Number of topics per batch (default 3 for 10-15s processing)

        Returns:
            List of topic batches
        """
        batches = []
        for i in range(0, len(topics), batch_size):
            batch = topics[i:i + batch_size]
            batches.append(batch)
        return batches

    def is_duplicate_topic(self, topic_hash: str, parent_pdf_id: str) -> bool:
        """
        Check if a topic has already been processed.

        Args:
            topic_hash: SHA256 hash of topic content
            parent_pdf_id: Parent PDF filename

        Returns:
            True if topic already processed, False otherwise
        """
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT COUNT(*) FROM processed_topics
                WHERE parent_pdf_id = ? AND topic_hash = ?
            """, (parent_pdf_id, topic_hash))

            count = cursor.fetchone()[0]
            return count > 0

        finally:
            conn.close()

    def mark_topic_processed(
        self,
        topic_hash: str,
        parent_pdf_id: str,
        chunk_id: int,
        topic_title: str,
        card_count: int = 0
    ):
        """
        Mark a topic as processed in the database.

        Args:
            topic_hash: SHA256 hash of topic content
            parent_pdf_id: Parent PDF filename
            chunk_id: Chunk ID this topic belongs to
            topic_title: Title/description of topic
            card_count: Number of cards generated for this topic
        """
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT OR IGNORE INTO processed_topics
                (parent_pdf_id, chunk_id, topic_title, topic_hash, processed_at, card_count)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                parent_pdf_id,
                chunk_id,
                topic_title,
                topic_hash,
                datetime.now().isoformat(),
                card_count
            ))

            conn.commit()

        except Exception as e:
            conn.rollback()
            raise RuntimeError(f"Failed to mark topic as processed: {e}")

        finally:
            conn.close()

    def get_processed_topics_count(self, parent_pdf_id: str) -> int:
        """Get count of processed topics for a PDF."""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT COUNT(*) FROM processed_topics
                WHERE parent_pdf_id = ?
            """, (parent_pdf_id,))

            count = cursor.fetchone()[0]
            return count

        finally:
            conn.close()

    def get_processed_topics(self, parent_pdf_id: str) -> List[Dict]:
        """Get all processed topics for a PDF."""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT * FROM processed_topics
                WHERE parent_pdf_id = ?
                ORDER BY processed_at
            """, (parent_pdf_id,))

            topics = [dict(row) for row in cursor.fetchall()]
            return topics

        finally:
            conn.close()


if __name__ == "__main__":
    # Test topic extraction
    import sys

    if len(sys.argv) < 2:
        print("Usage: python topic_extractor.py <pdf_path>")
        sys.exit(1)

    pdf_path = sys.argv[1]

    extractor = TopicExtractor()

    print(f"Extracting topics from {pdf_path}...\n")

    topics = extractor.extract_topics_from_pdf(pdf_path)

    print(f"Found {len(topics)} topics:\n")

    for i, topic in enumerate(topics, 1):
        print(f"{i}. {topic['title']}")
        print(f"   Pages: {topic['page_range']}")
        print(f"   Hash: {topic['hash'][:16]}...")
        print(f"   Length: {len(topic['content'])} chars")
        print()

    # Test batching
    batches = extractor.batch_topics(topics, batch_size=3)
    print(f"\nBatched into {len(batches)} batches of ~3 topics each")

    for i, batch in enumerate(batches, 1):
        print(f"Batch {i}: {len(batch)} topics")
