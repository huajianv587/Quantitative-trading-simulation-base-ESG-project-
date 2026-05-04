import { router, getAuthToken, getAuthUser, clearAuth } from './router.js?v=8';
import { api, getApiEndpointLabel } from './qtapi.js?v=8';
import { initNav, updateHealth } from './components/nav.js?v=8';
import { toast, initErrorListener, clearAllToasts } from './components/toast.js?v=8';
import { t, setLang, getLang, onLangChange } from './i18n.js?v=8';
import { ensureUiAuditLog } from './modules/ui-audit.js?v=8';
import { initClickContracts } from './modules/click-contract.js?v=8';
import { errorHandler } from './utils/error-handler.js?v=1';

function getTheme() {
  return localStorage.getItem('qt-theme') === 'light' ? 'light' : 'dark';
}

let shellAccountOpen = false;
let shellAccountGlobalEventsBound = false;

function setTheme(mode) {
  const next = mode === 'light' ? 'light' : 'dark';
  localStorage.setItem('qt-theme', next);
  document.body.classList.toggle('light', next === 'light');
  const button = document.getElementById('theme-toggle-btn');
  if (button) button.textContent = next === 'light' ? t('account.light') : t('account.dark');
}

function initTheme() {
  setTheme(getTheme());
}

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, (char) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  }[char]));
}

function getAuthState() {
  const token = getAuthToken();
  const user = getAuthUser();
  return {
    token,
    user,
    isSignedIn: Boolean(token || user),
  };
}

function getAccountName(user, isSignedIn) {
  if (!isSignedIn) return t('auth.login');
  return user?.name || user?.email || t('account.account');
}

function getAccountInitials(label, isSignedIn) {
  if (!isSignedIn) return 'QT';
  const chars = Array.from(String(label || 'U').trim()).filter((char) => /\S/.test(char));
  return (chars.slice(0, 2).join('') || 'U').toUpperCase();
}

function setShellAccountOpen(open) {
  shellAccountOpen = Boolean(open);
  const host = document.getElementById('shell-account');
  const trigger = document.getElementById('shell-account-trigger');
  const menu = document.getElementById('shell-account-menu');
  if (!host || !trigger || !menu) return;

  host.classList.toggle('is-open', shellAccountOpen);
  trigger.setAttribute('aria-expanded', shellAccountOpen ? 'true' : 'false');
  menu.hidden = !shellAccountOpen;
}

function bindShellAccountGlobalEvents() {
  if (shellAccountGlobalEventsBound) return;
  shellAccountGlobalEventsBound = true;

  document.addEventListener('click', (event) => {
    if (!event.target?.closest?.('#shell-account')) {
      setShellAccountOpen(false);
    }
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
      setShellAccountOpen(false);
    }
  });
}

