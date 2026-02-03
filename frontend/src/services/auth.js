/**
 * Authentication service for user login, signup, and token management.
 */

// Dynamically determine API URL based on current location
// In production: use /api prefix (nginx reverse proxy)
// In development: use localhost:8000 directly
function getApiBaseUrl() {
    if (window.API_BASE_URL) {
        return window.API_BASE_URL;
    }

    const hostname = window.location.hostname;

    // If on localhost, use localhost backend directly
    if (hostname === 'localhost' || hostname === '127.0.0.1') {
        return 'http://localhost:8000';
    }

    // In production, use /api prefix (nginx proxies to backend)
    return '/api';
}

const API_BASE_URL = getApiBaseUrl();
const TOKEN_KEY = 'auth_token';
const USER_KEY = 'current_user';

/**
 * Sign up a new user
 */
export async function signup(fullName, email, password) {
    try {
        const response = await fetch(`${API_BASE_URL}/auth/signup`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                full_name: fullName,
                email: email,
                password: password,
            }),
        });

        const data = await response.json();

        if (!response.ok) {
            // Handle Pydantic validation errors (detail is an array of objects)
            let errorMessage = 'Failed to create account';
            if (Array.isArray(data.detail)) {
                // Extract the first validation error message
                errorMessage = data.detail[0]?.msg || errorMessage;
            } else if (typeof data.detail === 'string') {
                errorMessage = data.detail;
            }
            throw new Error(errorMessage);
        }

        // Store token and user info
        localStorage.setItem(TOKEN_KEY, data.access_token);
        localStorage.setItem(USER_KEY, JSON.stringify(data.user));

        return data;
    } catch (error) {
        // Handle network errors
        if (error instanceof TypeError && error.message.includes('fetch')) {
            throw new Error('Cannot connect to server. Please make sure the backend is running on http://localhost:8000');
        }
        throw error;
    }
}

/**
 * Log in a user
 */
export async function login(email, password) {
    const response = await fetch(`${API_BASE_URL}/auth/login`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            email: email,
            password: password,
        }),
    });

    const data = await response.json();

    if (!response.ok) {
        // Handle Pydantic validation errors (detail is an array of objects)
        let errorMessage = 'Incorrect email or password';
        if (Array.isArray(data.detail)) {
            errorMessage = data.detail[0]?.msg || errorMessage;
        } else if (typeof data.detail === 'string') {
            errorMessage = data.detail;
        }
        throw new Error(errorMessage);
    }

    // Store token and user info
    localStorage.setItem(TOKEN_KEY, data.access_token);
    localStorage.setItem(USER_KEY, JSON.stringify(data.user));

    return data;
}

/**
 * Log out the current user
 */
export function logout() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    // Clear user-specific data
    clearUserData();
    window.location.href = 'login.html';
}

/**
 * Get the current authentication token
 */
export function getToken() {
    return localStorage.getItem(TOKEN_KEY);
}

/**
 * Get the current user
 */
export function getCurrentUser() {
    const userStr = localStorage.getItem(USER_KEY);
    if (!userStr) return null;
    try {
        return JSON.parse(userStr);
    } catch {
        return null;
    }
}

/**
 * Check if user is authenticated
 */
export function isAuthenticated() {
    return !!getToken() && !!getCurrentUser();
}

/**
 * Get the current user ID
 */
export function getCurrentUserId() {
    const user = getCurrentUser();
    return user ? user.id : null;
}

/**
 * Clear all user-specific data (liked books, borrowed books)
 */
export function clearUserData() {
    const userId = getCurrentUserId();
    if (userId) {
        localStorage.removeItem(`liked_books_${userId}`);
        localStorage.removeItem(`borrowed_books_${userId}`);
    }
    // Also clear old format if any
    localStorage.removeItem('liked_books');
    localStorage.removeItem('borrowed_books');

    // Clear chat session
    sessionStorage.removeItem('chat_conversation_history');
    sessionStorage.removeItem('chat_messages_html');
}

/**
 * Get authorization header for API requests
 */
export function getAuthHeader() {
    const token = getToken();
    return token ? { 'Authorization': `Bearer ${token}` } : {};
}

/**
 * Change user email
 */
export async function changeEmail(currentEmail, newEmail, confirmNewEmail) {
    const token = getToken();
    if (!token) {
        throw new Error('Not authenticated');
    }

    const response = await fetch(`${API_BASE_URL}/auth/change-email`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
            current_email: currentEmail,
            new_email: newEmail,
            confirm_new_email: confirmNewEmail,
        }),
    });

    const data = await response.json();

    if (!response.ok) {
        let errorMessage = 'Failed to change email';
        if (Array.isArray(data.detail)) {
            errorMessage = data.detail[0]?.msg || errorMessage;
        } else if (typeof data.detail === 'string') {
            errorMessage = data.detail;
        }
        throw new Error(errorMessage);
    }

    // Update stored user info
    if (data.email) {
        const user = getCurrentUser();
        if (user) {
            user.email = data.email;
            localStorage.setItem(USER_KEY, JSON.stringify(user));
        }
    }

    return data;
}

/**
 * Change user password
 */
export async function changePassword(currentPassword, newPassword, confirmNewPassword) {
    const token = getToken();
    if (!token) {
        throw new Error('Not authenticated');
    }

    const response = await fetch(`${API_BASE_URL}/auth/change-password`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
            current_password: currentPassword,
            new_password: newPassword,
            confirm_new_password: confirmNewPassword,
        }),
    });

    const data = await response.json();

    if (!response.ok) {
        let errorMessage = 'Failed to change password';
        if (Array.isArray(data.detail)) {
            errorMessage = data.detail[0]?.msg || errorMessage;
        } else if (typeof data.detail === 'string') {
            errorMessage = data.detail;
        }
        throw new Error(errorMessage);
    }

    return data;
}

/**
 * Request password reset (forgot password)
 */
export async function forgotPassword(email) {
    const response = await fetch(`${API_BASE_URL}/auth/forgot-password`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            email: email,
        }),
    });

    const data = await response.json();

    if (!response.ok) {
        let errorMessage = 'Failed to request password reset';
        if (Array.isArray(data.detail)) {
            errorMessage = data.detail[0]?.msg || errorMessage;
        } else if (typeof data.detail === 'string') {
            errorMessage = data.detail;
        }
        throw new Error(errorMessage);
    }

    return data;
}

/**
 * Reset password using reset token
 */
export async function resetPassword(email, resetToken, newPassword, confirmNewPassword) {
    const response = await fetch(`${API_BASE_URL}/auth/reset-password`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            email: email,
            reset_token: resetToken,
            new_password: newPassword,
            confirm_new_password: confirmNewPassword,
        }),
    });

    const data = await response.json();

    if (!response.ok) {
        let errorMessage = 'Failed to reset password';
        if (Array.isArray(data.detail)) {
            errorMessage = data.detail[0]?.msg || errorMessage;
        } else if (typeof data.detail === 'string') {
            errorMessage = data.detail;
        }
        throw new Error(errorMessage);
    }

    return data;
}

