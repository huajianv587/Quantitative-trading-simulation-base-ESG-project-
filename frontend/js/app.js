import { router } from './router.js';
import { store } from './store.js';
import { api } from './api.js';
import { renderNav, initNavListener, updateHealthStatus } from './components/nav.js';
import { toastError, toastInfo, initErrorListener } from './components/toast.js';
import { newSessionId } from './utils.js';

if (window.Chart) {
  Chart.defaults.color = '#B0BFD3';
  Chart.defaults.borderColor = '#2A3952';
  Chart.defaults.font.family = '"Plus Jakarta Sans", system-ui, sans-serif';
  Chart.defaults.font.size = 13;
  Chart.defaults.plugins.legend.labels.color = '#F3F7FB';
  Chart.defaults.plugins.tooltip.backgroundColor = 'rgba(17, 24, 39, 0.9)';
  Chart.defaults.plugins.tooltip.borderColor = '#2A3952';
  Chart.defaults.plugins.tooltip.titleColor = '#F3F7FB';
  Chart.defaults.plugins.tooltip.bodyColor = '#B0BFD3';
}

async function init() {
  console.log('[ESG Quant IO] booting...');

  renderNav();
  initNavListener();

  const appRoot = document.getElementById('app-root');
  router.init(appRoot);

  initErrorListener();
  await checkHealth();
  await initSession();

  setupGlobalListeners();
  setupMotionSystem();
  enhanceInteractiveSurfaces();
  startRuntimeRefresh();

  console.log('[ESG Quant IO] ready');
}

async function checkHealth() {
  try {
    const result = await api.system.health();
    updateHealthStatus(true);
    renderHeaderStatus(result);
  } catch (error) {
    updateHealthStatus(false);
    renderHeaderStatus(null, error);
    toastError('Unable to reach the backend runtime.', 'Connection Failed');
  }
}

async function initSession() {
  let sessionId = localStorage.getItem('esg_session_id');
  if (!sessionId) {
    sessionId = newSessionId();
    localStorage.setItem('esg_session_id', sessionId);
  }

  store.set('currentSession', {
    id: sessionId,
    createdAt: new Date().toISOString(),
  });

  try {
    await api.session.create(sessionId);
  } catch (error) {
    console.warn('Session bootstrap fell back to local mode:', error);
  }

  await loadSessionHistory(sessionId);
}

async function loadSessionHistory(sessionId) {
  try {
    const history = await api.session.getHistory(sessionId);
    const messages = history?.messages || [];
    if (messages.length > 0) {
      store.set('chatMessages', messages);
    }
  } catch (error) {
    console.warn('Session history unavailable:', error);
  }
}

function setupGlobalListeners() {
  window.addEventListener('online', async () => {
    updateHealthStatus(true);
    toastInfo('Network connection restored.');
    await checkHealth();
  });

  window.addEventListener('offline', () => {
    updateHealthStatus(false);
    renderHeaderStatus(null, new Error('Offline'));
    toastError('Network connection lost.', 'Network Error');
  });

  setupKeyboardShortcuts();

  window.addEventListener('route-change', () => {
    enhanceInteractiveSurfaces();
  });
}

function setupKeyboardShortcuts() {
  document.addEventListener('keydown', (event) => {
    const navMap = {
      '1': '/overview',
      '2': '/research',
      '3': '/portfolio',
      '4': '/backtests',
      '5': '/chat',
      '6': '/score',
      '7': '/reports',
      '8': '/data',
    };

    if ((event.ctrlKey || event.metaKey) && navMap[event.key]) {
      event.preventDefault();
      window.location.hash = `#${navMap[event.key]}`;
    }
  });
}

