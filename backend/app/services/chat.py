"""
RAG Chat service using Ollama for LLM and pgvector for retrieval.
"""
import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session
from typing import List, Optional

from app.config import OLLAMA_BASE_URL, OLLAMA_MODEL
from app.models import Book, BookCopy
from app.services.embedding import generate_embedding
from app.services.books import get_book_availability


async def extract_search_filters(query: str) -> dict:
    """Use LLM to extract structured search filters from natural language query."""
    import json
    
    system_prompt = """You are a search query parser for a library. Extract filters from the user's query.
    Return ONLY a JSON object with these keys (use null if not mentioned):
    - search_query: The semantic search terms (remove filter words)
    - max_pages: int (pages < X)
    - min_pages: int (pages > X)
    - genre: str (substring match)
    - year_start: int (published after X)
    - year_end: int (published before X)
    - language: str (e.g. English, French)
    
    Example: "sci-fi books under 300 pages from 2020"
    Output: {"search_query": "sci-fi", "max_pages": 300, "min_pages": null, "genre": "sci-fi", "year_start": 2020, "year_end": null, "language": null}
    """
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": f"Query: {query}\nJSON:",
                    "system": system_prompt,
                    "stream": False,
                    "format": "json"
                }
            )
            if response.status_code == 200:
                return json.loads(response.json()["response"])
    except Exception as e:
        print(f"Error extracting filters: {e}")
        
    return {"search_query": query}


def retrieve_relevant_books(session: Session, query: str, filters: dict = None, limit: int = 5) -> list[Book]:
    """Find books similar to query using hybrid search (Vector + SQL Filters)."""
    
    # Use the extracted search query for embedding, or fallback to original full query
    search_term = filters.get("search_query", query) if filters else query
    query_embedding = generate_embedding(search_term)

    # Base query with active vector search
    stmt = select(Book).where(Book.embedding.is_not(None))
    
    # Apply Metadata Filters
    if filters:
        if filters.get("max_pages"):
            stmt = stmt.where(Book.pages <= filters["max_pages"])
        if filters.get("min_pages"):
            stmt = stmt.where(Book.pages >= filters["min_pages"])
        if filters.get("genre"):
            stmt = stmt.where(Book.genres.ilike(f"%{filters['genre']}%"))
        if filters.get("language"):
            stmt = stmt.where(Book.language.ilike(f"%{filters['language']}%"))
        
        # Approximate year filtering (since date_published is string)
        if filters.get("year_start"):
             stmt = stmt.where(Book.date_published >= str(filters["year_start"]))
        if filters.get("year_end"):
             stmt = stmt.where(Book.date_published <= str(filters["year_end"]))

    # Add Vector Similarity Order
    stmt = stmt.order_by(Book.embedding.cosine_distance(query_embedding)).limit(limit)

    result = session.execute(stmt)
    return list(result.scalars())


def build_context(session: Session, books: list[Book]) -> str:
    """Build context string from retrieved books with availability info."""
    if not books:
        return "No relevant books found matching your criteria."

    context = ""
    for i, book in enumerate(books, 1):
        cover_url = book.cover_image_url or book.image or ""
        availability = get_book_availability(session, book_id=book.id)
        avail_text = f"{availability.available_copies}/{availability.total_copies} available"
        
        # Format: ID|Title|Author|CoverURL|Availability
        context += f"{i}. BOOK[{book.id}|{book.title}|{book.author}|{cover_url}|{avail_text}]\n"
        
        # Add metadata context for the LLM to use in its answer
        # Truncate synopsis to avoid token limits (approx 300 chars)
        synopsis_preview = (book.synopsis[:300] + "...") if book.synopsis else (book.description[:300] + "..." if book.description else "No description.")
        context += f"   (Genre: {book.genres}, Pages: {book.pages}, Year: {book.date_published})\n"
        context += f"   (Subjects: {book.subjects})\n"
        context += f"   (Synopsis: {synopsis_preview})\n"
        
    return context


