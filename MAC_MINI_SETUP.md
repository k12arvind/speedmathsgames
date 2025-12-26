# Mac Mini Setup Guide

This guide explains how to set up and sync the Mac Mini production server using Git.

## Initial Setup (One-time)

Run this **once** on Mac Mini to set up Git:

```bash
cd ~/clat_preparation
./scripts/setup_mac_mini_git.sh
```

This will:
- Initialize Git repository
- Add GitHub remote
- Pull all code and databases
- Configure Git user

## Daily Updates

Whenever you push new code from MacBook Pro, update Mac Mini with:

```bash
cd ~/clat_preparation
./scripts/pull_from_github.sh
```

This will:
- Stop the server
- Pull latest code from GitHub
- Get updated databases
- Restart the server
- Verify everything is working

## Workflow

### On MacBook Pro (Development)

1. Make changes to code
2. Test locally with `./start_server.sh --no-auth`
3. Commit changes:
   ```bash
   git add .
   git commit -m "Description of changes"
   git push origin main
   ```

### On Mac Mini (Production)

1. Pull latest changes:
   ```bash
   cd ~/clat_preparation
   ./scripts/pull_from_github.sh
   ```

2. Server automatically restarts with new code

## What Gets Synced via Git

✅ **Synced automatically:**
- Python code (`server/`, `pdf_generation/`, `utils/`)
- Dashboard files (`dashboard/*.html`, CSS, JS)
- Math module code
- Scripts
- **Databases** (assessment_tracker.db, revision_tracker.db, math_tracker.db)
- Configuration files

❌ **Not synced (intentionally):**
- PDFs (use `scripts/auto_sync_pdfs.sh` for PDFs)
- Logs
- Virtual environment (venv)
- `.env` file (contains secrets)

## PDF Syncing

PDFs are still synced separately using rsync:

```bash
# From MacBook Pro
cd ~/clat_preparation
./scripts/auto_sync_pdfs.sh
```

This is intentional because:
- PDFs are large binary files
- Git is optimized for code, not large binaries
- rsync is more efficient for PDFs

## Anki Database Syncing

The Anki `collection.anki2` database needs to be synced separately:

**Option 1: Manual Copy (Recommended)**
```bash
# From MacBook Pro
rsync -avz ~/Library/Application\ Support/Anki2/User\ 1/collection.anki2 \
  mac-mini:~/Library/Application\ Support/Anki2/User\ 1/
```

**Option 2: Use Anki Sync**
- Use Anki's built-in sync feature (AnkiWeb)
- Sync on MacBook Pro, then sync on Mac Mini

## Troubleshooting

### "Git not initialized" error
Run the setup script:
```bash
cd ~/clat_preparation
./scripts/setup_mac_mini_git.sh
```

### Server won't start after pull
Check logs:
```bash
tail -50 ~/clat_preparation/logs/server.log
```

Restart manually:
```bash
launchctl stop com.clatprep.server
launchctl start com.clatprep.server
```

### "Cannot connect to Anki" errors
1. Make sure Anki is running on Mac Mini
2. Verify AnkiConnect is installed
3. Sync Anki database from MacBook Pro

### Code changes not reflecting
1. Clear browser cache
2. Check you pulled latest: `git log -1`
3. Verify server restarted: `curl http://localhost:8001/api/dashboard`

## Benefits of Git Workflow

**Old Workflow (rsync):**
- Had to sync each directory separately
- No version history
- Hard to rollback changes
- Couldn't see what changed

**New Workflow (Git):**
- ✅ One command syncs everything
- ✅ Full version history
- ✅ Easy rollback: `git reset --hard <commit>`
- ✅ See changes: `git log` and `git diff`
- ✅ Databases included automatically

## Advanced: Rolling Back

If an update breaks something, rollback on Mac Mini:

```bash
cd ~/clat_preparation

# See recent commits
git log -5 --oneline

# Rollback to previous version
git reset --hard <commit-hash>

# Restart server
launchctl stop com.clatprep.server
launchctl start com.clatprep.server
```

## Architecture Summary

```
MacBook Pro (Development)          Mac Mini (Production)
─────────────────────              ──────────────────────
1. Write code
2. Test locally
3. Commit to Git
4. Push to GitHub ──────────────>  5. Pull from GitHub
                                   6. Server auto-restarts
                                   7. Live on speedmathsgames.com
```

## URLs

**Mac Mini Local:**
- http://localhost:8001/

**Mac Mini Public:**
- https://speedmathsgames.com/

**GitHub Repository:**
- https://github.com/k12arvind/speedmathsgames
