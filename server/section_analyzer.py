"""
Section Analyzer — maps questions to PDF sections via SID tags,
computes per-section performance, and generates color-coded PDFs.

Section performance scale (1-4):
  4 = Needs lots of revision (accuracy < 50%)
  3 = Needs revision (50-69%)
  2 = Fair (70-84%)
  1 = Good, minimal revision (85%+)
  0 = Not tested yet
"""

import sqlite3
import json
import fitz  # PyMuPDF
from pathlib import Path
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional, Tuple


# Color scheme for the 4-level scale — visually distinct
COLORS = {
    4: (0.85, 0.11, 0.11),   # Deep Red — must revise
    3: (0.61, 0.15, 0.69),   # Purple — needs revision
    2: (0.13, 0.47, 0.85),   # Blue — fair
    1: (0.06, 0.73, 0.40),   # Green — good
    0: (0.58, 0.64, 0.70),   # Grey — not tested
}

LABELS = {
    4: 'Must Revise',
    3: 'Needs Revision',
    2: 'Fair',
    1: 'Good',
    0: 'Not Tested',
}


def get_section_performance(pdf_filename: str,
                            questions_db_path: str,
                            assessment_db_path: str) -> List[Dict]:
    """Get per-section performance for a PDF.

    Groups questions by their SID prefix (which maps to a topic section),
    cross-references with test results, and returns accuracy per section.

    Returns list of {
        sid_prefix, category, question_count, attempted, correct, wrong,
        accuracy, level (1-4), label, sample_questions: [...]
    }
    """
    # Load questions for this PDF
    conn = sqlite3.connect(questions_db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
        SELECT question_id, question_text, answer_text, category, tags
        FROM questions WHERE pdf_filename = ?
        ORDER BY question_id
    """, (pdf_filename,))
    questions = [dict(r) for r in c.fetchall()]
    conn.close()

    if not questions:
        return []

    # Group questions by topic section.
    # SID tags: sid:legaledge_2026-april-6_0001
    # Consecutive SIDs with the same category = one section.
    sections = []
    current_section = None

    for q in questions:
        tags = json.loads(q['tags']) if q['tags'] else []
        sid = next((t.split(':')[1] for t in tags if t.startswith('sid:')), None)
        if not sid:
            continue

        # Group by: same category in consecutive SIDs = same section
        cat = q['category']
        if current_section and current_section['category'] == cat:
            current_section['question_ids'].append(q['question_id'])
            current_section['questions'].append(q)
            current_section['last_sid'] = sid
        else:
            if current_section:
                sections.append(current_section)
            current_section = {
                'first_sid': sid,
                'last_sid': sid,
                'category': cat,
                'question_ids': [q['question_id']],
                'questions': [q],
            }

    if current_section:
        sections.append(current_section)

    # Cross-reference with test performance
    conn2 = sqlite3.connect(assessment_db_path)
    conn2.row_factory = sqlite3.Row
    c2 = conn2.cursor()

    # Get all attempts for this PDF's questions
    c2.execute("""
        SELECT qa.question_text, qa.is_correct, qa.user_answer
        FROM question_attempts qa
        JOIN test_sessions ts ON qa.session_id = ts.session_id
        WHERE ts.pdf_id = ? OR ts.pdf_filename = ?
    """, (pdf_filename, pdf_filename))

    # Build lookup: question_text → [is_correct, ...]
    text_results = defaultdict(list)
    for r in c2.fetchall():
        if r['user_answer']:  # Only count answered questions
            text_results[r['question_text']].append(bool(r['is_correct']))
    conn2.close()

    # Calculate per-section performance
    result = []
    for sec in sections:
        attempted = 0
        correct = 0
        wrong = 0

        for q in sec['questions']:
            results = text_results.get(q['question_text'], [])
            if results:
                attempted += 1
                # Use latest attempt result
                if results[-1]:
                    correct += 1
                else:
                    wrong += 1

        accuracy = round(correct / attempted * 100, 1) if attempted > 0 else None

        # Determine level
        if attempted == 0:
            level = 0
        elif accuracy >= 85:
            level = 1
        elif accuracy >= 70:
            level = 2
        elif accuracy >= 50:
            level = 3
        else:
            level = 4

        # Infer topic title from first question
        first_q = sec['questions'][0]['question_text']
        # Use answer of first question as a rough topic hint
        first_a = sec['questions'][0].get('answer_text', '')

        result.append({
            'category': sec['category'],
            'question_count': len(sec['question_ids']),
            'attempted': attempted,
            'correct': correct,
            'wrong': wrong,
            'accuracy': accuracy,
            'level': level,
            'label': LABELS[level],
            'first_question': first_q[:100],
            'sample_answer': (first_a or '')[:60],
        })

    return result


def generate_scored_pdf(pdf_path: str,
                        section_data: List[Dict],
                        output_path: str = None) -> str:
    """Generate a color-coded version of the PDF with margin bars
    indicating revision priority per section.

    Args:
        pdf_path: path to original PDF
        section_data: output of get_section_performance()
        output_path: where to save (default: same dir with _scored suffix)

    Returns: path to scored PDF
    """
    if not output_path:
        p = Path(pdf_path)
        output_path = str(p.parent / (p.stem + '_scored.pdf'))

    doc = fitz.open(pdf_path)
    total_pages = len(doc)

    if not section_data:
        doc.close()
        return pdf_path  # Nothing to annotate

    # Map sections to pages by extracting section headers from each page
    # and matching them to the section_data order
    page_sections = _map_sections_to_pages(doc, section_data)

    # Add colored bars and a summary cover page
    _add_cover_page(doc, section_data, Path(pdf_path).name)
    _add_margin_bars(doc, page_sections, offset=1)  # offset=1 because cover page is first

    doc.save(output_path)
    doc.close()
    return output_path


def _map_sections_to_pages(doc, section_data: List[Dict]) -> Dict[int, List[Dict]]:
    """Map section_data entries to page numbers based on content flow.

    Since questions follow the PDF's section order, and we know each page's
    text content, we distribute sections across pages proportionally.
    """
    total_pages = len(doc)
    total_sections = len(section_data)
    if total_sections == 0:
        return {}

    # Simple proportional mapping: distribute sections evenly across pages
    # (More sophisticated: match via text search, but proportional is good enough
    # since sections appear in order in both the PDF and question list)
    page_sections = defaultdict(list)
    sections_per_page = max(1, total_sections / total_pages)

    for i, sec in enumerate(section_data):
        page_idx = min(int(i / sections_per_page), total_pages - 1)
        page_sections[page_idx].append(sec)

    return dict(page_sections)


def _add_cover_page(doc, section_data: List[Dict], filename: str):
    """Insert a summary cover page at the beginning of the PDF."""
    # A4 dimensions
    width, height = 595, 842
    cover = doc.new_page(pno=0, width=width, height=height)

    # Title
    cover.insert_text((40, 50), 'Revision Guide', fontsize=20, fontname='helv',
                       color=(0.2, 0.2, 0.2))
    cover.insert_text((40, 72), filename, fontsize=10, fontname='helv',
                       color=(0.5, 0.5, 0.5))
    cover.insert_text((40, 88), f'Generated: {datetime.now().strftime("%d %b %Y %H:%M")}',
                       fontsize=9, fontname='helv', color=(0.5, 0.5, 0.5))

    # Legend
    y = 115
    cover.insert_text((40, y), 'Color Legend:', fontsize=10, fontname='helv',
                       color=(0.3, 0.3, 0.3))
    y += 18
    for level in [4, 3, 2, 1, 0]:
        r, g, b = COLORS[level]
        cover.draw_rect(fitz.Rect(45, y - 10, 60, y + 2), color=(r, g, b), fill=(r, g, b))
        cover.insert_text((68, y), f'{LABELS[level]}', fontsize=9, fontname='helv',
                           color=(0.3, 0.3, 0.3))
        y += 16

    # Section table
    y += 15
    cover.insert_text((40, y), 'Section Performance:', fontsize=11, fontname='helv',
                       color=(0.2, 0.2, 0.2))
    y += 20

    # Table header
    cover.insert_text((45, y), '#', fontsize=8, fontname='helv', color=(0.5, 0.5, 0.5))
    cover.insert_text((60, y), 'Category', fontsize=8, fontname='helv', color=(0.5, 0.5, 0.5))
    cover.insert_text((240, y), 'Qs', fontsize=8, fontname='helv', color=(0.5, 0.5, 0.5))
    cover.insert_text((270, y), 'Correct', fontsize=8, fontname='helv', color=(0.5, 0.5, 0.5))
    cover.insert_text((320, y), 'Wrong', fontsize=8, fontname='helv', color=(0.5, 0.5, 0.5))
    cover.insert_text((365, y), 'Accuracy', fontsize=8, fontname='helv', color=(0.5, 0.5, 0.5))
    cover.insert_text((425, y), 'Status', fontsize=8, fontname='helv', color=(0.5, 0.5, 0.5))
    y += 5
    cover.draw_line((40, y), (width - 40, y), color=(0.8, 0.8, 0.8))
    y += 14

    for i, sec in enumerate(section_data):
        if y > height - 40:
            break  # Don't overflow

        r, g, b = COLORS[sec['level']]

        # Color indicator bar
        cover.draw_rect(fitz.Rect(40, y - 10, 52, y + 2), color=(r, g, b), fill=(r, g, b))

        cover.insert_text((60, y), sec['category'][:30], fontsize=9, fontname='helv',
                           color=(0.2, 0.2, 0.2))
        cover.insert_text((240, y), str(sec['question_count']), fontsize=9, fontname='helv',
                           color=(0.4, 0.4, 0.4))
        cover.insert_text((270, y), str(sec['correct']), fontsize=9, fontname='helv',
                           color=(0.06, 0.73, 0.50))
        cover.insert_text((320, y), str(sec['wrong']), fontsize=9, fontname='helv',
                           color=(0.94, 0.27, 0.27))

        acc_text = f"{sec['accuracy']}%" if sec['accuracy'] is not None else '—'
        cover.insert_text((365, y), acc_text, fontsize=9, fontname='helv',
                           color=(r, g, b))
        cover.insert_text((425, y), sec['label'], fontsize=9, fontname='helv',
                           color=(r, g, b))

        # Show topic hint (from first question)
        y += 12
        hint = sec.get('first_question', '')[:75]
        cover.insert_text((60, y), hint, fontsize=7, fontname='helv',
                           color=(0.6, 0.6, 0.6))

        y += 18


def _add_margin_bars(doc, page_sections: Dict[int, List[Dict]], offset: int = 0):
    """Add colored margin bars to each page of the original PDF content.

    offset: number of pages prepended (cover page) — shift page_sections indices.
    """
    for page_idx, sections in page_sections.items():
        actual_page = page_idx + offset
        if actual_page >= len(doc):
            continue

        page = doc[actual_page]
        page_height = page.rect.height

        # Determine worst (highest) level for this page
        worst = max(s['level'] for s in sections) if sections else 0
        r, g, b = COLORS[worst]

        # Draw a colored bar on the left margin (full height)
        bar_rect = fitz.Rect(0, 0, 8, page_height)
        page.draw_rect(bar_rect, color=(r, g, b), fill=(r, g, b), overlay=True)

        # If multiple sections on the page with different levels,
        # split the bar proportionally
        if len(sections) > 1:
            seg_height = page_height / len(sections)
            for i, sec in enumerate(sections):
                sr, sg, sb = COLORS[sec['level']]
                seg_rect = fitz.Rect(0, i * seg_height, 8, (i + 1) * seg_height)
                page.draw_rect(seg_rect, color=(sr, sg, sb), fill=(sr, sg, sb), overlay=True)
