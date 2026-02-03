/**
 * Shared header component for all pages
 * Provides consistent navigation and search functionality
 */

/**
 * Renders the header HTML
 * @returns {string} HTML string for the header
 */
export function renderHeader() {
    return `
        <header class="sticky top-0 z-50 w-full border-b border-border-light dark:border-border-dark bg-background-light/80 dark:bg-background-dark/80 backdrop-blur-sm">
            <div class="container mx-auto flex items-center justify-between whitespace-nowrap px-4 sm:px-6 lg:px-8 py-3">
                <div class="flex items-center gap-8">
                    <a href="index.html" class="flex items-center gap-2 text-text-light dark:text-text-dark hover:opacity-80 transition-opacity">
                        <span class="material-symbols-outlined text-primary text-3xl">local_library</span>
                        <h2 class="text-xl font-bold tracking-tight">Library Assistant</h2>
                    </a>
                    <nav class="hidden md:flex items-center gap-6 font-heading">
                        <a class="text-xl font-medium hover:text-primary dark:hover:text-primary transition-colors" href="index.html">Home</a>
                        <a class="text-xl font-medium text-primary" href="catalog.html">Catalog</a>
                        <a class="text-xl font-medium hover:text-primary dark:hover:text-primary transition-colors" href="my-books.html">My Books</a>
                    </nav>
                </div>
                <div class="flex flex-1 items-center justify-end gap-4">
                    <div class="hidden sm:block relative search-container w-full max-w-[10rem] transition-all duration-300">
                        <label class="relative flex items-center h-10 w-full cursor-text">
                            <span class="material-symbols-outlined absolute left-3 text-gray-500 dark:text-gray-400 pointer-events-none cursor-text">search</span>
                            <input
                                id="search-input"
                                class="form-input flex w-full min-w-0 flex-1 resize-none overflow-hidden rounded-full border-[1.5px] border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-800 text-text-light dark:text-text-dark h-full placeholder:text-gray-500 dark:placeholder:text-gray-400 pl-10 pr-4 text-base focus:outline-none hover:border-blue-300 dark:hover:border-blue-400 focus:border-blue-500 dark:focus:border-blue-500 transition-colors duration-150"
                                placeholder="Search..."
                                value=""
                                autocomplete="off"
                            />
                        </label>
                        <div id="search-dropdown" class="hidden absolute top-full mt-2 w-full max-w-[10rem] bg-white dark:bg-gray-800 border-[1.5px] border-gray-200 dark:border-gray-600 rounded-lg shadow-xl overflow-hidden z-[100] transition-all duration-150">
                            <!-- Autocomplete results will be inserted here -->
                        </div>
                    </div>
                    <div id="user-profile-container" class="relative">
                        <!-- User profile button/dropdown will be inserted here -->
                    </div>
                </div>
            </div>
        </header>
    `;
}

/**
 * Renders the user profile dropdown
 */
