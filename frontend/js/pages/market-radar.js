import { api } from '../qtapi.js?v=8';
import { router } from '../router.js?v=8';
import { getLang, onLangChange } from '../i18n.js?v=8';
import {
  emptyState,
  esc,
  loadPayloadSnapshot,
  metric,
  miniMetric,
  num,
  persistPayloadSnapshot,
  renderDegradedNotice,
  renderError,
  renderTokenPreview,
  setLoading,
  splitTokens,
  statusBadge,
} from './workbench-utils.js?v=8';

let _container = null;
let _langCleanup = null;
let _items = [];
let _view = { page: 1, pageSize: 5 };
let _lastLineage = [];
let _selectedItemId = null;
let _lastSentiment = null;
let _lastAlerts = [];
let _overlayState = { phase: 'loading', warnings: [], fallback: '', nextActions: [] };
let _degradedMeta = null;

const MARKET_RADAR_CACHE_KEY = 'qt.market-radar.snapshot.v1';
const MARKET_RADAR_CACHE_TTL_MS = 20 * 60 * 1000;

const COPY = {
  en: {
    title: 'Market Radar',
    subtitle: 'Live evidence stream from free-tier news, market data, SEC, and local ESG sources.',
    scan: 'Scan Radar',
    refresh: 'Refresh Evidence',
    provider: 'Provider Filter',
    symbol: 'Symbol Filter',
    universe: 'Universe',
    feed: 'Evidence Feed',
    quality: 'Quality Summary',
    prev: 'Prev',
    next: 'Next',
    showing: 'Showing',
    rows: 'items',
    providerMix: 'Provider Mix',
    freshness: 'Freshness',
    ready: 'Decision Ready',
    filters: 'Active Filters',
    sentiment: 'Sentiment Lane',
    alerts: 'Alert Jump',
    loadingEvidence: 'Loading evidence lake...',
    loadingScan: 'Scanning free-tier providers...',
    whyEmpty: 'Why Empty',
    fallback: 'Fallback',
    nextAction: 'Next Action',
    noEvidenceTitle: 'No evidence loaded yet',
    noEvidenceDetail: 'Refresh evidence or run a radar scan to seed the decision-ready feed.',
    noFilteredTitle: 'No evidence matched the current filters',
    noFilteredDetail: 'Clear the provider or symbol filters, then refresh evidence to restore the feed.',
    feedFallback: 'Feed is waiting on the evidence API, but the page stays interactive.',
    feedNextAction: 'Use Refresh Evidence, widen the filters, or jump to Connector Center to inspect providers.',
    overlay: 'Overlay Status',
    overlayLoading: 'overlay loading',
    overlayReady: 'ready',
    overlayDegraded: 'degraded',
    overlayHealthy: 'Sentiment and alert overlays are synced with the evidence feed.',
    overlayMissingSentiment: 'Sentiment overlay is unavailable right now.',
    overlayMissingAlerts: 'Today alert bridge is unavailable right now.',
    overlayFallback: 'The evidence feed still renders from the evidence lake while the right-side overlay degrades.',
    overlayNextAction: 'Refresh the page, inspect Risk Board, or open Trading Ops before trusting the paper path.',
    latestItem: 'Latest Item',
    pageProviders: 'Page Providers',
    decisionLane: 'Decision Lane',
    selectedEvidence: 'Selected Evidence',
    confidence: 'Confidence',
    qualityScore: 'Quality',
    linkage: 'Linkage',
    pageLabel: 'Page',
    visible: 'Visible',
    topQuality: 'Top q',
    leadSymbol: 'Lead',
    allProviders: 'All providers',
    allSymbols: 'All symbols',
  },
  zh: {
    title: '市场雷达',
    subtitle: '汇总免费新闻、行情、SEC 与本地 ESG 的实时证据流。',
    scan: '扫描雷达',
    refresh: '刷新证据',
    provider: '来源过滤',
    symbol: '股票过滤',
    universe: '股票池',
    feed: '证据流',
    quality: '质量摘要',
    prev: '上一页',
    next: '下一页',
    showing: '显示',
    rows: '条',
    providerMix: '来源分布',
    freshness: '新鲜度',
    ready: '决策就绪',
    filters: '当前过滤',
    sentiment: '情绪叠层',
    alerts: '告警跳转',
    loadingEvidence: '正在加载证据湖...',
    loadingScan: '正在扫描免费数据源...',
    whyEmpty: '为空原因',
    fallback: '回落说明',
    nextAction: '下一步动作',
    noEvidenceTitle: '证据流尚未加载',
    noEvidenceDetail: '点击刷新证据或运行一次雷达扫描，先把可进入决策链的证据流落下来。',
    noFilteredTitle: '当前过滤条件下没有匹配证据',
    noFilteredDetail: '清空来源或股票过滤条件后重新刷新，就能恢复首屏证据流。',
    feedFallback: '证据流正在等待证据接口返回，但页面不会因为叠层失败而卡死。',
    feedNextAction: '可以先刷新证据、放宽过滤条件，或跳到连接器中心检查数据源。',
    overlay: '叠层状态',
    overlayLoading: '叠层加载中',
    overlayReady: '已就绪',
    overlayDegraded: '已降级',
    overlayHealthy: '情绪与告警叠层已和证据流同步。',
    overlayMissingSentiment: '当前无法取得情绪叠层。',
    overlayMissingAlerts: '当前无法取得今日告警桥接。',
    overlayFallback: '左侧证据流继续来自证据湖，右侧摘要会明确显示叠层降级。',
    overlayNextAction: '先刷新页面、查看风控板，或进入交易运维，再决定是否推进 Paper 路径。',
    latestItem: '最新条目',
    pageProviders: '当前页来源',
    decisionLane: '决策通道',
    selectedEvidence: '当前选中证据',
    confidence: '置信度',
    qualityScore: '质量',
    linkage: '链路',
    pageLabel: '页码',
    visible: '当前显示',
    topQuality: '最高质量',
    leadSymbol: '首条股票',
    allProviders: '全部来源',
    allSymbols: '全部股票',
  },
};

