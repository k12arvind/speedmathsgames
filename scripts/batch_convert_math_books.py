#!/usr/bin/env python3
"""
batch_convert_math_books.py

Copies the 15 AoPS books from iCloud → /Users/arvind/saanvi/MathsBooks/
and converts each to a browsable HTML reader under
/Users/arvind/saanvi/MathsBooksHTML/<book_id>/.

Idempotent: skips a book if its HTML output dir already has a book.json
and the same number of pages. To force re-conversion delete the output
folder first.
"""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.convert_math_book_to_html import convert  # noqa: E402


SRC_ROOT = Path.home() / 'Library' / 'Mobile Documents' / 'com~apple~CloudDocs' / 'Desktop' / 'navya' / 'maths'
PDF_ROOT = Path.home() / 'saanvi' / 'MathsBooks'
HTML_ROOT = Path.home() / 'saanvi' / 'MathsBooksHTML'

# (book_id, source filename glob, display title)
# Picked one PDF per book — for duplicates (e.g. Volume 2 twice, Number Theory twice)
# we keep the more complete copy.
BOOKS = [
    ('aops_prealgebra',
     '813311573-Prealgebra-*.pdf',
     'AoPS Prealgebra'),
    ('aops_intro_algebra',
     '437543552-*Introduction-to-Algebra*.pdf',
     'AoPS Introduction to Algebra'),
    ('aops_intro_geometry',
     '604567594-Introduction-to-Geometry.pdf',
     'AoPS Introduction to Geometry'),
    ('aops_intro_geometry_2007',
     '543300066-Art-of-Problem-Solving-Richard-Rusczyk-Introduction-to-Geometry-AoPS-2007.pdf',
     'AoPS Introduction to Geometry (2007 edition)'),
    ('aops_intro_geometry_solutions',
     '761126798-Introduction-to-Geometry-Solutions-Manual-*.pdf',
     'AoPS Introduction to Geometry — Solutions Manual'),
    ('aops_intro_number_theory',
     '656073318-Introduction-to-Number-Theory-AOPS-Part-I-1.pdf',
     'AoPS Introduction to Number Theory'),
    ('aops_intro_number_theory_solutions',
     '893227125-The-Art-of-Problem-Solving-Introduction-to-Number-Theory-Solutions-Manual-*.pdf',
     'AoPS Number Theory — Solutions Manual'),
    ('aops_intermediate_algebra',
     '869589046-06-Intermediate-Algebra.pdf',
     'AoPS Intermediate Algebra'),
    ('aops_intermediate_algebra_2008',
     'pdfcoffee.com_rusczyk-r-intermediate-algebra-the-art-of-problem-solving-2008-pdf-free.pdf',
     'AoPS Intermediate Algebra (2008 edition)'),
    ('aops_volume_2',
     '518010977-Art-of-Problem-Solving-Volume-2-and-Beyond-by-Sandor-Lehoczky-Richard-Rusczyk.pdf',
     'AoPS Volume 2 and Beyond'),
    ('aops_volume_2_alt',
     '504661157-Pdfcoffee-com-the-Art-of-Problem-Solving-Volume-2-and-Beyond-by-Richard-Rusczyk-*.pdf',
     'AoPS Volume 2 and Beyond (alt edition)'),
    ('zeitz_art_and_craft',
     'Paul_Zeitz_The_Art_and_Craft_of_Problem_Solving*.pdf',
     'Paul Zeitz — The Art and Craft of Problem Solving'),
    ('engel_problem_solving',
     'problem-books-in-mathematics-problem-solving-strategies.pdf',
     'Engel — Problem-Solving Strategies'),
    ('aops_intro_number_theory_dup',
     '656073318-Introduction-to-Number-Theory-AOPS-Part-I.pdf',
     'AoPS Introduction to Number Theory (alt copy)'),
    ('aops_intro_algebra_dup',
     '437543552-341854248-The-AoPS-Introduction-to-Algebra-pdf.pdf',
     'AoPS Introduction to Algebra (alt copy)'),
]


def find_source(pattern: str) -> Path | None:
    for p in SRC_ROOT.glob(pattern):
        return p
    return None


def needs_conversion(html_dir: Path, expected_pages: int) -> bool:
    meta = html_dir / 'book.json'
    if not meta.exists():
        return True
    try:
        data = json.loads(meta.read_text())
        if data.get('total_pages') != expected_pages:
            return True
        # Spot-check that index.html exists and has at least one chapter file
        if not (html_dir / 'index.html').exists():
            return True
        return False
    except Exception:
        return True


def copy_pdf(src: Path, dst: Path) -> bool:
    if dst.exists() and dst.stat().st_size == src.stat().st_size:
        return False  # already there
    PDF_ROOT.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return True


def main():
    PDF_ROOT.mkdir(parents=True, exist_ok=True)
    HTML_ROOT.mkdir(parents=True, exist_ok=True)

    print(f'📚 Source : {SRC_ROOT}')
    print(f'📂 PDFs   : {PDF_ROOT}')
    print(f'🌐 HTML   : {HTML_ROOT}')
    print()

    converted, skipped, missing = [], [], []
    t_start = time.time()

    for book_id, pattern, title in BOOKS:
        src = find_source(pattern)
        if not src:
            print(f'⚠️  {book_id:35} not found ({pattern})')
            missing.append(book_id)
            continue

        local_pdf = PDF_ROOT / f'{book_id}.pdf'
        copied = copy_pdf(src, local_pdf)
        # Open just enough to read page count for the idempotency check.
        import fitz
        doc = fitz.open(str(local_pdf))
        page_count = doc.page_count
        doc.close()

        html_dir = HTML_ROOT / book_id
        if not needs_conversion(html_dir, page_count):
            print(f'⏭  {book_id:35} already converted ({page_count} pages)')
            skipped.append(book_id)
            continue

        prefix = '🆕' if copied else '🔄'
        print(f'{prefix} {book_id:35} {page_count} pages  →  converting…')
        try:
            convert(local_pdf, HTML_ROOT, book_id=book_id, book_title=title, verbose=False)
            converted.append(book_id)
        except Exception as e:
            print(f'❌ {book_id} failed: {e}')

    elapsed = time.time() - t_start
    print()
    print('=' * 60)
    print(f'Converted: {len(converted)}  Skipped: {len(skipped)}  Missing: {len(missing)}')
    print(f'Elapsed: {elapsed/60:.1f} min')
    if missing:
        print(f'Missing: {missing}')


if __name__ == '__main__':
    main()
