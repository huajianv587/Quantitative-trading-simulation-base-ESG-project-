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
    subtitle: 'Primary control surface for requested mode, guardrails, and execution automation.',
    refresh: 'Refresh Policy',
    save: 'Save Policy',
    saveFailed: 'Save failed',
    arm: 'Arm Autopilot',
    disarm: 'Disarm',
    loading: 'Loading autopilot policy...',
    saving: 'Saving autopilot policy...',
    saved: 'Autopilot policy saved',
    armed: 'Autopilot armed',
    disarmed: 'Autopilot disarmed',
    armBlocked: 'Live mode is selected but not ready yet.',
    runtime: 'Mode Summary',
    guardrails: 'Guardrails',
    allowlists: 'Allowlists',
    warnings: 'Warnings',
    protections: 'Protections',
    requestedMode: 'Requested Mode',
    effectiveMode: 'Effective Mode',
    paperReady: 'Paper Readiness',
    liveReady: 'Live Readiness',
    liveAvailable: 'Live Available',
    blockReason: 'Block Reason',
    nextActions: 'Next Actions',
    modeSelect: 'Execution Mode',
    paperMode: 'Paper (Simulated)',
    liveMode: 'Live (Real)',
    autoSubmit: 'Auto Submit',
    runtimeArm: 'Autopilot Arm',
    killSwitch: 'Kill Switch',
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
    noWarnings: 'No policy warnings',
    noWarningsHint: 'The current policy is internally consistent.',
    policyHint: 'Paper is the current recommended path. Live can be selected now, but execution stays blocked until live credentials, live account readiness, and broker gates all pass.',
    nextActionReady: 'Paper is ready. You can arm autopilot and run one cycle from Trading Ops.',
    nextActionGuarded: 'Keep validating in paper, or finish live readiness before enabling live execution.',
    on: 'On',
    off: 'Off',
    yes: 'Yes',
    no: 'No',
    unknown: 'Not set',
    recommendedPath: 'Current Recommendation',
    paperPreferred: 'Paper is the active product path',
    liveDeferred: 'Live is visible and selectable, but still gated',
  },
  zh: {
    title: '自动驾驶策略',
    subtitle: '统一管理请求模式、执行门禁与自动化策略，这是当前唯一的模式主入口。',
    refresh: '刷新策略',
    save: '保存策略',
    saveFailed: '保存失败',
    arm: '武装自动驾驶',
    disarm: '解除武装',
    loading: '正在加载自动驾驶策略...',
    saving: '正在保存自动驾驶策略...',
    saved: '自动驾驶策略已保存',
    armed: '自动驾驶已武装',
    disarmed: '自动驾驶已解除武装',
    armBlocked: '当前已选择 Live 模式，但实盘尚未就绪，暂时不能武装。',
    runtime: '模式摘要',
    guardrails: '门禁参数',
    allowlists: '白名单',
    warnings: '风险提示',
    protections: '保护与说明',
    requestedMode: '当前选择模式',
    effectiveMode: '当前生效模式',
    paperReady: 'Paper 就绪状态',
    liveReady: 'Live 就绪状态',
    liveAvailable: 'Live 可用性',
    blockReason: '阻断原因',
    nextActions: '下一步动作',
    modeSelect: '执行模式',
    paperMode: 'Paper（模拟）',
    liveMode: 'Live（实盘）',
    autoSubmit: '自动提交',
    runtimeArm: '自动驾驶武装',
    killSwitch: '熔断总开关',
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
    noWarnings: '暂无策略警告',
    noWarningsHint: '当前策略配置没有发现明显冲突。',
    policyHint: '当前推荐路径仍然是 Paper。Live 模式已经可见可选，但只有在 live account、live keys 与 broker readiness 全部通过后才会真正执行。',
    nextActionReady: 'Paper 已就绪，可以在交易运维里武装并运行一次闭环。',
    nextActionGuarded: '继续在 Paper 验证；如果想切到 Live，请先完成凭证、账户与门禁就绪。',
    on: '开启',
    off: '关闭',
    yes: '是',
    no: '否',
    unknown: '未设置',
    recommendedPath: '当前推荐路径',
    paperPreferred: '当前产品主路径仍是 Paper',
    liveDeferred: 'Live 已预留，但暂时受门禁限制',
  },
};

function c(key) {
  const lang = getLang() === 'zh' ? 'zh' : 'en';
  return COPY[lang][key] || COPY.en[key] || key;
}

function isMounted() {
  return Boolean(_container && _container.isConnected);
}

function autoSubmitEnabled(policy = _policy) {
  return Boolean(policy?.auto_submit_enabled || policy?.paper_auto_submit_enabled);
}

