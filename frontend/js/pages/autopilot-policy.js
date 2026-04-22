import { api } from '../qtapi.js?v=8';
import { toast } from '../components/toast.js?v=8';
import { getLang, onLangChange } from '../i18n.js?v=8';
import {
  emptyState,
  esc,
  metric,
  pct,
  renderError,
  renderTokenPreview,
  setLoading,
  splitTokens,
  statusBadge,
} from './workbench-utils.js?v=8';

let _container = null;
let _langCleanup = null;
let _policy = null;

const COPY = {
  en: {
    title: 'Autopilot Policy',
    subtitle: 'Unified execution policy surface for budget caps, strategy allowlists, and runtime guardrails.',
    refresh: 'Refresh Policy',
    save: 'Save Policy',
    saveFailed: 'Save failed',
    arm: 'Arm Autopilot',
    disarm: 'Disarm',
    paperOnly: 'Execution Surface',
    loading: 'Loading autopilot policy...',
    saving: 'Saving autopilot policy...',
    saved: 'Autopilot policy saved',
    armed: 'Autopilot armed',
    disarmed: 'Autopilot disarmed',
    runtime: 'Runtime State',
    guardrails: 'Guardrails',
    allowlists: 'Allowlists',
    warnings: 'Warnings',
    protections: 'Protections',
    mode: 'Execution Mode',
    autoSubmit: 'Auto Submit',
    runtimeArm: 'Runtime Arm',
    killSwitch: 'Kill Switch',
    protectionMeaning: 'Protection Meaning',
    dailyBudget: 'Daily Budget Cap ($)',
    perTrade: 'Per-Trade Cap ($)',
    maxOpen: 'Max Open Positions',
    maxWeight: 'Max Symbol Weight',
    reviewAbove: 'Require Human Review Above ($)',
    drawdown: 'Drawdown Limit',
    dailyLoss: 'Daily Loss Limit ($)',
    ttl: 'Signal TTL (min)',
    universe: 'Allowed Universe',
    strategies: 'Allowed Strategies',
    nextAction: 'Next Action',
    nextActionReady: 'Trading Ops can arm and run one cycle once both gates are open.',
    nextActionGuarded: 'Open both gates or clear warnings before auto-submit can proceed.',
    policyHint: 'Judge + Risk Manager remain mandatory gates. This page controls execution automation without bypassing broker readiness.',
    noWarnings: 'No policy warnings',
    noWarningsHint: 'Current execution policy is internally consistent.',
  },
  zh: {
    title: '自动驾驶策略',
    subtitle: '统一执行面：集中管理预算上限、策略白名单与运行时门禁。',
    refresh: '刷新策略',
    save: '保存策略',
    saveFailed: '保存失败',
    arm: '武装自动驾驶',
    disarm: '解除武装',
    paperOnly: '执行面',
    loading: '正在加载自动驾驶策略...',
    saving: '正在保存自动驾驶策略...',
    saved: '自动驾驶策略已保存',
    armed: '自动驾驶已武装',
    disarmed: '自动驾驶已解除武装',
    runtime: '运行状态',
    guardrails: '门禁参数',
    allowlists: '白名单',
    warnings: '风险提示',
    protections: '保护项',
    mode: '执行模式',
    autoSubmit: '自动提交',
    runtimeArm: '运行态武装',
    killSwitch: '熔断总开关',
    protectionMeaning: '保护说明',
    dailyBudget: '每日预算上限 ($)',
    perTrade: '单笔上限 ($)',
    maxOpen: '最大持仓数',
    maxWeight: '单票权重上限',
    reviewAbove: '超过该金额需人工复核 ($)',
    drawdown: '回撤上限',
    dailyLoss: '单日亏损上限 ($)',
    ttl: '信号 TTL（分钟）',
    universe: '允许股票池',
    strategies: '允许策略',
    nextAction: '下一步动作',
    nextActionReady: '两道门都打开后，可以在 Trading Ops 中武装并运行一次闭环。',
    nextActionGuarded: '先打开必要门禁或清除警告，再进入自动提交流程。',
    policyHint: 'Judge 与 Risk Manager 仍然是强制双门禁；此页控制通用执行自动化，不绕过券商就绪状态。',
    noWarnings: '暂无策略警告',
    noWarningsHint: '当前执行策略配置自洽。',
  },
};

