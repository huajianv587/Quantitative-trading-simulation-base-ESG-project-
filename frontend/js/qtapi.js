/* Quant Terminal - API Client */

function _normalizedApiBase() {
  var raw = window.__ESG_API_BASE_URL__ || window.__ESG_APP_ORIGIN__ || window.location.origin || '';
  return String(raw || '').replace(/\/+$/, '');
}

var BASE = _normalizedApiBase();
var Q = '/api/v1/quant';

function _isReadMethod(method) {
  var normalized = String(method || 'GET').toUpperCase();
  return normalized === 'GET' || normalized === 'HEAD';
}

function _normalizedPath(path) {
  return String(path || '').split('?')[0].replace(/\/+$/, '') || '/';
}

function _isPublicApiPath(path) {
  var normalized = _normalizedPath(path);
  return normalized === '/auth/register'
    || normalized === '/auth/login'
    || normalized === '/auth/reset-password/request'
    || normalized === '/auth/reset-password/confirm'
    || normalized === '/api/auth/register'
    || normalized === '/api/auth/login'
    || normalized === '/api/auth/reset-password/request'
    || normalized === '/api/auth/reset-password/confirm'
    || normalized === '/api/health'
    || normalized === '/health'
    || normalized === '/livez';
}

function _scopeForRequest(method, path, explicitScope) {
  if (explicitScope) return explicitScope;
  if (_isPublicApiPath(path)) return '';

  var normalized = _normalizedPath(path);
  if (normalized.indexOf('/admin') === 0) return 'admin';
  if (normalized.indexOf('/ops') === 0) return 'ops';
  if (normalized.indexOf('/scheduler') === 0) return 'scheduler';
  if (normalized.indexOf('/user') === 0) return 'user';
  if (normalized.indexOf('/api/v1/platform') === 0) return 'ops';
  if (normalized.indexOf('/api/v1/jobs') === 0) return 'ops';
  if (normalized.indexOf('/api/v1/data') === 0) return 'ops';
  if (normalized.indexOf('/api/v1/trading') === 0 || normalized.indexOf('/api/v1/watchlist') === 0) return 'trading';
  if (normalized.indexOf('/api/v1/connectors') === 0) return 'research';
  if (normalized.indexOf('/api/v1/quant/execution') === 0
      || normalized.indexOf('/api/v1/quant/validation') === 0
      || normalized.indexOf('/api/v1/quant/workflows') === 0
      || normalized.indexOf('/api/v1/quant/paper') === 0
      || normalized.indexOf('/api/v1/quant/promotion') === 0
      || normalized.indexOf('/api/v1/quant/models') === 0
      || normalized.indexOf('/api/v1/quant/deployment') === 0
      || normalized.indexOf('/api/v1/quant/observability') === 0
      || normalized.indexOf('/api/v1/quant/storage') === 0
      || normalized.indexOf('/api/v1/quant/submit-locks') === 0
      || normalized.indexOf('/api/v1/quant/session-evidence') === 0) {
    return 'execution';
  }
  if (normalized.indexOf('/api/v1/quant/rl/promote') === 0) return 'execution';
  if (normalized.indexOf('/api/v1/quant/rl') === 0) return 'research';
  if (normalized.indexOf('/api/v1/quant') === 0) return 'research';
  if (normalized.indexOf('/api/session') === 0
      || normalized.indexOf('/api/query') === 0
      || normalized.indexOf('/api/agent') === 0
      || normalized.indexOf('/session') === 0
      || normalized.indexOf('/query') === 0
      || normalized.indexOf('/agent') === 0) {
    return 'user';
  }
  return _isReadMethod(method) ? '' : 'user';
}

export function getApiBaseUrl() {
  BASE = _normalizedApiBase();
  return BASE;
}

export function getApiEndpointLabel() {
  try {
    var resolved = new URL(getApiBaseUrl(), window.location.origin);
    return resolved.host || resolved.origin || getApiBaseUrl();
  } catch (_ignore) {
    return getApiBaseUrl();
  }
}

// Generate a per-mutation trace id.
function _generateTraceId() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
    var r = Math.random() * 16 | 0;
    var v = c === 'x' ? r : (r & 0x3 | 0x8);
    return v.toString(16);
  });
}

// Last response trace id surfaced to the UI.
var _lastTraceId = null;

function _emitApiEvent(type, detail) {
  try {
    window.dispatchEvent(new CustomEvent('qtapi:' + type, {
      detail: {
        timestamp: new Date().toISOString(),
        ...detail,
      },
    }));
  } catch (_ignore) {
    // Ignore telemetry dispatch failures.
  }
}

