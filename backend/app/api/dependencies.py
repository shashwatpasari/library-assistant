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

from typing import Optional

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)

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


def get_current_user_optional(
    token: Optional[str] = Depends(oauth2_scheme_optional),
    session: Session = Depends(db_session_dependency),
) -> Optional[User]:
    """
    Get the current user if authenticated, otherwise return None.
    Does not raise HTTPException for missing/invalid tokens.
    """
    if not token:
        return None
        
    from app.services.auth import decode_access_token, get_user_by_id

    try:
        payload = decode_access_token(token)
        if payload is None:
            return None

        user_id: str = payload.get("sub")
        if user_id is None:
            return None

        user = get_user_by_id(session, int(user_id))
        return user

    except Exception:
        # Any error in decoding or lookup -> treat as guest
        return None


