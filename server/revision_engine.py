"""
Revision Engine — manages settings, schedules, and queue generation
for the spaced-repetition revision system.
"""

import sqlite3
import json
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any


# ============================================================
# DEFAULT SETTINGS
# ============================================================

DEFAULTS = {
    # Daily workload
    'daily_new_sections': {'value': 6, 'type': 'number', 'category': 'workload',
        'label': 'New sections per day', 'description': 'How many sections from unread PDFs to show per day',
        'min': 0, 'max': 30},
    'daily_revision_sections': {'value': 8, 'type': 'number', 'category': 'workload',
        'label': 'Revision sections per day', 'description': 'Max revision sections due per day',
        'min': 0, 'max': 30},
    'daily_total_cap': {'value': 14, 'type': 'number', 'category': 'workload',
        'label': 'Total daily cap', 'description': 'Hard cap on total sections (new + revision)',
        'min': 5, 'max': 50},
    'minutes_per_section': {'value': 4, 'type': 'number', 'category': 'workload',
        'label': 'Est. time per section (min)', 'description': 'For time estimate display',
        'min': 1, 'max': 15},

    # Revision buckets
    'bucket_recent_days': {'value': 30, 'type': 'number', 'category': 'buckets',
        'label': 'Recent bucket range (days)', 'description': 'PDFs read within this many days',
        'min': 7, 'max': 90},
    'bucket_recent_priority': {'value': 'high', 'type': 'select', 'category': 'buckets',
        'label': 'Recent bucket priority', 'options': ['high', 'medium', 'low']},
    'bucket_recent_interval': {'value': 7, 'type': 'number', 'category': 'buckets',
        'label': 'Recent default interval (days)', 'min': 1, 'max': 30},
    'bucket_older_days': {'value': 90, 'type': 'number', 'category': 'buckets',
        'label': 'Older bucket range (days)', 'min': 30, 'max': 180},
    'bucket_older_priority': {'value': 'medium', 'type': 'select', 'category': 'buckets',
        'label': 'Older bucket priority', 'options': ['high', 'medium', 'low']},
    'bucket_older_interval': {'value': 14, 'type': 'number', 'category': 'buckets',
        'label': 'Older default interval (days)', 'min': 7, 'max': 60},
    'bucket_archive_priority': {'value': 'low', 'type': 'select', 'category': 'buckets',
        'label': 'Archive bucket priority', 'options': ['high', 'medium', 'low']},
    'bucket_archive_interval': {'value': 30, 'type': 'number', 'category': 'buckets',
        'label': 'Archive default interval (days)', 'min': 14, 'max': 90},

    # New PDF definition
    'new_pdf_window_days': {'value': 30, 'type': 'number', 'category': 'new_pdfs',
        'label': 'New PDF window (days)', 'description': 'PDFs within this window are "new"',
        'min': 7, 'max': 90},
    'new_over_revision': {'value': True, 'type': 'boolean', 'category': 'new_pdfs',
        'label': 'Prioritize new over revision'},
    'new_revision_ratio': {'value': '1:2', 'type': 'text', 'category': 'new_pdfs',
        'label': 'New-to-revision ratio', 'description': 'e.g., 1:2 means 1 new per 2 revision'},

    # SRS intervals
    'srs_excellent_multiplier': {'value': 2.0, 'type': 'number', 'category': 'srs',
        'label': 'After 85%+ test: multiply interval by', 'min': 1.5, 'max': 3.0},
    'srs_good_interval': {'value': 7, 'type': 'number', 'category': 'srs',
        'label': 'After 70-84% test: interval (days)', 'min': 3, 'max': 14},
    'srs_weak_interval': {'value': 3, 'type': 'number', 'category': 'srs',
        'label': 'After 50-69% test: interval (days)', 'min': 1, 'max': 7},
    'srs_poor_interval': {'value': 1, 'type': 'number', 'category': 'srs',
        'label': 'After <50% test: interval (days)', 'min': 1, 'max': 3},
    'srs_read_only_interval': {'value': 7, 'type': 'number', 'category': 'srs',
        'label': 'After read, no test: interval (days)', 'min': 3, 'max': 14},
    'srs_mark_revised_interval': {'value': 5, 'type': 'number', 'category': 'srs',
        'label': 'After "Mark as Revised": interval (days)', 'min': 3, 'max': 14},
    'srs_mastery_threshold': {'value': 85, 'type': 'number', 'category': 'srs',
        'label': 'Mastery threshold (%)', 'min': 70, 'max': 95},
    'srs_mastery_consecutive': {'value': 3, 'type': 'number', 'category': 'srs',
        'label': 'Consecutive good for mastery', 'min': 2, 'max': 5},
    'srs_max_interval': {'value': 60, 'type': 'number', 'category': 'srs',
        'label': 'Max interval (days)', 'min': 30, 'max': 180},
    'srs_mastered_interval': {'value': 60, 'type': 'number', 'category': 'srs',
        'label': 'Mastered section interval (days)', 'min': 30, 'max': 90},

    # Category weights
    'weight_polity': {'value': 1.3, 'type': 'number', 'category': 'weights',
        'label': 'Polity & Constitution', 'min': 0.5, 'max': 2.0},
    'weight_international': {'value': 1.3, 'type': 'number', 'category': 'weights',
        'label': 'International Affairs', 'min': 0.5, 'max': 2.0},
    'weight_supreme_court': {'value': 1.3, 'type': 'number', 'category': 'weights',
        'label': 'Supreme Court / HC Judgements', 'min': 0.5, 'max': 2.0},
    'weight_economy': {'value': 1.2, 'type': 'number', 'category': 'weights',
        'label': 'Economy & Business', 'min': 0.5, 'max': 2.0},
    'weight_environment': {'value': 1.1, 'type': 'number', 'category': 'weights',
        'label': 'Environment & Science', 'min': 0.5, 'max': 2.0},
    'weight_awards': {'value': 1.0, 'type': 'number', 'category': 'weights',
        'label': 'Awards / Sports / Defence', 'min': 0.5, 'max': 2.0},
    'weight_government': {'value': 1.0, 'type': 'number', 'category': 'weights',
        'label': 'Government Schemes & Reports', 'min': 0.5, 'max': 2.0},
    'weight_static': {'value': 0.8, 'type': 'number', 'category': 'weights',
        'label': 'Static GK', 'min': 0.5, 'max': 2.0},
    'weakness_boost_threshold': {'value': 83, 'type': 'number', 'category': 'weights',
        'label': 'Weakness boost threshold (%)', 'min': 70, 'max': 90},
    'weakness_boost_multiplier': {'value': 1.2, 'type': 'number', 'category': 'weights',
        'label': 'Weakness boost multiplier', 'min': 1.0, 'max': 1.5},

    # Schedule overrides
    'weekend_mode': {'value': 'reduced', 'type': 'select', 'category': 'schedule',
        'label': 'Weekend mode', 'options': ['normal', 'reduced', 'off']},
    'weekend_load_percent': {'value': 50, 'type': 'number', 'category': 'schedule',
        'label': 'Weekend load (%)', 'min': 0, 'max': 100},
    'holiday_dates': {'value': [], 'type': 'text[]', 'category': 'schedule',
        'label': 'Holiday dates', 'description': 'Dates with reduced load'},
    'holiday_load_percent': {'value': 25, 'type': 'number', 'category': 'schedule',
        'label': 'Holiday load (%)', 'min': 0, 'max': 100},
    'exam_date': {'value': None, 'type': 'date', 'category': 'schedule',
        'label': 'CLAT Exam date'},
    'intensity_ramp': {'value': True, 'type': 'boolean', 'category': 'schedule',
        'label': 'Increase load as exam approaches'},
    'ramp_start_days': {'value': 60, 'type': 'number', 'category': 'schedule',
        'label': 'Ramp start (days before exam)', 'min': 14, 'max': 120},
    'ramp_peak_multiplier': {'value': 1.5, 'type': 'number', 'category': 'schedule',
        'label': 'Peak load multiplier', 'min': 1.0, 'max': 2.5},

    # Display
    'show_mastered': {'value': False, 'type': 'boolean', 'category': 'display',
        'label': 'Show mastered sections on dashboard'},
    'group_by_category': {'value': False, 'type': 'boolean', 'category': 'display',
        'label': 'Group queue by category (vs urgency)'},
    'show_time_estimates': {'value': True, 'type': 'boolean', 'category': 'display',
        'label': 'Show time estimates'},
    'revision_test_count': {'value': 20, 'type': 'number', 'category': 'display',
        'label': 'Max questions in revision test', 'min': 5, 'max': 50},
}

