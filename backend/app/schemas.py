"""
Pydantic schemas for request and response validation.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class BookBase(BaseModel):
    title: str = Field(..., description="Title of the book")
    title_long: Optional[str] = Field(default=None, description="Long/full title of the book")
    author: str = Field(..., description="Primary author of the book")
    authors: Optional[str] = Field(default=None, description="All authors (semicolon-separated)")
    isbn: Optional[str] = Field(default=None, description="ISBN identifier of the book")
    isbn10: Optional[str] = Field(default=None, description="ISBN-10 identifier")
    isbn13: Optional[str] = Field(default=None, description="ISBN-13 identifier")
    publisher: Optional[str] = Field(default=None, description="Publisher of the book")
    genres: Optional[str] = Field(default=None, description="Comma-separated list of genres")
    subjects: Optional[str] = Field(default=None, description="Subjects/categories (semicolon-separated)")
    description: Optional[str] = Field(default=None, description="Description of the book")
    synopsis: Optional[str] = Field(default=None, description="Synopsis (may contain HTML)")
    language: Optional[str] = Field(default=None, description="Language code (e.g., 'en')")
    pages: Optional[int] = Field(default=None, description="Number of pages")
    rating: Optional[float] = Field(default=None, description="Book rating (e.g., 4.5 out of 5)")
    date_published: Optional[str] = Field(default=None, description="Publication date (YYYY-MM-DD or year)")
    cover_image_url: Optional[str] = Field(
        default=None, description="URL or path to the book's cover image"
    )
    image: Optional[str] = Field(default=None, description="Image URL from API")
    image_original: Optional[str] = Field(default=None, description="Original image URL from API")


class BookCreate(BookBase):
    """Schema for creating a book."""


class BookRead(BookBase):
    """Schema for reading a book."""

    id: int

    class Config:
        from_attributes = True


class BookAvailability(BaseModel):
    """Schema representing availability information for a book."""

    book_id: int
    total_copies: int
    available_copies: int
    earliest_due_date: Optional[date]


class CopyRead(BaseModel):
    """Schema representing a copy of a book."""

    id: int
    book_id: int
    status: str
    due_date: Optional[date]

    class Config:
        from_attributes = True


class UserBase(BaseModel):
    """Base schema for user data."""

    email: str = Field(..., description="User's email address")
    full_name: str = Field(..., description="User's full name")


class UserCreate(UserBase):
    """Schema for creating a new user."""

    password: str = Field(..., min_length=8, description="User's password (minimum 8 characters, must contain at least one number and one special character)")

    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password meets requirements."""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not re.search(r'\d', v):
            raise ValueError('Password must contain at least one number')
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', v):
            raise ValueError('Password must contain at least one special character')
        return v


class UserRead(UserBase):
    """Schema for reading user data."""

    id: int
    created_at: str
    onboarding_completed: bool = False

    class Config:
        from_attributes = True


class UserLogin(BaseModel):
    """Schema for user login."""

    email: str = Field(..., description="User's email address")
    password: str = Field(..., description="User's password")


class Token(BaseModel):
    """Schema for authentication token."""

    access_token: str
    token_type: str = "bearer"
    user: UserRead


class ChangeEmail(BaseModel):
    """Schema for changing user email."""

    current_email: str = Field(..., description="Current email address")
    new_email: str = Field(..., description="New email address")
    confirm_new_email: str = Field(..., description="Confirm new email address")


class ChangePassword(BaseModel):
    """Schema for changing user password."""

    current_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=8, description="New password (minimum 8 characters, must contain at least one number and one special character)")
    confirm_new_password: str = Field(..., description="Confirm new password")

    @field_validator('new_password')
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        """Validate new password meets requirements."""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not re.search(r'\d', v):
            raise ValueError('Password must contain at least one number')
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', v):
            raise ValueError('Password must contain at least one special character')
        return v


class ForgotPassword(BaseModel):
    """Schema for forgot password request."""

    email: str = Field(..., description="Email address to reset password for")


class ResetPassword(BaseModel):
    """Schema for resetting password."""

    email: str = Field(..., description="Email address")
    reset_token: str = Field(..., description="Password reset token")
    new_password: str = Field(..., min_length=8, description="New password (minimum 8 characters, must contain at least one number and one special character)")
    confirm_new_password: str = Field(..., description="Confirm new password")

    @field_validator('new_password')
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        """Validate new password meets requirements."""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not re.search(r'\d', v):
            raise ValueError('Password must contain at least one number')
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', v):
            raise ValueError('Password must contain at least one special character')
        return v


class SavedBookCreate(BaseModel):
    """Schema for saving a book."""

    book_id: int = Field(..., description="ID of the book to save")


class SavedBookRead(BaseModel):
    """Schema for reading a saved book entry."""

    id: int
    user_id: int
    book_id: int
    saved_at: str
    book: Optional[BookRead] = None

    class Config:
        from_attributes = True


class UserPreferenceBase(BaseModel):
    """Base schema for user preferences."""
    favorite_genres: list[str] = Field(default=[], description="List of favorite genres")
    pacing_preference: Optional[str] = Field(default=None, description="Preferred pacing (Fast, Slow, etc) - legacy single value")
    pacing_preferences: list[str] = Field(default=[], description="List of preferred pacing options")
    tone_preference: Optional[str] = Field(default=None, description="Preferred tone (Dark, Light, etc)")
    preferred_themes: list[str] = Field(default=[], description="Preferred themes (redemption, survival, etc)")
    preferred_moods: list[str] = Field(default=[], description="Preferred moods (cozy, tense, romantic, etc)")
    triggers_to_avoid: list[str] = Field(default=[], description="List of triggers/content to avoid")
    disliked_genres: list[str] = Field(default=[], description="List of disliked genres")
    reading_goals: dict = Field(default={}, description="Reading goals object")
    onboarding_completed: bool = Field(default=False, description="Whether onboarding is completed")


class UserPreferenceCreate(UserPreferenceBase):
    """Schema for creating/updating user preferences."""
    pass


class UserPreferenceRead(UserPreferenceBase):
    """Schema for reading user preferences."""
    id: int
    user_id: int

    class Config:
        from_attributes = True


class ReadingListItemBase(BaseModel):
    """Base schema for items in a reading list."""
    book_id: int


class ReadingListItemCreate(ReadingListItemBase):
    """Schema for adding a book to a reading list."""
    pass


class ReadingListItemRead(ReadingListItemBase):
    """Schema for reading a reading list item."""
    id: int
    reading_list_id: int
    added_at: datetime
    book: Optional[BookRead] = None

    class Config:
        from_attributes = True


class ReadingListBase(BaseModel):
    """Base schema for reading lists."""
    name: str = Field(..., min_length=1, description="Name of the reading list")


class ReadingListCreate(ReadingListBase):
    """Schema for creating a new reading list."""
    pass


class ReadingListRead(ReadingListBase):
    """Schema for reading a reading list."""
    id: int
    user_id: int
    created_at: datetime
    items: list["ReadingListItemRead"] = []

    class Config:
        from_attributes = True


# Rebuild models to resolve forward references
ReadingListItemRead.model_rebuild()
ReadingListRead.model_rebuild()
