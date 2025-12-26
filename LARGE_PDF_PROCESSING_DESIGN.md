# Large PDF Processing with Real-Time Progress

## Problem Statement

Processing large PDFs (>40k characters, 30+ pages) takes 15-20 minutes with:
- ❌ No real-time feedback to user
- ❌ Black-box processing - user doesn't know what's happening
- ❌ No way to know if it's stuck or progressing
- ❌ User anxiety - "Is it working? Should I wait?"

## Solution Overview

Implement a **multi-layered progress tracking system** with:
1. ✅ Real-time log streaming to dashboard
2. ✅ Chunked processing with progress percentage
3. ✅ Server-Sent Events (SSE) for live updates
4. ✅ Processing status API
5. ✅ Visual progress indicator on dashboard

---

## Architecture Design

### 1. Processing Flow with Progress Tracking

```
User uploads/selects PDF
    ↓
Server creates processing job
    ↓
    ├─ Generates unique job_id
    ├─ Creates log file: logs/processing_{job_id}.log
    ├─ Stores job in processing_jobs.db
    └─ Returns job_id to frontend
    ↓
Frontend polls /api/processing/{job_id}/status
Frontend streams /api/processing/{job_id}/logs (SSE)
    ↓
Backend processes PDF in chunks:
    ├─ Chunk 1/4 → Log progress → Import cards
    ├─ Chunk 2/4 → Log progress → Import cards
    ├─ Chunk 3/4 → Log progress → Import cards
    └─ Chunk 4/4 → Log progress → Import cards
    ↓
Job marked as completed
Frontend shows success + total cards
```

### 2. Database Schema

**New Table: processing_jobs**

```sql
CREATE TABLE processing_jobs (
    job_id TEXT PRIMARY KEY,
    pdf_id TEXT NOT NULL,
    pdf_filename TEXT NOT NULL,
    status TEXT NOT NULL,  -- 'queued', 'processing', 'completed', 'failed'
    progress_percentage INTEGER DEFAULT 0,
    current_step TEXT,
    total_chunks INTEGER,
    completed_chunks INTEGER DEFAULT 0,
    total_cards INTEGER DEFAULT 0,
    log_file TEXT,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    error_message TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

### 3. API Endpoints

#### POST /api/processing/start
Start PDF processing job

**Request:**
```json
{
  "pdf_id": "2025-12-26",
  "pdf_path": "/path/to/pdf.pdf",
  "source": "career_launcher",
  "week": "2025_Dec_W2",
  "pages_per_chunk": 10
}
```

**Response:**
```json
{
  "job_id": "proc_2025_Dec_W2_1735219200",
  "status": "queued",
  "message": "Processing started"
}
```

#### GET /api/processing/{job_id}/status
Get current job status

**Response:**
```json
{
  "job_id": "proc_2025_Dec_W2_1735219200",
  "status": "processing",
  "progress_percentage": 50,
  "current_step": "Processing chunk 2/4",
  "total_chunks": 4,
  "completed_chunks": 2,
  "total_cards": 172,
  "started_at": "2025-12-26T10:30:00",
  "estimated_time_remaining": "5 minutes"
}
```

#### GET /api/processing/{job_id}/logs (SSE)
Stream real-time logs

**Response:** (Server-Sent Events)
```
data: {"timestamp": "10:30:15", "level": "INFO", "message": "Starting chunk 1/4"}

data: {"timestamp": "10:30:16", "level": "INFO", "message": "Extracting pages 1-10"}

data: {"timestamp": "10:30:18", "level": "INFO", "message": "Sending to Claude AI..."}

data: {"timestamp": "10:31:42", "level": "INFO", "message": "Generated 87 cards"}

data: {"timestamp": "10:31:45", "level": "INFO", "message": "Importing to Anki..."}

data: {"timestamp": "10:31:50", "level": "SUCCESS", "message": "Chunk 1/4 complete: 87 cards imported"}
```

#### GET /api/processing/jobs
List all processing jobs (recent)

**Response:**
```json
{
  "jobs": [
    {
      "job_id": "proc_2025_Dec_W2_1735219200",
      "pdf_filename": "5070_Manthan2.0DECEMBER-2025_WEEK-2.pdf",
      "status": "completed",
      "total_cards": 375,
      "started_at": "2025-12-26T10:30:00",
      "duration_seconds": 480
    }
  ]
}
```

---

## Implementation Plan

### Phase 1: Backend - Progress Tracking Infrastructure

#### File 1: `processing_jobs_db.py`
```python
#!/usr/bin/env python3
"""
processing_jobs_db.py
Database for tracking PDF processing jobs
"""

