"""
Entry point for the Library Assistant FastAPI application.
"""

from __future__ import annotations

import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.api.routes import auth as auth_router, books as books_router, chat as chat_router, saved_books as saved_books_router, voice as voice_router, users as users_router
from app.api.routes import reading_lists as reading_lists_router
from app.database import engine, init_pgvector
from app.models import Base

# Rate limiter - uses IP address to track requests
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="Library Assistant API",
    description="Backend services for managing the library catalogue and availability.",
    version="0.1.0",
)

# Add rate limiter to app state
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Configure CORS - use environment variable for production
# Format: comma-separated list, e.g., "http://localhost:3000,https://myapp.com"
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000")
allowed_origins = [origin.strip() for origin in CORS_ORIGINS.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    """
    Ensure database schema is created when the app starts.
    """
    # Enable pgvector extension before creating tables
    init_pgvector()
    Base.metadata.create_all(bind=engine)


app.include_router(auth_router.router)
app.include_router(books_router.router)
app.include_router(chat_router.router)
app.include_router(saved_books_router.router)
app.include_router(voice_router.router)
app.include_router(users_router.router)
app.include_router(reading_lists_router.router)


# To run: uvicorn app.main:app --reload
