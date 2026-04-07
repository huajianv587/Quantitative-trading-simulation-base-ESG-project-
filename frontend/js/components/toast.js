/**
 * Toast 通知系统
 */

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
  window.addEventListener('api:error', (event) => {
    const { message } = event.detail;
    toastError(message, '接口错误');
  });
}
