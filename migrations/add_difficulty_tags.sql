-- Migration: Add Question Difficulty Tags
-- Purpose: Track per-user difficulty ratings for questions based on answer history
-- Date: 2026-01-08

-- Create the question_difficulty_tags table
CREATE TABLE IF NOT EXISTS question_difficulty_tags (
    tag_id INTEGER PRIMARY KEY AUTOINCREMENT,
    anki_note_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    difficulty_tag TEXT DEFAULT 'not_attempted',  -- easy/medium/difficult/very_difficult/not_attempted
    total_attempts INTEGER DEFAULT 0,
    correct_attempts INTEGER DEFAULT 0,
    last_attempt_at TEXT,
    last_correct_at TEXT,
    last_wrong_at TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(anki_note_id, user_id)
);

-- Index for efficient queries by user and difficulty
CREATE INDEX IF NOT EXISTS idx_difficulty_user_tag ON question_difficulty_tags(user_id, difficulty_tag);

-- Index for looking up specific question for a user
CREATE INDEX IF NOT EXISTS idx_difficulty_note_user ON question_difficulty_tags(anki_note_id, user_id);

-- Backfill from existing question_attempts data
-- This populates difficulty tags for all questions that have been attempted
INSERT OR REPLACE INTO question_difficulty_tags (
    anki_note_id,
    user_id,
    difficulty_tag,
    total_attempts,
    correct_attempts,
    last_attempt_at,
    last_correct_at,
    last_wrong_at,
    created_at,
    updated_at
)
SELECT
    qa.anki_note_id,
    ts.user_id,
    CASE
        WHEN COUNT(*) >= 2 AND SUM(qa.is_correct) = COUNT(*) THEN 'easy'
        WHEN COUNT(*) = 1 AND SUM(qa.is_correct) = 1 THEN 'easy'
        WHEN CAST(SUM(qa.is_correct) AS FLOAT) / COUNT(*) >= 0.6 THEN 'medium'
        WHEN CAST(SUM(qa.is_correct) AS FLOAT) / COUNT(*) >= 0.3 THEN 'difficult'
        ELSE 'very_difficult'
    END as difficulty_tag,
    COUNT(*) as total_attempts,
    SUM(qa.is_correct) as correct_attempts,
    MAX(qa.answered_at) as last_attempt_at,
    MAX(CASE WHEN qa.is_correct = 1 THEN qa.answered_at ELSE NULL END) as last_correct_at,
    MAX(CASE WHEN qa.is_correct = 0 THEN qa.answered_at ELSE NULL END) as last_wrong_at,
    MIN(qa.answered_at) as created_at,
    MAX(qa.answered_at) as updated_at
FROM question_attempts qa
JOIN test_sessions ts ON qa.session_id = ts.session_id
WHERE qa.anki_note_id IS NOT NULL AND qa.anki_note_id != ''
GROUP BY qa.anki_note_id, ts.user_id;
