/* Quant Terminal — Toast  */

import { getErrorInfo } from '../utils/error-codes.js';
import { getLastTraceId } from '../qtapi.js';

const ICONS = {
  success: `<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><polyline points="20 6 9 17 4 12"/></svg>`,
  error:   `<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>`,
  warning: `<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/></svg>`,
  info:    `<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/></svg>`,
};

// Toast堆叠管理
const MAX_TOASTS = 3;
const toastQueue = [];

export const toast = {
  success: (title, msg='', dur=4000) => _show('success', title, msg, dur),
  error:   (title, msg='', dur=5000) => _show('error',   title, msg, dur),
  warning: (title, msg='', dur=4500) => _show('warning', title, msg, dur),
  info:    (title, msg='', dur=3500) => _show('info',    title, msg, dur),
};

function _show(type, title, msg, dur) {
  const c = document.getElementById('toast-container');
  if (!c) return;

  // 堆叠管理：超过最大数量时移除最旧的
  manageToastStack();

  const toastId = `toast_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  const el = document.createElement('div');
  el.id = toastId;
  el.className = `toast ${type}`;

  // ARIA属性
  el.setAttribute('role', type === 'error' ? 'alert' : 'status');
  el.setAttribute('aria-live', type === 'error' ? 'assertive' : 'polite');
  el.setAttribute('aria-atomic', 'true');

  el.innerHTML = `<div class="toast-icon" aria-hidden="true">${ICONS[type]}</div>
    <div class="toast-body"><div class="toast-title">${_esc(title)}</div>${msg?`<div class="toast-msg">${_esc(msg)}</div>`:''}</div>
    <button class="toast-close" aria-label="关闭通知" tabindex="0">×</button>`;

  c.appendChild(el);
  toastQueue.push(toastId);

  // 关闭按钮事件
  const closeBtn = el.querySelector('.toast-close');
  closeBtn.addEventListener('click', () => removeToastById(toastId));
  closeBtn.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      removeToastById(toastId);
    }
  });

  // 自动关闭
  if (dur > 0) {
    setTimeout(() => removeToastById(toastId), dur);
  }

  return toastId;
}

function _esc(s) {
  const d = document.createElement('div'); d.textContent = String(s); return d.innerHTML;
}

// 堆叠管理
function manageToastStack() {
  while (toastQueue.length >= MAX_TOASTS) {
    const oldestId = toastQueue.shift();
    removeToastById(oldestId);
  }
}

function removeToastById(toastId) {
  const el = document.getElementById(toastId);
  if (el) {
    el.style.animation = 'slideOutRight 0.3s ease-out';
    setTimeout(() => {
      el.remove();
      const idx = toastQueue.indexOf(toastId);
      if (idx > -1) toastQueue.splice(idx, 1);
    }, 300);
  }
}

const RECENT_TOASTS = new Map();
const TOAST_DEDUPE_MS = 4000;

/**
 * 显示通知
 * @param {Object} options
 *   - type: 'success' | 'error' | 'warning' | 'info' (默认: 'info')
 *   - title: 标题 (可选)
 *   - message: 消息内容
 *   - duration: 自动关闭毫秒数 (默认: 3000, 0 = 不自动关闭)
 *   - code: 错误码 (可选)
 *   - trace_id: 追踪ID (可选)
 */
export function showToast(options) {
  const {
    type = 'info',
    title = '',
    message = '',
    duration = 3000,
    code = null,
    trace_id = null,
  } = options;

  const container = document.getElementById('toast-container');
  if (!container) return;

  // 如果有错误码，使用错误码映射
  let displayMessage = message;
  if (code && type === 'error') {
    const errorInfo = getErrorInfo(code, message);
    displayMessage = errorInfo.message;
  }

  const signature = `${type}:${title}:${displayMessage}`;
  const lastShownAt = RECENT_TOASTS.get(signature) || 0;
  const now = Date.now();
  if (now - lastShownAt < TOAST_DEDUPE_MS) {
    return null;
  }
  RECENT_TOASTS.set(signature, now);

  // 堆叠管理
  manageToastStack();

  const toastId = `toast_${Date.now()}`;
  const icons = {
    success: '✓',
    error: '✕',
    warning: '⚠',
    info: 'ℹ',
  };

  const traceId = trace_id || getLastTraceId();

  const toast = document.createElement('div');
  toast.id = toastId;
  toast.className = `toast toast-${type}`;

  // ARIA属性
  toast.setAttribute('role', type === 'error' ? 'alert' : 'status');
  toast.setAttribute('aria-live', type === 'error' ? 'assertive' : 'polite');
  toast.setAttribute('aria-atomic', 'true');

  toast.innerHTML = `
    <div class="toast-icon" aria-hidden="true">${icons[type]}</div>
    <div class="flex-1">
      ${title ? `<div class="font-semibold text-sm">${escapeHtml(title)}</div>` : ''}
      <div class="toast-message">${escapeHtml(displayMessage)}</div>
      ${traceId && type === 'error' ? `
        <div class="toast-trace-id" style="font-size: 0.75rem; opacity: 0.7; margin-top: 4px;">
          <span>ID: </span>
          <code style="font-size: 0.7rem; cursor: pointer;" title="点击复制" data-trace-id="${escapeHtml(traceId)}">${escapeHtml(traceId.substring(0, 8))}...</code>
        </div>
      ` : ''}
    </div>
    <button class="toast-close" aria-label="关闭通知" tabindex="0">×</button>
  `;

  container.appendChild(toast);
  toastQueue.push(toastId);

  // 复制trace_id功能
  if (traceId && type === 'error') {
    const traceIdCode = toast.querySelector('[data-trace-id]');
    if (traceIdCode) {
      traceIdCode.addEventListener('click', () => {
        const fullTraceId = traceIdCode.getAttribute('data-trace-id');
        navigator.clipboard.writeText(fullTraceId).then(() => {
          traceIdCode.textContent = '已复制!';
          setTimeout(() => {
            traceIdCode.textContent = fullTraceId.substring(0, 8) + '...';
          }, 2000);
        }).catch(() => {
          // Fallback
          const textarea = document.createElement('textarea');
          textarea.value = fullTraceId;
          document.body.appendChild(textarea);
          textarea.select();
          document.execCommand('copy');
          document.body.removeChild(textarea);
        });
      });
    }
  }

  // 关闭按钮事件
  const closeBtn = toast.querySelector('.toast-close');
  if (closeBtn) {
    closeBtn.addEventListener('click', () => removeToast(toastId));
    closeBtn.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        removeToast(toastId);
      }
    });
  }

  // 自动关闭
  if (duration > 0) {
    setTimeout(() => {
      removeToast(toastId);
    }, duration);
  }

  return toastId;
}

/**
 * 关闭指定通知
 * @param {string} toastId
 */
export function removeToast(toastId) {
  const toast = document.getElementById(toastId);
  if (toast) {
    toast.style.animation = 'slideOutRight 0.3s ease-out';
    setTimeout(() => {
      toast.remove();
      const idx = toastQueue.indexOf(toastId);
      if (idx > -1) toastQueue.splice(idx, 1);
    }, 300);
  }
}

/**
 * 清空所有通知
 */
export function clearAllToasts() {
  const container = document.getElementById('toast-container');
  if (container) {
    container.innerHTML = '';
  }
  RECENT_TOASTS.clear();
  toastQueue.length = 0;
}

// ============================================
// 便利方法
// ============================================

export function toastSuccess(message, title = '成功') {
  return showToast({ type: 'success', title, message });
}

export function toastError(message, title = '错误', options = {}) {
  return showToast({
    type: 'error',
    title,
    message,
    duration: 5000,
    code: options.code,
    trace_id: options.trace_id
  });
}

export function toastWarning(message, title = '警告') {
  return showToast({ type: 'warning', title, message });
}

export function toastInfo(message, title = '') {
  return showToast({ type: 'info', title, message });
}

// ============================================
// 辅助函数
// ============================================

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

/**
 * 监听全局 API 错误
 */
export function initErrorListener() {
  window.addEventListener('api:error', (e) => toast.error('API Error', e.detail?.message));
}
