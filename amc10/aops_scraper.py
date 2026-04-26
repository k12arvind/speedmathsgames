"""AoPS Wiki scraper for AMC 10 problems.

The PDF text-extraction parser in `amc10/parser.py` was destroying multi-column
layouts and dropping math notation. AoPS Wiki has every AMC 10 problem in
clean form with proper LaTeX in `<img class="latex" alt="$...$">` tags, and
public answer-key pages with the correct letter for each problem.

This scraper is intentionally read-only against AoPS — single GETs with a
disk cache so reruns are fast and respectful of their servers.

Public API:
    client = AopsClient()
    answers = client.fetch_answer_key(year=2002, season=None, contest_code='A')
    # → ['D', 'C', 'B', 'E', ...]   (25 letters)

    problem = client.fetch_problem(year=2002, contest_code='A', problem_num=17)
    # → {'question_text', 'choice_a'..'choice_e', 'official_solution'}
"""

from __future__ import annotations

import hashlib
import html
import re
import time
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional

from bs4 import BeautifulSoup

WIKI_BASE = 'https://artofproblemsolving.com/wiki/index.php'
DEFAULT_CACHE = Path.home() / 'clat_preparation' / '.aops_cache'

USER_AGENT = (
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/120.0.0.0 Safari/537.36'
)


# ---------------------------------------------------------------------------
# URL builders
# ---------------------------------------------------------------------------
def _problems_slug(year: int, season: Optional[str], contest_code: Optional[str]) -> str:
    """Build the AoPS Wiki slug for the contest's index page.

    Conventions:
      2000-2001:   YYYY_AMC_10_Problems        (no A/B split)
      2002-2019:   YYYY_AMC_10{A|B}_Problems
      2021 Spring: 2021_AMC_10A_Problems  (Spring is the "default" 2021)
      2021 Fall:   2021_Fall_AMC_10A_Problems
      2022+:       YYYY_AMC_10A_Problems
    """
    if year <= 2001:
        return f'{year}_AMC_10_Problems'
    if season == 'Fall':
        return f'{year}_Fall_AMC_10{contest_code}_Problems'
    return f'{year}_AMC_10{contest_code}_Problems'


def _problem_slug(year: int, season: Optional[str], contest_code: Optional[str], num: int) -> str:
    return f'{_problems_slug(year, season, contest_code)}/Problem_{num}'


def _answer_key_slug(year: int, season: Optional[str], contest_code: Optional[str]) -> str:
    if year <= 2001:
        return f'{year}_AMC_10_Answer_Key'
    if season == 'Fall':
        return f'{year}_Fall_AMC_10{contest_code}_Answer_Key'
    return f'{year}_AMC_10{contest_code}_Answer_Key'


# ---------------------------------------------------------------------------
# HTTP client with disk cache
# ---------------------------------------------------------------------------
class AopsClient:
    def __init__(self, cache_dir: Optional[Path] = None,
                 sleep_between: float = 0.4):
        self.cache_dir = (cache_dir or DEFAULT_CACHE)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.sleep_between = sleep_between

    def _fetch(self, slug: str) -> str:
        # Cache by slug hash so renames don't bust caches.
        key = hashlib.sha1(slug.encode('utf-8')).hexdigest()[:24]
        path = self.cache_dir / f'{key}.html'
        if path.exists() and path.stat().st_size > 0:
            return path.read_text(encoding='utf-8')

        url = f'{WIKI_BASE}?title={slug}'
        req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode('utf-8', errors='ignore')
        path.write_text(body, encoding='utf-8')
        if self.sleep_between > 0:
            time.sleep(self.sleep_between)
        return body

    # -----------------------------------------------------------------
    # Answer keys
    # -----------------------------------------------------------------
    def fetch_answer_key(self, year: int,
                         season: Optional[str],
                         contest_code: Optional[str]) -> List[str]:
        """Return 25 letters in problem order. Raises on failure."""
        slug = _answer_key_slug(year, season, contest_code)
        body = self._fetch(slug)
        soup = BeautifulSoup(body, 'html.parser')
        content = soup.select_one('.mw-parser-output')
        if not content:
            raise ValueError(f'Answer key page has no .mw-parser-output: {slug}')

        # Letters can appear in <ol><li>X</li></ol>, in a <p>, or inline.
        # Strategy: collect every standalone A-E character in the main content.
        text = content.get_text('\n')
        letters = re.findall(r'(?:^|\b|\s)([ABCDE])(?:\b|\s|$)', text)
        # The page sometimes echoes navigation letters; restrict to the first 25.
        if len(letters) < 25:
            raise ValueError(
                f'Answer key {slug} returned only {len(letters)} letters'
            )
        return letters[:25]

    # -----------------------------------------------------------------
    # Problem pages
    # -----------------------------------------------------------------
    def fetch_problem(self, year: int,
                      season: Optional[str],
                      contest_code: Optional[str],
                      num: int) -> Dict[str, Optional[str]]:
        """Return dict with question_text, choice_a..e, official_solution.

        question_text and official_solution preserve LaTeX (inline `$...$`).
        Choices are split into per-letter cells.
        """
        slug = _problem_slug(year, season, contest_code, num)
        body = self._fetch(slug)
        soup = BeautifulSoup(body, 'html.parser')
        content = soup.select_one('.mw-parser-output')
        if not content:
            raise ValueError(f'Problem page has no .mw-parser-output: {slug}')

        # --- Find Problem section ---
        # Most pages have an explicit "Problem" h2. A few (e.g. 2007 AMC 10A
        # Problem 13) put the problem at the top of the article with no
        # heading — in that case treat everything from the start of the
        # content up to the first heading (usually "Solution …") as the body.
        problem_h2 = _find_section_heading(content, prefix='problem')
        if problem_h2:
            problem_blocks = _collect_until_next_h2(problem_h2)
        else:
            problem_blocks = _collect_until_first_h2(content)
        # --- Collect all Solution sections ---
        solution_blocks: List = []
        sol_h2 = problem_h2
        while True:
            sol_h2 = _find_next_heading(sol_h2, prefix='solution')
            if not sol_h2:
                break
            solution_blocks.extend([sol_h2, *_collect_until_next_h2(sol_h2)])

        # Convert HTML blocks to LaTeX-preserving plain text
        problem_text = _blocks_to_text(problem_blocks)
        solutions_text = _blocks_to_text(solution_blocks) if solution_blocks else None

        question_text, choices = _split_question_and_choices(problem_text)

        return {
            'question_text': question_text,
            'choice_a': choices.get('A'),
            'choice_b': choices.get('B'),
            'choice_c': choices.get('C'),
            'choice_d': choices.get('D'),
            'choice_e': choices.get('E'),
            'official_solution': solutions_text,
        }


