"""
Service layer for reading list operations.
"""
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional

from app.models import ReadingList, ReadingListItem

def create_reading_list(session: Session, *, user_id: int, name: str) -> ReadingList:
    """Create a new named reading list."""
    reading_list = ReadingList(user_id=user_id, name=name)
    session.add(reading_list)
    session.commit()
    session.refresh(reading_list)
    return reading_list

def get_user_reading_lists(session: Session, *, user_id: int) -> List[ReadingList]:
    """Get all reading lists for a user, including their items."""
    stmt = (
        select(ReadingList)
        .where(ReadingList.user_id == user_id)
        .options(joinedload(ReadingList.items).joinedload(ReadingListItem.book))
        .order_by(ReadingList.created_at.desc())
    )
    return list(session.scalars(stmt).unique())

def get_reading_list(session: Session, *, user_id: int, list_id: int) -> Optional[ReadingList]:
    """Get a specific reading list by ID for a user."""
    stmt = (
        select(ReadingList)
        .where(ReadingList.id == list_id, ReadingList.user_id == user_id)
        .options(joinedload(ReadingList.items).joinedload(ReadingListItem.book))
    )
    return session.scalar(stmt)

def add_book_to_list(session: Session, *, user_id: int, list_id: int, book_id: int) -> Optional[ReadingListItem]:
    """Add a book to a user's reading list."""
    # Verify list ownership
    reading_list = get_reading_list(session, user_id=user_id, list_id=list_id)
    if not reading_list:
        return None
        
    # Check if already in list
    stmt = select(ReadingListItem).where(
        ReadingListItem.reading_list_id == list_id,
        ReadingListItem.book_id == book_id
    )
    existing = session.scalar(stmt)
    if existing:
        return existing
        
    item = ReadingListItem(reading_list_id=list_id, book_id=book_id)
    session.add(item)
    session.commit()
    session.refresh(item)
    return item

def remove_book_from_list(session: Session, *, user_id: int, list_id: int, book_id: int) -> bool:
    """Remove a book from a reading list."""
    # Verify list ownership first (implicit via join or two steps)
    reading_list = get_reading_list(session, user_id=user_id, list_id=list_id)
    if not reading_list:
        return False

    stmt = select(ReadingListItem).where(
        ReadingListItem.reading_list_id == list_id,
        ReadingListItem.book_id == book_id
    )
    item = session.scalar(stmt)
    if item:
        session.delete(item)
        session.commit()
        return True
    return False

def delete_reading_list(session: Session, *, user_id: int, list_id: int) -> bool:
    """Delete an entire reading list."""
    reading_list = get_reading_list(session, user_id=user_id, list_id=list_id)
    if reading_list:
        session.delete(reading_list)
        session.commit()
        return True
    return False
