import { api } from '../qtapi.js?v=8';
import { toast } from '../components/toast.js?v=8';
import { getLang, onLangChange } from '../i18n.js?v=8';
import {
  emptyState,
  esc,
  loadPayloadSnapshot,
  metric,
  num,
  pct,
  persistPayloadSnapshot,
  renderDegradedNotice,
  readSymbol,
  readUniverse,
  renderError,
  renderFactorCards,
  renderMarketDepthDiagnostics,
  renderProtectionReport,
  renderRegistryGate,
  renderTokenPreview,
  setLoading,
  splitTokens,
  statusBadge,
} from './workbench-utils.js?v=8';

let _container = null;
let _langCleanup = null;
let _latest = { cards: [], payload: null };
let _view = { page: 1, pageSize: 10, status: '' };
let _degradedMeta = null;

const FACTOR_LAB_CACHE_KEY = 'qt.factor-lab.snapshot.v1';
const FACTOR_LAB_CACHE_TTL_MS = 30 * 60 * 1000;

const STATUS_FILTERS = [
  { value: '', key: 'all' },
  { value: 'promoted', key: 'promoted' },
  { value: 'research_only', key: 'researchOnly' },
  { value: 'low_confidence', key: 'lowConfidence' },
  { value: 'rejected', key: 'rejected' },
];

const COPY = {
  en: {
    title: 'Factor Lab',
    subtitle: 'Candidate generation, IC / RankIC gates, cost sensitivity, and FactorCards',
    refresh: 'Refresh Registry',
    setup: 'Discovery Setup',
    setupSub: 'As-of feature store and leakage gate stay active for every run.',
    symbol: 'Anchor Symbol',
    horizon: 'Horizon Days',
    universe: 'Universe',
    query: 'Discovery Question',
    queryValue: 'Find ESG, event, novelty, and risk factors with evidence-linked lineage.',
    minIc: 'Min |IC|',
    discover: 'Discover Factors',
    cards: 'Top Factor Cards',
    table: 'IC / RankIC Gate Browser',
    lineage: 'Promotion Policy + Lineage',
    loading: 'Discovering factors...',
    registryLoading: 'Loading factor registry...',
    all: 'All',
    promoted: 'Promoted',
    researchOnly: 'Research Only',
    lowConfidence: 'Low Confidence',
    rejected: 'Rejected',
    summary: 'Factor Run Summary',
    checklist: 'Promotion Checklist',
    total: 'Candidates',
    visible: 'Filtered',
    avgIc: 'Avg |IC|',
    lastRun: 'Last run',
    asofSafe: 'As-of safe',
    sampleSize: 'Sample size',
    icGate: 'IC gate',
    costGate: 'Cost gate',
    corrGate: 'Correlation gate',
    pass: 'pass',
    review: 'review',
    prev: 'Prev',
    next: 'Next',
    showing: 'Showing',
    rows: 'rows',
    topCards: 'Top cards stay compact here; the full gated matrix is paged below.',
    policy: 'Promotion Policy',
    lineageSteps: 'Lineage Steps',
    failureModes: 'Failure Modes',
    gateCounts: 'Gate Counts',
    noFailures: 'No blocking failure modes in the current filter.',
    noLineage: 'Lineage will appear after discovery or registry refresh.',
  },
  zh: {
    title: '因子实验室',
    subtitle: '候选因子发现、IC / RankIC 门禁、成本敏感性与因子卡复核',
    refresh: '刷新注册表',
    setup: '因子发现设置',
    setupSub: '每次运行都启用 as-of 特征、泄漏检查和升格门禁。',
    symbol: '核心股票',
    horizon: '预测天数',
    universe: '股票池',
    query: '发现问题',
    queryValue: '从 ESG、事件、新颖度和风险证据链中发现可回测因子。',
    minIc: '最小 |IC|',
    discover: '发现因子',
    cards: '精选因子卡',
    table: 'IC / RankIC 门禁浏览器',
    lineage: '升格规则与血缘',
    loading: '正在发现因子...',
    registryLoading: '正在加载因子注册表...',
    all: '全部',
    promoted: '已升格',
    researchOnly: '仅研究',
    lowConfidence: '低置信',
    rejected: '已拒绝',
    summary: '因子运行摘要',
    checklist: '升格检查清单',
    total: '候选数',
    visible: '筛选后',
    avgIc: '平均 |IC|',
    lastRun: '最近运行',
    asofSafe: '时点安全',
    sampleSize: '样本量',
    icGate: 'IC 门禁',
    costGate: '成本门禁',
    corrGate: '相关性门禁',
    pass: '通过',
    review: '复核',
    prev: '上一页',
    next: '下一页',
    showing: '显示',
    rows: '条',
    topCards: '上方只保留最强因子的摘要预览，完整矩阵在下方分页浏览。',
    policy: '升格规则',
    lineageSteps: '血缘步骤',
    failureModes: '失败模式',
    gateCounts: '门禁计数',
    noFailures: '当前筛选下没有阻塞性失败模式。',
    noLineage: '运行发现或刷新注册表后会显示血缘。',
  },
};

