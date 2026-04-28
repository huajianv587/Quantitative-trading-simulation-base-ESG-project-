import { api } from '../qtapi.js?v=8';
import { toast } from '../components/toast.js?v=8';
import { getLang, onLangChange } from '../i18n.js?v=8';
import { emptyState, esc, metric, pct, renderError, setLoading, statusBadge } from './workbench-utils.js?v=8';

let _container = null;
let _langCleanup = null;
let _state = null;

const COPY = {
  en: {
    title: 'Paper Performance',
    subtitle: '90-day paper evidence, outcomes, promotion gates, attribution, and cloud readiness.',
    refresh: 'Refresh',
    snapshot: 'Capture Snapshot',
    settle: 'Settle Outcomes',
    evaluate: 'Evaluate Promotion',
    loading: 'Loading paper performance...',
    performance: '90-Day Performance',
    recommendation: 'Live Canary Recommendation',
    preflight: 'Cloud Preflight',
    outcomes: 'Outcome Ledger',
    attribution: 'Attribution',
    observability: 'Observability',
    sessionEvidence: 'Session Evidence',
    submitLocks: 'Submit Locks',
    blocked: 'blocked',
    ready: 'ready',
  },
  zh: {
    title: 'Paper 绩效',
    subtitle: '90 天 paper 证据、结果结算、晋级门禁、归因和云端就绪状态。',
    refresh: '刷新',
    snapshot: '采集快照',
    settle: '结算结果',
    evaluate: '评估晋级',
    loading: '正在加载 paper 绩效...',
    performance: '90 天绩效',
    recommendation: 'Live Canary 建议',
    preflight: '云端 Preflight',
    outcomes: '结果账本',
    attribution: '归因',
    observability: '可观测性',
    sessionEvidence: 'Session Evidence',
    submitLocks: '下单锁',
    blocked: '阻断',
    ready: '就绪',
  },
};

function c(key) {
  const lang = getLang() === 'zh' ? 'zh' : 'en';
  return COPY[lang][key] || COPY.en[key] || key;
}

function mounted() {
  return Boolean(_container && _container.isConnected);
}

export async function render(container) {
  _container = container;
  renderShell();
  wire();
  _langCleanup = onLangChange(() => {
    if (!mounted()) return;
    renderShell();
    wire();
    if (_state) renderState();
  });
  await refresh();
}

export function destroy() {
  _langCleanup?.();
  _langCleanup = null;
  _container = null;
  _state = null;
}

function renderShell() {
  if (!_container) return;
  _container.innerHTML = `
    <div class="workbench-page paper-performance-page" data-no-autotranslate="true">
      <section class="run-panel">
        <div class="run-panel__header">
          <div class="run-panel__title">${c('title')}</div>
          <div class="run-panel__sub">${c('subtitle')}</div>
        </div>
        <div class="run-panel__body">
          <div class="grid-3 compact-control-grid">
            <label class="field"><span>Window</span><input id="paper-window-days" type="number" min="30" max="252" value="90"></label>
            <label class="field"><span>Broker</span><input value="alpaca / paper" disabled></label>
            <label class="field"><span>Policy</span><input value="operator-confirmed live canary only" disabled></label>
          </div>
          <div class="grid-5 compact-control-grid">
            <label class="field"><span>Symbol</span><input id="paper-filter-symbol" placeholder="AAPL"></label>
            <label class="field"><span>Kind</span><select id="paper-filter-kind"><option value="">All</option><option value="order">order</option><option value="p1_signal">p1_signal</option><option value="p2_signal">p2_signal</option><option value="paper_reward_candidate">reward</option></select></label>
            <label class="field"><span>Status</span><select id="paper-filter-status"><option value="">All</option><option value="pending">pending</option><option value="partially_settled">partially_settled</option><option value="settled">settled</option><option value="data_missing">data_missing</option></select></label>
            <label class="field"><span>Synthetic</span><select id="paper-filter-synthetic"><option value="">All</option><option value="false">eligible</option><option value="true">synthetic</option></select></label>
            <label class="field"><span>Horizon</span><select id="paper-filter-horizon"><option value="">All</option><option value="n1">N+1</option><option value="n3">N+3</option><option value="n5">N+5</option></select></label>
          </div>
        </div>
        <div class="run-panel__foot workbench-action-grid">
          <button class="btn workbench-action-btn workbench-action-btn--primary" id="btn-paper-performance-refresh">${c('refresh')}</button>
          <button class="btn workbench-action-btn workbench-action-btn--secondary" id="btn-paper-performance-snapshot">${c('snapshot')}</button>
          <button class="btn workbench-action-btn workbench-action-btn--secondary" id="btn-paper-outcomes-settle">${c('settle')}</button>
          <button class="btn workbench-action-btn workbench-action-btn--secondary" id="btn-paper-promotion-evaluate">${c('evaluate')}</button>
        </div>
      </section>

      <section class="trading-ops-kpi-grid" id="paper-kpis">${emptyState(c('loading'))}</section>
      <section class="grid-2 workbench-main-grid">
        ${card(c('performance'), 'paper-performance-body')}
        ${card(c('attribution'), 'paper-attribution-body')}
        ${card(c('sessionEvidence'), 'paper-session-evidence-body')}
        ${card(c('submitLocks'), 'paper-submit-locks-body')}
        ${card(c('recommendation'), 'paper-recommendation-body')}
        ${card(c('preflight'), 'paper-preflight-body')}
        ${card(c('observability'), 'paper-observability-body')}
        ${card(c('outcomes'), 'paper-outcomes-body')}
      </section>
    </div>
  `;
}

