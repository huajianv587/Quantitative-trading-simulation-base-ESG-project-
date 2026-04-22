import { api } from '../qtapi.js?v=8';
import { getLang, onLangChange } from '../i18n.js?v=8';
import {
  emptyState,
  esc,
  metric,
  num,
  renderError,
  renderTokenPreview,
  setLoading,
  splitTokens,
  statusBadge,
} from './workbench-utils.js?v=8';

let _container = null;
let _langCleanup = null;
let _registry = null;

const COPY = {
  en: {
    title: 'Connector Center',
    subtitle: 'Free-tier live data status, quota guard, sample payloads, and failure isolation.',
    health: 'Check Health',
    test: 'Dry Test',
    live: 'Live Scan',
    refresh: 'Refresh',
    providers: 'Providers',
    symbol: 'Symbol',
    universe: 'Universe',
    registry: 'Provider Registry',
    result: 'Connector Result',
    quota: 'Quota Guard',
    mode: 'free-tier shadow mode',
    previewTitle: 'Ready for connector check',
    previewText: 'Run health, dry test, or live scan. Every source is isolated and keys stay masked.',
    sample: 'Sample Payload',
    isolated: 'Failure Isolation',
    protected: 'Quota Guard',
    parseTitle: 'Parsed Control Surface',
    parseHint: 'Inputs are tokenized before each run so long provider chains stay readable.',
    symbolLabel: 'Primary symbol',
    universeLabel: 'Universe preview',
    providerLabel: 'Provider chain',
  },
  zh: {
    title: '数据源中心',
    subtitle: '免费档实时数据状态、额度保护、样本载荷和失败隔离。',
    health: '检查状态',
    test: '干跑测试',
    live: '实时扫描',
    refresh: '刷新',
    providers: '数据源',
    symbol: '股票',
    universe: '股票池',
    registry: '数据源注册表',
    result: '连接结果',
    quota: '额度保护',
    mode: '免费档影子模式',
    previewTitle: '可以开始连接检查',
    previewText: '运行健康检查、干跑测试或实时扫描。每个数据源独立失败，密钥不会显示。',
    sample: '样本载荷',
    isolated: '失败隔离',
    protected: '额度保护',
    parseTitle: '输入解析结果',
    parseHint: '每次运行前都会把输入拆成 token，长 provider 链也能保持可读。',
    symbolLabel: '主股票',
    universeLabel: '股票池预览',
    providerLabel: '数据源链路',
  },
};

function c(key) {
  const lang = getLang() === 'zh' ? 'zh' : 'en';
  return COPY[lang][key] || COPY.en[key] || key;
}

function isMounted() {
  return Boolean(_container && _container.isConnected);
}

export async function render(container) {
  _container = container;
  renderShell();
  wire();
  _langCleanup = onLangChange(() => {
    if (_container) {
      renderShell();
      wire();
      if (_registry) renderRegistry(_registry);
      renderInitialResultIntoTarget();
    }
  });
  await refreshRegistry();
}

export function unmount() {
  if (_langCleanup) _langCleanup();
  _container = null;
}

function renderShell() {
  if (!_container) return;
  _container.innerHTML = `
    <div class="workbench-page live-page connector-center-page">
      <section class="run-panel">
        <div class="run-panel__header">
          <div class="run-panel__title">${c('title')}</div>
          <div class="run-panel__sub">${c('subtitle')}</div>
        </div>
        <div class="run-panel__body">
          <div class="grid-3 compact-control-grid live-control-grid">
            <label class="field field--with-preview">
              <span>${c('symbol')}</span>
              <input id="connector-symbol" value="AAPL">
              <div id="connector-symbol-preview"></div>
            </label>
            <label class="field field--with-preview">
              <span>${c('universe')}</span>
              <input id="connector-universe" value="AAPL, MSFT, NVDA">
              <div id="connector-universe-preview"></div>
            </label>
            <label class="field field--with-preview">
              <span>${c('providers')}</span>
              <input id="connector-providers" value="local_esg, marketaux, twelvedata">
              <div id="connector-providers-preview"></div>
            </label>
          </div>
        </div>
        <div class="run-panel__foot workbench-action-grid connector-action-grid">
          <button class="btn btn-primary workbench-action-btn" id="btn-connector-health">${c('health')}</button>
          <button class="btn btn-ghost workbench-action-btn" id="btn-connector-test">${c('test')}</button>
          <button class="btn btn-primary workbench-action-btn" id="btn-connector-live-scan">${c('live')}</button>
          <button class="btn btn-ghost workbench-action-btn" id="btn-connector-refresh">${c('refresh')}</button>
        </div>
      </section>
      <section class="grid-2 workbench-main-grid workbench-equal-grid connector-main-grid">
        <article class="run-panel connector-registry-panel">
          <div class="run-panel__header"><div class="run-panel__title">${c('registry')}</div><div class="run-panel__sub">${c('mode')}</div></div>
          <div class="run-panel__body connector-registry-body" id="connector-registry">${emptyState('Loading registry')}</div>
        </article>
        <article class="run-panel">
          <div class="run-panel__header"><div class="run-panel__title">${c('result')}</div><div class="run-panel__sub">${c('quota')}</div></div>
          <div class="run-panel__body" id="connector-result">${renderInitialResult()}</div>
        </article>
      </section>
    </div>`;
  renderFieldPreviews();
}

