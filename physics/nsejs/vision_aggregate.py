"""
Aggregate per-page Vision extractions (vision_pages/p<NNN>.json) into
per-year question files (nsejs_<YYYY>_classified.json) compatible with
insert_questions.py.

Year boundary inference:
  1. Forward-fill year from explicit headers.
  2. Detect "section resets": when question number drops back to 1 on a page
     that has the same forward-filled year, treat that as a new year boundary.
  3. Solutions / answer-keys belong to the most recent year-anchored question
     block — we re-anchor them when the question_number on a solutions page
     conflicts with the current year context (e.g., resets to 1).

Then for each year:
  - Build a final question list (deduped by number)
  - Fill in `correct` from answer-keys / solutions whenever possible
  - Drop physics questions that are unanswerable due to figures
  - Write per-year JSON file matching nsejs_2019_20_classified.json shape
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

VISION_DIR = Path(__file__).parent / 'vision_pages'
OUT_DIR = Path(__file__).parent


def normalize_year(label: str | None) -> str | None:
    if not label:
        return None
    m = re.match(r'(\d{4})\s*[-–]\s*(\d{2,4})', str(label))
    if not m:
        return None
    yyyy = int(m.group(1))
    return f'{yyyy:04d}_{int(m.group(2)) % 100:02d}'  # e.g. 2010_11


def load_pages() -> list[dict]:
    pages = []
    for p in sorted(VISION_DIR.glob('p*.json')):
        d = json.loads(p.read_text())
        d['_page'] = int(p.stem[1:])
        if 'error' in d:
            print(f'  {p.name}: ERROR {d["error"][:80]}')
            continue
        pages.append(d)
    return pages


def assign_years(pages: list[dict]) -> None:
    """Forward-fill year, then split on Q-number resets within question pages."""
    # Step 1: forward-fill explicit years
    current = None
    for p in pages:
        if p.get('year'):
            current = normalize_year(p['year'])
        p['_year'] = current

    # Step 2: split solution/question groupings on Q-number resets within
    # the same year. We track the highest question/solution number we've seen
    # in the current year-block; when a page's first number drops below it,
    # we move to the *next* year-block (i.e. forward to the next non-null year
    # in the page list, or fabricate a new one).
    # Build sequence of unique years in order.
    year_order = []
    for p in pages:
        y = p.get('_year')
        if y and (not year_order or year_order[-1] != y):
            year_order.append(y)

    if not year_order:
        return  # nothing to do

    # For each page, decide which year it belongs to using both the
    # forward-filled year AND number-reset detection.
    cur_year_idx = 0
    last_q_seen = 0
    last_sol_seen = 0
    for p in pages:
        ptype = p.get('page_type')
        first_num = None
        if ptype == 'questions' and p.get('questions'):
            first_num = p['questions'][0].get('number')
        elif ptype == 'solutions' and p.get('solutions'):
            first_num = p['solutions'][0].get('number')
        elif ptype == 'answers-key' and p.get('answers'):
            first_num = p['answers'][0].get('number')

        # If this page has an explicit year, advance cur_year_idx to it
        if p.get('year'):
            target = normalize_year(p['year'])
            if target in year_order:
                cur_year_idx = year_order.index(target)
                last_q_seen = 0
                last_sol_seen = 0

        # Detect reset: number drops below previous high — implies new year
        if first_num is not None:
            if ptype == 'questions':
                if first_num <= 1 and last_q_seen >= 1:
                    # Q number reset: next year
                    if cur_year_idx + 1 < len(year_order):
                        cur_year_idx += 1
                        last_q_seen = 0
                        last_sol_seen = 0
                last_q_seen = max(last_q_seen, p['questions'][-1].get('number') or 0)
            elif ptype in ('solutions', 'answers-key'):
                if first_num <= 1 and last_sol_seen >= 1:
                    if cur_year_idx + 1 < len(year_order):
                        cur_year_idx += 1
                        last_q_seen = 0
                        last_sol_seen = 0
                items = p.get('solutions') or p.get('answers') or []
                last_sol_seen = max(last_sol_seen, items[-1].get('number') or 0)

        p['_year'] = year_order[cur_year_idx] if cur_year_idx < len(year_order) else None


def aggregate_per_year(pages: list[dict]) -> dict[str, dict]:
    """Returns { year_label: {questions, answers, solutions} } merged across pages."""
    by_year: dict[str, dict] = defaultdict(lambda: {
        'questions': {},   # number -> question record
        'answers': {},     # number -> letter
        'solutions': {},   # number -> text
    })
    for p in pages:
        y = p.get('_year')
        if not y:
            continue
        bucket = by_year[y]
        for q in p.get('questions') or []:
            n = q.get('number')
            if not n:
                continue
            # First-seen wins; if a later page has a more complete record (e.g.
            # has correct), prefer that.
            existing = bucket['questions'].get(n)
            if existing is None or (not existing.get('correct') and q.get('correct')):
                bucket['questions'][n] = q
        for a in p.get('answers') or []:
            n = a.get('number')
            if n and a.get('correct'):
                bucket['answers'][n] = (a['correct'] or '').lower()
        for s in p.get('solutions') or []:
            n = s.get('number')
            if n and s.get('solution'):
                bucket['solutions'][n] = s['solution']
    return by_year


def emit_classified(by_year: dict[str, dict]) -> dict[str, Path]:
    out_paths: dict[str, Path] = {}
    for year, bucket in sorted(by_year.items()):
        questions = []
        for n, q in sorted(bucket['questions'].items()):
            # Backfill correct from answer-key, then solutions if needed
            if not q.get('correct') and bucket['answers'].get(n):
                q['correct'] = bucket['answers'][n]
            if not q.get('solution') and bucket['solutions'].get(n):
                q['solution'] = bucket['solutions'][n]
            # Vision extracts have empty 'a/b/c/d' if no MCQ — keep what's there
            if 'choices' not in q or not isinstance(q['choices'], dict):
                q['choices'] = {'a': '', 'b': '', 'c': '', 'd': ''}
            else:
                # Ensure all 4 keys exist
                for k in ('a', 'b', 'c', 'd'):
                    q['choices'].setdefault(k, '')
            questions.append(q)

        out = {
            'paper': f'NSEJS {year.replace("_","-")}',
            'paper_code': '',
            'source_pdf': 'NSEJS-previous-year-papers-2006-to-2019-pdf.pdf',
            'questions': questions,
        }
        out_path = OUT_DIR / f'nsejs_{year}_classified.json'
        out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False))
        out_paths[year] = out_path
    return out_paths


def stats(by_year: dict[str, dict]):
    print(f'\n{"Year":<10} {"Qs":>4} {"WithAns":>8} {"Phys":>6} {"PhysOk":>8}')
    print('-' * 44)
    grand = {'q': 0, 'ans': 0, 'phys': 0, 'phys_ok': 0}
    for year, bucket in sorted(by_year.items()):
        qs = list(bucket['questions'].values())
        # Backfill from answers
        for q in qs:
            if not q.get('correct') and bucket['answers'].get(q.get('number')):
                q['correct'] = bucket['answers'][q['number']].lower()
        with_ans = sum(1 for q in qs if q.get('correct'))
        phys = [q for q in qs if (q.get('subject') == 'physics')]
        phys_ok = [q for q in phys if q.get('correct') and not q.get('skip_reason')]
        print(f'{year:<10} {len(qs):>4} {with_ans:>8} {len(phys):>6} {len(phys_ok):>8}')
        grand['q'] += len(qs)
        grand['ans'] += with_ans
        grand['phys'] += len(phys)
        grand['phys_ok'] += len(phys_ok)
    print('-' * 44)
    print(f'{"TOTAL":<10} {grand["q"]:>4} {grand["ans"]:>8} {grand["phys"]:>6} {grand["phys_ok"]:>8}')


def main():
    pages = load_pages()
    print(f'Loaded {len(pages)} page extractions')
    assign_years(pages)
    # Year debug
    yrs = sorted({p['_year'] for p in pages if p.get('_year')})
    print(f'Detected years: {yrs}')
    by_year = aggregate_per_year(pages)
    stats(by_year)
    out_paths = emit_classified(by_year)
    print(f'\nWrote {len(out_paths)} per-year JSON files')


if __name__ == '__main__':
    main()
