"""
Pydantic models for structured LLM outputs in the RAG pipeline.

Schemas enforce structured JSON output from the LLM, replacing
fragile tag parsing approaches.
"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class QueryIntent(str, Enum):
    """Possible intents for a user query."""
    GENERAL_INFO = "general_info"           # Opening hours, policies, owner
    USER_HISTORY = "user_history"           # Borrowed books, liked books, reading lists
    RECOMMENDATION = "recommendation"       # Book recommendations (filtered or generic)
    SIMILAR_BOOKS = "similar_books"         # Books similar to a specific title
    COMPARISON = "comparison"               # Compare two or more books
    BOOK_DETAILS = "book_details"           # Details about a specific book
    CONTINUATION = "continuation"           # "yes", "no", "more" — follow-up
    CLARIFICATION = "clarification"         # System asks for more detail
    ACCOUNT_ACTION = "account_action"       # Save, borrow, return a book


class IntentParserOutput(BaseModel):
    """Structured output from the intent parser. LLM must return JSON matching this."""
    intent: QueryIntent = Field(
        description="The detected intent of the user query"
    )
    filters: dict = Field(
        default_factory=dict,
        description="Extracted filters: genre, tone, author, pacing, themes, etc."
    )
    referenced_titles: list[str] = Field(
        default_factory=list,
        description="Specific book titles mentioned in the query"
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence score for the detected intent (0.0-1.0)"
    )


class RouterOutput(BaseModel):
    """Output from the intent router (kept for backward compat wrapper)."""
    intent: QueryIntent = Field(
        description="The detected intent of the user query"
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence score for the detected intent (0.0-1.0)"
    )
    targets: list[str] = Field(
        default_factory=list,
        description="Target entities (book titles, authors) mentioned in the query"
    )
    filters: dict = Field(
        default_factory=dict,
        description="Extracted filters"
    )

    class Config:
        use_enum_values = True


class PacingEnum(str, Enum):
    """Book pacing options."""
    FAST = "Fast"
    MODERATE = "Moderate"
    SLOW = "Slow"


class ToneEnum(str, Enum):
    """Book tone options."""
    DARK = "Dark"
    LIGHT = "Light"
    EMOTIONAL = "Emotional"
    SUSPENSEFUL = "Suspenseful"
    HUMOROUS = "Humorous"


class FilterOutput(BaseModel):
    """Extracted search filters from natural language query."""
    search_query: str = Field(
        description="The semantic search terms with filter words removed"
    )
    max_pages: Optional[int] = Field(
        default=None,
        description="Maximum number of pages"
    )
    min_pages: Optional[int] = Field(
        default=None,
        description="Minimum number of pages"
    )
    author: Optional[str] = Field(
        default=None,
        description="Author name to filter by"
    )
    genre: Optional[str] = Field(
        default=None,
        description="Genre to filter by (substring match)"
    )
    year_start: Optional[int] = Field(
        default=None,
        description="Published after this year (inclusive)"
    )
    year_end: Optional[int] = Field(
        default=None,
        description="Published before this year (inclusive)"
    )
    language: Optional[str] = Field(
        default=None,
        description="Book language (e.g., English, French)"
    )
    pacing: Optional[PacingEnum] = Field(
        default=None,
        description="Desired pacing"
    )
    tone: Optional[ToneEnum] = Field(
        default=None,
        description="Desired tone"
    )
    themes: list[str] = Field(
        default_factory=list,
        description="Themes to search for (e.g., 'revenge', 'survival')"
    )
    moods: list[str] = Field(
        default_factory=list,
        description="Moods to search for (e.g., 'tense', 'cozy')"
    )


class RecommendedBook(BaseModel):
    """A recommended book in the generation output."""
    id: int = Field(
        description="The book ID from the retrieved candidates"
    )
    why: str = Field(
        description="Brief explanation of why this book is recommended"
    )


class GenerationOutput(BaseModel):
    """Structured output from the generation LLM."""
    answer_markdown: str = Field(
        description="The markdown-formatted response to show the user"
    )
    recommended: list[RecommendedBook] = Field(
        default_factory=list,
        description="List of recommended books with IDs and explanations"
    )
    follow_up_question: Optional[str] = Field(
        default=None,
        description="A follow-up question to keep the conversation going"
    )


class BookCandidate(BaseModel):
    """Minimal book info for LLM context (no cover URLs to save tokens)."""
    id: int
    title: str
    author: str
    genres: Optional[str] = None
    pages: Optional[int] = None
    published_year: Optional[int] = None
    rating: Optional[float] = None
    pacing: Optional[str] = None
    tone: Optional[str] = None
    themes: list[str] = Field(default_factory=list)
    synopsis_snippet: str = Field(
        default="",
        description="1-2 sentence synopsis snippet"
    )
    availability: str = Field(
        default="",
        description="Availability status (e.g., '2/3 available')"
    )
    hybrid_score: Optional[float] = Field(
        default=None,
        description="Combined content + collaborative score"
    )


class BookCard(BaseModel):
    """UI card data with cover and availability for frontend display."""
    id: int
    title: str
    author: str
    cover: str = Field(default="", description="Cover image URL")
    availability: str = Field(default="", description="Availability status")
    why: str = Field(default="", description="Why this book was recommended")


# Fallback response for when LLM output parsing fails
class FallbackResponse(BaseModel):
    """Safe fallback response when parsing fails."""
    answer_markdown: str = "I found some books that might interest you. Here are my recommendations:"
    book_ids: list[int] = Field(
        default_factory=list,
        description="Book IDs from retrieved candidates to show as cards"
    )
