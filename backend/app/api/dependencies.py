"""
Shared API dependencies for FastAPI routes.
"""

from __future__ import annotations

from collections.abc import Generator


from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database import SessionLocal
# We'll use TYPE_CHECKING to avoid circular import at runtime if needed, 
# but models imports are usually fine if models.py doesn't import dependencies.
from app.models import User 

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

def get_db_session() -> Generator[Session, None, None]:
    """
    Yield a SQLAlchemy session for request-scoped usage.
    """
    session: Session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def db_session_dependency(session: Session = Depends(get_db_session)) -> Session:
    """
    FastAPI dependency wrapper for injecting a database session.
    """
    return session


def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: Session = Depends(db_session_dependency),
) -> User:
    """Get the current authenticated user as a dependency."""
    from app.services.auth import decode_access_token, get_user_by_id

    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id: str = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = get_user_by_id(session, int(user_id))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


