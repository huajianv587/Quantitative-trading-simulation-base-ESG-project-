import { router, getAuthUser, clearAuth } from './router.js?v=8';
import { api }    from './qtapi.js?v=8';
import { initNav, updateHealth } from './components/nav.js?v=8';
import { toast, initErrorListener } from './components/toast.js?v=8';
import { t, setLang, getLang, onLangChange } from './i18n.js?v=8';

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
  actions.innerHTML = `
    <!-- Language toggle -->
    <div class="topbar-lang-toggle">
      <button class="lang-btn${lang==='zh'?' active':''}" id="tb-lang-zh" data-lang="zh">中</button>
      <button class="lang-btn${lang==='en'?' active':''}" id="tb-lang-en" data-lang="en">EN</button>
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
  initNav();
  initErrorListener();

  const root = document.getElementById('app-root');
  buildTopbarActions();
  onLangChange(() => buildTopbarActions());

  router.init(root);

  /* health check */
  try {
    await api.health();
    updateHealth(true);
    toast.success(t('common.backend_online'));
  } catch {
    updateHealth(false);
    toast.error(t('common.backend_offline'), 'Some features may be unavailable');
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
