#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
assessment_database.py

Database schema and management for the assessment/testing engine.
Tracks test sessions, question attempts, and performance analytics.
"""

import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import json


class AssessmentDatabase:
    """Manages assessment and test tracking database."""

    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            db_path = Path(__file__).parent / "assessment_tracker.db"

        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self._init_database()

    def _init_database(self):
        """Create assessment database schema."""
        cursor = self.conn.cursor()

        # Test sessions table - tracks each test attempt
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS test_sessions (
                session_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                pdf_id TEXT NOT NULL,
                pdf_filename TEXT NOT NULL,
                source_date TEXT NOT NULL,
                session_type TEXT NOT NULL,  -- 'full', 'quick', 'weak_topics'
                total_questions INTEGER NOT NULL,
                correct_answers INTEGER DEFAULT 0,
                wrong_answers INTEGER DEFAULT 0,
                skipped_answers INTEGER DEFAULT 0,
                score_percentage REAL DEFAULT 0,
                time_taken_seconds INTEGER DEFAULT 0,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                status TEXT DEFAULT 'in_progress',  -- 'in_progress', 'completed', 'abandoned'
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Question attempts table - tracks each question answer
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS question_attempts (
                attempt_id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                anki_note_id TEXT NOT NULL,
                question_text TEXT NOT NULL,
                correct_answer TEXT NOT NULL,
                user_answer TEXT,
                category TEXT NOT NULL,
                is_correct INTEGER DEFAULT 0,  -- 0 or 1
                time_taken_seconds INTEGER DEFAULT 0,
                attempt_number INTEGER DEFAULT 1,
                answered_at TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES test_sessions(session_id) ON DELETE CASCADE
            )
        """)

        # Question performance table - aggregated stats per question
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS question_performance (
                performance_id INTEGER PRIMARY KEY AUTOINCREMENT,
                anki_note_id TEXT UNIQUE NOT NULL,
                question_text TEXT NOT NULL,
                category TEXT NOT NULL,
                total_attempts INTEGER DEFAULT 0,
                correct_attempts INTEGER DEFAULT 0,
                wrong_attempts INTEGER DEFAULT 0,
                first_attempt_correct INTEGER DEFAULT 0,  -- First time correct?
                last_attempt_correct INTEGER DEFAULT 0,
                last_attempted_at TEXT,
                mastery_level TEXT DEFAULT 'not_started',  -- 'not_started', 'learning', 'reviewing', 'mastered'
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # User performance by PDF
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pdf_performance (
                performance_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                pdf_id TEXT NOT NULL,
                total_tests INTEGER DEFAULT 0,
                best_score REAL DEFAULT 0,
                average_score REAL DEFAULT 0,
                last_test_date TEXT,
                total_questions_attempted INTEGER DEFAULT 0,
                mastered_questions INTEGER DEFAULT 0,
                weak_questions INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, pdf_id)
            )
        """)

        # Category performance tracking
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS category_performance (
                performance_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                category TEXT NOT NULL,
                total_questions INTEGER DEFAULT 0,
                correct_answers INTEGER DEFAULT 0,
                wrong_answers INTEGER DEFAULT 0,
                accuracy_percentage REAL DEFAULT 0,
                last_practiced_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, category)
            )
        """)

        # Weak questions tracking - questions answered incorrectly multiple times
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS weak_questions (
                weak_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                anki_note_id TEXT NOT NULL,
                question_text TEXT NOT NULL,
                category TEXT NOT NULL,
                times_wrong INTEGER DEFAULT 1,
                last_wrong_at TEXT NOT NULL,
                needs_review INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, anki_note_id)
            )
        """)

        # Create indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_test_sessions_user
            ON test_sessions(user_id, pdf_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_question_attempts_session
            ON question_attempts(session_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_question_performance_note
            ON question_performance(anki_note_id)
        """)

        self.conn.commit()

    def create_test_session(self, user_id: str, pdf_id: str, pdf_filename: str,
                           source_date: str, session_type: str, total_questions: int) -> int:
        """Create a new test session."""
        cursor = self.conn.cursor()

        cursor.execute("""
            INSERT INTO test_sessions
            (user_id, pdf_id, pdf_filename, source_date, session_type, total_questions, started_at, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'in_progress')
        """, (user_id, pdf_id, pdf_filename, source_date, session_type, total_questions, datetime.now().isoformat()))

        self.conn.commit()
        return cursor.lastrowid

    def record_question_attempt(self, session_id: int, anki_note_id: str, question_text: str,
                               correct_answer: str, user_answer: str, category: str,
                               is_correct: bool, time_taken: int) -> int:
        """Record a question attempt."""
        cursor = self.conn.cursor()

        # Get attempt number for this question
        cursor.execute("""
            SELECT COUNT(*) as count FROM question_attempts
            WHERE session_id = ? AND anki_note_id = ?
        """, (session_id, anki_note_id))

        attempt_number = cursor.fetchone()['count'] + 1

        # Insert attempt
        cursor.execute("""
            INSERT INTO question_attempts
            (session_id, anki_note_id, question_text, correct_answer, user_answer,
             category, is_correct, time_taken_seconds, attempt_number, answered_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (session_id, anki_note_id, question_text, correct_answer, user_answer,
              category, 1 if is_correct else 0, time_taken, attempt_number, datetime.now().isoformat()))

        attempt_id = cursor.lastrowid

        # Update question performance
        self._update_question_performance(anki_note_id, question_text, category, is_correct, attempt_number == 1)

        self.conn.commit()
        return attempt_id

    def _update_question_performance(self, anki_note_id: str, question_text: str,
                                    category: str, is_correct: bool, is_first_attempt: bool):
        """Update aggregated question performance stats."""
        cursor = self.conn.cursor()

        now = datetime.now().isoformat()

        cursor.execute("""
            SELECT * FROM question_performance WHERE anki_note_id = ?
        """, (anki_note_id,))

        existing = cursor.fetchone()

        if existing:
            # Update existing
            total_attempts = existing['total_attempts'] + 1
            correct_attempts = existing['correct_attempts'] + (1 if is_correct else 0)
            wrong_attempts = existing['wrong_attempts'] + (0 if is_correct else 1)

            # Update mastery level
            accuracy = (correct_attempts / total_attempts) * 100
            if accuracy >= 90 and total_attempts >= 3:
                mastery_level = 'mastered'
            elif accuracy >= 70:
                mastery_level = 'reviewing'
            elif accuracy >= 50:
                mastery_level = 'learning'
            else:
                mastery_level = 'not_started'

            cursor.execute("""
                UPDATE question_performance
                SET total_attempts = ?,
                    correct_attempts = ?,
                    wrong_attempts = ?,
                    last_attempt_correct = ?,
                    last_attempted_at = ?,
                    mastery_level = ?,
                    updated_at = ?
                WHERE anki_note_id = ?
            """, (total_attempts, correct_attempts, wrong_attempts, 1 if is_correct else 0,
                  now, mastery_level, now, anki_note_id))
        else:
            # Insert new
            cursor.execute("""
                INSERT INTO question_performance
                (anki_note_id, question_text, category, total_attempts, correct_attempts,
                 wrong_attempts, first_attempt_correct, last_attempt_correct, last_attempted_at, mastery_level)
                VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?, 'learning')
            """, (anki_note_id, question_text, category,
                  1 if is_correct else 0,
                  0 if is_correct else 1,
                  1 if (is_first_attempt and is_correct) else 0,
                  1 if is_correct else 0,
                  now))

    def complete_test_session(self, session_id: int):
        """Mark test session as completed and calculate stats."""
        cursor = self.conn.cursor()

        # Get session info
        cursor.execute("""
            SELECT * FROM test_sessions WHERE session_id = ?
        """, (session_id,))

        session = cursor.fetchone()

        if not session:
            return

        # Count answers
        cursor.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END) as correct,
                SUM(CASE WHEN is_correct = 0 AND user_answer IS NOT NULL THEN 1 ELSE 0 END) as wrong,
                SUM(CASE WHEN user_answer IS NULL THEN 1 ELSE 0 END) as skipped,
                SUM(time_taken_seconds) as total_time
            FROM question_attempts
            WHERE session_id = ?
        """, (session_id,))

        stats = cursor.fetchone()

        correct = stats['correct'] or 0
        wrong = stats['wrong'] or 0
        skipped = stats['skipped'] or 0
        total_time = stats['total_time'] or 0

        score_percentage = (correct / session['total_questions']) * 100 if session['total_questions'] > 0 else 0

        # Update session
        cursor.execute("""
            UPDATE test_sessions
            SET correct_answers = ?,
                wrong_answers = ?,
                skipped_answers = ?,
                score_percentage = ?,
                time_taken_seconds = ?,
                completed_at = ?,
                status = 'completed'
            WHERE session_id = ?
        """, (correct, wrong, skipped, score_percentage, total_time, datetime.now().isoformat(), session_id))

        # Update PDF performance
        self._update_pdf_performance(session['user_id'], session['pdf_id'], score_percentage)

        self.conn.commit()

    def _update_pdf_performance(self, user_id: str, pdf_id: str, score: float):
        """Update PDF performance stats."""
        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT * FROM pdf_performance WHERE user_id = ? AND pdf_id = ?
        """, (user_id, pdf_id))

        existing = cursor.fetchone()
        now = datetime.now().isoformat()

        if existing:
            total_tests = existing['total_tests'] + 1
            best_score = max(existing['best_score'], score)
            average_score = ((existing['average_score'] * existing['total_tests']) + score) / total_tests

            cursor.execute("""
                UPDATE pdf_performance
                SET total_tests = ?,
                    best_score = ?,
                    average_score = ?,
                    last_test_date = ?,
                    updated_at = ?
                WHERE user_id = ? AND pdf_id = ?
            """, (total_tests, best_score, average_score, now, now, user_id, pdf_id))
        else:
            cursor.execute("""
                INSERT INTO pdf_performance
                (user_id, pdf_id, total_tests, best_score, average_score, last_test_date)
                VALUES (?, ?, 1, ?, ?, ?)
            """, (user_id, pdf_id, score, score, now))

    def get_user_performance_summary(self, user_id: str) -> Dict:
        """Get overall performance summary for a user."""
        cursor = self.conn.cursor()

        # Total tests
        cursor.execute("""
            SELECT COUNT(*) as total FROM test_sessions
            WHERE user_id = ? AND status = 'completed'
        """, (user_id,))
        total_tests = cursor.fetchone()['total']

        # Average score
        cursor.execute("""
            SELECT AVG(score_percentage) as avg_score FROM test_sessions
            WHERE user_id = ? AND status = 'completed'
        """, (user_id,))
        avg_score = cursor.fetchone()['avg_score'] or 0

        # Questions attempted
        cursor.execute("""
            SELECT COUNT(*) as total FROM question_attempts qa
            JOIN test_sessions ts ON qa.session_id = ts.session_id
            WHERE ts.user_id = ?
        """, (user_id,))
        total_questions = cursor.fetchone()['total']

        # Mastery breakdown
        cursor.execute("""
            SELECT mastery_level, COUNT(*) as count
            FROM question_performance
            GROUP BY mastery_level
        """)
        mastery = {row['mastery_level']: row['count'] for row in cursor.fetchall()}

        return {
            'total_tests': total_tests,
            'average_score': round(avg_score, 1),
            'total_questions_attempted': total_questions,
            'mastery_breakdown': mastery
        }

    def get_weak_questions(self, user_id: str, limit: int = 20) -> List[Dict]:
        """Get questions that need more practice."""
        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT
                qp.anki_note_id,
                qp.question_text,
                qp.category,
                qp.total_attempts,
                qp.correct_attempts,
                qp.wrong_attempts,
                qp.mastery_level,
                CAST(qp.correct_attempts AS REAL) / qp.total_attempts * 100 as accuracy
            FROM question_performance qp
            WHERE qp.total_attempts >= 2
              AND CAST(qp.correct_attempts AS REAL) / qp.total_attempts < 0.7
            ORDER BY qp.wrong_attempts DESC, accuracy ASC
            LIMIT ?
        """, (limit,))

        return [dict(row) for row in cursor.fetchall()]

    def close(self):
        """Close database connection."""
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


if __name__ == '__main__':
    # Test database creation
    db = AssessmentDatabase()
    print(f"✅ Assessment database created at: {db.db_path}")
    print(f"📊 Tables: test_sessions, question_attempts, question_performance, pdf_performance, category_performance, weak_questions")
    db.close()
