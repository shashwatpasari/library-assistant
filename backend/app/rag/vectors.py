"""
Content-based feature vector encoding and hybrid scoring.

All similarity computations happen HERE in code — never by the LLM.
The LLM only handles intent understanding and explanation generation.

Feature vector layout (128 dims):
  - [0:30]   Genre multi-hot (30 known genres)
  - [30:36]  Tone multi-hot (6 known tones)
  - [36:39]  Pacing one-hot (Fast/Moderate/Slow)
  - [39:59]  Theme multi-hot (20 known themes, hashed)
  - [59:63]  Length bucket one-hot (short/medium/long/epic)
  - [63:64]  Rating (scaled 0-1)
  - [64:65]  Popularity (scaled 0-1)
  - [65:97]  Author hash (32-bit hash encoded as 32 binary dims)
  - [97:128] Reserved (padding/future)
"""

import hashlib
import math
from typing import Optional

import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.models import Book, SavedBook, BorrowHistory, ReadingListItem


# ── Known vocabularies ──

KNOWN_GENRES = [
    "fantasy", "sci-fi", "romance", "thriller", "mystery", "horror",
    "historical fiction", "literary fiction", "non-fiction", "biography",
    "memoir", "self-help", "adventure", "dystopian", "comedy", "drama",
    "crime", "western", "paranormal", "urban fantasy", "epic fantasy",
    "young adult", "graphic novel", "poetry", "philosophy", "psychology",
    "magical realism", "steampunk", "cyberpunk", "space opera",
]

KNOWN_TONES = ["dark", "light", "emotional", "suspenseful", "humorous", "neutral"]

KNOWN_PACINGS = ["fast", "moderate", "slow"]

# Using a hashing trick for themes (20 buckets)
THEME_BUCKETS = 20

# Length buckets: short (<200), medium (200-400), long (400-700), epic (700+)
LENGTH_THRESHOLDS = [200, 400, 700]

VECTOR_DIM = 128


def _genre_multi_hot(genres_str: Optional[str]) -> np.ndarray:
    """Encode genres as a 30-dim multi-hot vector."""
    vec = np.zeros(len(KNOWN_GENRES), dtype=np.float32)
    if not genres_str:
        return vec
    genres_lower = genres_str.lower()
    for i, genre in enumerate(KNOWN_GENRES):
        if genre in genres_lower:
            vec[i] = 1.0
    return vec


def _tone_multi_hot(tone_str: Optional[str]) -> np.ndarray:
    """Encode tone as a 6-dim multi-hot vector."""
    vec = np.zeros(len(KNOWN_TONES), dtype=np.float32)
    if not tone_str:
        return vec
    tone_lower = tone_str.lower()
    for i, tone in enumerate(KNOWN_TONES):
        if tone in tone_lower:
            vec[i] = 1.0
    return vec


def _pacing_one_hot(pacing_str: Optional[str]) -> np.ndarray:
    """Encode pacing as a 3-dim one-hot vector."""
    vec = np.zeros(len(KNOWN_PACINGS), dtype=np.float32)
    if not pacing_str:
        return vec
    pacing_lower = pacing_str.lower()
    for i, pacing in enumerate(KNOWN_PACINGS):
        if pacing in pacing_lower:
            vec[i] = 1.0
            break
    return vec


def _theme_hash_vector(themes: Optional[list]) -> np.ndarray:
    """Hash themes into a 20-dim vector using feature hashing."""
    vec = np.zeros(THEME_BUCKETS, dtype=np.float32)
    if not themes:
        return vec
    for theme in themes:
        if isinstance(theme, str):
            bucket = hash(theme.lower().strip()) % THEME_BUCKETS
            vec[bucket] = 1.0
    return vec


def _length_one_hot(pages: Optional[int]) -> np.ndarray:
    """Encode page count as a 4-dim one-hot length bucket."""
    vec = np.zeros(4, dtype=np.float32)
    if pages is None or pages <= 0:
        return vec
    if pages < LENGTH_THRESHOLDS[0]:
        vec[0] = 1.0  # short
    elif pages < LENGTH_THRESHOLDS[1]:
        vec[1] = 1.0  # medium
    elif pages < LENGTH_THRESHOLDS[2]:
        vec[2] = 1.0  # long
    else:
        vec[3] = 1.0  # epic
    return vec


def _rating_scaled(rating: Optional[float]) -> np.ndarray:
    """Scale rating to [0, 1]."""
    if rating is None:
        return np.array([0.5], dtype=np.float32)  # neutral default
    return np.array([min(max(rating / 5.0, 0.0), 1.0)], dtype=np.float32)


def _popularity_scaled(popularity: Optional[float]) -> np.ndarray:
    """Scale popularity to [0, 1]."""
    if popularity is None:
        return np.array([0.0], dtype=np.float32)
    return np.array([min(max(popularity, 0.0), 1.0)], dtype=np.float32)


def _author_hash(author: Optional[str]) -> np.ndarray:
    """Hash author name into a 32-dim binary vector."""
    vec = np.zeros(32, dtype=np.float32)
    if not author:
        return vec
    h = hashlib.md5(author.lower().strip().encode()).hexdigest()[:8]  # 32 bits
    bits = bin(int(h, 16))[2:].zfill(32)
    for i, bit in enumerate(bits):
        vec[i] = float(bit)
    return vec


