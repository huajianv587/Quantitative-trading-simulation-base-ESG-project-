/* Quant Terminal - Application Configuration */

(function configureQuantTerminal() {
  const origin = window.location.origin;
  const storedApiBase = (() => {
    try {
      return localStorage.getItem('qt-api-base') || sessionStorage.getItem('qt-api-base') || '';
    } catch {
      return '';
    }
  })();

  const queryApiBase = (() => {
    try {
      return new URLSearchParams(window.location.search).get('api_base') || '';
    } catch {
      return '';
    }
  })();

  const explicitApiBase = window.__ESG_API_BASE_URL__ || queryApiBase || storedApiBase || '';
  const apiBase = explicitApiBase || origin;
  const landingEntry = (() => {
    if (typeof window.__ESG_LANDING_ENTRY__ === 'string' && window.__ESG_LANDING_ENTRY__.trim()) {
      return window.__ESG_LANDING_ENTRY__;
    }
    const pathname = window.location.pathname || '/';
    if (/\/app\/index\.html$/i.test(pathname)) {
      return `${origin}${pathname.replace(/\/app\/index\.html$/i, '/')}`;
    }
    if (/\/app\/$/i.test(pathname)) {
      return `${origin}${pathname.replace(/\/app\/$/i, '/')}`;
    }
    return `${origin}/`;
  })();

  window.__ESG_APP_ORIGIN__ = window.__ESG_APP_ORIGIN__ || origin;
  window.__ESG_API_BASE_URL__ = apiBase;
  window.__ESG_LANDING_ENTRY__ = landingEntry;

  window.__ESG_API_KEY__ = window.__ESG_API_KEY__ || '';
  window.__ESG_ADMIN_API_KEY__ = window.__ESG_ADMIN_API_KEY__ || window.__ESG_API_KEY__ || '';
  window.__ESG_EXECUTION_API_KEY__ = window.__ESG_EXECUTION_API_KEY__ || window.__ESG_API_KEY__ || '';
  window.__ESG_OPS_API_KEY__ = window.__ESG_OPS_API_KEY__ || window.__ESG_ADMIN_API_KEY__ || window.__ESG_API_KEY__ || '';
  window.__ESG_USER_ID__ = window.__ESG_USER_ID__ || 'user_123';

  const isDevelopment = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
  window.__FEATURES__ = {
    enableDebugMode: isDevelopment,
    enablePerformanceMonitoring: true,
    enableErrorReporting: !isDevelopment,
  };

  window.__APP_META__ = {
    name: 'Quant Terminal',
    version: '1.0.0',
    buildDate: '2026-04-24',
    environment: isDevelopment ? 'development' : 'production',
    appOrigin: origin,
    apiBaseUrl: apiBase,
    landingEntry,
  };

  if (isDevelopment) {
    console.log('%c Quant Terminal ', 'background: #00FF88; color: #000; font-weight: bold; padding: 4px 8px;');
    console.log('Origin:', origin);
    console.log('API:', apiBase);
    console.log('Landing:', landingEntry);
  }
})();
