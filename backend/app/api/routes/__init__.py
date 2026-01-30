"""
Expose route modules for FastAPI.
"""

from app.api.routes import books, chat

__all__ = ["books", "chat"]


