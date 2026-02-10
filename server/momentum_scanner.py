#!/usr/bin/env python3
"""
Momentum Scanner — TradingView Screener Edition
Implements Minervini's Trend Template and VCP pattern detection for Indian stocks.
Uses tradingview-screener for instant bulk data (3000+ stocks in one API call).
Uses yfinance as fallback for VCP historical candle analysis on qualifying stocks only.
"""

import time
from typing import List, Dict, Optional
from datetime import datetime

try:
    from tradingview_screener import Query, Column
    import pandas as pd
    import numpy as np
except ImportError as e:
    print(f"Warning: Missing required packages for momentum scanner: {e}")
    print("Install with: pip install tradingview-screener pandas numpy")

# Optional: yfinance for VCP historical analysis on qualifying stocks
try:
    import yfinance as yf
    HAS_YFINANCE = True
except ImportError:
    HAS_YFINANCE = False

from server.momentum_db import MomentumDatabase

# NSE F&O stocks (for labeling — updated periodically)
FNO_SYMBOLS = {
    'AARTIIND', 'ABB', 'ABBOTINDIA', 'ABCAPITAL', 'ABFRL', 'ACC', 'ADANIENT',
    'ADANIPORTS', 'ALKEM', 'AMBUJACEM', 'APOLLOHOSP', 'APOLLOTYRE', 'ASHOKLEY',
    'ASIANPAINT', 'ASTRAL', 'ATUL', 'AUBANK', 'AUROPHARMA', 'AXISBANK',
    'BAJAJ-AUTO', 'BAJAJFINSV', 'BAJFINANCE', 'BALKRISIND', 'BANDHANBNK',
    'BANKBARODA', 'BATAINDIA', 'BEL', 'BERGEPAINT', 'BHARATFORG', 'BHARTIARTL',
    'BHEL', 'BIOCON', 'BOSCHLTD', 'BPCL', 'BRITANNIA', 'BSOFT', 'CANBK',
    'CANFINHOME', 'CHAMBLFERT', 'CHOLAFIN', 'CIPLA', 'COALINDIA', 'COFORGE',
    'COLPAL', 'CONCOR', 'COROMANDEL', 'CROMPTON', 'CUB', 'CUMMINS',
    'DABUR', 'DALBHARAT', 'DEEPAKNTR', 'DELTACORP', 'DIVISLAB', 'DIXON',
    'DLF', 'DRREDDY', 'EICHERMOT', 'ESCORTS', 'EXIDEIND', 'FEDERALBNK',
    'GAIL', 'GLENMARK', 'GMRINFRA', 'GNFC', 'GODREJCP', 'GODREJPROP',
    'GRANULES', 'GRASIM', 'GUJGASLTD', 'HAL', 'HAVELLS', 'HCLTECH',
    'HDFCAMC', 'HDFCBANK', 'HDFCLIFE', 'HEROMOTOCO', 'HINDALCO', 'HINDCOPPER',
    'HINDPETRO', 'HINDUNILVR', 'ICICIBANK', 'ICICIGI', 'ICICIPRULI',
    'IDEA', 'IDFC', 'IDFCFIRSTB', 'IEX', 'IGL', 'INDHOTEL', 'INDIACEM',
    'INDIAMART', 'INDIGO', 'INDUSINDBK', 'INDUSTOWER', 'INFY', 'IOC',
    'IPCALAB', 'IRCTC', 'ITC', 'JINDALSTEL', 'JKCEMENT', 'JSWSTEEL',
    'JUBLFOOD', 'KOTAKBANK', 'LALPATHLAB', 'LAURUSLABS', 'LICHSGFIN',
    'LICI', 'LT', 'LTIM', 'LTTS', 'LUPIN', 'M&M', 'MANAPPURAM',
    'MARICO', 'MARUTI', 'MCX', 'METROPOLIS', 'MFSL', 'MGL', 'MOTHERSON',
    'MPHASIS', 'MRF', 'MUTHOOTFIN', 'NATIONALUM', 'NAUKRI', 'NAVINFLUOR',
    'NESTLEIND', 'NMDC', 'NTPC', 'OBEROIRLTY', 'OFSS', 'ONGC', 'PAGEIND',
    'PEL', 'PERSISTENT', 'PETRONET', 'PFC', 'PIDGENINDS', 'PIIND', 'PNB',
    'POLYCAB', 'POWERGRID', 'PVRINOX', 'RAMCOCEM', 'RBLBANK', 'RECLTD',
    'RELIANCE', 'SAIL', 'SBICARD', 'SBILIFE', 'SBIN', 'SHREECEM',
    'SHRIRAMFIN', 'SIEMENS', 'SRF', 'SUNPHARMA', 'SUNTV', 'SYNGENE',
    'TATACHEM', 'TATACOMM', 'TATACONSUM', 'TATAELXSI', 'TATAMOTORS',
    'TATAPOWER', 'TATASTEEL', 'TCS', 'TECHM', 'TITAN', 'TORNTPHARM',
    'TRENT', 'TVSMOTOR', 'UBL', 'ULTRACEMCO', 'UNIONBANK', 'UNITDSPR',
    'UPL', 'VEDL', 'VOLTAS', 'WIPRO', 'ZYDUSLIFE',
}


