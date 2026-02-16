-- Migration: Add collaborative filtering columns and tables
-- Date: 2026-02-15

-- Add new vector columns to books
ALTER TABLE books ADD COLUMN IF NOT EXISTS feature_vector vector(128);
ALTER TABLE books ADD COLUMN IF NOT EXISTS collaborative_embedding vector(50);
ALTER TABLE books ADD COLUMN IF NOT EXISTS popularity_score FLOAT DEFAULT 0.0;

-- Create borrow_history table
CREATE TABLE IF NOT EXISTS borrow_history (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    borrowed_at TIMESTAMP NOT NULL DEFAULT NOW(),
    returned_at TIMESTAMP,
    rating FLOAT
);

CREATE INDEX IF NOT EXISTS idx_borrow_history_user_id ON borrow_history(user_id);
CREATE INDEX IF NOT EXISTS idx_borrow_history_book_id ON borrow_history(book_id);
ALTER TABLE borrow_history ADD CONSTRAINT uq_borrow_history UNIQUE (user_id, book_id, borrowed_at);

-- Create user_interactions table
CREATE TABLE IF NOT EXISTS user_interactions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE UNIQUE,
    interaction_count INTEGER DEFAULT 0,
    preference_vector vector(128),
    collaborative_embedding vector(50),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_interactions_user_id ON user_interactions(user_id);

-- Create indexes for vector similarity search
CREATE INDEX IF NOT EXISTS idx_books_feature_vector ON books USING ivfflat (feature_vector vector_cosine_ops) WITH (lists = 20);
CREATE INDEX IF NOT EXISTS idx_books_collab_embedding ON books USING ivfflat (collaborative_embedding vector_cosine_ops) WITH (lists = 20);
