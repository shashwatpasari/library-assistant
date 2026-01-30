"""
API routes for reading lists.
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import db_session_dependency
from app.api.dependencies import get_current_user
from app.models import User
from app.schemas import ReadingListCreate, ReadingListRead, ReadingListItemCreate, ReadingListItemRead
from app.services import reading_lists as reading_list_service
from app.services import books as book_service

router = APIRouter(prefix="/reading-lists", tags=["reading-lists"])


@router.post("/", response_model=ReadingListRead)
def create_reading_list(
    data: ReadingListCreate,
    session: Session = Depends(db_session_dependency),
    current_user: User = Depends(get_current_user),
):
    """Create a new named reading list."""
    return reading_list_service.create_reading_list(
        session, user_id=current_user.id, name=data.name
    )


@router.get("/", response_model=List[ReadingListRead])
def get_my_reading_lists(
    session: Session = Depends(db_session_dependency),
    current_user: User = Depends(get_current_user),
):
    """Get all reading lists for the current user."""
    return reading_list_service.get_user_reading_lists(session, user_id=current_user.id)


@router.get("/{list_id}", response_model=ReadingListRead)
def get_reading_list(
    list_id: int,
    session: Session = Depends(db_session_dependency),
    current_user: User = Depends(get_current_user),
):
    """Get a specific reading list."""
    reading_list = reading_list_service.get_reading_list(
        session, user_id=current_user.id, list_id=list_id
    )
    if not reading_list:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reading list not found"
        )
    return reading_list


@router.delete("/{list_id}")
def delete_reading_list(
    list_id: int,
    session: Session = Depends(db_session_dependency),
    current_user: User = Depends(get_current_user),
):
    """Delete a reading list."""
    deleted = reading_list_service.delete_reading_list(
        session, user_id=current_user.id, list_id=list_id
    )
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reading list not found"
        )
    return {"message": "Reading list deleted"}


@router.post("/{list_id}/items", response_model=ReadingListItemRead)
def add_book_to_list(
    list_id: int,
    data: ReadingListItemCreate,
    session: Session = Depends(db_session_dependency),
    current_user: User = Depends(get_current_user),
):
    """Add a book to a reading list."""
    # Verify book exists
    book = book_service.get_book_or_none(session, book_id=data.book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    item = reading_list_service.add_book_to_list(
        session, user_id=current_user.id, list_id=list_id, book_id=data.book_id
    )
    if not item:
        raise HTTPException(status_code=404, detail="Reading list not found")
        
    return item


@router.delete("/{list_id}/items/{book_id}")
def remove_book_from_list(
    list_id: int,
    book_id: int,
    session: Session = Depends(db_session_dependency),
    current_user: User = Depends(get_current_user),
):
    """Remove a book from a reading list."""
    removed = reading_list_service.remove_book_from_list(
        session, user_id=current_user.id, list_id=list_id, book_id=book_id
    )
    if not removed:
        raise HTTPException(status_code=404, detail="Item not found in reading list")
        
    return {"message": "Book removed from list"}
