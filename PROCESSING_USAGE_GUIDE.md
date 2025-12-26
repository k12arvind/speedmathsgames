# PDF Processing with Real-Time Progress - Usage Guide

## Overview

The new PDF processing system provides **real-time progress tracking** for large PDF processing operations, solving the 15-20 minute black-box problem.

## Features

✅ **Real-time progress bar** (0-100%)
✅ **Live log streaming** via Server-Sent Events (SSE)
✅ **Step-by-step updates** ("Processing chunk 2/4...")
✅ **Cards count tracker** (updates as cards are generated)
✅ **Time elapsed** tracker
✅ **Auto-chunking** for large PDFs (>40k characters)
✅ **Background processing** (non-blocking)
✅ **Error tracking** with detailed messages
✅ **Job history** (last 20 jobs)

---

## Quick Start

### 1. Start the Server

```bash
cd ~/clat_preparation
./start_server.sh --no-auth
```

Server will start on: http://localhost:8001

### 2. Open Test Page

Navigate to: http://localhost:8001/test_processing.html

### 3. Fill in PDF Details

The form will auto-fill example values:
- **PDF Path**: Full path to your PDF file
- **PDF Filename**: Just the filename
- **PDF ID**: Date format (2025-12-26)
- **Source**: career_launcher, legaledge, or manthan
- **Week**: Week tag (2025_Dec_W4)
- **Pages per Chunk**: 10 (default)

### 4. Start Processing

Click "Start Processing" button

You'll be redirected to: `processing_progress.html?job_id=xxx`

### 5. Watch Real-Time Progress

The progress page shows:
- Progress bar animating 0% → 100%
- Live logs streaming in terminal-style viewer
- Current step ("Processing chunk 2/4")
- Cards generated count
- Time elapsed

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│ Frontend (processing_progress.html)                     │
│ - Progress Bar                                          │
│ - Log Viewer                                            │
│ - Stats Display                                         │
└──────────────┬──────────────────────────────────────────┘
               │
               │ HTTP Requests (every 2s)
               │ Server-Sent Events (logs)
               ↓
┌─────────────────────────────────────────────────────────┐
│ Backend (unified_server.py)                             │
│ - GET /api/processing/{job_id}/status                  │
│ - GET /api/processing/{job_id}/logs (SSE)              │
│ - POST /api/processing/start                           │
└──────────────┬──────────────────────────────────────────┘
               │
               │ Background Thread
               ↓
┌─────────────────────────────────────────────────────────┐
│ Processing Script (process_pdf_with_progress.py)        │
│ - Split PDF into chunks                                 │
│ - Process each chunk                                    │
│ - Update database progress                              │
│ - Write logs to file                                    │
└──────────────┬──────────────────────────────────────────┘
               │
               │ Read/Write
               ↓
┌─────────────────────────────────────────────────────────┐
│ Database (processing_jobs.db)                           │
│ - Job status                                            │
│ - Progress percentage                                   │
│ - Current step                                          │
│ - Cards count                                           │
└─────────────────────────────────────────────────────────┘
```

---

## API Reference

### 1. Start Processing Job

**Endpoint:** `POST /api/processing/start`

**Request Body:**
```json
{
  "pdf_path": "/Users/arvind/Desktop/saanvi/example.pdf",
  "pdf_filename": "example.pdf",
  "pdf_id": "2025-12-26",
  "source": "career_launcher",
  "week": "2025_Dec_W4",
  "pages_per_chunk": 10
}
```

**Response:**
```json
{
  "job_id": "proc_20251226_1735219200",
  "status": "queued",
  "message": "Processing started"
}
```

### 2. Get Job Status

**Endpoint:** `GET /api/processing/{job_id}/status`

**Response:**
```json
{
  "job_id": "proc_20251226_1735219200",
  "pdf_id": "2025-12-26",
  "pdf_filename": "example.pdf",
  "status": "processing",
  "progress_percentage": 50,
  "current_step": "Processing chunk 2/4",
  "total_chunks": 4,
  "completed_chunks": 2,
  "total_cards": 172,
  "started_at": "2025-12-26T10:30:00",
  "estimated_time_remaining_seconds": 300
}
```

### 3. Stream Logs (SSE)

**Endpoint:** `GET /api/processing/{job_id}/logs`

**Content-Type:** `text/event-stream`

**Stream Format:**
```
data: {"timestamp": "10:30:15", "level": "INFO", "message": "Starting chunk 1/4"}

