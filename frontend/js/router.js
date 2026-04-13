const VER = 'v8';
import { applyLangToPage } from './i18n.js?v=8';

// ── Auth guard helpers ────────────────────────────────────────────
function getAuthToken() {
  return localStorage.getItem('qt-token') || sessionStorage.getItem('qt-token') || null;
}
function getAuthUser() {
  try {
    const raw = localStorage.getItem('qt-user') || sessionStorage.getItem('qt-user');
    return raw ? JSON.parse(raw) : null;
  } catch { return null; }
}
function clearAuth() {
  localStorage.removeItem('qt-token'); localStorage.removeItem('qt-user');
  sessionStorage.removeItem('qt-token'); sessionStorage.removeItem('qt-user');
}

// Public routes — no auth required
const PUBLIC_ROUTES = new Set(['/login', '/register', '/reset-password']);

export const ROUTES = {
  '/login':          { module: () => import(`./pages/login.js?${VER}`),          label: 'Sign In',     icon: 'lock',         group: 'auth',     hidden: true, noShell: true },
  '/register':       { module: () => import(`./pages/register.js?${VER}`),       label: 'Register',    icon: 'user-plus',    group: 'auth',     hidden: true, noShell: true },
  '/reset-password': { module: () => import(`./pages/reset-password.js?${VER}`), label: 'Reset PW',    icon: 'key',          group: 'auth',     hidden: true, noShell: true },

  '/dashboard': { module: () => import(`./pages/dashboard.js?${VER}`), label: 'Dashboard', icon: 'grid', group: 'core' },
  '/overview':  { module: () => import(`./pages/dashboard.js?${VER}`), label: 'Overview',  icon: 'grid', group: 'core', hidden: true },
  '/research':  { module: () => import(`./pages/research.js?${VER}`),  label: 'Research',  icon: 'search', group: 'quant' },
  '/portfolio': { module: () => import(`./pages/portfolio.js?${VER}`), label: 'Portfolio', icon: 'pie',    group: 'quant' },
  '/backtest':  { module: () => import(`./pages/backtest.js?${VER}`),  label: 'Backtest',  icon: 'chart',  group: 'quant' },
  '/backtests': { module: () => import(`./pages/backtests.js?${VER}`), label: 'Backtests', icon: 'chart',  group: 'quant', hidden: true },
  '/execution': { module: () => import(`./pages/execution.js?${VER}`), label: 'Execution', icon: 'zap',    group: 'quant' },
  '/validation':     { module: () => import(`./pages/validation.js?${VER}`),     label: 'Validation',  icon: 'shield',       group: 'research' },
  '/models':         { module: () => import(`./pages/models.js?${VER}`),         label: 'Models',      icon: 'cpu',          group: 'research' },
  '/chat':           { module: () => import(`./pages/chat.js?${VER}`),           label: 'Chat',        icon: 'message-square', group: 'research' },
  '/score':          { module: () => import(`./pages/score-dashboard.js?${VER}`),label: 'ESG Score',   icon: 'bar-chart-3',  group: 'research' },
  '/reports':        { module: () => import(`./pages/reports.js?${VER}`),        label: 'Reports',     icon: 'file-text',    group: 'ops' },
  '/data-management':{ module: () => import(`./pages/data-management.js?${VER}`),label: 'Data Sync',   icon: 'database',     group: 'ops' },
  '/push-rules':     { module: () => import(`./pages/push-rules.js?${VER}`),     label: 'Push Rules',  icon: 'bell',         group: 'ops' },
  '/subscriptions':  { module: () => import(`./pages/subscriptions.js?${VER}`),  label: 'Subscriptions',icon: 'users',       group: 'ops' },
};

const DEFAULT = '/dashboard';

class Router {
  constructor() {
    this._mod = null;
    this._container = null;
    this._current = null;
  }

  init(container) {
    this._container = container;
    window.addEventListener('hashchange', () => this._go());
    this._go();
  }

  path() {
    const hashPath = window.location.hash.slice(1);
    return hashPath in ROUTES ? hashPath : DEFAULT;
  }

  async navigate(path) {
    window.location.hash = `#${path}`;
  }

  async _go() {
    const path   = this.path();
    const config = ROUTES[path];
    if (!config) {
      window.location.hash = `#${DEFAULT}`;
      return;
    }

    // ── Auth guard: only bounce logged-in users away from auth pages ──
    const isPublic = PUBLIC_ROUTES.has(path);
    const token    = getAuthToken();
    // If already logged in, skip login/register pages → go to dashboard
    if (isPublic && token && (path === '/login' || path === '/register')) {
      window.location.hash = `#${DEFAULT}`;
      return;
    }
    // No forced redirect for unauthenticated users — they can freely browse

    if (this._mod && this._mod.destroy) await this._mod.destroy();
    this._current = path;

    const titleEl = document.getElementById('page-title');
    if (titleEl) titleEl.textContent = config.label;

    // ── Shell visibility ──
    const shell = document.querySelector('.app-shell');
    if (shell) {
      shell.classList.toggle('auth-mode', !!config.noShell);
    }

    window.dispatchEvent(new CustomEvent('route-change', { detail: { path } }));

    this._container.innerHTML = '';
    this._container.classList.remove('page-ready');

    try {
      this._mod = await config.module();
      await this._mod.render(this._container);
      applyLangToPage();
      requestAnimationFrame(() => this._container.classList.add('page-ready'));
    } catch (err) {
      console.error('Page load failed:', err);
      this._container.innerHTML = `<div class="empty-state">
        <div class="empty-state__icon">!</div>
        <div class="empty-state__title">Page failed to load</div>
        <div class="empty-state__text">${err.message}</div>
      </div>`;
    }
  }

  getRoutes()       { return ROUTES; }
  getCurrentPath()  { return this._current || DEFAULT; }
  getAuthToken()    { return getAuthToken(); }
  getAuthUser()     { return getAuthUser(); }
  logout() {
    clearAuth();
    window.location.hash = '#/login';
  }
}

export const router = new Router();
export { getAuthToken, getAuthUser, clearAuth };
