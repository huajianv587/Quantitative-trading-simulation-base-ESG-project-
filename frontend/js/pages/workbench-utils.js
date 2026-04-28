import { getLang } from '../i18n.js?v=8';

const COPY = {
  en: {
    loading: 'Loading...',
    empty: 'No data yet',
    requestFailed: 'Request failed',
    shadowOnly: 'Shadow mode only. No broker order will be created.',
    source: 'Source',
    quality: 'Quality',
    safe: 'As-of safe',
    noEvidence: 'No evidence',
    noFactorCards: 'No factor cards',
    noSimulation: 'No simulation result',
    noSimulationHint: 'Choose a scenario and run Monte Carlo.',
    notSet: 'Not set',
    evidenceHint: 'Scan evidence to load source-linked items.',
    factorHint: 'Run discovery to generate IC, RankIC, and gate results.',
    factorReviewHint: 'Gate passed or pending review',
    pathSummary: 'Path Summary',
    factorAttribution: 'Factor Attribution',
    historicalAnalogs: 'Historical Analogs',
    expected: 'Expected',
    lossProb: 'Loss Prob',
    stability: 'Stability',
    samples: 'Samples',
  },
  zh: {
    loading: '正在加载...',
    empty: '暂无数据',
    requestFailed: '请求失败',
    shadowOnly: '仅用于影子模式研究，不会创建券商订单。',
    source: '来源',
    quality: '质量',
    safe: '时点安全',
    noEvidence: '暂无证据',
    noFactorCards: '暂无因子卡片',
    noSimulation: '暂无模拟结果',
    noSimulationHint: '请选择场景后再运行 Monte Carlo。',
    notSet: '未设置',
    evidenceHint: '扫描证据后会加载带来源链路的条目。',
    factorHint: '运行因子发现后会生成 IC、RankIC 和门禁结果。',
    factorReviewHint: '门禁通过或待复核',
    pathSummary: '路径摘要',
    factorAttribution: '因子归因',
    historicalAnalogs: '历史相似事件',
    expected: '预期收益',
    lossProb: '亏损概率',
    stability: '稳定性',
    samples: '样本',
  },
};

const STATUS_COPY_ZH = {
  active: '活跃',
  approve: '批准',
  approved: '已批准',
  armed: '已武装',
  blocked: '已阻断',
  buy: '买入',
  clean: '正常',
  clear: '清晰',
  configured: '已配置',
  derived: '自动推导',
  disabled: '已停用',
  enabled: '已启用',
  error: '错误',
  failed: '失败',
  filled: '已填充',
  flagged: '已标记',
  forming: '形成中',
  guarded: '受保护',
  halt: '暂停',
  hold: '持有',
  idle: '空闲',
  linked: '已关联',
  logged: '已记录',
  long: '看多',
  missing_key: '缺少密钥',
  neutral: '中性',
  no: '否',
  off: '关闭',
  on: '开启',
  paper: '模拟',
  pass: '通过',
  paused: '已暂停',
  pending: '待处理',
  promoted: '已晋升',
  protected: '已保护',
  queued: '排队中',
  ready: '就绪',
  reduce: '缩减',
  reject: '拒绝',
  rejected: '已拒绝',
  research_only: '仅研究',
  review: '待复核',
  review_only: '仅复核',
  risk: '风险',
  running: '运行中',
  safe: '安全',
  sell: '卖出',
  shadow: '影子',
  short: '看空',
  stored: '已存储',
  submitted: '已提交',
  tagged: '已标注',
  tracked: '已追踪',
  untouched: '未触达',
  ui_only: '仅界面',
  waiting: '等待中',
  watch: '观察',
  yes: '是',
};

const POSITIVE_STATUSES = new Set([
  'active',
  'approve',
  'approved',
  'armed',
  'buy',
  'clean',
  'clear',
  'configured',
  'derived',
  'enabled',
  'filled',
  'guarded',
  'linked',
  'logged',
  'long',
  'on',
  'paper',
  'pass',
  'promoted',
  'protected',
  'queued',
  'ready',
  'running',
  'safe',
  'shadow',
  'stored',
  'submitted',
  'tagged',
  'tracked',
  'untouched',
  'yes',
]);

const NEGATIVE_STATUSES = new Set([
  'blocked',
  'disabled',
  'error',
  'failed',
  'halt',
  'missing_key',
  'off',
  'reduce',
  'reject',
  'rejected',
  'risk',
  'sell',
  'short',
]);

