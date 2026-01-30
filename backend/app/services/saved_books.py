"""
Service layer for saved books operations.
"""

from datetime import datetime
from sqlalchemy import select
from sqlalchemy.orm import Session
from typing import List, Optional

from app.models import SavedBook, Book


def save_book(session: Session, *, user_id: int, book_id: int) -> SavedBook:
    """Save a book for a user. Returns existing if already saved."""
    # Check if already saved
    existing = get_saved_book(session, user_id=user_id, book_id=book_id)
    if existing:
        return existing
    
    saved_book = SavedBook(
        user_id=user_id,
        book_id=book_id,
        saved_at=datetime.utcnow()
    )
    session.add(saved_book)
    session.commit()
    session.refresh(saved_book)
    return saved_book


def unsave_book(session: Session, *, user_id: int, book_id: int) -> bool:
    """Remove a book from user's saved books. Returns True if deleted."""
    saved_book = get_saved_book(session, user_id=user_id, book_id=book_id)
    if saved_book:
        session.delete(saved_book)
        session.commit()
        return True
    return False


def get_saved_book(session: Session, *, user_id: int, book_id: int) -> Optional[SavedBook]:
    """Get a specific saved book entry."""
    stmt = select(SavedBook).where(
        SavedBook.user_id == user_id,
        SavedBook.book_id == book_id
    )
    return session.scalar(stmt)


def get_saved_books(session: Session, *, user_id: int) -> List[SavedBook]:
    """Get all saved books for a user."""
    stmt = select(SavedBook).where(SavedBook.user_id == user_id).order_by(SavedBook.saved_at.desc())
    return list(session.scalars(stmt))


def is_book_saved(session: Session, *, user_id: int, book_id: int) -> bool:
    """Check if a book is saved by a user."""
    return get_saved_book(session, user_id=user_id, book_id=book_id) is not None

