#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
math_db.py

Database operations for Math Speed Games module.
Handles all database interactions for questions, sessions, answers, and analytics.
"""

import sqlite3
import json
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import uuid

# Configure logging
logger = logging.getLogger(__name__)


class MathDatabase:
    """Database manager for Math Speed Games."""

    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            db_path = Path(__file__).parent.parent / 'math_tracker.db'

        self.db_path = db_path
        logger.info(f"[MATH_DB] Initializing with path: {self.db_path}")
        logger.info(f"[MATH_DB] DB exists: {Path(self.db_path).exists()}")
        
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()
        
        # Log question count on init
        question_count = self.get_question_count()
        logger.info(f"[MATH_DB] Questions in database: {question_count}")

    def _init_schema(self):
        """Initialize database schema if tables don't exist."""
        cursor = self.conn.cursor()

        # 1. math_questions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS math_questions (
                question_id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT NOT NULL,
                difficulty TEXT NOT NULL,
                question_text TEXT NOT NULL,
                correct_answer TEXT NOT NULL,
                choice_a TEXT NOT NULL,
                choice_b TEXT NOT NULL,
                choice_c TEXT NOT NULL,
                choice_d TEXT NOT NULL,
                correct_choice TEXT NOT NULL,
                explanation TEXT,
                created_at TEXT NOT NULL
            )
        """)

        # 2. math_sessions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS math_sessions (
                session_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                topics TEXT NOT NULL,
                total_questions INTEGER NOT NULL,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                total_time_seconds REAL,
                correct_count INTEGER DEFAULT 0,
                wrong_count INTEGER DEFAULT 0,
                accuracy REAL
            )
        """)

        # 3. math_answers table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS math_answers (
                answer_id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                question_id INTEGER NOT NULL,
                selected_choice TEXT,
                is_correct BOOLEAN NOT NULL,
                time_taken_seconds REAL NOT NULL,
                answered_at TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES math_sessions(session_id),
                FOREIGN KEY (question_id) REFERENCES math_questions(question_id)
            )
        """)

        # 4. math_settings table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS math_settings (
                setting_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                topic TEXT NOT NULL,
                enabled BOOLEAN DEFAULT 1,
                difficulty TEXT DEFAULT 'medium',
                updated_at TEXT NOT NULL,
                UNIQUE(user_id, topic)
            )
        """)

        # 5. math_topic_performance table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS math_topic_performance (
                performance_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                topic TEXT NOT NULL,
                total_attempts INTEGER DEFAULT 0,
                correct_attempts INTEGER DEFAULT 0,
                total_time_seconds REAL DEFAULT 0,
                average_time_per_question REAL,
                accuracy REAL,
                last_practiced TEXT,
                UNIQUE(user_id, topic)
            )
        """)

        self.conn.commit()
        print("✅ Math database schema initialized")

    # ============================================================================
    # QUESTIONS
    # ============================================================================

    def add_question(self, topic: str, difficulty: str, question_text: str,
                    correct_answer: str, choices: Dict[str, str],
                    correct_choice: str, explanation: str = None) -> int:
        """Add a new math question."""
        cursor = self.conn.cursor()

        cursor.execute("""
            INSERT INTO math_questions
            (topic, difficulty, question_text, correct_answer,
             choice_a, choice_b, choice_c, choice_d,
             correct_choice, explanation, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            topic, difficulty, question_text, correct_answer,
            choices['A'], choices['B'], choices['C'], choices['D'],
            correct_choice, explanation, datetime.now().isoformat()
        ))

        self.conn.commit()
        return cursor.lastrowid

    def get_questions(self, topics: List[str], difficulty: str,
                     limit: int = None) -> List[Dict]:
        """Get random questions for specified topics and difficulty."""
        logger.info(f"[MATH_DB] get_questions called: topics={topics}, difficulty={difficulty}, limit={limit}")
        
        cursor = self.conn.cursor()

        # Build query
        placeholders = ','.join(['?' for _ in topics])
        query = f"""
            SELECT * FROM math_questions
            WHERE topic IN ({placeholders})
            AND difficulty = ?
            ORDER BY RANDOM()
        """

        params = topics + [difficulty]

        if limit:
            query += " LIMIT ?"
            params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        result = [dict(row) for row in rows]
        logger.info(f"[MATH_DB] get_questions returned {len(result)} questions")
        
        if len(result) == 0:
            # Log warning with diagnostic info
            total = self.get_question_count()
            by_topic = self.get_questions_by_topic()
            logger.warning(f"[MATH_DB] WARNING: 0 questions returned! Total in DB: {total}, By topic: {by_topic}")

        return result

    def get_question_by_id(self, question_id: int) -> Optional[Dict]:
        """Get a specific question by ID."""
        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT * FROM math_questions WHERE question_id = ?
        """, (question_id,))

        row = cursor.fetchone()
        return dict(row) if row else None

    def count_questions(self, topic: str = None, difficulty: str = None) -> int:
        """Count questions with optional filters."""
        cursor = self.conn.cursor()

        query = "SELECT COUNT(*) as count FROM math_questions WHERE 1=1"
        params = []

        if topic:
            query += " AND topic = ?"
            params.append(topic)

        if difficulty:
            query += " AND difficulty = ?"
            params.append(difficulty)

        cursor.execute(query, params)
        return cursor.fetchone()['count']

    def get_question_count(self) -> int:
        """Get total question count in database."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM math_questions")
        return cursor.fetchone()['count']

    def get_questions_by_topic(self) -> Dict[str, int]:
        """Get question count grouped by topic."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT topic, COUNT(*) as count FROM math_questions GROUP BY topic")
        return {row['topic']: row['count'] for row in cursor.fetchall()}

    # ============================================================================
    # SESSIONS
    # ============================================================================

    def create_session(self, user_id: str, topics: List[str],
                      total_questions: int) -> str:
        """Create a new practice session."""
        logger.info(f"[MATH_SESSION] Creating session for user={user_id}, topics={topics}, questions={total_questions}")
        logger.info(f"[MATH_SESSION] DB path: {self.db_path}")
        
        # Verify questions exist before creating session
        question_count = self.get_question_count()
        logger.info(f"[MATH_SESSION] Questions in DB: {question_count}")
        
        if question_count == 0:
            logger.error(f"[MATH_SESSION] CRITICAL: No questions in database! Cannot create valid session.")
        
        session_id = str(uuid.uuid4())
        cursor = self.conn.cursor()

        cursor.execute("""
            INSERT INTO math_sessions
            (session_id, user_id, topics, total_questions, started_at)
            VALUES (?, ?, ?, ?, ?)
        """, (
            session_id, user_id, json.dumps(topics),
            total_questions, datetime.now().isoformat()
        ))

        self.conn.commit()
        logger.info(f"[MATH_SESSION] Created session_id={session_id}")
        return session_id

    def complete_session(self, session_id: str, total_time_seconds: float,
                        correct_count: int, wrong_count: int):
        """Mark session as complete and update stats."""
        cursor = self.conn.cursor()

        accuracy = (correct_count / (correct_count + wrong_count) * 100) if (correct_count + wrong_count) > 0 else 0

        cursor.execute("""
            UPDATE math_sessions
            SET completed_at = ?,
                total_time_seconds = ?,
                correct_count = ?,
                wrong_count = ?,
                accuracy = ?
            WHERE session_id = ?
        """, (
            datetime.now().isoformat(),
            total_time_seconds,
            correct_count,
            wrong_count,
            accuracy,
            session_id
        ))

        self.conn.commit()

    def get_session(self, session_id: str) -> Optional[Dict]:
        """Get session details."""
        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT * FROM math_sessions WHERE session_id = ?
        """, (session_id,))

        row = cursor.fetchone()
        if row:
            session = dict(row)
            session['topics'] = json.loads(session['topics'])
            return session
        return None

    def get_user_sessions(self, user_id: str, limit: int = 10) -> List[Dict]:
        """Get recent sessions for a user."""
        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT * FROM math_sessions
            WHERE user_id = ?
            ORDER BY started_at DESC
            LIMIT ?
        """, (user_id, limit))

        rows = cursor.fetchall()
        sessions = []
        for row in rows:
            session = dict(row)
            session['topics'] = json.loads(session['topics'])
            sessions.append(session)

        return sessions

    # ============================================================================
    # ANSWERS
    # ============================================================================

    def record_answer(self, session_id: str, question_id: int,
                     selected_choice: Optional[str], is_correct: bool,
                     time_taken_seconds: float) -> int:
        """Record a question answer."""
        cursor = self.conn.cursor()

        cursor.execute("""
            INSERT INTO math_answers
            (session_id, question_id, selected_choice, is_correct,
             time_taken_seconds, answered_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            session_id, question_id, selected_choice, is_correct,
            time_taken_seconds, datetime.now().isoformat()
        ))

        self.conn.commit()
        return cursor.lastrowid

    def get_session_answers(self, session_id: str) -> List[Dict]:
        """Get all answers for a session with question details."""
        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT
                a.*,
                q.topic,
                q.question_text,
                q.correct_answer,
                q.difficulty
            FROM math_answers a
            JOIN math_questions q ON a.question_id = q.question_id
            WHERE a.session_id = ?
            ORDER BY a.answered_at
        """, (session_id,))

        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    # ============================================================================
    # SETTINGS
    # ============================================================================

    def get_settings(self, user_id: str) -> List[Dict]:
        """Get all topic settings for a user."""
        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT * FROM math_settings
            WHERE user_id = ?
            ORDER BY topic
        """, (user_id,))

        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def get_topic_setting(self, user_id: str, topic: str) -> Optional[Dict]:
        """Get setting for a specific topic."""
        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT * FROM math_settings
            WHERE user_id = ? AND topic = ?
        """, (user_id, topic))

        row = cursor.fetchone()
        return dict(row) if row else None

    def update_setting(self, user_id: str, topic: str,
                      enabled: bool = None, difficulty: str = None):
        """Update or create topic setting."""
        cursor = self.conn.cursor()

        # Check if setting exists
        existing = self.get_topic_setting(user_id, topic)

        if existing:
            # Update existing
            updates = []
            params = []

            if enabled is not None:
                updates.append("enabled = ?")
                params.append(enabled)

            if difficulty is not None:
                updates.append("difficulty = ?")
                params.append(difficulty)

            updates.append("updated_at = ?")
            params.append(datetime.now().isoformat())

            params.extend([user_id, topic])

            cursor.execute(f"""
                UPDATE math_settings
                SET {', '.join(updates)}
                WHERE user_id = ? AND topic = ?
            """, params)
        else:
            # Create new
            cursor.execute("""
                INSERT INTO math_settings
                (user_id, topic, enabled, difficulty, updated_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                user_id, topic,
                enabled if enabled is not None else True,
                difficulty if difficulty is not None else 'medium',
                datetime.now().isoformat()
            ))

        self.conn.commit()

    def get_enabled_topics(self, user_id: str) -> List[str]:
        """Get list of enabled topics for a user."""
        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT topic FROM math_settings
            WHERE user_id = ? AND enabled = 1
            ORDER BY topic
        """, (user_id,))

        rows = cursor.fetchall()
        return [row['topic'] for row in rows]

    # ============================================================================
    # PERFORMANCE ANALYTICS
    # ============================================================================

    def update_topic_performance(self, user_id: str, topic: str,
                                correct: bool, time_taken: float):
        """Update performance stats for a topic."""
        cursor = self.conn.cursor()

        # Get existing performance
        cursor.execute("""
            SELECT * FROM math_topic_performance
            WHERE user_id = ? AND topic = ?
        """, (user_id, topic))

        existing = cursor.fetchone()

        if existing:
            # Update existing
            new_total_attempts = existing['total_attempts'] + 1
            new_correct_attempts = existing['correct_attempts'] + (1 if correct else 0)
            new_total_time = existing['total_time_seconds'] + time_taken
            new_avg_time = new_total_time / new_total_attempts
            new_accuracy = (new_correct_attempts / new_total_attempts) * 100

            cursor.execute("""
                UPDATE math_topic_performance
                SET total_attempts = ?,
                    correct_attempts = ?,
                    total_time_seconds = ?,
                    average_time_per_question = ?,
                    accuracy = ?,
                    last_practiced = ?
                WHERE user_id = ? AND topic = ?
            """, (
                new_total_attempts, new_correct_attempts, new_total_time,
                new_avg_time, new_accuracy, datetime.now().isoformat(),
                user_id, topic
            ))
        else:
            # Create new
            accuracy = 100.0 if correct else 0.0

            cursor.execute("""
                INSERT INTO math_topic_performance
                (user_id, topic, total_attempts, correct_attempts,
                 total_time_seconds, average_time_per_question,
                 accuracy, last_practiced)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id, topic, 1, 1 if correct else 0,
                time_taken, time_taken, accuracy,
                datetime.now().isoformat()
            ))

        self.conn.commit()

    def get_topic_performance(self, user_id: str, topic: str = None) -> List[Dict]:
        """Get performance stats for topics."""
        cursor = self.conn.cursor()

        if topic:
            cursor.execute("""
                SELECT * FROM math_topic_performance
                WHERE user_id = ? AND topic = ?
            """, (user_id, topic))
        else:
            cursor.execute("""
                SELECT * FROM math_topic_performance
                WHERE user_id = ?
                ORDER BY topic
            """, (user_id,))

        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def get_overall_performance(self, user_id: str) -> Dict:
        """Get overall performance summary."""
        cursor = self.conn.cursor()

        # Total sessions
        cursor.execute("""
            SELECT COUNT(*) as count FROM math_sessions
            WHERE user_id = ? AND completed_at IS NOT NULL
        """, (user_id,))
        total_sessions = cursor.fetchone()['count']

        # Total questions
        cursor.execute("""
            SELECT
                COUNT(*) as total_questions,
                SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END) as correct,
                AVG(time_taken_seconds) as avg_time
            FROM math_answers
            WHERE session_id IN (
                SELECT session_id FROM math_sessions WHERE user_id = ?
            )
        """, (user_id,))

        stats = cursor.fetchone()

        if stats and stats['total_questions']:
            return {
                'total_sessions': total_sessions,
                'total_questions': stats['total_questions'],
                'correct_count': stats['correct'] or 0,
                'accuracy': (stats['correct'] / stats['total_questions'] * 100) if stats['total_questions'] > 0 else 0,
                'average_time': stats['avg_time'] or 0
            }
        else:
            return {
                'total_sessions': 0,
                'total_questions': 0,
                'correct_count': 0,
                'accuracy': 0,
                'average_time': 0
            }

    def get_database_stats(self) -> Dict:
        """Get overall database statistics."""
        cursor = self.conn.cursor()
        
        # Total questions
        cursor.execute("SELECT COUNT(*) as total FROM math_questions")
        total_questions = cursor.fetchone()['total']
        
        # Questions by topic
        cursor.execute("""
            SELECT topic, COUNT(*) as count
            FROM math_questions
            GROUP BY topic
            ORDER BY topic
        """)
        by_topic = {row['topic']: row['count'] for row in cursor.fetchall()}
        
        # Questions by difficulty
        cursor.execute("""
            SELECT difficulty, COUNT(*) as count
            FROM math_questions
            GROUP BY difficulty
            ORDER BY difficulty
        """)
        by_difficulty = {row['difficulty']: row['count'] for row in cursor.fetchall()}
        
        return {
            'total_questions': total_questions,
            'by_topic': by_topic,
            'by_difficulty': by_difficulty
        }

    def close(self):
        """Close database connection."""
        self.conn.close()


def main():
    """Test database operations."""
    print("\n" + "="*60)
    print("Math Database - Test Operations")
    print("="*60 + "\n")

    db = MathDatabase()

    # Show counts
    print(f"Total questions in database: {db.count_questions()}")

    # Show counts by topic
    topics = ['arithmetic', 'fractions', 'decimals', 'equations', 'profit_loss', 'bodmas']
    print("\nQuestions by topic:")
    for topic in topics:
        count = db.count_questions(topic=topic)
        print(f"  {topic}: {count}")

    print("\n" + "="*60)
    db.close()


if __name__ == '__main__':
    main()
