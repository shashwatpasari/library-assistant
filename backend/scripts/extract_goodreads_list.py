"""
Script to extract book information from Goodreads list pages.

This script:
1. Scrapes Goodreads list pages (specified page range)
2. Extracts book URLs from anchor tags
3. For each book, extracts detailed information using the Goodreads extractor
4. Saves all data to a CSV file

Usage:
    python -m scripts.extract_goodreads_list <list_url> [--from-page N] [--to-page M] [--output FILE]
    
Examples:
    # Extract pages 1 to 10
    python -m scripts.extract_goodreads_list <url> --from-page 1 --to-page 10
    
    # Extract pages 10 to 20
    python -m scripts.extract_goodreads_list <url> --from-page 10 --to-page 20
    
    # Extract 10 pages starting from page 1 (backward compatible)
    python -m scripts.extract_goodreads_list <url> --max-pages 10
"""

import argparse
import csv
import random
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from typing import List, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent

# Import the extractor class
from scripts.extract_goodreads import GoodreadsExtractor, GoodreadsBook

# Initialize UserAgent for rotating user agents
ua = UserAgent()

# Thread-safe lock for printing and CSV writing
print_lock = Lock()
write_lock = Lock()


def get_session_with_proxy(use_proxy: bool = True) -> requests.Session:
    """
    Create a requests session with proxy support and rotating user agents.
    
    Args:
        use_proxy: Whether to use proxy rotation (requires AWS API Gateway setup)
        
    Returns:
        Configured requests Session
    """
    session = requests.Session()
    
    # Rotate user agents
    session.headers.update({
        'User-Agent': ua.random,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    })
    
    # Note: For production use, you would set up AWS API Gateway with IP rotation
    # For now, we'll use rotating user agents and delays to avoid rate limiting
    if use_proxy:
        # You can add proxy configuration here if you have proxy servers
        # Example:
        # proxies = {
        #     'http': 'http://proxy-server:port',
        #     'https': 'https://proxy-server:port',
        # }
        # session.proxies.update(proxies)
        pass
    
    return session


