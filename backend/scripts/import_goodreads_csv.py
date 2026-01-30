"""
Import book data from goodreads_list_books.csv into the SQLite database.

This script:
1. Deletes the existing database
2. Creates a new database with the schema
3. Imports all book records from goodreads_list_books.csv
4. Automatically creates 5 copies per book

Usage:
    cd backend
    source venv/bin/activate
    python -m scripts.import_goodreads_csv \
        --csv scripts/goodreads_list_books.csv \
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
        description="Delete database and import book data from goodreads CSV into SQLite database."
    )
    parser.add_argument(
        "--csv",
        type=Path,
        required=True,
        help="Path to the goodreads CSV file.",
    )
    parser.add_argument(
        "--default-copies",
        type=int,
        default=5,
        help="Number of copies to create per book (default: 5).",
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


def normalize_float(value: Any) -> float | None:
    """Normalize CSV value to float or None."""
    if value is None or value == "":
        return None
    try:
        return float(str(value).strip())
    except (ValueError, TypeError):
        return None


def extract_primary_author(authors_str: str | None) -> str:
    """
    Extract primary author from authors string.
    
    If authors is "Author1, Author2", returns "Author1".
    If empty, returns "Unknown Author".
    """
    if not authors_str:
        return "Unknown Author"
    # Split by comma first, then take first author
    authors = [a.strip() for a in str(authors_str).split(",") if a.strip()]
    if authors:
        # Remove parenthetical info like "(Illustrator)"
        primary = authors[0].split("(")[0].strip()
        return primary if primary else "Unknown Author"
    return "Unknown Author"


def create_book_from_row(row: Dict[str, Any], default_copies: int) -> tuple[Book, list[BookCopy]]:
    """Create a Book and its copies from a CSV row."""
    # Extract primary author for the author field
    authors_str = normalize_value(row.get("authors"))
    primary_author = extract_primary_author(authors_str)
    
    # Use cover_image from CSV
    cover_image_url = normalize_value(row.get("cover_image"))
    
    # Get ISBN - prefer isbn, then isbn10
    isbn = normalize_value(row.get("isbn")) or normalize_value(row.get("isbn10"))
    
    # Handle date_published - convert published date if available
    date_published = normalize_value(row.get("date_published")) or normalize_value(row.get("published"))
    
    book = Book(
        title=normalize_value(row.get("title")) or "Untitled",
        title_long=None,
        author=primary_author,
        authors=authors_str,
        isbn=isbn,
        isbn10=normalize_value(row.get("isbn10")),
        isbn13=None,
        publisher=normalize_value(row.get("publisher")),
        genres=normalize_value(row.get("genres")),
        subjects=None,
        description=None,
        synopsis=normalize_value(row.get("synopsis")),
        language=normalize_value(row.get("language")),
        pages=normalize_int(row.get("pages")),
        rating=normalize_float(row.get("rating")),
        date_published=date_published,
        cover_image_url=cover_image_url,
        image=cover_image_url,
        image_original=None,
    )
    
    # Create default copies
    copies = [
        BookCopy(book=book, status="available", due_date=None)
        for _ in range(default_copies)
    ]
    
    return book, copies


def import_csv_to_db(
    csv_path: Path, default_copies: int, session: Session
) -> tuple[int, int]:
    """
    Import books from CSV into database.
    
    Returns:
        Number of books imported
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")
    
    books_imported = 0
    books_skipped = 0
    
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        
        for row_num, row in enumerate(reader, start=2):  # Start at 2 (row 1 is header)
            try:
                # Check if book already exists by ISBN
                isbn = normalize_value(row.get("isbn")) or normalize_value(row.get("isbn10"))
                if isbn:
                    existing = session.query(Book).filter(Book.isbn == isbn).first()
                    if existing:
                        books_skipped += 1
                        if books_skipped % 100 == 0:
                            print(f"Processed {row_num - 1} rows... (skipped: {books_skipped})")
                        continue
                
                book, copies = create_book_from_row(row, default_copies)
                session.add(book)
                session.add_all(copies)
                books_imported += 1
                
                if books_imported % 100 == 0:
                    session.commit()
                    print(f"Imported {books_imported} books...")
            except Exception as exc:
                print(f"Error importing row {row_num}: {exc}")
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
    
    with get_session() as session:
        # Delete all existing data
        print("Deleting all existing books and copies...")
        deleted_copies = session.query(BookCopy).delete()
        deleted_books = session.query(Book).delete()
        session.commit()
        print(f"✅ Deleted {deleted_books} books and {deleted_copies} copies.")
        
        books_imported, books_skipped = import_csv_to_db(
            args.csv, args.default_copies, session
        )
    
    print(f"\n✅ Import complete!")
    print(f"   Books imported: {books_imported}")
    if books_skipped > 0:
        print(f"   Books skipped (duplicates): {books_skipped}")
    print(f"   Total copies created: {books_imported * args.default_copies}")


if __name__ == "__main__":
    main()

