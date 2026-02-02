#!/usr/bin/env python3
"""
Book Enrichment Script using Ollama (Local LLM)

This script enriches book records with AI-generated metadata using your local Ollama instance.
- Free & Unlimited (no quotas)
- Privacy-focused (data stays local)
- Uses the model defined in .env (default: qwen2.5:7b-instruct)

Usage:
    python scripts/enrich_books.py            # Process all pending books
    python scripts/enrich_books.py --limit 5  # Process 5 books
"""

import argparse
import json
import os
import sys
import time
import requests
from typing import Optional
from dotenv import load_dotenv
from sqlalchemy import select, or_
from sqlalchemy.orm import Session

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import engine
from app.models import Book

# Load .env explicitly
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

# Configuration
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b-instruct")

# No rate limits for local inference, but we can add a small sleep if needed
REQUEST_DELAY = 0.1  

ENRICHMENT_PROMPT = """Analyze this book and provide structured metadata for a library recommendation system.

Book Title: {title}
Author: {author}
Genre: {genres}
Synopsis: {synopsis}

Respond with ONLY valid JSON (no markdown, no explanation) in this exact format:
{{
    "pacing": "Fast" | "Medium" | "Slow",
    "tone": "one word or short phrase describing overall tone",
    "mood_tags": ["up to 5 mood descriptors like cozy, tense, romantic, adventurous, melancholic"],
    "themes": ["up to 5 key themes like redemption, survival, found family, identity"],
    "content_warnings": ["list any content warnings like violence, explicit content, or empty array if none"]
}}

If the synopsis is missing, infer from title/genre. Return ONLY JSON."""

def enrich_book(book: Book) -> Optional[dict]:
    """Call Ollama to enrich a single book."""
    synopsis = book.synopsis or book.description or ""
    if len(synopsis) > 2000:
        synopsis = synopsis[:2000] + "..."
    
    prompt = ENRICHMENT_PROMPT.format(
        title=book.title,
        author=book.author,
        genres=book.genres or "Unknown",
        synopsis=synopsis or "No synopsis available"
    )
    
    try:
        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json={
                "model": OLLAMA_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "format": "json",
                "stream": False,
                "options": {
                    "temperature": 0.1  # Low temperature for consistent JSON
                }
            },
            timeout=120  # Local LLM can be slow
        )
        
        if response.status_code != 200:
            print(f"  Error: Ollama returned {response.status_code} - {response.text}")
            return None
            
        result = response.json()
        content = result.get("message", {}).get("content", "")
        
        # Parse JSON
        data = json.loads(content)
        
        # Validate keys
        required = ["pacing", "tone", "mood_tags", "themes"]
        if not all(k in data for k in required):
            print("  Error: Missing required JSON keys")
            return None
            
        return {
            "pacing": data.get("pacing", "Medium"),
            "tone": data.get("tone", "Neutral"),
            "mood_tags": data.get("mood_tags", [])[:5],
            "themes": data.get("themes", [])[:5],
            "content_warnings": data.get("content_warnings", [])
        }
        
    except json.JSONDecodeError:
        print(f"  Error: Failed to parse JSON response")
        return None
    except Exception as e:
        print(f"  Error: {e}")
        return None


def process_books(limit: Optional[int] = None, batch_size: int = 10):
    """Process books that need enrichment."""
    
    with Session(engine) as session:
        query = select(Book).where(
            or_(
                Book.enrichment_status.is_(None),
                Book.enrichment_status == "pending",
                Book.enrichment_status == "failed"  # Retry failed ones too
            )
        ).order_by(Book.id)
        
        if limit:
            query = query.limit(limit)
        
        books = list(session.scalars(query))
        total = len(books)
        
        if total == 0:
            print("No books need enrichment!")
            return
        
        print(f"Found {total} books to enrich via Ollama ({OLLAMA_MODEL})")
        print("-" * 50)
        
        success_count = 0
        fail_count = 0
        
        for i, book in enumerate(books, 1):
            print(f"[{i}/{total}] Processing: {book.title[:40]}...")
            
            start_time = time.time()
            result = enrich_book(book)
            duration = time.time() - start_time
            
            if result:
                book.pacing = result["pacing"]
                book.tone = result["tone"]
                book.mood_tags = result["mood_tags"]
                book.themes = result["themes"]
                book.content_warnings = result["content_warnings"]
                book.enrichment_status = "done"
                success_count += 1
                print(f"  ✓ {result['pacing']} | {result['tone']} ({duration:.1f}s)")
            else:
                book.enrichment_status = "failed"
                fail_count += 1
                print(f"  ✗ Failed ({duration:.1f}s)")
            
            if i % batch_size == 0:
                session.commit()
                print(f"  [Saved batch]")
            
            time.sleep(REQUEST_DELAY)
        
        session.commit()
        print("-" * 50)
        print(f"Complete! Success: {success_count}, Failed: {fail_count}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, help="Limit number of books")
    parser.add_argument("--batch-size", type=int, default=5, help="Batch size")
    args = parser.parse_args()
    
    process_books(limit=args.limit, batch_size=args.batch_size)
