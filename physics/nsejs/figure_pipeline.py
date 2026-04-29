"""
For every physics question that was skipped because it depends on a figure
we couldn't render from text:
  1. Trace the question back to its source page (via per-page Vision JSONs
     under vision_pages_<slug>/).
  2. Copy that page JPEG to ~/saanvi/NSEJSFigures/<slug>/p<NNN>.jpg so the
     server can serve it via /static/NSEJSFigures/.
  3. Re-call Claude Vision with the page image AND the question/choices,
     asking for the correct answer. Store as correct_source='ai_solved_figure'.
  4. Update the corresponding nsejs_<slug>_classified.json: set
     figure_image_path, set correct, drop skip_reason if we got an answer.

Skipped questions that remain unanswerable (Claude can't decide even with
the figure) keep skip_reason — they stay out of the question bank.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import shutil
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
FIGURES_ROOT = Path.home() / 'saanvi' / 'NSEJSFigures'

SYSTEM_PROMPT = """You are looking at a single page from an NSEJS exam paper.
The user will give you ONE question's text + four MCQ options. The question
references a figure/diagram/graph that's on the page.

Use the page image to read the figure, then determine the correct option.

You may reason step-by-step in <work> tags. Then ALWAYS finish with three
output tags:

  <answer>a|b|c|d|none</answer>
  <confidence>high|medium|low</confidence>
  <note>one short sentence</note>

- "none" means the figure genuinely doesn't match the question (e.g. wrong
  page) or no option works.
