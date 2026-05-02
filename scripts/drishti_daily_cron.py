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
import re
import sys
import time
import urllib.request
from pathlib import Path
from typing import Optional
from urllib.error import HTTPError, URLError


SERVER = 'http://localhost:8765'

# Indian Standard Time offset (no DST).
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))

# Per-source assessment poll budget. 15 min is enough for image-heavy days
# on the small VM running Claude assessments serially.
POLL_TIMEOUT_SEC = 900
POLL_INTERVAL_SEC = 30

# Hard cap on auto-backfill so a broken upstream can't drag the cron through
# weeks of dates. If the DB hasn't seen a PDF in this many days, we treat that
# as a manual-intervention case and only retry the most recent two days.
MAX_AUTO_BACKFILL_DAYS = 14


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


# Match a date triplet at the end of a PDF filename:
#   current_affairs_2026_april_30.pdf            → (2026, april, 30)
#   drishti_current_affairs_2026_april_30.pdf    → (2026, april, 30)
#   drishti_current_affairs_2026_april_30_part2.pdf → (2026, april, 30)
PDF_DATE_RE = re.compile(
    r'_(\d{4})_([a-zA-Z]+)_(\d{1,2})(?:_part\d+)?\.pdf$',
)


def latest_pdf_date(pdf_dir: Optional[str], filename_prefix: str) -> Optional[dt.date]:
    """Walk the source's PDF directory and return the most recent date for
    which a PDF was saved (parsing the date out of the filename).
    Returns None if the dir is missing or nothing matches.
    """
    if not pdf_dir:
        return None
    p = Path(pdf_dir)
    if not p.is_dir():
        return None
    months = {name: idx for idx, name in enumerate(DRISHTI_MONTHS) if name}
    latest: Optional[dt.date] = None
    for f in p.glob('*.pdf'):
        if filename_prefix and not f.name.startswith(filename_prefix):
            continue
        m = PDF_DATE_RE.search(f.name)
        if not m:
            continue
        try:
            year = int(m.group(1))
            month = months.get(m.group(2).lower())
            day = int(m.group(3))
            if not month:
                continue
            d = dt.date(year, month, day)
        except (ValueError, KeyError):
            continue
        if latest is None or d > latest:
            latest = d
    return latest


def candidate_dates_for(source: dict) -> list[dt.date]:
    """Build the date window for ONE source: from the day AFTER the latest
    PDF on disk for that source through today (IST), skipping Sundays.

    If we can't find any prior PDF (fresh deploy / dir missing), default to
    "yesterday + today" — same as the old behavior.

    Capped at MAX_AUTO_BACKFILL_DAYS. If the latest PDF is older than the
    cap, we trim the window to the cap rather than scanning weeks of dates.
    """
    today_ist = dt.datetime.now(IST).date()
    last = latest_pdf_date(source.get('pdf_dir'), source.get('filename_prefix', ''))
    if last is None:
        start = today_ist - dt.timedelta(days=1)
    else:
        start = last + dt.timedelta(days=1)
    # Cap how far back we'll go automatically.
    cap = today_ist - dt.timedelta(days=MAX_AUTO_BACKFILL_DAYS)
    if start < cap:
        logging.warning(
            f'[{source["label"]}] last saved PDF is {last} (>{MAX_AUTO_BACKFILL_DAYS}d old) '
            f'— trimming window to {cap}. Backfill the gap manually.'
        )
        start = cap
    # Ensure at least today + yesterday are tried, even if the source thinks
    # it's already up-to-date (handles late-publication).
    earliest_default = today_ist - dt.timedelta(days=1)
    if start > earliest_default:
        start = earliest_default
    out: list[dt.date] = []
    d = start
    while d <= today_ist:
        if d.weekday() != 6:  # skip Sundays
            out.append(d)
        d += dt.timedelta(days=1)
    return out


def candidate_dates() -> list[dt.date]:
    """Backwards-compatible default: yesterday + today (IST). Skip Sundays."""
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
        'pdf_dir': '/var/www/saanvi/DrishtiDailyGK',
        'filename_prefix': 'drishti_current_affairs_',
    },
    {
        'name': 'legaledge',
        'label': 'LegalEdge',
        'filename_for': legaledge_filename,
        'url_for': legaledge_url,
        'week_for': legaledge_week,
        'assessment_source': 'legaledge',
        'pdf_dir': '/var/www/saanvi/Legaledgedailygk',
        'filename_prefix': 'current_affairs_',
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

    summary: dict[str, dict[str, int]] = {}
    for source in SOURCES:
        dates = candidate_dates_for(source)
        last = latest_pdf_date(source.get('pdf_dir'), source.get('filename_prefix', ''))
        logging.info(
            f'[{source["label"]}] last saved={last}; '
            f'candidates (excl. Sundays): {dates}'
        )
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
