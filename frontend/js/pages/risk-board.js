import { api } from '../qtapi.js?v=8';
import { toast } from '../components/toast.js?v=8';
import { getLang, onLangChange } from '../i18n.js?v=8';
import {
  emptyState,
  esc,
  loadPayloadSnapshot,
  metric,
  num,
  persistPayloadSnapshot,
  pct,
  renderDegradedNotice,
  renderError,
  renderTokenPreview,
  setLoading,
  statusBadge,
} from './workbench-utils.js?v=8';

let _container = null;
let _langCleanup = null;
let _board = null;
let _actionState = { tone: 'pending', text: '' };
let _degradedMeta = null;

const RISK_BOARD_CACHE_KEY = 'qt.risk-board.snapshot.v1';
const RISK_BOARD_CACHE_TTL_MS = 20 * 60 * 1000;

const COPY = {
  en: {
    title: 'Risk Board',
    subtitle: 'Judge + Risk Manager gate the paper path before any auto-submit can happen.',
    symbol: 'Symbol',
    ttl: 'Signal TTL (min)',
    refresh: 'Refresh Board',
    evaluate: 'Evaluate Risk',
    loading: 'Loading risk board...',
    evaluating: 'Evaluating risk approval...',
    refreshed: 'Risk board refreshed',
    evaluated: 'Risk approval updated',
    failed: 'Risk evaluation failed',
    stateHint: 'Board State',
    latest: 'Approval Snapshot',
    controls: 'Risk Controls',
    ledger: 'Approval Ledger',
    alerts: 'Risk Alerts',
    approval: 'Approval',
    action: 'Action',
    kelly: 'Kelly Cap',
    maxWeight: 'Max Weight',
    ttlMetric: 'TTL',
    hardBlocks: 'Hard Blocks',
    drawdown: 'Drawdown',
    notional: 'Notional',
    rationale: 'Reason Summary',
    controlsHint: 'These controls stay live even when paper autopilot is armed.',
    ledgerHint: 'Every approval writes the requested action, verdict, weight, TTL, and the first risk reason.',
    alertsHint: 'Duplicate orders, drawdown breaches, stale orders, and budget pressure land here first.',
    noApproval: 'No approval yet',
    noApprovalHint: 'Run Evaluate Risk after the latest debate is ready for this symbol.',
    noLedger: 'No risk approvals yet',
    noLedgerHint: 'Once the risk gate runs, the approval chain will appear here for audit.',
    noAlerts: 'No risk alerts today',
    noAlertsHint: 'This means the duplicate, drawdown, stale-order, and budget-breach checks are currently quiet.',
    broker: 'Broker',
    mode: 'Mode',
    refreshRate: 'Refresh Rate',
    singleCap: 'Single-Name Cap',
    dailyOrders: 'Max Daily Orders',
    cashBuffer: 'Cash Buffer',
    duplicateWindow: 'Duplicate Window',
    killSwitch: 'Kill Switch',
    duplicate: 'Duplicate Guard',
    budget: 'Budget Gate',
    stale: 'Stale Order Guard',
    watch: 'watch',
    block: 'block',
    logged: 'logged',
    open: 'open',
    closed: 'closed',
    nextAction: 'Next Action',
    nextActionText: 'If the verdict is approve or reduce, Trading Ops can still decide whether to run shadow-only, review-only, or paper submit.',
  },
  zh: {
    title: '风控板',
    subtitle: 'Judge 与 Risk Manager 组成双门禁，任何 Paper 自动提交通道都必须先经过这里。',
    symbol: '股票',
    ttl: '信号 TTL（分钟）',
    refresh: '刷新风控板',
    evaluate: '评估风控',
    loading: '正在加载风控板...',
    evaluating: '正在评估风控审批...',
    refreshed: '风控板已刷新',
    evaluated: '风控审批已更新',
    failed: '风控评估失败',
    stateHint: '当前状态',
    latest: '审批快照',
    controls: '风险控制',
    ledger: '审批台账',
    alerts: '风险告警',
    approval: '审批结论',
    action: '动作',
    kelly: 'Kelly 上限',
    maxWeight: '最大权重',
    ttlMetric: 'TTL',
    hardBlocks: '硬阻断',
    drawdown: '回撤',
    notional: '名义金额',
    rationale: '理由摘要',
    controlsHint: '即使已经武装 Paper 自动驾驶，这些风险控制仍然持续生效。',
    ledgerHint: '每次审批都会记录请求动作、结论、建议权重、TTL，以及首条风险理由，便于审计。',
    alertsHint: '重复下单、回撤越界、陈旧订单和预算压力会优先在这里暴露。',
    noApproval: '暂无审批结果',
    noApprovalHint: '请先确保该股票已有最新辩论结果，再运行风控评估。',
    noLedger: '暂无风控审批记录',
    noLedgerHint: '一旦风控门禁运行，这里就会出现完整审批链路。',
    noAlerts: '今日暂无风险告警',
    noAlertsHint: '说明重复单、回撤、陈旧订单和预算越界检查目前都处于安静状态。',
    broker: '券商',
    mode: '模式',
    refreshRate: '刷新频率',
    singleCap: '单票上限',
    dailyOrders: '单日最大订单数',
    cashBuffer: '现金缓冲',
    duplicateWindow: '重复窗口',
    killSwitch: 'Kill Switch',
    duplicate: '重复单守卫',
    budget: '预算门禁',
    stale: '陈旧订单守卫',
    watch: '观察',
    block: '阻断',
    logged: '已记录',
    open: '开启',
    closed: '关闭',
    nextAction: '下一步动作',
    nextActionText: '即使审批通过，Trading Ops 仍会决定是只做 shadow、只做 review，还是进入 Paper 提交流程。',
  },
};

