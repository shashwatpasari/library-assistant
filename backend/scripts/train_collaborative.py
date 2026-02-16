"""
Script to train collaborative filtering model and store embeddings.

Usage:
    python -m scripts.train_collaborative

This builds the user-book interaction matrix from SavedBooks,
BorrowHistory, and ReadingListItems, runs SVD factorization,
and stores the resulting embeddings in the database.
"""

import sys
import os
import logging

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import engine
from app.rag.collaborative import train_and_store
from sqlalchemy.orm import Session

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main():
    with Session(engine) as session:
        logger.info("Starting collaborative filtering training...")
        stats = train_and_store(session)
        logger.info(f"Training results: {stats}")


if __name__ == "__main__":
    main()