function c(key) {
  const lang = getLang() === 'zh' ? 'zh' : 'en';
  return COPY[lang][key] || COPY.en[key] || key;
}

function autoSubmitEnabled(policy = _policy) {
  return Boolean(policy?.auto_submit_enabled || policy?.paper_auto_submit_enabled);
}

function yesNo(value) {
  if (getLang() === 'zh') return value ? '开启' : '关闭';
  return value ? 'on' : 'off';
}

function protectionLabel(value) {
  const normalized = String(value || '').trim().toLowerCase().replace(/[\s-]+/g, '_');
  if (normalized === 'auto_submit_disabled') {
    return getLang() === 'zh' ? '自动提交关闭' : 'Auto submit disabled';
  }
  const map = {
    judge_gate: getLang() === 'zh' ? 'Judge 门禁' : 'Judge gate',
    risk_gate: getLang() === 'zh' ? 'Risk 门禁' : 'Risk gate',
    daily_budget: getLang() === 'zh' ? '日预算保护' : 'Daily budget',
    kill_switch: c('killSwitch'),
    duplicate_order_guard: getLang() === 'zh' ? '重复订单保护' : 'Duplicate order guard',
    stale_signal_guard: getLang() === 'zh' ? '过期信号保护' : 'Stale signal guard',
    drawdown_guard: getLang() === 'zh' ? '回撤保护' : 'Drawdown guard',
    notifier_guard: getLang() === 'zh' ? '通知保护' : 'Notifier guard',
  };
  return map[normalized] || normalized.replace(/_/g, ' ').trim() || '-';
}

function protectionDetail(value) {
  const normalized = String(value || '').trim().toLowerCase().replace(/[\s-]+/g, '_');
  if (normalized === 'auto_submit_disabled') {
    return getLang() === 'zh'
      ? '自动提交目前处于关闭状态，执行链路会停留在 review / guarded。'
      : 'Auto submit is currently disabled, so the execution path stays in review/guarded mode.';
  }
  const map = {
    judge_gate: getLang() === 'zh' ? '任何自动提交前都必须先通过 judge 结论。' : 'Judge verdict must clear before any auto-submit.',
    risk_gate: getLang() === 'zh' ? 'Risk Manager 审批仍然是硬门禁。' : 'Risk Manager approval remains a hard gate.',
    daily_budget: getLang() === 'zh' ? '超过每日预算后不会继续自动提交。' : 'Auto-submit stops once the daily budget cap is exhausted.',
    kill_switch: getLang() === 'zh' ? '紧急停机后只保留审计与只读状态。' : 'Emergency stop keeps the page audit-only and blocks submit.',
    duplicate_order_guard: getLang() === 'zh' ? '防止同一标的在短窗口内重复生成订单。' : 'Prevents duplicate orders in the same short window.',
    stale_signal_guard: getLang() === 'zh' ? '过期信号不会继续流入自动提交流程。' : 'Stale signals are blocked from the auto-submit path.',
    drawdown_guard: getLang() === 'zh' ? '回撤过大时会把策略留在 review / guarded 状态。' : 'Large drawdowns keep the strategy in review/guarded mode.',
    notifier_guard: getLang() === 'zh' ? '关键动作需要可见通知链路，避免 silent failure。' : 'Critical actions stay visible through the notifier chain.',
  };
  return map[normalized] || value || '-';
}

function parseNumber(selector, fallback = 0) {
  const value = Number(_container?.querySelector(selector)?.value);
  return Number.isFinite(value) ? value : fallback;
}

function boolValue(selector) {
  return Boolean(_container?.querySelector(selector)?.checked);
}

function textValue(selector) {
  return String(_container?.querySelector(selector)?.value || '').trim();
}

export async function render(container) {
  _container = container;
  renderShell();
  wire();
  _langCleanup = onLangChange(() => {
    if (!_container?.isConnected) return;
    renderShell();
    wire();
    renderPolicy();
  });
  await refreshPolicy();
}

export function destroy() {
  _langCleanup?.();
  _langCleanup = null;
  _container = null;
  _policy = null;
}

