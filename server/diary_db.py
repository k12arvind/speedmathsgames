#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
diary_db.py

Database operations for the Daily Diary feature.
Tracks daily study entries, subjects practiced, streaks, and generates smart reminders.
"""

import sqlite3
import json
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
import os


class DiaryDatabase:
    """Database manager for Daily Diary feature."""

    def __init__(self, db_path: Optional[str] = None):
        """Initialize database connection."""
        if db_path is None:
            db_path = str(Path.home() / 'clat_preparation' / 'revision_tracker.db')
        
        self.db_path = db_path
        self._init_schema()

    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection with row factory."""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self):
        """Initialize diary tables if they don't exist."""
        migration_path = Path(__file__).parent.parent / 'migrations' / 'add_diary_tables.sql'
        
        if migration_path.exists():
            conn = self._get_connection()
            try:
                with open(migration_path, 'r') as f:
                    sql = f.read()
                conn.executescript(sql)
                conn.commit()
                print("✅ Diary database schema initialized")
            except sqlite3.Error as e:
                print(f"⚠️ Diary schema initialization: {e}")
            finally:
                conn.close()

    # ============================================================================
    # DIARY ENTRIES
    # ============================================================================

    def get_entry(self, entry_date: str, user_id: str = 'saanvi') -> Optional[Dict]:
        """Get diary entry for a specific date."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM diary_entries
                WHERE user_id = ? AND entry_date = ?
            """, (user_id, entry_date))
            
            row = cursor.fetchone()
            if row:
                entry = dict(row)
                # Get subjects for this entry
                entry['subjects'] = self.get_entry_subjects(entry['entry_id'])
                return entry
            return None
        finally:
            conn.close()

    def get_entries(self, user_id: str = 'saanvi', 
                   start_date: str = None, end_date: str = None,
                   limit: int = 30) -> List[Dict]:
        """Get diary entries with optional date range."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            query = "SELECT * FROM diary_entries WHERE user_id = ?"
            params = [user_id]
            
            if start_date:
                query += " AND entry_date >= ?"
                params.append(start_date)
            
            if end_date:
                query += " AND entry_date <= ?"
                params.append(end_date)
            
            query += " ORDER BY entry_date DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            entries = []
            for row in rows:
                entry = dict(row)
                entry['subjects'] = self.get_entry_subjects(entry['entry_id'])
                entries.append(entry)
            
            return entries
        finally:
            conn.close()

    def create_or_update_entry(self, entry_date: str, user_id: str = 'saanvi',
                               journal_text: str = None, mood: str = None,
                               energy_level: int = None, total_study_hours: float = None,
                               start_time: str = None, end_time: str = None,
                               daily_goal: str = None, goal_achieved: bool = None) -> int:
        """Create or update a diary entry for a date."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            # Check if entry exists
            cursor.execute("""
                SELECT entry_id FROM diary_entries
                WHERE user_id = ? AND entry_date = ?
            """, (user_id, entry_date))
            
            existing = cursor.fetchone()
            now = datetime.now().isoformat()
            
            if existing:
                # Update existing entry
                updates = ["updated_at = ?"]
                params = [now]
                
                if journal_text is not None:
                    updates.append("journal_text = ?")
                    params.append(journal_text)
                if mood is not None:
                    updates.append("mood = ?")
                    params.append(mood)
                if energy_level is not None:
                    updates.append("energy_level = ?")
                    params.append(energy_level)
                if total_study_hours is not None:
                    updates.append("total_study_hours = ?")
                    params.append(total_study_hours)
                if start_time is not None:
                    updates.append("start_time = ?")
                    params.append(start_time)
                if end_time is not None:
                    updates.append("end_time = ?")
                    params.append(end_time)
                if daily_goal is not None:
                    updates.append("daily_goal = ?")
                    params.append(daily_goal)
                if goal_achieved is not None:
                    updates.append("goal_achieved = ?")
                    params.append(1 if goal_achieved else 0)
                
                params.append(existing['entry_id'])
                
                cursor.execute(f"""
                    UPDATE diary_entries
                    SET {', '.join(updates)}
                    WHERE entry_id = ?
                """, params)
                
                conn.commit()
                return existing['entry_id']
            else:
                # Create new entry
                cursor.execute("""
                    INSERT INTO diary_entries 
                    (user_id, entry_date, journal_text, mood, energy_level,
                     total_study_hours, start_time, end_time, daily_goal, 
                     goal_achieved, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    user_id, entry_date, journal_text, mood, energy_level,
                    total_study_hours or 0, start_time, end_time, daily_goal,
                    1 if goal_achieved else 0, now, now
                ))
                
                conn.commit()
                return cursor.lastrowid
        finally:
            conn.close()

    def delete_entry(self, entry_date: str, user_id: str = 'saanvi') -> bool:
        """Delete a diary entry."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM diary_entries
                WHERE user_id = ? AND entry_date = ?
            """, (user_id, entry_date))
            
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    # ============================================================================
    # DIARY SUBJECTS (subjects studied each day)
    # ============================================================================

    def get_entry_subjects(self, entry_id: int) -> List[Dict]:
        """Get all subjects logged for an entry."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM diary_subjects
                WHERE entry_id = ?
                ORDER BY time_spent_minutes DESC
            """, (entry_id,))
            
            subjects = []
            for row in cursor.fetchall():
                subj = dict(row)
                # Parse JSON fields
                if subj.get('topics_covered'):
                    try:
                        subj['topics_covered'] = json.loads(subj['topics_covered'])
                    except:
                        subj['topics_covered'] = []
                if subj.get('pdf_ids'):
                    try:
                        subj['pdf_ids'] = json.loads(subj['pdf_ids'])
                    except:
                        subj['pdf_ids'] = []
                subjects.append(subj)
            
            return subjects
        finally:
            conn.close()

    def add_subject_to_entry(self, entry_id: int, subject_name: str,
                            time_spent_minutes: int = 0,
                            topics_covered: List[str] = None,
                            confidence_level: int = None,
                            difficulty_faced: str = None,
                            pdf_ids: List[str] = None,
                            anki_cards_reviewed: int = 0) -> int:
        """Add or update a subject for a diary entry."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            # Check if subject already logged for this entry
            cursor.execute("""
                SELECT subject_id, time_spent_minutes, anki_cards_reviewed
                FROM diary_subjects
                WHERE entry_id = ? AND subject_name = ?
            """, (entry_id, subject_name))
            
            existing = cursor.fetchone()
            
            topics_json = json.dumps(topics_covered) if topics_covered else None
            pdf_ids_json = json.dumps(pdf_ids) if pdf_ids else None
            
            if existing:
                # Update - add to existing time/cards
                new_time = existing['time_spent_minutes'] + time_spent_minutes
                new_cards = existing['anki_cards_reviewed'] + anki_cards_reviewed
                
                cursor.execute("""
                    UPDATE diary_subjects
                    SET time_spent_minutes = ?,
                        topics_covered = COALESCE(?, topics_covered),
                        confidence_level = COALESCE(?, confidence_level),
                        difficulty_faced = COALESCE(?, difficulty_faced),
                        pdf_ids = COALESCE(?, pdf_ids),
                        anki_cards_reviewed = ?
                    WHERE subject_id = ?
                """, (
                    new_time, topics_json, confidence_level, 
                    difficulty_faced, pdf_ids_json, new_cards,
                    existing['subject_id']
                ))
                
                conn.commit()
                subject_id = existing['subject_id']
            else:
                # Insert new
                cursor.execute("""
                    INSERT INTO diary_subjects
                    (entry_id, subject_name, time_spent_minutes, topics_covered,
                     confidence_level, difficulty_faced, pdf_ids, anki_cards_reviewed,
                     created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    entry_id, subject_name, time_spent_minutes, topics_json,
                    confidence_level, difficulty_faced, pdf_ids_json,
                    anki_cards_reviewed, datetime.now().isoformat()
                ))
                
                conn.commit()
                subject_id = cursor.lastrowid
            
            # Update streak for this subject
            entry = self._get_entry_by_id(entry_id)
            if entry:
                self._update_streak(entry['user_id'], subject_name, 
                                   entry['entry_date'], time_spent_minutes)
            
            return subject_id
        finally:
            conn.close()

    def _get_entry_by_id(self, entry_id: int) -> Optional[Dict]:
        """Get entry by ID (internal use)."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM diary_entries WHERE entry_id = ?", (entry_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    # ============================================================================
    # SUBJECTS MASTER
    # ============================================================================

    def get_all_subjects(self, active_only: bool = True) -> List[Dict]:
        """Get all subjects from master list."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            query = "SELECT * FROM subjects_master"
            if active_only:
                query += " WHERE is_active = 1"
            query += " ORDER BY display_order, subject_name"
            
            cursor.execute(query)
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def add_subject(self, subject_name: str, category: str = 'other',
                   color: str = '#6B7280', icon: str = '📚',
                   target_hours_weekly: float = 5) -> int:
        """Add a new subject to track."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            # Get max display order
            cursor.execute("SELECT MAX(display_order) as max_order FROM subjects_master")
            max_order = cursor.fetchone()['max_order'] or 0
            
            cursor.execute("""
                INSERT INTO subjects_master
                (subject_name, category, color, icon, target_hours_weekly, 
                 display_order, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                subject_name, category, color, icon, target_hours_weekly,
                max_order + 1, datetime.now().isoformat()
            ))
            
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def update_subject(self, subject_id: int, **kwargs) -> bool:
        """Update subject settings."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            allowed_fields = ['subject_name', 'category', 'color', 'icon', 
                            'target_hours_weekly', 'is_active', 'display_order']
            
            updates = []
            params = []
            
            for field, value in kwargs.items():
                if field in allowed_fields:
                    updates.append(f"{field} = ?")
                    params.append(value)
            
            if not updates:
                return False
            
            params.append(subject_id)
            
            cursor.execute(f"""
                UPDATE subjects_master
                SET {', '.join(updates)}
                WHERE subject_id = ?
            """, params)
            
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    # ============================================================================
    # STREAKS & ANALYTICS
    # ============================================================================

    def _update_streak(self, user_id: str, subject_name: str, 
                      practice_date: str, minutes: int):
        """Update streak data when a subject is practiced."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            # Get existing streak data
            cursor.execute("""
                SELECT * FROM subject_streaks
                WHERE user_id = ? AND subject_name = ?
            """, (user_id, subject_name))
            
            existing = cursor.fetchone()
            now = datetime.now()
            practice_dt = datetime.strptime(practice_date, '%Y-%m-%d').date()
            
            # Calculate week start (Monday)
            week_start = (practice_dt - timedelta(days=practice_dt.weekday())).isoformat()
            
            if existing:
                last_practiced = existing['last_practiced_date']
                current_streak = existing['current_streak']
                longest_streak = existing['longest_streak']
                this_week_minutes = existing['this_week_minutes']
                existing_week_start = existing['week_start_date']
                
                # Check if this is a new week
                if existing_week_start != week_start:
                    # New week - archive last week and reset
                    this_week_minutes = minutes
                    last_week_minutes = existing['this_week_minutes']
                else:
                    this_week_minutes += minutes
                    last_week_minutes = existing['last_week_minutes']
                
                # Update streak
                if last_practiced:
                    last_dt = datetime.strptime(last_practiced, '%Y-%m-%d').date()
                    days_diff = (practice_dt - last_dt).days
                    
                    if days_diff == 0:
                        # Same day - no streak change
                        pass
                    elif days_diff == 1:
                        # Consecutive day - increase streak
                        current_streak += 1
                    else:
                        # Streak broken - reset to 1
                        current_streak = 1
                else:
                    current_streak = 1
                
                # Update longest streak
                if current_streak > longest_streak:
                    longest_streak = current_streak
                
                cursor.execute("""
                    UPDATE subject_streaks
                    SET current_streak = ?,
                        longest_streak = ?,
                        last_practiced_date = ?,
                        this_week_minutes = ?,
                        last_week_minutes = ?,
                        week_start_date = ?,
                        total_sessions = total_sessions + 1,
                        total_minutes = total_minutes + ?,
                        updated_at = ?
                    WHERE user_id = ? AND subject_name = ?
                """, (
                    current_streak, longest_streak, practice_date,
                    this_week_minutes, last_week_minutes, week_start,
                    minutes, now.isoformat(), user_id, subject_name
                ))
            else:
                # Create new streak record
                cursor.execute("""
                    INSERT INTO subject_streaks
                    (user_id, subject_name, current_streak, longest_streak,
                     last_practiced_date, this_week_minutes, last_week_minutes,
                     week_start_date, total_sessions, total_minutes, updated_at)
                    VALUES (?, ?, 1, 1, ?, ?, 0, ?, 1, ?, ?)
                """, (
                    user_id, subject_name, practice_date, minutes,
                    week_start, minutes, now.isoformat()
                ))
            
            conn.commit()
        finally:
            conn.close()

    def get_streaks(self, user_id: str = 'saanvi') -> List[Dict]:
        """Get streak data for all subjects with days since practice."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            # Get all subjects with their streak data
            cursor.execute("""
                SELECT 
                    sm.subject_name,
                    sm.category,
                    sm.color,
                    sm.icon,
                    sm.target_hours_weekly,
                    COALESCE(ss.current_streak, 0) as current_streak,
                    COALESCE(ss.longest_streak, 0) as longest_streak,
                    ss.last_practiced_date,
                    COALESCE(ss.this_week_minutes, 0) as this_week_minutes,
                    COALESCE(ss.total_minutes, 0) as total_minutes,
                    COALESCE(ss.total_sessions, 0) as total_sessions,
                    CASE 
                        WHEN ss.last_practiced_date IS NULL THEN 999
                        ELSE CAST(julianday('now') - julianday(ss.last_practiced_date) AS INTEGER)
                    END as days_since_practice
                FROM subjects_master sm
                LEFT JOIN subject_streaks ss 
                    ON sm.subject_name = ss.subject_name AND ss.user_id = ?
                WHERE sm.is_active = 1
                ORDER BY days_since_practice DESC, sm.display_order
            """, (user_id,))
            
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_neglected_subjects(self, user_id: str = 'saanvi', 
                               days_threshold: int = 3) -> List[Dict]:
        """Get subjects not practiced for X or more days."""
        streaks = self.get_streaks(user_id)
        return [s for s in streaks if s['days_since_practice'] >= days_threshold]

    # ============================================================================
    # SMART REMINDERS
    # ============================================================================

    def generate_reminders(self, user_id: str = 'saanvi') -> List[Dict]:
        """Generate smart reminders for neglected subjects."""
        reminders = []
        streaks = self.get_streaks(user_id)
        today = datetime.now()
        
        for streak in streaks:
            days = streak['days_since_practice']
            subject = streak['subject_name']
            
            # 1. Days inactive reminders
            if days >= 7:
                reminders.append({
                    'subject_name': subject,
                    'type': 'days_inactive',
                    'message': f"⚠️ {subject} hasn't been practiced in {days} days!",
                    'priority': 'high',
                    'days_since': days,
                    'icon': streak['icon'],
                    'color': streak['color']
                })
            elif days >= 5:
                reminders.append({
                    'subject_name': subject,
                    'type': 'days_inactive',
                    'message': f"📅 {subject} - {days} days since last practice",
                    'priority': 'medium',
                    'days_since': days,
                    'icon': streak['icon'],
                    'color': streak['color']
                })
            elif days >= 3:
                reminders.append({
                    'subject_name': subject,
                    'type': 'days_inactive',
                    'message': f"💡 Consider practicing {subject} today ({days} days ago)",
                    'priority': 'low',
                    'days_since': days,
                    'icon': streak['icon'],
                    'color': streak['color']
                })
            
            # 2. Streak at risk (had a good streak, now might break)
            if streak['longest_streak'] >= 5 and streak['current_streak'] == 0 and 1 <= days <= 3:
                reminders.append({
                    'subject_name': subject,
                    'type': 'streak_broken',
                    'message': f"🔥 Your {streak['longest_streak']}-day {subject} streak was broken!",
                    'priority': 'high',
                    'days_since': days,
                    'icon': streak['icon'],
                    'color': streak['color']
                })
            
            # 3. Weekly target check (Thursday onwards)
            if today.weekday() >= 3:  # Thursday = 3
                target_minutes = streak['target_hours_weekly'] * 60
                current_minutes = streak['this_week_minutes']
                
                # Less than 50% of target by Thursday
                if current_minutes < target_minutes * 0.5:
                    hours_done = current_minutes / 60
                    hours_target = streak['target_hours_weekly']
                    reminders.append({
                        'subject_name': subject,
                        'type': 'weekly_target_low',
                        'message': f"📊 {subject}: {hours_done:.1f}h of {hours_target}h weekly target",
                        'priority': 'medium',
                        'hours_done': hours_done,
                        'hours_target': hours_target,
                        'icon': streak['icon'],
                        'color': streak['color']
                    })
        
        # Sort by priority
        priority_order = {'high': 0, 'medium': 1, 'low': 2}
        reminders.sort(key=lambda x: (priority_order.get(x['priority'], 3), -x.get('days_since', 0)))
        
        return reminders

    def dismiss_reminder(self, reminder_id: int) -> bool:
        """Dismiss a reminder."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE diary_reminders
                SET is_dismissed = 1, dismissed_at = ?
                WHERE reminder_id = ?
            """, (datetime.now().isoformat(), reminder_id))
            
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    # ============================================================================
    # ANALYTICS
    # ============================================================================

    def get_weekly_summary(self, user_id: str = 'saanvi', 
                          weeks_back: int = 0) -> Dict:
        """Get weekly study summary."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            # Calculate week boundaries
            today = datetime.now().date()
            week_start = today - timedelta(days=today.weekday() + (weeks_back * 7))
            week_end = week_start + timedelta(days=6)
            
            # Get entries for the week
            cursor.execute("""
                SELECT 
                    de.entry_date,
                    de.total_study_hours,
                    de.mood,
                    de.goal_achieved
                FROM diary_entries de
                WHERE de.user_id = ?
                AND de.entry_date BETWEEN ? AND ?
                ORDER BY de.entry_date
            """, (user_id, week_start.isoformat(), week_end.isoformat()))
            
            entries = [dict(row) for row in cursor.fetchall()]
            
            # Get subject breakdown for the week
            cursor.execute("""
                SELECT 
                    ds.subject_name,
                    SUM(ds.time_spent_minutes) as total_minutes,
                    SUM(ds.anki_cards_reviewed) as total_cards,
                    COUNT(DISTINCT de.entry_date) as days_practiced
                FROM diary_subjects ds
                JOIN diary_entries de ON ds.entry_id = de.entry_id
                WHERE de.user_id = ?
                AND de.entry_date BETWEEN ? AND ?
                GROUP BY ds.subject_name
                ORDER BY total_minutes DESC
            """, (user_id, week_start.isoformat(), week_end.isoformat()))
            
            subjects = [dict(row) for row in cursor.fetchall()]
            
            # Calculate totals
            total_hours = sum(e['total_study_hours'] or 0 for e in entries)
            days_studied = len(entries)
            goals_achieved = sum(1 for e in entries if e['goal_achieved'])
            
            return {
                'week_start': week_start.isoformat(),
                'week_end': week_end.isoformat(),
                'total_hours': round(total_hours, 1),
                'days_studied': days_studied,
                'goals_achieved': goals_achieved,
                'goals_total': days_studied,
                'entries': entries,
                'subjects': subjects,
                'average_hours_per_day': round(total_hours / max(days_studied, 1), 1)
            }
        finally:
            conn.close()

    def get_analytics(self, user_id: str = 'saanvi', days: int = 30) -> Dict:
        """Get overall analytics for the past N days."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            
            # Total study stats
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_entries,
                    SUM(total_study_hours) as total_hours,
                    AVG(total_study_hours) as avg_hours_per_day,
                    SUM(goal_achieved) as goals_achieved
                FROM diary_entries
                WHERE user_id = ? AND entry_date >= ?
            """, (user_id, start_date))
            
            stats = dict(cursor.fetchone())
            
            # Mood distribution
            cursor.execute("""
                SELECT mood, COUNT(*) as count
                FROM diary_entries
                WHERE user_id = ? AND entry_date >= ? AND mood IS NOT NULL
                GROUP BY mood
            """, (user_id, start_date))
            
            moods = {row['mood']: row['count'] for row in cursor.fetchall()}
            
            # Subject time breakdown
            cursor.execute("""
                SELECT 
                    ds.subject_name,
                    SUM(ds.time_spent_minutes) as total_minutes,
                    COUNT(DISTINCT de.entry_date) as days_practiced,
                    AVG(ds.confidence_level) as avg_confidence
                FROM diary_subjects ds
                JOIN diary_entries de ON ds.entry_id = de.entry_id
                WHERE de.user_id = ? AND de.entry_date >= ?
                GROUP BY ds.subject_name
                ORDER BY total_minutes DESC
            """, (user_id, start_date))
            
            subjects = [dict(row) for row in cursor.fetchall()]
            
            # Study pattern by day of week
            cursor.execute("""
                SELECT 
                    strftime('%w', entry_date) as day_of_week,
                    AVG(total_study_hours) as avg_hours
                FROM diary_entries
                WHERE user_id = ? AND entry_date >= ?
                GROUP BY day_of_week
                ORDER BY day_of_week
            """, (user_id, start_date))
            
            day_names = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 
                        'Thursday', 'Friday', 'Saturday']
            daily_pattern = {}
            for row in cursor.fetchall():
                day_idx = int(row['day_of_week'])
                daily_pattern[day_names[day_idx]] = round(row['avg_hours'] or 0, 1)
            
            return {
                'period_days': days,
                'total_entries': stats['total_entries'] or 0,
                'total_hours': round(stats['total_hours'] or 0, 1),
                'avg_hours_per_day': round(stats['avg_hours_per_day'] or 0, 1),
                'goals_achieved': stats['goals_achieved'] or 0,
                'mood_distribution': moods,
                'subjects': subjects,
                'daily_pattern': daily_pattern
            }
        finally:
            conn.close()

    def get_weekly_snapshot(self, user_id: str = 'saanvi', 
                           weeks_back: int = 0) -> Dict:
        """
        Get detailed weekly snapshot with day-by-day breakdown.
        Shows what was done each day and subject-wise totals for the week.
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            # Calculate week boundaries (Monday to Sunday)
            today = datetime.now().date()
            # Go back to Monday of current week, then subtract weeks
            days_since_monday = today.weekday()
            week_start = today - timedelta(days=days_since_monday + (weeks_back * 7))
            week_end = week_start + timedelta(days=6)
            
            # Get day-by-day entries with subjects
            cursor.execute("""
                SELECT 
                    de.entry_date,
                    de.total_study_hours,
                    de.mood,
                    de.energy_level,
                    de.goal_achieved,
                    de.daily_goal,
                    de.journal_text
                FROM diary_entries de
                WHERE de.user_id = ?
                AND de.entry_date BETWEEN ? AND ?
                ORDER BY de.entry_date
            """, (user_id, week_start.isoformat(), week_end.isoformat()))
            
            entries_raw = [dict(row) for row in cursor.fetchall()]
            
            # Build day-by-day with subjects
            days = []
            for i in range(7):
                day_date = week_start + timedelta(days=i)
                day_str = day_date.isoformat()
                day_name = day_date.strftime('%A')
                
                # Find entry for this day
                entry = next((e for e in entries_raw if e['entry_date'] == day_str), None)
                
                day_subjects = []
                if entry:
                    # Get subjects for this entry with all subjective remarks
                    cursor.execute("""
                        SELECT ds.subject_name, ds.time_spent_minutes, 
                               ds.topics_covered, ds.confidence_level,
                               ds.difficulty_faced, ds.anki_cards_reviewed
                        FROM diary_subjects ds
                        JOIN diary_entries de ON ds.entry_id = de.entry_id
                        WHERE de.user_id = ? AND de.entry_date = ?
                    """, (user_id, day_str))
                    
                    for row in cursor.fetchall():
                        subj = dict(row)
                        if subj.get('topics_covered'):
                            try:
                                import json
                                subj['topics_covered'] = json.loads(subj['topics_covered'])
                            except:
                                subj['topics_covered'] = []
                        day_subjects.append(subj)
                
                days.append({
                    'date': day_str,
                    'day_name': day_name,
                    'studied': entry is not None,
                    'hours': entry['total_study_hours'] if entry else 0,
                    'mood': entry['mood'] if entry else None,
                    'energy': entry['energy_level'] if entry else None,
                    'goal': entry['daily_goal'] if entry else None,
                    'goal_achieved': entry['goal_achieved'] if entry else False,
                    'journal_text': entry['journal_text'] if entry else None,
                    'subjects': day_subjects
                })
            
            # Get subject-wise totals for the week with all subjective remarks
            cursor.execute("""
                SELECT 
                    sm.subject_name,
                    sm.icon,
                    sm.color,
                    sm.target_hours_weekly,
                    COALESCE(SUM(ds.time_spent_minutes), 0) as total_minutes,
                    COUNT(DISTINCT de.entry_date) as days_practiced,
                    GROUP_CONCAT(DISTINCT de.entry_date) as practice_dates
                FROM subjects_master sm
                LEFT JOIN diary_subjects ds ON sm.subject_name = ds.subject_name
                LEFT JOIN diary_entries de ON ds.entry_id = de.entry_id 
                    AND de.user_id = ? 
                    AND de.entry_date BETWEEN ? AND ?
                WHERE sm.is_active = 1
                GROUP BY sm.subject_name, sm.icon, sm.color, sm.target_hours_weekly
                ORDER BY total_minutes DESC
            """, (user_id, week_start.isoformat(), week_end.isoformat()))
            
            subject_totals = []
            for row in cursor.fetchall():
                subj = dict(row)
                subj['total_hours'] = round(subj['total_minutes'] / 60, 1)
                subj['target_met'] = subj['total_hours'] >= subj['target_hours_weekly']
                subj['target_percent'] = round((subj['total_hours'] / subj['target_hours_weekly']) * 100) if subj['target_hours_weekly'] > 0 else 0
                subj['practice_dates'] = subj['practice_dates'].split(',') if subj['practice_dates'] else []
                
                # Get all subjective remarks for this subject during the week
                cursor.execute("""
                    SELECT 
                        de.entry_date,
                        ds.topics_covered,
                        ds.difficulty_faced,
                        ds.confidence_level,
                        ds.time_spent_minutes
                    FROM diary_subjects ds
                    JOIN diary_entries de ON ds.entry_id = de.entry_id
                    WHERE ds.subject_name = ?
                    AND de.user_id = ?
                    AND de.entry_date BETWEEN ? AND ?
                    ORDER BY de.entry_date
                """, (subj['subject_name'], user_id, week_start.isoformat(), week_end.isoformat()))
                
                remarks = []
                all_topics = []
                all_difficulties = []
                confidence_sum = 0
                confidence_count = 0
                
                for remark_row in cursor.fetchall():
                    remark = dict(remark_row)
                    if remark.get('topics_covered'):
                        try:
                            topics = json.loads(remark['topics_covered'])
                            remark['topics_covered'] = topics
                            all_topics.extend(topics)
                        except:
                            remark['topics_covered'] = []
                    
                    if remark.get('difficulty_faced'):
                        all_difficulties.append({
                            'date': remark['entry_date'],
                            'text': remark['difficulty_faced']
                        })
                    
                    if remark.get('confidence_level'):
                        confidence_sum += remark['confidence_level']
                        confidence_count += 1
                    
                    remarks.append(remark)
                
                subj['daily_remarks'] = remarks
                subj['all_topics'] = list(set(all_topics))  # Unique topics
                subj['difficulties'] = all_difficulties
                subj['avg_confidence'] = round(confidence_sum / confidence_count, 1) if confidence_count > 0 else None
                
                subject_totals.append(subj)
            
            # Calculate week totals
            total_hours = sum(d['hours'] or 0 for d in days)
            days_studied = sum(1 for d in days if d['studied'])
            goals_achieved = sum(1 for d in days if d['goal_achieved'])
            goals_set = sum(1 for d in days if d['goal'])
            
            return {
                'week_start': week_start.isoformat(),
                'week_end': week_end.isoformat(),
                'week_number': week_start.isocalendar()[1],
                'days': days,
                'subject_totals': subject_totals,
                'summary': {
                    'total_hours': round(total_hours, 1),
                    'days_studied': days_studied,
                    'goals_achieved': goals_achieved,
                    'goals_set': goals_set,
                    'avg_hours_per_study_day': round(total_hours / max(days_studied, 1), 1)
                }
            }
        finally:
            conn.close()

    def get_date_range_analytics(self, user_id: str = 'saanvi',
                                  start_date: str = None, 
                                  end_date: str = None,
                                  days: int = None) -> Dict:
        """
        Get detailed analytics for a custom date range.
        Can specify either start_date/end_date OR number of days back.
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            # Determine date range
            if start_date and end_date:
                date_start = start_date
                date_end = end_date
            elif days:
                date_end = datetime.now().strftime('%Y-%m-%d')
                date_start = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            else:
                # Default to last 7 days
                date_end = datetime.now().strftime('%Y-%m-%d')
                date_start = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
            
            # Overall stats
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_entries,
                    COALESCE(SUM(total_study_hours), 0) as total_hours,
                    COALESCE(AVG(total_study_hours), 0) as avg_hours,
                    SUM(CASE WHEN goal_achieved = 1 THEN 1 ELSE 0 END) as goals_achieved,
                    COUNT(CASE WHEN daily_goal IS NOT NULL THEN 1 END) as goals_set
                FROM diary_entries
                WHERE user_id = ? AND entry_date BETWEEN ? AND ?
            """, (user_id, date_start, date_end))
            
            overall = dict(cursor.fetchone())
            
            # Subject-wise breakdown
            cursor.execute("""
                SELECT 
                    sm.subject_name,
                    sm.icon,
                    sm.color,
                    sm.category,
                    sm.target_hours_weekly,
                    COALESCE(SUM(ds.time_spent_minutes), 0) as total_minutes,
                    COUNT(DISTINCT de.entry_date) as days_practiced,
                    COALESCE(AVG(ds.confidence_level), 0) as avg_confidence,
                    COALESCE(SUM(ds.anki_cards_reviewed), 0) as total_cards
                FROM subjects_master sm
                LEFT JOIN diary_subjects ds ON sm.subject_name = ds.subject_name
                LEFT JOIN diary_entries de ON ds.entry_id = de.entry_id 
                    AND de.user_id = ? 
                    AND de.entry_date BETWEEN ? AND ?
                WHERE sm.is_active = 1
                GROUP BY sm.subject_name, sm.icon, sm.color, sm.category, sm.target_hours_weekly
                ORDER BY total_minutes DESC
            """, (user_id, date_start, date_end))
            
            subjects = []
            for row in cursor.fetchall():
                subj = dict(row)
                subj['total_hours'] = round(subj['total_minutes'] / 60, 1)
                subj['avg_confidence'] = round(subj['avg_confidence'], 1) if subj['avg_confidence'] else None
                
                # Calculate number of weeks in range for target comparison
                start_dt = datetime.strptime(date_start, '%Y-%m-%d')
                end_dt = datetime.strptime(date_end, '%Y-%m-%d')
                weeks_in_range = max(1, (end_dt - start_dt).days / 7)
                expected_hours = subj['target_hours_weekly'] * weeks_in_range
                subj['expected_hours'] = round(expected_hours, 1)
                subj['target_percent'] = round((subj['total_hours'] / expected_hours) * 100) if expected_hours > 0 else 0
                
                subjects.append(subj)
            
            # Daily breakdown (for chart)
            cursor.execute("""
                SELECT 
                    entry_date,
                    total_study_hours,
                    mood,
                    goal_achieved
                FROM diary_entries
                WHERE user_id = ? AND entry_date BETWEEN ? AND ?
                ORDER BY entry_date
            """, (user_id, date_start, date_end))
            
            daily_data = [dict(row) for row in cursor.fetchall()]
            
            # Mood distribution
            cursor.execute("""
                SELECT mood, COUNT(*) as count
                FROM diary_entries
                WHERE user_id = ? AND entry_date BETWEEN ? AND ? AND mood IS NOT NULL
                GROUP BY mood
            """, (user_id, date_start, date_end))
            
            moods = {row['mood']: row['count'] for row in cursor.fetchall()}
            
            # Category breakdown
            cursor.execute("""
                SELECT 
                    sm.category,
                    COALESCE(SUM(ds.time_spent_minutes), 0) as total_minutes
                FROM subjects_master sm
                LEFT JOIN diary_subjects ds ON sm.subject_name = ds.subject_name
                LEFT JOIN diary_entries de ON ds.entry_id = de.entry_id 
                    AND de.user_id = ? 
                    AND de.entry_date BETWEEN ? AND ?
                WHERE sm.is_active = 1
                GROUP BY sm.category
            """, (user_id, date_start, date_end))
            
            categories = {}
            for row in cursor.fetchall():
                categories[row['category']] = round(row['total_minutes'] / 60, 1)
            
            # Calculate date range info
            start_dt = datetime.strptime(date_start, '%Y-%m-%d')
            end_dt = datetime.strptime(date_end, '%Y-%m-%d')
            total_days = (end_dt - start_dt).days + 1
            
            return {
                'date_range': {
                    'start': date_start,
                    'end': date_end,
                    'total_days': total_days
                },
                'overall': {
                    'total_entries': overall['total_entries'] or 0,
                    'total_hours': round(overall['total_hours'] or 0, 1),
                    'avg_hours_per_day': round((overall['total_hours'] or 0) / total_days, 1),
                    'avg_hours_per_study_day': round((overall['total_hours'] or 0) / max(overall['total_entries'] or 1, 1), 1),
                    'goals_achieved': overall['goals_achieved'] or 0,
                    'goals_set': overall['goals_set'] or 0,
                    'study_rate': round((overall['total_entries'] or 0) / total_days * 100)
                },
                'subjects': subjects,
                'daily_data': daily_data,
                'mood_distribution': moods,
                'category_breakdown': categories
            }
        finally:
            conn.close()

    # ============================================================================
    # INTEGRATION HELPERS
    # ============================================================================

    def auto_log_subject(self, user_id: str, date: str, subject_name: str,
                        pdf_id: str = None, minutes: int = 0, 
                        anki_cards: int = 0) -> bool:
        """
        Auto-log a subject from external triggers (PDF access, Anki review).
        Creates entry if needed, then adds/updates subject.
        """
        try:
            # Ensure entry exists for today
            entry_id = self.create_or_update_entry(date, user_id)
            
            # Add subject with the activity
            pdf_ids = [pdf_id] if pdf_id else None
            self.add_subject_to_entry(
                entry_id=entry_id,
                subject_name=subject_name,
                time_spent_minutes=minutes,
                pdf_ids=pdf_ids,
                anki_cards_reviewed=anki_cards
            )
            
            return True
        except Exception as e:
            print(f"Error auto-logging subject: {e}")
            return False

    def close(self):
        """Cleanup (for compatibility, connections are per-method)."""
        pass


# ============================================================================
# CLI TEST
# ============================================================================

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("Diary Database - Test Operations")
    print("=" * 60 + "\n")
    
    db = DiaryDatabase()
    
    # Test: Get all subjects
    print("📚 Subjects:")
    subjects = db.get_all_subjects()
    for s in subjects:
        print(f"  {s['icon']} {s['subject_name']} ({s['category']}) - {s['target_hours_weekly']}h/week")
    
    # Test: Create today's entry
    today = datetime.now().strftime('%Y-%m-%d')
    print(f"\n📝 Creating entry for {today}...")
    entry_id = db.create_or_update_entry(
        entry_date=today,
        journal_text="Test entry from diary_db.py",
        mood="good",
        energy_level=4,
        daily_goal="Complete testing"
    )
    print(f"  Entry ID: {entry_id}")
    
    # Test: Add subject
    print("\n📖 Adding CLAT GK subject...")
    db.add_subject_to_entry(
        entry_id=entry_id,
        subject_name="CLAT GK",
        time_spent_minutes=60,
        topics_covered=["Economy", "International Affairs"],
        confidence_level=4
    )
    
    # Test: Get streaks
    print("\n🔥 Subject Streaks:")
    streaks = db.get_streaks()
    for s in streaks:
        days = s['days_since_practice']
        days_str = "Never" if days >= 999 else f"{days} days ago"
        print(f"  {s['icon']} {s['subject_name']}: {s['current_streak']} day streak ({days_str})")
    
    # Test: Get reminders
    print("\n⏰ Smart Reminders:")
    reminders = db.generate_reminders()
    for r in reminders[:5]:
        print(f"  [{r['priority'].upper()}] {r['message']}")
    
    if not reminders:
        print("  No reminders - great job! 🎉")
    
    # Test: Get entry
    print(f"\n📅 Today's Entry:")
    entry = db.get_entry(today)
    if entry:
        print(f"  Mood: {entry.get('mood')}")
        print(f"  Journal: {entry.get('journal_text', '')[:50]}...")
        print(f"  Subjects: {len(entry.get('subjects', []))}")
    
    print("\n" + "=" * 60)
    print("✅ All tests passed!")
    print("=" * 60 + "\n")

