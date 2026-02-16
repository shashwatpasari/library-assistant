-- Migration: Add published_year and full-text search support
-- Date: 2026-02-05
-- Description: Adds published_year INT column for proper year filtering,
--              tsvector column with GIN index for full-text search,
--              and JSONB GIN indexes for themes and moods.

-- ============================================================================
-- 1. Add published_year column
-- ============================================================================

-- Add the column if it doesn't exist
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'books' AND column_name = 'published_year'
    ) THEN
        ALTER TABLE books ADD COLUMN published_year INTEGER;
    END IF;
END $$;

-- Backfill published_year from date_published
UPDATE books 
SET published_year = CAST(SUBSTRING(date_published FROM 1 FOR 4) AS INTEGER)
WHERE published_year IS NULL 
  AND date_published IS NOT NULL 
  AND date_published ~ '^\d{4}';

-- Create index on published_year
CREATE INDEX IF NOT EXISTS ix_books_published_year ON books (published_year);

-- ============================================================================
-- 2. Add tsvector column for full-text search
-- ============================================================================

-- Add tsvector generated column (Postgres 12+)
-- This column is automatically updated when source columns change
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'books' AND column_name = 'tsv'
    ) THEN
        ALTER TABLE books ADD COLUMN tsv tsvector 
        GENERATED ALWAYS AS (
            setweight(to_tsvector('english', COALESCE(title, '')), 'A') ||
            setweight(to_tsvector('english', COALESCE(author, '')), 'B') ||
            setweight(to_tsvector('english', COALESCE(synopsis, '')), 'C') ||
            setweight(to_tsvector('english', COALESCE(subjects, '')), 'D')
        ) STORED;
    END IF;
END $$;

-- Create GIN index for fast full-text search
CREATE INDEX IF NOT EXISTS ix_books_tsv ON books USING GIN (tsv);

-- ============================================================================
-- 3. Add JSONB GIN indexes for themes and moods
-- ============================================================================

-- Index for themes (for faster containment queries)
CREATE INDEX IF NOT EXISTS ix_books_themes ON books USING GIN ((themes::jsonb));

-- Index for mood_tags
CREATE INDEX IF NOT EXISTS ix_books_mood_tags ON books USING GIN ((mood_tags::jsonb));

-- Index for content_warnings (for exclusion filtering)
CREATE INDEX IF NOT EXISTS ix_books_content_warnings ON books USING GIN ((content_warnings::jsonb));

-- ============================================================================
-- 4. Analyze tables for query planner
-- ============================================================================

ANALYZE books;

-- ============================================================================
-- Verification queries (optional - run to verify migration)
-- ============================================================================

-- Check published_year backfill:
-- SELECT COUNT(*) FROM books WHERE published_year IS NOT NULL;

-- Check tsvector column:
-- SELECT title, tsv FROM books LIMIT 5;

-- Test full-text search:
-- SELECT title, ts_rank(tsv, plainto_tsquery('english', 'mystery')) as rank
-- FROM books 
-- WHERE tsv @@ plainto_tsquery('english', 'mystery')
-- ORDER BY rank DESC
-- LIMIT 10;
