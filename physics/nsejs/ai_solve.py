"""
For NSEJS PDFs that don't ship answer keys, ask Claude to solve each
physics question and fill in the correct option. Output replaces the
existing nsejs_<slug>_classified.json with `correct` set on physics
questions that Claude is confident about.

A `correct_source` field is added so the DB layer can tell AI-derived
answers apart from official answers (e.g., for confidence labelling later).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

env_path = Path(__file__).resolve().parent.parent.parent / '.env'
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        k, v = line.split('=', 1)
        os.environ.setdefault(k.strip(), v.strip())

from anthropic import Anthropic


SOLVE_MODEL = 'claude-sonnet-4-20250514'
HERE = Path(__file__).parent

SYSTEM_PROMPT = """You are solving NSEJS (National Standard Examination in
Junior Science) physics questions for an Indian Class 9 student. For each
question I send you, return the correct option letter (a/b/c/d).

Rules:
- Return JSON: a single array of {number, correct, confidence} objects in
  the order received.
- "correct" is one of "a", "b", "c", "d", or null if you genuinely cannot
  decide (e.g. question is unsolvable due to missing figure context, or
  the OCR text is corrupt).
- "confidence" is "high" / "medium" / "low".
- Use "low" if the question is ambiguous or relies on a figure you can't
  see, "high" if you're sure.
- Don't show your work — just return the JSON array. Output ONLY the
  array, nothing else."""


def solve_batch(client: Anthropic, items: list[dict]) -> list[dict]:
    payload = json.dumps(items, ensure_ascii=False)
    resp = client.messages.create(
        model=SOLVE_MODEL,
        max_tokens=8000,
        system=SYSTEM_PROMPT,
        messages=[{
            'role': 'user',
            'content': f'Solve these physics questions and return a JSON array of {{number, correct, confidence}}.\n\n{payload}',
        }],
    )
    text = resp.content[0].text.strip()
    if text.startswith('```'):
        text = text.split('```', 2)[1]
        if text.startswith('json'):
            text = text[4:]
        text = text.strip().rstrip('`').strip()
    return json.loads(text)


def process_file(slug: str, batch_size: int = 30, low_confidence_skip: bool = True) -> int:
    path = HERE / f'nsejs_{slug}_classified.json'
    if not path.exists():
        print(f'  no such file: {path}', file=sys.stderr)
        return 0
    data = json.loads(path.read_text())
    qs = data['questions']

    # Find physics questions missing `correct`
    needing = [
        q for q in qs
        if q.get('subject') == 'physics'
        and not q.get('correct')
        and not q.get('skip_reason')
        and all(q['choices'].get(L) for L in 'abcd')   # need full MCQ to solve
    ]
    if not needing:
        print(f'  {slug}: no physics Qs need solving', file=sys.stderr)
        return 0
    print(f'  {slug}: {len(needing)} physics Qs need solving', file=sys.stderr)

    client = Anthropic()
    solved_total = 0
    for i in range(0, len(needing), batch_size):
        chunk = needing[i:i + batch_size]
        items = [{
            'number': q['number'],
            'body': q['body'][:600],
            'choices': q['choices'],
        } for q in chunk]
        try:
            answers = solve_batch(client, items)
        except Exception as e:
            print(f'    batch {i}: ERROR {e}', file=sys.stderr)
            continue
        by_num = {a['number']: a for a in answers}
        for q in chunk:
            a = by_num.get(q['number'])
            if not a:
                continue
            if a.get('correct') and a['correct'] in ('a', 'b', 'c', 'd'):
                if low_confidence_skip and a.get('confidence') == 'low':
                    continue
                q['correct'] = a['correct']
                q['correct_source'] = 'ai_solved'
                q['correct_confidence'] = a.get('confidence', 'medium')
                solved_total += 1
        print(f'    batch {i}: +{sum(1 for a in answers if a.get("correct"))} answers', file=sys.stderr)

    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print(f'  {slug}: solved {solved_total}/{len(needing)} (saved)', file=sys.stderr)
    return solved_total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('slugs', nargs='+', help='one or more <slug> matching nsejs_<slug>_classified.json')
    ap.add_argument('--batch-size', type=int, default=30)
    ap.add_argument('--allow-low-confidence', action='store_true',
                    help='accept answers Claude marks as low-confidence')
    args = ap.parse_args()

    grand = 0
    for slug in args.slugs:
        print(f'\n=== {slug} ===', file=sys.stderr)
        grand += process_file(slug, args.batch_size, low_confidence_skip=not args.allow_low_confidence)
    print(f'\nTotal solved across all files: {grand}', file=sys.stderr)


if __name__ == '__main__':
    main()
