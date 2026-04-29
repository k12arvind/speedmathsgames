"""
Vision-based extractor for the image-only portion of the NSEJS PDF
(pages 45-199 of NSEJS-previous-year-papers-2006-to-2019).

For each page image we ask Claude Vision a single structured question:
  - What kind of page is this? (questions / solutions / answers-key / cover / blank)
  - What year does it belong to? (e.g. "2010-11")
  - For question pages: extract every question (number, body, choices, correct
    if shown, subject, physics topic if applicable, has_figure, skip_reason).
  - For solutions pages: extract solutions keyed by question number.
  - For answer-key pages: extract a flat number→letter map.

Each page result is written to vision_pages/p<NNN>.json so the run is
resumable. A second pass aggregates everything by year.

Run with parallelism (PARALLEL=N) to speed up wall-clock — Anthropic API
rate limits are generous enough for ~6 concurrent calls.
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

# Load .env
env_path = Path(__file__).resolve().parent.parent.parent / '.env'
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        k, v = line.split('=', 1)
        os.environ.setdefault(k.strip(), v.strip())

from anthropic import Anthropic


VISION_MODEL = 'claude-sonnet-4-20250514'
PAGES_DIR = Path('/tmp/nsejs_pages')
OUT_DIR = Path(__file__).parent / 'vision_pages'
OUT_DIR.mkdir(exist_ok=True)


SYSTEM_PROMPT = """You are extracting structured data from a single page of a
scanned NSEJS (National Standard Examination in Junior Science) compilation
book that contains question papers from years 2006-2017 plus their solutions.

Pages may be one of these types:
  questions    — one or more questions with their multiple-choice options
  solutions    — worked solutions, usually keyed by question number
  answers-key  — a small table mapping question number → A/B/C/D
  cover        — a title/cover page or chapter divider
  blank        — mostly empty / front matter / publisher boilerplate

Year header (e.g. "Years 2010-11") usually appears on the first page of each
year only. If absent, return year as null and we'll fill it in via context.

Return a SINGLE JSON object with this shape (no prose, no code fences):

{
  "page_type": "questions" | "solutions" | "answers-key" | "cover" | "blank",
  "year": "YYYY-YY" or null,
  "page_in_year": <integer page number from footer "Page - N"> or null,
  "questions": [
    {
      "number": <int>,
      "body": "<verbatim question text — preserve mathematical notation>",
      "choices": {"a": "...", "b": "...", "c": "...", "d": "..."},
      "correct": "a" | "b" | "c" | "d" | null,
      "subject": "physics" | "chemistry" | "biology" | "maths",
      "topic_code": "mechanics" | "thermal" | "waves" | "optics" | "electricity" | "magnetism" | "modern" | "general",
      "topic_name": "<human label>",
      "subtopic_code": "<short code>",
      "subtopic_name": "<human label>",
      "difficulty": "easy" | "medium" | "hard",
      "has_figure": <bool>,
      "skip_reason": "<reason>" or null
    },
    ...
  ],
  "solutions": [
    { "number": <int>, "solution": "<text>" }
  ],
  "answers": [
    { "number": <int>, "correct": "a"|"b"|"c"|"d" }
  ]
}

Rules:
- For non-questions pages, return empty arrays for the irrelevant fields.
- For physics questions, ALWAYS set topic_code/topic_name/subtopic_code/subtopic_name.
  For non-physics questions you may omit those.
- "has_figure" = true if the question shows a diagram/graph/circuit that is
  essential for solving. "skip_reason" should be set ONLY for questions
  that cannot be solved without the figure.
- "correct" should be filled if and only if the answer letter is visible on
  the page itself (e.g. shown next to the question, or in a results box).
  Don't guess.
- Preserve mathematical notation as readable text (use ^, sqrt, etc.). Don't
  use LaTeX delimiters.
- If the page is a duplicate of the watermark "IJSO International Junior
  Science Olympiad..." and has no other content, it's "blank".

Output a single JSON object, nothing else."""


def call_vision(client: Anthropic, image_path: Path) -> dict:
    image_data = base64.standard_b64encode(image_path.read_bytes()).decode()
    resp = client.messages.create(
        model=VISION_MODEL,
        max_tokens=8000,
        system=SYSTEM_PROMPT,
        messages=[{
            'role': 'user',
            'content': [
                {
                    'type': 'image',
                    'source': {
                        'type': 'base64',
                        'media_type': 'image/jpeg',
                        'data': image_data,
                    },
                },
                {
                    'type': 'text',
                    'text': 'Extract this page per the system instructions. Return one JSON object.',
                },
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
    out_path = OUT_DIR / f'p{page_num:03d}.json'
    if out_path.exists() and not force:
        return json.loads(out_path.read_text())

    image_path = PAGES_DIR / f'p{page_num:03d}.jpg'
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
    ap.add_argument('--start', type=int, default=45,
                    help='start page (1-indexed) inclusive')
    ap.add_argument('--end', type=int, default=199,
                    help='end page inclusive')
    ap.add_argument('--parallel', type=int, default=6)
    ap.add_argument('--force', action='store_true', help='re-extract even if JSON exists')
    args = ap.parse_args()

    pages = list(range(args.start, args.end + 1))
    pending = [p for p in pages if args.force or not (OUT_DIR / f'p{p:03d}.json').exists()]
    print(f'pages: {len(pages)} total, {len(pending)} pending', file=sys.stderr)
    done = 0
    types = {}
    with cf.ThreadPoolExecutor(max_workers=args.parallel) as ex:
        futures = {ex.submit(process_page, p, args.force): p for p in pending}
        for f in cf.as_completed(futures):
            r = f.result()
            done += 1
            if 'error' in r:
                print(f'  p{r["_page"]:03d}: ERR {r["error"][:80]}', file=sys.stderr)
            else:
                ptype = r.get('page_type', '?')
                year = r.get('year') or '?'
                nq = len(r.get('questions') or [])
                nsol = len(r.get('solutions') or [])
                nans = len(r.get('answers') or [])
                types[ptype] = types.get(ptype, 0) + 1
                print(f'  p{r["_page"]:03d}: {ptype:<11} year={year:<8} q={nq:>2} sol={nsol:>2} ans={nans:>2}', file=sys.stderr)
            if done % 10 == 0:
                print(f'... {done}/{len(pending)} done', file=sys.stderr)

    print(f'\npage types: {types}', file=sys.stderr)


if __name__ == '__main__':
    main()
