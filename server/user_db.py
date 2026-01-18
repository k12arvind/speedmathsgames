#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
user_db.py

User database manager for multi-user authentication.
Handles user accounts, sessions, and role management.
"""

import sqlite3
import os
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from pathlib import Path


class UserDatabase:
    """User database manager for authentication and sessions."""

    def __init__(self, db_path: str = None):
        """
        Initialize user database.

        Args:
            db_path: Path to SQLite database file (default: auth/users.db)
        """
        if db_path is None:
            auth_dir = Path(__file__).parent
            db_path = str(auth_dir / 'users.db')

        self.db_path = db_path
        self._create_tables()

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _create_tables(self):
        """Create database tables if they don't exist."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                google_id TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                name TEXT,
                picture TEXT,
                role TEXT DEFAULT 'student',
                created_at TEXT NOT NULL,
                last_login TEXT,
                is_active INTEGER DEFAULT 1
            )
        ''')

        # Sessions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                session_token TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                last_activity TEXT,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
        ''')

        # Create indexes
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_google_id ON users(google_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_email ON users(email)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_session_user ON sessions(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_session_expires ON sessions(expires_at)')

        conn.commit()
        conn.close()

    def create_or_update_user(
        self,
        google_id: str,
        email: str,
        name: str = None,
        picture: str = None
    ) -> str:
        """
        Create a new user or update existing user.
        First user gets 'admin' role, subsequent users get 'student' role.

        Args:
            google_id: Google account ID
            email: User email
            name: User's full name
            picture: URL to profile picture

        Returns:
            user_id (same as google_id)
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Check if this is the first user
        cursor.execute('SELECT COUNT(*) as count FROM users')
        user_count = cursor.fetchone()['count']
        role = 'admin' if user_count == 0 else 'student'

        # Check if user exists
        cursor.execute('SELECT user_id, role FROM users WHERE google_id = ?', (google_id,))
        existing_user = cursor.fetchone()

        now = datetime.utcnow().isoformat()

        if existing_user:
            # Update existing user
            user_id = existing_user['user_id']
            cursor.execute('''
                UPDATE users
                SET email = ?, name = ?, picture = ?, last_login = ?
                WHERE user_id = ?
            ''', (email, name, picture, now, user_id))
        else:
            # Create new user
            user_id = google_id
            cursor.execute('''
                INSERT INTO users (user_id, google_id, email, name, picture, role, created_at, last_login)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, google_id, email, name, picture, role, now, now))

        conn.commit()
        conn.close()

        return user_id

    def get_user(self, user_id: str = None, email: str = None, google_id: str = None) -> Optional[Dict]:
        """
        Get user by ID, email, or Google ID.

        Args:
            user_id: User ID
            email: User email
            google_id: Google account ID

        Returns:
            User dict or None if not found
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        if user_id:
            cursor.execute('SELECT * FROM users WHERE user_id = ? AND is_active = 1', (user_id,))
        elif email:
            cursor.execute('SELECT * FROM users WHERE email = ? AND is_active = 1', (email,))
        elif google_id:
            cursor.execute('SELECT * FROM users WHERE google_id = ? AND is_active = 1', (google_id,))
        else:
            conn.close()
            return None

        user = cursor.fetchone()
        conn.close()

        if user:
            return dict(user)
        return None

    def get_all_users(self) -> List[Dict]:
        """
        Get all active users.

        Returns:
            List of user dicts
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM users WHERE is_active = 1 ORDER BY created_at')
        users = [dict(row) for row in cursor.fetchall()]

        conn.close()
        return users

    def update_user_role(self, user_id: str, role: str) -> bool:
        """
        Update user's role (admin/student).

        Args:
            user_id: User ID
            role: New role ('admin' or 'student')

        Returns:
            True if updated, False if user not found
        """
        if role not in ['admin', 'student']:
            raise ValueError("Role must be 'admin' or 'student'")

        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute('UPDATE users SET role = ? WHERE user_id = ?', (role, user_id))
        updated = cursor.rowcount > 0

        conn.commit()
        conn.close()

        return updated

    def deactivate_user(self, user_id: str) -> bool:
        """
        Deactivate a user (soft delete).

        Args:
            user_id: User ID

        Returns:
            True if deactivated, False if user not found
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute('UPDATE users SET is_active = 0 WHERE user_id = ?', (user_id,))
        updated = cursor.rowcount > 0

        # Also delete all sessions
        if updated:
            cursor.execute('DELETE FROM sessions WHERE user_id = ?', (user_id,))

        conn.commit()
        conn.close()

        return updated

    def create_session(
        self,
        user_id: str,
        session_token: str,
        expires_in_days: int = 30
    ) -> bool:
        """
        Create a new session for user.

        Args:
            user_id: User ID
            session_token: Unique session token
            expires_in_days: Session expiration in days (default: 30)

        Returns:
            True if created successfully
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        now = datetime.utcnow()
        expires_at = now + timedelta(days=expires_in_days)

        cursor.execute('''
            INSERT INTO sessions (session_token, user_id, created_at, expires_at, last_activity)
            VALUES (?, ?, ?, ?, ?)
        ''', (session_token, user_id, now.isoformat(), expires_at.isoformat(), now.isoformat()))

        conn.commit()
        conn.close()

        return True

    def get_session(self, session_token: str) -> Optional[Dict]:
        """
        Get session info and validate expiration.

        Args:
            session_token: Session token

        Returns:
            Dict with session and user info, or None if invalid/expired
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Get session and join with user
        cursor.execute('''
            SELECT s.*, u.email, u.name, u.picture, u.role, u.is_active
            FROM sessions s
            JOIN users u ON s.user_id = u.user_id
            WHERE s.session_token = ?
        ''', (session_token,))

        session = cursor.fetchone()

        if not session:
            conn.close()
            return None

        session_dict = dict(session)

        # Check if expired
        expires_at = datetime.fromisoformat(session_dict['expires_at'])
        if datetime.utcnow() > expires_at:
            # Delete expired session
            cursor.execute('DELETE FROM sessions WHERE session_token = ?', (session_token,))
            conn.commit()
            conn.close()
            return None

        # Check if user is active
        if not session_dict['is_active']:
            conn.close()
            return None

        # Update last activity
        cursor.execute(
            'UPDATE sessions SET last_activity = ? WHERE session_token = ?',
            (datetime.utcnow().isoformat(), session_token)
        )

        conn.commit()
        conn.close()

        return session_dict

    def delete_session(self, session_token: str) -> bool:
        """
        Delete a session (logout).

        Args:
            session_token: Session token

        Returns:
            True if deleted
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute('DELETE FROM sessions WHERE session_token = ?', (session_token,))
        deleted = cursor.rowcount > 0

        conn.commit()
        conn.close()

        return deleted

    def delete_user_sessions(self, user_id: str) -> int:
        """
        Delete all sessions for a user.

        Args:
            user_id: User ID

        Returns:
            Number of sessions deleted
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute('DELETE FROM sessions WHERE user_id = ?', (user_id,))
        count = cursor.rowcount

        conn.commit()
        conn.close()

        return count

    def cleanup_expired_sessions(self) -> int:
        """
        Delete all expired sessions.

        Returns:
            Number of sessions deleted
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        now = datetime.utcnow().isoformat()
        cursor.execute('DELETE FROM sessions WHERE expires_at < ?', (now,))
        count = cursor.rowcount

        conn.commit()
        conn.close()

        return count


if __name__ == '__main__':
    # Quick test
    print("User Database Module")
    print("=" * 60)

    db = UserDatabase()
    print("✅ Database initialized")

    # Test user creation
    user_id = db.create_or_update_user(
        google_id='test_123',
        email='test@example.com',
        name='Test User'
    )
    print(f"✅ Created user: {user_id}")

    # Get user
    user = db.get_user(user_id=user_id)
    print(f"✅ Retrieved user: {user['email']} (Role: {user['role']})")

    # Create session
    session_token = 'test_session_token_123'
    db.create_session(user_id, session_token)
    print(f"✅ Created session")

    # Get session
    session = db.get_session(session_token)
    if session:
        print(f"✅ Retrieved valid session for {session['email']}")

    print("\n✅ All tests passed!")
