"""
Hybrid retrieval system combining lexical and vector search with RRF fusion.

Features:
- Lexical search: Postgres tsvector full-text search
- Vector search: pgvector cosine distance
- RRF (Reciprocal Rank Fusion) for combining rankings
- Title lookup with exact/ILIKE priority
- User preference exclusion filtering
"""

from typing import Optional
import logging
import re
from sqlalchemy import select, text, func, or_, and_, String
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.models import Book, UserPreference
from app.services.embedding import generate_embedding
from app.services.books import get_book_availability
from app.rag.schemas import FilterOutput, BookCandidate, QueryIntent
from app.rag.cache import get_cached_embedding, cache_embedding
from app.config import RETRIEVAL_CANDIDATE_LIMIT, RRF_K


def get_query_embedding(query: str) -> list[float]:
    """Get embedding for query, using cache if available."""
    hit, cached = get_cached_embedding(query)
    if hit:
        return cached
    
    embedding = generate_embedding(query)
    cache_embedding(query, embedding)
    return embedding


def apply_user_exclusions(
    session: Session,
    books: list[Book],
    prefs: Optional[UserPreference],
    refill_candidates: Optional[list[Book]] = None,
    exclude_ids: Optional[list[int]] = None,
    target_count: int = 10,
) -> list[Book]:
    """
    Apply hard exclusions from user preferences and explicit ID list.
    
    Filters out books that:
    - Are in the exclude_ids list (previously shown)
    - Match disliked genres
    - Contain content warnings matching triggers_to_avoid
    
    If too many books are filtered, attempts to refill from additional candidates.
    
    Args:
        session: Database session
        books: List of candidate books
        prefs: User preferences (None if no user/preferences)
        refill_candidates: Additional candidates to pull from if needed
        exclude_ids: List of book IDs to explicitly exclude
        target_count: Target number of books to return
        
    Returns:
        Filtered list of books
    """
    disliked_genres = set(g.lower() for g in (prefs.disliked_genres or [])) if prefs else set()
    triggers = set(t.lower() for t in (prefs.triggers_to_avoid or [])) if prefs else set()
    excluded_ids_set = set(exclude_ids or [])
    
    if not disliked_genres and not triggers and not excluded_ids_set:
        return books
    
    def is_excluded(book: Book) -> bool:
        # Check explicit ID exclusions
        if book.id in excluded_ids_set:
            return True

        # Check disliked genres
        if book.genres and disliked_genres:
            book_genres = set(g.strip().lower() for g in book.genres.split(','))
            if book_genres & disliked_genres:
                return True
        
        # Check content warnings
        if book.content_warnings and triggers:
            book_warnings = set(w.lower() for w in book.content_warnings)
            if book_warnings & triggers:
                return True
        
        return False
    
    filtered = [b for b in books if not is_excluded(b)]
    
    # Refill if needed
    if len(filtered) < target_count and refill_candidates:
        for candidate in refill_candidates:
            if candidate.id not in {b.id for b in filtered} and not is_excluded(candidate):
                filtered.append(candidate)
                if len(filtered) >= target_count:
                    break
    
    return filtered


def lexical_search(
    session: Session,
    query: str,
    filters: Optional[FilterOutput] = None,
    limit: int = 50,
) -> list[tuple[Book, float]]:
    """
    Perform full-text search using Postgres tsvector.
    
    Returns list of (book, rank) tuples ordered by relevance.
    
    Note: This requires the 'tsv' column to be present (added via migration).
    If not present, falls back to ILIKE search.
    """
    search_term = filters.search_query if filters else query
    
    # Try tsvector search first (if column exists)
    try:
        # Use plainto_tsquery for natural language query
        stmt = text("""
            SELECT id, ts_rank(tsv, plainto_tsquery('english', :query)) as rank
            FROM books
            WHERE tsv @@ plainto_tsquery('english', :query)
            ORDER BY rank DESC
            LIMIT :limit
        """)
        
        result = session.execute(stmt, {"query": search_term, "limit": limit})
        rows = result.fetchall()
        
        if rows:
            book_ids = [row[0] for row in rows]
            ranks = {row[0]: row[1] for row in rows}
            
            books = session.execute(
                select(Book).where(Book.id.in_(book_ids))
            ).scalars().all()
            
            # Maintain order by rank
            book_map = {b.id: b for b in books}
            return [(book_map[bid], ranks[bid]) for bid in book_ids if bid in book_map]
    
    except Exception as e:
        # tsv column might not exist yet, fall back to ILIKE
        logger.warning(f"[Retriever] tsvector search failed, falling back to ILIKE: {e}")
    
    # Fallback: ILIKE search on title, author, synopsis, subjects
    stmt = select(Book).where(
        or_(
            Book.title.ilike(f"%{search_term}%"),
            Book.author.ilike(f"%{search_term}%"),
            Book.synopsis.ilike(f"%{search_term}%"),
            Book.subjects.ilike(f"%{search_term}%"),
        )
    ).limit(limit)
    
    books = list(session.execute(stmt).scalars())
    # Assign uniform rank for fallback
    return [(b, 1.0) for b in books]


