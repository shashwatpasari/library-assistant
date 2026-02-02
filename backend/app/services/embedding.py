"""
Embedding service using sentence-transformers.
"""

from sentence_transformers import SentenceTransformer

from app.models import Book

_model = None

def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model

def generate_embedding(text: str) -> list[float]:
    """Generate embedding for text."""
    return get_model().encode(text).tolist()

def generate_book_embedding(book: Book) -> list[float]:
    """Generate embedding for a book combining title, author, synopsis, subjects, AND enriched AI fields."""
    parts = [
        book.title or "",
        book.author or "",
        book.synopsis or book.description or "",
        book.subjects or "",
        book.genres or "",
    ]
    
    # Add enriched AI fields for better semantic search
    if book.pacing:
        parts.append(f"Pacing: {book.pacing}")
    if book.tone:
        parts.append(f"Tone: {book.tone}")
    if book.themes:
        themes_str = ", ".join(book.themes) if isinstance(book.themes, list) else str(book.themes)
        parts.append(f"Themes: {themes_str}")
    if book.mood_tags:
        moods_str = ", ".join(book.mood_tags) if isinstance(book.mood_tags, list) else str(book.mood_tags)
        parts.append(f"Moods: {moods_str}")

    text = " ".join(part for part in parts if part)
    return generate_embedding(text)