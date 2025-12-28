-- Migration: Add questions table for local storage of assessment questions
-- This makes the system independent of AnkiConnect for tests
-- Date: 2025-12-27

-- Questions table - stores all generated questions tagged to PDF filename
CREATE TABLE IF NOT EXISTS questions (
    question_id INTEGER PRIMARY KEY AUTOINCREMENT,
    pdf_filename TEXT NOT NULL,           -- The PDF this question belongs to (KEY for lookups)
    anki_note_id TEXT,                    -- Optional: Anki note ID for reference
    question_text TEXT NOT NULL,          -- The question (front of card)
    answer_text TEXT NOT NULL,            -- The answer (back of card)
    category TEXT,                        -- Topic category (e.g., "Economy & Business")
    deck_name TEXT,                       -- Original deck name
    source_name TEXT,                     -- Source (career_launcher, legaledge)
    week_tag TEXT,                        -- Week tag (2025_Dec_W2)
    tags TEXT,                            -- JSON array of all tags
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- MCQ choices for questions (generated once, reused)
CREATE TABLE IF NOT EXISTS question_choices (
    choice_id INTEGER PRIMARY KEY AUTOINCREMENT,
    question_id INTEGER NOT NULL,
    choices TEXT NOT NULL,                -- JSON array of 4 choices
    correct_index INTEGER NOT NULL,       -- Index of correct answer (0-3)
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (question_id) REFERENCES questions(question_id) ON DELETE CASCADE
);

-- Indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_questions_pdf ON questions(pdf_filename);
CREATE INDEX IF NOT EXISTS idx_questions_category ON questions(category);
CREATE INDEX IF NOT EXISTS idx_questions_source ON questions(source_name);
CREATE INDEX IF NOT EXISTS idx_question_choices_qid ON question_choices(question_id);

-- Unique constraint to prevent duplicate questions per PDF
CREATE UNIQUE INDEX IF NOT EXISTS idx_questions_unique 
ON questions(pdf_filename, question_text);

