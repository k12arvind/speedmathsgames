# CLAT Preparation System - Architecture

## Overview

Two-machine setup with MacBook Pro as **development/source** and Mac Mini as **production server**.

## Machine Roles

### MacBook Pro (Development/Source)
- **Primary development machine**
- **Source of truth** for all code and data
- Git repository maintained here
- PDFs stored here: `~/saanvi/` (synced to iCloud)
- Testing server: `http://localhost:8001`

### Mac Mini (Production)
- **Production server** running 24/7
- Receives code and data from MacBook Pro via sync
- Public access via Cloudflare Tunnel
- Public URL: `https://speedmathsgames.com`

## Directory Structure

### Code Location (Both Machines)
```
~/clat_preparation/
├── unified_server.py          # Main HTTP server
├── assessment_database.py     # Assessment/test logic
├── pdf_scanner.py             # Scans PDFs from ~/saanvi/
├── anki_connector.py          # Anki integration
├── auth/                      # Google OAuth
│   ├── google_auth.py
│   └── user_db.py
├── dashboard/                 # HTML/CSS/JS files
│   ├── index.html
│   ├── comprehensive_dashboard.html
│   ├── assessment.html
│   ├── pdf_dashboard.html
│   └── daily_analytics.html
├── math/                      # Math practice
│   ├── math_api.py
│   └── math_db.py
├── logs/                      # Server logs
└── .git/                      # Version control (MacBook only)
```

### PDF Location (Both Machines)
```
~/saanvi/
├── Legaledgedailygk/          # Daily current affairs PDFs
│   └── current_affairs_2025_december_*.pdf
├── LegalEdgeweeklyGK/         # Weekly current affairs PDFs
│   └── weekly-current-affairs-*.pdf
└── weeklyGKCareerLauncher/    # Weekly GK from Career Launcher
    └── 5070_Manthan2.0*.pdf
```

**Note:** This folder can be shared on iCloud Drive for iPad access. Both machines use identical structure to avoid confusion.

## Version Control

### Git Repository (MacBook Pro Only)
- Repository: `~/clat_preparation/.git`
- Tracks: Python code, HTML/CSS/JS, configuration
- Ignores: PDFs, databases, logs, venv

### Syncing Changes

**To sync MacBook Pro → Mac Mini:**
```bash
cd ~/clat_preparation
./sync_to_mac_mini.sh
```

This syncs:
1. Python code (*.py files)
2. Dashboard files (HTML/CSS/JS)
3. Math module
4. New PDFs (preserves existing)
5. Restarts Mac Mini server

## Server Architecture

### Unified Server (Port 8001)
```
unified_server.py
├── Authentication (Google OAuth)
├── GK Dashboard API
│   ├── /api/dashboard
│   ├── /api/pdfs/*
│   └── /api/stats
├── Assessment API
│   ├── /api/assessment/start
│   ├── /api/assessment/submit
│   └── /api/assessment/results
├── Math API
│   ├── /api/math/questions
│   └── /api/math/submit
└── Analytics API
    ├── /api/analytics/daily
    └── /api/analytics/categories
```

### Cloudflare Tunnel (Mac Mini Only)
```
speedmathsgames.com → Cloudflare Tunnel → localhost:8001
```

Managed by: `launchctl` (always running)

## Databases

### 1. Revision Tracker (`revision_tracker.db`)
- Location: `~/clat_preparation/`
- Tables: `topics`, `revisions`, `pdfs`, `statistics`
- Purpose: GK topics and revision tracking

### 2. Assessment Database (`assessment.db`)
- Location: `~/clat_preparation/`
- Tables: `test_sessions`, `question_attempts`, `question_performance`
- Purpose: Assessment tests and analytics

### 3. Math Tracker (`math/math_tracker.db`)
- Location: `~/clat_preparation/math/`
- Tables: `questions`, `user_progress`, `sessions`
- Purpose: Math practice tracking

### 4. Users Database (`auth/users.db`)
- Location: `~/clat_preparation/auth/`
- Tables: `users`, `sessions`
- Purpose: User authentication and sessions

## Data Flow

### 1. Daily Current Affairs Processing
```
TopRankers URL
    ↓
MacBook Pro: generate_clean_pdf_final.py
    ↓
PDF saved: ~/saanvi/Legaledgedailygk/
    ↓
MacBook Pro: automate_html.sh
    ↓
Anki cards created and imported
    ↓
Run: ./sync_to_mac_mini.sh
    ↓
PDF synced to Mac Mini
    ↓
Mac Mini: PDF scanner detects new file
    ↓
Visible in dashboard
```

