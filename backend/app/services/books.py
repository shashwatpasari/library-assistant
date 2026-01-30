"""
Business logic for book related operations.
"""

from __future__ import annotations

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.models import Book, BookCopy
from app.schemas import BookAvailability


def search_books(
    session: Session,
    *,
    title_query: str | None = None,
    author_query: str | None = None,
    isbn: str | None = None,
    limit: int = 50,
) -> list[Book]:
    """
    Search for books matching the supplied title, author, or ISBN.

    Title and author searches perform a case-insensitive partial match. ISBN search is an exact match.
    When both title_query and author_query are provided, uses OR logic to match either field.
    """
    from sqlalchemy import or_
    
    stmt: Select[tuple[Book]] = select(Book)

    # Build search conditions
    conditions = []
    
    if title_query:
        conditions.append(Book.title.ilike(f"%{title_query.strip()}%"))
    
    if author_query:
        # Search in both author and authors fields
        author_pattern = f"%{author_query.strip()}%"
        conditions.append(
            or_(
                Book.author.ilike(author_pattern),
                Book.authors.ilike(author_pattern)
            )
        )

    if isbn:
        conditions.append(Book.isbn == isbn.strip())
    
    # Apply conditions with OR logic if multiple exist
    if conditions:
        if len(conditions) > 1:
            stmt = stmt.where(or_(*conditions))
        else:
            stmt = stmt.where(conditions[0])

    stmt = stmt.order_by(Book.title.asc()).limit(limit)

    return list(session.scalars(stmt))


def count_books(
    session: Session,
    *,
    subject: str | None = None,
    genre: str | None = None,
) -> int:
    """
    Count total books with optional filtering.
    """
    stmt: Select[tuple[int]] = select(func.count(Book.id))
    
    if subject:
        stmt = stmt.where(Book.subjects.ilike(f"%{subject.strip()}%"))
    
    if genre:
        stmt = stmt.where(Book.genres.ilike(f"%{genre.strip()}%"))
    
    return session.scalar(stmt) or 0


def list_books(
    session: Session,
    *,
    skip: int = 0,
    limit: int = 50,
    subject: str | None = None,
    genre: str | None = None,
) -> list[Book]:
    """
    List books with optional filtering and pagination.
    """
    stmt: Select[tuple[Book]] = select(Book)
    
    if subject:
        stmt = stmt.where(Book.subjects.ilike(f"%{subject.strip()}%"))
    
    if genre:
        stmt = stmt.where(Book.genres.ilike(f"%{genre.strip()}%"))
    
    stmt = stmt.order_by(Book.title.asc()).offset(skip).limit(limit)
    
    return list(session.scalars(stmt))


def get_book_or_none(session: Session, *, book_id: int) -> Book | None:
    """Return a book by id or None if not found."""
    stmt: Select[tuple[Book]] = select(Book).where(Book.id == book_id)
    return session.scalar(stmt)


def get_top_genres(session: Session, *, limit: int = 10) -> list[tuple[str, int]]:
    """
    Get the top N most common genres from all books.
    Returns a list of tuples: (genre_name, book_count)
    """
    # Get all books with genres
    books = session.scalars(select(Book).where(Book.genres.is_not(None))).all()
    
    # Count genres (genres are comma-separated)
    genre_counts = {}
    for book in books:
        if book.genres:
            # Split by comma and clean up
            genres = [g.strip() for g in book.genres.split(',') if g.strip()]
            for genre in genres:
                genre_counts[genre] = genre_counts.get(genre, 0) + 1
    
    # Sort by count (descending) and return top N
    sorted_genres = sorted(genre_counts.items(), key=lambda x: x[1], reverse=True)
    return sorted_genres[:limit]


def get_book_availability(session: Session, *, book_id: int) -> BookAvailability:
    """
    Compute availability metrics for a given book.
    """
    total_copies_stmt = select(func.count(BookCopy.id)).where(BookCopy.book_id == book_id)
    available_copies_stmt = select(func.count(BookCopy.id)).where(
        BookCopy.book_id == book_id, BookCopy.status == "available"
    )
    earliest_due_date_stmt = (
        select(func.min(BookCopy.due_date))
        .where(BookCopy.book_id == book_id, BookCopy.status == "issued")
        .where(BookCopy.due_date.is_not(None))
    )

    total_copies = session.scalar(total_copies_stmt) or 0
    available_copies = session.scalar(available_copies_stmt) or 0
    earliest_due_date = session.scalar(earliest_due_date_stmt)

    return BookAvailability(
        book_id=book_id,
        total_copies=total_copies,
        available_copies=available_copies,
        earliest_due_date=earliest_due_date,
    )


