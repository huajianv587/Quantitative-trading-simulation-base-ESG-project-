/**
 * ESG Copilot - API 客户端
 * 封装所有 HTTP 请求到后端
 */

// 默认走同源；静态部署到 Vercel / Cloudflare Pages 时，可通过 frontend/app-config.js
// 或部署环境生成的 app-config.js 覆盖 API 域名，例如 https://api.example.com
const BASE_URL = resolveBaseUrl();

function resolveBaseUrl() {
  const configuredBaseUrl = window.__ESG_API_BASE_URL__ || '';
  return normalizeBaseUrl(configuredBaseUrl);
}

function normalizeBaseUrl(value) {
  if (!value) return '';
  return String(value).trim().replace(/\/+$/, '');
}

/**
 * 通用 HTTP 请求封装
 * @param {string} method - GET, POST, PUT, DELETE
 * @param {string} path - API 路径 (无基础 URL)
 * @param {any} body - 请求体 (仅用于 POST/PUT)
 * @returns {Promise<any>}
 */
async function request(method, path, body = null, options = {}) {
  const { quiet = false } = options;
  const url = `${BASE_URL}${path}`;
  const fetchOptions = {
    method,
    headers: {
      'Content-Type': 'application/json',
    },
  };

  if (body) {
    fetchOptions.body = JSON.stringify(body);
  }

  try {
    const response = await fetch(url, fetchOptions);

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({
        error: { message: `HTTP ${response.status}` }
      }));
      const error = new Error(
        errorData?.detail ||
        errorData?.error?.message ||
        errorData?.message ||
        `HTTP ${response.status}`
      );
      error.status = response.status;
      error.data = errorData;
      throw error;
    }

    // 204 No Content
    if (response.status === 204) {
      return null;
    }

    return await response.json();

  } catch (error) {
    // 触发全局错误事件，让 app.js 监听
    if (!quiet) {
      const event = new CustomEvent('api:error', {
        detail: {
          message: error.message,
          path,
          status: error.status,
        }
      });
      window.dispatchEvent(event);
    }
    throw error;
  }
}

/**
 * 上传文件
 * @param {string} path
 * @param {FormData} formData
 * @returns {Promise<any>}
 */
