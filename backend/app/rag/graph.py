"""
LangGraph-based multi-agent pipeline for the Library Assistant.

Architecture:
  Entry → state_gate → intent_parser → agent_router
                                          ├→ general_info_agent → END
                                          ├→ user_history_agent → explain → END
                                          ├→ recommendation_agent → explain → END
                                          ├→ similar_books_agent → explain → END
                                          ├→ comparison_agent → explain → END
                                          └→ conversation_agent → END

Routing is DETERMINISTIC — the LLM only does intent understanding.
Similarity is computed in CODE (cosine similarity), never by LLM.
"""

import json
import logging
import re
from typing import Optional, AsyncGenerator, Any, TypedDict

from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, END
from pydantic import ValidationError
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.config import LIBRARY_NAME, LIBRARY_OWNER, LIBRARY_HOURS
from app.models import (
    User, UserPreference, Book, SavedBook,
    BorrowHistory, ReadingList, ReadingListItem, UserInteraction,
)
from app.rag.schemas import (
    QueryIntent, IntentParserOutput, FilterOutput,
    BookCandidate, BookCard, FallbackResponse,
)
from app.rag.state import (
    ConversationState, StateManager, StoredBook,
    PendingSlot, PendingAction,
)
from app.rag.prompts import (
    FILTER_SYSTEM_PROMPT, FILTER_USER_TEMPLATE,
    GENERATION_SYSTEM_PROMPT, GENERATION_USER_TEMPLATE,
    GENERAL_LIBRARY_PROMPT, ACCOUNT_ACTION_PROMPT,
    COMPARE_SYSTEM_PROMPT, CLARIFYING_PROMPT,
    USER_HISTORY_PROMPT, INJECTION_GUARD,
    BOOK_DETAILS_PROMPT,
)
from app.rag.router import parse_intent
from app.rag.llm import get_filter_llm, get_generation_llm
from app.rag.retrievers import (
    retrieve_for_intent, build_book_candidates, hybrid_retrieve,
)
from app.rag.vectors import (
    cosine_similarity, hybrid_score, rank_books_by_hybrid_score,
    compute_user_preference_vector, encode_book_features,
)
from app.rag.collaborative import (
    get_user_collaborative_embedding, get_user_interaction_count,
)
from app.rag.cache import get_cached_filter_output, cache_filter_output
from app.rag.guardrails import validate_response, build_repair_prompt
from app.services.books import get_book_availability

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# GRAPH STATE
# ═══════════════════════════════════════════════════════════════════════════════

class GraphState(TypedDict, total=False):
    """State that flows through the LangGraph."""
    # ── Input ──
    query: str
    history: list[dict]
    session: Session
    user: Optional[User]
    user_prefs: Optional[UserPreference]
    book_limit: int

    # ── Conversation state ──
    conv_state: ConversationState
    user_key: str

    # ── Intent parser output ──
    intent: str
    targets: list[str]
    confidence: float
    filters: Optional[FilterOutput]

    # ── Resolved entities ──
    resolved_book_ids: list[int]
    resolved_candidates: list[BookCandidate]

    # ── Retrieval results ──
    needs_retrieval: bool
    books: list
    candidates: list[BookCandidate]

    # ── Generation output ──
    response_text: str
    book_cards: list[BookCard]

    # ── Validation ──
    is_valid: bool
    validation_errors: list[str]

    # ── Control flow ──
    early_exit: bool
    skip_to: Optional[str]


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS (stateless)
# ═══════════════════════════════════════════════════════════════════════════════

def _load_user_prefs(session: Session, user: Optional[User]) -> Optional[UserPreference]:
    """Load user preferences from DB."""
    if not user:
        return None
    return session.scalar(
        select(UserPreference).where(UserPreference.user_id == user.id)
    )


def _build_user_context(prefs: Optional[UserPreference]) -> str:
    """Build user context string for prompts."""
    if not prefs:
        return ""
    return f"""
User Profile:
- Favorite Genres: {', '.join(prefs.favorite_genres) if prefs.favorite_genres else 'Not specified'}
- Pacing Preference: {prefs.pacing_preference or 'Not specified'}
- Tone Preference: {prefs.tone_preference or 'Not specified'}
- Avoid: {', '.join(prefs.triggers_to_avoid) if prefs.triggers_to_avoid else 'None'}
- Disliked Genres: {', '.join(prefs.disliked_genres) if prefs.disliked_genres else 'None'}

Use this profile to personalize recommendations. STRICTLY avoid any triggers listed above."""


def _format_candidates(candidates: list[BookCandidate]) -> str:
    """Format book candidates for LLM context."""
    if not candidates:
        return "No books found matching criteria."
    lines = []
    for i, c in enumerate(candidates, 1):
        lines.append(f"{i}. [ID:{c.id}] \"{c.title}\" by {c.author}")
        lines.append(f"   Genre: {c.genres or 'Unknown'} | Pages: {c.pages or '?'} | Year: {c.published_year or '?'}")
        if c.pacing or c.tone:
            lines.append(f"   Pacing: {c.pacing or '?'} | Tone: {c.tone or '?'}")
        if c.themes:
            lines.append(f"   Themes: {', '.join(c.themes)}")
        lines.append(f"   Synopsis: {c.synopsis_snippet}")
        lines.append(f"   Availability: {c.availability}")
        if c.hybrid_score is not None:
            lines.append(f"   Relevance Score: {c.hybrid_score:.3f}")
        lines.append("")
    return "\n".join(lines) + INJECTION_GUARD


def _format_history(messages: list[dict]) -> str:
    """Format conversation history for LLM context (last 6 messages)."""
    if not messages:
        return "No previous conversation."
    lines = []
    for msg in messages[-6:]:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if len(content) > 300:
            content = content[:297] + "..."
        lines.append(f"{role.capitalize()}: {content}")
    return "\n".join(lines)


