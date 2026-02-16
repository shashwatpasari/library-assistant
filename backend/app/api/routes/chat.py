"""
Chat API routes for RAG-powered library assistant.
"""

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database import get_session
from app.services.chat import generate_response

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatMessage(BaseModel):
    """Single message in conversation."""
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    """Request model for chat endpoint."""
    messages: List[ChatMessage]
    session_id: Optional[str] = None


from app.models import User
from app.api.dependencies import get_current_user, get_current_user_optional

@router.post("/")
async def chat(
    request: ChatRequest,
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """
    Send a message and get a streaming response from the library assistant.
    Supports conversation history for multi-turn conversations.
    """
    # Default to "guest" if not provided, but ideally frontend sends a UUID
    session_id = request.session_id or "guest"

    async def stream_response():
        # Session must be created INSIDE the generator so it stays open
        # during streaming. If created outside (with `with get_session()`),
        # the context manager exits before streaming starts, closing the session.
        with get_session() as session:
            async for chunk in generate_response(session, request.messages, user=current_user, session_id=session_id):
                yield chunk

    return StreamingResponse(
        stream_response(),
        media_type="text/plain"
    )


@router.post("/sync")
def chat_sync(request: ChatRequest):
    """
    Non-streaming version of chat for simpler clients.
    Returns the complete response as JSON.
    """
    import asyncio
    
    with get_session() as session:
        session_id = request.session_id or "guest"
        
        async def collect_response():
            chunks = []
            async for chunk in generate_response(session, request.messages, session_id=session_id):
                chunks.append(chunk)
            return "".join(chunks)
        
        # Run async generator in sync context
        response = asyncio.run(collect_response())
        return {"response": response}
