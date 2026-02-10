#!/usr/bin/env python3
"""Daily momentum scanner cron job.
Run at 6:00 PM IST (Mon-Fri) after market close via systemd timer.

On GCP VM: systemd timer runs at 12:30 UTC (6:00 PM IST)
"""
import sys
from datetime import datetime, date
from pathlib import Path

# Setup paths
script_dir = Path(__file__).parent.parent
sys.path.insert(0, str(script_dir))

from server.momentum_db import MomentumDatabase
from server.momentum_scanner import MomentumScanner

# NSE holidays for 2026 (source: NSE website)
NSE_HOLIDAYS_2026 = {
    date(2026, 1, 26),   # Republic Day
    date(2026, 2, 17),   # Mahashivratri (tentative)
    date(2026, 3, 10),   # Holi
    date(2026, 3, 30),   # Id-Ul-Fitr (tentative)
    date(2026, 4, 2),    # Ram Navami
    date(2026, 4, 3),    # Good Friday
    date(2026, 4, 14),   # Dr Ambedkar Jayanti
    date(2026, 5, 1),    # Maharashtra Day
    date(2026, 5, 25),   # Buddha Purnima (tentative)
    date(2026, 6, 5),    # Eid-Ul-Adha (tentative)
    date(2026, 7, 6),    # Muharram (tentative)
    date(2026, 8, 15),   # Independence Day
    date(2026, 8, 19),   # Janmashtami (tentative)
    date(2026, 9, 4),    # Milad-Un-Nabi (tentative)
    date(2026, 10, 2),   # Mahatma Gandhi Jayanti
    date(2026, 10, 20),  # Dussehra
    date(2026, 11, 9),   # Diwali (Laxmi Puja)
    date(2026, 11, 10),  # Diwali (Balipratipada)
    date(2026, 11, 27),  # Guru Nanak Jayanti
    date(2026, 12, 25),  # Christmas
}


def is_market_holiday(d=None):
    """Check if given date is an NSE holiday."""
    if d is None:
        d = date.today()
    # Weekend check
    if d.weekday() >= 5:
        return True, "Weekend"
    # Holiday check
    if d in NSE_HOLIDAYS_2026:
        return True, "NSE holiday"
    return False, ""


def main():
    today = date.today()
    is_holiday, reason = is_market_holiday(today)

    if is_holiday:
        print(f'[{datetime.now()}] Skipping scan: {reason} ({today})')
        return

    # Determine DB path: use home dir (works on both local and GCP)
    db_path = str(Path.home() / 'clat_preparation' / 'momentum_tracker.db')
    if not Path(db_path).parent.exists():
        # Fallback for GCP where home might differ
        db_path = '/opt/speedmathsgames/momentum_tracker.db'

    start = datetime.now()
    print(f'\n[{start}] Starting daily momentum scan...')
    print(f'  DB path: {db_path}')

    db = MomentumDatabase(db_path)
    scanner = MomentumScanner(db)

    def log_progress(update):
        print(f"  [{update.get('percent', 0)}%] {update['message']}")

    results = scanner.run_full_scan(progress_callback=log_progress)

    end = datetime.now()
    duration = (end - start).total_seconds()

    print(f'\n[{end}] Scan complete:')
    print(f'  Stocks scanned: {results["total_scanned"]}')
    print(f'  Qualifying (Trend Template): {results["qualifying_count"]}')
    print(f'  VCP candidates: {len(results["vcp_candidates"])}')
    print(f'  Breakouts: {len(results["breakouts"])}')
    print(f'  Errors: {results["errors"]}')
    print(f'  Duration: {duration:.1f}s')

    # Print top 10 qualifying stocks
    if results['qualifying_stocks']:
        print(f'\nTop qualifying stocks (by RS rating):')
        for s in results['qualifying_stocks'][:10]:
            print(f'  {s["symbol"]}: RS={s["rs_rating"]} Close={s["close"]} {s["tradingview_link"]}')

    if results['vcp_candidates']:
        print(f'\nVCP candidates:')
        for v in results['vcp_candidates']:
            print(f'  {v["symbol"]}: {v["notation"]} Pivot={v["pivot_price"]} ({v["pct_from_pivot"]}% away)')

    if results['breakouts']:
        print(f'\nBreakouts today:')
        for b in results['breakouts']:
            print(f'  {b["symbol"]}: Price={b["breakout_price"]} Vol={b["volume_ratio"]}x Stop={b["suggested_stop"]}')


if __name__ == '__main__':
    main()
