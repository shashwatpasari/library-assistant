"""
Entry point for the Library Assistant FastAPI application.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import auth as auth_router, books as books_router, chat as chat_router, saved_books as saved_books_router, voice as voice_router, users as users_router
from app.database import engine
from app.models import Base

app = FastAPI(
    title="Library Assistant API",
    description="Backend services for managing the library catalogue and availability.",
    version="0.1.0",
)

# Configure CORS to allow frontend requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    """
    Ensure database schema is created when the app starts.
    """
    Base.metadata.create_all(bind=engine)


app.include_router(auth_router.router)
app.include_router(books_router.router)
app.include_router(chat_router.router)
app.include_router(saved_books_router.router)
app.include_router(voice_router.router)
app.include_router(users_router.router)


# To run: uvicorn app.main:app --reload


