"""Free, no-API scan to catch Vision OCR errors in `correct_choice`.

For each Arihant reasoning question that has both an official_solution and a
correct_choice, parse the conclusion sentence of the solution and find which
answer choice it points to. If the inferred letter differs from the stored
correct_choice, flag (and optionally fix) the row.

Catches the Q6 PC_11.1 class of bugs where Vision misread the italic answer
letter on the answer-key page, e.g. "(d) ... So, Bindu is granddaughter of
Mahipal" got tagged with letter='c'. The solution TEXT is reliable; the
extracted letter is what's wrong, so we trust the text and overwrite the
letter when there's a clean match.

Usage:
    python text_scan_correct_choice.py --db <path>            # dry-run
    python text_scan_correct_choice.py --db <path> --apply    # fix
"""

from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from pathlib import Path
from typing import Optional


# Conclusion-marker patterns: a solution often ends with a sentence kicked
# off by one of these connectives that tells you the final answer.
CONCLUSION_MARKERS = [
    'so,', 'hence,', 'therefore,', 'thus,', 'clearly,',
    'so ', 'hence ', 'therefore ', 'thus ',
]


def normalize(s: str) -> str:
    """Lowercase, collapse whitespace, drop punctuation other than apostrophes."""
    s = s.lower()
    s = re.sub(r"[^a-z0-9'\s]", ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def extract_conclusion(solution: str) -> Optional[str]:
    """Return the most-likely conclusion fragment of a solution.

    Strategy: split into sentences. Prefer the LATEST sentence that starts
    with a conclusion marker (So, / Hence, / Therefore, / Thus, / Clearly,).
    Fall back to the last sentence if none qualifies.
    """
    if not solution:
        return None
    # Split on '.', '!', '?' but keep them
    parts = re.split(r'(?<=[.!?])\s+', solution.strip())
    parts = [p.strip() for p in parts if p.strip()]
    if not parts:
        return None
    # Latest sentence whose lowercased prefix matches a marker
    for p in reversed(parts):
        low = p.lower().lstrip('([{ ')
        for m in CONCLUSION_MARKERS:
            if low.startswith(m):
                return p
    # No marker — use the last non-empty sentence
    return parts[-1]


def match_choice(conclusion: str, choices: dict) -> Optional[str]:
    """Return the letter ('a'..'e') of the choice whose text is mentioned
    in the conclusion. Prefers the LONGEST choice text to avoid 'daughter'
    matching when 'granddaughter' is the real answer.

    Returns None if zero or >1 choice text matches with the same length.
    """
    norm_conc = normalize(conclusion)
    if not norm_conc:
        return None
    matches = []  # (letter, choice_text, length)
    for letter, text in choices.items():
        if not text:
            continue
        norm_choice = normalize(text)
        if not norm_choice:
            continue
        # Whole-token match: surround with word boundaries so "daughter"
        # doesn't match inside "granddaughter".
        pat = r'\b' + re.escape(norm_choice) + r'\b'
        if re.search(pat, norm_conc):
            matches.append((letter, norm_choice, len(norm_choice)))
    if not matches:
        return None
    matches.sort(key=lambda m: -m[2])
    # If the longest match is uniquely longest, pick it.
    if len(matches) >= 2 and matches[0][2] == matches[1][2]:
        # Tie at top length — ambiguous. Skip.
        return None
    return matches[0][0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--db', required=True)
    ap.add_argument('--apply', action='store_true',
                    help='Actually UPDATE the DB. Without it, dry-run report only.')
    ap.add_argument('--limit', type=int, default=None)
    args = ap.parse_args()

    c = sqlite3.connect(args.db)
    c.row_factory = sqlite3.Row

    rows = c.execute("""
        SELECT question_id, source_book, chapter_title, problem_number,
               correct_choice, official_solution,
               choice_a, choice_b, choice_c, choice_d, choice_e
        FROM reasoning_questions
        WHERE source_book = 'arihant'
          AND official_solution IS NOT NULL
          AND length(official_solution) > 0
          AND correct_choice IS NOT NULL
          AND length(correct_choice) > 0
    """).fetchall()

    if args.limit:
        rows = rows[: args.limit]

    counts = {
        'total': 0, 'no_conclusion': 0, 'no_choice_match': 0,
        'agrees': 0, 'disagrees_high': 0, 'disagrees_low': 0,
        'updated': 0,
    }
    flagged_high = []   # high-confidence: conclusion has ONE unique matching choice
    flagged_low = []    # low-confidence: multiple choice texts appear in conclusion

    for r in rows:
        counts['total'] += 1
        conc = extract_conclusion(r['official_solution'])
        if not conc:
            counts['no_conclusion'] += 1
            continue
        choices = {
            'a': r['choice_a'], 'b': r['choice_b'], 'c': r['choice_c'],
            'd': r['choice_d'], 'e': r['choice_e'],
        }
        inferred = match_choice(conc, choices)
        if not inferred:
            counts['no_choice_match'] += 1
            continue
        cur = (r['correct_choice'] or '').strip().lower()
        if inferred == cur:
            counts['agrees'] += 1
            continue

        # Confidence = how many choice-texts appear in the conclusion. If
        # only ONE choice text appears, the conclusion is naming the answer
        # unambiguously. If many appear (typical of analogy "X is to Y as
        # Z is to W"), my heuristic might pick the wrong one — defer to
        # human review.
        norm_conc = normalize(conc)
        n_choices_in_conc = 0
        for letter, text in choices.items():
            if not text:
                continue
            if re.search(r'\b' + re.escape(normalize(text)) + r'\b', norm_conc):
                n_choices_in_conc += 1

        bucket = flagged_high if n_choices_in_conc == 1 else flagged_low
        if n_choices_in_conc == 1:
            counts['disagrees_high'] += 1
        else:
            counts['disagrees_low'] += 1
        bucket.append({
            'qid': r['question_id'],
            'chapter': r['chapter_title'],
            'qnum': r['problem_number'],
            'cur': cur.upper(),
            'inferred': inferred.upper(),
            'cur_text': (choices.get(cur, '') or '')[:50],
            'inferred_text': (choices.get(inferred, '') or '')[:50],
            'conclusion': conc[:160],
            'n_in_conc': n_choices_in_conc,
        })

    print('=== scan summary ===', file=sys.stderr)
    for k, v in counts.items():
        print(f'  {k}: {v}', file=sys.stderr)

    def _show(label, flagged):
        if not flagged:
            return
        print(f'\n=== {label}: {len(flagged)} ===', file=sys.stderr)
        for f in flagged[:25]:
            print(
                f"  qid={f['qid']} {f['chapter']!r} Q{f['qnum']}: "
                f"stored={f['cur']} ({f['cur_text']!r}) → "
                f"inferred={f['inferred']} ({f['inferred_text']!r}) "
                f"[matches-in-conc={f['n_in_conc']}]",
                file=sys.stderr,
            )
            print(f"    conclusion: {f['conclusion']!r}", file=sys.stderr)
        if len(flagged) > 25:
            print(f'  ... + {len(flagged) - 25} more', file=sys.stderr)

    _show('HIGH confidence (auto-applicable)', flagged_high)
    _show('LOW confidence (manual review needed)', flagged_low)

    if args.apply and flagged_high:
        for f in flagged_high:
            c.execute(
                "UPDATE reasoning_questions "
                "SET correct_choice=?, correct_source='text_scan', "
                "    updated_at=datetime('now') "
                "WHERE question_id=?",
                (f['inferred'], f['qid']),
            )
        c.commit()
        counts['updated'] = len(flagged_high)
        print(f"\napplied: {counts['updated']} HIGH-confidence updates", file=sys.stderr)
        if flagged_low:
            print(f"  ({len(flagged_low)} LOW-confidence rows NOT applied — manual)",
                  file=sys.stderr)
    elif flagged_high or flagged_low:
        print('\n(dry-run — re-run with --apply to commit HIGH-confidence only)',
              file=sys.stderr)

    c.close()


if __name__ == '__main__':
    main()