function setupMotionSystem() {
  const cursorAura = document.getElementById('cursor-aura');
  const transitionEl = document.getElementById('route-transition');
  const transitionTitle = document.getElementById('route-transition-title');

  if (cursorAura) {
    window.addEventListener('pointermove', (event) => {
      document.documentElement.style.setProperty('--cursor-x', `${event.clientX}px`);
      document.documentElement.style.setProperty('--cursor-y', `${event.clientY}px`);
      cursorAura.classList.add('is-visible');
    }, { passive: true });

    window.addEventListener('pointerleave', () => {
      cursorAura.classList.remove('is-visible');
    });
  }

  window.addEventListener('route-will-change', (event) => {
    if (!transitionEl) return;
    if (transitionTitle) transitionTitle.textContent = event.detail?.label || 'ESG Quant IO';
    transitionEl.classList.remove('is-active');
    void transitionEl.offsetWidth;
    transitionEl.classList.add('is-active');
  });

  window.addEventListener('route-change', () => {
    if (!transitionEl) return;
    setTimeout(() => transitionEl.classList.remove('is-active'), 520);
  });
}

function enhanceInteractiveSurfaces() {
  const targets = document.querySelectorAll('[data-hover-glow], .card, .page-hero, .score-card, .app-topbar');
  targets.forEach((element) => {
    if (element.dataset.motionBound === 'true') return;
    element.dataset.motionBound = 'true';

    element.addEventListener('pointermove', (event) => {
      const rect = element.getBoundingClientRect();
      element.style.setProperty('--mx', `${event.clientX - rect.left}px`);
      element.style.setProperty('--my', `${event.clientY - rect.top}px`);
    });

    element.addEventListener('pointerleave', () => {
      element.style.removeProperty('--mx');
      element.style.removeProperty('--my');
    });
  });
}

function startRuntimeRefresh() {
  const refresh = async () => {
    try {
      const result = await api.system.health();
      updateHealthStatus(true);
      renderHeaderStatus(result);
    } catch (error) {
      updateHealthStatus(false);
      renderHeaderStatus(null, error);
    }
  };

  setInterval(refresh, 45000);
}

function renderHeaderStatus(health, error = null) {
  const container = document.getElementById('header-actions');
  if (!container) return;

  const cards = [];

  if (health) {
    cards.push(statusChip('API', health.ready ? 'Ready' : 'Degraded', health.ready ? 'success' : 'warning'));
    cards.push(statusChip('Mode', health.app_mode || 'unknown', 'info'));
    cards.push(statusChip('RAG', health.modules?.rag ? 'Online' : 'Offline', health.modules?.rag ? 'success' : 'warning'));
    cards.push(statusChip('Quant', health.modules?.quant_system ? 'Online' : 'Offline', health.modules?.quant_system ? 'success' : 'warning'));
  } else {
    cards.push(statusChip('API', 'Offline', 'danger'));
    cards.push(statusChip('Status', error?.message || 'Unavailable', 'danger'));
  }

  container.innerHTML = `
    <div class="flex flex-wrap items-center gap-2">
      ${cards.join('')}
    </div>
  `;
}

function statusChip(label, value, tone = 'info') {
  const toneMap = {
    success: 'border-[rgba(16,185,129,0.28)] bg-[rgba(16,185,129,0.10)] text-[#9ff3cf]',
    warning: 'border-[rgba(245,158,11,0.28)] bg-[rgba(245,158,11,0.10)] text-[#ffd48a]',
    danger: 'border-[rgba(239,68,68,0.28)] bg-[rgba(239,68,68,0.10)] text-[#ffb3b3]',
    info: 'border-[rgba(94,165,255,0.28)] bg-[rgba(94,165,255,0.10)] text-[#bfe0ff]',
  };
  return `
    <div class="px-3 py-2 rounded-2xl border ${toneMap[tone] || toneMap.info}">
      <div class="text-[10px] uppercase tracking-[0.24em] opacity-80">${label}</div>
      <div class="text-sm font-semibold mt-1">${value}</div>
    </div>
  `;
}

window.addEventListener('error', (event) => {
  console.error('Application error:', event.error);
  toastError(event.error?.message || 'Unknown application error.', 'Application Error');
});

window.addEventListener('unhandledrejection', (event) => {
  console.error('Unhandled promise rejection:', event.reason);
  toastError(event.reason?.message || 'Unknown async error.', 'Async Error');
});

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}

window.__ESG_DEBUG__ = {
  store,
  api,
  router,
  nav: (path) => {
    window.location.hash = `#${path}`;
  },
  state: () => store.getState(),
};
