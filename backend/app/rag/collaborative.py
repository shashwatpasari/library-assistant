"""
Collaborative filtering using SVD-based matrix factorization.

Uses scipy's sparse SVD to decompose a user-book interaction matrix
into latent factor embeddings. These embeddings are used alongside
content-based feature vectors for hybrid recommendations.

Interaction data sources:
  - SavedBook (liked books) — weight 2.0
  - BorrowHistory (borrowed books) — weight 1.5
  - ReadingListItem (in reading lists) — weight 1.0
"""

import logging
from typing import Optional

import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.linalg import svds
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.models import (
    Book,
    SavedBook,
    BorrowHistory,
    ReadingListItem,
    ReadingList,
    UserInteraction,
    User,
)

logger = logging.getLogger(__name__)

# SVD config
N_FACTORS = 50           # Collaborative embedding dimension
MIN_INTERACTIONS = 5     # Minimum interactions to include user


def build_interaction_matrix(
    session: Session,
) -> tuple[csr_matrix, list[int], list[int]]:
    """
    Build a sparse user-book interaction matrix from all interaction sources.

    Returns:
        (matrix, user_ids, book_ids) where matrix[i, j] = interaction weight
        for user_ids[i] and book_ids[j].
    """
    # Gather all interactions
    interactions: dict[tuple[int, int], float] = {}

    # Saved books (weight 2.0)
    saved = session.execute(select(SavedBook.user_id, SavedBook.book_id)).all()
    for user_id, book_id in saved:
        key = (user_id, book_id)
        interactions[key] = max(interactions.get(key, 0), 2.0)

    # Borrow history (weight 1.5)
    borrowed = session.execute(
        select(BorrowHistory.user_id, BorrowHistory.book_id)
    ).all()
    for user_id, book_id in borrowed:
        key = (user_id, book_id)
        interactions[key] = max(interactions.get(key, 0), 1.5)

    # Reading list items (weight 1.0)
    rl_items = session.execute(
        select(ReadingList.user_id, ReadingListItem.book_id)
        .join(ReadingListItem, ReadingList.id == ReadingListItem.reading_list_id)
    ).all()
    for user_id, book_id in rl_items:
        key = (user_id, book_id)
        interactions[key] = max(interactions.get(key, 0), 1.0)

    if not interactions:
        return csr_matrix((0, 0)), [], []

    # Build index mappings
    user_ids_set = set()
    book_ids_set = set()
    for (uid, bid) in interactions.keys():
        user_ids_set.add(uid)
        book_ids_set.add(bid)

    user_ids = sorted(user_ids_set)
    book_ids = sorted(book_ids_set)
    user_idx = {uid: i for i, uid in enumerate(user_ids)}
    book_idx = {bid: j for j, bid in enumerate(book_ids)}

    # Build sparse matrix
    rows, cols, vals = [], [], []
    for (uid, bid), weight in interactions.items():
        rows.append(user_idx[uid])
        cols.append(book_idx[bid])
        vals.append(weight)

    matrix = csr_matrix(
        (vals, (rows, cols)),
        shape=(len(user_ids), len(book_ids)),
        dtype=np.float32,
    )

    return matrix, user_ids, book_ids