def vector_search(
    session: Session,
    query: str,
    filters: Optional[FilterOutput] = None,
    limit: int = 50,
) -> list[tuple[Book, float]]:
    """
    Perform vector similarity search using pgvector.
    
    Returns list of (book, similarity_score) tuples.
    """
    search_term = filters.search_query if filters else query
    query_embedding = get_query_embedding(search_term)
    
    # Build base query
    stmt = select(Book).where(Book.embedding.is_not(None))
    
    # Apply metadata filters
    if filters:
        stmt = _apply_metadata_filters(stmt, filters)
    
    # Order by cosine distance (lower = more similar)
    stmt = stmt.order_by(Book.embedding.cosine_distance(query_embedding)).limit(limit)
    
    books = list(session.execute(stmt).scalars())
    
    # Convert distance to similarity score (1 - distance for cosine)
    # For ranking purposes, we invert so higher = better
    return [(b, 1.0 / (i + 1)) for i, b in enumerate(books)]

# ── Genre alias normalization ──
_GENRE_ALIASES = {
    "sci-fi": "Science Fiction",
    "scifi": "Science Fiction",
    "sf": "Science Fiction",
    "non-fiction": "Nonfiction",
    "nonfic": "Nonfiction",
    "ya": "Young Adult",
    "lit fic": "Literary Fiction",
    "litfic": "Literary Fiction",
    "hist fic": "Historical Fiction",
    "histfic": "Historical Fiction",
    "bio": "Biography",
    "auto-bio": "Autobiography",
    "autobio": "Autobiography",
    "rom-com": "Romance",
    "romcom": "Romance",
    "psych": "Psychology",
    "phil": "Philosophy",
    "poly sci": "Political Science",
    "polisci": "Political Science",
}


def _normalize_genre(genre: str) -> str:
    """Normalize genre aliases to canonical DB values."""
    return _GENRE_ALIASES.get(genre.lower().strip(), genre)


def _apply_metadata_filters(stmt, filters: FilterOutput):
    """Apply metadata filters to a SQLAlchemy select statement."""
    if filters.max_pages:
        stmt = stmt.where(Book.pages <= filters.max_pages)
    
    if filters.min_pages:
        stmt = stmt.where(Book.pages >= filters.min_pages)
    
    if filters.genre:
        genre = _normalize_genre(filters.genre)
        stmt = stmt.where(Book.genres.ilike(f"%{genre}%"))
    
    if filters.language:
        stmt = stmt.where(Book.language.ilike(f"%{filters.language}%"))
    
    if filters.author:
        stmt = stmt.where(Book.author.ilike(f"%{filters.author}%"))
    
    # Use published_year INT if available, otherwise fall back to string
    if filters.year_start:
        stmt = stmt.where(
            or_(
                Book.published_year >= filters.year_start,
                # Fallback for books without published_year
                and_(
                    Book.published_year.is_(None),
                    Book.date_published >= str(filters.year_start)
                )
            )
        )
    
    if filters.year_end:
        stmt = stmt.where(
            or_(
                Book.published_year <= filters.year_end,
                and_(
                    Book.published_year.is_(None),
                    Book.date_published <= str(filters.year_end)
                )
            )
        )
    
    if filters.pacing:
        stmt = stmt.where(Book.pacing.ilike(f"%{filters.pacing.value}%"))
    
    if filters.tone:
        stmt = stmt.where(Book.tone.ilike(f"%{filters.tone.value}%"))
    
    # JSONB containment for themes
    if filters.themes:
        for theme in filters.themes:
            # Check if theme is in the JSON array
            stmt = stmt.where(
                or_(
                    Book.themes.cast(String).ilike(f"%{theme}%"),
                    Book.subjects.ilike(f"%{theme}%"),
                )
            )
    
    # JSONB containment for moods
    if filters.moods:
        for mood in filters.moods:
            stmt = stmt.where(Book.mood_tags.cast(String).ilike(f"%{mood}%"))
    
    return stmt


