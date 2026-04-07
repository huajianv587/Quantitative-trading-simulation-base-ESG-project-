/**
 * ESG Copilot - 应用入口
 * 初始化路由、全局配置、事件监听
 */

import { router } from './router.js';
import { store } from './store.js';
import { api } from './api.js';
import { renderNav, initNavListener, updateHealthStatus } from './components/nav.js';
import { toastError, toastInfo, initErrorListener } from './components/toast.js';
import { newSessionId } from './utils.js';

// ============================================
// 全局配置
// ============================================

// Chart.js 全局配置（暗色主题）
if (window.Chart) {
  Chart.defaults.color = '#B0BFD3';
  Chart.defaults.borderColor = '#2A3952';
  Chart.defaults.font.family = '"Plus Jakarta Sans", system-ui, sans-serif';
  Chart.defaults.font.size = 13;

  // 颜色方案
  Chart.defaults.plugins.legend.labels.color = '#F3F7FB';
  Chart.defaults.plugins.tooltip.backgroundColor = 'rgba(17, 24, 39, 0.9)';
  Chart.defaults.plugins.tooltip.borderColor = '#2A3952';
  Chart.defaults.plugins.tooltip.titleColor = '#F3F7FB';
  Chart.defaults.plugins.tooltip.bodyColor = '#B0BFD3';
}

// ============================================
// 初始化函数
// ============================================

async function init() {
  console.log('🚀 ESG Copilot 启动...');

  // 初始化导航
  renderNav();
  initNavListener();

  // 初始化路由器
  const appRoot = document.getElementById('app-root');
  router.init(appRoot);

  // 初始化错误监听
  initErrorListener();

  // 检查后端健康状态
  await checkHealth();

  // 初始化会话
  await initSession();

  // 全局事件监听
  setupGlobalListeners();
  setupMotionSystem();
  enhanceInteractiveSurfaces();

  console.log('✓ 应用已就绪');
}

/**
 * 检查后端健康状态
 */
async function checkHealth() {
  try {
    const result = await api.system.health();
    console.log('✓ 后端连接正常', result);
    updateHealthStatus(true);
  } catch (error) {
    console.warn('⚠ 后端连接失败', error);
    updateHealthStatus(false);
    // 不阻止应用启动，但给出警告
    toastError('无法连接到后端服务', '连接失败');
  }
}

/**
 * 初始化用户会话
 */
async function initSession() {
  let sessionId = localStorage.getItem('esg_session_id');

  if (!sessionId) {
    sessionId = newSessionId();
    localStorage.setItem('esg_session_id', sessionId);
    console.log('📝 创建新会话:', sessionId);
  }

  store.set('currentSession', {
    id: sessionId,
    createdAt: new Date().toISOString(),
  });

  // 先在后端注册会话，避免聊天记录写入时触发外键错误。
  try {
    await api.session.create(sessionId);
  } catch (error) {
    console.warn('无法在后端创建会话，继续使用本地会话', error);
  }

  // 尝试加载历史记录
  await loadSessionHistory(sessionId);
}

/**
 * 加载会话历史
 * @param {string} sessionId
 */
async function loadSessionHistory(sessionId) {
  try {
    const history = await api.session.getHistory(sessionId);
    const messages = history?.messages || [];
    if (messages.length > 0) {
      store.set('chatMessages', messages);
      console.log('📚 加载会话历史:', messages.length, '条消息');
    }
  } catch (error) {
    console.warn('无法加载会话历史', error);
    // 不影响应用启动
  }
}

/**
 * 设置全局事件监听
 */
function setupGlobalListeners() {
  // 监听页面关闭，保存当前状态
  window.addEventListener('beforeunload', () => {
    // 可以在这里保存需要持久化的数据
  });

  // 监听在线/离线状态
  window.addEventListener('online', () => {
    updateHealthStatus(true);
    toastInfo('网络已连接');
  });

  window.addEventListener('offline', () => {
    updateHealthStatus(false);
    toastError('网络已断开连接', '网络错误');
  });

  // 快捷键支持
  setupKeyboardShortcuts();

  window.addEventListener('route-change', () => {
    enhanceInteractiveSurfaces();
  });
}

/**
 * 键盘快捷键
 */
function setupKeyboardShortcuts() {
  document.addEventListener('keydown', (e) => {
    // Ctrl/Cmd + K: 打开快速搜索 (预留)
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
      e.preventDefault();
      console.log('快速搜索 (未实现)');
    }

    // Ctrl/Cmd + 1-6: 快速导航
    const navMap = {
      '1': '/overview',
      '2': '/chat',
      '3': '/score',
      '4': '/reports',
      '5': '/data',
      '6': '/push-rules',
      '7': '/subscriptions',
    };

    if ((e.ctrlKey || e.metaKey) && e.key in navMap) {
      e.preventDefault();
      window.location.hash = `#${navMap[e.key]}`;
    }
  });
}

function setupMotionSystem() {
  const cursorAura = document.getElementById('cursor-aura');
  const transitionEl = document.getElementById('route-transition');
  const transitionTitle = document.getElementById('route-transition-title');

  if (cursorAura) {
    window.addEventListener('pointermove', (event) => {
      const { clientX, clientY } = event;
      document.documentElement.style.setProperty('--cursor-x', `${clientX}px`);
      document.documentElement.style.setProperty('--cursor-y', `${clientY}px`);
      cursorAura.classList.add('is-visible');
    }, { passive: true });

    window.addEventListener('pointerleave', () => {
      cursorAura.classList.remove('is-visible');
    });
  }

  window.addEventListener('route-will-change', (event) => {
    if (!transitionEl) return;
    if (transitionTitle) {
      transitionTitle.textContent = event.detail?.label || 'ESG Copilot';
    }

    transitionEl.classList.remove('is-active');
    void transitionEl.offsetWidth;
    transitionEl.classList.add('is-active');
  });

  window.addEventListener('route-change', () => {
    if (!transitionEl) return;
    setTimeout(() => {
      transitionEl.classList.remove('is-active');
    }, 520);
  });
}

function enhanceInteractiveSurfaces() {
  const targets = document.querySelectorAll(
    '[data-hover-glow], .card, .page-hero, .score-card, .app-topbar'
  );

  targets.forEach((element) => {
    if (element.dataset.motionBound === 'true') return;
    element.dataset.motionBound = 'true';

    element.addEventListener('pointermove', (event) => {
      const rect = element.getBoundingClientRect();
      const x = event.clientX - rect.left;
      const y = event.clientY - rect.top;

      element.style.setProperty('--mx', `${x}px`);
      element.style.setProperty('--my', `${y}px`);
    });

    element.addEventListener('pointerleave', () => {
      element.style.removeProperty('--mx');
      element.style.removeProperty('--my');
    });
  });
}

// ============================================
// 错误处理
// ============================================

window.addEventListener('error', (event) => {
  console.error('❌ 应用错误:', event.error);
  toastError(event.error?.message || '发生未知错误', '应用错误');
});

window.addEventListener('unhandledrejection', (event) => {
  console.error('❌ 未处理的 Promise:', event.reason);
  toastError(event.reason?.message || '发生未知错误', '异步错误');
});

// ============================================
// 启动应用
// ============================================

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}

// ============================================
// 导出全局对象 (便于调试)
// ============================================

window.__ESG_DEBUG__ = {
  store,
  api,
  router,
  // 快速导航函数
  nav: (path) => {
    window.location.hash = `#${path}`;
  },
  // 查看当前状态
  state: () => store.getState(),
};

console.log('💡 提示: 在浏览器控制台使用 window.__ESG_DEBUG__ 进行调试');
