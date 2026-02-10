# CLAT Preparation Project - Claude Instructions

## GCP Production Server

**Production URL:** https://speedmathsgames.com
**GCP VM:** `speedmathsgames-server` (zone: `us-central1-a`, IP: `34.61.145.248`)
**Server Port:** 8765

### GCP VM Directory Structure

```
/opt/speedmathsgames/              # Root (owned by www-data:www-data)
├── .env                           # API keys (ANTHROPIC_API_KEY, etc.)
├── .git/                          # Git repo (origin: github.com/k12arvind/speedmathsgames.git via HTTPS)
├── server/
│   ├── unified_server.py          # Main server
│   ├── momentum_scanner.py        # Momentum scanner
│   ├── momentum_db.py             # Momentum DB module
│   ├── momentum_tracker.db        # Momentum SQLite DB
│   └── ...                        # Other server modules
├── dashboard/
│   ├── index.html                 # Main hub
│   ├── momentum_dashboard.html    # Momentum scanner dashboard
│   ├── shared-styles.css          # Shared CSS
│   └── ...                        # Other HTML pages
├── book_practice/
│   ├── book_db.py
│   ├── book_practice.db
│   └── uploads/
├── scripts/
│   ├── momentum_scan_cron.py      # Daily scan cron job
│   ├── momentum-scan.service      # systemd service (copied to /etc/systemd/system/)
│   ├── momentum-scan.timer        # systemd timer (copied to /etc/systemd/system/)
│   └── start_server.sh
├── auth/
│   └── users.db                   # User auth database
├── logs/                          # Server and scan logs
├── venv/                          # Python 3.11 virtualenv
│   └── bin/python
├── backups/                       # Automated DB backups
└── requirements.txt
```

**Key facts:**
- Everything owned by `www-data:www-data`
- Server runs as `www-data` user
- Python: `/opt/speedmathsgames/venv/bin/python` (3.11.2)
- Git: installed, HTTPS remote (read-only pulls, no SSH key needed)
- Momentum DB: `/opt/speedmathsgames/server/momentum_tracker.db`

### SSH into GCP VM
```bash
gcloud compute ssh speedmathsgames-server --zone=us-central1-a
```

### Deploy to GCP (git pull method — preferred)

```bash
# One-liner from local machine (after git push):
gcloud compute ssh speedmathsgames-server --zone=us-central1-a --command="\
  cd /opt/speedmathsgames && \
  sudo -u www-data git pull origin main && \
  sudo -u www-data /opt/speedmathsgames/venv/bin/pip install -r requirements.txt && \
  sudo kill \$(pgrep -f unified_server) 2>/dev/null; sleep 2 && \
  cd /opt/speedmathsgames && sudo -u www-data nohup /opt/speedmathsgames/venv/bin/python unified_server.py --port 8765 > logs/server.log 2>&1 & \
  sleep 3 && curl -s http://localhost:8765/api/test"
```

### Deploy individual files (scp method — when git isn't practical)

```bash
# 1. Copy file to /tmp via scp
gcloud compute scp <local-file> arvind@speedmathsgames-server:/tmp/<filename> --zone=us-central1-a

# 2. Move to correct location on VM
gcloud compute ssh speedmathsgames-server --zone=us-central1-a --command="\
  sudo cp /tmp/<filename> /opt/speedmathsgames/<target-path> && \
  sudo chown www-data:www-data /opt/speedmathsgames/<target-path>"

# 3. Restart server if needed (only for server/ changes, NOT for dashboard/ changes)
gcloud compute ssh speedmathsgames-server --zone=us-central1-a --command="\
  sudo kill \$(pgrep -f unified_server) 2>/dev/null; sleep 2 && \
  cd /opt/speedmathsgames && sudo -u www-data nohup /opt/speedmathsgames/venv/bin/python unified_server.py --port 8765 > logs/server.log 2>&1 &"
```

**Note:** Dashboard HTML/CSS/JS changes are served statically — no server restart needed.

### Restart server only

```bash
gcloud compute ssh speedmathsgames-server --zone=us-central1-a --command="\
  sudo kill \$(pgrep -f unified_server) 2>/dev/null; sleep 2 && \
  cd /opt/speedmathsgames && sudo -u www-data nohup /opt/speedmathsgames/venv/bin/python unified_server.py --port 8765 > logs/server.log 2>&1 & \
  sleep 3 && ps aux | grep unified_server | grep -v grep"
```

### Daily Momentum Scan (systemd timer)

- Timer: `momentum-scan.timer` — runs Mon-Fri at 12:30 UTC (6:00 PM IST)
- Service: `momentum-scan.service` — runs `scripts/momentum_scan_cron.py` as `www-data`
- Logs: `/opt/speedmathsgames/logs/momentum_scan.log`
- Skips weekends and NSE holidays (2026 list in cron script)

```bash
# Check timer status
gcloud compute ssh speedmathsgames-server --zone=us-central1-a --command="sudo systemctl status momentum-scan.timer --no-pager"

# View scan logs
gcloud compute ssh speedmathsgames-server --zone=us-central1-a --command="tail -50 /opt/speedmathsgames/logs/momentum_scan.log"

# Run scan manually
gcloud compute ssh speedmathsgames-server --zone=us-central1-a --command="sudo -u www-data /opt/speedmathsgames/venv/bin/python /opt/speedmathsgames/scripts/momentum_scan_cron.py"

# If systemd files change, re-deploy them:
# sudo cp /opt/speedmathsgames/scripts/momentum-scan.{service,timer} /etc/systemd/system/
# sudo systemctl daemon-reload && sudo systemctl restart momentum-scan.timer
```

## Local Development

- Run locally: `/usr/local/bin/python3.13 server/unified_server.py --port 8765`
- Local URL: `http://localhost:8765`
- Python 3.13 has all deps installed system-wide (--break-system-packages)

## Browser Testing Before Deploy

Always test locally before deploying to GCP:
1. Start local server on port 8765
2. Use dev-browser skill (headless Chromium) to test all pages
3. Test: main hub, momentum dashboard (all tabs), methodology page
4. Test: Run Scan button, F&O filter, sector filter, search
5. Verify API endpoints: /api/momentum/summary, /api/momentum/results

## Momentum Scanner Module

- Scanner: `server/momentum_scanner.py` (TradingView Screener + yfinance)
- Database: `server/momentum_db.py` (SQLite — local: `~/clat_preparation/momentum_tracker.db`, GCP: `/opt/speedmathsgames/server/momentum_tracker.db`)
- Dashboard: `dashboard/momentum_dashboard.html`
- Methodology: `dashboard/momentum_methodology.html`
- Cron job: `scripts/momentum_scan_cron.py` (daily at 6 PM IST via systemd timer)
- Private module: only visible to parent accounts (Arvind & Deepa)
- Key deps: `tradingview-screener`, `yfinance`, `pandas`, `numpy`

## Book Practice Module

- Database: `book_practice/book_practice.db`
- Uploads stored in: `book_practice/uploads/`
- Uses Claude Vision API for extracting questions from book page photos
- Detects **circled question numbers** (not tick marks)
- Auto-detects topic from page number using Table of Contents page ranges
- Answer key pages auto-match to topics via `answer_key_page_start/end` columns

## Key Directories

- `server/` - Python unified server
- `dashboard/` - HTML frontend files (served statically)
- `book_practice/` - RS Aggarwal book practice module
- `scripts/` - Deployment, cron, and utility scripts
- `logs/` - Server and scan logs
- `auth/` - User authentication (users.db)
- `backups/` - Automated database backups
