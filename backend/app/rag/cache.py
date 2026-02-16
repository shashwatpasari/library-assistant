"""
LRU+TTL caching utilities for the RAG pipeline.

Provides caching for:
- Query embeddings (expensive to compute)
- Router output (avoid repeated LLM calls)
- Filter extraction (avoid repeated LLM calls)
"""

import time
from typing import Any
from collections import OrderedDict
from threading import Lock

from app.config import EMBEDDING_CACHE_TTL, ROUTER_CACHE_TTL


class LRUTTLCache:
    """
    A thread-safe LRU cache with TTL (time-to-live) expiration.
    
    Entries are evicted when:
    - They exceed the TTL
    - The cache is full (LRU eviction)
    """
    
    def __init__(self, maxsize: int = 1000, ttl: int = 3600):
        """
        Initialize the cache.
        
        Args:
            maxsize: Maximum number of entries
            ttl: Time-to-live in seconds
        """
        self.maxsize = maxsize
        self.ttl = ttl
        self.cache: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self.lock = Lock()
    
    def get(self, key: str) -> tuple[bool, Any]:
        """
        Get a value from the cache.
        
        Returns:
            (hit, value) - hit is True if found and not expired
        """
        with self.lock:
            if key not in self.cache:
                return False, None
            
            value, timestamp = self.cache[key]
            
            # Check TTL
            if time.time() - timestamp > self.ttl:
                del self.cache[key]
                return False, None
            
            # Move to end (most recently used)
            self.cache.move_to_end(key)
            return True, value
    
    def set(self, key: str, value: Any) -> None:
        """Set a value in the cache."""
        with self.lock:
            # Remove if exists (to update position)
            if key in self.cache:
                del self.cache[key]
            
            # Evict oldest if full
            while len(self.cache) >= self.maxsize:
                self.cache.popitem(last=False)
            
            self.cache[key] = (value, time.time())
    
    def clear(self) -> None:
        """Clear all entries."""
        with self.lock:
            self.cache.clear()
    
    def __len__(self) -> int:
        return len(self.cache)


# Pre-configured caches for common use cases
_embedding_cache = LRUTTLCache(maxsize=1000, ttl=EMBEDDING_CACHE_TTL)
_router_cache = LRUTTLCache(maxsize=500, ttl=ROUTER_CACHE_TTL)
_filter_cache = LRUTTLCache(maxsize=500, ttl=ROUTER_CACHE_TTL)


def get_cached_embedding(query: str) -> tuple[bool, list[float] | None]:
    """Check if embedding is cached."""
    return _embedding_cache.get(query)


def cache_embedding(query: str, embedding: list[float]) -> None:
    """Cache an embedding."""
    _embedding_cache.set(query, embedding)


def get_cached_router_output(query: str) -> tuple[bool, Any]:
    """Check if router output is cached."""
    return _router_cache.get(query)


def cache_router_output(query: str, output: Any) -> None:
    """Cache router output."""
    _router_cache.set(query, output)


def get_cached_filter_output(query: str) -> tuple[bool, Any]:
    """Check if filter output is cached."""
    return _filter_cache.get(query)


def cache_filter_output(query: str, output: Any) -> None:
    """Cache filter output."""
    _filter_cache.set(query, output)


def clear_all_caches() -> None:
    """Clear all caches (useful for testing)."""
    _embedding_cache.clear()
    _router_cache.clear()
    _filter_cache.clear()