import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional
import uuid

class ProcessingJobsDB:
    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            db_path = Path(__file__).parent / "processing_jobs.db"

        self.db_path = db_path
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self._init_database()

    def _init_database(self):
        cursor = self.conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS processing_jobs (
                job_id TEXT PRIMARY KEY,
                pdf_id TEXT NOT NULL,
                pdf_filename TEXT NOT NULL,
                status TEXT NOT NULL,
                progress_percentage INTEGER DEFAULT 0,
                current_step TEXT,
                total_chunks INTEGER,
                completed_chunks INTEGER DEFAULT 0,
                total_cards INTEGER DEFAULT 0,
                log_file TEXT,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                error_message TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        self.conn.commit()

    def create_job(self, pdf_id: str, pdf_filename: str, total_chunks: int) -> str:
        """Create a new processing job."""
        job_id = f"proc_{pdf_id}_{int(datetime.now().timestamp())}"
        log_file = f"logs/processing_{job_id}.log"

        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO processing_jobs
            (job_id, pdf_id, pdf_filename, status, total_chunks, log_file, started_at)
            VALUES (?, ?, ?, 'queued', ?, ?, ?)
        """, (job_id, pdf_id, pdf_filename, total_chunks, log_file, datetime.now().isoformat()))

        self.conn.commit()
        return job_id

    def update_progress(self, job_id: str, completed_chunks: int,
                       current_step: str, cards_count: int = 0):
        """Update job progress."""
        cursor = self.conn.cursor()

        # Get total chunks
        cursor.execute("SELECT total_chunks FROM processing_jobs WHERE job_id = ?", (job_id,))
        row = cursor.fetchone()
        if not row:
            return

        total_chunks = row['total_chunks']
        progress = int((completed_chunks / total_chunks) * 100)

        cursor.execute("""
            UPDATE processing_jobs
            SET completed_chunks = ?,
                progress_percentage = ?,
                current_step = ?,
                total_cards = total_cards + ?,
                status = 'processing'
            WHERE job_id = ?
        """, (completed_chunks, progress, current_step, cards_count, job_id))

        self.conn.commit()

    def mark_completed(self, job_id: str):
        """Mark job as completed."""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE processing_jobs
            SET status = 'completed',
                progress_percentage = 100,
                completed_at = ?
            WHERE job_id = ?
        """, (datetime.now().isoformat(), job_id))

        self.conn.commit()

    def mark_failed(self, job_id: str, error_message: str):
        """Mark job as failed."""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE processing_jobs
            SET status = 'failed',
                error_message = ?,
                completed_at = ?
            WHERE job_id = ?
        """, (error_message, datetime.now().isoformat(), job_id))

        self.conn.commit()

    def get_job(self, job_id: str) -> Optional[Dict]:
        """Get job status."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM processing_jobs WHERE job_id = ?", (job_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_recent_jobs(self, limit: int = 10) -> list:
        """Get recent jobs."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM processing_jobs
            ORDER BY started_at DESC
            LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]
```

#### File 2: `process_large_pdf_with_progress.py`
Enhanced version with progress logging

```python
#!/usr/bin/env python3
"""
process_large_pdf_with_progress.py
Process large PDFs with real-time progress tracking
"""

import sys
import os
import logging
from pathlib import Path
from processing_jobs_db import ProcessingJobsDB

def setup_logging(log_file: str):
    """Setup logging to file and console."""
    # Create logs directory
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)s | %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger(__name__)

def process_with_progress(pdf_path, source, week, pages_per_chunk, job_id):
    """Process PDF with progress tracking."""
    db = ProcessingJobsDB()
    job = db.get_job(job_id)

    if not job:
        raise ValueError(f"Job {job_id} not found")

    logger = setup_logging(job['log_file'])

    try:
        logger.info(f"Starting processing: {pdf_path}")
        logger.info(f"Source: {source}, Week: {week}")

        # Split PDF
        logger.info("Splitting PDF into chunks...")
        chunks = split_pdf_by_pages(Path(pdf_path), pages_per_chunk)
        logger.info(f"Created {len(chunks)} chunks")

        total_cards = 0

        for i, chunk in enumerate(chunks, 1):
            logger.info(f"")
            logger.info(f"{'='*60}")
            logger.info(f"Processing Chunk {i}/{len(chunks)}")
            logger.info(f"Pages: {chunk['pages']}")
            logger.info(f"{'='*60}")

            # Update progress
            db.update_progress(
                job_id,
                completed_chunks=i-1,
                current_step=f"Processing chunk {i}/{len(chunks)}"
            )

            # Process chunk
            logger.info(f"Generating flashcards...")
            cards_count = process_chunk(
                chunk['path'],
                source,
                week,
                chunk['num'],
                len(chunks),
                logger
            )

            logger.info(f"✓ Chunk {i}/{len(chunks)} complete: {cards_count} cards")
            total_cards += cards_count

            # Update progress with card count
            db.update_progress(
                job_id,
                completed_chunks=i,
                current_step=f"Completed chunk {i}/{len(chunks)}",
                cards_count=cards_count
            )

            # Wait between chunks
            if i < len(chunks):
                logger.info("Waiting 5 seconds before next chunk...")
                time.sleep(5)

        logger.info(f"")
        logger.info(f"{'='*60}")
        logger.info(f"✓ Processing complete!")
        logger.info(f"Total cards generated: {total_cards}")
        logger.info(f"{'='*60}")

        # Mark as completed
        db.mark_completed(job_id)

    except Exception as e:
        logger.error(f"❌ Error: {str(e)}")
        db.mark_failed(job_id, str(e))
        raise

if __name__ == '__main__':
    if len(sys.argv) < 6:
        print("Usage: python process_large_pdf_with_progress.py <pdf> <source> <week> <pages_per_chunk> <job_id>")
        sys.exit(1)

    process_with_progress(
        sys.argv[1],  # pdf_path
        sys.argv[2],  # source
        sys.argv[3],  # week
        int(sys.argv[4]),  # pages_per_chunk
        sys.argv[5]   # job_id
    )
```

### Phase 2: Frontend - Progress Dashboard

#### File 3: `processing_progress.html`
Real-time progress viewer

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>PDF Processing Progress</title>
    <style>
        .progress-container {
            max-width: 800px;
            margin: 20px auto;
            padding: 20px;
            border: 1px solid #ddd;
            border-radius: 8px;
            background: #f9f9f9;
        }

        .progress-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }

        .progress-bar-container {
            width: 100%;
            height: 30px;
            background: #e0e0e0;
            border-radius: 15px;
            overflow: hidden;
            margin-bottom: 10px;
        }

        .progress-bar {
            height: 100%;
            background: linear-gradient(90deg, #4CAF50, #8BC34A);
            transition: width 0.3s ease;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: bold;
        }

        .log-container {
            max-height: 400px;
            overflow-y: auto;
            background: #1e1e1e;
            color: #00ff00;
            padding: 15px;
            border-radius: 5px;
            font-family: 'Courier New', monospace;
            font-size: 13px;
        }

        .log-entry {
            margin: 5px 0;
            padding: 3px 0;
        }

        .log-entry.INFO { color: #00ff00; }
        .log-entry.SUCCESS { color: #00ffff; font-weight: bold; }
        .log-entry.ERROR { color: #ff0000; font-weight: bold; }
        .log-entry.WARNING { color: #ffaa00; }

        .status-badge {
            padding: 5px 15px;
            border-radius: 20px;
            font-weight: bold;
        }

        .status-badge.processing { background: #2196F3; color: white; }
        .status-badge.completed { background: #4CAF50; color: white; }
        .status-badge.failed { background: #f44336; color: white; }
    </style>
</head>
<body>
    <div class="progress-container">
        <div class="progress-header">
            <h2 id="job-title">Processing PDF...</h2>
            <span id="status-badge" class="status-badge processing">Processing</span>
        </div>

        <div class="progress-bar-container">
            <div id="progress-bar" class="progress-bar" style="width: 0%">
                <span id="progress-text">0%</span>
            </div>
        </div>

        <div style="display: flex; justify-content: space-between; margin-bottom: 20px;">
            <span id="current-step">Initializing...</span>
            <span id="cards-count">0 cards</span>
        </div>

        <h3>Live Logs:</h3>
        <div id="log-container" class="log-container">
            <!-- Logs will appear here -->
        </div>
    </div>

    <script>
        const jobId = new URLSearchParams(window.location.search).get('job_id');

        // Poll status
        function updateStatus() {
            fetch(`/api/processing/${jobId}/status`)
                .then(res => res.json())
                .then(data => {
                    document.getElementById('progress-bar').style.width = data.progress_percentage + '%';
                    document.getElementById('progress-text').textContent = data.progress_percentage + '%';
                    document.getElementById('current-step').textContent = data.current_step || 'Processing...';
                    document.getElementById('cards-count').textContent = data.total_cards + ' cards';

                    const badge = document.getElementById('status-badge');
                    badge.textContent = data.status.toUpperCase();
                    badge.className = 'status-badge ' + data.status;

                    if (data.status === 'completed' || data.status === 'failed') {
                        clearInterval(statusInterval);
                    }
                });
        }

        // Stream logs via SSE
        const logContainer = document.getElementById('log-container');
        const eventSource = new EventSource(`/api/processing/${jobId}/logs`);

        eventSource.onmessage = function(event) {
            const log = JSON.parse(event.data);
            const entry = document.createElement('div');
            entry.className = 'log-entry ' + log.level;
            entry.textContent = `[${log.timestamp}] ${log.message}`;
            logContainer.appendChild(entry);
            logContainer.scrollTop = logContainer.scrollHeight;
        };

        // Poll status every 2 seconds
        const statusInterval = setInterval(updateStatus, 2000);
        updateStatus(); // Initial call
    </script>
</body>
</html>
```

---

## Benefits of This Approach

### 1. User Experience
- ✅ **Real-time feedback:** User sees exactly what's happening
- ✅ **Progress indication:** Percentage and chunk progress
- ✅ **Time estimation:** User knows how long to wait
- ✅ **Peace of mind:** No black-box processing

### 2. Debugging
- ✅ **Complete logs:** Every step recorded
- ✅ **Error tracking:** Exact point of failure visible
- ✅ **Performance metrics:** Time per chunk visible

### 3. Reliability
- ✅ **Resume capability:** Can continue from failed chunk
- ✅ **Job history:** Track all processing attempts
- ✅ **Error recovery:** Clear error messages

### 4. Scalability
- ✅ **Queue system:** Can process multiple PDFs
- ✅ **Background processing:** Non-blocking
- ✅ **Resource management:** Control concurrent jobs

---

## Implementation Timeline

### Week 1: Backend Infrastructure
- Day 1-2: Create `processing_jobs_db.py` and database
- Day 3-4: Update `process_large_pdf.py` with progress tracking
- Day 5: Add API endpoints to `unified_server.py`

### Week 2: Frontend UI
- Day 1-2: Build progress dashboard HTML/CSS/JS
- Day 3: Implement Server-Sent Events (SSE)
- Day 4: Integrate with existing dashboard
- Day 5: Testing and bug fixes

### Week 3: Polish & Deploy
- Day 1-2: Add estimated time remaining
- Day 3: Add pause/resume capability (optional)
- Day 4: Documentation and user guide
- Day 5: Deploy to Mac Mini

---

## Alternative Approaches Considered

### Option 1: WebSockets (Not chosen)
- ❌ More complex setup
- ❌ Requires persistent connection
- ✅ Bi-directional communication (not needed here)

### Option 2: Long Polling (Not chosen)
- ❌ Higher server load
- ❌ Less efficient than SSE
- ✅ Better browser compatibility (not an issue)

### Option 3: Server-Sent Events (SSE) ✅ CHOSEN
- ✅ Simple to implement
- ✅ Built-in browser support
- ✅ Automatic reconnection
- ✅ Perfect for one-way updates (logs)

---

## Next Steps

1. Review and approve this design
2. Start with Phase 1: Backend Infrastructure
3. Test with sample large PDF
4. Build frontend UI
5. Integrate and deploy

**Estimated total implementation time:** 2-3 weeks

This design solves the 15-20 minute black-box problem by giving users complete visibility into what's happening at every step!
