/**
 * ESG Copilot - Hash 路由器
 * 单页应用路由管理 (#/chat, #/score, ...)
 */

const ASSET_VERSION = window.__APP_ASSET_VERSION__ || '20260404-frontend-v7';
const FLAGSHIP_LANDING_KEY = 'esg-flagship-landing-seen';
const FLAGSHIP_LANDING_VERSION = '20260330-v5';

/**
 * 路由配置表
 * 每个路由包含：模块导入函数、标签、图标等元数据
 */
const ROUTES = {
  '/overview': {
    module: () => import(`./pages/overview.js?v=${ASSET_VERSION}`),
    label: '旗舰总览',
    icon: 'sparkles',
    description: '沉浸式查看最新 ESG 情报与全部能力入口',
  },
  '/chat': {
    module: () => import(`./pages/chat.js?v=${ASSET_VERSION}`),
    label: 'ESG 对话',
    icon: 'message-circle',
    description: '与 AI 对话，分析企业 ESG 表现',
  },
  '/score': {
    module: () => import(`./pages/score-dashboard.js?v=${ASSET_VERSION}`),
    label: 'ESG 评分',
    icon: 'bar-chart-2',
    description: '详细评分仪表盘和可视化',
  },
  '/reports': {
    module: () => import(`./pages/reports.js?v=${ASSET_VERSION}`),
    label: '报告中心',
    icon: 'file-text',
    description: '查看和管理 ESG 报告',
  },
  '/data': {
    module: () => import(`./pages/data-management.js?v=${ASSET_VERSION}`),
    label: '数据同步',
    icon: 'database',
    description: '管理数据源和同步',
  },
  '/push-rules': {
    module: () => import(`./pages/push-rules.js?v=${ASSET_VERSION}`),
    label: '推送规则',
    icon: 'bell',
    description: '配置推送通知规则',
  },
  '/subscriptions': {
    module: () => import(`./pages/subscriptions.js?v=${ASSET_VERSION}`),
    label: '订阅管理',
    icon: 'rss',
    description: '管理报告订阅',
  },
};

const DEFAULT_ROUTE = '/overview';

class Router {
  constructor() {
    this.routes = ROUTES;
    this.currentRoute = null;
    this.currentPageModule = null;
    this.container = null;
  }

  /**
   * 初始化路由器
   * @param {HTMLElement} container - 用于挂载页面的 DOM 容器
   */
  init(container) {
    this.container = container;

    // 监听哈希变化
    window.addEventListener('hashchange', () => this.navigate());

    if (this.shouldShowFlagshipLanding()) {
      sessionStorage.setItem(FLAGSHIP_LANDING_KEY, FLAGSHIP_LANDING_VERSION);
      window.location.hash = `#${DEFAULT_ROUTE}`;
      return;
    }

    // 初始导航
    this.navigate();
  }

  shouldShowFlagshipLanding() {
    const currentHash = window.location.hash.substring(1);

    if (!currentHash || currentHash === DEFAULT_ROUTE) {
      return false;
    }

    return sessionStorage.getItem(FLAGSHIP_LANDING_KEY) !== FLAGSHIP_LANDING_VERSION;
  }

  /**
   * 获取当前路由 (去掉 #)
   * @returns {string}
   */
  getCurrentPath() {
    const hash = window.location.hash.substring(1);
    return hash || DEFAULT_ROUTE;
  }

  /**
   * 导航到指定路由
   * @param {string} path - 路由路径 (e.g., '/chat', '/score')
   */
  async navigate(path = null) {
    if (path && path !== this.getCurrentPath()) {
      window.location.hash = `#${path}`;
      return; // hashchange 事件会再次触发 navigate()
    }

    const route = this.getCurrentPath();
    const routeConfig = this.routes[route];

    if (!routeConfig) {
      console.warn(`未找到路由: ${route}，重定向到默认页面`);
      window.location.hash = `#${DEFAULT_ROUTE}`;
      return;
    }

    // 清理旧页面
    if (this.currentPageModule && this.currentPageModule.destroy) {
      await this.currentPageModule.destroy();
    }

    this.currentRoute = route;

    try {
      window.dispatchEvent(new CustomEvent('route-will-change', {
        detail: { path: route, ...routeConfig }
      }));

      // 动态导入页面模块
      this.currentPageModule = await routeConfig.module();

      // 清空容器
      this.container.innerHTML = '';
      this.container.classList.remove('page-ready');
      this.container.classList.add('page-enter');

      // 渲染新页面
      if (this.currentPageModule.render) {
        await this.currentPageModule.render(this.container);
      }

      requestAnimationFrame(() => {
        this.container.classList.remove('page-enter');
        this.container.classList.add('page-ready');
      });

      // 更新页面标题和头部
      this.updateHeader(routeConfig);

      // 触发路由变化事件
      window.dispatchEvent(new CustomEvent('route-change', {
        detail: { path: route, ...routeConfig }
      }));

    } catch (error) {
      console.error('页面加载失败:', error);
      this.container.innerHTML = `
        <div class="text-center py-12">
          <p class="text-red-500 font-semibold">页面加载失败</p>
          <p class="text-gray-400 text-sm mt-2">${error.message}</p>
        </div>
      `;
    }
  }

  /**
   * 更新顶部栏和标题
   * @param {Object} routeConfig
   */
  updateHeader(routeConfig) {
    const titleEl = document.getElementById('page-title');
    if (titleEl) {
      titleEl.textContent = routeConfig.label;
    }
  }

  /**
   * 获取路由配置
   * @returns {Object} - 路由映射表
   */
  getRoutes() {
    return this.routes;
  }

  /**
   * 检查路由是否存在
   * @param {string} path
   * @returns {boolean}
   */
  hasRoute(path) {
    return path in this.routes;
  }
}

// 全局单例路由器
export const router = new Router();

export default router;
