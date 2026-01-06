# SpeedMathsGames.com - Complete System Architecture

**Last Updated:** January 3, 2026
**Version:** 4.0
**Status:** Production (Active on speedmathsgames.com)

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Tech Stack](#2-tech-stack)
3. [Deployment Topology](#3-deployment-topology)
4. [Directory Structure](#4-directory-structure)
5. [Backend Architecture](#5-backend-architecture)
6. [Frontend Architecture](#6-frontend-architecture)
7. [Database Architecture](#7-database-architecture)
8. [Authentication & Authorization](#8-authentication--authorization)
9. [Feature Modules](#9-feature-modules)
10. [Third-Party Integrations](#10-third-party-integrations)
11. [Data Flows](#11-data-flows)
12. [Key Technical Patterns](#12-key-technical-patterns)

---

## 1. System Overview

### Purpose
SpeedMathsGames.com is a comprehensive CLAT (Common Law Admission Test) exam preparation system that includes:
- **GK Dashboard** - Current affairs PDF management and revision tracking
- **Math Speed Games** - 360+ math practice questions with analytics
- **Assessment System** - AI-powered flashcard generation from PDFs
- **Daily Diary** - Study tracking with streaks and reminders
- **Mock Test Analysis** - CLAT-format mock test tracking and analytics
- **Finance Dashboard** - Personal finance and net worth tracking (Parents only)
- **Health Dashboard** - Fitness, diet, and health tracking (Parents only)
- **Calendar Integration** - Google Calendar sync with bill reminders

### Family Users
| Email | Username | Role | Access |
|-------|----------|------|--------|
| k12arvind@gmail.com | arvind | Admin, Parent | All features + Finance + Health |
| deepay2019@gmail.com | deepa | Parent | All features + Finance + Health |
| 20saanvi12@gmail.com | saanvi | Child | Math, GK, Diary, Mocks |
| 20navya12@gmail.com | navya | Child | Math, GK, Diary, Mocks |

---

## 2. Tech Stack

### Backend
| Component | Technology |
|-----------|------------|
| Server | Python 3.9+ with `ThreadingHTTPServer` |
| Database | SQLite3 (6 databases) |
| API | Custom REST API |
| Authentication | Google OAuth 2.0 |

### Frontend
| Component | Technology |
|-----------|------------|
| Framework | Vanilla HTML5, CSS3, JavaScript |
| Styling | Custom CSS with dark/light mode |
| PDF Viewer | ts-pdf, pdfjs-dist |
| Charts | (if applicable) |

### External APIs
| Service | Purpose |
|---------|---------|
| Anthropic Claude API | AI flashcard generation |
| AnkiConnect | Flashcard synchronization |
| Google OAuth 2.0 | User authentication |
| Google Calendar API | Calendar sync |
| Gmail API | Email notifications |
| mStock API | Stock portfolio data |

---

## 3. Deployment Topology

```
┌─────────────────────────────────────────────────────────────────┐
│                        Internet                                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Cloudflare Tunnel                              │
│                 speedmathsgames.com                               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Mac Mini (Production)                          │
│  User: arvindkumar                                               │
│  Home: /Users/arvindkumar                                        │
│  Server: localhost:8001                                          │
│  Running: 24/7                                                   │
└─────────────────────────────────────────────────────────────────┘
                              ▲
                              │ Git Push/Pull + rsync (PDFs)
                              │
┌─────────────────────────────────────────────────────────────────┐
│                 MacBook Pro (Development)                        │
│  User: arvind                                                    │
│  Home: /Users/arvind                                             │
│  Server: localhost:8001 (testing)                                │
│  Git Repository: Source of Truth                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Machine Roles

| Machine | Role | URL | Purpose |
|---------|------|-----|---------|
| MacBook Pro | Development | localhost:8001 | Code development, testing, Git source |
| Mac Mini | Production | speedmathsgames.com | 24/7 public server via Cloudflare |

### Syncing Workflow
```bash
# On MacBook Pro
git add . && git commit -m "Changes" && git push origin main

# On Mac Mini
cd ~/clat_preparation && git pull origin main

# PDFs synced separately
./scripts/auto_sync_pdfs.sh
```

---

## 4. Directory Structure

```
~/clat_preparation/
├── server/                          # Backend Python modules
│   ├── unified_server.py           # Main HTTP server (4,300+ lines)
│   ├── assessment_database.py      # Assessment/test tracking
│   ├── anki_connector.py           # Anki integration
│   ├── pdf_scanner.py              # PDF discovery
│   ├── pdf_chunker.py              # PDF splitting
│   ├── math_db.py                  # Math module database
│   ├── diary_db.py                 # Diary tracking
│   ├── mock_db.py                  # Mock test analysis
│   ├── finance_db.py               # Financial tracking
│   ├── health_db.py                # Health tracking
│   ├── calendar_db.py              # Calendar events
│   ├── questions_db.py             # Local question storage
│   ├── google_calendar_client.py   # Google Calendar API
│   ├── email_service.py            # Gmail integration
│   ├── user_roles.py               # Family configuration
│   └── google_auth.py              # OAuth handler
│
├── dashboard/                       # Frontend files
│   ├── index.html                  # Landing page
│   ├── login.html                  # Google OAuth login
│   ├── comprehensive_dashboard.html # Main GK hub
│   ├── math_practice.html          # Math games
│   ├── assessment.html             # Take assessments
│   ├── assessment-progress.html    # Assessment creation tracker
│   ├── pdf_dashboard.html          # PDF management
│   ├── pdf-viewer.html             # Enhanced PDF reader
│   ├── pdf-chunker.html            # PDF splitting UI
│   ├── diary.html                  # Daily study diary
│   ├── mock_analysis.html          # Mock test analysis
│   ├── calendar.html               # Calendar integration
│   ├── finance_dashboard.html      # Finance overview
│   ├── finance_accounts.html       # Bank accounts
│   ├── finance_bills.html          # Bill tracking
│   ├── finance_stocks.html         # Stock portfolio
│   ├── finance_assets.html         # Assets tracking
│   ├── finance_liabilities.html    # Loans/debts
│   ├── health_dashboard.html       # Health overview
│   ├── health_diet.html            # Diet tracking
│   ├── health_weight.html          # Weight logging
│   ├── health_workout.html         # Workout sessions
│   ├── health_reports.html         # Blood reports
│   ├── family_dashboard.html       # Admin: family view
│   ├── math_admin.html             # Math questions admin
│   ├── shared-styles.css           # Global CSS
│   └── auth.js                     # Auth utilities
│
├── math_module/                     # Math module code
│   └── math_db.py                  # Math database class
│
├── toprankers/                      # TopRankers automation
│   ├── automate_html.sh            # Main automation
│   ├── generate_clean_pdf_final.py # PDF generation
│   ├── generate_flashcards_from_html.py
│   └── import_to_anki.py
│
├── scripts/                         # Utility scripts
│   ├── start_server.sh             # Start server
│   ├── sync_to_mac_mini.sh         # Full sync
│   ├── auto_sync_pdfs.sh           # PDF sync
│   └── deploy_resilient_services.sh
│
├── migrations/                      # Database migrations
│   ├── add_diary_tables.sql
│   └── add_mock_analysis_tables.sql
│
├── docs/                           # Additional docs
│   └── GOOGLE_CALENDAR_SETUP.md
│
├── logs/                           # Server logs
│
├── venv_clat/                      # Python virtual environment
│
├── .env                            # Environment variables
├── revision_tracker.db             # GK database
├── math_tracker.db                 # Math database
├── assessment_tracker.db           # Assessment database
├── finance_tracker.db              # Finance database
├── health_tracker.db               # Health database
└── calendar_tracker.db             # Calendar database

~/saanvi/                            # PDF storage
├── Legaledgedailygk/               # Daily current affairs
├── LegalEdgeweeklyGK/              # Weekly PDFs (LegalEdge)
└── weeklyGKCareerLauncher/         # Weekly PDFs (Career Launcher)
```

---

## 5. Backend Architecture

### Main Server: `server/unified_server.py`

The unified server (~4,300 lines) handles all HTTP requests using Python's `ThreadingHTTPServer`.

```python
class UnifiedHandler(SimpleHTTPRequestHandler):
    # Shared instances (initialized once)
    google_auth = None
    user_db = None
    assessment_db = None
    anki = None
    anthropic = None
    math_db = None
    pdf_scanner = None
    processing_db = None
    annotation_manager = None
    pdf_chunker = None
    diary_db = None
    mock_db = None
    questions_db = None
    finance_db = None
    health_db = None
    calendar_db = None
    calendar_client = None
```

### Request Flow
```
HTTP Request
    ↓
UnifiedHandler.do_GET/do_POST/do_DELETE
    ↓
Route matching (based on /api/* path)
    ↓
Authentication check (session cookie)
    ↓
Role-based access control
    ↓
Handler method execution
    ↓
JSON response + CORS headers
```

### API Endpoint Categories

| Category | Base Path | Purpose |
|----------|-----------|---------|
| Authentication | `/auth/*` | OAuth login/logout |
| Dashboard | `/api/dashboard` | GK PDF listing |
| PDF | `/api/pdf/*`, `/api/chunks/*` | PDF operations |
| Assessment | `/api/assessment/*` | Tests and results |
| Math | `/api/math/*` | Math practice |
| Diary | `/api/diary/*` | Study diary |
| Mock | `/api/mocks/*` | Mock test analysis |
| Analytics | `/api/analytics/*` | Performance stats |
| Finance | `/api/finance/*` | Financial tracking (Parents) |
| Health | `/api/health/*` | Health tracking (Parents) |
| Calendar | `/api/calendar/*` | Calendar sync |
| Admin | `/api/admin/*` | Family management |

---

## 6. Frontend Architecture

### Page Structure
All pages follow a consistent structure:
- Include `shared-styles.css` for theming
- Include `auth.js` for authentication
- Check authentication on load
- Support dark/light mode toggle

### Key Frontend Files

| File | Purpose |
|------|---------|
| `index.html` | Landing page with hero section |
| `login.html` | Google OAuth login |
| `comprehensive_dashboard.html` | Main GK hub |
| `auth.js` | `checkAuth()`, `logout()`, session management |
| `shared-styles.css` | CSS variables for theming |

### Dark/Light Mode
```css
:root {
    --bg-primary: #1a1a2e;
    --text-primary: #e0e0e0;
    /* ... dark mode colors */
}

[data-theme="light"] {
    --bg-primary: #f5f5f5;
    --text-primary: #333333;
    /* ... light mode colors */
}
```

### Real-Time Features
- **Server-Sent Events (SSE)**: Used for progress tracking during PDF processing
- **Polling**: Assessment progress checks every 2 seconds
- **Fetch API**: All API calls use async/await patterns

---

## 7. Database Architecture

### Database Files

| Database | Purpose | Size |
|----------|---------|------|
| `revision_tracker.db` | GK PDFs, topics, revisions, diary, mocks | ~1.5 MB |
| `math_tracker.db` | Math questions, sessions, answers | ~650 KB |
| `assessment_tracker.db` | Test sessions, question attempts | ~70 KB |
| `finance_tracker.db` | Accounts, assets, stocks, liabilities | ~85 KB |
| `health_tracker.db` | Weight, workouts, diet, reports | ~105 KB |
| `calendar_tracker.db` | OAuth tokens, events, sync status | New |

### Key Tables by Database

#### revision_tracker.db
- `pdfs` - PDF metadata
- `topics` - GK topics
- `pdf_chunks` - Chunked PDF tracking
- `pdf_annotations` - PDF annotations
- `diary_entries` - Daily study entries
- `diary_subjects` - Subject tracking
- `subject_streaks` - Streak calculations
- `mock_tests` - Mock test results
- `mock_sections` - Section-wise analysis
- `questions` - Local question storage

#### math_tracker.db
- `math_questions` - 360+ questions
- `math_sessions` - Practice sessions
- `math_answers` - User answers
- `math_settings` - Topic/difficulty preferences
- `math_topic_performance` - Performance aggregation

#### finance_tracker.db
- `bank_accounts` - Account tracking
- `balance_history` - Historical balances
- `assets` - Real estate, vehicles
- `stocks` - Stock holdings
- `dividends` - Dividend tracking
- `liabilities` - Loans, debts
- `net_worth_history` - Net worth over time

#### health_tracker.db
- `health_profiles` - User profiles (age, height)
- `weight_log` - Weight tracking
- `workouts` - Workout sessions
- `exercise_library` - Exercise catalog
- `diet_log` - Food/calorie tracking
- `blood_reports` - Medical reports

---

## 8. Authentication & Authorization

### Google OAuth 2.0 Flow
```
1. User visits /login.html
2. Clicks "Sign in with Google"
3. Redirect to Google OAuth consent
4. Google callback to /auth/google/callback
5. Server validates token, creates session
6. Session stored in HttpOnly cookie
7. Redirect to dashboard
```

### Role-Based Access Control

| Role | Permissions |
|------|-------------|
| Admin | All features + family management |
| Parent | All features + Finance + Health |
| Child | Math, GK, Diary, Mocks only |

### Permission Checks
```python
# In unified_server.py
def is_parent_or_admin(self, user):
    return user.get('role') in ['parent', 'admin']

def can_access_finance(self, user):
    return self.is_parent_or_admin(user)

def can_access_health(self, user):
    return self.is_parent_or_admin(user)
```

### Public Pages (No Auth Required)
- `/` and `/index.html`
- `/login.html`
- `/privacy_policy.html`

---

## 9. Feature Modules

### 9.1 GK Dashboard
**Purpose**: Manage and track current affairs PDFs

**Features**:
- Scans PDFs from 3 folders (LegalEdge Daily, Weekly, Career Launcher)
- Shows file metadata (size, pages, dates)
- PDF chunking for large files (>20 pages)
- PDF annotations (draw, highlight, notes)
- Revision tracking and statistics
- Assessment creation (AI flashcards)

### 9.2 Math Speed Games
**Purpose**: Practice math with 360+ questions

**Features**:
- Multiple topics: Arithmetic, Algebra, Geometry, Data Interpretation
- Difficulty levels: Easy, Medium, Hard
- Session tracking with accuracy
- Topic-based performance analytics
- User-customizable settings

### 9.3 Assessment System
**Purpose**: AI-powered flashcard generation and testing

**Features**:
- Create assessments from PDFs using Claude AI
- Multiple test modes: Full, Quick, Weak Topics
- Real-time progress tracking via SSE
- Question-wise performance analytics
- Mastery levels: Not Started → Learning → Reviewing → Mastered

### 9.4 Daily Diary
**Purpose**: Track daily study progress

**Features**:
- Daily entry logging
- Subject-wise tracking
- Streak calculation (consecutive days)
- Smart reminders
- Mood/confidence tracking
- Historical analytics

### 9.5 Mock Test Analysis
**Purpose**: Track CLAT mock test performance

**CLAT Format**:
| Section | Questions |
|---------|-----------|
| English | 28 |
| Current Affairs | 35 |
| Legal Reasoning | 35 |
| Logical Reasoning | 28 |
| Quantitative | 14 |
| **Total** | **150** (120 minutes) |

**Features**:
- Section-wise performance tracking
- Percentile and rank estimation
- Time-per-question analysis
- Weak areas identification
- Historical comparison

### 9.6 Finance Dashboard (Parents Only)
**Purpose**: Personal finance and net worth tracking

**Features**:
- Bank account management
- Stock portfolio tracking (via mStock API)
- Asset tracking (real estate, vehicles)
- Liability management (loans, debts)
- Bill tracking with reminders
- Net worth calculation and history
- Dividend tracking

### 9.7 Health Dashboard (Parents Only)
**Purpose**: Health and fitness tracking

**Features**:
- Weight logging with trends
- Workout session tracking
- Exercise library
- Diet/calorie logging
- Blood report parsing and analysis
- Health goals and progress

### 9.8 Calendar Integration
**Purpose**: Google Calendar sync

**Features**:
- Multi-account Google Calendar sync
- Bill reminders as calendar events
- Daily email summaries
- Event caching for performance

---

## 10. Third-Party Integrations

### Anthropic Claude API
- **Purpose**: AI flashcard generation from PDFs
- **Model**: Claude Sonnet 4.5
- **Flow**: PDF text → Claude prompt → Q&A flashcard pairs
- **Cost**: ~$0.05-0.08 per daily PDF

### AnkiConnect
- **Purpose**: Sync flashcards with Anki desktop
- **Port**: localhost:8765
- **Methods**: Query by tags, create notes, import cards
- **Tag Format**: `week:2025_Dec_D19`, `source:pdf_filename`

### Google APIs
- **OAuth 2.0**: User authentication
- **Calendar API**: Read/write calendar events
- **Gmail API**: Send daily summary emails

### mStock API
- **Purpose**: Stock portfolio data
- **Features**: CSV export parsing, price tracking, dividends

---

## 11. Data Flows

### Daily PDF Processing
```
TopRankers URL
    ↓
generate_clean_pdf_final.py
    ↓
PDF saved → ~/saanvi/Legaledgedailygk/
    ↓
automate_html.sh → Anki cards
    ↓
./sync_to_mac_mini.sh
    ↓
PDFScanner.scan_all_folders()
    ↓
Database updated
    ↓
Dashboard displays PDF
```

### Assessment Creation Flow
```
User clicks "Create Assessment"
    ↓
POST /api/create-assessment
    ↓
Job created in assessment_jobs table
    ↓
Background: AssessmentProcessor runs
    ↓
Fetches questions from Anki/Questions DB
    ↓
Frontend polls /api/assessment/progress
    ↓
SSE updates with progress
    ↓
Assessment ready
```

### Test Taking Flow
```
Student clicks "Take Test"
    ↓
GET /api/assessment/questions?session_id=...
    ↓
Questions displayed
    ↓
Student answers
    ↓
POST /api/assessment/submit
    ↓
Server grades, saves to DB
    ↓
Update: question_attempts, question_performance
    ↓
Results displayed
```

---

## 12. Key Technical Patterns

### Cross-Machine Path Handling
```python
def path_to_relative(absolute_path):
    """Convert /Users/arvind/saanvi/... → saanvi/..."""
    return absolute_path.replace(os.path.expanduser('~') + '/', '')

def relative_to_absolute(relative_path):
    """Convert saanvi/... → /Users/{current_user}/saanvi/..."""
    return os.path.join(os.path.expanduser('~'), relative_path)
```

### Server-Sent Events (SSE)
```python
# Server sends progress updates
self.wfile.write(f"data: {json.dumps(progress)}\n\n".encode())
self.wfile.flush()

# Client listens
const eventSource = new EventSource(`/api/processing/${jobId}/logs`);
eventSource.onmessage = (e) => updateProgress(JSON.parse(e.data));
```

### Thread-Safe Database
```python
conn = sqlite3.connect(db_path, check_same_thread=False)
conn.row_factory = sqlite3.Row  # Dict-like access
```

### CORS Headers
```python
def add_cors_headers(self):
    self.send_header('Access-Control-Allow-Origin', '*')
    self.send_header('Access-Control-Allow-Methods', 'GET, POST, DELETE, OPTIONS')
    self.send_header('Access-Control-Allow-Headers', 'Content-Type')
```

---

## Related Documentation

- **[API_REFERENCE.md](./API_REFERENCE.md)** - Complete API endpoint documentation
- **[DATABASE_SCHEMA.md](./DATABASE_SCHEMA.md)** - Detailed database schema
- **[DEPLOYMENT.md](./DEPLOYMENT.md)** - Deployment and operations guide
- **[MAC_MINI_SETUP.md](./MAC_MINI_SETUP.md)** - Mac Mini specific setup
- **[GOOGLE_CALENDAR_SETUP.md](./docs/GOOGLE_CALENDAR_SETUP.md)** - Calendar API setup

---

## Summary Statistics

| Metric | Value |
|--------|-------|
| Total Lines of Code | ~4,300+ (unified_server.py alone) |
| Database Tables | 60+ across all databases |
| HTML Pages | 30+ frontend pages |
| API Endpoints | 60+ REST endpoints |
| Family Members | 4 (2 parents, 2 children) |
| Math Questions | 360+ |
| Python Modules | 15+ |
| Database Files | 6 |
| Deployment Machines | 2 |

---

*This document is the source of truth for system architecture. Update when making significant changes.*
