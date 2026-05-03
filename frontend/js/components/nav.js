import { t, onLangChange } from '../i18n.js?v=8';
import { ROUTES } from '../router.js?v=8';

const NAV_STORAGE_KEY = 'qt-nav-open-groups';
const NAV_MOBILE_BREAKPOINT = 900;
let _runtimeGroupState = {};
let _lastRenderedPath = null;

const ICONS = {
  grid: '<path d="M3 3h7v7H3zM14 3h7v7h-7zM14 14h7v7h-7zM3 14h7v7H3z"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="m21 21-4.35-4.35"/>',
  pie: '<path d="M12 2a10 10 0 1 1-10 10"/><path d="M12 2v10l7 7"/>',
  chart: '<polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>',
  zap: '<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>',
  shield: '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>',
  cpu: '<rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/><path d="M9 1v3M15 1v3M9 20v3M15 20v3M1 9h3M1 15h3M20 9h3M20 15h3"/>',
  'message-square': '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
  'bar-chart-3': '<path d="M3 3v18h18"/><path d="M7 16V9"/><path d="M12 16V5"/><path d="M17 16v-4"/>',
  'file-text': '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><path d="M16 13H8"/><path d="M16 17H8"/><path d="M10 9H8"/>',
  database: '<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v6c0 1.7 4 3 9 3s9-1.3 9-3V5"/><path d="M3 11v6c0 1.7 4 3 9 3s9-1.3 9-3v-6"/>',
  bell: '<path d="M15 17h5l-1.4-1.4A2 2 0 0 1 18 14.2V11a6 6 0 1 0-12 0v3.2a2 2 0 0 1-.6 1.4L4 17h5"/><path d="M10 21a2 2 0 0 0 4 0"/>',
  users: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.9"/><path d="M16 3.1a4 4 0 0 1 0 7.8"/>',
};

const NAV_GROUPS = [
  {
    id: 'trading_workbench',
    labelKey: 'nav.trading_workbench',
    statusKey: 'trading',
    paths: ['/trading-ops', '/autopilot-policy', '/strategy-registry', '/portfolio', '/execution', '/paper-performance'],
  },
  {
    id: 'research_workbench',
    labelKey: 'nav.research_workbench',
    statusKey: 'research',
    paths: ['/research', '/intelligence', '/market-radar', '/factor-lab', '/simulation', '/agent-lab', '/chat', '/score'],
  },
  {
    id: 'risk_approval',
    labelKey: 'nav.risk_approval',
    statusKey: 'risk',
    paths: ['/debate-desk', '/risk-board', '/outcome-center', '/validation'],
  },
  {
    id: 'data_models',
    labelKey: 'nav.data_models',
    statusKey: 'data',
    paths: ['/connector-center', '/data-management', '/dataset', '/models', '/rl-lab', '/backtest', '/sweep', '/tearsheet'],
  },
  {
    id: 'ops_reports',
    labelKey: 'nav.ops_reports',
    statusKey: 'ops',
    paths: ['/reports', '/push-rules', '/subscriptions'],
  },
  {
    id: 'blueprint_center',
    labelKey: 'nav.blueprint_center',
    statusKey: 'blueprint',
    paths: ['/capabilities'],
  },
];

function icon(name) {
  const path = ICONS[name] || ICONS.grid;
  return `<svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${path}</svg>`;
}

function chevron() {
  return `<svg class="nav-group__chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"></polyline></svg>`;
}

