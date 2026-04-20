import { api } from '../qtapi.js?v=8';
import { getLang, onLangChange } from '../i18n.js?v=8';
import {
  emptyState,
  esc,
  metric,
  num,
  pct,
  renderError,
  renderTokenPreview,
  setLoading,
  statusBadge,
} from './workbench-utils.js?v=8';

let _container = null;
let _langCleanup = null;
let _board = null;

const COPY = {
  en: {
    title: 'Risk Board',
    subtitle: 'Risk manager approvals, single-name limits, drawdown gates, and kill-switch posture.',
    symbol: 'Symbol',
    ttl: 'Signal TTL (min)',
    refresh: 'Refresh Board',
    evaluate: 'Evaluate Risk',
    latest: 'Latest Approval',
    controls: 'Risk Controls',
    ledger: 'Approval Ledger',
    alerts: 'Risk Alerts',
    loading: 'Loading risk board...',
    evaluating: 'Evaluating risk gate...',
    noApproval: 'No approval yet',
    noApprovalHint: 'Run Evaluate Risk after at least one debate.',
    noLedger: 'No risk approvals yet',
    noAlerts: 'No risk alerts today',
    verdict: 'Verdict',
    action: 'Action',
    weight: 'Weight',
    notional: 'Notional',
    drawdown: 'Drawdown',
    broker: 'Broker',
    mode: 'Mode',
    refreshRate: 'Refresh Rate',
    singleCap: 'Single-name cap',
    dailyOrders: 'Max daily orders',
    cashBuffer: 'Min cash buffer',
    duplicateWindow: 'Duplicate window',
    trigger: 'Trigger',
    threshold: 'Threshold',
    logged: 'logged',
    watch: 'watch',
    block: 'block',
  },
  zh: {
    title: '风控板',
    subtitle: '查看 Risk Manager 审批、单票上限、回撤门禁，以及 kill switch 姿态。',
    symbol: '股票',
    ttl: '信号 TTL（分钟）',
    refresh: '刷新风控板',
    evaluate: '评估风控',
    latest: '最新审批',
    controls: '风控控制',
    ledger: '审批台账',
    alerts: '风险告警',
    loading: '正在加载风控板...',
    evaluating: '正在评估风控门禁...',
    noApproval: '暂无审批结果',
    noApprovalHint: '至少完成一轮辩论后再运行风控评估。',
    noLedger: '暂无风控审批记录',
    noAlerts: '今日暂无风险告警',
    verdict: '结论',
    action: '动作',
    weight: '权重',
    notional: '名义金额',
    drawdown: '回撤',
    broker: '券商',
    mode: '模式',
    refreshRate: '刷新频率',
    singleCap: '单票上限',
    dailyOrders: '单日最大订单数',
    cashBuffer: '最小现金缓冲',
    duplicateWindow: '重复下单窗口',
    trigger: '触发值',
    threshold: '阈值',
    logged: '已记录',
    watch: '观察',
    block: '阻止',
  },
};

const RATIONALE_COPY_ZH = new Map([
  ['Single-name cap respected.', '单票上限已满足。'],
  ['No duplicate paper order found.', '未发现重复纸面订单。'],
  ['Keep notional within Kelly cap.', '名义金额保持在 Kelly 上限内。'],
  ['Risk gate logged.', '风控门禁已记录。'],
]);

const TRIGGER_TYPE_ZH = {
  price_move: '价格异动',
  volume_spike: '成交量激增',
  drawdown_breach: '回撤越界',
  concentration: '集中度过高',
  cash_stress: '现金压力',
};

function c(key) {
  const lang = getLang() === 'zh' ? 'zh' : 'en';
  return COPY[lang][key] || COPY.en[key] || key;
}

function t(en, zh) {
  return getLang() === 'zh' ? zh : en;
}

function riskLabel(value) {
  const normalized = String(value || '').trim().toLowerCase();
  const map = {
    approve: t('approve', '批准'),
    reduce: t('reduce', '缩减'),
    reject: t('reject', '拒绝'),
    halt: t('halt', '暂停'),
    buy: t('buy', '买入'),
    sell: t('sell', '卖出'),
    hold: t('hold', '持有'),
    neutral: t('neutral', '中性'),
  };
  return map[normalized] || String(value || '-');
}

function zhText(raw) {
  const value = String(raw || '').trim();
  if (!value || getLang() !== 'zh') return value;
  return RATIONALE_COPY_ZH.get(value) || value;
}

function triggerLabel(raw) {
  const value = String(raw || '').trim();
  if (!value || getLang() !== 'zh') return value;
  return TRIGGER_TYPE_ZH[value] || value;
}

export async function render(container) {
  _container = container;
  renderShell();
  wire();
  renderPreview();
  _langCleanup = onLangChange(() => {
    if (_container) {
      renderShell();
      wire();
      renderPreview();
      renderBoard();
    }
  });
  await refreshBoard();
}

