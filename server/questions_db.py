"""
Questions Database - Local storage for assessment questions.

This is the source of truth for all test questions, independent of AnkiConnect.
Questions are tagged to PDF filenames for easy lookup.
"""

import sqlite3
import json
from pathlib import Path
from typing import List, Dict, Optional, Any
from datetime import datetime


class QuestionsDatabase:
    """Manages local storage of assessment questions."""

    def __init__(self, db_path: Optional[str] = None):
        """Initialize with database path."""
        if db_path is None:
            db_path = str(Path.home() / 'clat_preparation' / 'revision_tracker.db')
        self.db_path = db_path
        self._init_tables()

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection with row factory."""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_tables(self):
        """Initialize tables if they don't exist."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Questions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS questions (
                question_id INTEGER PRIMARY KEY AUTOINCREMENT,
                pdf_filename TEXT NOT NULL,
                anki_note_id TEXT,
                question_text TEXT NOT NULL,
                answer_text TEXT NOT NULL,
                category TEXT,
                deck_name TEXT,
                source_name TEXT,
                week_tag TEXT,
                tags TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # MCQ choices table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS question_choices (
                choice_id INTEGER PRIMARY KEY AUTOINCREMENT,
                question_id INTEGER NOT NULL,
                choices TEXT NOT NULL,
                correct_index INTEGER NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (question_id) REFERENCES questions(question_id) ON DELETE CASCADE
            )
        """)

        # Indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_questions_pdf ON questions(pdf_filename)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_questions_category ON questions(category)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_question_choices_qid ON question_choices(question_id)")

        conn.commit()
        conn.close()

    def add_question(
        self,
        pdf_filename: str,
        question_text: str,
        answer_text: str,
        category: str = None,
        deck_name: str = None,
        source_name: str = None,
        week_tag: str = None,
        tags: List[str] = None,
        anki_note_id: str = None
    ) -> int:
        """
        Add a question to the database.
        
        Returns question_id.
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO questions 
                (pdf_filename, question_text, answer_text, category, deck_name, 
                 source_name, week_tag, tags, anki_note_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                pdf_filename,
                question_text,
                answer_text,
                category,
                deck_name,
                source_name,
                week_tag,
                json.dumps(tags) if tags else None,
                anki_note_id,
                datetime.now().isoformat()
            ))
            
            question_id = cursor.lastrowid
            conn.commit()
            return question_id

        except sqlite3.IntegrityError:
            # Question already exists - get its ID
            cursor.execute("""
                SELECT question_id FROM questions 
                WHERE pdf_filename = ? AND question_text = ?
            """, (pdf_filename, question_text))
            row = cursor.fetchone()
            return row['question_id'] if row else None

        finally:
            conn.close()

    def add_questions_batch(
        self,
        pdf_filename: str,
        questions: List[Dict],
        source_name: str = None,
        week_tag: str = None
    ) -> int:
        """
        Add multiple questions in a batch.
        
        Args:
            pdf_filename: The PDF these questions belong to
            questions: List of dicts with 'front', 'back', 'deck', 'tags' keys
            source_name: Source identifier (career_launcher, legaledge)
            week_tag: Week tag (2025_Dec_W2)
            
        Returns count of questions added.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        added_count = 0

        for q in questions:
            try:
                # Extract category from deck name (e.g., "CLAT GK::Economy & Business" -> "Economy & Business")
                deck_name = q.get('deck', '')
                category = deck_name.split('::')[-1] if '::' in deck_name else deck_name

                cursor.execute("""
                    INSERT INTO questions 
                    (pdf_filename, question_text, answer_text, category, deck_name, 
                     source_name, week_tag, tags, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    pdf_filename,
                    q.get('front', ''),
                    q.get('back', ''),
                    category,
                    deck_name,
                    source_name,
                    week_tag,
                    json.dumps(q.get('tags', [])),
                    datetime.now().isoformat()
                ))
                added_count += 1

            except sqlite3.IntegrityError:
                # Duplicate question, skip
                continue

        conn.commit()
        conn.close()
        return added_count

    def get_questions_for_pdf(self, pdf_filename: str) -> List[Dict]:
        """
        Get all questions for a specific PDF.
        
        Returns list of question dicts ready for testing.
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT 
                q.question_id,
                q.pdf_filename,
                q.question_text,
                q.answer_text,
                q.category,
                q.deck_name,
                q.tags,
                qc.choices,
                qc.correct_index
            FROM questions q
            LEFT JOIN question_choices qc ON q.question_id = qc.question_id
            WHERE q.pdf_filename = ?
            ORDER BY q.question_id
        """, (pdf_filename,))

        questions = []
        for row in cursor.fetchall():
            q = {
                'question_id': row['question_id'],
                'note_id': row['question_id'],  # For compatibility with existing code
                'pdf_filename': row['pdf_filename'],
                'question': row['question_text'],
                'answer': row['answer_text'],
                'category': row['category'] or 'General',
                'deck': row['deck_name'],
                'tags': json.loads(row['tags']) if row['tags'] else []
            }
            
            # Add choices if available
            if row['choices']:
                q['choices'] = json.loads(row['choices'])
                q['correct_index'] = row['correct_index']
            
            questions.append(q)

        conn.close()
        return questions

    def get_question_count_for_pdf(self, pdf_filename: str) -> int:
        """Get count of questions for a PDF."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT COUNT(*) as count FROM questions WHERE pdf_filename = ?
        """, (pdf_filename,))

        count = cursor.fetchone()['count']
        conn.close()
        return count

    def save_mcq_choices(
        self,
        question_id: int,
        choices: List[str],
        correct_index: int
    ) -> bool:
        """Save MCQ choices for a question."""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Check if choices already exist
            cursor.execute("""
                SELECT choice_id FROM question_choices WHERE question_id = ?
            """, (question_id,))
            
            if cursor.fetchone():
                # Update existing
                cursor.execute("""
                    UPDATE question_choices 
                    SET choices = ?, correct_index = ?
                    WHERE question_id = ?
                """, (json.dumps(choices), correct_index, question_id))
            else:
                # Insert new
                cursor.execute("""
                    INSERT INTO question_choices (question_id, choices, correct_index, created_at)
                    VALUES (?, ?, ?, ?)
                """, (question_id, json.dumps(choices), correct_index, datetime.now().isoformat()))

            conn.commit()
            return True

        except Exception as e:
            print(f"Error saving MCQ choices: {e}")
            return False

        finally:
            conn.close()

    def get_mcq_choices(self, question_id: int) -> Optional[Dict]:
        """Get MCQ choices for a question."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT choices, correct_index FROM question_choices WHERE question_id = ?
        """, (question_id,))

        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                'choices': json.loads(row['choices']),
                'correct_index': row['correct_index']
            }
        return None

    def get_pdf_stats(self, pdf_filename: str) -> Dict:
        """Get statistics for a PDF's questions."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT 
                COUNT(*) as total_questions,
                COUNT(DISTINCT category) as categories,
                (SELECT COUNT(*) FROM question_choices qc 
                 JOIN questions q ON qc.question_id = q.question_id 
                 WHERE q.pdf_filename = ?) as questions_with_choices
            FROM questions
            WHERE pdf_filename = ?
        """, (pdf_filename, pdf_filename))

        row = cursor.fetchone()
        conn.close()

        return {
            'total_questions': row['total_questions'],
            'categories': row['categories'],
            'questions_with_choices': row['questions_with_choices']
        }

    def get_all_pdf_question_counts(self) -> Dict[str, int]:
        """Get question counts for all PDFs."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT pdf_filename, COUNT(*) as count 
            FROM questions 
            GROUP BY pdf_filename
        """)

        counts = {row['pdf_filename']: row['count'] for row in cursor.fetchall()}
        conn.close()
        return counts

    def get_questions_by_ids(self, question_ids: List[int]) -> List[Dict]:
        """
        Get questions by their IDs.

        Used for weak topics practice - fetches questions that need more practice.

        Args:
            question_ids: List of question IDs to fetch

        Returns list of question dicts ready for testing.
        """
        if not question_ids:
            return []

        conn = self._get_connection()
        cursor = conn.cursor()

        placeholders = ','.join('?' * len(question_ids))
        cursor.execute(f"""
            SELECT
                q.question_id,
                q.pdf_filename,
                q.question_text,
                q.answer_text,
                q.category,
                q.deck_name,
                q.tags,
                qc.choices,
                qc.correct_index
            FROM questions q
            LEFT JOIN question_choices qc ON q.question_id = qc.question_id
            WHERE q.question_id IN ({placeholders})
            ORDER BY q.question_id
        """, question_ids)

        questions = []
        for row in cursor.fetchall():
            q = {
                'question_id': row['question_id'],
                'note_id': row['question_id'],  # For compatibility
                'pdf_filename': row['pdf_filename'],
                'question': row['question_text'],
                'answer': row['answer_text'],
                'category': row['category'] or 'General',
                'deck': row['deck_name'],
                'tags': json.loads(row['tags']) if row['tags'] else []
            }

            # Add choices if available
            if row['choices']:
                q['choices'] = json.loads(row['choices'])
                q['correct_index'] = row['correct_index']

            questions.append(q)

        conn.close()
        return questions

    def search_questions(
        self,
        category: str = None,
        source_name: str = None,
        limit: int = None
    ) -> List[Dict]:
        """Search questions with filters."""
        conn = self._get_connection()
        cursor = conn.cursor()

        query = "SELECT * FROM questions WHERE 1=1"
        params = []

        if category:
            query += " AND category = ?"
            params.append(category)

        if source_name:
            query += " AND source_name = ?"
            params.append(source_name)

        query += " ORDER BY created_at DESC"

        if limit:
            query += " LIMIT ?"
            params.append(limit)

        cursor.execute(query, params)
        questions = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return questions

    def delete_questions_for_pdf(self, pdf_filename: str) -> int:
        """Delete all questions for a PDF. Returns count deleted."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Get question IDs first
        cursor.execute("SELECT question_id FROM questions WHERE pdf_filename = ?", (pdf_filename,))
        question_ids = [row['question_id'] for row in cursor.fetchall()]

        if question_ids:
            # Delete choices first (foreign key)
            cursor.execute(f"""
                DELETE FROM question_choices 
                WHERE question_id IN ({','.join('?' * len(question_ids))})
            """, question_ids)

            # Delete questions
            cursor.execute("DELETE FROM questions WHERE pdf_filename = ?", (pdf_filename,))

        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        return deleted


# Singleton instance for easy import
_instance = None

def get_questions_db() -> QuestionsDatabase:
    """Get singleton instance of QuestionsDatabase."""
    global _instance
    if _instance is None:
        _instance = QuestionsDatabase()
    return _instance