function yesNo(value) {
  return value ? c('yes') : c('no');
}

function onOff(value) {
  return value ? c('on') : c('off');
}

function humanMode(value) {
  return String(value || '').trim().toLowerCase() === 'live' ? c('liveMode') : c('paperMode');
}

function humanReason(value) {
  const normalized = String(value || '').trim().toLowerCase();
  const isZh = getLang() === 'zh';
  const map = {
    live_credentials_missing: isZh ? '尚未配置 Live 专属 Alpaca 凭证。' : 'Live-specific Alpaca credentials are missing.',
    live_trading_disabled: isZh ? '服务端仍关闭了 Live 提交。' : 'Live routing is still disabled in server settings.',
    live_account_unavailable: isZh ? 'Live 账户尚未接通，或当前密钥没有实盘权限。' : 'Live account is unavailable or current keys do not have live permission.',
    live_not_ready: isZh ? '实盘门禁还没有全部通过。' : 'Live readiness has not passed yet.',
    live_mode_selected: isZh ? '当前已选择 Live 模式，但还没有达到真实执行条件。' : 'Live mode is selected, but it is not ready for execution yet.',
    paper_credentials_missing: isZh ? 'Paper 凭证未配置。' : 'Paper credentials are missing.',
    auto_submit_disabled: isZh ? '自动提交当前处于关闭状态。' : 'Auto submit is currently disabled.',
    autopilot_disarmed: isZh ? '自动驾驶当前未武装。' : 'Autopilot is currently disarmed.',
    kill_switch_enabled: isZh ? '熔断总开关已开启。' : 'Kill switch is enabled.',
    daily_budget_not_set: isZh ? '每日预算上限尚未配置。' : 'Daily budget cap is not configured.',
    no_strategy_allowlist: isZh ? '策略白名单为空。' : 'Strategy allowlist is empty.',
    judge_gate: isZh ? 'Judge 门禁' : 'Judge gate',
    risk_gate: isZh ? 'Risk 门禁' : 'Risk gate',
    kelly_cap: isZh ? 'Kelly 上限' : 'Kelly cap',
    budget_gate: isZh ? '预算门禁' : 'Budget gate',
  };
  return map[normalized] || (value ? String(value) : c('unknown'));
}

