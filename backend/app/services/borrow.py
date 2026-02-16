"""
Borrow service — handles book borrowing and returning.
"""

from datetime import datetime, timedelta, date
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Book, BookCopy, BorrowHistory


DEFAULT_BORROW_DAYS = 14


def borrow_book(session: Session, user_id: int, book_id: int) -> tuple[bool, str]:
    """
    Borrow a book for a user.

    Finds an available BookCopy, marks it as issued, creates a BorrowHistory record.
    Returns (success: bool, message: str).
    """
    # Check if the book exists
    book = session.get(Book, book_id)
    if not book:
        return False, "I couldn't find that book in our system."

    # Check if user already has an active borrow for this book
    existing = session.scalars(
        select(BorrowHistory).where(
            BorrowHistory.user_id == user_id,
            BorrowHistory.book_id == book_id,
            BorrowHistory.returned_at.is_(None),
        )
    ).first()
    if existing:
        return False, f"You already have **{book.title}** checked out. It's due on {existing.borrowed_at.date() + timedelta(days=DEFAULT_BORROW_DAYS)}."

    # Find an available copy
    available_copy = session.scalars(
        select(BookCopy).where(
            BookCopy.book_id == book_id,
            BookCopy.status == "available",
        )
    ).first()

    if not available_copy:
        return False, f"Sorry, all copies of **{book.title}** are currently checked out. Would you like me to recommend something similar?"

    # Issue the copy
    due = date.today() + timedelta(days=DEFAULT_BORROW_DAYS)
    available_copy.status = "issued"
    available_copy.due_date = due

    # Create borrow history
    borrow = BorrowHistory(
        user_id=user_id,
        book_id=book_id,
        borrowed_at=datetime.utcnow(),
    )
    session.add(borrow)
    session.commit()

    return True, f"✓ You've borrowed **{book.title}**! It's due back on {due.strftime('%B %d, %Y')}. Enjoy your read! 📚"


def return_book(session: Session, user_id: int, book_id: int) -> tuple[bool, str]:
    """
    Return a borrowed book.

    Sets the BookCopy back to available and records the return time.
    Returns (success: bool, message: str).
    """
    book = session.get(Book, book_id)
    if not book:
        return False, "I couldn't find that book in our system."

    # Find the active borrow record
    active_borrow = session.scalars(
        select(BorrowHistory).where(
            BorrowHistory.user_id == user_id,
            BorrowHistory.book_id == book_id,
            BorrowHistory.returned_at.is_(None),
        )
    ).first()

    if not active_borrow:
        return False, f"You don't have **{book.title}** checked out."

    # Mark as returned
    active_borrow.returned_at = datetime.utcnow()

    # Find the issued copy and make it available again
    issued_copy = session.scalars(
        select(BookCopy).where(
            BookCopy.book_id == book_id,
            BookCopy.status == "issued",
        )
    ).first()

    if issued_copy:
        issued_copy.status = "available"
        issued_copy.due_date = None

    session.commit()

    return True, f"✓ You've returned **{book.title}**. Thanks for reading! 📖"