function buildShellAccount() {
  const actions = document.getElementById('header-actions');
  if (actions) actions.innerHTML = '';

  const host = document.getElementById('shell-account');
  if (!host) return;

  const lang = getLang();
  const theme = getTheme();
  const { user, isSignedIn } = getAuthState();
  const accountName = getAccountName(user, isSignedIn);
  const accountMeta = isSignedIn ? t('account.signed_in') : t('account.not_signed_in');
  const initials = getAccountInitials(accountName, isSignedIn);
  const themeText = theme === 'light' ? t('account.light') : t('account.dark');

  host.innerHTML = `
    <div class="shell-account" data-click-contract="off">
      <button
        type="button"
        class="shell-account-trigger${isSignedIn ? '' : ' shell-account-trigger--guest'}"
        id="shell-account-trigger"
        aria-haspopup="menu"
        aria-expanded="false"
        aria-controls="shell-account-menu"
      >
        <span class="shell-account-avatar" aria-hidden="true">${escapeHtml(initials)}</span>
        <span class="shell-account-trigger__copy">
          <span class="shell-account-trigger__name">${escapeHtml(accountName)}</span>
          <span class="shell-account-trigger__meta">${escapeHtml(accountMeta)}</span>
        </span>
        <span class="shell-account-chevron" aria-hidden="true">&rsaquo;</span>
      </button>

      <div class="shell-account-menu" id="shell-account-menu" role="menu" hidden>
        <div class="shell-account-menu__profile">
          <span class="shell-account-avatar shell-account-avatar--large" aria-hidden="true">${escapeHtml(initials)}</span>
          <span class="shell-account-menu__identity">
            <span class="shell-account-menu__name">${escapeHtml(accountName)}</span>
            <span class="shell-account-menu__meta">${escapeHtml(accountMeta)}</span>
          </span>
        </div>

        <div class="shell-account-menu__section">
          <button type="button" class="shell-account-menu__row" id="shell-theme-toggle" role="menuitem">
            <span class="shell-account-menu__row-copy">
              <span>${t('account.appearance')}</span>
              <small>${escapeHtml(themeText)}</small>
            </span>
            <span class="shell-account-menu__row-action">${escapeHtml(themeText)}</span>
          </button>
        </div>

        <div class="shell-account-menu__section">
          <div class="shell-account-menu__label">${t('account.language')}</div>
          <div class="shell-account-lang" data-no-autotranslate="true" translate="no">
            <button type="button" class="shell-account-lang__btn${lang === 'en' ? ' active' : ''}" data-shell-lang="en" role="menuitem" data-no-autotranslate="true" translate="no">EN</button>
            <button type="button" class="shell-account-lang__btn${lang === 'zh' ? ' active' : ''}" data-shell-lang="zh" role="menuitem" data-no-autotranslate="true" translate="no">中文</button>
          </div>
        </div>

        <div class="shell-account-menu__section shell-account-menu__section--actions">
          ${isSignedIn ? `
            <button type="button" class="shell-account-menu__row shell-account-menu__row--danger" id="shell-logout" role="menuitem">
              <span>${t('auth.logout')}</span>
              <span class="shell-account-menu__row-action">-&gt;</span>
            </button>
          ` : `
            <a class="shell-account-menu__row" id="shell-login" href="#/login" role="menuitem">
              <span>${t('auth.login')}</span>
              <span class="shell-account-menu__row-action">-&gt;</span>
            </a>
            <a class="shell-account-menu__row shell-account-menu__row--primary" id="shell-register" href="#/register" role="menuitem">
              <span>${t('auth.register')}</span>
              <span class="shell-account-menu__row-action">-&gt;</span>
            </a>
          `}
        </div>
      </div>
    </div>
  `;

  host.querySelector('#shell-account-trigger')?.addEventListener('click', (event) => {
    event.stopPropagation();
    setShellAccountOpen(!shellAccountOpen);
  });

  host.querySelector('#shell-theme-toggle')?.addEventListener('click', (event) => {
    event.stopPropagation();
    shellAccountOpen = true;
    setTheme(getTheme() === 'dark' ? 'light' : 'dark');
    buildShellAccount();
  });

  host.querySelectorAll('[data-shell-lang]').forEach((button) => {
    button.addEventListener('click', (event) => {
      event.preventDefault();
      event.stopPropagation();
      shellAccountOpen = true;
      const nextLang = button.dataset.shellLang;
      window.setTimeout(() => setLang(nextLang), 0);
    });
  });

  host.querySelector('#shell-logout')?.addEventListener('click', (event) => {
    event.stopPropagation();
    clearAuth();
    shellAccountOpen = false;
    buildShellAccount();
    toast.info(t('auth.logout'));
    window.location.hash = '#/login';
  });

  host.querySelectorAll('#shell-login, #shell-register').forEach((link) => {
    link.addEventListener('click', () => {
      shellAccountOpen = false;
    });
  });

  setShellAccountOpen(shellAccountOpen);
}

async function updateBackendHealth(showToast = false) {
  try {
    await api.health();
    updateHealth(true);
    if (showToast) toast.success(t('common.backend_online'));

    const banner = document.querySelector('.backend-disconnected-banner');
    if (banner) banner.remove();

    return true;
  } catch (error) {
    updateHealth(false);
    console.warn('API health check failed during init', error);

    if (showToast) {
      const errorInfo = errorHandler.parseError(error, { context: 'backend_health' });
      toast.error(errorInfo.message, errorInfo.details || t('common.features_limited'));
    }

    showBackendDisconnectedBanner();
    return false;
  }
}

function showBackendDisconnectedBanner() {
  if (document.querySelector('.backend-disconnected-banner')) return;

  const lang = getLang();
  const endpoint = getApiEndpointLabel();
  const banner = document.createElement('div');
  banner.className = 'backend-disconnected-banner';
  banner.innerHTML = `
    <button class="close-btn" aria-label="Close">×</button>
    <div class="banner-header">
      <span class="banner-icon">!</span>
      <span class="banner-title">${lang === 'zh' ? '后端服务未连接' : 'Backend disconnected'}</span>
    </div>
    <div class="banner-message">
      ${lang === 'zh'
        ? `后端服务（${endpoint}）暂时不可用，部分功能将回退到缓存或降级视图。`
        : `Backend service (${endpoint}) is unavailable. Some features are falling back to cached or degraded views.`}
    </div>
    <div class="banner-actions">
      <button class="retry-btn">${lang === 'zh' ? '重试连接' : 'Retry'}</button>
    </div>
  `;

  document.body.appendChild(banner);

  banner.querySelector('.close-btn')?.addEventListener('click', () => banner.remove());
  banner.querySelector('.retry-btn')?.addEventListener('click', async () => {
    const success = await updateBackendHealth(true);
    if (success) banner.remove();
  });
}

async function init() {
  ensureUiAuditLog();
  initClickContracts();
  initTheme();
  initNav();
  initErrorListener();
  bindShellAccountGlobalEvents();

  const root = document.getElementById('app-root');
  buildShellAccount();

  onLangChange(() => {
    clearAllToasts();
    buildShellAccount();
  });

  window.addEventListener('route-change', () => {
    buildShellAccount();
  });

  router.init(root);
  await updateBackendHealth(true);

  setInterval(() => {
    updateBackendHealth(false);
  }, 30000);
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