function card(title, id) {
  return `<article class="card"><div class="card-header"><span class="card-title">${esc(title)}</span></div><div class="card-body" id="${id}">${emptyState(c('loading'))}</div></article>`;
}

function wire() {
  _container?.querySelector('#btn-paper-performance-refresh')?.addEventListener('click', refresh);
  _container?.querySelector('#btn-paper-performance-snapshot')?.addEventListener('click', captureSnapshot);
  _container?.querySelector('#btn-paper-outcomes-settle')?.addEventListener('click', settleOutcomes);
  _container?.querySelector('#btn-paper-promotion-evaluate')?.addEventListener('click', evaluatePromotion);
  ['#paper-filter-symbol', '#paper-filter-kind', '#paper-filter-status', '#paper-filter-synthetic', '#paper-filter-horizon'].forEach((selector) => {
    _container?.querySelector(selector)?.addEventListener('input', renderState);
    _container?.querySelector(selector)?.addEventListener('change', renderState);
  });
}

async function refresh() {
  if (!mounted()) return;
  setLoading(_container.querySelector('#paper-kpis'), c('loading'));
  try {
    const windowDays = Number(_container.querySelector('#paper-window-days')?.value || 90);
    const [performance, outcomes, promotion, preflight, calendar, observability, sessionEvidence, submitLocks, timeline, slo] = await Promise.all([
      api.paper.performance(windowDays),
      api.paper.outcomes({ limit: 200 }),
      api.promotion.report(windowDays),
      api.deployment.preflight('paper_cloud'),
      api.tradingCalendar.status(),
      api.observability.paperWorkflow(30),
      api.paper.latestSessionEvidence().catch(() => null),
      api.paper.submitLocks({ limit: 50 }).catch(() => ({ count: 0, locks: [] })),
      api.promotion.timeline(50).catch(() => ({ events: [] })),
      api.observability.paperWorkflowSlo(30).catch(() => null),
    ]);
    _state = { performance, outcomes, promotion, preflight, calendar, observability, sessionEvidence, submitLocks, timeline, slo };
    if (mounted()) renderState();
  } catch (error) {
    ['#paper-kpis', '#paper-performance-body', '#paper-attribution-body', '#paper-session-evidence-body', '#paper-submit-locks-body', '#paper-recommendation-body', '#paper-preflight-body', '#paper-observability-body', '#paper-outcomes-body'].forEach((selector) => {
      const node = _container?.querySelector(selector);
      if (node) renderError(node, error, { onRetry: refresh });
    });
  }
}

async function captureSnapshot() {
  try {
    await api.paper.snapshot({ broker: 'alpaca', mode: 'paper', benchmark: 'SPY' });
    toast.success(c('snapshot'), 'snapshot captured');
    await refresh();
  } catch (error) {
    toast.error(c('snapshot'), error.message || '');
  }
}

async function settleOutcomes() {
  try {
    const result = await api.paper.settleOutcomes({ limit: 200 });
    toast.success(c('settle'), `${result.updated_count || 0} updated`);
    await refresh();
  } catch (error) {
    toast.error(c('settle'), error.message || '');
  }
}

async function evaluatePromotion() {
  try {
    const windowDays = Number(_container.querySelector('#paper-window-days')?.value || 90);
    const result = await api.promotion.evaluate({ window_days: windowDays, persist: true });
    toast.success(c('evaluate'), result.promotion_status || '');
    await refresh();
  } catch (error) {
    toast.error(c('evaluate'), error.message || '');
  }
}