function wire() {
  if (!_container) return;
  _container.querySelector('#btn-connector-refresh')?.addEventListener('click', refreshRegistry);
  _container.querySelector('#btn-connector-health')?.addEventListener('click', runHealth);
  _container.querySelector('#btn-connector-test')?.addEventListener('click', runDryTest);
  _container.querySelector('#btn-connector-live-scan')?.addEventListener('click', runLiveScan);
  ['#connector-symbol', '#connector-universe', '#connector-providers'].forEach((selector) => {
    _container.querySelector(selector)?.addEventListener('input', () => {
      renderFieldPreviews();
      renderInitialResultIntoTarget();
    });
  });
}

function symbol() {
  if (!_container) return 'AAPL';
  return String(_container.querySelector('#connector-symbol')?.value || 'AAPL').trim().toUpperCase();
}

function providers() {
  if (!_container) return [];
  return splitTokens(_container.querySelector('#connector-providers')?.value || '', { delimiters: /[,|\s]+/ });
}

function universe() {
  if (!_container) return [symbol()];
  return splitTokens(_container.querySelector('#connector-universe')?.value || symbol(), { uppercase: true, delimiters: /[,\s]+/ });
}

function renderFieldPreviews() {
  if (!_container) return;
  _container.querySelector('#connector-symbol-preview').innerHTML = renderTokenPreview([symbol()], {
    tone: 'accent',
    maxItems: 1,
  });
  _container.querySelector('#connector-universe-preview').innerHTML = renderTokenPreview(universe(), {
    uppercase: true,
    maxItems: 6,
    tone: 'accent',
  });
  _container.querySelector('#connector-providers-preview').innerHTML = renderTokenPreview(providers(), {
    maxItems: 6,
    tone: 'neutral',
  });
}

async function refreshRegistry() {
  if (!isMounted()) return;
  const target = _container.querySelector('#connector-registry');
  setLoading(target, 'Loading provider registry...');
  try {
    _registry = await api.connectors.registry();
    if (!isMounted()) return;
    renderRegistry(_registry);
  } catch (err) {
    if (!isMounted()) return;
    renderError(target, err);
  }
}

function shortMode(value) {
  return String(value || 'free-tier').replace('free_tier_first', 'free-tier').replace(/_/g, '-');
}

function renderRegistry(payload) {
  if (!_container) return;
  const target = _container.querySelector('#connector-registry');
  const rows = payload.providers || [];
  const configured = rows.filter((row) => row.configured).length;
  const cards = rows.map((row) => `
    <article class="live-provider-card">
      <div class="live-provider-card__head">
        <strong>${esc(row.display_name)}</strong>
        ${statusBadge(row.configured ? 'configured' : 'missing_key')}
      </div>
      <p>${esc(row.free_tier_note || '')}</p>
      <div class="workbench-mini-grid">
        <div class="workbench-mini-metric"><span>daily</span><strong>${num(row.daily_limit, 0)}</strong></div>
        <div class="workbench-mini-metric"><span>scan</span><strong>${num(row.scan_budget, 0)}</strong></div>
        <div class="workbench-mini-metric"><span>used</span><strong>${num(row.quota?.used_today || 0, 0)}</strong></div>
        <div class="workbench-mini-metric"><span>left</span><strong>${num(row.quota?.remaining_estimate || 0, 0)}</strong></div>
      </div>
      <div class="token-preview token-preview--dense">
        <span class="token-chip token-chip--muted">${esc(row.provider_id)}</span>
        ${(row.capabilities || []).slice(0, 4).map((capability) => `<span class="token-chip token-chip--neutral">${esc(capability)}</span>`).join('')}
      </div>
    </article>`).join('');
  target.innerHTML = `
    <div class="workbench-metric-grid connector-registry-metrics">
      ${metric('Providers', rows.length, 'positive')}
      ${metric('Configured', configured, configured ? 'positive' : '')}
      ${metric('Mode', shortMode(payload.mode || 'free-tier'))}
      ${metric('Feed', payload.defaults?.alpaca_feed || 'iex')}
    </div>
    <div class="connector-provider-shell">
      <div class="live-provider-grid connector-provider-scroll">${cards}</div>
    </div>`;
}