export async function render(container) {
  _container = container;
  container.innerHTML = buildShell();
  bindEvents(container);
  renderConfigPreview();
  hydrateFactorSnapshot(container);
  _langCleanup ||= onLangChange(() => {
    if (_container?.isConnected) {
      _container.innerHTML = buildShell();
      bindEvents(_container);
      renderConfigPreview();
      renderResults(_container, _latest.cards, _latest.payload);
    }
  });
  await refreshRegistry(container, false);
}

export function destroy() {
  _container = null;
  _latest = { cards: [], payload: null };
  _view = { page: 1, pageSize: 10, status: '' };
  _degradedMeta = null;
  _langCleanup?.();
  _langCleanup = null;
}

function c(key) {
  const current = getLang() === 'zh' ? 'zh' : 'en';
  return COPY[current][key] || COPY.en[key] || key;
}

function factorLabDegradedState(savedAt, reason) {
  return {
    tone: 'warning',
    saved_at: savedAt || null,
    title: getLang() === 'zh' ? '因子实验室已切换到缓存快照' : 'Factor Lab is showing a cached snapshot',
    reason: reason || (getLang() === 'zh'
      ? '当前继续展示最近一次成功的因子结果，等待注册表或发现任务恢复。'
      : 'The latest successful factor payload is still visible while registry or discovery requests recover.'),
    detail: getLang() === 'zh'
      ? '保护报告、数据集清单和注册表门禁都会继续跟随这份快照展示。'
      : 'Protection reports, dataset lineage, and registry gate status remain visible from the snapshot.',
    action: getLang() === 'zh'
      ? '可以继续点“刷新注册表”或“发现因子”重试。'
      : 'Use Refresh Registry or Discover Factors to retry.',
  };
}

function hydrateFactorSnapshot(container) {
  const cached = loadPayloadSnapshot(FACTOR_LAB_CACHE_KEY, FACTOR_LAB_CACHE_TTL_MS);
  if (!cached?.payload) return false;
  _latest = {
    cards: cached.payload.factor_cards || cached.payload.factors || [],
    payload: cached.payload,
  };
  _degradedMeta = factorLabDegradedState(
    cached.saved_at,
    getLang() === 'zh'
      ? '正在回填最近一次成功的因子快照，并在后台重连服务。'
      : 'Rehydrating the latest successful factor snapshot while the page reconnects.',
  );
  renderResults(container, _latest.cards, _latest.payload);
  return true;
}

