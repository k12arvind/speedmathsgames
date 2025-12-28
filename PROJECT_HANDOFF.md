# CLAT GK Preparation System - Project Handoff Document

**Last Updated:** December 27, 2025
**Version:** 3.0
**Status:** Production (Active on speedmathsgames.com)

---

## Table of Contents
1. [System Overview](#system-overview)
2. [Architecture](#architecture)
3. [Deployment Setup](#deployment-setup)
4. [Key Features](#key-features)
5. [File Structure](#file-structure)
6. [Workflows](#workflows)
7. [Database Schema](#database-schema)
8. [API Endpoints](#api-endpoints)
9. [Troubleshooting](#troubleshooting)
10. [Recent Changes](#recent-changes)

---

## System Overview

### Purpose
Automated system for CLAT (Common Law Admission Test) exam preparation that:
- Processes daily and weekly current affairs PDFs
- Generates Anki flashcards using Claude AI
- Provides web-based dashboard for PDF management
- Tracks progress and assessments
- Handles large PDFs through intelligent chunking

### Tech Stack
- **Backend:** Python 3.9, Flask
- **AI:** Anthropic Claude API (Sonnet 4.5)
- **Database:** SQLite
- **Frontend:** HTML/CSS/JavaScript, Bootstrap 5
- **PDF Processing:** PyMuPDF (fitz), ReportLab
- **Flashcards:** Anki with AnkiConnect

### Deployment
- **Production:** Mac Mini (speedmathsgames.com)
- **Development:** MacBook Pro (localhost:8001)
- **Sync Method:** Git repository + manual sync scripts

---

## Architecture

### Two-Machine Setup

```
┌─────────────────┐                    ┌─────────────────┐
│  MacBook Pro    │                    │   Mac Mini      │
│  (Development)  │ ─── Git Repo ────> │  (Production)   │
│  localhost:8001 │                    │  Public URL     │
└─────────────────┘                    └─────────────────┘
```

### Directory Structure (Both Machines)

```
~/saanvi/                          # PDF storage location
├── Legaledgedailygk/             # Daily current affairs (LegalEdge source)
├── LegalEdgeweeklyGK/            # Weekly PDFs (LegalEdge source)
└── weeklyGKCareerLauncher/       # Weekly PDFs (Career Launcher source)

~/clat_preparation/                # Main project directory
├── server/                        # Backend Python code
│   ├── unified_server.py         # Main Flask server (port 8001)
│   ├── pdf_chunker.py            # PDF splitting logic
│   ├── assessment_processor.py   # Background flashcard generation
│   ├── assessment_jobs_db.py     # Job tracking database
│   └── pdf_scanner.py            # PDF folder scanner
├── dashboard/                     # Frontend HTML/JS
│   ├── comprehensive_dashboard.html   # Main dashboard
│   ├── pdf-viewer.html           # PDF viewer with annotation
│   ├── assessment-progress.html  # Real-time progress tracker
│   └── pdf-chunker.html          # PDF chunking interface
├── toprankers/                    # TopRankers automation scripts
│   ├── automate_html.sh          # Main automation script
│   ├── extract_html.py           # HTML content extraction
│   ├── generate_clean_pdf_final.py  # PDF generation
│   ├── generate_flashcards_from_html.py  # Flashcard generation
│   ├── import_to_anki.py         # Anki import
│   ├── venv -> ../venv_clat      # Symlink to shared venv
│   └── inbox/                    # Temporary JSON files
├── venv_clat/                    # Shared Python virtual environment
├── revision_tracker.db           # Main database
├── assessment_tracker.db         # Assessment tracking
└── migrations/                    # Database migrations
```

---

## Deployment Setup

### MacBook Pro (Development)

**Paths:**
- User: `arvind`
- Home: `/Users/arvind`
- PDFs: `~/saanvi/*`
- Project: `~/clat_preparation`

**Server:**
```bash
cd ~/clat_preparation
source venv_clat/bin/activate
python3 server/unified_server.py
# Access: http://localhost:8001
```

### Mac Mini (Production)

**Paths:**
- User: `arvindkumar`
- Home: `/Users/arvindkumar`
- PDFs: `~/saanvi/*`
- Project: `~/clat_preparation`

**Server:**
```bash
cd ~/clat_preparation
source venv_clat/bin/activate
nohup python3 server/unified_server.py > /tmp/server.log 2>&1 &
# Access: http://speedmathsgames.com
```

**Start Script:** `/Users/arvindkumar/clat_preparation/start_server.sh`

### Cross-Machine Path Handling

The system automatically handles path differences:

```python
# server/unified_server.py
def correct_pdf_path(self, db_path: str) -> str:
    """
    MacBook Pro: /Users/arvind/saanvi/...
    Mac Mini:    /Users/arvindkumar/saanvi/...
    """
    current_user = os.path.expanduser('~').split('/')[-1]
    corrected = db_path.replace('/Users/arvind/', f'/Users/{current_user}/')
    return corrected
```

---

## Key Features

### 1. PDF Management Dashboard

**File:** `dashboard/comprehensive_dashboard.html`

**Features:**
- Lists all PDFs from 3 sources (LegalEdge Daily, LegalEdge Weekly, Career Launcher)
- Shows file size, page count, modification dates
- Indicates which PDFs need chunking (>20 pages)
- Displays assessment status and card counts
- "Create Assessment" button for generating flashcards

**Access:**
- Development: http://localhost:8001/comprehensive_dashboard.html
- Production: http://speedmathsgames.com/comprehensive_dashboard.html

### 2. PDF Chunking System

**Purpose:** Split large PDFs (>20 pages) into smaller chunks for better AI processing

**File:** `server/pdf_chunker.py`

**Logic:**
```python
# Chunking rules (from pdf_chunker.py:41-52)
if total_pages <= 20:
    return None  # No chunking needed

# Target: 8-10 pages per chunk
chunk_size = 10
chunks = []
for i in range(0, total_pages, chunk_size):
    chunks.append({
        'start_page': i,
        'end_page': min(i + chunk_size, total_pages),
        'page_count': min(chunk_size, total_pages - i)
    })
```

**Database Tracking:**
```sql
CREATE TABLE pdf_chunks (
    id INTEGER PRIMARY KEY,
    parent_pdf_id TEXT NOT NULL,
    chunk_number INTEGER NOT NULL,
    output_filename TEXT NOT NULL,
    start_page INTEGER NOT NULL,
    end_page INTEGER NOT NULL,
    page_count INTEGER NOT NULL,
    file_size_kb REAL,
    created_at TEXT NOT NULL,
    status TEXT DEFAULT 'created'  -- created/processed/failed
);
```

**Naming Convention:**
```
Original: 5070_Manthan2.0DECEMBER-2025_WEEK-1[Topic1-9]_V04122025.pdf (29 pages)
Chunks:   5070_Manthan2.0DECEMBER-2025_WEEK-1[Topic1-9]_V04122025_part1.pdf (10 pages)
          5070_Manthan2.0DECEMBER-2025_WEEK-1[Topic1-9]_V04122025_part2.pdf (10 pages)
          5070_Manthan2.0DECEMBER-2025_WEEK-1[Topic1-9]_V04122025_part3.pdf (9 pages)
```

### 3. Assessment Creation System

**Purpose:** Generate Anki flashcards from PDFs using Claude AI

**Architecture:**

```
User clicks "Create Assessment"
    ↓
POST /api/create-assessment
    ↓
Creates job_id (UUID)
    ↓
Launches background process (assessment_processor.py)
    ↓
Frontend polls /api/assessment-progress/{job_id} every 2 seconds
    ↓
Shows real-time progress with:
    - Current chunk/batch being processed
    - Topics being converted
    - Card counts
    - Progress percentage
```

**Topic-Level Batching:**

Instead of processing entire PDF at once (60-90 second silent stall), the system processes 2-3 topics at a time:

```python
# generate_flashcards_streaming.py
BATCH_SIZE = 3  # Process 3 topics at a time

for batch in topic_batches:
    # Each batch takes 10-15 seconds
    # User sees progress update every 10-15 seconds
    flashcards = generate_flashcards_for_topics(batch)
    import_to_anki(flashcards)
    update_progress()
```

**Progress Tracking:**

```sql
CREATE TABLE assessment_jobs (
    job_id TEXT PRIMARY KEY,
    parent_pdf_id TEXT NOT NULL,
    status TEXT NOT NULL,        -- queued/processing/completed/failed
    current_chunk INTEGER,
    total_chunks INTEGER,
    current_batch INTEGER,
    total_batches INTEGER,
    status_message TEXT,
    total_cards INTEGER DEFAULT 0,
    progress_percentage INTEGER DEFAULT 0,
    created_at TEXT,
    updated_at TEXT
);
```

**Duplicate Detection:**

The system prevents duplicate flashcards when PDFs have overlapping content:

```python
# Uses SHA256 hash of normalized topic content
CREATE TABLE processed_topics (
    id INTEGER PRIMARY KEY,
    parent_pdf_id TEXT NOT NULL,
    chunk_id INTEGER NOT NULL,
    topic_title TEXT NOT NULL,
    topic_hash TEXT NOT NULL,  -- SHA256 of normalized content
    processed_at TEXT NOT NULL,
    card_count INTEGER DEFAULT 0,
    UNIQUE(parent_pdf_id, topic_hash)
);
```

### 4. TopRankers Daily Automation

**Skill:** `toprankers-daily-automation`

**Purpose:** Automatically process TopRankers daily current affairs URLs

**Usage:**
```
User provides: https://www.toprankers.com/current-affairs-23rd-december-2025

System automatically:
1. Generates clean PDF → ~/saanvi/Legaledgedailygk/current_affairs_2025_december_23.pdf
2. Generates Anki flashcards → Imports to CLAT GK decks
```

**Commands:**
```bash
# PDF generation only
cd ~/clat_preparation/toprankers
source ~/.zshrc  # Load API key
python generate_clean_pdf_final.py <URL>

# Full automation (PDF + Anki)
./automate_html.sh <URL>
```

**Output:**
- PDF: 20-25KB, categorized by topics
- Anki Cards: 30-80 cards with tags (source:toprankers, week:YYYY_MMM_DD)

---

## Workflows

### Workflow 1: Processing a New Daily PDF

1. **User receives TopRankers URL** (e.g., current-affairs-27th-december-2025)

2. **Generate PDF + Anki Cards:**
   ```bash
   cd ~/clat_preparation/toprankers
   source ~/.zshrc  # Load API key
   ./automate_html.sh https://www.toprankers.com/current-affairs-27th-december-2025
   ```

3. **System Actions:**
   - Extracts content from TopRankers
   - Generates PDF with inferred categories → Saves to `~/saanvi/Legaledgedailygk/`
   - Sends to Claude API for flashcard generation
   - Validates cards (checks for 4 options, correct answer, etc.)
   - Imports to Anki via AnkiConnect
   - Tags cards with source and week

4. **Result:**
   - PDF appears in dashboard automatically (pdf_scanner.py detects it)
   - Flashcards available in Anki immediately
   - 60-70 cards typically generated

### Workflow 2: Processing a Large Weekly PDF

1. **User uploads PDF** to `~/saanvi/weeklyGKCareerLauncher/`

2. **Dashboard detects PDF** (pdf_scanner.py auto-scans on page load)

3. **User clicks "Chunk PDF"** (if >20 pages)
   - Opens chunking interface
   - Shows chunk preview with page ranges
   - Creates chunks (saves to same folder with _part1, _part2, etc.)

4. **User clicks "Create Assessment"** on each chunk
   - Opens progress tracker page
   - Background process starts
   - Progress updates every 10-15 seconds:
     ```
     Chunk 1: Batch 1/5 - Processing topics: "Haryana Declares Hansi...", "Advanced Dynamic Pos..."
     Chunk 1: Batch 2/5 - Processing topics: "Firefighting Capabilit...", "Cutting-Edge Pollutio..."
     ...
     ```

5. **System completes**:
   - Shows total card count
   - Button changes to "✅ Assessments (147 cards)"
   - Cards available in Anki

### Workflow 3: Syncing MacBook Pro → Mac Mini

**IMPORTANT:** All Mac Mini code comes from Git only (per user requirement)

1. **On MacBook Pro:**
   ```bash
   cd ~/clat_preparation
   git add .
   git commit -m "Description of changes"
   git push origin main
   ```

2. **On Mac Mini:**
   ```bash
   cd ~/clat_preparation
   git pull origin main
   # Restart server
   lsof -ti:8001 | xargs kill -9
   ./start_server.sh
   ```

3. **Verify:**
   ```bash
   curl http://speedmathsgames.com/api/dashboard
   ```

---

## Database Schema

### Main Database: `revision_tracker.db`

**Location:** `~/clat_preparation/revision_tracker.db`

**Tables:**

#### 1. pdfs
```sql
CREATE TABLE pdfs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT UNIQUE NOT NULL,
    filepath TEXT NOT NULL,
    source_type TEXT NOT NULL,      -- 'daily' or 'weekly'
    source_name TEXT NOT NULL,      -- 'legaledge' or 'career_launcher'
    date_published TEXT,
    date_added TEXT NOT NULL,
    total_topics INTEGER DEFAULT 0,
    last_modified TEXT,
    file_edit_count INTEGER DEFAULT 0,  -- Tracks manual PDF edits
    updated_at TEXT
);
```

#### 2. pdf_chunks
```sql
CREATE TABLE pdf_chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_pdf_id TEXT NOT NULL,
    chunk_number INTEGER NOT NULL,
    output_filename TEXT NOT NULL,
    start_page INTEGER NOT NULL,
    end_page INTEGER NOT NULL,
    page_count INTEGER NOT NULL,
    file_size_kb REAL,
    created_at TEXT NOT NULL,
    status TEXT DEFAULT 'created',
    FOREIGN KEY (parent_pdf_id) REFERENCES pdfs(filename)
);
```

#### 3. topics
```sql
CREATE TABLE topics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_date TEXT NOT NULL,
    title TEXT NOT NULL,
    content TEXT,
    category TEXT,
    created_at TEXT
);
```

### Assessment Database: `assessment_tracker.db`

**Location:** `~/clat_preparation/server/assessment_tracker.db`

#### 1. assessment_jobs
```sql
CREATE TABLE assessment_jobs (
    job_id TEXT PRIMARY KEY,
    parent_pdf_id TEXT NOT NULL,
    status TEXT NOT NULL,        -- queued/processing/completed/failed
    current_chunk INTEGER DEFAULT 0,
    total_chunks INTEGER NOT NULL,
    current_batch INTEGER DEFAULT 0,
    total_batches INTEGER DEFAULT 0,
    status_message TEXT,
    total_cards INTEGER DEFAULT 0,
    progress_percentage INTEGER DEFAULT 0,
    error_message TEXT,
    created_at TEXT,
    updated_at TEXT
);
```

#### 2. processed_topics
```sql
CREATE TABLE processed_topics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_pdf_id TEXT NOT NULL,
    chunk_id INTEGER NOT NULL,
    topic_title TEXT NOT NULL,
    topic_hash TEXT NOT NULL,     -- SHA256 hash for deduplication
    processed_at TEXT NOT NULL,
    card_count INTEGER DEFAULT 0,
    UNIQUE(parent_pdf_id, topic_hash)
);
```

#### 3. test_sessions
```sql
CREATE TABLE test_sessions (
    session_id TEXT PRIMARY KEY,
    source_date TEXT NOT NULL,
    pdf_id TEXT,
    total_questions INTEGER,
    score REAL,
    percentage REAL,
    started_at TEXT,
    completed_at TEXT
);
```

---

## API Endpoints

### Server: `server/unified_server.py` (Port 8001)

#### Dashboard APIs

**GET /api/dashboard**
- Returns all PDFs from 3 folders
- Includes metadata: page count, file size, assessment status
- Auto-detects which PDFs need chunking

**GET /api/chunks/all**
- Returns all PDF chunks with parent PDF info
- Used to populate chunked PDFs section

**GET /api/chunks/{parent_pdf_id}**
- Returns chunks for a specific PDF
- Used when creating assessments for chunked PDFs

#### PDF Chunking APIs

**POST /api/chunk-pdf**
```json
Request:
{
  "pdf_path": "/path/to/pdf.pdf",
  "chunk_size": 10
}

Response:
{
  "status": "success",
  "parent_pdf": "original.pdf",
  "chunks": [
    {
      "chunk_number": 1,
      "filename": "original_part1.pdf",
      "start_page": 0,
      "end_page": 10,
      "page_count": 10,
      "file_size_kb": 1234.56
    },
    ...
  ]
}
```

#### Assessment APIs

**POST /api/create-assessment**
```json
Request:
{
  "pdf_id": "current_affairs_2025_december_23.pdf",
  "source": "legaledge",
  "week": "2025_Dec_D23"
}

Response:
{
  "job_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "queued",
  "message": "Assessment job created"
}
```

**GET /api/assessment-progress/{job_id}**
```json
Response:
{
  "job_id": "...",
  "status": "processing",       -- queued/processing/completed/failed
  "current_chunk": 2,
  "total_chunks": 3,
  "current_batch": 4,
  "total_batches": 8,
  "status_message": "Chunk 2: Batch 4/8 - Processing 3 topics",
  "total_cards": 67,
  "progress_percentage": 65
}
```

**GET /api/assessment-status/{pdf_id}**
```json
Response:
{
  "has_assessments": true,
  "all_complete": true,
  "completed_chunks": 3,
  "total_chunks": 3,
  "total_cards": 147
}
```

#### PDF Serving

**GET /pdf/{filename}**
- Serves PDF files with correct path handling
- Automatically corrects paths for MacBook Pro vs Mac Mini

---

## Troubleshooting

### Server Not Starting

**Symptom:** Server won't start on port 8001

**Solution:**
```bash
# Kill existing process
lsof -ti:8001 | xargs kill -9

# Restart server
cd ~/clat_preparation
source venv_clat/bin/activate
python3 server/unified_server.py
```

**Check logs:**
```bash
tail -f /tmp/server.log  # Mac Mini
# or check terminal output (MacBook Pro)
```

### AnkiConnect Not Working

**Symptom:** "Cannot connect to Anki" errors

**Requirements:**
1. Anki desktop app must be running
2. AnkiConnect add-on must be installed
3. No dialog boxes open in Anki

**Test connection:**
```bash
curl -X POST http://localhost:8765 -H "Content-Type: application/json" -d '{"action":"version","version":6}'
# Should return: {"result":6,"error":null}
```

### Anthropic API Issues

**Symptom:** "API key not set" or "Invalid API key"

**Check API key:**
```bash
# Should be in ~/.zshrc
grep ANTHROPIC_API_KEY ~/.zshrc

# If missing, add:
echo 'export ANTHROPIC_API_KEY="sk-ant-..."' >> ~/.zshrc
source ~/.zshrc
```

**Verify:**
```bash
if [ -n "$ANTHROPIC_API_KEY" ]; then
  echo "✅ API key is set"
else
  echo "❌ API key not set"
fi
```

### PDF Chunking Failures

**Symptom:** Chunking creates empty or corrupted PDFs

**Debug:**
```bash
cd ~/clat_preparation
source venv_clat/bin/activate
python3 -c "
import fitz
doc = fitz.open('/path/to/problem.pdf')
print(f'Pages: {len(doc)}')
print(f'Encrypted: {doc.is_encrypted}')
"
```

**Common issues:**
- PDF is encrypted → Can't chunk
- PDF is image-based → Will chunk but won't extract text
- File permissions → Check with `ls -l`

### Assessment Creation Stuck

**Symptom:** Progress page shows "Processing..." but never completes

**Check job status:**
```bash
sqlite3 ~/clat_preparation/server/assessment_tracker.db \
  "SELECT * FROM assessment_jobs WHERE status='processing';"
```

**Check background process:**
```bash
ps aux | grep assessment_processor
# Should see a Python process running
```

**Force job completion:**
```bash
sqlite3 ~/clat_preparation/server/assessment_tracker.db \
  "UPDATE assessment_jobs SET status='failed', error_message='Manual intervention' WHERE job_id='...'"
```

### Mac Mini Server Not Accessible

**Symptom:** speedmathsgames.com not responding

**Check server status:**
```bash
ssh mac-mini "curl -s http://localhost:8001/api/test"
```

**Check if server is running:**
```bash
ssh mac-mini "lsof -ti:8001"
# Should return a process ID
```

**Restart server:**
```bash
ssh mac-mini "cd ~/clat_preparation && ./start_server.sh"
```

---

## Recent Changes

### December 27, 2025 - Project Consolidation

**What changed:**
- **Consolidated all code into `/Users/arvind/clat_preparation/`**
- Moved TopRankers automation from `~/Desktop/anki_automation/` to `~/clat_preparation/toprankers/`
- Created shared virtual environment (`venv_clat`) for all scripts
- Simplified project structure for easier team handoff

**Benefits:**
- Single project folder instead of multiple scattered folders
- Shared virtual environment (no duplicate dependencies)
- Clearer organization for new team members
- All code in one Git repository

**Migration Details:**
- Created `toprankers/` subdirectory in clat_preparation
- Copied essential scripts: automate_html.sh, extract_html.py, generate_clean_pdf_final.py, etc.
- Created symlink from `toprankers/venv` to `../venv_clat`
- Updated all documentation references
- Old location (`~/Desktop/anki_automation/`) now deprecated

### December 27, 2025 - PDF Spacing Feature Removed

**What happened:**
- Attempted to add PDF spacing feature to increase line spacing for iPad annotation
- Feature created PDFs with `_s.pdf` suffix
- **Issue:** Lost all formatting (colors, fonts, headers) during spacing process
- **Decision:** Reverted all changes, feature abandoned

**Files cleaned:**
- Deleted: `server/pdf_spacing_processor.py`
- Deleted: All `*_s.pdf` files from both MacBook Pro and Mac Mini
- Original PDFs remain unchanged and intact

**Current state:** System back to normal, using original PDFs only

### December 26, 2025 - Assessment Progress System

**Added:**
- Real-time progress tracking for flashcard generation
- Topic-level batching (process 2-3 topics at a time)
- Progress updates every 10-15 seconds (no more 60-90 second silent stalls)
- Duplicate detection using SHA256 hashing

**Files modified:**
- `server/assessment_processor.py` - Background processor
- `server/assessment_jobs_db.py` - Job tracking database
- `dashboard/assessment-progress.html` - Real-time progress UI

**Benefit:** User sees continuous feedback during 5-15 minute assessment creation process

### December 24, 2025 - TopRankers Automation

**Added:**
- `toprankers-daily-automation` skill
- Automatic PDF + Anki generation from single URL
- Clean PDF with inferred categories

**Usage:** Just paste TopRankers URL, system handles both PDF and flashcards

---

## Dependencies

### Python Packages (venv_clat)

```bash
flask==3.0.0
PyMuPDF==1.23.8      # fitz for PDF processing
anthropic==0.18.1    # Claude API
requests==2.31.0
```

### Python Packages (venv_clat - Shared Environment)

```bash
anthropic==0.18.1
requests==2.31.0
reportlab==4.0.7     # PDF generation
beautifulsoup4==4.12.2
```

### System Requirements

- Python 3.9+
- Anki Desktop App
- AnkiConnect Add-on (2055492159)

---

## Configuration Files

### Environment Variables (~/.zshrc)

```bash
# Required
export ANTHROPIC_API_KEY="sk-ant-api03-..."

# Optional
export CLAT_PREP_HOME="/Users/arvind/clat_preparation"
export ANKI_CONNECT_URL="http://localhost:8765"
```

### Git Configuration

**Repository:** Private Git repo (exact URL not in this document)

**Branches:**
- `main` - Production code (deployed on Mac Mini)
- No feature branches (direct commits to main)

**Workflow:**
1. Develop on MacBook Pro
2. Test locally
3. Commit and push to main
4. Pull on Mac Mini
5. Restart server

---

## Security Notes

### API Keys

- Anthropic API key stored in `~/.zshrc`
- Never commit `.env` files or credentials to Git
- API key usage: ~$0.05-$0.08 per daily PDF (30 PDFs = ~$1.50-$2.40/month)

### File Permissions

```bash
# Server should not be world-writable
chmod 755 ~/clat_preparation/server/*.py

# Databases should be user-only
chmod 600 ~/clat_preparation/*.db

# PDF folders should be readable
chmod 755 ~/saanvi/*
```

### AnkiConnect Security

AnkiConnect listens on localhost:8765 by default (not exposed to internet)

---

## Performance Metrics

### Typical Processing Times

- **Daily PDF (TopRankers):**
  - PDF generation: 3-5 seconds
  - Anki generation: 60-90 seconds
  - Total: ~2 minutes

- **Weekly PDF (Chunked):**
  - Chunking: 5-10 seconds
  - Assessment per chunk: 5-15 minutes
  - Total (3 chunks): 15-45 minutes

- **Dashboard load:**
  - Initial scan: 2-3 seconds (28-31 PDFs)
  - Subsequent loads: <1 second (cached in browser)

### File Sizes

- Daily PDFs: 18-72KB
- Weekly PDFs (original): 6-10MB
- Weekly PDFs (chunked): 500KB-2MB per chunk
- Spaced PDFs (abandoned): 35MB+ (not used)

---

## Common Commands Reference

### Start/Stop Server

```bash
# MacBook Pro (development)
cd ~/clat_preparation
source venv_clat/bin/activate
python3 server/unified_server.py

# Mac Mini (production)
cd ~/clat_preparation
./start_server.sh

# Stop server (both)
lsof -ti:8001 | xargs kill -9
```

### Process TopRankers URL

```bash
cd ~/clat_preparation/toprankers
source ~/.zshrc  # Load API key
./automate_html.sh <URL>
```

### Chunk a PDF

```bash
cd ~/clat_preparation
source venv_clat/bin/activate
python3 << EOF
from server.pdf_chunker import PDFChunker
chunker = PDFChunker()
result = chunker.chunk_pdf('/path/to/large.pdf', chunk_size=10)
print(result)
EOF
```

### Query Databases

```bash
# List all PDFs
sqlite3 ~/clat_preparation/revision_tracker.db \
  "SELECT filename, source_type, total_topics FROM pdfs;"

# List chunks
sqlite3 ~/clat_preparation/revision_tracker.db \
  "SELECT parent_pdf_id, chunk_number, page_count FROM pdf_chunks;"

# Check assessment jobs
sqlite3 ~/clat_preparation/server/assessment_tracker.db \
  "SELECT job_id, status, total_cards, progress_percentage FROM assessment_jobs;"
```

### Sync to Mac Mini

```bash
# On MacBook Pro
cd ~/clat_preparation
git add .
git commit -m "Changes description"
git push origin main

# On Mac Mini
ssh mac-mini "cd ~/clat_preparation && git pull origin main && lsof -ti:8001 | xargs kill -9 && ./start_server.sh"
```

---

## Testing Checklist

### Before Deploying to Production

- [ ] Test dashboard loads on localhost:8001
- [ ] Test PDF viewer opens and displays correctly
- [ ] Test chunking creates correct number of files
- [ ] Test "Create Assessment" generates flashcards
- [ ] Verify progress page shows real-time updates
- [ ] Check Anki imports cards successfully
- [ ] Test with both daily and weekly PDFs
- [ ] Verify no `_s.pdf` files exist anywhere
- [ ] Check database integrity (no null values in key fields)
- [ ] Run on MacBook Pro successfully before syncing

### After Deploying to Production

- [ ] Verify speedmathsgames.com loads
- [ ] Test dashboard shows all PDFs
- [ ] Test PDF viewer works via public URL
- [ ] Create test assessment and verify completion
- [ ] Check server logs for errors (`tail /tmp/server.log`)
- [ ] Verify cross-machine paths work correctly
- [ ] Test TopRankers automation end-to-end

---

## Contact & Support

### Key Personnel

- **Project Owner:** Arvind
- **End User:** Saanvi (daughter, CLAT exam prep)
- **Development:** MacBook Pro (arvind)
- **Production:** Mac Mini (arvindkumar)

### Important Notes for New Team Members

1. **CRITICAL:** Never sync code directly to Mac Mini - always use Git
2. User requirement: "All mac-mini codes should be taken only from git when confirmed"
3. Test everything on MacBook Pro first
4. Original PDFs are sacred - never modify them
5. The `_s.pdf` feature was abandoned - don't recreate it
6. AnkiConnect must be running before flashcard operations
7. Anthropic API key must be in ~/.zshrc on both machines

### Debugging First Steps

1. Check if server is running: `curl http://localhost:8001/api/test`
2. Check if Anki is running: `curl http://localhost:8765`
3. Check API key: `echo $ANTHROPIC_API_KEY`
4. Check logs: `tail -f /tmp/server.log` (Mac Mini) or terminal output (MacBook Pro)
5. Check database: `sqlite3 ~/clat_preparation/revision_tracker.db ".tables"`

---

## Future Enhancements (Not Yet Implemented)

### Planned Features

1. **Automatic Daily Sync**
   - Cron job to auto-process TopRankers daily URLs
   - Would run at 8 AM daily

2. **Progress Analytics**
   - Track which topics Saanvi struggles with
   - Suggest review schedules based on Anki performance

3. **Mobile App**
   - iOS app for iPad annotation
   - Direct sync with Anki

4. **Batch Processing**
   - Process multiple PDFs at once
   - Queue system for large batches

### Abandoned Features

1. **PDF Spacing** (December 27, 2025)
   - Attempted to add line spacing for iPad annotation
   - Lost formatting during processing
   - Decided to keep original PDFs

---

## Glossary

- **Chunk:** Split section of a large PDF (8-10 pages)
- **Assessment:** Set of Anki flashcards generated from a PDF
- **Topic:** Individual news item or subject within a PDF
- **Batch:** Group of 2-3 topics processed together
- **Job:** Background task for generating flashcards
- **Source:** Origin of PDFs (legaledge or career_launcher)
- **Type:** Daily or weekly PDF
- **AnkiConnect:** HTTP API for interacting with Anki

---

**End of Handoff Document**

*This document should be updated whenever major changes are made to the system.*
