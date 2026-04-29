"""
Vision-based extractor for reasoning books (Arihant, MK Pandey).

For each rendered page, ask Claude Vision to identify:
  - page_type: questions | solutions | answers-key | cover | blank | exercises
  - chapter info (if visible)
  - passages (a "setup" or rule + group of sub-questions)
  - questions (standalone OR sub-questions of a passage)
  - solutions / answer-keys (mapped by question number when present)

Per-page output written to vision_pages/p<NNN>.json. Resumable.

Topic taxonomy enforced:
  syllogisms, blood_relations, direction_sense, coding_decoding, series,
  seating_arrangement, puzzles, inequalities, statement_conclusion,
  statement_argument, statement_assumption, course_of_action, cause_effect,
  inference, principle_application, analytical_decision, data_sufficiency,
  logical_sequence, ranking_time, calendar_clock, mathematical_operation,
  venn_diagram, analogy, classification, alphabet_number_sequence,
  decision_making, input_output, missing_character, situation_reaction,
  general

Out-of-scope (will be returned with subject='non_verbal' or similar so we
can drop them):
  cube_dice, mirror_water, pattern_completion, figure_formation,
  embedded_figures, counting_figures, paper_folding, dot_situation,
  visual_analogy, visual_classification
"""

from __future__ import annotations

import argparse
import base64
import concurrent.futures as cf
import json
import os
import sys
import time
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


VISION_MODEL = 'claude-sonnet-4-20250514'

DEFAULT_PAGES_DIR = Path('/tmp/reasoning_pages')
DEFAULT_OUT_DIR = Path(__file__).parent / 'vision_pages'

PAGES_DIR = DEFAULT_PAGES_DIR
OUT_DIR = DEFAULT_OUT_DIR


SYSTEM_PROMPT = """You are extracting structured data from a single page of a
reasoning textbook (e.g. Arihant 'A New Approach to Reasoning' or MK Pandey
'Analytical Reasoning'). Pages may be:

  questions    — numbered MCQs (with or without a passage above them)
  solutions    — answers / explanations for previously-numbered questions
  answers-key  — a compact table of question_number → letter
  exercises    — practice exercises section header
  cover        — title / chapter divider page
  blank        — mostly empty / boilerplate

For each numbered question on the page, return a record. If multiple
sub-questions share a "passage" / "setup" / "directions for the following N
questions", return ONE passage object and link the sub-questions to it via
`passage_index` (0-based index into the passages array).

Topic taxonomy (use for `topic_code`):
  syllogisms, blood_relations, direction_sense, coding_decoding, series,
  seating_arrangement, puzzles, inequalities, statement_conclusion,
  statement_argument, statement_assumption, course_of_action, cause_effect,
  inference, principle_application, analytical_decision, data_sufficiency,
  logical_sequence, ranking_time, calendar_clock, mathematical_operation,
  venn_diagram, analogy, classification, alphabet_number_sequence,
  decision_making, input_output, missing_character, situation_reaction,
  general

If the question is non-verbal / visual (cubes, mirror images, pattern
completion, paper folding, embedded figures, counting figures, figure series
etc.), set `subject` to "non_verbal" instead of "verbal". We'll drop those.

Return a SINGLE JSON object — no prose, no fences:

{
  "page_type": "...",
  "chapter_number": <int or null>,
  "chapter_title": "..." or null,
  "passages": [
    {
      "passage_text": "...",        // verbatim setup / directions / rule
      "has_figure": <bool>,
      "topic_code": "..."           // best guess for the whole group
    }
  ],
  "questions": [
    {
      "number": <int>,
      "passage_index": <int or null>,    // 0-based index into passages
      "seq_in_passage": <int or null>,   // 1-based position within the group
      "subject": "verbal" | "non_verbal",
      "topic_code": "...",
      "topic_name": "human label",
      "subtopic_code": "short_id",
      "subtopic_name": "human subtopic",
      "body": "verbatim question text",
      "choices": {"a": "...", "b": "...", "c": "...", "d": "...", "e": "..."},
      "correct": "a"|"b"|"c"|"d"|"e"|null,   // ONLY if shown on this page
      "has_figure": <bool>,
      "skip_reason": null
    }
  ],
  "solutions": [
    {"number": <int>, "solution": "..." }
  ],
  "answers": [
    {"number": <int>, "correct": "a"|"b"|"c"|"d"|"e" }
  ]
}

Rules:
- Empty arrays for irrelevant fields are fine.
- "choices" may have 4 or 5 letters depending on the book — only include the
  letters present.
- Never guess `correct` — leave null unless the page explicitly shows the
  answer next to the question.
- For passage-grouped questions, the passage_text is shared; do not repeat
  it in each question's body. Only the question stem goes in body.
- "Directions: Read the following passage and answer the questions" style
  instructions count as a passage even if there's no real "story".
- If a page is only a chapter heading or "Practice Exercises" title, set
  page_type accordingly and leave arrays empty.
"""


