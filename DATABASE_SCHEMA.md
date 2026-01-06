# SpeedMathsGames.com - Database Schema

**Last Updated:** January 3, 2026

---

## Overview

The application uses 6 SQLite databases:

| Database | File | Purpose | Size |
|----------|------|---------|------|
| GK/Revision | revision_tracker.db | PDFs, topics, diary, mocks | ~1.5 MB |
| Math | math_tracker.db | Math questions and sessions | ~650 KB |
| Assessment | assessment_tracker.db | Test sessions and attempts | ~70 KB |
| Finance | finance_tracker.db | Financial tracking | ~85 KB |
| Health | health_tracker.db | Health/fitness tracking | ~105 KB |
| Calendar | calendar_tracker.db | Google Calendar sync | New |

---

## 1. revision_tracker.db

### pdfs
Stores metadata for all scanned PDFs.

```sql
CREATE TABLE pdfs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT UNIQUE NOT NULL,          -- current_affairs_2025_december_23.pdf
    filepath TEXT NOT NULL,                  -- Relative path: saanvi/Legaledgedailygk/...
    source_type TEXT NOT NULL,               -- 'daily' or 'weekly'
    source_name TEXT NOT NULL,               -- 'legaledge' or 'career_launcher'
    date_published TEXT,                     -- YYYY-MM-DD
    date_added TEXT NOT NULL,                -- When first scanned
    total_topics INTEGER DEFAULT 0,
    page_count INTEGER DEFAULT 0,
    file_size_kb REAL DEFAULT 0,
    last_modified TEXT,
    file_edit_count INTEGER DEFAULT 0,       -- Tracks manual PDF edits
    updated_at TEXT
);

CREATE INDEX idx_pdfs_source ON pdfs(source_type, source_name);
CREATE INDEX idx_pdfs_date ON pdfs(date_published);
```

### pdf_chunks
Tracks split PDF chunks for large files.

```sql
CREATE TABLE pdf_chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_pdf_id TEXT NOT NULL,             -- References pdfs.filename
    chunk_number INTEGER NOT NULL,
    output_filename TEXT NOT NULL,           -- file_part1.pdf
    start_page INTEGER NOT NULL,
    end_page INTEGER NOT NULL,
    page_count INTEGER NOT NULL,
    file_size_kb REAL,
    created_at TEXT NOT NULL,
    status TEXT DEFAULT 'created',           -- created/processed/failed
    FOREIGN KEY (parent_pdf_id) REFERENCES pdfs(filename)
);

CREATE INDEX idx_chunks_parent ON pdf_chunks(parent_pdf_id);
```

### pdf_annotations
Stores user annotations on PDFs.

```sql
CREATE TABLE pdf_annotations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pdf_id TEXT NOT NULL,                    -- References pdfs.filename
    user_id TEXT NOT NULL,                   -- User who created
    page_number INTEGER NOT NULL,
    annotation_type TEXT NOT NULL,           -- highlight/drawing/note
    annotation_data TEXT NOT NULL,           -- JSON blob
    color TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT,
    FOREIGN KEY (pdf_id) REFERENCES pdfs(filename)
);

CREATE INDEX idx_annotations_pdf ON pdf_annotations(pdf_id);
```

### topics
Individual topics extracted from PDFs.

```sql
CREATE TABLE topics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_date TEXT NOT NULL,               -- Date of the topic
    title TEXT NOT NULL,
    content TEXT,
    category TEXT,                           -- Economy, Polity, etc.
    pdf_id TEXT,
    created_at TEXT
);

CREATE INDEX idx_topics_date ON topics(source_date);
CREATE INDEX idx_topics_category ON topics(category);
```

### revisions
Tracks user revision history.

```sql
CREATE TABLE revisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id INTEGER NOT NULL,
    user_id TEXT NOT NULL,
    revision_date TEXT NOT NULL,
    confidence_level INTEGER,                -- 1-5
    notes TEXT,
    FOREIGN KEY (topic_id) REFERENCES topics(id)
);
```

### diary_entries
Daily study diary entries.

```sql
CREATE TABLE diary_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    date TEXT NOT NULL,                      -- YYYY-MM-DD
    subjects TEXT NOT NULL,                  -- JSON array of subjects
    hours_studied REAL DEFAULT 0,
    mood TEXT,                               -- good/neutral/bad
    confidence INTEGER,                      -- 1-5
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT,
    UNIQUE(user_id, date)
);

CREATE INDEX idx_diary_user_date ON diary_entries(user_id, date);
```

