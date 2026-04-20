import { router, getAuthUser, clearAuth } from './router.js?v=8';
import { api } from './qtapi.js?v=8';
import { initNav, updateHealth } from './components/nav.js?v=8';
import { toast, initErrorListener, clearAllToasts } from './components/toast.js?v=8';
import { t, setLang, getLang, onLangChange } from './i18n.js?v=8';
import { ensureUiAuditLog } from './modules/ui-audit.js?v=8';

function getTheme() {
  return localStorage.getItem('qt-theme') || 'dark';
}

function themeIcon(mode) {
  return mode === 'light' ? '☀' : '☾';
}

function setTheme(mode) {
  localStorage.setItem('qt-theme', mode);
  document.body.classList.toggle('light', mode === 'light');
  const button = document.getElementById('theme-toggle-btn');
  if (button) button.textContent = themeIcon(mode);
}

function initTheme() {
  setTheme(getTheme());
}

function buildTopbarActions() {
  const actions = document.getElementById('header-actions');
  if (!actions) return;

  const lang = getLang();
  const user = getAuthUser();
  const theme = getTheme();

  actions.innerHTML = `
    <button class="theme-toggle" id="theme-toggle-btn" title="Toggle light/dark mode">${themeIcon(theme)}</button>
    <div class="topbar-lang-toggle" data-no-autotranslate="true" translate="no">
      <button class="lang-btn${lang === 'zh' ? ' active' : ''}" id="tb-lang-zh" data-lang="zh" data-no-autotranslate="true" translate="no">中</button>
      <button class="lang-btn${lang === 'en' ? ' active' : ''}" id="tb-lang-en" data-lang="en" data-no-autotranslate="true" translate="no">EN</button>
    </div>
    ${user ? `
      <div class="topbar-user" id="topbar-user">
        <div class="topbar-avatar">${(user.name || user.email || 'U')[0].toUpperCase()}</div>
        <span class="topbar-username">${user.name || user.email || 'User'}</span>
        <button class="btn btn-ghost btn-sm" id="btn-logout" style="font-size:10px;padding:3px 8px">${t('auth.logout')}</button>
      </div>
    ` : `
      <div class="topbar-auth-links">
        <a href="#/login" class="topbar-auth-btn">${t('auth.login')}</a>
        <a href="#/register" class="topbar-auth-btn topbar-auth-btn--primary">${t('auth.register')}</a>
      </div>
    `}
  `;

  actions.querySelector('#theme-toggle-btn')?.addEventListener('click', () => {
    setTheme(getTheme() === 'dark' ? 'light' : 'dark');
  });

  actions.querySelector('#tb-lang-zh')?.addEventListener('click', () => {
    setLang('zh');
    buildTopbarActions();
  });

  actions.querySelector('#tb-lang-en')?.addEventListener('click', () => {
    setLang('en');
    buildTopbarActions();
  });

  actions.querySelector('#btn-logout')?.addEventListener('click', () => {
    clearAuth();
    toast.info(t('auth.logout'));
    window.location.hash = '#/login';
  });
}

async function updateBackendHealth(showToast = false) {
  try {
    await api.health();
    updateHealth(true);
    if (showToast) toast.success(t('common.backend_online'));
    return true;
  } catch (error) {
    updateHealth(false);
    console.warn('API health check failed during init', error);
    if (showToast) toast.error(t('common.backend_offline'), t('common.features_limited'));
    return false;
  }
}

async function init() {
  ensureUiAuditLog();
  initTheme();
  initNav();
  initErrorListener();

  const root = document.getElementById('app-root');
  buildTopbarActions();

  onLangChange(() => {
    clearAllToasts();
    buildTopbarActions();
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