function renderShell() {
  _container.innerHTML = `
    <div class="workbench-page autopilot-policy-page" data-no-autotranslate="true">
      <section class="run-panel">
        <div class="run-panel__header">
          <div class="run-panel__title">${c('title')}</div>
          <div class="run-panel__sub">${c('subtitle')}</div>
        </div>
        <div class="run-panel__body">
          <div class="preview-step-grid" id="autopilot-kpis">${emptyState(c('loading'))}</div>
          <div class="workbench-inline-status" id="autopilot-mode-strip">
            <div class="factor-check-row">
              <span>${c('mode')}</span>
              <strong class="is-watch">${esc((_policy?.execution_mode || 'paper').toUpperCase())}</strong>
            </div>
          </div>
        </div>
        <div class="run-panel__foot workbench-action-grid">
          <button class="btn workbench-action-btn workbench-action-btn--secondary" id="btn-autopilot-refresh">${c('refresh')}</button>
          <button class="btn workbench-action-btn workbench-action-btn--primary" id="btn-autopilot-save">${c('save')}</button>
          <button class="btn workbench-action-btn workbench-action-btn--secondary" id="btn-autopilot-arm">${c('arm')}</button>
          <button class="btn workbench-action-btn workbench-action-btn--secondary" id="btn-autopilot-disarm">${c('disarm')}</button>
        </div>
      </section>

      <section class="grid-2 workbench-main-grid trading-ops-grid">
        <article class="card">
          <div class="card-header"><span class="card-title">${c('guardrails')}</span></div>
          <div class="card-body" id="autopilot-guardrails">${emptyState(c('loading'))}</div>
        </article>
        <article class="card">
          <div class="card-header"><span class="card-title">${c('allowlists')}</span></div>
          <div class="card-body" id="autopilot-allowlists">${emptyState(c('loading'))}</div>
        </article>
        <article class="card">
          <div class="card-header"><span class="card-title">${c('warnings')}</span></div>
          <div class="card-body" id="autopilot-warnings">${emptyState(c('loading'))}</div>
        </article>
        <article class="card">
          <div class="card-header"><span class="card-title">${c('protections')}</span></div>
          <div class="card-body" id="autopilot-protections">${emptyState(c('loading'))}</div>
        </article>
      </section>
    </div>
  `;
}

function wire() {
  _container.querySelector('#btn-autopilot-refresh')?.addEventListener('click', refreshPolicy);
  _container.querySelector('#btn-autopilot-save')?.addEventListener('click', savePolicy);
  _container.querySelector('#btn-autopilot-arm')?.addEventListener('click', armPolicy);
  _container.querySelector('#btn-autopilot-disarm')?.addEventListener('click', disarmPolicy);
}

async function refreshPolicy() {
  ['#autopilot-kpis', '#autopilot-guardrails', '#autopilot-allowlists', '#autopilot-warnings', '#autopilot-protections'].forEach((selector) => {
    setLoading(_container.querySelector(selector), c('loading'));
  });
  try {
    _policy = await api.trading.autopilotPolicy();
    renderPolicy();
  } catch (error) {
    ['#autopilot-kpis', '#autopilot-guardrails', '#autopilot-allowlists', '#autopilot-warnings', '#autopilot-protections'].forEach((selector) => {
      renderError(_container.querySelector(selector), error);
    });
  }
}

async function savePolicy() {
  try {
    setLoading(_container.querySelector('#autopilot-guardrails'), c('saving'));
    const enabled = boolValue('#autopilot-enabled');
    const payload = {
      execution_mode: String(_policy?.execution_mode || 'paper').toLowerCase() === 'live' ? 'live' : 'paper',
      execution_permission: 'auto_submit',
      auto_submit_enabled: enabled,
      paper_auto_submit_enabled: enabled,
      armed: _policy?.armed || false,
      daily_budget_cap: parseNumber('#autopilot-daily-budget', _policy?.daily_budget_cap || 0),
      per_trade_cap: parseNumber('#autopilot-per-trade', _policy?.per_trade_cap || 0),
      max_open_positions: parseNumber('#autopilot-max-open', _policy?.max_open_positions || 0),
      max_symbol_weight: parseNumber('#autopilot-max-weight', _policy?.max_symbol_weight || 0),
      allowed_universe: splitTokens(textValue('#autopilot-universe'), { uppercase: true, delimiters: /[,\s]+/ }),
      allowed_strategies: splitTokens(textValue('#autopilot-strategies'), { delimiters: /[,\s]+/ }),
      require_human_review_above: parseNumber('#autopilot-review-above', _policy?.require_human_review_above || 0),
      drawdown_limit: parseNumber('#autopilot-drawdown', _policy?.drawdown_limit || 0),
      daily_loss_limit: parseNumber('#autopilot-daily-loss', _policy?.daily_loss_limit || 0),
      signal_ttl: parseNumber('#autopilot-ttl', _policy?.signal_ttl || 0),
      kill_switch: boolValue('#autopilot-kill-switch'),
      protections: Array.isArray(_policy?.protections) ? _policy.protections : [],
    };
    _policy = await api.trading.saveAutopilotPolicy(payload);
    renderPolicy();
    toast.success(c('saved'));
  } catch (error) {
    renderError(_container.querySelector('#autopilot-guardrails'), error);
    toast.error(c('saveFailed'), error.message || '');
  }
}