# ---------------------------------------------------------------------------
# HTML → LaTeX-preserving text
# ---------------------------------------------------------------------------
_LATEX_INLINE_RE  = re.compile(r'^\$(.*)\$$',     re.DOTALL)
_LATEX_DISPLAY_RE = re.compile(r'^\\\[(.*)\\\]$', re.DOTALL)


def _img_to_latex(tag) -> str:
    """Replace an <img class='latex…'> with its LaTeX alt content (in $...$).

    AoPS Wiki ships math in two flavours: inline math wrapped in `$ … $`, and
    display math wrapped in `\\[ … \\]`. Both come through the alt attribute.
    For our reader we always want inline-math `$ … $` so MathJax renders it
    flowing within the question text.
    """
    alt = (tag.get('alt') or '').strip()
    m = _LATEX_INLINE_RE.match(alt) or _LATEX_DISPLAY_RE.match(alt)
    if m:
        return '$' + m.group(1).strip() + '$'
    return alt


def _is_latex_img(node) -> bool:
    """AoPS uses class names like 'latex', 'latexcenter', 'tex' for math
    images. They all share the convention: the alt attribute holds the
    LaTeX source, possibly wrapped in $...$ or \\[...\\]."""
    classes = node.get('class') or []
    return any(c.startswith('latex') or c == 'tex' for c in classes)


def _node_to_text(node) -> str:
    """Recursively convert a BeautifulSoup node to plain text, but inline
    LaTeX wherever an AoPS math image appears."""
    if hasattr(node, 'name') and node.name == 'img':
        if _is_latex_img(node):
            return ' ' + _img_to_latex(node) + ' '
        return ''  # ignore non-latex images (figures handled separately if needed)
    if hasattr(node, 'name') and node.name == 'br':
        return '\n'
    if hasattr(node, 'children'):
        return ''.join(_node_to_text(c) for c in node.children)
    # Leaf: NavigableString
    return html.unescape(str(node))


def _block_to_text(node) -> str:
    txt = _node_to_text(node)
    # Trim per-line whitespace, drop fully-blank consecutive lines
    lines = [re.sub(r'[ \t]+', ' ', l).strip() for l in txt.splitlines()]
    out = []
    blank = False
    for l in lines:
        if not l:
            if not blank:
                out.append('')
            blank = True
        else:
            out.append(l)
            blank = False
    return '\n'.join(out).strip()


def _blocks_to_text(blocks) -> str:
    parts = []
    for b in blocks:
        if not hasattr(b, 'name'):
            continue
        if b.name in ('script', 'style'):
            continue
        text = _block_to_text(b)
        if text:
            parts.append(text)
    return '\n\n'.join(parts).strip()


