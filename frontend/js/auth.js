/* ================================================================
   Auth Module — Login, Register, Token Management
   ================================================================ */

const API_BASE = '/api';

// ---- Theme Management ----

function initTheme() {
    const savedTheme = localStorage.getItem('theme') || 'system';
    applyTheme(savedTheme);
}

function applyTheme(theme) {
    let effectiveTheme = theme;
    
    if (theme === 'system') {
        effectiveTheme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }
    
    document.documentElement.setAttribute('data-theme', effectiveTheme);
    localStorage.setItem('theme', theme);
    updateThemeOptions(theme);
}

function setTheme(theme) {
    applyTheme(theme);
    showToast(`Theme changed to ${theme}`, 'success', 2000);
}

function updateThemeOptions(activeTheme) {
    document.querySelectorAll('.theme-option').forEach(opt => {
        opt.classList.toggle('active', opt.dataset.theme === activeTheme);
    });
}

// Listen for system theme changes
window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
    if (localStorage.getItem('theme') === 'system') {
        applyTheme('system');
    }
});

// Initialize theme on load
initTheme();

// ---- User Dropdown ----

function toggleUserMenu() {
    const dropdown = document.getElementById('user-dropdown');
    if (dropdown) {
        dropdown.classList.toggle('open');
    }
}

function closeUserMenu() {
    const dropdown = document.getElementById('user-dropdown');
    if (dropdown) {
        dropdown.classList.remove('open');
    }
}

// Close user menu when clicking outside
document.addEventListener('click', (e) => {
    const dropdown = document.getElementById('user-dropdown');
    if (dropdown && !dropdown.contains(e.target)) {
        dropdown.classList.remove('open');
    }
});

function showHelpModal() {
    closeUserMenu();
    const modal = document.getElementById('helpModal');
    if (modal) {
        new bootstrap.Modal(modal).show();
    }
}

function showAccountModal() {
    closeUserMenu();
    const modal = document.getElementById('accountModal');
    if (modal) {
        const user = getUser();
        if (user) {
            document.getElementById('account-name').textContent = user.name;
            document.getElementById('account-email').textContent = user.email;
            document.getElementById('account-role').textContent = user.role;
        }
        new bootstrap.Modal(modal).show();
    }
}

// Build user dropdown menu HTML
function createUserDropdownMenu() {
    const user = getUser();
    if (!user) return '';
    
    const currentTheme = localStorage.getItem('theme') || 'system';
    
    return `
        <div class="user-menu-header">
            <div class="user-menu-email">${escapeHtmlBasic(user.email)}</div>
            <div class="user-menu-role">${user.role}</div>
        </div>
        <div class="user-menu-divider"></div>
        <div class="user-menu-section">
            <div class="user-menu-section-title">Theme</div>
            <div class="theme-options">
                <button class="theme-option ${currentTheme === 'light' ? 'active' : ''}" data-theme="light" onclick="setTheme('light')">
                    <div class="theme-icon">☀️</div>
                    <div>Light</div>
                </button>
                <button class="theme-option ${currentTheme === 'dark' ? 'active' : ''}" data-theme="dark" onclick="setTheme('dark')">
                    <div class="theme-icon">🌙</div>
                    <div>Dark</div>
                </button>
                <button class="theme-option ${currentTheme === 'system' ? 'active' : ''}" data-theme="system" onclick="setTheme('system')">
                    <div class="theme-icon">💻</div>
                    <div>System</div>
                </button>
            </div>
        </div>
        <div class="user-menu-divider"></div>
        <div class="user-menu-section">
            <button class="user-menu-item" onclick="showAccountModal()">
                <span class="item-icon">👤</span>
                <span>Account Details</span>
            </button>
            <button class="user-menu-item" onclick="showHelpModal()">
                <span class="item-icon">❓</span>
                <span>Help & Support</span>
            </button>
        </div>
        <div class="user-menu-divider"></div>
        <div class="user-menu-section">
            <button class="user-menu-item danger" onclick="logout()">
                <span class="item-icon">🚪</span>
                <span>Logout</span>
            </button>
        </div>
    `;
}

// Initialize user dropdown on dashboard pages
function initUserDropdown() {
    const menu = document.getElementById('user-menu');
    if (menu) {
        menu.innerHTML = createUserDropdownMenu();
        // Update theme options after rendering
        const currentTheme = localStorage.getItem('theme') || 'system';
        updateThemeOptions(currentTheme);
    }
}

// ---- Toast Notification System ----

let toastContainer = null;

function getToastContainer() {
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.className = 'toast-container';
        document.body.appendChild(toastContainer);
    }
    return toastContainer;
}

function showToast(message, type = 'info', duration = 4000) {
    const container = getToastContainer();
    const toast = document.createElement('div');
    toast.className = `toast-notification toast-${type}`;
    
    const icons = {
        success: '✓',
        error: '✕',
        warning: '⚠',
        info: 'ℹ'
    };
    
    const titles = {
        success: 'Success',
        error: 'Error',
        warning: 'Warning',
        info: 'Info'
    };
    
    toast.innerHTML = `
        <span class="toast-icon">${icons[type] || icons.info}</span>
        <div class="toast-content">
            <div class="toast-title">${titles[type] || titles.info}</div>
            <div class="toast-message">${escapeHtmlBasic(message)}</div>
        </div>
        <button class="toast-close" onclick="this.parentElement.remove()">×</button>
    `;
    
    container.appendChild(toast);
    
    // Auto-remove after duration
    setTimeout(() => {
        toast.classList.add('toast-exit');
        setTimeout(() => toast.remove(), 300);
    }, duration);
    
    return toast;
}