def train_svd(
    matrix: csr_matrix,
    n_factors: int = N_FACTORS,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Train SVD on the interaction matrix.

    Returns:
        (user_embeddings, book_embeddings) where:
        - user_embeddings.shape = (n_users, n_factors)
        - book_embeddings.shape = (n_books, n_factors)
    """
    n_users, n_books = matrix.shape

    if n_users < 2 or n_books < 2:
        logger.warning(f"Matrix too small for SVD: {n_users}x{n_books}")
        return np.zeros((n_users, n_factors)), np.zeros((n_books, n_factors))

    # Ensure k < min(n_users, n_books)
    k = min(n_factors, min(n_users, n_books) - 1)
    if k < 1:
        return np.zeros((n_users, n_factors)), np.zeros((n_books, n_factors))

    U, sigma, Vt = svds(matrix.astype(np.float64), k=k)

    # Scale by sqrt(sigma) for balanced embeddings
    sqrt_sigma = np.sqrt(np.diag(sigma))
    user_embeddings = U @ sqrt_sigma           # (n_users, k)
    book_embeddings = (sqrt_sigma @ Vt).T      # (n_books, k)

    # Pad to n_factors if k < n_factors
    if k < n_factors:
        user_pad = np.zeros((n_users, n_factors - k))
        book_pad = np.zeros((n_books, n_factors - k))
        user_embeddings = np.hstack([user_embeddings, user_pad])
        book_embeddings = np.hstack([book_embeddings, book_pad])

    return user_embeddings.astype(np.float32), book_embeddings.astype(np.float32)


def train_and_store(session: Session) -> dict:
    """
    Full training pipeline: build matrix, run SVD, store embeddings in DB.

    Returns stats about the training run.
    """
    logger.info("Building interaction matrix...")
    matrix, user_ids, book_ids = build_interaction_matrix(session)

    if matrix.shape[0] == 0:
        logger.warning("No interaction data found, skipping training")
        return {"status": "skipped", "reason": "no_interactions"}

    logger.info(
        f"Interaction matrix: {matrix.shape[0]} users x {matrix.shape[1]} books, "
        f"{matrix.nnz} interactions"
    )

    logger.info(f"Training SVD with {N_FACTORS} factors...")
    user_embeddings, book_embeddings = train_svd(matrix)

    # Store book embeddings
    book_idx = {bid: j for j, bid in enumerate(book_ids)}
    books_updated = 0
    for book_id in book_ids:
        idx = book_idx[book_id]
        emb = book_embeddings[idx].tolist()
        session.execute(
            Book.__table__.update()
            .where(Book.id == book_id)
            .values(collaborative_embedding=emb)
        )
        books_updated += 1

    # Store user embeddings in UserInteraction table
    user_idx = {uid: i for i, uid in enumerate(user_ids)}
    users_updated = 0
    for user_id in user_ids:
        idx = user_idx[user_id]
        emb = user_embeddings[idx].tolist()

        # Count interactions for this user
        count = sum(1 for (uid, _) in zip(
            [k[0] for k in [(uid, bid) for uid in [user_id] for bid in book_ids]],
            book_ids,
        ))

        existing = session.scalar(
            select(UserInteraction).where(UserInteraction.user_id == user_id)
        )
        if existing:
            existing.collaborative_embedding = emb
            existing.interaction_count = int(matrix[user_idx[user_id]].nnz)
        else:
            session.add(UserInteraction(
                user_id=user_id,
                collaborative_embedding=emb,
                interaction_count=int(matrix[user_idx[user_id]].nnz),
            ))
        users_updated += 1

    session.commit()

    stats = {
        "status": "trained",
        "n_users": len(user_ids),
        "n_books": len(book_ids),
        "n_interactions": matrix.nnz,
        "n_factors": N_FACTORS,
        "books_updated": books_updated,
        "users_updated": users_updated,
    }
    logger.info(f"Training complete: {stats}")
    return stats


def get_user_collaborative_embedding(
    session: Session,
    user_id: int,
) -> Optional[list[float]]:
    """Retrieve the stored collaborative embedding for a user."""
    interaction = session.scalar(
        select(UserInteraction).where(UserInteraction.user_id == user_id)
    )
    if interaction and interaction.collaborative_embedding:
        return list(interaction.collaborative_embedding)
    return None


def get_user_interaction_count(
    session: Session,
    user_id: int,
) -> int:
    """Get the total interaction count for a user."""
    interaction = session.scalar(
        select(UserInteraction).where(UserInteraction.user_id == user_id)
    )
    if interaction:
        return interaction.interaction_count

    # Fallback: count from source tables
    saved_count = session.scalar(
        select(func.count()).select_from(SavedBook).where(SavedBook.user_id == user_id)
    ) or 0
    borrowed_count = session.scalar(
        select(func.count()).select_from(BorrowHistory).where(BorrowHistory.user_id == user_id)
    ) or 0
    return saved_count + borrowed_count