### diary_subjects
Subject tracking for diary.

```sql
CREATE TABLE diary_subjects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    subject_name TEXT NOT NULL,
    total_hours REAL DEFAULT 0,
    total_sessions INTEGER DEFAULT 0,
    last_studied TEXT,
    UNIQUE(user_id, subject_name)
);
```

### subject_streaks
Streak tracking for consistent study.

```sql
CREATE TABLE subject_streaks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    subject_name TEXT NOT NULL,
    current_streak INTEGER DEFAULT 0,
    longest_streak INTEGER DEFAULT 0,
    last_study_date TEXT,
    streak_start_date TEXT,
    UNIQUE(user_id, subject_name)
);
```

### diary_reminders
Smart reminders for study habits.

```sql
CREATE TABLE diary_reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    reminder_type TEXT NOT NULL,             -- streak_at_risk/missed_day/goal_progress
    subject TEXT,
    message TEXT NOT NULL,
    created_at TEXT NOT NULL,
    read_at TEXT,
    dismissed_at TEXT
);
```

### mock_tests
CLAT mock test results.

```sql
CREATE TABLE mock_tests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    test_name TEXT NOT NULL,
    test_date TEXT NOT NULL,
    test_source TEXT,                        -- CL/LE/etc.
    total_marks INTEGER NOT NULL,            -- Usually 150
    obtained_marks REAL NOT NULL,
    percentage REAL NOT NULL,
    time_taken_minutes INTEGER,
    percentile REAL,
    rank_estimate INTEGER,
    notes TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX idx_mocks_user_date ON mock_tests(user_id, test_date);
```

### mock_sections
Section-wise breakdown of mock tests.

```sql
CREATE TABLE mock_sections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mock_test_id INTEGER NOT NULL,
    section_name TEXT NOT NULL,              -- English/Current Affairs/Legal/Logical/Quant
    total_marks INTEGER NOT NULL,
    obtained_marks REAL NOT NULL,
    attempted INTEGER,
    correct INTEGER,
    incorrect INTEGER,
    time_spent_minutes INTEGER,
    accuracy REAL,
    FOREIGN KEY (mock_test_id) REFERENCES mock_tests(id)
);
```

### questions
Local question storage (for PDFs without Anki).

```sql
CREATE TABLE questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pdf_id TEXT NOT NULL,
    topic TEXT,
    question_text TEXT NOT NULL,
    question_type TEXT DEFAULT 'mcq',        -- mcq/true_false
    difficulty TEXT DEFAULT 'medium',
    explanation TEXT,
    created_at TEXT NOT NULL
);
```

### question_choices
MCQ choices for questions.

```sql
CREATE TABLE question_choices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question_id INTEGER NOT NULL,
    choice_text TEXT NOT NULL,
    is_correct INTEGER DEFAULT 0,
    choice_order INTEGER,
    FOREIGN KEY (question_id) REFERENCES questions(id)
);
```

### statistics
Aggregated statistics.

```sql
CREATE TABLE statistics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stat_type TEXT NOT NULL,                 -- daily_summary/weekly_summary
    stat_date TEXT NOT NULL,
    user_id TEXT NOT NULL,
    data TEXT NOT NULL,                      -- JSON blob
    created_at TEXT NOT NULL
);
```

---

## 2. math_tracker.db

### math_questions
Math practice questions (360+).

```sql
CREATE TABLE math_questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question_text TEXT NOT NULL,
    topic TEXT NOT NULL,                     -- Arithmetic/Algebra/Geometry/Data Interpretation
    subtopic TEXT,
    difficulty TEXT NOT NULL,                -- easy/medium/hard
    choice_a TEXT NOT NULL,
    choice_b TEXT NOT NULL,
    choice_c TEXT NOT NULL,
    choice_d TEXT NOT NULL,
    correct_answer TEXT NOT NULL,            -- a/b/c/d
    explanation TEXT,
    times_attempted INTEGER DEFAULT 0,
    times_correct INTEGER DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE INDEX idx_math_topic ON math_questions(topic);
CREATE INDEX idx_math_difficulty ON math_questions(difficulty);
```

### math_sessions
Practice session tracking.

