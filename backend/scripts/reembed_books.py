#!/usr/bin/env python3
"""
Re-embed books with enriched AI fields.

This script regenerates embeddings for all books that have AI-enriched data
(pacing, tone, themes, moods), so that vector search can find books based
on these attributes, not just title/description.

Usage:
    python scripts/reembed_books.py [--limit N] [--batch-size N]
"""

import sys
import os
import argparse
from pathlib import Path

# Add parent to path so we can import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.database import engine
from app.models import Book
from app.services.embedding import generate_book_embedding


def reembed_books(limit: int = None, batch_size: int = 100):
    """Re-generate embeddings for books with enriched data."""
    
    with Session(engine) as session:
        # Find books that have at least one enriched field
        query = select(Book).where(
            (Book.pacing.isnot(None)) |
            (Book.tone.isnot(None)) |
            (Book.themes.isnot(None)) |
            (Book.mood_tags.isnot(None))
        )
        
        if limit:
            query = query.limit(limit)
        
        books = session.execute(query).scalars().all()
        total = len(books)
        
        print(f"Found {total} books with enriched data to re-embed")
        
        updated = 0
        for i, book in enumerate(books):
            try:
                # Generate new embedding with enriched fields
                new_embedding = generate_book_embedding(book)
                
                # Update in database
                book.embedding = new_embedding
                
                updated += 1
                
                # Commit in batches
                if updated % batch_size == 0:
                    session.commit()
                    print(f"Progress: {updated}/{total} ({100*updated/total:.1f}%)")
                    
            except Exception as e:
                print(f"Error processing book {book.id} ({book.title}): {e}")
                continue
        
        # Final commit
        session.commit()
        print(f"\n✅ Done! Re-embedded {updated}/{total} books.")


def main():
    parser = argparse.ArgumentParser(description="Re-embed books with enriched AI fields")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of books to process")
    parser.add_argument("--batch-size", type=int, default=100, help="Batch size for commits")
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("Re-embedding Books with Enriched AI Fields")
    print("=" * 60)
    print(f"Enriched fields: pacing, tone, themes, moods")
    print()
    
    reembed_books(limit=args.limit, batch_size=args.batch_size)


if __name__ == "__main__":
    main()
