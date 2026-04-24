#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
extract_html.py

Extracts daily news-analysis content from Drishti IAS HTML pages.

Target URL pattern:
  https://www.drishtiias.com/current-affairs-news-analysis-editorials/news-analysis/DD-MM-YYYY

Returns a list of article dicts, each with:
  {
    'section':   e.g. "Facts for UPSC Mains" / "Rapid Fire" / "Important Facts For Prelims"
    'title':     h1#dynamic-title text
    'link':      canonical article URL
    'stars':     1..5 (importance rating)
    'tags':      list of tag strings (e.g. "GS Paper - 2")
    'source':    "PIB" / "The Hindu" / etc. if found in first <p>
    'blocks':    ordered list of content blocks, each a dict of:
                 {'type': 'heading'|'paragraph'|'bullet'|'callout'|'image',
                  'level': int|None,
                  'text': str,
                  'src': str|None,   # absolute URL, image blocks only
                  'alt': str|None,   # image blocks only
                  'width': int|None} # image blocks only (hint, in px)
  }
"""

from __future__ import annotations

import re
import sys
from typing import Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup, NavigableString, Tag


DRISHTI_DAILY_URL_RE = re.compile(
    r'drishtiias\.com/current-affairs-news-analysis-editorials/news-analysis/(\d{2})-(\d{2})-(\d{4})',
    re.IGNORECASE,
)


def fetch_html_content(url: str, timeout: int = 30) -> str:
    headers = {
        'User-Agent': (
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/120.0.0.0 Safari/537.36'
        ),
        'Accept-Language': 'en-US,en;q=0.9',
    }
    response = requests.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()
    return response.text


def extract_date_from_url(url: str) -> Optional[Dict[str, str]]:
    """Return {'day','month','year'} or None.

    Drishti uses DD-MM-YYYY in its URL path.
    """
    m = DRISHTI_DAILY_URL_RE.search(url)
    if not m:
        return None
    day, month, year = m.groups()
    months = [
        'january', 'february', 'march', 'april', 'may', 'june',
        'july', 'august', 'september', 'october', 'november', 'december',
    ]
    idx = int(month) - 1
    month_name = months[idx] if 0 <= idx < 12 else month
    return {'day': str(int(day)), 'month': month_name, 'year': year}


def _clean(text: str) -> str:
    return re.sub(r'\s+', ' ', text or '').strip()


def _find_preceding_h6(detail: Tag) -> Optional[str]:
    """Drishti places an <h6> section tag right before each article-detail div."""
    prev = detail.find_previous_sibling()
    while prev is not None and getattr(prev, 'name', None) != 'h6':
        prev = prev.find_previous_sibling()
    if prev is None:
        return None
    return _clean(prev.get_text(' ', strip=True))


def _extract_tags(detail: Tag) -> List[str]:
    tags_div = detail.find('div', class_='tags-new')
    if not tags_div:
        return []
    return [_clean(li.get_text(' ', strip=True)) for li in tags_div.find_all('li')]


def _extract_stars(detail: Tag) -> int:
    rating_el = detail.find('div', class_='starRating')
    if not rating_el:
        return 0
    return len(rating_el.select('.fa-star.checked'))


def _extract_title_and_link(detail: Tag) -> Tuple[Optional[str], Optional[str]]:
    h1 = detail.find('h1', id='dynamic-title')
    if not h1:
        return None, None
    anchor = h1.find('a')
    if anchor:
        return _clean(anchor.get_text(' ', strip=True)), anchor.get('href')
    return _clean(h1.get_text(' ', strip=True)), None


# Child classes that don't carry article content.
_SKIP_CLASSES = {
    'next-post', 'tags-new', 'social-shares', 'starRating',
    'btn-group', 'fb-like', 'also-read',
}


def _absolutize(src: str) -> str:
    if not src:
        return src
    if src.startswith('//'):
        return 'https:' + src
    if src.startswith('/'):
        return 'https://www.drishtiias.com' + src
    return src


def _find_content_images(node: Tag):
    """Yield (src, alt, width) for every `img.content-img` under `node`."""
    for img in node.find_all('img', class_='content-img'):
        src = img.get('src', '')
        if not src:
            continue
        alt = img.get('alt') or None
        width_raw = img.get('width')
        try:
            width = int(width_raw) if width_raw else None
        except (TypeError, ValueError):
            width = None
        yield (_absolutize(src), alt, width)


def _image_block(src: str, alt, width) -> Dict:
    return {
        'type': 'image', 'level': None, 'text': alt or '',
        'src': src, 'alt': alt, 'width': width,
    }


def _iter_content_blocks(detail: Tag):
    """Yield raw content blocks (dicts) for an article in reading order.

    Keys: type (heading|paragraph|bullet|callout|image), plus the extras
    documented in the module docstring. Text-only blocks set src/alt/width
    to None.
    """
    for child in detail.children:
        if isinstance(child, NavigableString):
            continue
        if not isinstance(child, Tag):
            continue

        cls = child.get('class') or []
        if any(c in _SKIP_CLASSES for c in cls):
            continue
        if child.name in ('br', 'hr', 'script', 'style', 'noscript'):
            continue
        # Skip the title itself — captured separately.
        if child.name == 'h1' and child.get('id') == 'dynamic-title':
            continue

        # Top-level <img class="content-img"> (rare; usually nested inside a <p>)
        if child.name == 'img' and 'content-img' in cls:
            src = _absolutize(child.get('src', ''))
            if src:
                yield _image_block(src, child.get('alt'), child.get('width'))
            continue

        # Callout-style boxes: border-bg, custom note etc.
        if child.name == 'div' and ('border-bg' in cls or 'note' in cls):
            # Drishti sometimes drops infographics inside a border-bg too.
            for (src, alt, w) in _find_content_images(child):
                yield _image_block(src, alt, w)
            text = _clean(child.get_text(' ', strip=True))
            if text:
                yield {'type': 'callout', 'level': None, 'text': text,
                       'src': None, 'alt': None, 'width': None}
            continue

        if child.name in ('h2', 'h3', 'h4', 'h5'):
            level = int(child.name[1])
            text = _clean(child.get_text(' ', strip=True))
            if text and len(text) >= 2:
                yield {'type': 'heading', 'level': level, 'text': text,
                       'src': None, 'alt': None, 'width': None}
            continue

        if child.name == 'p':
            # Paragraphs commonly wrap infographics — capture images first, then text.
            for (src, alt, w) in _find_content_images(child):
                yield _image_block(src, alt, w)
            text = _clean(child.get_text(' ', strip=True))
            if text:
                yield {'type': 'paragraph', 'level': None, 'text': text,
                       'src': None, 'alt': None, 'width': None}
            continue

        if child.name in ('ul', 'ol'):
            for li in child.find_all('li', recursive=False):
                text = _clean(li.get_text(' ', strip=True))
                if text:
                    yield {'type': 'bullet', 'level': None, 'text': text,
                           'src': None, 'alt': None, 'width': None}
            continue

        # Fallback: generic div with text (rare on Drishti); flatten to paragraph.
        if child.name == 'div':
            for (src, alt, w) in _find_content_images(child):
                yield _image_block(src, alt, w)
            text = _clean(child.get_text(' ', strip=True))
            if text and len(text) > 20:
                yield {'type': 'paragraph', 'level': None, 'text': text,
                       'src': None, 'alt': None, 'width': None}


def _extract_source(blocks: List[Dict]) -> Optional[str]:
    """First paragraph is typically 'Source: PIB' etc. Pop it out."""
    if not blocks:
        return None
    b0 = blocks[0]
    if b0['type'] == 'paragraph' and b0['text'].lower().startswith('source:'):
        popped = blocks.pop(0)
        return popped['text'].split(':', 1)[1].strip()
    return None


def extract_articles_from_html(html_content: str) -> List[Dict]:
    """Parse one Drishti daily news-analysis page into a list of articles."""
    soup = BeautifulSoup(html_content, 'html.parser')
    articles: List[Dict] = []

    for detail in soup.find_all('div', class_='article-detail'):
        title, link = _extract_title_and_link(detail)
        if not title:
            continue

        section = _find_preceding_h6(detail) or 'Current Affairs'
        tags = _extract_tags(detail)
        stars = _extract_stars(detail)

        blocks: List[Dict] = list(_iter_content_blocks(detail))

        source = _extract_source(blocks)

        articles.append({
            'section': section,
            'title': title,
            'link': link,
            'stars': stars,
            'tags': tags,
            'source': source,
            'blocks': blocks,
        })

    return articles


def group_by_section(articles: List[Dict]) -> Dict[str, List[Dict]]:
    """Group articles by their Drishti-assigned section, preserving order."""
    # Ordering hint so Facts-for-Mains land first, Rapid-Fire last.
    preferred_order = [
        'Facts for UPSC Mains',
        'Important Facts For Prelims',
        'Important Facts for Prelims',
        'Biodiversity & Environment',
        'Economy',
        'Science & Technology',
        'International Relations',
        'Governance & Polity',
        'Rapid Fire',
    ]

    grouped: Dict[str, List[Dict]] = {}
    for art in articles:
        grouped.setdefault(art['section'], []).append(art)

    ordered: Dict[str, List[Dict]] = {}
    for sec in preferred_order:
        if sec in grouped:
            ordered[sec] = grouped.pop(sec)
    for sec, arts in grouped.items():
        ordered[sec] = arts
    return ordered


def main():
    if len(sys.argv) < 2:
        print('Usage: python extract_html.py <url> [--out file.txt]')
        sys.exit(1)
    url = sys.argv[1]
    html = fetch_html_content(url)
    articles = extract_articles_from_html(html)

    print(f'Found {len(articles)} articles')
    for a in articles:
        print(f"  [{a['section']}] {a['title']}  ({len(a['blocks'])} blocks, {a['stars']}⭐)")


if __name__ == '__main__':
    main()
