"""
API routes for saved books (user's book wishlist/favorites).
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import db_session_dependency
from app.api.routes.auth import get_current_user
from app.models import User
from app.schemas import BookRead, SavedBookRead
from app.services import saved_books as saved_books_service
from app.services import books as book_service

router = APIRouter(prefix="/saved-books", tags=["saved-books"])


@router.get("", response_model=List[SavedBookRead])
def list_saved_books(
    session: Session = Depends(db_session_dependency),
    current_user: User = Depends(get_current_user),
) -> List[SavedBookRead]:
    """Get all saved books for the current user."""
    saved = saved_books_service.get_saved_books(session, user_id=current_user.id)
    result = []
    for sb in saved:
        book = book_service.get_book_or_none(session, book_id=sb.book_id)
        result.append(SavedBookRead(
            id=sb.id,
            user_id=sb.user_id,
            book_id=sb.book_id,
            saved_at=str(sb.saved_at),
            book=BookRead.model_validate(book) if book else None
        ))
    return result


@router.post("/{book_id}", response_model=SavedBookRead)
def save_book(
    book_id: int,
    session: Session = Depends(db_session_dependency),
    current_user: User = Depends(get_current_user),
) -> SavedBookRead:
    """Save a book to user's list."""
    # Check book exists
    book = book_service.get_book_or_none(session, book_id=book_id)
    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Book with id {book_id} not found."
        )
    
    saved = saved_books_service.save_book(session, user_id=current_user.id, book_id=book_id)
    return SavedBookRead(
        id=saved.id,
        user_id=saved.user_id,
        book_id=saved.book_id,
        saved_at=str(saved.saved_at),
        book=BookRead.model_validate(book)
    )


@router.delete("/{book_id}")
def unsave_book(
    book_id: int,
    session: Session = Depends(db_session_dependency),
    current_user: User = Depends(get_current_user),
):
    """Remove a book from user's saved list."""
    deleted = saved_books_service.unsave_book(session, user_id=current_user.id, book_id=book_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Book not in saved list."
        )
    return {"message": "Book removed from saved list"}


@router.get("/{book_id}/check")
def check_if_saved(
    book_id: int,
    session: Session = Depends(db_session_dependency),
    current_user: User = Depends(get_current_user),
):
    """Check if a book is in user's saved list."""
    is_saved = saved_books_service.is_book_saved(session, user_id=current_user.id, book_id=book_id)
    return {"is_saved": is_saved}

