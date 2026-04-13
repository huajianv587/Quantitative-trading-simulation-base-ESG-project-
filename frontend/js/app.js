import { router, getAuthUser, clearAuth } from './router.js?v=8';
import { api }    from './qtapi.js?v=8';
import { initNav, updateHealth } from './components/nav.js?v=8';
import { toast, initErrorListener, clearAllToasts } from './components/toast.js?v=8';
import { t, setLang, getLang, onLangChange } from './i18n.js?v=8';

/* ── Theme (light / dark) ──────────────────────────────────── */
function getTheme() { return localStorage.getItem('qt-theme') || 'dark'; }
function setTheme(mode) {
  localStorage.setItem('qt-theme', mode);
  document.body.classList.toggle('light', mode === 'light');
  // Update toggle button icon
  const btn = document.getElementById('theme-toggle-btn');
  if (btn) btn.textContent = mode === 'light' ? '🌙' : '☀';
}
function initTheme() { setTheme(getTheme()); }

/* ── Chart.js global defaults ─ */
if (window.Chart) {
  Chart.defaults.color              = '#8ba4c8';
  Chart.defaults.borderColor        = 'rgba(96,165,250,0.08)';
  Chart.defaults.font.family        = "'IBM Plex Mono', monospace";
  Chart.defaults.font.size          = 11;
  Chart.defaults.plugins.legend.labels.color = '#8ba4c8';
  Chart.defaults.plugins.tooltip.backgroundColor = 'rgba(6,13,31,0.95)';
  Chart.defaults.plugins.tooltip.borderColor      = 'rgba(96,165,250,0.20)';
  Chart.defaults.plugins.tooltip.borderWidth      = 1;
  Chart.defaults.plugins.tooltip.titleColor       = '#e8f1ff';
  Chart.defaults.plugins.tooltip.bodyColor        = '#8ba4c8';
  Chart.defaults.plugins.tooltip.cornerRadius     = 8;
  Chart.defaults.plugins.tooltip.padding          = 12;
  Chart.defaults.plugins.tooltip.caretSize        = 5;
  Chart.defaults.elements.line.tension            = 0.4;
  Chart.defaults.elements.point.radius            = 0;
  Chart.defaults.elements.point.hoverRadius       = 4;
}

function buildTopbarActions() {
  const actions = document.getElementById('header-actions');
  if (!actions) return;
  const lang = getLang();
  const user = getAuthUser();
  const theme = getTheme();
  const zhLabel = lang === 'en' ? 'CH' : '中';
  actions.innerHTML = `
    <!-- Theme toggle -->
    <button class="theme-toggle" id="theme-toggle-btn" title="Toggle light/dark mode">${theme === 'light' ? '🌙' : '☀'}</button>
    <!-- Language toggle -->
    <div class="topbar-lang-toggle" data-no-autotranslate="true" translate="no">
      <button class="lang-btn${lang==='zh'?' active':''}" id="tb-lang-zh" data-lang="zh" data-no-autotranslate="true" translate="no">${zhLabel}</button>
      <button class="lang-btn${lang==='en'?' active':''}" id="tb-lang-en" data-lang="en" data-no-autotranslate="true" translate="no">EN</button>
    </div>
    ${user ? `
    <!-- User menu (authenticated) -->
    <div class="topbar-user" id="topbar-user">
      <div class="topbar-avatar">${(user.name||user.email||'U')[0].toUpperCase()}</div>
      <span class="topbar-username">${user.name || user.email || 'User'}</span>
      <button class="btn btn-ghost btn-sm" id="btn-logout" style="font-size:10px;padding:3px 8px">${t('auth.logout')}</button>
    </div>` : `
    <!-- Auth links (unauthenticated) -->
    <div class="topbar-auth-links">
      <a href="#/login" class="topbar-auth-btn">${t('auth.login')}</a>
      <a href="#/register" class="topbar-auth-btn topbar-auth-btn--primary">${t('auth.register')}</a>
    </div>`}
  `;

  // Theme toggle
  actions.querySelector('#theme-toggle-btn')?.addEventListener('click', () => {
    const next = getTheme() === 'dark' ? 'light' : 'dark';
    setTheme(next);
  });

  // Lang toggle
  actions.querySelector('#tb-lang-zh')?.addEventListener('click', () => { setLang('zh'); buildTopbarActions(); });
  actions.querySelector('#tb-lang-en')?.addEventListener('click', () => { setLang('en'); buildTopbarActions(); });

  // Logout
  actions.querySelector('#btn-logout')?.addEventListener('click', () => {
    clearAuth();
    toast.info(t('auth.logout'));
    window.location.hash = '#/login';
  });
}

async function init() {
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

  /* health check */
  try {
    await api.health();
    updateHealth(true);
    toast.success(t('common.backend_online'));
  } catch {
    updateHealth(false);
    toast.error(t('common.backend_offline'), t('common.features_limited'));
  }

  /* periodic health ping */
  setInterval(async () => {
    try { await api.health(); updateHealth(true); }
    catch { updateHealth(false); }
  }, 30000);
}

document.readyState === 'loading'
  ? document.addEventListener('DOMContentLoaded', init)
  : init();