function renderState() {
  if (!mounted() || !_state) return;
  const perf = _state.performance || {};
  const metrics = perf.metrics || {};
  const recommendation = perf.live_canary_recommendation || {};
  const preflight = _state.preflight || {};
  const promotion = _state.promotion || {};
  const timeline = _state.timeline || {};
  const calendar = _state.calendar || {};
  const observability = _state.observability || {};
  const sessionEvidence = _state.sessionEvidence || {};
  const submitLocks = _state.submitLocks || {};
  const slo = _state.slo || observability.slo || {};
  const filteredOutcomes = filterOutcomes((_state.outcomes || {}).outcomes || []);

  _container.querySelector('#paper-kpis').innerHTML = `
    ${metric('Valid Days', metrics.valid_days ?? 0, Number(metrics.valid_days || 0) >= 60 ? 'positive' : 'risk')}
    ${metric('Net Return', pct(metrics.net_return || 0), Number(metrics.net_return || 0) > 0 ? 'positive' : 'risk')}
    ${metric('Excess', pct(metrics.excess_return || 0), Number(metrics.excess_return || 0) > 0 ? 'positive' : 'risk')}
    ${metric('Sharpe', Number(metrics.sharpe || 0).toFixed(2), Number(metrics.sharpe || 0) >= 0.5 ? 'positive' : 'risk')}
    ${metric('Evidence SLO', pct(((slo.session_evidence || {}).completion_rate) || 0), Number(((slo.session_evidence || {}).completion_rate) || 0) >= 0.95 ? 'positive' : 'risk')}
    ${metric('Promotion', promotion.promotion_status || '-', recommendation.recommended ? 'positive' : '')}
  `;

  _container.querySelector('#paper-performance-body').innerHTML = `
    ${renderMiniChart('Equity Curve', perf.equity_curve || [], 'portfolio_nav')}
    ${renderMiniChart('Drawdown Curve', perf.drawdown_curve || [], 'drawdown')}
    ${renderMetricList([
      ['Equity', money((perf.latest_snapshot || {}).equity)],
      ['Cash-flow Adjusted', pct(perf.cash_flow_adjusted_return || 0)],
      ['Cash Flow Source', perf.cash_flow_adjustment_source || '-'],
      ['Paper Gate', (perf.paper_gate || {}).status || '-'],
      ['Calendar', `${calendar.calendar_id || 'XNYS'} / ${calendar.session_date || '-'}`],
    ])}
  `;

  _container.querySelector('#paper-attribution-body').innerHTML = `
    <div class="workbench-metric-grid">
      ${metric('Turnover', money(perf.turnover || 0))}
      ${metric('Fill Rate', pct(perf.fill_rate || 0), Number(perf.fill_rate || 0) > 0 ? 'positive' : '')}
      ${metric('Reject Rate', pct(perf.reject_rate || 0), Number(perf.reject_rate || 0) ? 'risk' : 'positive')}
      ${metric('Slippage', `${Number(perf.avg_slippage_bps || 0).toFixed(2)} bps`)}
      ${metric('Win Rate', pct(perf.win_rate || 0))}
      ${metric('Win/Loss', Number(perf.avg_win_loss_ratio || 0).toFixed(2))}
    </div>
    ${renderContributionRows(perf.symbol_contributions || [])}
    ${renderMetricList(Object.entries(perf.factor_exposures || {}).slice(0, 10))}
    ${renderMetricList(Object.entries(perf.industry_exposures || {}).slice(0, 10))}
    ${renderTrendRows((perf.attribution_trends || {}).rows || [])}
  `;

  _container.querySelector('#paper-session-evidence-body').innerHTML = `
    <div class="workbench-metric-grid">
      ${metric('Session', sessionEvidence.session_date || '-')}
      ${metric('Complete', sessionEvidence.complete ? 'yes' : 'no', sessionEvidence.complete ? 'positive' : 'risk')}
      ${metric('Missing', (sessionEvidence.missing_stages || []).length, (sessionEvidence.missing_stages || []).length ? 'risk' : 'positive')}
      ${metric('SLO', pct(((slo.session_evidence || {}).completion_rate) || 0))}
    </div>
    ${renderStageRows(sessionEvidence.stages || {})}
    ${renderMetricList([
      ['Reconcile', (perf.reconciliation_status || {}).status || '-'],
      ['Backup', (perf.backup_status || {}).status || '-'],
      ['Backup Remote', (perf.backup_status || {}).uploaded ? 'uploaded' : 'local-only'],
    ])}
  `;

  _container.querySelector('#paper-submit-locks-body').innerHTML = `
    <div class="workbench-metric-grid">
      ${metric('Locks', submitLocks.count || 0)}
      ${metric('Submit Unknown', ((slo.orders || {}).submit_unknown_count) || 0, ((slo.orders || {}).submit_unknown_count) ? 'risk' : 'positive')}
      ${metric('Duplicate Blocked', ((slo.orders || {}).duplicate_submit_blocked_count) || 0)}
    </div>
    ${renderSubmitLockRows(submitLocks.locks || [])}
  `;

  _container.querySelector('#paper-recommendation-body').innerHTML = `
    <div class="workbench-metric-grid">
      ${metric('Recommendation', recommendation.recommended ? c('ready') : c('blocked'), recommendation.recommended ? 'positive' : 'risk')}
      ${metric('Operator Required', recommendation.operator_confirmation_required ? 'yes' : 'no')}
      ${metric('Policy', ((recommendation.policy || {}).policy_id || (promotion.policy || {}).policy_id || '-'))}
    </div>
    ${renderList('Blockers', recommendation.blockers || [])}
    ${renderTimeline(timeline.events ? timeline : promotion)}
  `;

  _container.querySelector('#paper-preflight-body').innerHTML = `
    <div class="workbench-metric-grid">
      ${metric('Ready', preflight.ready ? c('ready') : c('blocked'), preflight.ready ? 'positive' : 'risk')}
      ${metric('Blockers', (preflight.blockers || []).length, (preflight.blockers || []).length ? 'risk' : 'positive')}
      ${metric('Warnings', (preflight.warnings || []).length, (preflight.warnings || []).length ? 'risk' : 'positive')}
    </div>
    ${renderList('Next actions', preflight.next_actions || [])}
    ${renderCheckRows(preflight.hard_checks || [])}
  `;

  _container.querySelector('#paper-observability-body').innerHTML = `
    <div class="workbench-metric-grid">
      ${metric('Success Rate', pct((observability.summary || {}).success_rate || 0))}
      ${metric('Alerts', (observability.summary || {}).alert_count || 0, ((observability.summary || {}).alert_count || 0) ? 'risk' : 'positive')}
      ${metric('Heartbeat', ((observability.heartbeat || {}).stale ? 'stale' : 'fresh'), ((observability.heartbeat || {}).stale ? 'risk' : 'positive'))}
      ${metric('Backup SLO', pct(((slo.backup || {}).success_rate) || 0))}
    </div>
    ${renderList('Alerts', (observability.alerts || []).map((item) => `${item.kind}: ${item.message}`))}
    ${renderList('Recovery', (observability.recovery_notifications || []).map((item) => `${item.kind}: ${item.message}`))}
  `;

  _container.querySelector('#paper-outcomes-body').innerHTML = filteredOutcomes.length ? `
    <div class="rl-lab-table-wrap">
      <table class="rl-lab-table">
        <thead><tr><th>Symbol</th><th>Kind</th><th>Status</th><th>Synthetic</th><th>N+1</th><th>N+3</th><th>N+5</th><th>Score</th></tr></thead>
        <tbody>${filteredOutcomes.slice(0, 50).map(renderOutcomeRow).join('')}</tbody>
      </table>
    </div>
  ` : emptyState('No outcomes match the filters');
}

