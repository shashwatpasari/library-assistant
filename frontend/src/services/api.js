/**
 * API service for communicating with the backend FastAPI server.
 */

const API_BASE_URL = 'http://localhost:8000';

/**
 * Fetch books from the API with optional filters and pagination.
 */
export async function fetchBooks({ skip = 0, limit = 50, subject = null, genre = null } = {}) {
    const params = new URLSearchParams({
        skip: skip.toString(),
        limit: limit.toString(),
    });

    if (subject) params.append('subject', subject);
    if (genre) params.append('genre', genre);

    const response = await fetch(`${API_BASE_URL}/books?${params}`);
    if (!response.ok) {
        throw new Error(`Failed to fetch books: ${response.statusText}`);
    }
    return await response.json();
}

/**
 * Get total count of books with optional filters.
 */
export async function getBookCount({ subject = null, genre = null } = {}) {
    const params = new URLSearchParams();

    if (subject) params.append('subject', subject);
    if (genre) params.append('genre', genre);

    const response = await fetch(`${API_BASE_URL}/books/count?${params}`);
    if (!response.ok) {
        throw new Error(`Failed to fetch book count: ${response.statusText}`);
    }
    return await response.json();
}

/**
 * Search books by title or ISBN.
 */
export async function searchBooks({ title = null, isbn = null } = {}) {
    if (!title && !isbn) {
        throw new Error('At least one search parameter (title or isbn) is required');
    }

    const params = new URLSearchParams();
    if (title) params.append('title', title);
    if (isbn) params.append('isbn', isbn);

    const response = await fetch(`${API_BASE_URL}/books/search?${params}`);
    if (!response.ok) {
        throw new Error(`Failed to search books: ${response.statusText}`);
    }
    return await response.json();
}

/**
 * Autocomplete search for books by title or author (returns top 5 results).
 */
export async function autocompleteSearch(query) {
    if (!query || query.trim().length < 2) {
        return [];
    }

    const params = new URLSearchParams({
        q: query.trim(),
        limit: '5',
    });

    const response = await fetch(`${API_BASE_URL}/books/search?${params}`);
    if (!response.ok) {
        throw new Error(`Failed to autocomplete search: ${response.statusText}`);
    }
    return await response.json();
}

/**
 * Get a single book by ID.
 */
export async function getBook(bookId) {
    const response = await fetch(`${API_BASE_URL}/books/${bookId}`);
    if (!response.ok) {
        if (response.status === 404) {
            throw new Error(`Book with id ${bookId} not found`);
        }
        throw new Error(`Failed to fetch book: ${response.statusText}`);
    }
    return await response.json();
}

/**
 * Get availability information for a book.
 */
export async function getBookAvailability(bookId) {
    const response = await fetch(`${API_BASE_URL}/books/${bookId}/availability`);
    if (!response.ok) {
        throw new Error(`Failed to fetch availability: ${response.statusText}`);
    }
    return await response.json();
}

/**
 * Get top genres from the API.
 */
export async function getTopGenres(limit = 10) {
    const response = await fetch(`${API_BASE_URL}/books/genres/top?limit=${limit}`);
    if (!response.ok) {
        throw new Error(`Failed to fetch top genres: ${response.statusText}`);
    }
    return await response.json();
}

/**
 * Get the cover image URL for a book (prioritizes image, then image_original, then cover_image_url).
 * Note: image_original URLs from ISBNdb may have expired JWT tokens, so we prioritize the regular image URL.
 */
export function getBookCoverUrl(book) {
    return book.image || book.image_original || book.cover_image_url || '/placeholder-book.jpg';
}

/**
 * Format authors string for display.
 */
export function formatAuthors(book) {
    if (book.authors) {
        return book.authors.split(';').map(a => a.trim()).join(', ');
    }
    return book.author || 'Unknown Author';
}

