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

        # Use check_same_thread=False to allow multi-threaded access
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
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

        # Question difficulty tags table - per-user difficulty ratings
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS question_difficulty_tags (
                tag_id INTEGER PRIMARY KEY AUTOINCREMENT,
                anki_note_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                difficulty_tag TEXT DEFAULT 'not_attempted',
                total_attempts INTEGER DEFAULT 0,
                correct_attempts INTEGER DEFAULT 0,
                last_attempt_at TEXT,
                last_correct_at TEXT,
                last_wrong_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(anki_note_id, user_id)
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_difficulty_user_tag
            ON question_difficulty_tags(user_id, difficulty_tag)
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
                               is_correct: bool, time_taken: int, active_time_seconds: int = 0) -> int:
        """Record a question attempt."""
        cursor = self.conn.cursor()

        # Get attempt number for this question
        cursor.execute("""
            SELECT COUNT(*) as count FROM question_attempts
            WHERE session_id = ? AND anki_note_id = ?
        """, (session_id, anki_note_id))

        attempt_number = cursor.fetchone()['count'] + 1

        # Insert attempt (with active_time_seconds)
        cursor.execute("""
            INSERT INTO question_attempts
            (session_id, anki_note_id, question_text, correct_answer, user_answer,
             category, is_correct, time_taken_seconds, active_time_seconds, attempt_number, answered_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (session_id, anki_note_id, question_text, correct_answer, user_answer,
              category, 1 if is_correct else 0, time_taken, active_time_seconds, attempt_number, datetime.now().isoformat()))

        attempt_id = cursor.lastrowid

        # Update question performance
        self._update_question_performance(anki_note_id, question_text, category, is_correct, attempt_number == 1)

        # Update difficulty tag for this user
        # Get user_id from session
        cursor.execute("SELECT user_id FROM test_sessions WHERE session_id = ?", (session_id,))
        session = cursor.fetchone()
        if session:
            self._update_difficulty_tag(session['user_id'], anki_note_id, is_correct)

        # Update session totals (correct_answers, wrong_answers, score)
        cursor.execute("""
            UPDATE test_sessions SET
                correct_answers = (SELECT COUNT(*) FROM question_attempts WHERE session_id = ? AND is_correct = 1),
                wrong_answers = (SELECT COUNT(*) FROM question_attempts WHERE session_id = ? AND is_correct = 0),
                score_percentage = ROUND(100.0 *
                    (SELECT COUNT(*) FROM question_attempts WHERE session_id = ? AND is_correct = 1) /
                    NULLIF((SELECT COUNT(*) FROM question_attempts WHERE session_id = ?), 0), 2)
            WHERE session_id = ?
        """, (session_id, session_id, session_id, session_id, session_id))

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

    def get_all_tests(self, user_id: str) -> List[Dict]:
        """Get all test sessions for a user."""
        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT
                session_id,
                pdf_id,
                pdf_filename,
                session_type,
                total_questions,
                correct_answers,
                wrong_answers,
                skipped_answers,
                score_percentage as score,
                time_taken_seconds,
                started_at,
                completed_at,
                status
            FROM test_sessions
            WHERE user_id = ?
            ORDER BY started_at DESC
        """, (user_id,))

        return [dict(row) for row in cursor.fetchall()]

    def get_total_questions_attempted(self, user_id: str) -> int:
        """Get total number of questions attempted by a user."""
        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT COUNT(*) as total FROM question_attempts qa
            JOIN test_sessions ts ON qa.session_id = ts.session_id
            WHERE ts.user_id = ?
        """, (user_id,))

        result = cursor.fetchone()
        return result['total'] if result else 0

    def get_mastery_breakdown(self, user_id: str) -> Dict:
        """Get mastery level breakdown for a user."""
        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT mastery_level, COUNT(*) as count
            FROM question_performance
            GROUP BY mastery_level
        """)

        return {row['mastery_level']: row['count'] for row in cursor.fetchall()}

    # ============== Difficulty Tag Methods ==============

    @staticmethod
    def calculate_difficulty_tag(total_attempts: int, correct_attempts: int) -> str:
        """Calculate difficulty tag based on attempt history.

        Questions start as 'easy' by default and become harder when answered incorrectly.
        - Easy: No attempts yet, OR 100% correct
        - Medium: 60-99% correct
        - Difficult: 30-59% correct
        - Very Difficult: <30% correct (consistently wrong)
        """
        if total_attempts == 0:
            return 'easy'  # New questions start as easy

        accuracy = correct_attempts / total_attempts

        # Easy: 100% correct (never got it wrong)
        if accuracy >= 1.0:
            return 'easy'
        # Medium: Mostly correct (60-99%)
        elif accuracy >= 0.6:
            return 'medium'
        # Difficult: Struggling (30-59%)
        elif accuracy >= 0.3:
            return 'difficult'
        # Very Difficult: Consistently wrong (<30%)
        else:
            return 'very_difficult'

    def _update_difficulty_tag(self, user_id: str, anki_note_id: str, is_correct: bool):
        """Update difficulty tag for a question after an attempt."""
        cursor = self.conn.cursor()
        now = datetime.now().isoformat()

        # Get existing tag record
        cursor.execute("""
            SELECT * FROM question_difficulty_tags
            WHERE user_id = ? AND anki_note_id = ?
        """, (user_id, anki_note_id))

        existing = cursor.fetchone()

        if existing:
            # Update existing record
            total_attempts = existing['total_attempts'] + 1
            correct_attempts = existing['correct_attempts'] + (1 if is_correct else 0)
            new_tag = self.calculate_difficulty_tag(total_attempts, correct_attempts)

            cursor.execute("""
                UPDATE question_difficulty_tags
                SET difficulty_tag = ?,
                    total_attempts = ?,
                    correct_attempts = ?,
                    last_attempt_at = ?,
                    last_correct_at = CASE WHEN ? = 1 THEN ? ELSE last_correct_at END,
                    last_wrong_at = CASE WHEN ? = 0 THEN ? ELSE last_wrong_at END,
                    updated_at = ?
                WHERE user_id = ? AND anki_note_id = ?
            """, (new_tag, total_attempts, correct_attempts, now,
                  1 if is_correct else 0, now,
                  1 if is_correct else 0, now,
                  now, user_id, anki_note_id))
        else:
            # Insert new record
            new_tag = self.calculate_difficulty_tag(1, 1 if is_correct else 0)

            cursor.execute("""
                INSERT INTO question_difficulty_tags
                (anki_note_id, user_id, difficulty_tag, total_attempts, correct_attempts,
                 last_attempt_at, last_correct_at, last_wrong_at)
                VALUES (?, ?, ?, 1, ?, ?, ?, ?)
            """, (anki_note_id, user_id, new_tag,
                  1 if is_correct else 0,
                  now,
                  now if is_correct else None,
                  now if not is_correct else None))

    def get_difficulty_summary(self, user_id: str) -> Dict:
        """Get distribution of questions by difficulty tag for a user."""
        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT difficulty_tag, COUNT(*) as count
            FROM question_difficulty_tags
            WHERE user_id = ?
            GROUP BY difficulty_tag
            ORDER BY CASE difficulty_tag
                WHEN 'easy' THEN 1
                WHEN 'medium' THEN 2
                WHEN 'difficult' THEN 3
                WHEN 'very_difficult' THEN 4
                WHEN 'not_attempted' THEN 5
            END
        """, (user_id,))

        result = {row['difficulty_tag']: row['count'] for row in cursor.fetchall()}

        # Ensure all tags are represented (no longer tracking 'not_attempted' - questions default to 'easy')
        for tag in ['easy', 'medium', 'difficult', 'very_difficult']:
            if tag not in result:
                result[tag] = 0

        # Calculate total (exclude any legacy 'not_attempted' entries)
        result['total'] = result['easy'] + result['medium'] + result['difficult'] + result['very_difficult']

        return result

    def get_questions_by_difficulty(self, user_id: str, difficulty_tag: str,
                                    limit: int = 50) -> List[Dict]:
        """Get questions filtered by difficulty tag."""
        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT
                qdt.anki_note_id,
                qdt.difficulty_tag,
                qdt.total_attempts,
                qdt.correct_attempts,
                qdt.last_attempt_at,
                qp.question_text,
                qp.category,
                CAST(qdt.correct_attempts AS REAL) / qdt.total_attempts * 100 as accuracy
            FROM question_difficulty_tags qdt
            LEFT JOIN question_performance qp ON qdt.anki_note_id = qp.anki_note_id
            WHERE qdt.user_id = ? AND qdt.difficulty_tag = ?
            ORDER BY qdt.last_attempt_at DESC
            LIMIT ?
        """, (user_id, difficulty_tag, limit))

        return [dict(row) for row in cursor.fetchall()]

    def get_difficulty_tag_for_question(self, user_id: str, anki_note_id: str) -> Optional[str]:
        """Get difficulty tag for a specific question and user.

        Returns 'easy' for questions with no attempt history (new questions start easy).
        """
        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT difficulty_tag FROM question_difficulty_tags
            WHERE user_id = ? AND anki_note_id = ?
        """, (user_id, anki_note_id))

        result = cursor.fetchone()
        return result['difficulty_tag'] if result else 'easy'  # New questions default to easy

    def get_today_activity(self, user_id: str) -> Dict:
        """Get today's activity summary for a user (for parent dashboard)."""
        cursor = self.conn.cursor()
        today = datetime.now().strftime('%Y-%m-%d')

        # Tests completed today
        cursor.execute("""
            SELECT
                session_id,
                pdf_filename,
                total_questions,
                correct_answers,
                wrong_answers,
                skipped_answers,
                score_percentage,
                time_taken_seconds,
                started_at,
                completed_at
            FROM test_sessions
            WHERE user_id = ? AND date(started_at) = ? AND status = 'completed'
            ORDER BY started_at DESC
        """, (user_id, today))

        tests = [dict(row) for row in cursor.fetchall()]

        # Calculate totals
        total_questions = sum(t['total_questions'] for t in tests)
        total_correct = sum(t['correct_answers'] for t in tests)
        total_wrong = sum(t['wrong_answers'] for t in tests)

        return {
            'date': today,
            'tests_completed': len(tests),
            'total_questions': total_questions,
            'total_correct': total_correct,
            'total_wrong': total_wrong,
            'accuracy': round((total_correct / total_questions * 100) if total_questions > 0 else 0, 1),
            'tests': tests
        }

    def backfill_difficulty_tags(self, user_id: str) -> int:
        """Backfill difficulty tags from existing question_attempts data."""
        cursor = self.conn.cursor()
        now = datetime.now().isoformat()

        # Get all questions attempted by this user with their stats
        cursor.execute("""
            SELECT
                qa.anki_note_id,
                COUNT(*) as total_attempts,
                SUM(qa.is_correct) as correct_attempts,
                MAX(qa.answered_at) as last_attempt_at,
                MAX(CASE WHEN qa.is_correct = 1 THEN qa.answered_at ELSE NULL END) as last_correct_at,
                MAX(CASE WHEN qa.is_correct = 0 THEN qa.answered_at ELSE NULL END) as last_wrong_at,
                MIN(qa.answered_at) as created_at
            FROM question_attempts qa
            JOIN test_sessions ts ON qa.session_id = ts.session_id
            WHERE ts.user_id = ? AND qa.anki_note_id IS NOT NULL AND qa.anki_note_id != ''
            GROUP BY qa.anki_note_id
        """, (user_id,))

        rows = cursor.fetchall()
        count = 0

        for row in rows:
            total = row['total_attempts']
            correct = row['correct_attempts'] or 0
            tag = self.calculate_difficulty_tag(total, correct)

            cursor.execute("""
                INSERT OR REPLACE INTO question_difficulty_tags
                (anki_note_id, user_id, difficulty_tag, total_attempts, correct_attempts,
                 last_attempt_at, last_correct_at, last_wrong_at, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (row['anki_note_id'], user_id, tag, total, correct,
                  row['last_attempt_at'], row['last_correct_at'], row['last_wrong_at'],
                  row['created_at'], now))
            count += 1

        self.conn.commit()
        return count

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
