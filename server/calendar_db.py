"""
Calendar Database Module

Manages:
- OAuth tokens for multiple Google accounts
- Cached calendar events
- Calendar sync status
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

class CalendarDatabase:
    """Database operations for calendar module."""
    
    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            db_path = Path(__file__).parent.parent / 'calendar_tracker.db'
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize database tables."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Google OAuth tokens for each account
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS google_accounts (
                    id INTEGER PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    display_name TEXT,
                    access_token TEXT,
                    refresh_token TEXT,
                    token_expiry TEXT,
                    scopes TEXT,
                    is_primary BOOLEAN DEFAULT FALSE,
                    color TEXT DEFAULT '#4285f4',
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Cached calendar events (for faster loading)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS cached_events (
                    id INTEGER PRIMARY KEY,
                    google_event_id TEXT NOT NULL,
                    account_email TEXT NOT NULL,
                    calendar_id TEXT DEFAULT 'primary',
                    title TEXT NOT NULL,
                    description TEXT,
                    location TEXT,
                    start_time TEXT NOT NULL,
                    end_time TEXT NOT NULL,
                    is_all_day BOOLEAN DEFAULT FALSE,
                    recurrence TEXT,
                    attendees TEXT,
                    status TEXT DEFAULT 'confirmed',
                    html_link TEXT,
                    color TEXT,
                    source TEXT DEFAULT 'google',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(google_event_id, account_email)
                )
            ''')
            
            # Bill events synced to Google Calendar
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS synced_bill_events (
                    id INTEGER PRIMARY KEY,
                    bill_id INTEGER NOT NULL,
                    google_event_id TEXT,
                    due_date TEXT NOT NULL,
                    synced_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(bill_id, due_date)
                )
            ''')
            
            # Daily summary log
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS summary_log (
                    id INTEGER PRIMARY KEY,
                    sent_date TEXT NOT NULL,
                    recipient_email TEXT NOT NULL,
                    events_count INTEGER,
                    bills_count INTEGER,
                    status TEXT DEFAULT 'sent',
                    error_message TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Sync status tracking
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sync_status (
                    id INTEGER PRIMARY KEY,
                    account_email TEXT NOT NULL,
                    last_sync TEXT,
                    sync_token TEXT,
                    status TEXT DEFAULT 'idle',
                    error_message TEXT,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(account_email)
                )
            ''')
            
            conn.commit()
    
    # =========================================================================
    # Google Account Management
    # =========================================================================
    
    def add_or_update_account(self, email: str, tokens: Dict[str, Any], 
                              display_name: str = None, is_primary: bool = False,
                              color: str = '#4285f4') -> int:
        """Add or update a Google account with OAuth tokens."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO google_accounts 
                (email, display_name, access_token, refresh_token, token_expiry, scopes, is_primary, color, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(email) DO UPDATE SET
                    display_name = COALESCE(excluded.display_name, display_name),
                    access_token = excluded.access_token,
                    refresh_token = COALESCE(excluded.refresh_token, refresh_token),
                    token_expiry = excluded.token_expiry,
                    scopes = excluded.scopes,
                    is_primary = excluded.is_primary,
                    color = excluded.color,
                    updated_at = excluded.updated_at
            ''', (
                email,
                display_name,
                tokens.get('access_token'),
                tokens.get('refresh_token'),
                tokens.get('expiry'),
                json.dumps(tokens.get('scopes', [])),
                is_primary,
                color,
                datetime.now().isoformat()
            ))
            
            conn.commit()
            return cursor.lastrowid
    
    def get_account(self, email: str) -> Optional[Dict[str, Any]]:
        """Get account details by email."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM google_accounts WHERE email = ?', (email,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_all_accounts(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """Get all configured Google accounts."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            query = 'SELECT * FROM google_accounts'
            if active_only:
                query += ' WHERE is_active = TRUE'
            query += ' ORDER BY is_primary DESC, email'
            
            cursor.execute(query)
            return [dict(row) for row in cursor.fetchall()]
    
    def update_tokens(self, email: str, access_token: str, expiry: str):
        """Update access token after refresh."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE google_accounts 
                SET access_token = ?, token_expiry = ?, updated_at = ?
                WHERE email = ?
            ''', (access_token, expiry, datetime.now().isoformat(), email))
            conn.commit()
    
    def deactivate_account(self, email: str):
        """Deactivate an account (keep data but stop syncing)."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE google_accounts SET is_active = FALSE, updated_at = ?
                WHERE email = ?
            ''', (datetime.now().isoformat(), email))
            conn.commit()
    
    # =========================================================================
    # Cached Events Management
    # =========================================================================
    
    def cache_events(self, events: List[Dict[str, Any]], account_email: str):
        """Cache events from Google Calendar."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            for event in events:
                cursor.execute('''
                    INSERT INTO cached_events 
                    (google_event_id, account_email, calendar_id, title, description,
                     location, start_time, end_time, is_all_day, recurrence, 
                     attendees, status, html_link, color, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(google_event_id, account_email) DO UPDATE SET
                        title = excluded.title,
                        description = excluded.description,
                        location = excluded.location,
                        start_time = excluded.start_time,
                        end_time = excluded.end_time,
                        is_all_day = excluded.is_all_day,
                        recurrence = excluded.recurrence,
                        attendees = excluded.attendees,
                        status = excluded.status,
                        html_link = excluded.html_link,
                        color = excluded.color,
                        updated_at = excluded.updated_at
                ''', (
                    event.get('id'),
                    account_email,
                    event.get('calendar_id', 'primary'),
                    event.get('summary', 'No Title'),
                    event.get('description'),
                    event.get('location'),
                    event.get('start'),
                    event.get('end'),
                    event.get('is_all_day', False),
                    json.dumps(event.get('recurrence')) if event.get('recurrence') else None,
                    json.dumps(event.get('attendees')) if event.get('attendees') else None,
                    event.get('status', 'confirmed'),
                    event.get('htmlLink'),
                    event.get('color'),
                    datetime.now().isoformat()
                ))
            
            conn.commit()
    
    def get_cached_events(self, start_date: str, end_date: str, 
                          account_email: str = None) -> List[Dict[str, Any]]:
        """Get cached events for date range."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            query = '''
                SELECT * FROM cached_events 
                WHERE start_time >= ? AND start_time <= ?
                AND status != 'cancelled'
            '''
            params = [start_date, end_date]
            
            if account_email:
                query += ' AND account_email = ?'
                params.append(account_email)
            
            query += ' ORDER BY start_time'
            
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    
    def delete_cached_events(self, account_email: str):
        """Delete all cached events for an account (before re-sync)."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM cached_events WHERE account_email = ?', 
                          (account_email,))
            conn.commit()
    
    # =========================================================================
    # Bill Event Sync
    # =========================================================================
    
    def record_bill_sync(self, bill_id: int, google_event_id: str, due_date: str):
        """Record that a bill was synced to Google Calendar."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO synced_bill_events (bill_id, google_event_id, due_date)
                VALUES (?, ?, ?)
                ON CONFLICT(bill_id, due_date) DO UPDATE SET
                    google_event_id = excluded.google_event_id,
                    synced_at = CURRENT_TIMESTAMP
            ''', (bill_id, google_event_id, due_date))
            conn.commit()
    
    def get_synced_bill(self, bill_id: int, due_date: str) -> Optional[str]:
        """Get Google event ID for a synced bill."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT google_event_id FROM synced_bill_events 
                WHERE bill_id = ? AND due_date = ?
            ''', (bill_id, due_date))
            row = cursor.fetchone()
            return row[0] if row else None
    
    # =========================================================================
    # Summary Log
    # =========================================================================
    
    def log_summary(self, recipient: str, events_count: int, bills_count: int,
                    status: str = 'sent', error: str = None):
        """Log a daily summary email."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO summary_log 
                (sent_date, recipient_email, events_count, bills_count, status, error_message)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                datetime.now().strftime('%Y-%m-%d'),
                recipient,
                events_count,
                bills_count,
                status,
                error
            ))
            conn.commit()
    
    def was_summary_sent_today(self, recipient: str) -> bool:
        """Check if today's summary was already sent."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT COUNT(*) FROM summary_log 
                WHERE sent_date = ? AND recipient_email = ? AND status = 'sent'
            ''', (datetime.now().strftime('%Y-%m-%d'), recipient))
            return cursor.fetchone()[0] > 0
    
    # =========================================================================
    # Sync Status
    # =========================================================================
    
    def update_sync_status(self, email: str, status: str, 
                           sync_token: str = None, error: str = None):
        """Update sync status for an account."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO sync_status (account_email, last_sync, sync_token, status, error_message, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(account_email) DO UPDATE SET
                    last_sync = CASE WHEN excluded.status = 'completed' THEN excluded.last_sync ELSE last_sync END,
                    sync_token = COALESCE(excluded.sync_token, sync_token),
                    status = excluded.status,
                    error_message = excluded.error_message,
                    updated_at = excluded.updated_at
            ''', (
                email,
                datetime.now().isoformat() if status == 'completed' else None,
                sync_token,
                status,
                error,
                datetime.now().isoformat()
            ))
            conn.commit()
    
    def get_sync_status(self, email: str) -> Optional[Dict[str, Any]]:
        """Get sync status for an account."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM sync_status WHERE account_email = ?', (email,))
            row = cursor.fetchone()
            return dict(row) if row else None

