#!/usr/bin/env python3
"""
drishti_daily_cron.py

Daily cron job that pulls the latest Drishti IAS news-analysis page and kicks
off both PDF generation and Claude question-generation.

Behaviour:
  1. Compute today's date (and yesterday's, since Drishti often publishes the
     evening prior).
  2. For each candidate date, hit the local /api/create-pdf-from-url endpoint
     with the YYYY-MM-DD URL.
  3. If the PDF was created (or already existed), trigger /api/create-assessment
     for it. Idempotent — skips dates where questions already exist.
  4. Skips Sundays (Drishti doesn't publish).

This script is meant to run on the GCP VM via systemd (see
scripts/drishti-daily.service / .timer) or a plain cron entry.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import sys
import time
import urllib.request
from urllib.error import HTTPError, URLError


SERVER = 'http://localhost:8765'
LOG_PATH = '/opt/speedmathsgames/logs/drishti_daily.log'

# Indian Standard Time offset (no DST).
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.FileHandler(LOG_PATH),
            logging.StreamHandler(sys.stdout),
        ],
    )


def post_json(path: str, payload: dict, timeout: int = 300) -> dict:
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        f'{SERVER}{path}',
        data=body,
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except HTTPError as e:
        try:
            err = json.loads(e.read().decode())
        except Exception:
            err = {'error': f'HTTP {e.code}'}
        return err
    except URLError as e:
        return {'error': f'URLError: {e}'}


def get_json(path: str, timeout: int = 60) -> dict:
    try:
        with urllib.request.urlopen(f'{SERVER}{path}', timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        return {'error': str(e)}


def candidate_dates() -> list[dt.date]:
    """Yesterday + today (IST). Skip Sundays."""
    today_ist = dt.datetime.now(IST).date()
    candidates = [today_ist - dt.timedelta(days=1), today_ist]
    return [d for d in candidates if d.weekday() != 6]  # 6 = Sunday


def filename_for(date: dt.date) -> str:
    months = ['', 'january', 'february', 'march', 'april', 'may', 'june',
              'july', 'august', 'september', 'october', 'november', 'december']
    return (
        f'drishti_current_affairs_{date.year}_{months[date.month]}_{date.day}.pdf'
    )


def already_has_questions(filename: str) -> bool:
    status = get_json(f'/api/assessment-status/{filename}')
    return bool(status.get('all_complete')) and (status.get('total_cards', 0) > 0)


def fetch_one(date: dt.date) -> bool:
    """Returns True iff the date is fully done (PDF + questions)."""
    url = (
        f'https://www.drishtiias.com/current-affairs-news-analysis-editorials/'
        f'news-analysis/{date.year:04d}-{date.month:02d}-{date.day:02d}'
    )
    filename = filename_for(date)

    # Already complete?
    if already_has_questions(filename):
        logging.info(f'[{date}] questions already exist for {filename} — skipping')
        return True

    # 1. Generate (or reuse) the PDF.
    logging.info(f'[{date}] fetching PDF from {url}')
    pdf_result = post_json('/api/create-pdf-from-url', {'url': url}, timeout=300)
    if not pdf_result.get('success'):
        logging.warning(f'[{date}] PDF generation failed: {pdf_result.get("error")}')
        return False
    logging.info(
        f'[{date}] PDF ok: {pdf_result.get("filename")} '
        f'({pdf_result.get("size_kb",0):.0f} KB, '
        f'existed={pdf_result.get("already_existed")})'
    )

    # 2. Kick off assessment.
    week = f'{date.year}_{date.strftime("%b")}_D{date.day}'
    logging.info(f'[{date}] kicking off assessment for {filename} (week={week})')
    assess = post_json('/api/create-assessment', {
        'pdf_id': filename, 'source': 'drishti', 'week': week,
    }, timeout=30)
    job_id = assess.get('job_id')
    if not job_id:
        logging.warning(f'[{date}] assessment kickoff failed: {assess.get("error")}')
        return False
    logging.info(f'[{date}] assessment started: job_id={job_id[:12]}')

    # 3. Poll. Up to 15 min — enough for image-heavy days on the small VM.
    start = time.monotonic()
    while time.monotonic() - start < 900:
        status = get_json(f'/api/assessment-status/{filename}')
        if status.get('all_complete') and status.get('total_cards', 0) > 0:
            logging.info(
                f'[{date}] ✅ assessment complete: {status["total_cards"]} cards'
            )
            return True
        time.sleep(30)

    logging.warning(f'[{date}] ⏱ assessment timed out after 15 min')
    return False


def main():
    setup_logging()
    logging.info('=== Drishti daily cron starting ===')
    dates = candidate_dates()
    logging.info(f'Candidate dates (IST today + yesterday, excl. Sundays): {dates}')
    ok = 0
    for d in dates:
        if fetch_one(d):
            ok += 1
    logging.info(f'=== Done: {ok}/{len(dates)} dates fully processed ===')


if __name__ == '__main__':
    main()
