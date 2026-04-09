import { router } from '../router.js';

export function renderNav() {
  const navLinks = document.getElementById('nav-links');
  if (!navLinks) return;

  const routes = router.getRoutes();
  const currentPath = router.getCurrentPath();

  navLinks.innerHTML = '';

  Object.entries(routes).forEach(([path, config]) => {
    const isActive = path === currentPath;
    const link = document.createElement('a');
    link.href = `#${path}`;
    link.dataset.hoverGlow = 'true';
    link.className = [
      'nav-link',
      'block shrink-0 whitespace-nowrap px-4 py-3 sm:px-5 sm:py-4 rounded-2xl text-base sm:text-[17px] font-semibold',
      'transition-all duration-200 border',
      isActive
        ? 'bg-[rgba(94,165,255,0.12)] text-[#8ec5ff] border-[rgba(94,165,255,0.3)] shadow-[0_10px_24px_rgba(0,0,0,0.12)]'
        : 'text-[var(--text-secondary)] border-transparent hover:text-[var(--text-primary)] hover:bg-[#182335]',
    ].join(' ');
    link.title = config.description;
    link.innerHTML = `
      <div class="flex items-center gap-3.5">
        <span class="inline-flex items-center justify-center w-9 h-9 rounded-xl bg-[rgba(255,255,255,0.03)] border border-[rgba(255,255,255,0.05)]">
          ${getIconSvg(config.icon)}
        </span>
        <span>${config.label}</span>
      </div>
    `;
    navLinks.appendChild(link);
  });
}

export function updateHealthStatus(isOnline) {
  const indicator = document.getElementById('health-indicator');
  if (!indicator) return;

  const dotColor = isOnline ? '#10B981' : '#F59E0B';
  const statusText = isOnline ? 'Backend Connected' : 'Waiting For Backend';

  indicator.innerHTML = `
    <span class="inline-block w-2 h-2 rounded-full" style="background-color: ${dotColor}; box-shadow: 0 0 0 6px ${isOnline ? 'rgba(16,185,129,0.12)' : 'rgba(245,158,11,0.12)'};"></span>
    <span>${statusText}</span>
  `;
}

export function initNavListener() {
  window.addEventListener('route-change', () => {
    renderNav();
  });
}

function getIconSvg(iconName) {
  const icons = {
    sparkles: pathIcon('M12 3l1.8 4.2L18 9l-4.2 1.8L12 15l-1.8-4.2L6 9l4.2-1.8L12 3zm6 10l.9 2.1L21 16l-2.1.9L18 19l-.9-2.1L15 16l2.1-.9L18 13zM6 14l1.2 2.8L10 18l-2.8 1.2L6 22l-1.2-2.8L2 18l2.8-1.2L6 14z'),
    brain: pathIcon('M9 4a3 3 0 0 0-3 3v1.2A2.8 2.8 0 0 0 4 11a2.8 2.8 0 0 0 2 2.8V15a3 3 0 0 0 3 3h1v-6H8m7-8a3 3 0 0 1 3 3v1.2A2.8 2.8 0 0 1 20 11a2.8 2.8 0 0 1-2 2.8V15a3 3 0 0 1-3 3h-1v-6h2M12 2v20M8 9h8'),
    layers: pathIcon('M12 3l9 5-9 5-9-5 9-5zm-9 9l9 5 9-5M3 16l9 5 9-5'),
    activity: pathIcon('M3 12h4l2.5-6 5 12 2.5-6H21'),
    'message-circle': pathIcon('M20 11a8 8 0 1 1-3.4-6.5A8 8 0 0 1 20 11zm-8 8a8.8 8.8 0 0 1-4.4-1.2L3 19l1.2-4.6A8 8 0 1 1 12 19z'),
    'bar-chart-2': pathIcon('M4 19V9m8 10V5m8 14v-7M2 21h20'),
    'file-text': pathIcon('M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6zm0 0v6h6M8 13h8M8 17h8M8 9h3'),
    database: pathIcon('M12 4c-4.4 0-8 1.3-8 3s3.6 3 8 3 8-1.3 8-3-3.6-3-8-3zm-8 9c0 1.7 3.6 3 8 3s8-1.3 8-3m-16 5c0 1.7 3.6 3 8 3s8-1.3 8-3M4 7v11m16-11v11'),
    bell: pathIcon('M15 17h5l-1.4-1.4A2 2 0 0 1 18 14.2V11a6 6 0 1 0-12 0v3.2a2 2 0 0 1-.6 1.4L4 17h5m6 0a3 3 0 1 1-6 0h6z'),
    rss: pathIcon('M4 11a9 9 0 0 1 9 9M4 4a16 16 0 0 1 16 16M5 19a1 1 0 1 0 0 .1'),
    settings: pathIcon('M12 2l1.5 3.3 3.6.5-2.6 2.5.6 3.7L12 10.9 8.9 12l.6-3.7L6.9 5.8l3.6-.5L12 2zm0 7a3 3 0 1 0 0 6 3 3 0 0 0 0-6z'),
    logout: pathIcon('M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9'),
  };

  return icons[iconName] || icons.sparkles;
}

function pathIcon(path) {
  return `
    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" class="text-[var(--text-primary)]">
      <path d="${path}"></path>
    </svg>
  `;
}
