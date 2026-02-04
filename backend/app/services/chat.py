"""
RAG Chat service using Ollama or Groq for LLM and pgvector for retrieval.
"""
import httpx
import json
from sqlalchemy import select, String
from sqlalchemy.orm import Session
from typing import List, Optional

from app.config import (
    OLLAMA_BASE_URL, OLLAMA_MODEL,
    LLM_PROVIDER, GROQ_API_KEY, GROQ_MODEL
)
from app.models import Book, BookCopy
from app.services.embedding import generate_embedding
from app.services.books import get_book_availability
from app.services.recommendations import get_personalized_recommendations


# Groq API base URL
GROQ_API_URL = "https://api.groq.com/openai/v1"


async def detect_query_intent(query: str) -> dict:
    """Detect the intent of a user query: generic, similarity, or filtered.
    
    Returns:
        {"intent": "generic" | "similarity" | "filtered", "target_book": str | null}
    """
    system_prompt = """You are a query intent classifier for a library assistant.
    Classify the user's query into one of these intents:
    
    1. "generic" - User wants general recommendations based on their preferences
       Examples: "recommend some books", "what should I read", "give me 5 books", "suggest something"
    
    2. "similarity" - User wants books similar to a specific book or author
       Examples: "books like The Martian", "similar to Stephen King", "more like Harry Potter"
    
    3. "filtered" - User specifies criteria (genre, pacing, themes, etc.)
       Examples: "fast-paced thrillers", "romance with happy ending", "dark fantasy books"
    
    Return ONLY a JSON object:
    {"intent": "generic" | "similarity" | "filtered", "target_book": "book name if similarity, else null"}
    
    Examples:
    - "recommend 5 books" → {"intent": "generic", "target_book": null}
    - "books like The Kite Runner" → {"intent": "similarity", "target_book": "The Kite Runner"}
    - "fast-paced sci-fi" → {"intent": "filtered", "target_book": null}
    """
    
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            if LLM_PROVIDER == "groq" and GROQ_API_KEY:
                response = await client.post(
                    f"{GROQ_API_URL}/chat/completions",
                    headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
                    json={
                        "model": GROQ_MODEL,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": f"Query: {query}\nJSON:"}
                        ],
                        "response_format": {"type": "json_object"},
                        "max_tokens": 100
                    }
                )
                if response.status_code == 200:
                    return json.loads(response.json()["choices"][0]["message"]["content"])
            else:
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
        print(f"Error detecting intent: {e}")
    
    # Default to filtered (safest fallback - will use vector search)
    return {"intent": "filtered", "target_book": None}


