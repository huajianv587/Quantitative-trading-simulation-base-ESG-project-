/* ═══════════════════════════════════════════════════════════════
   Enhanced API Client with Caching
   集成缓存、重试、错误处理的增强API客户端
   ═══════════════════════════════════════════════════════════════ */

import { apiCache, queryCache } from './cache-manager.js';
import { enhancedFetch } from './api-enhanced.js';

/**
 * Cache configuration for different API endpoints
 */
const CACHE_CONFIG = {
  // 长期缓存 (30分钟)
  long: {
    ttl: 30 * 60 * 1000,
    endpoints: [
      '/api/v1/quant/universe/default',
      '/api/v1/quant/factors/registry',
      '/api/v1/connectors/registry',
      '/api/v1/quant/experiments'
    ]
  },

  // 中期缓存 (5分钟)
  medium: {
    ttl: 5 * 60 * 1000,
    endpoints: [
      '/api/v1/quant/platform/overview',
      '/api/v1/quant/dashboard/chart',
      '/api/market/ohlcv',
      '/api/v1/quant/backtests',
      '/api/v1/quant/rl/overview',
      '/api/v1/quant/rl/runs'
    ]
  },

  // 短期缓存 (1分钟)
  short: {
    ttl: 60 * 1000,
    endpoints: [
      '/api/v1/quant/execution/account',
      '/api/v1/quant/execution/positions',
      '/api/v1/quant/execution/monitor',
      '/api/v1/connectors/health',
      '/api/v1/connectors/quota'
    ]
  },

  // 不缓存
  noCache: {
    ttl: 0,
    endpoints: [
      '/api/auth/',
      '/api/session',
      '/api/agent/',
      '/api/v1/quant/execution/paper',
      '/api/v1/quant/execution/run',
      '/api/v1/quant/execution/kill-switch',
      '/api/v1/quant/execution/orders'
    ]
  }
};

/**
 * Get cache TTL for endpoint
 */
function getCacheTTL(path) {
  // 检查是否在不缓存列表中
  for (const pattern of CACHE_CONFIG.noCache.endpoints) {
    if (path.includes(pattern)) {
      return 0;
    }
  }

  // 检查短期缓存
  for (const pattern of CACHE_CONFIG.short.endpoints) {
    if (path.includes(pattern)) {
      return CACHE_CONFIG.short.ttl;
    }
  }

  // 检查中期缓存
  for (const pattern of CACHE_CONFIG.medium.endpoints) {
    if (path.includes(pattern)) {
      return CACHE_CONFIG.medium.ttl;
    }
  }

  // 检查长期缓存
  for (const pattern of CACHE_CONFIG.long.endpoints) {
    if (path.includes(pattern)) {
      return CACHE_CONFIG.long.ttl;
    }
  }

  // 默认中期缓存
  return CACHE_CONFIG.medium.ttl;
}

/**
 * Enhanced request with caching
 */
async function cachedRequest(method, path, body, opts = {}) {
  const BASE = window.__ESG_API_BASE_URL__ || '';
  const fullUrl = BASE + path;
  const ttl = opts.cacheTTL !== undefined ? opts.cacheTTL : getCacheTTL(path);

  // 生成缓存键
  const cacheKey = `${method}:${path}:${body ? JSON.stringify(body) : ''}`;

  // 对于GET请求且有缓存配置，尝试从缓存获取
  if (method === 'GET' && ttl > 0) {
    const cached = queryCache.getQuery(cacheKey);
    if (cached) {
      console.log(`[Cache HIT] ${path}`);
      return cached;
    }
  }

  console.log(`[Cache MISS] ${path}`);

  // 构建请求选项
  const headers = _mergeHeaders(opts.scope, opts.headers);
  const requestOptions = {
    method,
    headers,
    retry: opts.retry !== false,
    timeout: opts.timeout || 30000,
    showToast: opts.showToast !== false
  };

  if (body !== undefined) {
    requestOptions.body = JSON.stringify(body);
  }

  // 发起请求
  try {
    const response = await enhancedFetch(fullUrl, requestOptions);

    // 缓存成功的GET请求
    if (method === 'GET' && ttl > 0 && response) {
      queryCache.setQuery(cacheKey, response, ttl);
    }

    return response;
  } catch (error) {
    // 如果是网络错误且有缓存，返回过期缓存
    if (method === 'GET' && error.message.includes('Network')) {
      const staleCache = queryCache.getQuery(cacheKey);
      if (staleCache) {
        console.warn(`[Cache] Returning stale cache for ${path}`);
        return staleCache;
      }
    }
    throw error;
  }
}

