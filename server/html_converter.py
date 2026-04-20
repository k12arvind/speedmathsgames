"""
PDF → Semantic HTML converter for current affairs PDFs.

Extracts section-level content with proper formatting (headings, bullets,
bold/italic) and stores in the html_articles table.
"""

import sqlite3
import json
import re
import fitz  # PyMuPDF
from pathlib import Path
from datetime import datetime
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
            annotation_type TEXT NOT NULL,  -- 'highlight', 'note'
            start_offset INTEGER,          -- character offset in plain_text
            end_offset INTEGER,
            highlighted_text TEXT,          -- the selected text
            note_text TEXT,                 -- user's note
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


def convert_pdf_to_html(pdf_path: str) -> List[Dict]:
    """Convert a PDF to a list of semantic HTML sections.

    Returns list of {title, category, page, html, plain_text}
    """
    doc = fitz.open(pdf_path)
    sections = []
    current_section = None
    current_category = 'General'

    for page_idx in range(len(doc)):
        page = doc[page_idx]
        blocks = page.get_text('dict')['blocks']

        for b in blocks:
            if 'lines' not in b:
                continue
            for line in b['lines']:
                full_text = ''.join(span['text'] for span in line['spans']).strip()
                if not full_text:
                    continue

                first_span = line['spans'][0]
                size = first_span['size']
                bold = bool(first_span['flags'] & (1 << 4))

                # Skip overall title (18pt+) and date lines
                if size >= 18:
                    continue
                if size >= 12 and not bold and re.match(r'^\d+\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}$', full_text):
                    continue

                # Category header: 14pt+ bold, known category name
                cat_check = full_text.strip().rstrip(':')
                if size >= 13.5 and bold and cat_check in CATEGORY_MAP:
                    current_category = CATEGORY_MAP[cat_check]
                    continue

                # Section title: 12pt bold, substantial text
                if size >= 11.5 and bold and len(full_text) > 15:
                    # Don't create sections from "Daily Current Affairs" or similar
                    if 'Daily Current Affairs' in full_text or 'Weekly Current Affairs' in full_text:
                        continue

                    if current_section and len(current_section['html_parts']) > 1:
                        sections.append(current_section)

                    current_section = {
                        'title': full_text,
                        'category': current_category,
                        'page': page_idx + 1,
                        'html_parts': [f'<h2>{_esc(full_text)}</h2>'],
                        'plain_parts': [full_text],
                    }
                    continue

                if not current_section:
                    continue

                # Body content
                is_bullet = full_text.startswith('•') or full_text.startswith('- ')

                # Build styled HTML from spans
                html_line = ''
                for span in line['spans']:
                    t = span['text']
                    if not t.strip():
                        html_line += t
                        continue
                    sb = bool(span['flags'] & (1 << 4))
                    si = bool(span['flags'] & (1 << 1))
                    ht = _esc(t)
                    if sb:
                        ht = f'<strong>{ht}</strong>'
                    if si:
                        ht = f'<em>{ht}</em>'
                    html_line += ht

                if is_bullet:
                    html_line = re.sub(r'^[•\-]\s*', '', html_line).strip()
                    current_section['html_parts'].append(f'<li>{html_line}</li>')
                elif re.match(r'^Key\s+Points', full_text, re.IGNORECASE):
                    current_section['html_parts'].append(f'<h3>{_esc(full_text)}</h3>')
                elif re.match(r'^(In the News|Background|Context)', full_text):
                    current_section['html_parts'].append(f'<p class="lead">{html_line}</p>')
                else:
                    current_section['html_parts'].append(f'<p>{html_line}</p>')

                current_section['plain_parts'].append(full_text)

    if current_section and len(current_section['html_parts']) > 1:
        sections.append(current_section)

    doc.close()

    # Post-process: wrap consecutive <li> in <ul>
    for sec in sections:
        parts = sec['html_parts']
        processed = []
        in_list = False
        for p in parts:
            if p.startswith('<li>'):
                if not in_list:
                    processed.append('<ul>')
                    in_list = True
                processed.append(p)
            else:
                if in_list:
                    processed.append('</ul>')
                    in_list = False
                processed.append(p)
        if in_list:
            processed.append('</ul>')
        sec['html'] = '\n'.join(processed)
        sec['plain_text'] = '\n'.join(sec['plain_parts'])
        del sec['html_parts']
        del sec['plain_parts']

    return sections


def store_html_sections(db_path: str, pdf_filename: str, sections: List[Dict]):
    """Store converted sections in the html_articles table."""
    init_html_tables(db_path)
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # Remove old entries for this PDF
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
