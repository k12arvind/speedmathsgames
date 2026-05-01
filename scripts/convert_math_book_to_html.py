#!/usr/bin/env python3
"""
convert_math_book_to_html.py

Converts a math PDF (typically an AoPS textbook) into a browsable, mobile-
friendly HTML reader. Math notation and diagrams are preserved 100% by
rendering each page as a PNG image; per-page text is extracted alongside
for search and accessibility.

Output layout (per book):

  out_root / <book_id> /
    book.json            # metadata: title, page count, chapter index
    p001.png … pNNN.png  # one image per page at <DPI> dpi
    ch001.html …         # one HTML file per chapter, lazy-loading images
    index.html           # book TOC + reader entry point

Chapter detection strategy (in order):
  1. Embedded PDF outline / bookmarks (preferred — accurate)
  2. Text-pattern scan for "Chapter N" headings on page-start
  3. Fixed-size fallback (every CHAPTER_FALLBACK_PAGES pages → one "section")
"""

from __future__ import annotations

import argparse
import json
import re
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional

import fitz  # PyMuPDF


DEFAULT_DPI = 144                  # ~2× display @ 72 dpi; sharp on Retina
JPEG_QUALITY = 85                  # imperceptible vs lossless for text+diagrams; ~4-6× smaller than PNG
PAGE_FORMAT = 'jpg'                # 'jpg' or 'png'
CHAPTER_FALLBACK_PAGES = 30        # if no chapter detection works, group every N pages


@dataclass
class Chapter:
    number: int
    title: str
    page_start: int      # 0-indexed page in the PDF
    page_end: int        # inclusive
    html_filename: str   # e.g. "ch001.html"


# ---------------------------------------------------------------------------
# Chapter detection
# ---------------------------------------------------------------------------

CHAPTER_RE = re.compile(
    r'^\s*(?:CHAPTER|Chapter)\s+(\d+)\b\s*[\.\:]?\s*(.{0,80})',
)


def chapters_from_outline(doc: fitz.Document) -> List[Chapter]:
    """Build chapters from PDF outline. AoPS books often include nested levels —
    take only top-level entries (level == 1) since those map to chapters."""
    toc = doc.get_toc()
    if not toc:
        return []

    top_entries = [(title.strip(), page - 1) for level, title, page in toc if level == 1 and page > 0]
    if not top_entries:
        return []

    chapters: List[Chapter] = []
    for i, (title, start) in enumerate(top_entries):
        end = top_entries[i + 1][1] - 1 if i + 1 < len(top_entries) else doc.page_count - 1
        chapters.append(Chapter(
            number=i + 1, title=title, page_start=start, page_end=end,
            html_filename=f"ch{i+1:03d}.html",
        ))
    return chapters


def chapters_from_text(doc: fitz.Document) -> List[Chapter]:
    """Detect chapters by scanning the first ~600 chars of each page for
    a 'CHAPTER N' or 'Chapter N' marker."""
    starts: List[tuple[int, int, str]] = []  # (chapter_num, page_idx, title)
    seen_numbers = set()
    for i in range(doc.page_count):
        txt = doc[i].get_text()[:600]
        # Look only at the top of the page — chapter heads are at top.
        head = txt.strip().split('\n', 4)
        head_text = '\n'.join(head[:4])
        m = CHAPTER_RE.search(head_text)
        if not m:
            continue
        ch_num = int(m.group(1))
        # Same chapter number can repeat in a TOC page; only take first occurrence.
        if ch_num in seen_numbers:
            continue
        seen_numbers.add(ch_num)
        title_part = (m.group(2) or '').strip()
        # If title was on the next line, grab it
        if not title_part and len(head) > 1:
            title_part = head[1].strip()[:80]
        title = f"Chapter {ch_num}" + (f": {title_part}" if title_part else '')
        starts.append((ch_num, i, title))

    if not starts:
        return []

    # Make sure chapters are in monotonic order — drop out-of-order detections
    starts.sort(key=lambda x: x[1])
    chapters: List[Chapter] = []
    for idx, (ch_num, page, title) in enumerate(starts):
        end = starts[idx + 1][1] - 1 if idx + 1 < len(starts) else doc.page_count - 1
        chapters.append(Chapter(
            number=idx + 1, title=title, page_start=page, page_end=end,
            html_filename=f"ch{idx+1:03d}.html",
        ))
    return chapters


