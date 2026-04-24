/**
 * Enhanced API utilities with error classification, retry logic, and network monitoring
 */

import { showToast } from '../components/toast.js';
import { showLoading, hideLoading } from '../components/loading.js';

// ── Error Classification ──────────────────────────────────────────
const ErrorType = {
  NETWORK: 'network',
  SERVER: 'server',
  CLIENT: 'client',
  TIMEOUT: 'timeout',
  UNKNOWN: 'unknown'
};

const ErrorMessages = {
  [ErrorType.NETWORK]: '网络连接失败，请检查您的网络设置',
  [ErrorType.SERVER]: '服务器暂时无法响应，请稍后重试',
  [ErrorType.CLIENT]: '请求参数有误，请检查输入',
  [ErrorType.TIMEOUT]: '请求超时，请稍后重试',
  [ErrorType.UNKNOWN]: '发生未知错误，请联系技术支持'
};

/**
 * Classify error based on status code and error type
 */
function classifyError(error, response = null) {
  // Network errors (no response)
  if (!response && (error.message === 'Failed to fetch' || error.name === 'TypeError')) {
    return {
      type: ErrorType.NETWORK,
      message: ErrorMessages[ErrorType.NETWORK],
      retryable: true
    };
  }

  // Timeout errors
  if (error.name === 'AbortError' || error.message.includes('timeout')) {
    return {
      type: ErrorType.TIMEOUT,
      message: ErrorMessages[ErrorType.TIMEOUT],
      retryable: true
    };
  }

  // HTTP status code errors
  if (response) {
    const status = response.status;

    // Client errors (4xx)
    if (status >= 400 && status < 500) {
      return {
        type: ErrorType.CLIENT,
        message: status === 404 ? '请求的资源不存在' : ErrorMessages[ErrorType.CLIENT],
        retryable: false
      };
    }

    // Server errors (5xx)
    if (status >= 500) {
      return {
        type: ErrorType.SERVER,
        message: ErrorMessages[ErrorType.SERVER],
        retryable: true
      };
    }
  }

  // Unknown errors
  return {
    type: ErrorType.UNKNOWN,
    message: ErrorMessages[ErrorType.UNKNOWN],
    retryable: false
  };
}

// ── Retry Logic ───────────────────────────────────────────────────
const RetryConfig = {
  maxRetries: 3,
  baseDelay: 1000, // 1 second
  maxDelay: 8000,  // 8 seconds
  backoffMultiplier: 2
};

/**
 * Calculate delay for exponential backoff
 */
function calculateRetryDelay(attempt) {
  const delay = RetryConfig.baseDelay * Math.pow(RetryConfig.backoffMultiplier, attempt - 1);
  return Math.min(delay, RetryConfig.maxDelay);
}

/**
 * Sleep for specified milliseconds
 */
function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 * Retry a function with exponential backoff
 */
async function retryWithBackoff(fn, shouldRetry = () => true) {
  let lastError;

  for (let attempt = 1; attempt <= RetryConfig.maxRetries; attempt++) {
    try {
      return await fn(attempt);
    } catch (error) {
      lastError = error;

      // Check if we should retry
      if (attempt < RetryConfig.maxRetries && shouldRetry(error)) {
        const delay = calculateRetryDelay(attempt);
        console.log(`Retry attempt ${attempt}/${RetryConfig.maxRetries} after ${delay}ms`);
        await sleep(delay);
      } else {
        break;
      }
    }
  }

  throw lastError;
}

// ── Network Status Monitoring ─────────────────────────────────────
class NetworkMonitor {
  constructor() {
    this.isOnline = navigator.onLine;
    this.listeners = new Set();
    this.indicator = null;

    // Listen to online/offline events
    window.addEventListener('online', () => this.handleOnline());
    window.addEventListener('offline', () => this.handleOffline());
  }

  /**
   * Add status change listener
   */
  addListener(callback) {
    this.listeners.add(callback);
    return () => this.listeners.delete(callback);
  }

  /**
   * Notify all listeners
   */
  notifyListeners() {
    this.listeners.forEach(callback => callback(this.isOnline));
  }

  /**
   * Handle online event
   */
  handleOnline() {
    this.isOnline = true;
    this.hideIndicator();
    this.notifyListeners();
    showToast('网络连接已恢复', 'success');
  }

  /**
   * Handle offline event
   */
  handleOffline() {
    this.isOnline = false;
    this.showIndicator();
    this.notifyListeners();
  }