async def extract_search_filters(query: str) -> dict:
    """Use LLM to extract structured search filters from natural language query."""
    
    system_prompt = """You are a search query parser for a library. Extract filters from the user's query.
    Return ONLY a JSON object with these keys (use null if not mentioned):
    - search_query: The semantic search terms (remove filter words)
    - max_pages: int (pages < X)
    - min_pages: int (pages > X)
    - genre: str (substring match)
    - year_start: int (published after X)
    - year_end: int (published before X)
    - language: str (e.g. English, French)
    - pacing: str ("Fast", "Slow", or "Moderate" - if user mentions fast-paced, slow-burn, etc.)
    - tone: str ("Dark", "Light", "Emotional" - if user mentions dark, gritty, fun, emotional, etc.)
    - themes: list[str] (themes like "love", "revenge", "survival", "redemption", etc.)
    - moods: list[str] (moods like "tense", "cozy", "adventurous", "romantic", etc.)
    
    Example: "fast-paced sci-fi books about revenge"
    Output: {"search_query": "sci-fi revenge", "pacing": "Fast", "themes": ["revenge"], "genre": "sci-fi", "max_pages": null, "min_pages": null, "year_start": null, "year_end": null, "language": null, "tone": null, "moods": null}
    """
    
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            if LLM_PROVIDER == "groq" and GROQ_API_KEY:
                response = await client.post(
                    f"{GROQ_API_URL}/chat/completions",
                    headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
                    json={
                        "model": GROQ_MODEL,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": f"Query: {query}\nJSON:"}
                        ],
                        "response_format": {"type": "json_object"},
                        "max_tokens": 200
                    }
                )
                if response.status_code == 200:
                    return json.loads(response.json()["choices"][0]["message"]["content"])
            else:
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
        
        # Enriched field filters (pacing, tone, themes, moods)
        if filters.get("pacing"):
            stmt = stmt.where(Book.pacing.ilike(f"%{filters['pacing']}%"))
        if filters.get("tone"):
            stmt = stmt.where(Book.tone.ilike(f"%{filters['tone']}%"))
        if filters.get("themes"):
            for theme in filters["themes"]:
                stmt = stmt.where(Book.themes.cast(String).ilike(f"%{theme}%"))
        if filters.get("moods"):
            for mood in filters["moods"]:
                stmt = stmt.where(Book.mood_tags.cast(String).ilike(f"%{mood}%"))

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
        
        # Add AI-enriched metadata if available
        if book.pacing:
            context += f"   (Pacing: {book.pacing}, Tone: {book.tone})\n"
        if book.themes:
            # Flatten themes list if it's a list (it is JSON)
            themes_str = ", ".join(book.themes) if isinstance(book.themes, list) else str(book.themes)
            context += f"   (Themes: {themes_str})\n"
            
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
        query_intent = {"intent": "cached"}
    else:
        # Step 1: Detect Query Intent (LLM Call)
        query_intent = await detect_query_intent(latest_query)
        print(f"[Chat] Query intent: {query_intent}")
        
        if query_intent.get("intent") == "generic" and user:
            # Generic recommendation → Use user preferences
            print(f"[Chat] Using preference-based recommendations for user {user.id}")
            books = get_personalized_recommendations(session, user.id, limit=book_limit)
            search_filters = {"source": "preferences"}
            
        elif query_intent.get("intent") == "similarity":
            # Similarity query → Vector search on target book
            target_book = query_intent.get("target_book", latest_query)
            search_filters = {"similarity_target": target_book}
            books = retrieve_relevant_books(session, target_book, filters=None, limit=book_limit)
            
        else:
            # Filtered query → Extract filters + Hybrid Search
            search_filters = await extract_search_filters(latest_query)
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
    1. **Smart Follow-up**: ALWAYS end your response with a follow-up question to keep the conversation going (e.g., "Would you like more recommendations like these?" or "Do you prefer faster or slower pacing?").
    2. **Compare Mode**: If the user asks to compare specific books, use the provided book data to contrast them (Pacing, Tone, Themes).
    
    RESPONSE STRUCTURE for Recommendations:
    1. Start with a brief OPENING sentence (e.g., "Here are some books you might enjoy:" or "Based on your preferences, I found these:").
    2. List ALL books from the Available Books section in a numbered format.
    3. End with a CLOSING sentence and a follow-up question.
    
    FORMATTING RULES for the Book List:
    1. **RECOMMEND ALL BOOKS** provided in the Available Books section above. Do not skip any.
    2. **Number your list** (1., 2., 3., etc.).
    3. Format exactly: **1. Title** by Author
    4. Follow with a 1-2 sentence explanation explaining WHY it fits.
    5. End EACH item with `BID[id]` where id is the book's ID from the BOOK[id|...] data.
    
    Example Response:
    
    Here are some great mystery books for you:
    
    1. **The Martian** by Andy Weir
       A fast-paced survival story perfect for your sci-fi craving. BID[123]
       
    2. **Project Hail Mary** by Andy Weir
       Similar tone but with more emotional depth. BID[456]
    
    I hope you find something you love! Would you like me to suggest books with a specific theme or mood?
       
    CRITICAL INSTRUCTIONS:
    - **ALWAYS** start with an opening sentence before the list.
    - **ALWAYS** recommend ALL books from the Available Books list.
    - **ALWAYS** use bold for the **Title**.
    - **ALWAYS** include `BID[id]` at the end of EACH book entry.
    - **ALWAYS** end with a closing sentence and follow-up question.
    - **ALWAYS** ensure double line breaks between list items.
    - **NEVER** output the full BOOK[...] tag. Use **ONLY** `BID[id]`.
    """

    # Build messages array for LLM chat API
    llm_messages = [{"role": "system", "content": system_message}]
    
    # Add conversation history
    for msg in messages:
        llm_messages.append({
            "role": msg.role,
            "content": msg.content
        })

    buffer = ""
    collected_ids = []  # Use list to preserve order

    async with httpx.AsyncClient(timeout=120.0) as client:
        if LLM_PROVIDER == "groq" and GROQ_API_KEY:
            # Use Groq API (OpenAI-compatible streaming)
            async with client.stream(
                "POST",
                f"{GROQ_API_URL}/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
                json={
                    "model": GROQ_MODEL,
                    "messages": llm_messages,
                    "stream": True,
                    "max_tokens": 1500
                }
            ) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str.strip() == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            if "choices" in data and data["choices"]:
                                delta = data["choices"][0].get("delta", {})
                                chunk = delta.get("content", "")
                                if chunk:
                                    buffer += chunk
                                    
                                    # Process buffer for BID tags
                                    while "BID[" in buffer:
                                        start_idx = buffer.find("BID[")
                                        end_idx = buffer.find("]", start_idx)
                                        
                                        if end_idx != -1:
                                            if start_idx > 0:
                                                yield buffer[:start_idx]
                                            
                                            bid_content = buffer[start_idx+4:end_idx]
                                            if bid_content.isdigit():
                                                bid_int = int(bid_content)
                                                if bid_int not in collected_ids:
                                                    collected_ids.append(bid_int)
                                            
                                            buffer = buffer[end_idx+1:]
                                        else:
                                            break
                                    
                                    # Yield text if no BID tag is being built
                                    # Only hold back if we see start of potential tag
                                    if "BID[" not in buffer:
                                        if buffer and not buffer.endswith("BID") and not buffer.endswith("BI") and not buffer.endswith("B"):
                                            yield buffer
                                            buffer = ""
                        except json.JSONDecodeError:
                            pass
        else:
            # Use Ollama API
            async with client.stream(
                "POST",
                f"{OLLAMA_BASE_URL}/api/chat",
                json={
                    "model": OLLAMA_MODEL,
                    "messages": llm_messages,
                    "stream": True,
                }
            ) as response:
                async for line in response.aiter_lines():
                    if line:
                        data = json.loads(line)
                        if "message" in data and "content" in data["message"]:
                            chunk = data["message"]["content"]
                            buffer += chunk
                            
                            # Process buffer for BID tags
                            while "BID[" in buffer:
                                start_idx = buffer.find("BID[")
                                end_idx = buffer.find("]", start_idx)
                                
                                if end_idx != -1:
                                    if start_idx > 0:
                                        yield buffer[:start_idx]
                                    
                                    bid_content = buffer[start_idx+4:end_idx]
                                    if bid_content.isdigit():
                                        bid_int = int(bid_content)
                                        if bid_int not in collected_ids:
                                            collected_ids.append(bid_int)
                                    
                                    buffer = buffer[end_idx+1:]
                                else:
                                    break
                            
                            if "BID" not in buffer and "[" not in buffer:
                                yield buffer
                                buffer = ""
        
        # Yield remaining buffer
        if buffer:
            yield buffer

        # End of stream: Append Book Cards Data
        if collected_ids or books_map:
            cards_data = []
            
            if collected_ids:
                for bid in collected_ids:
                    b = books_map.get(bid)
                    if not b:
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
            else:
                for b in books_map.values():
                    avail = get_book_availability(session, book_id=b.id)
                    cards_data.append({
                        "id": b.id,
                        "title": b.title,
                        "author": b.author,
                        "cover": b.cover_image_url or b.image or "",
                        "availability": f"{avail.available_copies}/{avail.total_copies} available"
                    })
            
            if cards_data:
                yield f"\n\n__JSON_START__{json.dumps(cards_data)}"