def chapters_fixed_chunks(page_count: int, chunk: int = CHAPTER_FALLBACK_PAGES) -> List[Chapter]:
    chapters: List[Chapter] = []
    n = 1
    for start in range(0, page_count, chunk):
        end = min(start + chunk - 1, page_count - 1)
        chapters.append(Chapter(
            number=n, title=f"Pages {start + 1}–{end + 1}",
            page_start=start, page_end=end,
            html_filename=f"ch{n:03d}.html",
        ))
        n += 1
    return chapters


def detect_chapters(doc: fitz.Document) -> tuple[List[Chapter], str]:
    """Returns (chapters, source) where source explains how they were detected."""
    ch = chapters_from_outline(doc)
    if ch:
        return ch, 'outline'
    ch = chapters_from_text(doc)
    if ch:
        return ch, 'text-scan'
    return chapters_fixed_chunks(doc.page_count), 'fixed-chunks'


# ---------------------------------------------------------------------------
# Page rendering + HTML build
# ---------------------------------------------------------------------------

def render_page(doc: fitz.Document, page_idx: int, out_path: Path, dpi: int,
                fmt: str = PAGE_FORMAT, jpeg_quality: int = JPEG_QUALITY):
    """Render one page at the requested DPI.

    JPEG is the default — for text-on-white book pages it's 4–6× smaller
    than PNG with no visible difference. Skips if output exists and is
    non-empty so the converter is resumable across crashes."""
    if out_path.exists() and out_path.stat().st_size > 0:
        return
    page = doc[page_idx]
    zoom = dpi / 72.0
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    if fmt.lower() in ('jpg', 'jpeg'):
        pix.pil_save(str(out_path), format='JPEG',
                     quality=jpeg_quality, optimize=True)
    else:
        pix.save(str(out_path))


def page_text(doc: fitz.Document, page_idx: int) -> str:
    return doc[page_idx].get_text().strip()


