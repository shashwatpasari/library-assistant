import json
import time
import requests
import argparse
import sys
from datetime import datetime

# Configuration
OLLAMA_URL = "http://localhost:11434"
MODEL = "qwen2.5:7b-instruct"  # Ensure this model is pulled on the GPU machine

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

def enrich_book(book):
    """Call Ollama to enrich a single book."""
    synopsis = book.get("synopsis") or book.get("description") or ""
    if len(synopsis) > 2000:
        synopsis = synopsis[:2000] + "..."
    
    prompt = ENRICHMENT_PROMPT.format(
        title=book.get("title", ""),
        author=book.get("author", ""),
        genres=book.get("genres", "Unknown"),
        synopsis=synopsis or "No synopsis available"
    )
    
    try:
        response = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "format": "json",
                "stream": False,
                "options": {
                    "temperature": 0.1
                }
            },
            timeout=120
        )
        
        if response.status_code != 200:
            print(f"  Error: Ollama returned {response.status_code}")
            return None
            
        result = response.json()
        content = result.get("message", {}).get("content", "")
        data = json.loads(content)
        
        # Validate keys
        required = ["pacing", "tone", "mood_tags", "themes"]
        if not all(k in data for k in required):
            print("  Error: Missing keys")
            return None
            
        return data
        
    except Exception as e:
        print(f"  Error: {e}")
        return None

def main():
    parser = argparse.ArgumentParser(description="Run book enrichment on GPU machine")
    parser.add_argument("--input", default="books_to_enrich.json", help="Input JSON file")
    parser.add_argument("--output", default="enriched_books.json", help="Output JSON file")
    parser.add_argument("--start-index", type=int, default=0, help="Resume from index")
    args = parser.parse_args()

    print(f"Loading {args.input}...")
    try:
        with open(args.input, "r", encoding="utf-8") as f:
            books = json.load(f)
    except FileNotFoundError:
        print(f"Error: {args.input} not found!")
        return

    print(f"Found {len(books)} books. Starting enrichment on {MODEL}...")
    
    # Load existing results if resuming
    results = {}
    if args.start_index == 0:
        try:
            with open(args.output, "r", encoding="utf-8") as f:
                existing = json.load(f)
                results = {str(b["id"]): b for b in existing}
                print(f"resuming with {len(results)} already done...")
        except FileNotFoundError:
            pass
            
    success_count = 0
    
    try:
        for i, book in enumerate(books):
            if i < args.start_index:
                continue
            
            book_id = str(book.get("id"))
            if book_id in results:
                continue
                
            print(f"[{i+1}/{len(books)}] {book.get('title', 'Unknown')[:40]}...")
            
            start = time.time()
            data = enrich_book(book)
            duration = time.time() - start
            
            if data:
                # Merge original ID with new data
                data["id"] = book["id"]
                results[book_id] = data
                success_count += 1
                print(f"  ✓ {data.get('pacing')} | {data.get('tone')} ({duration:.2f}s)")
            else:
                print(f"  ✗ Failed ({duration:.2f}s)")
            
            # Save every 5 books
            if success_count % 5 == 0:
                with open(args.output, "w", encoding="utf-8") as f:
                    json.dump(list(results.values()), f, indent=2)
                    
    except KeyboardInterrupt:
        print("\nStopping...")
    
    # Final save
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(list(results.values()), f, indent=2)
    
    print("-" * 50)
    print(f"Done! Saved {len(results)} books to {args.output}")

if __name__ == "__main__":
    main()
