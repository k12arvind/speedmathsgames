-- Migration: Add chunk tracking columns to pdfs table
-- Purpose: Track which PDFs are chunks and which originals have been chunked

-- Add column to mark PDFs that are chunks
ALTER TABLE pdfs ADD COLUMN is_chunk BOOLEAN DEFAULT 0;

-- Add column to store parent PDF filename for chunks
ALTER TABLE pdfs ADD COLUMN parent_pdf TEXT;

-- Add column to mark original PDFs that have been chunked
ALTER TABLE pdfs ADD COLUMN is_chunked BOOLEAN DEFAULT 0;

-- Create indexes for querying
CREATE INDEX IF NOT EXISTS idx_pdfs_chunks ON pdfs(is_chunk, parent_pdf);
CREATE INDEX IF NOT EXISTS idx_pdfs_chunked ON pdfs(is_chunked);
