#!/usr/bin/env python3
"""
drishti_daily_cron.py

Daily cron that pulls the latest current-affairs material from BOTH:
  * Drishti IAS         — news-analysis page (/news-analysis/dd-mm-yyyy)
  * LegalEdge / TopRankers — daily current-affairs page (/current-affairs-Nth-month-yyyy)

For each source, for each candidate date (today + yesterday IST, Mon–Sat):
  1. Hit /api/create-pdf-from-url with the source URL.
  2. If a PDF was created/exists, kick off /api/create-assessment.
  3. Poll until questions are generated.

Skips Sundays. Idempotent — already-complete dates are skipped via
/api/assessment-status. Designed to run on the GCP VM via systemd
(scripts/drishti-daily.service / .timer).

Note on logging: stdout is captured by systemd's `StandardOutput=append:`
directive, which writes the log as root. The script must NOT also open
the same file via FileHandler — that crashes with PermissionError when
running as www-data. Stick to StreamHandler(sys.stdout).
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

# Indian Standard Time offset (no DST).
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))

# Per-source assessment poll budget. 15 min is enough for image-heavy days
# on the small VM running Claude assessments serially.
POLL_TIMEOUT_SEC = 900
POLL_INTERVAL_SEC = 30


def setup_logging():
    # systemd's StandardOutput=append: captures stdout to a root-owned log
    # file. We do NOT open a FileHandler here — that would race with systemd
    # and PermissionError as www-data.
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)],
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
    return [d for d in candidates if d.weekday() != 6]


# ----------------------------------------------------------------------
# Source: Drishti IAS
# ----------------------------------------------------------------------

DRISHTI_MONTHS = ['', 'january', 'february', 'march', 'april', 'may', 'june',
                  'july', 'august', 'september', 'october', 'november', 'december']


def drishti_filename(date: dt.date) -> str:
    return f'drishti_current_affairs_{date.year}_{DRISHTI_MONTHS[date.month]}_{date.day}.pdf'


def drishti_url(date: dt.date) -> str:
    return (
        'https://www.drishtiias.com/current-affairs-news-analysis-editorials/'
        f'news-analysis/{date.day:02d}-{date.month:02d}-{date.year:04d}'
    )


def drishti_week(date: dt.date) -> str:
    return f'{date.year}_{date.strftime("%b")}_D{date.day}'


# ----------------------------------------------------------------------
# Source: LegalEdge / TopRankers
# ----------------------------------------------------------------------

def ordinal_suffix(day: int) -> str:
    """1→st, 2→nd, 3→rd, 4-20→th, 21→st, 22→nd, 23→rd, 24-30→th, 31→st."""
    if 11 <= day % 100 <= 13:
        return 'th'
    return {1: 'st', 2: 'nd', 3: 'rd'}.get(day % 10, 'th')


def legaledge_filename(date: dt.date) -> str:
    return f'current_affairs_{date.year}_{DRISHTI_MONTHS[date.month]}_{date.day}.pdf'


def legaledge_url(date: dt.date) -> str:
    month_name = DRISHTI_MONTHS[date.month]   # full month name lowercased
    return (
        f'https://www.toprankers.com/current-affairs-'
        f'{date.day}{ordinal_suffix(date.day)}-{month_name}-{date.year}'
    )


def legaledge_week(date: dt.date) -> str:
    return f'{date.year}_{date.strftime("%b")}_D{date.day}_LE'


# ----------------------------------------------------------------------
# Generic fetch + assess + poll
# ----------------------------------------------------------------------

SOURCES = [
    {
        'name': 'drishti',
        'label': 'Drishti',
        'filename_for': drishti_filename,
        'url_for': drishti_url,
        'week_for': drishti_week,
        'assessment_source': 'drishti',
    },
    {
        'name': 'legaledge',
        'label': 'LegalEdge',
        'filename_for': legaledge_filename,
        'url_for': legaledge_url,
        'week_for': legaledge_week,
        'assessment_source': 'legaledge',
    },
]


def already_has_questions(filename: str) -> bool:
    status = get_json(f'/api/assessment-status/{filename}')
    return bool(status.get('all_complete')) and (status.get('total_cards', 0) > 0)


def fetch_one(source: dict, date: dt.date) -> tuple[str, str]:
    """Process one (source, date) pair.

    Returns (status, detail) where status is one of:
      'done'        — questions already exist or were generated this run
      'no-publish'  — source returned 404/no PDF (e.g. publication missed today)
      'failed'      — an error we should keep running past
    """
    label = source['label']
    filename = source['filename_for'](date)
    url = source['url_for'](date)

    if already_has_questions(filename):
        logging.info(f'[{label} {date}] ✅ questions already exist for {filename} — skipping')
        return ('done', 'pre-existing')

    logging.info(f'[{label} {date}] fetching PDF from {url}')
    pdf_result = post_json('/api/create-pdf-from-url', {'url': url}, timeout=300)
    if not pdf_result.get('success'):
        err = str(pdf_result.get('error') or '')
        # Treat "publication not yet available" cases as no-publish (the next
        # day's run, which also pulls yesterday, will pick it up):
        #   - HTTP 404 / "not found"
        #   - TopRankers soft-404: their server returns 200 with a 404 page,
        #     so the upstream script raises "No topics found in HTML content"
        #   - Drishti pre-publication: "No articles found on the Drishti page"
        no_publish_signals = (
            '404', 'not found', 'no such', 'returned 404',
            'no topics found',          # TopRankers soft-404
            'no articles found',         # Drishti before publish
        )
        if any(s in err.lower() for s in no_publish_signals):
            logging.info(f'[{label} {date}] no publication yet — will retry tomorrow')
            return ('no-publish', err[:200])
        logging.warning(f'[{label} {date}] PDF generation failed: {err[:200]}')
        return ('failed', err[:200])

    logging.info(
        f'[{label} {date}] PDF ok: {pdf_result.get("filename")} '
        f'({pdf_result.get("size_kb",0):.0f} KB, '
        f'existed={pdf_result.get("already_existed")})'
    )

    week = source['week_for'](date)
    logging.info(f'[{label} {date}] kicking off assessment for {filename} (week={week})')
    assess = post_json('/api/create-assessment', {
        'pdf_id': filename,
        'source': source['assessment_source'],
        'week': week,
    }, timeout=30)
    job_id = assess.get('job_id')
    if not job_id:
        logging.warning(f'[{label} {date}] assessment kickoff failed: {assess.get("error")}')
        return ('failed', f'assess-kickoff: {assess.get("error")}')
    logging.info(f'[{label} {date}] assessment started: job_id={job_id[:12]}')

    start = time.monotonic()
    while time.monotonic() - start < POLL_TIMEOUT_SEC:
        status = get_json(f'/api/assessment-status/{filename}')
        if status.get('all_complete') and status.get('total_cards', 0) > 0:
            logging.info(
                f'[{label} {date}] ✅ assessment complete: {status["total_cards"]} cards'
            )
            return ('done', f'{status["total_cards"]} cards')
        time.sleep(POLL_INTERVAL_SEC)

    logging.warning(f'[{label} {date}] ⏱ assessment timed out after {POLL_TIMEOUT_SEC}s')
    return ('failed', 'timeout')


def main():
    setup_logging()
    logging.info('=== Daily GK cron starting (Drishti + LegalEdge) ===')
    dates = candidate_dates()
    logging.info(f'Candidate dates (IST today + yesterday, excl. Sundays): {dates}')

    summary: dict[str, dict[str, int]] = {}
    for source in SOURCES:
        summary[source['label']] = {'done': 0, 'no-publish': 0, 'failed': 0}
        for d in dates:
            status, _detail = fetch_one(source, d)
            summary[source['label']][status] = summary[source['label']].get(status, 0) + 1

    logging.info('=== Summary ===')
    for label, counts in summary.items():
        logging.info(
            f'  {label}: done={counts.get("done",0)} '
            f'no-publish={counts.get("no-publish",0)} '
            f'failed={counts.get("failed",0)}'
        )
    logging.info('=== Done ===')


if __name__ == '__main__':
    main()