def rrf_fusion(
    lexical_results: list[tuple[Book, float]],
    vector_results: list[tuple[Book, float]],
    k: int = 60,
) -> list[Book]:
    """
    Combine lexical and vector search results using Reciprocal Rank Fusion.
    
    RRF score = sum(1 / (k + rank)) for each list where item appears.
    
    Args:
        lexical_results: Results from lexical search with scores
        vector_results: Results from vector search with scores
        k: RRF constant (default 60)
        
    Returns:
        Merged list of books ordered by RRF score
    """
    # Build book ID to Book mapping
    all_books = {}
    
    # Calculate RRF scores
    rrf_scores = {}
    
    for rank, (book, _) in enumerate(lexical_results, start=1):
        all_books[book.id] = book
        rrf_scores[book.id] = rrf_scores.get(book.id, 0) + 1 / (k + rank)
    
    for rank, (book, _) in enumerate(vector_results, start=1):
        all_books[book.id] = book
        rrf_scores[book.id] = rrf_scores.get(book.id, 0) + 1 / (k + rank)
    
    # Sort by RRF score descending
    sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)
    
    return [all_books[bid] for bid in sorted_ids]


def title_lookup(
    session: Session,
    title_query: str,
    limit: int = 5,
    prioritize_ids: Optional[list[int]] = None,
) -> list[Book]:
    """
    Lookup books by exact or close title match.
    
    Priority:
    1. Exact match (case-insensitive) — if multiple, prefer prioritize_ids
    2. ILIKE prefix match
    3. ILIKE contains match
    4. Vector similarity (fallback)
    
    Args:
        prioritize_ids: If provided, books with these IDs are sorted first
                        when there are multiple title matches (e.g. "Perfect"
                        by Sara Shepard vs Ellen Hopkins).
    """
    # Normalize query
    title_clean = title_query.strip()
    
    # Parse "Title by Author" pattern
    author_filter = None
    by_match = re.match(r'^(.+?)\s+by\s+(.+)$', title_clean, re.IGNORECASE)
    if by_match:
        title_clean = by_match.group(1).strip()
        author_filter = by_match.group(2).strip()
    
    def _prioritize(books: list[Book]) -> list[Book]:
        """Sort books so that prioritized IDs and author matches come first."""
        if not books:
            return books
        
        # First: filter by author if specified
        if author_filter:
            author_matches = [
                b for b in books
                if b.author and author_filter.lower() in b.author.lower()
            ]
            if author_matches:
                return author_matches[:limit]
        
        # Then: prioritize by viewed IDs
        if not prioritize_ids or len(books) <= 1:
            return books
        priority_set = set(prioritize_ids)
        prioritized = [b for b in books if b.id in priority_set]
        rest = [b for b in books if b.id not in priority_set]
        return (prioritized + rest)[:limit]
    
    # 1. Exact match
    exact = session.execute(
        select(Book).where(func.lower(Book.title) == title_clean.lower()).limit(limit)
    ).scalars().all()
    
    if exact:
        return _prioritize(list(exact))
    
    # 2. Prefix match
    prefix = session.execute(
        select(Book).where(Book.title.ilike(f"{title_clean}%")).limit(limit)
    ).scalars().all()
    
    if prefix:
        return _prioritize(list(prefix))
    
    # 3. Contains match
    contains = session.execute(
        select(Book).where(Book.title.ilike(f"%{title_clean}%")).limit(limit)
    ).scalars().all()
    
    if contains:
        return _prioritize(list(contains))
    
    # 4. Vector fallback
    embedding = get_query_embedding(title_clean)
    vector_results = session.execute(
        select(Book)
        .where(Book.embedding.is_not(None))
        .order_by(Book.embedding.cosine_distance(embedding))
        .limit(limit)
    ).scalars().all()
    
    return list(vector_results)


def hybrid_retrieve(
    session: Session,
    query: str,
    filters: Optional[FilterOutput] = None,
    user_prefs: Optional[UserPreference] = None,
    exclude_ids: Optional[list[int]] = None,
    limit: int = 10,
) -> list[Book]:
    """
    Main hybrid retrieval function.
    
    Combines lexical and vector search with RRF, applies exclusions,
    and returns top-K results.
    
    Args:
        session: Database session
        query: Search query
        filters: Extracted filters
        user_prefs: User preferences for exclusions
        limit: Number of results to return
        
    Returns:
        List of Book objects
    """
    # Retrieve more candidates than needed for filtering
    candidate_limit = min(RETRIEVAL_CANDIDATE_LIMIT, limit * 5)
    
    # Parallel retrieval
    lexical_results = lexical_search(session, query, filters, candidate_limit)
    vector_results = vector_search(session, query, filters, candidate_limit)
    
    # RRF fusion
    fused = rrf_fusion(lexical_results, vector_results, k=RRF_K)
    
    # Apply user exclusions with refill
    # Get extra candidates for refill if exclusions remove too many
    extra_candidates = []
    if len(fused) < limit * 2:
        # Get more vector results as backup
        extra_vector = vector_search(session, query, filters, candidate_limit * 2)
        extra_candidates = [b for b, _ in extra_vector if b.id not in {x.id for x in fused}]
    
    filtered = apply_user_exclusions(
        session, fused, user_prefs,
        refill_candidates=extra_candidates,
        exclude_ids=exclude_ids,
        target_count=limit,
    )
    
    return filtered[:limit]