export function renderUserProfile() {
    // Dynamic import to avoid circular dependency
    return import('/src/services/auth.js').then(({ getCurrentUser, isAuthenticated, logout }) => {
        const container = document.getElementById('user-profile-container');
        if (!container) return;

        if (!isAuthenticated()) {
            container.innerHTML = `
                <a href="login.html" class="inline-flex items-center justify-center px-4 py-2 rounded-lg bg-primary text-white hover:bg-primary/90 transition-colors text-sm font-medium">
                    Login
                </a>
            `;
            return;
        }

        const user = getCurrentUser();
        if (!user) return;

        container.innerHTML = `
            <div class="relative">
                <button 
                    id="user-profile-btn"
                    class="flex items-center justify-center size-10 rounded-full bg-gray-200 dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-300 dark:hover:bg-gray-600 transition-colors cursor-pointer border-2 border-transparent hover:border-primary"
                    aria-label="User profile"
                >
                    <span class="material-symbols-outlined text-xl">person</span>
                </button>
                <div id="user-profile-dropdown" class="hidden absolute right-0 mt-2 w-64 bg-white dark:bg-gray-800 rounded-lg shadow-xl border border-border-light dark:border-border-dark overflow-hidden z-50">
                    <div class="p-4 border-b border-border-light dark:border-border-dark">
                        <p class="text-sm font-semibold text-text-light dark:text-text-dark">${escapeHtml(user.full_name || 'User')}</p>
                        <p class="text-xs text-gray-600 dark:text-gray-400 mt-1">${escapeHtml(user.email || '')}</p>
                    </div>
                    <div class="py-2">
                        <button id="settings-btn" class="w-full text-left px-4 py-2 text-sm text-text-light dark:text-text-dark hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors flex items-center gap-2">
                            <span class="material-symbols-outlined text-base">settings</span>
                            Settings
                        </button>
                        <button id="logout-btn" class="w-full text-left px-4 py-2 text-sm text-red-600 dark:text-red-400 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors flex items-center gap-2">
                            <span class="material-symbols-outlined text-base">logout</span>
                            Logout
                        </button>
                    </div>
                </div>
            </div>
        `;

        // Initialize dropdown toggle
        const profileBtn = document.getElementById('user-profile-btn');
        const dropdown = document.getElementById('user-profile-dropdown');

        if (profileBtn && dropdown) {
            profileBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                dropdown.classList.toggle('hidden');
            });

            // Close dropdown when clicking outside
            document.addEventListener('click', (e) => {
                if (!container.contains(e.target)) {
                    dropdown.classList.add('hidden');
                }
            });

            // Handle logout
            document.getElementById('logout-btn')?.addEventListener('click', () => {
                logout();
            });

            // Handle settings
            document.getElementById('settings-btn')?.addEventListener('click', () => {
                dropdown.classList.add('hidden');
                showSettingsModal(user);
            });
        }
    }).catch(err => {
        console.error('Error rendering user profile:', err);
    });
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Show settings modal
 */
function showSettingsModal(user) {
    const modal = document.createElement('div');
    modal.id = 'settings-modal';
    modal.className = 'fixed inset-0 bg-black/50 flex items-center justify-center z-50';
    modal.innerHTML = `
        <div class="bg-white dark:bg-gray-800 rounded-xl shadow-lg p-6 max-w-md w-full mx-4 border border-border-light dark:border-border-dark">
            <div class="flex items-center justify-between mb-6">
                <h2 class="font-heading text-2xl font-medium text-text-light dark:text-text-dark">Settings</h2>
                <button id="close-settings-modal" class="text-gray-500 hover:text-gray-700 dark:hover:text-gray-300">
                    <span class="material-symbols-outlined">close</span>
                </button>
            </div>
            <div class="space-y-3">
                <button id="settings-change-email-btn" class="w-full text-left px-4 py-3 rounded-lg border border-border-light dark:border-border-dark hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors flex items-center gap-3">
                    <span class="material-symbols-outlined text-xl text-primary">email</span>
                    <div class="flex-1">
                        <p class="text-sm font-medium text-text-light dark:text-text-dark">Change Email</p>
                        <p class="text-xs text-gray-500 dark:text-gray-400">Update your email address</p>
                    </div>
                    <span class="material-symbols-outlined text-gray-400">chevron_right</span>
                </button>
                <button id="settings-change-password-btn" class="w-full text-left px-4 py-3 rounded-lg border border-border-light dark:border-border-dark hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors flex items-center gap-3">
                    <span class="material-symbols-outlined text-xl text-primary">lock</span>
                    <div class="flex-1">
                        <p class="text-sm font-medium text-text-light dark:text-text-dark">Change Password</p>
                        <p class="text-xs text-gray-500 dark:text-gray-400">Update your password</p>
                    </div>
                    <span class="material-symbols-outlined text-gray-400">chevron_right</span>
                </button>
            </div>
        </div>
    `;

    document.body.appendChild(modal);

    // Handle close
    const closeModal = () => modal.remove();
    document.getElementById('close-settings-modal')?.addEventListener('click', closeModal);
    modal.addEventListener('click', (e) => {
        if (e.target === modal) closeModal();
    });

    // Handle change email button
    document.getElementById('settings-change-email-btn')?.addEventListener('click', () => {
        closeModal();
        showChangeEmailModal(user);
    });

    // Handle change password button
    document.getElementById('settings-change-password-btn')?.addEventListener('click', () => {
        closeModal();
        showChangePasswordModal();
    });
}