function renderInitialResult() {
  const parsedProviders = providers();
  const parsedUniverse = universe();
  return `
    <div class="live-result-preview connector-result-preview">
      <div>
        <div class="functional-empty__eyebrow">${c('quota')}</div>
        <h3>${c('previewTitle')}</h3>
        <p>${c('previewText')}</p>
      </div>
      <div class="workbench-metric-grid">
        ${metric(c('protected'), 'on', 'positive')}
        ${metric(c('isolated'), 'on', 'positive')}
        ${metric(c('sample'), 'ready')}
        ${metric('providers', parsedProviders.length)}
      </div>
      <section class="workbench-section">
        <div class="workbench-section__title">${c('parseTitle')}</div>
        <div class="workbench-kv-list compact-kv-list">
          <div class="workbench-kv-row"><span>${c('symbolLabel')}</span><strong>${esc(symbol())}</strong></div>
          <div class="workbench-kv-row"><span>${c('universeLabel')}</span><strong>${esc(parsedUniverse.length)}</strong></div>
          <div class="workbench-kv-row"><span>${c('providerLabel')}</span><strong>${esc(parsedProviders.length)}</strong></div>
        </div>
        <p class="workbench-report-text connector-result-hint">${c('parseHint')}</p>
        <div class="preview-step-grid">
          <div class="preview-step"><span>${c('symbolLabel')}</span><strong>${esc(symbol())}</strong></div>
          <div class="preview-step"><span>${c('universeLabel')}</span><strong>${esc(parsedUniverse.join(', ') || '-')}</strong></div>
          <div class="preview-step"><span>${c('providerLabel')}</span><strong>${esc(parsedProviders.join(', ') || '-')}</strong></div>
        </div>
      </section>
      <section class="workbench-section">
        <div class="workbench-section__title">Provider Ladder</div>
        <div class="preview-step-grid">
          ${renderProviderLadder(parsedProviders)}
        </div>
      </section>
      <section class="workbench-section">
        <div class="workbench-section__title">Run Preview</div>
        <div class="factor-checklist">
          <div class="factor-check-row"><span>Quota reserve</span><strong class="is-pass">protected</strong></div>
          <div class="factor-check-row"><span>Failure isolation</span><strong class="is-pass">enabled</strong></div>
          <div class="factor-check-row"><span>Secret redaction</span><strong class="is-pass">masked</strong></div>
        </div>
      </section>
    </div>`;
}

function renderInitialResultIntoTarget() {
  if (!_container) return;
  const target = _container.querySelector('#connector-result');
  if (target) target.innerHTML = renderInitialResult();
}