function c(key) {
  const lang = getLang() === 'zh' ? 'zh' : 'en';
  return COPY[lang][key] || COPY.en[key] || key;
}

function t(en, zh) {
  return getLang() === 'zh' ? zh : en;
}

function isMounted() {
  return Boolean(_container && _container.isConnected);
}

function radarDegradedState(savedAt, reason, detail) {
  return {
    tone: 'warning',
    saved_at: savedAt || null,
    title: t('Cached evidence snapshot', '已切换到缓存证据快照'),
    reason: reason || t('Showing the last successful evidence feed while live refresh recovers.', '正在使用最近一次成功的证据流，等待实时刷新恢复。'),
    detail: detail || t('Alpaca-first market context stays active; only the evidence refresh is degraded.', 'Alpaca 优先的市场上下文仍保留，当前只是证据刷新进入降级。'),
    action: t('Use Refresh Evidence to retry the live feed.', '可以继续点击“刷新证据”重试实时链路。'),
  };
}

function hydrateRadarSnapshot() {
  const cached = loadPayloadSnapshot(MARKET_RADAR_CACHE_KEY, MARKET_RADAR_CACHE_TTL_MS);
  if (!cached?.payload) return false;
  assignEvidence(cached.payload);
  _degradedMeta = radarDegradedState(
    cached.saved_at,
    t('Loading the last evidence snapshot while reconnecting.', '正在回填最近一次成功快照，并同步重连后端。'),
  );
  renderItems(cached.payload);
  return true;
}

function buildOverlayState(phase, warnings = []) {
  const nextActions = phase === 'ready'
    ? [t('Open Debate Desk', '打开辩论台'), t('Open Risk Board', '打开风控板'), t('Open Trading Ops', '打开交易运维')]
    : [t('Refresh Evidence', '刷新证据'), t('Inspect Risk Board', '查看风控板'), t('Open Trading Ops', '打开交易运维')];
  return {
    phase,
    warnings,
    fallback: phase === 'ready' ? c('overlayHealthy') : c('overlayFallback'),
    nextActions,
  };
}

function riskDecisionLabel(value) {
  const normalized = String(value || '').trim().toLowerCase();
  const map = {
    approve: t('approve', '批准'),
    reduce: t('reduce', '缩减'),
    reject: t('reject', '拒绝'),
    halt: t('halt', '暂停'),
    watch: t('watch', '观察'),
  };
  return map[normalized] || String(value || '-');
}

function defaultLineage() {
  return getLang() === 'zh'
    ? ['免费扫描', '证据标准化', '时点安全保护', '可进入决策链']
    : ['Free-tier scan', 'Evidence normalization', 'As-of guard', 'Decision-ready feed'];
}

