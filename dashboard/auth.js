/**
 * auth.js - Shared authentication utilities for CLAT Preparation Hub
 * 
 * Provides:
 * - checkAuth() - Check if user is logged in and get user profile
 * - User indicator UI component
 * - Automatic redirect to login for protected pages
 */

const AUTH_API = window.location.origin;

/**
 * Check authentication status and get user profile
 * @param {boolean} requireAuth - If true, redirect to login if not authenticated
 * @returns {Object|null} User profile or null if not authenticated
 */
async function checkAuth(requireAuth = false) {
    try {
        const response = await fetch(`${AUTH_API}/auth/user`);
        
        if (response.ok) {
            const user = await response.json();
            
            // Update user indicator if it exists
            updateUserIndicator(user);
            
            return user;
        } else if (requireAuth) {
            // Not logged in and auth is required
            window.location.href = '/login.html';
            return null;
        }
        
        return null;
    } catch (error) {
        console.log('Auth check failed:', error);
        
        if (requireAuth) {
            window.location.href = '/login.html';
        }
        
        return null;
    }
}

/**
 * Update the user indicator in the UI
 * @param {Object} user - User profile object
 */
function updateUserIndicator(user) {
    const indicator = document.getElementById('user-indicator');
    if (!indicator) return;
    
    if (user) {
        const initial = (user.name || user.email || 'U')[0].toUpperCase();
        const displayName = user.name || user.email?.split('@')[0] || 'User';
        
        indicator.innerHTML = `
            <div class="user-avatar" title="${user.email || ''}">${initial}</div>
            <span class="user-name">${displayName}</span>
            <a href="/auth/logout" class="logout-btn" title="Sign out">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
                    <polyline points="16 17 21 12 16 7"/>
                    <line x1="21" y1="12" x2="9" y2="12"/>
                </svg>
            </a>
        `;
        indicator.style.display = 'flex';
    } else {
        indicator.innerHTML = `
            <a href="/login.html" class="login-link">Sign In</a>
        `;
        indicator.style.display = 'flex';
    }
}

/**
 * Sign out the current user
 */
async function signOut() {
    try {
        await fetch(`${AUTH_API}/auth/logout`);
        window.location.href = '/login.html';
    } catch (error) {
        console.error('Sign out failed:', error);
        window.location.href = '/login.html';
    }
}

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { checkAuth, updateUserIndicator, signOut };
}

