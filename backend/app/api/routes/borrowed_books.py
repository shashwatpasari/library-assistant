"""
API routes for borrowed books (active borrows for a user).
"""

from datetime import date, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import db_session_dependency
from app.api.routes.auth import get_current_user
from app.models import Book, BorrowHistory, User
from app.schemas import BookRead
from app.services.borrow import DEFAULT_BORROW_DAYS

router = APIRouter(prefix="/borrowed-books", tags=["borrowed-books"])


class BorrowedBookRead(BaseModel):
    """A borrowed book with borrow metadata."""
    id: int
    book_id: int
    borrowed_at: str
    due_date: str
    returned_at: Optional[str] = None
    book: Optional[BookRead] = None

    class Config:
        from_attributes = True


@router.get("", response_model=List[BorrowedBookRead])
def list_borrowed_books(
    active_only: bool = True,
    session: Session = Depends(db_session_dependency),
    current_user: User = Depends(get_current_user),
) -> List[BorrowedBookRead]:
    """Get all borrowed books for the current user. Defaults to active (unreturned) borrows only."""
    query = select(BorrowHistory).where(BorrowHistory.user_id == current_user.id)
    if active_only:
        query = query.where(BorrowHistory.returned_at.is_(None))
    query = query.order_by(BorrowHistory.borrowed_at.desc())

    borrows = session.scalars(query).all()
    result = []
    for borrow in borrows:
        book = session.get(Book, borrow.book_id)
        due = borrow.borrowed_at.date() + timedelta(days=DEFAULT_BORROW_DAYS)
        result.append(BorrowedBookRead(
            id=borrow.id,
            book_id=borrow.book_id,
            borrowed_at=str(borrow.borrowed_at),
            due_date=str(due),
            returned_at=str(borrow.returned_at) if borrow.returned_at else None,
            book=BookRead.model_validate(book) if book else None,
        ))
    return result


@router.post("/{book_id}")
def borrow_book_endpoint(
    book_id: int,
    session: Session = Depends(db_session_dependency),
    current_user: User = Depends(get_current_user),
):
    """Borrow a book."""
    from app.services.borrow import borrow_book
    success, message = borrow_book(session, user_id=current_user.id, book_id=book_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)
    return {"message": message}

@router.post("/{book_id}/return")
def return_borrowed_book(
    book_id: int,
    session: Session = Depends(db_session_dependency),
    current_user: User = Depends(get_current_user),
):
    """Return a borrowed book."""
    from app.services.borrow import return_book
    success, message = return_book(session, user_id=current_user.id, book_id=book_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)
    return {"message": message}
