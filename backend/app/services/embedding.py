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
    """Generate embedding for a book combining title, author, synopsis, subjects."""
    parts = [
        book.title or "",
        book.author or "",
        book.synopsis or book.description or "",
        book.subjects or "",
        book.genres or "",
    ]

    text = " ".join(part for part in parts if part)
    return generate_embedding(text)