function filterOutcomes(rows) {
  const symbol = String(_container?.querySelector('#paper-filter-symbol')?.value || '').trim().toUpperCase();
  const kind = String(_container?.querySelector('#paper-filter-kind')?.value || '');
  const status = String(_container?.querySelector('#paper-filter-status')?.value || '');
  const synthetic = String(_container?.querySelector('#paper-filter-synthetic')?.value || '');
  const horizon = String(_container?.querySelector('#paper-filter-horizon')?.value || '');
  return rows.filter((row) => {
    if (symbol && !String(row.symbol || '').toUpperCase().includes(symbol)) return false;
    if (kind && row.record_kind !== kind) return false;
    if (status && row.status !== status) return false;
    if (synthetic && String(Boolean(row.synthetic_used)) !== synthetic) return false;
    if (horizon && !((row.settlements || {})[horizon] || {}).status) return false;
    return true;
  });
}

function renderMiniChart(title, points, key) {
  const rows = Array.isArray(points) ? points.slice(-30) : [];
  if (!rows.length) return emptyState(title);
  const values = rows.map((row) => Number(row[key] || 0));
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  return `<div class="workbench-section" data-chart="${esc(title)}"><div class="workbench-section__title">${esc(title)}</div><div class="factor-mini-bars">${values.map((value) => `<span style="height:${Math.max(4, Math.round(((value - min) / span) * 44 + 4))}px"></span>`).join('')}</div></div>`;
}

