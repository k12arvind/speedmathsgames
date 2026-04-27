#!/usr/bin/env python3
"""
register_physics_books.py

Reads `book.json` from each converted book under PhysicsBooksHTML/ and inserts /
updates the corresponding rows in `physics_books` and `physics_book_chapters`.

Idempotent — safe to re-run any time.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Make project imports work whether run from project root or scripts/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from physics.practice_db import PhysicsPracticeDB


HTML_ROOT = Path.home() / 'saanvi' / 'PhysicsBooksHTML'


def main():
    # On the VM, www-data's home is /var/www, but the unified server initializes
    # the DB at <repo-root>/physics_practice.db (sibling of server/). Use the
    # same path here so registration writes to the DB the server actually reads.
    db_path = Path(__file__).resolve().parent.parent / 'physics_practice.db'
    db = PhysicsPracticeDB(str(db_path))
    print(f'Using DB: {db_path}')
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