/**
 * Helper functions
 */
function _apiKeyForScope(scope) {
  if (scope === 'admin') return window.__ESG_ADMIN_API_KEY__ || window.__ESG_API_KEY__ || '';
  if (scope === 'execution') return window.__ESG_EXECUTION_API_KEY__ || window.__ESG_API_KEY__ || '';
  if (scope === 'ops') return window.__ESG_OPS_API_KEY__ || window.__ESG_ADMIN_API_KEY__ || window.__ESG_API_KEY__ || '';
  return window.__ESG_API_KEY__ || '';
}

function _mergeHeaders(scope, extraHeaders) {
  const headers = { 'Content-Type': 'application/json' };
  const apiKey = _apiKeyForScope(scope);
  if (apiKey) headers['x-api-key'] = apiKey;
  if (extraHeaders) {
    Object.keys(extraHeaders).forEach(key => {
      headers[key] = extraHeaders[key];
    });
  }
  return headers;
}

// Request methods
function _get(path, opts) { return cachedRequest('GET', path, undefined, opts); }
function _post(path, body, opts) { return cachedRequest('POST', path, body, opts); }
function _put(path, body, opts) { return cachedRequest('PUT', path, body, opts); }
function _del(path, opts) { return cachedRequest('DELETE', path, undefined, opts); }

/**
 * Cache invalidation helpers
 */
export const cacheInvalidation = {
  // 清除所有缓存
  clearAll() {
    queryCache.cache.clear();
    console.log('[Cache] All cache cleared');
  },

  // 清除特定前缀的缓存
  clearByPrefix(prefix) {
    const count = queryCache.invalidateQueries(prefix);
    console.log(`[Cache] Cleared ${count} entries with prefix "${prefix}"`);
  },

  // 清除执行相关缓存
  clearExecution() {
    this.clearByPrefix('GET:/api/v1/quant/execution');
  },

  // 清除市场数据缓存
  clearMarket() {
    this.clearByPrefix('GET:/api/market');
  },

  // 清除回测缓存
  clearBacktests() {
    this.clearByPrefix('GET:/api/v1/quant/backtests');
  },

  // 清除连接器缓存
  clearConnectors() {
    this.clearByPrefix('GET:/api/v1/connectors');
  }
};

/**
 * Prefetch helper - 预加载常用数据
 */
export async function prefetchCommonData() {
  const prefetchList = [
    { fn: () => api.platform.overview(), name: 'Platform Overview' },
    { fn: () => api.platform.universe(), name: 'Universe' },
    { fn: () => api.connectors.registry(), name: 'Connectors Registry' }
  ];

  console.log('[Prefetch] Starting prefetch of common data...');

  const results = await Promise.allSettled(
    prefetchList.map(item => item.fn())
  );

  results.forEach((result, index) => {
    if (result.status === 'fulfilled') {
      console.log(`[Prefetch] ✓ ${prefetchList[index].name}`);
    } else {
      console.warn(`[Prefetch] ✗ ${prefetchList[index].name}:`, result.reason);
    }
  });
}

/**
 * Export enhanced API
 */
const Q = '/api/v1/quant';

