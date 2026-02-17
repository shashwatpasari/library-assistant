/**
 * User-specific book management (liked and borrowed books)
 * Uses backend API for saved books (liked) and localStorage for borrowed books.
 */

import { getCurrentUserId } from './auth.js';
import { API_BASE_URL } from './api.js';

/**
 * Get auth headers for API calls
 */
function getAuthHeaders() {
    const token = localStorage.getItem('auth_token');
    return {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
    };
}

// ── Liked Books (Backend API) ──────────────────────────────────

/**
 * Get all liked/saved books for the current user from backend API.
 * Returns array of book objects.
 */
export async function getLikedBooks() {
    const token = localStorage.getItem('auth_token');
    if (!token) return [];

    try {
        const response = await fetch(`${API_BASE_URL}/saved-books`, {
            headers: getAuthHeaders(),
        });
        if (!response.ok) return [];
        const savedBooks = await response.json();
        // Each saved book entry has { id, user_id, book_id, saved_at, book: {...} }
        // Return the nested book objects (with the saved book's book_id as fallback)
        return savedBooks
            .filter(sb => sb.book)
            .map(sb => sb.book);
    } catch (error) {
        console.error('Error fetching liked books:', error);
        return [];
    }
}

/**
 * Check which book IDs from a list are saved by the user.
 * Returns a Set of saved book IDs.
 */
export async function getSavedBookIds(bookIds) {
    const token = localStorage.getItem('auth_token');
    if (!token || !bookIds || bookIds.length === 0) return new Set();

    try {
        const response = await fetch(`${API_BASE_URL}/saved-books/check-batch`, {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify({ book_ids: bookIds.map(id => parseInt(id)) }),
        });
        if (!response.ok) return new Set();
        const data = await response.json();
        return new Set(data.saved_ids);
    } catch (error) {
        console.error('Error checking saved book IDs:', error);
        return new Set();
    }
}

/**
 * Check if a specific book is saved (uses batch check for single book).
 */
export async function isBookLiked(bookId) {
    const saved = await getSavedBookIds([parseInt(bookId)]);
    return saved.has(parseInt(bookId));
}

/**
 * Save a book via backend API.
 */
export async function addToLiked(bookId) {
    const token = localStorage.getItem('auth_token');
    if (!token) return false;

    try {
        const response = await fetch(`${API_BASE_URL}/saved-books/${bookId}`, {
            method: 'POST',
            headers: getAuthHeaders(),
        });
        return response.ok;
    } catch (error) {
        console.error('Error saving book:', error);
        return false;
    }
}

/**
 * Remove a book from saved list via backend API.
 */
export async function removeFromLiked(bookId) {
    const token = localStorage.getItem('auth_token');
    if (!token) return false;

    try {
        const response = await fetch(`${API_BASE_URL}/saved-books/${bookId}`, {
            method: 'DELETE',
            headers: getAuthHeaders(),
        });
        return response.ok;
    } catch (error) {
        console.error('Error removing saved book:', error);
        return false;
    }
}

/**
 * Toggle like status for a book. Returns new saved state (true/false).
 */
export async function toggleLike(bookId) {
    const isSaved = await isBookLiked(bookId);
    if (isSaved) {
        await removeFromLiked(bookId);
        return false;
    } else {
        await addToLiked(bookId);
        return true;
    }
}


// ── Borrowed Books (Backend API) ───────────────────────────────

/**
 * Get all borrowed books for the current user from backend API.
 * Returns array of book objects (active borrows only).
 */
export async function getBorrowedBooks() {
    const token = localStorage.getItem('auth_token');
    if (!token) return [];

    try {
        const response = await fetch(`${API_BASE_URL}/borrowed-books`, {
            headers: getAuthHeaders(),
        });
        if (!response.ok) return [];
        const borrows = await response.json();
        // Each borrow entry has { id, book_id, borrowed_at, due_date, book: {...} }
        // Return the nested book objects with due_date attached
        return borrows
            .filter(b => b.book)
            .map(b => ({ ...b.book, due_date: b.due_date, borrow_id: b.id }));
    } catch (error) {
        console.error('Error fetching borrowed books:', error);
        return [];
    }
}

/**
 * Return a borrowed book via backend API.
 */
export async function removeFromBorrowed(bookId) {
    const token = localStorage.getItem('auth_token');
    if (!token) return false;

    try {
        const response = await fetch(`${API_BASE_URL}/borrowed-books/${bookId}/return`, {
            method: 'POST',
            headers: getAuthHeaders(),
        });
        return response.ok;
    } catch (error) {
        console.error('Error returning book:', error);
        return false;
    }
}
/**
 * Borrow a book via backend API.
 */
export async function borrowBook(bookId) {
    const token = localStorage.getItem('auth_token');
    if (!token) return false;

    try {
        const response = await fetch(`${API_BASE_URL}/borrowed-books/${bookId}`, {
            method: 'POST',
            headers: getAuthHeaders(),
        });
        return response.ok;
    } catch (error) {
        console.error('Error borrowing book:', error);
        return false;
    }
}

/**
 * Check if a specific book is borrowed.
 */
export async function isBookBorrowed(bookId) {
    const borrowedBooks = await getBorrowedBooks();
    // getBorrowedBooks returns the BOOK objects, so we compare book.id
    return borrowedBooks.some(book => book.id === parseInt(bookId));
}

/**
 * Toggle borrow status for a book.
 */
export async function toggleBorrow(book) {
    const bookId = book.id;
    const isBorrowed = await isBookBorrowed(bookId);

    if (isBorrowed) {
        return await removeFromBorrowed(bookId);
    } else {
        return await borrowBook(bookId);
    }
}