function buildShell() {
  return `
  <div class="workbench-page factor-lab-page" data-no-autotranslate="true">
    <div class="page-header">
      <div>
        <div class="page-header__title">${c('title')}</div>
        <div class="page-header__sub">${c('subtitle')}</div>
      </div>
      <div class="page-header__actions">
        <button class="btn btn-ghost btn-sm" id="btn-factor-refresh">${c('refresh')}</button>
      </div>
    </div>

    <div class="grid-col-1-2 workbench-top-grid factor-lab-top-grid">
      <section class="run-panel factor-run-panel">
        <div class="run-panel__header">
          <div class="run-panel__title">${c('setup')}</div>
          <div class="run-panel__sub">${c('setupSub')}</div>
        </div>
        <div class="run-panel__body">
          <div class="form-row">
            <div class="form-group">
              <label class="form-label">${c('symbol')}</label>
              <input class="form-input" id="factor-symbol" value="AAPL" autocomplete="off">
            </div>
            <div class="form-group">
              <label class="form-label">${c('horizon')}</label>
              <input class="form-input" id="factor-horizon" type="number" value="20" min="1" max="252">
            </div>
          </div>
          <div class="form-group">
            <label class="form-label">${c('universe')}</label>
            <input class="form-input" id="factor-universe" value="AAPL, MSFT, NVDA, NEE">
          </div>
          <div class="form-row">
            <div class="form-group">
              <label class="form-label">Data Mode</label>
              <select class="form-input" id="factor-mode">
                <option value="local">local / cached</option>
                <option value="mixed">mixed free-tier live</option>
              </select>
            </div>
            <div class="form-group">
              <label class="form-label">Evidence Run ID</label>
              <input class="form-input" id="factor-evidence-run" placeholder="optional evidence bundle id">
            </div>
          </div>
          <div id="factor-config-preview" class="config-token-strip"></div>
          <div class="form-group">
            <label class="form-label">${c('query')}</label>
            <textarea class="form-textarea" id="factor-query" rows="3">${c('queryValue')}</textarea>
          </div>
          <div class="form-group">
            <label class="form-label">${c('minIc')}</label>
            <input class="form-input" id="factor-min-ic" type="number" value="0" min="0" max="1" step="0.01">
          </div>
          <div id="factor-run-summary" class="factor-run-summary"></div>
        </div>
        <div class="run-panel__foot workbench-action-grid">
          <button class="btn btn-primary workbench-action-btn" id="btn-factor-discover">${c('discover')}</button>
          <button class="btn btn-ghost workbench-action-btn" id="btn-factor-refresh-bottom">${c('refresh')}</button>
        </div>
      </section>

      <section class="card factor-lineage-card">
        <div class="card-header"><span class="card-title">${c('lineage')}</span></div>
        <div class="card-body factor-lineage-card__body">
          <div id="factor-lineage-panel"></div>
          <section class="factor-card-panel-card factor-card-panel-card--inline">
            <div class="workbench-section__title">${c('cards')}</div>
            <div id="factor-card-panel"></div>
          </section>
        </div>
      </section>
    </div>

    <section class="card factor-gate-card">
      <div class="card-header"><span class="card-title">${c('table')}</span></div>
      <div class="card-body" id="factor-table-panel"></div>
    </section>
  </div>`;
}

function bindEvents(container) {
  container.querySelector('#btn-factor-refresh')?.addEventListener('click', () => refreshRegistry(container, true));
  container.querySelector('#btn-factor-refresh-bottom')?.addEventListener('click', () => refreshRegistry(container, true));
  container.querySelector('#btn-factor-discover')?.addEventListener('click', () => runDiscover(container));
  ['#factor-symbol', '#factor-universe', '#factor-mode', '#factor-evidence-run'].forEach((selector) => {
    container.querySelector(selector)?.addEventListener('input', renderConfigPreview);
    container.querySelector(selector)?.addEventListener('change', renderConfigPreview);
  });
  container.querySelector('#factor-min-ic')?.addEventListener('input', () => {
    _view.page = 1;
    renderResults(container, _latest.cards, _latest.payload);
  });
  container.querySelector('#factor-table-panel')?.addEventListener('click', (event) => {
    const statusButton = event.target.closest('[data-factor-status]');
    if (statusButton) {
      _view.status = statusButton.getAttribute('data-factor-status') || '';
      _view.page = 1;
      renderResults(container, _latest.cards, _latest.payload);
      return;
    }
    const pageButton = event.target.closest('[data-factor-page]');
    if (pageButton && !pageButton.disabled) {
      _view.page = Number(pageButton.getAttribute('data-factor-page')) || 1;
      renderResults(container, _latest.cards, _latest.payload);
    }
  });
}

function readConfig(container) {
  const symbol = readSymbol(container, '#factor-symbol', 'AAPL');
  return {
    symbol,
    universe: readUniverse(container.querySelector('#factor-universe')?.value, symbol),
    query: container.querySelector('#factor-query')?.value || '',
    horizon_days: Number(container.querySelector('#factor-horizon')?.value) || 20,
    mode: container.querySelector('#factor-mode')?.value || 'local',
    evidence_run_id: container.querySelector('#factor-evidence-run')?.value || null,
  };
}