export function lang() {
  return getLang() === 'zh' ? 'zh' : 'en';
}

export function text(key) {
  return COPY[lang()]?.[key] || COPY.en[key] || key;
}

export function esc(value) {
  return String(value ?? '').replace(/[&<>"']/g, (ch) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    '\'': '&#39;',
  }[ch]));
}

export function num(value, digits = 3) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return '-';
  return parsed.toFixed(digits);
}

export function pct(value, digits = 2) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return '-';
  return `${(parsed * 100).toFixed(digits)}%`;
}

export function readSymbol(container, selector, fallback = 'AAPL') {
  return (container.querySelector(selector)?.value || fallback).trim().toUpperCase();
}

export function splitTokens(raw, options = {}) {
  const delimiters = options.delimiters || /[,\s]+/;
  const uppercase = Boolean(options.uppercase);
  return String(raw || '')
    .split(delimiters)
    .map((item) => item.trim())
    .filter(Boolean)
    .map((item) => (uppercase ? item.toUpperCase() : item));
}

export function readUniverse(raw, symbol) {
  const values = splitTokens(raw, { uppercase: true, delimiters: /[,\s]+/ });
  if (symbol && !values.includes(symbol)) values.unshift(symbol);
  return Array.from(new Set(values));
}

export function setLoading(el, message = text('loading')) {
  if (!el) return;
  el.innerHTML = `<div class="empty-state empty-state--compact"><div class="empty-state__title">${esc(message)}</div></div>`;
}

export function emptyState(title = text('empty'), detail = '') {
  return `<div class="empty-state">
    <div class="empty-state__title">${esc(title)}</div>
    ${detail ? `<div class="empty-state__text">${esc(detail)}</div>` : ''}
  </div>`;
}

export function renderError(el, err, options = {}) {
  if (!el) return;

  // 使用统一的错误处理系统
  if (window.errorHandler) {
    const errorInfo = window.errorHandler.parseError(err, {
      context: options.context || 'workbench',
    });
    const errorUI = window.errorHandler.createErrorUI(errorInfo, {
      variant: options.variant || 'compact',
      showRetry: options.showRetry !== undefined ? options.showRetry : Boolean(options.onRetry),
      showSuggestions: options.showSuggestions !== undefined ? options.showSuggestions : true,
      onRetry: typeof options.onRetry === 'function' ? options.onRetry : null,
    });
    el.innerHTML = '';
    el.appendChild(errorUI);
  } else {
    // 降级处理
    el.innerHTML = emptyState(text('requestFailed'), err?.message || String(err || ''));
  }
}

export function persistPayloadSnapshot(storageKey, payload, meta) {
  if (!storageKey || payload === undefined) return null;
  const metadata = meta || {};
  const record = {
    schema_version: metadata.schema_version || 1,
    saved_at: Date.now(),
    payload,
    meta: metadata,
  };
  try {
    localStorage.setItem(storageKey, JSON.stringify(record));
  } catch (_ignore) {
    return null;
  }
  return record;
}

export function loadPayloadSnapshot(storageKey, ttlMs, expectedSchemaVersion = 1) {
  if (!storageKey) return null;
  try {
    const raw = localStorage.getItem(storageKey);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed || parsed.payload === undefined) return null;
    if (parsed.schema_version !== expectedSchemaVersion) return null;
    const savedAt = Number(parsed.saved_at || 0);
    if (ttlMs && savedAt && (Date.now() - savedAt) > Number(ttlMs)) return null;
    return {
      saved_at: savedAt || null,
      payload: parsed.payload,
      meta: parsed.meta || {},
    };
  } catch (_ignore) {
    return null;
  }
}

export function removePayloadSnapshot(storageKey) {
  if (!storageKey) return;
  try {
    localStorage.removeItem(storageKey);
  } catch (_ignore) {
    // Ignore cleanup failures.
  }
}

function formatSnapshotAge(savedAt) {
  const ageMs = Date.now() - Number(savedAt || 0);
  if (!Number.isFinite(ageMs) || ageMs <= 0) return '-';
  const ageSeconds = Math.round(ageMs / 1000);
  if (ageSeconds < 60) return `${ageSeconds}s`;
  const ageMinutes = Math.round(ageSeconds / 60);
  if (ageMinutes < 60) return `${ageMinutes}m`;
  const ageHours = Math.round(ageMinutes / 60);
  if (ageHours < 48) return `${ageHours}h`;
  return `${Math.round(ageHours / 24)}d`;
}

