/* Loading & Error Components JavaScript */

import { getErrorInfo, isRetryable } from '../utils/error-codes.js';
import { getLastTraceId } from '../qtapi.js';

// Loading Overlay
export function showLoading(message = 'Loading...', timeout = 30000) {
  const existing = document.getElementById('global-loading');
  if (existing) return;

  const overlay = document.createElement('div');
  overlay.id = 'global-loading';
  overlay.className = 'loading-overlay';
  overlay.setAttribute('role', 'status');
  overlay.setAttribute('aria-live', 'polite');
  overlay.setAttribute('aria-label', message);
  overlay.innerHTML = `
    <div class="loading-content">
      <div class="loading-spinner"></div>
      <div class="loading-text">${message}</div>
    </div>
  `;
  document.body.appendChild(overlay);

  // Timeout handler
  if (timeout > 0) {
    overlay._timeoutId = setTimeout(() => {
      hideLoading();
      showError('Request Timeout', 'The operation took too long. Please try again.', {
        type: 'timeout',
        onRetry: () => location.reload()
      });
    }, timeout);
  }
}

export function hideLoading() {
  const overlay = document.getElementById('global-loading');
  if (overlay) {
    if (overlay._timeoutId) {
      clearTimeout(overlay._timeoutId);
    }
    overlay.style.opacity = '0';
    setTimeout(() => overlay.remove(), 200);
  }
}

// Progress Bar
let progressBar = null;
let progressValue = 0;

export function showProgress() {
  if (!progressBar) {
    progressBar = document.createElement('div');
    progressBar.className = 'progress-bar';
    progressBar.innerHTML = '<div class="progress-bar-fill"></div>';
    document.body.appendChild(progressBar);
  }
  progressValue = 0;
  updateProgress(0);
}

export function updateProgress(value) {
  if (!progressBar) return;
  progressValue = Math.min(100, Math.max(0, value));
  const fill = progressBar.querySelector('.progress-bar-fill');
  if (fill) fill.style.width = progressValue + '%';
}

export function hideProgress() {
  if (progressBar) {
    updateProgress(100);
    setTimeout(() => {
      if (progressBar) {
        progressBar.remove();
        progressBar = null;
      }
    }, 300);
  }
}

// Indeterminate Progress
export function showIndeterminateProgress() {
  if (!progressBar) {
    progressBar = document.createElement('div');
    progressBar.className = 'progress-bar';
    progressBar.innerHTML = '<div class="progress-bar-indeterminate"></div>';
    document.body.appendChild(progressBar);
  }
}

// Error Display with Classification
const ERROR_TYPES = {
  network: { icon: '⚠', title: 'Network Error', color: '#ff6b6b' },
  timeout: { icon: '⏱', title: 'Timeout', color: '#ffa500' },
  auth: { icon: '🔒', title: 'Authentication Error', color: '#ff4757' },
  validation: { icon: '✗', title: 'Validation Error', color: '#ffa502' },
  server: { icon: '⚡', title: 'Server Error', color: '#ee5a6f' },
  notfound: { icon: '?', title: 'Not Found', color: '#95afc0' },
  unknown: { icon: '!', title: 'Error', color: '#ff6348' }
};

export function showError(title, message, options = {}) {
  const container = document.createElement('div');
  container.className = 'error-container';
  container.setAttribute('role', 'alert');
  container.setAttribute('aria-live', 'assertive');

  // 如果有错误码，使用错误码映射
  let errorInfo = { icon: '!', color: '#ff6348' };
  if (options.code) {
    const info = getErrorInfo(options.code, message);
    errorInfo.icon = info.icon;
    errorInfo.color = info.color === 'error' ? '#ff6348' : info.color === 'warning' ? '#ffa500' : '#ff6348';
    message = info.message;
  } else {
    const errorType = ERROR_TYPES[options.type] || ERROR_TYPES.unknown;
    errorInfo.icon = options.icon || errorType.icon;
    errorInfo.color = errorType.color;
  }

  const errorTitle = title || 'Error';
  const showRetry = options.onRetry !== undefined || (options.retryable && options.code);
  const showDetails = options.details !== undefined;
  const traceId = options.trace_id || getLastTraceId();

  container.innerHTML = `
    <div class="error-icon" style="color: ${errorInfo.color}">${errorInfo.icon}</div>
    <div class="error-title">${errorTitle}</div>
    <div class="error-message">${message}</div>
    ${traceId ? `
      <div class="error-trace-id">
        <span class="trace-id-label">追踪ID:</span>
        <code class="trace-id-value" title="点击复制">${traceId}</code>
        <button class="trace-id-copy" aria-label="复制追踪ID">📋</button>
      </div>
    ` : ''}
    ${showDetails ? `
      <details class="error-details">
        <summary>Technical Details</summary>
        <pre>${JSON.stringify(options.details, null, 2)}</pre>
      </details>
    ` : ''}
    ${showRetry ? `
      <div class="error-actions">
        <button class="retry-btn" id="error-retry-btn" aria-label="Retry operation">
          <span>↻</span>
          <span>Retry</span>
        </button>
      </div>
    ` : ''}
  `;

  // 复制trace_id功能
  if (traceId) {
    setTimeout(() => {
      const copyBtn = container.querySelector('.trace-id-copy');
      const traceIdValue = container.querySelector('.trace-id-value');
      if (copyBtn && traceIdValue) {
        const copyToClipboard = () => {
          navigator.clipboard.writeText(traceId).then(() => {
            copyBtn.textContent = '✓';
            setTimeout(() => { copyBtn.textContent = '📋'; }, 2000);
          }).catch(() => {
            // Fallback for older browsers
            const textarea = document.createElement('textarea');
            textarea.value = traceId;
            document.body.appendChild(textarea);
            textarea.select();
            document.execCommand('copy');
            document.body.removeChild(textarea);
            copyBtn.textContent = '✓';
            setTimeout(() => { copyBtn.textContent = '📋'; }, 2000);
          });
        };
        copyBtn.addEventListener('click', copyToClipboard);
        traceIdValue.addEventListener('click', copyToClipboard);
        traceIdValue.style.cursor = 'pointer';
      }
    }, 0);
  }

  if (showRetry) {
    setTimeout(() => {
      const retryBtn = container.querySelector('#error-retry-btn');
      if (retryBtn) {
        retryBtn.addEventListener('click', options.onRetry || (() => location.reload()));
      }
    }, 0);
  }

  return container;
}

