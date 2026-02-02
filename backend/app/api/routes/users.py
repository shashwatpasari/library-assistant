"""
API routes for user management and preferences.
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.api.dependencies import db_session_dependency, get_current_user
from app.models import User, UserPreference
from app.schemas import UserPreferenceBase, UserPreferenceCreate, UserPreferenceRead, BookRead
from app.services.recommendations import (
    get_personalized_recommendations,
    get_available_themes,
    get_available_moods
)

router = APIRouter(
    prefix="/users",
    tags=["users"],
)

@router.get("/me/preferences", response_model=UserPreferenceRead)
def get_my_preferences(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(db_session_dependency)
):
    """Retrieve the current user's preferences."""
    pref = db.scalar(select(UserPreference).where(UserPreference.user_id == current_user.id))
    if not pref:
        # Create default empty preferences if they don't exist
        pref = UserPreference(user_id=current_user.id)
        db.add(pref)
        db.commit()
        db.refresh(pref)
    return pref

@router.post("/me/preferences", response_model=UserPreferenceRead)
def update_my_preferences(
    preferences: UserPreferenceCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(db_session_dependency)
):
    """Update or create the current user's preferences."""
    existing_pref = db.scalar(select(UserPreference).where(UserPreference.user_id == current_user.id))
    
    if existing_pref:
        # Update existing
        for key, value in preferences.model_dump(exclude_unset=True).items():
            setattr(existing_pref, key, value)
        db.commit()
        db.refresh(existing_pref)
        return existing_pref
    else:
        # Create new (though GET should usually handle creation too)
        new_pref = UserPreference(**preferences.model_dump(), user_id=current_user.id)
        db.add(new_pref)
        db.commit()
        db.refresh(new_pref)
        return new_pref


@router.get("/me/recommendations", response_model=list[BookRead])
def get_my_recommendations(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(db_session_dependency),
    limit: int = 20
):
    """Get personalized book recommendations based on user preferences."""
    books = get_personalized_recommendations(db, current_user.id, limit=limit)
    return books


@router.get("/preferences/available-themes", response_model=list[str])
def list_available_themes(
    db: Session = Depends(db_session_dependency)
):
    """Get list of available themes for onboarding selection."""
    return get_available_themes(db)


@router.get("/preferences/available-moods", response_model=list[str])
def list_available_moods(
    db: Session = Depends(db_session_dependency)
):
    """Get list of available moods for onboarding selection."""
    return get_available_moods(db)