export function renderDegradedNotice(meta) {
  const state = meta || {};
  const tone = String(state.tone || 'warning').toLowerCase();
  const title = state.title || 'Degraded view';
  const reason = state.reason || 'Showing the last successful snapshot while the live request recovers.';
  const detail = state.detail || '';
  const action = state.action || '';
  const savedAt = state.savedAt || state.saved_at || null;
  const staleLabel = savedAt ? `snapshot ${formatSnapshotAge(savedAt)} ago` : '';
  return `<div class="degraded-notice degraded-notice--${esc(tone)}">
    <div class="degraded-notice__header">
      <strong>${esc(title)}</strong>
      ${staleLabel ? `<span>${esc(staleLabel)}</span>` : ''}
    </div>
    <div class="degraded-notice__body">
      <span>${esc(reason)}</span>
      ${detail ? `<span>${esc(detail)}</span>` : ''}
      ${action ? `<span>${esc(action)}</span>` : ''}
    </div>
  </div>`;
}

export function metric(label, value, tone = '') {
  const toneClass = tone ? ` workbench-metric-card--${tone}` : '';
  return `<article class="workbench-metric-card${toneClass}">
    <div class="workbench-metric-card__label">${esc(label)}</div>
    <div class="workbench-metric-card__value">${esc(value)}</div>
  </article>`;
}

export function miniMetric(label, value) {
  return `<div class="workbench-mini-metric">
    <span>${esc(label)}</span>
    <strong>${esc(value)}</strong>
  </div>`;
}

export function badge(label, status = 'neutral') {
  const safeStatus = ['filled', 'failed', 'neutral'].includes(status) ? status : 'neutral';
  return `<span class="badge badge-${safeStatus}">${esc(label)}</span>`;
}

function humanizeStatus(status) {
  const normalized = String(status || 'neutral').trim().toLowerCase().replace(/[\s-]+/g, '_');
  if (lang() === 'zh' && STATUS_COPY_ZH[normalized]) return STATUS_COPY_ZH[normalized];
  return normalized.replace(/_/g, ' ').trim();
}

export function statusBadge(status) {
  const normalized = String(status || 'neutral').trim().toLowerCase().replace(/[\s-]+/g, '_');
  const tone = POSITIVE_STATUSES.has(normalized)
    ? 'filled'
    : NEGATIVE_STATUSES.has(normalized)
      ? 'failed'
      : 'neutral';
  return badge(humanizeStatus(normalized), tone);
}

export function pathChip(value, empty = '-') {
  const raw = String(value || empty);
  return `<span class="path-chip" title="${esc(raw)}">${esc(raw)}</span>`;
}

export function renderTokenPreview(raw, options = {}) {
  const tokens = Array.isArray(raw) ? raw : splitTokens(raw, options);
  const maxItems = Number(options.maxItems || 8);
  const tone = options.tone || 'neutral';
  const emptyLabel = options.emptyLabel || text('notSet');
  if (!tokens.length) {
    return `<div class="token-preview token-preview--empty"><span class="token-chip token-chip--muted">${esc(emptyLabel)}</span></div>`;
  }
  const visible = tokens.slice(0, maxItems);
  const overflow = tokens.length - visible.length;
  return `<div class="token-preview">
    ${visible.map((token) => `<span class="token-chip token-chip--${esc(tone)}">${esc(token)}</span>`).join('')}
    ${overflow > 0 ? `<span class="token-chip token-chip--muted">+${overflow}</span>` : ''}
  </div>`;
}

export function renderEvidenceItems(items, options = {}) {
  if (!items?.length) return emptyState(text('noEvidence'), text('evidenceHint'));
  const resolvedLimit = options.limit === null
    ? null
    : Number.isFinite(Number(options.limit ?? options.maxItems))
      ? Number(options.limit ?? options.maxItems)
      : 8;
  const visibleItems = resolvedLimit == null ? items : items.slice(0, resolvedLimit);
  const listClass = [
    'workbench-list',
    options.scroll ? 'workbench-scroll-list' : '',
    options.listClass || '',
  ].filter(Boolean).join(' ');
  const itemClass = options.itemClass ? ` ${options.itemClass}` : '';
  return `<div class="${listClass}">
    ${visibleItems.map((item) => `
      <article class="workbench-item${itemClass}">
        <div class="workbench-item__head">
          <strong>${esc(item.title || item.item_id || '')}</strong>
          ${badge(item.item_type || 'evidence', 'neutral')}
        </div>
        <p>${esc(item.summary || '')}</p>
        <div class="workbench-item__meta">
          <span>${esc(item.symbol || '')}</span>
          <span>${esc(item.provider || '')}</span>
          <span>q=${num(item.quality_score ?? item.confidence)}</span>
        </div>
      </article>
    `).join('')}
  </div>`;
}

