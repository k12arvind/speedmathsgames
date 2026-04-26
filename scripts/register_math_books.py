#!/usr/bin/env python3
"""
register_math_books.py

Reads `book.json` from each converted book under MathsBooksHTML/ and inserts /
updates the corresponding rows in `math_books` and `math_book_chapters`.

Idempotent — safe to re-run any time. Should be invoked after the batch
converter finishes (locally) and again on the VM after the HTMLs are rsynced.
"""

from __future__ import annotations

import json
from pathlib import Path

from amc10.practice_db import AMC10PracticeDB


HTML_ROOT = Path.home() / 'saanvi' / 'MathsBooksHTML'


def main():
    db = AMC10PracticeDB()
    if not HTML_ROOT.exists():
        print(f'No HTML root at {HTML_ROOT}, nothing to register')
        return

    registered = 0
    for book_dir in sorted(HTML_ROOT.iterdir()):
        meta_path = book_dir / 'book.json'
        if not meta_path.exists():
            continue
        try:
            meta = json.loads(meta_path.read_text())
        except Exception as e:
            print(f'⚠️  {book_dir.name}: bad book.json ({e})')
            continue

        book_id = meta['book_id']
        # Compute total file size of all images for the storage estimate
        total_kb = sum(p.stat().st_size for p in book_dir.glob('*.jpg')) // 1024
        if total_kb == 0:
            total_kb = sum(p.stat().st_size for p in book_dir.glob('*.png')) // 1024

        db.upsert_book(
            book_id=book_id,
            title=meta['book_title'],
            pdf_filename=meta.get('pdf_filename'),
            total_pages=meta['total_pages'],
            chapter_count=len(meta.get('chapters', [])),
            detection_method=meta.get('detection_method', 'unknown'),
            file_size_kb=total_kb,
        )
        db.replace_book_chapters(book_id, meta.get('chapters', []))
        print(f'✅ {book_id:<35} {meta["total_pages"]:>4} pages, {len(meta.get("chapters", [])):>2} chapters, {total_kb/1024:>5.1f} MB')
        registered += 1

    print()
    print(f'Registered {registered} books')


if __name__ == '__main__':
    main()