def _build_book_cards(books: list, candidates: list[BookCandidate]) -> list[BookCard]:
    """Build UI cards from books + candidates."""
    cards = []
    for book, candidate in zip(books, candidates):
        cover = book.cover_image_url or book.image or ""
        cards.append(BookCard(
            id=book.id,
            title=book.title,
            author=book.author,
            cover=cover,
            availability=candidate.availability,
        ))
    return cards


def _store_viewed_books(user_key: str, candidates: list[BookCandidate]):
    """Store canonical metadata in state for retrieval-free lookups."""
    stored = [
        StoredBook(
            id=c.id, title=c.title, author=c.author,
            genres=c.genres, pages=c.pages, rating=c.rating,
            pacing=c.pacing, tone=c.tone, themes=c.themes,
            synopsis_snippet=c.synopsis_snippet,
            availability=c.availability,
        )
        for c in candidates
    ]
    StateManager.add_viewed_books(user_key, stored)


async def _extract_filters(query: str) -> FilterOutput:
    """Extract search filters from query using LLM."""
    hit, cached = get_cached_filter_output(query)
    if hit:
        return cached

    llm = get_filter_llm()
    messages = [
        SystemMessage(content=FILTER_SYSTEM_PROMPT),
        HumanMessage(content=FILTER_USER_TEMPLATE.format(query=query)),
    ]
    try:
        response = await llm.ainvoke(messages)
        result = json.loads(response.content)
        filters = FilterOutput(
            search_query=result.get("search_query", query),
            max_pages=result.get("max_pages"),
            min_pages=result.get("min_pages"),
            author=result.get("author"),
            genre=result.get("genre"),
            year_start=result.get("year_start"),
            year_end=result.get("year_end"),
            language=result.get("language"),
            pacing=result.get("pacing"),
            tone=result.get("tone"),
            themes=result.get("themes") or [],
            moods=result.get("moods") or [],
        )
        cache_filter_output(query, filters)
        return filters
    except (json.JSONDecodeError, ValidationError) as e:
        logger.warning(f"Filter extraction failed: {e}")
        return FilterOutput(search_query=query)


def _has_substantive_filters(filters: FilterOutput) -> bool:
    """Check if filters have real criteria beyond just a search query."""
    return bool(
        filters.genre or filters.author or filters.pacing or
        filters.tone or filters.themes or filters.moods or
        filters.max_pages or filters.min_pages or
        filters.year_start or filters.year_end or filters.language
    )


# ── Slot extraction helpers (deterministic, no LLM) ──

_KNOWN_GENRES = {
    "fantasy", "sci-fi", "science fiction", "scifi", "romance", "thriller",
    "mystery", "horror", "historical fiction", "literary fiction",
    "non-fiction", "nonfiction", "biography", "memoir", "self-help",
    "adventure", "dystopian", "comedy", "drama", "crime", "western",
    "paranormal", "urban fantasy", "epic fantasy", "dark fantasy",
    "young adult", "ya", "children", "graphic novel", "manga",
    "poetry", "philosophy", "psychology", "history", "travel",
    "classics", "contemporary", "magical realism", "steampunk",
    "cyberpunk", "space opera", "military", "detective", "suspense",
    "action", "satire", "gothic", "supernatural", "political",
}

_PACING_KEYWORDS = {
    "fast": "Fast", "fast-paced": "Fast", "quick": "Fast",
    "page-turner": "Fast", "gripping": "Fast",
    "slow": "Slow", "slow-burn": "Slow", "leisurely": "Slow",
    "atmospheric": "Slow", "meditative": "Slow",
    "moderate": "Moderate", "medium": "Moderate",
}

_TONE_KEYWORDS = {
    "dark": "Dark", "grim": "Dark", "bleak": "Dark", "gritty": "Dark",
    "light": "Light", "lighthearted": "Light", "fun": "Light",
    "feel-good": "Light", "uplifting": "Light", "cozy": "Light",
    "emotional": "Emotional", "moving": "Emotional", "heartfelt": "Emotional",
    "suspenseful": "Suspenseful", "tense": "Suspenseful", "thrilling": "Suspenseful",
    "humorous": "Humorous", "funny": "Humorous", "witty": "Humorous",
}


def _extract_all_slots(text: str) -> dict:
    """Parse ALL slots from freetext. No LLM — deterministic keyword matching."""
    slots = {}
    lower = text.lower().strip()

    for kw, val in _PACING_KEYWORDS.items():
        if kw in lower:
            slots["pacing"] = val
            lower = lower.replace(kw, "").strip()
            break

    for kw, val in _TONE_KEYWORDS.items():
        if kw in lower:
            slots["tone"] = val
            lower = lower.replace(kw, "").strip()
            break

    sorted_genres = sorted(_KNOWN_GENRES, key=len, reverse=True)
    for genre in sorted_genres:
        if genre in lower:
            slots["genre"] = genre.title()
            lower = lower.replace(genre, "").strip()
            break

    remaining = re.sub(
        r'\b(i|like|want|love|prefer|enjoy|read|some|books?|please|recommend|me|something|anything)\b',
        '', lower,
    ).strip()
    if remaining and "genre" not in slots:
        slots["genre"] = remaining.title()

    return slots