function renderResult(payload) {
  if (!_container) return;
  const target = _container.querySelector('#connector-result');
  const rows = payload.results || payload.items || payload.providers || [];
  const summary = payload.summary || {};
  const normalized = summary.normalized_count ?? rows.reduce((acc, row) => acc + Number(row.normalized_count || 0), 0);
  const avgLatency = averageLatency(rows);
  const resultRows = Array.isArray(rows)
    ? rows.slice(0, 24).map((row) => `
      <article class="workbench-item">
        <div class="workbench-item__head">
          <strong>${esc(row.provider || row.title || row.item_id || 'connector')}</strong>
          ${statusBadge(row.status || row.item_type || 'evidence')}
        </div>
        <p>${esc(row.failure_reason || row.summary || row.title || '')}</p>
        <div class="workbench-item__meta">
          <span>${esc(row.symbol || '')}</span>
          <span>normalized=${esc(row.normalized_count ?? '')}</span>
          <span>latency=${esc(row.latency_ms ?? '')}ms</span>
        </div>
      </article>`).join('')
    : '';
  target.innerHTML = `
    <div class="workbench-metric-grid">
      ${metric('Run', payload.run_id || payload.bundle_id || 'latest')}
      ${metric('OK', summary.ok_count ?? payload.quality_summary?.item_count ?? '-')}
      ${metric('Failed', summary.failed_count ?? '-')}
      ${metric('Quota', summary.quota_protected_count ?? 0)}
      ${metric('Normalized', normalized || '-')}
      ${metric('Latency', avgLatency ? `${avgLatency}ms` : '-')}
    </div>
    <div class="preview-step-grid connector-result-summary">
      <div class="preview-step"><span>${c('symbolLabel')}</span><strong>${esc(symbol())}</strong></div>
      <div class="preview-step"><span>${c('universeLabel')}</span><strong>${esc(universe().length)}</strong></div>
      <div class="preview-step"><span>${c('providerLabel')}</span><strong>${esc(providers().join(', ') || '-')}</strong></div>
    </div>
    <section class="workbench-section">
      <div class="workbench-section__title">Provider Ladder</div>
      <div class="preview-step-grid">
        ${renderProviderLadder(providers(), rows)}
      </div>
    </section>
    <section class="workbench-section">
      <div class="workbench-section__title">Run Guard</div>
      <div class="factor-checklist">
        <div class="factor-check-row"><span>Quota mode</span><strong>${esc(payload.mode || payload.quota_mode || 'guarded')}</strong></div>
        <div class="factor-check-row"><span>Failure isolation</span><strong class="is-pass">${esc(summary.failure_isolation || 'enabled')}</strong></div>
        <div class="factor-check-row"><span>Persisted record</span><strong>${payload.storage?.record_id ? 'stored' : 'ephemeral'}</strong></div>
      </div>
    </section>
    <div class="workbench-list workbench-scroll-list connector-result-scroll">${resultRows || emptyState('No rows')}</div>`;
}

async function runHealth() {
  if (!isMounted()) return;
  const target = _container.querySelector('#connector-result');
  setLoading(target, 'Checking connectors...');
  try {
    const payload = await api.connectors.health(providers(), false);
    if (!isMounted()) return;
    renderResult(payload);
  } catch (err) {
    if (!isMounted()) return;
    renderError(target, err);
  }
}

async function runDryTest() {
  if (!isMounted()) return;
  const target = _container.querySelector('#connector-result');
  setLoading(target, 'Running dry connector test...');
  try {
    const payload = await api.connectors.test({
      providers: providers(),
      symbol: symbol(),
      dry_run: true,
    });
    if (!isMounted()) return;
    renderResult(payload);
  } catch (err) {
    if (!isMounted()) return;
    renderError(target, err);
  }
}

async function runLiveScan() {
  if (!isMounted()) return;
  const target = _container.querySelector('#connector-result');
  setLoading(target, 'Running free-tier live scan...');
  try {
    const payload = await api.connectors.liveScan({
      universe: universe(),
      providers: providers(),
      quota_guard: true,
      persist: true,
      limit: 6,
    });
    if (!isMounted()) return;
    renderResult(payload);
  } catch (err) {
    if (!isMounted()) return;
    renderError(target, err);
  }
}

function renderProviderLadder(providerIds, rows = []) {
  if (!providerIds.length) {
    return '<div class="preview-step"><span>providers</span><strong>-</strong></div>';
  }
  const byProvider = Array.isArray(rows)
    ? rows.reduce((acc, row) => {
      const key = row.provider || row.provider_id || 'provider';
      acc[key] ||= { total: 0, ok: 0 };
      acc[key].total += 1;
      if (['ok', 'configured', 'dry_run_ready', 'empty'].includes(String(row.status || '').toLowerCase())) acc[key].ok += 1;
      return acc;
    }, {})
    : {};
  return providerIds.slice(0, 5).map((providerId, index) => {
    const stats = byProvider[providerId];
    const label = stats ? `${stats.ok}/${stats.total}` : `P${index + 1}`;
    return `<div class="preview-step"><span>${esc(providerId)}</span><strong>${esc(label)}</strong></div>`;
  }).join('');
}

function averageLatency(rows) {
  const values = Array.isArray(rows)
    ? rows.map((row) => Number(row.latency_ms || 0)).filter((value) => Number.isFinite(value) && value > 0)
    : [];
  if (!values.length) return 0;
  return Math.round(values.reduce((acc, value) => acc + value, 0) / values.length);
}
