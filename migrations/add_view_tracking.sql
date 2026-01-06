-- Migration: Add PDF view tracking
-- Created: 2026-01-06
-- Purpose: Track when users have scrolled through all pages of a PDF

-- Add view_count column to pdfs table
ALTER TABLE pdfs ADD COLUMN view_count INTEGER DEFAULT 0;

-- Track view sessions (each PDF viewing session)
CREATE TABLE IF NOT EXISTS pdf_view_sessions (
    session_id TEXT PRIMARY KEY,
    pdf_id TEXT NOT NULL,
    user_id TEXT DEFAULT 'system',
    total_pages INTEGER NOT NULL,
    pages_viewed TEXT NOT NULL DEFAULT '[]',  -- JSON array of viewed page numbers
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT,  -- NULL until all pages viewed
    is_complete INTEGER DEFAULT 0,  -- 1 when all pages have been viewed
    FOREIGN KEY (pdf_id) REFERENCES pdfs(filename) ON DELETE CASCADE
);

-- Indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_view_sessions_pdf ON pdf_view_sessions(pdf_id);
CREATE INDEX IF NOT EXISTS idx_view_sessions_complete ON pdf_view_sessions(is_complete);
CREATE INDEX IF NOT EXISTS idx_view_sessions_started ON pdf_view_sessions(started_at DESC);