```sql
CREATE TABLE math_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT UNIQUE NOT NULL,
    user_id TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT,
    total_questions INTEGER NOT NULL,
    questions_answered INTEGER DEFAULT 0,
    correct_answers INTEGER DEFAULT 0,
    topics TEXT,                             -- JSON array
    difficulty TEXT,
    status TEXT DEFAULT 'in_progress'        -- in_progress/completed/abandoned
);

CREATE INDEX idx_sessions_user ON math_sessions(user_id);
```

### math_answers
Individual answer records.

```sql
CREATE TABLE math_answers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    question_id INTEGER NOT NULL,
    user_id TEXT NOT NULL,
    selected_answer TEXT NOT NULL,
    is_correct INTEGER NOT NULL,
    time_taken_ms INTEGER,
    answered_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES math_sessions(session_id),
    FOREIGN KEY (question_id) REFERENCES math_questions(id)
);
```

### math_settings
User preferences for math practice.

```sql
CREATE TABLE math_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT UNIQUE NOT NULL,
    enabled_topics TEXT,                     -- JSON array
    preferred_difficulty TEXT DEFAULT 'medium',
    questions_per_session INTEGER DEFAULT 10,
    time_limit_enabled INTEGER DEFAULT 0,
    time_limit_seconds INTEGER DEFAULT 60,
    updated_at TEXT
);
```

### math_topic_performance
Aggregated topic performance.

```sql
CREATE TABLE math_topic_performance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    topic TEXT NOT NULL,
    total_attempted INTEGER DEFAULT 0,
    total_correct INTEGER DEFAULT 0,
    accuracy REAL DEFAULT 0,
    average_time_ms INTEGER,
    last_practiced TEXT,
    UNIQUE(user_id, topic)
);
```

---

## 3. assessment_tracker.db

### test_sessions
Assessment test sessions.

```sql
CREATE TABLE test_sessions (
    session_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    pdf_id TEXT,
    test_type TEXT NOT NULL,                 -- full/quick/weak_topics
    source_date TEXT,
    total_questions INTEGER NOT NULL,
    questions_answered INTEGER DEFAULT 0,
    score REAL,
    percentage REAL,
    time_taken_seconds INTEGER,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT DEFAULT 'in_progress'
);

CREATE INDEX idx_test_user ON test_sessions(user_id);
CREATE INDEX idx_test_pdf ON test_sessions(pdf_id);
```

### question_attempts
Individual question attempts.

```sql
CREATE TABLE question_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    question_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    selected_answer TEXT NOT NULL,
    correct_answer TEXT NOT NULL,
    is_correct INTEGER NOT NULL,
    time_taken_ms INTEGER,
    attempted_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES test_sessions(session_id)
);

CREATE INDEX idx_attempts_session ON question_attempts(session_id);
CREATE INDEX idx_attempts_question ON question_attempts(question_id);
```

### question_performance
Aggregate question performance.

```sql
CREATE TABLE question_performance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question_id TEXT UNIQUE NOT NULL,
    times_shown INTEGER DEFAULT 0,
    times_correct INTEGER DEFAULT 0,
    accuracy REAL DEFAULT 0,
    average_time_ms INTEGER,
    mastery_level TEXT DEFAULT 'not_started', -- not_started/learning/reviewing/mastered
    last_attempted TEXT
);
```

### pdf_performance
PDF-wise performance tracking.

```sql
CREATE TABLE pdf_performance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    pdf_id TEXT NOT NULL,
    total_questions INTEGER DEFAULT 0,
    mastered INTEGER DEFAULT 0,
    reviewing INTEGER DEFAULT 0,
    learning INTEGER DEFAULT 0,
    not_started INTEGER DEFAULT 0,
    last_tested TEXT,
    best_score REAL,
    UNIQUE(user_id, pdf_id)
);
```

### assessment_jobs
Background job tracking for assessment creation.

```sql
CREATE TABLE assessment_jobs (
    job_id TEXT PRIMARY KEY,
    parent_pdf_id TEXT NOT NULL,
    user_id TEXT,
    status TEXT NOT NULL,                    -- queued/processing/completed/failed
    current_chunk INTEGER DEFAULT 0,
    total_chunks INTEGER NOT NULL,
    current_batch INTEGER DEFAULT 0,
    total_batches INTEGER DEFAULT 0,
    status_message TEXT,
    total_cards INTEGER DEFAULT 0,
    progress_percentage INTEGER DEFAULT 0,
    error_message TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT
);
```