async function armPolicy() {
  try {
    _policy = await api.trading.autopilotArm({ armed: true });
    renderPolicy();
    toast.success(c('armed'));
  } catch (error) {
    toast.error(c('armed'), error.message || '');
  }
}

async function disarmPolicy() {
  try {
    _policy = await api.trading.autopilotDisarm({ armed: false });
    renderPolicy();
    toast.success(c('disarmed'));
  } catch (error) {
    toast.error(c('disarmed'), error.message || '');
  }
}

function renderPolicy() {
  if (!_policy) return;
  renderKpis();
  renderGuardrails();
  renderAllowlists();
  renderWarnings();
  renderProtections();
}

function renderKpis() {
  const ready = Boolean(
    (_policy.execution_permission === 'auto_submit' || _policy.execution_permission === 'paper_auto_submit')
      && autoSubmitEnabled(_policy)
      && _policy.armed
      && !_policy.kill_switch
  );
  const modeStrip = _container.querySelector('#autopilot-mode-strip');
  if (modeStrip) {
    modeStrip.innerHTML = `
      <div class="factor-check-row">
        <span>${c('mode')}</span>
        <strong class="is-watch">${esc(`${_policy.execution_mode || 'paper'} / ${_policy.execution_permission || 'manual_review'}`)}</strong>
      </div>
    `;
  }
  _container.querySelector('#autopilot-kpis').innerHTML = `
    ${metric(c('mode'), `${_policy.execution_mode || 'paper'} / ${_policy.execution_permission || 'manual_review'}`)}
    ${metric(c('autoSubmit'), yesNo(autoSubmitEnabled(_policy)), autoSubmitEnabled(_policy) ? 'positive' : 'risk')}
    ${metric(c('runtimeArm'), yesNo(_policy.armed), _policy.armed ? 'positive' : 'risk')}
    ${metric(c('killSwitch'), yesNo(_policy.kill_switch), _policy.kill_switch ? 'risk' : 'positive')}
    ${metric(c('dailyBudget'), `$${Number(_policy.daily_budget_cap || 0).toLocaleString()}`)}
    ${metric(c('nextAction'), ready ? c('nextActionReady') : c('nextActionGuarded'), ready ? 'positive' : 'risk')}
  `;
}

