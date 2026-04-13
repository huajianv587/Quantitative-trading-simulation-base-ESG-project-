/* Quant Terminal — Toast  */

const ICONS = {
  success: `<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><polyline points="20 6 9 17 4 12"/></svg>`,
  error:   `<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>`,
  warning: `<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/></svg>`,
  info:    `<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/></svg>`,
};

export const toast = {
  success: (title, msg='', dur=4000) => _show('success', title, msg, dur),
  error:   (title, msg='', dur=5000) => _show('error',   title, msg, dur),
  warning: (title, msg='', dur=4500) => _show('warning', title, msg, dur),
  info:    (title, msg='', dur=3500) => _show('info',    title, msg, dur),
};

function _show(type, title, msg, dur) {
  const c = document.getElementById('toast-container');
  if (!c) return;
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.innerHTML = `<div class="toast-icon">${ICONS[type]}</div>
    <div class="toast-body"><div class="toast-title">${_esc(title)}</div>${msg?`<div class="toast-msg">${_esc(msg)}</div>`:''}</div>`;
  c.appendChild(el);
  setTimeout(() => el.remove(), dur);
}

function _esc(s) {
  const d = document.createElement('div'); d.textContent = String(s); return d.innerHTML;
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
 */
export function showToast(options) {
  const {
    type = 'info',
    title = '',
    message = '',
    duration = 3000,
  } = options;

  const container = document.getElementById('toast-container');
  if (!container) return;

  const signature = `${type}:${title}:${message}`;
  const lastShownAt = RECENT_TOASTS.get(signature) || 0;
  const now = Date.now();
  if (now - lastShownAt < TOAST_DEDUPE_MS) {
    return null;
  }
  RECENT_TOASTS.set(signature, now);

  const toastId = `toast_${Date.now()}`;
  const icons = {
    success: '✓',
    error: '✕',
    warning: '⚠',
    info: 'ℹ',
  };

  const toast = document.createElement('div');
  toast.id = toastId;
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `
    <div class="toast-icon">${icons[type]}</div>
    <div class="flex-1">
      ${title ? `<div class="font-semibold text-sm">${escapeHtml(title)}</div>` : ''}
      <div class="toast-message">${escapeHtml(message)}</div>
    </div>
  `;

  container.appendChild(toast);

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
    toast.style.animation = 'slideInRight 0.3s ease-out reverse';
    setTimeout(() => {
      toast.remove();
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
}

// ============================================
// 便利方法
// ============================================

export function toastSuccess(message, title = '成功') {
  return showToast({ type: 'success', title, message });
}

export function toastError(message, title = '错误') {
  return showToast({ type: 'error', title, message, duration: 5000 });
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