### processed_topics
Tracks processed topics to avoid duplicates.

```sql
CREATE TABLE processed_topics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_pdf_id TEXT NOT NULL,
    chunk_id INTEGER NOT NULL,
    topic_title TEXT NOT NULL,
    topic_hash TEXT NOT NULL,                -- SHA256 for deduplication
    processed_at TEXT NOT NULL,
    card_count INTEGER DEFAULT 0,
    UNIQUE(parent_pdf_id, topic_hash)
);
```

---

## 4. finance_tracker.db

### bank_accounts
Bank account tracking.

```sql
CREATE TABLE bank_accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    account_name TEXT NOT NULL,
    account_type TEXT NOT NULL,              -- savings/current/fd/rd
    bank_name TEXT NOT NULL,
    account_number TEXT,
    balance REAL DEFAULT 0,
    interest_rate REAL,
    maturity_date TEXT,
    notes TEXT,
    is_active INTEGER DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT
);
```

### balance_history
Historical balance tracking.

```sql
CREATE TABLE balance_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    balance REAL NOT NULL,
    recorded_date TEXT NOT NULL,
    notes TEXT,
    FOREIGN KEY (account_id) REFERENCES bank_accounts(id)
);

CREATE INDEX idx_balance_account ON balance_history(account_id, recorded_date);
```

### assets
Non-liquid assets (real estate, vehicles, etc.).

```sql
CREATE TABLE assets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    asset_name TEXT NOT NULL,
    asset_type TEXT NOT NULL,                -- real_estate/vehicle/gold/other
    purchase_value REAL NOT NULL,
    current_value REAL NOT NULL,
    purchase_date TEXT,
    location TEXT,
    notes TEXT,
    is_active INTEGER DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT
);
```

### asset_value_history
Track asset value changes.

```sql
CREATE TABLE asset_value_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id INTEGER NOT NULL,
    value REAL NOT NULL,
    recorded_date TEXT NOT NULL,
    notes TEXT,
    FOREIGN KEY (asset_id) REFERENCES assets(id)
);
```

### stocks
Stock portfolio.

```sql
CREATE TABLE stocks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    company_name TEXT NOT NULL,
    exchange TEXT DEFAULT 'NSE',
    quantity INTEGER NOT NULL,
    average_price REAL NOT NULL,
    current_price REAL,
    investment_value REAL,
    current_value REAL,
    gain_loss REAL,
    gain_loss_percent REAL,
    last_updated TEXT,
    notes TEXT
);

CREATE INDEX idx_stocks_user ON stocks(user_id);
```

### dividends
Dividend tracking.

```sql
CREATE TABLE dividends (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_id INTEGER NOT NULL,
    dividend_date TEXT NOT NULL,
    amount_per_share REAL NOT NULL,
    total_amount REAL NOT NULL,
    dividend_type TEXT,                      -- interim/final
    FOREIGN KEY (stock_id) REFERENCES stocks(id)
);
```

### liabilities
Loans and debts.

```sql
CREATE TABLE liabilities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    liability_name TEXT NOT NULL,
    liability_type TEXT NOT NULL,            -- home_loan/car_loan/personal_loan/credit_card
    lender TEXT,
    principal_amount REAL NOT NULL,
    outstanding_amount REAL NOT NULL,
    interest_rate REAL,
    emi_amount REAL,
    start_date TEXT,
    end_date TEXT,
    next_payment_date TEXT,
    notes TEXT,
    is_active INTEGER DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT
);
```

### liability_payments
Payment history for liabilities.

```sql
CREATE TABLE liability_payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    liability_id INTEGER NOT NULL,
    payment_date TEXT NOT NULL,
    amount REAL NOT NULL,
    principal_component REAL,
    interest_component REAL,
    notes TEXT,
    FOREIGN KEY (liability_id) REFERENCES liabilities(id)
);
```

### bills
Recurring bills.

```sql
CREATE TABLE bills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    bill_name TEXT NOT NULL,
    category TEXT,                           -- utilities/insurance/subscription/other
    amount REAL NOT NULL,
    due_date TEXT NOT NULL,
    is_recurring INTEGER DEFAULT 0,
    frequency TEXT,                          -- monthly/quarterly/yearly
    last_paid TEXT,
    notes TEXT,
    is_active INTEGER DEFAULT 1,
    calendar_event_id TEXT,                  -- Linked Google Calendar event
    created_at TEXT NOT NULL
);
```

