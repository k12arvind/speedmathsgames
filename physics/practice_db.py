"""
Physics practice-session + book-reading tracking.

Mirrors `amc10/practice_db.py` so the UI can reuse the same shapes. Differences
from AMC10:

- Physics questions don't come from a contest series. The schema has a
  `physics_questions` table that stores difficulty directly (no problem-number
  proxy) and a `physics_question_topics` table for many-to-many topic tags.
- Books, chapters and reading-progress tables use the `physics_books*` prefix.
- Session/attempt tables use the `physics_*` prefix.

All tables share the same SQLite file: physics_practice.db
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class PhysicsPracticeDB:
    """Sessions, attempts, books and reading-progress for the Physics module.

    Tables:
      - physics_practice_sessions
      - physics_question_attempts
      - physics_book_view_sessions
      - physics_books
      - physics_book_chapters
      - physics_book_reading_progress  (rolled-up per user/chapter)
      - physics_questions
      - physics_question_topics
    """

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = str(Path.home() / 'clat_preparation' / 'physics_practice.db')
        self.db_path = db_path
        self._init_tables()

    # ------------------------------------------------------------------ infra
    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(self.db_path)
        c.row_factory = sqlite3.Row
        c.execute('PRAGMA foreign_keys = ON')
        return c

    def _init_tables(self) -> None:
        with self._conn() as c:
            c.executescript("""
            CREATE TABLE IF NOT EXISTS physics_practice_sessions (
                session_id           TEXT PRIMARY KEY,
                user_id              TEXT NOT NULL,
                created_at           TEXT NOT NULL,
                started_at           TEXT,
                finished_at          TEXT,
                status               TEXT NOT NULL DEFAULT 'in_progress',
                topic_filter         TEXT,
                subtopic_filter      TEXT,
                book_filter          TEXT,
                chapter_filter       TEXT,
                difficulty_band      TEXT,
                requested_count      INTEGER NOT NULL,
                served_count         INTEGER DEFAULT 0,
                correct_count        INTEGER DEFAULT 0,
                wrong_count          INTEGER DEFAULT 0,
                skipped_count        INTEGER DEFAULT 0,
                time_limit_seconds   INTEGER DEFAULT 0,
                elapsed_seconds      INTEGER,
                notes                TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_physics_sessions_user
                ON physics_practice_sessions(user_id, created_at DESC);

            CREATE TABLE IF NOT EXISTS physics_question_attempts (
                attempt_id           INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id           TEXT NOT NULL REFERENCES physics_practice_sessions(session_id) ON DELETE CASCADE,
                question_id          INTEGER NOT NULL,
                seq_in_session       INTEGER NOT NULL,
                user_choice          TEXT,
                is_correct           INTEGER,
                time_spent_seconds   INTEGER DEFAULT 0,
                flagged              INTEGER DEFAULT 0,
                revealed_solution    INTEGER DEFAULT 0,
                answered_at          TEXT,
                UNIQUE(session_id, seq_in_session)
            );
            CREATE INDEX IF NOT EXISTS idx_physics_attempts_session
                ON physics_question_attempts(session_id);
            CREATE INDEX IF NOT EXISTS idx_physics_attempts_question
                ON physics_question_attempts(question_id);

            CREATE TABLE IF NOT EXISTS physics_books (
                book_id              TEXT PRIMARY KEY,
                title                TEXT NOT NULL,
                pdf_filename         TEXT,
                total_pages          INTEGER NOT NULL,
                chapter_count        INTEGER NOT NULL,
                detection_method     TEXT,
                file_size_kb         INTEGER,
                added_at             TEXT NOT NULL,
                updated_at           TEXT
            );

            CREATE TABLE IF NOT EXISTS physics_book_chapters (
                chapter_id           INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id              TEXT NOT NULL REFERENCES physics_books(book_id) ON DELETE CASCADE,
                chapter_number       INTEGER NOT NULL,
                title                TEXT NOT NULL,
                page_start           INTEGER NOT NULL,
                page_end             INTEGER NOT NULL,
                html_filename        TEXT NOT NULL,
                UNIQUE(book_id, chapter_number)
            );
            CREATE INDEX IF NOT EXISTS idx_physics_book_chapters_book
                ON physics_book_chapters(book_id);

            CREATE TABLE IF NOT EXISTS physics_book_view_sessions (
                view_id              INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id              TEXT NOT NULL,
                book_id              TEXT NOT NULL,
                chapter_number       INTEGER,
                page_number          INTEGER,
                seconds_read         INTEGER NOT NULL,
                recorded_at          TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_physics_book_view_user
                ON physics_book_view_sessions(user_id, recorded_at DESC);
            CREATE INDEX IF NOT EXISTS idx_physics_book_view_book
                ON physics_book_view_sessions(user_id, book_id);

            CREATE TABLE IF NOT EXISTS physics_book_reading_progress (
                user_id              TEXT NOT NULL,
                book_id              TEXT NOT NULL,
                chapter_number       INTEGER NOT NULL,
                pages_seen           INTEGER NOT NULL DEFAULT 0,
                seconds_read         INTEGER NOT NULL DEFAULT 0,
                last_page_viewed     INTEGER,
                last_viewed_at       TEXT,
                completed            INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (user_id, book_id, chapter_number)
            );

            CREATE TABLE IF NOT EXISTS physics_questions (
                question_id          INTEGER PRIMARY KEY AUTOINCREMENT,
                source_book_id       TEXT,
                chapter_number       INTEGER,
                problem_number       TEXT,
                question_text        TEXT NOT NULL,
                choice_a             TEXT,
                choice_b             TEXT,
                choice_c             TEXT,
                choice_d             TEXT,
                choice_e             TEXT,
                correct_choice       TEXT,
                official_solution    TEXT,
                difficulty_band      TEXT DEFAULT 'medium',
                parse_status         TEXT DEFAULT 'ok',
                figure_image_path    TEXT,
                correct_source       TEXT,   -- 'official' | 'ai_solved' | NULL
                correct_confidence   TEXT,   -- 'high' | 'medium' | 'low' | NULL
                added_at             TEXT NOT NULL,
                updated_at           TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_physics_questions_book
                ON physics_questions(source_book_id, chapter_number);
            CREATE INDEX IF NOT EXISTS idx_physics_questions_diff
                ON physics_questions(difficulty_band);
            CREATE INDEX IF NOT EXISTS idx_physics_questions_status
                ON physics_questions(parse_status);

            CREATE TABLE IF NOT EXISTS physics_question_topics (
                tag_id               INTEGER PRIMARY KEY AUTOINCREMENT,
                question_id          INTEGER NOT NULL REFERENCES physics_questions(question_id) ON DELETE CASCADE,
                topic_code           TEXT NOT NULL,
                topic_name           TEXT,
                subtopic_code        TEXT,
                subtopic_name        TEXT,
                is_active            INTEGER NOT NULL DEFAULT 1
            );
            CREATE INDEX IF NOT EXISTS idx_physics_qtopics_q
                ON physics_question_topics(question_id);
            CREATE INDEX IF NOT EXISTS idx_physics_qtopics_topic
                ON physics_question_topics(topic_code, is_active);
            """)

            # Lightweight migration: add columns introduced after the table
            # was first created. SQLite doesn't error on `ADD COLUMN` if we
            # check first via PRAGMA.
            existing_cols = {row[1] for row in c.execute(
                "PRAGMA table_info(physics_questions)").fetchall()}
            for col, ddl in [
                ('figure_image_path', 'ALTER TABLE physics_questions ADD COLUMN figure_image_path TEXT'),
                ('correct_source',    'ALTER TABLE physics_questions ADD COLUMN correct_source TEXT'),
                ('correct_confidence','ALTER TABLE physics_questions ADD COLUMN correct_confidence TEXT'),
            ]:
                if col not in existing_cols:
                    c.execute(ddl)

    # ----------------------------------------------------------------- books
    def upsert_book(self, *, book_id: str, title: str, pdf_filename: Optional[str],
                    total_pages: int, chapter_count: int, detection_method: str,
                    file_size_kb: Optional[int]) -> None:
        with self._conn() as c:
            c.execute("""
                INSERT INTO physics_books (book_id, title, pdf_filename, total_pages,
                                           chapter_count, detection_method, file_size_kb,
                                           added_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(book_id) DO UPDATE SET
                    title = excluded.title,
                    pdf_filename = excluded.pdf_filename,
                    total_pages = excluded.total_pages,
                    chapter_count = excluded.chapter_count,
                    detection_method = excluded.detection_method,
                    file_size_kb = excluded.file_size_kb,
                    updated_at = excluded.updated_at
            """, (book_id, title, pdf_filename, total_pages, chapter_count,
                  detection_method, file_size_kb, _now(), _now()))

    def replace_book_chapters(self, book_id: str, chapters: List[Dict[str, Any]]) -> None:
        with self._conn() as c:
            c.execute('DELETE FROM physics_book_chapters WHERE book_id = ?', (book_id,))
            c.executemany("""
                INSERT INTO physics_book_chapters
                    (book_id, chapter_number, title, page_start, page_end, html_filename)
                VALUES (?, ?, ?, ?, ?, ?)
            """, [
                (book_id, ch['number'], ch['title'], ch['page_start'],
                 ch['page_end'], ch['html_filename'])
                for ch in chapters
            ])

    def list_books(self, user_id: str) -> List[Dict[str, Any]]:
        with self._conn() as c:
            rows = c.execute("""
                SELECT b.book_id, b.title, b.total_pages, b.chapter_count,
                       COALESCE(SUM(rp.seconds_read), 0)  AS total_seconds_read,
                       COALESCE(SUM(rp.pages_seen), 0)    AS pages_seen,
                       MAX(rp.last_viewed_at)             AS last_viewed_at
                FROM physics_books b
                LEFT JOIN physics_book_reading_progress rp
                       ON rp.book_id = b.book_id AND rp.user_id = ?
                GROUP BY b.book_id
                ORDER BY b.title
            """, (user_id,)).fetchall()
            return [dict(r) for r in rows]

    def list_chapters(self, book_id: str, user_id: str) -> List[Dict[str, Any]]:
        with self._conn() as c:
            rows = c.execute("""
                SELECT ch.chapter_number, ch.title, ch.page_start, ch.page_end, ch.html_filename,
                       COALESCE(rp.pages_seen, 0)    AS pages_seen,
                       COALESCE(rp.seconds_read, 0) AS seconds_read,
                       rp.last_page_viewed,
                       rp.completed
                FROM physics_book_chapters ch
                LEFT JOIN physics_book_reading_progress rp
                       ON rp.book_id = ch.book_id
                      AND rp.chapter_number = ch.chapter_number
                      AND rp.user_id = ?
                WHERE ch.book_id = ?
                ORDER BY ch.chapter_number
            """, (user_id, book_id)).fetchall()
            return [dict(r) for r in rows]

    def record_book_view(self, *, user_id: str, book_id: str,
                         chapter_number: int, page_number: int, seconds: int) -> None:
        if seconds <= 0:
            return
        with self._conn() as c:
            c.execute("""
                INSERT INTO physics_book_view_sessions
                    (user_id, book_id, chapter_number, page_number, seconds_read, recorded_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, book_id, chapter_number, page_number, seconds, _now()))
            existing = c.execute("""
                SELECT 1 FROM physics_book_view_sessions
                WHERE user_id=? AND book_id=? AND chapter_number=? AND page_number=?
                  AND view_id < (SELECT MAX(view_id) FROM physics_book_view_sessions
                                  WHERE user_id=? AND book_id=? AND chapter_number=? AND page_number=?)
                LIMIT 1
            """, (user_id, book_id, chapter_number, page_number,
                  user_id, book_id, chapter_number, page_number)).fetchone()
            new_page = 0 if existing else 1
            c.execute("""
                INSERT INTO physics_book_reading_progress
                    (user_id, book_id, chapter_number, pages_seen, seconds_read,
                     last_page_viewed, last_viewed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, book_id, chapter_number) DO UPDATE SET
                    pages_seen       = pages_seen + ?,
                    seconds_read     = seconds_read + excluded.seconds_read,
                    last_page_viewed = excluded.last_page_viewed,
                    last_viewed_at   = excluded.last_viewed_at
            """, (user_id, book_id, chapter_number, new_page, seconds,
                  page_number, _now(), new_page))

    # ---------------------------------------------------------------- topics
    def topic_tree(self) -> List[Dict[str, Any]]:
        with self._conn() as c:
            rows = c.execute("""
                SELECT topic_code, topic_name, subtopic_code, subtopic_name,
                       COUNT(*) AS n
                FROM physics_question_topics
                WHERE is_active = 1
                GROUP BY topic_code, subtopic_code
                ORDER BY topic_name, subtopic_name
            """).fetchall()
        topics: Dict[str, Dict[str, Any]] = {}
        for r in rows:
            t_code = r['topic_code']
            t = topics.setdefault(t_code, {
                'code': t_code, 'name': r['topic_name'],
                'count': 0, 'subtopics': [],
            })
            t['count'] += r['n']
            t['subtopics'].append({
                'code': r['subtopic_code'] or '',
                'name': r['subtopic_name'] or 'General',
                'count': r['n'],
            })
        return list(topics.values())

    # -------------------------------------------------------------- sessions
    def create_session(self, *, user_id: str, topic_filter: Optional[List[str]],
                       subtopic_filter: Optional[List[str]],
                       book_filter: Optional[List[str]],
                       chapter_filter: Optional[List[int]],
                       difficulty_band: Optional[str],
                       requested_count: int,
                       time_limit_seconds: int) -> Dict[str, Any]:
        sid = str(uuid.uuid4())
        with self._conn() as c:
            qs = self._select_questions(c, topic_filter, subtopic_filter,
                                        book_filter, chapter_filter,
                                        difficulty_band, requested_count, user_id)
            served = len(qs)
            c.execute("""
                INSERT INTO physics_practice_sessions
                    (session_id, user_id, created_at, started_at, status,
                     topic_filter, subtopic_filter, book_filter, chapter_filter,
                     difficulty_band, requested_count, served_count,
                     time_limit_seconds)
                VALUES (?, ?, ?, ?, 'in_progress', ?, ?, ?, ?, ?, ?, ?, ?)
            """, (sid, user_id, _now(), _now(),
                  json.dumps(topic_filter) if topic_filter else None,
                  json.dumps(subtopic_filter) if subtopic_filter else None,
                  json.dumps(book_filter) if book_filter else None,
                  json.dumps(chapter_filter) if chapter_filter else None,
                  difficulty_band,
                  requested_count, served, time_limit_seconds))
            for seq, q in enumerate(qs, 1):
                c.execute("""
                    INSERT INTO physics_question_attempts
                        (session_id, question_id, seq_in_session)
                    VALUES (?, ?, ?)
                """, (sid, q['question_id'], seq))
        return self.get_session(sid, user_id, include_correct=False)

    @staticmethod
    def _select_questions(c: sqlite3.Connection,
                          topic_filter: Optional[List[str]],
                          subtopic_filter: Optional[List[str]],
                          book_filter: Optional[List[str]],
                          chapter_filter: Optional[List[int]],
                          difficulty_band: Optional[str],
                          requested_count: int,
                          user_id: str) -> List[Dict[str, Any]]:
        del user_id
        # Exclude both hard-failed parses and questions flagged for review
        where = ["q.parse_status NOT IN ('failed', 'needs_review')"]
        params: List[Any] = []
        joins = ''
        if topic_filter or subtopic_filter:
            joins += ' LEFT JOIN physics_question_topics t ON t.question_id = q.question_id AND t.is_active = 1 '
            if topic_filter:
                where.append('t.topic_code IN (' + ','.join('?' * len(topic_filter)) + ')')
                params.extend(topic_filter)
            if subtopic_filter:
                where.append('t.subtopic_code IN (' + ','.join('?' * len(subtopic_filter)) + ')')
                params.extend(subtopic_filter)
        if book_filter:
            where.append('q.source_book_id IN (' + ','.join('?' * len(book_filter)) + ')')
            params.extend(book_filter)
        if chapter_filter:
            where.append('q.chapter_number IN (' + ','.join('?' * len(chapter_filter)) + ')')
            params.extend(chapter_filter)
        if difficulty_band in ('easy', 'medium', 'hard'):
            where.append('q.difficulty_band = ?')
            params.append(difficulty_band)

        sql = f"""
            SELECT DISTINCT q.question_id, q.problem_number,
                   q.source_book_id, q.chapter_number, q.difficulty_band
            FROM physics_questions q
            {joins}
            WHERE {' AND '.join(where)}
            ORDER BY RANDOM()
            LIMIT ?
        """
        params.append(requested_count)
        rows = c.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def get_session(self, session_id: str, user_id: str,
                    include_correct: bool = False) -> Dict[str, Any]:
        with self._conn() as c:
            sess = c.execute("""
                SELECT * FROM physics_practice_sessions
                WHERE session_id = ? AND user_id = ?
            """, (session_id, user_id)).fetchone()
            if not sess:
                raise ValueError(f'session {session_id} not found for {user_id}')
            sess = dict(sess)

            extra = ", q.correct_choice, q.official_solution" if include_correct else ""
            attempts = c.execute(f"""
                SELECT a.attempt_id, a.seq_in_session, a.question_id, a.user_choice,
                       a.is_correct, a.time_spent_seconds, a.flagged, a.revealed_solution,
                       a.answered_at,
                       q.problem_number, q.source_book_id, q.chapter_number,
                       q.difficulty_band,
                       q.figure_image_path, q.correct_source, q.correct_confidence,
                       q.question_text, q.choice_a, q.choice_b, q.choice_c, q.choice_d, q.choice_e,
                       b.title AS book_title,
                       ch.title AS chapter_title,
                       (SELECT topic_name FROM physics_question_topics
                          WHERE question_id = q.question_id AND is_active = 1 LIMIT 1) AS topic_name,
                       (SELECT subtopic_name FROM physics_question_topics
                          WHERE question_id = q.question_id AND is_active = 1 LIMIT 1) AS subtopic_name
                       {extra}
                FROM physics_question_attempts a
                JOIN physics_questions q ON q.question_id = a.question_id
                LEFT JOIN physics_books b ON b.book_id = q.source_book_id
                LEFT JOIN physics_book_chapters ch
                       ON ch.book_id = q.source_book_id AND ch.chapter_number = q.chapter_number
                WHERE a.session_id = ?
                ORDER BY a.seq_in_session
            """, (session_id,)).fetchall()
            sess['attempts'] = [dict(r) for r in attempts]
        return sess

    def submit_attempt(self, *, session_id: str, user_id: str,
                       question_id: int, user_choice: Optional[str],
                       time_spent_seconds: int,
                       flagged: bool = False,
                       revealed_solution: bool = False) -> Dict[str, Any]:
        with self._conn() as c:
            sess = c.execute("""
                SELECT user_id, status FROM physics_practice_sessions
                WHERE session_id = ?
            """, (session_id,)).fetchone()
            if not sess:
                raise ValueError(f'session {session_id} not found')
            if sess['user_id'] != user_id:
                raise PermissionError('not your session')

            correct = c.execute(
                'SELECT correct_choice FROM physics_questions WHERE question_id = ?',
                (question_id,)
            ).fetchone()
            if not correct:
                raise ValueError(f'question {question_id} not found')
            is_correct = (
                int(user_choice is not None and user_choice.upper() == (correct['correct_choice'] or '').upper())
                if user_choice else 0
            )
            c.execute("""
                UPDATE physics_question_attempts
                SET user_choice = ?, is_correct = ?,
                    time_spent_seconds = ?, flagged = ?,
                    revealed_solution = ?, answered_at = ?
                WHERE session_id = ? AND question_id = ?
            """, (
                (user_choice or '').upper() or None, is_correct,
                time_spent_seconds, int(flagged),
                int(revealed_solution), _now(),
                session_id, question_id,
            ))
            return {
                'is_correct': bool(is_correct),
                'correct_choice': correct['correct_choice'],
            }

    def finish_session(self, session_id: str, user_id: str) -> Dict[str, Any]:
        with self._conn() as c:
            sess = c.execute("""
                SELECT * FROM physics_practice_sessions WHERE session_id = ? AND user_id = ?
            """, (session_id, user_id)).fetchone()
            if not sess:
                raise ValueError(f'session {session_id} not found for {user_id}')

            stats = c.execute("""
                SELECT
                    SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END) AS correct_count,
                    SUM(CASE WHEN is_correct = 0 AND user_choice IS NOT NULL THEN 1 ELSE 0 END) AS wrong_count,
                    SUM(CASE WHEN user_choice IS NULL THEN 1 ELSE 0 END) AS skipped_count,
                    SUM(time_spent_seconds) AS total_seconds
                FROM physics_question_attempts
                WHERE session_id = ?
            """, (session_id,)).fetchone()

            started = sess['started_at']
            elapsed = stats['total_seconds'] or 0
            if started:
                try:
                    elapsed = max(elapsed, int((datetime.now(timezone.utc) - datetime.fromisoformat(started)).total_seconds()))
                except Exception:
                    pass

            c.execute("""
                UPDATE physics_practice_sessions
                SET finished_at = ?, status = 'completed',
                    correct_count = ?, wrong_count = ?, skipped_count = ?,
                    elapsed_seconds = ?
                WHERE session_id = ?
            """, (_now(), stats['correct_count'] or 0, stats['wrong_count'] or 0,
                  stats['skipped_count'] or 0, elapsed, session_id))

        return self.get_session(session_id, user_id, include_correct=True)

    def recent_sessions(self, user_id: str, limit: int = 25) -> List[Dict[str, Any]]:
        with self._conn() as c:
            rows = c.execute("""
                SELECT session_id, created_at, finished_at, status,
                       served_count, requested_count, correct_count,
                       wrong_count, skipped_count, elapsed_seconds,
                       topic_filter, difficulty_band
                FROM physics_practice_sessions
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (user_id, limit)).fetchall()
            out = []
            for r in rows:
                d = dict(r)
                d['topic_filter'] = json.loads(d['topic_filter']) if d['topic_filter'] else None
                out.append(d)
            return out

    def topic_mastery(self, user_id: str) -> List[Dict[str, Any]]:
        with self._conn() as c:
            rows = c.execute("""
                SELECT t.topic_code, t.topic_name,
                       COUNT(a.attempt_id) AS attempted,
                       SUM(CASE WHEN a.is_correct = 1 THEN 1 ELSE 0 END) AS correct
                FROM physics_practice_sessions s
                JOIN physics_question_attempts a ON a.session_id = s.session_id
                JOIN physics_question_topics t   ON t.question_id = a.question_id AND t.is_active = 1
                WHERE s.user_id = ? AND a.user_choice IS NOT NULL
                GROUP BY t.topic_code
                ORDER BY t.topic_name
            """, (user_id,)).fetchall()
            return [
                {**dict(r), 'accuracy': round((r['correct'] / r['attempted']) * 100, 1) if r['attempted'] else 0.0}
                for r in rows
            ]

    def daily_summary(self, user_id: str, days: int = 14) -> List[Dict[str, Any]]:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        with self._conn() as c:
            rows = c.execute("""
                SELECT DATE(s.created_at) AS day,
                       COUNT(DISTINCT s.session_id) AS sessions,
                       COUNT(a.attempt_id) AS attempted,
                       SUM(CASE WHEN a.is_correct = 1 THEN 1 ELSE 0 END) AS correct,
                       SUM(CASE WHEN a.user_choice IS NULL THEN 1 ELSE 0 END) AS skipped,
                       SUM(a.time_spent_seconds) AS total_seconds
                FROM physics_practice_sessions s
                LEFT JOIN physics_question_attempts a ON a.session_id = s.session_id
                WHERE s.user_id = ? AND s.created_at >= ?
                GROUP BY DATE(s.created_at)
                ORDER BY day DESC
            """, (user_id, cutoff)).fetchall()
            return [dict(r) for r in rows]

    def daily_reading_summary(self, user_id: str, days: int = 14) -> List[Dict[str, Any]]:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        with self._conn() as c:
            rows = c.execute("""
                SELECT DATE(recorded_at) AS day,
                       SUM(seconds_read) AS seconds,
                       COUNT(DISTINCT book_id || '|' || chapter_number || '|' || page_number) AS pages_seen
                FROM physics_book_view_sessions
                WHERE user_id = ? AND recorded_at >= ?
                GROUP BY DATE(recorded_at)
                ORDER BY day DESC
            """, (user_id, cutoff)).fetchall()
            return [dict(r) for r in rows]

    def books_in_progress(self, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        with self._conn() as c:
            rows = c.execute("""
                SELECT b.book_id, b.title, b.total_pages, b.chapter_count,
                       SUM(rp.pages_seen)   AS pages_seen,
                       SUM(rp.seconds_read) AS seconds_read,
                       MAX(rp.last_viewed_at) AS last_viewed_at
                FROM physics_books b
                JOIN physics_book_reading_progress rp ON rp.book_id = b.book_id
                WHERE rp.user_id = ? AND rp.pages_seen > 0
                GROUP BY b.book_id
                ORDER BY MAX(rp.last_viewed_at) DESC
                LIMIT ?
            """, (user_id, limit)).fetchall()
            return [dict(r) for r in rows]

    def lifetime_reading(self, user_id: str) -> Dict[str, Any]:
        with self._conn() as c:
            r = c.execute("""
                SELECT COALESCE(SUM(pages_seen), 0)     AS pages,
                       COALESCE(SUM(seconds_read), 0)   AS seconds,
                       COUNT(DISTINCT book_id)          AS books
                FROM physics_book_reading_progress
                WHERE user_id = ?
            """, (user_id,)).fetchone()
        return dict(r) if r else {'pages': 0, 'seconds': 0, 'books': 0}

    def streak(self, user_id: str) -> int:
        with self._conn() as c:
            rows = c.execute("""
                SELECT DISTINCT DATE(s.created_at) AS day
                FROM physics_practice_sessions s
                JOIN physics_question_attempts a ON a.session_id = s.session_id
                WHERE s.user_id = ?
                ORDER BY day DESC
            """, (user_id,)).fetchall()
        days = [r['day'] for r in rows]
        if not days:
            return 0
        today = datetime.now().date()
        streak = 0
        for offset, d in enumerate(days):
            target = (today - timedelta(days=offset)).isoformat()
            if d == target:
                streak += 1
            else:
                break
        return streak

    def total_question_count(self) -> int:
        with self._conn() as c:
            r = c.execute("SELECT COUNT(*) AS n FROM physics_questions WHERE parse_status != 'failed'").fetchone()
        return int(r['n']) if r else 0