function getStoredGroups() {
  try {
    const raw = localStorage.getItem(NAV_STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : {};
    return parsed && typeof parsed === 'object' ? parsed : {};
  } catch {
    return {};
  }
}

function setStoredGroups(value) {
  if (!isDesktopNavViewport()) {
    _runtimeGroupState = { ...value };
    return;
  }
  try {
    localStorage.setItem(NAV_STORAGE_KEY, JSON.stringify(value));
  } catch {
    // ignore storage failures
  }
}

function isDesktopNavViewport() {
  return window.innerWidth > NAV_MOBILE_BREAKPOINT;
}

function currentGroupState() {
  return isDesktopNavViewport() ? getStoredGroups() : _runtimeGroupState;
}

function defaultGroupState(currentPath) {
  const openAllGroups = !isDesktopNavViewport();
  const state = {};
  NAV_GROUPS.forEach((group) => {
    state[group.id] = openAllGroups || group.paths.includes(currentPath);
  });
  return state;
}

function routeMeta(path) {
  return ROUTES[path];
}

function groupStatus(group) {
  const count = group.paths.filter((path) => !!routeMeta(path)).length;
  const statusMap = {
    trading: t('nav.status.paper'),
    research: t('nav.status.live'),
    risk: t('nav.status.audit'),
    data: `${count}`,
    system: t('nav.status.ops'),
    ops: t('nav.status.ops'),
    blueprint: t('nav.status.blueprint'),
  };
  return statusMap[group.statusKey] || `${count}`;
}

function groupChildCount(group) {
  return group.paths.filter((path) => {
    const config = routeMeta(path);
    return config && !config.hidden;
  }).length;
}

function normalizeGroupState(currentPath) {
  const stored = currentGroupState();
  const hasStoredPreference = NAV_GROUPS.some((group) => Object.prototype.hasOwnProperty.call(stored, group.id));
  const state = defaultGroupState(currentPath);
  NAV_GROUPS.forEach((group) => {
    const hasActive = group.paths.includes(currentPath);
    if (hasStoredPreference && Object.prototype.hasOwnProperty.call(stored, group.id)) {
      state[group.id] = Boolean(stored[group.id]);
    }
    if (hasActive) {
      state[group.id] = true;
    }
  });
  return state;
}

function renderGroup(group, currentPath, openState) {
  const isOpen = openState[group.id];
  const hasActive = group.paths.includes(currentPath);
  const bodyId = `nav-group-body-${group.id}`;
  const children = group.paths
    .map((path) => ({ path, config: routeMeta(path) }))
    .filter(({ config }) => config && !config.hidden);

  return `
    <section class="nav-group ${isOpen ? 'is-open' : ''} ${hasActive ? 'has-active' : ''}" data-group-id="${group.id}">
      <button class="nav-group__trigger" type="button" data-group-trigger="${group.id}" aria-expanded="${isOpen ? 'true' : 'false'}" aria-controls="${bodyId}">
        <span class="nav-group__copy">
          <span class="nav-group__label">${t(group.labelKey)}</span>
          <span class="nav-group__summary">${t(`${group.labelKey}_hint`)}</span>
        </span>
        <span class="nav-group__meta">
          <span class="nav-group__status">${groupStatus(group)}</span>
          <span class="nav-group__count">${groupChildCount(group)}</span>
          ${chevron()}
        </span>
      </button>
      <div class="nav-group__body" id="${bodyId}">
        ${children.map(({ path, config }) => `
          <a class="nav-item ${path === currentPath ? 'active' : ''}" href="#${path}" data-path="${path}">
            ${icon(config.icon)}
            <span>${config.labelKey ? t(config.labelKey) : config.label}</span>
          </a>
        `).join('')}
      </div>
    </section>
  `;
}

export function renderNav() {
  const container = document.getElementById('nav-links');
  if (!container) return;

  const current = window.location.hash.slice(1) || '/dashboard';
  const routeChanged = current !== _lastRenderedPath;
  const openState = normalizeGroupState(current);
  if (routeChanged) {
    _lastRenderedPath = current;
    setStoredGroups(openState);
  }

  const dashboardMeta = ROUTES['/dashboard'];
  let html = `
    <div class="nav-section-label">${t('nav.platform')}</div>
    <a class="nav-item ${(current === '/dashboard' || current === '/overview') ? 'active' : ''}" href="#/dashboard" data-path="/dashboard">
      ${icon(dashboardMeta.icon)}
      <span>${t(dashboardMeta.labelKey)}</span>
    </a>
  `;

  html += NAV_GROUPS.map((group) => renderGroup(group, current, openState)).join('');
  container.innerHTML = html;

  container.querySelectorAll('[data-group-trigger]').forEach((button) => {
    button.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        button.click();
      }
    });
    button.addEventListener('click', () => {
      const groupId = button.getAttribute('data-group-trigger');
      const currentState = normalizeGroupState(current);
      const next = { ...currentGroupState(), [groupId]: !currentState[groupId] };
      setStoredGroups(next);
      renderNav();
    });
  });
}

export function updateHealth(online) {
  const dot = document.getElementById('health-dot');
  const text = document.getElementById('health-text');
  if (!dot || !text) return;
  dot.className = `status-dot ${online ? 'online' : 'degraded'}`;
  text.textContent = online ? t('common.backend_online') : t('common.backend_offline');
}

function syncHealthLabel() {
  const dot = document.getElementById('health-dot');
  const text = document.getElementById('health-text');
  if (!dot || !text) return;

  if (dot.classList.contains('online')) {
    updateHealth(true);
    return;
  }

  if (dot.classList.contains('degraded')) {
    updateHealth(false);
    return;
  }

  text.textContent = t('common.connecting');
}

export function initNav() {
  renderNav();
  syncHealthLabel();
  window.addEventListener('route-change', () => {
    renderNav();
    requestAnimationFrame(syncHealthLabel);
  });
  onLangChange(() => {
    renderNav();
    syncHealthLabel();
  });
}