def call_vision(client: Anthropic, image_path: Path) -> dict:
    image_data = base64.standard_b64encode(image_path.read_bytes()).decode()
    resp = client.messages.create(
        model=VISION_MODEL,
        max_tokens=8000,
        system=SYSTEM_PROMPT,
        messages=[{
            'role': 'user',
            'content': [
                {'type': 'image', 'source': {'type': 'base64',
                                              'media_type': 'image/jpeg',
                                              'data': image_data}},
                {'type': 'text', 'text': 'Extract this page per the system instructions. Return one JSON object.'},
            ],
        }],
    )
    text = resp.content[0].text.strip()
    if text.startswith('```'):
        text = text.split('```', 2)[1]
        if text.startswith('json'):
            text = text[4:]
        text = text.strip().rstrip('`').strip()
    return json.loads(text)


def process_page(page_num: int, force: bool = False) -> dict:
    out_path = OUT_DIR / f'p{page_num:04d}.json'
    if out_path.exists() and not force:
        try:
            return json.loads(out_path.read_text())
        except Exception:
            pass

    image_path = PAGES_DIR / f'p{page_num:04d}.jpg'
    if not image_path.exists():
        return {'error': f'no image at {image_path}'}

    client = Anthropic()
    last_err = None
    for attempt in range(3):
        try:
            result = call_vision(client, image_path)
            result['_page'] = page_num
            out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False))
            return result
        except Exception as e:
            last_err = e
            time.sleep(2 ** attempt)
    err_obj = {'error': str(last_err), '_page': page_num}
    out_path.write_text(json.dumps(err_obj, indent=2))
    return err_obj


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--start', type=int, default=1)
    ap.add_argument('--end', type=int, required=True)
    ap.add_argument('--parallel', type=int, default=6)
    ap.add_argument('--force', action='store_true')
    ap.add_argument('--pages-dir', type=str, default=str(DEFAULT_PAGES_DIR))
    ap.add_argument('--out-dir', type=str, default=str(DEFAULT_OUT_DIR))
    args = ap.parse_args()

    global PAGES_DIR, OUT_DIR
    PAGES_DIR = Path(args.pages_dir)
    OUT_DIR = Path(args.out_dir)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    pages = list(range(args.start, args.end + 1))
    pending = [p for p in pages if args.force or not (OUT_DIR / f'p{p:04d}.json').exists()]
    print(f'pages: {len(pages)} total, {len(pending)} pending', file=sys.stderr)
    done = 0
    types: dict = {}
    with cf.ThreadPoolExecutor(max_workers=args.parallel) as ex:
        futures = {ex.submit(process_page, p, args.force): p for p in pending}
        for f in cf.as_completed(futures):
            r = f.result()
            done += 1
            if 'error' in r:
                print(f'  p{r["_page"]:04d}: ERR {r["error"][:80]}', file=sys.stderr)
            else:
                pt = r.get('page_type', '?')
                nq = len(r.get('questions') or [])
                np = len(r.get('passages') or [])
                ns = len(r.get('solutions') or [])
                na = len(r.get('answers') or [])
                types[pt] = types.get(pt, 0) + 1
                print(f'  p{r["_page"]:04d}: {pt:<11} q={nq:>3} pas={np:>2} sol={ns:>3} ans={na:>3}', file=sys.stderr)
            if done % 10 == 0:
                print(f'... {done}/{len(pending)} done', file=sys.stderr)
    print(f'\npage types: {types}', file=sys.stderr)


if __name__ == '__main__':
    main()
