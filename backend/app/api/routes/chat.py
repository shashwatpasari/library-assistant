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


from app.models import User
from app.api.dependencies import get_current_user

@router.post("/")
async def chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Send a message and get a streaming response from the library assistant.
    Supports conversation history for multi-turn conversations.
    """
    with get_session() as session:
        async def stream_response():
            async for chunk in generate_response(session, request.messages, user=current_user):
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
        async def collect_response():
            chunks = []
            async for chunk in generate_response(session, request.messages):
                chunks.append(chunk)
            return "".join(chunks)
        
        # Run async generator in sync context
        response = asyncio.run(collect_response())
        return {"response": response}
