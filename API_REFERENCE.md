# SpeedMathsGames.com - API Reference

**Last Updated:** January 3, 2026
**Base URL:** `https://speedmathsgames.com` (Production) | `http://localhost:8001` (Development)

---

## Table of Contents

1. [Overview](#overview)
2. [Authentication](#authentication)
3. [Dashboard APIs](#dashboard-apis)
4. [PDF APIs](#pdf-apis)
5. [Assessment APIs](#assessment-apis)
6. [Math APIs](#math-apis)
7. [Diary APIs](#diary-apis)
8. [Mock Test APIs](#mock-test-apis)
9. [Analytics APIs](#analytics-apis)
10. [Finance APIs](#finance-apis)
11. [Health APIs](#health-apis)
12. [Calendar APIs](#calendar-apis)
13. [Admin APIs](#admin-apis)
14. [Error Handling](#error-handling)

---

## Overview

### Request Format
- All POST requests accept JSON body with `Content-Type: application/json`
- Authentication via session cookie (set after OAuth login)

### Response Format
```json
{
  "status": "success" | "error",
  "data": { ... },
  "message": "Optional message"
}
```

### CORS Headers
All responses include:
```
Access-Control-Allow-Origin: *
Access-Control-Allow-Methods: GET, POST, DELETE, OPTIONS
Access-Control-Allow-Headers: Content-Type
```

---

## Authentication

### GET /auth/login
Initiates Google OAuth flow.

**Response:** Redirects to Google OAuth consent screen.

---

### GET /auth/google/callback
OAuth callback handler.

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| code | string | OAuth authorization code |
| state | string | CSRF token |

**Response:** Redirects to dashboard with session cookie set.

---

### GET /auth/logout
Ends user session.

**Response:** Redirects to login page with session cookie cleared.

---

### GET /auth/user
Returns current authenticated user info.

**Response:**
```json
{
  "email": "user@example.com",
  "name": "User Name",
  "picture": "https://...",
  "role": "parent" | "child" | "admin",
  "username": "arvind"
}
```

---

## Dashboard APIs

### GET /api/dashboard
Returns all PDFs from scanned folders.

**Response:**
```json
{
  "status": "success",
  "pdfs": [
    {
      "id": 1,
      "filename": "current_affairs_2025_december_23.pdf",
      "filepath": "saanvi/Legaledgedailygk/...",
      "source_type": "daily",
      "source_name": "legaledge",
      "date_published": "2025-12-23",
      "page_count": 15,
      "file_size_kb": 45.2,
      "has_assessment": true,
      "needs_chunking": false
    }
  ],
  "total_count": 28
}
```

---

### GET /api/stats
Returns overall statistics.

**Response:**
```json
{
  "total_pdfs": 28,
  "total_topics": 450,
  "total_revisions": 120,
  "recent_activity": [...]
}
```

---

## PDF APIs

### GET /api/pdf/serve/{pdf_id}
Serves the actual PDF file for viewing.

**Response:** Binary PDF file with `Content-Type: application/pdf`

---

### GET /api/pdfs/{pdf_id}
Returns metadata for a specific PDF.

**Response:**
```json
{
  "id": 1,
  "filename": "current_affairs_2025_december_23.pdf",
  "filepath": "/full/path/to/file.pdf",
  "source_type": "daily",
  "page_count": 15,
  "topics": [...]
}
```

---

### POST /api/pdf/chunk
Splits a large PDF into smaller chunks.

**Request:**
```json
{
  "pdf_path": "/path/to/large.pdf",
  "chunk_size": 10
}
```

**Response:**
```json
{
  "status": "success",
  "parent_pdf": "large.pdf",
  "chunks": [
    {
      "chunk_number": 1,
      "filename": "large_part1.pdf",
      "start_page": 0,
      "end_page": 10,
      "page_count": 10,
      "file_size_kb": 1234.56
    }
  ]
}
```

---

### GET /api/chunks/{parent_pdf_id}
Returns chunks for a specific parent PDF.

**Response:**
```json
{
  "chunks": [
    {
      "id": 1,
      "parent_pdf_id": "large.pdf",
      "chunk_number": 1,
      "output_filename": "large_part1.pdf",
      "start_page": 0,
      "end_page": 10,
      "status": "created"
    }
  ]
}
```

---

### GET /api/chunks/all
Returns all PDF chunks.

**Response:**
```json
{
  "chunks": [...],
  "total_count": 15
}
```

---

### POST /api/annotations/{pdf_id}
Saves annotations for a PDF.

**Request:**
```json
{
  "annotations": [
    {
      "type": "highlight",
      "page": 1,
      "color": "#FFFF00",
      "rect": [100, 200, 300, 220]
    }
  ]
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Annotations saved"
}
```

---

### GET /api/annotations/{pdf_id}
Returns annotations for a PDF.

**Response:**
```json
{
  "annotations": [
    {
      "id": 1,
      "type": "highlight",
      "page": 1,
      "data": {...}
    }
  ]
}
```

---

## Assessment APIs

### POST /api/create-assessment
Creates a new assessment job (generates flashcards from PDF).

**Request:**
```json
{
  "pdf_id": "current_affairs_2025_december_23.pdf",
  "source": "legaledge",
  "week": "2025_Dec_D23"
}
```

**Response:**
```json
{
  "job_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "queued",
  "message": "Assessment job created"
}
```

---

### GET /api/assessment/progress/{job_id}
Returns progress of assessment creation job.

**Response:**
```json
{
  "job_id": "...",
  "status": "processing",
  "current_chunk": 2,
  "total_chunks": 3,
  "current_batch": 4,
  "total_batches": 8,
  "status_message": "Chunk 2: Batch 4/8 - Processing 3 topics",
  "total_cards": 67,
  "progress_percentage": 65
}
```

---

### GET /api/assessment/status/{pdf_id}
Returns assessment status for a PDF.

**Response:**
```json
{
  "has_assessments": true,
  "all_complete": true,
  "completed_chunks": 3,
  "total_chunks": 3,
  "total_cards": 147
}
```

---

### POST /api/assessment/start
Starts a new test session.

**Request:**
```json
{
  "pdf_id": "current_affairs_2025_december_23.pdf",
  "test_type": "full" | "quick" | "weak_topics",
  "question_count": 20
}
```

**Response:**
```json
{
  "session_id": "sess_abc123",
  "questions": [
    {
      "id": 1,
      "question": "What is...?",
      "choices": ["A", "B", "C", "D"],
      "topic": "Economy"
    }
  ],
  "total_questions": 20
}
```

---

### POST /api/assessment/submit
Submits answers for a test session.

**Request:**
```json
{
  "session_id": "sess_abc123",
  "answers": [
    {"question_id": 1, "selected": "A"},
    {"question_id": 2, "selected": "C"}
  ],
  "time_taken": 600
}
```

**Response:**
```json
{
  "score": 18,
  "total": 20,
  "percentage": 90.0,
  "results": [
    {
      "question_id": 1,
      "correct": true,
      "correct_answer": "A",
      "selected": "A"
    }
  ]
}
```

---

### GET /api/assessment/results/{session_id}
Returns results for a completed test.

**Response:**
```json
{
  "session_id": "sess_abc123",
  "score": 18,
  "total": 20,
  "percentage": 90.0,
  "time_taken": 600,
  "completed_at": "2025-12-23T10:30:00Z",
  "breakdown": {
    "by_topic": {...},
    "by_difficulty": {...}
  }
}
```

---

### GET /api/assessment/list
Returns list of available assessments.

**Response:**
```json
{
  "assessments": [
    {
      "pdf_id": "...",
      "total_cards": 67,
      "last_taken": "2025-12-22",
      "best_score": 95
    }
  ]
}
```

---

## Math APIs

### GET /api/math/questions
Returns math questions based on filters.

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| topic | string | Filter by topic (optional) |
| difficulty | string | easy/medium/hard (optional) |
| count | number | Number of questions (default: 10) |

**Response:**
```json
{
  "questions": [
    {
      "id": 1,
      "question": "What is 15 x 23?",
      "choices": ["345", "335", "355", "325"],
      "topic": "Arithmetic",
      "difficulty": "medium"
    }
  ]
}
```

---

### POST /api/math/submit
Submits answers for a math session.

**Request:**
```json
{
  "session_id": "math_sess_123",
  "answers": [
    {"question_id": 1, "selected": "345", "time_ms": 5000}
  ]
}
```

**Response:**
```json
{
  "correct": 8,
  "total": 10,
  "accuracy": 80.0,
  "average_time_ms": 4500
}
```

---

### GET /api/math/sessions
Returns math session history.

**Response:**
```json
{
  "sessions": [
    {
      "session_id": "...",
      "date": "2025-12-23",
      "questions": 10,
      "correct": 8,
      "accuracy": 80.0
    }
  ]
}
```

---

### GET /api/math/topics
Returns list of math topics.

**Response:**
```json
{
  "topics": [
    {"name": "Arithmetic", "question_count": 120},
    {"name": "Algebra", "question_count": 80},
    {"name": "Geometry", "question_count": 60}
  ]
}
```

---

### GET /api/math/analytics
Returns math performance analytics.

**Response:**
```json
{
  "overall_accuracy": 75.5,
  "by_topic": {
    "Arithmetic": {"accuracy": 85, "sessions": 20},
    "Algebra": {"accuracy": 70, "sessions": 15}
  },
  "trend": [...]
}
```

---

### GET /api/math/settings
Returns user's math topic/difficulty settings.

**Response:**
```json
{
  "enabled_topics": ["Arithmetic", "Algebra"],
  "difficulty": "medium"
}
```

---

### POST /api/math/settings
Updates math settings.

**Request:**
```json
{
  "enabled_topics": ["Arithmetic", "Algebra", "Geometry"],
  "difficulty": "hard"
}
```

---

## Diary APIs

### GET /api/diary/entries
Returns diary entries.

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| start_date | string | Start date (YYYY-MM-DD) |
| end_date | string | End date (YYYY-MM-DD) |

**Response:**
```json
{
  "entries": [
    {
      "id": 1,
      "date": "2025-12-23",
      "subjects": ["GK", "Math"],
      "hours_studied": 3.5,
      "mood": "good",
      "notes": "Completed chapter 5"
    }
  ]
}
```

---

### POST /api/diary/entries
Creates a new diary entry.

**Request:**
```json
{
  "date": "2025-12-23",
  "subjects": ["GK", "Math"],
  "hours_studied": 3.5,
  "mood": "good",
  "notes": "Completed chapter 5"
}
```

---

### GET /api/diary/subjects
Returns subject tracking data.

**Response:**
```json
{
  "subjects": [
    {"name": "GK", "total_hours": 45.5, "sessions": 20},
    {"name": "Math", "total_hours": 30.0, "sessions": 15}
  ]
}
```

---

### GET /api/diary/streaks
Returns streak information.

**Response:**
```json
{
  "current_streak": 7,
  "longest_streak": 21,
  "streaks_by_subject": {
    "GK": {"current": 7, "longest": 15},
    "Math": {"current": 5, "longest": 12}
  }
}
```

---

### GET /api/diary/reminders
Returns smart reminders.

**Response:**
```json
{
  "reminders": [
    {
      "type": "streak_at_risk",
      "message": "Don't break your 7-day GK streak!",
      "subject": "GK"
    }
  ]
}
```

---

## Mock Test APIs

### POST /api/mocks/create
Creates a new mock test entry.

**Request:**
```json
{
  "test_name": "CLAT 2025 Mock 1",
  "test_date": "2025-12-23",
  "total_marks": 150,
  "obtained_marks": 120,
  "sections": [
    {"name": "English", "total": 28, "obtained": 24},
    {"name": "Current Affairs", "total": 35, "obtained": 30}
  ]
}
```

---

### GET /api/mocks/list
Returns list of mock tests.

**Response:**
```json
{
  "mocks": [
    {
      "id": 1,
      "test_name": "CLAT 2025 Mock 1",
      "test_date": "2025-12-23",
      "total_marks": 150,
      "obtained_marks": 120,
      "percentage": 80.0
    }
  ]
}
```

---

### GET /api/mocks/analysis/{mock_id}
Returns detailed analysis of a mock test.

**Response:**
```json
{
  "id": 1,
  "test_name": "CLAT 2025 Mock 1",
  "sections": [
    {
      "name": "English",
      "total": 28,
      "obtained": 24,
      "accuracy": 85.7,
      "time_spent": 20
    }
  ],
  "percentile": 85,
  "rank_estimate": 1500,
  "weak_areas": ["Legal Reasoning", "Quantitative"]
}
```

---

## Analytics APIs

### GET /api/analytics/daily
Returns daily performance statistics.

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| date | string | Date (YYYY-MM-DD) |

**Response:**
```json
{
  "date": "2025-12-23",
  "assessments_taken": 3,
  "questions_answered": 60,
  "accuracy": 78.5,
  "time_spent_minutes": 45
}
```

---

### GET /api/analytics/weekly
Returns weekly trends.

**Response:**
```json
{
  "weeks": [
    {
      "week_start": "2025-12-16",
      "assessments": 15,
      "accuracy": 75.2,
      "improvement": 5.3
    }
  ]
}
```

---

### GET /api/analytics/category
Returns performance by category/topic.

**Response:**
```json
{
  "categories": [
    {
      "name": "Economy",
      "total_questions": 120,
      "correct": 96,
      "accuracy": 80.0,
      "mastery": "reviewing"
    }
  ]
}
```

---

## Finance APIs

**Note:** These APIs are only accessible to users with parent/admin role.

### GET /api/finance/dashboard
Returns finance overview.

**Response:**
```json
{
  "net_worth": 5000000,
  "total_assets": 6000000,
  "total_liabilities": 1000000,
  "monthly_summary": {...}
}
```

---

### GET /api/finance/accounts
Returns bank accounts.

**Response:**
```json
{
  "accounts": [
    {
      "id": 1,
      "name": "HDFC Savings",
      "type": "savings",
      "balance": 150000,
      "last_updated": "2025-12-23"
    }
  ]
}
```

---

### POST /api/finance/accounts
Creates a new bank account.

**Request:**
```json
{
  "name": "ICICI Savings",
  "type": "savings",
  "balance": 100000
}
```

---

### PUT /api/finance/accounts/{id}
Updates account balance.

**Request:**
```json
{
  "balance": 175000
}
```

---

### GET /api/finance/stocks
Returns stock portfolio.

**Response:**
```json
{
  "stocks": [
    {
      "symbol": "RELIANCE",
      "name": "Reliance Industries",
      "quantity": 50,
      "avg_price": 2400,
      "current_price": 2650,
      "gain_loss": 12500,
      "gain_loss_percent": 10.4
    }
  ],
  "total_value": 500000,
  "total_gain_loss": 45000
}
```

---

### GET /api/finance/assets
Returns assets (real estate, vehicles, etc.).

**Response:**
```json
{
  "assets": [
    {
      "id": 1,
      "name": "House",
      "type": "real_estate",
      "purchase_value": 5000000,
      "current_value": 6500000,
      "purchase_date": "2020-01-15"
    }
  ]
}
```

---

### GET /api/finance/liabilities
Returns loans and debts.

**Response:**
```json
{
  "liabilities": [
    {
      "id": 1,
      "name": "Home Loan",
      "type": "loan",
      "principal": 4000000,
      "outstanding": 3200000,
      "emi": 35000,
      "interest_rate": 8.5
    }
  ]
}
```

---

### GET /api/finance/bills
Returns upcoming bills.

**Response:**
```json
{
  "bills": [
    {
      "id": 1,
      "name": "Electricity",
      "amount": 3500,
      "due_date": "2025-12-25",
      "recurring": true,
      "frequency": "monthly"
    }
  ]
}
```

---

### GET /api/finance/net-worth-history
Returns net worth over time.

**Response:**
```json
{
  "history": [
    {"date": "2025-01-01", "net_worth": 4500000},
    {"date": "2025-06-01", "net_worth": 4800000},
    {"date": "2025-12-01", "net_worth": 5000000}
  ]
}
```

---

## Health APIs

**Note:** These APIs are only accessible to users with parent/admin role.

### GET /api/health/dashboard
Returns health overview.

**Response:**
```json
{
  "current_weight": 75.5,
  "target_weight": 70.0,
  "bmi": 24.5,
  "weekly_workouts": 4,
  "calories_today": 1800
}
```

---

### GET /api/health/weight
Returns weight history.

**Response:**
```json
{
  "entries": [
    {"date": "2025-12-23", "weight": 75.5},
    {"date": "2025-12-22", "weight": 75.8}
  ],
  "trend": "decreasing",
  "change_last_week": -0.5
}
```

---

### POST /api/health/weight
Logs weight entry.

**Request:**
```json
{
  "date": "2025-12-23",
  "weight": 75.5
}
```

---

### GET /api/health/workouts
Returns workout history.

**Response:**
```json
{
  "workouts": [
    {
      "id": 1,
      "date": "2025-12-23",
      "type": "strength",
      "duration_minutes": 45,
      "exercises": [
        {"name": "Squats", "sets": 3, "reps": 12}
      ],
      "calories_burned": 350
    }
  ]
}
```

---

### POST /api/health/workouts
Creates workout entry.

**Request:**
```json
{
  "date": "2025-12-23",
  "type": "strength",
  "duration_minutes": 45,
  "exercises": [
    {"name": "Squats", "sets": 3, "reps": 12}
  ]
}
```

---

### GET /api/health/diet
Returns diet log.

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| date | string | Date (YYYY-MM-DD) |

**Response:**
```json
{
  "entries": [
    {
      "id": 1,
      "meal_type": "breakfast",
      "food": "Oatmeal with fruits",
      "calories": 350,
      "protein": 12,
      "carbs": 55,
      "fat": 8
    }
  ],
  "totals": {
    "calories": 1800,
    "protein": 80,
    "carbs": 200,
    "fat": 60
  }
}
```

---

### POST /api/health/diet
Logs food entry.

**Request:**
```json
{
  "date": "2025-12-23",
  "meal_type": "breakfast",
  "food": "Oatmeal with fruits",
  "calories": 350,
  "protein": 12,
  "carbs": 55,
  "fat": 8
}
```

---

### GET /api/health/reports
Returns blood report history.

**Response:**
```json
{
  "reports": [
    {
      "id": 1,
      "date": "2025-12-01",
      "type": "CBC",
      "metrics": {
        "hemoglobin": {"value": 14.5, "unit": "g/dL", "status": "normal"},
        "glucose": {"value": 95, "unit": "mg/dL", "status": "normal"}
      }
    }
  ]
}
```

---

## Calendar APIs

### GET /api/calendar/events
Returns calendar events.

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| start | string | Start date (ISO) |
| end | string | End date (ISO) |
| account | string | Google account email (optional) |

**Response:**
```json
{
  "events": [
    {
      "id": "event123",
      "title": "Electricity Bill Due",
      "start": "2025-12-25T00:00:00Z",
      "end": "2025-12-25T23:59:59Z",
      "type": "bill_reminder"
    }
  ]
}
```

---

### POST /api/calendar/sync
Triggers calendar sync with Google.

**Response:**
```json
{
  "status": "success",
  "synced_events": 15,
  "last_sync": "2025-12-23T10:30:00Z"
}
```

---

### GET /api/calendar/accounts
Returns connected Google accounts.

**Response:**
```json
{
  "accounts": [
    {
      "email": "user@gmail.com",
      "connected": true,
      "last_sync": "2025-12-23T10:30:00Z"
    }
  ]
}
```

---

## Admin APIs

**Note:** These APIs are only accessible to admin users.

### GET /api/admin/family
Returns all family members' data.

**Response:**
```json
{
  "members": [
    {
      "username": "saanvi",
      "email": "20saanvi12@gmail.com",
      "role": "child",
      "last_active": "2025-12-23T10:30:00Z",
      "stats": {
        "assessments_taken": 45,
        "average_score": 78.5
      }
    }
  ]
}
```

---

### GET /api/admin/user/{username}
Returns detailed data for a specific user.

**Response:**
```json
{
  "username": "saanvi",
  "email": "20saanvi12@gmail.com",
  "role": "child",
  "activity": {...},
  "performance": {...}
}
```

---

## Error Handling

### Error Response Format
```json
{
  "status": "error",
  "message": "Error description",
  "code": "ERROR_CODE"
}
```

### Common Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| AUTH_REQUIRED | 401 | User not authenticated |
| FORBIDDEN | 403 | User lacks permission |
| NOT_FOUND | 404 | Resource not found |
| VALIDATION_ERROR | 400 | Invalid request data |
| SERVER_ERROR | 500 | Internal server error |

### Authentication Errors
```json
{
  "status": "error",
  "message": "Authentication required",
  "code": "AUTH_REQUIRED"
}
```

### Permission Errors
```json
{
  "status": "error",
  "message": "Access denied. Parents only.",
  "code": "FORBIDDEN"
}
```

---

## Rate Limiting

Currently no rate limiting is implemented. The server is designed for family use only (4 users).

---

## Testing Endpoints

### GET /api/test
Health check endpoint.

**Response:**
```json
{
  "status": "ok",
  "server": "unified_server",
  "version": "4.0"
}
```

---

*For more details on the server implementation, see `server/unified_server.py`.*