### net_worth_history
Track net worth over time.

```sql
CREATE TABLE net_worth_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    recorded_date TEXT NOT NULL,
    total_assets REAL NOT NULL,
    total_liabilities REAL NOT NULL,
    net_worth REAL NOT NULL,
    breakdown TEXT                           -- JSON details
);

CREATE INDEX idx_networth_date ON net_worth_history(user_id, recorded_date);
```

### mstock_config
mStock API configuration.

```sql
CREATE TABLE mstock_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    api_key TEXT,
    last_sync TEXT,
    sync_enabled INTEGER DEFAULT 0,
    settings TEXT                            -- JSON
);
```

---

## 5. health_tracker.db

### health_profiles
User health profiles.

```sql
CREATE TABLE health_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT UNIQUE NOT NULL,
    date_of_birth TEXT,
    gender TEXT,
    height_cm REAL,
    target_weight_kg REAL,
    activity_level TEXT,                     -- sedentary/light/moderate/active/very_active
    health_conditions TEXT,                  -- JSON array
    created_at TEXT NOT NULL,
    updated_at TEXT
);
```

### weight_log
Weight tracking.

```sql
CREATE TABLE weight_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    recorded_date TEXT NOT NULL,
    weight_kg REAL NOT NULL,
    body_fat_percent REAL,
    muscle_mass_kg REAL,
    notes TEXT,
    UNIQUE(user_id, recorded_date)
);

CREATE INDEX idx_weight_user_date ON weight_log(user_id, recorded_date);
```

### workouts
Workout sessions.

```sql
CREATE TABLE workouts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    workout_date TEXT NOT NULL,
    workout_type TEXT NOT NULL,              -- strength/cardio/yoga/sports/other
    duration_minutes INTEGER NOT NULL,
    calories_burned INTEGER,
    intensity TEXT,                          -- low/medium/high
    notes TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX idx_workouts_user_date ON workouts(user_id, workout_date);
```

### workout_exercises
Individual exercises in a workout.

```sql
CREATE TABLE workout_exercises (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workout_id INTEGER NOT NULL,
    exercise_id INTEGER,
    exercise_name TEXT NOT NULL,
    sets INTEGER,
    reps INTEGER,
    weight_kg REAL,
    duration_seconds INTEGER,
    distance_km REAL,
    notes TEXT,
    FOREIGN KEY (workout_id) REFERENCES workouts(id)
);
```

### exercise_library
Exercise catalog.

```sql
CREATE TABLE exercise_library (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    category TEXT NOT NULL,                  -- upper_body/lower_body/core/cardio/flexibility
    muscle_groups TEXT,                      -- JSON array
    equipment TEXT,
    instructions TEXT,
    is_custom INTEGER DEFAULT 0
);
```

### diet_log
Food and calorie tracking.

```sql
CREATE TABLE diet_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    logged_date TEXT NOT NULL,
    meal_type TEXT NOT NULL,                 -- breakfast/lunch/dinner/snack
    food_name TEXT NOT NULL,
    serving_size TEXT,
    calories INTEGER,
    protein_g REAL,
    carbs_g REAL,
    fat_g REAL,
    fiber_g REAL,
    notes TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX idx_diet_user_date ON diet_log(user_id, logged_date);
```

### blood_reports
Medical blood report tracking.

```sql
CREATE TABLE blood_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    report_date TEXT NOT NULL,
    report_type TEXT NOT NULL,               -- CBC/lipid/thyroid/diabetes/liver/kidney/vitamin
    lab_name TEXT,
    pdf_path TEXT,
    metrics TEXT NOT NULL,                   -- JSON: {name: {value, unit, min, max, status}}
    notes TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX idx_reports_user_date ON blood_reports(user_id, report_date);
```

### health_goals
Health and fitness goals.

```sql
CREATE TABLE health_goals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    goal_type TEXT NOT NULL,                 -- weight/workout_frequency/calories/steps
    target_value REAL NOT NULL,
    current_value REAL,
    target_date TEXT,
    status TEXT DEFAULT 'active',            -- active/achieved/abandoned
    created_at TEXT NOT NULL,
    achieved_at TEXT
);
```

---

## 6. calendar_tracker.db

### google_accounts
Connected Google accounts for calendar.