function renderGuardrails() {
  _container.querySelector('#autopilot-guardrails').innerHTML = `
    <div class="grid-2 compact-control-grid">
      <label class="field">
        <span>${c('dailyBudget')}</span>
        <input id="autopilot-daily-budget" type="number" value="${esc(_policy.daily_budget_cap ?? 0)}">
      </label>
      <label class="field">
        <span>${c('perTrade')}</span>
        <input id="autopilot-per-trade" type="number" value="${esc(_policy.per_trade_cap ?? 0)}">
      </label>
      <label class="field">
        <span>${c('maxOpen')}</span>
        <input id="autopilot-max-open" type="number" value="${esc(_policy.max_open_positions ?? 0)}">
      </label>
      <label class="field">
        <span>${c('maxWeight')}</span>
        <input id="autopilot-max-weight" type="number" step="0.01" value="${esc(_policy.max_symbol_weight ?? 0)}">
      </label>
      <label class="field">
        <span>${c('reviewAbove')}</span>
        <input id="autopilot-review-above" type="number" value="${esc(_policy.require_human_review_above ?? 0)}">
      </label>
      <label class="field">
        <span>${c('ttl')}</span>
        <input id="autopilot-ttl" type="number" value="${esc(_policy.signal_ttl ?? 0)}">
      </label>
      <label class="field">
        <span>${c('drawdown')}</span>
        <input id="autopilot-drawdown" type="number" step="0.01" value="${esc(_policy.drawdown_limit ?? 0)}">
      </label>
      <label class="field">
        <span>${c('dailyLoss')}</span>
        <input id="autopilot-daily-loss" type="number" value="${esc(_policy.daily_loss_limit ?? 0)}">
      </label>
    </div>
    <div class="factor-checklist">
      <label class="factor-check-row">
        <span>${c('autoSubmit')}</span>
        <strong><input id="autopilot-enabled" type="checkbox" ${autoSubmitEnabled(_policy) ? 'checked' : ''}></strong>
      </label>
      <label class="factor-check-row">
        <span>${c('killSwitch')}</span>
        <strong><input id="autopilot-kill-switch" type="checkbox" ${_policy.kill_switch ? 'checked' : ''}></strong>
      </label>
    </div>
    <div class="workbench-section">
      <div class="workbench-section__title">${c('paperOnly')}</div>
      <p class="workbench-section__hint">${c('policyHint')}</p>
    </div>
  `;
}

function renderAllowlists() {
  _container.querySelector('#autopilot-allowlists').innerHTML = `
    <div class="grid-1 compact-control-grid">
      <label class="field field--with-preview">
        <span>${c('universe')}</span>
        <input id="autopilot-universe" value="${esc((_policy.allowed_universe || []).join(', '))}">
        <div>${renderTokenPreview(_policy.allowed_universe || [], { tone: 'accent', maxItems: 8 })}</div>
      </label>
      <label class="field field--with-preview">
        <span>${c('strategies')}</span>
        <input id="autopilot-strategies" value="${esc((_policy.allowed_strategies || []).join(', '))}">
        <div>${renderTokenPreview(_policy.allowed_strategies || [], { tone: 'neutral', maxItems: 8 })}</div>
      </label>
    </div>
  `;
}

function renderWarnings() {
  const warnings = Array.isArray(_policy.warnings) ? _policy.warnings : [];
  _container.querySelector('#autopilot-warnings').innerHTML = warnings.length ? `
    <div class="workbench-list">
      ${warnings.map((warning) => `
        <article class="workbench-item">
          <div class="workbench-item__head">
            <strong>${esc(protectionLabel(warning))}</strong>
            ${statusBadge('watch')}
          </div>
          <p>${esc(protectionDetail(warning))}</p>
        </article>
      `).join('')}
    </div>
  ` : emptyState(c('noWarnings'), c('noWarningsHint'));
}

function renderProtections() {
  const protections = Array.isArray(_policy.protections) ? _policy.protections : [];
  _container.querySelector('#autopilot-protections').innerHTML = `
    <div class="workbench-metric-grid">
      ${metric(c('runtimeArm'), yesNo(_policy.armed), _policy.armed ? 'positive' : 'risk')}
      ${metric(c('autoSubmit'), yesNo(autoSubmitEnabled(_policy)), autoSubmitEnabled(_policy) ? 'positive' : 'risk')}
      ${metric(c('maxWeight'), pct(_policy.max_symbol_weight || 0))}
      ${metric(c('drawdown'), pct(_policy.drawdown_limit || 0), 'risk')}
    </div>
    <div class="token-preview">
      ${protections.map((item) => `<span class="token-chip token-chip--accent">${esc(protectionLabel(item))}</span>`).join('')}
    </div>
    <div class="workbench-kv-list compact-kv-list">
      ${protections.map((item) => `
        <div class="workbench-kv-row">
          <span>${esc(protectionLabel(item))}</span>
          <strong>${esc(protectionDetail(item))}</strong>
        </div>
      `).join('')}
      <div class="workbench-kv-row">
        <span>${c('nextAction')}</span>
        <strong>${esc(_policy.armed && autoSubmitEnabled(_policy) && !_policy.kill_switch ? c('nextActionReady') : c('nextActionGuarded'))}</strong>
      </div>
    </div>
  `;
}