def _build_filters_from_slots(slots: dict) -> FilterOutput:
    """Build FilterOutput from slot dict."""
    genre = slots.get("genre")
    pacing = slots.get("pacing")
    tone = slots.get("tone")
    themes_raw = slots.get("themes", "")
    themes = [t.strip() for t in themes_raw.split(",") if t.strip()] if themes_raw else []

    return FilterOutput(
        search_query=genre or themes_raw or "",
        genre=genre, pacing=pacing, tone=tone, themes=themes,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# GRAPH NODES
# ═══════════════════════════════════════════════════════════════════════════════


async def node_state_gate(state: GraphState) -> dict:
    """
    Node: state_gate — Deterministic routing priority.

    1. pending_action → handle it
    2. pending_slot → fill it
    3. Pass through to intent_parser
    """
    user_key = state["user_key"]
    conv = state["conv_state"]
    query = state["query"]

    logger.info(f"[state_gate] pending_action={conv.pending_action} pending_slot={conv.pending_slot}")

    # ── Priority 1: Handle pending slot (user's answer fills it) ──
    if conv.pending_slot:
        logger.info(f"[state_gate] Filling slot: {conv.pending_slot.value} ← '{query}'")
        extracted = _extract_all_slots(query)
        if not extracted:
            conv.collected_slots[conv.pending_slot.value] = query.strip()
        else:
            for k, v in extracted.items():
                conv.collected_slots[k] = v

        conv.pending_slot = None
        filters = _build_filters_from_slots(conv.collected_slots)
        conv.last_filters = filters
        conv.last_intent = QueryIntent.RECOMMENDATION
        StateManager.update_state(user_key, conv)

        return {
            "intent": QueryIntent.RECOMMENDATION.value,
            "filters": filters,
            "targets": [],
            "confidence": 1.0,
            "early_exit": False,
            "skip_to": "recommendation_agent",
        }

    # ── Priority 2: Handle pending action ──
    if conv.pending_action:
        action = conv.pending_action
        query_lower = query.lower().strip()
        is_affirmative = query_lower in ("yes", "yeah", "sure", "ok", "yep", "please", "y")
        is_negative = query_lower in ("no", "nah", "nope", "n", "no thanks")
        is_more = bool(re.search(r"\b(more|another|continue|next|show more)\b", query_lower))

        if action == PendingAction.MORE_RECOMMENDATIONS and (is_affirmative or is_more):
            conv.pending_action = None
            StateManager.update_state(user_key, conv)
            return {
                "intent": QueryIntent.RECOMMENDATION.value,
                "filters": conv.last_filters,
                "targets": [],
                "confidence": 1.0,
                "early_exit": False,
                "skip_to": "recommendation_agent",
            }

        if action in (PendingAction.DETAILS_AFTER_RECO, PendingAction.DETAILS_AFTER_COMPARISON):
            # Check if user is asking about a specific book from viewed books
            if not is_negative and not is_affirmative and not is_more:
                # User might be naming a book — try to resolve from state
                # Strip common prefixes like "yes about", "tell me about"
                title_query = re.sub(
                    r'^(yes|yeah|sure)?\s*(about|tell\s+me\s+about|more\s+(info|details?)\s+(on|about))?\s*',
                    '', query, flags=re.IGNORECASE,
                ).strip()
                if title_query:
                    # Try "Title by Author" pattern
                    by_match = re.match(r'^(.+?)\s+by\s+(.+)$', title_query, re.IGNORECASE)
                    if by_match:
                        stored = conv.resolve_book_by_title(by_match.group(1).strip(), by_match.group(2).strip())
                    else:
                        stored = conv.resolve_book_by_title(title_query)
                    if stored:
                        conv.pending_action = None
                        StateManager.update_state(user_key, conv)
                        return {
                            "intent": QueryIntent.BOOK_DETAILS.value,
                            "targets": [stored.title],
                            "resolved_book_ids": [stored.id],
                            "confidence": 1.0,
                            "early_exit": False,
                            "skip_to": "book_details_agent",
                        }

            if is_affirmative or not is_negative:
                conv.pending_action = None
                StateManager.update_state(user_key, conv)
                # Fall through to normal intent parsing
            else:
                conv.pending_action = None
                StateManager.update_state(user_key, conv)

        if is_negative:
            conv.pending_action = None
            StateManager.update_state(user_key, conv)

    # ── Priority 3: Check for continuation pattern ──
    query_lower = query.lower().strip()
    is_continuation = query_lower in ("yes", "yeah", "sure", "ok", "yep", "more", "please", "y", "show more", "next", "another")
    if is_continuation and conv.last_intent:
        return {
            "intent": QueryIntent.CONTINUATION.value,
            "filters": conv.last_filters,
            "targets": [],
            "confidence": 1.0,
            "early_exit": False,
        }

    logger.info("[state_gate] No pending state, proceeding to intent_parser")
    return {"early_exit": False}


async def node_intent_parser(state: GraphState) -> dict:
    """
    Node: intent_parser — LLM classifies the query into one of 7 intents.

    The LLM outputs JSON. This is ONLY intent understanding, not routing.
    """
    if state.get("skip_to"):
        return {}

    query = state["query"]
    conv = state["conv_state"]
    user_key = state["user_key"]

    # If already classified (from state_gate), skip
    if state.get("intent"):
        return {}

    parsed = await parse_intent(query)
    logger.info(f"[intent_parser] intent={parsed.intent} confidence={parsed.confidence} targets={parsed.referenced_titles}")

    # ── Handle CONTINUATION → re-use last intent ──
    if parsed.intent == QueryIntent.CONTINUATION and conv.last_intent:
        return {
            "intent": conv.last_intent.value,
            "targets": parsed.referenced_titles,
            "confidence": parsed.confidence,
            "filters": conv.last_filters,
        }

    # ── Handle RECOMMENDATION without user prefs (cold user) ──
    if parsed.intent == QueryIntent.RECOMMENDATION:
        user_prefs = state.get("user_prefs")
        # Try to extract filters from the query or from parser output
        filters = None
        if parsed.filters:
            filters = FilterOutput(
                search_query=parsed.filters.get("search_query", query),
                genre=parsed.filters.get("genre"),
                author=parsed.filters.get("author"),
                pacing=parsed.filters.get("pacing"),
                tone=parsed.filters.get("tone"),
                themes=parsed.filters.get("themes", []),
                moods=parsed.filters.get("moods", []),
            )
        if filters is None or not _has_substantive_filters(filters or FilterOutput(search_query=query)):
            filters = await _extract_filters(query)

        if not user_prefs and not _has_substantive_filters(filters) and len(state.get("history", [])) < 2:
            # Cold user, vague query → ask clarifying question
            conv.pending_slot = PendingSlot.GENRE
            conv.pending_intent = QueryIntent.RECOMMENDATION
            StateManager.update_state(user_key, conv)
            return {
                "intent": QueryIntent.CLARIFICATION.value,
                "targets": [],
                "confidence": parsed.confidence,
                "filters": None,
                "early_exit": True,
            }

        # Save filters for "more" requests
        conv.last_filters = filters
        conv.last_intent = QueryIntent.RECOMMENDATION
        conv.last_search_query = query
        StateManager.update_state(user_key, conv)

        return {
            "intent": QueryIntent.RECOMMENDATION.value,
            "targets": parsed.referenced_titles,
            "confidence": parsed.confidence,
            "filters": filters,
        }

    # ── Handle SIMILAR_BOOKS: Extract filters if present ──
    if parsed.intent == QueryIntent.SIMILAR_BOOKS:
        filters = await _extract_filters(query)
        conv.last_filters = filters
        conv.last_intent = QueryIntent.SIMILAR_BOOKS
        StateManager.update_state(user_key, conv)
        return {
            "intent": parsed.intent.value,
            "targets": parsed.referenced_titles,
            "confidence": parsed.confidence,
            "filters": filters,
        }

    # ── Handle BOOK_DETAILS: Resolve target book ──
    if parsed.intent == QueryIntent.BOOK_DETAILS:
        conv.last_intent = QueryIntent.BOOK_DETAILS
        StateManager.update_state(user_key, conv)
        return {
            "intent": parsed.intent.value,
            "targets": parsed.referenced_titles,
            "confidence": parsed.confidence,
            "filters": None,
        }

    return {
        "intent": parsed.intent.value,
        "targets": parsed.referenced_titles,
        "confidence": parsed.confidence,
        "filters": None,
    }


# ── Agent Nodes ──

async def node_general_info_agent(state: GraphState) -> dict:
    """
    Agent: general_info — Library hours, owner, policies, greetings.
    No DB retrieval needed.
    """
    query = state["query"]
    llm = get_generation_llm()
    prompt = GENERAL_LIBRARY_PROMPT.format(query=query)

    response = await llm.ainvoke([HumanMessage(content=prompt)])
    return {
        "response_text": response.content,
        "book_cards": [],
        "candidates": [],
    }


async def node_user_history_agent(state: GraphState) -> dict:
    """
    Agent: user_history — Fetch borrowed/liked books, reading lists.
    Returns canonical book cards, no LLM decision-making.
    """
    session = state["session"]
    user = state.get("user")
    query = state["query"]

    if not user:
        return {
            "response_text": "You need to be logged in to view your reading history. Please sign in first!",
            "book_cards": [],
            "candidates": [],
        }

    # Fetch saved books
    saved = list(session.scalars(
        select(Book).join(SavedBook, SavedBook.book_id == Book.id)
        .where(SavedBook.user_id == user.id)
        .order_by(SavedBook.saved_at.desc())
        .limit(20)
    ))

    # Fetch borrow history
    borrowed = list(session.scalars(
        select(Book).join(BorrowHistory, BorrowHistory.book_id == Book.id)
        .where(BorrowHistory.user_id == user.id)
        .order_by(BorrowHistory.borrowed_at.desc())
        .limit(20)
    ))

    # Fetch reading lists
    reading_lists = list(session.scalars(
        select(ReadingList).where(ReadingList.user_id == user.id)
    ))

    # Build history data string for the LLM to explain
    history_parts = []
    if saved:
        history_parts.append("**Saved/Liked Books:**")
        for b in saved:
            history_parts.append(f"- \"{b.title}\" by {b.author}")
    else:
        history_parts.append("**Saved Books:** None yet")

    if borrowed:
        history_parts.append("\n**Borrowed Books:**")
        for b in borrowed:
            history_parts.append(f"- \"{b.title}\" by {b.author}")
    else:
        history_parts.append("\n**Borrowed Books:** None yet")

    if reading_lists:
        history_parts.append("\n**Reading Lists:**")
        for rl in reading_lists:
            items = list(session.scalars(
                select(Book).join(ReadingListItem, ReadingListItem.book_id == Book.id)
                .where(ReadingListItem.reading_list_id == rl.id)
            ))
            item_titles = [f"\"{b.title}\"" for b in items] if items else ["(empty)"]
            history_parts.append(f"- {rl.name}: {', '.join(item_titles)}")

    history_data = "\n".join(history_parts)

    # Generate friendly explanation
    llm = get_generation_llm()
    prompt = USER_HISTORY_PROMPT.format(history_data=history_data, query=query)
    response = await llm.ainvoke([HumanMessage(content=prompt)])

    # Build book cards from saved books as the primary display
    book_cards = []
    for b in saved[:10]:
        cover = b.cover_image_url or b.image or ""
        avail = get_book_availability(session, book_id=b.id)
        avail_str = f"{avail['available']}/{avail['total']} available" if avail else ""
        book_cards.append(BookCard(
            id=b.id, title=b.title, author=b.author,
            cover=cover, availability=avail_str,
        ))

    return {
        "response_text": response.content,
        "book_cards": book_cards,
        "candidates": [],
    }


async def node_recommendation_agent(state: GraphState) -> dict:
    """
    Agent: recommendation — Hybrid recommendation pipeline.

    1. Apply genre/tone filters (SQL pre-filter)
    2. Compute content similarity (feature vectors, cosine sim in code)
    3. Compute collaborative similarity (if user has embeddings)
    4. Compute hybrid score (alpha * content + beta * collaborative)
    5. Return ranked top N books
    """
    session = state["session"]
    user = state.get("user")
    user_prefs = state.get("user_prefs")
    query = state["query"]
    filters = state.get("filters")
    conv = state["conv_state"]
    user_key = state["user_key"]
    book_limit = state.get("book_limit", 5)

    # Exclude previously shown books
    exclude_ids = list(conv.viewed_book_ids)

    # Check for "more" pattern and reuse last filters
    is_more = bool(re.search(r"\b(more|another|continue)\b", query, re.IGNORECASE))
    if is_more and conv.last_filters and not filters:
        filters = conv.last_filters

    # ── Step 1: Retrieve candidates via hybrid retrieval (lexical + vector + filters) ──
    books = retrieve_for_intent(
        session, query,
        QueryIntent.RECOMMENDATION,
        state.get("targets", []),
        filters, user_prefs,
        exclude_ids=exclude_ids,
        prioritize_ids=[],
        limit=book_limit * 3,  # Over-fetch for re-ranking
    )

    if not books:
        return {
            "response_text": "I couldn't find any books matching your criteria. Could you try different keywords or broaden your search?",
            "book_cards": [],
            "candidates": [],
            "books": [],
        }

    # ── Step 2: Build candidates and apply hybrid re-ranking ──
    candidates = build_book_candidates(session, books)

    # Get user vectors for hybrid scoring
    user_pref_vector = None
    user_collab_embedding = None
    interaction_count = 0

    if user:
        # Try to get pre-computed vectors
        interaction = session.scalar(
            select(UserInteraction).where(UserInteraction.user_id == user.id)
        )
        if interaction:
            if interaction.preference_vector:
                user_pref_vector = list(interaction.preference_vector)
            if interaction.collaborative_embedding:
                user_collab_embedding = list(interaction.collaborative_embedding)
            interaction_count = interaction.interaction_count

        # Fallback: compute on-the-fly if no stored vectors
        if not user_pref_vector:
            user_pref_vector = compute_user_preference_vector(session, user.id)

        if not user_collab_embedding:
            user_collab_embedding = get_user_collaborative_embedding(session, user.id)

        if interaction_count == 0:
            interaction_count = get_user_interaction_count(session, user.id)

    # ── Step 3: Apply hybrid re-ranking if we have user vectors ──
    if user_pref_vector:
        scored = rank_books_by_hybrid_score(
            user_pref_vector, user_collab_embedding,
            books, interaction_count,
        )
        # Re-order books and rebuild candidates with scores
        books = [b for b, _ in scored[:book_limit]]
        candidates = build_book_candidates(session, books)
        # Attach hybrid scores
        for i, (_, score) in enumerate(scored[:book_limit]):
            if i < len(candidates):
                candidates[i].hybrid_score = score
    else:
        books = books[:book_limit]
        candidates = candidates[:book_limit]

    # ── Step 4: Store viewed books in state ──
    if books:
        StateManager.add_viewed_ids(user_key, {b.id for b in books})
    _store_viewed_books(user_key, candidates)

    # Update state for future "more" requests
    if filters:
        conv.last_filters = filters
    conv.last_intent = QueryIntent.RECOMMENDATION
    conv.last_search_query = query
    conv.pending_action = PendingAction.MORE_RECOMMENDATIONS
    StateManager.update_state(user_key, conv)

    return {
        "books": books,
        "candidates": candidates,
        "book_cards": _build_book_cards(books, candidates),
    }


async def node_similar_books_agent(state: GraphState) -> dict:
    """
    Agent: similar_books — Find books similar to a specific title.

    1. Resolve title → canonical book ID
    2. Get source book's feature vector
    3. Compute cosine similarity (in code)
    4. Blend collaborative similarity if available
    5. Return ranked results
    """
    session = state["session"]
    user = state.get("user")
    user_prefs = state.get("user_prefs")
    query = state["query"]
    targets = state.get("targets", [])
    filters = state.get("filters")
    conv = state["conv_state"]
    user_key = state["user_key"]
    book_limit = state.get("book_limit", 5)

    exclude_ids = list(conv.viewed_book_ids)

    # Retrieve via hybrid search (includes title matching + vector similarity)
    books = retrieve_for_intent(
        session, query,
        QueryIntent.SIMILAR_BOOKS,
        targets, filters, user_prefs,
        exclude_ids=exclude_ids,
        prioritize_ids=[],
        limit=book_limit * 2,
    )

    if not books:
        target_desc = f" like \"{targets[0]}\"" if targets else ""
        return {
            "response_text": f"I couldn't find books{target_desc} in our collection. Could you try a different title?",
            "book_cards": [],
            "candidates": [],
            "books": [],
        }

    candidates = build_book_candidates(session, books)

    # If source book has a feature vector, re-rank by content similarity
    if targets:
        source_book = None
        for t in targets:
            source_book = session.scalar(
                select(Book).where(Book.title.ilike(f"%{t}%"))
            )
            if source_book:
                break

        if source_book and source_book.feature_vector:
            source_vec = list(source_book.feature_vector)
            scored = []
            for book in books:
                if book.feature_vector:
                    sim = cosine_similarity(source_vec, list(book.feature_vector))
                else:
                    sim = 0.0
                scored.append((book, sim))
            scored.sort(key=lambda x: x[1], reverse=True)
            books = [b for b, _ in scored[:book_limit]]
            candidates = build_book_candidates(session, books)
            for i, (_, score) in enumerate(scored[:book_limit]):
                if i < len(candidates):
                    candidates[i].hybrid_score = score

    books = books[:book_limit]
    candidates = candidates[:book_limit]

    if books:
        StateManager.add_viewed_ids(user_key, {b.id for b in books})
    _store_viewed_books(user_key, candidates)

    conv.last_intent = QueryIntent.SIMILAR_BOOKS
    conv.last_search_query = query
    conv.pending_action = PendingAction.MORE_RECOMMENDATIONS
    StateManager.update_state(user_key, conv)

    return {
        "books": books,
        "candidates": candidates,
        "book_cards": _build_book_cards(books, candidates),
    }


async def node_comparison_agent(state: GraphState) -> dict:
    """
    Agent: comparison — Compare two or more books.

    1. Resolve titles → canonical IDs (via state first, then DB)
    2. Fetch canonical DB data
    3. Compare using ONLY DB facts (never hallucinate)
    """
    session = state["session"]
    query = state["query"]
    targets = state.get("targets", [])
    conv = state["conv_state"]
    user_key = state["user_key"]

    if len(targets) < 2:
        return {
            "response_text": "I need at least two book titles to do a comparison. Could you specify which books you'd like me to compare?",
            "book_cards": [],
            "candidates": [],
            "books": [],
        }

    resolved_books = []
    resolved_candidates = []

    for target in targets[:3]:  # Max 3 books for comparison
        # Try state-based resolution first (retrieval-free)
        by_match = re.match(r'^(.+?)\s+by\s+(.+)$', target.strip(), re.IGNORECASE)
        if by_match:
            title_part = by_match.group(1).strip()
            author_hint = by_match.group(2).strip()
        else:
            title_part = target.strip()
            author_hint = None

        stored = conv.resolve_book_by_title(title_part, author_hint)
        if stored:
            book = session.get(Book, stored.id)
            if book:
                resolved_books.append(book)
                resolved_candidates.append(BookCandidate(
                    id=stored.id, title=stored.title, author=stored.author,
                    genres=stored.genres, pages=stored.pages,
                    pacing=stored.pacing, tone=stored.tone,
                    themes=stored.themes, synopsis_snippet=stored.synopsis_snippet,
                    availability=stored.availability,
                ))
                continue

        # Fallback: DB lookup
        book = session.scalar(
            select(Book).where(Book.title.ilike(f"%{title_part}%"))
        )
        if book:
            resolved_books.append(book)
            avail = get_book_availability(session, book_id=book.id)
            avail_str = f"{avail['available']}/{avail['total']} available" if avail else ""
            resolved_candidates.append(BookCandidate(
                id=book.id, title=book.title, author=book.author,
                genres=book.genres, pages=book.pages,
                pacing=book.pacing, tone=book.tone,
                themes=book.themes if book.themes else [],
                synopsis_snippet=(book.synopsis or book.description or "")[:150],
                availability=avail_str,
            ))

    if len(resolved_candidates) < 2:
        return {
            "response_text": f"I couldn't find all the books you mentioned in our collection. I found {len(resolved_candidates)} of {len(targets)} titles.",
            "book_cards": [],
            "candidates": [],
            "books": [],
        }

    _store_viewed_books(user_key, resolved_candidates)
    StateManager.add_viewed_ids(user_key, {c.id for c in resolved_candidates})
    conv.last_intent = QueryIntent.COMPARISON
    conv.pending_action = PendingAction.DETAILS_AFTER_COMPARISON
    StateManager.update_state(user_key, conv)

    return {
        "books": resolved_books,
        "candidates": resolved_candidates,
        "book_cards": _build_book_cards(resolved_books, resolved_candidates),
    }


async def node_book_details_agent(state: GraphState) -> dict:
    """
    Agent: book_details — Provide detailed info about a single book.

    1. Resolve title from conversation state (viewed_books) first
    2. Fallback to DB lookup
    3. Return single candidate for node_explain to describe
    """
    session = state["session"]
    query = state["query"]
    targets = state.get("targets", [])
    conv = state["conv_state"]
    user_key = state["user_key"]

    resolved_book = None
    resolved_candidate = None

    # Try to resolve from pre-resolved IDs (from state_gate)
    resolved_ids = state.get("resolved_book_ids", [])
    if resolved_ids:
        book = session.get(Book, resolved_ids[0])
        if book:
            resolved_book = book

    # Try to resolve from targets
    if not resolved_book and targets:
        for target in targets:
            # Try state resolution first
            by_match = re.match(r'^(.+?)\s+by\s+(.+)$', target.strip(), re.IGNORECASE)
            if by_match:
                stored = conv.resolve_book_by_title(by_match.group(1).strip(), by_match.group(2).strip())
            else:
                stored = conv.resolve_book_by_title(target)

            if stored:
                book = session.get(Book, stored.id)
                if book:
                    resolved_book = book
                    break

            # Fallback: DB lookup
            book = session.scalar(
                select(Book).where(Book.title.ilike(f"%{target}%"))
            )
            if book:
                resolved_book = book
                break

    # Last resort: try the raw query itself as a title
    if not resolved_book:
        # Strip common prefixes
        title_query = re.sub(
            r'^(yes|yeah|sure)?\s*(about|tell\s+me\s+about|more\s+(info|details?)\s+(on|about))?\s*',
            '', query, flags=re.IGNORECASE,
        ).strip()
        if title_query:
            # Try state
            stored = conv.resolve_book_by_title(title_query)
            if stored:
                resolved_book = session.get(Book, stored.id)
            # Try DB
            if not resolved_book:
                resolved_book = session.scalar(
                    select(Book).where(Book.title.ilike(f"%{title_query}%"))
                )

    if not resolved_book:
        target_name = targets[0] if targets else "that book"
        return {
            "response_text": f'I couldn\'t find "{target_name}" in our collection. Could you double-check the title?',
            "book_cards": [],
            "candidates": [],
            "books": [],
        }

    # Build candidate from resolved book
    avail = get_book_availability(session, book_id=resolved_book.id)
    avail_str = f"{avail['available']}/{avail['total']} available" if avail else ""
    resolved_candidate = BookCandidate(
        id=resolved_book.id,
        title=resolved_book.title,
        author=resolved_book.author,
        genres=resolved_book.genres,
        pages=resolved_book.pages,
        pacing=resolved_book.pacing,
        tone=resolved_book.tone,
        themes=resolved_book.themes if resolved_book.themes else [],
        synopsis_snippet=(resolved_book.synopsis or resolved_book.description or "")[:300],
        availability=avail_str,
    )

    _store_viewed_books(user_key, [resolved_candidate])
    StateManager.add_viewed_ids(user_key, {resolved_book.id})
    conv.last_intent = QueryIntent.BOOK_DETAILS
    conv.pending_action = PendingAction.DETAILS_AFTER_RECO
    StateManager.update_state(user_key, conv)

    return {
        "books": [resolved_book],
        "candidates": [resolved_candidate],
        "book_cards": _build_book_cards([resolved_book], [resolved_candidate]),
    }


async def node_conversation_agent(state: GraphState) -> dict:
    """
    Agent: conversation — General chat (clarification, etc).
    Must NOT override routing.
    """
    query = state["query"]
    intent = state.get("intent", "")

    # Clarification: ask for more detail
    if intent == QueryIntent.CLARIFICATION.value:
        llm = get_generation_llm()
        prompt = CLARIFYING_PROMPT.format(query=query)
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        return {
            "response_text": response.content,
            "book_cards": [],
            "candidates": [],
        }

    # Generic conversation fallback
    llm = get_generation_llm()
    prompt = GENERAL_LIBRARY_PROMPT.format(query=query)
    response = await llm.ainvoke([HumanMessage(content=prompt)])
    return {
        "response_text": response.content,
        "book_cards": [],
        "candidates": [],
    }


async def node_explain(state: GraphState) -> dict:
    """
    Node: explain — LLM generates natural language explanation from results.

    This is the ONLY node where the LLM sees retrieved book data.
    All similarity/ranking was already done in code by the agent nodes.
    """
    candidates = state.get("candidates", [])
    query = state["query"]
    history = state.get("history", [])
    user_prefs = state.get("user_prefs")
    intent = state.get("intent", "")

    if not candidates:
        # No candidates means the agent already produced response_text
        return {}

    llm = get_generation_llm()
    conv = state.get("conv_state")

    # Determine if we should suppress user prefs
    filters = state.get("filters")
    has_explicit_filters = filters and _has_substantive_filters(filters)

    user_context = "" if has_explicit_filters else _build_user_context(user_prefs)
    candidates_text = _format_candidates(candidates)
    history_text = _format_history(history)

    # Build active topic context for continuity
    active_topic = ""
    if conv and conv.last_filters and conv.last_filters.genre:
        active_topic = f"ACTIVE TOPIC: The user is currently browsing {conv.last_filters.genre} books. Acknowledge this when providing more recommendations."
    elif conv and conv.last_search_query and intent == QueryIntent.RECOMMENDATION.value:
        active_topic = f"ACTIVE TOPIC: The user's current search is: \"{conv.last_search_query}\". Keep recommendations relevant to this topic."

    # Pick the right system prompt based on intent
    if intent == QueryIntent.COMPARISON.value:
        system_prompt = COMPARE_SYSTEM_PROMPT.format(candidates=candidates_text)
    elif intent == QueryIntent.BOOK_DETAILS.value:
        system_prompt = BOOK_DETAILS_PROMPT.format(candidates=candidates_text, query=query)
    else:
        system_prompt = GENERATION_SYSTEM_PROMPT.format(
            user_context=user_context,
            candidates=candidates_text,
            active_topic=active_topic,
        )

    user_prompt = GENERATION_USER_TEMPLATE.format(
        query=query, history=history_text,
    )

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]

    response = await llm.ainvoke(messages)
    text = response.content

    # Guardrail validation
    is_valid, errors = validate_response(text, candidates)
    if not is_valid:
        logger.warning(f"[explain] Validation failed: {errors}")
        # One repair attempt
        repair_prompt = build_repair_prompt(query, errors, candidates)
        repair_response = await llm.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=repair_prompt),
        ])
        text = repair_response.content

    # Add hidden ID tracking for history
    ids = [str(c.id) for c in candidates]
    if ids:
        text += f"\n<!-- IDs: {','.join(ids)} -->"

    return {"response_text": text}


