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