export function renderFactorCards(cards, options = {}) {
  const maxItems = options.maxItems || 6;
  if (!cards?.length) return emptyState(text('noFactorCards'), text('factorHint'));
  return `<div class="factor-card-grid">
    ${cards.slice(0, maxItems).map((card) => `
      <article class="factor-card">
        <div class="factor-card__head">
          <div>
            <strong>${esc(card.factor_name || card.name || '')}</strong>
            <span>${esc(card.family || card.category || '')}</span>
          </div>
          ${statusBadge(card.gate_status || card.status || 'review')}
        </div>
        <div class="workbench-mini-grid">
          ${miniMetric(text('quality'), num(card.quality_score ?? card.information_coefficient ?? card.ic))}
          ${miniMetric(text('expected'), pct(card.expected_return ?? card.expected_alpha ?? 0))}
          ${miniMetric(text('stability'), num(card.stability_score ?? card.rank_ic ?? 0))}
          ${miniMetric(text('samples'), card.sample_count ?? card.observation_count ?? '-')}
        </div>
        <div class="factor-check-row">
          <span>${text('factorReviewHint')}</span>
          <strong class="${String(card.gate_status || '').toLowerCase() === 'pass' ? 'is-pass' : 'is-watch'}">${esc(humanizeStatus(card.gate_status || card.status || 'review'))}</strong>
        </div>
      </article>
    `).join('')}
  </div>`;
}

export function renderProtectionChecks(checks) {
  var entries = checks && typeof checks === 'object' ? Object.entries(checks) : [];
  if (!entries.length) return emptyState('Protection Checks', text('notSet'));
  return `<div class="workbench-kv-list compact-kv-list">
    ${entries.map(function(entry) {
      var key = entry[0];
      var value = entry[1] || {};
      var violations = Array.isArray(value.violations) ? value.violations : [];
      return `<div class="workbench-kv-row">
        <span>${esc(key.replace(/_/g, ' '))}</span>
        <strong>${statusBadge(value.passed ? 'pass' : 'blocked')}</strong>
        <em>${esc(violations.length ? violations.slice(0, 2).join(', ') : (value.detail || 'clean'))}</em>
      </div>`;
    }).join('')}
  </div>`;
}

export function renderProtectionReport(report) {
  if (!report || typeof report !== 'object') return emptyState('Protection Report', text('notSet'));
  return `
    <section class="workbench-section">
      <div class="workbench-section__title">Protection Report</div>
      <div class="workbench-mini-grid">
        ${miniMetric('dataset', report.dataset_id || '-')}
        ${miniMetric('market', report.market || 'US')}
        ${miniMetric('frequency', report.frequency || '-')}
        ${miniMetric('tier', report.data_tier || 'l1')}
      </div>
      <div class="factor-check-row">
        <span>status</span>
        <strong>${statusBadge(report.protection_status || 'review')}</strong>
      </div>
      ${renderTokenPreview(report.blocking_reasons || report.blocking_checks || [], { tone: 'risk', maxItems: 6, emptyLabel: 'no blockers' })}
      ${renderProtectionChecks(report.checks)}
    </section>
  `;
}

export function renderRegistryGate(payload) {
  if (!payload || typeof payload !== 'object') return emptyState('Registry Gate', text('notSet'));
  return `
    <section class="workbench-section">
      <div class="workbench-section__title">Registry Gate</div>
      <div class="workbench-mini-grid">
        ${miniMetric('status', humanizeStatus(payload.registry_gate_status || payload.eligibility_status || 'review'))}
        ${miniMetric('eligible', payload.eligible_for_execution === undefined ? '-' : String(Boolean(payload.eligible_for_execution)))}
        ${miniMetric('required freq', payload.required_frequency || payload.frequency || '-')}
        ${miniMetric('required tier', payload.required_data_tier || payload.data_tier || 'l1')}
      </div>
      ${renderTokenPreview(payload.blocking_reasons || [], { tone: 'risk', maxItems: 6, emptyLabel: 'no blockers' })}
    </section>
  `;
}

