import { api } from '../qtapi.js?v=8';
import { computeAllIndicators, buildIndicatorsPanel, showIndicatorModal } from '../modules/indicators.js?v=8';
import { getLang, getLocale, onLangChange } from '../i18n.js?v=8';
import { createDashboardKlineRenderer } from '../modules/dashboard-kline-renderer.js?v=8';
import { ensureUiAuditLog, recordUiAuditEvent } from '../modules/ui-audit.js?v=8';

const ZOOM_SEQUENCE = ['116%', '352%', '600%'];
const ZOOM_MIN = 100;
const ZOOM_MAX = 600;
const ZOOM_STEP = 20;
const DEFAULT_INDICATORS = ['VOL'];
const HEATMAP_TFS = ['1D', '1W', '1M'];
const CHART_CACHE_TTL_MS = 45_000;
const DASHBOARD_PROVIDER_STORAGE_KEY = 'qt.dashboard.provider.v1';
const DASHBOARD_STATE_STORAGE_KEY = 'qt.dashboard.state.v1';
const DASHBOARD_CHART_STORAGE_PREFIX = 'qt.dashboard.chart.v1';

const TEXT = {
  en: {
    title: 'Platform Dashboard',
    subtitle: 'Real candles + real model projections only',
    runResearch: 'Run Research Pipeline',
    executePlan: 'Execute Plan',
    marketOpen: 'MARKET OPEN',
    marketClosed: 'MARKET CLOSED',
    portfolioNav: 'PORTFOLIO NAV',
    capitalBase: 'Capital Base',
    expectedAlpha: 'EXPECTED ALPHA',
    vsBenchmark: 'vs Benchmark',
    activeSignals: 'ACTIVE SIGNALS',
    backtestSharpe: 'BACKTEST SHARPE',
    regime: 'REGIME',
    symbols: 'symbols',
    riskOn: 'RISK-ON',
    riskOff: 'RISK-OFF',
    neutral: 'NEUTRAL',
    klineTitle: 'WATCHLIST · K-LINE ANALYSIS',
    signalSummary: 'SIGNAL SUMMARY',
    confidence: 'Confidence',
    expectedReturn: 'Expected Return',
    esgScore: 'ESG Score',
    momentum5d: '5D Model',
    riskLabel: 'Risk',
    indicators: 'TECHNICAL INDICATORS',
    indicatorsHint: 'Click any row for detail',
    aiAnalysis: 'AI ANALYSIS',
    aiPlaceholder: 'Select a projection line to inspect the backend explanation.',
    fullResearch: 'Open Research',
    heatmapTitle: 'MARKET HEATMAP · SURFACE',
    heatmapWeight: 'Weight',
    heatmapSymbols: 'Symbols',
    houseScore: 'House Score',
    livePerformance: 'LIVE PERFORMANCE · SESSION METRICS',
    topSignals: 'TOP SIGNALS · SUMMARY',
    live: 'LIVE',
    positionsTitle: 'LIVE POSITIONS · ALPACA',
    refresh: 'Refresh',
    noSignalsTitle: 'No watchlist signals',
    noSignalsText: 'Run the research pipeline to generate backend-covered symbols.',
    source: 'Source',
    prediction: 'Prediction',
    unavailable: 'Unavailable',
    available: 'Model',
    whyNotOpposite: 'Why not opposite',
    drivers: 'Drivers',
    positionUnavailable: 'Positions unavailable',
    positionHint: 'Execution API key or broker session is missing.',
    syntheticOnly: 'Degraded market feed disables projection',
    modelUnavailable: 'Model coverage unavailable for this symbol',
    realOnly: 'Real candles only',
    noProjection: 'No projection line selected',
    projectionInstruction: 'Click upper / center / lower dashed lines to open explanation.',
    directionUp: 'Direction: upside path',
    directionDown: 'Direction: downside path',
    directionFlat: 'Direction: range-bound',
    backendUnavailableTitle: 'Backend unavailable',
    backendUnavailableText: 'The API service could not be reached. Check port 8000 and refresh this page.',
    chartLoadingTitle: 'Loading chart',
    chartLoadingText: 'Fetching live candles and model coverage for the current symbol.',
    chartUnavailableText: 'Chart data is temporarily unavailable for the current symbol.',
    noAccountData: 'Awaiting live account snapshot',
    degradedTitle: 'Degraded dashboard preview',
    fallbackSymbol: 'Current Symbol',
    providerChain: 'Provider Chain',
    lastSnapshot: 'Last Snapshot',
    degradedReason: 'Degraded Reason',
    nextStep: 'Next Step',
    sourceUnknownWhy: 'Source remains unknown because no live provider has returned a valid candle payload yet.',
    providerStatus: 'Provider Status',
    degradedFrom: 'Degraded From',
    providerConnectedNoPayload: 'The provider is connected, but the current symbol or timeframe has not returned a usable candle payload yet.',
    providerNotConfigured: 'Live broker or market-data credentials are not configured for this route yet.',
    providerQuotaBlocked: 'The upstream provider rejected the request or quota is exhausted, so the dashboard is falling back.',
    cacheFallbackOnly: 'Only cache or synthetic fallback is available right now while live data recovers.',
    noSnapshot: 'No recent snapshot',
    noReason: 'No explicit degradation reason returned',
    sourceMode: 'Data Source',
    providerAuto: 'auto (alpaca-first)',
    providerAlpaca: 'alpaca',
    providerTwelveData: 'twelvedata',
    providerYfinance: 'yfinance',
    providerCache: 'cache',
    providerSynthetic: 'synthetic',
    refreshDashboard: 'Refresh dashboard state',
    switchSymbol: 'Switch symbol',
    openMarketRadar: 'Open Market Radar',
    openBacktest: 'Open Backtest',
    readyBanner: 'Chart ready',
  },
  zh: {
    title: '平台控制台',
    subtitle: '只展示真实 K 线与后端真实预测',
    runResearch: '运行研究流水线',
    executePlan: '执行计划',
    marketOpen: '市场开盘',
    marketClosed: '市场休市',
    portfolioNav: '账户净值',
    capitalBase: '资金基线',
    expectedAlpha: '预期 Alpha',
    vsBenchmark: '相对基准',
    activeSignals: '活跃信号',
    backtestSharpe: '回测夏普',
    regime: '市场状态',
    symbols: '只标的',
    riskOn: '风险偏好',
    riskOff: '风险规避',
    neutral: '中性',
    klineTitle: '观察池 · K 线分析',
    signalSummary: '信号摘要',
    confidence: '置信度',
    expectedReturn: '预期收益',
    esgScore: 'ESG 评分',
    momentum5d: '5日模型',
    riskLabel: '风险',
    indicators: '技术指标',
    indicatorsHint: '点击任意一行查看详情',
    aiAnalysis: 'AI 解释',
    aiPlaceholder: '点击 upper / center / lower 任意预测线查看解释。',
    fullResearch: '打开研究页',
    heatmapTitle: '市场热力图 · 市场表面',
    heatmapWeight: '权重',
    heatmapSymbols: '成分',
    houseScore: 'House Score',
    livePerformance: '实时表现 · 会话指标',
    topSignals: '顶部信号 · 摘要',
    live: '实时',
    positionsTitle: '实时持仓 · Alpaca',
    refresh: '刷新',
    noSignalsTitle: '暂无观察信号',
    noSignalsText: '请先运行研究流水线，生成后端覆盖标的。',
    source: '来源',
    prediction: '预测',
    unavailable: '不可用',
    available: '模型',
    whyNotOpposite: '为何不是反方向',
    drivers: '主驱动',
    positionUnavailable: '持仓暂不可用',
    positionHint: '缺少执行 API Key 或券商连接未就绪。',
    syntheticOnly: '降级行情源已禁用预测',
    modelUnavailable: '当前标的暂无真实模型覆盖',
    realOnly: '仅显示真实 K 线',
    noProjection: '尚未选中预测线',
    projectionInstruction: '点击 upper / center / lower 虚线查看解释。',
    directionUp: '方向：上行路径',
    directionDown: '方向：下行路径',
    directionFlat: '方向：震荡路径',
    backendUnavailableTitle: '后端不可用',
    backendUnavailableText: '当前无法连接 8000 API 服务，请检查后端后再刷新页面。',
    chartLoadingTitle: '图表加载中',
    chartLoadingText: '正在拉取当前标的的实时 K 线与模型覆盖。',
    chartUnavailableText: '当前标的暂无可用图表数据。',
    noAccountData: '等待实时账户快照',
    degradedTitle: '降级预览',
    fallbackSymbol: '当前标的',
    providerChain: '数据源链',
    lastSnapshot: '最近快照',
    degradedReason: '降级原因',
    nextStep: '下一步动作',
    sourceUnknownWhy: '当前 source 仍为 unknown，是因为还没有任何实时数据源返回可用 K 线载荷。',
    providerStatus: '连接状态',
    degradedFrom: '回落来源',
    providerConnectedNoPayload: '连接存在，但当前标的或周期暂时没有返回可用的 K 线载荷。',
    providerNotConfigured: '当前路由还没有可用的实时券商或行情凭证。',
    providerQuotaBlocked: '上游数据源拒绝了请求或额度耗尽，Dashboard 已进入回落链路。',
    cacheFallbackOnly: '当前只拿到了缓存或 synthetic fallback，正在等待实时行情恢复。',
    noSnapshot: '暂无最近快照',
    noReason: '后端没有返回明确的降级原因',
    sourceMode: '数据源',
    providerAuto: '自动（Alpaca 优先）',
    providerAlpaca: 'Alpaca',
    providerTwelveData: 'TwelveData',
    providerYfinance: 'yfinance',
    providerCache: '缓存',
    providerSynthetic: 'Synthetic',
    refreshDashboard: '刷新 Dashboard 状态',
    switchSymbol: '切换标的',
    openMarketRadar: '打开市场雷达',
    openBacktest: '打开回测',
    readyBanner: '图表已就绪',
  },
};
let _container = null;
let _disposeLang = null;
let _clockTimer = null;
let _renderer = null;
let _overview = null;
let _overviewError = null;
let _chartLoading = false;
let _dashboardState = null;
let _watchlist = [];
let _activeSymbol = '';
let _activeTF = '1D';
let _activeZoom = '116%';
let _activeHeatTf = '1D';
let _activeIndicators = new Set(DEFAULT_INDICATORS);
let _selectedProjection = null;
let _lastCandleResponse = {
  source: 'unknown',
  candles: [],
  indicators: {},
  projection_scenarios: {},
  projection_explanations: {},
  projected_volume: [],
  signal: null,
  prediction_disabled_reason: null,
};
let _heatmapChart = null;
let _selectedHeatmapNode = null;
let _boundClickHandler = null;
let _boundPointerDownHandler = null;
let _boundResizeHandler = null;
let _zoomHoldTimer = null;
let _zoomHoldInterval = null;
let _chartRequestSeq = 0;
let _selectedProvider = 'auto';
const _chartCache = new Map();
const _chartInflight = new Map();

function copy(key) {
  return TEXT[getLang()]?.[key] ?? TEXT.en[key] ?? key;
}

function dashboardProviderOptions() {
  return [
    { value: 'auto', label: copy('providerAuto') },
    { value: 'alpaca', label: copy('providerAlpaca') },
    { value: 'twelvedata', label: copy('providerTwelveData') },
    { value: 'yfinance', label: copy('providerYfinance') },
    { value: 'cache', label: copy('providerCache') },
    { value: 'synthetic', label: copy('providerSynthetic') },
  ];
}

function loadStoredProvider() {
  try {
    const stored = localStorage.getItem(DASHBOARD_PROVIDER_STORAGE_KEY);
    return dashboardProviderOptions().some((item) => item.value === stored) ? stored : 'auto';
  } catch {
    return 'auto';
  }
}

function persistSelectedProvider() {
  try {
    localStorage.setItem(DASHBOARD_PROVIDER_STORAGE_KEY, _selectedProvider);
  } catch {
    // Ignore storage failures in restricted browser contexts.
  }
}

function sourceChainDefault() {
  return ['alpaca', 'twelvedata', 'yfinance', 'cache', 'synthetic'];
}

function chartStorageKey(symbol, timeframe, provider = _selectedProvider) {
  return `${DASHBOARD_CHART_STORAGE_PREFIX}:${String(symbol || '').toUpperCase()}:${String(timeframe || '1D').toUpperCase()}:${provider}`;
}