function overlayPhaseLabel(phase) {
  const map = {
    loading: c('overlayLoading'),
    ready: c('overlayReady'),
    degraded: c('overlayDegraded'),
  };
  return map[String(phase || '').toLowerCase()] || String(phase || '-');
}

function normalizeEvidenceItem(item, index) {
  const raw = item || {};
  const itemId = raw.item_id || raw.id || `evidence-${index + 1}`;
  const symbol = String(raw.symbol || raw.ticker || raw.asset || raw.metadata?.symbol || '').trim().toUpperCase() || '-';
  const provider = String(raw.provider || raw.source || raw.provider_id || raw.metadata?.provider || 'unknown').trim() || 'unknown';
  const title = raw.title || raw.headline || raw.name || `${symbol} evidence`;
  const summary = raw.summary || raw.abstract || raw.snippet || raw.description || raw.body || '';
  const qualityScore = Number(raw.quality_score ?? raw.confidence ?? raw.score ?? 0);
  const confidence = Number(raw.confidence ?? raw.quality_score ?? raw.score ?? 0);
  return {
    item_id: String(itemId),
    item_type: raw.item_type || raw.type || 'evidence',
    provider,
    title,
    summary,
    symbol,
    confidence: Number.isFinite(confidence) ? confidence : 0,
    quality_score: Number.isFinite(qualityScore) ? qualityScore : 0,
    leakage_guard: raw.leakage_guard || raw.guard || raw.metadata?.guard || 'review',
    published_at: raw.published_at || raw.timestamp || raw.created_at || '-',
    observed_at: raw.observed_at || raw.as_of || raw.generated_at || raw.published_at || '-',
  };
}

function assignEvidence(payload) {
  _items = Array.isArray(payload?.items) ? payload.items.map(normalizeEvidenceItem) : [];
  _lastLineage = payload?.lineage || defaultLineage();
  _selectedItemId = _items[0]?.item_id || null;
  _view.page = 1;
}

export async function render(container) {
  _container = container;
  _overlayState = buildOverlayState('loading');
  renderShell();
  wire();
  hydrateRadarSnapshot();
  _langCleanup = onLangChange(() => {
    if (!_container?.isConnected) return;
    renderShell();
    wire();
    renderItems({ lineage: _lastLineage });
  });
  await refreshEvidence();
}

export function destroy() {
  _langCleanup?.();
  _langCleanup = null;
  _container = null;
  _degradedMeta = null;
}

function renderShell() {
  if (!_container) return;
  _container.innerHTML = `
    <div class="workbench-page live-page market-radar-page" data-no-autotranslate="true">
      <section class="run-panel">
        <div class="run-panel__header">
          <div class="run-panel__title">${c('title')}</div>
          <div class="run-panel__sub">${c('subtitle')}</div>
        </div>
        <div class="run-panel__body">
          <div class="grid-3 compact-control-grid live-control-grid">
            <label class="field field--with-preview">
              <span>${c('universe')}</span>
              <input id="radar-universe" value="AAPL, MSFT, NVDA, TSLA">
              <div id="radar-universe-preview"></div>
            </label>
            <label class="field field--with-preview">
              <span>${c('provider')}</span>
              <input id="radar-provider" placeholder="marketaux, local_esg">
              <div id="radar-provider-preview"></div>
            </label>
            <label class="field field--with-preview">
              <span>${c('symbol')}</span>
              <input id="radar-symbol" placeholder="AAPL">
              <div id="radar-symbol-preview"></div>
            </label>
          </div>
        </div>
        <div class="run-panel__foot workbench-action-grid">
          <button class="btn btn-primary workbench-action-btn" id="btn-market-radar-scan">${c('scan')}</button>
          <button class="btn btn-ghost workbench-action-btn" id="btn-market-radar-refresh">${c('refresh')}</button>
        </div>
      </section>
      <section class="grid-2 market-radar-layout workbench-main-grid">
        <article class="card">
          <div class="card-header"><span class="card-title">${c('feed')}</span></div>
          <div class="card-body" id="market-radar-feed">${emptyState(c('loadingEvidence'))}</div>
        </article>
        <article class="card">
          <div class="card-header"><span class="card-title">${c('quality')}</span></div>
          <div class="card-body" id="market-radar-summary">${emptyState(c('loadingEvidence'))}</div>
        </article>
      </section>
    </div>`;
  renderFieldPreviews();
}

