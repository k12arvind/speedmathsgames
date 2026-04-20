"""
PDF → Semantic HTML converter for current affairs PDFs.

Extracts section-level content with proper formatting (headings, bullets,
bold/italic) and stores in the html_articles table.

Key design: PDF text is extracted line-by-line, but consecutive body-text
lines are JOINED into single paragraphs. Bullet continuation lines (that
don't start with •) are merged into the previous bullet item.
"""

import sqlite3
import re
import fitz  # PyMuPDF
from pathlib import Path
from typing import List, Dict


# Category normalization
CATEGORY_MAP = {
    'National': 'National',
    'International': 'International Affairs',
    'Economy': 'Economy & Business',
    'Economy & Business': 'Economy & Business',
    'Environment & Science': 'Environment & Science',
    'Science & Technology': 'Environment & Science',
    'Sports': 'Awards / Sports / Defence',
    'Defence': 'Awards / Sports / Defence',
    'Polity': 'Polity & Constitution',
    'Legal': 'Supreme Court / High Court Judgements',
    'Awards': 'Awards / Sports / Defence',
}


def init_html_tables(db_path: str):
    """Create html_articles and html_annotations tables if they don't exist."""
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS html_articles (
            article_id INTEGER PRIMARY KEY AUTOINCREMENT,
            pdf_filename TEXT NOT NULL,
            section_index INTEGER NOT NULL,
            section_title TEXT,
            category TEXT,
            html_content TEXT NOT NULL,
            plain_text TEXT,
            page_number INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(pdf_filename, section_index)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS html_annotations (
            annotation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            article_id INTEGER NOT NULL,
            pdf_filename TEXT NOT NULL,
            section_index INTEGER NOT NULL,
            annotation_type TEXT NOT NULL,
            start_offset INTEGER,
            end_offset INTEGER,
            highlighted_text TEXT,
            note_text TEXT,
            color TEXT DEFAULT '#FFFF00',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT 1,
            FOREIGN KEY (article_id) REFERENCES html_articles(article_id)
        )
    """)

    c.execute("CREATE INDEX IF NOT EXISTS idx_html_articles_pdf ON html_articles(pdf_filename)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_html_annotations_article ON html_annotations(article_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_html_annotations_pdf ON html_annotations(pdf_filename)")

    conn.commit()
    conn.close()


def _esc(s: str) -> str:
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def _styled_span(span) -> str:
    """Convert a PDF text span to styled HTML."""
    t = span['text']
    if not t.strip():
        return t
    sb = bool(span['flags'] & (1 << 4))  # bold
    si = bool(span['flags'] & (1 << 1))  # italic
    ht = _esc(t)
    if sb:
        ht = f'<strong>{ht}</strong>'
    if si:
        ht = f'<em>{ht}</em>'
    return ht


def _line_to_html(line) -> str:
    """Convert all spans in a line to HTML."""
    return ''.join(_styled_span(s) for s in line['spans'])


def convert_pdf_to_html(pdf_path: str) -> List[Dict]:
    """Convert a PDF to a list of semantic HTML sections.

    Lines that belong to the same paragraph are joined. Bullet continuation
    lines are merged into the previous bullet item.
    """
    doc = fitz.open(pdf_path)
    sections = []
    current_section = None
    current_category = 'General'

    # Collect all classified lines first
    classified_lines = []

    for page_idx in range(len(doc)):
        page = doc[page_idx]
        blocks = page.get_text('dict')['blocks']

        for b in blocks:
            if 'lines' not in b:
                continue
            for line in b['lines']:
                full_text = ''.join(s['text'] for s in line['spans']).strip()
                if not full_text:
                    continue

                first_span = line['spans'][0]
                size = first_span['size']
                bold = bool(first_span['flags'] & (1 << 4))
                html = _line_to_html(line)

                classified_lines.append({
                    'text': full_text,
                    'html': html,
                    'size': size,
                    'bold': bold,
                    'page': page_idx + 1,
                    'is_bullet': full_text.startswith('•') or full_text.startswith('- '),
                    'is_key_points': bool(re.match(r'^Key\s+Points', full_text, re.IGNORECASE)),
                })

    doc.close()

    # Now process classified lines: group into sections, merge paragraphs
    for cl in classified_lines:
        # Skip title and date
        if cl['size'] >= 18:
            continue
        if cl['size'] >= 12 and not cl['bold'] and re.match(
            r'^\d+\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}$',
            cl['text']
        ):
            continue

        # Category header
        cat_check = cl['text'].strip().rstrip(':')
        if cl['size'] >= 13.5 and cl['bold'] and cat_check in CATEGORY_MAP:
            current_category = CATEGORY_MAP[cat_check]
            continue

        # Section title
        if cl['size'] >= 11.5 and cl['bold'] and len(cl['text']) > 15:
            if 'Daily Current Affairs' in cl['text'] or 'Weekly Current Affairs' in cl['text']:
                continue

            # Save previous section
            if current_section and current_section['elements']:
                sections.append(_finalize_section(current_section))

            current_section = {
                'title': cl['text'],
                'category': current_category,
                'page': cl['page'],
                'elements': [],  # list of {type: 'p'|'bullet'|'h3', html, text}
            }
            continue

        if not current_section:
            continue

        # Classify this line
        if cl['is_key_points']:
            current_section['elements'].append({
                'type': 'h3', 'html': _esc(cl['text']), 'text': cl['text']
            })
        elif cl['is_bullet']:
            # Start a new bullet item (strip the bullet character)
            bullet_html = re.sub(r'^[•\-]\s*', '', cl['html']).strip()
            bullet_text = re.sub(r'^[•\-]\s*', '', cl['text']).strip()
            current_section['elements'].append({
                'type': 'bullet', 'html': bullet_html, 'text': bullet_text
            })
        else:
            # Body text — should we merge with previous element?
            prev = current_section['elements'][-1] if current_section['elements'] else None

            if prev and prev['type'] == 'bullet' and cl['size'] < 11:
                # Continuation of previous bullet (same or smaller font, no bullet marker)
                prev['html'] += ' ' + cl['html']
                prev['text'] += ' ' + cl['text']
            elif prev and prev['type'] == 'p' and cl['size'] < 11 and not cl['bold']:
                # Continuation of previous paragraph
                prev['html'] += ' ' + cl['html']
                prev['text'] += ' ' + cl['text']
            else:
                # New paragraph
                current_section['elements'].append({
                    'type': 'p', 'html': cl['html'], 'text': cl['text']
                })

    # Don't forget the last section
    if current_section and current_section['elements']:
        sections.append(_finalize_section(current_section))

    return sections


def _finalize_section(sec: dict) -> dict:
    """Convert section elements into final HTML string."""
    html_parts = [f'<h2>{_esc(sec["title"])}</h2>']
    plain_parts = [sec['title']]
    in_list = False

    for el in sec['elements']:
        if el['type'] == 'bullet':
            if not in_list:
                html_parts.append('<ul>')
                in_list = True
            html_parts.append(f'<li>{el["html"]}</li>')
        else:
            if in_list:
                html_parts.append('</ul>')
                in_list = False
            if el['type'] == 'h3':
                html_parts.append(f'<h3>{el["html"]}</h3>')
            elif el['type'] == 'p':
                html_parts.append(f'<p>{el["html"]}</p>')

        plain_parts.append(el['text'])

    if in_list:
        html_parts.append('</ul>')

    return {
        'title': sec['title'],
        'category': sec['category'],
        'page': sec['page'],
        'html': '\n'.join(html_parts),
        'plain_text': '\n'.join(plain_parts),
    }


def store_html_sections(db_path: str, pdf_filename: str, sections: List[Dict]):
    """Store converted sections in the html_articles table."""
    init_html_tables(db_path)
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    c.execute("DELETE FROM html_articles WHERE pdf_filename = ?", (pdf_filename,))

    for i, sec in enumerate(sections):
        c.execute("""
            INSERT INTO html_articles
            (pdf_filename, section_index, section_title, category, html_content, plain_text, page_number)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (pdf_filename, i, sec['title'], sec['category'], sec['html'], sec['plain_text'], sec['page']))

    conn.commit()
    conn.close()
    return len(sections)


def convert_and_store(pdf_path: str, db_path: str) -> int:
    """Convert a PDF and store all sections. Returns section count."""
    sections = convert_pdf_to_html(pdf_path)
    pdf_filename = Path(pdf_path).name
    return store_html_sections(db_path, pdf_filename, sections)