async function uploadFile(path, formData) {
  const url = `${BASE_URL}${path}`;
  try {
    const response = await fetch(url, {
      method: 'POST',
      body: formData,
      // 不设置 Content-Type，让浏览器自动设置 multipart/form-data
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    return await response.json();
  } catch (error) {
    const event = new CustomEvent('api:error', {
      detail: { message: error.message, path }
    });
    window.dispatchEvent(event);
    throw error;
  }
}

/**
 * 下载文件（打开新标签页）
 * @param {string} path
 * @param {string} filename
 */
async function downloadFile(path, filename) {
  const url = `${BASE_URL}${path}`;
  const link = document.createElement('a');
  link.href = url;
  link.download = filename || 'download';
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

// ============================================
// Agent API
// ============================================

export const agent = {
  /**
   * 分析 ESG - 自由形式问题
   * 注意: 使用查询参数，不是请求体
   */
  analyze: (question, sessionId = '') => {
    const params = new URLSearchParams({ question });
    if (sessionId) params.append('session_id', sessionId);
    return request('POST', `/agent/analyze?${params}`);
  },

  /**
   * 生成完整 ESG 评分报告和可视化数据
   */
  getESGScore: (payload) => {
    return request('POST', '/agent/esg-score', payload);
  },
};

// ============================================
// Session & History
// ============================================

export const session = {
  /**
   * 创建新会话
   */
  create: (sessionId) => {
    return request('POST', `/session?session_id=${encodeURIComponent(sessionId)}`);
  },

  /**
   * 获取会话对话历史
   */
  getHistory: (sessionId) => {
    return request('GET', `/history/${encodeURIComponent(sessionId)}`);
  },

  /**
   * 发送查询 (RAG 模式)
   */
  query: (payload) => {
    return request('POST', '/query', payload);
  },
};

// ============================================
// Reports API
// ============================================

export const reports = {
  /**
   * 生成新报告 (异步)
   */
  generate: (payload) => {
    return request('POST', '/admin/reports/generate', payload);
  },

  /**
   * 获取单个报告
   */
  getById: (reportId) => {
    return request('GET', `/admin/reports/${reportId}`);
  },

  /**
   * 获取最新报告
   */
  getLatest: (reportType) => {
    return request('GET', `/admin/reports/latest?report_type=${reportType}`, null, { quiet: true });
  },

  /**
   * 导出报告
   */
  export: (reportId, format = 'pdf') => {
    const filename = `report_${reportId}.${format === 'pdf' ? 'pdf' : format === 'xlsx' ? 'xlsx' : 'json'}`;
    downloadFile(`/admin/reports/export/${reportId}?format=${format}`, filename);
  },

  /**
   * 获取报告统计
   */
  getStatistics: (period = null, groupBy = 'report_type') => {
    let path = '/admin/reports/statistics?group_by=' + groupBy;
    if (period) path += '&period=' + period;
    return request('GET', path);
  },
};

// ============================================
// Data Sources API
// ============================================

export const dataSources = {
  /**
   * 触发数据同步
   */
  sync: (payload) => {
    return request('POST', '/admin/data-sources/sync', payload);
  },

  /**
   * 获取同步任务状态
   */
  getSyncStatus: (jobId) => {
    return request('GET', `/admin/data-sources/sync/${jobId}`);
  },
};

// ============================================
// Push Rules API
// ============================================

export const pushRules = {
  /**
   * 获取所有推送规则
   */
  getAll: () => {
    return request('GET', '/admin/push-rules', null, { quiet: true });
  },

  /**
   * 创建推送规则
   */
  create: (payload) => {
    return request('POST', '/admin/push-rules', payload);
  },

  /**
   * 更新推送规则
   */
  update: (ruleId, payload) => {
    return request('PUT', `/admin/push-rules/${ruleId}`, payload);
  },

  /**
   * 删除推送规则
   */
  delete: (ruleId) => {
    return request('DELETE', `/admin/push-rules/${ruleId}`);
  },

  /**
   * 测试推送规则
   */
  test: (ruleId, payload) => {
    return request('POST', `/admin/push-rules/${ruleId}/test`, payload);
  },
};

// ============================================
// Subscriptions API
// ============================================

export const subscriptions = {
  /**
   * 获取用户订阅
   */
  getAll: () => {
    return request('GET', '/user/reports/subscriptions');
  },

  /**
   * 创建订阅
   */
  create: (payload) => {
    return request('POST', '/user/reports/subscribe', payload);
  },

  /**
   * 更新订阅
   */
  update: (subscriptionId, payload) => {
    return request('PUT', `/user/reports/subscriptions/${subscriptionId}`, payload);
  },

  /**
   * 删除订阅
   */
  delete: (subscriptionId) => {
    return request('DELETE', `/user/reports/subscriptions/${subscriptionId}`);
  },
};

// ============================================
// System API
// ============================================

export const system = {
  /**
   * 健康检查
   */
  health: () => {
    return request('GET', '/health');
  },

  /**
   * 获取调度器统计
   */
  schedulerStats: (days = 7) => {
    return request('GET', `/scheduler/statistics?days=${days}`, null, { quiet: true });
  },

  /**
   * 扫描状态
   */
  getScanStatus: () => {
    return request('GET', '/scheduler/scan/status');
  },

  /**
   * 触发扫描
   */
  triggerScan: () => {
    return request('POST', '/scheduler/scan');
  },
};

// ============================================
// Dashboard API
// ============================================

export const dashboard = {
  /**
   * 获取旗舰首页总览数据
   */
  overview: () => {
    return request('GET', '/dashboard/overview', null, { quiet: true });
  },
};

// ============================================
// 导出 API 对象
// ============================================

export const api = {
  agent,
  session,
  reports,
  dataSources,
  pushRules,
  subscriptions,
  system,
  dashboard,
};

export default api;