function wire() {
  if (!_container) return;
  _container.querySelector('#btn-market-radar-scan')?.addEventListener('click', scanRadar);
  _container.querySelector('#btn-market-radar-refresh')?.addEventListener('click', refreshEvidence);
  _container.querySelector('#radar-provider')?.addEventListener('input', () => {
    _view.page = 1;
    renderFieldPreviews();
    renderItems({ lineage: _lastLineage });
  });
  _container.querySelector('#radar-symbol')?.addEventListener('input', () => {
    _view.page = 1;
    renderFieldPreviews();
    renderItems({ lineage: _lastLineage });
  });
  _container.querySelector('#radar-universe')?.addEventListener('input', renderFieldPreviews);
  _container.querySelector('#market-radar-feed')?.addEventListener('click', (event) => {
    const itemButton = event.target.closest('[data-radar-item-id]');
    if (itemButton) {
      _selectedItemId = itemButton.getAttribute('data-radar-item-id');
      renderItems({ lineage: _lastLineage });
      return;
    }
    const button = event.target.closest('[data-radar-page]');
    if (!button || button.disabled) return;
    _view.page = Number(button.getAttribute('data-radar-page')) || 1;
    renderItems({ lineage: _lastLineage });
  });
  _container.querySelector('#market-radar-summary')?.addEventListener('click', (event) => {
    const target = event.target.closest('[data-radar-link]');
    if (!target) return;
    const route = {
      debate: '/debate-desk',
      risk: '/risk-board',
      ops: '/trading-ops',
    }[target.getAttribute('data-radar-link')];
    if (route) router.navigate(route);
  });
}

function universe() {
  if (!_container) return ['AAPL'];
  return splitTokens(_container.querySelector('#radar-universe')?.value || 'AAPL', { uppercase: true, delimiters: /[,\s]+/ });
}

function providers() {
  if (!_container) return [];
  return splitTokens(_container.querySelector('#radar-provider')?.value || '', { delimiters: /[,|\s]+/ });
}

function symbolFilter() {
  if (!_container) return '';
  return String(_container.querySelector('#radar-symbol')?.value || '').trim().toUpperCase();
}

function renderFieldPreviews() {
  if (!_container) return;
  _container.querySelector('#radar-universe-preview').innerHTML = renderTokenPreview(universe(), {
    uppercase: true,
    maxItems: 6,
    tone: 'accent',
  });
  _container.querySelector('#radar-provider-preview').innerHTML = renderTokenPreview(providers(), {
    maxItems: 6,
    tone: 'neutral',
    emptyLabel: c('allProviders'),
  });
  const symbol = symbolFilter();
  _container.querySelector('#radar-symbol-preview').innerHTML = renderTokenPreview(symbol ? [symbol] : [], {
    tone: 'accent',
    emptyLabel: c('allSymbols'),
  });
}

async function scanRadar() {
  if (!isMounted()) return;
  const feed = _container.querySelector('#market-radar-feed');
  setLoading(feed, c('loadingScan'));
  _overlayState = buildOverlayState('loading');
  try {
    const payload = await api.connectors.liveScan({
      universe: universe(),
      providers: providers(),
      quota_guard: true,
      persist: true,
      limit: 24,
    });
    if (!isMounted()) return;
    assignEvidence(payload);
    persistPayloadSnapshot(MARKET_RADAR_CACHE_KEY, payload, { symbol: symbolFilter() || null });
    _degradedMeta = null;
    renderItems(payload);
    void refreshTradingOverlay();
  } catch (error) {
    if (!isMounted()) return;
    const cached = loadPayloadSnapshot(MARKET_RADAR_CACHE_KEY, MARKET_RADAR_CACHE_TTL_MS);
    if (cached?.payload) {
      assignEvidence(cached.payload);
      _degradedMeta = radarDegradedState(
        cached.saved_at,
        error?.message || t('Radar scan failed, so the latest successful evidence snapshot is still shown.', '雷达扫描失败，当前继续保留最近一次成功的证据快照。'),
      );
      _overlayState = buildOverlayState('degraded', [error?.message || t('Radar scan failed.', '雷达扫描失败。')]);
      renderItems(cached.payload);
      return;
    }
    renderError(feed, error, { onRetry: scanRadar });
    _overlayState = buildOverlayState('degraded', [error?.message || t('Radar scan failed.', '雷达扫描失败。')]);
    renderSummary({ lineage: _lastLineage });
  }
}