```sql
CREATE TABLE google_accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    email TEXT NOT NULL,
    access_token TEXT NOT NULL,
    refresh_token TEXT NOT NULL,
    token_expiry TEXT NOT NULL,
    is_primary INTEGER DEFAULT 0,
    last_sync TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(user_id, email)
);
```

### cached_events
Cached calendar events.

```sql
CREATE TABLE cached_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    google_account_id INTEGER NOT NULL,
    event_id TEXT NOT NULL,
    calendar_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    all_day INTEGER DEFAULT 0,
    location TEXT,
    event_type TEXT,                         -- regular/bill_reminder/study_schedule
    raw_data TEXT,                           -- Full JSON from Google
    last_updated TEXT NOT NULL,
    FOREIGN KEY (google_account_id) REFERENCES google_accounts(id)
);

CREATE INDEX idx_events_account ON cached_events(google_account_id);
CREATE INDEX idx_events_time ON cached_events(start_time, end_time);
```

### synced_bill_events
Bill reminders synced to calendar.

```sql
CREATE TABLE synced_bill_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bill_id INTEGER NOT NULL,
    google_account_id INTEGER NOT NULL,
    event_id TEXT NOT NULL,
    calendar_id TEXT NOT NULL,
    last_synced TEXT NOT NULL,
    FOREIGN KEY (google_account_id) REFERENCES google_accounts(id)
);
```

### summary_log
Daily email summary tracking.

```sql
CREATE TABLE summary_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    summary_date TEXT NOT NULL,
    sent_at TEXT NOT NULL,
    recipient_email TEXT NOT NULL,
    summary_type TEXT,                       -- daily/weekly
    content_hash TEXT,                       -- To detect changes
    UNIQUE(user_id, summary_date, summary_type)
);
```

### sync_status
Calendar sync status tracking.

```sql
CREATE TABLE sync_status (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    google_account_id INTEGER NOT NULL,
    last_sync_start TEXT,
    last_sync_end TEXT,
    last_sync_status TEXT,                   -- success/failed/partial
    events_synced INTEGER,
    error_message TEXT,
    FOREIGN KEY (google_account_id) REFERENCES google_accounts(id)
);
```

---

## Database Conventions

### Naming
- Tables: `snake_case`, plural nouns
- Columns: `snake_case`
- Primary keys: `id` (auto-increment) or descriptive like `session_id`
- Foreign keys: `{table_singular}_id`

### Common Columns
- `created_at TEXT` - ISO timestamp when created
- `updated_at TEXT` - ISO timestamp when last updated
- `user_id TEXT` - User identifier (email or username)
- `is_active INTEGER` - Soft delete flag (1=active, 0=deleted)

### Data Types
- Dates: `TEXT` in ISO format (YYYY-MM-DD)
- Timestamps: `TEXT` in ISO format (YYYY-MM-DDTHH:MM:SSZ)
- Booleans: `INTEGER` (0 or 1)
- JSON: `TEXT` (stored as JSON string)
- Currency: `REAL` (floating point)

### Indexes
- Created on frequently queried columns
- Named: `idx_{table}_{column(s)}`
- Compound indexes for common query patterns

---

## Common Queries

### Get user's recent activity
```sql
SELECT * FROM diary_entries
WHERE user_id = 'saanvi'
ORDER BY date DESC LIMIT 10;
```

### Calculate current streak
```sql
SELECT current_streak, longest_streak
FROM subject_streaks
WHERE user_id = 'saanvi' AND subject_name = 'GK';
```

### Get mock test trend
```sql
SELECT test_date, percentage
FROM mock_tests
WHERE user_id = 'saanvi'
ORDER BY test_date;
```

### Calculate net worth
```sql
SELECT
    (SELECT COALESCE(SUM(balance), 0) FROM bank_accounts WHERE user_id = 'arvind' AND is_active = 1) +
    (SELECT COALESCE(SUM(current_value), 0) FROM assets WHERE user_id = 'arvind' AND is_active = 1) +
    (SELECT COALESCE(SUM(current_value), 0) FROM stocks WHERE user_id = 'arvind') -
    (SELECT COALESCE(SUM(outstanding_amount), 0) FROM liabilities WHERE user_id = 'arvind' AND is_active = 1)
AS net_worth;
```

---

*For API documentation, see [API_REFERENCE.md](./API_REFERENCE.md)*
*For architecture overview, see [ARCHITECTURE.md](./ARCHITECTURE.md)*
