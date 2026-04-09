const ASSET_VERSION = window.__APP_ASSET_VERSION__ || '20260409-frontend-v8';

const ROUTES = {
  '/overview': {
    module: () => import(`./pages/overview.js?v=${ASSET_VERSION}`),
    label: 'Platform Overview',
    icon: 'sparkles',
    description: 'Command center for architecture, runtime, signals, and delivery status.',
  },
  '/research': {
    module: () => import(`./pages/research-lab.js?v=${ASSET_VERSION}`),
    label: 'Research Lab',
    icon: 'brain',
    description: 'Run ESG quant research and generate ranked investment signals.',
  },
  '/portfolio': {
    module: () => import(`./pages/portfolio-lab.js?v=${ASSET_VERSION}`),
    label: 'Execution Lab',
    icon: 'layers',
    description: 'Optimize portfolios and route paper trading orders to Alpaca.',
  },
  '/backtests': {
    module: () => import(`./pages/backtests.js?v=${ASSET_VERSION}`),
    label: 'Backtests',
    icon: 'activity',
    description: 'Validate strategies, inspect drawdowns, and monitor risk controls.',
  },
  '/chat': {
    module: () => import(`./pages/chat.js?v=${ASSET_VERSION}`),
    label: 'ESG Copilot',
    icon: 'message-circle',
    description: 'Ask the agent for grounded ESG research and company analysis.',
  },
  '/score': {
    module: () => import(`./pages/score-dashboard.js?v=${ASSET_VERSION}`),
    label: 'Score Lab',
    icon: 'bar-chart-2',
    description: 'Generate structured ESG scorecards and visual diagnostics.',
  },
  '/reports': {
    module: () => import(`./pages/reports.js?v=${ASSET_VERSION}`),
    label: 'Report Center',
    icon: 'file-text',
    description: 'Generate, inspect, and export periodic ESG reports.',
  },
  '/data': {
    module: () => import(`./pages/data-management.js?v=${ASSET_VERSION}`),
    label: 'Data Hub',
    icon: 'database',
    description: 'Manage ingestion jobs, sync tasks, and runtime data pipelines.',
  },
  '/push-rules': {
    module: () => import(`./pages/push-rules.js?v=${ASSET_VERSION}`),
    label: 'Automation',
    icon: 'bell',
    description: 'Configure push rules, alert logic, and notification orchestration.',
  },
  '/subscriptions': {
    module: () => import(`./pages/subscriptions.js?v=${ASSET_VERSION}`),
    label: 'Watchlists',
    icon: 'rss',
    description: 'Manage report subscriptions, watchlists, and follow-up coverage.',
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

  init(container) {
    this.container = container;
    window.addEventListener('hashchange', () => this.navigate());
    this.navigate();
  }

  getCurrentPath() {
    const hash = window.location.hash.substring(1);
    return hash || DEFAULT_ROUTE;
  }

  async navigate(path = null) {
    if (path && path !== this.getCurrentPath()) {
      window.location.hash = `#${path}`;
      return;
    }

    const route = this.getCurrentPath();
    const routeConfig = this.routes[route];

    if (!routeConfig) {
      console.warn(`Unknown route: ${route}. Redirecting to ${DEFAULT_ROUTE}.`);
      window.location.hash = `#${DEFAULT_ROUTE}`;
      return;
    }

    if (this.currentPageModule?.destroy) {
      await this.currentPageModule.destroy();
    }

    this.currentRoute = route;

    try {
      window.dispatchEvent(new CustomEvent('route-will-change', {
        detail: { path: route, ...routeConfig },
      }));

      this.currentPageModule = await routeConfig.module();
      this.container.innerHTML = '';
      this.container.classList.remove('page-ready');
      this.container.classList.add('page-enter');

      if (this.currentPageModule?.render) {
        await this.currentPageModule.render(this.container);
      }

      requestAnimationFrame(() => {
        this.container.classList.remove('page-enter');
        this.container.classList.add('page-ready');
      });

      this.updateHeader(routeConfig);

      window.dispatchEvent(new CustomEvent('route-change', {
        detail: { path: route, ...routeConfig },
      }));
    } catch (error) {
      console.error('Page load failed:', error);
      this.container.innerHTML = `
        <div class="text-center py-12">
          <p class="text-red-500 font-semibold">Page Load Failed</p>
          <p class="text-gray-400 text-sm mt-2">${error.message}</p>
        </div>
      `;
    }
  }

  updateHeader(routeConfig) {
    const titleEl = document.getElementById('page-title');
    if (titleEl) titleEl.textContent = routeConfig.label;
  }

  getRoutes() {
    return this.routes;
  }

  hasRoute(path) {
    return path in this.routes;
  }
}

export const router = new Router();
export default router;