async def node_account_action_agent(state: GraphState) -> dict:
    """
    Agent: account_action — Save, borrow, or return a book.
    Performs the actual operation via services (no hallucination).
    """
    query = state["query"]
    session = state["session"]
    user = state.get("user")
    user_key = state.get("user_key", "guest")
    conv = state.get("conv_state") or StateManager.get_state(user_key)
    targets = state.get("targets", [])

    # Must be logged in
    if not user:
        return {
            "response_text": "Please log in to save or borrow books. You can log in using the account button at the top of the page.",
            "book_cards": [],
            "candidates": [],
        }

    # Determine action type from query
    query_lower = query.lower()
    if any(word in query_lower for word in ["return"]):
        action = "return"
    elif any(word in query_lower for word in ["borrow", "check out", "checkout", "issue"]):
        action = "borrow"
    else:
        action = "save"  # save, add, put into my books

    # Resolve the book
    book_id = None
    book_title = None

    # 1. Try targets from intent parser
    if targets:
        title_query = targets[0]
        stored = conv.resolve_book_by_title(title_query)
        if stored:
            book_id = stored.id
            book_title = stored.title
        else:
            # Try DB lookup by title
            from sqlalchemy import func as sqlfunc
            db_book = session.scalars(
                select(Book).where(
                    sqlfunc.lower(Book.title).contains(title_query.lower())
                ).limit(1)
            ).first()
            if db_book:
                book_id = db_book.id
                book_title = db_book.title

    # 2. Try resolved_book_ids from state_gate
    if not book_id:
        resolved_ids = state.get("resolved_book_ids", [])
        if resolved_ids:
            book_id = resolved_ids[0]
            db_book = session.get(Book, book_id)
            if db_book:
                book_title = db_book.title

    # 3. Try the most recently viewed book
    if not book_id and conv.viewed_books:
        last_book = list(conv.viewed_books.values())[-1]
        book_id = last_book.id
        book_title = last_book.title

    if not book_id:
        return {
            "response_text": "I'm not sure which book you mean. Could you tell me the title?",
            "book_cards": [],
            "candidates": [],
        }

    # Perform the action
    if action == "save":
        from app.services.saved_books import save_book, is_book_saved
        if is_book_saved(session, user_id=user.id, book_id=book_id):
            result_msg = f"**{book_title}** is already in your saved books! 💛"
        else:
            save_book(session, user_id=user.id, book_id=book_id)
            result_msg = f"✓ **{book_title}** has been saved to your collection! 💛"
    elif action == "borrow":
        from app.services.borrow import borrow_book
        success, result_msg = borrow_book(session, user.id, book_id)
    elif action == "return":
        from app.services.borrow import return_book
        success, result_msg = return_book(session, user.id, book_id)
    else:
        result_msg = "I'm not sure what action you'd like me to take."

    logger.info(f"[account_action] action={action} book_id={book_id} title={book_title}")

    return {
        "response_text": result_msg,
        "book_cards": [],
        "candidates": [],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# GRAPH ROUTING (deterministic — no LLM)
# ═══════════════════════════════════════════════════════════════════════════════

def route_after_state_gate(state: GraphState) -> str:
    """Deterministic: skip_to takes priority, then check early_exit."""
    if state.get("skip_to"):
        return state["skip_to"]
    if state.get("early_exit"):
        return "conversation_agent"
    return "intent_parser"


def route_after_intent_parser(state: GraphState) -> str:
    """Deterministic: map intent string → agent node name."""
    if state.get("early_exit"):
        return "conversation_agent"

    intent = state.get("intent", "")

    INTENT_TO_AGENT = {
        QueryIntent.GENERAL_INFO.value: "general_info_agent",
        QueryIntent.USER_HISTORY.value: "user_history_agent",
        QueryIntent.RECOMMENDATION.value: "recommendation_agent",
        QueryIntent.SIMILAR_BOOKS.value: "similar_books_agent",
        QueryIntent.COMPARISON.value: "comparison_agent",
        QueryIntent.BOOK_DETAILS.value: "book_details_agent",
        QueryIntent.CONTINUATION.value: "recommendation_agent",
        QueryIntent.CLARIFICATION.value: "conversation_agent",
        QueryIntent.ACCOUNT_ACTION.value: "account_action_agent",
    }

    return INTENT_TO_AGENT.get(intent, "conversation_agent")


def route_after_agent(state: GraphState) -> str:
    """After an agent runs: if it produced candidates, go to explain. Otherwise END."""
    candidates = state.get("candidates", [])
    if candidates:
        return "explain"
    return END


# ═══════════════════════════════════════════════════════════════════════════════
# GRAPH CONSTRUCTION
# ═══════════════════════════════════════════════════════════════════════════════

def build_graph() -> StateGraph:
    """Build the LangGraph StateGraph with all nodes and deterministic edges."""
    graph = StateGraph(GraphState)

    # Add nodes
    graph.add_node("state_gate", node_state_gate)
    graph.add_node("intent_parser", node_intent_parser)
    graph.add_node("general_info_agent", node_general_info_agent)
    graph.add_node("user_history_agent", node_user_history_agent)
    graph.add_node("recommendation_agent", node_recommendation_agent)
    graph.add_node("similar_books_agent", node_similar_books_agent)
    graph.add_node("comparison_agent", node_comparison_agent)
    graph.add_node("book_details_agent", node_book_details_agent)
    graph.add_node("conversation_agent", node_conversation_agent)
    graph.add_node("account_action_agent", node_account_action_agent)
    graph.add_node("explain", node_explain)

    # Set entry point
    graph.set_entry_point("state_gate")

    # Conditional edges
    graph.add_conditional_edges("state_gate", route_after_state_gate, {
        "intent_parser": "intent_parser",
        "recommendation_agent": "recommendation_agent",
        "similar_books_agent": "similar_books_agent",
        "comparison_agent": "comparison_agent",
        "book_details_agent": "book_details_agent",
        "conversation_agent": "conversation_agent",
    })

    graph.add_conditional_edges("intent_parser", route_after_intent_parser, {
        "general_info_agent": "general_info_agent",
        "user_history_agent": "user_history_agent",
        "recommendation_agent": "recommendation_agent",
        "similar_books_agent": "similar_books_agent",
        "comparison_agent": "comparison_agent",
        "book_details_agent": "book_details_agent",
        "conversation_agent": "conversation_agent",
        "account_action_agent": "account_action_agent",
    })

    # Agent → explain or END
    for agent in ["recommendation_agent", "similar_books_agent", "comparison_agent", "book_details_agent"]:
        graph.add_conditional_edges(agent, route_after_agent, {
            "explain": "explain",
            END: END,
        })

    # These agents always go to END (no candidates to explain)
    graph.add_edge("general_info_agent", END)
    graph.add_edge("user_history_agent", END)
    graph.add_edge("conversation_agent", END)
    graph.add_edge("account_action_agent", END)
    graph.add_edge("explain", END)

    return graph


# Compile the graph once at module level
_compiled_graph = None

def get_compiled_graph():
    """Get or create the compiled graph (singleton)."""
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph().compile()
    return _compiled_graph


# ═══════════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ═══════════════════════════════════════════════════════════════════════════════

async def run_graph_pipeline(
    session: Session,
    query: str,
    history: list[dict],
    user: Optional[User] = None,
    book_limit: int = 5,
    session_id: str = "guest",
) -> tuple[AsyncGenerator[str, None], list[BookCard]]:
    """
    Run the LangGraph pipeline. Returns (text_generator, book_cards).

    This is the public API called by streaming.py.
    """
    user_key = str(user.id) if user else session_id
    conv_state = StateManager.get_state(user_key)
    user_prefs = _load_user_prefs(session, user)

    initial_state: GraphState = {
        "query": query,
        "history": history,
        "session": session,
        "user": user,
        "user_prefs": user_prefs,
        "book_limit": book_limit,
        "conv_state": conv_state,
        "user_key": user_key,
        "early_exit": False,
    }

    graph = get_compiled_graph()
    result = await graph.ainvoke(initial_state)

    response_text = result.get("response_text", "I'm not sure how to help with that. Could you rephrase your question?")
    book_cards = result.get("book_cards", [])

    # Wrap text in an async generator for streaming compatibility
    async def text_stream():
        yield response_text

    return text_stream(), book_cards
