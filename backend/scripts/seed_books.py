"""
Populate the SQLite database with books and their copies from a CSV input file.

Expected CSV columns (header row mandatory):
    title, author, isbn, genres, description, cover_image_url, copies

You can omit the `copies` column entirely or leave it blank; by default the script
creates five available copies per book. If you do include the column, use a
semicolon-separated list of entries:
    - `available`
    - `issued:YYYY-MM-DD` (include due date)

Usage:
    python -m scripts.seed_books --csv path/to/books.csv
Optional:
    python -m scripts.seed_books --csv path/to/books.csv --default-copies 3
"""

from __future__ import annotations

import argparse
import csv
from datetime import date
from pathlib import Path
from typing import Any, Iterable, TypedDict

from app.database import engine, get_session
from app.models import Base, Book, BookCopy


class CopyPayload(TypedDict, total=False):
    status: str
    due_date: date | None


class BookPayload(TypedDict, total=False):
    title: str
    author: str
    isbn: str | None
    genres: str | None
    description: str | None
    cover_image_url: str | None
    copies: list[CopyPayload]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed the library database from a CSV file.")
    parser.add_argument(
        "--csv",
        required=True,
        type=Path,
        help="Path to the CSV file containing book data.",
    )
    parser.add_argument(
        "--default-copies",
        type=int,
        default=5,
        help="Number of available copies to create per book when none are specified (default: 5).",
    )
    return parser.parse_args()


def load_books_from_csv(csv_path: Path) -> list[BookPayload]:
    """
    Read book definitions from a CSV file.
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    books: list[BookPayload] = []
    with csv_path.open(newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        required_columns = {"title", "author"}
        missing = required_columns - set(reader.fieldnames or set())
        if missing:
            raise ValueError(f"CSV missing required column(s): {', '.join(sorted(missing))}")

        for row_number, row in enumerate(reader, start=2):  # start=2 accounts for header row
            copies_field = row.get("copies") if "copies" in (reader.fieldnames or []) else None
            book_payload: BookPayload = {
                "title": row.get("title", "").strip(),
                "author": row.get("author", "").strip(),
                "isbn": _safe_strip(row.get("isbn")),
                "genres": _safe_strip(row.get("genres")),
                "description": _safe_strip(row.get("description")),
                "cover_image_url": _safe_strip(row.get("cover_image_url")),
                "copies": list(_parse_copies_field(copies_field, row_number=row_number)),
            }

            if not book_payload["title"] or not book_payload["author"]:
                raise ValueError(
                    f"Row {row_number}: 'title' and 'author' must not be empty (row={row})."
                )

            books.append(book_payload)
    return books


def seed_books(books: list[BookPayload], *, default_copies: int = 5) -> None:
    """
    Insert books and their copies into the database.
    """
    if not books:
        print("No books to insert.")
        return

    Base.metadata.create_all(bind=engine)

    with get_session() as session:
        for payload in books:
            copies_payload = payload.get("copies", [])
            book_data = {k: v for k, v in payload.items() if k != "copies"}

            book = Book(**book_data)
            session.add(book)
            session.flush()  # ensure book.id is populated for copy FK usage

            copies_to_create = copies_payload or [
                {"status": "available", "due_date": None} for _ in range(max(default_copies, 0))
            ]

            book_copies = [
                BookCopy(
                    book_id=book.id,
                    status=copy.get("status", "available"),
                    due_date=_normalize_due_date(copy.get("due_date")),
                )
                for copy in copies_to_create
            ]

            if book_copies:
                session.add_all(book_copies)

    print(f"Inserted {len(books)} book(s) into the database.")


def _parse_copies_field(value: Any, *, row_number: int) -> Iterable[CopyPayload]:
    """
    Parse the `copies` column into structured payloads.
    """
    if value is None:
        return []

    value_str = str(value).strip()
    if not value_str:
        return []

    copies_payload: list[CopyPayload] = []
    for copy_entry in value_str.split(";"):
        entry = copy_entry.strip()
        if not entry:
            continue

        if ":" in entry:
            status, due_date_str = entry.split(":", maxsplit=1)
            status = status.strip().lower()
            due_date = _normalize_due_date(due_date_str.strip())
        else:
            status = entry.strip().lower()
            due_date = None

        if status not in {"available", "issued"}:
            raise ValueError(
                f"Row {row_number}: unsupported copy status '{status}' in entry '{entry}'. "
                "Use 'available' or 'issued[:YYYY-MM-DD]'."
            )

        copies_payload.append({"status": status, "due_date": due_date})

    return copies_payload


def _normalize_due_date(value: Any) -> date | None:
    """
    Accept either a `date` instance or an ISO `YYYY-MM-DD` string.
    """
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value.strip():
        try:
            year, month, day = (int(part) for part in value.split("-"))
        except ValueError as exc:
            raise ValueError(f"Invalid due date string: {value}") from exc
        return date(year, month, day)
    raise TypeError(f"Unsupported due date type: {type(value).__name__}")


def _safe_strip(value: Any) -> str | None:
    if value is None:
        return None
    value_str = str(value).strip()
    return value_str or None


def main() -> None:
    args = parse_args()
    books = load_books_from_csv(args.csv)
    seed_books(books, default_copies=args.default_copies)


if __name__ == "__main__":
    main()