function escapeHtmlBasic(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Legacy alert function (redirects to toast for backward compatibility)
function showAlert(msg, type = 'danger') {
    // Map Bootstrap alert types to toast types
    const typeMap = {
        'danger': 'error',
        'success': 'success',
        'warning': 'warning',
        'info': 'info',
        'primary': 'info'
    };
    showToast(msg, typeMap[type] || 'info');
    
    // Also update inline alert if exists (for form feedback)
    const box = document.getElementById('alert-box');
    if (box) {
        box.className = `alert alert-${type}`;
        box.textContent = msg;
        box.classList.remove('d-none');
        setTimeout(() => box.classList.add('d-none'), 4000);
    }
}

// ---- Password Toggle ----

function setupPasswordToggles() {
    document.querySelectorAll('.password-wrapper').forEach(wrapper => {
        const input = wrapper.querySelector('input[type="password"], input[data-password]');
        const toggle = wrapper.querySelector('.password-toggle');
        if (input && toggle) {
            toggle.addEventListener('click', () => {
                const isPassword = input.type === 'password';
                input.type = isPassword ? 'text' : 'password';
                toggle.innerHTML = isPassword ? '👁️' : '👁️‍🗨️';
            });
        }
    });
}

// Setup password toggles on DOM ready
document.addEventListener('DOMContentLoaded', setupPasswordToggles);

function saveAuth(token, user) {
    localStorage.setItem('token', token);
    localStorage.setItem('user', JSON.stringify(user));
}

function getToken() {
    return localStorage.getItem('token');
}

function getUser() {
    const u = localStorage.getItem('user');
    return u ? JSON.parse(u) : null;
}

function logout() {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    window.location.href = '/';
}

function redirectToDashboard(role) {
    const routes = {
        student: '/student/dashboard.html',
        faculty: '/faculty/dashboard.html',
        admin: '/admin/dashboard.html',
    };
    window.location.href = routes[role] || '/';
}

// ---- Auth Check (use on dashboard pages) ----

function requireAuth(expectedRole) {
    const token = getToken();
    const user = getUser();
    if (!token || !user) {
        window.location.href = '/';
        return null;
    }
    if (expectedRole && user.role !== expectedRole) {
        window.location.href = '/';
        return null;
    }
    return user;
}

// ---- API Helper ----

async function apiRequest(url, options = {}) {
    const token = getToken();
    const headers = options.headers || {};

    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }

    if (!(options.body instanceof FormData)) {
        headers['Content-Type'] = 'application/json';
    }

    const response = await fetch(API_BASE + url, { ...options, headers });
    const data = await response.json();

    if (!response.ok) {
        throw new Error(data.error || data.message || 'Request failed');
    }

    return data;
}

// ---- Auto-redirect if already logged in ----

(function checkExistingAuth() {
    const user = getUser();
    const token = getToken();

    // Only auto-redirect on the login page
    if (user && token && window.location.pathname === '/') {
        redirectToDashboard(user.role);
    }
})();

// ---- Toggle Forms ----

document.getElementById('show-register')?.addEventListener('click', (e) => {
    e.preventDefault();
    document.getElementById('login-form').classList.add('d-none');
    document.getElementById('register-form').classList.remove('d-none');
    document.getElementById('alert-box').classList.add('d-none');
});

document.getElementById('show-login')?.addEventListener('click', (e) => {
    e.preventDefault();
    document.getElementById('register-form').classList.add('d-none');
    document.getElementById('login-form').classList.remove('d-none');
    document.getElementById('alert-box').classList.add('d-none');
});

// ---- Login ----

document.getElementById('login-form')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = document.getElementById('login-btn');
    btn.disabled = true;
    btn.textContent = 'Logging in...';

    try {
        const data = await apiRequest('/auth/login', {
            method: 'POST',
            body: JSON.stringify({
                email: document.getElementById('login-email').value,
                password: document.getElementById('login-password').value,
            }),
        });

        saveAuth(data.token, data.user);
        showAlert('Login successful! Redirecting...', 'success');
        setTimeout(() => redirectToDashboard(data.user.role), 500);
    } catch (err) {
        showAlert(err.message);
    } finally {
        btn.disabled = false;
        btn.textContent = 'Login';
    }
});

// ---- Register ----

document.getElementById('register-form')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = document.getElementById('register-btn');
    btn.disabled = true;
    btn.textContent = 'Creating account...';

    try {
        const data = await apiRequest('/auth/register', {
            method: 'POST',
            body: JSON.stringify({
                name: document.getElementById('reg-name').value,
                email: document.getElementById('reg-email').value,
                password: document.getElementById('reg-password').value,
                role: document.getElementById('reg-role').value,
            }),
        });

        saveAuth(data.token, data.user);
        showAlert('Account created! Redirecting...', 'success');
        setTimeout(() => redirectToDashboard(data.user.role), 500);
    } catch (err) {
        showAlert(err.message);
    } finally {
        btn.disabled = false;
        btn.textContent = 'Create Account';
    }
});