function persistDashboardState(state) {
  try {
    localStorage.setItem(DASHBOARD_STATE_STORAGE_KEY, JSON.stringify({
      saved_at: Date.now(),
      payload: state,
    }));
  } catch {
    // Ignore storage failures in restricted browser contexts.
  }
}

function loadPersistedDashboardState() {
  try {
    const raw = localStorage.getItem(DASHBOARD_STATE_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return parsed?.payload || null;
  } catch {
    return null;
  }
}

function persistChartSnapshot(symbol, timeframe, provider, payload) {
  try {
    localStorage.setItem(chartStorageKey(symbol, timeframe, provider), JSON.stringify({
      saved_at: Date.now(),
      payload,
    }));
  } catch {
    // Ignore storage failures in restricted browser contexts.
  }
}

function loadPersistedChartSnapshot(symbol, timeframe, provider = _selectedProvider) {
  try {
    const raw = localStorage.getItem(chartStorageKey(symbol, timeframe, provider));
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return parsed?.payload || null;
  } catch {
    return null;
  }
}

function formatPct(value) {
  if (value == null || Number.isNaN(Number(value))) return '--';
  return `${Number(value) >= 0 ? '+' : ''}${(Number(value) * 100).toFixed(2)}%`;
}

function formatMaybePct(value) {
  if (value == null || Number.isNaN(Number(value))) return '--';
  return `${(Number(value) * 100).toFixed(2)}%`;
}

function formatNum(value, digits = 2) {
  if (value == null || Number.isNaN(Number(value))) return '--';
  return Number(value).toFixed(digits);
}

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, (ch) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  }[ch]));
}

function defaultDashboardState(overrides = {}) {
  const symbol = overrides.symbol ?? _activeSymbol ?? '';
  const sourceChain = Array.isArray(overrides.source_chain) && overrides.source_chain.length
    ? overrides.source_chain
    : sourceChainDefault();
  const phase = overrides.phase || 'loading';
  return {
    generated_at: overrides.generated_at || null,
    phase,
    ready: phase === 'ready',
    symbol,
    source: overrides.source || 'unknown',
    selected_provider: overrides.selected_provider || _selectedProvider,
    source_chain: sourceChain,
    provider_status: overrides.provider_status || {},
    degraded_from: overrides.degraded_from || null,
    fallback_preview: {
      symbol,
      source: overrides.source || 'unknown',
      source_chain: sourceChain,
      last_snapshot: overrides.fallback_preview?.last_snapshot || null,
      reason: overrides.fallback_preview?.reason || (phase === 'loading' ? ['chart_loading'] : ['chart_data_unavailable']),
      next_actions: overrides.fallback_preview?.next_actions || ['refresh_dashboard', 'switch_symbol', 'open_market_radar', 'open_backtest'],
    },
  };
}

function chartReady() {
  return Boolean(
    _activeSymbol
    && _lastCandleResponse.candles?.length
    && _lastCandleResponse.source
    && !['unknown', 'loading', 'unavailable', ''].includes(_lastCandleResponse.source),
  );
}

function reasonLabel(reason) {
  const normalized = String(reason || '').trim();
  if (!normalized) return copy('noReason');
  if (normalized.startsWith('provider_degraded_from_')) {
    return `${copy('degradedFrom')}: ${normalized.replace('provider_degraded_from_', '').toUpperCase()}`;
  }
  const map = {
    backend_unavailable: copy('backendUnavailableText'),
    chart_loading: copy('chartLoadingText'),
    chart_data_unavailable: copy('chartUnavailableText'),
    market_data_unavailable: copy('chartUnavailableText'),
    no_watchlist_signal: copy('noSignalsText'),
    source_unknown: copy('sourceUnknownWhy'),
    provider_connected_but_no_payload: copy('providerConnectedNoPayload'),
    provider_not_configured: copy('providerNotConfigured'),
    provider_quota_exceeded: copy('providerQuotaBlocked'),
    cache_or_synthetic_fallback: copy('cacheFallbackOnly'),
  };
  return map[normalized] || normalized;
}

function nextActionLabel(action) {
  const map = {
    refresh_dashboard: copy('refreshDashboard'),
    switch_symbol: copy('switchSymbol'),
    open_market_radar: copy('openMarketRadar'),
    open_backtest: copy('openBacktest'),
  };
  return map[String(action || '').trim()] || String(action || '-');
}

function snapshotLabel(snapshot) {
  if (!snapshot) return copy('noSnapshot');
  const close = snapshot.close ?? snapshot.c ?? snapshot.price;
  const date = snapshot.date ?? snapshot.t ?? snapshot.timestamp;
  if (close == null && !date) return copy('noSnapshot');
  return `${close != null ? `$${Number(close).toFixed(2)}` : '--'} · ${date ? String(date).slice(0, 16) : '--'}`;
}

function syncDashboardStateFromChart(response, symbol) {
  const source = response?.source || 'unknown';
  const sourceChain = response?.source_chain || response?.data_source_chain || _dashboardState?.source_chain || sourceChainDefault();
  const providerStatus = response?.provider_status || _dashboardState?.provider_status || {};
  const degradedFrom = response?.degraded_from || _dashboardState?.degraded_from || null;
  const ready = Boolean(symbol && response?.candles?.length && source && !['unknown', 'loading', 'unavailable', ''].includes(source));
  const reason = Array.isArray(response?.fallback_preview?.reason) ? [...response.fallback_preview.reason] : [];
  if (response?.warning) reason.push(response.warning);
  if (response?.detail) reason.push(response.detail);
  if (Array.isArray(response?.market_data_warnings)) reason.push(...response.market_data_warnings);
  if (!ready && providerStatus?.available && !response?.candles?.length) reason.push('provider_connected_but_no_payload');
  if (!ready && degradedFrom) reason.push(`provider_degraded_from_${degradedFrom}`);
  if (!ready && providerStatus?.provider === 'unavailable') reason.push('provider_not_configured');
  if (!ready && ['cache', 'synthetic'].includes(source)) reason.push('cache_or_synthetic_fallback');
  if (!ready && source === 'unknown') reason.push('source_unknown');
  if (!ready && !reason.length) reason.push(response?.prediction_disabled_reason || 'chart_data_unavailable');
  _dashboardState = defaultDashboardState({
    phase: ready ? 'ready' : (_chartLoading ? 'loading' : 'degraded'),
    symbol,
    source,
    selected_provider: response?.selected_provider || _selectedProvider,
    source_chain: sourceChain,
    provider_status: providerStatus,
    degraded_from: degradedFrom,
    fallback_preview: {
      symbol,
      source,
      source_chain: sourceChain,
      last_snapshot: response?.candles?.length ? response.candles[response.candles.length - 1] : (_dashboardState?.fallback_preview?.last_snapshot || null),
      reason,
      next_actions: ['refresh_dashboard', 'switch_symbol', 'open_market_radar', 'open_backtest'],
    },
  });
  persistDashboardState(_dashboardState);
}

