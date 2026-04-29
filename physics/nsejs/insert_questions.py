"""
Insert classified NSEJS physics questions into physics_practice.db.

Schema reuse:
  - A virtual entry in physics_books with book_id='nsejs_papers' represents
    "NSEJS Previous Year Papers". Each year is a "chapter".
  - Questions go to physics_questions with:
        source_book_id = 'nsejs_papers'
        chapter_number = year (e.g. 2019)
        problem_number = original Q number from the paper
  - Topic tags go into physics_question_topics.

Idempotent: re-running for the same paper deletes prior NSEJS rows for that
year before inserting, so the latest classification always wins.

Skips:
  - non-physics questions
  - physics questions with `skip_reason` (figure-dependent etc.)
  - questions missing the correct answer
"""

from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _conn(db_path: Path) -> sqlite3.Connection:
    c = sqlite3.connect(str(db_path))
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA foreign_keys = ON')
    return c


def ensure_virtual_book(c: sqlite3.Connection):
    """Create the 'NSEJS Previous Year Papers' virtual book row if missing.
    The reader can't open this book — total_pages is 0 and there's no
    static-asset folder. Its only role is to namespace the questions and
    show up in the book filter on the practice setup page."""
    row = c.execute(
        "SELECT 1 FROM physics_books WHERE book_id = ?", ('nsejs_papers',)
    ).fetchone()
    now = _now()
    if not row:
        c.execute("""
            INSERT INTO physics_books
                (book_id, title, pdf_filename, total_pages, chapter_count,
                 detection_method, file_size_kb, added_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            'nsejs_papers',
            'NSEJS Previous Year Papers',
            None,            # not openable as a reader
            0,
            0,               # bumped after we know how many years
            'manual',
            None,
            now, now,
        ))


def upsert_year_chapter(c: sqlite3.Connection, year: int, paper_label: str):
    c.execute("""
        INSERT INTO physics_book_chapters
            (book_id, chapter_number, title, page_start, page_end, html_filename)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(book_id, chapter_number) DO UPDATE SET
            title = excluded.title
    """, ('nsejs_papers', year, paper_label, 0, 0, ''))


def delete_existing_for_year(c: sqlite3.Connection, year: int):
    c.execute("""
        DELETE FROM physics_questions
        WHERE source_book_id = 'nsejs_papers' AND chapter_number = ?
    """, (year,))


def insert_one_question(c: sqlite3.Connection, year: int, q: dict):
    parse_status = q.get('parse_status') or 'ok'
    cur = c.execute("""
        INSERT INTO physics_questions
            (source_book_id, chapter_number, problem_number,
             question_text, choice_a, choice_b, choice_c, choice_d, choice_e,
             correct_choice, official_solution,
             difficulty_band, parse_status,
             figure_image_path, correct_source, correct_confidence,
             added_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        'nsejs_papers',
        year,
        str(q['number']),
        q['body'],
        q['choices'].get('a') or None,
        q['choices'].get('b') or None,
        q['choices'].get('c') or None,
        q['choices'].get('d') or None,
        q['choices'].get('e') or None,
        (q.get('correct') or '').upper() or None,
        q.get('solution') or None,
        q.get('difficulty') or 'medium',
        parse_status,
        q.get('figure_image_path') or None,
        q.get('correct_source') or None,
        q.get('correct_confidence') or None,
        _now(), _now(),
    ))
    qid = cur.lastrowid

    topic_code = q.get('topic_code') or 'general'
    topic_name = q.get('topic_name') or topic_code.title()
    sub_code = q.get('subtopic_code') or ''
    sub_name = q.get('subtopic_name') or ''
    c.execute("""
        INSERT INTO physics_question_topics
            (question_id, topic_code, topic_name, subtopic_code, subtopic_name, is_active)
        VALUES (?, ?, ?, ?, ?, 1)
    """, (qid, topic_code, topic_name, sub_code, sub_name))


def main(paper_id: str = '2019_20', year: int = 2019,
         paper_label: str = 'NSEJS 2019-20 (Code 52)'):
    db_path = Path(__file__).resolve().parent.parent.parent / 'physics_practice.db'

    # Trigger schema migration (adds figure_image_path/correct_source/etc. on
    # DBs that pre-date those columns). Cheap; idempotent.
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
    from physics.practice_db import PhysicsPracticeDB
    PhysicsPracticeDB(str(db_path))

    classified_path = Path(__file__).parent / f'nsejs_{paper_id}_classified.json'

    if not classified_path.exists():
        print(f'no such file: {classified_path}', file=sys.stderr)
        sys.exit(1)

    data = json.loads(classified_path.read_text())
    qs = data['questions']

    physics_qs = [q for q in qs if q.get('subject') == 'physics']
    answerable = [
        q for q in physics_qs
        # Keep questions that either don't need a figure, OR do but have one
        # rendered (figure_image_path set). Must always have an answer.
        if q.get('correct')
        and (not q.get('skip_reason') or q.get('figure_image_path'))
    ]
    skipped_fig = len(physics_qs) - len(answerable)

    print(f'paper={paper_id} year={year}', file=sys.stderr)
    print(f'  total Qs in paper: {len(qs)}', file=sys.stderr)
    print(f'  physics Qs:        {len(physics_qs)}', file=sys.stderr)
    print(f'  answerable (no figure dep, has answer): {len(answerable)}', file=sys.stderr)
    print(f'  skipped:           {skipped_fig}', file=sys.stderr)

    with _conn(db_path) as c:
        ensure_virtual_book(c)
        upsert_year_chapter(c, year, paper_label)
        delete_existing_for_year(c, year)
        for q in answerable:
            insert_one_question(c, year, q)
        # Recompute chapter_count on the virtual book
        n_years = c.execute(
            "SELECT COUNT(*) AS n FROM physics_book_chapters WHERE book_id = ?",
            ('nsejs_papers',)
        ).fetchone()['n']
        c.execute("""
            UPDATE physics_books SET chapter_count = ?, updated_at = ?
            WHERE book_id = ?
        """, (n_years, _now(), 'nsejs_papers'))

    # Verify
    with _conn(db_path) as c:
        n_q = c.execute("""
            SELECT COUNT(*) AS n FROM physics_questions
            WHERE source_book_id = 'nsejs_papers' AND chapter_number = ?
        """, (year,)).fetchone()['n']
        topics = c.execute("""
            SELECT t.topic_code, COUNT(*) AS n
            FROM physics_question_topics t
            JOIN physics_questions q ON q.question_id = t.question_id
            WHERE q.source_book_id='nsejs_papers' AND q.chapter_number = ?
            GROUP BY t.topic_code
            ORDER BY n DESC
        """, (year,)).fetchall()
    print(f'\nInserted {n_q} questions for year {year}.', file=sys.stderr)
    for r in topics:
        print(f'  {r["topic_code"]:<12} {r["n"]}', file=sys.stderr)


if __name__ == '__main__':
    main(
        sys.argv[1] if len(sys.argv) > 1 else '2019_20',
        int(sys.argv[2]) if len(sys.argv) > 2 else 2019,
        sys.argv[3] if len(sys.argv) > 3 else 'NSEJS 2019-20 (Code 52)',
    )
