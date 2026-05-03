const VER = 'v8';
import { applyLangToPage, onLangChange, t } from './i18n.js?v=8';

function getAuthToken() {
  return localStorage.getItem('qt-token') || sessionStorage.getItem('qt-token') || null;
}

function getAuthUser() {
  try {
    const raw = localStorage.getItem('qt-user') || sessionStorage.getItem('qt-user');
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function clearAuth() {
  localStorage.removeItem('qt-token');
  localStorage.removeItem('qt-user');
  sessionStorage.removeItem('qt-token');
  sessionStorage.removeItem('qt-user');
}

const PUBLIC_ROUTES = new Set(['/login', '/register', '/reset-password']);

export const ROUTES = {
  '/login': { module: () => import(`./pages/login.js?${VER}`), labelKey: 'page.login', icon: 'lock', group: 'auth', hidden: true, noShell: true },
  '/register': { module: () => import(`./pages/register.js?${VER}`), labelKey: 'page.register_auth', icon: 'user-plus', group: 'auth', hidden: true, noShell: true },
  '/reset-password': { module: () => import(`./pages/reset-password.js?${VER}`), labelKey: 'page.reset_pw', icon: 'key', group: 'auth', hidden: true, noShell: true },

  '/dashboard': { module: () => import(`./pages/dashboard.js?${VER}`), labelKey: 'page.dashboard', icon: 'grid', group: 'core' },
  '/overview': { module: () => import(`./pages/dashboard.js?${VER}`), labelKey: 'page.dashboard', icon: 'grid', group: 'core', hidden: true },
  '/research': { module: () => import(`./pages/research.js?${VER}`), labelKey: 'page.research', icon: 'search', group: 'research' },
  '/intelligence': { module: () => import(`./pages/intelligence.js?${VER}`), labelKey: 'page.intelligence', icon: 'bar-chart-3', group: 'research' },
  '/factor-lab': { module: () => import(`./pages/factor-lab.js?${VER}`), labelKey: 'page.factor_lab', icon: 'chart', group: 'research' },
  '/simulation': { module: () => import(`./pages/simulation.js?${VER}`), labelKey: 'page.simulation', icon: 'zap', group: 'research' },
  '/connector-center': { module: () => import(`./pages/connector-center.js?${VER}`), labelKey: 'page.connector_center', icon: 'database', group: 'data' },
  '/market-radar': { module: () => import(`./pages/market-radar.js?${VER}`), labelKey: 'page.market_radar', icon: 'search', group: 'research' },
  '/agent-lab': { module: () => import(`./pages/agent-lab.js?${VER}`), labelKey: 'page.agent_lab', icon: 'cpu', group: 'research' },
  '/debate-desk': { module: () => import(`./pages/debate-desk.js?${VER}`), labelKey: 'page.debate_desk', icon: 'message-square', group: 'risk' },
  '/risk-board': { module: () => import(`./pages/risk-board.js?${VER}`), labelKey: 'page.risk_board', icon: 'shield', group: 'risk' },
  '/trading-ops': { module: () => import(`./pages/trading-ops.js?${VER}`), labelKey: 'page.trading_ops', icon: 'zap', group: 'trading' },
  '/autopilot-policy': { module: () => import(`./pages/autopilot-policy.js?${VER}`), labelKey: 'page.autopilot_policy', icon: 'shield', group: 'trading' },
  '/strategy-registry': { module: () => import(`./pages/strategy-registry.js?${VER}`), labelKey: 'page.strategy_registry', icon: 'chart', group: 'trading' },
  '/outcome-center': { module: () => import(`./pages/outcome-center.js?${VER}`), labelKey: 'page.outcome_center', icon: 'shield', group: 'risk' },
  '/portfolio': { module: () => import(`./pages/portfolio.js?${VER}`), labelKey: 'page.portfolio', icon: 'pie', group: 'trading' },
  '/backtest': { module: () => import(`./pages/backtest.js?${VER}`), labelKey: 'page.backtest', icon: 'chart', group: 'data' },
  '/backtests': { module: () => import(`./pages/backtests.js?${VER}`), labelKey: 'page.backtest', icon: 'chart', group: 'data', hidden: true },
  '/sweep': { module: () => import(`./pages/sweep.js?${VER}`), labelKey: 'page.sweep', icon: 'grid', group: 'data' },
  '/tearsheet': { module: () => import(`./pages/tearsheet.js?${VER}`), labelKey: 'page.tearsheet', icon: 'file-text', group: 'data' },
  '/dataset': { module: () => import(`./pages/dataset.js?${VER}`), labelKey: 'page.dataset', icon: 'database', group: 'data' },
  '/execution': { module: () => import(`./pages/execution.js?${VER}`), labelKey: 'page.execution', icon: 'zap', group: 'trading' },
  '/paper-performance': { module: () => import(`./pages/paper-performance.js?${VER}`), labelKey: 'page.paper_performance', icon: 'bar-chart-3', group: 'trading' },
  '/validation': { module: () => import(`./pages/validation.js?${VER}`), labelKey: 'page.validation', icon: 'shield', group: 'risk' },
  '/capabilities': { module: () => import(`./pages/capabilities.js?${VER}`), labelKey: 'page.capabilities', icon: 'grid', group: 'blueprint' },
  '/models': { module: () => import(`./pages/models.js?${VER}`), labelKey: 'page.models', icon: 'cpu', group: 'data' },
  '/rl-lab': { module: () => import(`./pages/rl-lab.js?${VER}`), labelKey: 'page.rl_lab', icon: 'cpu', group: 'data' },
  '/chat': { module: () => import(`./pages/chat.js?${VER}`), labelKey: 'page.chat', icon: 'message-square', group: 'research' },
  '/score': { module: () => import(`./pages/score-dashboard.js?${VER}`), labelKey: 'page.score', icon: 'bar-chart-3', group: 'research' },
  '/reports': { module: () => import(`./pages/reports.js?${VER}`), labelKey: 'page.reports', icon: 'file-text', group: 'ops' },
  '/data-management': { module: () => import(`./pages/data-management.js?${VER}`), labelKey: 'page.data', icon: 'database', group: 'data' },
  '/push-rules': { module: () => import(`./pages/push-rules.js?${VER}`), labelKey: 'page.push', icon: 'bell', group: 'ops' },
  '/subscriptions': { module: () => import(`./pages/subscriptions.js?${VER}`), labelKey: 'page.subs', icon: 'users', group: 'ops' },
};

const DEFAULT = '/dashboard';

function resolveLandingEntry() {
  const configured = typeof window.__ESG_LANDING_ENTRY__ === 'string' ? window.__ESG_LANDING_ENTRY__.trim() : '';
  if (configured) return configured;

  const { origin, pathname } = window.location;
  if (/\/app\/index\.html$/i.test(pathname || '')) {
    return `${origin}${pathname.replace(/\/app\/index\.html$/i, '/')}`;
  }
  if (/\/app\/$/i.test(pathname || '')) {
    return `${origin}${pathname.replace(/\/app\/$/i, '/')}`;
  }
  return `${origin}/`;
}

class Router {
  constructor() {
    this._mod = null;
    this._container = null;
    this._current = null;
  }

  init(container) {
    this._container = container;
    window.addEventListener('hashchange', () => this._go());
    onLangChange(() => this._applyTitle(this.getCurrentPath()));

    if (!window.location.hash || window.location.hash === '#' || window.location.hash === '#/') {
      window.location.replace(resolveLandingEntry());
      return;
    }
    this._go();
  }

  path() {
    const hashPath = window.location.hash.slice(1);
    if (!hashPath || hashPath === '/') return DEFAULT;
    return hashPath in ROUTES ? hashPath : DEFAULT;
  }

  async navigate(path) {
    window.location.hash = `#${path}`;
  }

  _applyTitle(path) {
    const config = ROUTES[path];
    const titleEl = document.getElementById('page-title');
    if (!titleEl || !config) return;
    titleEl.textContent = config.labelKey ? t(config.labelKey) : config.label;
  }

  async _go() {
    const path = this.path();
    const config = ROUTES[path];
    if (!config) {
      window.location.hash = `#${DEFAULT}`;
      return;
    }

    const isPublic = PUBLIC_ROUTES.has(path);
    const token = getAuthToken();
    if (isPublic && token && (path === '/login' || path === '/register')) {
      window.location.hash = `#${DEFAULT}`;
      return;
    }

    if (this._mod && this._mod.destroy) await this._mod.destroy();
    this._current = path;
    this._applyTitle(path);

    const shell = document.querySelector('.app-shell');
    if (shell) shell.classList.toggle('auth-mode', Boolean(config.noShell));

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
      if (window.errorHandler) {
        const errorInfo = window.errorHandler.parseError(err, {
          page: path,
          url: `${window.location.origin}/app/#/pages/${path.slice(1)}.js?${VER}`,
        });
        const errorUI = window.errorHandler.createErrorUI(errorInfo, {
          variant: 'compact',
          showRetry: true,
          onRetry: () => this._go(),
        });
        this._container.appendChild(errorUI);
      } else {
        this._container.innerHTML = `<div class="empty-state">
          <div class="empty-state__icon">!</div>
          <div class="empty-state__title">${t('common.page_failed_load')}</div>
          <div class="empty-state__text">${err.message || t('common.page_failed_retry')}</div>
        </div>`;
      }
    }
  }

  getRoutes() { return ROUTES; }
  getCurrentPath() { return this._current || DEFAULT; }
  getAuthToken() { return getAuthToken(); }
  getAuthUser() { return getAuthUser(); }
  logout() {
    clearAuth();
    window.location.hash = '#/login';
  }
}

export const router = new Router();
export { getAuthToken, getAuthUser, clearAuth };
