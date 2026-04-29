"""
Fill in `correct_choice` for reasoning_questions where the source book
provided a solution explanation but no explicit answer letter.

Targets MK Pandey-style solutions ("Friend's brother is the maternal uncle...
hence ... uncle. answer is X" or just an explanation that you must reason
through). Sends question + choices + solution to Claude as a small classifier
and asks for a single letter.

Updates rows in-place:
  correct_choice  = 'A'..'E'
  correct_source  = 'ai_derived'
"""

from __future__ import annotations

import argparse
import os
import re
import sqlite3
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

env_path = Path(__file__).resolve().parent.parent / '.env'
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        k, v = line.split('=', 1)
        os.environ.setdefault(k.strip(), v.strip())

from anthropic import Anthropic

MODEL = 'claude-sonnet-4-20250514'
MAX_TOKENS = 200
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / 'reasoning_practice.db'

SYSTEM = """You are an answer-key extractor for reasoning MCQs.

You receive a question, its 4-5 lettered choices, and an explanation/solution.
The explanation often does NOT name the answer letter directly, but the
correct choice can be inferred from what it concludes.

Return ONLY the answer in this exact XML form:

<answer>A</answer>
<confidence>high|medium|low</confidence>

Letter must be one of A B C D E.
Use 'high' when the solution clearly points at one choice; 'medium' if you
had to match the conclusion against the choices yourself; 'low' if it's
genuinely ambiguous (in which case still pick your best guess).
"""


ANS_RE = re.compile(r'<answer>\s*([A-Ea-e])\s*</answer>')
CONF_RE = re.compile(r'<confidence>\s*(high|medium|low)\s*</confidence>')


def derive_one(client: Anthropic, q: dict) -> tuple[str | None, str | None]:
    choice_lines = []
    for L in 'abcde':
        v = q.get(f'choice_{L}')
        if v:
            choice_lines.append(f"({L.upper()}) {v}")
    if len(choice_lines) < 2:
        return None, None
    user = (
        f"QUESTION:\n{q['question_text']}\n\n"
        f"CHOICES:\n" + '\n'.join(choice_lines) + "\n\n"
        f"OFFICIAL SOLUTION:\n{q['official_solution']}"
    )
    last_err = None
    for attempt in range(3):
        try:
            r = client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=SYSTEM,
                messages=[{'role': 'user', 'content': user}],
            )
            text = r.content[0].text
            m = ANS_RE.search(text)
            if not m:
                return None, None
            letter = m.group(1).upper()
            cm = CONF_RE.search(text)
            conf = cm.group(1) if cm else 'medium'
            return letter, conf
        except Exception as e:
            last_err = e
            time.sleep(2 ** attempt)
    print(f"  q{q['question_id']}: error {last_err}", file=sys.stderr)
    return None, None


def find_targets(slug: str | None, limit: int | None) -> list[dict]:
    c = sqlite3.connect(str(DB_PATH))
    c.row_factory = sqlite3.Row
    q = """
        SELECT question_id, question_text, official_solution,
               choice_a, choice_b, choice_c, choice_d, choice_e,
               source_book
        FROM reasoning_questions
        WHERE (correct_choice IS NULL OR correct_choice = '')
          AND official_solution IS NOT NULL
          AND TRIM(official_solution) <> ''
    """
    args: list = []
    if slug:
        q += ' AND source_book = ?'
        args.append(slug)
    q += ' ORDER BY question_id'
    if limit:
        q += f' LIMIT {int(limit)}'
    rows = [dict(r) for r in c.execute(q, args).fetchall()]
    c.close()
    return rows


def update_answer(qid: int, letter: str):
    c = sqlite3.connect(str(DB_PATH))
    c.execute("""
        UPDATE reasoning_questions
        SET correct_choice = ?, correct_source = 'ai_derived',
            parse_status = 'ok',
            updated_at = datetime('now')
        WHERE question_id = ?
    """, (letter, qid))
    c.commit()
    c.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--source-book', help='only this book, e.g. mkpandey')
    ap.add_argument('--limit', type=int, help='cap N questions (debug)')
    ap.add_argument('--parallel', type=int, default=8)
    args = ap.parse_args()

    targets = find_targets(args.source_book, args.limit)
    print(f"targets: {len(targets)}", file=sys.stderr)
    if not targets:
        return

    client = Anthropic()
    done = 0
    derived = 0
    failed = 0

    def worker(q):
        nonlocal done
        letter, _ = derive_one(client, q)
        return q['question_id'], letter

    with ThreadPoolExecutor(max_workers=args.parallel) as ex:
        futs = {ex.submit(worker, q): q for q in targets}
        for f in as_completed(futs):
            qid, letter = f.result()
            done += 1
            if letter:
                update_answer(qid, letter)
                derived += 1
            else:
                failed += 1
            if done % 25 == 0:
                print(f"  {done}/{len(targets)} (derived={derived}, failed={failed})", file=sys.stderr)

    print(f"\nderived: {derived}/{len(targets)}", file=sys.stderr)
    print(f"failed:  {failed}", file=sys.stderr)


if __name__ == '__main__':
    main()
