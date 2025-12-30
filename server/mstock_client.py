#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
mstock_client.py

m.Stock Trading API Client for Personal Finance Module.
Handles authentication, portfolio sync, and real-time market data.

API Documentation: https://tradingapi.mstock.com/docs/v1/Introduction/

Access restricted to: Arvind & Deepa only
"""

import requests
import pyotp
import json
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any


class MStockClient:
    """Client for m.Stock Trading API."""
    
    BASE_URL = "https://api.mstock.trade"
    WS_URL = "wss://ws.mstock.trade"
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize m.Stock client with credentials."""
        if config_path is None:
            config_path = Path.home() / '.mstock_config.json'
        
        self.config_path = Path(config_path)
        self.config = self._load_config()
        
        self.api_key = self.config.get('api_key', '')
        self.totp_secret = self.config.get('totp_secret', '')
        self.access_token = None
        self.token_expiry = None
        
    def _load_config(self) -> Dict:
        """Load configuration from file."""
        if self.config_path.exists():
            with open(self.config_path) as f:
                return json.load(f)
        return {}
    
    def _save_config(self):
        """Save configuration to file."""
        with open(self.config_path, 'w') as f:
            json.dump(self.config, f, indent=2)
        os.chmod(self.config_path, 0o600)
    
    def is_configured(self) -> bool:
        """Check if API credentials are configured."""
        return bool(self.api_key and self.totp_secret)
    
    def generate_totp(self) -> str:
        """Generate current TOTP code."""
        if not self.totp_secret:
            raise ValueError("TOTP secret not configured")
        totp = pyotp.TOTP(self.totp_secret)
        return totp.now()
    
    def authenticate(self) -> Dict:
        """Authenticate with m.Stock API and get access token."""
        if not self.is_configured():
            return {'status': 'error', 'message': 'API not configured'}
        
        totp_code = self.generate_totp()
        
        url = f"{self.BASE_URL}/openapi/typea/session/verifytotp"
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Mirae-Version": "1",
            "X-PrivateKey": self.api_key,
        }
        data = f"totp={totp_code}&api_key={self.api_key}"
        
        try:
            response = requests.post(url, data=data, headers=headers, timeout=15)
            result = response.json()
            
            if result.get('status') == 'success':
                self.access_token = result['data']['access_token']
                self.token_expiry = datetime.now() + timedelta(hours=12)
                
                # Update config with user info
                self.config['user_name'] = result['data'].get('user_name')
                self.config['user_id'] = result['data'].get('user_id')
                self.config['last_login'] = datetime.now().isoformat()
                self._save_config()
                
            return result
            
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    def _get_auth_headers(self) -> Dict:
        """Get headers with authentication token."""
        if not self.access_token:
            auth_result = self.authenticate()
            if auth_result.get('status') != 'success':
                raise Exception(f"Authentication failed: {auth_result.get('message')}")
        
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Mirae-Version": "1",
            "X-PrivateKey": self.api_key,
            "Authorization": f"token {self.api_key}:{self.access_token}",
        }
    
    def get_holdings(self) -> Dict:
        """Get portfolio holdings from m.Stock."""
        try:
            headers = self._get_auth_headers()
            url = f"{self.BASE_URL}/openapi/typea/portfolio/holdings"
            
            response = requests.get(url, headers=headers, timeout=15)
            return response.json()
            
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    def get_positions(self) -> Dict:
        """Get current positions from m.Stock."""
        try:
            headers = self._get_auth_headers()
            url = f"{self.BASE_URL}/openapi/typea/portfolio/positions"
            
            response = requests.get(url, headers=headers, timeout=15)
            return response.json()
            
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    def get_funds(self) -> Dict:
        """Get fund summary from m.Stock."""
        try:
            headers = self._get_auth_headers()
            url = f"{self.BASE_URL}/openapi/typea/user/fundsummary"
            
            response = requests.get(url, headers=headers, timeout=15)
            return response.json()
            
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    def get_quote(self, symbol: str, exchange: str = "NSE") -> Dict:
        """Get live quote for a symbol."""
        try:
            headers = self._get_auth_headers()
            url = f"{self.BASE_URL}/openapi/typea/market/quote"
            
            params = {
                "exchange": exchange,
                "tradingsymbol": symbol,
            }
            
            response = requests.get(url, headers=headers, params=params, timeout=15)
            return response.json()
            
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    def sync_portfolio_to_db(self, finance_db) -> Dict:
        """Sync m.Stock portfolio to local database."""
        holdings_result = self.get_holdings()
        
        if holdings_result.get('status') != 'success':
            return holdings_result
        
        holdings = holdings_result.get('data', [])
        synced = 0
        errors = []
        
        for h in holdings:
            try:
                stock_data = {
                    'symbol': h['tradingsymbol'],
                    'exchange': h['exchange'],
                    'quantity': h['quantity'],
                    'avg_buy_price': h['average_price'],
                    'current_price': h['last_price'],
                    'source': 'mstock',
                    'mstock_isin': h.get('isin'),
                    'owner': 'arvind',
                }
                
                # Check if stock exists
                existing = finance_db.get_stock_by_symbol(h['tradingsymbol'], 'arvind')
                
                if existing:
                    finance_db.update_stock_holding(existing['id'], stock_data)
                else:
                    finance_db.add_stock_holding(stock_data)
                
                synced += 1
                
            except Exception as e:
                errors.append(f"{h.get('tradingsymbol', 'unknown')}: {str(e)}")
        
        return {
            'status': 'success',
            'synced': synced,
            'total': len(holdings),
            'errors': errors,
        }


class FreeMarketData:
    """Free market data from Yahoo Finance or NSE."""
    
    @staticmethod
    def get_nse_quote(symbol: str) -> Optional[Dict]:
        """Get quote from NSE (free, no API key needed)."""
        try:
            url = f"https://www.nseindia.com/api/quote-equity?symbol={symbol}"
            headers = {
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json",
            }
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                return {
                    'symbol': symbol,
                    'last_price': data.get('priceInfo', {}).get('lastPrice'),
                    'change': data.get('priceInfo', {}).get('change'),
                    'change_percent': data.get('priceInfo', {}).get('pChange'),
                }
        except:
            pass
        return None


def parse_mstock_csv_export(file_path: str) -> List[Dict]:
    """Parse m.Stock portfolio CSV/Excel export."""
    import pandas as pd
    
    df = pd.read_excel(file_path, header=15)
    df.columns = ['Scrip', 'Qty', 'AvgPrice', 'InvestedValue', 'PrevClose', 
                  'CurrentValue', 'PnL', 'UnsettledQty', 'DPQty', 'MTFQty', 'PledgeQty']
    
    # Skip header row and filter valid data
    df = df.iloc[1:].copy()
    df = df[df['Scrip'].notna() & (df['Scrip'].astype(str) != 'TOTAL')]
    df = df[df['Qty'].notna()]
    
    holdings = []
    for _, row in df.iterrows():
        try:
            holdings.append({
                'symbol': str(row['Scrip']).strip(),
                'quantity': int(float(row['Qty'])),
                'avg_price': float(row['AvgPrice']),
                'invested_value': float(row['InvestedValue']),
                'current_price': float(row['PrevClose']),
                'current_value': float(row['CurrentValue']),
                'pnl': float(row['PnL']),
            })
        except:
            continue
    
    return holdings