export function renderMarketDepthDiagnostics(payload) {
  if (!payload || typeof payload !== 'object') return emptyState('Market Depth', text('notSet'));
  var latest = Array.isArray(payload.latest) ? payload.latest : [];
  return `
    <section class="workbench-section">
      <div class="workbench-section__title">Market Depth</div>
      <div class="workbench-mini-grid">
        ${miniMetric('provider', payload.selected_provider || payload.provider || '-')}
        ${miniMetric('tier', payload.data_tier || 'l1')}
        ${miniMetric('history', payload.history_ready === undefined ? '-' : String(Boolean(payload.history_ready)))}
        ${miniMetric('realtime', payload.realtime_ready === undefined ? '-' : String(Boolean(payload.realtime_ready)))}
      </div>
      <div class="factor-check-row">
        <span>gate</span>
        <strong>${statusBadge(payload.eligibility_status || 'review')}</strong>
      </div>
      ${renderTokenPreview(payload.blocking_reasons || [], { tone: 'risk', maxItems: 6, emptyLabel: 'no blockers' })}
      ${latest.length ? `<div class="workbench-kv-list compact-kv-list">
        ${latest.slice(0, 3).map(function(snapshot) {
          return `<div class="workbench-kv-row"><span>${esc(snapshot.symbol || '')}</span><strong>${esc(snapshot.spread_bps || 0)} bps / ${esc(snapshot.session || '-')}</strong></div>`;
        }).join('')}
      </div>` : ''}
    </section>
  `;
}

export function renderSimulationSummary(payload) {
  if (!payload) return emptyState(text('noSimulation'), text('noSimulationHint'));
  var scenario = payload.scenario || {};
  return `
    <div class="workbench-metric-grid functional-empty__metrics">
      ${metric(text('expected'), pct(payload.expected_return ?? payload.mean_return ?? 0))}
      ${metric(text('lossProb'), pct(payload.probability_of_loss ?? payload.loss_probability ?? payload.tail_loss_probability ?? 0))}
      ${metric(text('stability'), num(payload.max_drawdown_p95 ?? payload.stability_score ?? payload.sharpe_like ?? 0))}
      ${metric(text('samples'), payload.path_summary?.p50 !== undefined ? Object.keys(payload.path_summary || {}).length : (scenario.paths ?? payload.paths ?? '-'))}
    </div>
    <div class="workbench-kv-list compact-kv-list">
      <div class="workbench-kv-row"><span>${text('pathSummary')}</span><strong>${esc(scenario.regime || scenario.scenario_name || '-')}</strong></div>
      <div class="workbench-kv-row"><span>frequency / tier</span><strong>${esc((payload.dataset_manifest || {}).frequency || payload.frequency || '-')} / ${esc(payload.data_tier || ((payload.dataset_manifest || {}).data_tier) || 'l1')}</strong></div>
      <div class="workbench-kv-row"><span>${text('historicalAnalogs')}</span><strong>${esc((payload.historical_analogs || []).length || '-')}</strong></div>
    </div>
  `;
}

export function renderSimulationResult(payload) {
  if (!payload) return renderSimulationSummary(payload);
  var micro = payload.microstructure || {};
  var sandbox = payload.execution_quality_sandbox || {};
  var replay = payload.order_book_replay || {};
  return `
    ${renderSimulationSummary(payload)}
    ${renderMarketDepthDiagnostics(payload.market_depth_status || replay)}
    ${renderProtectionReport(payload.protection_report)}
    <section class="workbench-section">
      <div class="workbench-section__title">Execution Sandbox</div>
      <div class="workbench-mini-grid">
        ${miniMetric('best session', micro.metrics?.best_session || sandbox.best_session || '-')}
        ${miniMetric('spread', num(micro.metrics?.avg_spread_bps || replay.summary?.avg_spread_bps || 0, 2))}
        ${miniMetric('depth', num(micro.metrics?.avg_depth || replay.summary?.avg_bid_depth || 0, 2))}
        ${miniMetric('imbalance', num(micro.metrics?.avg_imbalance || replay.summary?.avg_imbalance || 0, 3))}
      </div>
      ${sandbox.fallback_banner ? `<div class="empty-state empty-state--compact"><div class="empty-state__text">${esc(sandbox.fallback_banner)}</div></div>` : ''}
      ${renderTokenPreview((sandbox.warnings || micro.warnings || []), { tone: 'risk', maxItems: 6, emptyLabel: 'no warnings' })}
    </section>
  `;
}
