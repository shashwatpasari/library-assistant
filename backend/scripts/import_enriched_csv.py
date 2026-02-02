"""
Import enriched book data from CSV into the SQLite database.

This script reads the enriched CSV file (from ISBNdb API) and imports all
book records into the database. It automatically creates 5 copies per book
as specified in the requirements.

Usage:
    cd backend
    source venv/bin/activate
    python -m scripts.import_enriched_csv \
        --csv scripts/books_isbndb_enriched.csv \
        --default-copies 5
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any, Dict

from sqlalchemy.orm import Session

from app.database import engine, get_session
from app.models import Base, Book, BookCopy


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Import enriched book data from CSV into SQLite database."
    )
    parser.add_argument(
        "--csv",
        type=Path,
        required=True,
        help="Path to the enriched CSV file.",
    )
    parser.add_argument(
        "--default-copies",
        type=int,
        default=5,
        help="Number of copies to create per book (default: 5).",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip books that already exist in the database (by ISBN).",
    )
    return parser.parse_args()


def normalize_value(value: Any) -> str | None:
    """Normalize CSV value to string or None."""
    if value is None or value == "":
        return None
    return str(value).strip() or None


def normalize_int(value: Any) -> int | None:
    """Normalize CSV value to integer or None."""
    if value is None or value == "":
        return None
    try:
        return int(float(str(value).strip()))
    except (ValueError, TypeError):
        return None


def extract_primary_author(authors_str: str | None) -> str:
    """
    Extract primary author from authors string.
    
    If authors is "Author1; Author2", returns "Author1".
    If empty, returns "Unknown Author".
    """
    if not authors_str:
        return "Unknown Author"
    # Split by semicolon and take first
    authors = [a.strip() for a in str(authors_str).split(";") if a.strip()]
    return authors[0] if authors else "Unknown Author"


def create_book_from_row(row: Dict[str, Any], default_copies: int) -> tuple[Book, list[BookCopy]]:
    """Create a Book and its copies from a CSV row."""
    # Extract primary author for the author field
    authors_str = normalize_value(row.get("authors"))
    primary_author = extract_primary_author(authors_str)
    
    # Use image_original if available, otherwise image, otherwise cover_image_url
    image_url = (
        normalize_value(row.get("image_original"))
        or normalize_value(row.get("image"))
        or normalize_value(row.get("cover_image_url"))
    )
    
    book = Book(
        title=normalize_value(row.get("title")) or "Untitled",
        title_long=normalize_value(row.get("title_long")),
        author=primary_author,
        authors=authors_str,
        isbn=normalize_value(row.get("isbn")),
        isbn10=normalize_value(row.get("isbn10")),
        isbn13=normalize_value(row.get("isbn13")),
        publisher=normalize_value(row.get("publisher")),
        genres=normalize_value(row.get("genres")),
        subjects=normalize_value(row.get("subjects")),
        description=normalize_value(row.get("description")),
        synopsis=normalize_value(row.get("synopsis")),
        language=normalize_value(row.get("language")),
        pages=normalize_int(row.get("pages")),
        date_published=normalize_value(row.get("date_published")),
        cover_image_url=image_url,
        image=normalize_value(row.get("image")),
        image_original=normalize_value(row.get("image_original")),
    )
    
    # Create default copies
    copies = [
        BookCopy(book=book, status="available", due_date=None)
        for _ in range(default_copies)
    ]
    
    return book, copies


def import_csv_to_db(
    csv_path: Path, default_copies: int, skip_existing: bool, session: Session
) -> tuple[int, int]:
    """
    Import books from CSV into database.
    
    Returns:
        Tuple of (books_imported, books_skipped)
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")
    
    books_imported = 0
    books_skipped = 0
    
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        
        for row_num, row in enumerate(reader, start=2):  # Start at 2 (row 1 is header)
            isbn = normalize_value(row.get("isbn"))
            
            # Check if book already exists (if skip_existing is enabled)
            if skip_existing and isbn:
                existing = session.query(Book).filter(Book.isbn == isbn).first()
                if existing:
                    books_skipped += 1
                    if (row_num - 1) % 100 == 0:
                        print(f"Processed {row_num - 1} rows... (skipped: {books_skipped})")
                    continue
            
            try:
                book, copies = create_book_from_row(row, default_copies)
                session.add(book)
                session.add_all(copies)
                books_imported += 1
                
                if books_imported % 100 == 0:
                    session.commit()
                    print(f"Imported {books_imported} books...")
            except Exception as exc:
                print(f"Error importing row {row_num} (ISBN: {isbn}): {exc}")
                session.rollback()
                continue
    
    session.commit()
    return books_imported, books_skipped


def main() -> None:
    """Entry point for the import script."""
    args = parse_args()
    
    # Ensure database tables exist
    Base.metadata.create_all(bind=engine)
    
    print(f"Importing books from: {args.csv}")
    print(f"Default copies per book: {args.default_copies}")
    if args.skip_existing:
        print("Skipping books that already exist in database.")
    
    with get_session() as session:
        books_imported, books_skipped = import_csv_to_db(
            args.csv, args.default_copies, args.skip_existing, session
        )
    
    print(f"\n✅ Import complete!")
    print(f"   Books imported: {books_imported}")
    print(f"   Books skipped: {books_skipped}")
    print(f"   Total copies created: {books_imported * args.default_copies}")


if __name__ == "__main__":
    main()

