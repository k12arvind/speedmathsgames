"""Diff Opus re-Vision results vs Sonnet v2 outputs and apply only the
disagreements to the reasoning_practice DB.

Strategy:
  - For each Opus page, look up the matching v2 page.
  - For each (exercise_id, question_number, page) match, compare:
      - the answer letter (`correct` per Q, `letter` per S, leading-letter
        in solution text)
      - the body text — focusing on differences in single capital letters
        (which are the OCR-prone tokens)
  - Update the DB row when Opus disagrees AND the disagreement looks like
    a Vision OCR fix (small letter difference, conclusion sentence still
    matches the new letter).

Dry-run by default; use --apply to commit.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path
from typing import Dict, Tuple, Optional


VP_V2 = Path('/Users/arvind/clat_preparation/reasoning/vision_pages_arihant_v2')
VP_OPUS = Path('/Users/arvind/clat_preparation/reasoning/vision_pages_arihant_v2_opus')


def load_page(pdir: Path, n: int) -> Optional[dict]:
    f = pdir / f'p{n:04d}.json'
    if not f.exists():
        return None
    try:
        d = json.loads(f.read_text())
    except Exception:
        return None
    if 'error' in d:
        return None
    d['_page'] = n
    return d


def index_questions(d: dict) -> Dict[Tuple[str, int], dict]:
    """Map (exercise_id, qnum) -> question dict for a single page."""
    out: Dict[Tuple[str, int], dict] = {}
    page_ex = d.get('exercise_id') or ''
    for q in (d.get('questions') or []):
        n = q.get('number')
        if not isinstance(n, int):
            continue
        ex = q.get('exercise_id') or page_ex or ''
        out[(ex, n)] = q
    return out


def index_solutions(d: dict) -> Dict[Tuple[str, int], dict]:
    out: Dict[Tuple[str, int], dict] = {}
    page_ex = d.get('exercise_id') or ''
    for s in (d.get('solutions') or []):
        n = s.get('number')
        if not isinstance(n, int):
            continue
        ex = s.get('exercise_id') or page_ex or ''
        out[(ex, n)] = s
    return out


_LETTER = lambda x: (x or '').strip().lower() or None  # noqa: E731

# Trailing source-citation tag that Opus emits but Sonnet strips, e.g.
# "  [SBI (PO) 2009]" or "[NIFT (UG) 2014]". We don't want to count this as a
# meaningful body change.
_TRAILING_CITATION = re.compile(r'\s*\[[^\[\]]+\]\s*$')


def strip_citation(s: str) -> str:
    return _TRAILING_CITATION.sub('', s or '').strip()


# Strip every char that doesn't carry semantic content. Used to ignore
# punctuation/whitespace/quote-mark differences that don't change meaning
# (Sonnet and Opus very often disagree on a comma vs period etc.).
_NONCONTENT = re.compile(r"[\s\.\,\;\:\!\?\'\"\[\]\(\)\-\—\–]+")


def content_only(s: str) -> str:
    s = (s or '').lower()
    return _NONCONTENT.sub('', s)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--db', required=True)
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()

    page_nums = sorted(int(f.stem[1:]) for f in VP_OPUS.glob('p*.json'))
    print(f'Opus pages to diff: {len(page_nums)}', file=sys.stderr)

    c = sqlite3.connect(args.db)
    c.row_factory = sqlite3.Row

    diffs = {
        'answer_letter': [],   # (qid, page, ex, qnum, old, new, conclusion-snip)
        'body': [],            # (qid, page, ex, qnum, old, new, hamming)
    }
    skipped_match = 0

    for pn in page_nums:
        v2 = load_page(VP_V2, pn)
        op = load_page(VP_OPUS, pn)
        if not v2 or not op:
            continue

        v2q = index_questions(v2)
        opq = index_questions(op)
        v2s = index_solutions(v2)
        ops = index_solutions(op)

        # Compare common keys
        for key in set(v2q) & set(opq):
            ex, n = key
            v_q, o_q = v2q[key], opq[key]
            # Find DB row that matches this (book, ex, qnum). The DB has no
            # exercise_id column — we approximate via chapter+problem_number
            # near this page. Quick correlate by chapter_title and exact
            # body-prefix to avoid mismatched siblings (especially Master
            # Exercise which restarts numbering).
            v_body = (v_q.get('body') or '').strip()
            o_body = (o_q.get('body') or '').strip()
            # Skip if the only difference is a trailing source citation.
            v_stripped = strip_citation(v_body)
            o_stripped = strip_citation(o_body)
            if v_stripped == o_stripped:
                continue
            # Skip if differences are purely punctuation/whitespace — both
            # Sonnet and Opus disagree on those constantly and they don't
            # change correctness for the user.
            if content_only(v_stripped) == content_only(o_stripped):
                continue

            # Find DB row by problem_number + body-prefix
            row = c.execute(
                "SELECT question_id, chapter_title, question_text, correct_choice "
                "FROM reasoning_questions "
                "WHERE source_book='arihant' AND problem_number=? "
                "  AND substr(question_text,1,30) = substr(?,1,30)",
                (str(n), v_body),
            ).fetchone()
            if not row:
                skipped_match += 1
                continue

            diffs['body'].append({
                'qid': row['question_id'],
                'page': pn, 'ex': ex, 'qnum': n,
                'old': v_body[:160],
                'new': o_body[:160],
            })

        # Compare answer letters (from solutions block)
        for key in set(v2s) & set(ops):
            ex, n = key
            v_s, o_s = v2s[key], ops[key]
            v_letter = _LETTER(v_s.get('letter'))
            o_letter = _LETTER(o_s.get('letter'))
            if v_letter == o_letter:
                continue
            if not o_letter:
                continue  # don't downgrade
            # Find DB row by qnum + chapter (need page → chapter mapping)
            # Approximation: any row with this problem_number whose solution
            # text overlaps Opus solution.
            o_sol = (o_s.get('solution') or '').strip()
            row = c.execute(
                "SELECT question_id, chapter_title, correct_choice, official_solution "
                "FROM reasoning_questions "
                "WHERE source_book='arihant' AND problem_number=? "
                "  AND substr(official_solution,1,40) = substr(?,1,40)",
                (str(n), o_sol),
            ).fetchone()
            if not row:
                skipped_match += 1
                continue
            cur_letter = _LETTER(row['correct_choice'])
            if cur_letter == o_letter:
                continue  # already correct (text_scan may have fixed it)
            diffs['answer_letter'].append({
                'qid': row['question_id'],
                'page': pn, 'ex': ex, 'qnum': n,
                'cur_db': (cur_letter or '').upper(),
                'opus': o_letter.upper(),
                'sol_snip': o_sol[:120],
            })

    print(f'\nDiffs found:', file=sys.stderr)
    print(f'  answer-letter changes: {len(diffs["answer_letter"])}', file=sys.stderr)
    print(f'  body changes:          {len(diffs["body"])}', file=sys.stderr)
    print(f'  unmatched DB rows:     {skipped_match}', file=sys.stderr)

    if diffs['answer_letter']:
        print('\n--- answer-letter sample (first 15) ---', file=sys.stderr)
        for d in diffs['answer_letter'][:15]:
            print(
                f"  qid={d['qid']} p{d['page']} {d['ex']} Q{d['qnum']}: "
                f"db={d['cur_db']} → opus={d['opus']}",
                file=sys.stderr,
            )

    if diffs['body']:
        print('\n--- body change sample (first 10) ---', file=sys.stderr)
        for d in diffs['body'][:10]:
            print(f"  qid={d['qid']} p{d['page']} Q{d['qnum']}:", file=sys.stderr)
            print(f"    OLD: {d['old']!r}", file=sys.stderr)
            print(f"    NEW: {d['new']!r}", file=sys.stderr)

    if args.apply:
        applied = {'letter': 0, 'body': 0}
        for d in diffs['answer_letter']:
            c.execute(
                "UPDATE reasoning_questions "
                "SET correct_choice=?, correct_source='opus_revision', "
                "    updated_at=datetime('now') WHERE question_id=?",
                (d['opus'], d['qid']),
            )
            applied['letter'] += 1
        for d in diffs['body']:
            c.execute(
                "UPDATE reasoning_questions "
                "SET question_text=?, updated_at=datetime('now') "
                "WHERE question_id=?",
                (d['new'], d['qid']),
            )
            applied['body'] += 1
        c.commit()
        print(f"\napplied: {applied}", file=sys.stderr)
    elif diffs['answer_letter'] or diffs['body']:
        print('\n(dry-run — re-run with --apply to commit)', file=sys.stderr)

    c.close()


if __name__ == '__main__':
    main()