// Skeleton Loader
export function createSkeleton(type = 'text', count = 1) {
  const container = document.createElement('div');

  for (let i = 0; i < count; i++) {
    const skeleton = document.createElement('div');
    skeleton.className = `skeleton skeleton-${type}`;
    container.appendChild(skeleton);
  }

  return container;
}

// Empty State
export function showEmptyState(title, message, icon = '∅') {
  const container = document.createElement('div');
  container.className = 'empty-state';
  container.innerHTML = `
    <div class="empty-state__icon">${icon}</div>
    <div class="empty-state__title">${title}</div>
    <div class="empty-state__text">${message}</div>
  `;
  return container;
}

// API Request with Loading & Error Handling
export async function apiRequestWithFeedback(apiCall, options = {}) {
  const {
    loadingMessage = 'Loading...',
    showLoadingOverlay = false,
    showProgress = false,
    onSuccess,
    onError,
    retryable = true
  } = options;

  try {
    if (showLoadingOverlay) {
      showLoading(loadingMessage);
    } else if (showProgress) {
      showIndeterminateProgress();
    }

    const result = await apiCall();

    if (onSuccess) onSuccess(result);
    return result;

  } catch (error) {
    console.error('API Request failed:', error);

    if (onError) {
      onError(error);
    } else {
      // Default error handling with error code support
      const errorMessage = error.message || 'An unexpected error occurred';
      const shouldRetry = retryable && (error.retryable !== false || isRetryable(error));

      if (shouldRetry) {
        return showError(
          'Request Failed',
          errorMessage,
          {
            code: error.code,
            trace_id: error.trace_id,
            details: error.details,
            retryable: true,
            onRetry: () => apiRequestWithFeedback(apiCall, options)
          }
        );
      } else {
        return showError('Error', errorMessage, {
          code: error.code,
          trace_id: error.trace_id,
          details: error.details
        });
      }
    }

    throw error;

  } finally {
    if (showLoadingOverlay) {
      hideLoading();
    } else if (showProgress) {
      hideProgress();
    }
  }
}

// Fetch with Retry and Exponential Backoff
export async function fetchWithRetry(url, options = {}, retries = 3, delay = 1000) {
  let lastError;

  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      const controller = new AbortController();
      const timeout = options.timeout || 10000;
      const timeoutId = setTimeout(() => controller.abort(), timeout);

      const response = await fetch(url, {
        ...options,
        signal: controller.signal
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        const errorType = classifyHttpError(response.status);
        throw new Error(`HTTP ${response.status}: ${response.statusText}`, { cause: errorType });
      }

      return response;

    } catch (error) {
      lastError = error;

      // Don't retry on certain errors
      if (error.name === 'AbortError') {
        throw new Error('Request timeout', { cause: 'timeout' });
      }

      if (error.message.includes('401') || error.message.includes('403')) {
        throw new Error('Authentication failed', { cause: 'auth' });
      }

      if (attempt < retries) {
        const backoffDelay = delay * Math.pow(1.5, attempt);
        await new Promise(resolve => setTimeout(resolve, backoffDelay));
      }
    }
  }

  throw lastError;
}

// Classify HTTP errors
function classifyHttpError(status) {
  if (status >= 400 && status < 500) {
    if (status === 401 || status === 403) return 'auth';
    if (status === 404) return 'notfound';
    if (status === 422) return 'validation';
    return 'client';
  }
  if (status >= 500) return 'server';
  return 'unknown';
}

// Network Status Monitor
let isOnline = navigator.onLine;

window.addEventListener('online', () => {
  isOnline = true;
  console.log('Network connection restored');
});

window.addEventListener('offline', () => {
  isOnline = false;
  console.warn('Network connection lost');
});

export function isNetworkOnline() {
  return isOnline;
}
