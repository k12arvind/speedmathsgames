"""
Aggregate per-page Vision JSONs for ONE book into the reasoning_practice.db.

Input:  vision_pages_<slug>/p<NNN>.json
Output: rows in reasoning_passages + reasoning_questions + reasoning_question_topics
        (figures copied to ~/saanvi/ReasoningFigures/<slug>/)

Workflow per page, in order:
  1. Forward-fill chapter context (chapter_number / chapter_title) from the
     last page that declared one — most subsequent pages omit it.
  2. Each `passages[]` entry on that page becomes a row in reasoning_passages
     (book_local passage IDs are mapped → DB passage_id).
  3. Each `questions[]` entry becomes a reasoning_questions row, linking to
     its passage if `passage_index` was set on the page.
  4. After all pages, walk through `solutions[]` and `answers[]` from the
     same book (collected globally) and backfill correct_choice / solution
     onto the matching reasoning_questions row by problem_number.
  5. Drop questions where subject != 'verbal'.
  6. For passage-figures or question-figures, copy the source page JPEG to
     ~/saanvi/ReasoningFigures/<slug>/p<NNN>.jpg and store the relative path.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
FIGURES_ROOT = Path.home() / 'saanvi' / 'ReasoningFigures'


def load_pages(vp_dir: Path) -> List[Dict[str, Any]]:
    pages = []
    for f in sorted(vp_dir.glob('p*.json')):
        try:
            d = json.loads(f.read_text())
        except Exception:
            continue
        if 'error' in d:
            continue
        d['_page'] = int(f.stem[1:])
        pages.append(d)
    return pages


def forward_fill_chapter(pages: List[Dict[str, Any]]):
    """Each questions/exercises page should know its enclosing chapter.
    Vision sets chapter_number/title only when visible (typically first
    page of each chapter). Forward-fill across subsequent pages."""
    cur_num: Optional[int] = None
    cur_title: Optional[str] = None
    for p in pages:
        cn = p.get('chapter_number')
        ct = p.get('chapter_title')
        if cn is not None:
            cur_num = cn
            cur_title = ct
        elif ct and not cur_title:
            cur_title = ct
        p['_chapter_number'] = cur_num
        p['_chapter_title'] = cur_title


def aggregate_book(slug: str, vp_dir: Path, render_dir: Path) -> Dict[str, Any]:
    pages = load_pages(vp_dir)
    print(f'  loaded {len(pages)} page extractions', file=sys.stderr)
    forward_fill_chapter(pages)

    # Solutions and answers are keyed by (number, source_page) so we can
    # match them to questions by page proximity. Same question number can
    # appear many times in a book (one per exercise), so we link each Q to
    # the *nearest following* solution with the same number.
    answers_list: List[Dict[str, Any]] = []   # {number, letter, page}
    solutions_list: List[Dict[str, Any]] = [] # {number, solution, page}
    questions: List[Dict[str, Any]] = []
    passages: List[Dict[str, Any]] = []

    figures_dir = FIGURES_ROOT / slug
    figures_dir.mkdir(parents=True, exist_ok=True)

    for p in pages:
        pn = p['_page']
        page_passages = p.get('passages') or []
        # Map this page's passage indices → indices into our `passages` list
        passage_idx_map: Dict[int, int] = {}
        for i, pas in enumerate(page_passages):
            full = {
                **pas,
                'source_book': slug,
                'chapter_number': p['_chapter_number'],
                'chapter_title': p['_chapter_title'],
                '_source_page': pn,
            }
            if pas.get('has_figure'):
                src = render_dir / f'p{pn:04d}.jpg'
                if src.exists():
                    dst = figures_dir / src.name
                    if not dst.exists():
                        shutil.copy2(src, dst)
                    full['_figure_image_path'] = f'/static/ReasoningFigures/{slug}/{src.name}'
            passage_idx_map[i] = len(passages)
            passages.append(full)

        for q in p.get('questions') or []:
            if q.get('subject') and q['subject'] != 'verbal':
                continue
            num = q.get('number')
            if not num:
                continue
            mapped_passage_id = None
            if q.get('passage_index') is not None:
                mapped_passage_id = passage_idx_map.get(q['passage_index'])
            if q.get('has_figure'):
                src = render_dir / f'p{pn:04d}.jpg'
                if src.exists():
                    dst = figures_dir / src.name
                    if not dst.exists():
                        shutil.copy2(src, dst)
                    q['_figure_image_path'] = f'/static/ReasoningFigures/{slug}/{src.name}'
            q['_passage_idx_global'] = mapped_passage_id
            q['_chapter_number'] = p['_chapter_number']
            q['_chapter_title'] = p['_chapter_title']
            q['_source_page'] = pn
            questions.append(q)

        for s in p.get('solutions') or []:
            n = s.get('number')
            if n and s.get('solution'):
                solutions_list.append({'number': n, 'solution': s['solution'], 'page': pn})
        for a in p.get('answers') or []:
            n = a.get('number')
            if n and a.get('correct'):
                answers_list.append({'number': n, 'letter': a['correct'].lower(), 'page': pn})

    # Backfill correct + solution by page-proximity match.
    # For each question, find the nearest solution/answer with the same
    # number that appears on or after the question's page. This avoids
    # gluing Ch.3-Q5 to Ch.7-Q5's solution.
    import re
    # Matches "(c) As ...", "c) As ...", "c. As ...", "c; As ...", "c: As ..."
    # at the start of a solution. The letter must be followed by a clear
    # delimiter so we don't pick up a stray "a" word.
    leading_letter = re.compile(r'^\s*\(?\s*([a-eA-E])\s*[\)\.;:]\s+')

    def _nearest_following(items: List[Dict[str, Any]], num: int, q_page: int):
        best = None
        best_dist = None
        for it in items:
            if it['number'] != num:
                continue
            if it['page'] < q_page:
                continue
            d = it['page'] - q_page
            if best_dist is None or d < best_dist:
                best = it
                best_dist = d
        return best

    num_to_letter = {'1': 'a', '2': 'b', '3': 'c', '4': 'd', '5': 'e'}

    def _norm(v: Optional[str]) -> Optional[str]:
        if not v:
            return None
        v = v.strip().lower()
        if v in 'abcde':
            return v
        if v in num_to_letter:
            return num_to_letter[v]
        return None

    for q in questions:
        qp = q.get('_source_page', 0)
        q['correct'] = _norm(q.get('correct'))

        # Prefer solution-text leading-letter (more reliable than the
        # consolidated answer-key tables, which Vision sometimes glues
        # across multiple exercises).
        sol = _nearest_following(solutions_list, q['number'], qp)
        if sol:
            if not q.get('solution'):
                q['solution'] = sol['solution']
            if not q.get('correct'):
                m = leading_letter.match(sol['solution'])
                if m:
                    q['correct'] = m.group(1).lower()

        # Fallback to answer-key page (normalized — books use either letters
        # or 1..5 numbers).
        if not q.get('correct'):
            ans = _nearest_following(answers_list, q['number'], qp)
            if ans:
                q['correct'] = _norm(ans['letter'])

    print(f'  aggregated: {len(passages)} passages, {len(questions)} questions',
          file=sys.stderr)
    print(f'    with answer: {sum(1 for q in questions if q.get("correct"))}',
          file=sys.stderr)
    return {'passages': passages, 'questions': questions}


def insert_into_db(slug: str, agg: Dict[str, Any]) -> Dict[str, int]:
    db_path = PROJECT_ROOT / 'reasoning_practice.db'

    # Trigger schema migration via the class
    sys.path.insert(0, str(PROJECT_ROOT))
    from reasoning.practice_db import ReasoningPracticeDB
    ReasoningPracticeDB(str(db_path))

    c = sqlite3.connect(str(db_path))
    c.row_factory = sqlite3.Row

    # Idempotent: clear prior rows from this source_book
    c.execute("DELETE FROM reasoning_questions WHERE source_book = ?", (slug,))
    c.execute("DELETE FROM reasoning_passages  WHERE source_book = ?", (slug,))
    c.commit()

    # Insert passages first to get DB IDs
    passage_db_id: Dict[int, int] = {}  # global idx -> db passage_id
    for i, pas in enumerate(agg['passages']):
        cur = c.execute("""
            INSERT INTO reasoning_passages
                (source_book, chapter_number, chapter_title, passage_text,
                 figure_image_path, question_count, added_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            pas['source_book'],
            pas.get('chapter_number'),
            pas.get('chapter_title'),
            pas.get('passage_text', ''),
            pas.get('_figure_image_path'),
            0,  # we'll fix this below
            _now(),
        ))
        passage_db_id[i] = cur.lastrowid

    inserted = 0
    pending_ai = 0
    skipped_no_choices = 0
    for q in agg['questions']:
        choices = q.get('choices') or {}
        if not all(choices.get(L) for L in 'abcd'):
            skipped_no_choices += 1
            continue

        passage_id = None
        if q.get('_passage_idx_global') is not None:
            passage_id = passage_db_id.get(q['_passage_idx_global'])

        has_answer = bool(q.get('correct'))
        # No answer letter but a solution explanation → AI-derive will fill it.
        # Mark needs_review so it stays hidden from Saanvi until then.
        # No answer AND no solution → permanently skip (nothing to derive from).
        if not has_answer and not q.get('solution'):
            skipped_no_choices += 1  # treat as junk
            continue
        parse_status = 'ok' if has_answer else 'needs_review'
        correct_source = 'official' if has_answer else 'pending_ai'
        if not has_answer:
            pending_ai += 1

        cur = c.execute("""
            INSERT INTO reasoning_questions
                (source_book, chapter_number, chapter_title, problem_number,
                 passage_id, seq_in_passage,
                 question_text, choice_a, choice_b, choice_c, choice_d, choice_e,
                 correct_choice, official_solution,
                 figure_image_path, parse_status, correct_source,
                 added_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            slug,
            q.get('_chapter_number'),
            q.get('_chapter_title'),
            str(q['number']),
            passage_id,
            q.get('seq_in_passage'),
            q.get('body', ''),
            choices.get('a'),
            choices.get('b'),
            choices.get('c'),
            choices.get('d'),
            choices.get('e'),
            (q.get('correct') or '').upper() or None,
            q.get('solution'),
            q.get('_figure_image_path'),
            parse_status,
            correct_source,
            _now(), _now(),
        ))
        qid = cur.lastrowid
        topic_code = q.get('topic_code') or 'general'
        topic_name = q.get('topic_name') or topic_code.replace('_', ' ').title()
        sub_code = q.get('subtopic_code') or ''
        sub_name = q.get('subtopic_name') or ''
        c.execute("""
            INSERT INTO reasoning_question_topics
                (question_id, topic_code, topic_name, subtopic_code, subtopic_name, is_active)
            VALUES (?, ?, ?, ?, ?, 1)
        """, (qid, topic_code, topic_name, sub_code, sub_name))
        inserted += 1

    # Update passage question_count
    c.execute("""
        UPDATE reasoning_passages
        SET question_count = (
            SELECT COUNT(*) FROM reasoning_questions
            WHERE passage_id = reasoning_passages.passage_id
        )
        WHERE source_book = ?
    """, (slug,))

    # Drop passages with zero linked questions (cleanup)
    c.execute("DELETE FROM reasoning_passages WHERE source_book = ? AND question_count = 0", (slug,))
    c.commit()
    c.close()

    return {
        'inserted': inserted,
        'pending_ai': pending_ai,
        'skipped_no_choices': skipped_no_choices,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('slug', help='source_book identifier, e.g. arihant or mkpandey')
    ap.add_argument('--vision-dir', required=True, type=str)
    ap.add_argument('--render-dir', required=True, type=str)
    args = ap.parse_args()

    print(f'\n=== {args.slug} ===', file=sys.stderr)
    agg = aggregate_book(args.slug, Path(args.vision_dir), Path(args.render_dir))
    out = insert_into_db(args.slug, agg)
    print(f'  inserted: {out["inserted"]} (pending AI-derive: {out["pending_ai"]})', file=sys.stderr)
    print(f'  skipped (incomplete/no usable data): {out["skipped_no_choices"]}', file=sys.stderr)


if __name__ == '__main__':
    main()