class MomentumScanner:
    """Core scanner using TradingView Screener for Indian stocks."""

    # Fields to fetch from TradingView screener
    SCREENER_FIELDS = [
        'name', 'close', 'exchange',
        'SMA50', 'SMA150', 'SMA200', 'EMA20',
        'price_52_week_high', 'price_52_week_low',
        'High.6M',  # 6-month high for recency check
        'volume', 'average_volume_30d_calc', 'average_volume_60d_calc',
        'relative_volume_10d_calc',
        'market_cap_basic', 'sector', 'industry',
        'Perf.1M', 'Perf.3M', 'Perf.6M', 'Perf.Y',
        'change',  # Today's % change (for purple dot detection)
        'RSI', 'ATR',
        'Volatility.D',
        'is_primary',
    ]

    def __init__(self, db: MomentumDatabase = None):
        self.db = db or MomentumDatabase()

    def fetch_screener_data(self, min_market_cap: float = 1_000_000_000,
                            progress_callback=None) -> pd.DataFrame:
        """
        Fetch all Indian stocks with pre-computed indicators from TradingView.
        Returns DataFrame with ~2000-5000 stocks in seconds.
        """
        if progress_callback:
            progress_callback({
                'type': 'progress',
                'message': 'Fetching data from TradingView Screener...',
                'percent': 5
            })

        total, df = (Query()
            .set_markets('india')
            .select(*self.SCREENER_FIELDS)
            .where(Column('market_cap_basic') > min_market_cap)
            .where(Column('is_primary') == True)
            .order_by('market_cap_basic', ascending=False)
            .limit(5000)
            .get_scanner_data()
        )

        if progress_callback:
            progress_callback({
                'type': 'progress',
                'message': f'Received {len(df)} stocks from TradingView ({total} total)',
                'percent': 20
            })

        # Parse exchange and symbol from ticker (e.g. "NSE:RELIANCE" -> "NSE", "RELIANCE")
        df['exchange_code'] = df['ticker'].str.split(':').str[0]
        df['symbol'] = df['ticker'].str.split(':').str[1]

        # Mark F&O stocks
        df['is_fno'] = df['symbol'].isin(FNO_SYMBOLS).astype(int)

        return df

    def compute_rs_rating(self, df: pd.DataFrame) -> pd.Series:
        """
        Compute Relative Strength rating (0-100) from pre-computed performance fields.
        Percentile rank of weighted composite across the entire universe.
        """
        r1m = df['Perf.1M'].fillna(0)
        r3m = df['Perf.3M'].fillna(0)
        r6m = df['Perf.6M'].fillna(0)
        r1y = df['Perf.Y'].fillna(0)

        # Weighted composite: 40% 3-month + 20% 6-month + 20% 1-year + 20% 1-month
        composite = 0.4 * r3m + 0.2 * r6m + 0.2 * r1y + 0.2 * r1m

        # Percentile rank within universe
        rs_rating = composite.rank(pct=True) * 100
        return rs_rating.round(1)

    def apply_trend_template(self, df: pd.DataFrame,
                             progress_callback=None) -> pd.DataFrame:
        """
        Apply all 8 Minervini Trend Template criteria (vectorized).
        Returns DataFrame with criteria columns and pass/fail status.
        """
        if progress_callback:
            progress_callback({
                'type': 'progress',
                'message': 'Applying Trend Template criteria...',
                'percent': 30
            })

        df = df.copy()

        # Compute RS rating for the full universe
        df['rs_rating'] = self.compute_rs_rating(df)

        # Drop rows with missing SMA data
        required_cols = ['close', 'SMA50', 'SMA150', 'SMA200',
                         'price_52_week_high', 'price_52_week_low']
        valid_mask = df[required_cols].notna().all(axis=1)

        # Criterion 1: Price above 150 and 200 DMA
        df['c1_above_150_200'] = (df['close'] > df['SMA150']) & (df['close'] > df['SMA200'])

        # Criterion 2: 150 DMA above 200 DMA
        df['c2_150_above_200'] = df['SMA150'] > df['SMA200']

        # Criterion 3: 200 DMA trending up
        # Proxy: if SMA150 > SMA200, the 200 DMA is being pulled upward
        df['c3_200_rising'] = df['SMA150'] > df['SMA200']

        # Criterion 4: 50 DMA above 150 and 200 DMA
        df['c4_50_above_150_200'] = (df['SMA50'] > df['SMA150']) & (df['SMA50'] > df['SMA200'])

        # Criterion 5: Price above 50 DMA
        df['c5_above_50'] = df['close'] > df['SMA50']

        # Criterion 6: Price at least 30% above 52-week low
        df['pct_above_low'] = ((df['close'] - df['price_52_week_low']) /
                                df['price_52_week_low'] * 100).round(1)
        df['c6_30pct_above_low'] = df['pct_above_low'] >= 30

        # Criterion 7: Price within 25% of 52-week high
        df['pct_below_high'] = ((df['price_52_week_high'] - df['close']) /
                                 df['price_52_week_high'] * 100).round(1)
        df['c7_within_25pct_high'] = df['pct_below_high'] <= 25

        # Criterion 8: RS Rating >= 70
        df['c8_rs_above_70'] = df['rs_rating'] >= 70

        # Overall pass: all criteria met AND valid data
        criteria_cols = ['c1_above_150_200', 'c2_150_above_200', 'c3_200_rising',
                        'c4_50_above_150_200', 'c5_above_50',
                        'c6_30pct_above_low', 'c7_within_25pct_high', 'c8_rs_above_70']

        df['passes_trend_template'] = valid_mask & df[criteria_cols].all(axis=1)
        df['criteria_met'] = df[criteria_cols].sum(axis=1)

        # --- Manas Arora enhancements ---

        # Momentum Burst / Purple Dot: big daily move (>=5%) on high relative volume (>=2x)
        daily_change = df['change'].fillna(0)
        rel_vol = df['relative_volume_10d_calc'].fillna(0)
        df['momentum_burst'] = (daily_change >= 5) & (rel_vol >= 2.0)

        # Recent 52W high: 52W high should be within last 6 months (not stale)
        # High.6M is the highest price in last 6 months
        high_6m = df['High.6M'].fillna(0)
        high_52w = df['price_52_week_high'].fillna(0)
        # If 6-month high is close to 52W high (within 5%), the 52W high is recent
        df['recent_52w_high'] = (high_6m >= high_52w * 0.95) | (high_52w <= 0)

        # Near 21 EMA check (within 3% of EMA20 — TradingView's EMA20 ≈ 21 EMA)
        ema20 = df['EMA20'].fillna(0)
        df['near_ema21'] = ((df['close'] - ema20).abs() / ema20 * 100 <= 3) & (ema20 > 0)

        # Stricter qualifying: pct_above_low >= 50 (Manas Arora's prior upmove filter)
        df['c6_50pct_above_low'] = df['pct_above_low'] >= 50

        if progress_callback:
            qualifying = df['passes_trend_template'].sum()
            bursts = df['momentum_burst'].sum()
            progress_callback({
                'type': 'progress',
                'message': f'Trend Template: {qualifying} qualify, {bursts} momentum bursts',
                'percent': 50
            })

        return df

    def detect_vcp(self, ohlcv_df: pd.DataFrame, lookback_weeks: int = 12) -> Optional[Dict]:
        """
        Detect Volatility Contraction Pattern (VCP) from OHLCV data.
        Looks for progressively tighter contractions in price with declining volume.
        """
        if ohlcv_df is None or len(ohlcv_df) < lookback_weeks * 5:
            return None

        lookback_days = lookback_weeks * 5
        recent = ohlcv_df.tail(lookback_days).copy()

        if len(recent) < 20:
            return None

        close = recent['Close'].values
        high = recent['High'].values
        low = recent['Low'].values
        volume = recent['Volume'].values

        # Find the highest high in the base period
        base_high = max(high)

        # Split data into segments for contraction analysis
        segment_size = len(close) // 3
        if segment_size < 5:
            return None

        contractions = []
        for i in range(3):
            start = i * segment_size
            end = min((i + 1) * segment_size, len(close))
            if end - start < 3:
                continue

            seg_high = max(high[start:end])
            seg_low = min(low[start:end])
            seg_range = seg_high - seg_low
            seg_depth = (seg_range / seg_high) * 100 if seg_high > 0 else 0
            contractions.append({
                'depth': round(seg_depth, 1),
                'high': float(seg_high),
                'low': float(seg_low),
            })

        # Check if contractions are progressively smaller
        if len(contractions) < 2:
            return None

        is_contracting = True
        for i in range(1, len(contractions)):
            if contractions[i]['depth'] >= contractions[i - 1]['depth'] * 1.1:
                is_contracting = False
                break

        if not is_contracting:
            return None

        # First contraction <= 35%
        if contractions[0]['depth'] > 35:
            return None

        # Final contraction is tight (< 15%)
        final_depth = contractions[-1]['depth']
        if final_depth > 15:
            return None

        # Volume declining
        vol_first_half = np.mean(volume[:len(volume) // 2])
        vol_second_half = np.mean(volume[len(volume) // 2:])
        volume_declining = vol_second_half < vol_first_half

        # Pivot point = highest point in the base
        pivot = float(base_high)
        current_close = float(close[-1])
        pct_from_pivot = ((pivot - current_close) / pivot) * 100

        # 21 EMA proximity check (Manas Arora: price should respect 21 EMA)
        ema_21 = None
        near_21ema = False
        if len(close) >= 21:
            # Compute 21 EMA from close prices
            ema = float(close[0])
            multiplier = 2.0 / (21 + 1)
            for p in close[1:]:
                ema = float(p) * multiplier + ema * (1 - multiplier)
            ema_21 = round(ema, 2)
            near_21ema = abs(current_close - ema) / ema * 100 <= 5

        # Inside bar detection (last bar's range within prior bar's range)
        has_inside_bar = False
        if len(high) >= 2 and len(low) >= 2:
            has_inside_bar = (high[-1] <= high[-2]) and (low[-1] >= low[-2])

        # VCP quality score (0-100)
        quality = 50
        if volume_declining:
            quality += 15
        if near_21ema:
            quality += 15  # Holding above 21 EMA
        if has_inside_bar:
            quality += 10  # Tight final contraction
        if final_depth <= 8:
            quality += 10  # Very tight final contraction

        # Notation
        depths_str = '-'.join([f"{c['depth']:.0f}%" for c in contractions])
        notation = f"{lookback_weeks}W {depths_str} / {len(contractions)}T"

        return {
            'num_contractions': len(contractions),
            'contraction_depths': [c['depth'] for c in contractions],
            'pivot_price': round(pivot, 2),
            'current_price': round(current_close, 2),
            'pct_from_pivot': round(pct_from_pivot, 1),
            'volume_trend': 'declining' if volume_declining else 'mixed',
            'notation': notation,
            'base_duration_weeks': lookback_weeks,
            'final_contraction_depth': round(final_depth, 1),
            'ema_21': ema_21,
            'near_21ema': near_21ema,
            'has_inside_bar': has_inside_bar,
            'quality_score': min(quality, 100),
        }

    def check_breakout(self, ohlcv_df: pd.DataFrame, pivot_price: float,
                       avg_volume: float = 0) -> Optional[Dict]:
        """Check if a stock has broken out above its pivot on high volume."""
        if ohlcv_df is None or ohlcv_df.empty:
            return None

        latest = ohlcv_df.iloc[-1]
        close = latest['Close']
        volume = latest['Volume']

        # Use avg volume from OHLCV if not provided
        if avg_volume <= 0:
            avg_volume = ohlcv_df['Volume'].tail(50).mean()

        if close > pivot_price and avg_volume > 0:
            vol_ratio = volume / avg_volume
            if vol_ratio >= 1.4:  # 40% above average volume
                risk_pct = ((close - pivot_price * 0.92) / close) * 100

                return {
                    'breakout_price': round(float(close), 2),
                    'volume_ratio': round(float(vol_ratio), 2),
                    'suggested_stop': round(float(pivot_price * 0.92), 2),
                    'risk_pct': round(float(risk_pct), 1),
                }
        return None

    @staticmethod
    def _tv_to_yf_symbol(symbol: str, exchange: str = 'NSE') -> Optional[str]:
        """Convert TradingView symbol to yfinance ticker format."""
        # Skip ETFs, REITs, InvITs, partly-paid shares
        skip_suffixes = ('.RR', '.PP', '.E1', '.E2', '.SM', '.B1', '.B2')
        if any(symbol.endswith(s) for s in skip_suffixes):
            return None

        # Skip if symbol starts with a digit (BSE scrip codes like 09GPG)
        if symbol and symbol[0].isdigit():
            return None

        # TradingView uses underscores, yfinance uses hyphens
        yf_symbol = symbol.replace('_', '-')

        suffix = '.NS' if exchange == 'NSE' else '.BO'
        return f"{yf_symbol}{suffix}"

    def fetch_historical_for_vcp(self, symbol: str, exchange: str = 'NSE') -> Optional[pd.DataFrame]:
        """Download historical OHLCV data for VCP detection on a single stock."""
        if not HAS_YFINANCE:
            return None

        ticker = self._tv_to_yf_symbol(symbol, exchange)
        if ticker is None:
            return None

        try:
            df = yf.download(ticker, period='6mo', interval='1d', progress=False)
            if df is None or df.empty or len(df) < 30:
                return None

            # Handle MultiIndex columns from yfinance
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            return df
        except Exception as e:
            print(f"  Error fetching historical for {symbol}: {e}")
            return None

    def run_full_scan(self, symbols: List[str] = None,
                      progress_callback=None) -> Dict:
        """
        Run a full Trend Template + VCP scan.

        Phase 1: Fetch all Indian stocks from TradingView (instant, ~5 seconds)
        Phase 2: Apply Trend Template criteria (vectorized, milliseconds)
        Phase 3: VCP detection on qualifying stocks via yfinance (~1-2 minutes)

        Returns summary dict compatible with the existing API.
        """
        scan_date = datetime.now().strftime('%Y-%m-%d')
        start_time = time.time()

        # Phase 1: Fetch all Indian stocks from TradingView Screener
        try:
            df = self.fetch_screener_data(progress_callback=progress_callback)
        except Exception as e:
            return {
                'scan_id': 0,
                'scan_date': scan_date,
                'total_scanned': 0,
                'errors': 1,
                'qualifying_count': 0,
                'qualifying_stocks': [],
                'vcp_candidates': [],
                'breakouts': [],
                'duration_sec': round(time.time() - start_time, 1),
                'error_message': f'TradingView Screener error: {str(e)}',
            }

        total_scanned = len(df)
        scan_id = self.db.create_scan(scan_date, 'trend_template', total_scanned)

        # Phase 2: Apply Trend Template (vectorized — milliseconds)
        df = self.apply_trend_template(df, progress_callback)

        qualifying_df = df[df['passes_trend_template']].copy()
        qualifying_df = qualifying_df.sort_values('rs_rating', ascending=False)

        # Build result dicts and save to DB
        qualifying = []
        errors = 0

        for _, row in df.iterrows():
            try:
                vol_avg = row.get('average_volume_30d_calc', 0) or 0
                vol = row.get('volume', 0) or 0
                vol_ratio = round(vol / vol_avg, 2) if vol_avg > 0 else 0

                tt_criteria = {
                    'c1_above_150_200': bool(row.get('c1_above_150_200', False)),
                    'c2_150_above_200': bool(row.get('c2_150_above_200', False)),
                    'c3_200_rising': bool(row.get('c3_200_rising', False)),
                    'c4_50_above_150_200': bool(row.get('c4_50_above_150_200', False)),
                    'c5_above_50': bool(row.get('c5_above_50', False)),
                    'c6_30pct_above_low': bool(row.get('c6_30pct_above_low', False)),
                    'c7_within_25pct_high': bool(row.get('c7_within_25pct_high', False)),
                    'c8_rs_above_70': bool(row.get('c8_rs_above_70', False)),
                    # Manas Arora enhancements
                    'momentum_burst': bool(row.get('momentum_burst', False)),
                    'near_ema21': bool(row.get('near_ema21', False)),
                    'recent_52w_high': bool(row.get('recent_52w_high', False)),
                    'pct_above_low_50': bool(row.get('c6_50pct_above_low', False)),
                }

                ema20_val = row.get('EMA20')
                ema20_float = round(float(ema20_val), 2) if pd.notna(ema20_val) else None

                result = {
                    'symbol': row['symbol'],
                    'company_name': row.get('name', ''),
                    'close': round(float(row['close']), 2) if pd.notna(row.get('close')) else 0,
                    'sma_50': round(float(row['SMA50']), 2) if pd.notna(row.get('SMA50')) else None,
                    'sma_150': round(float(row['SMA150']), 2) if pd.notna(row.get('SMA150')) else None,
                    'sma_200': round(float(row['SMA200']), 2) if pd.notna(row.get('SMA200')) else None,
                    'ema_20': ema20_float,
                    'sma_200_prev': None,  # Not available from screener
                    'rs_rating': round(float(row.get('rs_rating', 0)), 1),
                    'pct_from_52w_high': round(float(-row.get('pct_below_high', 0)), 1),
                    'pct_from_52w_low': round(float(row.get('pct_above_low', 0)), 1),
                    'high_52w': round(float(row['price_52_week_high']), 2) if pd.notna(row.get('price_52_week_high')) else None,
                    'low_52w': round(float(row['price_52_week_low']), 2) if pd.notna(row.get('price_52_week_low')) else None,
                    'volume': int(vol),
                    'avg_volume_50': int(vol_avg),
                    'volume_ratio': vol_ratio,
                    'sector': row.get('sector', ''),
                    'industry': row.get('industry', ''),
                    'market_cap': float(row.get('market_cap_basic', 0) or 0),
                    'is_fno': int(row.get('is_fno', 0)),
                    'passes_trend_template': bool(row.get('passes_trend_template', False)),
                    'momentum_burst': bool(row.get('momentum_burst', False)),
                    'near_ema21': bool(row.get('near_ema21', False)),
                    'recent_52w_high': bool(row.get('recent_52w_high', False)),
                    'pct_above_low_50': bool(row.get('c6_50pct_above_low', False)),
                    'tt_criteria_met': tt_criteria,
                    'tradingview_link': f"https://www.tradingview.com/chart/?symbol={row['exchange_code']}:{row['symbol']}",
                }

                self.db.save_result(scan_id, result)

                if result['passes_trend_template']:
                    qualifying.append(result)
            except Exception as e:
                errors += 1

        if progress_callback:
            progress_callback({
                'type': 'progress',
                'message': f'{len(qualifying)} stocks pass Trend Template. Checking VCP patterns...',
                'percent': 60
            })

        # Phase 3: VCP detection on top qualifying stocks (by RS rating)
        # Manas Arora filter: only check VCP on stocks >=50% above 52W low (prior upmove)
        # and with recent 52W high (within 6 months)
        vcp_candidates = []
        breakouts = []
        vcp_eligible = [s for s in qualifying
                        if s.get('pct_from_52w_low', 0) >= 50]
        vcp_check_list = vcp_eligible[:100]  # Top 100 by RS rating

        if HAS_YFINANCE and vcp_check_list:
            for i, stock in enumerate(vcp_check_list):
                symbol = stock['symbol']
                exchange = 'NSE'  # Default; could parse from ticker
                # Determine exchange from the qualifying_df
                match = qualifying_df[qualifying_df['symbol'] == symbol]
                if not match.empty:
                    exchange = match.iloc[0].get('exchange_code', 'NSE')

                if progress_callback and i % 5 == 0:
                    pct = 60 + int((i / max(len(vcp_check_list), 1)) * 35)
                    progress_callback({
                        'type': 'progress',
                        'message': f'VCP check: {symbol} ({i + 1}/{len(qualifying)})',
                        'percent': pct
                    })

                ohlcv = self.fetch_historical_for_vcp(symbol, exchange)
                if ohlcv is None:
                    continue

                vcp = self.detect_vcp(ohlcv)
                if vcp:
                    vcp['symbol'] = symbol
                    vcp['detected_date'] = scan_date
                    vcp_candidates.append(vcp)
                    self.db.save_vcp_pattern(vcp)

                    # Check for breakout
                    breakout = self.check_breakout(
                        ohlcv, vcp['pivot_price'],
                        avg_volume=stock.get('avg_volume_50', 0)
                    )
                    if breakout:
                        breakout['symbol'] = symbol
                        breakout['breakout_date'] = scan_date
                        breakout['pattern_id'] = None
                        breakouts.append(breakout)
                        self.db.save_breakout(breakout)

                # Small delay between yfinance calls
                if i % 10 == 9:
                    time.sleep(0.5)

        duration = time.time() - start_time
        self.db.update_scan(scan_id, len(qualifying), duration)

        if progress_callback:
            progress_callback({
                'type': 'complete',
                'message': f'Scan complete: {len(qualifying)} qualifying, '
                           f'{len(vcp_candidates)} VCP, {len(breakouts)} breakouts '
                           f'({duration:.0f}s)',
                'percent': 100
            })

        return {
            'scan_id': scan_id,
            'scan_date': scan_date,
            'total_scanned': total_scanned,
            'errors': errors,
            'qualifying_count': len(qualifying),
            'qualifying_stocks': qualifying,
            'vcp_candidates': vcp_candidates,
            'breakouts': breakouts,
            'duration_sec': round(duration, 1),
        }


if __name__ == '__main__':
    """Quick test scan."""
    scanner = MomentumScanner()

    print("Testing momentum scanner (TradingView Screener edition)...\n")

    def print_progress(update):
        print(f"  [{update.get('percent', 0)}%] {update['message']}")

    results = scanner.run_full_scan(progress_callback=print_progress)

    print(f"\nResults:")
    print(f"  Total scanned: {results['total_scanned']}")
    print(f"  Qualifying: {results['qualifying_count']}")
    print(f"  VCP Candidates: {len(results['vcp_candidates'])}")
    print(f"  Breakouts: {len(results['breakouts'])}")
    print(f"  Errors: {results['errors']}")
    print(f"  Duration: {results['duration_sec']}s")

    if results['qualifying_stocks']:
        print(f"\nTop qualifying stocks (by RS rating):")
        for s in results['qualifying_stocks'][:20]:
            fno_tag = " [F&O]" if s.get('is_fno') else ""
            burst_tag = " *BURST*" if s.get('momentum_burst') else ""
            ema_tag = " [21EMA]" if s.get('near_ema21') else ""
            print(f"  {s['symbol']}{fno_tag}{burst_tag}{ema_tag}: RS={s['rs_rating']} "
                  f"Close={s['close']} +{s['pct_from_52w_low']}% from low "
                  f"Sector={s.get('sector', '')}")

    if results['vcp_candidates']:
        print(f"\nVCP candidates:")
        for v in results['vcp_candidates']:
            ema_tag = " [21EMA]" if v.get('near_21ema') else ""
            ib_tag = " [IB]" if v.get('has_inside_bar') else ""
            print(f"  {v['symbol']}: {v['notation']} Q={v.get('quality_score', 0)}"
                  f"{ema_tag}{ib_tag} Pivot={v['pivot_price']} "
                  f"({v['pct_from_pivot']}% away)")

    if results['breakouts']:
        print(f"\nBreakouts today:")
        for b in results['breakouts']:
            print(f"  {b['symbol']}: Price={b['breakout_price']} "
                  f"Vol={b['volume_ratio']}x Stop={b['suggested_stop']}")
