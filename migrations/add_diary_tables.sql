-- ============================================================
-- DIARY TABLES MIGRATION
-- Add to revision_tracker.db for CLAT preparation daily diary
-- Created: 2025-12-27
-- ============================================================

-- 1. diary_entries - Main journal entries (one per day)
CREATE TABLE IF NOT EXISTS diary_entries (
    entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL DEFAULT 'saanvi',
    entry_date TEXT NOT NULL,  -- YYYY-MM-DD (one entry per day)
    
    -- Free-form journal
    journal_text TEXT,  -- What she did, how she felt, notes
    mood TEXT,  -- 'great', 'good', 'okay', 'tired', 'stressed'
    energy_level INTEGER,  -- 1-5 scale
    
    -- Time tracking
    total_study_hours REAL DEFAULT 0,
    start_time TEXT,  -- When she started studying (HH:MM)
    end_time TEXT,  -- When she finished (HH:MM)
    
    -- Goals
    daily_goal TEXT,  -- What she planned to do
    goal_achieved BOOLEAN DEFAULT 0,
    
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(user_id, entry_date)
);

-- 2. diary_subjects - Track subjects studied each day
CREATE TABLE IF NOT EXISTS diary_subjects (
    subject_id INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id INTEGER NOT NULL,
    subject_name TEXT NOT NULL,  -- 'CLAT GK', 'Math', 'English', etc.
    
    -- Time spent
    time_spent_minutes INTEGER DEFAULT 0,
    
    -- What was covered
    topics_covered TEXT,  -- JSON array of topic names
    
    -- Self-assessment
    confidence_level INTEGER,  -- 1-5: How confident after studying
    difficulty_faced TEXT,  -- Notes on what was hard
    
    -- Linked resources
    pdf_ids TEXT,  -- JSON array of PDF filenames studied
    anki_cards_reviewed INTEGER DEFAULT 0,
    
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (entry_id) REFERENCES diary_entries(entry_id) ON DELETE CASCADE
);

-- 3. subjects_master - Master list of subjects to track
CREATE TABLE IF NOT EXISTS subjects_master (
    subject_id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_name TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL,  -- 'clat_core', 'clat_gk', 'other'
    color TEXT,  -- Hex color for UI
    icon TEXT,  -- Emoji or icon name
    target_hours_weekly REAL DEFAULT 5,  -- Target study hours per week
    is_active BOOLEAN DEFAULT 1,
    display_order INTEGER DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 4. subject_streaks - Track practice streaks and days since last practice
CREATE TABLE IF NOT EXISTS subject_streaks (
    streak_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL DEFAULT 'saanvi',
    subject_name TEXT NOT NULL,
    
    current_streak INTEGER DEFAULT 0,  -- Days in a row practiced
    longest_streak INTEGER DEFAULT 0,  -- Best streak ever
    last_practiced_date TEXT,  -- YYYY-MM-DD
    
    -- Weekly stats (reset every Monday)
    this_week_minutes INTEGER DEFAULT 0,
    last_week_minutes INTEGER DEFAULT 0,
    week_start_date TEXT,  -- Monday of current tracking week
    
    -- Total stats
    total_sessions INTEGER DEFAULT 0,
    total_minutes INTEGER DEFAULT 0,
    
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(user_id, subject_name)
);

-- 5. diary_reminders - Smart reminders for neglected subjects
CREATE TABLE IF NOT EXISTS diary_reminders (
    reminder_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL DEFAULT 'saanvi',
    subject_name TEXT NOT NULL,
    reminder_type TEXT NOT NULL,  -- 'streak_broken', 'days_inactive', 'weekly_target_low'
    message TEXT NOT NULL,
    priority TEXT NOT NULL,  -- 'high', 'medium', 'low'
    is_dismissed BOOLEAN DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    dismissed_at TEXT
);

-- ============================================================
-- INDEXES for performance
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_diary_entries_date ON diary_entries(entry_date DESC);
CREATE INDEX IF NOT EXISTS idx_diary_entries_user ON diary_entries(user_id, entry_date DESC);
CREATE INDEX IF NOT EXISTS idx_diary_subjects_entry ON diary_subjects(entry_id);
CREATE INDEX IF NOT EXISTS idx_diary_subjects_name ON diary_subjects(subject_name);
CREATE INDEX IF NOT EXISTS idx_subject_streaks_user ON subject_streaks(user_id, subject_name);
CREATE INDEX IF NOT EXISTS idx_subject_streaks_practice ON subject_streaks(last_practiced_date DESC);
CREATE INDEX IF NOT EXISTS idx_diary_reminders_active ON diary_reminders(user_id, is_dismissed, priority);

-- ============================================================
-- SEED DATA - Default CLAT subjects
-- ============================================================
INSERT OR IGNORE INTO subjects_master (subject_name, category, color, icon, target_hours_weekly, display_order) VALUES
    ('CLAT GK', 'clat_gk', '#8B5CF6', '📰', 7, 1),
    ('Legal Reasoning', 'clat_core', '#3B82F6', '⚖️', 7, 2),
    ('Logical Reasoning', 'clat_core', '#10B981', '🧩', 5, 3),
    ('English', 'clat_core', '#F59E0B', '📖', 5, 4),
    ('Quantitative Aptitude', 'clat_core', '#EF4444', '🔢', 4, 5),
    ('Current Affairs Reading', 'clat_gk', '#EC4899', '📱', 3, 6),
    ('Mock Tests', 'other', '#6366F1', '📝', 3, 7),
    ('Revision', 'other', '#14B8A6', '🔄', 2, 8);

-- ============================================================
-- VERIFY TABLES CREATED
-- ============================================================
-- Run: SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'diary%' OR name LIKE 'subject%';

