-- Migration: Track Chunked PDFs and Original File Deletion
-- Purpose: Keep record of original files that were chunked and optionally deleted

-- Add columns to pdf_chunks table to track if original was deleted
ALTER TABLE pdf_chunks ADD COLUMN original_file_deleted BOOLEAN DEFAULT 0;
ALTER TABLE pdf_chunks ADD COLUMN deletion_timestamp TEXT;
ALTER TABLE pdf_chunks ADD COLUMN original_file_path TEXT;

-- Create index for querying deleted originals
CREATE INDEX IF NOT EXISTS idx_chunks_deleted ON pdf_chunks(parent_pdf_id, original_file_deleted);

-- Add metadata to track chunking settings
ALTER TABLE pdf_chunks ADD COLUMN overlap_enabled BOOLEAN DEFAULT 0;
ALTER TABLE pdf_chunks ADD COLUMN max_pages_per_chunk INTEGER DEFAULT 10;
