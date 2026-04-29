"""
End-to-end processor for a SINGLE NSEJS-style practice/mock/year PDF.

Usage:
  python process_paper.py <pdf_path> --slug <slug> --chapter-num <int> --label <str>

Steps:
  1. Render all pages of the PDF to /tmp/nsejs_<slug>_pages/p<NNN>.jpg
  2. Run vision_extract on those (parallelized, resumable)
  3. Aggregate every question across the pages into one list (single-paper —
     no year-boundary inference needed, unlike the multi-year bundle).
  4. Backfill correct_choice from any answer-key/solution pages found.
  5. Write physics/nsejs/nsejs_<slug>_classified.json
  6. Insert into physics_practice.db via insert_questions.main()

The chapter_number scheme keeps mocks/practice PDFs separate from year
papers (years use 2008..2019, mocks/etc. use 8001..8099).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

import fitz  # PyMuPDF

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from physics.nsejs.insert_questions import main as insert_main


HERE = Path(__file__).parent
VISION_EXTRACT = HERE / 'vision_extract.py'


def render_pages(pdf_path: Path, slug: str, dpi: int = 144) -> Path:
    """Render all pages of pdf to /tmp/nsejs_<slug>_pages/. Idempotent."""
    out = Path(f'/tmp/nsejs_{slug}_pages')
    out.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(pdf_path)
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)
    rendered = 0
    for i in range(doc.page_count):
        target = out / f'p{i+1:03d}.jpg'
        if target.exists() and target.stat().st_size > 0:
            continue
        pix = doc[i].get_pixmap(matrix=mat, alpha=False)
        pix.pil_save(str(target), format='JPEG', quality=85, optimize=True)
        rendered += 1
    print(f'  rendered {rendered} new pages ({doc.page_count} total)', file=sys.stderr)
    return out


def run_vision(pages_dir: Path, slug: str, parallel: int = 6) -> Path:
    """Run vision_extract.py on pages_dir → vision_pages_<slug>/."""
    out_dir = HERE / f'vision_pages_{slug}'
    out_dir.mkdir(parents=True, exist_ok=True)
    # Determine page count from rendered images
    page_files = sorted(pages_dir.glob('p*.jpg'))
    if not page_files:
        print(f'  no rendered pages in {pages_dir}', file=sys.stderr)
        return out_dir
    end_page = max(int(p.stem[1:]) for p in page_files)
    cmd = [
        sys.executable, str(VISION_EXTRACT),
        '--start', '1', '--end', str(end_page),
        '--parallel', str(parallel),
        '--pages-dir', str(pages_dir),
        '--out-dir', str(out_dir),
    ]
    print(f'  running vision: {" ".join(cmd[2:])}', file=sys.stderr)
    subprocess.run(cmd, check=True)
    return out_dir


def aggregate(out_dir: Path, slug: str) -> dict:
    """Walk every page JSON for this PDF, build one questions list.
    For a single-paper PDF (mock/practice/single year), there's no year
    boundary inference — questions/answers/solutions all belong to the
    same paper."""
    questions: dict[int, dict] = {}
    answers: dict[int, str] = {}
    solutions: dict[int, str] = {}
    n_pages = 0
    page_types = defaultdict(int)

    for f in sorted(out_dir.glob('p*.json')):
        d = json.loads(f.read_text())
        if 'error' in d:
            continue
        n_pages += 1
        page_types[d.get('page_type', '?')] += 1
        for q in d.get('questions') or []:
            num = q.get('number')
            if not num:
                continue
            existing = questions.get(num)
            if existing is None:
                questions[num] = q
            else:
                # Prefer the version with `correct` filled in, or longer body
                if not existing.get('correct') and q.get('correct'):
                    questions[num] = q
                elif len(q.get('body', '')) > len(existing.get('body', '')):
                    questions[num] = q
        for a in d.get('answers') or []:
            n = a.get('number')
            if n and a.get('correct'):
                answers[n] = (a['correct'] or '').lower()
        for s in d.get('solutions') or []:
            n = s.get('number')
            if n and s.get('solution'):
                solutions[n] = s['solution']

    # Backfill correct + solution
    out_questions = []
    for num, q in sorted(questions.items()):
        if not q.get('correct') and answers.get(num):
            q['correct'] = answers[num]
        if not q.get('solution') and solutions.get(num):
            q['solution'] = solutions[num]
        # Normalize choices
        ch = q.get('choices') or {}
        if not isinstance(ch, dict):
            ch = {}
        for k in ('a', 'b', 'c', 'd'):
            ch.setdefault(k, '')
        q['choices'] = ch
        out_questions.append(q)

    print(f'  aggregated: {n_pages} pages, page_types={dict(page_types)}, '
          f'unique Qs={len(out_questions)}, '
          f'with-answer={sum(1 for q in out_questions if q.get("correct"))}',
          file=sys.stderr)

    out = {
        'paper': slug,
        'paper_code': '',
        'source_pdf': '',
        'questions': out_questions,
    }
    out_path = HERE / f'nsejs_{slug}_classified.json'
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('pdf', type=str)
    ap.add_argument('--slug', required=True, help='used for filenames + tmp dirs')
    ap.add_argument('--chapter-num', required=True, type=int, help='chapter_number in physics_book_chapters')
    ap.add_argument('--label', required=True, help='human title shown in UI')
    ap.add_argument('--parallel', type=int, default=6)
    ap.add_argument('--skip-vision', action='store_true', help='reuse existing per-page JSONs')
    ap.add_argument('--skip-render', action='store_true', help='reuse existing rendered images')
    args = ap.parse_args()

    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        print(f'no such PDF: {pdf_path}', file=sys.stderr)
        sys.exit(1)

    print(f'\n=== Processing {pdf_path.name} as {args.slug} (ch={args.chapter_num}) ===', file=sys.stderr)

    pages_dir = Path(f'/tmp/nsejs_{args.slug}_pages')
    if not args.skip_render:
        pages_dir = render_pages(pdf_path, args.slug)
    out_dir = HERE / f'vision_pages_{args.slug}'
    if not args.skip_vision:
        out_dir = run_vision(pages_dir, args.slug, parallel=args.parallel)

    aggregate(out_dir, args.slug)

    # Insert
    print(f'  inserting into physics_practice.db...', file=sys.stderr)
    insert_main(args.slug, args.chapter_num, args.label)


if __name__ == '__main__':
    main()