function renderConfigPreview() {
  if (!_container) return;
  const cfg = readConfig(_container);
  const host = _container.querySelector('#factor-config-preview');
  if (!host) return;
  host.innerHTML = `
    <div class="config-token-strip__block">
      <span class="config-token-strip__label">${c('universe')}</span>
      ${renderTokenPreview(cfg.universe, { tone: 'accent', maxItems: 6 })}
    </div>
    <div class="config-token-strip__block">
      <span class="config-token-strip__label">Mode</span>
      ${renderTokenPreview([cfg.mode], { tone: 'neutral', maxItems: 1 })}
    </div>
    <div class="config-token-strip__block">
      <span class="config-token-strip__label">Evidence Run</span>
      ${renderTokenPreview(cfg.evidence_run_id ? [cfg.evidence_run_id] : [], { tone: 'neutral', maxItems: 1, emptyLabel: getLang() === 'zh' ? '自动选择' : 'auto' })}
    </div>
  `;
}

function normalizeStatus(status) {
  return String(status || 'research_only').trim().toLowerCase().replace(/[\s-]+/g, '_');
}

function filteredByMinIc(container, cards) {
  const minIc = Math.abs(Number(container.querySelector('#factor-min-ic')?.value || 0));
  return (cards || []).filter((card) => !Number.isFinite(minIc) || Math.abs(Number(card.ic || 0)) >= minIc);
}

function filteredCards(container, cards) {
  return filteredByMinIc(container, cards).filter((card) => !_view.status || normalizeStatus(card.status) === _view.status);
}

async function refreshRegistry(container, showToast) {
  if (!container?.isConnected) return;
  setLoading(container.querySelector('#factor-card-panel'), c('registryLoading'));
  try {
    const data = await api.factors.registry(50);
    if (!container?.isConnected) return;
    _latest = { cards: data.factors || data.factor_cards || [], payload: data };
    persistPayloadSnapshot(FACTOR_LAB_CACHE_KEY, data, { source: 'registry' });
    _degradedMeta = null;
    _view.page = 1;
    renderResults(container, _latest.cards, _latest.payload);
    if (showToast) toast.success(c('refresh'), `${_latest.cards.length} cards`);
  } catch (err) {
    if (!container?.isConnected) return;
    const cached = loadPayloadSnapshot(FACTOR_LAB_CACHE_KEY, FACTOR_LAB_CACHE_TTL_MS);
    if (cached?.payload) {
      _latest = {
        cards: cached.payload.factor_cards || cached.payload.factors || [],
        payload: cached.payload,
      };
      _degradedMeta = factorLabDegradedState(cached.saved_at, err.message);
      renderResults(container, _latest.cards, _latest.payload);
      return;
    }
    renderError(container.querySelector('#factor-card-panel'), err, { onRetry: () => refreshRegistry(container, showToast) });
  }
}

async function runDiscover(container) {
  if (!container?.isConnected) return;
  const cfg = readConfig(container);
  setLoading(container.querySelector('#factor-card-panel'), c('loading'));
  try {
    const payload = await api.factors.discover({
      universe: cfg.universe,
      query: cfg.query,
      horizon_days: cfg.horizon_days,
      mode: cfg.mode,
      evidence_run_id: cfg.evidence_run_id,
      quota_guard: true,
    });
    if (!container?.isConnected) return;
    _latest = { cards: payload.factor_cards || [], payload };
    persistPayloadSnapshot(FACTOR_LAB_CACHE_KEY, payload, { source: 'discover' });
    _degradedMeta = null;
    _view.page = 1;
    renderResults(container, _latest.cards, _latest.payload);
    toast.success(c('discover'), `${_latest.cards.length} cards`);
  } catch (err) {
    if (!container?.isConnected) return;
    const cached = loadPayloadSnapshot(FACTOR_LAB_CACHE_KEY, FACTOR_LAB_CACHE_TTL_MS);
    if (cached?.payload) {
      _latest = {
        cards: cached.payload.factor_cards || cached.payload.factors || [],
        payload: cached.payload,
      };
      _degradedMeta = factorLabDegradedState(cached.saved_at, err.message);
      renderResults(container, _latest.cards, _latest.payload);
      toast.error(c('discover'), err.message);
      return;
    }
    renderError(container.querySelector('#factor-card-panel'), err, { onRetry: () => runDiscover(container) });
    toast.error(c('discover'), err.message);
  }
}

