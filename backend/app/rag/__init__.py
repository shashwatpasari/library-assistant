"""
RAG (Retrieval-Augmented Generation) module for the library assistant.

This module provides a production-grade LangChain-based RAG pipeline with:
- Structured JSON outputs (no fragile BID[] parsing)
- Hybrid retrieval (lexical + vector + RRF fusion)
- 7-intent routing with heuristic-first approach
- Prompt injection hardening
- User preference exclusion filtering
- LRU+TTL caching for embeddings and router output
"""

from app.rag.schemas import (
    RouterOutput,
    FilterOutput,
    GenerationOutput,
    RecommendedBook,
    BookCandidate,
    BookCard,
    QueryIntent,
)
from app.rag.streaming import stream_rag_response

__all__ = [
    "RouterOutput",
    "FilterOutput",
    "GenerationOutput",
    "RecommendedBook",
    "BookCandidate",
    "BookCard",
    "QueryIntent",
    "stream_rag_response",
]
