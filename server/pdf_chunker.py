#!/usr/bin/env python3
"""
PDF Chunker
Splits large PDFs into smaller chunks with progress tracking.

CROSS-MACHINE COMPATIBILITY:
- Uses relative paths (relative to home directory) for database storage
- This allows the same database to work on both MacBook Pro and Mac Mini
"""

import PyPDF2
from pathlib import Path
from typing import List, Dict, Generator
import json
import sqlite3
from datetime import datetime
import shutil
from server.pdf_scanner import path_to_relative, relative_to_absolute


class PdfChunker:
    """Handles PDF chunking operations with progress tracking."""

    def __init__(self, db_path: str = None):
        """Initialize with database path."""
        if db_path is None:
            db_path = str(Path.home() / 'clat_preparation' / 'revision_tracker.db')
        self.db_path = db_path

    def chunk_pdf(
        self,
        input_path: str,
        output_dir: str,
        max_pages: int = 10,
        naming_pattern: str = "{basename}_part{num}",
        overlap_pages: bool = True
    ) -> Generator[Dict, None, None]:
        """
        Split PDF into chunks and yield progress updates.

        Args:
            input_path: Path to input PDF
            output_dir: Directory to save chunks
            max_pages: Maximum pages per chunk
            naming_pattern: Pattern for chunk filenames
            overlap_pages: If True, last page of each chunk becomes first page of next chunk

        Yields:
            dict: Progress updates with type: 'progress', 'chunk_created', 'error', 'complete'
        """
        try:
            input_pdf = Path(input_path)
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)

            # Open PDF
            yield {
                'type': 'progress',
                'message': f'Opening PDF: {input_pdf.name}',
                'percent_complete': 5
            }

            with open(input_pdf, 'rb') as pdf_file:
                reader = PyPDF2.PdfReader(pdf_file)
                total_pages = len(reader.pages)

                # Calculate number of chunks needed
                # With overlap: each chunk after the first shares 1 page with the previous
                # So effective advance per chunk is (max_pages - 1) except for the first chunk
                if overlap_pages:
                    # Formula: 1 + ceil((total_pages - max_pages) / (max_pages - 1))
                    # Simplified: ceil((total_pages - 1) / (max_pages - 1))
                    if total_pages <= max_pages:
                        initial_chunks = 1
                    else:
                        initial_chunks = 1 + ((total_pages - max_pages - 1) // (max_pages - 1)) + 1
                else:
                    initial_chunks = (total_pages + max_pages - 1) // max_pages

                # Calculate what the last chunk size would be
                if overlap_pages and initial_chunks > 1:
                    # Last chunk starts at: (initial_chunks - 1) * (max_pages - 1)
                    last_chunk_start = (initial_chunks - 1) * (max_pages - 1)
                    remaining_pages = total_pages - last_chunk_start
                else:
                    remaining_pages = total_pages % max_pages
                    if remaining_pages == 0:
                        remaining_pages = max_pages

                # Smart chunk calculation: avoid tiny final chunks (1-3 pages)
                # If final chunk would be too small, extend second-to-last chunk instead
                MIN_CHUNK_SIZE = 4
                if initial_chunks > 1 and remaining_pages < MIN_CHUNK_SIZE:
                    total_chunks = initial_chunks - 1
                    extend_last_chunk = True
                else:
                    total_chunks = initial_chunks
                    extend_last_chunk = False

                yield {
                    'type': 'info',
                    'message': f'PDF has {total_pages} pages, will create {total_chunks} chunks',
                    'total_pages': total_pages,
                    'total_chunks': total_chunks
                }

                chunks = []
                previous_end_page = 0

                for chunk_num in range(total_chunks):
                    # Calculate page range with overlap
                    if overlap_pages and chunk_num > 0:
                        # Start from last page of previous chunk (overlap)
                        start_page = previous_end_page - 1
                    else:
                        # First chunk starts from page 0
                        start_page = chunk_num * max_pages

                    # For the last chunk, if we're extending it, go to the end of the PDF
                    if chunk_num == total_chunks - 1 and extend_last_chunk:
                        end_page = total_pages
                    else:
                        end_page = min(start_page + max_pages, total_pages)

                    previous_end_page = end_page

                    yield {
                        'type': 'progress',
                        'message': f'Creating chunk {chunk_num + 1}/{total_chunks} (pages {start_page + 1}-{end_page})',
                        'current_chunk': chunk_num + 1,
                        'total_chunks': total_chunks,
                        'percent_complete': int((chunk_num / total_chunks) * 90)
                    }

                    # Create chunk
                    writer = PyPDF2.PdfWriter()
                    for page_num in range(start_page, end_page):
                        writer.add_page(reader.pages[page_num])

                    # Generate output filename
                    basename = input_pdf.stem
                    chunk_filename = naming_pattern.format(
                        basename=basename,
                        num=chunk_num + 1
                    ) + '.pdf'
                    chunk_path = output_path / chunk_filename

                    # Write chunk
                    with open(chunk_path, 'wb') as output_file:
                        writer.write(output_file)

                    file_size = chunk_path.stat().st_size / 1024

                    chunk_info = {
                        'filename': chunk_filename,
                        'path': str(chunk_path),
                        'chunk_number': chunk_num + 1,
                        'start_page': start_page + 1,
                        'end_page': end_page,
                        'total_pages': end_page - start_page,
                        'size_kb': round(file_size, 2)
                    }
                    chunks.append(chunk_info)

                    yield {
                        'type': 'chunk_created',
                        **chunk_info
                    }

                    # Save to database
                    self._save_chunk_to_db(
                        input_pdf.name,
                        chunk_info,
                        original_file_path=str(input_pdf.absolute()),
                        overlap_enabled=overlap_pages,
                        max_pages=max_pages
                    )

                # Mark original PDF as chunked (hide it from main tabs)
                self.mark_original_as_chunked(input_pdf.name)

                # Move original file to large_files folder and copy chunks to original location
                yield {
                    'type': 'progress',
                    'message': 'Moving original file to large_files folder...',
                    'percent_complete': 95
                }

                original_folder = input_pdf.parent
                large_files_dir = Path.home() / 'Desktop' / 'saanvi' / 'large_files'
                large_files_dir.mkdir(parents=True, exist_ok=True)

                # Move original file to large_files
                large_file_dest = large_files_dir / input_pdf.name
                if input_pdf.exists():
                    shutil.move(str(input_pdf), str(large_file_dest))

                    yield {
                        'type': 'progress',
                        'message': f'Moved original to {large_file_dest}',
                        'percent_complete': 97
                    }

                # Copy chunks from output_dir to original folder
                yield {
                    'type': 'progress',
                    'message': 'Copying chunks to original folder...',
                    'percent_complete': 98
                }

                for chunk_info in chunks:
                    chunk_src = Path(chunk_info['path'])
                    chunk_dest = original_folder / chunk_src.name
                    if chunk_src.exists():
                        shutil.copy2(str(chunk_src), str(chunk_dest))
                        # Update chunk path in database to point to new location
                        chunk_info['path'] = str(chunk_dest)

                yield {
                    'type': 'complete',
                    'message': f'Successfully created {len(chunks)} chunks and moved original file',
                    'total_chunks': len(chunks),
                    'chunks': chunks,
                    'original_moved_to': str(large_file_dest),
                    'percent_complete': 100
                }

        except Exception as e:
            yield {
                'type': 'error',
                'message': str(e),
                'error': str(e)
            }

    def _save_chunk_to_db(self, parent_pdf_id: str, chunk_info: Dict, original_file_path: str = None,
                          overlap_enabled: bool = False, max_pages: int = 10):
        """Save chunk metadata to database and add chunk to main pdfs table."""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        cursor = conn.cursor()

        # Convert paths to relative for cross-machine compatibility
        relative_chunk_path = path_to_relative(chunk_info['path'])
        relative_original_path = path_to_relative(original_file_path) if original_file_path else None

        try:
            cursor.execute("""
                INSERT INTO pdf_chunks
                (parent_pdf_id, chunk_filename, chunk_path, chunk_number,
                 start_page, end_page, total_pages, file_size_kb,
                 original_file_path, overlap_enabled, max_pages_per_chunk)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                parent_pdf_id,
                chunk_info['filename'],
                relative_chunk_path,
                chunk_info['chunk_number'],
                chunk_info['start_page'],
                chunk_info['end_page'],
                chunk_info['total_pages'],
                chunk_info['size_kb'],
                relative_original_path,
                1 if overlap_enabled else 0,
                max_pages
            ))

            # Also add chunk to main pdfs table so it appears in weekly/daily tabs
            # First, get metadata from original PDF if it exists
            cursor.execute("""
                SELECT source_name, date_published, source_type
                FROM pdfs
                WHERE filename = ?
            """, (parent_pdf_id,))

            original_metadata = cursor.fetchone()

            if original_metadata:
                source_name, date_published, source_type = original_metadata

                # Insert chunk into pdfs table (using relative path)
                cursor.execute("""
                    INSERT OR IGNORE INTO pdfs
                    (filename, filepath, source_name, date_published, source_type, is_chunk, parent_pdf, date_added)
                    VALUES (?, ?, ?, ?, ?, 1, ?, datetime('now'))
                """, (
                    chunk_info['filename'],
                    relative_chunk_path,  # Use relative path for cross-machine compatibility
                    source_name,
                    date_published,
                    source_type,
                    parent_pdf_id
                ))

            conn.commit()
        except sqlite3.IntegrityError:
            # Chunk already exists, skip
            pass
        except Exception as e:
            conn.rollback()
            raise RuntimeError(f"Failed to save chunk to database: {e}")
        finally:
            conn.close()

    def mark_original_as_chunked(self, parent_pdf_id: str) -> bool:
        """Mark original PDF as chunked (hide it from main tabs)."""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        cursor = conn.cursor()

        try:
            # Update original PDF to mark it as chunked
            cursor.execute("""
                UPDATE pdfs
                SET is_chunked = 1
                WHERE filename = ?
            """, (parent_pdf_id,))

            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            conn.rollback()
            raise RuntimeError(f"Failed to mark PDF as chunked: {e}")
        finally:
            conn.close()

    def delete_original_file(self, parent_pdf_id: str, original_file_path: str) -> bool:
        """Mark original file as deleted and optionally remove it from disk."""
        import os
        from datetime import datetime

        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        cursor = conn.cursor()

        try:
            # Mark all chunks of this PDF as having deleted original
            cursor.execute("""
                UPDATE pdf_chunks
                SET original_file_deleted = 1,
                    deletion_timestamp = ?
                WHERE parent_pdf_id = ?
            """, (datetime.now().isoformat(), parent_pdf_id))

            conn.commit()

            # Actually delete the file if it exists
            if os.path.exists(original_file_path):
                os.remove(original_file_path)
                return True
            return False

        except Exception as e:
            conn.rollback()
            raise RuntimeError(f"Failed to mark file as deleted: {e}")
        finally:
            conn.close()

    def get_chunks(self, parent_pdf_id: str) -> List[Dict]:
        """Get all chunks for a parent PDF."""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT * FROM pdf_chunks
                WHERE parent_pdf_id = ?
                ORDER BY chunk_number
            """, (parent_pdf_id,))

            chunks = [dict(row) for row in cursor.fetchall()]
            return chunks

        finally:
            conn.close()

    def delete_chunks(self, parent_pdf_id: str) -> int:
        """Delete all chunks for a parent PDF."""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        cursor = conn.cursor()

        try:
            # Get chunk paths before deleting
            cursor.execute("""
                SELECT chunk_path FROM pdf_chunks
                WHERE parent_pdf_id = ?
            """, (parent_pdf_id,))

            chunk_paths = [row[0] for row in cursor.fetchall()]

            # Delete from database
            cursor.execute("""
                DELETE FROM pdf_chunks
                WHERE parent_pdf_id = ?
            """, (parent_pdf_id,))

            deleted_count = cursor.rowcount
            conn.commit()

            # Delete physical files
            for chunk_path in chunk_paths:
                try:
                    Path(chunk_path).unlink(missing_ok=True)
                except Exception as e:
                    print(f"Warning: Could not delete {chunk_path}: {e}")

            return deleted_count

        except Exception as e:
            conn.rollback()
            raise RuntimeError(f"Failed to delete chunks: {e}")
        finally:
            conn.close()

    def is_chunked(self, parent_pdf_id: str) -> bool:
        """Check if a PDF has been chunked."""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT COUNT(*) FROM pdf_chunks
                WHERE parent_pdf_id = ?
            """, (parent_pdf_id,))

            count = cursor.fetchone()[0]
            return count > 0

        finally:
            conn.close()

    @staticmethod
    def get_pdf_page_count(pdf_path: str) -> int:
        """Get the number of pages in a PDF file."""
        try:
            with open(pdf_path, 'rb') as pdf_file:
                reader = PyPDF2.PdfReader(pdf_file)
                return len(reader.pages)
        except Exception as e:
            print(f"Error getting page count for {pdf_path}: {e}")
            return 0


if __name__ == "__main__":
    # Test chunking
    import sys

    if len(sys.argv) < 3:
        print("Usage: python pdf_chunker.py <input_pdf> <output_dir> [max_pages]")
        sys.exit(1)

    input_path = sys.argv[1]
    output_dir = sys.argv[2]
    max_pages = int(sys.argv[3]) if len(sys.argv) > 3 else 10

    chunker = PdfChunker()

    print(f"Chunking {input_path} into {output_dir} (max {max_pages} pages per chunk)...\n")

    for update in chunker.chunk_pdf(input_path, output_dir, max_pages):
        if update['type'] == 'progress':
            print(f"[{update['percent_complete']}%] {update['message']}")
        elif update['type'] == 'info':
            print(f"ℹ️  {update['message']}")
        elif update['type'] == 'chunk_created':
            print(f"✅ Created: {update['filename']} ({update['total_pages']} pages, {update['size_kb']} KB)")
        elif update['type'] == 'complete':
            print(f"\n🎉 {update['message']}")
        elif update['type'] == 'error':
            print(f"❌ Error: {update['message']}")
            sys.exit(1)