const TRIGGER_LABELS = {
  price_move: { en: 'Price Move', zh: '价格异动' },
  volume_spike: { en: 'Volume Spike', zh: '成交量突增' },
  drawdown_breach: { en: 'Drawdown Breach', zh: '回撤越界' },
  concentration: { en: 'Concentration', zh: '集中度过高' },
  cash_stress: { en: 'Cash Stress', zh: '现金压力' },
  manual_scan: { en: 'Manual Scan', zh: '手动扫描' },
};

function c(key) {
  const lang = getLang() === 'zh' ? 'zh' : 'en';
  return COPY[lang][key] || COPY.en[key] || key;
}

function verdictLabel(value) {
  const normalized = String(value || '').trim().toLowerCase();
  const map = {
    approve: getLang() === 'zh' ? '批准' : 'approve',
    reduce: getLang() === 'zh' ? '缩减' : 'reduce',
    reject: getLang() === 'zh' ? '拒绝' : 'reject',
    halt: getLang() === 'zh' ? '暂停' : 'halt',
    long: getLang() === 'zh' ? '看多' : 'long',
    neutral: getLang() === 'zh' ? '中性' : 'neutral',
    short: getLang() === 'zh' ? '看空' : 'short',
    block: getLang() === 'zh' ? '阻断' : 'block',
  };
  return map[normalized] || String(value || '-');
}

function triggerLabel(value) {
  const normalized = String(value || '').trim().toLowerCase();
  const row = TRIGGER_LABELS[normalized];
  if (!row) return String(value || '-');
  return getLang() === 'zh' ? row.zh : row.en;
}

function statusClass(verdict) {
  const normalized = String(verdict || '').trim().toLowerCase();
  if (normalized === 'approve') return 'is-pass';
  if (normalized === 'reduce') return 'is-watch';
  return 'is-risk';
}

function signalSymbol() {
  return String(_container?.querySelector('#risk-symbol')?.value || 'AAPL').trim().toUpperCase();
}

function riskBoardDegradedState(savedAt, reason) {
  return {
    tone: 'warning',
    saved_at: savedAt || null,
    title: getLang() === 'zh' ? '风控板已切换到缓存快照' : 'Risk Board is showing a cached snapshot',
    reason: reason || (getLang() === 'zh'
      ? '当前继续展示最近一次成功的风控审批结果，等待实时刷新恢复。'
      : 'The latest successful approval snapshot is still visible while the live refresh recovers.'),
    detail: getLang() === 'zh'
      ? '审批快照、控制项、台账和告警都来自最近一次成功结果。'
      : 'Approval snapshot, controls, ledger, and alerts come from the latest successful payload.',
    action: getLang() === 'zh'
      ? '可以继续点击“刷新风控板”或“评估风控”重试。'
      : 'Use Refresh Board or Evaluate Risk to retry.',
  };
}

