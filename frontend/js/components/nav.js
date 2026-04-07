/**
 * 导航侧边栏组件
 */

import { router } from '../router.js';

/**
 * 渲染导航菜单
 */
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
    link.className = `
      nav-link
      block shrink-0 whitespace-nowrap px-4 py-3 sm:px-5 sm:py-4 rounded-2xl text-base sm:text-[17px] font-semibold
      transition-all duration-200 border
      ${isActive
        ? 'bg-[rgba(94,165,255,0.12)] text-[#8ec5ff] border-[rgba(94,165,255,0.3)] shadow-[0_10px_24px_rgba(0,0,0,0.12)]'
        : 'text-[var(--text-secondary)] border-transparent hover:text-[var(--text-primary)] hover:bg-[#182335]'
      }
    `;
    link.title = config.description;
    link.innerHTML = `
      <div class="flex items-center gap-3.5">
        <span class="text-xl">
          ${getIconEmoji(config.icon)}
        </span>
        <span>${config.label}</span>
      </div>
    `;

    navLinks.appendChild(link);
  });
}

/**
 * 更新健康状态指示器
 * @param {boolean} isOnline
 */
export function updateHealthStatus(isOnline) {
  const indicator = document.getElementById('health-indicator');
  if (!indicator) return;

  const dotColor = isOnline ? '#10B981' : '#6B7280';
  const statusText = isOnline ? '后端已连接' : '等待后端响应';

  indicator.innerHTML = `
    <span class="inline-block w-2 h-2 rounded-full" style="background-color: ${dotColor};"></span>
    <span>${statusText}</span>
  `;
}

/**
 * 获取图标对应的 Emoji
 * @param {string} iconName
 * @returns {string}
 */
function getIconEmoji(iconName) {
  const icons = {
    'sparkles': '✦',
    'message-circle': '💬',
    'bar-chart-2': '📊',
    'file-text': '📄',
    'database': '💾',
    'bell': '🔔',
    'rss': '📮',
    'settings': '⚙️',
    'logout': '🚪',
  };

  return icons[iconName] || '📌';
}

/**
 * 监听路由变化，自动更新导航状态
 */
export function initNavListener() {
  window.addEventListener('route-change', () => {
    renderNav();
  });
}