- "high" = you read the figure cleanly and your math hits exactly one option.
- Keep <work> brief — a few short lines."""


YEAR_BUNDLE_SLUGS = {
    '2008_09', '2009_10', '2010_11', '2011_12', '2012_13', '2013_14',
    '2014_15', '2015_16', '2016_17', '2017_18', '2019_20',
}


def find_pages_for_pdf(slug: str) -> tuple[Path | None, Path | None]:
    """Returns (vision_pages_dir, rendered_pages_dir) for a given slug."""
    if slug in YEAR_BUNDLE_SLUGS:
        return HERE / 'vision_pages', Path('/tmp/nsejs_pages')
    return HERE / f'vision_pages_{slug}', Path(f'/tmp/nsejs_{slug}_pages')


def _bundle_year_pages_index(target_year: str) -> dict[int, int]:
    """For a year-bundle slug like '2010_11', figure out which bundle pages
    belong to that year (using the same forward-fill year inference as
    vision_aggregate), then build a {qnum: bundle_page_num} mapping scoped
    to that year only."""
    vp_dir = HERE / 'vision_pages'
    if not vp_dir.exists():
        return {}

    # Read all page JSONs in order
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

    # Forward-fill year using the same rule the aggregator uses
    target_label = target_year.replace('_', '-')

    def _norm(label):
        if not label:
            return None
        import re as _r
        m = _r.match(r'(\d{4})\s*[-–]\s*(\d{2,4})', str(label))
        if not m:
            return None
        yyyy = int(m.group(1))
        return f'{yyyy:04d}-{int(m.group(2)) % 100:02d}'

    # Build year_order from explicit headers
    cur = None
    year_order = []
    for p in pages:
        ny = _norm(p.get('year'))
        if ny:
            cur = ny
            if not year_order or year_order[-1] != ny:
                year_order.append(ny)
        p['_year'] = cur

    # Apply Q-number reset detection (same as aggregator)
    cur_idx = 0
    last_q = 0
    last_sol = 0
    for p in pages:
        ptype = p.get('page_type')
        first_num = None
        items = []
        if ptype == 'questions':
            items = p.get('questions') or []
        elif ptype in ('solutions', 'answers-key'):
            items = p.get('solutions') or p.get('answers') or []
        if items:
            first_num = items[0].get('number')

        if p.get('year'):
            ny = _norm(p['year'])
            if ny in year_order:
                cur_idx = year_order.index(ny)
                last_q = last_sol = 0

        if first_num is not None:
            if ptype == 'questions':
                if first_num <= 1 and last_q >= 1 and cur_idx + 1 < len(year_order):
                    cur_idx += 1
                    last_q = last_sol = 0
                last_q = max(last_q, items[-1].get('number') or 0)
            elif ptype in ('solutions', 'answers-key'):
                if first_num <= 1 and last_sol >= 1 and cur_idx + 1 < len(year_order):
                    cur_idx += 1
                    last_q = last_sol = 0
                last_sol = max(last_sol, items[-1].get('number') or 0)

        p['_year'] = year_order[cur_idx] if cur_idx < len(year_order) else None

    # Scope to target year, build qnum -> page mapping
    out: dict[int, int] = {}
    for p in pages:
        if p.get('_year') != target_label:
            continue
        if p.get('page_type') != 'questions':
            continue
        for q in p.get('questions') or []:
            n = q.get('number')
            if n and n not in out:
                out[n] = p['_page']
    return out


def index_questions_by_page(vp_dir: Path, slug: str | None = None) -> dict[int, int]:
    """For each question number found across this PDF's per-page JSONs,
    return the page number (1-indexed in the rendered images) where it lives.

    For year-bundle slugs we MUST scope by year — Q1 exists in every year and
    we'd otherwise pick whichever year's first page is hit first."""
    if slug and slug in YEAR_BUNDLE_SLUGS:
        return _bundle_year_pages_index(slug)

    out: dict[int, int] = {}
    if not vp_dir.exists():
        return out
    for f in sorted(vp_dir.glob('p*.json')):
        try:
            d = json.loads(f.read_text())
        except Exception:
            continue
        if 'error' in d:
            continue
        page_num = int(f.stem[1:])
        for q in d.get('questions') or []:
            n = q.get('number')
            if n and n not in out:
                out[n] = page_num
    return out


def encode_image(path: Path) -> str:
    return base64.standard_b64encode(path.read_bytes()).decode()


import re as _re
_TAG_RE = _re.compile(r'<(\w+)>(.*?)</\1>', _re.DOTALL)


def solve_with_figure(client: Anthropic, page_jpg: Path, q: dict) -> dict:
    img = encode_image(page_jpg)
    user_text = (
        f'Question {q["number"]}: {q["body"]}\n\n'
        + '\n'.join(f'({L}) {q["choices"].get(L, "")}' for L in 'abcd')
    )
    resp = client.messages.create(
        model=SOLVE_MODEL,
        max_tokens=2000,
        system=SYSTEM_PROMPT,
        messages=[{
            'role': 'user',
            'content': [
                {'type': 'image', 'source': {'type': 'base64',
                                              'media_type': 'image/jpeg',
                                              'data': img}},
                {'type': 'text', 'text': user_text},
            ],
        }],
    )
    text = resp.content[0].text.strip()
    tags = {m.group(1): m.group(2).strip() for m in _TAG_RE.finditer(text)}
    ans = tags.get('answer', '').lower()
    if ans not in ('a', 'b', 'c', 'd'):
        ans = None
    return {
        'correct': ans,
        'confidence': tags.get('confidence', 'medium').lower() or 'medium',
        'reasoning': tags.get('note', ''),
    }


def process_slug(slug: str, low_conf_skip: bool = False) -> dict:
    """Process every figure-skipped physics Q in one classified file.
    For year-papers (2008..2019), the slug is the year_<yy> name and
    the vision pages and rendered images come from the bundle dirs."""
    cls_path = HERE / f'nsejs_{slug}_classified.json'
    if not cls_path.exists():
        return {'slug': slug, 'error': 'no classified file'}
    data = json.loads(cls_path.read_text())

    vp_dir, render_dir = find_pages_for_pdf(slug)
    if vp_dir is None or not render_dir.exists():
        return {'slug': slug, 'error': f'no rendered pages dir at {render_dir}'}

    qnum_to_page = index_questions_by_page(vp_dir, slug)
    figures_dir = FIGURES_ROOT / slug
    figures_dir.mkdir(parents=True, exist_ok=True)

    client = Anthropic()
    n_processed = 0
    n_solved = 0
    n_failed = 0

    for q in data['questions']:
        if q.get('subject') != 'physics':
            continue
        if not q.get('skip_reason'):
            continue   # already usable
        if q.get('figure_image_path'):
            continue   # already processed

        n_processed += 1
        page_num = qnum_to_page.get(q['number'])
        if page_num is None:
            print(f'  [{slug} Q{q["number"]}] no page mapping found, skipping')
            n_failed += 1
            continue

        src_jpg = render_dir / f'p{page_num:03d}.jpg'
        if not src_jpg.exists():
            print(f'  [{slug} Q{q["number"]}] source jpg missing: {src_jpg}')
            n_failed += 1
            continue

        dst_jpg = figures_dir / src_jpg.name
        if not dst_jpg.exists():
            shutil.copy2(src_jpg, dst_jpg)

        # Need 4 choices to solve
        choices = q.get('choices') or {}
        if not all(choices.get(L) for L in 'abcd'):
            # No MCQ → can't solve with confidence, but still keep figure
            q['figure_image_path'] = f'/static/NSEJSFigures/{slug}/{src_jpg.name}'
            print(f'  [{slug} Q{q["number"]}] figure-only (no MCQ to solve)')
            continue

        try:
            result = solve_with_figure(client, dst_jpg, q)
        except Exception as e:
            print(f'  [{slug} Q{q["number"]}] vision-solve error: {e}')
            n_failed += 1
            continue

        ans = result.get('correct')
        conf = result.get('confidence', 'medium')
        if ans in ('a', 'b', 'c', 'd') and not (low_conf_skip and conf == 'low'):
            q['correct'] = ans
            q['correct_source'] = 'ai_solved_figure'
            q['correct_confidence'] = conf
            q['figure_image_path'] = f'/static/NSEJSFigures/{slug}/{src_jpg.name}'
            # Clear skip_reason so the inserter accepts it
            q['skip_reason'] = None
            n_solved += 1
            print(f'  [{slug} Q{q["number"]}] ✓ {ans} (conf={conf}) page={page_num}')
        else:
            print(f'  [{slug} Q{q["number"]}] ✗ vision returned ans={ans} conf={conf}')
            n_failed += 1

    cls_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    return {
        'slug': slug, 'processed': n_processed,
        'solved': n_solved, 'failed': n_failed,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('slugs', nargs='*',
                    help='slugs to process; defaults to all classified files')
    ap.add_argument('--low-conf-skip', action='store_true')
    args = ap.parse_args()

    if args.slugs:
        slugs = args.slugs
    else:
        slugs = sorted(p.stem.replace('nsejs_', '').replace('_classified', '')
                       for p in HERE.glob('nsejs_*_classified.json'))
    print(f'processing {len(slugs)} slugs:', slugs)
    summary = []
    for slug in slugs:
        print(f'\n=== {slug} ===')
        r = process_slug(slug, args.low_conf_skip)
        summary.append(r)

    print('\n=== Summary ===')
    print(f'{"slug":<25} {"proc":>5} {"solved":>7} {"failed":>7}')
    grand = {'p': 0, 's': 0, 'f': 0}
    for r in summary:
        if 'error' in r:
            print(f'{r["slug"]:<25} ERROR: {r["error"]}')
            continue
        print(f'{r["slug"]:<25} {r["processed"]:>5} {r["solved"]:>7} {r["failed"]:>7}')
        grand['p'] += r['processed']
        grand['s'] += r['solved']
        grand['f'] += r['failed']
    print(f'{"TOTAL":<25} {grand["p"]:>5} {grand["s"]:>7} {grand["f"]:>7}')


if __name__ == '__main__':
    main()