  /**
   * Show network status indicator
   */
  showIndicator() {
    if (this.indicator) return;

    this.indicator = document.createElement('div');
    this.indicator.className = 'network-status-indicator';
    this.indicator.innerHTML = `
      <div class="network-status-content">
        <span class="network-status-icon">⚠️</span>
        <span class="network-status-text">网络连接已断开</span>
        <button class="network-status-retry" onclick="location.reload()">刷新页面</button>
      </div>
    `;

    document.body.appendChild(this.indicator);

    // Trigger reflow for animation
    requestAnimationFrame(() => {
      this.indicator.classList.add('visible');
    });
  }

  /**
   * Hide network status indicator
   */
  hideIndicator() {
    if (!this.indicator) return;

    this.indicator.classList.remove('visible');
    this.indicator.classList.add('hidden');

    setTimeout(() => {
      if (this.indicator && this.indicator.parentNode) {
        this.indicator.parentNode.removeChild(this.indicator);
      }
      this.indicator = null;
    }, 300);
  }

  /**
   * Check if online
   */
  checkOnline() {
    return this.isOnline;
  }
}

// Create singleton instance
const networkMonitor = new NetworkMonitor();

// ── Enhanced Fetch ────────────────────────────────────────────────
/**
 * Enhanced fetch with timeout, retry, and error handling
 */
async function enhancedFetch(url, options = {}) {
  const {
    timeout = 30000,
    retry = true,
    showLoadingIndicator = false,
    loadingMessage = '加载中...',
    ...fetchOptions
  } = options;

  // Check network status
  if (!networkMonitor.checkOnline()) {
    throw new Error('网络连接已断开，请检查您的网络设置');
  }

  // Show loading indicator if requested
  if (showLoadingIndicator) {
    showLoading(loadingMessage);
  }

  try {
    // Create abort controller for timeout
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeout);

    // Define fetch function
    const fetchFn = async () => {
      try {
        const response = await fetch(url, {
          ...fetchOptions,
          signal: controller.signal
        });

        clearTimeout(timeoutId);

        // Check response status
        if (!response.ok) {
          const error = new Error(`HTTP ${response.status}`);
          error.response = response;
          throw error;
        }

        return response;
      } catch (error) {
        clearTimeout(timeoutId);
        throw error;
      }
    };

    // Execute with retry if enabled
    if (retry) {
      return await retryWithBackoff(
        fetchFn,
        (error) => {
          const classified = classifyError(error, error.response);
          return classified.retryable;
        }
      );
    } else {
      return await fetchFn();
    }
  } catch (error) {
    // Classify and handle error
    const classified = classifyError(error, error.response);

    // Show error toast
    showToast(classified.message, 'error');

    // Re-throw with classification
    error.classification = classified;
    throw error;
  } finally {
    // Hide loading indicator
    if (showLoadingIndicator) {
      hideLoading();
    }
  }
}

/**
 * Enhanced JSON fetch
 */
async function fetchJSON(url, options = {}) {
  const response = await enhancedFetch(url, options);
  return await response.json();
}

/**
 * Enhanced POST request
 */
async function postJSON(url, data, options = {}) {
  return await fetchJSON(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...options.headers
    },
    body: JSON.stringify(data),
    ...options
  });
}

// ── Request Queue Management ──────────────────────────────────────
class RequestQueue {
  constructor(maxConcurrent = 6) {
    this.maxConcurrent = maxConcurrent;
    this.running = 0;
    this.queue = [];
  }

  /**
   * Add request to queue
   */
  async enqueue(fn) {
    // Wait if at capacity
    while (this.running >= this.maxConcurrent) {
      await new Promise(resolve => {
        this.queue.push(resolve);
      });
    }

    this.running++;

    try {
      return await fn();
    } finally {
      this.running--;

      // Process next in queue
      if (this.queue.length > 0) {
        const resolve = this.queue.shift();
        resolve();
      }
    }
  }
}

// Create singleton instance
const requestQueue = new RequestQueue();

/**
 * Queued fetch request
 */
async function queuedFetch(url, options = {}) {
  return await requestQueue.enqueue(() => enhancedFetch(url, options));
}

// ── Exports ───────────────────────────────────────────────────────
export {
  ErrorType,
  classifyError,
  enhancedFetch,
  fetchJSON,
  postJSON,
  queuedFetch,
  networkMonitor,
  RetryConfig
};