function _apiKeyForScope(scope) {
  if (!scope || scope === 'public') return '';
  if (scope === 'admin') return window.__ESG_ADMIN_API_KEY__ || window.__ESG_API_KEY__ || '';
  if (scope === 'execution') return window.__ESG_EXECUTION_API_KEY__ || window.__ESG_API_KEY__ || '';
  if (scope === 'ops') return window.__ESG_OPS_API_KEY__ || window.__ESG_ADMIN_API_KEY__ || window.__ESG_API_KEY__ || '';
  if (scope === 'trading') return window.__ESG_TRADING_API_KEY__ || window.__ESG_EXECUTION_API_KEY__ || window.__ESG_API_KEY__ || '';
  if (scope === 'scheduler') return window.__ESG_SCHEDULER_API_KEY__ || window.__ESG_OPS_API_KEY__ || window.__ESG_API_KEY__ || '';
  if (scope === 'research') return window.__ESG_RESEARCH_API_KEY__ || window.__ESG_API_KEY__ || '';
  if (scope === 'user') return window.__ESG_USER_API_KEY__ || window.__ESG_API_KEY__ || '';
  return window.__ESG_API_KEY__ || '';
}

function _mergeHeaders(method, path, scope, body, extraHeaders) {
  var headers = {};
  var resolvedScope = _scopeForRequest(method, path, scope);
  var apiKey = _apiKeyForScope(resolvedScope);
  if (apiKey) headers['x-api-key'] = apiKey;
  if (body !== undefined) {
    headers['Content-Type'] = 'application/json';
  }

  // Attach trace ids only to requests that can mutate state.
  if (!_isReadMethod(method)) {
    headers['X-Trace-ID'] = _generateTraceId();
  }

  if (extraHeaders) {
    Object.keys(extraHeaders).forEach(function(key) {
      headers[key] = extraHeaders[key];
    });
  }
  return headers;
}

function _req(method, path, body, opts) {
  var options = opts || {};
  var startedAt = Date.now();
  var detail = { method: method, path: path, scope: _scopeForRequest(method, path, options.scope) };
  _emitApiEvent('request-start', detail);
  var requestOptions = {
    method: method,
    headers: _mergeHeaders(method, path, options.scope, body, options.headers),
  };
  if (body !== undefined) requestOptions.body = JSON.stringify(body);

  return fetch(getApiBaseUrl() + path, requestOptions).then(function(res) {
    _emitApiEvent('request-end', {
      ...detail,
      ok: res.ok,
      status: res.status,
      duration_ms: Date.now() - startedAt,
    });
    // Preserve the latest response trace id.
    var traceId = res.headers.get('X-Trace-ID');
    if (traceId) _lastTraceId = traceId;

    if (res.status === 204) return null;
    if (!res.ok) {
      return res.json().catch(function() {
        return {
          success: false,
          error: {
            code: 'HTTP_' + res.status,
            message: res.statusText,
            trace_id: traceId
          }
        };
      }).then(function(err) {
        // Preferred structured error format.
        if (err.success === false && err.error) {
          var error = new Error(err.error.message || ('HTTP ' + res.status));
          error.code = err.error.code;
          error.trace_id = err.error.trace_id || traceId;
          error.details = err.error.details;
          error.retryable = err.error.retryable;
          throw error;
        }
        // Backward-compatible FastAPI error format.
        var error = new Error(err.detail || ('HTTP ' + res.status));
        error.trace_id = traceId;
        throw error;
      });
    }
    return res.json();
  }).catch(function(error) {
    _emitApiEvent('request-error', {
      ...detail,
      ok: false,
      error: error && error.message ? error.message : String(error || 'request_failed'),
      duration_ms: Date.now() - startedAt,
    });
    throw error;
  });
}

function _get(path, opts) { return _req('GET', path, undefined, opts); }
function _post(path, body, opts) { return _req('POST', path, body, opts); }
function _put(path, body, opts) { return _req('PUT', path, body, opts); }
function _del(path, opts) { return _req('DELETE', path, undefined, opts); }

