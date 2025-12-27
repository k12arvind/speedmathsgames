"""
Mock Analysis Database Module
Handles CRUD operations for mock test tracking and analysis
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any


class MockDatabase:
    """Database handler for mock test analysis"""
    
    # Default CLAT sections
    DEFAULT_SECTIONS = [
        {'name': 'English', 'order': 1, 'questions': 28, 'max_score': 28, 'time': 20, 'color': '#3B82F6', 'icon': '📖'},
        {'name': 'Current Affairs', 'order': 2, 'questions': 35, 'max_score': 35, 'time': 25, 'color': '#8B5CF6', 'icon': '📰'},
        {'name': 'Legal Reasoning', 'order': 3, 'questions': 35, 'max_score': 35, 'time': 30, 'color': '#10B981', 'icon': '⚖️'},
        {'name': 'Logical Reasoning', 'order': 4, 'questions': 28, 'max_score': 28, 'time': 25, 'color': '#F59E0B', 'icon': '🧩'},
        {'name': 'Quantitative', 'order': 5, 'questions': 14, 'max_score': 14, 'time': 20, 'color': '#EF4444', 'icon': '🔢'},
    ]
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = Path.home() / "clat_preparation" / "revision_tracker.db"
        self.db_path = str(db_path)
        self._init_tables()
    
    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _init_tables(self):
        """Initialize mock analysis tables"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            # Main mock tests table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS mock_tests (
                    mock_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL DEFAULT 'saanvi',
                    mock_name TEXT NOT NULL,
                    mock_source TEXT,
                    mock_date DATE NOT NULL,
                    mock_type TEXT DEFAULT 'full',
                    total_questions INTEGER DEFAULT 150,
                    total_attempted INTEGER,
                    total_correct INTEGER,
                    total_incorrect INTEGER,
                    total_unattempted INTEGER,
                    total_score REAL,
                    max_score REAL DEFAULT 150,
                    percentile REAL,
                    rank INTEGER,
                    total_time_minutes INTEGER DEFAULT 120,
                    time_taken_minutes INTEGER,
                    what_went_well TEXT,
                    areas_to_improve TEXT,
                    key_learnings TEXT,
                    overall_feeling TEXT,
                    difficulty_rating INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Section-wise performance
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS mock_sections (
                    section_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mock_id INTEGER NOT NULL,
                    section_name TEXT NOT NULL,
                    section_order INTEGER,
                    questions_total INTEGER,
                    questions_attempted INTEGER,
                    questions_correct INTEGER,
                    questions_incorrect INTEGER,
                    questions_unattempted INTEGER,
                    section_score REAL,
                    max_section_score REAL,
                    time_allocated_minutes INTEGER,
                    time_taken_minutes INTEGER,
                    section_feedback TEXT,
                    confidence_level INTEGER,
                    topics_struggled TEXT,
                    topics_strong TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (mock_id) REFERENCES mock_tests(mock_id) ON DELETE CASCADE
                )
            """)
            
            # Section configuration
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS clat_section_config (
                    config_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    section_name TEXT NOT NULL UNIQUE,
                    section_order INTEGER,
                    default_questions INTEGER,
                    default_max_score REAL,
                    default_time_minutes INTEGER,
                    color TEXT,
                    icon TEXT
                )
            """)
            
            # Insert default section config
            for section in self.DEFAULT_SECTIONS:
                cursor.execute("""
                    INSERT OR IGNORE INTO clat_section_config 
                    (section_name, section_order, default_questions, default_max_score, default_time_minutes, color, icon)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (section['name'], section['order'], section['questions'], 
                      section['max_score'], section['time'], section['color'], section['icon']))
            
            # Create indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_mock_tests_user_date ON mock_tests(user_id, mock_date DESC)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_mock_sections_mock ON mock_sections(mock_id)")
            
            conn.commit()
        finally:
            conn.close()
    
    def get_section_config(self) -> List[Dict]:
        """Get CLAT section configuration"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT section_name, section_order, default_questions, 
                       default_max_score, default_time_minutes, color, icon
                FROM clat_section_config
                ORDER BY section_order
            """)
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()
    
    def create_mock(self, data: Dict, user_id: str = 'saanvi') -> int:
        """Create a new mock test entry with sections"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            # Calculate totals from sections if not provided
            sections = data.get('sections', [])
            if sections:
                data['total_attempted'] = sum(s.get('questions_attempted', 0) or 0 for s in sections)
                data['total_correct'] = sum(s.get('questions_correct', 0) or 0 for s in sections)
                data['total_incorrect'] = sum(s.get('questions_incorrect', 0) or 0 for s in sections)
                data['total_unattempted'] = sum(s.get('questions_unattempted', 0) or 0 for s in sections)
                data['total_score'] = sum(s.get('section_score', 0) or 0 for s in sections)
                data['time_taken_minutes'] = sum(s.get('time_taken_minutes', 0) or 0 for s in sections)
            
            # Insert main mock record
            cursor.execute("""
                INSERT INTO mock_tests (
                    user_id, mock_name, mock_source, mock_date, mock_type,
                    total_questions, total_attempted, total_correct, total_incorrect,
                    total_unattempted, total_score, max_score, percentile, rank,
                    total_time_minutes, time_taken_minutes,
                    what_went_well, areas_to_improve, key_learnings,
                    overall_feeling, difficulty_rating
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id,
                data.get('mock_name'),
                data.get('mock_source'),
                data.get('mock_date'),
                data.get('mock_type', 'full'),
                data.get('total_questions', 150),
                data.get('total_attempted'),
                data.get('total_correct'),
                data.get('total_incorrect'),
                data.get('total_unattempted'),
                data.get('total_score'),
                data.get('max_score', 150),
                data.get('percentile'),
                data.get('rank'),
                data.get('total_time_minutes', 120),
                data.get('time_taken_minutes'),
                data.get('what_went_well'),
                data.get('areas_to_improve'),
                data.get('key_learnings'),
                data.get('overall_feeling'),
                data.get('difficulty_rating')
            ))
            
            mock_id = cursor.lastrowid
            
            # Insert sections
            for section in sections:
                topics_struggled = json.dumps(section.get('topics_struggled', [])) if section.get('topics_struggled') else None
                topics_strong = json.dumps(section.get('topics_strong', [])) if section.get('topics_strong') else None
                
                cursor.execute("""
                    INSERT INTO mock_sections (
                        mock_id, section_name, section_order,
                        questions_total, questions_attempted, questions_correct,
                        questions_incorrect, questions_unattempted,
                        section_score, max_section_score,
                        time_allocated_minutes, time_taken_minutes,
                        section_feedback, confidence_level,
                        topics_struggled, topics_strong
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    mock_id,
                    section.get('section_name'),
                    section.get('section_order'),
                    section.get('questions_total'),
                    section.get('questions_attempted'),
                    section.get('questions_correct'),
                    section.get('questions_incorrect'),
                    section.get('questions_unattempted'),
                    section.get('section_score'),
                    section.get('max_section_score'),
                    section.get('time_allocated_minutes'),
                    section.get('time_taken_minutes'),
                    section.get('section_feedback'),
                    section.get('confidence_level'),
                    topics_struggled,
                    topics_strong
                ))
            
            conn.commit()
            return mock_id
        finally:
            conn.close()
    
    def get_mock(self, mock_id: int, user_id: str = 'saanvi') -> Optional[Dict]:
        """Get a single mock test with all sections"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            # Get main mock record
            cursor.execute("""
                SELECT * FROM mock_tests
                WHERE mock_id = ? AND user_id = ?
            """, (mock_id, user_id))
            
            row = cursor.fetchone()
            if not row:
                return None
            
            mock = dict(row)
            
            # Get sections
            cursor.execute("""
                SELECT * FROM mock_sections
                WHERE mock_id = ?
                ORDER BY section_order
            """, (mock_id,))
            
            sections = []
            for section_row in cursor.fetchall():
                section = dict(section_row)
                # Parse JSON fields
                if section.get('topics_struggled'):
                    try:
                        section['topics_struggled'] = json.loads(section['topics_struggled'])
                    except:
                        section['topics_struggled'] = []
                if section.get('topics_strong'):
                    try:
                        section['topics_strong'] = json.loads(section['topics_strong'])
                    except:
                        section['topics_strong'] = []
                sections.append(section)
            
            mock['sections'] = sections
            return mock
        finally:
            conn.close()
    
    def get_mocks(self, user_id: str = 'saanvi', limit: int = 50, 
                  offset: int = 0) -> List[Dict]:
        """Get list of mocks with basic info"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    m.mock_id, m.mock_name, m.mock_source, m.mock_date,
                    m.total_score, m.max_score, m.total_attempted, m.total_correct,
                    m.total_incorrect, m.time_taken_minutes, m.overall_feeling,
                    m.difficulty_rating,
                    ROUND((m.total_score * 100.0 / NULLIF(m.max_score, 0)), 1) as score_percentage,
                    ROUND((m.total_correct * 100.0 / NULLIF(m.total_attempted, 0)), 1) as accuracy
                FROM mock_tests m
                WHERE m.user_id = ?
                ORDER BY m.mock_date DESC, m.created_at DESC
                LIMIT ? OFFSET ?
            """, (user_id, limit, offset))
            
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()
    
    def get_mocks_with_sections(self, user_id: str = 'saanvi', 
                                limit: int = 7) -> List[Dict]:
        """Get mocks with section-wise breakdown for table display"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            # Get mocks
            cursor.execute("""
                SELECT * FROM mock_tests
                WHERE user_id = ?
                ORDER BY mock_date DESC, created_at DESC
                LIMIT ?
            """, (user_id, limit))
            
            mocks = []
            for row in cursor.fetchall():
                mock = dict(row)
                
                # Get sections for this mock
                cursor.execute("""
                    SELECT * FROM mock_sections
                    WHERE mock_id = ?
                    ORDER BY section_order
                """, (mock['mock_id'],))
                
                sections = []
                for section_row in cursor.fetchall():
                    section = dict(section_row)
                    if section.get('topics_struggled'):
                        try:
                            section['topics_struggled'] = json.loads(section['topics_struggled'])
                        except:
                            section['topics_struggled'] = []
                    sections.append(section)
                
                mock['sections'] = sections
                mock['score_percentage'] = round((mock['total_score'] or 0) * 100 / (mock['max_score'] or 150), 1)
                mock['accuracy'] = round((mock['total_correct'] or 0) * 100 / max(mock['total_attempted'] or 1, 1), 1)
                
                mocks.append(mock)
            
            return mocks
        finally:
            conn.close()
    
    def update_mock(self, mock_id: int, data: Dict, user_id: str = 'saanvi') -> bool:
        """Update a mock test entry"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            # Build update query dynamically
            allowed_fields = [
                'mock_name', 'mock_source', 'mock_date', 'mock_type',
                'total_questions', 'total_attempted', 'total_correct', 'total_incorrect',
                'total_unattempted', 'total_score', 'max_score', 'percentile', 'rank',
                'total_time_minutes', 'time_taken_minutes',
                'what_went_well', 'areas_to_improve', 'key_learnings',
                'overall_feeling', 'difficulty_rating'
            ]
            
            updates = []
            values = []
            for field in allowed_fields:
                if field in data:
                    updates.append(f"{field} = ?")
                    values.append(data[field])
            
            if not updates:
                return False
            
            updates.append("updated_at = CURRENT_TIMESTAMP")
            values.extend([mock_id, user_id])
            
            cursor.execute(f"""
                UPDATE mock_tests 
                SET {', '.join(updates)}
                WHERE mock_id = ? AND user_id = ?
            """, values)
            
            # Update sections if provided
            if 'sections' in data:
                # Delete existing sections
                cursor.execute("DELETE FROM mock_sections WHERE mock_id = ?", (mock_id,))
                
                # Insert new sections
                for section in data['sections']:
                    topics_struggled = json.dumps(section.get('topics_struggled', [])) if section.get('topics_struggled') else None
                    topics_strong = json.dumps(section.get('topics_strong', [])) if section.get('topics_strong') else None
                    
                    cursor.execute("""
                        INSERT INTO mock_sections (
                            mock_id, section_name, section_order,
                            questions_total, questions_attempted, questions_correct,
                            questions_incorrect, questions_unattempted,
                            section_score, max_section_score,
                            time_allocated_minutes, time_taken_minutes,
                            section_feedback, confidence_level,
                            topics_struggled, topics_strong
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        mock_id,
                        section.get('section_name'),
                        section.get('section_order'),
                        section.get('questions_total'),
                        section.get('questions_attempted'),
                        section.get('questions_correct'),
                        section.get('questions_incorrect'),
                        section.get('questions_unattempted'),
                        section.get('section_score'),
                        section.get('max_section_score'),
                        section.get('time_allocated_minutes'),
                        section.get('time_taken_minutes'),
                        section.get('section_feedback'),
                        section.get('confidence_level'),
                        topics_struggled,
                        topics_strong
                    ))
            
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()
    
    def delete_mock(self, mock_id: int, user_id: str = 'saanvi') -> bool:
        """Delete a mock test and its sections"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            # Sections will be deleted via CASCADE
            cursor.execute("""
                DELETE FROM mock_tests
                WHERE mock_id = ? AND user_id = ?
            """, (mock_id, user_id))
            
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()
    
    def get_stats(self, user_id: str = 'saanvi') -> Dict:
        """Get overall mock statistics for dashboard"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            # Overall stats
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_mocks,
                    ROUND(AVG(total_score), 1) as average_score,
                    MAX(total_score) as best_score,
                    MIN(total_score) as lowest_score,
                    ROUND(AVG(total_correct * 100.0 / NULLIF(total_attempted, 0)), 1) as avg_accuracy,
                    ROUND(AVG(time_taken_minutes), 0) as avg_time
                FROM mock_tests
                WHERE user_id = ?
            """, (user_id,))
            
            stats = dict(cursor.fetchone())
            
            # Recent trend (last 5 mocks)
            cursor.execute("""
                SELECT total_score, mock_date
                FROM mock_tests
                WHERE user_id = ?
                ORDER BY mock_date DESC
                LIMIT 5
            """, (user_id,))
            
            recent_scores = [dict(row) for row in cursor.fetchall()]
            stats['recent_scores'] = recent_scores
            
            # Calculate trend
            if len(recent_scores) >= 2:
                latest = recent_scores[0]['total_score'] or 0
                previous = recent_scores[-1]['total_score'] or 0
                stats['trend'] = 'up' if latest > previous else 'down' if latest < previous else 'stable'
            else:
                stats['trend'] = 'stable'
            
            # Section-wise averages
            cursor.execute("""
                SELECT 
                    ms.section_name,
                    COUNT(*) as mock_count,
                    ROUND(AVG(ms.section_score), 1) as avg_score,
                    ROUND(AVG(ms.questions_correct * 100.0 / NULLIF(ms.questions_attempted, 0)), 1) as avg_accuracy,
                    ROUND(AVG(ms.time_taken_minutes), 0) as avg_time,
                    ROUND(AVG(ms.confidence_level), 1) as avg_confidence
                FROM mock_sections ms
                JOIN mock_tests m ON ms.mock_id = m.mock_id
                WHERE m.user_id = ?
                GROUP BY ms.section_name
                ORDER BY ms.section_order
            """, (user_id,))
            
            stats['section_averages'] = [dict(row) for row in cursor.fetchall()]
            
            return stats
        finally:
            conn.close()
    
    def get_section_trends(self, user_id: str = 'saanvi', 
                          limit: int = 10) -> Dict[str, List]:
        """Get section-wise performance trends over last N mocks"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            # Get mock IDs in order
            cursor.execute("""
                SELECT mock_id, mock_date, mock_name
                FROM mock_tests
                WHERE user_id = ?
                ORDER BY mock_date DESC
                LIMIT ?
            """, (user_id, limit))
            
            mocks = [dict(row) for row in cursor.fetchall()]
            mock_ids = [m['mock_id'] for m in mocks]
            
            if not mock_ids:
                return {'mocks': [], 'sections': {}}
            
            # Get section scores for these mocks
            placeholders = ','.join(['?' for _ in mock_ids])
            cursor.execute(f"""
                SELECT 
                    ms.mock_id, ms.section_name, ms.section_score,
                    ms.questions_correct, ms.questions_attempted
                FROM mock_sections ms
                WHERE ms.mock_id IN ({placeholders})
                ORDER BY ms.mock_id, ms.section_order
            """, mock_ids)
            
            # Organize by section
            sections = {}
            for row in cursor.fetchall():
                r = dict(row)
                name = r['section_name']
                if name not in sections:
                    sections[name] = []
                sections[name].append({
                    'mock_id': r['mock_id'],
                    'score': r['section_score'],
                    'correct': r['questions_correct'],
                    'attempted': r['questions_attempted']
                })
            
            return {
                'mocks': mocks[::-1],  # Chronological order
                'sections': sections
            }
        finally:
            conn.close()

