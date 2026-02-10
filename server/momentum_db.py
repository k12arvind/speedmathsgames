#!/usr/bin/env python3
"""
Momentum Scanner Database
Stores scan results, VCP patterns, breakout alerts, and portfolio positions.
"""

import sqlite3
from pathlib import Path
from datetime import datetime, date
from typing import List, Dict, Optional
import json


class MomentumDatabase:
    """Database operations for momentum scanner module."""

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = str(Path.home() / 'clat_preparation' / 'momentum_tracker.db')
        self.db_path = db_path
        self._init_db()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self):
        conn = self._get_conn()
        cursor = conn.cursor()

        # Daily scan metadata
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS momentum_scans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_date TEXT NOT NULL,
                scan_type TEXT NOT NULL DEFAULT 'trend_template',
                total_stocks_scanned INTEGER DEFAULT 0,
                qualifying_count INTEGER DEFAULT 0,
                scan_duration_sec REAL DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now')),
                UNIQUE(scan_date, scan_type)
            )
        """)

        # Individual stock scan results
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS momentum_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                company_name TEXT,
                close_price REAL,
                sma_50 REAL,
                sma_150 REAL,
                sma_200 REAL,
                sma_200_prev REAL,
                rs_rating REAL,
                pct_from_52w_high REAL,
                pct_from_52w_low REAL,
                high_52w REAL,
                low_52w REAL,
                volume REAL,
                avg_volume_50 REAL,
                volume_ratio REAL,
                sector TEXT,
                industry TEXT,
                market_cap REAL,
                is_fno INTEGER DEFAULT 0,
                tradingview_link TEXT,
                passes_trend_template INTEGER DEFAULT 0,
                tt_criteria_met TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (scan_id) REFERENCES momentum_scans(id)
            )
        """)

        # VCP pattern tracking
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vcp_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                detected_date TEXT NOT NULL,
                num_contractions INTEGER,
                contraction_depths TEXT,
                pivot_price REAL,
                current_price REAL,
                pct_from_pivot REAL,
                volume_trend TEXT,
                notation TEXT,
                base_duration_weeks REAL,
                status TEXT DEFAULT 'active',
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            )
        """)

        # Add new VCP quality columns (safe to run multiple times)
        for col, col_type in [('ema_21', 'REAL'), ('near_21ema', 'INTEGER'),
                               ('has_inside_bar', 'INTEGER'), ('quality_score', 'INTEGER')]:
            try:
                cursor.execute(f"ALTER TABLE vcp_patterns ADD COLUMN {col} {col_type}")
            except sqlite3.OperationalError:
                pass  # Column already exists

        # Breakout alerts
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS breakout_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                breakout_date TEXT NOT NULL,
                breakout_price REAL,
                volume_ratio REAL,
                suggested_stop REAL,
                risk_pct REAL,
                pattern_id INTEGER,
                status TEXT DEFAULT 'new',
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (pattern_id) REFERENCES vcp_patterns(id)
            )
        """)

        # Portfolio positions
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS momentum_positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                entry_date TEXT,
                entry_price REAL,
                quantity INTEGER DEFAULT 0,
                stop_loss REAL,
                target_price REAL,
                current_price REAL,
                pnl REAL DEFAULT 0,
                pnl_pct REAL DEFAULT 0,
                status TEXT DEFAULT 'open',
                exit_date TEXT,
                exit_price REAL,
                notes TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            )
        """)

        # NSE stock universe (cached)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS nse_stocks (
                symbol TEXT PRIMARY KEY,
                company_name TEXT,
                isin TEXT,
                sector TEXT,
                industry TEXT,
                is_fno INTEGER DEFAULT 0,
                market_cap_cr REAL,
                last_updated TEXT DEFAULT (datetime('now'))
            )
        """)

        # Create indices
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_results_scan ON momentum_results(scan_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_results_symbol ON momentum_results(symbol)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_scans_date ON momentum_scans(scan_date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vcp_symbol ON vcp_patterns(symbol)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_breakout_date ON breakout_alerts(breakout_date)")

        conn.commit()
        conn.close()

    # --- Scan operations ---

    def create_scan(self, scan_date: str, scan_type: str = 'trend_template',
                    total_scanned: int = 0) -> int:
        conn = self._get_conn()
        try:
            cursor = conn.execute("""
                INSERT OR REPLACE INTO momentum_scans
                (scan_date, scan_type, total_stocks_scanned)
                VALUES (?, ?, ?)
            """, (scan_date, scan_type, total_scanned))
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def update_scan(self, scan_id: int, qualifying_count: int, duration_sec: float):
        conn = self._get_conn()
        try:
            conn.execute("""
                UPDATE momentum_scans
                SET qualifying_count = ?, scan_duration_sec = ?
                WHERE id = ?
            """, (qualifying_count, duration_sec, scan_id))
            conn.commit()
        finally:
            conn.close()

    def save_result(self, scan_id: int, result: Dict):
        conn = self._get_conn()
        try:
            conn.execute("""
                INSERT INTO momentum_results
                (scan_id, symbol, company_name, close_price, sma_50, sma_150, sma_200,
                 sma_200_prev, rs_rating, pct_from_52w_high, pct_from_52w_low,
                 high_52w, low_52w, volume, avg_volume_50, volume_ratio,
                 sector, industry, market_cap, is_fno, tradingview_link,
                 passes_trend_template, tt_criteria_met)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                scan_id, result['symbol'], result.get('company_name', ''),
                result.get('close'), result.get('sma_50'), result.get('sma_150'),
                result.get('sma_200'), result.get('sma_200_prev'),
                result.get('rs_rating'), result.get('pct_from_52w_high'),
                result.get('pct_from_52w_low'), result.get('high_52w'),
                result.get('low_52w'), result.get('volume'),
                result.get('avg_volume_50'), result.get('volume_ratio'),
                result.get('sector', ''), result.get('industry', ''),
                result.get('market_cap'), result.get('is_fno', 0),
                result.get('tradingview_link', ''),
                1 if result.get('passes_trend_template') else 0,
                json.dumps(result.get('tt_criteria_met', {}))
            ))
            conn.commit()
        finally:
            conn.close()

    def save_results_batch(self, scan_id: int, results: List[Dict]):
        conn = self._get_conn()
        try:
            for result in results:
                conn.execute("""
                    INSERT INTO momentum_results
                    (scan_id, symbol, company_name, close_price, sma_50, sma_150, sma_200,
                     sma_200_prev, rs_rating, pct_from_52w_high, pct_from_52w_low,
                     high_52w, low_52w, volume, avg_volume_50, volume_ratio,
                     sector, industry, market_cap, is_fno, tradingview_link,
                     passes_trend_template, tt_criteria_met)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    scan_id, result['symbol'], result.get('company_name', ''),
                    result.get('close'), result.get('sma_50'), result.get('sma_150'),
                    result.get('sma_200'), result.get('sma_200_prev'),
                    result.get('rs_rating'), result.get('pct_from_52w_high'),
                    result.get('pct_from_52w_low'), result.get('high_52w'),
                    result.get('low_52w'), result.get('volume'),
                    result.get('avg_volume_50'), result.get('volume_ratio'),
                    result.get('sector', ''), result.get('industry', ''),
                    result.get('market_cap'), result.get('is_fno', 0),
                    result.get('tradingview_link', ''),
                    1 if result.get('passes_trend_template') else 0,
                    json.dumps(result.get('tt_criteria_met', {}))
                ))
            conn.commit()
        finally:
            conn.close()

    def get_latest_scan(self, scan_type: str = 'trend_template') -> Optional[Dict]:
        conn = self._get_conn()
        try:
            row = conn.execute("""
                SELECT * FROM momentum_scans
                WHERE scan_type = ?
                ORDER BY scan_date DESC LIMIT 1
            """, (scan_type,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_scan_results(self, scan_id: int, passes_only: bool = True) -> List[Dict]:
        conn = self._get_conn()
        try:
            query = "SELECT * FROM momentum_results WHERE scan_id = ?"
            if passes_only:
                query += " AND passes_trend_template = 1"
            query += " ORDER BY rs_rating DESC"
            rows = conn.execute(query, (scan_id,)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_scan_history(self, days: int = 30) -> List[Dict]:
        conn = self._get_conn()
        try:
            rows = conn.execute("""
                SELECT * FROM momentum_scans
                ORDER BY scan_date DESC
                LIMIT ?
            """, (days,)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # --- VCP operations ---

    def save_vcp_pattern(self, pattern: Dict) -> int:
        conn = self._get_conn()
        try:
            cursor = conn.execute("""
                INSERT INTO vcp_patterns
                (symbol, detected_date, num_contractions, contraction_depths,
                 pivot_price, current_price, pct_from_pivot, volume_trend,
                 notation, base_duration_weeks, status,
                 ema_21, near_21ema, has_inside_bar, quality_score)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                pattern['symbol'], pattern['detected_date'],
                pattern.get('num_contractions', 0),
                json.dumps(pattern.get('contraction_depths', [])),
                pattern.get('pivot_price'), pattern.get('current_price'),
                pattern.get('pct_from_pivot'), pattern.get('volume_trend', ''),
                pattern.get('notation', ''), pattern.get('base_duration_weeks'),
                pattern.get('status', 'active'),
                pattern.get('ema_21'), int(pattern.get('near_21ema', False)),
                int(pattern.get('has_inside_bar', False)),
                pattern.get('quality_score', 0),
            ))
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def get_active_vcp_patterns(self) -> List[Dict]:
        conn = self._get_conn()
        try:
            # Get most recent entry per symbol (deduplicates across scans)
            rows = conn.execute("""
                SELECT v.* FROM vcp_patterns v
                INNER JOIN (
                    SELECT symbol, MAX(id) as max_id
                    FROM vcp_patterns WHERE status = 'active'
                    GROUP BY symbol
                ) latest ON v.id = latest.max_id
                ORDER BY v.quality_score DESC, v.pct_from_pivot ASC
            """).fetchall()
            results = []
            for r in rows:
                d = dict(r)
                d['contraction_depths'] = json.loads(d['contraction_depths']) if d['contraction_depths'] else []
                results.append(d)
            return results
        finally:
            conn.close()

    # --- Breakout operations ---

    def save_breakout(self, alert: Dict) -> int:
        conn = self._get_conn()
        try:
            cursor = conn.execute("""
                INSERT INTO breakout_alerts
                (symbol, breakout_date, breakout_price, volume_ratio,
                 suggested_stop, risk_pct, pattern_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                alert['symbol'], alert['breakout_date'],
                alert.get('breakout_price'), alert.get('volume_ratio'),
                alert.get('suggested_stop'), alert.get('risk_pct'),
                alert.get('pattern_id')
            ))
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def get_recent_breakouts(self, days: int = 7) -> List[Dict]:
        conn = self._get_conn()
        try:
            rows = conn.execute("""
                SELECT b.*, v.notation, v.num_contractions
                FROM breakout_alerts b
                LEFT JOIN vcp_patterns v ON b.pattern_id = v.id
                WHERE b.breakout_date >= date('now', ? || ' days')
                ORDER BY b.breakout_date DESC
            """, (f'-{days}',)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # --- NSE stock universe ---

    def save_nse_stocks(self, stocks: List[Dict]):
        conn = self._get_conn()
        try:
            for stock in stocks:
                conn.execute("""
                    INSERT OR REPLACE INTO nse_stocks
                    (symbol, company_name, isin, sector, industry, is_fno,
                     market_cap_cr, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
                """, (
                    stock['symbol'], stock.get('company_name', ''),
                    stock.get('isin', ''), stock.get('sector', ''),
                    stock.get('industry', ''), stock.get('is_fno', 0),
                    stock.get('market_cap_cr')
                ))
            conn.commit()
        finally:
            conn.close()

    def get_nse_stocks(self, fno_only: bool = False) -> List[Dict]:
        conn = self._get_conn()
        try:
            query = "SELECT * FROM nse_stocks"
            if fno_only:
                query += " WHERE is_fno = 1"
            query += " ORDER BY symbol"
            rows = conn.execute(query).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # --- Dashboard summary ---

    def get_dashboard_summary(self) -> Dict:
        conn = self._get_conn()
        try:
            # Latest scan info
            latest_scan = conn.execute("""
                SELECT * FROM momentum_scans
                ORDER BY scan_date DESC LIMIT 1
            """).fetchone()

            # Count qualifying stocks from latest scan
            qualifying = 0
            if latest_scan:
                row = conn.execute("""
                    SELECT COUNT(*) as cnt FROM momentum_results
                    WHERE scan_id = ? AND passes_trend_template = 1
                """, (latest_scan['id'],)).fetchone()
                qualifying = row['cnt'] if row else 0

            # Active VCP count
            vcp_row = conn.execute("""
                SELECT COUNT(*) as cnt FROM vcp_patterns WHERE status = 'active'
            """).fetchone()

            # Recent breakouts (7 days)
            breakout_row = conn.execute("""
                SELECT COUNT(*) as cnt FROM breakout_alerts
                WHERE breakout_date >= date('now', '-7 days')
            """).fetchone()

            return {
                'last_scan_date': latest_scan['scan_date'] if latest_scan else None,
                'total_scanned': latest_scan['total_stocks_scanned'] if latest_scan else 0,
                'qualifying_count': qualifying,
                'active_vcp_count': vcp_row['cnt'] if vcp_row else 0,
                'recent_breakouts': breakout_row['cnt'] if breakout_row else 0,
            }
        finally:
            conn.close()
