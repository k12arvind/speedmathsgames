-- PDF Annotation System Database Migration
-- Created: 2025-12-27
-- Purpose: Add tables for PDF annotations, revision tracking, and access logging

-- Table 1: Annotation metadata storage
CREATE TABLE IF NOT EXISTS pdf_annotations (
    annotation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    pdf_id TEXT NOT NULL,
    page_number INTEGER NOT NULL,
    annotation_type TEXT NOT NULL,  -- 'highlight', 'underline', 'shape', 'pen'
    annotation_data TEXT NOT NULL,  -- JSON blob from ts-pdf
    created_by TEXT DEFAULT 'system',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT 1,
    FOREIGN KEY (pdf_id) REFERENCES pdfs(filename) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_annotations_pdf ON pdf_annotations(pdf_id, page_number);
CREATE INDEX IF NOT EXISTS idx_annotations_active ON pdf_annotations(pdf_id, is_active);

-- Table 2: Revision tracking with history
CREATE TABLE IF NOT EXISTS pdf_revision_records (
    revision_id INTEGER PRIMARY KEY AUTOINCREMENT,
    pdf_id TEXT NOT NULL,
    revision_number INTEGER NOT NULL,
    revision_type TEXT NOT NULL,  -- 'annotation_added', 'annotation_modified', 'annotation_deleted', 'export'
    timestamp TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    changed_by TEXT DEFAULT 'system',
    change_summary TEXT,
    change_details TEXT,  -- JSON blob with details
    FOREIGN KEY (pdf_id) REFERENCES pdfs(filename) ON DELETE CASCADE,
    UNIQUE(pdf_id, revision_number)
);

CREATE INDEX IF NOT EXISTS idx_revisions_pdf ON pdf_revision_records(pdf_id, timestamp DESC);

-- Table 3: Access logging for analytics
CREATE TABLE IF NOT EXISTS pdf_access_log (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    pdf_id TEXT NOT NULL,
    user_id TEXT DEFAULT 'system',
    access_type TEXT NOT NULL,  -- 'view', 'annotate', 'export', 'view_annotations'
    timestamp TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    duration_seconds INTEGER,
    FOREIGN KEY (pdf_id) REFERENCES pdfs(filename) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_access_pdf ON pdf_access_log(pdf_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_access_type ON pdf_access_log(access_type, timestamp DESC);

-- Extend pdfs table with new columns (these may fail if columns already exist - that's OK)
ALTER TABLE pdfs ADD COLUMN access_count INTEGER DEFAULT 0;
ALTER TABLE pdfs ADD COLUMN edit_count INTEGER DEFAULT 0;
ALTER TABLE pdfs ADD COLUMN annotation_count INTEGER DEFAULT 0;
ALTER TABLE pdfs ADD COLUMN last_accessed TEXT;

-- Verify tables were created
SELECT 'Migration completed successfully. Created tables:' as message;
SELECT name FROM sqlite_master WHERE type='table' AND name IN ('pdf_annotations', 'pdf_revision_records', 'pdf_access_log');