export var api = {
  health: function() { return _get('/api/health'); },

  // Auth
  auth: {
    register:     function(payload) { return _post('/api/auth/register', payload); },
    login:        function(payload) { return _post('/api/auth/login', payload); },
    verify:       function(token)   { return _get('/api/auth/verify?token=' + encodeURIComponent(token)); },
    resetRequest: function(payload) { return _post('/api/auth/reset-password/request', payload); },
    resetConfirm: function(payload) { return _post('/api/auth/reset-password/confirm', payload); },
  },

  // Market data
  market: {
    ohlcv: function(symbol, timeframe, limit) {
      return _get('/api/market/ohlcv?symbol=' + encodeURIComponent(symbol || 'NVDA')
        + '&timeframe=' + encodeURIComponent(timeframe || '1D')
        + '&limit=' + encodeURIComponent(limit || 120));
    },
  },

  platform: {
    schemaHealth: function() { return _get('/api/v1/platform/schema-health', { scope: 'ops' }); },
    releaseHealth: function() { return _get('/api/v1/platform/release-health', { scope: 'ops' }); },
    recordUiAction: function(payload) { return _post('/api/v1/platform/ui-action/evidence', payload || {}, { scope: 'ops' }); },
    latestUiActions: function(limit) { return _get('/api/v1/platform/ui-action/evidence/latest?limit=' + encodeURIComponent(limit || 50), { scope: 'ops' }); },
    overview: function() { return _get(Q + '/platform/overview'); },
    dashboardSummary: function(provider) {
      var query = provider ? ('?provider=' + encodeURIComponent(provider)) : '';
      return _get(Q + '/platform/dashboard-summary' + query);
    },
    dashboardSecondary: function(provider) {
      var query = provider ? ('?provider=' + encodeURIComponent(provider)) : '';
      return _get(Q + '/platform/dashboard-secondary' + query);
    },
    dashboardChart: function(symbol, timeframe, provider) {
      var query = '?timeframe=' + encodeURIComponent(timeframe || '1D');
      if (symbol) query += '&symbol=' + encodeURIComponent(symbol);
      if (provider) query += '&provider=' + encodeURIComponent(provider);
      return _get(Q + '/dashboard/chart' + query);
    },
    universe: function() { return _get(Q + '/universe/default'); },
  },

  jobs: {
    list: function(params) {
      params = params || {};
      var query = '?limit=' + encodeURIComponent(params.limit || 50);
      if (params.status) query += '&status=' + encodeURIComponent(params.status);
      return _get('/api/v1/jobs' + query, { scope: 'ops' });
    },
    create: function(payload) { return _post('/api/v1/jobs', payload || {}, { scope: 'ops' }); },
    get: function(jobId) { return _get('/api/v1/jobs/' + encodeURIComponent(jobId), { scope: 'ops' }); },
    cancel: function(jobId) { return _post('/api/v1/jobs/' + encodeURIComponent(jobId) + '/cancel', {}, { scope: 'ops' }); },
    retry: function(jobId) { return _post('/api/v1/jobs/' + encodeURIComponent(jobId) + '/retry', {}, { scope: 'ops' }); },
    logs: function(jobId) { return _get('/api/v1/jobs/' + encodeURIComponent(jobId) + '/logs', { scope: 'ops' }); },
  },

  dataConfig: {
    center: function() { return _get('/api/v1/data/config-center', { scope: 'ops' }); },
    saveProvider: function(payload) { return _post('/api/v1/data/config-center/providers', payload || {}, { scope: 'ops' }); },
  },

  blueprint: {
    capabilities: function() { return _get(Q + '/capabilities'); },
    analysisRun: function(payload) { return _post(Q + '/analysis/run', payload || {}); },
    modelTrain: function(payload) { return _post(Q + '/models/train', payload || {}); },
    modelPredict: function(payload) { return _post(Q + '/models/predict', payload || {}); },
    dataPipelineRun: function(payload) { return _post(Q + '/data/pipeline/run', payload || {}); },
    riskEvaluate: function(payload) { return _post(Q + '/risk/evaluate', payload || {}); },
    advancedBacktestRun: function(payload) { return _post(Q + '/backtest/advanced/run', payload || {}); },
    infrastructureCheck: function(payload) { return _post(Q + '/infrastructure/check', payload || {}); },
    reportingBuild: function(payload) { return _post(Q + '/reporting/build', payload || {}); },
  },

  agent: {
    newSession: function(sessionId, userId) {
      var query = '?session_id=' + encodeURIComponent(sessionId || '');
      if (userId) query += '&user_id=' + encodeURIComponent(userId);
      return _post('/session' + query, undefined);
    },
    history: function(sessionId, limit) {
      return _get('/history/' + encodeURIComponent(sessionId) + '?limit=' + encodeURIComponent(limit || 20));
    },
    analyze: function(payload) { return _post('/agent/analyze', payload); },
    esgScore: function(payload) { return _post('/agent/esg-score', payload); },
  },

  research: {
    context: function(symbol, provider, limit) {
      var query = '?provider=' + encodeURIComponent(provider || 'auto') + '&limit=' + encodeURIComponent(limit || 6);
      if (symbol) query += '&symbol=' + encodeURIComponent(symbol);
      return _get(Q + '/research/context' + query);
    },
    run: function(payload) { return _post(Q + '/research/run', payload); },
    buildDataset: function(payload) { return _post(Q + '/research/datasets/build', payload || {}); },
    datasets: function(limit) { return _get(Q + '/research/datasets?limit=' + encodeURIComponent(limit || 20)); },
    qualityChecks: function(payload) { return _post(Q + '/research/quality/checks', payload || {}); },
  },
  portfolio: { optimize: function(payload) { return _post(Q + '/portfolio/optimize', payload); } },

  p1: {
    status: function() { return _get(Q + '/p1/status'); },
    run: function(payload) { return _post(Q + '/p1/stack/run', payload); },
  },

  p2: {
    status: function() { return _get(Q + '/p2/status'); },
    run: function(payload) { return _post(Q + '/p2/decision/run', payload); },
  },

  backtests: {
    list: function() { return _get(Q + '/backtests'); },
    get: function(id) { return _get(Q + '/backtests/' + id); },
    run: function(payload) { return _post(Q + '/backtests/run', payload); },
    sweep: function(payload) { return _post(Q + '/backtests/sweep', payload || {}); },
    listSweeps: function(limit) { return _get(Q + '/backtests/sweep?limit=' + encodeURIComponent(limit || 20)); },
    getSweep: function(id) { return _get(Q + '/backtests/sweep/' + id); },
  },

  reports: {
    tearsheet: function(backtestId) { return _get(Q + '/reports/tearsheet/' + encodeURIComponent(backtestId)); },
  },

  execution: {
    paper: function(payload) { return _post(Q + '/execution/paper', payload, { scope: 'execution' }); },
    run: function(payload) { return _post(Q + '/execution/run', payload, { scope: 'execution' }); },
    brokers: function() { return _get(Q + '/execution/brokers', { scope: 'execution' }); },
    account: function(broker, mode) {
      return _get(
        Q + '/execution/account?broker=' + encodeURIComponent(broker || 'alpaca') + '&mode=' + encodeURIComponent(mode || 'paper'),
        { scope: 'execution' }
      );
    },
    controls: function() { return _get(Q + '/execution/controls', { scope: 'execution' }); },
    killSwitch: function(enabled, reason) {
      return _post(
        Q + '/execution/kill-switch',
        { enabled: !!enabled, reason: reason || '' },
        { scope: 'execution' }
      );
    },
    monitor: function(broker, executionId, limit, mode) {
      var query = '?broker=' + encodeURIComponent(broker || 'alpaca')
        + '&limit=' + encodeURIComponent(limit || 20)
        + '&mode=' + encodeURIComponent(mode || 'paper');
      if (executionId) query += '&execution_id=' + encodeURIComponent(executionId);
      return _get(Q + '/execution/monitor' + query, { scope: 'execution' });
    },
    orders: function(broker, status, limit, mode) {
      return _get(
        Q + '/execution/orders?broker=' + encodeURIComponent(broker || 'alpaca')
          + '&status=' + encodeURIComponent(status || 'all')
          + '&limit=' + encodeURIComponent(limit || 50)
          + '&mode=' + encodeURIComponent(mode || 'paper'),
        { scope: 'execution' }
      );
    },
    cancel: function(orderId, payload) {
      return _post(Q + '/execution/orders/' + orderId + '/cancel', payload, { scope: 'execution' });
    },
    retry: function(orderId, payload) {
      return _post(Q + '/execution/orders/' + orderId + '/retry', payload, { scope: 'execution' });
    },
    journal: function(executionId) {
      return _get(Q + '/execution/journal/' + executionId, { scope: 'execution' });
    },
    syncJournal: function(executionId, broker) {
      return _post(Q + '/execution/journal/' + executionId + '/sync', { broker: broker }, { scope: 'execution' });
    },
    positions: function(broker, mode) {
      return _get(
        Q + '/execution/positions?broker=' + encodeURIComponent(broker || 'alpaca') + '&mode=' + encodeURIComponent(mode || 'paper'),
        { scope: 'execution' }
      );
    },
  },

  workflows: {
    runPaperStrategy: function(payload) {
      return _post(Q + '/workflows/paper-strategy/run', payload || {}, { scope: 'execution' });
    },
    getPaperStrategy: function(workflowId) {
      return _get(Q + '/workflows/paper-strategy/' + encodeURIComponent(workflowId), { scope: 'execution' });
    },
  },

  paper: {
    performance: function(windowDays) {
      return _get(Q + '/paper/performance?window_days=' + encodeURIComponent(windowDays || 90), { scope: 'execution' });
    },
    snapshot: function(payload) {
      return _post(Q + '/paper/performance/snapshot', payload || {}, { scope: 'execution' });
    },
    backfill: function(payload) {
      return _post(Q + '/paper/performance/backfill', payload || {}, { scope: 'execution' });
    },
    dailyDigest: function(phase, sessionDate) {
      var query = '?phase=' + encodeURIComponent(phase || 'postclose');
      if (sessionDate) query += '&session_date=' + encodeURIComponent(sessionDate);
      return _get(Q + '/paper/daily-digest/latest' + query, { scope: 'execution' });
    },
    sendDailyDigest: function(payload) {
      return _post(Q + '/paper/daily-digest/send', payload || {}, { scope: 'execution' });
    },
    weeklyDigest: function(windowDays, sessionDate) {
      var query = '?window_days=' + encodeURIComponent(windowDays || 7);
      if (sessionDate) query += '&session_date=' + encodeURIComponent(sessionDate);
      return _get(Q + '/paper/weekly-digest/latest' + query, { scope: 'execution' });
    },
    sendWeeklyDigest: function(payload) {
      return _post(Q + '/paper/weekly-digest/send', payload || {}, { scope: 'execution' });
    },
    latestSessionEvidence: function() {
      return _get(Q + '/session-evidence/latest', { scope: 'execution' });
    },
    sessionEvidence: function(sessionDate) {
      return _get(Q + '/session-evidence/' + encodeURIComponent(sessionDate || ''), { scope: 'execution' });
    },
    reconcileAlpacaPaper: function(payload) {
      return _post(Q + '/execution/reconcile/alpaca-paper', payload || {}, { scope: 'execution' });
    },
    backupStorage: function(payload) {
      return _post(Q + '/storage/backup', payload || {}, { scope: 'execution' });
    },
    submitLocks: function(params) {
      params = params || {};
      var query = '?limit=' + encodeURIComponent(params.limit || 100);
      if (params.session_date) query += '&session_date=' + encodeURIComponent(params.session_date);
      if (params.status) query += '&status=' + encodeURIComponent(params.status);
      return _get(Q + '/submit-locks' + query, { scope: 'execution' });
    },
    outcomes: function(params) {
      params = params || {};
      var query = '?limit=' + encodeURIComponent(params.limit || 200);
      if (params.record_kind) query += '&record_kind=' + encodeURIComponent(params.record_kind);
      if (params.status) query += '&status=' + encodeURIComponent(params.status);
      if (params.symbol) query += '&symbol=' + encodeURIComponent(params.symbol);
      return _get(Q + '/paper/outcomes' + query, { scope: 'execution' });
    },
    settleOutcomes: function(payload) {
      return _post(Q + '/paper/outcomes/settle', payload || {}, { scope: 'execution' });
    },
  },

  promotion: {
    report: function(windowDays) {
      return _get(Q + '/promotion/report?window_days=' + encodeURIComponent(windowDays || 90), { scope: 'execution' });
    },
    evaluate: function(payload) {
      return _post(Q + '/promotion/evaluate', payload || {}, { scope: 'execution' });
    },
    timeline: function(limit) {
      return _get(Q + '/promotion/timeline?limit=' + encodeURIComponent(limit || 50), { scope: 'execution' });
    },
  },

  models: {
    runShadowRetrain: function(payload) {
      return _post(Q + '/models/shadow-retrain/run', payload || {}, { scope: 'execution' });
    },
    latestShadowRetrain: function() {
      return _get(Q + '/models/shadow-retrain/latest', { scope: 'execution' });
    },
  },

  deployment: {
    preflight: function(profile, dryRun) {
      var query = '?profile=' + encodeURIComponent(profile || 'paper_cloud');
      if (dryRun) query += '&dry_run=true';
      return _get(Q + '/deployment/preflight' + query, { scope: 'execution' });
    },
    evaluatePreflight: function(profile) {
      return _post(Q + '/deployment/preflight/evaluate?profile=' + encodeURIComponent(profile || 'paper_cloud'), {}, { scope: 'execution' });
    },
  },

  tradingCalendar: {
    status: function() {
      return _get(Q + '/trading-calendar/status', { scope: 'execution' });
    },
  },

  observability: {
    paperWorkflow: function(windowDays) {
      return _get(Q + '/observability/paper-workflow?window_days=' + encodeURIComponent(windowDays || 30), { scope: 'execution' });
    },
    paperWorkflowSlo: function(windowDays) {
      return _get(Q + '/slo/paper-workflow?window_days=' + encodeURIComponent(windowDays || 30), { scope: 'execution' });
    },
    evaluatePaperWorkflow: function(windowDays) {
      return _post(Q + '/observability/paper-workflow/evaluate?window_days=' + encodeURIComponent(windowDays || 30), {}, { scope: 'execution' });
    },
  },

  validation: {
    run: function(payload) { return _post(Q + '/validation/run', payload, { scope: 'execution' }); },
  },

  quantRL: {
    overview: function(params) {
      params = params || {};
      var query = '?limit=' + encodeURIComponent(params.limit || 20)
        + '&offset=' + encodeURIComponent(params.offset || 0);
      if (params.includeEligibility) query += '&include_eligibility=true';
      if (params.includeBindings) query += '&include_bindings=true';
      if (params.includeArtifacts === false) query += '&include_artifacts=false';
      if (params.includeOutputStatus) query += '&include_output_status=true';
      return _get(Q + '/rl/overview' + query);
    },
    runs: function() { return _get(Q + '/rl/runs'); },
    buildDataset: function(payload) { return _post(Q + '/rl/datasets/build', payload); },
    buildRecipeDataset: function(payload) { return _post(Q + '/rl/recipes/build', payload); },
    search: function(payload) { return _post(Q + '/rl/search', payload); },
    buildDemoDataset: function(payload) { return _post(Q + '/rl/datasets/demo', payload); },
    train: function(payload) { return _post(Q + '/rl/train', payload); },
    backtest: function(payload) { return _post(Q + '/rl/backtest', payload); },
    promote: function(payload) { return _post(Q + '/rl/promote', payload || {}); },
  },

  experiments: {
    list: function() { return _get(Q + '/experiments'); },
  },

  intelligence: {
    scan: function(payload) { return _post(Q + '/intelligence/scan', payload || {}); },
    evidence: function(symbol, limit) {
      var query = '?limit=' + encodeURIComponent(limit || 20);
      if (symbol) query += '&symbol=' + encodeURIComponent(symbol);
      return _get(Q + '/intelligence/evidence' + query);
    },
  },

  factors: {
    discover: function(payload) { return _post(Q + '/factors/discover', payload || {}); },
    registry: function(limit) { return _get(Q + '/factors/registry?limit=' + encodeURIComponent(limit || 50)); },
  },

  marketDepth: {
    status: function(symbols, requireL2) {
      var query = '?require_l2=' + encodeURIComponent(requireL2 ? 'true' : 'false');
      if (symbols && symbols.length) query += '&symbols=' + encodeURIComponent(Array.isArray(symbols) ? symbols.join(',') : symbols);
      return _get(Q + '/market-depth/status' + query);
    },
    replay: function(payload) { return _post(Q + '/market-depth/replay', payload || {}); },
    getReplay: function(sessionId) { return _get(Q + '/market-depth/replay/' + encodeURIComponent(sessionId)); },
    latest: function(symbol) { return _get(Q + '/market-depth/latest?symbol=' + encodeURIComponent(symbol || 'AAPL')); },
  },

  factorLab: {
    discover: function(payload) { return _post(Q + '/factors/discover', payload || {}); },
    registry: function(limit) { return _get(Q + '/factors/registry?limit=' + encodeURIComponent(limit || 50)); },
  },

  decision: {
    explain: function(payload) { return _post(Q + '/decision/explain', payload || {}); },
    auditTrail: function(symbol, limit) {
      var query = '?limit=' + encodeURIComponent(limit || 20);
      if (symbol) query += '&symbol=' + encodeURIComponent(symbol);
      return _get(Q + '/decision/audit-trail' + query);
    },
  },

  simulate: {
    scenario: function(payload) { return _post(Q + '/simulate/scenario', payload || {}); },
  },

  simulation: {
    run: function(payload) { return _post(Q + '/simulate/scenario', payload || {}); },
  },

  outcomes: {
    evaluate: function(payload) { return _post(Q + '/outcomes/evaluate', payload || {}); },
  },

  connectors: {
    registry: function() { return _get('/api/v1/connectors/registry'); },
    health: function(providers, live) {
      var query = '?live=' + encodeURIComponent(live ? 'true' : 'false');
      if (providers && providers.length) query += '&providers=' + encodeURIComponent(providers.join(','));
      return _get('/api/v1/connectors/health' + query);
    },
    quota: function(providers) {
      var query = '';
      if (providers && providers.length) query = '?providers=' + encodeURIComponent(providers.join(','));
      return _get('/api/v1/connectors/quota' + query);
    },
    test: function(payload) { return _post('/api/v1/connectors/test', payload || {}); },
    liveScan: function(payload) { return _post('/api/v1/connectors/live-scan', payload || {}); },
    runs: function(limit) { return _get('/api/v1/connectors/runs?limit=' + encodeURIComponent(limit || 20)); },
  },

  trading: {
    scheduleStatus: function() { return _get('/api/v1/trading/schedule/status'); },
    watchlist: function() { return _get('/api/v1/trading/watchlist'); },
    watchlistAdd: function(payload) { return _post('/api/v1/trading/watchlist/add', payload || {}); },
    latestReview: function() { return _get('/api/v1/trading/review/latest'); },
    alertsToday: function() { return _get('/api/v1/trading/alerts/today'); },
    sentimentRun: function(payload) { return _post('/api/v1/trading/sentiment/run', payload || {}); },
    debateRun: function(payload) { return _post('/api/v1/trading/debate/run', payload || {}); },
    debateRuns: function(symbol, limit) {
      var query = '?limit=' + encodeURIComponent(limit || 20);
      if (symbol) query += '&symbol=' + encodeURIComponent(symbol);
      return _get('/api/v1/trading/debate/runs' + query);
    },
    riskEvaluate: function(payload) { return _post('/api/v1/trading/risk/evaluate', payload || {}); },
    riskBoard: function(symbol, limit) {
      var query = '?limit=' + encodeURIComponent(limit || 20);
      if (symbol) query += '&symbol=' + encodeURIComponent(symbol);
      return _get('/api/v1/trading/risk/board' + query);
    },
    cycleRun: function(payload) { return _post('/api/v1/trading/cycle/run', payload || {}, { scope: 'execution' }); },
    monitorStatus: function() { return _get('/api/v1/trading/monitor/status'); },
    monitorStart: function() { return _post('/api/v1/trading/monitor/start', {}, { scope: 'execution' }); },
    monitorStop: function() { return _post('/api/v1/trading/monitor/stop', {}, { scope: 'execution' }); },
    jobRun: function(jobName, payload) {
      return _post('/api/v1/trading/jobs/run/' + encodeURIComponent(jobName), payload || {}, { scope: 'execution' });
    },
    opsSnapshot: function() { return _get('/api/v1/trading/ops/snapshot'); },
    autopilotPolicy: function() { return _get('/api/v1/trading/autopilot/policy'); },
    saveAutopilotPolicy: function(payload) { return _post('/api/v1/trading/autopilot/policy', payload || {}, { scope: 'execution' }); },
    autopilotArm: function(payload) { return _post('/api/v1/trading/autopilot/arm', payload || { armed: true }, { scope: 'execution' }); },
    autopilotDisarm: function(payload) { return _post('/api/v1/trading/autopilot/disarm', payload || { armed: false }, { scope: 'execution' }); },
    strategies: function() { return _get('/api/v1/trading/strategies'); },
    strategyEligibility: function(symbol) {
      var query = symbol ? ('?symbol=' + encodeURIComponent(symbol)) : '';
      return _get('/api/v1/trading/strategies/eligibility' + query);
    },
    toggleStrategy: function(strategyId, payload) {
      return _post('/api/v1/trading/strategies/' + encodeURIComponent(strategyId) + '/toggle', payload || {}, { scope: 'execution' });
    },
    allocateStrategy: function(strategyId, payload) {
      return _post('/api/v1/trading/strategies/' + encodeURIComponent(strategyId) + '/allocation', payload || {}, { scope: 'execution' });
    },
    executionPathStatus: function() { return _get('/api/v1/trading/execution-path/status'); },
    safetyCenter: function() { return _get('/api/v1/trading/safety-center'); },
    automationTimeline: function() { return _get('/api/v1/trading/automation/timeline'); },
    dashboardState: function(provider) {
      var query = provider ? ('?provider=' + encodeURIComponent(provider)) : '';
      return _get('/api/v1/trading/dashboard/state' + query);
    },
    fusionStatus: function() { return _get('/api/v1/trading/fusion/status'); },
  },

  reports: {
    generate: function(payload) { return _post('/admin/reports/generate', payload, { scope: 'admin' }); },
    latest: function(reportType, company) {
      var query = '?report_type=' + encodeURIComponent(reportType || 'daily');
      if (company) query += '&company=' + encodeURIComponent(company);
      return _get('/admin/reports/latest' + query, { scope: 'admin' });
    },
    get: function(reportId, reportType) {
      var path = '/admin/reports/' + encodeURIComponent(reportId);
      if (reportType) path += '?report_type=' + encodeURIComponent(reportType);
      return _get(path, { scope: 'admin' });
    },
  },

  admin: {
    dataSync: {
      start: function(payload) { return _post('/admin/data-sources/sync', payload, { scope: 'admin' }); },
      status: function(jobId) { return _get('/admin/data-sources/sync/' + encodeURIComponent(jobId), { scope: 'admin' }); },
    },
    pushRules: {
      list: function() { return _get('/admin/push-rules', { scope: 'admin' }); },
      create: function(payload) { return _post('/admin/push-rules', payload, { scope: 'admin' }); },
      update: function(ruleId, payload) { return _put('/admin/push-rules/' + encodeURIComponent(ruleId), payload, { scope: 'admin' }); },
      remove: function(ruleId) { return _del('/admin/push-rules/' + encodeURIComponent(ruleId), { scope: 'admin' }); },
      test: function(ruleId, payload) {
        return _post('/admin/push-rules/' + encodeURIComponent(ruleId) + '/test', payload, { scope: 'admin' });
      },
    },
  },

  user: {
    subscriptions: {
      list: function(userId) {
        return _get('/user/reports/subscriptions?user_id=' + encodeURIComponent(userId || window.__ESG_USER_ID__ || 'user_123'));
      },
      create: function(payload, userId) {
        return _post('/user/reports/subscribe?user_id=' + encodeURIComponent(userId || window.__ESG_USER_ID__ || 'user_123'), payload);
      },
      update: function(subscriptionId, payload) {
        return _put('/user/reports/subscriptions/' + encodeURIComponent(subscriptionId), payload);
      },
      remove: function(subscriptionId) {
        return _del('/user/reports/subscriptions/' + encodeURIComponent(subscriptionId));
      },
    },
  },
};

