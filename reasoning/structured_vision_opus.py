"""Targeted Opus re-Vision for letter-identity-prone pages of the Arihant
verbal-reasoning book.

Re-runs the same structured-vision prompt as structured_vision.py but with
Claude Opus 4.7 instead of Sonnet 4. Outputs go to a SEPARATE directory so
we can diff against the existing v2 outputs and only update DB rows where
Opus disagrees on:
  - the answer letter (`correct` per question, `letter` per solution)
  - the question body / choice text (single-letter mis-OCR)

Reads /tmp/target_pages.json (a list of int page numbers).
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

from anthropic import Anthropic  # noqa: E402

# Re-use the SAME system prompt from the Sonnet pass so output schema is
# identical and downstream parsing is reusable.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from structured_vision import SYSTEM_PROMPT, DEFAULT_PAGES_DIR  # type: ignore

OPUS_MODEL = 'claude-opus-4-7'
OUT_DIR = Path(__file__).parent / 'vision_pages_arihant_v2_opus'


def call_vision(client: Anthropic, image_path: Path) -> dict:
    image_data = base64.standard_b64encode(image_path.read_bytes()).decode()
    resp = client.messages.create(
        model=OPUS_MODEL,
        max_tokens=10000,
        system=SYSTEM_PROMPT,
        messages=[{
            'role': 'user',
            'content': [
                {'type': 'image', 'source': {'type': 'base64',
                                              'media_type': 'image/jpeg',
                                              'data': image_data}},
                {'type': 'text', 'text': (
                    'Extract this page. Return one JSON object per the system '
                    'instructions. PAY EXTRA CARE on small italic letters in '
                    'answer-key parentheses (a/c/d easily confuse) and on '
                    'single-letter variables in question stems (A/N, B/D, '
                    'I/L, O/Q, etc.). Be careful: distinguish worked examples '
                    '(theory) from real practice questions.'
                )},
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


def process_page(page_num: int, pages_dir: Path, out_dir: Path,
                 force: bool = False) -> dict:
    out_path = out_dir / f'p{page_num:04d}.json'
    if out_path.exists() and not force:
        try:
            return json.loads(out_path.read_text())
        except Exception:
            pass

    image_path = pages_dir / f'p{page_num:04d}.jpg'
    if not image_path.exists():
        return {'error': f'no image at {image_path}', '_page': page_num}

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
    ap.add_argument('--pages-file', type=str, default='/tmp/target_pages.json')
    ap.add_argument('--parallel', type=int, default=5)
    ap.add_argument('--force', action='store_true')
    ap.add_argument('--pages-dir', type=str, default=str(DEFAULT_PAGES_DIR))
    ap.add_argument('--out-dir', type=str, default=str(OUT_DIR))
    args = ap.parse_args()

    target_pages = json.loads(Path(args.pages_file).read_text())
    pages_dir = Path(args.pages_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    pending = [p for p in target_pages
               if args.force or not (out_dir / f'p{p:04d}.json').exists()]
    print(f'Opus re-Vision: {len(target_pages)} target pages, {len(pending)} pending',
          file=sys.stderr)

    counts = {'cover':0,'theory':0,'practice_q':0,'master_q':0,
              'solutions':0,'mixed':0,'blank':0,'other':0,'error':0}
    done = 0
    with cf.ThreadPoolExecutor(max_workers=args.parallel) as ex:
        futures = {ex.submit(process_page, p, pages_dir, out_dir, args.force): p
                   for p in pending}
        for f in cf.as_completed(futures):
            r = f.result()
            done += 1
            if 'error' in r:
                counts['error'] += 1
                if counts['error'] <= 5:
                    print(f"  p{r['_page']:04d}: ERR {r['error'][:120]}", file=sys.stderr)
            else:
                kind = r.get('page_kind', 'other')
                counts[kind] = counts.get(kind, 0) + 1
                nq = len(r.get('questions') or [])
                ns = len(r.get('solutions') or [])
                ex_id = r.get('exercise_id') or '-'
                print(f"  p{r['_page']:04d}: {kind:<10} {ex_id:<10} q={nq:>3} s={ns:>3}",
                      file=sys.stderr)
            if done % 10 == 0:
                print(f'... {done}/{len(pending)}', file=sys.stderr)

    print(f'\npage-kind tally: {counts}', file=sys.stderr)


if __name__ == '__main__':
    main()
