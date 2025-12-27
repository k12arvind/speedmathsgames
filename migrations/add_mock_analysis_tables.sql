-- ============================================================
-- MOCK ANALYSIS TABLES
-- For tracking CLAT mock test performance and self-reflection
-- ============================================================

-- Main mock test entries table
CREATE TABLE IF NOT EXISTS mock_tests (
    mock_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL DEFAULT 'saanvi',
    
    -- Mock identification
    mock_name TEXT NOT NULL,           -- e.g., "AILET Mock 1", "CL Full Mock 5"
    mock_source TEXT,                  -- e.g., "Career Launcher", "Legal Edge", "Self-made"
    mock_date DATE NOT NULL,           -- When the mock was taken
    mock_type TEXT DEFAULT 'full',     -- 'full', 'sectional', 'mini'
    
    -- Overall scores
    total_questions INTEGER DEFAULT 150,
    total_attempted INTEGER,
    total_correct INTEGER,
    total_incorrect INTEGER,
    total_unattempted INTEGER,
    total_score REAL,                  -- Actual score (with negative marking)
    max_score REAL DEFAULT 150,        -- Maximum possible score
    percentile REAL,                   -- If available from mock provider
    rank INTEGER,                      -- If available
    
    -- Time tracking
    total_time_minutes INTEGER DEFAULT 120,
    time_taken_minutes INTEGER,
    
    -- Self-reflection
    what_went_well TEXT,               -- Things done well in this mock
    areas_to_improve TEXT,             -- Areas needing improvement
    key_learnings TEXT,                -- Key takeaways
    overall_feeling TEXT,              -- 'confident', 'average', 'struggled', 'disaster'
    difficulty_rating INTEGER,         -- 1-5 scale (1=easy, 5=very hard)
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Section-wise performance for each mock
-- CLAT sections: English, Current Affairs, Legal Reasoning, Logical Reasoning, Quantitative
CREATE TABLE IF NOT EXISTS mock_sections (
    section_id INTEGER PRIMARY KEY AUTOINCREMENT,
    mock_id INTEGER NOT NULL,
    
    -- Section identification
    section_name TEXT NOT NULL,        -- 'English', 'Current Affairs', 'Legal Reasoning', 'Logical Reasoning', 'Quantitative'
    section_order INTEGER,             -- Display order (1-5)
    
    -- Section scores
    questions_total INTEGER,
    questions_attempted INTEGER,
    questions_correct INTEGER,
    questions_incorrect INTEGER,
    questions_unattempted INTEGER,
    section_score REAL,
    max_section_score REAL,
    
    -- Time for this section
    time_allocated_minutes INTEGER,
    time_taken_minutes INTEGER,
    
    -- Section-specific feedback
    section_feedback TEXT,             -- Self-notes for this section
    confidence_level INTEGER,          -- 1-5 scale
    topics_struggled TEXT,             -- JSON array of topics that were difficult
    topics_strong TEXT,                -- JSON array of topics that went well
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (mock_id) REFERENCES mock_tests(mock_id) ON DELETE CASCADE
);

-- Indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_mock_tests_user_date ON mock_tests(user_id, mock_date DESC);
CREATE INDEX IF NOT EXISTS idx_mock_tests_user ON mock_tests(user_id);
CREATE INDEX IF NOT EXISTS idx_mock_sections_mock ON mock_sections(mock_id);

-- Default CLAT section configuration
CREATE TABLE IF NOT EXISTS clat_section_config (
    config_id INTEGER PRIMARY KEY AUTOINCREMENT,
    section_name TEXT NOT NULL UNIQUE,
    section_order INTEGER,
    default_questions INTEGER,
    default_max_score REAL,
    default_time_minutes INTEGER,
    color TEXT,                        -- For UI display
    icon TEXT                          -- Emoji for UI
);

-- Insert default CLAT section configuration
INSERT OR IGNORE INTO clat_section_config (section_name, section_order, default_questions, default_max_score, default_time_minutes, color, icon) VALUES
    ('English', 1, 28, 28, 20, '#3B82F6', '📖'),
    ('Current Affairs', 2, 35, 35, 25, '#8B5CF6', '📰'),
    ('Legal Reasoning', 3, 35, 35, 30, '#10B981', '⚖️'),
    ('Logical Reasoning', 4, 28, 28, 25, '#F59E0B', '🧩'),
    ('Quantitative', 5, 14, 14, 20, '#EF4444', '🔢');

-- ============================================================
-- VIEWS FOR ANALYTICS
-- ============================================================

-- View: Mock summary with section scores
CREATE VIEW IF NOT EXISTS v_mock_summary AS
SELECT 
    m.mock_id,
    m.user_id,
    m.mock_name,
    m.mock_source,
    m.mock_date,
    m.total_score,
    m.max_score,
    m.total_attempted,
    m.total_correct,
    m.total_incorrect,
    m.time_taken_minutes,
    m.overall_feeling,
    m.difficulty_rating,
    ROUND((m.total_score * 100.0 / NULLIF(m.max_score, 0)), 1) as score_percentage,
    ROUND((m.total_correct * 100.0 / NULLIF(m.total_attempted, 0)), 1) as accuracy,
    (SELECT GROUP_CONCAT(ms.section_name || ':' || ms.section_score, ', ')
     FROM mock_sections ms WHERE ms.mock_id = m.mock_id
     ORDER BY ms.section_order) as section_scores
FROM mock_tests m;

-- View: Section-wise average performance
CREATE VIEW IF NOT EXISTS v_section_averages AS
SELECT 
    ms.section_name,
    COUNT(*) as mock_count,
    ROUND(AVG(ms.section_score), 1) as avg_score,
    ROUND(AVG(ms.questions_correct * 100.0 / NULLIF(ms.questions_attempted, 0)), 1) as avg_accuracy,
    ROUND(AVG(ms.time_taken_minutes), 0) as avg_time,
    ROUND(AVG(ms.confidence_level), 1) as avg_confidence
FROM mock_sections ms
JOIN mock_tests m ON ms.mock_id = m.mock_id
GROUP BY ms.section_name
ORDER BY (SELECT section_order FROM clat_section_config WHERE section_name = ms.section_name);