function renderResults(container, cards, payload) {
  if (!container?.isConnected) return;
  const allCards = cards || [];
  const statusBase = filteredByMinIc(container, allCards);
  const visible = filteredCards(container, allCards);
  const pageCount = Math.max(1, Math.ceil(visible.length / _view.pageSize));
  _view.page = Math.min(Math.max(1, _view.page), pageCount);
  const pageItems = visible.slice((_view.page - 1) * _view.pageSize, _view.page * _view.pageSize);
  const degradedBanner = _degradedMeta ? renderDegradedNotice(_degradedMeta) : '';

  const panel = container.querySelector('#factor-card-panel');
  if (!panel) return;
  panel.innerHTML = `
    ${degradedBanner}
    <div class="workbench-metric-grid factor-card-metrics">
      ${metric(getLang() === 'zh' ? '因子数' : 'Factors', num(visible.length, 0))}
      ${metric(c('promoted'), num(visible.filter((card) => normalizeStatus(card.status) === 'promoted').length, 0), 'positive')}
      ${metric('Avg IC', num(avg(visible.map((card) => Math.abs(Number(card.ic || 0))))) )}
      ${metric(getLang() === 'zh' ? '低置信' : 'Low Conf', num(visible.filter((card) => normalizeStatus(card.status) === 'low_confidence').length, 0))}
    </div>
    <p class="workbench-report-text factor-card-hint">${c('topCards')}</p>
    ${renderFactorCards(visible, { maxItems: 4, compact: true })}
  `;
  renderRunSummary(container, allCards, visible, payload);
  renderLineage(container, payload, statusBase);
  renderTable(container, statusBase, visible, pageItems, pageCount);
}

function renderRunSummary(container, cards, visible, payload) {
  if (!container?.isConnected) return;
  const target = container.querySelector('#factor-run-summary');
  if (!target) return;
  const counts = statusCounts(cards);
  const cfg = readConfig(container);
  const avgAbsIc = avg(visible.map((card) => Math.abs(Number(card.ic || 0))));
  const sampleAvg = avg(visible.map((card) => Number(card.sample_count || 0)));
  const lastRun = payload?.run_id || payload?.registry_id || payload?.generated_at || 'registry';
  const dataset = payload?.dataset_manifest || payload?.latest_dataset_manifest || {};
  const protection = payload?.protection_report || payload?.latest_protection_report || {};
  const checks = [
    { label: c('asofSafe'), value: String(protection?.checks?.as_of_leakage?.passed) === 'true' ? c('pass') : c('review') },
    { label: c('sampleSize'), value: sampleAvg >= 3 ? c('pass') : c('review') },
    { label: c('icGate'), value: avgAbsIc > 0 ? c('pass') : c('review') },
    { label: c('costGate'), value: visible.some((card) => String(card.transaction_cost_sensitivity || '').includes('high')) ? c('review') : c('pass') },
    { label: c('corrGate'), value: protection?.protection_status === 'blocked' ? c('review') : c('pass') },
  ];
  target.innerHTML = `
    <div class="factor-summary-block">
      <div class="workbench-section__title">${c('summary')}</div>
      <div class="factor-summary-grid">
        <div><span>${c('total')}</span><strong>${num(cards.length, 0)}</strong></div>
        <div><span>${c('visible')}</span><strong>${num(visible.length, 0)}</strong></div>
        <div><span>${c('avgIc')}</span><strong>${num(avgAbsIc)}</strong></div>
        <div><span>${c('promoted')}</span><strong>${num(counts.promoted || 0, 0)}</strong></div>
      </div>
      <div class="factor-summary-meta">
        <span>${esc(cfg.universe.join(', '))}</span>
        <span>${esc(cfg.horizon_days)}d</span>
        <span>${esc((dataset.frequency || 'daily') + ' / ' + (dataset.data_tier || 'l1'))}</span>
        <span title="${esc(lastRun)}">${esc(String(lastRun).slice(0, 36))}</span>
      </div>
      <div class="factor-summary-meta">
        <span>${esc(dataset.dataset_id || 'dataset-pending')}</span>
        <span>${esc((dataset.provider_chain || []).join(' > ') || 'provider-chain-pending')}</span>
      </div>
    </div>
    <div class="factor-summary-block">
      <div class="workbench-section__title">${c('checklist')}</div>
      <div class="factor-checklist">
        ${checks.map((item) => `
          <div class="factor-check-row">
            <span>${esc(item.label)}</span>
            <strong class="${item.value === c('pass') ? 'is-pass' : 'is-review'}">${esc(item.value)}</strong>
          </div>
        `).join('')}
      </div>
    </div>`;
}