def build_book_candidates(
    session: Session,
    books: list[Book],
) -> list[BookCandidate]:
    """
    Convert Book models to BookCandidate schemas for LLM context.
    
    - Truncates synopsis to 1-2 sentences
    - Excludes cover URLs (save tokens)
    - Includes availability info
    """
    candidates = []
    
    for book in books:
        # Get availability
        avail = get_book_availability(session, book_id=book.id)
        avail_text = f"{avail.available_copies}/{avail.total_copies} available"
        
        # Truncate synopsis to ~150 chars (1-2 sentences)
        synopsis = book.synopsis or book.description or ""
        if len(synopsis) > 150:
            # Try to cut at sentence boundary
            cut_point = synopsis[:150].rfind('.')
            if cut_point > 50:
                synopsis = synopsis[:cut_point + 1]
            else:
                synopsis = synopsis[:147] + "..."
        
        # Extract themes as list
        themes = []
        if book.themes:
            if isinstance(book.themes, list):
                themes = book.themes[:5]  # Limit to 5 themes
            elif isinstance(book.themes, str):
                themes = [t.strip() for t in book.themes.split(',')][:5]
        
        # Get published year
        pub_year = None
        if hasattr(book, 'published_year') and book.published_year:
            pub_year = book.published_year
        elif book.date_published:
            try:
                pub_year = int(book.date_published[:4])
            except (ValueError, TypeError):
                pass
        
        candidates.append(BookCandidate(
            id=book.id,
            title=book.title,
            author=book.author,
            genres=book.genres,
            pages=book.pages,
            published_year=pub_year,
            pacing=book.pacing,
            tone=book.tone,
            themes=themes,
            synopsis_snippet=synopsis,
            availability=avail_text,
        ))
    
    return candidates


def retrieve_for_intent(
    session: Session,
    query: str,
    intent: QueryIntent,
    targets: list[str],
    filters: Optional[FilterOutput] = None,
    user_prefs: Optional[UserPreference] = None,
    exclude_ids: Optional[list[int]] = None,
    prioritize_ids: Optional[list[int]] = None,
    limit: int = 10,
) -> list[Book]:
    """
    Retrieve books based on intent type.
    
    Intent mapping:
    - SIMILAR_BOOKS: Vector search on target book/author, or title lookup
    - COMPARISON: Title lookup for each target
    - RECOMMENDATION: Hybrid search with filters + preference fallback
    - CONTINUATION: Re-use filters from previous turn
    
    Args:
        prioritize_ids: Book IDs to prefer when resolving ambiguous titles
                        (typically from state.viewed_book_ids)
    """
    if intent == QueryIntent.SIMILAR_BOOKS:
        # If targets are given, find similar books
        search_query = targets[0] if targets else query
        current_exclude_ids = list(exclude_ids) if exclude_ids else []
        
        if targets:
            # Try to identify the target book to exclude it from results
            target_books = title_lookup(session, targets[0], limit=1, prioritize_ids=prioritize_ids)
            if target_books:
                current_exclude_ids.append(target_books[0].id)
        
        return hybrid_retrieve(session, search_query, filters, user_prefs, current_exclude_ids, limit)
    
    elif intent == QueryIntent.COMPARISON:
        # Retrieve each target book — prioritize recently viewed books
        books = []
        for target in targets[:3]:  # Max 3 for comparison
            found = title_lookup(session, target, 1, prioritize_ids=prioritize_ids)
            books.extend(found)
        return books
    
    elif intent in (QueryIntent.RECOMMENDATION, QueryIntent.CONTINUATION):
        # If filters are present (meaningful ones), use them
        has_filters = filters and (
            filters.genre or 
            filters.themes or 
            filters.moods or 
            filters.year_start or 
            filters.pacing or 
            filters.tone or
            filters.author
        )
        
        if has_filters:
            return hybrid_retrieve(session, query, filters, user_prefs, exclude_ids, limit)

        # Use preferences if available, otherwise hybrid search
        if user_prefs:
            from app.services.recommendations import get_personalized_recommendations
            if exclude_ids:
                 return hybrid_retrieve(session, query, filters, user_prefs, exclude_ids, limit)
            
            return get_personalized_recommendations(session, user_prefs.user_id, limit)
        else:
            return hybrid_retrieve(session, query, filters, user_prefs, exclude_ids, limit)
    
    else:
        # Default: hybrid search
        return hybrid_retrieve(session, query, filters, user_prefs, exclude_ids, limit)

