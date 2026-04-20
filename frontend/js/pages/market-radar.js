import { api } from '../qtapi.js?v=8';
import { router } from '../router.js?v=8';
import { getLang, onLangChange } from '../i18n.js?v=8';
import {
  emptyState,
  esc,
  metric,
  miniMetric,
  num,
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
    sentiment: '情绪通道',
    alerts: '告警跳转',
  },
};

function c(key) {
  const lang = getLang() === 'zh' ? 'zh' : 'en';
  return COPY[lang][key] || COPY.en[key] || key;
}

function t(en, zh) {
  return getLang() === 'zh' ? zh : en;
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

export async function render(container) {
  _container = container;
  renderShell();
  wire();
  _langCleanup = onLangChange(() => {
    if (_container) {
      renderShell();
      wire();
      renderItems();
    }
  });
  await refreshEvidence();
}

export function destroy() {
  _langCleanup?.();
  _container = null;
}

function renderShell() {
  _container.innerHTML = `
    <div class="workbench-page live-page market-radar-page">
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
          <div class="card-body" id="market-radar-feed">${emptyState(t('Loading evidence', '正在加载证据'))}</div>
        </article>
        <article class="card">
          <div class="card-header"><span class="card-title">${c('quality')}</span></div>
          <div class="card-body" id="market-radar-summary">${emptyState(t('No scan yet', '尚未扫描'))}</div>
        </article>
      </section>
    </div>`;
  renderFieldPreviews();
}

function wire() {
  _container.querySelector('#btn-market-radar-scan')?.addEventListener('click', scanRadar);
  _container.querySelector('#btn-market-radar-refresh')?.addEventListener('click', refreshEvidence);
  _container.querySelector('#radar-provider')?.addEventListener('input', () => {
    _view.page = 1;
    renderFieldPreviews();
    renderItems();
  });
  _container.querySelector('#radar-symbol')?.addEventListener('input', () => {
    _view.page = 1;
    renderFieldPreviews();
    renderItems();
  });
  _container.querySelector('#radar-universe')?.addEventListener('input', renderFieldPreviews);
  _container.querySelector('#market-radar-feed')?.addEventListener('click', (event) => {
    const itemButton = event.target.closest('[data-radar-item-id]');
    if (itemButton) {
      _selectedItemId = itemButton.getAttribute('data-radar-item-id');
      renderItems();
      return;
    }
    const button = event.target.closest('[data-radar-page]');
    if (!button || button.disabled) return;
    _view.page = Number(button.getAttribute('data-radar-page')) || 1;
    renderItems();
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
  return splitTokens(_container.querySelector('#radar-universe')?.value || 'AAPL', { uppercase: true, delimiters: /[,\s]+/ });
}

function providers() {
  return splitTokens(_container.querySelector('#radar-provider')?.value || '', { delimiters: /[,|\s]+/ });
}

function symbolFilter() {
  return String(_container.querySelector('#radar-symbol')?.value || '').trim().toUpperCase();
}

function renderFieldPreviews() {
  _container.querySelector('#radar-universe-preview').innerHTML = renderTokenPreview(universe(), {
    uppercase: true,
    maxItems: 6,
    tone: 'accent',
  });
  _container.querySelector('#radar-provider-preview').innerHTML = renderTokenPreview(providers(), {
    maxItems: 6,
    tone: 'neutral',
    emptyLabel: getLang() === 'zh' ? '全部来源' : 'All providers',
  });
  const symbol = symbolFilter();
  _container.querySelector('#radar-symbol-preview').innerHTML = renderTokenPreview(symbol ? [symbol] : [], {
    tone: 'accent',
    emptyLabel: getLang() === 'zh' ? '全部股票' : 'All symbols',
  });
}

async function scanRadar() {
  const feed = _container.querySelector('#market-radar-feed');
  setLoading(feed, t('Scanning free-tier providers...', '正在扫描免费数据源...'));
  try {
    const payload = await api.connectors.liveScan({
      universe: universe(),
      providers: providers(),
      quota_guard: true,
      persist: true,
      limit: 24,
    });
    _items = payload.items || [];
    _lastLineage = payload.lineage || defaultLineage();
    _selectedItemId = _items[0]?.item_id || null;
    _view.page = 1;
    await refreshTradingOverlay();
    renderItems(payload);
  } catch (err) {
    renderError(feed, err);
  }
}

async function refreshEvidence() {
  const feed = _container.querySelector('#market-radar-feed');
  setLoading(feed, t('Loading evidence lake...', '正在加载证据湖...'));
  try {
    const payload = await api.intelligence.evidence(null, 40);
    _items = payload.items || [];
    _lastLineage = payload.lineage || defaultLineage();
    _selectedItemId = _items[0]?.item_id || null;
    _view.page = 1;
    await refreshTradingOverlay();
    renderItems(payload);
  } catch (err) {
    renderError(feed, err);
  }
}

async function refreshTradingOverlay() {
  const tasks = await Promise.allSettled([
    api.trading.sentimentRun({
      universe: universe(),
      providers: providers(),
      quota_guard: true,
    }),
    api.trading.alertsToday(),
  ]);
  _lastSentiment = tasks[0].status === 'fulfilled' ? tasks[0].value : null;
  _lastAlerts = tasks[1].status === 'fulfilled' ? tasks[1].value?.alerts || [] : [];
}

function filteredItems() {
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

function renderEvidencePage(items, pageItems, pageCount) {
  if (!items.length) return emptyState();
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
  return `
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
        ${miniMetric(t('Page', '页码'), `${_view.page}/${pageCount}`)}
        ${miniMetric(t('Visible', '当前显示'), `${pageItems.length}`)}
        ${miniMetric(t('Top q', '最高质量'), num(topQuality))}
        ${miniMetric(t('Lead', '首条股票'), esc(leadSymbol))}
      </div>
      <div class="workbench-kv-list compact-kv-list radar-feed-footer__list">
        <div class="workbench-kv-row"><span>${t('Page providers', '当前页来源')}</span><strong>${esc(pageProviders.join(', ') || '-')}</strong></div>
        <div class="workbench-kv-row"><span>${t('Decision lane', '决策通道')}</span><strong>${pageItems.some((item) => String(item.leakage_guard || '').includes('safe')) ? t('as-of safe', '时点安全') : t('review', '复核')}</strong></div>
      </div>
      <section class="radar-selected-evidence">
        <div class="workbench-section__title">${t('Selected Evidence', '当前选中证据')}</div>
        <div class="radar-selected-evidence__head">
          <div>
            <strong>${esc(selected?.title || '-')}</strong>
            <span>${esc(selected?.summary || '')}</span>
          </div>
          ${statusBadge(selected?.item_type || 'evidence')}
        </div>
        <div class="workbench-mini-grid radar-feed-mini-grid">
          ${miniMetric(t('Confidence', '置信度'), num(selected?.confidence || selected?.quality_score || 0))}
          ${miniMetric(t('Quality', '质量'), num(selected?.quality_score || selected?.confidence || 0))}
          ${miniMetric(t('Freshness', '新鲜度'), num(selected?.confidence || 0))}
          ${miniMetric(t('Lineage', '链路'), selected?.provider ? t('linked', '已关联') : t('pending', '待处理'))}
        </div>
        <div class="workbench-kv-list compact-kv-list radar-selected-evidence__meta">
          ${detailMeta.map(([label, value]) => `<div class="workbench-kv-row"><span>${esc(label)}</span><strong>${esc(value)}</strong></div>`).join('')}
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
  _container.querySelector('#market-radar-summary').innerHTML = `
    <div class="quality-summary-panel">
      <div class="workbench-metric-grid">
        ${metric(t('Items', '条目数'), filtered.length, 'positive')}
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
          <div class="workbench-kv-row"><span>${c('provider')}</span><strong>${esc(providers().join(', ') || t('all', '全部'))}</strong></div>
          <div class="workbench-kv-row"><span>${c('symbol')}</span><strong>${esc(symbolFilter() || t('all', '全部'))}</strong></div>
          <div class="workbench-kv-row"><span>${c('freshness')}</span><strong>${num(freshnessValue)}</strong></div>
        </div>
      </section>
      <section class="workbench-section">
        <div class="workbench-section__title">${c('sentiment')}</div>
        <div class="workbench-metric-grid">
          ${metric(t('Polarity', '极性'), num(symbolSentiment?.polarity || _lastSentiment?.overall_polarity || 0), (Number(symbolSentiment?.polarity || _lastSentiment?.overall_polarity || 0) || 0) >= 0 ? 'positive' : 'risk')}
          ${metric(t('Confidence', '置信度'), num(symbolSentiment?.confidence || _lastSentiment?.confidence || 0))}
          ${metric(t('Headlines', '标题数'), symbolSentiment?.article_count || _lastSentiment?.headline_count || 0)}
          ${metric(t('Freshness', '新鲜度'), num(symbolSentiment?.freshness_score || _lastSentiment?.freshness_score || 0))}
        </div>
        <div class="workbench-kv-list compact-kv-list">
          <div class="workbench-kv-row"><span>${t('Feature score', '特征分数')}</span><strong>${num(symbolSentiment?.feature_value || 50)}</strong></div>
          <div class="workbench-kv-row"><span>${t('Snapshot', '快照')}</span><strong>${esc(_lastSentiment?.snapshot_id || '-')}</strong></div>
          <div class="workbench-kv-row"><span>${t('Sources', '来源构成')}</span><strong>${esc(Object.entries(symbolSentiment?.source_mix || _lastSentiment?.source_mix || {}).map(([key, value]) => `${key}:${value}`).join(' | ') || '-')}</strong></div>
        </div>
      </section>
      <section class="workbench-section">
        <div class="workbench-section__title">${c('ready')}</div>
        <div class="preview-step-grid">
          ${lineage.slice(0, 4).map((step) => `<div class="preview-step"><span>${esc(step)}</span><strong>${t('safe', '安全')}</strong></div>`).join('')}
          <div class="preview-step"><span>${t('Frozen paper inputs', '论文冻结输入')}</span><strong>${t('untouched', '未触碰')}</strong></div>
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
        <div class="workbench-section__title">${t('Latest item', '最新条目')}</div>
        <div class="workbench-kv-list compact-kv-list">
          <div class="workbench-kv-row"><span>${t('Symbol', '股票')}</span><strong>${esc(latest?.symbol || '-')}</strong></div>
          <div class="workbench-kv-row"><span>${t('Provider', '来源')}</span><strong>${esc(latest?.provider || '-')}</strong></div>
          <div class="workbench-kv-row"><span>${t('Type', '类型')}</span><strong>${esc(latest?.item_type || '-')}</strong></div>
          <div class="workbench-kv-row"><span>${t('Confidence', '置信度')}</span><strong>${num(latest?.confidence || latest?.quality_score || 0)}</strong></div>
        </div>
      </section>
    </div>`;
}
