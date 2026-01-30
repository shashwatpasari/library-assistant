"""
Database session and engine configuration for the library backend.
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import DATABASE_URL

engine = create_engine(
    DATABASE_URL,
    future=True,
    echo=False,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

def init_pgvector():
    """Enable pgvector extension."""
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()

@contextmanager
def get_session() -> Iterator[Session]:
    """
    Provide a transactional scope for database operations.

    This helper is used outside of the FastAPI dependency system.
    """
    session: Session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