async function refreshEvidence() {
  if (!isMounted()) return;
  const feed = _container.querySelector('#market-radar-feed');
  setLoading(feed, c('loadingEvidence'));
  _overlayState = buildOverlayState('loading');
  try {
    const payload = await api.intelligence.evidence(null, 40);
    if (!isMounted()) return;
    assignEvidence(payload);
    persistPayloadSnapshot(MARKET_RADAR_CACHE_KEY, payload, { symbol: symbolFilter() || null });
    _degradedMeta = null;
    renderItems(payload);
    void refreshTradingOverlay();
  } catch (error) {
    if (!isMounted()) return;
    const cached = loadPayloadSnapshot(MARKET_RADAR_CACHE_KEY, MARKET_RADAR_CACHE_TTL_MS);
    if (cached?.payload) {
      assignEvidence(cached.payload);
      _degradedMeta = radarDegradedState(
        cached.saved_at,
        error?.message || t('Evidence API is unavailable, so the last successful snapshot is still shown.', '证据接口暂不可用，当前继续展示最近一次成功快照。'),
      );
      _overlayState = buildOverlayState('degraded', [error?.message || t('Evidence API unavailable.', '证据接口当前不可用。')]);
      renderItems(cached.payload);
      return;
    }
    renderError(feed, error, { onRetry: refreshEvidence });
    _overlayState = buildOverlayState('degraded', [error?.message || t('Evidence API unavailable.', '证据接口当前不可用。')]);
    renderSummary({ lineage: _lastLineage });
  }
}

async function refreshTradingOverlay() {
  if (!isMounted()) return;
  const tasks = await Promise.allSettled([
    api.trading.sentimentRun({
      universe: universe(),
      providers: providers(),
      quota_guard: true,
    }),
    api.trading.alertsToday(),
  ]);
  if (!isMounted()) return;
  const warnings = [];
  if (tasks[0].status === 'fulfilled') {
    _lastSentiment = tasks[0].value;
  } else {
    _lastSentiment = null;
    warnings.push(c('overlayMissingSentiment'));
  }
  if (tasks[1].status === 'fulfilled') {
    _lastAlerts = tasks[1].value?.alerts || [];
  } else {
    _lastAlerts = [];
    warnings.push(c('overlayMissingAlerts'));
  }
  _overlayState = buildOverlayState(warnings.length ? 'degraded' : 'ready', warnings);
  renderSummary({ lineage: _lastLineage });
}

function filteredItems() {
  if (!_container) return _items;
  const provider = String(_container.querySelector('#radar-provider')?.value || '').trim().toLowerCase();
  const symbol = symbolFilter();
  return _items.filter((item) => {
    const providerOk = !provider || String(item.provider || '').toLowerCase().includes(provider);
    const symbolOk = !symbol || String(item.symbol || '').toUpperCase().includes(symbol);
    return providerOk && symbolOk;
  });
}

function providerBreakdown(items) {
  const counts = new Map();
  items.forEach((item) => {
    const key = String(item.provider || 'unknown');
    counts.set(key, (counts.get(key) || 0) + 1);
  });
  return Array.from(counts.entries()).sort((left, right) => right[1] - left[1]);
}

function renderFeedEmptyState(filtered) {
  const hasFilters = Boolean(providers().length || symbolFilter());
  const title = hasFilters ? c('noFilteredTitle') : c('noEvidenceTitle');
  const detail = hasFilters ? c('noFilteredDetail') : c('noEvidenceDetail');
  const whyEmpty = hasFilters
    ? `${c('provider')}: ${providers().join(', ') || c('allProviders')} · ${c('symbol')}: ${symbolFilter() || c('allSymbols')}`
    : t('No evidence rows have reached the feed yet.', '当前还没有证据条目进入首屏证据流。');
  const fallback = filtered.length ? c('overlayFallback') : c('feedFallback');
  return `
    <div class="functional-empty compact-functional-empty">
      <div class="functional-empty__eyebrow">${esc(c('feed'))}</div>
      <h3>${esc(title)}</h3>
      <p>${esc(detail)}</p>
      <div class="workbench-kv-list compact-kv-list">
        <div class="workbench-kv-row"><span>${c('whyEmpty')}</span><strong>${esc(whyEmpty)}</strong></div>
        <div class="workbench-kv-row"><span>${c('fallback')}</span><strong>${esc(fallback)}</strong></div>
        <div class="workbench-kv-row"><span>${c('nextAction')}</span><strong>${esc(c('feedNextAction'))}</strong></div>
      </div>
    </div>`;
}