export const api = {
  health: () => _get('/api/health'),

  // ── Auth ─────────────────────────────────────
  auth: {
    register: (payload) => _post('/api/auth/register', payload),
    login: (payload) => _post('/api/auth/login', payload),
    verify: (token) => _get('/api/auth/verify?token=' + encodeURIComponent(token)),
    resetRequest: (payload) => _post('/api/auth/reset-password/request', payload),
    resetConfirm: (payload) => _post('/api/auth/reset-password/confirm', payload),
  },

  // ── Market data ──────────────────────────────
  market: {
    ohlcv: (symbol, timeframe, limit) => {
      return _get('/api/market/ohlcv?symbol=' + encodeURIComponent(symbol || 'NVDA')
        + '&timeframe=' + encodeURIComponent(timeframe || '1D')
        + '&limit=' + encodeURIComponent(limit || 120));
    },
  },

  platform: {
    overview: () => _get(Q + '/platform/overview'),
    dashboardChart: (symbol, timeframe, provider) => {
      let query = '?timeframe=' + encodeURIComponent(timeframe || '1D');
      if (symbol) query += '&symbol=' + encodeURIComponent(symbol);
      if (provider) query += '&provider=' + encodeURIComponent(provider);
      return _get(Q + '/dashboard/chart' + query);
    },
    universe: () => _get(Q + '/universe/default'),
  },

  blueprint: {
    capabilities: () => _get(Q + '/capabilities'),
    analysisRun: (payload) => _post(Q + '/analysis/run', payload || {}),
    modelTrain: (payload) => _post(Q + '/models/train', payload || {}),
    modelPredict: (payload) => _post(Q + '/models/predict', payload || {}),
    dataPipelineRun: (payload) => _post(Q + '/data/pipeline/run', payload || {}),
    riskEvaluate: (payload) => _post(Q + '/risk/evaluate', payload || {}),
    advancedBacktestRun: (payload) => _post(Q + '/backtest/advanced/run', payload || {}),
    infrastructureCheck: (payload) => _post(Q + '/infrastructure/check', payload || {}),
    reportingBuild: (payload) => _post(Q + '/reporting/build', payload || {}),
  },

  agent: {
    newSession: (sessionId, userId) => {
      let query = '?session_id=' + encodeURIComponent(sessionId || '');
      if (userId) query += '&user_id=' + encodeURIComponent(userId);
      return _post('/session' + query, undefined);
    },
    history: (sessionId, limit) => {
      return _get('/history/' + encodeURIComponent(sessionId) + '?limit=' + encodeURIComponent(limit || 20));
    },
    analyze: (payload) => _post('/agent/analyze', payload),
    esgScore: (payload) => _post('/agent/esg-score', payload),
  },

  research: {
    context: (symbol, provider, limit) => {
      let query = '?provider=' + encodeURIComponent(provider || 'auto') + '&limit=' + encodeURIComponent(limit || 6);
      if (symbol) query += '&symbol=' + encodeURIComponent(symbol);
      return _get(Q + '/research/context' + query);
    },
    run: (payload) => _post(Q + '/research/run', payload),
  },

  portfolio: {
    optimize: (payload) => _post(Q + '/portfolio/optimize', payload)
  },

  p1: {
    status: () => _get(Q + '/p1/status'),
    run: (payload) => _post(Q + '/p1/stack/run', payload),
  },

  p2: {
    status: () => _get(Q + '/p2/status'),
    run: (payload) => _post(Q + '/p2/decision/run', payload),
  },

  backtests: {
    list: () => _get(Q + '/backtests'),
    get: (id) => _get(Q + '/backtests/' + id),
    run: (payload) => _post(Q + '/backtests/run', payload),
  },

  execution: {
    paper: (payload) => _post(Q + '/execution/paper', payload, { scope: 'execution' }),
    run: (payload) => _post(Q + '/execution/run', payload, { scope: 'execution' }),
    brokers: () => _get(Q + '/execution/brokers', { scope: 'execution' }),
    account: (broker, mode) => {
      return _get(
        Q + '/execution/account?broker=' + encodeURIComponent(broker || 'alpaca') + '&mode=' + encodeURIComponent(mode || 'paper'),
        { scope: 'execution' }
      );
    },
    controls: () => _get(Q + '/execution/controls', { scope: 'execution' }),
    killSwitch: (enabled, reason) => {
      return _post(
        Q + '/execution/kill-switch',
        { enabled: !!enabled, reason: reason || '' },
        { scope: 'execution' }
      );
    },
    monitor: (broker, executionId, limit, mode) => {
      let query = '?broker=' + encodeURIComponent(broker || 'alpaca')
        + '&limit=' + encodeURIComponent(limit || 20)
        + '&mode=' + encodeURIComponent(mode || 'paper');
      if (executionId) query += '&execution_id=' + encodeURIComponent(executionId);
      return _get(Q + '/execution/monitor' + query, { scope: 'execution' });
    },
    orders: (broker, status, limit, mode) => {
      return _get(
        Q + '/execution/orders?broker=' + encodeURIComponent(broker || 'alpaca')
          + '&status=' + encodeURIComponent(status || 'all')
          + '&limit=' + encodeURIComponent(limit || 50)
          + '&mode=' + encodeURIComponent(mode || 'paper'),
        { scope: 'execution' }
      );
    },
    cancel: (orderId, payload) => {
      return _post(Q + '/execution/orders/' + orderId + '/cancel', payload, { scope: 'execution' });
    },
    retry: (orderId, payload) => {
      return _post(Q + '/execution/orders/' + orderId + '/retry', payload, { scope: 'execution' });
    },
    journal: (executionId) => {
      return _get(Q + '/execution/journal/' + executionId, { scope: 'execution' });
    },
    syncJournal: (executionId, broker) => {
      return _post(Q + '/execution/journal/' + executionId + '/sync', { broker: broker }, { scope: 'execution' });
    },
    positions: (broker, mode) => {
      return _get(
        Q + '/execution/positions?broker=' + encodeURIComponent(broker || 'alpaca') + '&mode=' + encodeURIComponent(mode || 'paper'),
        { scope: 'execution' }
      );
    },
  },

  validation: {
    run: (payload) => _post(Q + '/validation/run', payload, { scope: 'execution' }),
  },

  quantRL: {
    overview: () => _get(Q + '/rl/overview'),
    runs: () => _get(Q + '/rl/runs'),
    buildDataset: (payload) => _post(Q + '/rl/datasets/build', payload),
    buildRecipeDataset: (payload) => _post(Q + '/rl/recipes/build', payload),
    search: (payload) => _post(Q + '/rl/search', payload),
    buildDemoDataset: (payload) => _post(Q + '/rl/datasets/demo', payload),
    train: (payload) => _post(Q + '/rl/train', payload),
    backtest: (payload) => _post(Q + '/rl/backtest', payload),
  },

  experiments: {
    list: () => _get(Q + '/experiments'),
  },

  intelligence: {
    scan: (payload) => _post(Q + '/intelligence/scan', payload || {}),
    evidence: (symbol, limit) => {
      let query = '?limit=' + encodeURIComponent(limit || 20);
      if (symbol) query += '&symbol=' + encodeURIComponent(symbol);
      return _get(Q + '/intelligence/evidence' + query);
    },
  },

  factors: {
    discover: (payload) => _post(Q + '/factors/discover', payload || {}),
    registry: (limit) => _get(Q + '/factors/registry?limit=' + encodeURIComponent(limit || 50)),
  },

  factorLab: {
    discover: (payload) => _post(Q + '/factors/discover', payload || {}),
    registry: (limit) => _get(Q + '/factors/registry?limit=' + encodeURIComponent(limit || 50)),
  },

  decision: {
    explain: (payload) => _post(Q + '/decision/explain', payload || {}),
    auditTrail: (symbol, limit) => {
      let query = '?limit=' + encodeURIComponent(limit || 20);
      if (symbol) query += '&symbol=' + encodeURIComponent(symbol);
      return _get(Q + '/decision/audit-trail' + query);
    },
  },

  simulate: {
    scenario: (payload) => _post(Q + '/simulate/scenario', payload || {}),
  },

  simulation: {
    run: (payload) => _post(Q + '/simulate/scenario', payload || {}),
  },

  outcomes: {
    evaluate: (payload) => _post(Q + '/outcomes/evaluate', payload || {}),
  },

  connectors: {
    registry: () => _get('/api/v1/connectors/registry'),
    health: (providers, live) => {
      let query = '?live=' + encodeURIComponent(live ? 'true' : 'false');
      if (providers && providers.length) query += '&providers=' + encodeURIComponent(providers.join(','));
      return _get('/api/v1/connectors/health' + query);
    },
    quota: (providers) => {
      let query = '';
      if (providers && providers.length) query = '?providers=' + encodeURIComponent(providers.join(','));
      return _get('/api/v1/connectors/quota' + query);
    },
    test: (payload) => _post('/api/v1/connectors/test', payload || {}),
    liveScan: (payload) => _post('/api/v1/connectors/live-scan', payload || {}),
    runs: (limit) => _get('/api/v1/connectors/runs?limit=' + encodeURIComponent(limit || 20)),
  },
};

// 在页面加载时预取常用数据
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    setTimeout(prefetchCommonData, 1000);
  });
} else {
  setTimeout(prefetchCommonData, 1000);
}
