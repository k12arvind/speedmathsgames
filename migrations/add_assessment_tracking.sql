-- Migration: Add Assessment Tracking
-- Purpose: Track assessment creation per chunk and detect duplicate topics from overlapping pages
-- Created: 2025-12-27

-- Add columns to pdf_chunks table to track assessment creation
ALTER TABLE pdf_chunks ADD COLUMN assessment_created BOOLEAN DEFAULT 0;
ALTER TABLE pdf_chunks ADD COLUMN assessment_card_count INTEGER DEFAULT 0;
ALTER TABLE pdf_chunks ADD COLUMN assessment_created_at TEXT;

-- Create new table for tracking processed topics (duplicate detection)
CREATE TABLE IF NOT EXISTS processed_topics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_pdf_id TEXT NOT NULL,
    chunk_id INTEGER NOT NULL,
    topic_title TEXT NOT NULL,
    topic_hash TEXT NOT NULL,  -- SHA256 hash of normalized topic content
    processed_at TEXT NOT NULL,
    card_count INTEGER DEFAULT 0,
    UNIQUE(parent_pdf_id, topic_hash)  -- Prevent duplicate topics across chunks
);

-- Create index for fast duplicate lookups
CREATE INDEX IF NOT EXISTS idx_topics_hash ON processed_topics(parent_pdf_id, topic_hash);
CREATE INDEX IF NOT EXISTS idx_topics_chunk ON processed_topics(chunk_id);

-- Create table for tracking assessment jobs
CREATE TABLE IF NOT EXISTS assessment_jobs (
    job_id TEXT PRIMARY KEY,
    parent_pdf_id TEXT NOT NULL,
    status TEXT NOT NULL,  -- queued, processing, completed, failed
    current_chunk INTEGER DEFAULT 0,
    total_chunks INTEGER NOT NULL,
    current_batch INTEGER DEFAULT 0,
    total_batches INTEGER DEFAULT 0,
    status_message TEXT,
    total_cards INTEGER DEFAULT 0,
    progress_percentage INTEGER DEFAULT 0,
    error_message TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Create index for job queries
CREATE INDEX IF NOT EXISTS idx_jobs_pdf ON assessment_jobs(parent_pdf_id);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON assessment_jobs(status);