function humanNextAction(value) {
  const normalized = String(value || '').trim().toLowerCase();
  const isZh = getLang() === 'zh';
  const map = {
    add_live_alpaca_keys: isZh ? '补充 ALPACA_LIVE_API_KEY / ALPACA_LIVE_API_SECRET。' : 'Add ALPACA_LIVE_API_KEY / ALPACA_LIVE_API_SECRET.',
    keep_using_paper_mode: isZh ? '先继续使用 Paper 完整验证策略。' : 'Keep validating on Paper first.',
    enable_live_trading_after_paper_stabilizes: isZh ? '等 Paper 路径稳定后，再打开 Live 提交开关。' : 'Enable live routing only after the paper path stabilizes.',
    enable_live_trading_when_ready: isZh ? '确认流程稳定后，再打开 Live 交易开关。' : 'Enable live trading only after the path is ready.',
    verify_live_account_and_permissions: isZh ? '确认 Live account 已开通，且密钥具备实盘权限。' : 'Verify the live account and confirm the keys have live permission.',
    verify_live_account_permissions: isZh ? '确认 Live 账户和密钥权限都已打通。' : 'Verify live account and key permissions.',
    verify_live_broker_readiness: isZh ? '检查 broker readiness、预算门禁与风控门禁。' : 'Verify broker readiness and execution gates.',
    configure_paper_credentials: isZh ? '补充 Paper 凭证，恢复当前推荐执行路径。' : 'Configure paper credentials to restore the default execution path.',
    switch_to_paper_mode: isZh ? '切回 Paper 模式继续验证。' : 'Switch back to Paper mode and keep validating.',
  };
  return map[normalized] || (value ? String(value) : c('unknown'));
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
    if (!isMounted()) return;
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
  if (!_container) return;
  _container.innerHTML = `
    <div class="workbench-page autopilot-policy-page" data-no-autotranslate="true">
      <section class="run-panel">
        <div class="run-panel__header">
          <div class="run-panel__title">${c('title')}</div>
          <div class="run-panel__sub">${c('subtitle')}</div>
        </div>
        <div class="run-panel__body">
          <div class="preview-step-grid" id="autopilot-kpis">${emptyState(c('loading'))}</div>
          <div class="workbench-inline-status" id="autopilot-mode-strip">${emptyState(c('loading'))}</div>
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
  if (!isMounted()) return;
  _container.querySelector('#btn-autopilot-refresh')?.addEventListener('click', refreshPolicy);
  _container.querySelector('#btn-autopilot-save')?.addEventListener('click', savePolicy);
  _container.querySelector('#btn-autopilot-arm')?.addEventListener('click', armPolicy);
  _container.querySelector('#btn-autopilot-disarm')?.addEventListener('click', disarmPolicy);
}

async function refreshPolicy() {
  if (!isMounted()) return;
  ['#autopilot-kpis', '#autopilot-guardrails', '#autopilot-allowlists', '#autopilot-warnings', '#autopilot-protections']
    .forEach((selector) => {
      const host = _container?.querySelector(selector);
      if (host) setLoading(host, c('loading'));
    });
  try {
    _policy = await api.trading.autopilotPolicy();
    if (!isMounted()) return;
    renderPolicy();
  } catch (error) {
    if (!isMounted()) return;
    ['#autopilot-kpis', '#autopilot-guardrails', '#autopilot-allowlists', '#autopilot-warnings', '#autopilot-protections']
      .forEach((selector) => {
        const host = _container?.querySelector(selector);
        if (host) renderError(host, error);
      });
  }
}

async function savePolicy() {
  if (!isMounted()) return;
  try {
    const guardrailsHost = _container?.querySelector('#autopilot-guardrails');
    if (guardrailsHost) setLoading(guardrailsHost, c('saving'));
    const enabled = boolValue('#autopilot-enabled');
    const payload = {
      execution_mode: textValue('#autopilot-mode-select') === 'live' ? 'live' : 'paper',
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
    if (!isMounted()) return;
    renderPolicy();
    toast.success(c('saved'));
  } catch (error) {
    if (!isMounted()) return;
    const guardrailsHost = _container?.querySelector('#autopilot-guardrails');
    if (guardrailsHost) renderError(guardrailsHost, error);
    toast.error(c('saveFailed'), error.message || '');
  }
}

async function armPolicy() {
  try {
    _policy = await api.trading.autopilotArm({ armed: true });
    if (!isMounted()) return;
    renderPolicy();
    if (_policy?.block_reason && !_policy?.armed) {
      toast.error(c('armBlocked'), humanReason(_policy.block_reason));
      return;
    }
    toast.success(c('armed'));
  } catch (error) {
    toast.error(c('arm'), error.message || '');
  }
}

async function disarmPolicy() {
  try {
    _policy = await api.trading.autopilotDisarm({ armed: false });
    if (!isMounted()) return;
    renderPolicy();
    toast.success(c('disarmed'));
  } catch (error) {
    toast.error(c('disarm'), error.message || '');
  }
}

function renderPolicy() {
  if (!_policy || !isMounted()) return;
  renderKpis();
  renderGuardrails();
  renderAllowlists();
  renderWarnings();
  renderProtections();
}

function renderKpis() {
  const host = _container?.querySelector('#autopilot-kpis');
  const modeStrip = _container?.querySelector('#autopilot-mode-strip');
  if (!host || !modeStrip) return;

  const requestedMode = _policy.requested_mode || _policy.execution_mode || 'paper';
  const effectiveMode = _policy.effective_mode || 'paper';
  const nextActionSummary = _policy.block_reason ? c('nextActionGuarded') : c('nextActionReady');

  host.innerHTML = `
    ${metric(c('requestedMode'), humanMode(requestedMode))}
    ${metric(c('effectiveMode'), humanMode(effectiveMode), effectiveMode === 'live' ? 'risk' : 'positive')}
    ${metric(c('paperReady'), yesNo(_policy.paper_ready), _policy.paper_ready ? 'positive' : 'risk')}
    ${metric(c('liveReady'), yesNo(_policy.live_ready), _policy.live_ready ? 'positive' : 'risk')}
    ${metric(c('autoSubmit'), onOff(autoSubmitEnabled(_policy)), autoSubmitEnabled(_policy) ? 'positive' : 'risk')}
    ${metric(c('runtimeArm'), onOff(_policy.armed), _policy.armed ? 'positive' : 'risk')}
    ${metric(c('killSwitch'), onOff(_policy.kill_switch), _policy.kill_switch ? 'risk' : 'positive')}
    ${metric(c('recommendedPath'), _policy.block_reason ? c('liveDeferred') : c('paperPreferred'), _policy.block_reason ? 'risk' : 'positive')}
  `;

  modeStrip.innerHTML = `
    <div class="workbench-kv-list compact-kv-list">
      <div class="workbench-kv-row"><span>${c('requestedMode')}</span><strong>${esc(humanMode(requestedMode))}</strong></div>
      <div class="workbench-kv-row"><span>${c('effectiveMode')}</span><strong>${esc(humanMode(effectiveMode))}</strong></div>
      <div class="workbench-kv-row"><span>${c('liveAvailable')}</span><strong>${esc(yesNo(_policy.live_available))}</strong></div>
      <div class="workbench-kv-row"><span>${c('blockReason')}</span><strong>${esc(humanReason(_policy.block_reason))}</strong></div>
      <div class="workbench-kv-row"><span>${c('nextActions')}</span><strong>${esc((_policy.next_actions || []).map(humanNextAction).join(' / ') || nextActionSummary)}</strong></div>
    </div>
  `;
}

function renderGuardrails() {
  const host = _container?.querySelector('#autopilot-guardrails');
  if (!host) return;
  host.innerHTML = `
    <div class="grid-2 compact-control-grid">
      <label class="field">
        <span>${c('modeSelect')}</span>
        <select id="autopilot-mode-select">
          <option value="paper" ${(_policy.execution_mode || 'paper') === 'paper' ? 'selected' : ''}>${c('paperMode')}</option>
          <option value="live" ${_policy.execution_mode === 'live' ? 'selected' : ''}>${c('liveMode')}</option>
        </select>
      </label>
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
      <div class="factor-check-row">
        <span>${c('paperReady')}</span>
        <strong>${esc(yesNo(_policy.paper_ready))}</strong>
      </div>
      <div class="factor-check-row">
        <span>${c('liveReady')}</span>
        <strong>${esc(yesNo(_policy.live_ready))}</strong>
      </div>
    </div>
    <div class="workbench-section">
      <div class="workbench-section__title">${c('runtime')}</div>
      <p class="workbench-section__hint">${c('policyHint')}</p>
    </div>
  `;
}

function renderAllowlists() {
  const host = _container?.querySelector('#autopilot-allowlists');
  if (!host) return;
  host.innerHTML = `
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
  const host = _container?.querySelector('#autopilot-warnings');
  if (!host) return;
  host.innerHTML = warnings.length ? `
    <div class="workbench-list">
      ${warnings.map((warning) => `
        <article class="workbench-item">
          <div class="workbench-item__head">
            <strong>${esc(humanReason(warning))}</strong>
            ${statusBadge('watch')}
          </div>
          <p>${esc(humanReason(warning))}</p>
        </article>
      `).join('')}
    </div>
  ` : emptyState(c('noWarnings'), c('noWarningsHint'));
}

