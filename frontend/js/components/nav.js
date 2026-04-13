import { ROUTES } from '../router.js?v=3';

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

function icon(name) {
  const path = ICONS[name] || ICONS.grid;
  return `<svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${path}</svg>`;
}

export function renderNav() {
  const container = document.getElementById('nav-links');
  if (!container) return;

  const current = window.location.hash.slice(1) || '/dashboard';
  const groups = {};
  Object.entries(ROUTES).forEach(([path, config]) => {
    if (config.hidden) return;
    const group = config.group || 'other';
    if (!groups[group]) groups[group] = [];
    groups[group].push({ path, config });
  });

  const groupLabels = {
    core: 'Platform',
    quant: 'Quant Engine',
    research: 'Research',
    ops: 'Operations',
  };

  let html = '';
  Object.entries(groups).forEach(([group, items]) => {
    html += `<div class="nav-section-label">${groupLabels[group] || group}</div>`;
    items.forEach(({ path, config }) => {
      const active = path === current ? 'active' : '';
      html += `<a class="nav-item ${active}" href="#${path}" data-path="${path}">
        ${icon(config.icon)}
        <span>${config.label}</span>
      </a>`;
    });
  });

  container.innerHTML = html;
}

export function updateHealth(online) {
  const dot = document.getElementById('health-dot');
  const text = document.getElementById('health-text');
  if (!dot || !text) return;
  dot.className = `status-dot ${online ? 'online' : 'degraded'}`;
  text.textContent = online ? 'Backend Online' : 'Backend Offline';
}

export function initNav() {
  renderNav();
  window.addEventListener('route-change', renderNav);
}
