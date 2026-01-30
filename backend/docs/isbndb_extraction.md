### ISBNdb Extraction Utilities

This backend includes a small utility to enrich a CSV of ISBNs with metadata
fetched from the [ISBNdb](https://isbndb.com/) HTTPS API.

The goal is to keep the data-extraction workflow **simple**, **reproducible**, and
ready for RAG/LLM indexing later.

---

### Script: `scripts/enrich_isbn_from_csv.py`

**Purpose**

- Read an input CSV that contains an ISBN column.
- Check the output CSV for existing ISBNs to avoid duplicate API calls.
- Call the ISBNdb batch API (30 ISBNs per request) for efficiency.
- Append new records to the output CSV (or create it if it doesn't exist).

**Batch Processing**

The script uses the ISBNdb batch API endpoint to fetch 30 books per request,
significantly reducing the number of API calls and improving performance.
This is especially beneficial when processing large datasets.

**Incremental Processing**

The script is designed to be run multiple times safely:
- If the output CSV already exists, it will only fetch data for ISBNs that aren't
  already present in the output file.
- Duplicate ISBNs in the output are automatically removed (first occurrence kept).
- This makes it safe to run incrementally on growing datasets without wasting
  API calls on books you've already enriched.

---

### Expected input CSV

- Must have at least one column containing ISBNs.
- By default the column is named `isbn`, but you can override it.

Minimal example (header + one row):

```text
isbn
9780135957059
```

You can have additional columns (they are ignored by the enrichment script).

---

### Output CSV

The enriched CSV contains one row per **unique** ISBN from the input and
these columns:

- `isbn`, `isbn10`, `isbn13`
- `title`, `title_long`
- `publisher`
- `synopsis` (may contain HTML, commas, quotes, and newlines)
- `language`
- `pages`
- `date_published`
- `image`, `image_original`
- `subjects` (normalised to a `; `-separated string)
- `authors` (normalised to a `; `-separated string)

All fields are written as strings so they are easy to inspect and process.

**CSV Formatting:**
- Fields containing commas, quotes, or newlines are automatically quoted
  to ensure proper CSV parsing.
- This means titles, subjects, authors, and **synopsis** with commas will be correctly
  preserved in the CSV file.
- The synopsis field may contain HTML tags, double quotes, commas, and newlines.
  All of these are properly handled by CSV quoting - the entire synopsis field
  will be wrapped in double quotes, and any internal double quotes will be
  escaped by doubling them (`""`).

---

### API key configuration

The script needs an ISBNdb API key. You can provide it via:

- **Environment variable**:

```bash
export ISBNDB_API_KEY="YOUR_ISBNDB_API_KEY"
```

- **CLI flag**:

```bash
--api-key YOUR_ISBNDB_API_KEY
```

Environment variable is convenient for day‑to‑day use; the CLI flag is useful
for one‑off runs or CI.

---

### How to run the enrichment script

From the backend directory, using the existing virtual environment:

```bash
cd backend
source venv/bin/activate

python -m scripts.enrich_isbn_from_csv \
  --input scripts/books.csv \
  --output scripts/books_isbndb_enriched.csv \
  --isbn-column isbn \
  --api-key "$ISBNDB_API_KEY"
```

You can customise:

- `--input` / `--output`: paths to input and output CSVs.
- `--isbn-column`: the name of the ISBN column if it is not `isbn`.
- `--delay`: seconds to wait between HTTP requests (default `0.2`).

**Running incrementally**

You can run the script multiple times with the same or different input CSVs:

```bash
# First run: creates books_isbndb_enriched.csv
python -m scripts.enrich_isbn_from_csv \
  --input scripts/books_batch1.csv \
  --output scripts/books_isbndb_enriched.csv

# Second run: only fetches new ISBNs from batch2, appends to existing file
python -m scripts.enrich_isbn_from_csv \
  --input scripts/books_batch2.csv \
  --output scripts/books_isbndb_enriched.csv
```

The script will:
- Skip ISBNs that already exist in the output CSV (saves API calls).
- Only fetch and append new ISBNs.
- Automatically remove any duplicate ISBNs in the final output.

---

### Error handling behaviour

**HTTP errors (4xx, 5xx):**
- If the API returns any HTTP error status code (403 Forbidden, 404 Not Found,
  429 Too Many Requests, 500 Internal Server Error, etc.), the script will:
  1. **Stop processing immediately** (no more API calls will be made).
  2. **Save any records collected before the error occurred** to the output CSV.
  3. **Exit with an error code** (exit code 1).
- This ensures you don't waste API quota on failed requests and preserves
  any progress made before encountering the error.
- You can resume processing later by running the script again; it will skip
  ISBNs that were already saved and continue from where it left off.

**Special cases:**
- **429 (Too Many Requests)**: Raises `RateLimitError` with a specific message.
- **Other HTTP errors (403, 404, 500, etc.)**: Raises `APIError` with details
  about the status code and response.

---

### Next steps

- Use the enriched CSV as a **staging dataset** for:
  - loading into the FastAPI backend via a seeding script, or
  - building vector indexes / RAG corpora for the library assistant.
- If needed, you can add another script that:
  - reads `books_isbndb_enriched.csv`,
  - maps columns to your `Book` model fields, and
  - inserts them into the SQLite database via SQLAlchemy.


