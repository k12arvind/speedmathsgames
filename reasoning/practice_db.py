"""
Reasoning practice-session tracking + question bank.

This module stores Saanvi's analytical-reasoning practice exclusively.
There is no book reader (questions-only), so the schema is leaner than
the physics module — no books/chapters tables, no reading-progress.

Group / passage handling: many reasoning questions come in clusters
("Setup: ... Then 4 questions follow"). Those passages live once in
`reasoning_passages` and each sub-question carries `passage_id` +
`seq_in_passage`. Standalone questions have passage_id = NULL.

When the practice selector picks a passage-question, ALL its sibling
sub-questions are pulled in the same session (so the user always sees
the passage's full set together — never a stray sub-question without
its setup).

DB file: reasoning_practice.db (sibling of physics_practice.db)
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


class ReasoningPracticeDB:
    """Sessions, attempts, questions and topics for the reasoning module.

    Tables:
      - reasoning_practice_sessions   (one per attempted set)
      - reasoning_question_attempts   (one per Q within a session)
      - reasoning_passages            (group/setup text shared by N sub-Qs)
      - reasoning_questions           (the bank)
      - reasoning_question_topics     (topic tags, many-to-many)
    """

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = str(Path.home() / 'clat_preparation' / 'reasoning_practice.db')
        self.db_path = db_path
        self._init_tables()

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(self.db_path)
        c.row_factory = sqlite3.Row
        c.execute('PRAGMA foreign_keys = ON')
        return c

    # ------------------------------------------------------------------ schema
    def _init_tables(self) -> None:
        with self._conn() as c:
            c.executescript("""
            CREATE TABLE IF NOT EXISTS reasoning_practice_sessions (
                session_id           TEXT PRIMARY KEY,
                user_id              TEXT NOT NULL,
                created_at           TEXT NOT NULL,
                started_at           TEXT,
                finished_at          TEXT,
                status               TEXT NOT NULL DEFAULT 'in_progress',
                topic_filter         TEXT,
                subtopic_filter      TEXT,
                source_filter        TEXT,
                requested_count      INTEGER NOT NULL,
                served_count         INTEGER DEFAULT 0,
                correct_count        INTEGER DEFAULT 0,
                wrong_count          INTEGER DEFAULT 0,
                skipped_count        INTEGER DEFAULT 0,
                time_limit_seconds   INTEGER DEFAULT 0,
                elapsed_seconds      INTEGER,
                notes                TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_reasoning_sessions_user
                ON reasoning_practice_sessions(user_id, created_at DESC);

            CREATE TABLE IF NOT EXISTS reasoning_question_attempts (
                attempt_id           INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id           TEXT NOT NULL REFERENCES reasoning_practice_sessions(session_id) ON DELETE CASCADE,
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
            CREATE INDEX IF NOT EXISTS idx_reasoning_attempts_session
                ON reasoning_question_attempts(session_id);
            CREATE INDEX IF NOT EXISTS idx_reasoning_attempts_question
                ON reasoning_question_attempts(question_id);

            CREATE TABLE IF NOT EXISTS reasoning_passages (
                passage_id           INTEGER PRIMARY KEY AUTOINCREMENT,
                source_book          TEXT NOT NULL,        -- 'arihant' | 'mkpandey' | ...
                chapter_number       INTEGER,
                chapter_title        TEXT,
                passage_text         TEXT NOT NULL,
                figure_image_path    TEXT,                 -- if the passage itself has a diagram
                question_count       INTEGER NOT NULL DEFAULT 0,
                added_at             TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_reasoning_passages_source
                ON reasoning_passages(source_book, chapter_number);

            CREATE TABLE IF NOT EXISTS reasoning_questions (
                question_id          INTEGER PRIMARY KEY AUTOINCREMENT,
                source_book          TEXT NOT NULL,
                chapter_number       INTEGER,
                chapter_title        TEXT,
                problem_number       TEXT,
                passage_id           INTEGER REFERENCES reasoning_passages(passage_id) ON DELETE SET NULL,
                seq_in_passage       INTEGER,             -- 1, 2, 3 ... within the passage
                question_text        TEXT NOT NULL,
                choice_a             TEXT,
                choice_b             TEXT,
                choice_c             TEXT,
                choice_d             TEXT,
                choice_e             TEXT,
                correct_choice       TEXT,
                official_solution    TEXT,
                figure_image_path    TEXT,
                parse_status         TEXT DEFAULT 'ok',   -- ok | needs_review | failed
                correct_source       TEXT,                -- official | ai_solved | ...
                added_at             TEXT NOT NULL,
                updated_at           TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_reasoning_questions_source
                ON reasoning_questions(source_book, chapter_number);
            CREATE INDEX IF NOT EXISTS idx_reasoning_questions_passage
                ON reasoning_questions(passage_id, seq_in_passage);
            CREATE INDEX IF NOT EXISTS idx_reasoning_questions_status
                ON reasoning_questions(parse_status);

            CREATE TABLE IF NOT EXISTS reasoning_question_topics (
                tag_id               INTEGER PRIMARY KEY AUTOINCREMENT,
                question_id          INTEGER NOT NULL REFERENCES reasoning_questions(question_id) ON DELETE CASCADE,
                topic_code           TEXT NOT NULL,
                topic_name           TEXT,
                subtopic_code        TEXT,
                subtopic_name        TEXT,
                is_active            INTEGER NOT NULL DEFAULT 1
            );
            CREATE INDEX IF NOT EXISTS idx_reasoning_qtopics_q
                ON reasoning_question_topics(question_id);
            CREATE INDEX IF NOT EXISTS idx_reasoning_qtopics_topic
                ON reasoning_question_topics(topic_code, is_active);
            """)

    # ---------------------------------------------------------------- topics
    def topic_tree(self) -> List[Dict[str, Any]]:
        """Return topics → subtopics with practice-eligible counts."""
        with self._conn() as c:
            rows = c.execute("""
                SELECT t.topic_code, t.topic_name, t.subtopic_code, t.subtopic_name,
                       COUNT(*) AS n
                FROM reasoning_question_topics t
                JOIN reasoning_questions q ON q.question_id = t.question_id
                WHERE t.is_active = 1
                  AND q.parse_status NOT IN ('failed', 'needs_review')
                GROUP BY t.topic_code, t.subtopic_code
                ORDER BY t.topic_name, t.subtopic_name
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

    def list_sources(self) -> List[Dict[str, Any]]:
        """Distinct source books with practice-eligible Q counts."""
        with self._conn() as c:
            rows = c.execute("""
                SELECT source_book, COUNT(*) AS n
                FROM reasoning_questions
                WHERE parse_status NOT IN ('failed', 'needs_review')
                GROUP BY source_book
                ORDER BY source_book
            """).fetchall()
        return [dict(r) for r in rows]

    def total_question_count(self) -> int:
        with self._conn() as c:
            r = c.execute(
                "SELECT COUNT(*) AS n FROM reasoning_questions WHERE parse_status NOT IN ('failed','needs_review')"
            ).fetchone()
        return int(r['n']) if r else 0

    # -------------------------------------------------------------- sessions
    def create_session(self, *, user_id: str,
                       topic_filter: Optional[List[str]],
                       subtopic_filter: Optional[List[str]],
                       source_filter: Optional[List[str]],
                       requested_count: int,
                       time_limit_seconds: int) -> Dict[str, Any]:
        sid = str(uuid.uuid4())
        with self._conn() as c:
            qs = self._select_questions(c, topic_filter, subtopic_filter,
                                        source_filter, requested_count)
            served = len(qs)
            c.execute("""
                INSERT INTO reasoning_practice_sessions
                    (session_id, user_id, created_at, started_at, status,
                     topic_filter, subtopic_filter, source_filter,
                     requested_count, served_count, time_limit_seconds)
                VALUES (?, ?, ?, ?, 'in_progress', ?, ?, ?, ?, ?, ?)
            """, (sid, user_id, _now(), _now(),
                  json.dumps(topic_filter) if topic_filter else None,
                  json.dumps(subtopic_filter) if subtopic_filter else None,
                  json.dumps(source_filter) if source_filter else None,
                  requested_count, served, time_limit_seconds))
            for seq, q in enumerate(qs, 1):
                c.execute("""
                    INSERT INTO reasoning_question_attempts
                        (session_id, question_id, seq_in_session)
                    VALUES (?, ?, ?)
                """, (sid, q['question_id'], seq))
        return self.get_session(sid, user_id, include_correct=False)

    @staticmethod
    def _select_questions(c: sqlite3.Connection,
                          topic_filter: Optional[List[str]],
                          subtopic_filter: Optional[List[str]],
                          source_filter: Optional[List[str]],
                          requested_count: int) -> List[Dict[str, Any]]:
        """Pick `requested_count` questions matching filters. When a passage-
        linked question is picked, ALL its sibling sub-questions are added
        too (so the user sees the full setup intact)."""
        where = ["q.parse_status NOT IN ('failed', 'needs_review')"]
        params: List[Any] = []
        joins = ''
        if topic_filter or subtopic_filter:
            joins += ' LEFT JOIN reasoning_question_topics t ON t.question_id = q.question_id AND t.is_active = 1 '
            if topic_filter:
                where.append('t.topic_code IN (' + ','.join('?' * len(topic_filter)) + ')')
                params.extend(topic_filter)
            if subtopic_filter:
                where.append('t.subtopic_code IN (' + ','.join('?' * len(subtopic_filter)) + ')')
                params.extend(subtopic_filter)
        if source_filter:
            where.append('q.source_book IN (' + ','.join('?' * len(source_filter)) + ')')
            params.extend(source_filter)

        # Pull a generous candidate set, then iterate and gather passages.
        sql = f"""
            SELECT DISTINCT q.question_id, q.passage_id, q.seq_in_passage
            FROM reasoning_questions q
            {joins}
            WHERE {' AND '.join(where)}
            ORDER BY RANDOM()
            LIMIT ?
        """
        params.append(max(requested_count * 4, requested_count + 50))
        rows = c.execute(sql, params).fetchall()

        selected: List[Dict[str, Any]] = []
        seen_q_ids: set = set()
        seen_passages: set = set()

        for r in rows:
            if len(selected) >= requested_count:
                break
            qid = r['question_id']
            pid = r['passage_id']
            if qid in seen_q_ids:
                continue
            if pid:
                if pid in seen_passages:
                    continue
                seen_passages.add(pid)
                # Fetch ALL sub-questions in the passage, in order
                subs = c.execute("""
                    SELECT question_id, passage_id, seq_in_passage
                    FROM reasoning_questions
                    WHERE passage_id = ?
                      AND parse_status NOT IN ('failed','needs_review')
                    ORDER BY COALESCE(seq_in_passage, 9999), question_id
                """, (pid,)).fetchall()
                for s in subs:
                    if s['question_id'] not in seen_q_ids:
                        seen_q_ids.add(s['question_id'])
                        selected.append(dict(s))
            else:
                seen_q_ids.add(qid)
                selected.append(dict(r))

        return selected

    def get_session(self, session_id: str, user_id: str,
                    include_correct: bool = False) -> Dict[str, Any]:
        with self._conn() as c:
            sess = c.execute("""
                SELECT * FROM reasoning_practice_sessions
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
                       q.problem_number, q.source_book, q.chapter_number, q.chapter_title,
                       q.figure_image_path, q.correct_source,
                       q.passage_id, q.seq_in_passage,
                       q.question_text, q.choice_a, q.choice_b, q.choice_c, q.choice_d, q.choice_e,
                       p.passage_text, p.figure_image_path AS passage_figure_path,
                       (SELECT topic_name FROM reasoning_question_topics
                          WHERE question_id = q.question_id AND is_active = 1 LIMIT 1) AS topic_name,
                       (SELECT subtopic_name FROM reasoning_question_topics
                          WHERE question_id = q.question_id AND is_active = 1 LIMIT 1) AS subtopic_name
                       {extra}
                FROM reasoning_question_attempts a
                JOIN reasoning_questions q ON q.question_id = a.question_id
                LEFT JOIN reasoning_passages p ON p.passage_id = q.passage_id
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
            sess = c.execute(
                'SELECT user_id FROM reasoning_practice_sessions WHERE session_id = ?',
                (session_id,),
            ).fetchone()
            if not sess:
                raise ValueError(f'session {session_id} not found')
            if sess['user_id'] != user_id:
                raise PermissionError('not your session')

            correct = c.execute(
                'SELECT correct_choice FROM reasoning_questions WHERE question_id = ?',
                (question_id,),
            ).fetchone()
            if not correct:
                raise ValueError(f'question {question_id} not found')
            is_correct = (
                int(user_choice is not None and user_choice.upper() == (correct['correct_choice'] or '').upper())
                if user_choice else 0
            )
            c.execute("""
                UPDATE reasoning_question_attempts
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
            return {'is_correct': bool(is_correct), 'correct_choice': correct['correct_choice']}

    def finish_session(self, session_id: str, user_id: str) -> Dict[str, Any]:
        with self._conn() as c:
            sess = c.execute("""
                SELECT * FROM reasoning_practice_sessions WHERE session_id = ? AND user_id = ?
            """, (session_id, user_id)).fetchone()
            if not sess:
                raise ValueError(f'session {session_id} not found for {user_id}')

            stats = c.execute("""
                SELECT
                    SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END) AS correct_count,
                    SUM(CASE WHEN is_correct = 0 AND user_choice IS NOT NULL THEN 1 ELSE 0 END) AS wrong_count,
                    SUM(CASE WHEN user_choice IS NULL THEN 1 ELSE 0 END) AS skipped_count,
                    SUM(time_spent_seconds) AS total_seconds
                FROM reasoning_question_attempts WHERE session_id = ?
            """, (session_id,)).fetchone()

            started = sess['started_at']
            elapsed = stats['total_seconds'] or 0
            if started:
                try:
                    elapsed = max(elapsed, int((datetime.now(timezone.utc) - datetime.fromisoformat(started)).total_seconds()))
                except Exception:
                    pass

            c.execute("""
                UPDATE reasoning_practice_sessions
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
                       topic_filter
                FROM reasoning_practice_sessions
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
                FROM reasoning_practice_sessions s
                JOIN reasoning_question_attempts a ON a.session_id = s.session_id
                JOIN reasoning_question_topics t  ON t.question_id = a.question_id AND t.is_active = 1
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
                FROM reasoning_practice_sessions s
                LEFT JOIN reasoning_question_attempts a ON a.session_id = s.session_id
                WHERE s.user_id = ? AND s.created_at >= ?
                GROUP BY DATE(s.created_at)
                ORDER BY day DESC
            """, (user_id, cutoff)).fetchall()
            return [dict(r) for r in rows]

    def streak(self, user_id: str) -> int:
        with self._conn() as c:
            rows = c.execute("""
                SELECT DISTINCT DATE(s.created_at) AS day
                FROM reasoning_practice_sessions s
                JOIN reasoning_question_attempts a ON a.session_id = s.session_id
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