/**
 * Show change email modal
 */
function showChangeEmailModal(user) {
    // This will be implemented with a modal component
    const modal = document.createElement('div');
    modal.id = 'change-email-modal';
    modal.className = 'fixed inset-0 bg-black/50 flex items-center justify-center z-50';
    modal.innerHTML = `
        <div class="bg-white dark:bg-gray-800 rounded-xl shadow-lg p-6 max-w-md w-full mx-4 border border-border-light dark:border-border-dark">
            <div class="flex items-center justify-between mb-4">
                <h2 class="font-heading text-2xl font-medium text-text-light dark:text-text-dark">Change Email</h2>
                <button id="close-change-email-modal" class="text-gray-500 hover:text-gray-700 dark:hover:text-gray-300">
                    <span class="material-symbols-outlined">close</span>
                </button>
            </div>
            <form id="change-email-form" class="space-y-4">
                <div id="change-email-error" class="hidden bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-400 px-4 py-3 rounded-lg text-sm"></div>
                <div>
                    <label class="block text-sm font-medium text-text-light dark:text-text-dark mb-2">Current Email</label>
                    <input type="email" id="current-email" required
                        class="w-full px-4 py-2 rounded-lg border border-border-light dark:border-border-dark bg-white dark:bg-gray-700 text-text-light dark:text-text-dark focus:ring-2 focus:ring-primary focus:border-transparent outline-none"
                        value="${escapeHtml(user.email || '')}"
                    />
                </div>
                <div>
                    <label class="block text-sm font-medium text-text-light dark:text-text-dark mb-2">New Email</label>
                    <input type="email" id="new-email" required
                        class="w-full px-4 py-2 rounded-lg border border-border-light dark:border-border-dark bg-white dark:bg-gray-700 text-text-light dark:text-text-dark focus:ring-2 focus:ring-primary focus:border-transparent outline-none"
                    />
                </div>
                <div>
                    <label class="block text-sm font-medium text-text-light dark:text-text-dark mb-2">Confirm New Email</label>
                    <input type="email" id="confirm-new-email" required
                        class="w-full px-4 py-2 rounded-lg border border-border-light dark:border-border-dark bg-white dark:bg-gray-700 text-text-light dark:text-text-dark focus:ring-2 focus:ring-primary focus:border-transparent outline-none"
                    />
                </div>
                <div class="flex gap-3">
                    <button type="submit" class="flex-1 bg-primary text-white py-2 px-4 rounded-lg hover:bg-primary/90 transition-colors">Change Email</button>
                    <button type="button" id="cancel-change-email" class="px-4 py-2 rounded-lg border border-border-light dark:border-border-dark hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors">Cancel</button>
                </div>
            </form>
        </div>
    `;

    document.body.appendChild(modal);

    // Handle close
    document.getElementById('close-change-email-modal')?.addEventListener('click', () => modal.remove());
    document.getElementById('cancel-change-email')?.addEventListener('click', () => modal.remove());
    modal.addEventListener('click', (e) => {
        if (e.target === modal) modal.remove();
    });

    // Handle form submission
    document.getElementById('change-email-form')?.addEventListener('submit', async (e) => {
        e.preventDefault();
        const errorDiv = document.getElementById('change-email-error');
        const submitBtn = e.target.querySelector('button[type="submit"]');

        errorDiv.classList.add('hidden');

        const currentEmail = document.getElementById('current-email').value;
        const newEmail = document.getElementById('new-email').value;
        const confirmNewEmail = document.getElementById('confirm-new-email').value;

        if (newEmail !== confirmNewEmail) {
            errorDiv.textContent = 'New email addresses do not match';
            errorDiv.classList.remove('hidden');
            return;
        }

        submitBtn.disabled = true;
        submitBtn.textContent = 'Changing...';

        try {
            const { changeEmail } = await import('/src/services/auth.js');
            await changeEmail(currentEmail, newEmail, confirmNewEmail);
            alert('Email changed successfully!');
            modal.remove();
            renderUserProfile(); // Refresh profile
            window.location.reload(); // Reload to update everywhere
        } catch (error) {
            errorDiv.textContent = error.message || 'Failed to change email';
            errorDiv.classList.remove('hidden');
            submitBtn.disabled = false;
            submitBtn.textContent = 'Change Email';
        }
    });
}

