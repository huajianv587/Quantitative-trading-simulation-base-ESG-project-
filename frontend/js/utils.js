/**
 * ESG Copilot - 工具函数库
 */

// ============================================
// ESG 颜色常量
// ============================================

export const ESG_COLORS = {
  E: '#10B981',     // 环境 - 翡翠绿
  S: '#3B82F6',     // 社会 - 电光蓝
  G: '#F59E0B',     // 治理 - 琥珀橙
};

export const ESG_DIM_COLORS = {
  E: '#064E3B',     // 环境背景淡色
  S: '#1E3A5F',     // 社会背景淡色
  G: '#451A03',     // 治理背景淡色
};

export const SCORE_RANGES = {
  EXCELLENT: { min: 80, max: 100, color: '#10B981', label: 'Excellent' },
  GOOD: { min: 60, max: 79, color: '#84CC16', label: 'Good' },
  AVERAGE: { min: 40, max: 59, color: '#F59E0B', label: 'Average' },
  POOR: { min: 0, max: 39, color: '#EF4444', label: 'Poor' },
};

// ============================================
// 分数相关函数
// ============================================

/**
 * 根据分数返回对应的颜色值
 * @param {number} score - 分数 0-100
 * @returns {string} - CSS 颜色值
 */
export function scoreColor(score) {
  if (score >= 80) return SCORE_RANGES.EXCELLENT.color;
  if (score >= 60) return SCORE_RANGES.GOOD.color;
  if (score >= 40) return SCORE_RANGES.AVERAGE.color;
  return SCORE_RANGES.POOR.color;
}

/**
 * 根据分数返回评级标签
 * @param {number} score - 分数 0-100
 * @returns {string} - 评级标签
 */
export function scoreLabel(score) {
  if (score >= 80) return SCORE_RANGES.EXCELLENT.label;
  if (score >= 60) return SCORE_RANGES.GOOD.label;
  if (score >= 40) return SCORE_RANGES.AVERAGE.label;
  return SCORE_RANGES.POOR.label;
}

/**
 * 根据分数返回评级 CSS 类名
 * @param {number} score
 * @returns {string}
 */
export function scoreClassName(score) {
  if (score >= 80) return 'excellent';
  if (score >= 60) return 'good';
  if (score >= 40) return 'average';
  return 'poor';
}

/**
 * 格式化分数为百分比字符串
 * @param {number} score
 * @param {number} decimals - 小数位
 * @returns {string}
 */
export function formatScore(score, decimals = 1) {
  return score.toFixed(decimals);
}

// ============================================
// 趋势指示
// ============================================

export const TREND_ICONS = {
  up: '📈',
  down: '📉',
  stable: '➡️',
};

/**
 * 根据趋势返回符号
 * @param {string} trend - 'up' | 'down' | 'stable'
 * @returns {string}
 */
export function trendIcon(trend) {
  return TREND_ICONS[trend] ?? '➖';
}

/**
 * 根据趋势返回 CSS 类名
 * @param {string} trend
 * @returns {string}
 */
export function trendClass(trend) {
  if (trend === 'up') return 'trend-up';
  if (trend === 'down') return 'trend-down';
  return 'trend-stable';
}

// ============================================
// 日期格式化
// ============================================

export const DATE_FORMATS = {
  SHORT: 'YYYY-MM-DD',
  LONG: 'YYYY-MM-DD HH:mm:ss',
  TIME: 'HH:mm',
};

/**
 * 格式化 ISO 日期字符串
 * @param {string} isoString
 * @param {string} format
 * @returns {string}
 */
export function formatDate(isoString, format = 'YYYY-MM-DD HH:mm') {
  const date = new Date(isoString);
  if (isNaN(date)) return '无效日期';

  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  const hours = String(date.getHours()).padStart(2, '0');
  const minutes = String(date.getMinutes()).padStart(2, '0');
  const seconds = String(date.getSeconds()).padStart(2, '0');

  let result = format
    .replace('YYYY', year)
    .replace('MM', month)
    .replace('DD', day)
    .replace('HH', hours)
    .replace('mm', minutes)
    .replace('ss', seconds);

  return result;
}

/**
 * 获取相对时间字符串 (e.g., "2 小时前")
 * @param {string} isoString
 * @returns {string}
 */