function pctCls(value) {
  if (value == null || Number.isNaN(Number(value))) return '';
  if (Number(value) > 0) return 'pos';
  if (Number(value) < 0) return 'neg';
  return '';
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function parseZoomPercent(label) {
  const value = Number(String(label || '').replace('%', ''));
  return clamp(Number.isFinite(value) ? value : 116, ZOOM_MIN, ZOOM_MAX);
}

function zoomLabel(percent) {
  return `${Math.round(clamp(percent, ZOOM_MIN, ZOOM_MAX))}%`;
}

function stepZoomLabel(label, direction) {
  return zoomLabel(parseZoomPercent(label) + direction * ZOOM_STEP);
}

function normalizeZoomLabel(label) {
  return zoomLabel(parseZoomPercent(label));
}

function marketOpenLabel() {
  const now = new Date();
  const open = now.getHours() >= 9 && now.getHours() < 16;
  return { open, label: open ? copy('marketOpen') : copy('marketClosed') };
}

function activeSignal() {
  return _watchlist.find((item) => item.symbol === _activeSymbol) || _watchlist[0] || null;
}

function buildShell() {
  const market = marketOpenLabel();
  return `
    <div class="page-header">
      <div>
        <div class="page-header__title">${copy('title')}</div>
        <div class="page-header__sub" style="display:flex;gap:16px;align-items:center;flex-wrap:wrap">
          <span id="dash-clock" style="font-family:var(--f-mono);font-size:11px"></span>
          <span style="font-family:var(--f-mono);font-size:11px;color:${market.open ? 'var(--green)' : 'var(--text-dim)'}">${market.label}</span>
          <span style="font-size:11px;color:var(--text-dim)">${copy('subtitle')}</span>
        </div>
      </div>
      <div class="page-header__actions">
        <a href="#/research" class="btn btn-ghost btn-sm">${copy('runResearch')}</a>
        <a href="#/execution" class="btn btn-primary btn-sm">${copy('executePlan')}</a>
      </div>
    </div>

    <div class="metrics-row-5" id="kpi-row">${Array.from({ length: 5 }).map(() => `
      <div class="metric-card">
        <div class="metric-sheen"></div>
        <div class="metric-label skeleton" style="height:10px;width:80px;margin-bottom:12px"></div>
        <div class="metric-value skeleton" style="height:28px;width:120px"></div>
        <div class="metric-sub skeleton" style="height:10px;width:70px;margin-top:8px"></div>
      </div>
    `).join('')}</div>

    <div class="kline-wrap" id="kline-section">
      <div class="kline-header" style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px;flex-wrap:wrap">
        <span class="kline-title">${copy('klineTitle')}</span>
        <div class="kline-controls" style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;justify-content:flex-end">
          <div class="tf-tabs" id="tf-tabs">${['1D', '1W', '1M', '3M', '1Y'].map((tf) => `
            <button type="button" class="tf-tab${tf === _activeTF ? ' active' : ''}" data-tf="${tf}">${tf}</button>
          `).join('')}</div>
          <label class="dashboard-provider-switch">
            <span class="dashboard-provider-switch__label">${copy('sourceMode')}</span>
            <select id="dashboard-provider-select" class="dashboard-provider-switch__select">
              ${dashboardProviderOptions().map((option) => `
                <option value="${option.value}" ${option.value === _selectedProvider ? 'selected' : ''}>${option.label}</option>
              `).join('')}
            </select>
          </label>
          <div style="display:flex;gap:4px" id="ind-btns">${['MA20', 'MA60', 'BOLL', 'VOL'].map((ind) => `
            <button type="button" class="ind-btn${_activeIndicators.has(ind) ? ' active' : ''}" data-ind="${ind}">${ind}</button>
          `).join('')}</div>
          <div style="display:flex;align-items:center;gap:6px">
            <button type="button" class="ind-btn" id="zoom-out-btn" aria-label="zoom out">-</button>
            <span class="zoom-readout" id="zoom-readout" title="Continuous zoom 100%-600%">
              <span class="zoom-readout__label">Zoom</span>
              <span class="zoom-readout__value">${_activeZoom}</span>
            </span>
            <div class="tf-tabs" id="zoom-tabs">${ZOOM_SEQUENCE.map((zoom) => `
              <button type="button" class="tf-tab${zoom === _activeZoom ? ' active' : ''}" data-zoom="${zoom}">${zoom}</button>
            `).join('')}</div>
            <button type="button" class="ind-btn" id="zoom-in-btn" aria-label="zoom in">+</button>
          </div>
        </div>
      </div>

      <div class="symbol-chips-row" id="symbol-chips"></div>
      <div id="dashboard-health-banner" class="dashboard-degraded-banner" hidden></div>

      <div class="kline-canvas-wrap" style="position:relative;min-height:560px;padding:0 0 12px">
        <canvas id="kline-canvas" height="560"></canvas>
        <div id="kline-status-note" class="dashboard-status-note"></div>
        <div id="kline-legend" style="position:absolute;top:18px;right:18px;z-index:2"></div>
        <div id="kline-projection-float" style="display:none;position:absolute;z-index:3;pointer-events:none"></div>
      </div>

      <div class="kline-footer">
        <div class="kline-panel">
          <div class="kline-panel-title"><span class="live-dot"></span>${copy('signalSummary')}</div>
          <div id="signal-summary">
            <div class="sig-v2-wrap">
              <div class="sig-v2-hero">
                <div class="signal-badge-large neutral" id="signal-badge">${copy('neutral')}</div>
                <div class="sig-v2-sym" id="sig-v2-sym">--</div>
              </div>
              <div class="sig-v2-grid">
                <div class="sig-v2-cell">
                  <div class="sig-v2-lbl">${copy('confidence')}</div>
                  <div class="sig-v2-val" id="signal-conf" style="color:var(--amber)">--</div>
                </div>
                <div class="sig-v2-cell">
                  <div class="sig-v2-lbl">${copy('expectedReturn')}</div>
                  <div class="sig-v2-val" id="signal-ret" style="color:var(--green)">--</div>
                </div>
                <div class="sig-v2-cell">
                  <div class="sig-v2-lbl">${copy('esgScore')}</div>
                  <div class="sig-v2-val" id="sig-v2-esg" style="color:var(--cyan)">--</div>
                </div>
                <div class="sig-v2-cell">
                  <div class="sig-v2-lbl">${copy('momentum5d')}</div>
                  <div class="sig-v2-val" id="sig-v2-mom">--</div>
                </div>
              </div>
              <div class="sig-v2-gauge-row">
                <span class="sig-v2-gl">${copy('riskLabel')}</span>
                <div class="sig-v2-track"><div class="sig-v2-fill" id="sig-v2-gauge" style="width:50%"></div></div>
                <span class="sig-v2-gval" id="sig-v2-gval">50%</span>
              </div>
              <div class="sig-v2-tags">
                <span class="sig-v2-tag" id="sig-v2-sector">--</span>
                <span class="sig-v2-tag sig-v2-tag--regime" id="sig-v2-regime">--</span>
              </div>
              <div style="margin-top:10px;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;font:500 10px var(--f-mono)">
                <div id="signal-source-line" style="padding:8px 10px;border-radius:12px;background:rgba(255,255,255,0.03);color:var(--text-secondary)"></div>
                <div id="signal-prediction-line" style="padding:8px 10px;border-radius:12px;background:rgba(255,255,255,0.03);color:var(--text-secondary)"></div>
              </div>
            </div>
          </div>
        </div>

        <div class="kline-panel kline-panel--ind">
          <div class="kline-panel-title" style="display:flex;justify-content:space-between;align-items:center">
            <span>${copy('indicators')}</span>
            <span style="font-size:9px;color:var(--text-dim);font-family:var(--f-mono)">${copy('indicatorsHint')}</span>
          </div>
          <div id="tech-indicators" style="overflow-y:auto;max-height:340px"></div>
        </div>

        <div class="kline-panel">
          <div class="kline-panel-title" style="color:var(--purple)">${copy('aiAnalysis')}</div>
          <div id="ai-analysis" style="font-family:var(--f-mono);font-size:11px;line-height:1.8;color:var(--text-secondary)">${copy('aiPlaceholder')}</div>
          <div style="margin-top:12px">
            <a href="#/research" class="btn btn-ghost btn-sm" style="width:100%;justify-content:center">${copy('fullResearch')}</a>
          </div>
        </div>
      </div>
    </div>

    <div class="heatmap-wrap" id="heatmap-section">
      <div class="heatmap-header">
        <span class="kline-title">${copy('heatmapTitle')}</span>
        <div class="tf-tabs" id="heat-tf-tabs">${HEATMAP_TFS.map((tf) => `
          <button type="button" class="tf-tab${tf === _activeHeatTf ? ' active' : ''}" data-heat-tf="${tf}">${tf}</button>
        `).join('')}</div>
      </div>
      <div class="heatmap-canvas-container heatmap-chart-container">
        <div id="heatmap-chart" class="heatmap-chart" role="img" aria-label="${copy('heatmapTitle')}"></div>
        <div class="heatmap-tooltip" id="heatmap-popup"></div>
      </div>
    </div>

    <div class="grid-sidebar-wide" style="margin-bottom:16px">
      <div class="card">
        <div class="card-header">
          <span class="card-title">${copy('livePerformance')}</span>
          <div class="live-pill" style="font-size:8px;padding:2px 8px">${copy('live')}</div>
        </div>
        <div id="sparkline-wrap" class="sparkline-stage">
          <canvas id="equity-sparkline" height="96" style="width:100%;display:block"></canvas>
        </div>
        <div style="padding:12px 16px;border-top:1px solid var(--border-subtle)">
          <div id="perf-metrics-grid" style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px 20px"></div>
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <span class="card-title">${copy('topSignals')}</span>
          <a href="#/research" class="btn btn-ghost btn-sm">${copy('fullResearch')}</a>
        </div>
        <div id="signals-body"></div>
      </div>
    </div>

    <div class="card" id="positions-section">
      <div class="card-header">
        <span class="card-title">${copy('positionsTitle')}</span>
        <div style="display:flex;gap:8px;align-items:center">
          <span class="text-xs text-muted font-mono" id="pos-timestamp"></span>
          <button class="btn btn-ghost btn-sm" id="btn-refresh-pos">${copy('refresh')}</button>
        </div>
      </div>
      <div id="positions-body"></div>
    </div>
  `;
}

function normalizedWatchlist(data) {
  const input = Array.isArray(data?.watchlist_signals) && data.watchlist_signals.length
    ? data.watchlist_signals
    : Array.isArray(data?.top_signals) ? data.top_signals : [];
  return input.map((signal, index) => ({
    market_data_source: signal.market_data_source || 'unavailable',
    prediction_mode: signal.prediction_mode || 'unavailable',
    projection_basis_return: signal.projection_basis_return ?? null,
    projection_scenarios: signal.projection_scenarios || {},
    house_score: signal.house_score ?? signal.overall_score ?? 0,
    house_grade: signal.house_grade || '--',
    formula_version: signal.formula_version || '',
    pillar_breakdown: signal.pillar_breakdown || {},
    disclosure_confidence: signal.disclosure_confidence ?? null,
    controversy_penalty: signal.controversy_penalty ?? null,
    data_gap_penalty: signal.data_gap_penalty ?? null,
    materiality_adjustment: signal.materiality_adjustment ?? null,
    trend_bonus: signal.trend_bonus ?? null,
    house_explanation: signal.house_explanation || '',
    factor_scores: signal.factor_scores || [],
    catalysts: signal.catalysts || [],
    data_lineage: signal.data_lineage || [],
    regime_label: signal.regime_label || 'neutral',
    company_name: signal.company_name || signal.symbol,
    sector: signal.sector || 'Unknown',
    thesis: signal.thesis || `${signal.symbol} remains on the backend watchlist.`,
    confidence: signal.confidence ?? 0.5,
    expected_return: signal.expected_return ?? 0,
    predicted_return_5d: signal.predicted_return_5d ?? null,
    predicted_volatility_10d: signal.predicted_volatility_10d ?? null,
    predicted_drawdown_20d: signal.predicted_drawdown_20d ?? null,
    decision_confidence: signal.decision_confidence ?? signal.confidence ?? 0.5,
    risk_score: signal.risk_score ?? (1 - (signal.confidence ?? 0.5)),
    overall_score: signal.overall_score ?? 0,
    action: signal.action || 'neutral',
    symbol: signal.symbol || `SIG${index + 1}`,
    e_score: signal.e_score ?? signal.overall_score ?? 0,
    s_score: signal.s_score ?? signal.overall_score ?? 0,
    g_score: signal.g_score ?? signal.overall_score ?? 0,
  }));
}

function unifiedWatchlist(data) {
  const base = normalizedWatchlist(data);
  const merged = new Map(base.map((signal) => [signal.symbol, signal]));
  const positionSymbols = Array.isArray(data?.position_symbols) ? data.position_symbols : [];
  const shouldOverlayRealPool = positionSymbols.length > 0
    || Boolean(data?.live_account_snapshot)
    || (Array.isArray(data?.heatmap_nodes) && data.heatmap_nodes.length > 0);
  const overlaySymbols = shouldOverlayRealPool
    ? [...positionSymbols, 'AAPL', 'MSFT', 'NVDA', 'GOOGL', 'NEE', 'PG', 'TSLA', 'AMZN', 'WMT', 'JPM']
    : [];
  overlaySymbols.forEach((value) => {
    const symbol = String(value || '').toUpperCase().trim();
    if (!symbol || merged.has(symbol)) return;
    merged.set(symbol, {
      market_data_source: 'alpaca',
      prediction_mode: 'unavailable',
      projection_basis_return: null,
      projection_scenarios: {},
      house_score: 0,
      house_grade: '--',
      formula_version: '',
      pillar_breakdown: {},
      disclosure_confidence: null,
      controversy_penalty: null,
      data_gap_penalty: null,
      materiality_adjustment: null,
      trend_bonus: null,
      house_explanation: '',
      factor_scores: [],
      catalysts: [],
      data_lineage: [],
      regime_label: 'neutral',
      company_name: symbol,
      sector: 'Tracked',
      thesis: `${symbol} is in the live observation pool.`,
      confidence: 0.5,
      expected_return: 0,
      predicted_return_5d: null,
      predicted_volatility_10d: null,
      predicted_drawdown_20d: null,
      decision_confidence: 0.5,
      risk_score: 0.5,
      overall_score: 0,
      action: 'neutral',
      symbol,
      e_score: 0,
      s_score: 0,
      g_score: 0,
    });
  });
  return Array.from(merged.values()).slice(0, 10);
}

function mockOverview() {
  return {
    platform_name: 'ESG Quant Intelligence System',
    watchlist_signals: [
      {
        symbol: 'NVDA',
        company_name: 'NVIDIA',
        sector: 'Technology',
        thesis: 'Model stack keeps NVIDIA in a risk-on leadership bucket with drawdown control.',
        action: 'long',
        confidence: 0.86,
        decision_confidence: 0.88,
        expected_return: 0.072,
        predicted_return_5d: 0.058,
        predicted_volatility_10d: 0.118,
        predicted_drawdown_20d: 0.084,
        overall_score: 87.4,
        e_score: 82.0,
        s_score: 79.0,
        g_score: 84.0,
        regime_label: 'risk_on',
        market_data_source: 'yfinance',
        prediction_mode: 'model',
        projection_basis_return: 0.072,
        projection_scenarios: {
          upper: { label: 'Bull Case', expected_return: 0.134, confidence: 0.88, band_source: 'volatility_plus_atr_proxy' },
          center: { label: 'Base Case', expected_return: 0.072, confidence: 0.88, band_source: 'signed_expected_return' },
          lower: { label: 'Risk Floor', expected_return: -0.012, confidence: 0.74, band_source: 'drawdown_plus_atr_proxy' },
        },
        factor_scores: [
          { name: 'momentum', value: 84, contribution: 0.32, description: 'Trend strength remains above peer median.' },
          { name: 'quality', value: 78, contribution: 0.18, description: 'Quality and balance sheet keep the center line positive.' },
          { name: 'regime_fit', value: 81, contribution: 0.15, description: 'Risk-on regime support remains active.' },
        ],
        catalysts: ['Demand cadence remains intact', 'Risk-on regime still supports high-beta leaders'],
        data_lineage: ['L0: yfinance daily bars', 'L2: P1 suite', 'L3: P2 decision stack'],
      },
      {
        symbol: 'NEE',
        company_name: 'NextEra Energy',
        sector: 'Utilities',
        thesis: 'Short-term rebound exists but the final decision remains neutral-to-defensive.',
        action: 'neutral',
        confidence: 0.74,
        decision_confidence: 0.76,
        expected_return: -0.011,
        predicted_return_5d: 0.031,
        predicted_volatility_10d: 0.094,
        predicted_drawdown_20d: 0.088,
        overall_score: 76.3,
        e_score: 83.0,
        s_score: 75.0,
        g_score: 79.0,
        regime_label: 'risk_off',
        market_data_source: 'yfinance',
        prediction_mode: 'model',
        projection_basis_return: -0.011,
        projection_scenarios: {
          upper: { label: 'Bull Case', expected_return: 0.041, confidence: 0.76, band_source: 'volatility_plus_atr_proxy' },
          center: { label: 'Base Case', expected_return: -0.011, confidence: 0.76, band_source: 'signed_expected_return' },
          lower: { label: 'Risk Floor', expected_return: -0.071, confidence: 0.81, band_source: 'drawdown_plus_atr_proxy' },
        },
        factor_scores: [
          { name: 'drawdown', value: 63, contribution: 0.24, description: 'Drawdown risk keeps the center path muted.' },
          { name: 'regime_fit', value: 58, contribution: 0.18, description: 'Risk-off regime caps upside.' },
          { name: 'esg_delta', value: 80, contribution: 0.14, description: 'ESG strength supports resilience, not aggression.' },
        ],
        catalysts: ['Defensive sector support persists', 'Short-term rebound branch conflicts with final action'],
        data_lineage: ['L0: yfinance daily bars', 'L2: P1 suite', 'L3: P2 decision stack'],
      },
      {
        symbol: 'MSFT',
        company_name: 'Microsoft',
        sector: 'Technology',
        thesis: 'Synthetic fallback should show real candles only and no projection.',
        action: 'long',
        confidence: 0.81,
        expected_return: 0.035,
        predicted_return_5d: 0.028,
        predicted_volatility_10d: 0.09,
        predicted_drawdown_20d: 0.07,
        overall_score: 82.2,
        e_score: 80.0,
        s_score: 82.0,
        g_score: 85.0,
        regime_label: 'neutral',
        market_data_source: 'synthetic',
        prediction_mode: 'unavailable',
        projection_basis_return: null,
        projection_scenarios: {},
        factor_scores: [{ name: 'quality', value: 82, contribution: 0.21, description: 'Quality remains strong.' }],
        catalysts: ['Synthetic candle path should not enable projections'],
        data_lineage: ['L0: synthetic fallback factor proxies'],
      },
    ],
    top_signals: [],
    portfolio_preview: { capital_base: null, expected_alpha: 0.084, positions: [] },
    latest_backtest: { metrics: { sharpe: 1.84, max_drawdown: -0.092, annualized_return: 0.214, hit_rate: 0.581 } },
    p1_signal_snapshot: { regime_counts: { risk_on: 1, neutral: 1, risk_off: 1 } },
    universe: { size: 3, benchmark: 'SPY' },
    sector_heatmap: [
      { name: 'Technology', value: 182, score: 84.8, change: 0.053, symbols: ['NVDA', 'MSFT'], market_data_sources: ['yfinance', 'synthetic'] },
      { name: 'Utilities', value: 74, score: 76.3, change: -0.011, symbols: ['NEE'], market_data_sources: ['yfinance'] },
    ],
  };
}

function mergeActiveSignal(nextSignal) {
  if (!nextSignal || !nextSignal.symbol) return;
  const normalized = normalizedWatchlist({ watchlist_signals: [nextSignal] })[0];
  if (!normalized) return;
  const index = _watchlist.findIndex((item) => item.symbol === normalized.symbol);
  if (index >= 0) {
    _watchlist[index] = { ..._watchlist[index], ...normalized };
  } else {
    _watchlist.unshift(normalized);
  }
}

function scenarioExplanation(signal, selectedScenarioKey) {
  if (!signal || !selectedScenarioKey) return null;
  const explanation = _lastCandleResponse.projection_explanations?.[selectedScenarioKey];
  if (explanation) return explanation;
  return null;
}

function buildSparkline(metrics = {}) {
  const annual = Number(metrics.annualized_return || 0.14);
  const sharpe = Number(metrics.sharpe || 1.2);
  const points = [];
  let value = 1;
  for (let index = 0; index < 90; index += 1) {
    const drift = annual / 252;
    const noise = (((index * 17) % 11) - 5) * 0.0007 / Math.max(sharpe, 0.5);
    value *= (1 + drift + noise);
    points.push(value);
  }
  return points;
}

function drawSparkline(canvas, metrics = {}) {
  if (!canvas) return;
  const width = canvas.parentElement?.clientWidth || 440;
  const height = 96;
  const dpr = window.devicePixelRatio || 1;
  canvas.width = width * dpr;
  canvas.height = height * dpr;
  canvas.style.width = `${width}px`;
  canvas.style.height = `${height}px`;
  const ctx = canvas.getContext('2d');
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = getComputedStyle(document.body).getPropertyValue('--bg-base').trim() || '#07070F';
  ctx.fillRect(0, 0, width, height);

  const points = buildSparkline(metrics);
  const min = Math.min(...points);
  const max = Math.max(...points);
  const x = (index) => 16 + (index / (points.length - 1)) * (width - 32);
  const y = (value) => 14 + (height - 28) - ((value - min) / Math.max(0.0001, max - min)) * (height - 28);

  ctx.strokeStyle = 'rgba(0,255,136,0.16)';
  ctx.lineWidth = 1;
  for (let row = 0; row <= 4; row += 1) {
    const yy = 12 + row * ((height - 24) / 4);
    ctx.beginPath();
    ctx.moveTo(12, yy);
    ctx.lineTo(width - 12, yy);
    ctx.stroke();
  }

  ctx.beginPath();
  points.forEach((value, index) => {
    const px = x(index);
    const py = y(value);
    if (!index) ctx.moveTo(px, py);
    else ctx.lineTo(px, py);
  });
  ctx.lineWidth = 2;
  ctx.strokeStyle = '#00FF88';
  ctx.stroke();
}

function formatCurrencyValue(value) {
  if (value == null || Number.isNaN(Number(value))) return '--';
  return `$${Number(value).toLocaleString()}`;
}

function renderHealthBanner() {
  const banner = _container.querySelector('#dashboard-health-banner');
  if (!banner) return;
  const state = _dashboardState || defaultDashboardState({ phase: _chartLoading ? 'loading' : 'degraded' });
  const fallback = state.fallback_preview || {};
  const providerStatus = state.provider_status || {};
  const reasonText = (fallback.reason || []).map(reasonLabel).join(' | ') || copy('noReason');
  const nextSteps = (fallback.next_actions || []).map(nextActionLabel).join(' · ') || copy('refreshDashboard');
  if (_overviewError) {
    banner.hidden = false;
    banner.classList.add('is-error');
    banner.innerHTML = `
      <strong>${copy('backendUnavailableTitle')}</strong>
      <span>${copy('backendUnavailableText')}</span>
      <span>${copy('nextStep')}: ${escapeHtml(nextSteps)}</span>
    `;
    return;
  }
  if (_chartLoading && chartReady()) {
    banner.hidden = true;
    banner.classList.remove('is-error');
    banner.innerHTML = '';
    return;
  }
  if (_chartLoading || state.phase === 'loading') {
    banner.hidden = false;
    banner.classList.remove('is-error');
    banner.innerHTML = `
      <strong>${copy('chartLoadingTitle')}</strong>
      <span>${copy('chartLoadingText')}</span>
      <span>${copy('providerChain')}: ${escapeHtml((state.source_chain || []).join(' -> ') || '-')}</span>
    `;
    return;
  }
  if (!chartReady()) {
    banner.hidden = false;
    banner.classList.remove('is-error');
    banner.innerHTML = `
      <strong>${copy('degradedTitle')}</strong>
      <span>${copy('source')}: ${escapeHtml(state.source || copy('unavailable'))}</span>
      <span>${copy('providerStatus')}: ${escapeHtml(providerStatus.provider || copy('unavailable'))}</span>
      <span>${copy('degradedReason')}: ${escapeHtml(reasonText)}</span>
      <span>${copy('nextStep')}: ${escapeHtml(nextSteps)}</span>
    `;
    return;
  }
  banner.hidden = true;
  banner.classList.remove('is-error');
  banner.innerHTML = '';
}

function renderChartFallbackCard() {
  const state = _dashboardState || defaultDashboardState({ phase: _chartLoading ? 'loading' : 'degraded' });
  const fallback = state.fallback_preview || {};
  const providerStatus = state.provider_status || {};
  const reasonText = (fallback.reason || []).map(reasonLabel).join(' | ') || copy('noReason');
  const nextSteps = (fallback.next_actions || []).map(nextActionLabel);
  return `
    <div class="functional-empty compact-functional-empty">
      <div>
        <div class="functional-empty__eyebrow">${copy(state.phase === 'loading' ? 'chartLoadingTitle' : 'degradedTitle')}</div>
        <h3>${copy(state.phase === 'loading' ? 'chartLoadingTitle' : 'chartUnavailableText')}</h3>
        <p>${escapeHtml(state.phase === 'loading' ? copy('chartLoadingText') : reasonText)}</p>
      </div>
      <div class="workbench-kv-list compact-kv-list">
        <div class="workbench-kv-row"><span>${copy('source')}</span><strong>${escapeHtml(state.source || copy('unavailable'))}</strong></div>
        <div class="workbench-kv-row"><span>${copy('providerStatus')}</span><strong>${escapeHtml(providerStatus.provider || copy('unavailable'))}</strong></div>
        <div class="workbench-kv-row"><span>${copy('degradedFrom')}</span><strong>${escapeHtml(state.degraded_from || '-')}</strong></div>
        <div class="workbench-kv-row"><span>${copy('fallbackSymbol')}</span><strong>${escapeHtml(fallback.symbol || _activeSymbol || '--')}</strong></div>
        <div class="workbench-kv-row"><span>${copy('providerChain')}</span><strong>${escapeHtml((fallback.source_chain || state.source_chain || []).join(' -> ') || '-')}</strong></div>
        <div class="workbench-kv-row"><span>${copy('lastSnapshot')}</span><strong>${escapeHtml(snapshotLabel(fallback.last_snapshot))}</strong></div>
        <div class="workbench-kv-row"><span>${copy('degradedReason')}</span><strong>${escapeHtml(reasonText)}</strong></div>
      </div>
      <div class="preview-step-grid">
        ${nextSteps.map((step) => `<div class="preview-step"><span>${copy('nextStep')}</span><strong>${escapeHtml(step)}</strong></div>`).join('')}
      </div>
    </div>
  `;
}

function populateKPIs() {
  const row = _container.querySelector('#kpi-row');
  if (!row) return;
  if (_overviewError) {
    row.innerHTML = [
      { label: copy('portfolioNav'), value: '--', cls: '', sub: copy('backendUnavailableTitle') },
      { label: copy('expectedAlpha'), value: '--', cls: '', sub: copy('backendUnavailableTitle') },
      { label: copy('activeSignals'), value: '--', cls: '', sub: copy('backendUnavailableTitle') },
      { label: copy('backtestSharpe'), value: '--', cls: '', sub: copy('backendUnavailableTitle') },
      { label: copy('regime'), value: '--', cls: '', sub: copy('backendUnavailableTitle') },
    ].map((item) => `
      <div class="metric-card">
        <div class="metric-sheen"></div>
        <div class="metric-label">${item.label}</div>
        <div class="metric-value ${item.cls}">${item.value}</div>
        <div class="metric-sub">${item.sub}</div>
      </div>
    `).join('');
    return;
  }
  const portfolio = _overview?.portfolio_preview || {};
  const account = _overview?.live_account_snapshot?.account || {};
  const metrics = _overview?.latest_backtest?.metrics || {};
  const signals = _watchlist;
  const longCount = signals.filter((item) => item.action === 'long').length;
  const regimeCounts = _overview?.p1_signal_snapshot?.regime_counts || {};
  const regimeLabel = regimeCounts.risk_on > regimeCounts.risk_off
    ? copy('riskOn')
    : regimeCounts.risk_off > 0
      ? copy('riskOff')
      : copy('neutral');

  const cards = [
    {
      label: copy('portfolioNav'),
      value: formatCurrencyValue(account.equity ?? portfolio.capital_base),
      cls: '',
      sub: account.equity != null || portfolio.capital_base != null ? copy('capitalBase') : copy('noAccountData'),
    },
    { label: copy('expectedAlpha'), value: formatPct(account.daily_change_pct ?? portfolio.expected_alpha), cls: pctCls(account.daily_change_pct ?? portfolio.expected_alpha), sub: copy('vsBenchmark') },
    { label: copy('activeSignals'), value: String(signals.length), cls: 'pos', sub: `${longCount} long` },
    { label: copy('backtestSharpe'), value: formatNum(metrics.sharpe), cls: Number(metrics.sharpe || 0) >= 1 ? 'pos' : '', sub: `MaxDD ${formatMaybePct(metrics.max_drawdown)}` },
    { label: copy('regime'), value: regimeLabel, cls: regimeLabel === copy('riskOff') ? 'neg' : 'pos', sub: `${(_overview?.position_symbols || []).length || _overview?.universe?.size || signals.length} ${copy('symbols')}` },
  ];

  row.innerHTML = cards.map((item) => `
    <div class="metric-card">
      <div class="metric-sheen"></div>
      <div class="metric-label">${item.label}</div>
      <div class="metric-value ${item.cls}">${item.value}</div>
      <div class="metric-sub">${item.sub}</div>
    </div>
  `).join('');
}

function populateSignalTable() {
  const body = _container.querySelector('#signals-body');
  if (!body) return;
  if (_overviewError) {
    body.innerHTML = `
      <div class="empty-state" style="min-height:180px">
        <div class="empty-state__title">${copy('backendUnavailableTitle')}</div>
        <div class="empty-state__text">${copy('backendUnavailableText')}</div>
      </div>
    `;
    return;
  }
  if (!_watchlist.length) {
    body.innerHTML = `
      <div class="empty-state" style="min-height:180px">
        <div class="empty-state__title">${copy('noSignalsTitle')}</div>
        <div class="empty-state__text">${copy('noSignalsText')}</div>
      </div>
    `;
    return;
  }

  body.innerHTML = `
    <div class="tbl-wrap">
      <table>
        <thead>
          <tr>
            <th>Symbol</th>
            <th>Action</th>
            <th>${copy('confidence')}</th>
            <th>${copy('expectedReturn')}</th>
            <th>${copy('source')}</th>
            <th>${copy('prediction')}</th>
          </tr>
        </thead>
        <tbody>
          ${_watchlist.map((signal) => `
            <tr>
              <td class="cell-symbol">${signal.symbol}</td>
              <td><span class="badge badge-${signal.action === 'long' ? 'filled' : signal.action === 'short' ? 'failed' : 'neutral'}">${signal.action.toUpperCase()}</span></td>
              <td class="cell-num ${pctCls(signal.confidence)}">${formatMaybePct(signal.confidence)}</td>
              <td class="cell-num ${pctCls(signal.expected_return)}">${formatPct(signal.expected_return)}</td>
              <td style="font-size:10px;color:var(--text-dim)">${signal.market_data_source}</td>
              <td style="font-size:10px;color:var(--text-dim)">${signal.prediction_mode === 'model' ? copy('available') : copy('unavailable')}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `;
}

function updateSignalSummary(signal) {
  if (!signal) {
    const source = _container.querySelector('#signal-source-line');
    const prediction = _container.querySelector('#signal-prediction-line');
    const sym = _container.querySelector('#sig-v2-sym');
    const conf = _container.querySelector('#signal-conf');
    const ret = _container.querySelector('#signal-ret');
    const esg = _container.querySelector('#sig-v2-esg');
    const mom = _container.querySelector('#sig-v2-mom');
    const sector = _container.querySelector('#sig-v2-sector');
    const regime = _container.querySelector('#sig-v2-regime');
    const gauge = _container.querySelector('#sig-v2-gauge');
    const gaugeValue = _container.querySelector('#sig-v2-gval');
    if (sym) sym.textContent = '--';
    if (conf) conf.textContent = '--';
    if (ret) ret.textContent = '--';
    if (esg) esg.textContent = '--';
    if (mom) mom.textContent = '--';
    if (sector) sector.textContent = '--';
    if (regime) regime.textContent = '--';
    if (gauge) gauge.style.width = '0%';
    if (gaugeValue) gaugeValue.textContent = '--';
    if (source) source.textContent = `${copy('source')}: ${copy('unavailable')}`;
    if (prediction) prediction.textContent = `${copy('prediction')}: ${copy('unavailable')}`;
    return;
  }
  const badge = _container.querySelector('#signal-badge');
  const conf = _container.querySelector('#signal-conf');
  const ret = _container.querySelector('#signal-ret');
  const sym = _container.querySelector('#sig-v2-sym');
  const esg = _container.querySelector('#sig-v2-esg');
  const mom = _container.querySelector('#sig-v2-mom');
  const gauge = _container.querySelector('#sig-v2-gauge');
  const gaugeValue = _container.querySelector('#sig-v2-gval');
  const sector = _container.querySelector('#sig-v2-sector');
  const regime = _container.querySelector('#sig-v2-regime');
  const source = _container.querySelector('#signal-source-line');
  const prediction = _container.querySelector('#signal-prediction-line');

  badge.className = `signal-badge-large ${signal.action || 'neutral'}`;
  badge.textContent = (signal.action || 'neutral').toUpperCase();
  conf.textContent = formatMaybePct(signal.confidence);
  ret.textContent = formatPct(signal.expected_return);
  sym.textContent = signal.symbol;
  esg.textContent = formatNum(signal.house_score ?? signal.overall_score);
  mom.textContent = signal.predicted_return_5d == null ? '--' : formatPct(signal.predicted_return_5d);
  mom.style.color = signal.predicted_return_5d == null ? 'var(--text-dim)' : signal.predicted_return_5d >= 0 ? 'var(--green)' : 'var(--red)';
  const inferredRisk = signal.risk_score == null
    ? (1 - Math.min(0.95, Number(signal.confidence || 0.5)))
    : Number(signal.risk_score);
  const riskPct = Math.max(8, Math.round(Math.min(0.95, Math.max(0.02, inferredRisk)) * 100));
  gauge.style.width = `${riskPct}%`;
  gaugeValue.textContent = `${riskPct}%`;
  sector.textContent = signal.sector || '--';
  const regimeText = signal.regime_label === 'risk_on' ? copy('riskOn') : signal.regime_label === 'risk_off' ? copy('riskOff') : copy('neutral');
  regime.textContent = regimeText;
  regime.className = `sig-v2-tag sig-v2-tag--regime${signal.regime_label === 'risk_on' ? ' on' : signal.regime_label === 'risk_off' ? ' off' : ''}`;
  source.textContent = `${copy('source')}: ${signal.market_data_source} · ${signal.house_grade || '--'}`;
  prediction.textContent = `${copy('prediction')}: ${signal.prediction_mode === 'model' ? copy('available') : copy('unavailable')}`;
}

function buildAnalysisModel(signal, selectedScenarioKey, candleSource) {
  if (!signal || !selectedScenarioKey || signal.prediction_mode !== 'model') return null;
  const scenario = signal.projection_scenarios?.[selectedScenarioKey];
  if (!scenario) return null;

  const explanation = scenarioExplanation(signal, selectedScenarioKey) || {};
  const topDrivers = [...(signal.factor_scores || [])]
    .sort((left, right) => Math.abs(Number(right.contribution || 0)) - Math.abs(Number(left.contribution || 0)))
    .slice(0, 3)
    .map((item) => `${item.name}: ${item.description}`);
  (explanation.drivers || []).forEach((driver) => {
    if (driver && topDrivers.length < 3) topDrivers.push(driver);
  });
  while (topDrivers.length < 2) {
    topDrivers.push('Factor blend remains aligned with the final decision score.');
  }

  const centerReturn = Number(signal.projection_scenarios?.center?.expected_return || 0);
  const shortTermReturn = Number(signal.predicted_return_5d || 0);
  const conflict = shortTermReturn !== 0 && Math.sign(shortTermReturn) !== Math.sign(centerReturn) && Math.sign(centerReturn) !== 0;
  const oppositeReason = conflict
    ? `Short-term model path is ${formatPct(shortTermReturn)}, but drawdown/regime filters keep the signed center path at ${formatPct(centerReturn)}.`
    : signal.regime_label === 'risk_off'
      ? 'Risk-off regime and drawdown constraints block the opposite bullish branch from becoming the main path.'
      : signal.regime_label === 'risk_on'
        ? 'Risk-on regime and decision score keep the opposite bearish branch from becoming the main path.'
        : 'Final action and decision stack keep the opposite branch below the center path.';

  let directionText = copy('directionFlat');
  if (Number(scenario.expected_return) > 0.002) directionText = copy('directionUp');
  if (Number(scenario.expected_return) < -0.002) directionText = copy('directionDown');

  return {
    title: explanation.title || scenario.label || selectedScenarioKey,
    directionText,
    expectedReturnText: formatPct(explanation.expected_return ?? scenario.expected_return),
    confidenceText: `${copy('confidence')}: ${formatMaybePct(explanation.confidence ?? scenario.confidence ?? signal.decision_confidence ?? signal.confidence)}`,
    sourceText: `${explanation.source || candleSource} / ${signal.market_data_source} / ${signal.prediction_mode}`,
    drivers: topDrivers,
    oppositeReason: explanation.why_not_opposite || oppositeReason,
    houseExplanation: explanation.house_explanation || signal.house_explanation || '',
    dataLineage: explanation.data_lineage || signal.data_lineage || [],
  };
}

function renderAiPanel(signal) {
  const panel = _container.querySelector('#ai-analysis');
  if (!panel) return;
  if (!signal) {
    panel.innerHTML = _overviewError ? copy('backendUnavailableText') : copy('aiPlaceholder');
    return;
  }

  if (_selectedProjection) {
    const analysis = buildAnalysisModel(signal, _selectedProjection, _lastCandleResponse.source);
    if (analysis) {
      const lineage = (analysis.dataLineage || []).slice(0, 3).join('<br>');
      panel.innerHTML = `
        <div style="display:grid;gap:8px">
          <div><strong>${analysis.title}</strong> · <span class="${pctCls(signal.projection_scenarios[_selectedProjection]?.expected_return)}">${analysis.expectedReturnText}</span></div>
          <div>${analysis.directionText}</div>
          <div>${analysis.confidenceText}</div>
          <div>${copy('source')}: ${analysis.sourceText}</div>
          <div><strong>${copy('drivers')}:</strong><br>${analysis.drivers.slice(0, 3).join('<br>')}</div>
          <div><strong>${copy('whyNotOpposite')}:</strong><br>${analysis.oppositeReason}</div>
          ${analysis.houseExplanation ? `<div><strong>${copy('houseScore')}:</strong><br>${analysis.houseExplanation}</div>` : ''}
          ${lineage ? `<div><strong>Lineage:</strong><br>${lineage}</div>` : ''}
        </div>
      `;
      return;
    }
  }

  if (_lastCandleResponse.source === 'synthetic') {
    panel.innerHTML = `
      <div>${copy('realOnly')}</div>
      <div>${copy('syntheticOnly')}</div>
      <div>${copy('source')}: degraded</div>
      <div>${signal.thesis}</div>
    `;
    return;
  }

  if (_lastCandleResponse.source === 'unavailable') {
    panel.innerHTML = `
      <div>${copy('realOnly')}</div>
      <div>Market data temporarily unavailable.</div>
      <div>${copy('source')}: unavailable</div>
      <div>${signal.thesis}</div>
    `;
    return;
  }

  if (signal.prediction_mode !== 'model' || _lastCandleResponse.prediction_disabled_reason) {
    panel.innerHTML = `
      <div>${copy('realOnly')}</div>
      <div>${copy('modelUnavailable')}</div>
      <div>${signal.thesis}</div>
      <div>${copy('projectionInstruction')}</div>
    `;
    return;
  }

  panel.innerHTML = `
    <div>${copy('noProjection')}</div>
    <div>${copy('projectionInstruction')}</div>
    <div>${copy('source')}: ${_lastCandleResponse.source} / ${signal.market_data_source}</div>
    <div>${signal.thesis}</div>
    ${signal.house_explanation ? `<div style="margin-top:8px"><strong>${copy('houseScore')}:</strong><br>${signal.house_explanation}</div>` : ''}
  `;
}

function updateIndicators(candles) {
  const panel = _container.querySelector('#tech-indicators');
  if (!panel) return;
  const indicators = computeAllIndicators(candles || []);
  _container._indicatorValues = indicators;
  _container._indicatorCandles = candles || [];
  panel.innerHTML = buildIndicatorsPanel(indicators, getLang());
}

function renderChips() {
  const chips = _container.querySelector('#symbol-chips');
  if (!chips) return;
  if (!_watchlist.length) {
    chips.innerHTML = `<div class="dashboard-empty-chip-row">${copy('noSignalsText')}</div>`;
    renderHealthBanner();
    return;
  }
  chips.innerHTML = _watchlist.map((signal) => `
    <button type="button" class="symbol-chip${signal.symbol === _activeSymbol ? ' active' : ''}" data-sym="${signal.symbol}">
      <span class="chip-ticker">${signal.symbol}</span>
      <span class="chip-chg ${pctCls(signal.expected_return)}">${formatPct(signal.expected_return)}</span>
    </button>
  `).join('');
  renderHealthBanner();
}

function renderPerformancePanel() {
  const metrics = _overview?.latest_backtest?.metrics || {};
  drawSparkline(_container.querySelector('#equity-sparkline'), metrics);
  const grid = _container.querySelector('#perf-metrics-grid');
  if (!grid) return;
  const signal = activeSignal();
  const items = [
    { label: 'Sharpe', value: formatNum(metrics.sharpe), color: Number(metrics.sharpe || 0) >= 1 ? 'var(--green)' : 'var(--amber)' },
    { label: 'Annual Return', value: formatMaybePct(metrics.annualized_return), color: 'var(--green)' },
    { label: 'Max Drawdown', value: formatMaybePct(metrics.max_drawdown), color: Number(metrics.max_drawdown || 0) < -0.14 ? 'var(--red)' : 'var(--amber)' },
    { label: 'Hit Rate', value: formatMaybePct(metrics.hit_rate), color: 'var(--cyan)' },
    { label: 'Active Symbol', value: signal?.symbol || '--', color: 'var(--text-primary)' },
    { label: 'Zoom', value: _activeZoom, color: 'var(--text-secondary)' },
  ];
  grid.innerHTML = items.map((item) => `
    <div style="padding:6px 0;border-bottom:1px solid rgba(255,255,255,0.03)">
      <div style="font-family:var(--f-mono);font-size:9px;color:var(--text-dim);text-transform:uppercase;letter-spacing:0.06em">${item.label}</div>
      <div style="font-family:var(--f-display);font-size:15px;font-weight:700;color:${item.color};margin-top:2px">${item.value}</div>
    </div>
  `).join('');
}

function heatmapData() {
  const multiplier = _activeHeatTf === '1W' ? 1.35 : _activeHeatTf === '1M' ? 1.9 : 1;
  if (Array.isArray(_overview?.heatmap_nodes) && _overview.heatmap_nodes.length) {
    return _overview.heatmap_nodes.map((node) => ({
      name: node.symbol || node.name,
      weight: Math.max(8, Number(node.weight || node.value || 0)),
      delta: Number(node.change || 0) * 100 * multiplier,
      score: Number(node.score || 0),
      symbols: [node.symbol || node.name],
      marketData: node.source || 'mixed',
      children: [{
        name: node.symbol || node.name,
        value: Math.max(8, Number(node.weight || node.value || 0)),
        change: Number(node.change || 0),
        score: Number(node.score || 0),
        action: Number(node.change || 0) >= 0 ? 'long' : 'neutral',
      }],
    }));
  }
  if (Array.isArray(_overview?.sector_heatmap) && _overview.sector_heatmap.length) {
    return _overview.sector_heatmap.map((sector) => ({
      name: sector.name,
      weight: Math.max(8, Number(sector.value || 0)),
      delta: Number(sector.change || 0) * 100 * multiplier,
      score: Number(sector.score || 0),
      symbols: sector.symbols || [],
      marketData: (sector.market_data_sources || []).join(', ') || 'mixed',
      children: sector.children || [],
    }));
  }
  return _watchlist.map((signal) => ({
    name: signal.sector || signal.symbol,
    weight: Math.max(8, Number(signal.house_score ?? signal.overall_score ?? 0)),
    delta: Number(signal.expected_return || 0) * 100 * multiplier,
    score: Number(signal.house_score ?? signal.overall_score ?? 0),
    symbols: [signal.symbol],
    marketData: signal.market_data_source,
    children: [{
      name: signal.symbol,
      value: Math.max(8, Number(signal.confidence || 0) * 100),
      change: Number(signal.expected_return || 0),
      score: Number(signal.house_score ?? signal.overall_score ?? 0),
      action: signal.action,
    }],
  }));
}

function heatmapColor(delta) {
  const value = clamp(Number(delta || 0), -8, 8);
  const alpha = clamp(Math.abs(value) / 8, 0.22, 0.76);
  return value >= 0 ? `rgba(0,255,136,${alpha})` : `rgba(255,77,109,${alpha})`;
}

function heatmapBorderColor(delta) {
  return Number(delta || 0) >= 0 ? 'rgba(0,255,136,0.72)' : 'rgba(255,77,109,0.72)';
}

function normalizeHeatmapNode(item, index, depth = 0) {
  const nodeId = `${depth}:${index}:${item.name}`;
  const delta = Number(item.delta || 0);
  const value = Math.max(1, Number(item.weight || item.value || 1));
  const children = Array.isArray(item.children) && item.children.length > 1
    ? item.children.slice(0, 12).map((child, childIndex) => normalizeHeatmapNode({
      name: child.name || child.symbol || `${item.name}-${childIndex + 1}`,
      weight: child.value || child.weight || value / Math.max(item.children.length, 1),
      delta: Number(child.change || child.delta || 0) * 100,
      score: child.score ?? item.score,
      symbols: [child.name || child.symbol].filter(Boolean),
      marketData: item.marketData,
    }, childIndex, depth + 1))
    : undefined;

  return {
    id: nodeId,
    name: item.name,
    value,
    children,
    itemStyle: {
      color: heatmapColor(delta),
      borderColor: heatmapBorderColor(delta),
      borderWidth: 1,
      gapWidth: 5,
    },
    emphasis: {
      itemStyle: {
        borderColor: '#f0f4ff',
        borderWidth: 2,
        shadowColor: Number(delta || 0) >= 0 ? 'rgba(0,255,136,0.32)' : 'rgba(255,77,109,0.32)',
        shadowBlur: 18,
      },
    },
    __nodeId: nodeId,
    __raw: {
      ...item,
      delta,
      weight: value,
    },
  };
}

function heatmapFormatter(params) {
  const raw = params?.data?.__raw || {};
  const value = Number(raw.weight || params.value || 0);
  const delta = Number(raw.delta || 0);
  const sign = delta >= 0 ? '+' : '';
  if (value < 18) return `${params.name}`;
  if (value < 34) return `${params.name}\n${sign}${delta.toFixed(1)}%`;
  return [
    `{name|${params.name}}`,
    `{delta|${sign}${delta.toFixed(1)}%}`,
    `{meta|${copy('houseScore')}: ${formatNum(raw.score)}}`,
    `{meta|${copy('heatmapWeight')}: ${formatNum(value, 0)}}`,
  ].join('\n');
}

function heatmapTooltipFormatter(params) {
  const raw = params?.data?.__raw || {};
  const delta = Number(raw.delta || 0);
  return `
    <div class="heatmap-echarts-tooltip">
      <strong>${params.name || raw.name || '--'}</strong>
      <span class="${pctCls(delta / 100)}">${delta >= 0 ? '+' : ''}${delta.toFixed(2)}%</span>
      <span>${copy('houseScore')}: ${formatNum(raw.score)}</span>
      <span>${copy('heatmapWeight')}: ${formatNum(raw.weight, 0)}</span>
      <span>${copy('source')}: ${raw.marketData || 'mixed'}</span>
      <span>${copy('heatmapSymbols')}: ${(raw.symbols || []).join(', ') || '--'}</span>
    </div>
  `;
}

function writeHeatmapAuditState(data) {
  window.__dashboardAuditState = {
    ...(window.__dashboardAuditState || {}),
    heatmap: {
      timeframe: _activeHeatTf,
      tileCount: data.length,
      selected: _selectedHeatmapNode?.name || null,
      renderer: window.echarts ? 'echarts_treemap' : 'unavailable',
      symbols: data.flatMap((item) => item.symbols || []).filter(Boolean).slice(0, 40),
    },
  };
}

function positionHeatmapPopup(params) {
  const popup = _container?.querySelector('#heatmap-popup');
  const chartEl = _container?.querySelector('#heatmap-chart');
  if (!popup || !chartEl || !params?.data?.__raw) return;
  const raw = params.data.__raw;
  const event = params.event?.event;
  const bounds = chartEl.getBoundingClientRect();
  const localX = event ? event.clientX - bounds.left : bounds.width * 0.5;
  const localY = event ? event.clientY - bounds.top : bounds.height * 0.5;
  const width = 278;
  popup.style.display = 'block';
  popup.style.left = `${Math.max(12, Math.min(localX + 14, bounds.width - width - 12))}px`;
  popup.style.top = `${Math.max(12, Math.min(localY + 12, bounds.height - 150))}px`;
  popup.innerHTML = `
    <div class="heatmap-popup-card">
      <div class="heatmap-popup-card__title">${raw.name || params.name}</div>
      <div><span class="${pctCls(raw.delta / 100)}">${raw.delta >= 0 ? '+' : ''}${Number(raw.delta || 0).toFixed(2)}%</span></div>
      <div>${copy('houseScore')}: ${formatNum(raw.score)}</div>
      <div>${copy('heatmapWeight')}: ${formatNum(raw.weight, 0)}</div>
      <div>${copy('source')}: ${raw.marketData || 'mixed'}</div>
      <div>${copy('heatmapSymbols')}: ${(raw.symbols || []).join(', ') || '--'}</div>
      <button type="button" class="btn btn-primary btn-sm heatmap-trade-btn" data-trade-symbol="${(raw.symbols || [raw.name])[0] || raw.name}">
        ${copy('executePlan')}
      </button>
    </div>
  `;
}

function drawHeatmap() {
  const chartEl = _container.querySelector('#heatmap-chart');
  if (!chartEl) return;
  const popup = _container.querySelector('#heatmap-popup');
  const data = heatmapData().sort((left, right) => Number(right.weight || 0) - Number(left.weight || 0));
  const echartsLib = window.echarts;
  if (!echartsLib) {
    chartEl.innerHTML = `<div class="empty-state" style="min-height:220px"><div class="empty-state__title">Heatmap renderer unavailable</div></div>`;
    writeHeatmapAuditState(data);
    return;
  }

  if (!_heatmapChart || _heatmapChart.isDisposed?.()) {
    _heatmapChart = echartsLib.init(chartEl, null, { renderer: 'canvas' });
  }

  const option = {
    backgroundColor: 'transparent',
    animation: true,
    animationDuration: 550,
    animationEasing: 'cubicOut',
    tooltip: {
      confine: true,
      className: 'heatmap-echarts-tooltip-wrap',
      borderWidth: 1,
      backgroundColor: getComputedStyle(document.documentElement).getPropertyValue('--bg-surface').trim() || '#101223',
      borderColor: getComputedStyle(document.documentElement).getPropertyValue('--border-dim').trim() || 'rgba(90,120,160,0.35)',
      textStyle: {
        color: getComputedStyle(document.documentElement).getPropertyValue('--text-primary').trim() || '#f0f4ff',
        fontFamily: 'IBM Plex Mono, monospace',
        fontSize: 11,
      },
      formatter: heatmapTooltipFormatter,
    },
    series: [{
      type: 'treemap',
      roam: false,
      nodeClick: false,
      breadcrumb: { show: false },
      left: 10,
      right: 10,
      top: 10,
      bottom: 10,
      visibleMin: 10,
      leafDepth: 1,
      sort: 'desc',
      squareRatio: 0.72,
      data: data.map((item, index) => normalizeHeatmapNode(item, index)),
      label: {
        show: true,
        color: getComputedStyle(document.documentElement).getPropertyValue('--text-primary').trim() || '#f0f4ff',
        fontFamily: 'IBM Plex Mono, monospace',
        lineHeight: 18,
        overflow: 'truncate',
        formatter: heatmapFormatter,
        rich: {
          name: { fontSize: 12, fontWeight: 700, color: '#f0f4ff', lineHeight: 20 },
          delta: { fontSize: 18, fontWeight: 800, color: '#f0f4ff', lineHeight: 24 },
          meta: { fontSize: 10, color: 'rgba(190,210,235,0.78)', lineHeight: 17 },
        },
      },
      upperLabel: {
        show: false,
      },
      levels: [
        {
          itemStyle: {
            borderColor: 'rgba(255,255,255,0.04)',
            borderWidth: 0,
            gapWidth: 8,
          },
        },
        {
          itemStyle: {
            borderRadius: 12,
            gapWidth: 6,
          },
        },
      ],
    }],
  };

  _heatmapChart.setOption(option, true);
  _heatmapChart.off('click');
  _heatmapChart.on('click', (params) => {
    if (!params?.data?.__raw) return;
    _selectedHeatmapNode = params.data.__raw;
    positionHeatmapPopup(params);
    writeHeatmapAuditState(data);
    recordUiAuditEvent('heatmap_tile_select', 'dashboard_heatmap', {}, {
      sector: _selectedHeatmapNode.name,
      symbols: _selectedHeatmapNode.symbols || [],
    });
  });

  if (!_selectedHeatmapNode && popup) {
    popup.style.display = 'none';
    popup.innerHTML = '';
  }
  writeHeatmapAuditState(data);
}

async function loadPositions() {
  const body = _container.querySelector('#positions-body');
  const stamp = _container.querySelector('#pos-timestamp');
  if (!body) return;
  body.innerHTML = `<div class="loading-overlay" style="min-height:90px"><div class="spinner"></div></div>`;
  try {
    const payload = await api.execution.positions('alpaca', 'paper');
    const positions = payload?.positions || [];
    stamp.textContent = new Date().toLocaleTimeString(getLocale());
    if (!positions.length) {
      body.innerHTML = `<div class="empty-state" style="min-height:120px"><div class="empty-state__title">No open positions</div></div>`;
      return;
    }
    body.innerHTML = `
      <div class="tbl-wrap">
        <table>
          <thead><tr><th>Symbol</th><th>Qty</th><th>Side</th><th>Current</th><th>P&L</th></tr></thead>
          <tbody>
            ${positions.slice(0, 8).map((position) => `
              <tr>
                <td class="cell-symbol">${position.symbol || '--'}</td>
                <td>${position.qty || position.quantity || '--'}</td>
                <td>${position.side || 'long'}</td>
                <td>${position.current_price || position.market_price || '--'}</td>
                <td class="${pctCls(position.unrealized_plpc || position.unrealized_pct || 0)}">${position.unrealized_pl || position.unrealized_plpc || '--'}</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    `;
  } catch {
    stamp.textContent = '';
    body.innerHTML = `
      <div class="empty-state" style="min-height:120px">
        <div class="empty-state__title">${copy('positionUnavailable')}</div>
        <div class="empty-state__text">${copy('positionHint')}</div>
      </div>
    `;
  }
}

function syncPageState() {
  const signal = activeSignal();
  updateSignalSummary(signal);
  renderAiPanel(signal);
  renderPerformancePanel();
}

function indicatorButtonsState() {
  _container.querySelectorAll('[data-ind]').forEach((button) => {
    button.classList.toggle('active', _activeIndicators.has(button.dataset.ind));
  });
  _container.querySelectorAll('[data-zoom]').forEach((button) => {
    button.classList.toggle('active', button.dataset.zoom === _activeZoom);
  });
  const zoomReadout = _container.querySelector('#zoom-readout');
  if (zoomReadout) {
    const valueEl = zoomReadout.querySelector('.zoom-readout__value');
    if (valueEl) {
      valueEl.textContent = _activeZoom;
    }
    zoomReadout.dataset.zoom = _activeZoom;
  }
  _container.querySelectorAll('[data-tf]').forEach((button) => {
    button.classList.toggle('active', button.dataset.tf === _activeTF);
  });
  _container.querySelectorAll('[data-heat-tf]').forEach((button) => {
    button.classList.toggle('active', button.dataset.heatTf === _activeHeatTf);
  });
}

function candleFallback(symbol, limit = 140) {
  const seeds = { NVDA: 188, MSFT: 324, NEE: 68, AAPL: 182, TSLA: 176 };
  let close = seeds[symbol] || 120;
  const candles = [];
  for (let index = 0; index < limit; index += 1) {
    const drift = (((index * 11) % 7) - 3) * 0.004 + (symbol === 'NEE' ? -0.0006 : 0.0014);
    const open = close;
    close = Math.max(20, close * (1 + drift));
    const high = Math.max(open, close) * 1.012;
    const low = Math.min(open, close) * 0.988;
    candles.push({
      open,
      high,
      low,
      close,
      volume: 8000000 + ((index * 97000) % 2400000),
      date: new Date(Date.now() - (limit - index) * 86400000).toISOString(),
    });
  }
  return candles;
}

async function fetchCandles(symbol, timeframe) {
  const cacheKey = `${String(symbol || '').toUpperCase()}::${String(timeframe || '1D').toUpperCase()}::${_selectedProvider}`;
  const cached = _chartCache.get(cacheKey);
  if (cached && (Date.now() - cached.at) < CHART_CACHE_TTL_MS) {
    return cached.payload;
  }
  if (_chartInflight.has(cacheKey)) {
    return _chartInflight.get(cacheKey);
  }
  const request = (async () => {
    try {
      const response = await api.platform.dashboardChart(symbol, timeframe, _selectedProvider);
      const payload = {
        source: response.source || 'unknown',
        selected_provider: response.selected_provider || _selectedProvider,
        source_chain: response.data_source_chain || response.provider_chain || [],
        provider_status: response.provider_status || {},
        degraded_from: response.degraded_from || null,
        fallback_preview: response.fallback_preview || null,
        indicators: response.indicators || {},
        projection_scenarios: response.projection_scenarios || {},
        projection_explanations: response.projection_explanations || {},
        projected_volume: response.projected_volume || [],
        viewport_defaults: response.viewport_defaults || {},
        click_targets: response.click_targets || [],
        prediction_disabled_reason: response.prediction_disabled_reason || null,
        market_data_warnings: response.market_data_warnings || [],
        warning: response.warning || null,
        detail: response.detail || null,
        signal: response.signal || null,
        candles: (response.candles || []).map((candle) => ({
          open: candle.open ?? candle.o,
          high: candle.high ?? candle.h,
          low: candle.low ?? candle.l,
          close: candle.close ?? candle.c,
          volume: candle.volume ?? candle.v,
          date: candle.date ?? candle.t,
        })),
      };
      _chartCache.set(cacheKey, { at: Date.now(), payload });
      if (payload.candles?.length) {
        persistChartSnapshot(symbol, timeframe, _selectedProvider, payload);
      }
      return payload;
    } catch {
      const payload = {
        source: 'unavailable',
        selected_provider: _selectedProvider,
        source_chain: _dashboardState?.source_chain || sourceChainDefault(),
        provider_status: _dashboardState?.provider_status || { available: false, provider: 'unavailable' },
        degraded_from: _dashboardState?.degraded_from || null,
        fallback_preview: _dashboardState?.fallback_preview || null,
        indicators: {},
        projection_scenarios: {},
        projection_explanations: {},
        projected_volume: [],
        viewport_defaults: {},
        click_targets: [],
        prediction_disabled_reason: 'market_data_unavailable',
        market_data_warnings: ['market_data_unavailable'],
        warning: 'market_data_unavailable',
        detail: null,
        signal: null,
        candles: [],
      };
      _chartCache.set(cacheKey, { at: Date.now(), payload });
      return payload;
    } finally {
      _chartInflight.delete(cacheKey);
    }
  })();
  _chartInflight.set(cacheKey, request);
  return request;
}

function renderChartStage() {
  const canvas = _container?.querySelector('#kline-canvas');
  const statusEl = _container?.querySelector('#kline-status-note');
  const legendEl = _container?.querySelector('#kline-legend');
  const overlayEl = _container?.querySelector('#kline-projection-float');
  if (!canvas || !statusEl) return false;

  if (!chartReady()) {
    canvas.style.display = 'none';
    legendEl.innerHTML = '';
    if (overlayEl) {
      overlayEl.style.display = 'none';
      overlayEl.innerHTML = '';
    }
    if (_renderer) {
      _renderer.destroy();
      _renderer = null;
    }
    statusEl.classList.add('dashboard-status-note--card');
    statusEl.innerHTML = renderChartFallbackCard();
    return false;
  }

  statusEl.classList.remove('dashboard-status-note--card');
  canvas.style.display = 'block';
  ensureRenderer();
  return true;
}

function updateRenderer() {
  if (!renderChartStage()) return;
  const signal = activeSignal();
  const analysis = _selectedProjection ? buildAnalysisModel(signal, _selectedProjection, _lastCandleResponse.source) : null;
  _renderer.update({
    symbol: _activeSymbol,
    timeframe: _activeTF,
    zoomLabel: _activeZoom,
    source: _lastCandleResponse.source,
    selectedProvider: _selectedProvider,
    candles: _lastCandleResponse.candles,
    signal,
    selectedScenario: _selectedProjection,
    indicators: [..._activeIndicators],
    analysis,
  });
}

async function loadActiveKline() {
  const requestId = ++_chartRequestSeq;
  const signal = activeSignal();
  if (!signal) {
    _chartLoading = false;
    _lastCandleResponse = {
      source: _overviewError ? 'unavailable' : 'unknown',
      selected_provider: _selectedProvider,
      source_chain: _dashboardState?.source_chain || sourceChainDefault(),
      indicators: {},
      projection_scenarios: {},
      projection_explanations: {},
      projected_volume: [],
      viewport_defaults: {},
      click_targets: [],
      prediction_disabled_reason: _overviewError ? 'backend_unavailable' : 'no_watchlist_signal',
      market_data_warnings: [],
      warning: null,
      detail: null,
      signal: null,
      candles: [],
    };
    syncDashboardStateFromChart(_lastCandleResponse, _activeSymbol);
    updateIndicators([]);
    renderAiPanel(null);
    updateRenderer();
    renderHealthBanner();
    return;
  }
  const hadRenderableChart = chartReady();
  _chartLoading = true;
  _dashboardState = defaultDashboardState({
    ..._dashboardState,
    phase: 'loading',
    symbol: signal.symbol,
    fallback_preview: {
      ...(_dashboardState?.fallback_preview || {}),
      symbol: signal.symbol,
      reason: ['chart_loading'],
      next_actions: ['refresh_dashboard', 'switch_symbol', 'open_market_radar', 'open_backtest'],
    },
  });
  renderHealthBanner();
  if (!hadRenderableChart) {
    _lastCandleResponse = {
      source: 'loading',
        selected_provider: _selectedProvider,
        source_chain: _dashboardState?.source_chain || sourceChainDefault(),
      indicators: {},
      projection_scenarios: {},
      projection_explanations: {},
      projected_volume: [],
      viewport_defaults: {},
      click_targets: [],
      prediction_disabled_reason: 'loading',
      market_data_warnings: [],
      warning: null,
      detail: null,
      signal,
      candles: [],
    };
    updateRenderer();
  }
  const response = await fetchCandles(signal.symbol, _activeTF);
  if (requestId !== _chartRequestSeq) return;
  _lastCandleResponse = response;
  _chartLoading = false;
  syncDashboardStateFromChart(_lastCandleResponse, signal.symbol);
  if (_lastCandleResponse.signal) {
    mergeActiveSignal(_lastCandleResponse.signal);
    populateSignalTable();
    renderChips();
    drawHeatmap();
  }
  const latestSignal = activeSignal();
  if (_lastCandleResponse.source === 'unavailable' || latestSignal?.prediction_mode !== 'model' || _lastCandleResponse.prediction_disabled_reason) {
    _selectedProjection = null;
  }
  updateIndicators(_lastCandleResponse.candles);
  renderAiPanel(latestSignal);
  updateRenderer();
  renderHealthBanner();
}

function ensureRenderer() {
  if (_renderer) return;
  _renderer = createDashboardKlineRenderer({
    canvas: _container.querySelector('#kline-canvas'),
    overlayEl: _container.querySelector('#kline-projection-float'),
    legendEl: _container.querySelector('#kline-legend'),
    statusEl: _container.querySelector('#kline-status-note'),
    onProjectionSelect(nextSelection, meta) {
      const signal = activeSignal();
      const before = { selected: _selectedProjection };
      _selectedProjection = nextSelection;
      updateRenderer();
      renderAiPanel(signal);
      if (nextSelection) {
        recordUiAuditEvent('projection_select', signal?.symbol || 'dashboard', before, { selected: nextSelection }, meta || {});
      } else {
        recordUiAuditEvent('projection_clear', signal?.symbol || 'dashboard', before, { selected: null }, meta || {});
      }
    },
    onBlankClick() {
      // Blank chart areas are intentionally silent.
    },
    onZoomChange(nextZoom, origin) {
      setZoom(nextZoom, origin);
    },
  });
}

function setZoom(nextZoom, origin = 'button') {
  const normalizedZoom = normalizeZoomLabel(nextZoom);
  if (normalizedZoom === _activeZoom) return;
  const before = { zoom: _activeZoom };
  _activeZoom = normalizedZoom;
  indicatorButtonsState();
  updateRenderer();
  recordUiAuditEvent('zoom_change', 'dashboard_kline', before, { zoom: _activeZoom }, { origin });
}

function clearZoomHold() {
  if (_zoomHoldTimer) clearTimeout(_zoomHoldTimer);
  if (_zoomHoldInterval) clearInterval(_zoomHoldInterval);
  _zoomHoldTimer = null;
  _zoomHoldInterval = null;
}

function startZoomHold(direction) {
  clearZoomHold();
  _zoomHoldTimer = setTimeout(() => {
    _zoomHoldInterval = setInterval(() => {
      setZoom(stepZoomLabel(_activeZoom, direction), 'hold');
    }, 110);
  }, 260);
}

async function loadOverview() {
  const persistedState = loadPersistedDashboardState();
  if (persistedState) {
    _dashboardState = defaultDashboardState({
      ...persistedState,
      selected_provider: _selectedProvider,
    });
    if (!_activeSymbol && persistedState.symbol) {
      _activeSymbol = persistedState.symbol;
    }
  }
  const persistedChart = loadPersistedChartSnapshot(_activeSymbol || _dashboardState?.symbol, _activeTF, _selectedProvider);
  if (persistedChart?.candles?.length) {
    _lastCandleResponse = {
      ..._lastCandleResponse,
      ...persistedChart,
    };
    syncDashboardStateFromChart(_lastCandleResponse, persistedChart.symbol || _dashboardState?.symbol || _activeSymbol);
    updateIndicators(_lastCandleResponse.candles);
    updateRenderer();
  }
  renderHealthBanner();

  const overviewPromise = api.platform.overview();
  const dashboardStateResult = await Promise.allSettled([api.trading.dashboardState(_selectedProvider)]).then((results) => results[0]);

  if (dashboardStateResult.status === 'fulfilled') {
    _dashboardState = defaultDashboardState(dashboardStateResult.value || {});
    persistDashboardState(_dashboardState);
  } else {
    _dashboardState = defaultDashboardState({
      phase: 'loading',
      symbol: _activeSymbol,
      source: 'unknown',
      selected_provider: _selectedProvider,
      fallback_preview: {
        reason: ['chart_loading'],
        next_actions: ['refresh_dashboard', 'switch_symbol', 'open_market_radar', 'open_backtest'],
      },
    });
  }
  const prefetchSymbol = _dashboardState?.symbol || _activeSymbol || '';
  const chartPrefetch = prefetchSymbol ? fetchCandles(prefetchSymbol, _activeTF).catch(() => null) : Promise.resolve(null);

  const overviewResult = await Promise.allSettled([overviewPromise]).then((results) => results[0]);
  if (overviewResult.status === 'fulfilled') {
    _overview = overviewResult.value;
    _overviewError = null;
  } else {
    console.warn('Dashboard overview unavailable', overviewResult.reason);
    _overviewError = overviewResult.reason;
    _overview = {
      watchlist_signals: [],
      top_signals: [],
      portfolio_preview: {},
      latest_backtest: { metrics: {} },
      p1_signal_snapshot: { regime_counts: {} },
      universe: { size: 0 },
      sector_heatmap: [],
      heatmap_nodes: [],
      live_account_snapshot: null,
      position_symbols: [],
    };
    if (!(_dashboardState?.fallback_preview?.reason || []).length) {
      _dashboardState = defaultDashboardState({
        ..._dashboardState,
        phase: 'degraded',
        fallback_preview: {
          ...(_dashboardState?.fallback_preview || {}),
          reason: ['backend_unavailable'],
          next_actions: ['refresh_dashboard', 'switch_symbol', 'open_market_radar', 'open_backtest'],
        },
      });
    }
  }
  _watchlist = unifiedWatchlist(_overview);
  _selectedHeatmapNode = null;
  if (!_watchlist.find((signal) => signal.symbol === _activeSymbol)) {
    _activeSymbol = _watchlist[0]?.symbol || '';
  }
  _dashboardState = defaultDashboardState({
    ..._dashboardState,
    symbol: _dashboardState?.symbol || _activeSymbol,
    fallback_preview: {
      ...(_dashboardState?.fallback_preview || {}),
      symbol: (_dashboardState?.fallback_preview?.symbol || _activeSymbol),
    },
  });
  populateKPIs();
  populateSignalTable();
  renderChips();
  drawHeatmap();
  syncPageState();
  renderHealthBanner();
  await Promise.allSettled([
    chartPrefetch,
    loadActiveKline(),
    loadPositions(),
  ]);
}

function bindEvents() {
  const tick = () => {
    const clock = _container.querySelector('#dash-clock');
    if (clock) {
      clock.textContent = new Date().toLocaleString(getLocale(), {
        weekday: 'short',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      });
    }
  };
  tick();
  _clockTimer = setInterval(tick, 1000);

  _container.querySelector('#dashboard-provider-select')?.addEventListener('change', async (event) => {
    const nextProvider = String(event.target.value || 'auto');
    if (nextProvider === _selectedProvider) return;
    const before = { provider: _selectedProvider };
    _selectedProvider = nextProvider;
    persistSelectedProvider();
    _selectedProjection = null;
    const cachedChart = loadPersistedChartSnapshot(_activeSymbol || _dashboardState?.symbol, _activeTF, _selectedProvider);
    if (cachedChart?.candles?.length) {
      _lastCandleResponse = {
        ..._lastCandleResponse,
        ...cachedChart,
      };
      syncDashboardStateFromChart(_lastCandleResponse, _activeSymbol || _dashboardState?.symbol || '');
      updateIndicators(_lastCandleResponse.candles);
      updateRenderer();
      renderHealthBanner();
    }
    recordUiAuditEvent('provider_change', 'dashboard_source', before, { provider: _selectedProvider });
    try {
      const nextState = await api.trading.dashboardState(_selectedProvider);
      _dashboardState = defaultDashboardState(nextState || {});
      persistDashboardState(_dashboardState);
    } catch {
      _dashboardState = defaultDashboardState({
        ..._dashboardState,
        selected_provider: _selectedProvider,
      });
    }
    await loadActiveKline();
  });

  if (_boundClickHandler) {
    _container.removeEventListener('click', _boundClickHandler);
  }

  _boundClickHandler = async (event) => {
    const symbolChip = event.target.closest('[data-sym]');
    if (symbolChip) {
      const nextSymbol = symbolChip.dataset.sym;
      if (nextSymbol !== _activeSymbol) {
        const before = { symbol: _activeSymbol };
        _activeSymbol = nextSymbol;
        _selectedProjection = null;
        renderChips();
        syncPageState();
        recordUiAuditEvent('symbol_change', 'dashboard_watchlist', before, { symbol: _activeSymbol });
        await loadActiveKline();
      }
      return;
    }

    const timeframeButton = event.target.closest('[data-tf]');
    if (timeframeButton) {
      const nextTf = timeframeButton.dataset.tf;
      if (nextTf !== _activeTF) {
        const before = { timeframe: _activeTF };
        _activeTF = nextTf;
        _selectedProjection = null;
        indicatorButtonsState();
        recordUiAuditEvent('timeframe_change', 'dashboard_kline', before, { timeframe: _activeTF });
        await loadActiveKline();
      }
      return;
    }

    const indicatorButton = event.target.closest('[data-ind]');
    if (indicatorButton) {
      const indicator = indicatorButton.dataset.ind;
      const before = { active: _activeIndicators.has(indicator) };
      if (_activeIndicators.has(indicator)) _activeIndicators.delete(indicator);
      else _activeIndicators.add(indicator);
      indicatorButtonsState();
      updateRenderer();
      recordUiAuditEvent('indicator_toggle', indicator, before, { active: _activeIndicators.has(indicator) });
      return;
    }

    const zoomButton = event.target.closest('[data-zoom]');
    if (zoomButton) {
      setZoom(zoomButton.dataset.zoom, 'preset');
      return;
    }

    if (event.target.closest('#zoom-out-btn')) {
      setZoom(stepZoomLabel(_activeZoom, -1), 'button');
      return;
    }

    if (event.target.closest('#zoom-in-btn')) {
      setZoom(stepZoomLabel(_activeZoom, 1), 'button');
      return;
    }

    const heatTf = event.target.closest('[data-heat-tf]');
    if (heatTf) {
      _activeHeatTf = heatTf.dataset.heatTf;
      indicatorButtonsState();
      drawHeatmap();
      return;
    }

    const tradeButton = event.target.closest('[data-trade-symbol]');
    if (tradeButton) {
      const symbol = String(tradeButton.dataset.tradeSymbol || '').toUpperCase();
      if (symbol) {
        window.sessionStorage.setItem('qt.execution.prefill', JSON.stringify({
          universe: symbol,
          broker: 'alpaca',
          source: 'dashboard_heatmap',
        }));
        recordUiAuditEvent('trade_prefill', 'dashboard_heatmap', {}, { symbol, route: '/execution' });
        window.location.hash = '#/execution';
      }
      return;
    }

    const indicatorRow = event.target.closest('[data-ikey]');
    if (indicatorRow) {
      const key = indicatorRow.dataset.ikey;
      showIndicatorModal(key, _container._indicatorValues || {}, _container._indicatorCandles || [], getLang());
      recordUiAuditEvent('indicator_modal_open', key, {}, { open: true });
      return;
    }

    if (event.target.closest('#btn-refresh-pos')) {
      await loadPositions();
    }
  };

  _container.addEventListener('click', _boundClickHandler);

  if (_boundPointerDownHandler) {
    _container.removeEventListener('pointerdown', _boundPointerDownHandler);
  }
  if (_boundResizeHandler) {
    window.removeEventListener('resize', _boundResizeHandler);
  }
  _boundPointerDownHandler = (event) => {
    if (event.target.closest('#zoom-out-btn')) {
      startZoomHold(-1);
      window.addEventListener('pointerup', clearZoomHold, { once: true });
      window.addEventListener('pointercancel', clearZoomHold, { once: true });
      return;
    }
    if (event.target.closest('#zoom-in-btn')) {
      startZoomHold(1);
      window.addEventListener('pointerup', clearZoomHold, { once: true });
      window.addEventListener('pointercancel', clearZoomHold, { once: true });
    }
  };
  _container.addEventListener('pointerdown', _boundPointerDownHandler);

  _boundResizeHandler = () => {
    _heatmapChart?.resize?.();
  };
  window.addEventListener('resize', _boundResizeHandler);
}

export async function render(container) {
  ensureUiAuditLog();
  if (_clockTimer) clearInterval(_clockTimer);
  _clockTimer = null;
  _renderer?.destroy();
  _renderer = null;
  _heatmapChart?.dispose?.();
  _heatmapChart = null;
  clearZoomHold();
  _container = container;
  _overview = null;
  _overviewError = null;
  _chartLoading = false;
  _selectedProvider = loadStoredProvider();
  _dashboardState = defaultDashboardState({ phase: 'loading', selected_provider: _selectedProvider });
  _watchlist = [];
  _activeIndicators = new Set(DEFAULT_INDICATORS);
  _activeZoom = '116%';
  _activeTF = '1D';
  _activeHeatTf = '1D';
  _selectedProjection = null;
  _selectedHeatmapNode = null;
  _lastCandleResponse = {
    source: 'unknown',
    selected_provider: _selectedProvider,
    source_chain: sourceChainDefault(),
    candles: [],
    indicators: {},
    projection_scenarios: {},
    projection_explanations: {},
    projected_volume: [],
    market_data_warnings: [],
    warning: null,
    detail: null,
    signal: null,
    prediction_disabled_reason: null,
  };
  _disposeLang?.();
  _disposeLang = onLangChange(() => render(container));
  container.innerHTML = buildShell();
  bindEvents();
  indicatorButtonsState();
  await loadOverview();
}

export function destroy() {
  _disposeLang?.();
  _disposeLang = null;
  if (_clockTimer) clearInterval(_clockTimer);
  _clockTimer = null;
  if (_container && _boundClickHandler) {
    _container.removeEventListener('click', _boundClickHandler);
  }
  if (_container && _boundPointerDownHandler) {
    _container.removeEventListener('pointerdown', _boundPointerDownHandler);
  }
  if (_boundResizeHandler) {
    window.removeEventListener('resize', _boundResizeHandler);
  }
  clearZoomHold();
  _boundClickHandler = null;
  _boundPointerDownHandler = null;
  _boundResizeHandler = null;
  _renderer?.destroy();
  _renderer = null;
  _heatmapChart?.dispose?.();
  _heatmapChart = null;
  _container = null;
  _overview = null;
  _overviewError = null;
  _chartLoading = false;
  _dashboardState = null;
  _watchlist = [];
  _selectedProjection = null;
  _selectedHeatmapNode = null;
  _lastCandleResponse = {
    source: 'unknown',
    selected_provider: _selectedProvider,
    source_chain: sourceChainDefault(),
    candles: [],
    indicators: {},
    projection_scenarios: {},
    projection_explanations: {},
    projected_volume: [],
    market_data_warnings: [],
    warning: null,
    detail: null,
    signal: null,
    prediction_disabled_reason: null,
  };
}

