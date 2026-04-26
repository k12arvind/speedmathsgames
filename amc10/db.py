"""SQLite storage for the AMC 10 question bank."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Dict, Iterable, Optional


class AMC10Database:
    """Stores parsed AMC 10 contests, questions, and topic tags."""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = str(Path.home() / "clat_preparation" / "amc10_practice.db")
        self.db_path = db_path
        self._init_tables()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_tables(self) -> None:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS amc10_contests (
                    contest_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    year INTEGER NOT NULL,
                    season TEXT,
                    contest_code TEXT,
                    contest_label TEXT NOT NULL UNIQUE,
                    problems_pdf_path TEXT NOT NULL,
                    solutions_pdf_path TEXT NOT NULL,
                    import_status TEXT DEFAULT 'pending',
                    question_count INTEGER DEFAULT 0,
                    imported_at TEXT,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS amc10_questions (
                    question_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    contest_id INTEGER NOT NULL REFERENCES amc10_contests(contest_id) ON DELETE CASCADE,
                    problem_number INTEGER NOT NULL,
                    question_text TEXT NOT NULL,
                    question_text_raw TEXT,
                    choice_a TEXT,
                    choice_b TEXT,
                    choice_c TEXT,
                    choice_d TEXT,
                    choice_e TEXT,
                    correct_choice TEXT,
                    official_solution TEXT,
                    official_solution_raw TEXT,
                    problem_page_start INTEGER,
                    problem_page_end INTEGER,
                    solution_page_start INTEGER,
                    solution_page_end INTEGER,
                    parse_status TEXT DEFAULT 'parsed',
                    parse_notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(contest_id, problem_number)
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS amc10_question_topics (
                    tag_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    question_id INTEGER NOT NULL REFERENCES amc10_questions(question_id) ON DELETE CASCADE,
                    topic_code TEXT NOT NULL,
                    topic_name TEXT NOT NULL,
                    subtopic_code TEXT,
                    subtopic_name TEXT,
                    confidence REAL,
                    reasoning TEXT,
                    tag_source TEXT NOT NULL,
                    is_primary INTEGER DEFAULT 1,
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_amc10_questions_contest ON amc10_questions(contest_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_amc10_question_topics_question ON amc10_question_topics(question_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_amc10_question_topics_topic ON amc10_question_topics(topic_code, subtopic_code)")
            conn.commit()
        finally:
            conn.close()

    def upsert_contest(self, metadata: Dict[str, object]) -> int:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO amc10_contests (
                    year, season, contest_code, contest_label,
                    problems_pdf_path, solutions_pdf_path, import_status, question_count, imported_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(contest_label) DO UPDATE SET
                    year = excluded.year,
                    season = excluded.season,
                    contest_code = excluded.contest_code,
                    problems_pdf_path = excluded.problems_pdf_path,
                    solutions_pdf_path = excluded.solutions_pdf_path,
                    import_status = excluded.import_status,
                    question_count = excluded.question_count,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    metadata["year"],
                    metadata.get("season"),
                    metadata.get("contest_code"),
                    metadata["contest_label"],
                    metadata["problems_pdf_path"],
                    metadata["solutions_pdf_path"],
                    metadata.get("import_status", "parsed"),
                    metadata.get("question_count", 0),
                ),
            )
            conn.commit()
            cursor.execute("SELECT contest_id FROM amc10_contests WHERE contest_label = ?", (metadata["contest_label"],))
            return int(cursor.fetchone()["contest_id"])
        finally:
            conn.close()

    def replace_contest_questions(self, contest_id: int, questions: Iterable[Dict[str, object]]) -> None:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM amc10_questions WHERE contest_id = ?", (contest_id,))
            for question in questions:
                cursor.execute(
                    """
                    INSERT INTO amc10_questions (
                        contest_id, problem_number, question_text, question_text_raw,
                        choice_a, choice_b, choice_c, choice_d, choice_e, correct_choice,
                        official_solution, official_solution_raw,
                        problem_page_start, problem_page_end, solution_page_start, solution_page_end,
                        parse_status, parse_notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        contest_id,
                        question["problem_number"],
                        question["question_text"],
                        question.get("question_text_raw"),
                        question.get("choice_a"),
                        question.get("choice_b"),
                        question.get("choice_c"),
                        question.get("choice_d"),
                        question.get("choice_e"),
                        question.get("correct_choice"),
                        question.get("official_solution"),
                        question.get("official_solution_raw"),
                        question.get("problem_page_start"),
                        question.get("problem_page_end"),
                        question.get("solution_page_start"),
                        question.get("solution_page_end"),
                        question.get("parse_status", "parsed"),
                        question.get("parse_notes"),
                    ),
                )
            cursor.execute(
                """
                UPDATE amc10_contests
                SET question_count = ?, import_status = 'parsed', imported_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                WHERE contest_id = ?
                """,
                (len(list(questions)) if not isinstance(questions, list) else len(questions), contest_id),
            )
            conn.commit()
        finally:
            conn.close()

    def replace_auto_tags(self, contest_id: int, topic_rows: Iterable[Dict[str, object]]) -> None:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                DELETE FROM amc10_question_topics
                WHERE tag_source = 'auto'
                  AND question_id IN (
                      SELECT question_id FROM amc10_questions WHERE contest_id = ?
                  )
                """,
                (contest_id,),
            )
            for row in topic_rows:
                cursor.execute(
                    """
                    INSERT INTO amc10_question_topics (
                        question_id, topic_code, topic_name, subtopic_code, subtopic_name,
                        confidence, reasoning, tag_source, is_primary, is_active
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 'auto', 1, 1)
                    """,
                    (
                        row["question_id"],
                        row["topic_code"],
                        row["topic_name"],
                        row.get("subtopic_code"),
                        row.get("subtopic_name"),
                        row.get("confidence"),
                        row.get("reasoning"),
                    ),
                )
            conn.commit()
        finally:
            conn.close()

    def set_manual_override(
        self,
        question_id: int,
        topic_code: str,
        topic_name: str,
        subtopic_code: Optional[str] = None,
        subtopic_name: Optional[str] = None,
        reasoning: Optional[str] = None,
    ) -> None:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("UPDATE amc10_question_topics SET is_active = 0 WHERE question_id = ?", (question_id,))
            cursor.execute(
                """
                INSERT INTO amc10_question_topics (
                    question_id, topic_code, topic_name, subtopic_code, subtopic_name,
                    confidence, reasoning, tag_source, is_primary, is_active
                ) VALUES (?, ?, ?, ?, ?, 1.0, ?, 'manual', 1, 1)
                """,
                (question_id, topic_code, topic_name, subtopic_code, subtopic_name, reasoning),
            )
            conn.commit()
        finally:
            conn.close()

