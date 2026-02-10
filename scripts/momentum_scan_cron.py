#!/usr/bin/env python3
"""Daily momentum scanner cron job.
Run at 6:30 PM IST (Mon-Fri) after market close.

Crontab entry (www-data):
  0 13 * * 1-5 cd /opt/speedmathsgames && python3 scripts/momentum_scan_cron.py >> /opt/speedmathsgames/logs/momentum_scan.log 2>&1

Note: 13:00 UTC = 6:30 PM IST (UTC+5:30)
"""
import sys
import os
from datetime import datetime
from pathlib import Path

# Setup paths
script_dir = Path(__file__).parent.parent
sys.path.insert(0, str(script_dir))

from server.momentum_db import MomentumDatabase
from server.momentum_scanner import MomentumScanner


def main():
    start = datetime.now()
    print(f'\n[{start}] Starting daily momentum scan...')

    db = MomentumDatabase()
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
