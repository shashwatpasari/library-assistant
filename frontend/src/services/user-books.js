/**
 * User-specific book management (liked and borrowed books)
 */

import { getCurrentUserId } from './auth.js';

/**
 * Get user-specific storage key for liked books
 */
function getLikedBooksKey() {
    const userId = getCurrentUserId();
    return userId ? `likedBooks_${userId}` : 'likedBooks';
}

/**
 * Get user-specific storage key for borrowed books
 */
function getBorrowedBooksKey() {
    const userId = getCurrentUserId();
    return userId ? `borrowedBooks_${userId}` : 'borrowedBooks';
}

/**
 * Get all liked books for the current user
 */
export function getLikedBooks() {
    const key = getLikedBooksKey();
    return JSON.parse(localStorage.getItem(key) || '[]');
}

/**
 * Save liked books for the current user
 */
export function saveLikedBooks(books) {
    const key = getLikedBooksKey();
    localStorage.setItem(key, JSON.stringify(books));
}

/**
 * Get all borrowed books for the current user
 */
export function getBorrowedBooks() {
    const key = getBorrowedBooksKey();
    return JSON.parse(localStorage.getItem(key) || '[]');
}

/**
 * Save borrowed books for the current user
 */
export function saveBorrowedBooks(books) {
    const key = getBorrowedBooksKey();
    localStorage.setItem(key, JSON.stringify(books));
}

/**
 * Check if a book is liked by the current user
 */
export function isBookLiked(bookId) {
    return getLikedBooks().some(book => book.id === parseInt(bookId));
}

/**
 * Check if a book is borrowed by the current user
 */
export function isBookBorrowed(bookId) {
    return getBorrowedBooks().some(book => book.id === parseInt(bookId));
}

/**
 * Add a book to liked books for the current user
 */
export function addToLiked(book) {
    const likedBooks = getLikedBooks();
    if (!likedBooks.some(b => b.id === book.id)) {
        likedBooks.push(book);
        saveLikedBooks(likedBooks);
    }
}

/**
 * Remove a book from liked books for the current user
 */
export function removeFromLiked(bookId) {
    const likedBooks = getLikedBooks().filter(book => book.id !== parseInt(bookId));
    saveLikedBooks(likedBooks);
}

/**
 * Toggle like status for a book
 */
export function toggleLike(book) {
    if (isBookLiked(book.id)) {
        removeFromLiked(book.id);
    } else {
        addToLiked(book);
    }
}

/**
 * Add a book to borrowed books for the current user
 */
export function addToBorrowed(book) {
    const borrowedBooks = getBorrowedBooks();
    if (!borrowedBooks.some(b => b.id === book.id)) {
        borrowedBooks.push(book);
        saveBorrowedBooks(borrowedBooks);
    }
}

/**
 * Remove a book from borrowed books for the current user
 */
export function removeFromBorrowed(bookId) {
    const borrowedBooks = getBorrowedBooks().filter(book => book.id !== parseInt(bookId));
    saveBorrowedBooks(borrowedBooks);
}

/**
 * Toggle borrow status for a book
 */
export function toggleBorrow(book) {
    if (isBookBorrowed(book.id)) {
        removeFromBorrowed(book.id);
    } else {
        addToBorrowed(book);
    }
}


