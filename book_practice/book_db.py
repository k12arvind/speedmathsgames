"""
Book Practice Database Module
Handles CRUD operations for RS Aggarwal book questions, topics, sessions, and mastery tracking
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Any, Tuple
import random


class BookPracticeDB:
    """Database handler for book practice questions and sessions"""

    # Default RS Aggarwal topics (will be populated from the book)
    DEFAULT_TOPICS = [
        {'name': 'Number Series', 'chapter_number': 1},
        {'name': 'Letter Series', 'chapter_number': 2},
        {'name': 'Coding-Decoding', 'chapter_number': 3},
        {'name': 'Blood Relations', 'chapter_number': 4},
        {'name': 'Analogy', 'chapter_number': 5},
        {'name': 'Classification', 'chapter_number': 6},
        {'name': 'Direction Sense', 'chapter_number': 7},
        {'name': 'Logical Sequence of Words', 'chapter_number': 8},
        {'name': 'Arithmetical Reasoning', 'chapter_number': 9},
        {'name': 'Number, Ranking & Time Sequence', 'chapter_number': 10},
        {'name': 'Mathematical Operations', 'chapter_number': 11},
        {'name': 'Inserting Missing Character', 'chapter_number': 12},
        {'name': 'Data Sufficiency', 'chapter_number': 13},
        {'name': 'Logic', 'chapter_number': 14},
        {'name': 'Statement - Arguments', 'chapter_number': 15},
        {'name': 'Statement - Assumptions', 'chapter_number': 16},
        {'name': 'Statement - Courses of Action', 'chapter_number': 17},
        {'name': 'Statement - Conclusions', 'chapter_number': 18},
        {'name': 'Deriving Conclusions from Passages', 'chapter_number': 19},
        {'name': 'Theme Detection', 'chapter_number': 20},
        {'name': 'Alligation or Mixture', 'chapter_number': 21},
        {'name': 'Average', 'chapter_number': 22},
        {'name': 'Percentage', 'chapter_number': 23},
        {'name': 'Profit and Loss', 'chapter_number': 24},
        {'name': 'Ratio and Proportion', 'chapter_number': 25},
        {'name': 'Partnership', 'chapter_number': 26},
        {'name': 'Chain Rule', 'chapter_number': 27},
        {'name': 'Time and Work', 'chapter_number': 28},
        {'name': 'Pipes and Cisterns', 'chapter_number': 29},
        {'name': 'Time and Distance', 'chapter_number': 30},
        {'name': 'Boats and Streams', 'chapter_number': 31},
        {'name': 'Problems on Trains', 'chapter_number': 32},
        {'name': 'Simple Interest', 'chapter_number': 33},
        {'name': 'Compound Interest', 'chapter_number': 34},
        {'name': 'Permutation and Combination', 'chapter_number': 35},
        {'name': 'Probability', 'chapter_number': 36},
        {'name': 'Area', 'chapter_number': 37},
        {'name': 'Volume and Surface Area', 'chapter_number': 38},
        {'name': 'Races and Games of Skill', 'chapter_number': 39},
    ]

    # Spaced repetition intervals (in days)
    SPACED_INTERVALS = [1, 3, 7, 14, 30, 60]

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = Path.home() / "clat_preparation" / "book_practice.db"
        self.db_path = str(db_path)
        self._init_tables()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        # Enable foreign keys
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_tables(self):
        """Initialize all book practice tables"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            # Topics from the book
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS book_topics (
                    topic_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    topic_name TEXT NOT NULL UNIQUE,
                    chapter_number INTEGER,
                    page_range TEXT,
                    total_questions INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Uploaded page images
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS uploaded_pages (
                    page_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    topic_id INTEGER REFERENCES book_topics(topic_id),
                    image_path TEXT NOT NULL,
                    page_number INTEGER,
                    is_answer_key BOOLEAN DEFAULT FALSE,
                    extraction_status TEXT DEFAULT 'pending',
                    extracted_data TEXT,
                    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Extracted questions
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS book_questions (
                    question_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    topic_id INTEGER REFERENCES book_topics(topic_id),
                    page_id INTEGER REFERENCES uploaded_pages(page_id),
                    question_number INTEGER,
                    question_text TEXT NOT NULL,
                    choice_a TEXT,
                    choice_b TEXT,
                    choice_c TEXT,
                    choice_d TEXT,
                    choice_e TEXT,
                    correct_choice TEXT,
                    difficulty TEXT DEFAULT 'difficult',
                    source_exam TEXT,
                    is_verified BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Practice sessions
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS practice_sessions (
                    session_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    selected_topics TEXT,
                    question_count INTEGER,
                    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    total_correct INTEGER DEFAULT 0,
                    total_attempted INTEGER DEFAULT 0
                )
            """)

            # Individual question attempts
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS question_attempts (
                    attempt_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER REFERENCES practice_sessions(session_id),
                    question_id INTEGER REFERENCES book_questions(question_id),
                    user_id TEXT NOT NULL,
                    selected_choice TEXT,
                    is_correct BOOLEAN,
                    time_taken_seconds INTEGER,
                    attempt_number INTEGER,
                    notes TEXT,
                    attempted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Aggregated question mastery
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS question_mastery (
                    mastery_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    question_id INTEGER UNIQUE REFERENCES book_questions(question_id),
                    user_id TEXT NOT NULL,
                    total_attempts INTEGER DEFAULT 0,
                    correct_attempts INTEGER DEFAULT 0,
                    accuracy REAL DEFAULT 0.0,
                    average_time_seconds REAL,
                    best_time_seconds INTEGER,
                    last_attempted TIMESTAMP,
                    mastery_level TEXT DEFAULT 'new',
                    next_review_date DATE,
                    spaced_interval_index INTEGER DEFAULT 0
                )
            """)

            # Create indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_questions_topic ON book_questions(topic_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_attempts_session ON question_attempts(session_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_attempts_question ON question_attempts(question_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_attempts_user ON question_attempts(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_mastery_user ON question_mastery(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_mastery_level ON question_mastery(mastery_level)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_pages_topic ON uploaded_pages(topic_id)")

            # Insert default topics if empty
            cursor.execute("SELECT COUNT(*) FROM book_topics")
            if cursor.fetchone()[0] == 0:
                for topic in self.DEFAULT_TOPICS:
                    cursor.execute("""
                        INSERT INTO book_topics (topic_name, chapter_number)
                        VALUES (?, ?)
                    """, (topic['name'], topic['chapter_number']))

            conn.commit()
        finally:
            conn.close()

    # ============================================================
    # TOPIC OPERATIONS
    # ============================================================

    def get_topics(self) -> List[Dict]:
        """Get all topics with question counts"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT t.*,
                       COUNT(DISTINCT q.question_id) as question_count,
                       SUM(CASE WHEN q.is_verified = 1 THEN 1 ELSE 0 END) as verified_count
                FROM book_topics t
                LEFT JOIN book_questions q ON t.topic_id = q.topic_id
                GROUP BY t.topic_id
                ORDER BY t.chapter_number
            """)
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_topic(self, topic_id: int) -> Optional[Dict]:
        """Get a single topic by ID"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM book_topics WHERE topic_id = ?
            """, (topic_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def add_topic(self, name: str, chapter_number: int = None, page_range: str = None) -> int:
        """Add a new topic"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO book_topics (topic_name, chapter_number, page_range)
                VALUES (?, ?, ?)
            """, (name, chapter_number, page_range))
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def update_topic(self, topic_id: int, **kwargs) -> bool:
        """Update topic properties"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            fields = []
            values = []
            for key, value in kwargs.items():
                if key in ['topic_name', 'chapter_number', 'page_range']:
                    fields.append(f"{key} = ?")
                    values.append(value)
            if not fields:
                return False
            values.append(topic_id)
            cursor.execute(f"""
                UPDATE book_topics SET {', '.join(fields)}
                WHERE topic_id = ?
            """, values)
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def delete_topic(self, topic_id: int) -> bool:
        """Delete a topic and all its associated questions"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            # Delete associated questions first
            cursor.execute("DELETE FROM book_questions WHERE topic_id = ?", (topic_id,))
            # Delete uploaded pages
            cursor.execute("DELETE FROM uploaded_pages WHERE topic_id = ?", (topic_id,))
            # Delete the topic
            cursor.execute("DELETE FROM book_topics WHERE topic_id = ?", (topic_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    # ============================================================
    # PAGE UPLOAD OPERATIONS
    # ============================================================

    def add_uploaded_page(self, topic_id: int, image_path: str, page_number: int = None,
                          is_answer_key: bool = False) -> int:
        """Record an uploaded page image"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO uploaded_pages (topic_id, image_path, page_number, is_answer_key)
                VALUES (?, ?, ?, ?)
            """, (topic_id, image_path, page_number, is_answer_key))
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def update_page_extraction(self, page_id: int, status: str, extracted_data: str = None) -> bool:
        """Update extraction status for a page"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE uploaded_pages
                SET extraction_status = ?, extracted_data = ?
                WHERE page_id = ?
            """, (status, extracted_data, page_id))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def get_pending_pages(self) -> List[Dict]:
        """Get pages pending extraction"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT p.*, t.topic_name
                FROM uploaded_pages p
                JOIN book_topics t ON p.topic_id = t.topic_id
                WHERE p.extraction_status = 'pending' AND p.is_answer_key = 0
                ORDER BY p.uploaded_at
            """)
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_pages_by_topic(self, topic_id: int) -> List[Dict]:
        """Get all pages for a topic"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM uploaded_pages
                WHERE topic_id = ?
                ORDER BY page_number, uploaded_at
            """, (topic_id,))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    # ============================================================
    # QUESTION OPERATIONS
    # ============================================================

    def add_question(self, topic_id: int, question_text: str, choices: Dict[str, str],
                     question_number: int = None, correct_choice: str = None,
                     page_id: int = None, difficulty: str = 'difficult',
                     source_exam: str = None) -> int:
        """Add a new question"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO book_questions
                (topic_id, page_id, question_number, question_text,
                 choice_a, choice_b, choice_c, choice_d, choice_e,
                 correct_choice, difficulty, source_exam)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                topic_id, page_id, question_number, question_text,
                choices.get('a'), choices.get('b'), choices.get('c'),
                choices.get('d'), choices.get('e'),
                correct_choice, difficulty, source_exam
            ))

            # Update topic question count
            cursor.execute("""
                UPDATE book_topics
                SET total_questions = (
                    SELECT COUNT(*) FROM book_questions WHERE topic_id = ?
                )
                WHERE topic_id = ?
            """, (topic_id, topic_id))

            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def add_questions_bulk(self, questions: List[Dict]) -> int:
        """Add multiple questions at once"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            count = 0
            topic_ids = set()

            for q in questions:
                choices = q.get('choices', {})
                cursor.execute("""
                    INSERT INTO book_questions
                    (topic_id, page_id, question_number, question_text,
                     choice_a, choice_b, choice_c, choice_d, choice_e,
                     correct_choice, difficulty, source_exam)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    q.get('topic_id'), q.get('page_id'), q.get('question_number'),
                    q.get('question_text'),
                    choices.get('a'), choices.get('b'), choices.get('c'),
                    choices.get('d'), choices.get('e'),
                    q.get('correct_choice'), q.get('difficulty', 'difficult'),
                    q.get('source_exam')
                ))
                count += 1
                if q.get('topic_id'):
                    topic_ids.add(q['topic_id'])

            # Update topic question counts
            for topic_id in topic_ids:
                cursor.execute("""
                    UPDATE book_topics
                    SET total_questions = (
                        SELECT COUNT(*) FROM book_questions WHERE topic_id = ?
                    )
                    WHERE topic_id = ?
                """, (topic_id, topic_id))

            conn.commit()
            return count
        finally:
            conn.close()

    def get_question(self, question_id: int) -> Optional[Dict]:
        """Get a single question by ID"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT q.*, t.topic_name
                FROM book_questions q
                JOIN book_topics t ON q.topic_id = t.topic_id
                WHERE q.question_id = ?
            """, (question_id,))
            row = cursor.fetchone()
            if row:
                q = dict(row)
                # Convert choices to dict
                q['choices'] = {
                    'a': q.pop('choice_a'),
                    'b': q.pop('choice_b'),
                    'c': q.pop('choice_c'),
                    'd': q.pop('choice_d'),
                    'e': q.pop('choice_e'),
                }
                # Remove None choices
                q['choices'] = {k: v for k, v in q['choices'].items() if v}
                return q
            return None
        finally:
            conn.close()

    def get_questions_by_topic(self, topic_id: int, limit: int = None) -> List[Dict]:
        """Get all questions for a topic"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            query = """
                SELECT q.*, t.topic_name
                FROM book_questions q
                JOIN book_topics t ON q.topic_id = t.topic_id
                WHERE q.topic_id = ?
                ORDER BY q.question_number
            """
            if limit:
                query += f" LIMIT {limit}"
            cursor.execute(query, (topic_id,))

            results = []
            for row in cursor.fetchall():
                q = dict(row)
                q['choices'] = {
                    'a': q.pop('choice_a'),
                    'b': q.pop('choice_b'),
                    'c': q.pop('choice_c'),
                    'd': q.pop('choice_d'),
                    'e': q.pop('choice_e'),
                }
                q['choices'] = {k: v for k, v in q['choices'].items() if v}
                results.append(q)
            return results
        finally:
            conn.close()

    def get_pending_review_questions(self, page_id: int = None) -> List[Dict]:
        """Get questions that need verification"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            if page_id:
                cursor.execute("""
                    SELECT q.*, t.topic_name
                    FROM book_questions q
                    JOIN book_topics t ON q.topic_id = t.topic_id
                    WHERE q.is_verified = 0 AND q.page_id = ?
                    ORDER BY q.question_number
                """, (page_id,))
            else:
                cursor.execute("""
                    SELECT q.*, t.topic_name
                    FROM book_questions q
                    JOIN book_topics t ON q.topic_id = t.topic_id
                    WHERE q.is_verified = 0
                    ORDER BY q.topic_id, q.question_number
                """)

            results = []
            for row in cursor.fetchall():
                q = dict(row)
                q['choices'] = {
                    'a': q.pop('choice_a'),
                    'b': q.pop('choice_b'),
                    'c': q.pop('choice_c'),
                    'd': q.pop('choice_d'),
                    'e': q.pop('choice_e'),
                }
                q['choices'] = {k: v for k, v in q['choices'].items() if v}
                results.append(q)
            return results
        finally:
            conn.close()

    def update_question(self, question_id: int, **kwargs) -> bool:
        """Update a question"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            fields = []
            values = []

            # Handle choices separately
            if 'choices' in kwargs:
                choices = kwargs.pop('choices')
                for key in ['a', 'b', 'c', 'd', 'e']:
                    if key in choices:
                        fields.append(f"choice_{key} = ?")
                        values.append(choices[key])

            for key, value in kwargs.items():
                if key in ['question_text', 'question_number', 'correct_choice',
                           'difficulty', 'source_exam', 'is_verified', 'topic_id']:
                    fields.append(f"{key} = ?")
                    values.append(value)

            if not fields:
                return False

            values.append(question_id)
            cursor.execute(f"""
                UPDATE book_questions SET {', '.join(fields)}
                WHERE question_id = ?
            """, values)
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def verify_questions(self, question_ids: List[int]) -> int:
        """Mark questions as verified"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            placeholders = ','.join('?' * len(question_ids))
            cursor.execute(f"""
                UPDATE book_questions SET is_verified = 1
                WHERE question_id IN ({placeholders})
            """, question_ids)
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()

    def set_correct_answers(self, answers: Dict[int, str]) -> int:
        """Set correct answers for multiple questions (from answer key)"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            count = 0
            for question_number, correct_choice in answers.items():
                cursor.execute("""
                    UPDATE book_questions
                    SET correct_choice = ?
                    WHERE question_number = ?
                """, (correct_choice.lower(), question_number))
                count += cursor.rowcount
            conn.commit()
            return count
        finally:
            conn.close()

    def set_correct_answers_by_topic(self, topic_id: int, answers: Dict[int, str]) -> int:
        """Set correct answers for questions in a specific topic"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            count = 0
            for question_number, correct_choice in answers.items():
                cursor.execute("""
                    UPDATE book_questions
                    SET correct_choice = ?
                    WHERE topic_id = ? AND question_number = ?
                """, (correct_choice.lower(), topic_id, question_number))
                count += cursor.rowcount
            conn.commit()
            return count
        finally:
            conn.close()

    def delete_question(self, question_id: int) -> bool:
        """Delete a question"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            # Get topic_id first for count update
            cursor.execute("SELECT topic_id FROM book_questions WHERE question_id = ?", (question_id,))
            row = cursor.fetchone()
            if not row:
                return False
            topic_id = row['topic_id']

            cursor.execute("DELETE FROM book_questions WHERE question_id = ?", (question_id,))

            # Update topic question count
            cursor.execute("""
                UPDATE book_topics
                SET total_questions = (
                    SELECT COUNT(*) FROM book_questions WHERE topic_id = ?
                )
                WHERE topic_id = ?
            """, (topic_id, topic_id))

            conn.commit()
            return True
        finally:
            conn.close()

    # ============================================================
    # PRACTICE SESSION OPERATIONS
    # ============================================================

    def create_session(self, user_id: str, mode: str, topic_ids: List[int] = None,
                       question_count: int = 10) -> int:
        """Create a new practice session"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO practice_sessions
                (user_id, mode, selected_topics, question_count)
                VALUES (?, ?, ?, ?)
            """, (user_id, mode, json.dumps(topic_ids) if topic_ids else None, question_count))
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def get_session(self, session_id: int) -> Optional[Dict]:
        """Get session details"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM practice_sessions WHERE session_id = ?
            """, (session_id,))
            row = cursor.fetchone()
            if row:
                session = dict(row)
                if session['selected_topics']:
                    session['selected_topics'] = json.loads(session['selected_topics'])
                return session
            return None
        finally:
            conn.close()

    def get_questions_for_practice(self, topic_ids: List[int] = None, count: int = 10,
                                   mode: str = 'random', user_id: str = None) -> List[Dict]:
        """Get questions for a practice session"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            if mode == 'smart_weak' and user_id:
                # Smart mode: prioritize weak questions
                questions = self._get_smart_questions(cursor, user_id, topic_ids, count)
            else:
                # Random mode from selected topics
                if topic_ids:
                    placeholders = ','.join('?' * len(topic_ids))
                    cursor.execute(f"""
                        SELECT q.*, t.topic_name
                        FROM book_questions q
                        JOIN book_topics t ON q.topic_id = t.topic_id
                        WHERE q.topic_id IN ({placeholders})
                          AND q.is_verified = 1
                          AND q.correct_choice IS NOT NULL
                        ORDER BY RANDOM()
                        LIMIT ?
                    """, (*topic_ids, count))
                else:
                    cursor.execute("""
                        SELECT q.*, t.topic_name
                        FROM book_questions q
                        JOIN book_topics t ON q.topic_id = t.topic_id
                        WHERE q.is_verified = 1
                          AND q.correct_choice IS NOT NULL
                        ORDER BY RANDOM()
                        LIMIT ?
                    """, (count,))

                questions = []
                for row in cursor.fetchall():
                    q = dict(row)
                    q['choices'] = {
                        'a': q.pop('choice_a'),
                        'b': q.pop('choice_b'),
                        'c': q.pop('choice_c'),
                        'd': q.pop('choice_d'),
                        'e': q.pop('choice_e'),
                    }
                    q['choices'] = {k: v for k, v in q['choices'].items() if v}
                    questions.append(q)

            return questions
        finally:
            conn.close()

    def _get_smart_questions(self, cursor, user_id: str, topic_ids: List[int] = None,
                             count: int = 10) -> List[Dict]:
        """Get questions using spaced repetition algorithm"""
        questions = []
        today = date.today().isoformat()

        topic_filter = ""
        params = [user_id]
        if topic_ids:
            placeholders = ','.join('?' * len(topic_ids))
            topic_filter = f"AND q.topic_id IN ({placeholders})"
            params.extend(topic_ids)

        # 60% learning questions (low accuracy, few attempts)
        learning_count = int(count * 0.6)
        cursor.execute(f"""
            SELECT q.*, t.topic_name, m.accuracy, m.total_attempts
            FROM book_questions q
            JOIN book_topics t ON q.topic_id = t.topic_id
            LEFT JOIN question_mastery m ON q.question_id = m.question_id AND m.user_id = ?
            WHERE q.is_verified = 1 AND q.correct_choice IS NOT NULL
              {topic_filter}
              AND (m.mastery_level = 'learning' OR m.mastery_level IS NULL OR m.mastery_level = 'new')
            ORDER BY COALESCE(m.accuracy, 0), RANDOM()
            LIMIT ?
        """, (*params, learning_count))

        for row in cursor.fetchall():
            q = dict(row)
            q['choices'] = {
                'a': q.pop('choice_a'),
                'b': q.pop('choice_b'),
                'c': q.pop('choice_c'),
                'd': q.pop('choice_d'),
                'e': q.pop('choice_e'),
            }
            q['choices'] = {k: v for k, v in q['choices'].items() if v}
            questions.append(q)

        question_ids = [q['question_id'] for q in questions]
        remaining = count - len(questions)

        if remaining > 0:
            # 30% practiced questions due for review
            practiced_count = int(count * 0.3)
            exclude_filter = ""
            if question_ids:
                exclude_filter = f"AND q.question_id NOT IN ({','.join('?' * len(question_ids))})"

            cursor.execute(f"""
                SELECT q.*, t.topic_name, m.accuracy
                FROM book_questions q
                JOIN book_topics t ON q.topic_id = t.topic_id
                LEFT JOIN question_mastery m ON q.question_id = m.question_id AND m.user_id = ?
                WHERE q.is_verified = 1 AND q.correct_choice IS NOT NULL
                  {topic_filter}
                  {exclude_filter}
                  AND m.mastery_level = 'practiced'
                  AND (m.next_review_date IS NULL OR m.next_review_date <= ?)
                ORDER BY m.next_review_date, RANDOM()
                LIMIT ?
            """, (*params, *question_ids, today, practiced_count))

            for row in cursor.fetchall():
                q = dict(row)
                q['choices'] = {
                    'a': q.pop('choice_a'),
                    'b': q.pop('choice_b'),
                    'c': q.pop('choice_c'),
                    'd': q.pop('choice_d'),
                    'e': q.pop('choice_e'),
                }
                q['choices'] = {k: v for k, v in q['choices'].items() if v}
                questions.append(q)

        remaining = count - len(questions)
        if remaining > 0:
            # 10% mastered questions for maintenance
            question_ids = [q['question_id'] for q in questions]
            exclude_filter = ""
            if question_ids:
                exclude_filter = f"AND q.question_id NOT IN ({','.join('?' * len(question_ids))})"

            cursor.execute(f"""
                SELECT q.*, t.topic_name, m.accuracy
                FROM book_questions q
                JOIN book_topics t ON q.topic_id = t.topic_id
                LEFT JOIN question_mastery m ON q.question_id = m.question_id AND m.user_id = ?
                WHERE q.is_verified = 1 AND q.correct_choice IS NOT NULL
                  {topic_filter}
                  {exclude_filter}
                  AND m.mastery_level = 'mastered'
                ORDER BY RANDOM()
                LIMIT ?
            """, (*params, *question_ids, remaining))

            for row in cursor.fetchall():
                q = dict(row)
                q['choices'] = {
                    'a': q.pop('choice_a'),
                    'b': q.pop('choice_b'),
                    'c': q.pop('choice_c'),
                    'd': q.pop('choice_d'),
                    'e': q.pop('choice_e'),
                }
                q['choices'] = {k: v for k, v in q['choices'].items() if v}
                questions.append(q)

        # Shuffle the final list
        random.shuffle(questions)
        return questions

    def complete_session(self, session_id: int) -> Dict:
        """Complete a session and return summary"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            # Calculate session stats
            cursor.execute("""
                SELECT
                    COUNT(*) as total_attempted,
                    SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END) as total_correct,
                    AVG(time_taken_seconds) as avg_time
                FROM question_attempts
                WHERE session_id = ?
            """, (session_id,))
            stats = dict(cursor.fetchone())

            # Update session
            cursor.execute("""
                UPDATE practice_sessions
                SET completed_at = CURRENT_TIMESTAMP,
                    total_correct = ?,
                    total_attempted = ?
                WHERE session_id = ?
            """, (stats['total_correct'] or 0, stats['total_attempted'] or 0, session_id))

            conn.commit()
            return stats
        finally:
            conn.close()

    # ============================================================
    # ATTEMPT & MASTERY OPERATIONS
    # ============================================================

    def record_attempt(self, session_id: int, question_id: int, user_id: str,
                       selected_choice: str, time_taken: int, notes: str = None) -> Dict:
        """Record a question attempt and update mastery"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            # Get correct answer
            cursor.execute("""
                SELECT correct_choice FROM book_questions WHERE question_id = ?
            """, (question_id,))
            row = cursor.fetchone()
            if not row:
                return {'error': 'Question not found'}

            correct_choice = row['correct_choice']
            is_correct = selected_choice.lower() == correct_choice.lower() if correct_choice else None

            # Get attempt number
            cursor.execute("""
                SELECT COUNT(*) + 1 as attempt_number
                FROM question_attempts
                WHERE question_id = ? AND user_id = ?
            """, (question_id, user_id))
            attempt_number = cursor.fetchone()['attempt_number']

            # Record attempt
            cursor.execute("""
                INSERT INTO question_attempts
                (session_id, question_id, user_id, selected_choice, is_correct,
                 time_taken_seconds, attempt_number, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (session_id, question_id, user_id, selected_choice,
                  is_correct, time_taken, attempt_number, notes))

            # Update mastery
            self._update_mastery(cursor, question_id, user_id, is_correct, time_taken)

            conn.commit()

            return {
                'is_correct': is_correct,
                'correct_choice': correct_choice,
                'attempt_number': attempt_number,
                'time_taken': time_taken
            }
        finally:
            conn.close()

    def _update_mastery(self, cursor, question_id: int, user_id: str,
                        is_correct: bool, time_taken: int):
        """Update question mastery based on attempt"""
        # Get existing mastery
        cursor.execute("""
            SELECT * FROM question_mastery
            WHERE question_id = ? AND user_id = ?
        """, (question_id, user_id))
        mastery = cursor.fetchone()

        if mastery:
            mastery = dict(mastery)
            total_attempts = mastery['total_attempts'] + 1
            correct_attempts = mastery['correct_attempts'] + (1 if is_correct else 0)
            accuracy = (correct_attempts / total_attempts) * 100

            # Calculate average time
            avg_time = ((mastery['average_time_seconds'] or 0) * mastery['total_attempts'] + time_taken) / total_attempts
            best_time = min(mastery['best_time_seconds'] or time_taken, time_taken) if is_correct else mastery['best_time_seconds']

            # Determine mastery level
            if total_attempts < 3 or accuracy < 50:
                mastery_level = 'learning'
            elif accuracy < 80:
                mastery_level = 'practiced'
            else:
                mastery_level = 'mastered'

            # Calculate next review date (spaced repetition)
            interval_index = mastery['spaced_interval_index']
            if is_correct:
                interval_index = min(interval_index + 1, len(self.SPACED_INTERVALS) - 1)
            else:
                interval_index = 0  # Reset on incorrect

            next_review = date.today() + timedelta(days=self.SPACED_INTERVALS[interval_index])

            cursor.execute("""
                UPDATE question_mastery
                SET total_attempts = ?, correct_attempts = ?, accuracy = ?,
                    average_time_seconds = ?, best_time_seconds = ?,
                    last_attempted = CURRENT_TIMESTAMP, mastery_level = ?,
                    next_review_date = ?, spaced_interval_index = ?
                WHERE mastery_id = ?
            """, (total_attempts, correct_attempts, accuracy, avg_time, best_time,
                  mastery_level, next_review.isoformat(), interval_index, mastery['mastery_id']))
        else:
            # Create new mastery record
            accuracy = 100.0 if is_correct else 0.0
            mastery_level = 'new' if not is_correct else 'learning'
            interval_index = 1 if is_correct else 0
            next_review = date.today() + timedelta(days=self.SPACED_INTERVALS[interval_index])

            cursor.execute("""
                INSERT INTO question_mastery
                (question_id, user_id, total_attempts, correct_attempts, accuracy,
                 average_time_seconds, best_time_seconds, last_attempted, mastery_level,
                 next_review_date, spaced_interval_index)
                VALUES (?, ?, 1, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?, ?)
            """, (question_id, user_id, 1 if is_correct else 0, accuracy,
                  time_taken, time_taken if is_correct else None, mastery_level,
                  next_review.isoformat(), interval_index))

    def add_note_to_attempt(self, attempt_id: int, note: str) -> bool:
        """Add or update note for an attempt"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE question_attempts SET notes = ?
                WHERE attempt_id = ?
            """, (note, attempt_id))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    # ============================================================
    # ANALYTICS OPERATIONS
    # ============================================================

    def get_overview_stats(self, user_id: str) -> Dict:
        """Get overall statistics for a user"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            # Total questions and mastery breakdown
            cursor.execute("""
                SELECT
                    COUNT(DISTINCT q.question_id) as total_questions,
                    COUNT(DISTINCT CASE WHEN m.mastery_level = 'new' OR m.mastery_level IS NULL
                          THEN q.question_id END) as new_count,
                    COUNT(DISTINCT CASE WHEN m.mastery_level = 'learning'
                          THEN q.question_id END) as learning_count,
                    COUNT(DISTINCT CASE WHEN m.mastery_level = 'practiced'
                          THEN q.question_id END) as practiced_count,
                    COUNT(DISTINCT CASE WHEN m.mastery_level = 'mastered'
                          THEN q.question_id END) as mastered_count
                FROM book_questions q
                LEFT JOIN question_mastery m ON q.question_id = m.question_id AND m.user_id = ?
                WHERE q.is_verified = 1
            """, (user_id,))
            mastery_stats = dict(cursor.fetchone())

            # Overall attempt stats
            cursor.execute("""
                SELECT
                    COUNT(*) as total_attempts,
                    SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END) as correct_attempts,
                    AVG(time_taken_seconds) as avg_time,
                    MIN(time_taken_seconds) as min_time
                FROM question_attempts
                WHERE user_id = ?
            """, (user_id,))
            attempt_stats = dict(cursor.fetchone())

            # Session stats
            cursor.execute("""
                SELECT COUNT(*) as total_sessions
                FROM practice_sessions
                WHERE user_id = ? AND completed_at IS NOT NULL
            """, (user_id,))
            session_stats = dict(cursor.fetchone())

            # Combine all stats
            accuracy = 0
            if attempt_stats['total_attempts'] and attempt_stats['total_attempts'] > 0:
                accuracy = (attempt_stats['correct_attempts'] / attempt_stats['total_attempts']) * 100

            return {
                **mastery_stats,
                'total_attempts': attempt_stats['total_attempts'] or 0,
                'overall_accuracy': round(accuracy, 1),
                'average_time': round(attempt_stats['avg_time'] or 0, 1),
                'total_sessions': session_stats['total_sessions'] or 0
            }
        finally:
            conn.close()

    def get_topic_performance(self, user_id: str) -> List[Dict]:
        """Get performance breakdown by topic"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    t.topic_id,
                    t.topic_name,
                    t.chapter_number,
                    COUNT(DISTINCT q.question_id) as total_questions,
                    COUNT(DISTINCT a.question_id) as attempted_questions,
                    SUM(CASE WHEN a.is_correct = 1 THEN 1 ELSE 0 END) as correct_count,
                    COUNT(a.attempt_id) as attempt_count,
                    AVG(a.time_taken_seconds) as avg_time
                FROM book_topics t
                LEFT JOIN book_questions q ON t.topic_id = q.topic_id AND q.is_verified = 1
                LEFT JOIN question_attempts a ON q.question_id = a.question_id AND a.user_id = ?
                GROUP BY t.topic_id
                ORDER BY t.chapter_number
            """, (user_id,))

            results = []
            for row in cursor.fetchall():
                topic = dict(row)
                if topic['attempt_count'] and topic['attempt_count'] > 0:
                    topic['accuracy'] = round((topic['correct_count'] / topic['attempt_count']) * 100, 1)
                else:
                    topic['accuracy'] = 0
                topic['avg_time'] = round(topic['avg_time'] or 0, 1)
                results.append(topic)

            return results
        finally:
            conn.close()

    def get_question_history(self, question_id: int, user_id: str) -> Dict:
        """Get attempt history for a single question"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            # Get question details
            cursor.execute("""
                SELECT q.*, t.topic_name
                FROM book_questions q
                JOIN book_topics t ON q.topic_id = t.topic_id
                WHERE q.question_id = ?
            """, (question_id,))
            question = dict(cursor.fetchone())
            question['choices'] = {
                'a': question.pop('choice_a'),
                'b': question.pop('choice_b'),
                'c': question.pop('choice_c'),
                'd': question.pop('choice_d'),
                'e': question.pop('choice_e'),
            }
            question['choices'] = {k: v for k, v in question['choices'].items() if v}

            # Get mastery
            cursor.execute("""
                SELECT * FROM question_mastery
                WHERE question_id = ? AND user_id = ?
            """, (question_id, user_id))
            mastery_row = cursor.fetchone()
            mastery = dict(mastery_row) if mastery_row else None

            # Get all attempts
            cursor.execute("""
                SELECT * FROM question_attempts
                WHERE question_id = ? AND user_id = ?
                ORDER BY attempted_at DESC
            """, (question_id, user_id))
            attempts = [dict(row) for row in cursor.fetchall()]

            return {
                'question': question,
                'mastery': mastery,
                'attempts': attempts
            }
        finally:
            conn.close()

    def get_accuracy_trend(self, user_id: str, days: int = 30) -> List[Dict]:
        """Get accuracy trend over time"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    DATE(attempted_at) as date,
                    COUNT(*) as attempts,
                    SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END) as correct,
                    AVG(time_taken_seconds) as avg_time
                FROM question_attempts
                WHERE user_id = ?
                  AND attempted_at >= DATE('now', ?)
                GROUP BY DATE(attempted_at)
                ORDER BY date
            """, (user_id, f'-{days} days'))

            results = []
            for row in cursor.fetchall():
                data = dict(row)
                data['accuracy'] = round((data['correct'] / data['attempts']) * 100, 1) if data['attempts'] > 0 else 0
                data['avg_time'] = round(data['avg_time'] or 0, 1)
                results.append(data)

            return results
        finally:
            conn.close()

    def get_weak_topics(self, user_id: str, limit: int = 5) -> List[Dict]:
        """Get topics where user is struggling"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    t.topic_id,
                    t.topic_name,
                    COUNT(a.attempt_id) as attempts,
                    SUM(CASE WHEN a.is_correct = 1 THEN 1 ELSE 0 END) as correct,
                    CAST(SUM(CASE WHEN a.is_correct = 1 THEN 1 ELSE 0 END) AS FLOAT) /
                        COUNT(a.attempt_id) * 100 as accuracy
                FROM book_topics t
                JOIN book_questions q ON t.topic_id = q.topic_id
                JOIN question_attempts a ON q.question_id = a.question_id
                WHERE a.user_id = ?
                GROUP BY t.topic_id
                HAVING COUNT(a.attempt_id) >= 3
                ORDER BY accuracy ASC
                LIMIT ?
            """, (user_id, limit))

            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_session_history(self, user_id: str, limit: int = 20) -> List[Dict]:
        """Get recent practice sessions"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    s.*,
                    AVG(a.time_taken_seconds) as avg_time
                FROM practice_sessions s
                LEFT JOIN question_attempts a ON s.session_id = a.session_id
                WHERE s.user_id = ? AND s.completed_at IS NOT NULL
                GROUP BY s.session_id
                ORDER BY s.completed_at DESC
                LIMIT ?
            """, (user_id, limit))

            results = []
            for row in cursor.fetchall():
                session = dict(row)
                if session['selected_topics']:
                    session['selected_topics'] = json.loads(session['selected_topics'])
                session['accuracy'] = round((session['total_correct'] / session['total_attempted']) * 100, 1) if session['total_attempted'] > 0 else 0
                session['avg_time'] = round(session['avg_time'] or 0, 1)
                results.append(session)

            return results
        finally:
            conn.close()