def format_conversation_history(messages: List[dict]) -> str:
    """Format conversation history for the prompt."""
    if not messages:
        return ""
    
    history = ""
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role == "user":
            history += f"User: {content}\n"
        else:
            history += f"Assistant: {content}\n"
    return history


def should_retrieve_new_books(current_query: str, conversation_history: str) -> bool:
    """
    Determine if we should retrieve new books based on the query.
    Returns True if the user seems to be asking about a different book/topic.
    """
    # Keywords that suggest a new book query
    new_query_indicators = [
        "do you have", "looking for", "find me", "search for", 
        "recommend", "suggest", "show me", "any books about",
        "what books", "which books", "tell me about"
    ]
    
    query_lower = current_query.lower()
    
    # If it's one of the first messages, always retrieve
    if len(conversation_history) < 50:
        return True
    
    # Check if query contains new book indicators
    for indicator in new_query_indicators:
        if indicator in query_lower:
            return True
            
    # If query mentions specific filters like pages or years, always search
    if any(k in query_lower for k in ["page", "year", "genre", "category", "author"]):
        return True
    
    # Short follow-up questions don't need new retrieval
    if len(current_query) < 20:
        return False
    
    return False


from app.models import User, UserPreference

async def generate_response(session: Session, messages: List[dict], cached_context: Optional[str] = None, user: Optional[User] = None):
    """Generate streaming response using Ollama chat API with conversation history."""
    import re
    import json
    
    # Get the latest user message
    latest_query = ""
    for msg in reversed(messages):
        if msg.role == "user":
            latest_query = msg.content
            break
    
    # Format conversation history for context check
    conversation = format_conversation_history([{"role": m.role, "content": m.content} for m in messages[:-1]])
    
    # Extract number of books requested (default 5)
    num_match = re.search(r'(\d+)\s*books?', latest_query.lower())
    book_limit = int(num_match.group(1)) if num_match else 5
    book_limit = min(max(book_limit, 1), 20)  # Clamp between 1 and 20
    
    # Build User Preference Context
    user_context = ""
    if user:
        pref = session.scalar(select(UserPreference).where(UserPreference.user_id == user.id))
        if pref:
            # Add strict filters for hybrid search if they match dealbreakers
            # (Note: simpler to just instruct LLM for now, unless we want strict SQL exclusion)
            
            user_context = f"""
User Profile:
- Favorite Genres: {', '.join(pref.favorite_genres)}
- Pacing: {pref.pacing_preference}
- Tone: {pref.tone_preference}
- Avoid/Triggers: {', '.join(pref.triggers_to_avoid)}
- Disliked Genres: {', '.join(pref.disliked_genres)}
- Goals: {pref.reading_goals}

PERSONALIZATION INSTRUCTIONS:
1. Use "Because you liked..." reasoning based on the user's profile.
2. If a book matches their Favorite Genres, mention it.
3. STRICTLY AVOID any book containing their Triggers or Disliked Genres.
4. If their pacing preference is "{pref.pacing_preference}", highlight that aspect of the book.
"""

    # Decide whether to retrieve new books or use cached context
    if cached_context and not should_retrieve_new_books(latest_query, conversation):
        context = cached_context
        search_filters = {}
    else:
        # Step 1: Extract Filters (LLM Call)
        search_filters = await extract_search_filters(latest_query)
        
        # Step 2: Hybrid Search (Vector + SQL)
        # TODO: We could inject user preferences (like disliked genres) into SQL filters here
        books = retrieve_relevant_books(session, latest_query, filters=search_filters, limit=book_limit)
        context = build_context(session, books)
    
    # Build map of available books for fast lookup by ID
    books_map = {b.id: b for b in books} if 'books' in locals() else {}

    # Build system message with library context
    system_message = f"""You are a smart, agentic library assistant for Library Hub.
    
    Library Info:
    - Name: Library Hub
    - Owner: Shashwat Pasari  
    - Timings: 9:00 AM to 9:00 PM
    
    {user_context}
    
    Detected Search Filters: {search_filters}
    Available Books:
    {context}
    
    CORE BEHAVIORS:
    1. **Smart Follow-up**: If the user's request is broad (e.g., "mystery books"), provide initial recommendations BUT append a smart, playful follow-up question to narrow it down (e.g., "Do you prefer cozy mysteries or hard-boiled thrillers?").
    2. **Compare Mode**: If the user asks to compare specific books, use the provided book data to contrast them (Pacing, Tone, Themes).
    
    FORMATTING RULES for Recommendations:
    1. **Number your list** (1., 2., 3.).
    2. Format exactly: **1. Title** by Author
    3. Follow with a 1-2 sentence explanation explaining WHY it fits.
    4. End the item with `BID[id]` to attach the book card.
    
    Example Layout:
    
    1. **The Martian** by Andy Weir
       A fast-paced survival story perfect for your sci-fi craving. BID[123]
       
    2. **Project Hail Mary** by Andy Weir
       Similar tone but with more emotional depth. BID[456]
       
    CRITICAL INSTRUCTIONS:
    - **ALWAYS** use bold for the **Title**.
    - **ALWAYS** ensure double line breaks between list items.
    - **NEVER** output the full BOOK[...] tag. Use **ONLY** `BID[id]`.
    """

    # Build messages array for Ollama chat API
    ollama_messages = [{"role": "system", "content": system_message}]
    
    # Add conversation history
    for msg in messages:
        ollama_messages.append({
            "role": msg.role,
            "content": msg.content
        })

    async with httpx.AsyncClient(timeout=60.0) as client:
        async with client.stream(
            "POST",
            f"{OLLAMA_BASE_URL}/api/chat",
            json={
                "model": OLLAMA_MODEL,
                "messages": ollama_messages,
                "stream": True,
            }
        ) as response:
            buffer = ""
            collected_ids = set()
            
            async for line in response.aiter_lines():
                if line:
                    data = json.loads(line)
                    if "message" in data and "content" in data["message"]:
                        chunk = data["message"]["content"]
                        buffer += chunk
                        
                        # Process buffer for BID tags
                        # We need to be careful not to split a tag across chunks
                        # Simple approach: Yield everything up to the last potential open bracket
                        
                        while "BID[" in buffer:
                            start_idx = buffer.find("BID[")
                            end_idx = buffer.find("]", start_idx)
                            
                            if end_idx != -1:
                                # We found a complete tag
                                # Yield text before the tag
                                if start_idx > 0:
                                    yield buffer[:start_idx]
                                
                                # Extract ID
                                bid_content = buffer[start_idx+4:end_idx]
                                if bid_content.isdigit():
                                    collected_ids.add(int(bid_content))
                                
                                # Remove processed part from buffer
                                buffer = buffer[end_idx+1:]
                            else:
                                # Tag is incomplete, wait for more chunks
                                break
                        
                        # Yield safe part of buffer (if no partial tag at end)
                        if "BID" not in buffer and "[" not in buffer:
                            yield buffer
                            buffer = ""
            
            # Yield remaining buffer
            if buffer:
                yield buffer

            # End of stream: Append Book Cards Data
            # End of stream: Append Book Cards Data
            if collected_ids:
                import json
                cards_data = []
                for bid in collected_ids:
                    b = books_map.get(bid)
                    if not b:
                        # Fetch from DB if not in current search results (e.g. from cached context)
                        b = session.get(Book, bid)
                    
                    if b:
                        avail = get_book_availability(session, book_id=b.id)
                        cards_data.append({
                            "id": b.id,
                            "title": b.title,
                            "author": b.author,
                            "cover": b.cover_image_url or b.image or "",
                            "availability": f"{avail.available_copies}/{avail.total_copies} available"
                        })
                
                if cards_data:
                    yield f"\n\n__JSON_START__\n{json.dumps(cards_data)}"