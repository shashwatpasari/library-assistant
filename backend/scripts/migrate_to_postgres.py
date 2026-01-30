"""
Migrate data from SQLite to PostgreSQL and generate embedding.
"""

import sqlite3
from pathlib import Path

from sqlalchemy import text
from app.config import DATABASE_URL
from app.models import Base, Book, BookCopy, User
from app.services.embedding import generate_book_embedding
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Database configuration
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# SQLite database file
SQLITE_DB = Path(__file__).parent.parent / "library.db"


def migrate_to_postgres():
    """Migrate data from SQLite to PostgreSQL."""
    if not SQLITE_DB.exists():
        print(f"SQLite database not found: {SQLITE_DB}")
        return

    print("Connecting to PostgreSQL...")
    engine = create_engine(DATABASE_URL)
    
    # Enable pgvector extension before creating tables
    from app.database import init_pgvector
    init_pgvector()
    
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()

    try:
        print("Connecting to SQLite...")
        sqlite_conn = sqlite3.connect(SQLITE_DB)
        sqlite_conn.row_factory = sqlite3.Row
        sqlite_cursor = sqlite_conn.cursor()

        print("Migrating users...")
        sqlite_cursor.execute("SELECT * FROM users")
        users = sqlite_cursor.fetchall()
        for user in users:
            session.add(User(
                id=user["id"],
                full_name=user["full_name"],
                email=user["email"],
                hashed_password=user["hashed_password"],
                created_at=user["created_at"],
            ))
        session.commit()

        print("Migrating books...")
        sqlite_cursor.execute("SELECT * FROM books")
        books = sqlite_cursor.fetchall()
        for row in books:
            new_book = Book(
                id=row["id"],
                title=row["title"],
                title_long=row["title_long"],
                author=row["author"],
                authors=row["authors"],
                isbn=row["isbn"],
                isbn10=row["isbn10"],
                isbn13=row["isbn13"],
                publisher=row["publisher"],
                genres=row["genres"],
                subjects=row["subjects"],
                description=row["description"],
                synopsis=row["synopsis"],
                language=row["language"],
                pages=row["pages"],
                rating=row["rating"],
                date_published=row["date_published"],
                cover_image_url=row["cover_image_url"],
                image=row["image"],
                image_original=row["image_original"],
            )
            # Generate embedding using the Book object
            new_book.embedding = generate_book_embedding(new_book)
            session.add(new_book)
        session.commit()

        print("Migrating book copies...")
        sqlite_cursor.execute("SELECT * FROM book_copies")
        book_copies = sqlite_cursor.fetchall()
        for copy in book_copies:
            session.add(BookCopy(
                id=copy["id"],
                book_id=copy["book_id"],
                status=copy["status"],
                due_date=copy["due_date"],
            ))
        session.commit()

        print("Migration completed successfully!")

    except Exception as e:
        print(f"Error migrating data: {e}")
        session.rollback()
    finally:
        session.close()
        sqlite_conn.close()


if __name__ == "__main__":
    migrate_to_postgres()