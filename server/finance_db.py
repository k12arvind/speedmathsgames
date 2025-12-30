#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
finance_db.py

Database operations for Personal Finance Module.
Tracks bank accounts, assets, stocks, liabilities, and net worth.

Access restricted to: Arvind & Deepa only
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime, date
from typing import Dict, List, Optional, Any
from contextlib import contextmanager


class FinanceDatabase:
    """Database manager for personal finance tracking."""
    
    def __init__(self, db_path: Optional[str] = None):
        """Initialize database connection."""
        if db_path is None:
            db_path = Path(__file__).parent.parent / 'finance_tracker.db'
        self.db_path = Path(db_path)
        self._init_db()
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def _init_db(self):
        """Initialize database schema."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Bank Accounts
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS bank_accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_name TEXT NOT NULL,
                    bank_name TEXT NOT NULL,
                    account_type TEXT NOT NULL,
                    account_number TEXT,
                    current_balance REAL DEFAULT 0,
                    interest_rate REAL,
                    maturity_date TEXT,
                    owner TEXT NOT NULL,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Balance History
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS balance_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_id INTEGER NOT NULL,
                    balance REAL NOT NULL,
                    recorded_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (account_id) REFERENCES bank_accounts(id) ON DELETE CASCADE
                )
            ''')
            
            # Assets
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS assets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    asset_type TEXT NOT NULL,
                    name TEXT NOT NULL,
                    purchase_date TEXT,
                    purchase_price REAL,
                    current_value REAL,
                    quantity REAL,
                    location TEXT,
                    details TEXT,
                    owner TEXT NOT NULL,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Asset Value History
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS asset_value_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    asset_id INTEGER NOT NULL,
                    value REAL NOT NULL,
                    recorded_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (asset_id) REFERENCES assets(id) ON DELETE CASCADE
                )
            ''')
            
            # Stock Holdings
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS stock_holdings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    exchange TEXT DEFAULT 'NSE',
                    company_name TEXT,
                    quantity INTEGER NOT NULL,
                    avg_buy_price REAL NOT NULL,
                    current_price REAL,
                    current_value REAL,
                    profit_loss REAL,
                    profit_loss_percent REAL,
                    source TEXT DEFAULT 'manual',
                    mstock_isin TEXT,
                    owner TEXT NOT NULL,
                    last_price_update TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(symbol, exchange, owner)
                )
            ''')
            
            # Stock Watchlist
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS stock_watchlist (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    exchange TEXT DEFAULT 'NSE',
                    company_name TEXT,
                    current_price REAL,
                    target_price REAL,
                    stop_loss REAL,
                    research_notes TEXT,
                    rating TEXT,
                    added_by TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Dividends
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS dividends (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    company_name TEXT,
                    dividend_amount REAL NOT NULL,
                    ex_date TEXT,
                    record_date TEXT,
                    payment_date TEXT,
                    shares_held INTEGER,
                    total_received REAL,
                    owner TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Liabilities
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS liabilities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    liability_type TEXT NOT NULL,
                    name TEXT NOT NULL,
                    lender TEXT,
                    principal_amount REAL,
                    interest_rate REAL,
                    emi_amount REAL,
                    tenure_months INTEGER,
                    start_date TEXT,
                    end_date TEXT,
                    outstanding_balance REAL,
                    owner TEXT NOT NULL,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Liability Payments
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS liability_payments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    liability_id INTEGER NOT NULL,
                    payment_date TEXT NOT NULL,
                    amount REAL NOT NULL,
                    principal_paid REAL,
                    interest_paid REAL,
                    balance_after REAL,
                    notes TEXT,
                    FOREIGN KEY (liability_id) REFERENCES liabilities(id) ON DELETE CASCADE
                )
            ''')
            
            # Net Worth History
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS net_worth_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    snapshot_date TEXT NOT NULL UNIQUE,
                    total_bank_balance REAL,
                    total_assets REAL,
                    total_stocks REAL,
                    total_liabilities REAL,
                    net_worth REAL,
                    breakdown TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # MStock Configuration
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS mstock_config (
                    id INTEGER PRIMARY KEY DEFAULT 1,
                    api_key TEXT,
                    client_id TEXT,
                    access_token TEXT,
                    token_expiry TEXT,
                    last_sync TEXT,
                    auto_sync_enabled INTEGER DEFAULT 1,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create indexes
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_balance_history_account ON balance_history(account_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_asset_value_history_asset ON asset_value_history(asset_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_stock_holdings_symbol ON stock_holdings(symbol)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_liability_payments_liability ON liability_payments(liability_id)')
    
    # =========================================================================
    # BANK ACCOUNTS
    # =========================================================================
    
    def get_accounts(self, owner: Optional[str] = None) -> List[Dict]:
        """Get all bank accounts, optionally filtered by owner."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if owner:
                cursor.execute(
                    'SELECT * FROM bank_accounts WHERE owner = ? ORDER BY bank_name, account_name',
                    (owner,)
                )
            else:
                cursor.execute('SELECT * FROM bank_accounts ORDER BY owner, bank_name, account_name')
            return [dict(row) for row in cursor.fetchall()]
    
    def get_account(self, account_id: int) -> Optional[Dict]:
        """Get a specific bank account."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM bank_accounts WHERE id = ?', (account_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def add_account(self, data: Dict) -> int:
        """Add a new bank account."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO bank_accounts 
                (account_name, bank_name, account_type, account_number, current_balance,
                 interest_rate, maturity_date, owner, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                data['account_name'],
                data['bank_name'],
                data['account_type'],
                data.get('account_number'),
                data.get('current_balance', 0),
                data.get('interest_rate'),
                data.get('maturity_date'),
                data['owner'],
                data.get('notes')
            ))
            account_id = cursor.lastrowid
            
            # Record initial balance in history
            if data.get('current_balance', 0) > 0:
                cursor.execute(
                    'INSERT INTO balance_history (account_id, balance) VALUES (?, ?)',
                    (account_id, data.get('current_balance', 0))
                )
            
            return account_id
    
    def update_account(self, account_id: int, data: Dict) -> bool:
        """Update a bank account."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE bank_accounts 
                SET account_name = ?, bank_name = ?, account_type = ?, 
                    account_number = ?, interest_rate = ?, maturity_date = ?,
                    notes = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (
                data.get('account_name'),
                data.get('bank_name'),
                data.get('account_type'),
                data.get('account_number'),
                data.get('interest_rate'),
                data.get('maturity_date'),
                data.get('notes'),
                account_id
            ))
            return cursor.rowcount > 0
    
    def update_account_balance(self, account_id: int, balance: float) -> bool:
        """Update account balance and record in history."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE bank_accounts SET current_balance = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                (balance, account_id)
            )
            cursor.execute(
                'INSERT INTO balance_history (account_id, balance) VALUES (?, ?)',
                (account_id, balance)
            )
            return cursor.rowcount > 0
    
    def delete_account(self, account_id: int) -> bool:
        """Delete a bank account."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM bank_accounts WHERE id = ?', (account_id,))
            return cursor.rowcount > 0
    
    def get_balance_history(self, account_id: int, limit: int = 12) -> List[Dict]:
        """Get balance history for an account."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT * FROM balance_history WHERE account_id = ? ORDER BY recorded_at DESC LIMIT ?',
                (account_id, limit)
            )
            return [dict(row) for row in cursor.fetchall()]
    
    # =========================================================================
    # ASSETS
    # =========================================================================
    
    def get_assets(self, owner: Optional[str] = None, asset_type: Optional[str] = None) -> List[Dict]:
        """Get all assets with optional filters."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            query = 'SELECT * FROM assets WHERE 1=1'
            params = []
            
            if owner:
                query += ' AND owner = ?'
                params.append(owner)
            if asset_type:
                query += ' AND asset_type = ?'
                params.append(asset_type)
            
            query += ' ORDER BY asset_type, name'
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    
    def get_asset(self, asset_id: int) -> Optional[Dict]:
        """Get a specific asset."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM assets WHERE id = ?', (asset_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def add_asset(self, data: Dict) -> int:
        """Add a new asset."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            details = json.dumps(data.get('details', {})) if data.get('details') else None
            cursor.execute('''
                INSERT INTO assets 
                (asset_type, name, purchase_date, purchase_price, current_value,
                 quantity, location, details, owner, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                data['asset_type'],
                data['name'],
                data.get('purchase_date'),
                data.get('purchase_price'),
                data.get('current_value'),
                data.get('quantity'),
                data.get('location'),
                details,
                data['owner'],
                data.get('notes')
            ))
            asset_id = cursor.lastrowid
            
            # Record initial value in history
            if data.get('current_value'):
                cursor.execute(
                    'INSERT INTO asset_value_history (asset_id, value) VALUES (?, ?)',
                    (asset_id, data.get('current_value'))
                )
            
            return asset_id
    
    def update_asset(self, asset_id: int, data: Dict) -> bool:
        """Update an asset."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            details = json.dumps(data.get('details', {})) if data.get('details') else None
            cursor.execute('''
                UPDATE assets 
                SET asset_type = ?, name = ?, purchase_date = ?, purchase_price = ?,
                    quantity = ?, location = ?, details = ?, notes = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (
                data.get('asset_type'),
                data.get('name'),
                data.get('purchase_date'),
                data.get('purchase_price'),
                data.get('quantity'),
                data.get('location'),
                details,
                data.get('notes'),
                asset_id
            ))
            return cursor.rowcount > 0
    
    def update_asset_value(self, asset_id: int, value: float) -> bool:
        """Update asset value and record in history."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE assets SET current_value = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                (value, asset_id)
            )
            cursor.execute(
                'INSERT INTO asset_value_history (asset_id, value) VALUES (?, ?)',
                (asset_id, value)
            )
            return cursor.rowcount > 0
    
    def delete_asset(self, asset_id: int) -> bool:
        """Delete an asset."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM assets WHERE id = ?', (asset_id,))
            return cursor.rowcount > 0
    
    # =========================================================================
    # STOCK HOLDINGS
    # =========================================================================
    
    def get_stock_holdings(self, owner: Optional[str] = None) -> List[Dict]:
        """Get all stock holdings."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if owner:
                cursor.execute(
                    'SELECT * FROM stock_holdings WHERE owner = ? ORDER BY symbol',
                    (owner,)
                )
            else:
                cursor.execute('SELECT * FROM stock_holdings ORDER BY owner, symbol')
            return [dict(row) for row in cursor.fetchall()]
    
    def get_stock_holding(self, holding_id: int) -> Optional[Dict]:
        """Get a specific stock holding."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM stock_holdings WHERE id = ?', (holding_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def add_stock_holding(self, data: Dict) -> int:
        """Add a new stock holding."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            current_value = data.get('quantity', 0) * data.get('current_price', data.get('avg_buy_price', 0))
            invested = data.get('quantity', 0) * data.get('avg_buy_price', 0)
            profit_loss = current_value - invested if invested > 0 else 0
            profit_loss_percent = (profit_loss / invested * 100) if invested > 0 else 0
            
            cursor.execute('''
                INSERT INTO stock_holdings 
                (symbol, exchange, company_name, quantity, avg_buy_price, current_price,
                 current_value, profit_loss, profit_loss_percent, source, mstock_isin, owner)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                data['symbol'].upper(),
                data.get('exchange', 'NSE'),
                data.get('company_name'),
                data['quantity'],
                data['avg_buy_price'],
                data.get('current_price', data.get('avg_buy_price')),
                current_value,
                profit_loss,
                profit_loss_percent,
                data.get('source', 'manual'),
                data.get('mstock_isin'),
                data['owner']
            ))
            return cursor.lastrowid
    
    def update_stock_holding(self, holding_id: int, data: Dict) -> bool:
        """Update a stock holding."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE stock_holdings 
                SET quantity = ?, avg_buy_price = ?, company_name = ?, notes = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (
                data.get('quantity'),
                data.get('avg_buy_price'),
                data.get('company_name'),
                data.get('notes'),
                holding_id
            ))
            return cursor.rowcount > 0
    
    def update_stock_prices(self, prices: Dict[str, float]) -> int:
        """Update current prices for multiple stocks. Returns count updated."""
        updated = 0
        with self.get_connection() as conn:
            cursor = conn.cursor()
            for symbol, price in prices.items():
                cursor.execute('''
                    UPDATE stock_holdings 
                    SET current_price = ?,
                        current_value = quantity * ?,
                        profit_loss = (quantity * ?) - (quantity * avg_buy_price),
                        profit_loss_percent = CASE 
                            WHEN avg_buy_price > 0 THEN ((? - avg_buy_price) / avg_buy_price * 100)
                            ELSE 0 
                        END,
                        last_price_update = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE symbol = ?
                ''', (price, price, price, price, symbol.upper()))
                updated += cursor.rowcount
        return updated
    
    def delete_stock_holding(self, holding_id: int) -> bool:
        """Delete a stock holding."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM stock_holdings WHERE id = ?', (holding_id,))
            return cursor.rowcount > 0
    
    def upsert_stock_from_mstock(self, data: Dict) -> int:
        """Insert or update stock from MStock sync."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Check if exists
            cursor.execute(
                'SELECT id FROM stock_holdings WHERE symbol = ? AND owner = ?',
                (data['symbol'].upper(), data['owner'])
            )
            existing = cursor.fetchone()
            
            current_value = data.get('quantity', 0) * data.get('current_price', 0)
            invested = data.get('quantity', 0) * data.get('avg_buy_price', 0)
            profit_loss = current_value - invested
            profit_loss_percent = (profit_loss / invested * 100) if invested > 0 else 0
            
            if existing:
                cursor.execute('''
                    UPDATE stock_holdings 
                    SET quantity = ?, avg_buy_price = ?, current_price = ?,
                        current_value = ?, profit_loss = ?, profit_loss_percent = ?,
                        mstock_isin = ?, company_name = ?, source = 'mstock',
                        last_price_update = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (
                    data['quantity'], data['avg_buy_price'], data.get('current_price'),
                    current_value, profit_loss, profit_loss_percent,
                    data.get('mstock_isin'), data.get('company_name'), existing[0]
                ))
                return existing[0]
            else:
                cursor.execute('''
                    INSERT INTO stock_holdings 
                    (symbol, exchange, company_name, quantity, avg_buy_price, current_price,
                     current_value, profit_loss, profit_loss_percent, source, mstock_isin, owner)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'mstock', ?, ?)
                ''', (
                    data['symbol'].upper(), data.get('exchange', 'NSE'), data.get('company_name'),
                    data['quantity'], data['avg_buy_price'], data.get('current_price'),
                    current_value, profit_loss, profit_loss_percent,
                    data.get('mstock_isin'), data['owner']
                ))
                return cursor.lastrowid
    
    # =========================================================================
    # WATCHLIST
    # =========================================================================
    
    def get_watchlist(self, added_by: Optional[str] = None) -> List[Dict]:
        """Get stock watchlist."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if added_by:
                cursor.execute(
                    'SELECT * FROM stock_watchlist WHERE added_by = ? ORDER BY symbol',
                    (added_by,)
                )
            else:
                cursor.execute('SELECT * FROM stock_watchlist ORDER BY added_by, symbol')
            return [dict(row) for row in cursor.fetchall()]
    
    def add_to_watchlist(self, data: Dict) -> int:
        """Add stock to watchlist."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO stock_watchlist 
                (symbol, exchange, company_name, current_price, target_price,
                 stop_loss, research_notes, rating, added_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                data['symbol'].upper(),
                data.get('exchange', 'NSE'),
                data.get('company_name'),
                data.get('current_price'),
                data.get('target_price'),
                data.get('stop_loss'),
                data.get('research_notes'),
                data.get('rating'),
                data['added_by']
            ))
            return cursor.lastrowid
    
    def update_watchlist_item(self, item_id: int, data: Dict) -> bool:
        """Update watchlist item."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE stock_watchlist 
                SET target_price = ?, stop_loss = ?, research_notes = ?, rating = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (
                data.get('target_price'),
                data.get('stop_loss'),
                data.get('research_notes'),
                data.get('rating'),
                item_id
            ))
            return cursor.rowcount > 0
    
    def delete_from_watchlist(self, item_id: int) -> bool:
        """Remove from watchlist."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM stock_watchlist WHERE id = ?', (item_id,))
            return cursor.rowcount > 0
    
    # =========================================================================
    # LIABILITIES
    # =========================================================================
    
    def get_liabilities(self, owner: Optional[str] = None) -> List[Dict]:
        """Get all liabilities."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if owner:
                cursor.execute(
                    'SELECT * FROM liabilities WHERE owner = ? ORDER BY name',
                    (owner,)
                )
            else:
                cursor.execute('SELECT * FROM liabilities ORDER BY owner, name')
            return [dict(row) for row in cursor.fetchall()]
    
    def get_liability(self, liability_id: int) -> Optional[Dict]:
        """Get a specific liability."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM liabilities WHERE id = ?', (liability_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def add_liability(self, data: Dict) -> int:
        """Add a new liability."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO liabilities 
                (liability_type, name, lender, principal_amount, interest_rate,
                 emi_amount, tenure_months, start_date, end_date, outstanding_balance, owner, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                data['liability_type'],
                data['name'],
                data.get('lender'),
                data.get('principal_amount'),
                data.get('interest_rate'),
                data.get('emi_amount'),
                data.get('tenure_months'),
                data.get('start_date'),
                data.get('end_date'),
                data.get('outstanding_balance', data.get('principal_amount')),
                data['owner'],
                data.get('notes')
            ))
            return cursor.lastrowid
    
    def update_liability(self, liability_id: int, data: Dict) -> bool:
        """Update a liability."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE liabilities 
                SET liability_type = ?, name = ?, lender = ?, principal_amount = ?,
                    interest_rate = ?, emi_amount = ?, tenure_months = ?, start_date = ?,
                    end_date = ?, outstanding_balance = ?, notes = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (
                data.get('liability_type'),
                data.get('name'),
                data.get('lender'),
                data.get('principal_amount'),
                data.get('interest_rate'),
                data.get('emi_amount'),
                data.get('tenure_months'),
                data.get('start_date'),
                data.get('end_date'),
                data.get('outstanding_balance'),
                data.get('notes'),
                liability_id
            ))
            return cursor.rowcount > 0
    
    def record_liability_payment(self, liability_id: int, data: Dict) -> int:
        """Record a liability payment."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO liability_payments 
                (liability_id, payment_date, amount, principal_paid, interest_paid, balance_after, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                liability_id,
                data.get('payment_date', datetime.now().strftime('%Y-%m-%d')),
                data['amount'],
                data.get('principal_paid'),
                data.get('interest_paid'),
                data.get('balance_after'),
                data.get('notes')
            ))
            
            # Update outstanding balance if provided
            if data.get('balance_after') is not None:
                cursor.execute(
                    'UPDATE liabilities SET outstanding_balance = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                    (data.get('balance_after'), liability_id)
                )
            
            return cursor.lastrowid
    
    def get_liability_payments(self, liability_id: int) -> List[Dict]:
        """Get payment history for a liability."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT * FROM liability_payments WHERE liability_id = ? ORDER BY payment_date DESC',
                (liability_id,)
            )
            return [dict(row) for row in cursor.fetchall()]
    
    def delete_liability(self, liability_id: int) -> bool:
        """Delete a liability."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM liabilities WHERE id = ?', (liability_id,))
            return cursor.rowcount > 0
    
    # =========================================================================
    # NET WORTH & DASHBOARD
    # =========================================================================
    
    def get_dashboard_summary(self) -> Dict:
        """Get complete financial dashboard summary."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Total bank balances
            cursor.execute('SELECT SUM(current_balance) as total FROM bank_accounts')
            total_bank = cursor.fetchone()['total'] or 0
            
            # Bank accounts by type
            cursor.execute('''
                SELECT account_type, SUM(current_balance) as total 
                FROM bank_accounts GROUP BY account_type
            ''')
            bank_by_type = {row['account_type']: row['total'] for row in cursor.fetchall()}
            
            # Total assets
            cursor.execute('SELECT SUM(current_value) as total FROM assets')
            total_assets = cursor.fetchone()['total'] or 0
            
            # Assets by type
            cursor.execute('''
                SELECT asset_type, SUM(current_value) as total 
                FROM assets GROUP BY asset_type
            ''')
            assets_by_type = {row['asset_type']: row['total'] for row in cursor.fetchall()}
            
            # Total stocks
            cursor.execute('SELECT SUM(current_value) as total, SUM(profit_loss) as pnl FROM stock_holdings')
            stock_row = cursor.fetchone()
            total_stocks = stock_row['total'] or 0
            total_stock_pnl = stock_row['pnl'] or 0
            
            # Total liabilities
            cursor.execute('SELECT SUM(outstanding_balance) as total FROM liabilities')
            total_liabilities = cursor.fetchone()['total'] or 0
            
            # Liabilities by type
            cursor.execute('''
                SELECT liability_type, SUM(outstanding_balance) as total 
                FROM liabilities GROUP BY liability_type
            ''')
            liabilities_by_type = {row['liability_type']: row['total'] for row in cursor.fetchall()}
            
            # Net worth
            net_worth = total_bank + total_assets + total_stocks - total_liabilities
            
            return {
                'net_worth': net_worth,
                'total_bank_balance': total_bank,
                'bank_by_type': bank_by_type,
                'total_assets': total_assets,
                'assets_by_type': assets_by_type,
                'total_stocks': total_stocks,
                'stock_pnl': total_stock_pnl,
                'total_liabilities': total_liabilities,
                'liabilities_by_type': liabilities_by_type,
                'allocation': {
                    'Bank Accounts': total_bank,
                    'Assets': total_assets,
                    'Stocks': total_stocks,
                    'Liabilities': -total_liabilities
                }
            }
    
    def take_net_worth_snapshot(self) -> int:
        """Take a snapshot of current net worth."""
        summary = self.get_dashboard_summary()
        snapshot_date = date.today().strftime('%Y-%m-%d')
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO net_worth_history 
                (snapshot_date, total_bank_balance, total_assets, total_stocks,
                 total_liabilities, net_worth, breakdown)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                snapshot_date,
                summary['total_bank_balance'],
                summary['total_assets'],
                summary['total_stocks'],
                summary['total_liabilities'],
                summary['net_worth'],
                json.dumps(summary)
            ))
            return cursor.lastrowid
    
    def get_net_worth_history(self, months: int = 12) -> List[Dict]:
        """Get historical net worth data."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM net_worth_history 
                ORDER BY snapshot_date DESC LIMIT ?
            ''', (months,))
            return [dict(row) for row in cursor.fetchall()]
    
    # =========================================================================
    # MSTOCK CONFIG
    # =========================================================================
    
    def get_mstock_config(self) -> Optional[Dict]:
        """Get MStock API configuration."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM mstock_config WHERE id = 1')
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def save_mstock_config(self, data: Dict) -> bool:
        """Save MStock API configuration."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO mstock_config 
                (id, api_key, client_id, access_token, token_expiry, auto_sync_enabled, updated_at)
                VALUES (1, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (
                data.get('api_key'),
                data.get('client_id'),
                data.get('access_token'),
                data.get('token_expiry'),
                data.get('auto_sync_enabled', 1)
            ))
            return True
    
    def update_mstock_token(self, access_token: str, expiry: str) -> bool:
        """Update MStock access token."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE mstock_config 
                SET access_token = ?, token_expiry = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = 1
            ''', (access_token, expiry))
            return cursor.rowcount > 0
    
    def update_mstock_last_sync(self) -> bool:
        """Update last sync timestamp."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE mstock_config 
                SET last_sync = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                WHERE id = 1
            ''')
            return cursor.rowcount > 0
    
    # =========================================================================
    # RECURRING BILLS
    # =========================================================================
    
    def _init_bills_tables(self):
        """Initialize bill tracking tables."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Recurring Bills Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS recurring_bills (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    category TEXT NOT NULL,
                    account_number TEXT,
                    provider TEXT,
                    frequency TEXT NOT NULL DEFAULT 'monthly',
                    due_day INTEGER,
                    billing_month INTEGER,
                    typical_amount REAL,
                    property_id INTEGER,
                    reminder_days TEXT DEFAULT '7,3,2,1',
                    owner TEXT NOT NULL,
                    notes TEXT,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Bill Payments History
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS bill_payments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bill_id INTEGER NOT NULL,
                    due_date TEXT NOT NULL,
                    amount_due REAL,
                    amount_paid REAL,
                    payment_date TEXT,
                    payment_method TEXT,
                    status TEXT DEFAULT 'pending',
                    late_fee REAL DEFAULT 0,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (bill_id) REFERENCES recurring_bills(id) ON DELETE CASCADE
                )
            ''')
    
    def get_bills(self, owner: Optional[str] = None, category: Optional[str] = None) -> List[Dict]:
        """Get all recurring bills."""
        self._init_bills_tables()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            query = 'SELECT * FROM recurring_bills WHERE is_active = 1'
            params = []
            
            if owner:
                query += ' AND owner = ?'
                params.append(owner)
            if category:
                query += ' AND category = ?'
                params.append(category)
            
            query += ' ORDER BY due_day'
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    
    def get_bill(self, bill_id: int) -> Optional[Dict]:
        """Get a specific bill."""
        self._init_bills_tables()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM recurring_bills WHERE id = ?', (bill_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def add_bill(self, data: Dict) -> int:
        """Add a new recurring bill."""
        self._init_bills_tables()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO recurring_bills
                (name, category, account_number, provider, frequency, due_day, 
                 billing_month, typical_amount, property_id, reminder_days, owner, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                data['name'],
                data['category'],
                data.get('account_number'),
                data.get('provider'),
                data.get('frequency', 'monthly'),
                data.get('due_day'),
                data.get('billing_month'),
                data.get('typical_amount'),
                data.get('property_id'),
                data.get('reminder_days', '7,3,2,1'),
                data['owner'],
                data.get('notes')
            ))
            return cursor.lastrowid
    
    def update_bill(self, bill_id: int, data: Dict) -> bool:
        """Update a recurring bill."""
        self._init_bills_tables()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE recurring_bills 
                SET name = ?, category = ?, account_number = ?, provider = ?,
                    frequency = ?, due_day = ?, billing_month = ?, typical_amount = ?,
                    property_id = ?, reminder_days = ?, notes = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (
                data['name'],
                data['category'],
                data.get('account_number'),
                data.get('provider'),
                data.get('frequency', 'monthly'),
                data.get('due_day'),
                data.get('billing_month'),
                data.get('typical_amount'),
                data.get('property_id'),
                data.get('reminder_days', '7,3,2,1'),
                data.get('notes'),
                bill_id
            ))
            return cursor.rowcount > 0
    
    def delete_bill(self, bill_id: int) -> bool:
        """Soft delete a bill."""
        self._init_bills_tables()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE recurring_bills SET is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                (bill_id,)
            )
            return cursor.rowcount > 0
    
    def get_bill_payments(self, bill_id: int, limit: int = 12) -> List[Dict]:
        """Get payment history for a bill."""
        self._init_bills_tables()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM bill_payments 
                WHERE bill_id = ? 
                ORDER BY due_date DESC 
                LIMIT ?
            ''', (bill_id, limit))
            return [dict(row) for row in cursor.fetchall()]
    
    def add_bill_payment(self, bill_id: int, data: Dict) -> int:
        """Add a payment record for a bill."""
        self._init_bills_tables()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO bill_payments
                (bill_id, due_date, amount_due, amount_paid, payment_date, payment_method, status, late_fee, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                bill_id,
                data['due_date'],
                data.get('amount_due'),
                data.get('amount_paid'),
                data.get('payment_date'),
                data.get('payment_method'),
                data.get('status', 'pending'),
                data.get('late_fee', 0),
                data.get('notes')
            ))
            return cursor.lastrowid
    
    def update_bill_payment(self, payment_id: int, data: Dict) -> bool:
        """Update a payment record."""
        self._init_bills_tables()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE bill_payments 
                SET amount_due = ?, amount_paid = ?, payment_date = ?, 
                    payment_method = ?, status = ?, late_fee = ?, notes = ?
                WHERE id = ?
            ''', (
                data.get('amount_due'),
                data.get('amount_paid'),
                data.get('payment_date'),
                data.get('payment_method'),
                data.get('status'),
                data.get('late_fee', 0),
                data.get('notes'),
                payment_id
            ))
            return cursor.rowcount > 0
    
    def mark_bill_paid(self, payment_id: int, amount_paid: float, payment_method: str = None) -> bool:
        """Mark a bill payment as paid."""
        self._init_bills_tables()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE bill_payments 
                SET amount_paid = ?, payment_date = DATE('now'), status = 'paid', payment_method = ?
                WHERE id = ?
            ''', (amount_paid, payment_method, payment_id))
            return cursor.rowcount > 0
    
    def get_upcoming_bills(self, days: int = 7) -> List[Dict]:
        """Get bills due in the next N days."""
        self._init_bills_tables()
        from datetime import datetime, timedelta
        
        today = datetime.now()
        bills = self.get_bills()
        upcoming = []
        
        for bill in bills:
            next_due = self._calculate_next_due_date(bill)
            if next_due:
                days_until = (next_due - today.date()).days
                if 0 <= days_until <= days:
                    bill['next_due_date'] = next_due.isoformat()
                    bill['days_until_due'] = days_until
                    bill['urgency'] = 'high' if days_until <= 2 else 'medium' if days_until <= 3 else 'normal'
                    
                    # Check if payment record exists for this cycle
                    payment = self._get_current_payment(bill['id'], next_due)
                    bill['current_payment'] = payment
                    
                    upcoming.append(bill)
        
        return sorted(upcoming, key=lambda x: x['days_until_due'])
    
    def get_overdue_bills(self) -> List[Dict]:
        """Get overdue bills."""
        self._init_bills_tables()
        from datetime import datetime
        
        today = datetime.now()
        bills = self.get_bills()
        overdue = []
        
        for bill in bills:
            next_due = self._calculate_next_due_date(bill)
            if next_due:
                days_until = (next_due - today.date()).days
                if days_until < 0:
                    # Check if already paid
                    payment = self._get_current_payment(bill['id'], next_due)
                    if not payment or payment.get('status') != 'paid':
                        bill['next_due_date'] = next_due.isoformat()
                        bill['days_overdue'] = abs(days_until)
                        bill['current_payment'] = payment
                        overdue.append(bill)
        
        return sorted(overdue, key=lambda x: x['days_overdue'], reverse=True)
    
    def get_bills_summary(self, month: int = None, year: int = None) -> Dict:
        """Get bills summary for a month."""
        self._init_bills_tables()
        from datetime import datetime
        
        if not month:
            month = datetime.now().month
        if not year:
            year = datetime.now().year
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Get payments for the month
            start_date = f"{year}-{month:02d}-01"
            if month == 12:
                end_date = f"{year + 1}-01-01"
            else:
                end_date = f"{year}-{month + 1:02d}-01"
            
            cursor.execute('''
                SELECT 
                    COUNT(*) as total_bills,
                    SUM(CASE WHEN status = 'paid' THEN 1 ELSE 0 END) as paid_count,
                    SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending_count,
                    SUM(CASE WHEN status = 'overdue' THEN 1 ELSE 0 END) as overdue_count,
                    SUM(COALESCE(amount_due, 0)) as total_due,
                    SUM(CASE WHEN status = 'paid' THEN COALESCE(amount_paid, 0) ELSE 0 END) as total_paid,
                    SUM(CASE WHEN status != 'paid' THEN COALESCE(amount_due, 0) ELSE 0 END) as total_pending
                FROM bill_payments
                WHERE due_date >= ? AND due_date < ?
            ''', (start_date, end_date))
            
            row = cursor.fetchone()
            return {
                'month': month,
                'year': year,
                'total_bills': row['total_bills'] or 0,
                'paid_count': row['paid_count'] or 0,
                'pending_count': row['pending_count'] or 0,
                'overdue_count': row['overdue_count'] or 0,
                'total_due': row['total_due'] or 0,
                'total_paid': row['total_paid'] or 0,
                'total_pending': row['total_pending'] or 0,
            }
    
    def _calculate_next_due_date(self, bill: Dict) -> Optional[date]:
        """Calculate the next due date for a bill."""
        from datetime import datetime, timedelta
        from calendar import monthrange
        
        today = datetime.now().date()
        due_day = bill.get('due_day')
        frequency = bill.get('frequency', 'monthly')
        
        if not due_day:
            return None
        
        if frequency == 'monthly':
            # Find next occurrence of due_day
            year, month = today.year, today.month
            
            # Handle months with fewer days
            _, last_day = monthrange(year, month)
            actual_due_day = min(due_day, last_day)
            
            due_date = today.replace(day=actual_due_day)
            
            # If already passed this month, move to next month
            if due_date < today:
                if month == 12:
                    year += 1
                    month = 1
                else:
                    month += 1
                _, last_day = monthrange(year, month)
                actual_due_day = min(due_day, last_day)
                due_date = today.replace(year=year, month=month, day=actual_due_day)
            
            return due_date
        
        elif frequency == 'quarterly':
            billing_month = bill.get('billing_month', 1)
            quarter_months = [billing_month, billing_month + 3, billing_month + 6, billing_month + 9]
            quarter_months = [m if m <= 12 else m - 12 for m in quarter_months]
            
            for m in sorted(quarter_months):
                year = today.year
                if m < today.month:
                    continue
                _, last_day = monthrange(year, m)
                actual_due_day = min(due_day, last_day)
                due_date = today.replace(month=m, day=actual_due_day)
                if due_date >= today:
                    return due_date
            
            # Next year
            m = min(quarter_months)
            year = today.year + 1
            _, last_day = monthrange(year, m)
            actual_due_day = min(due_day, last_day)
            return date(year, m, actual_due_day)
        
        elif frequency == 'half_yearly':
            billing_month = bill.get('billing_month', 1)
            half_months = [billing_month, billing_month + 6]
            half_months = [m if m <= 12 else m - 12 for m in half_months]
            
            for m in sorted(half_months):
                year = today.year
                _, last_day = monthrange(year, m)
                actual_due_day = min(due_day, last_day)
                due_date = date(year, m, actual_due_day)
                if due_date >= today:
                    return due_date
            
            m = min(half_months)
            year = today.year + 1
            _, last_day = monthrange(year, m)
            actual_due_day = min(due_day, last_day)
            return date(year, m, actual_due_day)
        
        elif frequency == 'yearly':
            billing_month = bill.get('billing_month', 1)
            year = today.year
            _, last_day = monthrange(year, billing_month)
            actual_due_day = min(due_day, last_day)
            due_date = date(year, billing_month, actual_due_day)
            
            if due_date < today:
                year += 1
                _, last_day = monthrange(year, billing_month)
                actual_due_day = min(due_day, last_day)
                due_date = date(year, billing_month, actual_due_day)
            
            return due_date
        
        return None
    
    def _get_current_payment(self, bill_id: int, due_date) -> Optional[Dict]:
        """Get payment record for current billing cycle."""
        self._init_bills_tables()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM bill_payments 
                WHERE bill_id = ? AND due_date = ?
            ''', (bill_id, due_date.isoformat()))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def ensure_payment_record(self, bill_id: int, due_date: str) -> int:
        """Ensure a payment record exists for the billing cycle."""
        self._init_bills_tables()
        
        # Check if record exists
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id FROM bill_payments 
                WHERE bill_id = ? AND due_date = ?
            ''', (bill_id, due_date))
            row = cursor.fetchone()
            
            if row:
                return row['id']
            
            # Get bill details for typical amount
            bill = self.get_bill(bill_id)
            
            # Create new payment record
            cursor.execute('''
                INSERT INTO bill_payments (bill_id, due_date, amount_due, status)
                VALUES (?, ?, ?, 'pending')
            ''', (bill_id, due_date, bill.get('typical_amount') if bill else None))
            
            return cursor.lastrowid
    
    # =========================================================================
    # BILL REMINDERS & NOTIFICATIONS
    # =========================================================================
    
    def _init_reminders_table(self):
        """Initialize bill reminders table."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS bill_reminders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bill_id INTEGER NOT NULL,
                    due_date TEXT NOT NULL,
                    reminder_date TEXT NOT NULL,
                    days_before INTEGER NOT NULL,
                    status TEXT DEFAULT 'pending',
                    sent_at TEXT,
                    notification_type TEXT DEFAULT 'dashboard',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (bill_id) REFERENCES recurring_bills(id) ON DELETE CASCADE,
                    UNIQUE(bill_id, due_date, days_before)
                )
            ''')
    
    def get_pending_reminders(self) -> List[Dict]:
        """Get all pending reminders for today or overdue."""
        self._init_reminders_table()
        from datetime import datetime
        today = datetime.now().date().isoformat()
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT r.*, b.name as bill_name, b.category, b.typical_amount, b.owner
                FROM bill_reminders r
                JOIN recurring_bills b ON r.bill_id = b.id
                WHERE r.status = 'pending' AND r.reminder_date <= ?
                ORDER BY r.reminder_date, r.days_before
            ''', (today,))
            return [dict(row) for row in cursor.fetchall()]
    
    def generate_reminders_for_bill(self, bill: Dict) -> int:
        """Generate reminder records for a bill's upcoming due date."""
        self._init_reminders_table()
        
        next_due = self._calculate_next_due_date(bill)
        if not next_due:
            return 0
        
        reminder_days = [int(d) for d in bill.get('reminder_days', '7,3,2,1').split(',')]
        generated = 0
        
        from datetime import timedelta
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            for days in reminder_days:
                reminder_date = next_due - timedelta(days=days)
                
                try:
                    cursor.execute('''
                        INSERT OR IGNORE INTO bill_reminders 
                        (bill_id, due_date, reminder_date, days_before, status)
                        VALUES (?, ?, ?, ?, 'pending')
                    ''', (bill['id'], next_due.isoformat(), reminder_date.isoformat(), days))
                    if cursor.rowcount > 0:
                        generated += 1
                except:
                    pass
            
            return generated
    
    def generate_all_reminders(self) -> int:
        """Generate reminders for all active bills."""
        bills = self.get_bills()
        total = 0
        for bill in bills:
            total += self.generate_reminders_for_bill(bill)
        return total
    
    def mark_reminder_sent(self, reminder_id: int) -> bool:
        """Mark a reminder as sent."""
        self._init_reminders_table()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE bill_reminders 
                SET status = 'sent', sent_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (reminder_id,))
            return cursor.rowcount > 0
    
    def dismiss_reminder(self, reminder_id: int) -> bool:
        """Dismiss a reminder."""
        self._init_reminders_table()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE bill_reminders 
                SET status = 'dismissed', sent_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (reminder_id,))
            return cursor.rowcount > 0
    
    def get_dashboard_notifications(self) -> List[Dict]:
        """Get notifications for dashboard display."""
        notifications = []
        
        # Get overdue bills
        overdue = self.get_overdue_bills()
        for bill in overdue:
            notifications.append({
                'type': 'overdue',
                'severity': 'high',
                'title': f'{bill["name"]} is overdue!',
                'message': f'{bill["days_overdue"]} days overdue - ₹{bill.get("typical_amount", 0):,.0f}',
                'bill_id': bill['id'],
                'due_date': bill['next_due_date']
            })
        
        # Get upcoming reminders
        reminders = self.get_pending_reminders()
        for r in reminders:
            if r['days_before'] == 1:
                severity = 'high'
                title = f'{r["bill_name"]} is due tomorrow!'
            elif r['days_before'] <= 3:
                severity = 'medium'
                title = f'{r["bill_name"]} due in {r["days_before"]} days'
            else:
                severity = 'low'
                title = f'{r["bill_name"]} due in {r["days_before"]} days'
            
            notifications.append({
                'type': 'reminder',
                'severity': severity,
                'title': title,
                'message': f'Due: {r["due_date"]} - ₹{r.get("typical_amount", 0):,.0f}',
                'bill_id': r['bill_id'],
                'reminder_id': r['id'],
                'due_date': r['due_date']
            })
        
        return sorted(notifications, key=lambda x: (
            0 if x['severity'] == 'high' else 1 if x['severity'] == 'medium' else 2
        ))
    
    # =========================================================================
    # BILL ANALYTICS
    # =========================================================================
    
    def get_bill_analytics(self, months: int = 12) -> Dict:
        """Get bill payment analytics for the last N months."""
        self._init_bills_tables()
        from datetime import datetime, timedelta
        from calendar import monthrange
        
        today = datetime.now()
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Monthly spending by category
            monthly_by_category = []
            for i in range(months - 1, -1, -1):
                # Calculate month
                month = today.month - i
                year = today.year
                while month <= 0:
                    month += 12
                    year -= 1
                
                start_date = f"{year}-{month:02d}-01"
                _, last_day = monthrange(year, month)
                end_date = f"{year}-{month:02d}-{last_day}"
                
                cursor.execute('''
                    SELECT 
                        b.category,
                        SUM(COALESCE(p.amount_paid, 0)) as total_paid,
                        COUNT(CASE WHEN p.status = 'paid' THEN 1 END) as paid_count
                    FROM bill_payments p
                    JOIN recurring_bills b ON p.bill_id = b.id
                    WHERE p.due_date >= ? AND p.due_date <= ?
                    GROUP BY b.category
                ''', (start_date, end_date))
                
                category_data = {}
                for row in cursor.fetchall():
                    category_data[row['category']] = {
                        'total_paid': row['total_paid'] or 0,
                        'paid_count': row['paid_count'] or 0
                    }
                
                monthly_by_category.append({
                    'month': f"{year}-{month:02d}",
                    'month_name': datetime(year, month, 1).strftime('%b %Y'),
                    'categories': category_data
                })
            
            # Total by category (all time)
            cursor.execute('''
                SELECT 
                    b.category,
                    SUM(COALESCE(p.amount_paid, 0)) as total_paid,
                    COUNT(*) as total_payments,
                    AVG(COALESCE(p.amount_paid, 0)) as avg_payment
                FROM bill_payments p
                JOIN recurring_bills b ON p.bill_id = b.id
                WHERE p.status = 'paid'
                GROUP BY b.category
            ''')
            
            category_totals = {}
            for row in cursor.fetchall():
                category_totals[row['category']] = {
                    'total_paid': row['total_paid'] or 0,
                    'total_payments': row['total_payments'] or 0,
                    'avg_payment': row['avg_payment'] or 0
                }
            
            # Payment stats
            cursor.execute('''
                SELECT 
                    COUNT(*) as total_records,
                    SUM(CASE WHEN status = 'paid' THEN 1 ELSE 0 END) as paid_count,
                    SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending_count,
                    SUM(CASE WHEN status = 'overdue' THEN 1 ELSE 0 END) as overdue_count,
                    SUM(COALESCE(amount_paid, 0)) as total_paid,
                    SUM(CASE WHEN status != 'paid' THEN COALESCE(amount_due, 0) ELSE 0 END) as total_pending
                FROM bill_payments
            ''')
            
            stats_row = cursor.fetchone()
            payment_stats = {
                'total_records': stats_row['total_records'] or 0,
                'paid_count': stats_row['paid_count'] or 0,
                'pending_count': stats_row['pending_count'] or 0,
                'overdue_count': stats_row['overdue_count'] or 0,
                'total_paid': stats_row['total_paid'] or 0,
                'total_pending': stats_row['total_pending'] or 0
            }
            
            # Monthly totals
            monthly_totals = []
            for i in range(months - 1, -1, -1):
                month = today.month - i
                year = today.year
                while month <= 0:
                    month += 12
                    year -= 1
                
                start_date = f"{year}-{month:02d}-01"
                _, last_day = monthrange(year, month)
                end_date = f"{year}-{month:02d}-{last_day}"
                
                cursor.execute('''
                    SELECT 
                        SUM(COALESCE(amount_paid, 0)) as total_paid,
                        COUNT(CASE WHEN status = 'paid' THEN 1 END) as paid_count
                    FROM bill_payments
                    WHERE due_date >= ? AND due_date <= ? AND status = 'paid'
                ''', (start_date, end_date))
                
                row = cursor.fetchone()
                monthly_totals.append({
                    'month': f"{year}-{month:02d}",
                    'month_name': datetime(year, month, 1).strftime('%b %Y'),
                    'total_paid': row['total_paid'] or 0,
                    'paid_count': row['paid_count'] or 0
                })
            
            return {
                'monthly_by_category': monthly_by_category,
                'category_totals': category_totals,
                'payment_stats': payment_stats,
                'monthly_totals': monthly_totals
            }
    
    def get_bill_payment_history(self, bill_id: int, limit: int = 24) -> List[Dict]:
        """Get detailed payment history for a specific bill."""
        self._init_bills_tables()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT p.*, b.name as bill_name, b.category
                FROM bill_payments p
                JOIN recurring_bills b ON p.bill_id = b.id
                WHERE p.bill_id = ?
                ORDER BY p.due_date DESC
                LIMIT ?
            ''', (bill_id, limit))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_all_payment_history(self, months: int = 6) -> List[Dict]:
        """Get all payment history for the last N months."""
        self._init_bills_tables()
        from datetime import datetime, timedelta
        
        start_date = (datetime.now() - timedelta(days=months * 30)).date().isoformat()
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT p.*, b.name as bill_name, b.category, b.provider
                FROM bill_payments p
                JOIN recurring_bills b ON p.bill_id = b.id
                WHERE p.due_date >= ?
                ORDER BY p.due_date DESC, p.created_at DESC
            ''', (start_date,))
            return [dict(row) for row in cursor.fetchall()]
