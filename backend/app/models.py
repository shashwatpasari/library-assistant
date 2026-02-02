"""
SQLAlchemy ORM models for the library domain.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from pgvector.sqlalchemy import Vector

class Base(DeclarativeBase):
    """Base declarative class for SQLAlchemy models."""


class User(Base):
    """Represents a user account in the library system."""

    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("email", name="uq_users_email"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class Book(Base):
    """Represents a book in the library's catalogue."""

    __tablename__ = "books"
    __table_args__ = (
        UniqueConstraint("isbn", name="uq_books_isbn"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    title_long: Mapped[str | None] = mapped_column(String(512), nullable=True)
    author: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    authors: Mapped[str | None] = mapped_column(String(512), nullable=True)  # Full authors list from API
    isbn: Mapped[str | None] = mapped_column(String(32), unique=True, nullable=True, index=True)
    isbn10: Mapped[str | None] = mapped_column(String(32), nullable=True)
    isbn13: Mapped[str | None] = mapped_column(String(32), nullable=True)
    publisher: Mapped[str | None] = mapped_column(String(255), nullable=True)
    genres: Mapped[str | None] = mapped_column(String(255), nullable=True)
    subjects: Mapped[str | None] = mapped_column(String(512), nullable=True)  # Subjects from API
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    synopsis: Mapped[str | None] = mapped_column(Text, nullable=True)  # Synopsis from API (may contain HTML)
    language: Mapped[str | None] = mapped_column(String(64), nullable=True)
    pages: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)  # Book rating (e.g., 4.5 out of 5)
    date_published: Mapped[str | None] = mapped_column(String(32), nullable=True)  # Store as string (YYYY-MM-DD or year)
    cover_image_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    image: Mapped[str | None] = mapped_column(String(512), nullable=True)  # Image URL from API
    image_original: Mapped[str | None] = mapped_column(String(512), nullable=True)  # Original image URL from API
    embedding: Mapped[list[float] | None] = mapped_column(Vector(384), nullable=True) # Vector embedding for semantic search
    
    # AI-enriched metadata fields
    pacing: Mapped[str | None] = mapped_column(String(32), nullable=True)  # Fast, Medium, Slow
    tone: Mapped[str | None] = mapped_column(String(64), nullable=True)  # Dark, Lighthearted, Suspenseful, etc.
    mood_tags: Mapped[list | None] = mapped_column(JSON, nullable=True)  # ["cozy", "tense", "romantic"]
    themes: Mapped[list | None] = mapped_column(JSON, nullable=True)  # ["redemption", "survival", "found family"]
    content_warnings: Mapped[list | None] = mapped_column(JSON, nullable=True)  # ["violence", "explicit language"]
    enrichment_status: Mapped[str | None] = mapped_column(String(16), nullable=True)  # pending, done, failed

    copies: Mapped[list["BookCopy"]] = relationship(
        back_populates="book", cascade="all, delete-orphan"
    )


class BookCopy(Base):
    """Represents a physical or digital copy of a book."""

    __tablename__ = "book_copies"
    __table_args__ = (
        CheckConstraint("status IN ('available', 'issued')", name="chk_copy_status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    book_id: Mapped[int] = mapped_column(
        ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="available")
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    book: Mapped["Book"] = relationship(back_populates="copies")


class SavedBook(Base):
    """Represents a book saved/liked by a user."""

    __tablename__ = "saved_books"
    __table_args__ = (
        UniqueConstraint("user_id", "book_id", name="uq_saved_books_user_book"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    book_id: Mapped[int] = mapped_column(
        ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True
    )
    saved_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    user: Mapped["User"] = relationship()
    book: Mapped["Book"] = relationship()


class UserPreference(Base):
    """Represents a user's taste profile and reading preferences."""

    __tablename__ = "user_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True
    )
    
    # Core Preferences
    favorite_genres: Mapped[list[str]] = mapped_column(JSON, default=list) # e.g. ["Sci-Fi", "Thriller"]
    pacing_preference: Mapped[str | None] = mapped_column(String(32), nullable=True) # e.g. "Fast", "Slow" (legacy)
    pacing_preferences: Mapped[list[str]] = mapped_column(JSON, default=list) # e.g. ["Fast", "Slow", "Moderate"]
    tone_preference: Mapped[str | None] = mapped_column(String(32), nullable=True) # e.g. "Dark", "Light"
    
    # New enriched preferences (themes and moods from AI enrichment)
    preferred_themes: Mapped[list[str]] = mapped_column(JSON, default=list)  # e.g. ["redemption", "survival"]
    preferred_moods: Mapped[list[str]] = mapped_column(JSON, default=list)   # e.g. ["cozy", "tense"]
    
    # Constraints & Dealbreakers
    triggers_to_avoid: Mapped[list[str]] = mapped_column(JSON, default=list)
    disliked_genres: Mapped[list[str]] = mapped_column(JSON, default=list)
    
    # Reading Goals
    reading_goals: Mapped[dict] = mapped_column(JSON, default=dict) # e.g. {"monthly_target": 4}
    
    # Onboarding Status
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    
    user: Mapped["User"] = relationship()


class ReadingList(Base):
    """User-created named reading lists."""
    __tablename__ = "reading_lists"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user: Mapped["User"] = relationship()
    items: Mapped[list["ReadingListItem"]] = relationship(back_populates="reading_list", cascade="all, delete-orphan")


class ReadingListItem(Base):
    """Items (books) within a reading list."""
    __tablename__ = "reading_list_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    reading_list_id: Mapped[int] = mapped_column(ForeignKey("reading_lists.id"), nullable=False, index=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id"), nullable=False)
    added_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    reading_list: Mapped["ReadingList"] = relationship(back_populates="items")
    book: Mapped["Book"] = relationship()