export function relativeTime(isoString) {
  const date = new Date(isoString);
  const now = new Date();
  const seconds = Math.floor((now - date) / 1000);

  if (seconds < 60) return '刚刚';
  if (seconds < 3600) return `${Math.floor(seconds / 60)} 分钟前`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)} 小时前`;
  if (seconds < 604800) return `${Math.floor(seconds / 86400)} 天前`;

  return formatDate(isoString, 'YYYY-MM-DD');
}

// ============================================
// UUID 和 ID 生成
// ============================================

/**
 * 生成新的会话 ID
 * @returns {string}
 */
export function newSessionId() {
  return `session_${crypto.randomUUID()}`;
}

/**
 * 生成短 ID (用于临时引用)
 * @returns {string}
 */
export function generateId(prefix = '') {
  const id = Math.random().toString(36).substring(2, 9);
  return prefix ? `${prefix}_${id}` : id;
}

// ============================================
// 防抖和节流
// ============================================

/**
 * 防抖函数
 * @param {Function} fn
 * @param {number} ms - 延迟毫秒数
 * @returns {Function}
 */
export function debounce(fn, ms = 400) {
  let timeoutId;
  return function (...args) {
    clearTimeout(timeoutId);
    timeoutId = setTimeout(() => fn.apply(this, args), ms);
  };
}

/**
 * 节流函数
 * @param {Function} fn
 * @param {number} ms - 间隔毫秒数
 * @returns {Function}
 */
export function throttle(fn, ms = 400) {
  let lastCall = 0;
  return function (...args) {
    const now = Date.now();
    if (now - lastCall >= ms) {
      lastCall = now;
      fn.apply(this, args);
    }
  };
}

// ============================================
// 数据格式化
// ============================================

/**
 * 格式化大数字 (e.g., 1000 -> "1K")
 * @param {number} num
 * @returns {string}
 */
export function formatNumber(num) {
  if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
  if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
  return num.toString();
}

/**
 * 格式化百分比
 * @param {number} value
 * @param {number} decimals
 * @returns {string}
 */
export function formatPercent(value, decimals = 1) {
  return (value * 100).toFixed(decimals) + '%';
}

// ============================================
// 色彩处理
// ============================================

/**
 * 在两种颜色之间插值
 * @param {number} value - 0-100
 * @param {string} colorLow - CSS 色值
 * @param {string} colorHigh - CSS 色值
 * @returns {string} - RGB 字符串
 */
export function interpolateColor(value, colorLow = '#EF4444', colorHigh = '#10B981') {
  // 简化实现：根据分数直接返回相应颜色
  const score = Math.max(0, Math.min(100, value));
  return scoreColor(score);
}

// ============================================
// 文本处理
// ============================================

/**
 * 截断文本
 * @param {string} text
 * @param {number} maxLen
 * @param {string} suffix
 * @returns {string}
 */
export function truncate(text, maxLen = 50, suffix = '...') {
  if (!text) return '';
  if (text.length <= maxLen) return text;
  return text.substring(0, maxLen) + suffix;
}

/**
 * 首字母大写
 * @param {string} str
 * @returns {string}
 */
export function capitalize(str) {
  if (!str) return '';
  return str.charAt(0).toUpperCase() + str.slice(1);
}

// ============================================
// HTTP 辅助
// ============================================

/**
 * URL 查询参数编码
 * @param {string} str
 * @returns {string}
 */
export function encodeQuery(str) {
  return encodeURIComponent(str);
}

/**
 * 构建 URL 查询字符串
 * @param {Object} params
 * @returns {string}
 */
export function buildQueryString(params) {
  return Object.entries(params)
    .filter(([, v]) => v !== null && v !== undefined)
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`)
    .join('&');
}

// ============================================
// DOM 操作
// ============================================

/**
 * 创建元素
 * @param {string} tag
 * @param {string} className
 * @param {string} innerHTML
 * @returns {HTMLElement}
 */
export function createElement(tag, className = '', innerHTML = '') {
  const el = document.createElement(tag);
  if (className) el.className = className;
  if (innerHTML) el.innerHTML = innerHTML;
  return el;
}

/**
 * 设置元素属性
 * @param {HTMLElement} el
 * @param {Object} attrs
 * @returns {HTMLElement}
 */
export function setAttrs(el, attrs) {
  Object.entries(attrs).forEach(([key, value]) => {
    if (value === null) {
      el.removeAttribute(key);
    } else {
      el.setAttribute(key, value);
    }
  });
  return el;
}

/**
 * 清空容器
 * @param {HTMLElement} el
 */
export function clearElement(el) {
  while (el.firstChild) {
    el.removeChild(el.firstChild);
  }
}

// ============================================
// 验证
// ============================================

/**
 * 检查邮箱格式
 * @param {string} email
 * @returns {boolean}
 */
export function isValidEmail(email) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

/**
 * 检查 URL 格式
 * @param {string} url
 * @returns {boolean}
 */
export function isValidUrl(url) {
  try {
    new URL(url);
    return true;
  } catch {
    return false;
  }
}

// ============================================
// 延迟
// ============================================

/**
 * 延迟执行
 * @param {number} ms
 * @returns {Promise}
 */
export function delay(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// ============================================
// localStorage 辅助
// ============================================

/**
 * 安全地存储 JSON 数据
 * @param {string} key
 * @param {any} value
 */
export function setStorage(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch (e) {
    console.warn('localStorage 存储失败:', e);
  }
}

/**
 * 安全地读取 JSON 数据
 * @param {string} key
 * @param {any} defaultValue
 * @returns {any}
 */
export function getStorage(key, defaultValue = null) {
  try {
    const item = localStorage.getItem(key);
    return item ? JSON.parse(item) : defaultValue;
  } catch (e) {
    console.warn('localStorage 读取失败:', e);
    return defaultValue;
  }
}

/**
 * 移除存储项
 * @param {string} key
 */
export function removeStorage(key) {
  localStorage.removeItem(key);
}

export function setVersionedStorageValue(storage, key, value, schemaVersion = 1) {
  try {
    const payload = value && typeof value === 'object' ? { ...value, schema_version: schemaVersion } : {
      value,
      schema_version: schemaVersion,
    };
    storage.setItem(key, JSON.stringify(payload));
  } catch (e) {
    console.warn('storage save failed:', e);
  }
}

export function getVersionedStorageValue(storage, key, expectedSchemaVersion = 1) {
  try {
    const item = storage.getItem(key);
    if (!item) return null;
    const parsed = JSON.parse(item);
    if (!parsed || typeof parsed !== 'object' || parsed.schema_version !== expectedSchemaVersion) {
      storage.removeItem(key);
      return null;
    }
    return parsed;
  } catch (e) {
    console.warn('storage parse failed, cleared cache:', e);
    try {
      storage.removeItem(key);
    } catch {
      // no-op
    }
    return null;
  }
}