function renderProtections() {
  const protections = Array.isArray(_policy.protections) ? _policy.protections : [];
  const host = _container?.querySelector('#autopilot-protections');
  if (!host) return;
  host.innerHTML = `
    <div class="workbench-metric-grid">
      ${metric(c('requestedMode'), humanMode(_policy.requested_mode || _policy.execution_mode || 'paper'))}
      ${metric(c('effectiveMode'), humanMode(_policy.effective_mode || 'paper'), (_policy.effective_mode || 'paper') === 'live' ? 'risk' : 'positive')}
      ${metric(c('liveAvailable'), yesNo(_policy.live_available), _policy.live_available ? 'positive' : 'risk')}
      ${metric(c('blockReason'), humanReason(_policy.block_reason), _policy.block_reason ? 'risk' : 'positive')}
    </div>
    <div class="token-preview">
      ${(protections.length ? protections : ['judge_gate', 'risk_gate']).map((item) => `
        <span class="token-chip token-chip--accent">${esc(humanReason(item))}</span>
      `).join('')}
    </div>
    <div class="workbench-kv-list compact-kv-list">
      <div class="workbench-kv-row"><span>${c('requestedMode')}</span><strong>${esc(humanMode(_policy.requested_mode || _policy.execution_mode || 'paper'))}</strong></div>
      <div class="workbench-kv-row"><span>${c('effectiveMode')}</span><strong>${esc(humanMode(_policy.effective_mode || 'paper'))}</strong></div>
      <div class="workbench-kv-row"><span>${c('paperReady')}</span><strong>${esc(yesNo(_policy.paper_ready))}</strong></div>
      <div class="workbench-kv-row"><span>${c('liveReady')}</span><strong>${esc(yesNo(_policy.live_ready))}</strong></div>
      <div class="workbench-kv-row"><span>${c('maxWeight')}</span><strong>${esc(pct(_policy.max_symbol_weight || 0))}</strong></div>
      <div class="workbench-kv-row"><span>${c('nextActions')}</span><strong>${esc((_policy.next_actions || []).map(humanNextAction).join(' / ') || (_policy.block_reason ? c('nextActionGuarded') : c('nextActionReady')))}</strong></div>
    </div>
  `;
}