function renderTable(container, statusBase, cards, pageItems, pageCount) {
  if (!container?.isConnected) return;
  const panel = container.querySelector('#factor-table-panel');
  if (!panel) return;
  const statusTabs = `
    <div class="factor-status-tabs" role="tablist" aria-label="Factor status filter">
      ${STATUS_FILTERS.map((filter) => {
        const active = _view.status === filter.value ? ' active' : '';
        const count = filter.value
          ? statusBase.filter((card) => normalizeStatus(card.status) === filter.value).length
          : statusBase.length;
        return `<button class="factor-status-tab${active}" data-factor-status="${esc(filter.value)}" type="button">
          <span>${esc(c(filter.key))}</span><strong>${num(count, 0)}</strong>
        </button>`;
      }).join('')}
    </div>`;

  if (!cards.length) {
    panel.innerHTML = `${statusTabs}${emptyState()}`;
    return;
  }

  const rows = pageItems.map((card) => {
    const status = normalizeStatus(card.status);
    return `
      <article class="factor-gate-row" data-factor-row>
        <div class="factor-gate-main">
          <div class="factor-gate-cell factor-name-cell">
            <strong>${esc(card.name)}</strong>
            <span>${esc(card.definition || card.description || '')}</span>
          </div>
          <div class="factor-gate-cell"><span>Family</span><strong>${esc(card.family)}</strong></div>
          <div class="factor-gate-cell"><span>Status</span>${statusBadge(status)}</div>
          <div class="factor-gate-cell cell-num"><span>IC</span><strong>${num(card.ic)}</strong></div>
          <div class="factor-gate-cell cell-num"><span>RankIC</span><strong>${num(card.rank_ic)}</strong></div>
          <div class="factor-gate-cell cell-num"><span>Stability</span><strong>${num(card.stability_score)}</strong></div>
          <div class="factor-gate-cell"><span>Cost</span><strong>${esc(card.transaction_cost_sensitivity || 'medium')}</strong></div>
        </div>
        <div class="factor-gate-detail">
          <span>tier ${esc(card.data_tier || 'l1')}</span>
          <span>gate ${esc(card.registry_gate_status || card.protection_status || 'review')}</span>
          <span>turnover ${num(card.turnover_estimate)}</span>
          <span>missing ${pct(card.missing_rate)}</span>
          <span>samples ${num(card.sample_count, 0)}</span>
          <span>${esc((card.blocking_reasons || [])[0] || (card.failure_modes || [])[0] || 'gate passed or pending review')}</span>
        </div>
      </article>`;
  }).join('');

  const start = (Math.max(1, _view.page) - 1) * _view.pageSize + 1;
  const end = Math.min(cards.length, _view.page * _view.pageSize);
  const degradedBanner = _degradedMeta ? renderDegradedNotice(_degradedMeta) : '';
  panel.innerHTML = `
    ${degradedBanner}
    ${statusTabs}
    <div class="factor-gate-table factor-gate-table--browser" data-page-size="${_view.pageSize}">
      ${rows}
    </div>
    <div class="factor-pagination">
      <span>${c('showing')} ${start}-${end} / ${cards.length} ${c('rows')}</span>
      <div class="factor-pagination__buttons">
        <button class="factor-page-btn factor-page-prev" type="button" data-factor-page="${_view.page - 1}" ${_view.page <= 1 ? 'disabled' : ''}>${c('prev')}</button>
        ${Array.from({ length: pageCount }, (_, index) => index + 1).map((page) => `
          <button class="factor-page-btn factor-page-number${page === _view.page ? ' active' : ''}" type="button" data-factor-page="${page}">${page}</button>
        `).join('')}
        <button class="factor-page-btn factor-page-next" type="button" data-factor-page="${_view.page + 1}" ${_view.page >= pageCount ? 'disabled' : ''}>${c('next')}</button>
      </div>
    </div>`;
}