function hydrateRiskSnapshot() {
  const cached = loadPayloadSnapshot(RISK_BOARD_CACHE_KEY, RISK_BOARD_CACHE_TTL_MS);
  if (!cached?.payload) return false;
  _board = cached.payload;
  _degradedMeta = riskBoardDegradedState(
    cached.saved_at,
    getLang() === 'zh'
      ? '正在回填最近一次成功的风控快照，并在后台重连服务。'
      : 'Rehydrating the latest successful risk snapshot while reconnecting.',
  );
  renderBoard();
  return true;
}

function setState(tone, text) {
  _actionState = { tone, text };
  const host = _container?.querySelector('#risk-board-state');
  if (!host) return;
  const cls = tone === 'error' ? 'is-risk' : tone === 'warning' ? 'is-watch' : tone === 'success' ? 'is-pass' : 'is-review';
  host.innerHTML = `
    <div class="factor-check-row">
      <span>${c('stateHint')}</span>
      <strong class="${cls}">${esc(text)}</strong>
    </div>
  `;
}

export async function render(container) {
  _container = container;
  renderShell();
  wire();
  renderPreview();
  hydrateRiskSnapshot();
  _langCleanup = onLangChange(() => {
    if (!_container?.isConnected) return;
    renderShell();
    wire();
    renderPreview();
    renderBoard();
  });
  await refreshBoard();
}

export function destroy() {
  _langCleanup?.();
  _langCleanup = null;
  _container = null;
  _board = null;
  _degradedMeta = null;
}

function renderShell() {
  _container.innerHTML = `
    <div class="workbench-page risk-board-page" data-no-autotranslate="true">
      <section class="run-panel">
        <div class="run-panel__header">
          <div class="run-panel__title">${c('title')}</div>
          <div class="run-panel__sub">${c('subtitle')}</div>
        </div>
        <div class="run-panel__body">
          <div class="grid-2 compact-control-grid">
            <label class="field field--with-preview">
              <span>${c('symbol')}</span>
              <input id="risk-symbol" value="AAPL">
              <div id="risk-symbol-preview"></div>
            </label>
            <label class="field">
              <span>${c('ttl')}</span>
              <input id="risk-ttl" type="number" value="180" min="1" max="1440">
            </label>
          </div>
          <div id="risk-board-state" class="workbench-inline-status"></div>
        </div>
        <div class="run-panel__foot workbench-action-grid">
          <button class="btn btn-primary workbench-action-btn" id="btn-risk-evaluate">${c('evaluate')}</button>
          <button class="btn btn-ghost workbench-action-btn" id="btn-risk-refresh">${c('refresh')}</button>
        </div>
      </section>

      <section class="grid-2 workbench-main-grid risk-board-grid">
        <article class="card">
          <div class="card-header"><span class="card-title">${c('latest')}</span></div>
          <div class="card-body" id="risk-latest">${emptyState(c('loading'))}</div>
        </article>
        <article class="card">
          <div class="card-header"><span class="card-title">${c('controls')}</span></div>
          <div class="card-body" id="risk-controls">${emptyState(c('loading'))}</div>
        </article>
      </section>

      <section class="grid-2 workbench-main-grid risk-board-lower-grid" style="margin-top:16px">
        <article class="card risk-board-ledger-card">
          <div class="card-header"><span class="card-title">${c('ledger')}</span></div>
          <div class="card-body" id="risk-ledger">${emptyState(c('loading'))}</div>
        </article>
        <article class="card risk-board-alerts-card">
          <div class="card-header"><span class="card-title">${c('alerts')}</span></div>
          <div class="card-body" id="risk-alerts">${emptyState(c('loading'))}</div>
        </article>
      </section>
    </div>`;
}