# ---------------------------------------------------------------------------
# Section navigation
# ---------------------------------------------------------------------------
def _find_section_heading(content, prefix: str):
    """Find the first <h2> whose headline starts with `prefix` (case-insensitive)."""
    for h2 in content.find_all('h2'):
        txt = h2.get_text(' ', strip=True).lower()
        if txt.startswith(prefix):
            return h2
    return None


def _find_next_heading(after_node, prefix: str):
    sib = after_node.find_next_sibling()
    while sib is not None:
        if hasattr(sib, 'name') and sib.name == 'h2':
            txt = sib.get_text(' ', strip=True).lower()
            if txt.startswith(prefix):
                return sib
        sib = sib.find_next_sibling()
    return None


def _collect_until_next_h2(start_h2) -> list:
    blocks = []
    sib = start_h2.find_next_sibling()
    while sib is not None and not (hasattr(sib, 'name') and sib.name == 'h2'):
        blocks.append(sib)
        sib = sib.find_next_sibling()
    return blocks


def _collect_until_first_h2(content) -> list:
    """Take all top-level children up to (but not including) the first h2.
    Used when a problem page has no explicit "Problem" heading."""
    blocks = []
    for node in content.children:
        if hasattr(node, 'name') and node.name == 'h2':
            break
        blocks.append(node)
    return blocks


# ---------------------------------------------------------------------------
# Choice extraction
# ---------------------------------------------------------------------------
# Pattern that matches a single letter cell inside the giant choices LaTeX.
# AoPS canonical:    \textbf{(A)} ~12 \qquad\textbf{(B)} ~1 ...
# Older AMC pages:   \mathrm{(A)}\ I only \qquad\mathrm{(B)}\ ...
# Some pages use:    \text{(A) } 12 ...
# Be permissive on the wrapper and the post-marker spacing.
_CHOICE_LETTER_RE = re.compile(
    # Wrapper command. AoPS uses any of these (and we tolerate \textrm, \texttt
    # and double-brace forms like \\textbf{{(B)}} too):
    r'\\(?:textbf|textrm|texttt|mathrm|mathbf|mathit|mathsf|text|bf|rm|fbox)'
    r'\s*\{+\s*\(([A-E])\)(?P<inner>[^{}]*?)\}+\s*'
    r'(?:~|\\,|\\ |\\ )?\s*'
)


def _split_question_and_choices(problem_text: str):
    """Split the Problem section into question_text + dict{A..E -> latex}."""
    m = _CHOICE_LETTER_RE.search(problem_text)
    if not m:
        return _clean_question(problem_text), {}
    return _clean_question(problem_text[:m.start()]), _parse_choices_blob(problem_text[m.start():])


def _clean_question(text: str) -> str:
    """Strip the dangling LaTeX delimiters that come from splitting away the
    choices line (the choices are wrapped in $...$ as a single image, and our
    splitter cuts inside that block, leaving an unmatched leading $)."""
    text = text.strip()
    # Drop trailing isolated $ (or $\n at end), and the same on each line edge.
    text = re.sub(r'\$\s*$', '', text).rstrip()
    text = re.sub(r'^\s*\$\s*\n', '', text)  # rare: leading orphan
    return text.strip()


def _parse_choices_blob(blob: str) -> Dict[str, str]:
    """Walk through the blob picking up A..E spans.

    Two layouts on AoPS:
      a) \\text{(A)} 12   \\qquad \\text{(B)} 5  …   — cell is OUT-of-brace
      b) \\text{(A) 12}\\qquad\\text{(B) 5}…       — cell is IN-brace (older AMC)
    We prefer the out-of-brace tail when non-empty; otherwise fall back to the
    in-brace `inner` group captured by the regex.
    """
    matches = list(_CHOICE_LETTER_RE.finditer(blob))
    out: Dict[str, str] = {}
    for i, m in enumerate(matches):
        letter = m.group(1)
        inner = (m.group('inner') or '').strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(blob)
        outer = blob[start:end]
        # Strip qquad separators and the closing $ if present.
        outer = re.sub(r'\\qquad', '', outer).strip()
        if outer.endswith('$') and outer.count('$') % 2 == 1:
            outer = outer[:-1].strip()

        cell = outer if outer else inner
        if not cell:
            continue
        # Re-wrap in $...$ if it contains LaTeX commands or special chars so
        # MathJax renders it correctly. Plain numbers/words pass through bare.
        if any(ch in cell for ch in '\\{}^_') and not (cell.startswith('$') and cell.endswith('$')):
            cell = '$' + cell + '$'
        out[letter] = cell
    return out


# ---------------------------------------------------------------------------
# Convenience for callers
# ---------------------------------------------------------------------------
def fetch_one_problem(year: int, season: Optional[str], contest_code: Optional[str],
                      num: int, client: Optional[AopsClient] = None) -> Dict:
    return (client or AopsClient()).fetch_problem(year, season, contest_code, num)