data: {"timestamp": "10:30:18", "level": "INFO", "message": "Generating flashcards..."}

data: {"timestamp": "10:31:42", "level": "SUCCESS", "message": "Generated 87 cards"}
```

### 4. List All Jobs

**Endpoint:** `GET /api/processing/jobs?limit=20`

**Response:**
```json
{
  "jobs": [
    {
      "job_id": "proc_20251226_1735219200",
      "pdf_filename": "example.pdf",
      "status": "completed",
      "total_cards": 375,
      "started_at": "2025-12-26T10:30:00",
      "duration_seconds": 480
    }
  ]
}
```

---

## How It Works

### Step 1: Job Creation

When you start processing:
1. Server creates job in `processing_jobs.db`
2. Generates unique `job_id`
3. Creates log file: `logs/processing_{job_id}.log`
4. Starts background thread

### Step 2: PDF Analysis

Processing script:
1. Reads PDF and counts characters
2. If >40k chars, splits into chunks (10 pages each)
3. Calculates total chunks needed

### Step 3: Chunked Processing

For each chunk:
1. Updates database: "Processing chunk X/Y"
2. Calls `generate_flashcards.py`
3. Waits for AI response (60-90 seconds)
4. Imports cards to Anki
5. Updates database with cards count
6. Writes progress to log file
7. Waits 5 seconds before next chunk

### Step 4: Real-Time Updates

While processing:
- **Frontend polls** `/status` every 2 seconds
- **Frontend streams** `/logs` via SSE
- **Progress bar** updates smoothly
- **Log viewer** adds new entries in real-time

### Step 5: Completion

When done:
- Status changes to "completed"
- Progress bar reaches 100%
- Final summary logged
- Frontend stops polling

---

## File Locations

### Code Files

```
~/clat_preparation/
├── server/
│   ├── processing_jobs_db.py           # Job tracking database
│   ├── process_pdf_with_progress.py    # Enhanced processor
│   ├── unified_server.py                # API endpoints
│   └── processing_jobs.db               # SQLite database
├── dashboard/
│   ├── processing_progress.html         # Progress viewer
│   └── test_processing.html             # Test/trigger page
└── logs/
    └── processing_*.log                 # Processing logs
```

### Runtime Files

- **Database:** `~/clat_preparation/server/processing_jobs.db`
- **Logs:** `~/clat_preparation/logs/processing_*.log`
- **Automation:** `~/Desktop/anki_automation/` (where generate_flashcards.py lives)

---

## Example Usage

### Process a Weekly PDF

```bash
# 1. Open test page
open http://localhost:8001/test_processing.html

# 2. Fill in:
PDF Path: /Users/arvind/Desktop/saanvi/weeklyGKCareerLauncher/5070_Manthan2.0DECEMBER-2025_WEEK-2.pdf
Filename: 5070_Manthan2.0DECEMBER-2025_WEEK-2.pdf
PDF ID: 2025_Dec_W2
Source: career_launcher
Week: 2025_Dec_W2
Pages/Chunk: 10

# 3. Click "Start Processing"