function renderEvidencePage(items, pageItems, pageCount) {
  if (!items.length) return renderFeedEmptyState(items);
  const start = (_view.page - 1) * _view.pageSize + 1;
  const end = Math.min(items.length, _view.page * _view.pageSize);
  const pageProviders = Array.from(new Set(pageItems.map((item) => String(item.provider || '-')))).slice(0, 3);
  const topQuality = pageItems.reduce((best, item) => Math.max(best, Number(item.quality_score || item.confidence || 0)), 0);
  const leadSymbol = String(pageItems[0]?.symbol || '-');
  const selected = pageItems.find((item) => String(item.item_id || '') === String(_selectedItemId || '')) || pageItems[0];
  const detailMeta = [
    [t('Provider', '来源'), selected?.provider || '-'],
    [t('Symbol', '股票'), selected?.symbol || '-'],
    [t('Type', '类型'), selected?.item_type || '-'],
    [t('Guard', '门控'), selected?.leakage_guard || '-'],
    [t('Published', '发布时间'), selected?.published_at || '-'],
    [t('Observed', '观测时间'), selected?.observed_at || '-'],
  ];
  const rows = pageItems.map((item) => `
    <article class="workbench-item radar-feed-item ${String(item.item_id || '') === String(selected?.item_id || '') ? 'radar-feed-item--active' : ''}" data-radar-item-id="${esc(item.item_id || '')}">
      <div class="workbench-item__head">
        <strong>${esc(item.title || item.item_id || '')}</strong>
        ${statusBadge(item.item_type || 'evidence')}
      </div>
      <p>${esc(item.summary || '')}</p>
      <div class="workbench-item__meta">
        <span>${esc(item.symbol || '')}</span>
        <span>${esc(item.provider || '')}</span>
        <span>q=${num(item.quality_score || item.confidence)}</span>
        <span>${esc(item.leakage_guard || '')}</span>
      </div>
    </article>`).join('');
  const degradedBanner = _degradedMeta ? renderDegradedNotice(_degradedMeta) : '';
  return `
    ${degradedBanner}
    <div class="workbench-list workbench-scroll-list workbench-scroll-list--short radar-feed-scroll">${rows}</div>
    <div class="workbench-pagination">
      <span>${c('showing')} ${start}-${end} / ${items.length} ${c('rows')}</span>
      <div class="workbench-pagination__buttons">
        <button class="workbench-page-btn" type="button" data-radar-page="${_view.page - 1}" ${_view.page <= 1 ? 'disabled' : ''}>${c('prev')}</button>
        ${Array.from({ length: pageCount }, (_, i) => i + 1).map((page) => `
          <button class="workbench-page-btn${page === _view.page ? ' active' : ''}" type="button" data-radar-page="${page}">${page}</button>
        `).join('')}
        <button class="workbench-page-btn" type="button" data-radar-page="${_view.page + 1}" ${_view.page >= pageCount ? 'disabled' : ''}>${c('next')}</button>
      </div>
    </div>
    <div class="radar-feed-footer">
      <div class="workbench-mini-grid radar-feed-mini-grid">
        ${miniMetric(c('pageLabel'), `${_view.page}/${pageCount}`)}
        ${miniMetric(c('visible'), `${pageItems.length}`)}
        ${miniMetric(c('topQuality'), num(topQuality))}
        ${miniMetric(c('leadSymbol'), esc(leadSymbol))}
      </div>
      <div class="workbench-kv-list compact-kv-list radar-feed-footer__list">
        <div class="workbench-kv-row"><span>${c('pageProviders')}</span><strong>${esc(pageProviders.join(', ') || '-')}</strong></div>
        <div class="workbench-kv-row"><span>${c('decisionLane')}</span><strong>${pageItems.some((item) => String(item.leakage_guard || '').includes('safe')) ? t('as-of safe', '时点安全') : t('review', '复核')}</strong></div>
      </div>
      <section class="radar-selected-evidence">
        <div class="workbench-section__title">${c('selectedEvidence')}</div>
        <div class="radar-selected-evidence__head">
          <div>
            <strong>${esc(selected?.title || '-')}</strong>
            <span>${esc(selected?.summary || '')}</span>
          </div>
          ${statusBadge(selected?.item_type || 'evidence')}
        </div>
        <div class="workbench-mini-grid radar-feed-mini-grid">
          ${miniMetric(c('confidence'), num(selected?.confidence || selected?.quality_score || 0))}
          ${miniMetric(c('qualityScore'), num(selected?.quality_score || selected?.confidence || 0))}
          ${miniMetric(c('freshness'), num(selected?.confidence || 0))}
          ${miniMetric(c('linkage'), selected?.provider ? t('linked', '已关联') : t('pending', '待处理'))}
        </div>
        <div class="workbench-kv-list compact-kv-list radar-selected-evidence__meta">
          ${detailMeta.map(([label, value]) => `<div class="workbench-kv-row"><span>${esc(label)}</span><strong>${esc(value)}</strong></div>`).join('')}
        </div>
      </section>
    </div>`;
}