### 2. Assessment Flow
```
User clicks "Take Test" on dashboard
    ↓
Frontend: assessment.html
    ↓
API: /api/assessment/start
    ↓
Backend: Fetches questions from Anki
    ↓
User answers questions
    ↓
API: /api/assessment/submit
    ↓
Backend: Stores in assessment.db
    ↓
Results displayed + Analytics updated
```

## Key Principles

### 1. Single Source of Truth
- **MacBook Pro** is the source
- All development happens here
- Git tracks code changes
- PDFs stored here first

### 2. Sync, Don't Modify on Mac Mini
- Mac Mini receives updates
- Don't edit code directly on Mac Mini
- Only logs and databases change on Mac Mini

### 3. Folder Structure Consistency
- **NEVER** change `~/saanvi/` paths
- `pdf_scanner.py` expects this exact structure
- Both machines must have identical structure
- This folder is in home directory (not Desktop) to avoid permission issues

### 4. Database Independence
- Databases are **NOT** synced
- Each machine has independent data
- Mac Mini has production data
- MacBook Pro has test data

## Common Operations

### Add New Feature
```bash
# On MacBook Pro
cd ~/clat_preparation
git status
# Edit files
git add .
git commit -m "Add feature"
./sync_to_mac_mini.sh
```

### Add New Daily PDF
```bash
# On MacBook Pro
cd ~/Desktop/anki_automation
source venv/bin/activate
source ~/.zshrc
./automate_html.sh https://www.toprankers.com/current-affairs-[date]
# PDF automatically saved to ~/saanvi/Legaledgedailygk/
# Then sync PDFs to Mac Mini
cd ~/clat_preparation
./auto_sync_pdfs.sh
```

### Restart Mac Mini Server
```bash
ssh mac-mini "launchctl stop com.clatprep.server && launchctl start com.clatprep.server"
```

### View Mac Mini Logs
```bash
ssh mac-mini "tail -50 ~/clat_preparation/logs/server.log"
```

### Check Server Status
```bash
# Mac Mini (local)
curl http://localhost:8001/api/dashboard

# Mac Mini (public)
curl https://speedmathsgames.com/api/dashboard
```

## Troubleshooting

### PDFs Not Showing
1. Check PDFs exist: `ls ~/saanvi/Legaledgedailygk/`
2. Check scanner paths: `grep BASE_PATH ~/clat_preparation/pdf_scanner.py`
3. Sync: `./auto_sync_pdfs.sh`
4. Test scanner: `python3 ~/clat_preparation/pdf_scanner.py`
5. Restart server on Mac Mini if needed

### Code Changes Not Reflecting
1. Check you synced: `./sync_to_mac_mini.sh`
2. Verify server restarted
3. Clear browser cache

### Authentication Not Working
1. Check `.env` exists: `ls ~/clat_preparation/.env`
2. Verify OAuth credentials set
3. Server must run WITHOUT `--no-auth` flag

### Folder Structure Clarification
- **ALWAYS** use `~/saanvi/` (home directory, not Desktop)
- Desktop has permission issues on Mac Mini
- Same structure on both machines avoids confusion
- Folder can be shared on iCloud for iPad access

## Environment Variables

### Required Variables (.env)
```bash
# Anthropic API (for flashcard generation)
ANTHROPIC_API_KEY=sk-ant-api03-...

# Google OAuth (for authentication)
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_REDIRECT_URI=https://speedmathsgames.com/auth/callback
```

## URLs

### Local (MacBook Pro)
- Main: http://localhost:8001/
- Dashboard: http://localhost:8001/comprehensive_dashboard.html
- Assessment: http://localhost:8001/assessment.html
- Analytics: http://localhost:8001/dashboard/daily_analytics.html

### Local Network (Mac Mini)
- Main: http://mac-mini:8001/
- Dashboard: http://mac-mini:8001/comprehensive_dashboard.html

### Public (Mac Mini via Cloudflare)
- Main: https://speedmathsgames.com/
- Dashboard: https://speedmathsgames.com/comprehensive_dashboard.html
- Assessment: https://speedmathsgames.com/assessment.html

## Maintenance

### Daily
- Download new PDFs from LegalEdge to `~/saanvi/` folders
- Run `./auto_sync_pdfs.sh` to sync to Mac Mini

### Weekly
- Commit code changes: `git add . && git commit -m "..."`
- Check Mac Mini server logs
- Verify public URL is accessible

### Monthly
- Review database sizes
- Clean old logs: `rm ~/clat_preparation/logs/*.log`
- Backup databases

## Future Improvements

- [ ] Automated Git commits before sync
- [ ] Automated sync on file changes (fswatch)
- [ ] Database backup to MacBook Pro
- [ ] Health monitoring dashboard
- [ ] Automated testing before sync