// Return the latest trace id.
export function getLastTraceId() {
  return _lastTraceId;
}

export function openExecutionWS(broker, executionId, limit, onMsg, onClose, mode) {
  var wsBase = getApiBaseUrl().replace(/^https?/, 'ws');
  var url = wsBase + '/api/v1/quant/execution/live/ws?broker=' + encodeURIComponent(broker || 'alpaca')
    + '&limit=' + encodeURIComponent(limit || 20)
    + '&mode=' + encodeURIComponent(mode || 'paper');
  if (executionId) url += '&execution_id=' + encodeURIComponent(executionId);

  var apiKey = _apiKeyForScope('execution');
  if (apiKey) url += '&api_key=' + encodeURIComponent(apiKey);

  var ws = new WebSocket(url);
  ws.onmessage = function(event) {
    try { onMsg(JSON.parse(event.data)); } catch (_ignore) {}
  };
  ws.onclose = function() { if (onClose) onClose(); };
  ws.onerror = function() { if (onClose) onClose(); };
  return ws;
}

export function openMarketDepthWS(symbols, requireL2, onMsg, onClose) {
  var wsBase = getApiBaseUrl().replace(/^https?/, 'ws');
  var url = wsBase + '/api/v1/quant/market-depth/live/ws?symbols=' + encodeURIComponent(
    Array.isArray(symbols) ? symbols.join(',') : (symbols || 'AAPL')
  ) + '&require_l2=' + encodeURIComponent(requireL2 ? 'true' : 'false');
  var ws = new WebSocket(url);
  ws.onmessage = function(event) {
    try { onMsg(JSON.parse(event.data)); } catch (_ignore) {}
  };
  ws.onclose = function() { if (onClose) onClose(); };
  ws.onerror = function() { if (onClose) onClose(); };
  return ws;
}