function wire() {
  _container.querySelector('#btn-risk-refresh')?.addEventListener('click', refreshBoard);
  _container.querySelector('#btn-risk-evaluate')?.addEventListener('click', evaluateRisk);
  _container.querySelector('#risk-symbol')?.addEventListener('input', renderPreview);
}

function renderPreview() {
  const host = _container?.querySelector('#risk-symbol-preview');
  if (!host) return;
  host.innerHTML = renderTokenPreview([signalSymbol()], { tone: 'accent', maxItems: 1 });
  setState(_actionState.tone, _actionState.text || c('controlsHint'));
}

async function refreshBoard() {
  ['#risk-latest', '#risk-controls', '#risk-ledger', '#risk-alerts'].forEach((selector) => {
    setLoading(_container.querySelector(selector), c('loading'));
  });
  setState('pending', c('loading'));
  try {
    _board = await api.trading.riskBoard(signalSymbol(), 12);
    persistPayloadSnapshot(RISK_BOARD_CACHE_KEY, _board, { symbol: signalSymbol() });
    _degradedMeta = null;
    setState('success', c('refreshed'));
    renderBoard();
  } catch (error) {
    const cached = loadPayloadSnapshot(RISK_BOARD_CACHE_KEY, RISK_BOARD_CACHE_TTL_MS);
    if (cached?.payload) {
      _board = cached.payload;
      _degradedMeta = riskBoardDegradedState(cached.saved_at, error.message);
      setState('warning', error.message || c('failed'));
      renderBoard();
      return;
    }
    setState('error', error.message || c('failed'));
    ['#risk-latest', '#risk-controls', '#risk-ledger', '#risk-alerts'].forEach((selector) => {
      renderError(_container.querySelector(selector), error, { onRetry: refreshBoard });
    });
  }
}

async function evaluateRisk() {
  const button = _container?.querySelector('#btn-risk-evaluate');
  if (button) {
    button.disabled = true;
    button.textContent = c('evaluating');
  }
  setState('pending', c('evaluating'));
  setLoading(_container.querySelector('#risk-latest'), c('evaluating'));
  try {
    await api.trading.riskEvaluate({
      symbol: signalSymbol(),
      signal_ttl_minutes: Number(_container?.querySelector('#risk-ttl')?.value || 180),
    });
    toast.success(c('evaluated'));
    await refreshBoard();
  } catch (error) {
    const cached = loadPayloadSnapshot(RISK_BOARD_CACHE_KEY, RISK_BOARD_CACHE_TTL_MS);
    if (cached?.payload) {
      _board = cached.payload;
      _degradedMeta = riskBoardDegradedState(cached.saved_at, error.message);
      setState('warning', error.message || c('failed'));
      renderBoard();
      toast.error(c('failed'), error.message || '');
      return;
    }
    setState('error', error.message || c('failed'));
    renderError(_container.querySelector('#risk-latest'), error, { onRetry: evaluateRisk });
    toast.error(c('failed'), error.message || '');
  } finally {
    if (button) {
      button.disabled = false;
      button.textContent = c('evaluate');
    }
  }
}

function renderBoard() {
  if (!_board) return;
  renderLatestApproval();
  renderControls();
  renderLedger();
  renderAlerts();
}