def encode_book_features(book: Book) -> list[float]:
    """
    Build a 128-dim content-based feature vector for a book.

    This is computed entirely in code — no LLM involved.
    """
    parts = [
        _genre_multi_hot(book.genres),           # 30 dims
        _tone_multi_hot(book.tone),              # 6 dims
        _pacing_one_hot(book.pacing),            # 3 dims
        _theme_hash_vector(book.themes),         # 20 dims
        _length_one_hot(book.pages),             # 4 dims
        _rating_scaled(book.rating),             # 1 dim
        _popularity_scaled(book.popularity_score),  # 1 dim
        _author_hash(book.author),               # 32 dims
    ]
    # That's 30+6+3+20+4+1+1+32 = 97 dims
    feature = np.concatenate(parts)

    # Pad to 128 dims
    padding = np.zeros(VECTOR_DIM - len(feature), dtype=np.float32)
    feature = np.concatenate([feature, padding])

    return feature.tolist()


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """
    Compute cosine similarity between two vectors. Done in code, NOT by LLM.

    Returns value in [-1, 1]. Returns 0.0 if either vector is zero.
    """
    a = np.array(vec_a, dtype=np.float32)
    b = np.array(vec_b, dtype=np.float32)

    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)

    if norm_a < 1e-10 or norm_b < 1e-10:
        return 0.0

    return float(np.dot(a, b) / (norm_a * norm_b))


def hybrid_score(
    content_sim: float,
    collaborative_sim: float,
    interaction_count: int,
    threshold_n: int = 10,
) -> float:
    """
    Combine content-based and collaborative similarity scores.

    Dynamic alpha/beta weighting:
    - New users (interaction_count < threshold_n):  alpha=1.0, beta=0.0
    - Established users: alpha decreases, beta increases linearly
    - At 100+ interactions: alpha=0.3, beta=0.7
    """
    if interaction_count < threshold_n:
        # Cold start: pure content-based
        return content_sim

    # Scale from threshold_n to 100 interactions
    progress = min((interaction_count - threshold_n) / (100 - threshold_n), 1.0)
    alpha = 1.0 - 0.7 * progress   # 1.0 → 0.3
    beta = 0.7 * progress           # 0.0 → 0.7

    return alpha * content_sim + beta * collaborative_sim


def compute_user_preference_vector(
    session: Session,
    user_id: int,
) -> Optional[list[float]]:
    """
    Compute a user's preference vector by averaging feature vectors of
    books they've liked (saved), borrowed, or added to reading lists.

    Returns None if the user has no interaction data.
    """
    # Gather all book IDs from liked + borrowed + reading lists
    liked_ids = set(
        session.scalars(
            select(SavedBook.book_id).where(SavedBook.user_id == user_id)
        )
    )

    borrowed_ids = set(
        session.scalars(
            select(BorrowHistory.book_id).where(BorrowHistory.user_id == user_id)
        )
    )

    reading_list_ids = set()
    from app.models import ReadingList
    rl_ids = list(session.scalars(
        select(ReadingList.id).where(ReadingList.user_id == user_id)
    ))
    if rl_ids:
        reading_list_ids = set(session.scalars(
            select(ReadingListItem.book_id).where(
                ReadingListItem.reading_list_id.in_(rl_ids)
            )
        ))

    all_book_ids = liked_ids | borrowed_ids | reading_list_ids
    if not all_book_ids:
        return None

    # Fetch feature vectors for these books
    books = list(session.scalars(
        select(Book).where(
            Book.id.in_(list(all_book_ids)),
            Book.feature_vector.isnot(None),
        )
    ))

    if not books:
        return None

    # Weight: saved=2.0, borrowed=1.5, reading_list=1.0
    vectors = []
    weights = []
    for book in books:
        vec = np.array(book.feature_vector, dtype=np.float32)
        weight = 1.0
        if book.id in liked_ids:
            weight = max(weight, 2.0)
        if book.id in borrowed_ids:
            weight = max(weight, 1.5)
        vectors.append(vec * weight)
        weights.append(weight)

    if not vectors:
        return None

    # Weighted average
    total_weight = sum(weights)
    avg_vector = sum(vectors) / total_weight

    return avg_vector.tolist()


def rank_books_by_hybrid_score(
    user_pref_vector: list[float],
    user_collab_embedding: Optional[list[float]],
    candidates: list[Book],
    interaction_count: int,
) -> list[tuple[Book, float]]:
    """
    Rank candidate books by hybrid score (content + collaborative).

    Returns list of (Book, score) tuples sorted by score descending.
    """
    scored = []
    for book in candidates:
        content_sim = 0.0
        collab_sim = 0.0

        if book.feature_vector is not None:
            content_sim = cosine_similarity(user_pref_vector, list(book.feature_vector))

        if user_collab_embedding is not None and book.collaborative_embedding is not None:
            collab_sim = cosine_similarity(user_collab_embedding, list(book.collaborative_embedding))

        score = hybrid_score(content_sim, collab_sim, interaction_count)
        scored.append((book, score))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored
