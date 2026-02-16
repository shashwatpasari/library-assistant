"""
RAG Chat service - thin wrapper around the LangChain RAG pipeline.
"""

from typing import List, Optional, AsyncGenerator

from sqlalchemy.orm import Session

from app.models import User
from app.rag.streaming import stream_rag_response


async def generate_response(
    session: Session,
    messages: List,
    user: Optional[User] = None,
    session_id: str = "guest"
) -> AsyncGenerator[str, None]:
    """
    Generate streaming response using the LangChain RAG pipeline.
    
    This is the main entry point called by the chat API route.
    
    Args:
        session: SQLAlchemy database session
        messages: List of ChatMessage objects with role and content
        user: Optional current user for personalization
        session_id: Optional session ID for guest state persistence
        
    Yields:
        Text chunks from the LLM response, followed by __JSON_START__ + cards JSON
    """
    async for chunk in stream_rag_response(session, messages, user, session_id):
        yield chunk