function renderMetricList(rows) {
  return `<div class="workbench-kv-list compact-kv-list">${rows.map(([key, value]) => `<div class="workbench-kv-row"><span>${esc(key)}</span><strong>${esc(value ?? '-')}</strong></div>`).join('')}</div>`;
}

function renderContributionRows(rows) {
  const values = Array.isArray(rows) ? rows.slice(0, 8) : [];
  return values.length ? `<div class="factor-checklist" id="paper-symbol-contribution">${values.map((row) => `<div class="factor-check-row"><span>${esc(row.symbol || '-')}</span><strong>${Number(row.score || 0).toFixed(4)}</strong></div>`).join('')}</div>` : emptyState('No symbol contribution yet');
}

function renderTrendRows(rows) {
  const values = Array.isArray(rows) ? rows.slice(-8) : [];
  return values.length ? `<div class="factor-checklist" id="paper-attribution-trends">${values.map((row) => `<div class="factor-check-row"><span>${esc(row.session_date || '-')}</span><strong>${pct(row.fill_rate || 0)} fill / ${pct(row.reject_rate || 0)} reject</strong></div>`).join('')}</div>` : emptyState('No attribution trend yet');
}

function renderTimeline(promotion) {
  const status = promotion.current_status || promotion.promotion_status || 'research_only';
  const statuses = promotion.allowed_statuses || ['research_only', 'shadow', 'paper_candidate', 'paper_promoted', 'canary_candidate', 'blocked'];
  const events = promotion.events || [];
  return `<div class="factor-checklist" id="paper-promotion-timeline">${statuses.map((item) => `<div class="factor-check-row"><span>${esc(item)}</span><strong class="${item === status ? 'is-pass' : 'is-muted'}">${item === status ? 'current' : ''}</strong></div>`).join('')}${events.slice(0, 5).map((item) => `<div class="factor-check-row"><span>${esc(item.generated_at || '')}</span><strong>${esc(item.status || '')}</strong></div>`).join('')}</div>`;
}

function renderStageRows(stages) {
  const names = ['preopen', 'workflow', 'paper_submit', 'broker_sync', 'outcomes', 'snapshot', 'promotion', 'digest', 'backup'];
  return `<div class="factor-checklist" id="paper-session-evidence">${names.map((name) => {
    const stage = stages[name] || {};
    const status = stage.status || 'missing';
    const klass = ['completed', 'submitted', 'planned', 'blocked', 'skipped'].includes(status) ? 'is-pass' : 'is-watch';
    return `<div class="factor-check-row"><span>${esc(name)}</span><strong class="${klass}">${esc(status)}</strong></div>`;
  }).join('')}</div>`;
}

function renderSubmitLockRows(rows) {
  const values = Array.isArray(rows) ? rows.slice(0, 20) : [];
  return values.length ? `<div class="factor-checklist" id="paper-submit-locks">${values.map((row) => `<div class="factor-check-row"><span>${esc(row.session_date || '-')} ${esc(row.symbol || '-')} ${esc(row.side || '')}</span><strong>${esc(row.status || '-')}</strong></div>`).join('')}</div>` : emptyState('No submit locks');
}

function renderList(title, items) {
  const values = Array.isArray(items) ? items : [];
  return `<div class="workbench-section"><div class="workbench-section__title">${esc(title)}</div>${values.length ? values.map((item) => `<div class="factor-check-row"><span>${esc(item)}</span><strong class="is-watch">review</strong></div>`).join('') : emptyState('None')}</div>`;
}

function renderCheckRows(rows) {
  return `<div class="factor-checklist" id="paper-preflight-drilldown">${rows.map((row) => `<div class="factor-check-row" title="${esc(row.detail || '')}"><span>${esc(row.name || '')}</span><strong class="${row.ok ? 'is-pass' : 'is-watch'}">${esc(row.ok ? 'pass' : 'fail')}</strong></div>`).join('')}</div>`;
}

function renderOutcomeRow(row) {
  const settlements = row.settlements || {};
  return `<tr><td>${esc(row.symbol || '-')}</td><td>${esc(row.record_kind || '-')}</td><td>${statusBadge(row.status || 'pending')}</td><td>${esc(row.synthetic_used ? 'yes' : 'no')}</td><td>${esc((settlements.n1 || {}).status || '-')}</td><td>${esc((settlements.n3 || {}).status || '-')}</td><td>${esc((settlements.n5 || {}).status || '-')}</td><td>${row.score == null ? '-' : Number(row.score).toFixed(4)}</td></tr>`;
}

function money(value) {
  const number = Number(value || 0);
  return number.toLocaleString(undefined, { style: 'currency', currency: 'USD', maximumFractionDigits: 2 });
}