/**
 * Show change password modal
 */
function showChangePasswordModal() {
    const modal = document.createElement('div');
    modal.id = 'change-password-modal';
    modal.className = 'fixed inset-0 bg-black/50 flex items-center justify-center z-50';
    modal.innerHTML = `
        <div class="bg-white dark:bg-gray-800 rounded-xl shadow-lg p-6 max-w-md w-full mx-4 border border-border-light dark:border-border-dark">
            <div class="flex items-center justify-between mb-4">
                <h2 class="font-heading text-2xl font-medium text-text-light dark:text-text-dark">Change Password</h2>
                <button id="close-change-password-modal" class="text-gray-500 hover:text-gray-700 dark:hover:text-gray-300">
                    <span class="material-symbols-outlined">close</span>
                </button>
            </div>
            <form id="change-password-form" class="space-y-4">
                <div id="change-password-error" class="hidden bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-400 px-4 py-3 rounded-lg text-sm"></div>
                <div>
                    <label class="block text-sm font-medium text-text-light dark:text-text-dark mb-2">Current Password</label>
                    <div class="relative">
                        <input type="password" id="current-password" required
                            class="w-full px-4 py-2 pr-10 rounded-lg border border-border-light dark:border-border-dark bg-white dark:bg-gray-700 text-text-light dark:text-text-dark focus:ring-2 focus:ring-primary focus:border-transparent outline-none"
                        />
                        <button 
                            type="button"
                            id="toggle-current-password"
                            class="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 transition-colors"
                            aria-label="Toggle password visibility"
                        >
                            <span class="material-symbols-outlined text-lg">visibility</span>
                        </button>
                    </div>
                </div>
                <div>
                    <label class="block text-sm font-medium text-text-light dark:text-text-dark mb-2">New Password</label>
                    <div class="relative">
                        <input type="password" id="new-password" required minlength="8"
                            class="w-full px-4 py-2 pr-10 rounded-lg border border-border-light dark:border-border-dark bg-white dark:bg-gray-700 text-text-light dark:text-text-dark focus:ring-2 focus:ring-primary focus:border-transparent outline-none"
                        />
                        <button 
                            type="button"
                            id="toggle-new-password"
                            class="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 transition-colors"
                            aria-label="Toggle password visibility"
                        >
                            <span class="material-symbols-outlined text-lg">visibility</span>
                        </button>
                    </div>
                    <p class="mt-1 text-xs text-gray-500 dark:text-gray-400">
                        Password must be at least 8 characters long, contain at least one number and one special character
                    </p>
                    <div id="change-password-requirements" class="mt-2 space-y-1 text-xs">
                        <div id="change-req-length" class="text-gray-500 dark:text-gray-400">
                            <span class="material-symbols-outlined text-sm align-middle">circle</span> At least 8 characters
                        </div>
                        <div id="change-req-number" class="text-gray-500 dark:text-gray-400">
                            <span class="material-symbols-outlined text-sm align-middle">circle</span> Contains a number
                        </div>
                        <div id="change-req-special" class="text-gray-500 dark:text-gray-400">
                            <span class="material-symbols-outlined text-sm align-middle">circle</span> Contains a special character (!@#$%^&*)
                        </div>
                    </div>
                </div>
                <div>
                    <label class="block text-sm font-medium text-text-light dark:text-text-dark mb-2">Confirm New Password</label>
                    <div class="relative">
                        <input type="password" id="confirm-new-password" required minlength="8"
                            class="w-full px-4 py-2 pr-10 rounded-lg border border-border-light dark:border-border-dark bg-white dark:bg-gray-700 text-text-light dark:text-text-dark focus:ring-2 focus:ring-primary focus:border-transparent outline-none"
                        />
                        <button 
                            type="button"
                            id="toggle-confirm-password"
                            class="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 transition-colors"
                            aria-label="Toggle password visibility"
                        >
                            <span class="material-symbols-outlined text-lg">visibility</span>
                        </button>
                    </div>
                </div>
                <div class="flex gap-3">
                    <button type="submit" class="flex-1 bg-primary text-white py-2 px-4 rounded-lg hover:bg-primary/90 transition-colors">Change Password</button>
                    <button type="button" id="cancel-change-password" class="px-4 py-2 rounded-lg border border-border-light dark:border-border-dark hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors">Cancel</button>
                </div>
            </form>
        </div>
    `;

    document.body.appendChild(modal);

    // Handle close
    document.getElementById('close-change-password-modal')?.addEventListener('click', () => modal.remove());
    document.getElementById('cancel-change-password')?.addEventListener('click', () => modal.remove());
    modal.addEventListener('click', (e) => {
        if (e.target === modal) modal.remove();
    });

    // Toggle password visibility for change password modal
    const setupPasswordToggle = (toggleBtnId, inputId) => {
        const toggleBtn = document.getElementById(toggleBtnId);
        const input = document.getElementById(inputId);
        if (toggleBtn && input) {
            toggleBtn.addEventListener('click', () => {
                const type = input.getAttribute('type') === 'password' ? 'text' : 'password';
                input.setAttribute('type', type);
                const icon = toggleBtn.querySelector('.material-symbols-outlined');
                icon.textContent = type === 'password' ? 'visibility' : 'visibility_off';
            });
        }
    };

    setupPasswordToggle('toggle-current-password', 'current-password');
    setupPasswordToggle('toggle-new-password', 'new-password');
    setupPasswordToggle('toggle-confirm-password', 'confirm-new-password');

    // Real-time password validation
    const newPasswordInput = document.getElementById('new-password');
    if (newPasswordInput) {
        newPasswordInput.addEventListener('input', (e) => {
            validateChangePassword(e.target.value);
        });
    }

    function validateChangePassword(password) {
        const hasLength = password.length >= 8;
        const hasNumber = /\d/.test(password);
        const hasSpecial = /[!@#$%^&*(),.?":{}|<>]/.test(password);

        // Update requirement indicators
        updateChangeRequirement('change-req-length', hasLength);
        updateChangeRequirement('change-req-number', hasNumber);
        updateChangeRequirement('change-req-special', hasSpecial);

        return hasLength && hasNumber && hasSpecial;
    }

    function updateChangeRequirement(id, met) {
        const element = document.getElementById(id);
        if (element) {
            const icon = element.querySelector('.material-symbols-outlined');
            if (met) {
                icon.textContent = 'check_circle';
                icon.classList.add('text-green-500');
                icon.classList.remove('text-gray-500');
                element.classList.remove('text-gray-500', 'dark:text-gray-400');
                element.classList.add('text-green-600', 'dark:text-green-400');
            } else {
                icon.textContent = 'circle';
                icon.classList.remove('text-green-500');
                icon.classList.add('text-gray-500');
                element.classList.remove('text-green-600', 'dark:text-green-400');
                element.classList.add('text-gray-500', 'dark:text-gray-400');
            }
        }
    }

    // Handle form submission
    document.getElementById('change-password-form')?.addEventListener('submit', async (e) => {
        e.preventDefault();
        const errorDiv = document.getElementById('change-password-error');
        const submitBtn = e.target.querySelector('button[type="submit"]');

        errorDiv.classList.add('hidden');

        const currentPassword = document.getElementById('current-password').value;
        const newPassword = document.getElementById('new-password').value;
        const confirmNewPassword = document.getElementById('confirm-new-password').value;

        if (newPassword !== confirmNewPassword) {
            errorDiv.textContent = 'New passwords do not match';
            errorDiv.classList.remove('hidden');
            return;
        }

        // Validate password before submitting
        if (!validateChangePassword(newPassword)) {
            errorDiv.textContent = 'Password does not meet requirements. Please check the requirements below.';
            errorDiv.classList.remove('hidden');
            return;
        }

        submitBtn.disabled = true;
        submitBtn.textContent = 'Changing...';

        try {
            const { changePassword } = await import('/src/services/auth.js');
            await changePassword(currentPassword, newPassword, confirmNewPassword);
            alert('Password changed successfully!');
            modal.remove();
        } catch (error) {
            errorDiv.textContent = error.message || 'Failed to change password';
            errorDiv.classList.remove('hidden');
            submitBtn.disabled = false;
            submitBtn.textContent = 'Change Password';
        }
    });
}

/**
 * Initializes header functionality (search, navigation highlighting, autocomplete, user profile)
 */
export function initHeader() {
    // Render user profile
    renderUserProfile();
    // Get current page to highlight active nav link
    const currentPage = window.location.pathname.split('/').pop() || 'index.html';

    // Highlight active navigation link
    document.querySelectorAll('header nav a[href]').forEach(link => {
        const linkPage = link.getAttribute('href');
        // Check if this link matches the current page
        const isActive = linkPage === currentPage ||
            (currentPage === '' && linkPage === 'index.html') ||
            (currentPage === 'index.html' && linkPage === 'index.html');

        if (isActive) {
            link.classList.add('text-primary');
            link.classList.remove('hover:text-primary', 'dark:hover:text-primary');
        } else {
            link.classList.remove('text-primary');
            if (!link.classList.contains('hover:text-primary')) {
                link.classList.add('hover:text-primary', 'dark:hover:text-primary');
            }
        }
    });

    // Autocomplete search functionality
    initAutocomplete('search-input', 'search-dropdown');
}

/**
 * Initialize autocomplete for a search input
 */
async function initAutocomplete(inputId, dropdownId) {
    const searchInput = document.getElementById(inputId);
    const dropdown = document.getElementById(dropdownId);

    if (!searchInput || !dropdown) return;

    // Import autocomplete function
    const { autocompleteSearch, getBookCoverUrl, formatAuthors } = await import('../services/api.js');

    let debounceTimer = null;
    let currentResults = [];
    let selectedIndex = -1;

    // Escape HTML to prevent XSS
    function escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // Render dropdown results
    function renderResults(books) {
        if (!books || books.length === 0) {
            dropdown.classList.add('hidden');
            return;
        }

        // Limit to 5 results
        const limitedBooks = books.slice(0, 5);

        currentResults = limitedBooks;
        selectedIndex = -1;

        const html = limitedBooks.map((book, index) => {
            const coverUrl = getBookCoverUrl(book);
            const authors = formatAuthors(book);

            return `
                <a href="book-details.html?id=${book.id}" 
                   class="autocomplete-item flex items-center gap-2 py-2 px-3 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors cursor-pointer border-b border-border-light dark:border-border-dark last:border-b-0"
                   data-index="${index}">
                    <img src="${coverUrl}" 
                         alt="${escapeHtml(book.title)}" 
                         class="w-10 h-14 object-cover rounded shadow-sm flex-shrink-0"
                         onerror="this.style.display='none'"/>
                    <div class="flex-1 min-w-0">
                        <p class="text-sm font-medium text-text-light dark:text-text-dark truncate">${escapeHtml(book.title)}</p>
                        <p class="text-xs text-gray-600 dark:text-gray-400 truncate">${escapeHtml(authors)}</p>
                    </div>
                </a>
            `;
        }).join('');

        dropdown.innerHTML = html;
        dropdown.classList.remove('hidden');
    }

    // Highlight selected item
    function highlightItem(index) {
        const items = dropdown.querySelectorAll('.autocomplete-item');
        items.forEach((item, i) => {
            if (i === index) {
                item.classList.add('bg-gray-100', 'dark:bg-gray-700');
            } else {
                item.classList.remove('bg-gray-100', 'dark:bg-gray-700');
            }
        });
    }

    // Handle search input
    searchInput.addEventListener('input', (e) => {
        const query = e.target.value.trim();

        // Clear previous timer
        if (debounceTimer) {
            clearTimeout(debounceTimer);
        }

        // Hide dropdown if query is too short
        if (query.length < 2) {
            dropdown.classList.add('hidden');
            return;
        }

        // Debounce search (300ms delay)
        debounceTimer = setTimeout(async () => {
            try {
                const results = await autocompleteSearch(query);
                renderResults(results);
            } catch (error) {
                console.error('Autocomplete search error:', error);
                dropdown.classList.add('hidden');
            }
        }, 300);
    });

    // Handle keyboard navigation
    searchInput.addEventListener('keydown', (e) => {
        const items = dropdown.querySelectorAll('.autocomplete-item');

        if (e.key === 'ArrowDown') {
            e.preventDefault();
            selectedIndex = Math.min(selectedIndex + 1, items.length - 1);
            highlightItem(selectedIndex);
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            selectedIndex = Math.max(selectedIndex - 1, -1);
            highlightItem(selectedIndex);
        } else if (e.key === 'Enter') {
            e.preventDefault();
            if (selectedIndex >= 0 && items[selectedIndex]) {
                items[selectedIndex].click();
            }
        } else if (e.key === 'Escape') {
            dropdown.classList.add('hidden');
            selectedIndex = -1;
        }
    });

    // Handle focus - expand search bar and show dropdown, and match borders
    searchInput.addEventListener('focus', () => {
        // Expand search bar and dropdown
        const searchContainer = searchInput.closest('.search-container');
        if (searchContainer) {
            searchContainer.classList.remove('max-w-[10rem]');
            searchContainer.classList.add('max-w-[20rem]');
        }

        // Expand dropdown to match width; border color handled purely in CSS
        dropdown.classList.remove('max-w-[10rem]');
        dropdown.classList.add('max-w-[20rem]');

        if (currentResults.length > 0) {
            dropdown.classList.remove('hidden');
        }
    });

    // Handle blur - contract search bar and hide results, reset borders
    searchInput.addEventListener('blur', () => {
        // Delay to allow dropdown clicks to register
        setTimeout(() => {
            const searchContainer = searchInput.closest('.search-container');
            if (searchContainer && !searchInput.matches(':focus')) {
                searchContainer.classList.remove('max-w-[20rem]');
                searchContainer.classList.add('max-w-[10rem]');

                // Contract dropdown to match width; border color handled in CSS
                dropdown.classList.remove('max-w-[20rem]');
                dropdown.classList.add('max-w-[10rem]');

                // Hide results when search loses focus
                dropdown.classList.add('hidden');
                selectedIndex = -1;
            }
        }, 200);
    });

    // Close dropdown when clicking outside
    document.addEventListener('click', (e) => {
        if (!searchInput.contains(e.target) && !dropdown.contains(e.target)) {
            dropdown.classList.add('hidden');
            selectedIndex = -1;
        }
    });
}
