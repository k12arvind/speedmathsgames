# SpeedMathsGames.com - Deployment & Operations Guide

**Last Updated:** January 3, 2026

---

## Table of Contents

1. [Deployment Architecture](#1-deployment-architecture)
2. [Development Setup](#2-development-setup)
3. [Production Setup](#3-production-setup)
4. [Syncing Code](#4-syncing-code)
5. [Server Operations](#5-server-operations)
6. [Cloudflare Tunnel](#6-cloudflare-tunnel)
7. [Database Operations](#7-database-operations)
8. [Monitoring & Logging](#8-monitoring--logging)
9. [Backup & Recovery](#9-backup--recovery)
10. [Troubleshooting](#10-troubleshooting)
11. [Security](#11-security)

---

## 1. Deployment Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                          INTERNET                                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              CLOUDFLARE (DNS + Tunnel)                          │
│              speedmathsgames.com                                 │
│              - SSL/TLS termination                              │
│              - DDoS protection                                  │
│              - Caching                                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   MAC MINI (Production)                          │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  cloudflared tunnel                                      │    │
│  │  └── forwards to localhost:8001                         │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  unified_server.py (ThreadingHTTPServer)                │    │
│  │  Port: 8001                                              │    │
│  │  ├── Static files (dashboard/*.html, *.css, *.js)       │    │
│  │  ├── REST API (/api/*)                                   │    │
│  │  ├── OAuth (/auth/*)                                     │    │
│  │  └── PDF serving (/pdf/*)                                │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  SQLite Databases                                        │    │
│  │  ├── revision_tracker.db                                 │    │
│  │  ├── math_tracker.db                                     │    │
│  │  ├── assessment_tracker.db                               │    │
│  │  ├── finance_tracker.db                                  │    │
│  │  ├── health_tracker.db                                   │    │
│  │  └── calendar_tracker.db                                 │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

### Machine Details

| Property | MacBook Pro (Dev) | Mac Mini (Prod) |
|----------|-------------------|-----------------|
| Username | arvind | arvindkumar |
| Home | /Users/arvind | /Users/arvindkumar |
| Project Path | ~/clat_preparation | ~/clat_preparation |
| PDF Path | ~/saanvi | ~/saanvi |
| Server Port | 8001 | 8001 |
| Public URL | N/A | speedmathsgames.com |
| SSH Alias | N/A | mac-mini |

---

## 2. Development Setup

### Prerequisites
- macOS (tested on Darwin 25.0.0)
- Python 3.9+
- Git
- Anki Desktop with AnkiConnect add-on

### Initial Setup

```bash
# Clone repository
cd ~
git clone https://github.com/k12arvind/speedmathsgames.git clat_preparation
cd clat_preparation

# Create virtual environment
python3 -m venv venv_clat
source venv_clat/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cat > .env << 'EOF'
ANTHROPIC_API_KEY=sk-ant-api03-...
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_REDIRECT_URI=http://localhost:8001/auth/callback
EOF

# Create PDF directories
mkdir -p ~/saanvi/Legaledgedailygk
mkdir -p ~/saanvi/LegalEdgeweeklyGK
mkdir -p ~/saanvi/weeklyGKCareerLauncher
```

### Running Development Server

```bash
cd ~/clat_preparation
source venv_clat/bin/activate

# With authentication (production-like)
python3 server/unified_server.py

# Without authentication (for testing)
python3 server/unified_server.py --no-auth

# Custom port
python3 server/unified_server.py --port 8080
```

### Accessing Development Server

| Page | URL |
|------|-----|
| Landing | http://localhost:8001/ |
| Login | http://localhost:8001/login.html |
| Dashboard | http://localhost:8001/comprehensive_dashboard.html |
| Math | http://localhost:8001/math_practice.html |

---

## 3. Production Setup

### Mac Mini Initial Setup

```bash
# SSH to Mac Mini
ssh mac-mini

# Clone repository
cd ~
git clone https://github.com/k12arvind/speedmathsgames.git clat_preparation
cd clat_preparation

# Create virtual environment
python3 -m venv venv_clat
source venv_clat/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create .env file (with production redirect URI)
cat > .env << 'EOF'
ANTHROPIC_API_KEY=sk-ant-api03-...
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_REDIRECT_URI=https://speedmathsgames.com/auth/callback
EOF

# Create PDF directories
mkdir -p ~/saanvi/Legaledgedailygk
mkdir -p ~/saanvi/LegalEdgeweeklyGK
mkdir -p ~/saanvi/weeklyGKCareerLauncher
```

### LaunchAgent Setup (Auto-start on boot)

Create `/Users/arvindkumar/Library/LaunchAgents/com.clatprep.server.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.clatprep.server</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/arvindkumar/clat_preparation/venv_clat/bin/python3</string>
        <string>/Users/arvindkumar/clat_preparation/server/unified_server.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/Users/arvindkumar/clat_preparation</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/Users/arvindkumar/clat_preparation/logs/server.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/arvindkumar/clat_preparation/logs/server.error.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin</string>
    </dict>
</dict>
</plist>
```

Load the service:
```bash
launchctl load ~/Library/LaunchAgents/com.clatprep.server.plist
launchctl start com.clatprep.server
```

---

## 4. Syncing Code

### Development → Production Workflow

```bash
# On MacBook Pro (Development)
cd ~/clat_preparation

# 1. Make changes and test locally
python3 server/unified_server.py --no-auth
# Test at http://localhost:8001

# 2. Commit changes
git add .
git commit -m "Description of changes"
git push origin main

# 3. SSH to Mac Mini and pull
ssh mac-mini "cd ~/clat_preparation && git pull origin main"

# 4. Restart server
ssh mac-mini "launchctl stop com.clatprep.server && launchctl start com.clatprep.server"

# 5. Verify
curl https://speedmathsgames.com/api/test
```

### Syncing PDFs

PDFs are NOT in Git (too large). Sync manually:

```bash
# From MacBook Pro
cd ~/clat_preparation
./scripts/auto_sync_pdfs.sh

# Or manually with rsync
rsync -avz ~/saanvi/ mac-mini:~/saanvi/
```

### One-Command Deploy Script

Create `deploy.sh`:
```bash
#!/bin/bash
set -e

echo "=== Deploying to Production ==="

# Commit any uncommitted changes
if [[ $(git status --porcelain) ]]; then
    echo "Uncommitted changes found. Please commit first."
    exit 1
fi

# Push to GitHub
echo "Pushing to GitHub..."
git push origin main

# Pull on Mac Mini
echo "Pulling on Mac Mini..."
ssh mac-mini "cd ~/clat_preparation && git pull origin main"

# Restart server
echo "Restarting server..."
ssh mac-mini "launchctl stop com.clatprep.server && launchctl start com.clatprep.server"

# Wait for server
sleep 3

# Verify
echo "Verifying..."
curl -s https://speedmathsgames.com/api/test | grep -q "ok" && echo "✅ Deploy successful!" || echo "❌ Deploy failed!"
```

---

## 5. Server Operations

### Start Server

```bash
# Via launchctl (recommended)
launchctl start com.clatprep.server

# Manual start
cd ~/clat_preparation
source venv_clat/bin/activate
python3 server/unified_server.py
```

### Stop Server

```bash
# Via launchctl
launchctl stop com.clatprep.server

# Force kill
lsof -ti:8001 | xargs kill -9
```

### Restart Server

```bash
launchctl stop com.clatprep.server && launchctl start com.clatprep.server
```

### Check Server Status

```bash
# Check if process is running
lsof -ti:8001

# Check if responding
curl http://localhost:8001/api/test

# Check public URL
curl https://speedmathsgames.com/api/test

# View recent logs
tail -50 ~/clat_preparation/logs/server.log
```

---

## 6. Cloudflare Tunnel

### Overview

Cloudflare Tunnel provides secure access to the Mac Mini without port forwarding or static IP.

### Tunnel Setup

1. Install cloudflared:
```bash
brew install cloudflared
```

2. Authenticate:
```bash
cloudflared tunnel login
```

3. Create tunnel:
```bash
cloudflared tunnel create clat-prep
```

4. Configure tunnel (`~/.cloudflared/config.yml`):
```yaml
tunnel: <tunnel-id>
credentials-file: /Users/arvindkumar/.cloudflared/<tunnel-id>.json

ingress:
  - hostname: speedmathsgames.com
    service: http://localhost:8001
  - service: http_status:404
```

5. Route DNS:
```bash
cloudflared tunnel route dns clat-prep speedmathsgames.com
```

### Tunnel LaunchAgent

Create `/Users/arvindkumar/Library/LaunchAgents/com.cloudflare.tunnel.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.cloudflare.tunnel</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/cloudflared</string>
        <string>tunnel</string>
        <string>run</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/Users/arvindkumar/clat_preparation/logs/cloudflared.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/arvindkumar/clat_preparation/logs/cloudflared.error.log</string>
</dict>
</plist>
```

### Tunnel Operations

```bash
# Start tunnel
launchctl start com.cloudflare.tunnel

# Stop tunnel
launchctl stop com.cloudflare.tunnel

# Check status
cloudflared tunnel info

# View tunnel logs
tail -f ~/clat_preparation/logs/cloudflared.log
```

---

## 7. Database Operations

### Database Locations

| Database | Path | Purpose |
|----------|------|---------|
| revision_tracker.db | ~/clat_preparation/ | GK, Diary, Mocks |
| math_tracker.db | ~/clat_preparation/ | Math module |
| assessment_tracker.db | ~/clat_preparation/ | Assessments |
| finance_tracker.db | ~/clat_preparation/ | Finance |
| health_tracker.db | ~/clat_preparation/ | Health |
| calendar_tracker.db | ~/clat_preparation/ | Calendar |

### Common Queries

```bash
# List all tables in a database
sqlite3 ~/clat_preparation/revision_tracker.db ".tables"

# View table schema
sqlite3 ~/clat_preparation/revision_tracker.db ".schema pdfs"

# Count rows
sqlite3 ~/clat_preparation/revision_tracker.db "SELECT COUNT(*) FROM pdfs;"

# View recent entries
sqlite3 ~/clat_preparation/revision_tracker.db "SELECT * FROM pdfs ORDER BY date_added DESC LIMIT 5;"
```

### Database Migrations

Migrations are stored in `migrations/` folder:
```bash
# Run a migration
sqlite3 ~/clat_preparation/revision_tracker.db < migrations/add_diary_tables.sql
```

### Database Independence

**Important:** Databases are NOT synced between machines.
- Each machine maintains independent data
- Mac Mini has production user data
- MacBook Pro has test data

---

## 8. Monitoring & Logging

### Log Files

| Log | Path | Purpose |
|-----|------|---------|
| Server | logs/server.log | Main server output |
| Server Errors | logs/server.error.log | Python exceptions |
| Cloudflared | logs/cloudflared.log | Tunnel status |

### Viewing Logs

```bash
# Live server logs
tail -f ~/clat_preparation/logs/server.log

# Last 100 lines
tail -100 ~/clat_preparation/logs/server.log

# Search for errors
grep -i error ~/clat_preparation/logs/server.log

# Search for specific date
grep "2025-12-23" ~/clat_preparation/logs/server.log
```

### Health Check Script

Create `scripts/health_check.sh`:
```bash
#!/bin/bash

echo "=== SpeedMathsGames Health Check ==="
echo "Time: $(date)"

# Check server process
if lsof -ti:8001 > /dev/null; then
    echo "✅ Server process: Running"
else
    echo "❌ Server process: NOT RUNNING"
fi

# Check server response
if curl -s http://localhost:8001/api/test | grep -q "ok"; then
    echo "✅ Server API: Responding"
else
    echo "❌ Server API: NOT RESPONDING"
fi

# Check public URL
if curl -s https://speedmathsgames.com/api/test | grep -q "ok"; then
    echo "✅ Public URL: Accessible"
else
    echo "❌ Public URL: NOT ACCESSIBLE"
fi

# Check tunnel
if pgrep cloudflared > /dev/null; then
    echo "✅ Cloudflare Tunnel: Running"
else
    echo "❌ Cloudflare Tunnel: NOT RUNNING"
fi

# Check databases
for db in revision_tracker.db math_tracker.db assessment_tracker.db finance_tracker.db health_tracker.db; do
    if [ -f ~/clat_preparation/$db ]; then
        echo "✅ Database $db: Exists"
    else
        echo "❌ Database $db: MISSING"
    fi
done

echo "=== Health Check Complete ==="
```

---

## 9. Backup & Recovery

### Backup Script

Create `scripts/backup_databases.sh`:
```bash
#!/bin/bash

BACKUP_DIR=~/clat_preparation/backups
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR/$DATE

# Backup all databases
for db in revision_tracker.db math_tracker.db assessment_tracker.db finance_tracker.db health_tracker.db calendar_tracker.db; do
    if [ -f ~/clat_preparation/$db ]; then
        cp ~/clat_preparation/$db $BACKUP_DIR/$DATE/
        echo "Backed up: $db"
    fi
done

# Keep only last 7 days of backups
find $BACKUP_DIR -type d -mtime +7 -exec rm -rf {} \;

echo "Backup complete: $BACKUP_DIR/$DATE"
```

### Cron Job for Daily Backups

```bash
# Edit crontab
crontab -e

# Add daily backup at 2 AM
0 2 * * * /Users/arvindkumar/clat_preparation/scripts/backup_databases.sh
```

### Restoring from Backup

```bash
# Stop server
launchctl stop com.clatprep.server

# Restore database
cp ~/clat_preparation/backups/20251223_020000/revision_tracker.db ~/clat_preparation/

# Restart server
launchctl start com.clatprep.server
```

### Git-based Code Recovery

```bash
# View recent commits
git log --oneline -10

# Rollback to previous commit
git reset --hard <commit-hash>

# Restart server
launchctl stop com.clatprep.server && launchctl start com.clatprep.server
```

---

## 10. Troubleshooting

### Server Won't Start

```bash
# Check if port is in use
lsof -ti:8001

# Kill existing process
lsof -ti:8001 | xargs kill -9

# Check Python syntax
python3 -m py_compile server/unified_server.py

# Check imports
python3 -c "import server.unified_server"

# Run with verbose output
python3 server/unified_server.py 2>&1 | head -50
```

### Can't Access Public URL

```bash
# 1. Check server is running
curl http://localhost:8001/api/test

# 2. Check tunnel is running
pgrep cloudflared

# 3. Restart tunnel
launchctl stop com.cloudflare.tunnel
launchctl start com.cloudflare.tunnel

# 4. Check Cloudflare status
cloudflared tunnel info
```

### Authentication Not Working

```bash
# 1. Check .env file exists
cat ~/clat_preparation/.env

# 2. Verify OAuth credentials
# - Check Google Cloud Console for correct Client ID/Secret
# - Verify redirect URI matches environment

# 3. Clear browser cookies and try again
```

### PDFs Not Showing

```bash
# 1. Check PDF folder exists
ls ~/saanvi/Legaledgedailygk/

# 2. Check PDF scanner can read
python3 -c "from server.pdf_scanner import PDFScanner; s = PDFScanner(); print(s.scan_all_folders())"

# 3. Check database
sqlite3 ~/clat_preparation/revision_tracker.db "SELECT COUNT(*) FROM pdfs;"
```

### Database Errors

```bash
# Check database integrity
sqlite3 ~/clat_preparation/revision_tracker.db "PRAGMA integrity_check;"

# Recover from corruption
sqlite3 ~/clat_preparation/revision_tracker.db ".recover" | sqlite3 ~/clat_preparation/revision_tracker_recovered.db
```

---

## 11. Security

### Environment Variables

Never commit `.env` to Git. Contains:
- `ANTHROPIC_API_KEY` - AI API key
- `GOOGLE_CLIENT_ID` - OAuth client ID
- `GOOGLE_CLIENT_SECRET` - OAuth secret

### File Permissions

```bash
# Databases should be user-only
chmod 600 ~/clat_preparation/*.db

# .env should be user-only
chmod 600 ~/clat_preparation/.env

# Scripts should be executable but not world-writable
chmod 755 ~/clat_preparation/scripts/*.sh
```

### Network Security

- Cloudflare provides SSL/TLS termination
- Cloudflare provides DDoS protection
- Server only listens on localhost
- No direct port exposure to internet

### Authentication

- Google OAuth 2.0 for user authentication
- HttpOnly cookies for session tokens
- Role-based access control for sensitive features
- Only whitelisted email addresses can access

### Sensitive Data

| Data | Protection |
|------|------------|
| User sessions | HttpOnly cookies, server-side storage |
| Finance data | Parent-only access, SQLite file permissions |
| Health data | Parent-only access, SQLite file permissions |
| API keys | .env file, not in Git |

---

## Quick Reference

### Common Commands

```bash
# Start server
launchctl start com.clatprep.server

# Stop server
launchctl stop com.clatprep.server

# Restart server
launchctl stop com.clatprep.server && launchctl start com.clatprep.server

# View logs
tail -f ~/clat_preparation/logs/server.log

# Deploy from MacBook Pro
git push origin main && ssh mac-mini "cd ~/clat_preparation && git pull && launchctl stop com.clatprep.server && launchctl start com.clatprep.server"

# Sync PDFs
rsync -avz ~/saanvi/ mac-mini:~/saanvi/

# Health check
curl https://speedmathsgames.com/api/test

# Backup databases
./scripts/backup_databases.sh
```

### SSH Config

Add to `~/.ssh/config`:
```
Host mac-mini
    HostName <mac-mini-local-ip>
    User arvindkumar
    IdentityFile ~/.ssh/id_rsa
```

---

*For architecture details, see [ARCHITECTURE.md](./ARCHITECTURE.md)*
*For API documentation, see [API_REFERENCE.md](./API_REFERENCE.md)*
