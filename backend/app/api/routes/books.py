"""
Routers providing book catalogue endpoints.
"""

from __future__ import annotations

from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import db_session_dependency
from app.schemas import BookAvailability, BookRead
from app.services import books as book_service

router = APIRouter(prefix="/books", tags=["books"])


@router.get("/count", response_model=int)
def count_books(
    *,
    session: Session = Depends(db_session_dependency),
    subject: str | None = Query(default=None, description="Filter by subject (case-insensitive partial match)"),
    genre: str | None = Query(default=None, description="Filter by genre (case-insensitive partial match)"),
) -> int:
    """
    Get total count of books with optional filtering.
    """
    return book_service.count_books(session, subject=subject, genre=genre)


@router.get("", response_model=List[BookRead])
def list_books(
    *,
    session: Session = Depends(db_session_dependency),
    skip: int = Query(default=0, ge=0, description="Number of records to skip"),
    limit: int = Query(default=50, ge=1, le=100, description="Maximum number of records to return"),
    subject: str | None = Query(default=None, description="Filter by subject (case-insensitive partial match)"),
    genre: str | None = Query(default=None, description="Filter by genre (case-insensitive partial match)"),
) -> list[BookRead]:
    """
    List books with optional filtering and pagination.
    """
    books = book_service.list_books(
        session, skip=skip, limit=limit, subject=subject, genre=genre
    )
    return [BookRead.model_validate(book) for book in books]


@router.get("/search", response_model=List[BookRead])
def search_books(
    *,
    session: Session = Depends(db_session_dependency),
    q: str | None = Query(default=None, description="Search query for both title and author (autocomplete)"),
    title: str | None = Query(default=None, description="Partial title to match"),
    author: str | None = Query(default=None, description="Partial author name to match"),
    isbn: str | None = Query(default=None, description="Exact ISBN to match"),
    limit: int = Query(default=50, ge=1, le=100, description="Maximum number of results to return"),
) -> list[BookRead]:
    """
    Search books by title, author, or ISBN.

    Title and author matches are case-insensitive and partial; ISBN matches are exact.
    Use 'q' parameter for autocomplete (searches both title and author).
    Use specific parameters (title, author, isbn) for targeted searches.
    """
    # If 'q' is provided, use it for both title and author search
    if q:
        title_query = q
        author_query = q
    else:
        title_query = title
        author_query = author
    
    if not any([title_query, author_query, isbn]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide at least one search parameter (q, title, author, or isbn).",
        )

    books = book_service.search_books(
        session,
        title_query=title_query,
        author_query=author_query,
        isbn=isbn,
        limit=limit,
    )
    return [BookRead.model_validate(book) for book in books]


@router.get("/genres/top", response_model=List[dict[str, Any]])
def get_top_genres(
    session: Session = Depends(db_session_dependency),
    limit: int = Query(default=10, ge=1, le=50, description="Number of top genres to return"),
) -> list[dict[str, Any]]:
    """
    Get the top N most common genres.
    Returns a list of dictionaries with 'genre' and 'count' keys.
    """
    top_genres = book_service.get_top_genres(session, limit=limit)
    return [{"genre": genre, "count": count} for genre, count in top_genres]


@router.get("/{book_id}", response_model=BookRead)
def get_book(
    book_id: int,
    session: Session = Depends(db_session_dependency),
) -> BookRead:
    """
    Get a single book by ID.
    """
    book = book_service.get_book_or_none(session, book_id=book_id)
    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Book with id {book_id} not found.",
        )
    return BookRead.model_validate(book)


@router.get("/{book_id}/availability", response_model=BookAvailability)
def get_book_availability(
    book_id: int,
    session: Session = Depends(db_session_dependency),
) -> BookAvailability:
    """
    Return aggregated availability information for a given book.
    """
    book = book_service.get_book_or_none(session, book_id=book_id)
    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Book with id {book_id} not found.",
        )

    return book_service.get_book_availability(session, book_id=book_id)