export function destroy() {
  _container = null;
  _board = null;
  _langCleanup?.();
  _langCleanup = null;
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
        <article class="card">
          <div class="card-header"><span class="card-title">${c('ledger')}</span></div>
          <div class="card-body" id="risk-ledger">${emptyState(c('loading'))}</div>
        </article>
        <article class="card">
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

function symbol() {
  return String(_container.querySelector('#risk-symbol')?.value || 'AAPL').trim().toUpperCase();
}

function renderPreview() {
  _container.querySelector('#risk-symbol-preview').innerHTML = renderTokenPreview([symbol()], { tone: 'accent', maxItems: 1 });
}

async function refreshBoard() {
  const targets = ['#risk-latest', '#risk-controls', '#risk-ledger', '#risk-alerts']
    .map((selector) => _container.querySelector(selector));
  targets.forEach((node) => setLoading(node, c('loading')));
  try {
    _board = await api.trading.riskBoard(symbol(), 12);
    renderBoard();
  } catch (err) {
    targets.forEach((node) => renderError(node, err));
  }
}

async function evaluateRisk() {
  setLoading(_container.querySelector('#risk-latest'), c('evaluating'));
  try {
    await api.trading.riskEvaluate({
      symbol: symbol(),
      signal_ttl_minutes: Number(_container.querySelector('#risk-ttl')?.value || 180),
    });
    await refreshBoard();
  } catch (err) {
    renderError(_container.querySelector('#risk-latest'), err);
  }
}

function renderBoard() {
  if (!_board) return;
  const latest = _board.latest_approval;
  _container.querySelector('#risk-latest').innerHTML = latest ? `
    <div class="workbench-metric-grid">
      ${metric(c('verdict'), riskLabel(latest.verdict), latest.verdict === 'approve' ? 'positive' : 'risk')}
      ${metric(c('action'), riskLabel(latest.approved_action))}
      ${metric('Kelly', pct(latest.kelly_fraction || 0))}
      ${metric(c('weight'), pct(latest.recommended_weight || 0))}
      ${metric(c('notional'), num(latest.recommended_notional || 0, 2))}
      ${metric(c('drawdown'), pct(latest.drawdown_estimate || 0), 'risk')}
    </div>
    <div class="factor-checklist">
      ${(latest.rationale || []).map((item) => `<div class="factor-check-row"><span>${esc(zhText(item))}</span><strong class="is-pass">${c('logged')}</strong></div>`).join('')}
      ${(latest.risk_flags || []).map((item) => `<div class="factor-check-row"><span>${esc(zhText(item))}</span><strong class="is-watch">${c('watch')}</strong></div>`).join('')}
      ${(latest.hard_blocks || []).map((item) => `<div class="factor-check-row"><span>${esc(zhText(item))}</span><strong class="is-risk">${c('block')}</strong></div>`).join('')}
    </div>
  ` : emptyState(c('noApproval'), c('noApprovalHint'));

  const controls = _board.controls || {};
  _container.querySelector('#risk-controls').innerHTML = `
    <div class="workbench-metric-grid">
      ${metric('Kill Switch', controls.kill_switch_enabled ? t('on', '开启') : t('off', '关闭'), controls.kill_switch_enabled ? 'risk' : 'positive')}
      ${metric(c('broker'), controls.default_broker || 'alpaca')}
      ${metric(c('mode'), controls.default_mode || 'paper')}
      ${metric(c('refreshRate'), `${controls.realtime_refresh_seconds || 5}s`)}
    </div>
    <div class="workbench-kv-list compact-kv-list">
      <div class="workbench-kv-row"><span>${c('singleCap')}</span><strong>${pct(controls.single_name_weight_cap || 0)}</strong></div>
      <div class="workbench-kv-row"><span>${c('dailyOrders')}</span><strong>${esc(controls.max_daily_orders || '-')}</strong></div>
      <div class="workbench-kv-row"><span>${c('cashBuffer')}</span><strong>${esc(controls.min_buying_power_buffer || '-')}</strong></div>
      <div class="workbench-kv-row"><span>${c('duplicateWindow')}</span><strong>${esc(controls.duplicate_order_window_minutes || '-')}m</strong></div>
    </div>`;

  const approvals = _board.approvals || [];
  _container.querySelector('#risk-ledger').innerHTML = approvals.length ? `
    <div class="workbench-list workbench-scroll-list">
      ${approvals.map((item) => `
        <article class="workbench-item">
          <div class="workbench-item__head">
            <strong>${esc(item.symbol)} | ${esc(riskLabel(item.verdict))}</strong>
            ${statusBadge(item.verdict)}
          </div>
          <p>${esc(zhText((item.risk_flags || [])[0] || (item.hard_blocks || [])[0] || 'Risk gate logged.'))}</p>
          <div class="workbench-item__meta">
            <span>${esc(item.generated_at || '')}</span>
            <span>${c('weight')}=${pct(item.recommended_weight || 0)}</span>
            <span>ttl=${esc(item.signal_ttl_minutes || '-')}m</span>
          </div>
        </article>
      `).join('')}
    </div>` : emptyState(c('noLedger'));

  const alerts = _board.alerts || [];
  _container.querySelector('#risk-alerts').innerHTML = alerts.length ? `
    <div class="workbench-list workbench-scroll-list">
      ${alerts.map((item) => `
        <article class="workbench-item">
          <div class="workbench-item__head">
            <strong>${esc(item.symbol)} | ${esc(triggerLabel(item.trigger_type))}</strong>
            ${statusBadge(item.risk_decision || 'watch')}
          </div>
          <p>${esc(zhText(item.agent_analysis || ''))}</p>
          <div class="workbench-item__meta">
            <span>${esc(item.timestamp || '')}</span>
            <span>${c('trigger')}=${num(item.trigger_value || 0)}</span>
            <span>${c('threshold')}=${num(item.threshold || 0)}</span>
          </div>
        </article>
      `).join('')}
    </div>` : emptyState(c('noAlerts'));
}