def extract_book_urls_from_list_page(url: str, page_num: int = 1, session: Optional[requests.Session] = None) -> List[str]:
    """
    Extract book URLs from a Goodreads list page.
    
    Args:
        url: Base URL of the Goodreads list
        page_num: Page number to scrape
        session: Requests session to use
        
    Returns:
        List of book URLs
    """
    if session is None:
        session = get_session_with_proxy()
    
    # Construct page URL
    if page_num > 1:
        if '?' in url:
            page_url = f"{url}&page={page_num}"
        else:
            page_url = f"{url}?page={page_num}"
    else:
        page_url = url
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            # Random delay to avoid rate limiting
            time.sleep(random.uniform(1.0, 2.5))
            
            response = session.get(page_url, timeout=15)
            response.raise_for_status()
            
            # Wait a bit for JavaScript to potentially load content
            # Goodreads pages may have dynamic content that loads after initial HTML
            time.sleep(random.uniform(1.5, 3.0))
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            book_urls = []
            seen_urls = set()
            
            def add_book_url(href: str) -> None:
                """Helper function to add a book URL if it's valid and unique."""
                if not href:
                    return
                
                # Convert relative URLs to absolute
                if href.startswith('/'):
                    full_url = f"https://www.goodreads.com{href}"
                elif href.startswith('http'):
                    full_url = href
                else:
                    full_url = urljoin('https://www.goodreads.com', href)
                
                # Extract just the base book URL (remove query params and fragments)
                parsed = urlparse(full_url)
                clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                
                # Only add unique URLs
                if clean_url not in seen_urls and '/book/show/' in clean_url:
                    seen_urls.add(clean_url)
                    book_urls.append(clean_url)
            
            # Method 1: Look for books in the main table (div#all_votes > table.tableList)
            # This is the primary method for Goodreads list pages
            # First try to find the specific table in all_votes div
            # Retry logic: if table not found, wait and check again (for dynamic content)
            all_votes_div = None
            max_table_wait_attempts = 3
            for wait_attempt in range(max_table_wait_attempts):
                all_votes_div = soup.find('div', id='all_votes')
                if all_votes_div:
                    main_table = all_votes_div.find('table', class_=re.compile(r'tableList'))
                    if main_table and main_table.find_all('tr'):
                        break  # Table found with rows, proceed
                
                # If table not found and not last attempt, wait a bit more
                if wait_attempt < max_table_wait_attempts - 1:
                    time.sleep(random.uniform(1.0, 2.0))
                    # Re-fetch the page content (in case it's dynamically loaded)
                    try:
                        response = session.get(page_url, timeout=15)
                        response.raise_for_status()
                        soup = BeautifulSoup(response.content, 'html.parser')
                    except:
                        pass  # If re-fetch fails, continue with original soup
            # Extract from the table if found
            if all_votes_div:
                main_table = all_votes_div.find('table', class_=re.compile(r'tableList'))
                if main_table:
                    table_rows = main_table.find_all('tr')
                    for row in table_rows:
                        # Find book title link in the row
                        book_link = row.find('a', href=re.compile(r'/book/show/'))
                        if book_link:
                            href = book_link.get('href')
                            add_book_url(href)
                else:
                    # Fallback: look for any table in all_votes
                    table_rows = all_votes_div.find_all('tr')
                    for row in table_rows:
                        book_link = row.find('a', href=re.compile(r'/book/show/'))
                        if book_link:
                            href = book_link.get('href')
                            add_book_url(href)
            else:
                # Fallback: if all_votes div not found, search all table rows
                table_rows = soup.find_all('tr')
                for row in table_rows:
                    # Find book title link in the row
                    book_link = row.find('a', href=re.compile(r'/book/show/'))
                    if book_link:
                        href = book_link.get('href')
                        add_book_url(href)
            
            # Method 2: Look for book title links with specific classes
            # Only add if not already found in Method 1
            book_title_links = soup.find_all('a', href=re.compile(r'/book/show/'), 
                                             class_=lambda x: x and ('bookTitle' in str(x).lower() or 'book' in str(x).lower()) if x else False)
            
            for link in book_title_links:
                href = link.get('href')
                if href:
                    # Check if already found
                    parsed = urlparse(href if href.startswith('http') else f"https://www.goodreads.com{href}")
                    clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                    if clean_url not in seen_urls:
                        add_book_url(href)
            
            # Method 3: Look for links in list item containers
            # Only add if not already found
            list_items = soup.find_all(['li', 'div'], class_=lambda x: x and ('book' in str(x).lower() or 'item' in str(x).lower()) if x else False)
            for item in list_items:
                book_link = item.find('a', href=re.compile(r'/book/show/'))
                if book_link:
                    href = book_link.get('href')
                    if href:
                        parsed = urlparse(href if href.startswith('http') else f"https://www.goodreads.com{href}")
                        clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                        if clean_url not in seen_urls:
                            add_book_url(href)
            
            # Method 4: Fallback - find all book links but filter out navigation/sidebar
            # Only add if not already found and not in excluded sections
            all_book_links = soup.find_all('a', href=re.compile(r'/book/show/'))
            
            for link in all_book_links:
                href = link.get('href')
                if not href:
                    continue
                
                # Check if already found
                parsed = urlparse(href if href.startswith('http') else f"https://www.goodreads.com{href}")
                clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                if clean_url in seen_urls:
                    continue
                
                # Skip links in navigation, footer, sidebar, or header
                parent = link.find_parent(['nav', 'footer', 'aside', 'header'])
                if parent:
                    continue
                
                # Skip if link text is very short (likely navigation)
                link_text = link.get_text(strip=True)
                if len(link_text) < 3:
                    continue
                
                # Skip if it's in a script tag or comment
                if link.find_parent(['script', 'style']):
                    continue
                
                # Skip if it's in a "related books" or "similar books" section
                parent_div = link.find_parent('div', class_=lambda x: x and ('related' in str(x).lower() or 'similar' in str(x).lower() or 'recommend' in str(x).lower()) if x else False)
                if parent_div:
                    continue
                
                add_book_url(href)
            
            print(f"Page {page_num}: Found {len(book_urls)} book URLs")
            return book_urls
            
        except requests.RequestException as e:
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 5  # Exponential backoff
                print(f"Error fetching page {page_num} (attempt {attempt + 1}/{max_retries}): {e}")
                print(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
                # Rotate user agent on retry
                session.headers['User-Agent'] = ua.random
            else:
                print(f"Error fetching page {page_num} after {max_retries} attempts: {e}", file=sys.stderr)
                return []
    
    return []


def extract_book_info(book_url: str, delay: float = 0.5, session: Optional[requests.Session] = None, index: int = 0, total: int = 0) -> tuple[Optional[GoodreadsBook], str]:
    """
    Extract book information from a Goodreads book page.
    
    Args:
        book_url: URL of the book page
        delay: Delay between requests (seconds) - reduced for async
        session: Requests session to use (for proxy support)
        index: Current book index (for progress tracking)
        total: Total number of books (for progress tracking)
        
    Returns:
        Tuple of (GoodreadsBook object or None, book_url)
    """
    max_retries = 3
    for attempt in range(max_retries):
        try:
            # Small random delay to avoid rate limiting (reduced for async)
            time.sleep(delay + random.uniform(0.1, 0.5))
            
            # Create extractor with custom session if provided
            extractor = GoodreadsExtractor(book_url, session=session)
            
            book = extractor.extract_all()
            
            with print_lock:
                print(f"  [{index}/{total}] ✓ Extracted: {book.title or 'Unknown'}")
            
            return book, book_url
            
        except requests.HTTPError as e:
            if e.response.status_code == 429:  # Too Many Requests
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 5  # Shorter wait for async
                    with print_lock:
                        print(f"  [{index}/{total}] ⚠ Rate limited. Waiting {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                else:
                    with print_lock:
                        print(f"  [{index}/{total}] ✗ Rate limited after {max_retries} attempts", file=sys.stderr)
                    return None, book_url
            else:
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2
                    with print_lock:
                        print(f"  [{index}/{total}] ⚠ HTTP {e.response.status_code}. Retrying...")
                    time.sleep(wait_time)
                    continue
                else:
                    with print_lock:
                        print(f"  [{index}/{total}] ✗ HTTP error {e.response.status_code}: {e}", file=sys.stderr)
                    return None, book_url
                    
        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 1
                with print_lock:
                    print(f"  [{index}/{total}] ⚠ Error (attempt {attempt + 1}/{max_retries}): {str(e)[:50]}")
                time.sleep(wait_time)
                continue
            else:
                with print_lock:
                    print(f"  [{index}/{total}] ✗ Error extracting: {str(e)[:100]}", file=sys.stderr)
                return None, book_url
    
    return None, book_url


def main() -> None:
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description='Extract book information from Goodreads list pages'
    )
    parser.add_argument(
        'list_url',
        type=str,
        help='URL of the Goodreads list page'
    )
    parser.add_argument(
        '--from-page',
        type=int,
        default=None,
        help='Starting page number (e.g., 1). If not specified, uses --start-page or defaults to 1'
    )
    parser.add_argument(
        '--to-page',
        type=int,
        default=None,
        help='Ending page number (inclusive, e.g., 10). If not specified, uses --max-pages from --from-page'
    )
    parser.add_argument(
        '--max-pages',
        type=int,
        default=10,
        help='Maximum number of pages to scrape (default: 10). Ignored if --to-page is specified'
    )
    parser.add_argument(
        '--output',
        type=str,
        default='goodreads_list_books.csv',
        help='Output CSV file path (default: goodreads_list_books.csv)'
    )
    parser.add_argument(
        '--delay',
        type=float,
        default=1.0,
        help='Delay between book page requests in seconds (default: 1.0)'
    )
    parser.add_argument(
        '--start-page',
        type=int,
        default=1,
        help='Starting page number (default: 1). Deprecated: use --from-page instead'
    )
    parser.add_argument(
        '--use-proxy',
        action='store_true',
        help='Use proxy rotation (requires proxy configuration)'
    )
    parser.add_argument(
        '--max-workers',
        type=int,
        default=5,
        help='Maximum number of concurrent workers for book extraction (default: 5)'
    )
    
    args = parser.parse_args()
    
    # Validate URL
    if 'goodreads.com/list/show/' not in args.list_url:
        print(f"Error: Invalid Goodreads list URL: {args.list_url}", file=sys.stderr)
        print("Expected format: https://www.goodreads.com/list/show/<list_id>", file=sys.stderr)
        sys.exit(1)
    
    # Calculate start and end pages based on arguments
    # Priority: --from-page/--to-page > --start-page/--max-pages
    if args.from_page is not None:
        start_page = args.from_page
    else:
        start_page = args.start_page
    
    if args.to_page is not None:
        end_page = args.to_page
        # Validate that to_page >= from_page
        if end_page < start_page:
            print(f"Error: --to-page ({end_page}) must be >= --from-page ({start_page})", file=sys.stderr)
            sys.exit(1)
    else:
        # Use max-pages from start_page
        end_page = start_page + args.max_pages - 1
    
    total_pages = end_page - start_page + 1
    
    print(f"Scraping Goodreads list: {args.list_url}")
    print(f"Pages: {start_page} to {end_page} (inclusive, {total_pages} page(s))")
    print(f"Output file: {args.output}")
    print(f"Delay between requests: {args.delay}s")
    print(f"Max concurrent workers: {args.max_workers}")
    print(f"Using proxy rotation: {args.use_proxy}\n")
    
    # Check if output file exists (needed for checking existing URLs)
    file_exists = False
    try:
        with open(args.output, 'r', encoding='utf-8') as f:
            file_exists = True
    except FileNotFoundError:
        file_exists = False
    
    # Create session with proxy support
    session = get_session_with_proxy(use_proxy=args.use_proxy)
    
    # Collect all book URLs from all pages
    all_book_urls = []
    for page_num in range(start_page, end_page + 1):
        print(f"Scraping page {page_num}...")
        book_urls = extract_book_urls_from_list_page(args.list_url, page_num, session=session)
        all_book_urls.extend(book_urls)
        
        # Random delay between pages to avoid detection
        if page_num < end_page:
            time.sleep(random.uniform(2.0, 4.0))
    
    # Remove duplicates while preserving order
    seen = set()
    unique_book_urls = []
    for url in all_book_urls:
        if url not in seen:
            seen.add(url)
            unique_book_urls.append(url)
    
    # Check for existing books in CSV to avoid re-extraction
    existing_urls = set()
    if file_exists:
        try:
            with open(args.output, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get('url'):
                        existing_urls.add(row['url'])
            print(f"Found {len(existing_urls)} books already in CSV")
        except Exception as e:
            print(f"Warning: Could not read existing CSV: {e}", file=sys.stderr)
    
    # Filter out books that are already in the CSV
    books_to_process = [url for url in unique_book_urls if url not in existing_urls]
    skipped_count = len(unique_book_urls) - len(books_to_process)
    
    print(f"\nTotal unique books found: {len(unique_book_urls)}")
    if skipped_count > 0:
        print(f"Books already in CSV (skipping): {skipped_count}")
    print(f"Books to process: {len(books_to_process)}")
    
    # Check if there are any books to process
    if len(books_to_process) == 0:
        print("\nAll books are already in the CSV. Nothing to extract.")
        print(f"Total books in CSV: {len(existing_urls)}")
        return
    
    print(f"Starting extraction of book details...\n")
    
    # Extract book information
    books = []
    fieldnames = [
        'url', 'title', 'original_title', 'authors', 'rating', 'rating_count',
        'pages', 'language', 'published', 'isbn', 'isbn10', 'cover_image',
        'genres', 'setting', 'characters', 'synopsis'
    ]
    
    # Open CSV file for writing (append mode since we already checked existing URLs)
    with open(args.output, 'a' if file_exists else 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(
            csvfile,
            fieldnames=fieldnames,
            extrasaction='ignore',
            quoting=csv.QUOTE_ALL
        )
        
        if not file_exists:
            # Manually write header without quotes
            header_writer = csv.writer(csvfile, quoting=csv.QUOTE_MINIMAL)
            header_writer.writerow(fieldnames)
            csvfile.flush()
        
        # Use ThreadPoolExecutor for concurrent extraction
        print(f"Starting concurrent extraction with {args.max_workers} workers...\n")
        
        extracted_count = 0
        failed_count = 0
        
        with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
            # Create a session for each worker to avoid conflicts
            sessions = [get_session_with_proxy(use_proxy=args.use_proxy) for _ in range(args.max_workers)]
            
            # Submit all tasks
            future_to_url = {}
            for i, book_url in enumerate(books_to_process, 1):
                # Rotate user agent for each request
                session_idx = (i - 1) % len(sessions)
                worker_session = sessions[session_idx]
                if i % 5 == 0:
                    worker_session.headers['User-Agent'] = ua.random
                
                # Submit task with reduced delay for async processing
                future = executor.submit(
                    extract_book_info,
                    book_url,
                    delay=args.delay / args.max_workers,  # Reduce delay per worker
                    session=worker_session,
                    index=i,
                    total=len(books_to_process)
                )
                future_to_url[future] = book_url
            
            # Process completed tasks as they finish
            for future in as_completed(future_to_url):
                book_url = future_to_url[future]
                try:
                    book, url = future.result()
                    
                    if book:
                        book_dict = book.to_dict()
                        # Replace None with empty string
                        for key, value in book_dict.items():
                            if value is None:
                                book_dict[key] = ''
                        
                        # Thread-safe writing
                        with write_lock:
                            writer.writerow(book_dict)
                            csvfile.flush()  # Ensure data is written immediately
                        
                        books.append(book)
                        extracted_count += 1
                    else:
                        failed_count += 1
                    
                    # Progress update every 10 completed books
                    total_completed = extracted_count + failed_count
                    if total_completed % 10 == 0:
                        with print_lock:
                            print(f"\n📊 Progress: {total_completed}/{len(books_to_process)} completed")
                            print(f"   ✓ Success: {extracted_count} | ✗ Failed: {failed_count}\n")
                    
                except Exception as e:
                    failed_count += 1
                    with print_lock:
                        print(f"  ✗ Exception processing {book_url}: {e}", file=sys.stderr)
    
    print(f"\n{'='*60}")
    print(f"Extraction complete!")
    print(f"Total books extracted: {len(books)}")
    print(f"Output saved to: {args.output}")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()