function renderLineage(container, payload, cards) {
  if (!container?.isConnected) return;
  const panel = container.querySelector('#factor-lineage-panel');
  if (!panel) return;
  const policy = payload?.promotion_policy || payload?.registry_policy || 'Only promoted factors can become runtime inputs; research-only factors remain visible but gated.';
  const lineage = Array.isArray(payload?.lineage) && payload.lineage.length
    ? payload.lineage.slice(0, 5)
    : [
        'candidate generation',
        'as-of feature build',
        'IC / RankIC gate',
        'cost sensitivity review',
        'registry promotion decision',
      ];
  const failures = Array.from(new Set(cards.flatMap((card) => card.failure_modes || []))).slice(0, 4);
  const counts = statusCounts(cards);
  const dataset = payload?.dataset_manifest || payload?.latest_dataset_manifest || {};
  const protection = payload?.protection_report || payload?.latest_protection_report || {};
  const registryGate = {
    registry_gate_status: protection?.protection_status === 'blocked'
      ? 'blocked'
      : (cards.some((card) => String(card.registry_gate_status || '').toLowerCase() === 'pass') ? 'pass' : 'review'),
    required_frequency: dataset.frequency || 'daily',
    required_data_tier: dataset.data_tier || 'l1',
    eligible_for_execution: cards.some((card) => String(card.registry_gate_status || '').toLowerCase() === 'pass'),
    blocking_reasons: protection?.blocking_reasons || [],
  };
  const degradedBanner = _degradedMeta ? renderDegradedNotice(_degradedMeta) : '';
  panel.innerHTML = `
    ${degradedBanner}
    <div class="workbench-metric-grid factor-lineage-metrics">
      ${metric(c('promoted'), num(counts.promoted || 0, 0), 'positive')}
      ${metric(c('researchOnly'), num(counts.research_only || 0, 0))}
      ${metric(c('lowConfidence'), num(counts.low_confidence || 0, 0))}
      ${metric(c('rejected'), num(counts.rejected || 0, 0), 'risk')}
    </div>
    <div class="factor-lineage-stack">
      <section class="workbench-section">
        <div class="workbench-section__title">${c('policy')}</div>
        <div class="workbench-report-text">${esc(typeof policy === 'string' ? policy : JSON.stringify(policy, null, 2))}</div>
      </section>
      ${renderRegistryGate(registryGate)}
      ${renderProtectionReport(protection)}
      ${renderMarketDepthDiagnostics(dataset.market_depth_status)}
      <section class="workbench-section">
        <div class="workbench-section__title">${c('lineageSteps')}</div>
        <div class="factor-lineage-steps">
          ${lineage.map((item, index) => `
            <div class="factor-lineage-step">
              <strong>${index + 1}</strong>
              <span>${esc(item)}</span>
            </div>
          `).join('') || emptyState(c('noLineage'))}
        </div>
      </section>
      <section class="workbench-section">
        <div class="workbench-section__title">${c('failureModes')}</div>
        <div class="workbench-list factor-failure-list">
          ${failures.length ? failures.map((item) => `<div class="workbench-kv-row"><span>${esc(item)}</span></div>`).join('') : emptyState(c('noFailures'))}
        </div>
      </section>
    </div>`;
}

function statusCounts(cards) {
  return (cards || []).reduce((acc, card) => {
    const status = normalizeStatus(card.status);
    acc[status] = (acc[status] || 0) + 1;
    return acc;
  }, {});
}

function avg(values) {
  const clean = values.filter((value) => Number.isFinite(value));
  return clean.length ? clean.reduce((sum, value) => sum + value, 0) / clean.length : 0;
}
