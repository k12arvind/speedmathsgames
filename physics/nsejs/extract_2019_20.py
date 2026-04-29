"""
Parse the 2019-20 NSEJS paper from the text-extractable portion (pages 1-44)
of the bundled NSEJS-previous-year-papers-2006-to-2019 PDF.

Output: a JSON file `nsejs_2019_20_raw.json` with one record per question:
  { number, body, choices: {a,b,c,d}, correct, solution, has_figure }

This is the *raw* extraction step — it does NOT classify subjects/topics.
That comes next (physics-only classifier) so we can validate parse quality
first.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import fitz  # PyMuPDF


PDF_PATH = Path('/tmp/nsejs_2006_2019.pdf')
OUT_PATH = Path(__file__).parent / 'nsejs_2019_20_raw.json'

# 2019-20 paper occupies pages 1-44 (1-indexed). Page 1 = instructions,
# Q1 starts on page 2.
START_PAGE = 1   # 0-indexed
END_PAGE = 43    # 0-indexed inclusive


def gather_text() -> str:
    doc = fitz.open(PDF_PATH)
    chunks = []
    for i in range(START_PAGE, END_PAGE + 1):
        chunks.append(doc[i].get_text())
    return '\n'.join(chunks)


# Regex matching a question header: "<n>.\n" at the start of a logical line.
# Has to be very strict — solutions also have numbered sub-points like "1." that
# we must not mis-classify. Question headers appear in their own line followed
# by either an empty line or text.
QUESTION_RE = re.compile(r'(?m)^(\d{1,3})\.\s*\n')

CHOICE_RE = re.compile(r'\(([a-dA-D])\)\s+([^\n]+(?:\n(?!\([a-dA-D]\)|Answer )[^\n]+)*)')
ANSWER_RE = re.compile(r'Answer\s+\(([a-dA-D])\)')
SOLUTION_RE = re.compile(r'Sol\.\s*([\s\S]*)')

# Tokens that indicate the question depends on a figure we don't have in pure text.
FIGURE_TOKENS = (
    'adjacent figure', 'shown below', 'shown above', 'shown in the figure',
    'shown in figure', 'in the diagram', 'in the figure',
    'figure shown', 'see figure', 'refer to', 'as shown',
)

# Known structural cleanup — strip header lines that PyMuPDF leaves on every page.
HEADER_NOISE = re.compile(r'^\s*\d+\s*\nNSEJS\s+201\s*-\s*\n9\s+20.*?\n', re.MULTILINE)


def split_questions(text: str) -> list[dict]:
    # Strip per-page headers that the converter inserts ("\n<pgnum>\nNSEJS 201-9 20 (Question Paper Code 52)\n")
    # These appear repeatedly and get glued into question text.
    text = re.sub(r'\n\d{1,3}\nNSEJS 201 -\n9 20 \(Question Paper Code 52\)\n', '\n', text)

    matches = list(QUESTION_RE.finditer(text))
    print(f'Question header markers: {len(matches)}', file=sys.stderr)

    out = []
    for i, m in enumerate(matches):
        num = int(m.group(1))
        # We need monotonic 1..80. Drop spurious markers.
        if not (1 <= num <= 80):
            continue
        if out and num != out[-1]['number'] + 1:
            # Not a clean increment — could be a sub-point in a solution. Skip.
            continue

        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = text[start:end].strip()

        # Body is everything up to the first "(a)" choice marker
        body = block
        choices = {'a': '', 'b': '', 'c': '', 'd': ''}
        correct = None
        solution = ''

        ch_match = re.search(r'\(a\)\s', block)
        if ch_match:
            body = block[:ch_match.start()].strip()
            rest = block[ch_match.start():]
            ans_match = ANSWER_RE.search(rest)
            choices_part = rest[:ans_match.start()] if ans_match else rest
            for cm in CHOICE_RE.finditer(choices_part):
                letter = cm.group(1).lower()
                if letter in choices:
                    choices[letter] = cm.group(2).strip()
            if ans_match:
                correct = ans_match.group(1).lower()
                rest_after = rest[ans_match.end():]
                sol_match = SOLUTION_RE.search(rest_after)
                if sol_match:
                    solution = sol_match.group(1).strip()

        body = body.replace('\n', ' ').strip()
        body = re.sub(r'\s+', ' ', body)

        has_figure = any(tok in body.lower() for tok in FIGURE_TOKENS)

        out.append({
            'number': num,
            'body': body,
            'choices': choices,
            'correct': correct,
            'solution': solution,
            'has_figure': has_figure,
        })

    return out


def main():
    text = gather_text()
    qs = split_questions(text)
    print(f'Parsed {len(qs)} questions', file=sys.stderr)

    # Quality stats
    no_choices = [q for q in qs if not all(q['choices'].values())]
    no_correct = [q for q in qs if not q['correct']]
    figure_deps = [q for q in qs if q['has_figure']]
    print(f'  - missing >=1 choice: {len(no_choices)}', file=sys.stderr)
    print(f'  - missing answer key: {len(no_correct)}', file=sys.stderr)
    print(f'  - figure-dependent: {len(figure_deps)}', file=sys.stderr)

    OUT_PATH.write_text(json.dumps({
        'paper': 'NSEJS 2019-20',
        'paper_code': '52',
        'source_pdf': PDF_PATH.name,
        'questions': qs,
    }, indent=2, ensure_ascii=False))
    print(f'Wrote {OUT_PATH}', file=sys.stderr)


if __name__ == '__main__':
    main()
