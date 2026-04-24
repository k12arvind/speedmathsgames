#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
generate_pdf.py

Generates a clean daily-GK PDF from a Drishti IAS news-analysis URL.

Output structure:
  - Cover title + date
  - One section box per Drishti section (e.g. "Facts for UPSC Mains", "Rapid Fire")
  - Per-article: title, tags line, star rating, source (if any), full content

Keeps full detail — no summarization — so the reader gets the same density as
the source page.
"""

from __future__ import annotations

import hashlib
import io
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import requests
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image as RLImage,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from extract_html import (
    extract_articles_from_html,
    extract_date_from_url,
    fetch_html_content,
    group_by_section,
)


def _escape(text: str) -> str:
    return (
        (text or '')
        .replace('&', '&amp;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
    )


def _readable_date(url: str) -> str:
    d = extract_date_from_url(url)
    if d:
        try:
            dt = datetime.strptime(f"{d['day']} {d['month']} {d['year']}", '%d %B %Y')
            return dt.strftime('%d %B %Y')
        except ValueError:
            pass
    return datetime.now().strftime('%d %B %Y')


def _filename_from_url(url: str) -> str:
    d = extract_date_from_url(url)
    if d:
        return f"drishti_current_affairs_{d['year']}_{d['month'].lower()}_{d['day']}.pdf"
    return f"drishti_current_affairs_{datetime.now().strftime('%Y_%m_%d')}.pdf"


def _build_styles():
    base = getSampleStyleSheet()
    return {
        'title': ParagraphStyle(
            'DrishtiTitle', parent=base['Heading1'],
            fontSize=20, leading=24, alignment=TA_CENTER,
            textColor=HexColor('#1a365d'), fontName='Helvetica-Bold',
            spaceAfter=4,
        ),
        'subtitle': ParagraphStyle(
            'DrishtiSubtitle', parent=base['Normal'],
            fontSize=12, leading=16, alignment=TA_CENTER,
            textColor=HexColor('#4a5568'), fontName='Helvetica',
            spaceAfter=18,
        ),
        'section_header': ParagraphStyle(
            'SectionHeader', parent=base['Heading1'],
            fontSize=15, leading=19, alignment=TA_CENTER,
            textColor=HexColor('#FFFFFF'), fontName='Helvetica-Bold',
        ),
        'article_title': ParagraphStyle(
            'ArticleTitle', parent=base['Heading2'],
            fontSize=13, leading=17, alignment=TA_LEFT,
            textColor=HexColor('#b22222'), fontName='Helvetica-Bold',
            spaceBefore=14, spaceAfter=4,
        ),
        'meta': ParagraphStyle(
            'MetaLine', parent=base['Normal'],
            fontSize=8.5, leading=12, alignment=TA_LEFT,
            textColor=HexColor('#718096'), fontName='Helvetica-Oblique',
            spaceAfter=8,
        ),
        'heading2': ParagraphStyle(
            'ContentH2', parent=base['Heading3'],
            fontSize=11.5, leading=15, alignment=TA_LEFT,
            textColor=HexColor('#2d3748'), fontName='Helvetica-Bold',
            spaceBefore=10, spaceAfter=4,
        ),
        'heading3': ParagraphStyle(
            'ContentH3', parent=base['Heading4'],
            fontSize=10.5, leading=14, alignment=TA_LEFT,
            textColor=HexColor('#2d3748'), fontName='Helvetica-Bold',
            spaceBefore=8, spaceAfter=3,
        ),
        'body': ParagraphStyle(
            'Body', parent=base['Normal'],
            fontSize=10, leading=14, alignment=TA_JUSTIFY,
            textColor=HexColor('#2c3e50'), fontName='Helvetica',
            spaceAfter=6,
        ),
        'bullet': ParagraphStyle(
            'Bullet', parent=base['Normal'],
            fontSize=9.5, leading=13.5, alignment=TA_LEFT,
            textColor=HexColor('#34495e'), fontName='Helvetica',
            leftIndent=16, bulletIndent=4, spaceAfter=4,
        ),
        'callout': ParagraphStyle(
            'Callout', parent=base['Normal'],
            fontSize=9.5, leading=13, alignment=TA_LEFT,
            textColor=HexColor('#2d3748'), fontName='Helvetica',
            leftIndent=10, rightIndent=10, spaceBefore=6, spaceAfter=6,
        ),
        'footer': ParagraphStyle(
            'Footer', parent=base['Normal'],
            fontSize=8, alignment=TA_CENTER,
            textColor=HexColor('#a0aec0'), fontName='Helvetica-Oblique',
        ),
    }


# Colors cycled per section box (Drishti uses blue/green/cyan dividers — we pick
# a deep-blue primary and let section boxes stay uniform for readability).
SECTION_BG = HexColor('#1a365d')


def _section_box(title: str, styles) -> Table:
    t = Table(
        [[Paragraph(f'<b>{_escape(title).upper()}</b>', styles['section_header'])]],
        colWidths=[6.5 * inch],
    )
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), SECTION_BG),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    return t


def _callout_box(text: str, styles) -> Table:
    t = Table(
        [[Paragraph(_escape(text), styles['callout'])]],
        colWidths=[6.5 * inch],
    )
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), HexColor('#f1f5f9')),
        ('BOX', (0, 0), (-1, -1), 0.6, HexColor('#cbd5e1')),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    return t


def _stars_str(n: int) -> str:
    # Helvetica lacks the ★ glyph; use an ASCII-safe rating instead.
    n = max(0, min(5, int(n or 0)))
    return f'Importance: {n}/5'


# Target usable image width on A4 at 0.75" margins ≈ 6.5 inches.
_MAX_IMG_WIDTH = 6.2 * inch
# Safety cap: never let an image consume more than this much vertical space on one page.
_MAX_IMG_HEIGHT = 7.5 * inch


def _download_image(src: str, cache_dir: Path) -> Optional[Path]:
    """Download an image URL to cache_dir and return the local path.

    Silently returns None on any failure so one bad image doesn't kill the PDF.
    WebP is preserved as-is; ReportLab routes through Pillow which decodes WebP.
    """
    try:
        key = hashlib.sha1(src.encode('utf-8')).hexdigest()[:16]
        suffix = Path(src.split('?', 1)[0]).suffix.lower() or '.img'
        dest = cache_dir / f'{key}{suffix}'
        if dest.exists() and dest.stat().st_size > 0:
            return dest
        headers = {
            'User-Agent': (
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/120.0.0.0 Safari/537.36'
            ),
            'Referer': 'https://www.drishtiias.com/',
        }
        resp = requests.get(src, headers=headers, timeout=30, stream=True)
        resp.raise_for_status()
        with open(dest, 'wb') as f:
            for chunk in resp.iter_content(8192):
                f.write(chunk)
        if dest.stat().st_size == 0:
            dest.unlink(missing_ok=True)
            return None
        return dest
    except Exception as e:
        print(f'   ⚠️  image download failed: {src} — {e}')
        return None


def _build_image_flowable(local_path: Path) -> Optional[RLImage]:
    """Create a ReportLab Image scaled to fit page width, preserving aspect ratio.

    WebP and other Pillow-decodable formats are converted to PNG on the fly
    because ReportLab's Image flowable expects a format it can embed (JPEG/PNG).
    """
    try:
        from PIL import Image as PILImage
        with PILImage.open(local_path) as im:
            im.load()
            # Normalize mode (WebP with alpha → flatten to white).
            if im.mode in ('RGBA', 'LA'):
                bg = PILImage.new('RGB', im.size, (255, 255, 255))
                bg.paste(im, mask=im.split()[-1])
                im = bg
            elif im.mode != 'RGB':
                im = im.convert('RGB')

            buf = io.BytesIO()
            im.save(buf, format='PNG', optimize=True)
            buf.seek(0)
            natural_w, natural_h = im.size

        aspect = natural_h / natural_w if natural_w else 1.0
        draw_w = min(_MAX_IMG_WIDTH, natural_w * 72.0 / 96.0)  # treat px as 96 dpi
        draw_h = draw_w * aspect
        if draw_h > _MAX_IMG_HEIGHT:
            draw_h = _MAX_IMG_HEIGHT
            draw_w = draw_h / aspect

        img = RLImage(buf, width=draw_w, height=draw_h)
        img.hAlign = 'CENTER'
        return img
    except Exception as e:
        print(f'   ⚠️  image render failed: {local_path} — {e}')
        return None


def _render_article(article: Dict, styles, image_cache_dir: Path) -> List:
    story = []

    story.append(Paragraph(_escape(article['title']), styles['article_title']))

    # Meta line: stars + tags + source
    meta_parts = []
    if article.get('stars'):
        meta_parts.append(_stars_str(article['stars']))
    if article.get('tags'):
        meta_parts.append(' · '.join(_escape(t) for t in article['tags']))
    if article.get('source'):
        meta_parts.append(f"Source: {_escape(article['source'])}")
    if meta_parts:
        story.append(Paragraph(' &nbsp;|&nbsp; '.join(meta_parts), styles['meta']))

    for block in article.get('blocks', []):
        btype = block['type']
        if btype == 'image':
            src = block.get('src')
            if not src:
                continue
            local = _download_image(src, image_cache_dir)
            if not local:
                continue
            flow = _build_image_flowable(local)
            if not flow:
                continue
            story.append(Spacer(1, 0.05 * inch))
            story.append(flow)
            caption = block.get('alt')
            if caption and caption.strip() not in ('', 'image1', 'image'):
                pretty = _escape(caption.replace('_', ' ').strip())
                story.append(Paragraph(pretty, styles['meta']))
            story.append(Spacer(1, 0.08 * inch))
            continue

        text = block.get('text') or ''
        if not text:
            continue
        if btype == 'heading':
            lvl = block.get('level') or 2
            style = styles['heading2'] if lvl <= 2 else styles['heading3']
            story.append(Paragraph(_escape(text), style))
        elif btype == 'paragraph':
            story.append(Paragraph(_escape(text), styles['body']))
        elif btype == 'bullet':
            story.append(Paragraph(f'• {_escape(text)}', styles['bullet']))
        elif btype == 'callout':
            story.append(_callout_box(text, styles))

    story.append(Spacer(1, 0.15 * inch))
    return story


def create_pdf_from_url(url: str, output_path: Path) -> Dict:
    print('=' * 60)
    print('Drishti IAS Daily Current-Affairs PDF Generator')
    print('=' * 60)

    print(f'🌐 Fetching {url}')
    html = fetch_html_content(url)
    print('✅ HTML loaded')

    print('🔍 Extracting articles...')
    articles = extract_articles_from_html(html)
    if not articles:
        raise ValueError('No articles found on the Drishti page')
    print(f'✅ {len(articles)} articles found')

    grouped = group_by_section(articles)
    print(f'📂 Sections: {list(grouped.keys())}')

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Per-day image cache sits alongside the PDF so regeneration reuses downloads.
    image_cache_dir = output_path.parent / '.image_cache' / output_path.stem
    image_cache_dir.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(output_path), pagesize=A4,
        leftMargin=0.75 * inch, rightMargin=0.75 * inch,
        topMargin=0.75 * inch, bottomMargin=0.75 * inch,
        title='Drishti Daily Current Affairs',
    )

    styles = _build_styles()
    story: List = []

    date_str = _readable_date(url)
    story.append(Paragraph('Drishti IAS — Daily Current Affairs', styles['title']))
    story.append(Paragraph(date_str, styles['subtitle']))

    for section_name, section_articles in grouped.items():
        story.append(_section_box(section_name, styles))
        story.append(Spacer(1, 0.1 * inch))
        for art in section_articles:
            story.extend(_render_article(art, styles, image_cache_dir))

    story.append(Spacer(1, 0.3 * inch))
    story.append(Paragraph(
        f'Source: drishtiias.com · Generated {datetime.now().strftime("%d %B %Y")}',
        styles['footer'],
    ))

    doc.build(story)
    size_kb = output_path.stat().st_size / 1024
    print(f'✅ PDF saved to: {output_path}')
    print(f'📊 Size: {size_kb:.1f} KB')
    return {
        'success': True,
        'path': str(output_path),
        'filename': output_path.name,
        'size_kb': size_kb,
        'article_count': len(articles),
        'section_count': len(grouped),
    }


def main():
    if len(sys.argv) < 2:
        print('Usage: python generate_pdf.py <url> [output_path]')
        sys.exit(1)

    url = sys.argv[1]
    if len(sys.argv) > 2:
        output_path = Path(sys.argv[2]).expanduser().resolve()
    else:
        output_path = Path.home() / 'saanvi' / 'DrishtiDailyGK' / _filename_from_url(url)

    try:
        create_pdf_from_url(url, output_path)
    except Exception as e:
        print(f'❌ Error: {e}')
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
