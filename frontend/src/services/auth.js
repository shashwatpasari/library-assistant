/**
 * Authentication service for user login, signup, and token management.
 */

// API_BASE_URL can be overridden by setting window.API_BASE_URL before loading this script
const API_BASE_URL = window.API_BASE_URL || 'http://localhost:8000';
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
            throw new Error(data.detail || 'Failed to create account');
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
        throw new Error(data.detail || 'Incorrect email or password');
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
        throw new Error(data.detail || 'Failed to change email');
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
        throw new Error(data.detail || 'Failed to change password');
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
        throw new Error(data.detail || 'Failed to request password reset');
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
        throw new Error(data.detail || 'Failed to reset password');
    }

    return data;
}