def html_escape(s: str) -> str:
    return (s or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


CHAPTER_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{book_title} — {chapter_title}</title>
  <style>
    body {{ margin:0; padding:0; background:#0b0d10; color:#e7eaee;
           font-family:-apple-system,system-ui,Segoe UI,Roboto,sans-serif; }}
    header {{ position:sticky; top:0; z-index:5; background:#11161c;
             border-bottom:1px solid #243040; padding:10px 16px;
             display:flex; align-items:center; gap:12px; flex-wrap:wrap; }}
    header .title {{ font-weight:600; font-size:14px; }}
    header .meta {{ color:#8a96a4; font-size:12px; }}
    header .nav {{ margin-left:auto; display:flex; gap:8px; }}
    header .nav a {{ padding:5px 12px; background:#1c2530; border:1px solid #2c3949;
                    border-radius:6px; color:#cfd8e3; text-decoration:none;
                    font-size:13px; }}
    header .nav a:hover {{ background:#2c3949; }}
    main {{ max-width:920px; margin:0 auto; padding:14px; }}
    .page {{ margin-bottom:24px; background:#fff; border-radius:6px; overflow:hidden;
            box-shadow:0 6px 20px rgba(0,0,0,0.35); position:relative; }}
    .page img {{ display:block; width:100%; height:auto; }}
    .page-num {{ position:absolute; top:6px; right:8px; background:rgba(11,13,16,0.65);
                 color:#cbd5e1; font-size:11px; padding:2px 6px; border-radius:3px; }}
    .page-text {{ display:none; }}   /* searchable but not visible */
    .progress-bar {{ position:fixed; bottom:0; left:0; right:0; height:3px;
                    background:#1c2530; }}
    .progress-bar > span {{ display:block; height:100%; width:0%; background:#10b981;
                            transition:width .3s; }}
  </style>
</head>
<body>
  <header>
    <div class="title">{book_title}</div>
    <div class="meta">{chapter_title} · pages {first_page}–{last_page} of {total_pages}</div>
    <div class="nav">
      <a href="index.html">📚 Book index</a>
      {prev_link}
      {next_link}
    </div>
  </header>
  <main id="main">
    {pages_html}
  </main>
  <div class="progress-bar"><span id="prog"></span></div>

  <script>
    // Reading-time tracking — tick-based, GK-module style.
    // Counts 1s for each currently-visible page while the tab is foreground;
    // flushes via fetch every 30s and via sendBeacon on pagehide.
    const bookId = "{book_id}";
    const chapterNum = {chapter_num};

    function readerUserId() {{
      try {{
        const u = JSON.parse((window.parent || window).localStorage.getItem('cachedUser') || '{{}}');
        return u.user_id || 'navya';
      }} catch (e) {{ return 'navya'; }}
    }}

    const visiblePages = new Set();   // pageNum currently >=40% visible
    const pending = new Map();        // pageNum -> seconds not yet flushed

    const observer = new IntersectionObserver(entries => {{
      for (const e of entries) {{
        const num = parseInt(e.target.dataset.pageNum, 10);
        if (e.isIntersecting && e.intersectionRatio >= 0.4) {{
          visiblePages.add(num);
        }} else {{
          visiblePages.delete(num);
        }}
      }}
    }}, {{ threshold: [0, 0.4] }});
    document.querySelectorAll('.page').forEach(el => observer.observe(el));

    // Update progress bar based on scroll position.
    document.addEventListener('scroll', () => {{
      const total = document.documentElement.scrollHeight - window.innerHeight;
      const pct = total > 0 ? Math.min(100, (window.scrollY / total) * 100) : 0;
      const bar = document.getElementById('prog');
      if (bar) bar.style.width = pct + '%';
    }}, {{passive: true}});

    let docVisible = document.visibilityState === 'visible';
    document.addEventListener('visibilitychange', () => {{
      const wasVisible = docVisible;
      docVisible = document.visibilityState === 'visible';
      if (wasVisible && !docVisible) flushPending(false);  // tab hidden -> flush
    }});

    // 1s tick: add a second to every visible page while tab is foregrounded.
    setInterval(() => {{
      if (!docVisible || visiblePages.size === 0) return;
      for (const num of visiblePages) {{
        pending.set(num, (pending.get(num) || 0) + 1);
      }}
    }}, 1000);

    // Flush pending counts every 30s.
    setInterval(() => flushPending(false), 30000);

    // On navigation/close, send remaining counts via sendBeacon (survives unload).
    window.addEventListener('pagehide', () => flushPending(true));

    function flushPending(useBeacon) {{
      if (pending.size === 0) return;
      const userId = readerUserId();
      for (const [num, secs] of pending.entries()) {{
        if (!secs || secs <= 0) continue;
        const payload = JSON.stringify({{
          user_id: userId,
          book_id: bookId,
          chapter_number: chapterNum,
          page_number: num,
          seconds: secs,
        }});
        if (useBeacon && navigator.sendBeacon) {{
          navigator.sendBeacon(
            '/api/physics/book-view',
            new Blob([payload], {{ type: 'application/json' }})
          );
        }} else {{
          fetch('/api/physics/book-view', {{
            method: 'POST',
            headers: {{ 'Content-Type': 'application/json' }},
            body: payload,
            keepalive: true,
          }}).catch(() => {{}});
        }}
        pending.set(num, 0);
      }}
    }}
  </script>
</body>
</html>
"""


PAGE_BLOCK_TEMPLATE = """    <div class="page" data-page-num="{page_num}">
      <span class="page-num">p {page_num}</span>
      <img loading="lazy" src="p{page_num:03d}.{fmt}" alt="Page {page_num}">
      <div class="page-text">{escaped_text}</div>
    </div>"""


INDEX_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{book_title}</title>
  <style>
    body {{ margin:0; background:#0b0d10; color:#e7eaee;
           font-family:-apple-system,system-ui,Segoe UI,Roboto,sans-serif;
           padding:20px; }}
    .wrap {{ max-width:760px; margin:0 auto; }}
    h1 {{ font-size:22px; margin:0 0 6px; }}
    .meta {{ color:#8a96a4; font-size:13px; margin-bottom:24px; }}
    .ch-list {{ display:flex; flex-direction:column; gap:6px; }}
    .ch {{ display:flex; justify-content:space-between; align-items:center;
          padding:12px 14px; background:#11161c; border:1px solid #1f2731;
          border-radius:8px; text-decoration:none; color:#e7eaee; }}
    .ch:hover {{ border-color:#2c3949; }}
    .ch .num {{ color:#5fa8ff; font-weight:600; min-width:46px; }}
    .ch .title {{ flex:1; padding:0 12px; }}
    .ch .pgs {{ color:#8a96a4; font-size:12px; }}
  </style>
</head>
<body>
  <div class="wrap">
    <h1>{book_title}</h1>
    <div class="meta">{total_pages} pages · {chapter_count} chapters · detection: {detection_method}</div>
    <div class="ch-list">
      {chapter_links}
    </div>
  </div>
</body>
</html>
"""


def write_chapter_html(book_id: str, book_title: str, total_pages: int,
                       chapters: List[Chapter], ch_idx: int, doc: fitz.Document,
                       out_dir: Path):
    """Build one chapter HTML referencing the page images and embedding
    per-page text in hidden divs."""
    ch = chapters[ch_idx]
    pages_html_parts = []
    for page_idx in range(ch.page_start, ch.page_end + 1):
        page_num = page_idx + 1
        text = html_escape(page_text(doc, page_idx))
        pages_html_parts.append(PAGE_BLOCK_TEMPLATE.format(
            page_num=page_num, escaped_text=text, fmt=PAGE_FORMAT,
        ))

    prev_link = (
        f'<a href="{chapters[ch_idx - 1].html_filename}">← Prev</a>' if ch_idx > 0 else ''
    )
    next_link = (
        f'<a href="{chapters[ch_idx + 1].html_filename}">Next →</a>' if ch_idx + 1 < len(chapters) else ''
    )

    html = CHAPTER_HTML_TEMPLATE.format(
        book_title=html_escape(book_title),
        chapter_title=html_escape(ch.title),
        first_page=ch.page_start + 1, last_page=ch.page_end + 1,
        total_pages=total_pages,
        prev_link=prev_link, next_link=next_link,
        pages_html='\n'.join(pages_html_parts),
        book_id=html_escape(book_id),
        chapter_num=ch.number,
    )
    (out_dir / ch.html_filename).write_text(html, encoding='utf-8')


def write_index_html(book_title: str, total_pages: int,
                     chapters: List[Chapter], detection_method: str,
                     out_dir: Path):
    chapter_links = []
    for ch in chapters:
        npages = ch.page_end - ch.page_start + 1
        chapter_links.append(
            f'<a class="ch" href="{ch.html_filename}">'
            f'<span class="num">{ch.number}.</span>'
            f'<span class="title">{html_escape(ch.title)}</span>'
            f'<span class="pgs">{npages} pp</span>'
            f'</a>'
        )
    html = INDEX_HTML_TEMPLATE.format(
        book_title=html_escape(book_title),
        total_pages=total_pages,
        chapter_count=len(chapters),
        detection_method=detection_method,
        chapter_links='\n      '.join(chapter_links),
    )
    (out_dir / 'index.html').write_text(html, encoding='utf-8')


# ---------------------------------------------------------------------------
# Top-level conversion
# ---------------------------------------------------------------------------

def convert(pdf_path: Path, out_root: Path, book_id: str, book_title: str,
            dpi: int = DEFAULT_DPI, only_chapter: Optional[int] = None,
            verbose: bool = True) -> dict:
    if not pdf_path.exists():
        raise FileNotFoundError(pdf_path)
    out_dir = out_root / book_id
    out_dir.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(str(pdf_path))
    chapters, detection = detect_chapters(doc)
    if verbose:
        print(f"📚 {pdf_path.name}: {doc.page_count} pages, {len(chapters)} chapters ({detection})")

    # Render pages
    target_chapters = (
        [chapters[only_chapter - 1]] if only_chapter and 0 < only_chapter <= len(chapters)
        else chapters
    )
    page_numbers_to_render = []
    for ch in target_chapters:
        page_numbers_to_render.extend(range(ch.page_start, ch.page_end + 1))

    if verbose:
        print(f"   rendering {len(page_numbers_to_render)} pages @ {dpi} DPI to {out_dir}")
    t0 = time.time()
    for i, page_idx in enumerate(page_numbers_to_render, 1):
        out_path = out_dir / f"p{page_idx + 1:03d}.{PAGE_FORMAT}"
        render_page(doc, page_idx, out_path, dpi)
        if verbose and i % 25 == 0:
            elapsed = time.time() - t0
            rate = i / max(0.001, elapsed)
            eta = (len(page_numbers_to_render) - i) / max(0.001, rate)
            print(f"   ...{i}/{len(page_numbers_to_render)} pages  {rate:.1f}p/s  eta {eta:.0f}s")

    # Build chapter HTML files
    for ch_idx, ch in enumerate(chapters):
        if only_chapter and ch.number != only_chapter:
            continue
        write_chapter_html(book_id, book_title, doc.page_count, chapters, ch_idx, doc, out_dir)

    # Build the index page
    if not only_chapter:
        write_index_html(book_title, doc.page_count, chapters, detection, out_dir)

    # Persist metadata
    meta = {
        'book_id': book_id,
        'book_title': book_title,
        'pdf_filename': pdf_path.name,
        'total_pages': doc.page_count,
        'detection_method': detection,
        'dpi': dpi,
        'chapters': [asdict(c) for c in chapters],
    }
    (out_dir / 'book.json').write_text(json.dumps(meta, indent=2), encoding='utf-8')
    doc.close()

    if verbose:
        size_mb = sum(p.stat().st_size for p in out_dir.glob('*.png')) / (1024 * 1024)
        print(f"   ✅ done in {time.time() - t0:.0f}s; image total {size_mb:.1f} MB")

    return meta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('pdf', type=Path)
    ap.add_argument('--out-root', type=Path,
                    default=Path.home() / 'saanvi' / 'MathsBooksHTML')
    ap.add_argument('--book-id', help='Slug for the output folder. Defaults to PDF stem.')
    ap.add_argument('--title', help='Display title. Defaults to PDF stem prettified.')
    ap.add_argument('--dpi', type=int, default=DEFAULT_DPI)
    ap.add_argument('--only-chapter', type=int,
                    help='Only render this chapter (1-indexed) — useful for testing.')
    args = ap.parse_args()

    book_id = args.book_id or args.pdf.stem.lower().replace(' ', '_')[:60]
    title = args.title or args.pdf.stem.replace('-', ' ').replace('_', ' ').title()

    convert(args.pdf, args.out_root, book_id=book_id, book_title=title,
            dpi=args.dpi, only_chapter=args.only_chapter)


if __name__ == '__main__':
    main()
