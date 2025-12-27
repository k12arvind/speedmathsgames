-- Migration: Add PDF Chunks Tracking
-- Purpose: Track chunks created from large PDFs for question generation

CREATE TABLE IF NOT EXISTS pdf_chunks (
    chunk_id INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_pdf_id TEXT NOT NULL,
    chunk_filename TEXT NOT NULL UNIQUE,
    chunk_path TEXT NOT NULL,
    chunk_number INTEGER NOT NULL,
    start_page INTEGER NOT NULL,
    end_page INTEGER NOT NULL,
    total_pages INTEGER NOT NULL,
    file_size_kb REAL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    processed_for_questions BOOLEAN DEFAULT 0,
    question_count INTEGER DEFAULT 0,
    FOREIGN KEY (parent_pdf_id) REFERENCES pdfs(filename)
);

CREATE INDEX IF NOT EXISTS idx_chunks_parent ON pdf_chunks(parent_pdf_id);
CREATE INDEX IF NOT EXISTS idx_chunks_processed ON pdf_chunks(processed_for_questions);