function renderLatestApproval() {
  const host = _container.querySelector('#risk-latest');
  const latest = _board.latest_approval;
  const degradedBanner = _degradedMeta ? renderDegradedNotice(_degradedMeta) : '';
  if (!latest) {
    host.innerHTML = emptyState(c('noApproval'), c('noApprovalHint'));
    return;
  }

  host.innerHTML = `
    ${degradedBanner}
    <div class="workbench-metric-grid">
      ${metric(c('approval'), verdictLabel(latest.verdict), String(latest.verdict || '').toLowerCase() === 'approve' ? 'positive' : 'risk')}
      ${metric(c('action'), verdictLabel(latest.approved_action))}
      ${metric(c('kelly'), pct(latest.kelly_fraction || 0))}
      ${metric(c('maxWeight'), pct(latest.max_position_weight || latest.recommended_weight || 0))}
      ${metric(c('ttlMetric'), `${latest.signal_ttl_minutes || 0}m`)}
      ${metric(c('hardBlocks'), latest.hard_blocks?.length || 0, latest.hard_blocks?.length ? 'risk' : 'positive')}
    </div>
    <div class="workbench-kv-list compact-kv-list">
      <div class="workbench-kv-row"><span>${c('notional')}</span><strong>$${Number(latest.recommended_notional || 0).toLocaleString()}</strong></div>
      <div class="workbench-kv-row"><span>${c('drawdown')}</span><strong>${pct(latest.drawdown_estimate || 0)}</strong></div>
      <div class="workbench-kv-row"><span>${c('rationale')}</span><strong>${esc((latest.rationale || latest.risk_flags || latest.hard_blocks || ['-']).slice(0, 2).join(' | '))}</strong></div>
    </div>
    <div class="factor-checklist">
      ${(latest.rationale || []).map((item) => `<div class="factor-check-row"><span>${esc(item)}</span><strong class="is-pass">${c('logged')}</strong></div>`).join('')}
      ${(latest.risk_flags || []).map((item) => `<div class="factor-check-row"><span>${esc(item)}</span><strong class="is-watch">${c('watch')}</strong></div>`).join('')}
      ${(latest.hard_blocks || []).map((item) => `<div class="factor-check-row"><span>${esc(item)}</span><strong class="is-risk">${c('block')}</strong></div>`).join('')}
      ${!(latest.rationale || []).length && !(latest.risk_flags || []).length && !(latest.hard_blocks || []).length
        ? `<div class="factor-check-row"><span>${c('nextAction')}</span><strong class="${statusClass(latest.verdict)}">${esc(c('nextActionText'))}</strong></div>`
        : ''}
    </div>
  `;
}

function renderControls() {
  const host = _container.querySelector('#risk-controls');
  const controls = _board.controls || {};
  const latest = _board.latest_approval || {};
  const degradedBanner = _degradedMeta ? renderDegradedNotice(_degradedMeta) : '';
  host.innerHTML = `
    ${degradedBanner}
    <div class="workbench-metric-grid">
      ${metric(c('killSwitch'), controls.kill_switch_enabled ? c('open') : c('closed'), controls.kill_switch_enabled ? 'risk' : 'positive')}
      ${metric(c('broker'), controls.default_broker || 'alpaca')}
      ${metric(c('mode'), controls.default_mode || 'paper')}
      ${metric(c('refreshRate'), `${controls.realtime_refresh_seconds || 5}s`)}
    </div>
    <div class="workbench-kv-list compact-kv-list">
      <div class="workbench-kv-row"><span>${c('singleCap')}</span><strong>${pct(controls.single_name_weight_cap || latest.max_position_weight || 0)}</strong></div>
      <div class="workbench-kv-row"><span>${c('dailyOrders')}</span><strong>${esc(controls.max_daily_orders || '-')}</strong></div>
      <div class="workbench-kv-row"><span>${c('cashBuffer')}</span><strong>${esc(controls.min_buying_power_buffer || '-')}</strong></div>
      <div class="workbench-kv-row"><span>${c('duplicateWindow')}</span><strong>${esc(controls.duplicate_order_window_minutes || '-')}m</strong></div>
    </div>
    <div class="factor-checklist">
      <div class="factor-check-row"><span>${c('duplicate')}</span><strong class="is-pass">${controls.duplicate_order_window_minutes ? `${controls.duplicate_order_window_minutes}m` : c('closed')}</strong></div>
      <div class="factor-check-row"><span>${c('budget')}</span><strong class="is-pass">${pct(latest.max_position_weight || controls.single_name_weight_cap || 0)}</strong></div>
      <div class="factor-check-row"><span>${c('stale')}</span><strong class="is-watch">${latest.signal_ttl_minutes ? `${latest.signal_ttl_minutes}m` : '-'}</strong></div>
    </div>
    <div class="workbench-section">
      <div class="workbench-section__title">${c('controls')}</div>
      <p class="workbench-section__hint">${c('controlsHint')}</p>
    </div>
  `;
}

