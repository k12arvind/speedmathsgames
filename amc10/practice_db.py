"""
AMC10 practice-session + book-reading tracking.

Separate from `amc10/db.py` (which is the question-bank ingestion layer)
because the ingestion code is finished and stable. Practice/reading state
lives here so the two concerns don't collide.

All tables share the same SQLite file: amc10_practice.db
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


class AMC10PracticeDB:
    """Sessions, attempts, books and reading-progress for the AMC10 module.

    Tables:
      - amc10_practice_sessions
      - amc10_question_attempts
      - amc10_book_view_sessions
      - math_books
      - math_book_chapters
      - math_book_reading_progress  (rolled-up per user/chapter)
    """

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = str(Path.home() / 'clat_preparation' / 'amc10_practice.db')
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
            CREATE TABLE IF NOT EXISTS amc10_practice_sessions (
                session_id           TEXT PRIMARY KEY,
                user_id              TEXT NOT NULL,
                created_at           TEXT NOT NULL,
                started_at           TEXT,
                finished_at          TEXT,
                status               TEXT NOT NULL DEFAULT 'in_progress',  -- in_progress | completed | abandoned
                topic_filter         TEXT,                                  -- JSON array
                subtopic_filter      TEXT,                                  -- JSON array
                contest_year_min     INTEGER,
                contest_year_max     INTEGER,
                difficulty_band      TEXT,                                  -- easy | medium | hard | mixed
                requested_count      INTEGER NOT NULL,
                served_count         INTEGER DEFAULT 0,
                correct_count        INTEGER DEFAULT 0,
                wrong_count          INTEGER DEFAULT 0,
                skipped_count        INTEGER DEFAULT 0,
                time_limit_seconds   INTEGER DEFAULT 0,                     -- 0 = untimed
                elapsed_seconds      INTEGER,
                notes                TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_amc10_sessions_user ON amc10_practice_sessions(user_id, created_at DESC);

            CREATE TABLE IF NOT EXISTS amc10_question_attempts (
                attempt_id           INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id           TEXT NOT NULL REFERENCES amc10_practice_sessions(session_id) ON DELETE CASCADE,
                question_id          INTEGER NOT NULL,
                seq_in_session       INTEGER NOT NULL,
                user_choice          TEXT,                                  -- A/B/C/D/E or NULL=skipped
                is_correct           INTEGER,
                time_spent_seconds   INTEGER DEFAULT 0,
                flagged              INTEGER DEFAULT 0,
                revealed_solution    INTEGER DEFAULT 0,
                answered_at          TEXT,
                UNIQUE(session_id, seq_in_session)
            );
            CREATE INDEX IF NOT EXISTS idx_amc10_attempts_session  ON amc10_question_attempts(session_id);
            CREATE INDEX IF NOT EXISTS idx_amc10_attempts_question ON amc10_question_attempts(question_id);

            CREATE TABLE IF NOT EXISTS math_books (
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

            CREATE TABLE IF NOT EXISTS math_book_chapters (
                chapter_id           INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id              TEXT NOT NULL REFERENCES math_books(book_id) ON DELETE CASCADE,
                chapter_number       INTEGER NOT NULL,
                title                TEXT NOT NULL,
                page_start           INTEGER NOT NULL,
                page_end             INTEGER NOT NULL,
                html_filename        TEXT NOT NULL,
                UNIQUE(book_id, chapter_number)
            );
            CREATE INDEX IF NOT EXISTS idx_book_chapters_book ON math_book_chapters(book_id);

            CREATE TABLE IF NOT EXISTS amc10_book_view_sessions (
                view_id              INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id              TEXT NOT NULL,
                book_id              TEXT NOT NULL,
                chapter_number       INTEGER,
                page_number          INTEGER,
                seconds_read         INTEGER NOT NULL,
                recorded_at          TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_book_view_user ON amc10_book_view_sessions(user_id, recorded_at DESC);
            CREATE INDEX IF NOT EXISTS idx_book_view_book ON amc10_book_view_sessions(user_id, book_id);

            CREATE TABLE IF NOT EXISTS math_book_reading_progress (
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
            """)

    # ----------------------------------------------------------------- books
    def upsert_book(self, *, book_id: str, title: str, pdf_filename: Optional[str],
                    total_pages: int, chapter_count: int, detection_method: str,
                    file_size_kb: Optional[int]) -> None:
        with self._conn() as c:
            c.execute("""
                INSERT INTO math_books (book_id, title, pdf_filename, total_pages,
                                        chapter_count, detection_method, file_size_kb, added_at, updated_at)
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
            c.execute('DELETE FROM math_book_chapters WHERE book_id = ?', (book_id,))
            c.executemany("""
                INSERT INTO math_book_chapters
                    (book_id, chapter_number, title, page_start, page_end, html_filename)
                VALUES (?, ?, ?, ?, ?, ?)
            """, [
                (book_id, ch['number'], ch['title'], ch['page_start'],
                 ch['page_end'], ch['html_filename'])
                for ch in chapters
            ])

    def list_books(self, user_id: str) -> List[Dict[str, Any]]:
        """List all books with this user's reading progress rolled up."""
        with self._conn() as c:
            rows = c.execute("""
                SELECT b.book_id, b.title, b.total_pages, b.chapter_count,
                       COALESCE(SUM(rp.seconds_read), 0)  AS total_seconds_read,
                       COALESCE(SUM(rp.pages_seen), 0)    AS pages_seen,
                       MAX(rp.last_viewed_at)             AS last_viewed_at
                FROM math_books b
                LEFT JOIN math_book_reading_progress rp
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
                FROM math_book_chapters ch
                LEFT JOIN math_book_reading_progress rp
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
                INSERT INTO amc10_book_view_sessions
                    (user_id, book_id, chapter_number, page_number, seconds_read, recorded_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, book_id, chapter_number, page_number, seconds, _now()))
            # Roll up per chapter — one new page seen if first time on this page
            existing = c.execute("""
                SELECT 1 FROM amc10_book_view_sessions
                WHERE user_id=? AND book_id=? AND chapter_number=? AND page_number=?
                  AND view_id < (SELECT MAX(view_id) FROM amc10_book_view_sessions
                                  WHERE user_id=? AND book_id=? AND chapter_number=? AND page_number=?)
                LIMIT 1
            """, (user_id, book_id, chapter_number, page_number,
                  user_id, book_id, chapter_number, page_number)).fetchone()
            new_page = 0 if existing else 1
            c.execute("""
                INSERT INTO math_book_reading_progress
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
        """Topics + subtopics + question counts, taken from the active tags."""
        with self._conn() as c:
            rows = c.execute("""
                SELECT topic_code, topic_name, subtopic_code, subtopic_name,
                       COUNT(*) AS n
                FROM amc10_question_topics
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
                       year_min: Optional[int], year_max: Optional[int],
                       difficulty_band: Optional[str],
                       requested_count: int,
                       time_limit_seconds: int) -> Dict[str, Any]:
        """Pick `requested_count` questions matching the filters, insert
        attempt-shell rows, return the session + question list (without
        revealing correct answers)."""
        sid = str(uuid.uuid4())
        with self._conn() as c:
            qs = self._select_questions(c, topic_filter, subtopic_filter,
                                        year_min, year_max, difficulty_band,
                                        requested_count, user_id)
            served = len(qs)
            c.execute("""
                INSERT INTO amc10_practice_sessions
                    (session_id, user_id, created_at, started_at, status,
                     topic_filter, subtopic_filter, contest_year_min, contest_year_max,
                     difficulty_band, requested_count, served_count,
                     time_limit_seconds)
                VALUES (?, ?, ?, ?, 'in_progress', ?, ?, ?, ?, ?, ?, ?, ?)
            """, (sid, user_id, _now(), _now(),
                  json.dumps(topic_filter) if topic_filter else None,
                  json.dumps(subtopic_filter) if subtopic_filter else None,
                  year_min, year_max, difficulty_band,
                  requested_count, served, time_limit_seconds))
            for seq, q in enumerate(qs, 1):
                c.execute("""
                    INSERT INTO amc10_question_attempts
                        (session_id, question_id, seq_in_session)
                    VALUES (?, ?, ?)
                """, (sid, q['question_id'], seq))
        return self.get_session(sid, user_id, include_correct=False)

    @staticmethod
    def _select_questions(c: sqlite3.Connection,
                          topic_filter: Optional[List[str]],
                          subtopic_filter: Optional[List[str]],
                          year_min: Optional[int], year_max: Optional[int],
                          difficulty_band: Optional[str],
                          requested_count: int,
                          user_id: str) -> List[Dict[str, Any]]:
        # user_id reserved for future "skip already-attempted" weighting
        del user_id
        # Difficulty proxy: AMC problem number ranges
        # 1-10 = easy, 11-20 = medium, 21-25 = hard
        diff_clauses = ''
        if difficulty_band == 'easy':
            diff_clauses = ' AND q.problem_number BETWEEN 1 AND 10 '
        elif difficulty_band == 'medium':
            diff_clauses = ' AND q.problem_number BETWEEN 11 AND 20 '
        elif difficulty_band == 'hard':
            diff_clauses = ' AND q.problem_number BETWEEN 21 AND 25 '

        where = ['t.is_active = 1', 'q.parse_status != \'failed\'']
        params: List[Any] = []
        if topic_filter:
            where.append('t.topic_code IN (' + ','.join('?' * len(topic_filter)) + ')')
            params.extend(topic_filter)
        if subtopic_filter:
            where.append('t.subtopic_code IN (' + ','.join('?' * len(subtopic_filter)) + ')')
            params.extend(subtopic_filter)
        if year_min is not None:
            where.append('co.year >= ?'); params.append(year_min)
        if year_max is not None:
            where.append('co.year <= ?'); params.append(year_max)

        sql = f"""
            SELECT DISTINCT q.question_id, q.problem_number,
                   co.year, co.season, co.contest_label,
                   t.topic_code, t.topic_name, t.subtopic_code, t.subtopic_name
            FROM amc10_questions q
            JOIN amc10_contests co ON co.contest_id = q.contest_id
            JOIN amc10_question_topics t ON t.question_id = q.question_id
            WHERE {' AND '.join(where)}
            {diff_clauses}
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
                SELECT * FROM amc10_practice_sessions
                WHERE session_id = ? AND user_id = ?
            """, (session_id, user_id)).fetchone()
            if not sess:
                raise ValueError(f'session {session_id} not found for {user_id}')
            sess = dict(sess)

            attempts = c.execute("""
                SELECT a.attempt_id, a.seq_in_session, a.question_id, a.user_choice,
                       a.is_correct, a.time_spent_seconds, a.flagged, a.revealed_solution,
                       a.answered_at,
                       q.problem_number, q.question_text, q.choice_a, q.choice_b,
                       q.choice_c, q.choice_d, q.choice_e,
                       co.year, co.season, co.contest_label,
                       t.topic_name, t.subtopic_name
                       {extra}
                FROM amc10_question_attempts a
                JOIN amc10_questions q ON q.question_id = a.question_id
                JOIN amc10_contests co ON co.contest_id = q.contest_id
                LEFT JOIN amc10_question_topics t
                       ON t.question_id = q.question_id AND t.is_active = 1
                WHERE a.session_id = ?
                ORDER BY a.seq_in_session
            """.format(extra=", q.correct_choice, q.official_solution" if include_correct else ""),
                                  (session_id,)).fetchall()
            sess['attempts'] = [dict(r) for r in attempts]
        return sess

    def submit_attempt(self, *, session_id: str, user_id: str,
                       question_id: int, user_choice: Optional[str],
                       time_spent_seconds: int,
                       flagged: bool = False,
                       revealed_solution: bool = False) -> Dict[str, Any]:
        with self._conn() as c:
            sess = c.execute("""
                SELECT user_id, status FROM amc10_practice_sessions
                WHERE session_id = ?
            """, (session_id,)).fetchone()
            if not sess:
                raise ValueError(f'session {session_id} not found')
            if sess['user_id'] != user_id:
                raise PermissionError('not your session')

            correct = c.execute(
                'SELECT correct_choice FROM amc10_questions WHERE question_id = ?',
                (question_id,)
            ).fetchone()
            if not correct:
                raise ValueError(f'question {question_id} not found')
            is_correct = (
                int(user_choice is not None and user_choice.upper() == (correct['correct_choice'] or '').upper())
                if user_choice else 0
            )
            c.execute("""
                UPDATE amc10_question_attempts
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
                SELECT * FROM amc10_practice_sessions WHERE session_id = ? AND user_id = ?
            """, (session_id, user_id)).fetchone()
            if not sess:
                raise ValueError(f'session {session_id} not found for {user_id}')

            stats = c.execute("""
                SELECT
                    SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END) AS correct_count,
                    SUM(CASE WHEN is_correct = 0 AND user_choice IS NOT NULL THEN 1 ELSE 0 END) AS wrong_count,
                    SUM(CASE WHEN user_choice IS NULL THEN 1 ELSE 0 END) AS skipped_count,
                    SUM(time_spent_seconds) AS total_seconds
                FROM amc10_question_attempts
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
                UPDATE amc10_practice_sessions
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
                FROM amc10_practice_sessions
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
                FROM amc10_practice_sessions s
                JOIN amc10_question_attempts a ON a.session_id = s.session_id
                JOIN amc10_question_topics t   ON t.question_id = a.question_id AND t.is_active = 1
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
                FROM amc10_practice_sessions s
                LEFT JOIN amc10_question_attempts a ON a.session_id = s.session_id
                WHERE s.user_id = ? AND s.created_at >= ?
                GROUP BY DATE(s.created_at)
                ORDER BY day DESC
            """, (user_id, cutoff)).fetchall()
            return [dict(r) for r in rows]

    def daily_reading_summary(self, user_id: str, days: int = 14) -> List[Dict[str, Any]]:
        """Per-day pages read and seconds spent across all books."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        with self._conn() as c:
            rows = c.execute("""
                SELECT DATE(recorded_at) AS day,
                       SUM(seconds_read) AS seconds,
                       COUNT(DISTINCT book_id || '|' || chapter_number || '|' || page_number) AS pages_seen
                FROM amc10_book_view_sessions
                WHERE user_id = ? AND recorded_at >= ?
                GROUP BY DATE(recorded_at)
                ORDER BY day DESC
            """, (user_id, cutoff)).fetchall()
            return [dict(r) for r in rows]

    def books_in_progress(self, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Books the user has started but not finished, sorted by most recent."""
        with self._conn() as c:
            rows = c.execute("""
                SELECT b.book_id, b.title, b.total_pages, b.chapter_count,
                       SUM(rp.pages_seen)   AS pages_seen,
                       SUM(rp.seconds_read) AS seconds_read,
                       MAX(rp.last_viewed_at) AS last_viewed_at
                FROM math_books b
                JOIN math_book_reading_progress rp ON rp.book_id = b.book_id
                WHERE rp.user_id = ? AND rp.pages_seen > 0
                GROUP BY b.book_id
                ORDER BY MAX(rp.last_viewed_at) DESC
                LIMIT ?
            """, (user_id, limit)).fetchall()
            return [dict(r) for r in rows]

    def lifetime_reading(self, user_id: str) -> Dict[str, Any]:
        """Total pages, seconds, and number of distinct books touched."""
        with self._conn() as c:
            r = c.execute("""
                SELECT COALESCE(SUM(pages_seen), 0)     AS pages,
                       COALESCE(SUM(seconds_read), 0)   AS seconds,
                       COUNT(DISTINCT book_id)          AS books
                FROM math_book_reading_progress
                WHERE user_id = ?
            """, (user_id,)).fetchone()
        return dict(r) if r else {'pages': 0, 'seconds': 0, 'books': 0}

    def streak(self, user_id: str) -> int:
        """Consecutive days (including today) with at least one practice attempt."""
        with self._conn() as c:
            rows = c.execute("""
                SELECT DISTINCT DATE(s.created_at) AS day
                FROM amc10_practice_sessions s
                JOIN amc10_question_attempts a ON a.session_id = s.session_id
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
