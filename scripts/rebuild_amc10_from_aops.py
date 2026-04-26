#!/usr/bin/env python3
"""
rebuild_amc10_from_aops.py

Rebuilds the AMC 10 question bank from the AoPS Wiki, replacing the broken
content created by the PDF text-extraction parser. Updates in place:

  amc10_questions.question_text         — full statement with LaTeX preserved
  amc10_questions.question_text_raw     — same (no separate raw form)
  amc10_questions.choice_a..e           — split per letter, LaTeX preserved
  amc10_questions.correct_choice        — from AoPS Answer Key page
  amc10_questions.official_solution     — full AoPS solution write-up
  amc10_questions.parse_status          — set to 'aops_scrape'
  amc10_questions.parse_notes           — provenance line

Idempotent and resumable. The on-disk HTML cache makes re-runs ~free.
After the rebuild, re-runs the auto-tagger on the fresh text so topic
classifications reflect the cleaner content.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from amc10.aops_scraper import AopsClient
from amc10.topics import classify_question


DB_PATH = Path.home() / 'clat_preparation' / 'amc10_practice.db'


def list_contests(conn) -> List[Dict]:
    rows = conn.execute(
        'SELECT contest_id, contest_label, year, season, contest_code FROM amc10_contests ORDER BY year, contest_code'
    ).fetchall()
    return [dict(r) for r in rows]


def fetch_contest_answers(client: AopsClient, year: int,
                          season: Optional[str], contest_code: Optional[str]) -> Optional[List[str]]:
    try:
        return client.fetch_answer_key(year, season, contest_code)
    except Exception as e:
        print(f'  ⚠️  answer-key fetch failed for {year} {season or ""} {contest_code or ""}: {e}')
        return None


def reclassify_topic(conn, question_id: int, qrow: Dict) -> None:
    """Update active topic tag based on the new question_text. Keeps any
    previous manual override intact (only updates rows with tag_source='auto')."""
    classification = classify_question(
        qrow.get('question_text') or '',
        qrow.get('official_solution') or '',
    )
    cur = conn.cursor()
    # Was there a manual override? If so, leave it alone.
    cur.execute('''
        SELECT 1 FROM amc10_question_topics
        WHERE question_id = ? AND tag_source = 'manual' AND is_active = 1
    ''', (question_id,))
    if cur.fetchone():
        return
    cur.execute('''
        DELETE FROM amc10_question_topics
        WHERE question_id = ? AND tag_source = 'auto'
    ''', (question_id,))
    cur.execute('''
        INSERT INTO amc10_question_topics
            (question_id, topic_code, topic_name, subtopic_code, subtopic_name,
             confidence, reasoning, tag_source, is_primary, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'auto', 1, 1)
    ''', (
        question_id, classification['topic_code'], classification['topic_name'],
        classification.get('subtopic_code'), classification.get('subtopic_name'),
        classification.get('confidence'), classification.get('reasoning'),
    ))


def rebuild(only_year: Optional[int] = None, retag: bool = True) -> None:
    client = AopsClient()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    contests = list_contests(conn)
    if only_year:
        contests = [c for c in contests if c['year'] == only_year]

    n_updated = 0
    n_failed = 0
    n_skipped = 0
    n_retagged = 0

    for contest in contests:
        year = contest['year']
        season = contest['season'] or None
        code = contest['contest_code'] or None
        label = contest['contest_label']
        print(f'\n=== {label} ===')

        answers = fetch_contest_answers(client, year, season, code)

        for num in range(1, 26):
            row = conn.execute(
                'SELECT question_id, problem_number FROM amc10_questions '
                'WHERE contest_id = ? AND problem_number = ?',
                (contest['contest_id'], num),
            ).fetchone()
            if not row:
                # Some contests had a missing question that was reconstructed
                # from solutions earlier — insert a fresh row in that case
                # (so all 25 are covered).
                conn.execute(
                    'INSERT INTO amc10_questions (contest_id, problem_number, question_text) '
                    'VALUES (?, ?, ?)',
                    (contest['contest_id'], num, ''),
                )
                row = conn.execute(
                    'SELECT question_id, problem_number FROM amc10_questions '
                    'WHERE contest_id = ? AND problem_number = ?',
                    (contest['contest_id'], num),
                ).fetchone()

            try:
                p = client.fetch_problem(year, season, code, num)
            except Exception as e:
                print(f'  ✗ #{num:02d} fetch failed: {e}')
                n_failed += 1
                continue

            correct = answers[num - 1] if answers and num - 1 < len(answers) else None

            conn.execute('''
                UPDATE amc10_questions SET
                    question_text       = ?,
                    question_text_raw   = ?,
                    choice_a            = ?,
                    choice_b            = ?,
                    choice_c            = ?,
                    choice_d            = ?,
                    choice_e            = ?,
                    correct_choice      = COALESCE(?, correct_choice),
                    official_solution   = ?,
                    official_solution_raw = ?,
                    parse_status        = 'aops_scrape',
                    parse_notes         = 'Rebuilt from AoPS Wiki on ' || datetime('now'),
                    updated_at          = CURRENT_TIMESTAMP
                WHERE question_id = ?
            ''', (
                p['question_text'], p['question_text'],
                p['choice_a'], p['choice_b'], p['choice_c'], p['choice_d'], p['choice_e'],
                correct,
                p['official_solution'], p['official_solution'],
                row['question_id'],
            ))
            n_updated += 1

            if retag:
                qrow = conn.execute(
                    'SELECT question_text, official_solution FROM amc10_questions WHERE question_id = ?',
                    (row['question_id'],),
                ).fetchone()
                try:
                    reclassify_topic(conn, row['question_id'], dict(qrow))
                    n_retagged += 1
                except Exception as e:
                    # topic re-tag is best-effort
                    print(f'    (topic retag failed for #{num}: {e})')

            if num % 5 == 0:
                print(f'  ✓ {num}/25')
            conn.commit()

    conn.commit()
    conn.close()

    print()
    print('============================================================')
    print(f'  Updated: {n_updated}   Failed: {n_failed}   Re-tagged: {n_retagged}')
    print('============================================================')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--year', type=int, help='Limit rebuild to a single year')
    ap.add_argument('--no-retag', action='store_true', help='Skip topic re-tagging')
    args = ap.parse_args()
    rebuild(only_year=args.year, retag=not args.no_retag)


if __name__ == '__main__':
    main()
