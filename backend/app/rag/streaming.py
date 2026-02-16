"""
FastAPI streaming adapter for the RAG pipeline.

This module provides the interface between the FastAPI endpoint and the
RAG pipeline, handling:
- Streaming answer_markdown tokens
- Appending __JSON_START__ + cards JSON at the end
- Error handling and fallback responses
"""

import json
import re
import traceback
from typing import Optional, AsyncGenerator

from sqlalchemy.orm import Session

from app.models import User
from app.rag.schemas import BookCard
from app.rag.graph import run_graph_pipeline as run_rag_pipeline


async def stream_rag_response(
    session: Session,
    messages: list,
    user: Optional[User] = None,
    session_id: str = "guest",
) -> AsyncGenerator[str, None]:
    """
    Stream a RAG response for the chat endpoint.
    
    This is the main interface between the FastAPI chat endpoint and the
    RAG pipeline. It:
    1. Runs the RAG pipeline
    2. Streams the text response
    3. Appends __JSON_START__ + cards JSON at the end
    
    Args:
        session: Database session
        messages: List of ChatMessage objects with role and content
        user: Optional current user
        
    Yields:
        Text chunks, followed by JSON card data
    """
    # Extract the latest user query
    latest_query = ""
    for msg in reversed(messages):
        if hasattr(msg, 'role'):
            role = msg.role
        else:
            role = msg.get("role", "")
        
        if role == "user":
            if hasattr(msg, 'content'):
                latest_query = msg.content
            else:
                latest_query = msg.get("content", "")
            break
    
    if not latest_query:
        yield "I didn't catch that. Could you please rephrase your question?"
        return
    
    # Build history from messages
    history = []
    for msg in messages[:-1]:  # Exclude the current message
        if hasattr(msg, 'role'):
            history.append({
                "role": msg.role,
                "content": msg.content,
            })
        else:
            history.append(msg)
    
    # Extract requested book count from query
    book_limit = _extract_book_limit(latest_query)
    
    try:
        # Run the RAG pipeline
        text_generator, book_cards = await run_rag_pipeline(
            session=session,
            query=latest_query,
            history=history,
            user=user,
            book_limit=book_limit,
            session_id=session_id,
        )
        
        # Stream the text response
        full_text = ""
        async for chunk in text_generator:
            full_text += chunk
            yield chunk
        
        # Try to extract recommended books by matching titles in text
        recommended_ids = _extract_recommended_ids(full_text, book_cards)
        
        # Build cards JSON - if extraction found matches, use those.
        # Otherwise, if generic search, maybe showing all is safer? 
        # But user complained about "other books". 
        # So let's trust the extraction. If empty, show nothing? 
        # No, fallback to all is better than nothing if extraction fails completely.
        # But if the text has recommendations, we should filter.
        
        # Better logic:
        # 1. If we found matches in text, show ONLY those in that order.
        # 2. If NO matches found (maybe titles slightly off), fallback to showing top 3-5 candidates?
        #    Or if it's a short response "I couldn't find any...", don't show cards.
        
        # Let's rely on the extraction. If it fails, we default to the first few candidates 
        # to avoid showing "irrelevant" ones, or all if few.
        
        cards_data = _build_cards_json(book_cards, recommended_ids)
        
        # Append cards JSON at the end
        if cards_data:
            yield f"\n\n__JSON_START__{json.dumps(cards_data)}"
    
    except Exception as e:
        print(f"[Streaming] Pipeline error: {e}")
        traceback.print_exc()
        yield f"I apologize, but I encountered an error processing your request. Please try again."


def _extract_book_limit(query: str) -> int:
    """Extract the number of books requested from the query."""
    # Look for patterns like "5 books", "give me 10", etc.
    match = re.search(r'(\d+)\s*books?', query.lower())
    if match:
        limit = int(match.group(1))
        return min(max(limit, 1), 20)  # Clamp between 1 and 20
    
    # Look for numbers in common patterns
    match = re.search(r'(give|recommend|suggest|show|find)\s*(?:me\s*)?(\d+)', query.lower())
    if match:
        limit = int(match.group(2))
        return min(max(limit, 1), 20)
    
    return 5  # Default to 5


def _extract_recommended_ids(text: str, candidates: list[BookCard]) -> list[int]:
    """
    Extract recommended book IDs by finding candidate titles in the response text.
    
    This is more robust than relying on the LLM to output specific IDs or JSON,
    which can be prone to formatting errors or hallucinations.
    
    Args:
        text: The full response text from the LLM
        candidates: List of available BookCandidate objects
        
    Returns:
        List of book IDs in the order they appear in the text.
    """
    # map {lowercase_title: id}
    # We use a list of (index, id) to sort by appearance
    matches = []
    
    text_lower = text.lower()
    
    for card in candidates:
        # Check if title appears in text
        # We look for the full title case-insensitive
        title = card.title.lower()
        
        # Simple substring check
        try:
            idx = text_lower.find(title)
            if idx != -1:
                matches.append((idx, card.id))
        except Exception:
            continue
            
    # Sort matches by position in text (preserve flow)
    matches.sort(key=lambda x: x[0])
    
    # Extract IDs, removing duplicates while preserving order
    seen = set()
    ordered_ids = []
    for _, bid in matches:
        if bid not in seen:
            ordered_ids.append(bid)
            seen.add(bid)
            
    return ordered_ids


def _build_cards_json(
    cards: list[BookCard],
    recommended_ids: list[int],
) -> list[dict]:
    """
    Build the final cards JSON for the frontend.
    
    If recommended_ids are available, only include those cards in order.
    Otherwise, include all cards.
    """
    if not cards:
        return []
    
    # Build ID -> card mapping
    card_map = {c.id: c for c in cards}
    
    result = []
    
    if recommended_ids:
        # Include only recommended cards in order
        for bid in recommended_ids:
            if bid in card_map:
                card = card_map[bid]
                result.append({
                    "id": card.id,
                    "title": card.title,
                    "author": card.author,
                    "cover": card.cover,
                    "availability": card.availability,
                })
    else:
        # Include all cards
        for card in cards:
            result.append({
                "id": card.id,
                "title": card.title,
                "author": card.author,
                "cover": card.cover,
                "availability": card.availability,
            })
    
    return result