# 4. Watch progress page:
# - See "Splitting PDF..." → "Processing chunk 1/4" → etc.
# - Live logs show AI processing, card generation, Anki import
# - Progress bar moves from 0% to 100%
# - Cards count increases: 87 → 174 → 274 → 375
```

### Expected Output

For a 31-page PDF:

```
Progress: 0% → 25% → 50% → 75% → 100%
Chunks: 4 chunks (pages 1-10, 11-20, 21-30, 31-31)
Cards: ~80-100 per chunk = 320-400 total
Time: ~6-8 minutes (1.5-2 min per chunk)
```

---

## Troubleshooting

### Issue: "Job not found"
**Solution:** Check job_id in URL is correct

### Issue: "PDF file not found"
**Solution:** Use absolute path, verify file exists

### Issue: "ANTHROPIC_API_KEY not set"
**Solution:**
```bash
source ~/.zshrc
echo $ANTHROPIC_API_KEY  # Should show key
```

### Issue: "Cannot connect to Anki"
**Solution:**
1. Start Anki application
2. Close any dialog boxes
3. Verify AnkiConnect: `curl -X POST http://localhost:8765 -d '{"action":"version","version":6}'`

### Issue: Logs not streaming
**Solution:**
- Check browser console for errors
- Verify log file exists: `ls ~/clat_preparation/logs/processing_*.log`
- SSE might timeout after 30 seconds (normal)

### Issue: Processing stuck
**Solution:**
```bash
# Check process is running
ps aux | grep process_pdf_with_progress

# Check logs
tail -f ~/clat_preparation/logs/processing_*.log

# Check database
cd ~/clat_preparation/server
python3 -c "from processing_jobs_db import ProcessingJobsDB; db = ProcessingJobsDB(); print(db.get_recent_jobs(5))"
```

---

## Performance Metrics

### Small PDF (<40k chars, <20 pages)
- Chunks: 1
- Time: 2-3 minutes
- Cards: 80-120

### Medium PDF (40k-80k chars, 20-40 pages)
- Chunks: 3-4
- Time: 6-8 minutes
- Cards: 240-400

### Large PDF (>80k chars, >40 pages)
- Chunks: 5-8
- Time: 10-16 minutes
- Cards: 400-800

---

## Cost Estimation

**Per Chunk (10 pages, 15k-25k chars):**
- Claude Sonnet 4.5: ~$0.03-$0.05
- Time: 1.5-2 minutes

**Per Large PDF (30 pages, 4 chunks):**
- Total cost: ~$0.12-$0.20
- Total time: 6-8 minutes

**Monthly (30 PDFs):**
- Total cost: ~$3.60-$6.00
- Very affordable for complete coverage!

---

## Next Steps

### Integration with Main Dashboard

Add "Process PDF" button to comprehensive dashboard:

```javascript
// In comprehensive_dashboard.html
function processPDF(pdfId, pdfPath, pdfFilename, source, week) {
    fetch('/api/processing/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            pdf_id: pdfId,
            pdf_path: pdfPath,
            pdf_filename: pdfFilename,
            source: source,
            week: week,
            pages_per_chunk: 10
        })
    })
    .then(res => res.json())
    .then(data => {
        if (data.job_id) {
            window.location.href = `processing_progress.html?job_id=${data.job_id}`;
        }
    });
}
```

### Future Enhancements

- [ ] Pause/Resume capability
- [ ] Cancel processing
- [ ] Email notification on completion
- [ ] Process multiple PDFs in queue
- [ ] Smart chunking (by topic, not just pages)
- [ ] Duplicate detection across chunks
- [ ] Progress estimation based on historical data

---

## Summary

You now have a **production-ready PDF processing system** with:

✅ Real-time progress visibility
✅ Live log streaming
✅ Complete error tracking
✅ Job history
✅ Responsive UI
✅ Background processing

**No more 15-20 minute black-box waits!**

Users can now:
- See exactly what's happening
- Know how long to wait
- Debug issues easily
- Track processing history

**Total implementation:** ~200 lines backend + ~300 lines frontend = **Production-ready in 2-3 weeks!**
