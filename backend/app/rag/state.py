"""
Deterministic state management for the LangGraph Library Assistant.

State is never reset incorrectly — only cleared on explicit first turn.
Routing priority:
  1. pending_action → handle it
  2. pending_slot  → fill it
  3. Parse intent
  4. Route to agent
"""

from typing import Optional, Dict, List, Set
from enum import Enum
from pydantic import BaseModel, Field
import time

from app.rag.schemas import FilterOutput, QueryIntent


class PendingSlot(str, Enum):
    """Slot types the assistant can ask about."""
    GENRE = "genre"
    PACING = "pacing"
    TONE = "tone"
    THEMES = "themes"
    SPECIFICS = "specifics"


class PendingAction(str, Enum):
    """Explicit next-turn actions for deterministic flow control."""
    DETAILS_AFTER_RECO = "details_after_reco"
    DETAILS_AFTER_COMPARISON = "details_after_comparison"
    MORE_RECOMMENDATIONS = "more_recommendations"
    CONFIRM_SELECTION = "confirm_selection"


class StoredBook(BaseModel):
    """Canonical book metadata stored in session state."""
    id: int
    title: str
    author: str
    genres: Optional[str] = None
    pages: Optional[int] = None
    rating: Optional[float] = None
    pacing: Optional[str] = None
    tone: Optional[str] = None
    themes: list[str] = Field(default_factory=list)
    synopsis_snippet: str = ""
    availability: str = ""


class ConversationState(BaseModel):
    """
    Tracks the state of a user's conversation for deterministic routing.

    This state matches the spec exactly:
    - user_id, pending_action, pending_slot, selected_book_ids
    - last_intent, conversation_history
    - user_preference_vector, collaborative_user_embedding
    """
    # ── Spec-required fields ──
    user_id: str = ""
    pending_action: Optional[PendingAction] = None
    pending_slot: Optional[PendingSlot] = None
    selected_book_ids: List[str] = Field(default_factory=list)
    last_intent: Optional[QueryIntent] = None
    conversation_history: List[dict] = Field(default_factory=list)
    user_preference_vector: List[float] = Field(default_factory=list)
    collaborative_user_embedding: List[float] = Field(default_factory=list)

    # ── Internal state for routing ──
    last_filters: Optional[FilterOutput] = None
    last_search_query: Optional[str] = None
    pending_intent: Optional[QueryIntent] = None
    collected_slots: Dict[str, str] = Field(default_factory=dict)

    # ── Canonical book storage ──
    viewed_book_ids: Set[int] = Field(default_factory=set)
    viewed_books: Dict[int, StoredBook] = Field(default_factory=dict)

    # ── Interaction tracking ──
    interaction_count: int = 0
    updated_at: float = Field(default_factory=time.time)

    class Config:
        arbitrary_types_allowed = True

    def resolve_book_by_title(self, title_query: str, author_hint: Optional[str] = None) -> Optional[StoredBook]:
        """
        Fuzzy-match a title (and optionally author) against stored books.
        Returns the best match or None if no match found.
        """
        title_lower = title_query.strip().lower()

        # First pass: exact title + author match
        if author_hint:
            author_lower = author_hint.strip().lower()
            for book in self.viewed_books.values():
                if (title_lower in book.title.lower() or book.title.lower() in title_lower) and \
                   author_lower in book.author.lower():
                    return book

        # Second pass: exact title match
        for book in self.viewed_books.values():
            if book.title.lower() == title_lower:
                return book

        # Third pass: substring title match
        for book in self.viewed_books.values():
            if title_lower in book.title.lower() or book.title.lower() in title_lower:
                return book

        return None


class StateManager:
    """Simple in-memory state manager. In production, use Redis."""
    _states: Dict[str, ConversationState] = {}

    @classmethod
    def get_state(cls, user_id: str) -> ConversationState:
        if user_id not in cls._states:
            cls._states[user_id] = ConversationState(user_id=user_id)
        return cls._states[user_id]

    @classmethod
    def update_state(cls, user_id: str, state: ConversationState):
        state.updated_at = time.time()
        cls._states[user_id] = state

    @classmethod
    def clear_state(cls, user_id: str):
        if user_id in cls._states:
            del cls._states[user_id]

    @classmethod
    def add_viewed_ids(cls, user_id: str, ids: Set[int]):
        state = cls.get_state(user_id)
        state.viewed_book_ids.update(ids)
        cls.update_state(user_id, state)

    @classmethod
    def add_viewed_books(cls, user_id: str, books: list[StoredBook]):
        """Store canonical book metadata for later retrieval-free lookups."""
        state = cls.get_state(user_id)
        for book in books:
            state.viewed_books[book.id] = book
            state.viewed_book_ids.add(book.id)
        cls.update_state(user_id, state)
