"""
Authentication service for user management and JWT token generation.
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timedelta
from typing import Optional, Tuple

import bcrypt
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User

# JWT settings - SECRET_KEY must be set via environment variable in production
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-only-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 7 * 24 * 60  # 7 days (reduced from 30 for security)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password."""
    if isinstance(hashed_password, str):
        hashed_password = hashed_password.encode('utf-8')
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt."""
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def validate_password_strength(password: str) -> Tuple[bool, str]:
    """
    Validate password strength.
    Returns (is_valid, error_message).
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    
    if not re.search(r'\d', password):
        return False, "Password must contain at least one number"
    
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False, "Password must contain at least one special character (!@#$%^&*(),.?\":{}|<>)"
    
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"
    
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"
    
    return True, ""


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    """Decode and verify a JWT access token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


def get_user_by_email(session: Session, email: str) -> Optional[User]:
    """Get a user by email address."""
    stmt = select(User).where(User.email == email)
    return session.scalar(stmt)


def get_user_by_id(session: Session, user_id: int) -> Optional[User]:
    """Get a user by ID."""
    stmt = select(User).where(User.id == user_id)
    return session.scalar(stmt)


def create_user(session: Session, email: str, full_name: str, password: str) -> User:
    """Create a new user."""
    hashed_password = get_password_hash(password)
    user = User(
        email=email,
        full_name=full_name,
        hashed_password=hashed_password,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def authenticate_user(session: Session, email: str, password: str) -> Optional[User]:
    """Authenticate a user by email and password."""
    user = get_user_by_email(session, email)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def update_user_email(session: Session, user_id: int, current_email: str, new_email: str) -> User:
    """Update user email after verifying current email matches."""
    user = get_user_by_id(session, user_id)
    if not user:
        raise ValueError("User not found")
    if user.email != current_email:
        raise ValueError("Current email does not match")
    if user.email == new_email:
        raise ValueError("New email is the same as current email")
    
    # Check if new email is already taken
    existing_user = get_user_by_email(session, new_email)
    if existing_user and existing_user.id != user_id:
        raise ValueError("Email is already taken")
    
    user.email = new_email
    session.commit()
    session.refresh(user)
    return user


def update_user_password(session: Session, user_id: int, current_password: str, new_password: str) -> User:
    """Update user password after verifying current password."""
    user = get_user_by_id(session, user_id)
    if not user:
        raise ValueError("User not found")
    if not verify_password(current_password, user.hashed_password):
        raise ValueError("Current password is incorrect")
    
    user.hashed_password = get_password_hash(new_password)
    session.commit()
    session.refresh(user)
    return user


def create_password_reset_token(email: str) -> str:
    """Create a password reset token for an email."""
    # Token expires in 1 hour
    expire = datetime.utcnow() + timedelta(hours=1)
    payload = {
        "email": email,
        "type": "password_reset",
        "exp": expire,
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return token


def verify_password_reset_token(token: str) -> Optional[str]:
    """Verify a password reset token and return the email if valid."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "password_reset":
            return None
        return payload.get("email")
    except JWTError:
        return None


def reset_user_password(session: Session, email: str, reset_token: str, new_password: str) -> User:
    """Reset user password using a reset token."""
    # Verify token
    token_email = verify_password_reset_token(reset_token)
    if not token_email or token_email != email:
        raise ValueError("Invalid or expired reset token")
    
    # Get user
    user = get_user_by_email(session, email)
    if not user:
        raise ValueError("User not found")
    
    # Update password
    user.hashed_password = get_password_hash(new_password)
    session.commit()
    session.refresh(user)
    return user

