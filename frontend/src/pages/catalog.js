/**
 * Book catalog page functionality.
 */

import { fetchBooks, getBookCoverUrl, formatAuthors } from '../services/api.js';

let currentPage = 0;
let currentSubject = null;
const pageSize = 30;

/**
 * Render a book card.
 */
function renderBookCard(book) {
    const coverUrl = getBookCoverUrl(book);
    const authors = formatAuthors(book);
    
    return `
        <div class="group flex flex-col gap-3">
            <a href="book-details.html?id=${book.id}" class="relative w-full overflow-hidden bg-center bg-no-repeat aspect-[3/4] bg-cover rounded-lg shadow-md transition-transform duration-300 group-hover:scale-105">
                <div class="w-full h-full bg-cover bg-center" style='background-image: url("${coverUrl}");'></div>
                <button aria-label="Add to My Books" class="absolute top-2 right-2 flex items-center justify-center size-8 rounded-full bg-black/30 backdrop-blur-sm text-white hover:bg-primary/80 transition-colors" onclick="event.preventDefault(); toggleFavorite(${book.id})">
                    <span class="material-symbols-outlined text-base">favorite</span>
                </button>
            </a>
            <div>
                <p class="text-base font-medium leading-tight truncate">${escapeHtml(book.title)}</p>
                <p class="text-sm text-gray-600 dark:text-gray-400">${escapeHtml(authors)}</p>
            </div>
        </div>
    `;
}

/**
 * Escape HTML to prevent XSS.
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Load and display books.
 */
async function loadBooks(subject = null, page = 0) {
    const grid = document.getElementById('books-grid');
    if (!grid) return;
    
    try {
        grid.innerHTML = '<div class="col-span-full text-center py-8">Loading books...</div>';
        
        const books = await fetchBooks({
            skip: page * pageSize,
            limit: pageSize,
            subject: subject,
        });
        
        if (books.length === 0) {
            grid.innerHTML = '<div class="col-span-full text-center py-8 text-gray-500">No books found.</div>';
            return;
        }
        
        grid.innerHTML = books.map(renderBookCard).join('');
    } catch (error) {
        console.error('Error loading books:', error);
        grid.innerHTML = `<div class="col-span-full text-center py-8 text-red-500">Error loading books: ${error.message}</div>`;
    }
}

/**
 * Handle subject filter clicks.
 */
function handleSubjectFilter(subject) {
    currentSubject = subject === 'All' ? null : subject;
    currentPage = 0;
    loadBooks(currentSubject, currentPage);
    
    // Update active button
    document.querySelectorAll('.subject-filter').forEach(btn => {
        btn.classList.remove('bg-primary', 'text-white');
        btn.classList.add('bg-white', 'dark:bg-gray-800', 'border');
    });
    event.target.classList.add('bg-primary', 'text-white');
    event.target.classList.remove('bg-white', 'dark:bg-gray-800', 'border');
}

/**
 * Handle search.
 */
function handleSearch() {
    const searchInput = document.querySelector('input[placeholder*="Search"]');
    if (!searchInput) return;
    
    const query = searchInput.value.trim();
    if (query.length < 2) {
        loadBooks(currentSubject, currentPage);
        return;
    }
    
    // For now, just filter by title - can be enhanced to use search endpoint
    // This is a simple client-side filter
    window.location.href = `search.html?q=${encodeURIComponent(query)}`;
}

/**
 * Toggle favorite (placeholder - can be enhanced with backend).
 */
function toggleFavorite(bookId) {
    // TODO: Implement favorite functionality with backend
    console.log('Toggle favorite for book:', bookId);
}

// Initialize page
document.addEventListener('DOMContentLoaded', () => {
    loadBooks(currentSubject, currentPage);
    
    // Set up search
    const searchInput = document.querySelector('input[placeholder*="Search"]');
    if (searchInput) {
        searchInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                handleSearch();
            }
        });
    }
    
    // Set up subject filters
    document.querySelectorAll('.subject-filter').forEach(btn => {
        btn.addEventListener('click', (e) => {
            handleSubjectFilter(e.target.textContent.trim());
        });
    });
});

// Export for use in HTML
window.loadBooks = loadBooks;
window.handleSubjectFilter = handleSubjectFilter;
window.toggleFavorite = toggleFavorite;