# Map category names to weight setting keys
CATEGORY_WEIGHT_MAP = {
    'National': 'weight_government',
    'Polity & Constitution': 'weight_polity',
    'International Affairs': 'weight_international',
    'Supreme Court / High Court Judgements': 'weight_supreme_court',
    'Economy & Business': 'weight_economy',
    'Environment & Science': 'weight_environment',
    'Awards / Sports / Defence': 'weight_awards',
    'Government Schemes & Reports': 'weight_government',
    'Static GK': 'weight_static',
    'General': 'weight_static',
    'General Knowledge': 'weight_static',
}

PRIORITY_SORT = {'high': 3, 'medium': 2, 'low': 1}


class RevisionEngine:
    """Manages revision settings, schedules, and daily queue generation."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_tables()
        self._ensure_defaults()

    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_tables(self):
        conn = self._conn()
        c = conn.cursor()

        c.execute("""
            CREATE TABLE IF NOT EXISTS revision_settings (
                setting_key TEXT PRIMARY KEY,
                setting_value TEXT NOT NULL,
                setting_type TEXT NOT NULL,
                category TEXT NOT NULL,
                label TEXT NOT NULL,
                description TEXT,
                min_value REAL,
                max_value REAL,
                options TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS revision_schedule (
                schedule_id INTEGER PRIMARY KEY AUTOINCREMENT,
                pdf_filename TEXT NOT NULL,
                section_index INTEGER NOT NULL,
                section_title TEXT,
                category TEXT,

                first_read_date DATE,
                last_read_date DATE,
                total_reads INTEGER DEFAULT 0,

                last_test_date DATE,
                last_test_accuracy REAL,
                best_test_accuracy REAL,
                total_tests INTEGER DEFAULT 0,

                revision_level INTEGER DEFAULT 0,
                current_interval_days INTEGER DEFAULT 1,
                next_review_date DATE,

                is_mastered BOOLEAN DEFAULT 0,
                consecutive_good_tests INTEGER DEFAULT 0,

                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                UNIQUE(pdf_filename, section_index)
            )
        """)

        c.execute("CREATE INDEX IF NOT EXISTS idx_revision_next_date ON revision_schedule(next_review_date)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_revision_level ON revision_schedule(revision_level)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_revision_category ON revision_schedule(category)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_revision_pdf ON revision_schedule(pdf_filename)")

        conn.commit()
        conn.close()

    def _ensure_defaults(self):
        """Insert default settings for any missing keys."""
        conn = self._conn()
        c = conn.cursor()
        for key, meta in DEFAULTS.items():
            c.execute("SELECT 1 FROM revision_settings WHERE setting_key = ?", (key,))
            if not c.fetchone():
                c.execute("""
                    INSERT INTO revision_settings
                    (setting_key, setting_value, setting_type, category, label, description,
                     min_value, max_value, options)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    key,
                    json.dumps(meta['value']),
                    meta['type'],
                    meta['category'],
                    meta['label'],
                    meta.get('description', ''),
                    meta.get('min'),
                    meta.get('max'),
                    json.dumps(meta.get('options')) if meta.get('options') else None,
                ))
        conn.commit()
        conn.close()

    # ── Settings CRUD ──────────────────────────────────────

    def get_all_settings(self) -> Dict[str, Any]:
        conn = self._conn()
        c = conn.cursor()
        c.execute("SELECT * FROM revision_settings ORDER BY category, setting_key")
        settings = {}
        for r in c.fetchall():
            d = dict(r)
            d['setting_value'] = json.loads(d['setting_value'])
            if d['options']:
                d['options'] = json.loads(d['options'])
            settings[d['setting_key']] = d
        conn.close()
        return settings

    def get_setting(self, key: str) -> Any:
        conn = self._conn()
        c = conn.cursor()
        c.execute("SELECT setting_value FROM revision_settings WHERE setting_key = ?", (key,))
        row = c.fetchone()
        conn.close()
        if row:
            return json.loads(row['setting_value'])
        return DEFAULTS.get(key, {}).get('value')

    def update_settings(self, updates: Dict[str, Any]) -> int:
        conn = self._conn()
        c = conn.cursor()
        count = 0
        for key, value in updates.items():
            c.execute("""
                UPDATE revision_settings
                SET setting_value = ?, updated_at = CURRENT_TIMESTAMP
                WHERE setting_key = ?
            """, (json.dumps(value), key))
            count += c.rowcount
        conn.commit()
        conn.close()
        return count

    def reset_all_settings(self):
        conn = self._conn()
        c = conn.cursor()
        for key, meta in DEFAULTS.items():
            c.execute("""
                UPDATE revision_settings
                SET setting_value = ?, updated_at = CURRENT_TIMESTAMP
                WHERE setting_key = ?
            """, (json.dumps(meta['value']), key))
        conn.commit()
        conn.close()

    # ── Schedule Management ────────────────────────────────

    def update_section_after_test(self, pdf_filename: str, section_index: int,
                                  section_title: str, category: str, accuracy: float):
        """Update revision schedule for a section after a test."""
        conn = self._conn()
        c = conn.cursor()

        # Load SRS settings
        mastery_threshold = self.get_setting('srs_mastery_threshold')
        mastery_consecutive = self.get_setting('srs_mastery_consecutive')
        max_interval = self.get_setting('srs_max_interval')

        # Get existing schedule
        c.execute("""
            SELECT * FROM revision_schedule
            WHERE pdf_filename = ? AND section_index = ?
        """, (pdf_filename, section_index))
        existing = c.fetchone()

        today = date.today().isoformat()

        if existing:
            existing = dict(existing)
            current_interval = existing['current_interval_days'] or 1
            consecutive = existing['consecutive_good_tests'] or 0
            best = existing['best_test_accuracy'] or 0

            # Calculate new interval based on accuracy
            if accuracy >= mastery_threshold:
                new_interval = min(int(current_interval * self.get_setting('srs_excellent_multiplier')), max_interval)
                consecutive += 1
            elif accuracy >= 70:
                new_interval = self.get_setting('srs_good_interval')
                consecutive = 0
            elif accuracy >= 50:
                new_interval = self.get_setting('srs_weak_interval')
                consecutive = 0
            else:
                new_interval = self.get_setting('srs_poor_interval')
                consecutive = 0

            # Mastery check
            is_mastered = consecutive >= mastery_consecutive
            if is_mastered:
                new_interval = self.get_setting('srs_mastered_interval')

            # Level
            if accuracy >= mastery_threshold:
                level = 1
            elif accuracy >= 70:
                level = 2
            elif accuracy >= 50:
                level = 3
            else:
                level = 4

            next_review = (date.today() + timedelta(days=new_interval)).isoformat()

            c.execute("""
                UPDATE revision_schedule SET
                    last_test_date = ?,
                    last_test_accuracy = ?,
                    best_test_accuracy = MAX(COALESCE(best_test_accuracy, 0), ?),
                    total_tests = total_tests + 1,
                    revision_level = ?,
                    current_interval_days = ?,
                    next_review_date = ?,
                    is_mastered = ?,
                    consecutive_good_tests = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE schedule_id = ?
            """, (today, accuracy, accuracy, level, new_interval, next_review,
                  is_mastered, consecutive, existing['schedule_id']))
        else:
            # New entry
            if accuracy >= mastery_threshold:
                interval = self.get_setting('srs_good_interval')
                level = 1
            elif accuracy >= 70:
                interval = self.get_setting('srs_good_interval')
                level = 2
            elif accuracy >= 50:
                interval = self.get_setting('srs_weak_interval')
                level = 3
            else:
                interval = self.get_setting('srs_poor_interval')
                level = 4

            next_review = (date.today() + timedelta(days=interval)).isoformat()

            c.execute("""
                INSERT INTO revision_schedule
                (pdf_filename, section_index, section_title, category,
                 first_read_date, last_test_date, last_test_accuracy,
                 best_test_accuracy, total_tests, revision_level,
                 current_interval_days, next_review_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
            """, (pdf_filename, section_index, section_title, category,
                  today, today, accuracy, accuracy, level, interval, next_review))

        conn.commit()
        conn.close()

    def mark_section_read(self, pdf_filename: str, section_index: int,
                          section_title: str = '', category: str = ''):
        """Record that a section was read (view tracked)."""
        conn = self._conn()
        c = conn.cursor()
        today = date.today().isoformat()
        read_interval = self.get_setting('srs_read_only_interval')
        next_review = (date.today() + timedelta(days=read_interval)).isoformat()

        c.execute("""
            INSERT INTO revision_schedule
            (pdf_filename, section_index, section_title, category,
             first_read_date, last_read_date, total_reads,
             next_review_date, current_interval_days)
            VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
            ON CONFLICT(pdf_filename, section_index) DO UPDATE SET
                last_read_date = ?,
                total_reads = total_reads + 1,
                next_review_date = CASE
                    WHEN next_review_date IS NULL OR next_review_date < ? THEN ?
                    ELSE next_review_date
                END,
                updated_at = CURRENT_TIMESTAMP
        """, (pdf_filename, section_index, section_title, category,
              today, today, next_review, read_interval,
              today, today, next_review))
        conn.commit()
        conn.close()

    def mark_section_revised(self, pdf_filename: str, section_index: int):
        """Mark a section as revised (manual button click)."""
        conn = self._conn()
        c = conn.cursor()
        today = date.today().isoformat()
        interval = self.get_setting('srs_mark_revised_interval')
        next_review = (date.today() + timedelta(days=interval)).isoformat()

        c.execute("""
            UPDATE revision_schedule SET
                last_read_date = ?,
                total_reads = total_reads + 1,
                next_review_date = ?,
                current_interval_days = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE pdf_filename = ? AND section_index = ?
        """, (today, next_review, interval, pdf_filename, section_index))
        conn.commit()
        conn.close()

    # ── Queue Generation ───────────────────────────────────

    def get_daily_queue(self) -> Dict:
        """Generate today's revision queue based on settings."""
        settings = self.get_all_settings()
        s = {k: v['setting_value'] for k, v in settings.items()}

        today = date.today()
        today_str = today.isoformat()
        day_of_week = today.weekday()  # 0=Mon, 5=Sat, 6=Sun

        # Calculate today's capacity
        base_cap = s['daily_total_cap']
        load_factor = 1.0

        # Weekend adjustment
        if day_of_week >= 5 and s['weekend_mode'] != 'normal':
            if s['weekend_mode'] == 'off':
                load_factor = 0
            else:
                load_factor = s['weekend_load_percent'] / 100

        # Holiday adjustment
        if today_str in (s.get('holiday_dates') or []):
            load_factor = min(load_factor, s['holiday_load_percent'] / 100)

        # Exam ramp
        if s.get('exam_date') and s.get('intensity_ramp'):
            try:
                exam = date.fromisoformat(s['exam_date'])
                days_left = (exam - today).days
                if 0 < days_left <= s['ramp_start_days']:
                    progress = 1 - (days_left / s['ramp_start_days'])
                    ramp = 1.0 + progress * (s['ramp_peak_multiplier'] - 1.0)
                    load_factor *= ramp
            except Exception:
                pass

        effective_cap = max(0, int(base_cap * load_factor))
        revision_cap = min(s['daily_revision_sections'], effective_cap)
        new_cap = min(s['daily_new_sections'], effective_cap - revision_cap)

        conn = self._conn()
        c = conn.cursor()

        # ── Revision items (due today or overdue) ──
        c.execute("""
            SELECT * FROM revision_schedule
            WHERE next_review_date <= ?
              AND (is_mastered = 0 OR ? = 1)
            ORDER BY revision_level DESC, next_review_date ASC
        """, (today_str, 1 if s.get('show_mastered') else 0))

        revision_items = []
        for r in c.fetchall():
            item = dict(r)
            item['days_overdue'] = (today - date.fromisoformat(item['next_review_date'])).days
            # Apply category weight
            weight_key = CATEGORY_WEIGHT_MAP.get(item['category'], 'weight_static')
            item['category_weight'] = s.get(weight_key, 1.0)
            item['sort_score'] = item['revision_level'] * 10 + item['days_overdue'] + item['category_weight']
            revision_items.append(item)

        # Sort by composite score
        revision_items.sort(key=lambda x: x['sort_score'], reverse=True)
        revision_queue = revision_items[:revision_cap]

        # ── New items (unread sections) ──
        new_window = today - timedelta(days=s['new_pdf_window_days'])
        c.execute("""
            SELECT ha.pdf_filename, ha.section_index, ha.section_title, ha.category
            FROM html_articles ha
            LEFT JOIN revision_schedule rs
                ON ha.pdf_filename = rs.pdf_filename AND ha.section_index = rs.section_index
            WHERE rs.schedule_id IS NULL
            ORDER BY ha.pdf_filename DESC, ha.section_index ASC
            LIMIT ?
        """, (new_cap * 3,))  # fetch extra, we'll pick by weight

        new_items = []
        for r in c.fetchall():
            item = dict(r)
            item['is_new'] = True
            weight_key = CATEGORY_WEIGHT_MAP.get(item['category'], 'weight_static')
            item['category_weight'] = s.get(weight_key, 1.0)
            new_items.append(item)

        new_items.sort(key=lambda x: x['category_weight'], reverse=True)
        new_queue = new_items[:new_cap]

        conn.close()

        # Stats
        overdue_count = sum(1 for r in revision_items if r['days_overdue'] > 0)
        est_time = (len(revision_queue) + len(new_queue)) * s['minutes_per_section']

        return {
            'revision_queue': revision_queue,
            'new_queue': new_queue,
            'stats': {
                'due_today': len(revision_items),
                'overdue': overdue_count,
                'showing_revision': len(revision_queue),
                'showing_new': len(new_queue),
                'estimated_minutes': est_time,
                'effective_cap': effective_cap,
                'load_factor': round(load_factor, 2),
                'is_weekend': day_of_week >= 5,
                'is_holiday': today_str in (s.get('holiday_dates') or []),
            },
        }

    def get_schedule_stats(self) -> Dict:
        """Get overall revision statistics."""
        conn = self._conn()
        c = conn.cursor()
        today = date.today().isoformat()

        c.execute("SELECT COUNT(*) as n FROM revision_schedule")
        total = c.fetchone()['n']
        c.execute("SELECT COUNT(*) as n FROM revision_schedule WHERE is_mastered = 1")
        mastered = c.fetchone()['n']
        c.execute("SELECT COUNT(*) as n FROM revision_schedule WHERE next_review_date <= ?", (today,))
        due = c.fetchone()['n']
        c.execute("SELECT COUNT(*) as n FROM revision_schedule WHERE next_review_date < ?", (today,))
        overdue = c.fetchone()['n']
        c.execute("SELECT COUNT(*) as n FROM html_articles")
        total_sections = c.fetchone()['n']

        # Streak: consecutive days with revision_schedule updates
        c.execute("""
            SELECT DISTINCT DATE(updated_at) as d FROM revision_schedule
            WHERE updated_at IS NOT NULL
            ORDER BY d DESC LIMIT 30
        """)
        dates = [r['d'] for r in c.fetchall()]
        streak = 0
        for i, d in enumerate(dates):
            expected = (date.today() - timedelta(days=i)).isoformat()
            if d == expected:
                streak += 1
            else:
                break

        conn.close()
        return {
            'total_scheduled': total,
            'total_sections': total_sections,
            'mastered': mastered,
            'due_today': due,
            'overdue': overdue,
            'streak': streak,
            'read_percent': round(total / max(1, total_sections) * 100, 1),
            'mastered_percent': round(mastered / max(1, total_sections) * 100, 1),
        }
