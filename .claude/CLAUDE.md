# CLAT Preparation Project - Claude Instructions

## GCP Production Server

**Production URL:** https://speedmathsgames.com
**GCP VM:** `speedmathsgames-server` (zone: `us-central1-a`, IP: `34.61.145.248`)
**Server Port:** 8765

### SSH into GCP VM
```bash
gcloud compute ssh speedmathsgames-server --zone=us-central1-a
```

### Deploy to GCP (after pushing to GitHub)
```bash
# 1. SSH into GCP VM
gcloud compute ssh speedmathsgames-server --zone=us-central1-a

# 2. Pull latest code
cd ~/clat_preparation && git pull

# 3. Install any new dependencies
./venv_clat/bin/pip install -r requirements.txt

# 4. Restart server
pkill -f unified_server; sleep 2
cd ~/clat_preparation && nohup ./venv_clat/bin/python server/unified_server.py --port 8765 > logs/server.log 2>&1 &

# 5. Verify
curl -s http://localhost:8765/api/momentum/summary
```

### One-liner deploy (from local machine)
```bash
gcloud compute ssh speedmathsgames-server --zone=us-central1-a --command="cd ~/clat_preparation && git pull && ./venv_clat/bin/pip install -r requirements.txt && pkill -f unified_server; sleep 2 && cd ~/clat_preparation && nohup ./venv_clat/bin/python server/unified_server.py --port 8765 > logs/server.log 2>&1 &"
```

### Server startup script (on GCP VM)
- Location: `~/clat_preparation/scripts/start_server.sh`
- Uses venv: `~/clat_preparation/venv_clat/`
- Loads API keys from: `~/clat_preparation/.env`
- Python: `~/clat_preparation/venv_clat/bin/python`

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
- Database: `server/momentum_db.py` (SQLite at `~/clat_preparation/momentum_tracker.db`)
- Dashboard: `dashboard/momentum_dashboard.html`
- Methodology: `dashboard/momentum_methodology.html`
- Cron job: `scripts/momentum_scan_cron.py` (run daily at 6:30 PM IST)
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
- `dashboard/` - HTML frontend files
- `book_practice/` - RS Aggarwal book practice module
- `scripts/` - Deployment and utility scripts
- `logs/` - Server logs
