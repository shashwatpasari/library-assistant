import json
import sys
import os
from sqlalchemy.orm import Session

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import engine
from app.models import Book

def export_books():
    print("Connecting to database...")
    with Session(engine) as session:
        # Fetch pending books (or failed/null)
        books = session.query(Book).filter(
            (Book.enrichment_status == None) | 
            (Book.enrichment_status == 'failed') |
            (Book.enrichment_status == 'pending')
        ).all()
        
        print(f"Found {len(books)} books waiting for enrichment.")
        
        data = []
        for b in books:
            data.append({
                "id": b.id,
                "title": b.title,
                "author": b.author,
                "genres": b.genres,
                "synopsis": b.synopsis or b.description or ""
            })
            
        output_file = "books_to_enrich.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            
        print(f"Successfully exported {len(data)} books to {output_file}")

if __name__ == "__main__":
    export_books()
