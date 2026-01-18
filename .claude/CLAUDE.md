# CLAT Preparation Project - Claude Instructions

## Server Configuration

**IMPORTANT: Mac Mini Server Port is 8765**

The unified server runs on port **8765** (not 8001) to avoid conflicts with other work on the Mac Mini.

- Server URL: `http://localhost:8765` or `http://mac-mini.local:8765`
- SSH host alias: `mac-mini` (configured in ~/.ssh/config)
- Start command: `python3 unified_server.py --port 8765`

When deploying or restarting:
```bash
ssh mac-mini "pkill -9 -f unified_server; sleep 2; cd ~/clat_preparation/server && nohup python3 unified_server.py --port 8765 > ~/clat_preparation/logs/server.log 2>&1 &"
```

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
- `logs/` - Server logs (on Mac Mini)