function renderSummary(payload = {}) {
  if (!_container) return;
  const filtered = filteredItems();
  const providersCount = new Set(filtered.map((item) => item.provider)).size;
  const symbolsCount = new Set(filtered.map((item) => item.symbol)).size;
  const avgQuality = filtered.reduce((acc, item) => acc + Number(item.quality_score || item.confidence || 0), 0) / Math.max(filtered.length, 1);
  const lineage = payload.lineage || _lastLineage || [];
  const freshnessValue = filtered.length ? Math.max(...filtered.map((item) => Number(item.confidence || item.quality_score || 0))) : 0;
  const mix = providerBreakdown(filtered).slice(0, 5);
  const latest = filtered[0] || null;
  const symbolSentiment = (_lastSentiment?.symbol_scores || []).find((row) => String(row.symbol || '') === String(symbolFilter() || latest?.symbol || '').toUpperCase())
    || (_lastSentiment?.symbol_scores || [])[0]
    || null;
  const latestAlert = _lastAlerts[0] || null;
  const overlayWarnings = Array.isArray(_overlayState.warnings) ? _overlayState.warnings : [];
  const degradedBanner = _degradedMeta ? renderDegradedNotice(_degradedMeta) : '';
  _container.querySelector('#market-radar-summary').innerHTML = `
    ${degradedBanner}
    <div class="quality-summary-panel">
      <div class="workbench-metric-grid">
        ${metric(t('Items', '条目数'), filtered.length, filtered.length ? 'positive' : 'risk')}
        ${metric(t('Providers', '来源数'), providersCount)}
        ${metric(t('Symbols', '股票数'), symbolsCount)}
        ${metric(t('Avg quality', '平均质量'), num(avgQuality))}
      </div>
      <section class="workbench-section">
        <div class="workbench-section__title">${c('providerMix')}</div>
        <div class="token-preview">
          ${mix.map(([provider, count]) => `<span class="token-chip token-chip--neutral">${esc(provider)} | ${count}</span>`).join('') || `<span class="token-chip token-chip--muted">-</span>`}
        </div>
      </section>
      <section class="workbench-section">
        <div class="workbench-section__title">${c('filters')}</div>
        <div class="workbench-kv-list compact-kv-list">
          <div class="workbench-kv-row"><span>${c('universe')}</span><strong>${esc(universe().length)}</strong></div>
          <div class="workbench-kv-row"><span>${c('provider')}</span><strong>${esc(providers().join(', ') || c('allProviders'))}</strong></div>
          <div class="workbench-kv-row"><span>${c('symbol')}</span><strong>${esc(symbolFilter() || c('allSymbols'))}</strong></div>
          <div class="workbench-kv-row"><span>${c('freshness')}</span><strong>${num(freshnessValue)}</strong></div>
        </div>
      </section>
      <section class="workbench-section">
        <div class="workbench-section__title">${c('overlay')}</div>
        <div class="workbench-metric-grid">
          ${metric(c('overlay'), overlayPhaseLabel(_overlayState.phase), _overlayState.phase === 'ready' ? 'positive' : _overlayState.phase === 'degraded' ? 'risk' : '')}
          ${metric(c('sentiment'), num(symbolSentiment?.polarity || _lastSentiment?.overall_polarity || 0), (Number(symbolSentiment?.polarity || _lastSentiment?.overall_polarity || 0) || 0) >= 0 ? 'positive' : 'risk')}
          ${metric(c('alerts'), _lastAlerts.length || 0, _lastAlerts.length ? 'risk' : 'positive')}
          ${metric(c('nextAction'), (_overlayState.nextActions || [])[0] || '-', _overlayState.phase === 'ready' ? 'positive' : 'risk')}
        </div>
        <div class="workbench-kv-list compact-kv-list">
          <div class="workbench-kv-row"><span>${c('fallback')}</span><strong>${esc(_overlayState.fallback || c('overlayFallback'))}</strong></div>
          <div class="workbench-kv-row"><span>${c('whyEmpty')}</span><strong>${esc(overlayWarnings.join(' | ') || c('overlayHealthy'))}</strong></div>
          <div class="workbench-kv-row"><span>${c('nextAction')}</span><strong>${esc((_overlayState.nextActions || []).join(' · ') || '-')}</strong></div>
        </div>
      </section>
      <section class="workbench-section">
        <div class="workbench-section__title">${c('ready')}</div>
        <div class="preview-step-grid">
          ${lineage.slice(0, 4).map((step) => `<div class="preview-step"><span>${esc(step)}</span><strong>${t('safe', '安全')}</strong></div>`).join('')}
          <div class="preview-step"><span>${t('Frozen paper inputs', 'Paper 冻结输入')}</span><strong>${t('untouched', '未触碰')}</strong></div>
        </div>
      </section>
      <section class="workbench-section">
        <div class="workbench-section__title">${c('alerts')}</div>
        <div class="workbench-kv-list compact-kv-list">
          <div class="workbench-kv-row"><span>${t('Today alerts', '今日告警')}</span><strong>${esc(_lastAlerts.length)}</strong></div>
          <div class="workbench-kv-row"><span>${t('Latest trigger', '最新触发')}</span><strong>${esc(latestAlert ? `${latestAlert.symbol} | ${latestAlert.trigger_type}` : '-')}</strong></div>
          <div class="workbench-kv-row"><span>${t('Risk verdict', '风控结论')}</span><strong>${esc(riskDecisionLabel(latestAlert?.risk_decision || '-'))}</strong></div>
        </div>
        <div class="workbench-action-grid workbench-action-grid--compact">
          <button class="btn btn-ghost workbench-action-btn" data-radar-link="debate">${t('Debate Desk', '辩论台')}</button>
          <button class="btn btn-ghost workbench-action-btn" data-radar-link="risk">${t('Risk Board', '风控板')}</button>
          <button class="btn btn-ghost workbench-action-btn" data-radar-link="ops">${t('Trading Ops', '交易运维')}</button>
        </div>
      </section>
      <section class="workbench-section">
        <div class="workbench-section__title">${c('latestItem')}</div>
        <div class="workbench-kv-list compact-kv-list">
          <div class="workbench-kv-row"><span>${t('Symbol', '股票')}</span><strong>${esc(latest?.symbol || '-')}</strong></div>
          <div class="workbench-kv-row"><span>${t('Provider', '来源')}</span><strong>${esc(latest?.provider || '-')}</strong></div>
          <div class="workbench-kv-row"><span>${t('Type', '类型')}</span><strong>${esc(latest?.item_type || '-')}</strong></div>
          <div class="workbench-kv-row"><span>${c('confidence')}</span><strong>${num(latest?.confidence || latest?.quality_score || 0)}</strong></div>
        </div>
      </section>
    </div>`;
}

function renderItems(payload = {}) {
  if (!_container) return;
  const filtered = filteredItems();
  const pageCount = Math.max(1, Math.ceil(filtered.length / _view.pageSize));
  _view.page = Math.min(Math.max(1, _view.page), pageCount);
  const pageItems = filtered.slice((_view.page - 1) * _view.pageSize, _view.page * _view.pageSize);
  if (!_selectedItemId || !pageItems.some((item) => String(item.item_id || '') === String(_selectedItemId))) {
    _selectedItemId = pageItems[0]?.item_id || null;
  }
  _container.querySelector('#market-radar-feed').innerHTML = renderEvidencePage(filtered, pageItems, pageCount);
  renderSummary(payload);
}