function renderLedger() {
  const host = _container.querySelector('#risk-ledger');
  const approvals = Array.isArray(_board.approvals) ? _board.approvals : [];
  const degradedBanner = _degradedMeta ? renderDegradedNotice(_degradedMeta) : '';
  if (!approvals.length) {
    host.innerHTML = emptyState(c('noLedger'), c('noLedgerHint'));
    return;
  }

  host.innerHTML = `
    ${degradedBanner}
    <div class="workbench-section">
      <div class="workbench-section__title">${c('ledger')}</div>
      <p class="workbench-section__hint">${c('ledgerHint')}</p>
    </div>
    <div class="workbench-list workbench-scroll-list">
      ${approvals.map((item) => `
        <article class="workbench-item">
          <div class="workbench-item__head">
            <strong>${esc(item.symbol)} | ${esc(verdictLabel(item.verdict))}</strong>
            ${statusBadge(item.verdict)}
          </div>
          <p>${esc((item.hard_blocks || item.risk_flags || item.rationale || ['Risk gate logged.'])[0])}</p>
          <div class="workbench-item__meta">
            <span>${esc(item.generated_at || '-')}</span>
            <span>${c('action')}=${esc(verdictLabel(item.approved_action || item.requested_action || '-'))}</span>
            <span>w=${pct(item.recommended_weight || 0)}</span>
            <span>ttl=${esc(item.signal_ttl_minutes || '-')}m</span>
          </div>
        </article>
      `).join('')}
    </div>
  `;
}

function renderAlerts() {
  const host = _container.querySelector('#risk-alerts');
  const alerts = Array.isArray(_board.alerts) ? _board.alerts : [];
  const degradedBanner = _degradedMeta ? renderDegradedNotice(_degradedMeta) : '';
  if (!alerts.length) {
    host.innerHTML = emptyState(c('noAlerts'), c('noAlertsHint'));
    return;
  }

  host.innerHTML = `
    ${degradedBanner}
    <div class="workbench-section risk-alerts-summary">
      <div class="workbench-section__title">${c('alerts')}</div>
      <p class="workbench-section__hint">${c('alertsHint')}</p>
    </div>
    <div class="workbench-metric-grid risk-alerts-metrics">
      ${metric(c('duplicate'), countAlert(alerts, 'duplicate'), countAlert(alerts, 'duplicate') ? 'risk' : 'positive')}
      ${metric(c('drawdown'), countAlert(alerts, 'drawdown'), countAlert(alerts, 'drawdown') ? 'risk' : 'positive')}
      ${metric(c('stale'), countAlert(alerts, 'stale'), countAlert(alerts, 'stale') ? 'risk' : 'positive')}
      ${metric(c('budget'), countAlert(alerts, 'budget'), countAlert(alerts, 'budget') ? 'risk' : 'positive')}
    </div>
    <div class="workbench-list workbench-scroll-list risk-alerts-list">
      ${alerts.map((item) => `
        <article class="workbench-item">
          <div class="workbench-item__head">
            <strong>${esc(item.symbol || '-')} | ${esc(triggerLabel(item.trigger_type))}</strong>
            ${statusBadge(item.risk_decision || 'watch')}
          </div>
          <p>${esc(item.agent_analysis || '')}</p>
          <div class="workbench-item__meta">
            <span>${esc(item.timestamp || '-')}</span>
            <span>${c('duplicate')}=${num(item.trigger_value || 0)}</span>
            <span>${c('budget')}=${num(item.threshold || 0)}</span>
          </div>
        </article>
      `).join('')}
    </div>
  `;
}

function countAlert(alerts, kind) {
  return alerts.filter((item) => classifyAlert(item) === kind).length;
}

function classifyAlert(alert) {
  const text = `${alert?.trigger_type || ''} ${alert?.agent_analysis || ''}`.toLowerCase();
  if (text.includes('duplicate')) return 'duplicate';
  if (text.includes('drawdown')) return 'drawdown';
  if (text.includes('stale')) return 'stale';
  if (text.includes('budget') || text.includes('cash')) return 'budget';
  return 'drawdown';
}
