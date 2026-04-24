function currentApiLabel() {
  try {
    var raw = window.__ESG_API_BASE_URL__ || window.__ESG_APP_ORIGIN__ || window.location.origin || '';
    var resolved = new URL(String(raw || ''), window.location.origin);
    return resolved.host || resolved.origin || String(raw || '');
  } catch (_ignore) {
    return String(window.__ESG_API_BASE_URL__ || window.__ESG_APP_ORIGIN__ || window.location.origin || '');
  }
}

function backendMessage(lang) {
  var endpoint = currentApiLabel();
  return lang === 'zh'
    ? `后端服务暂时不可用（${endpoint}），请启动 Quant Terminal 服务后重试。`
    : `Backend service is unavailable (${endpoint}). Please start Quant Terminal and try again.`;
}

function backendSuggestions(lang) {
  var endpoint = currentApiLabel();
  return [
    lang === 'zh' ? '1. 确认 Quant Terminal 已由 start.cmd 启动。' : '1. Confirm Quant Terminal was started from start.cmd.',
    lang === 'zh' ? `2. 检查 ${endpoint} 是否已被本项目后端接管。` : `2. Confirm ${endpoint} is serving this project backend.`,
    lang === 'zh' ? '3. 若端口被其他项目占用，请关闭冲突服务后重试。' : '3. If another app owns the port, close the conflicting service and retry.',
  ];
}

export class ErrorHandler {
  constructor() {
    this.errorMessages = {
      NETWORK_ERROR: {
        zh: '网络连接失败，请检查网络设置。',
        en: 'Network connection failed. Please check your network settings.',
      },
      BACKEND_UNAVAILABLE: {
        zh: '',
        en: '',
      },
      TIMEOUT: {
        zh: '请求超时，请稍后重试。',
        en: 'Request timeout. Please try again later.',
      },
      API_ERROR: {
        zh: 'API 请求失败。',
        en: 'API request failed.',
      },
      INVALID_RESPONSE: {
        zh: '服务端返回的数据格式异常。',
        en: 'Invalid response format from server.',
      },
      UNAUTHORIZED: {
        zh: '未授权访问，请先登录。',
        en: 'Unauthorized access. Please login.',
      },
      FORBIDDEN: {
        zh: '没有访问权限。',
        en: 'Access forbidden.',
      },
      NOT_FOUND: {
        zh: '请求的资源不存在。',
        en: 'Requested resource not found.',
      },
      SERVER_ERROR: {
        zh: '服务端内部错误，请稍后重试。',
        en: 'Internal server error. Please try again later.',
      },
      DATA_LOAD_FAILED: {
        zh: '数据加载失败。',
        en: 'Failed to load data.',
      },
      MODULE_LOAD_FAILED: {
        zh: '模块加载失败，请刷新页面后重试。',
        en: 'Failed to load module. Please refresh the page.',
      },
      INVALID_DATA: {
        zh: '数据格式不正确。',
        en: 'Invalid data format.',
      },
      OPERATION_FAILED: {
        zh: '操作失败。',
        en: 'Operation failed.',
      },
      VALIDATION_ERROR: {
        zh: '输入校验失败。',
        en: 'Input validation failed.',
      },
    };
  }

  getCurrentLanguage() {
    return window.currentLanguage || 'zh';
  }

  parseError(error, context = {}) {
    var lang = this.getCurrentLanguage();
    var errorType = 'API_ERROR';
    var details = '';
    var suggestions = [];
    var message = '';
    var errorMessage = String(error?.message || '');

    if (errorMessage === 'Failed to fetch' || error?.name === 'TypeError') {
      errorType = 'BACKEND_UNAVAILABLE';
      message = backendMessage(lang);
      suggestions = backendSuggestions(lang);
    } else if (error?.status) {
      switch (error.status) {
        case 401:
          errorType = 'UNAUTHORIZED';
          break;
        case 403:
          errorType = 'FORBIDDEN';
          break;
        case 404:
          errorType = 'NOT_FOUND';
          details = context.url || '';
          break;
        case 500:
        case 502:
        case 503:
          errorType = 'SERVER_ERROR';
          break;
        case 408:
          errorType = 'TIMEOUT';
          break;
        default:
          errorType = 'API_ERROR';
          details = 'HTTP ' + error.status;
      }
    } else if (error?.name === 'AbortError' || errorMessage.toLowerCase().includes('timeout')) {
      errorType = 'TIMEOUT';
    } else if (errorMessage.includes('import')) {
      errorType = 'MODULE_LOAD_FAILED';
      details = errorMessage;
    }

    if (!message) {
      message = this.errorMessages[errorType]?.[lang] || errorMessage || this.errorMessages.API_ERROR[lang];
    }

    return {
      type: errorType,
      message: message,
      details: details,
      suggestions: suggestions,
      originalError: error,
      context: context,
    };
  }

  showError(error, context = {}) {
    var errorInfo = this.parseError(error, context);

    if (window.showToast) {
      var toastMessage = errorInfo.message;
      if (errorInfo.details) {
        toastMessage += '\n' + errorInfo.details;
      }
      window.showToast(toastMessage, 'error', 5000);
    }

    console.error('[ErrorHandler]', {
      type: errorInfo.type,
      message: errorInfo.message,
      details: errorInfo.details,
      suggestions: errorInfo.suggestions,
      context: errorInfo.context,
      originalError: errorInfo.originalError,
    });

    return errorInfo;
  }

  createErrorUI(errorInfo, options = {}) {
    var lang = this.getCurrentLanguage();
    var showRetry = options.showRetry !== undefined ? options.showRetry : true;
    var showSuggestions = options.showSuggestions !== undefined ? options.showSuggestions : true;
    var onRetry = options.onRetry || null;
    var variant = options.variant || 'default';

    var container = document.createElement('div');
    container.className = variant === 'compact' ? 'error-state-container error-state-container--compact' : 'error-state-container';

    var html = `
      <div class="error-state${variant === 'compact' ? ' error-state--compact' : ''}">
        <div class="error-icon">${variant === 'compact' ? '!' : '⚠️'}</div>
        <div class="error-copy">
          <div class="error-title">${errorInfo.message}</div>
          ${errorInfo.details ? `<div class="error-details">${errorInfo.details}</div>` : ''}
          ${showSuggestions && errorInfo.suggestions.length > 0 ? `
            <div class="error-suggestions">
              <div class="suggestions-title">${lang === 'zh' ? '解决建议' : 'Suggestions'}</div>
              <ul>${errorInfo.suggestions.map(function(item) { return `<li>${item}</li>`; }).join('')}</ul>
            </div>` : ''}
        </div>
        ${showRetry ? `<button class="error-retry-btn">${lang === 'zh' ? '重试' : 'Retry'}</button>` : ''}
      </div>
    `;

    container.innerHTML = html;

    if (showRetry && onRetry) {
      var retryBtn = container.querySelector('.error-retry-btn');
      if (retryBtn) retryBtn.addEventListener('click', onRetry);
    }

    return container;
  }

  async wrapAsync(fn, context = {}) {
    try {
      return await fn();
    } catch (error) {
      this.showError(error, context);
      throw error;
    }
  }
}

export const errorHandler = new ErrorHandler();
window.errorHandler = errorHandler;
