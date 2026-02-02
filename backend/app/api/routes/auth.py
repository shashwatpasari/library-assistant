"""
Authentication routes for user signup and login.
"""

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from app.models import User

from app.api.dependencies import db_session_dependency, get_current_user
from app.schemas import (
    ChangeEmail,
    ChangePassword,
    ForgotPassword,
    ResetPassword,
    Token,
    UserCreate,
    UserLogin,
    UserRead,
)
from app.services.auth import (
    authenticate_user,
    create_access_token,
    create_password_reset_token,
    create_user,
    get_user_by_email,
    get_user_by_id,
    reset_user_password,
    update_user_email,
    update_user_password,
    validate_password_strength,
    verify_password_reset_token,
)

router = APIRouter(prefix="/auth", tags=["authentication"])

# Rate limiter for auth endpoints
limiter = Limiter(key_func=get_remote_address)

# oauth2_scheme moved to dependencies.py


@router.post("/signup", response_model=Token, status_code=status.HTTP_201_CREATED)
@limiter.limit("3/minute")  # Prevent mass account creation
def signup(user_data: UserCreate, request: Request, session: Session = Depends(db_session_dependency)) -> Token:
    """Register a new user account."""
    # Validate password strength
    is_valid, error_msg = validate_password_strength(user_data.password)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg,
        )
    
    # Check if email already exists
    existing_user = get_user_by_email(session, user_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists",
        )

    # Create new user
    user = create_user(
        session=session,
        email=user_data.email,
        full_name=user_data.full_name,
        password=user_data.password,
    )

    # Create access token
    access_token = create_access_token(data={"sub": str(user.id)})

    return Token(
        access_token=access_token,
        token_type="bearer",
        user=UserRead(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            created_at=user.created_at.isoformat(),
        ),
    )


@router.post("/login", response_model=Token)
@limiter.limit("5/minute")  # Prevent brute force attacks
def login(
    user_credentials: UserLogin,
    request: Request,
    session: Session = Depends(db_session_dependency),
) -> Token:
    """Authenticate a user and return an access token."""
    user = authenticate_user(session, user_credentials.email, user_credentials.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create access token
    access_token = create_access_token(data={"sub": str(user.id)})

    # Check onboarding status
    from sqlalchemy import select
    from app.models import UserPreference
    
    # Check if preferences exist
    pref = session.scalar(select(UserPreference).where(UserPreference.user_id == user.id))
    onboarding_status = pref.onboarding_completed if pref else False

    return Token(
        access_token=access_token,
        token_type="bearer",
        user=UserRead(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            created_at=user.created_at.isoformat(),
            onboarding_completed=onboarding_status
        ),
    )


# get_current_user moved to dependencies.py


@router.get("/me", response_model=UserRead)
def get_current_user(
    current_user: "User" = Depends(get_current_user),
) -> UserRead:
    """Get the current authenticated user."""
    return UserRead(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        created_at=current_user.created_at.isoformat(),
    )


@router.post("/change-email", response_model=UserRead)
def change_email(
    email_data: ChangeEmail,
    current_user: "User" = Depends(get_current_user),
    session: Session = Depends(db_session_dependency),
) -> UserRead:
    """Change user email address."""
    # Validate that new emails match
    if email_data.new_email != email_data.confirm_new_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New email addresses do not match",
        )

    try:
        user = update_user_email(
            session=session,
            user_id=current_user.id,
            current_email=email_data.current_email,
            new_email=email_data.new_email,
        )
        return UserRead(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            created_at=user.created_at.isoformat(),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/change-password", response_model=dict)
def change_password(
    password_data: ChangePassword,
    current_user: "User" = Depends(get_current_user),
    session: Session = Depends(db_session_dependency),
) -> dict:
    """Change user password."""
    # Validate that new passwords match
    if password_data.new_password != password_data.confirm_new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New passwords do not match",
        )
    
    # Validate password strength
    is_valid, error_msg = validate_password_strength(password_data.new_password)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg,
        )

    try:
        update_user_password(
            session=session,
            user_id=current_user.id,
            current_password=password_data.current_password,
            new_password=password_data.new_password,
        )
        return {"message": "Password changed successfully"}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/forgot-password", response_model=dict)
@limiter.limit("3/minute")  # Prevent email enumeration attacks
async def forgot_password(
    forgot_data: ForgotPassword,
    request: Request,
    session: Session = Depends(db_session_dependency),
) -> dict:
    """Generate a password reset token for a user and send it via email."""
    user = get_user_by_email(session, forgot_data.email)
    if not user:
        # Don't reveal if email exists for security
        return {"message": "If the email exists, a reset token has been generated and sent to your email"}
    
    # Create reset token
    reset_token = create_password_reset_token(forgot_data.email)
    
    # Send password reset email
    from app.services.email import send_password_reset_email
    email_sent = await send_password_reset_email(
        email=forgot_data.email,
        reset_token=reset_token,
        user_name=user.full_name
    )
    
    if not email_sent:
        # Log error but don't reveal to user for security
        pass
    
    # Always return the same message for security (don't reveal if email exists)
    return {"message": "If the email exists, a reset token has been generated and sent to your email"}


@router.post("/reset-password", response_model=dict)
def reset_password(
    reset_data: ResetPassword,
    session: Session = Depends(db_session_dependency),
) -> dict:
    """Reset password using a reset token."""
    # Validate that new passwords match
    if reset_data.new_password != reset_data.confirm_new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New passwords do not match",
        )
    
    # Validate password strength
    is_valid, error_msg = validate_password_strength(reset_data.new_password)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg,
        )

    try:
        reset_user_password(
            session=session,
            email=reset_data.email,
            reset_token=reset_data.reset_token,
            new_password=reset_data.new_password,
        )
        return {"message": "Password reset successfully"}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

