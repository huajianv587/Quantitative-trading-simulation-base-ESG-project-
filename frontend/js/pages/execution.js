import { api, openExecutionWS } from '../qtapi.js?v=8';
import { toast } from '../components/toast.js?v=8';
import { getLang, getLocale, onLangChange } from '../i18n.js?v=8';
import { getVersionedStorageValue, setVersionedStorageValue } from '../utils.js?v=8';

let _ws = null;
let _orders = [];
let _currentContainer = null;
let _langCleanup = null;
let _killArmed = false;
let _policy = null;

const EXECUTION_PREFILL_STORAGE_KEY = 'qt.execution.prefill';
const WORKFLOW_LATEST_STORAGE_KEY = 'qt.workflow.latest';
const EXECUTION_PREFILL_SCHEMA_VERSION = 1;
const WORKFLOW_LATEST_SCHEMA_VERSION = 1;

const COPY = {
  en: {
    title: 'Execution Monitor',
    subtitle: 'Real broker account sync with a single mode source controlled by Autopilot Policy.',
    planTitle: 'Submit Execution Plan',
    planHint: 'Paper remains the active route. Change the mode in Autopilot Policy when you want to prepare for Live.',
    universe: 'Universe',
    capital: 'Capital Base ($)',
    broker: 'Broker',
    mode: 'Mode',
    modeManaged: 'Mode is managed in Autopilot Policy',
    submitOrders: 'Submit to broker',
    brokerStatus: 'Broker Status',
    account: 'Account',
    clock: 'Clock',
    warnings: 'Warnings',
    note: 'Mode is mirrored from Autopilot Policy.',
    runPlan: 'Run Execution Plan',
    refresh: 'Refresh',
    accountCapital: 'Account Capital',
    positions: 'Live Positions',
    orderFeed: 'Order Feed',
    feedWaiting: 'Waiting for broker events...',
    noOrders: 'No orders yet',
    noPositions: 'No positions yet',
    killSwitch: 'Emergency Control',
    killHint: 'Kill switch cancels pending broker orders immediately and blocks new submissions.',
    killEnable: 'Enable Kill Switch',
    killConfirm: 'Confirm halt for the current execution chain',
    killCancel: 'Cancel',
    killDo: 'Confirm Halt',
    killActive: 'KILL SWITCH ACTIVATED',
    killActiveHint: 'All pending orders cancelled and no new orders can be submitted.',
    liveConfirmTitle: 'Confirm Live Submission',
    liveConfirm: 'Confirm Submit to Live',
    requestedMode: 'Requested Mode',
    effectiveMode: 'Effective Mode',
    paperMode: 'Paper (Simulated)',
    liveMode: 'Live (Real)',
    paperReady: 'Paper Ready',
    liveReady: 'Live Ready',
    liveAvailable: 'Live Available',
    blockReason: 'Block Reason',
    nextActions: 'Next Actions',
    latestWorkflow: 'Latest Hybrid Workflow',
    workflowHint: 'Open the execution created by the one-click paper strategy workflow.',
    openWorkflowExecution: 'Open Workflow Execution',
    noWorkflowExecution: 'No workflow execution saved yet.',
    paperPerformance: 'Paper Performance',
    openPaperPerformance: 'Open Paper Performance',
    blockedTitle: 'Live is selected but still gated',
    blockedHint: 'Switch back to Paper or finish live readiness before attempting execution.',
    accountOnline: 'ACCOUNT ONLINE',
    accountOffline: 'BROKER OFFLINE',
    marketOpen: 'Market Open',
    marketClosed: 'Market Closed',
    unknown: 'Not set',
  },
  zh: {
    title: '执行监控',
    subtitle: '真实 broker 账户同步，但模式来源统一由自动驾驶策略控制。',
    planTitle: '提交执行计划',
    planHint: '当前主路径仍是 Paper。需要准备 Live 时，请去 Autopilot Policy 修改模式。',
    universe: '股票池',
    capital: '资金规模 ($)',
    broker: '券商',
    mode: '模式',
    modeManaged: '模式由自动驾驶策略统一管理',
    submitOrders: '提交到券商',
    brokerStatus: 'Broker 状态',
    account: '账户',
    clock: '时钟',
    warnings: '警告',
    note: '这里显示的是 Autopilot Policy 当前镜像模式。',
    runPlan: '运行执行计划',
    refresh: '刷新',
    accountCapital: '账户资金',
    positions: '实时持仓',
    orderFeed: '订单流',
    feedWaiting: '等待 broker 事件...',
    noOrders: '当前没有订单',
    noPositions: '当前没有持仓',
    killSwitch: '紧急控制',
    killHint: 'Kill switch 会立即取消当前挂单，并阻止新的券商提交。',
    killEnable: '启用熔断开关',
    killConfirm: '确认暂停当前执行链路',
    killCancel: '取消',
    killDo: '确认熔断',
    killActive: 'KILL SWITCH 已激活',
    killActiveHint: '所有待成交订单都会被取消，新的订单也会被阻断。',
    liveConfirmTitle: '确认 Live 提交',
    liveConfirm: '确认提交到 Live',
    requestedMode: '当前选择模式',
    effectiveMode: '当前生效模式',
    paperMode: 'Paper（模拟）',
    liveMode: 'Live（实盘）',
    paperReady: 'Paper 就绪',
    liveReady: 'Live 就绪',
    liveAvailable: 'Live 可用',
    blockReason: '阻断原因',
    nextActions: '下一步动作',
    blockedTitle: '当前已选择 Live，但执行仍然受限',
    blockedHint: '先切回 Paper 继续验证，或先完成 Live 凭证、账户与 readiness。',
    accountOnline: '账户在线',
    accountOffline: 'BROKER 离线',
    marketOpen: '市场开盘',
    marketClosed: '市场休市',
    unknown: '未设置',
  },
};

function c(key) {
  const lang = getLang() === 'zh' ? 'zh' : 'en';
  return COPY[lang][key] || COPY.en[key] || key;
}

function currentMode() {
  return String(_policy?.requested_mode || _policy?.execution_mode || 'paper').toLowerCase() === 'live' ? 'live' : 'paper';
}

function currentBroker(container = _currentContainer) {
  return container?.querySelector('#ex-broker')?.value || 'alpaca';
}

function isMounted(container = _currentContainer) {
  return Boolean(container && container.isConnected);
}

function fmtMoney(value) {
  const number = Number(value || 0);
  return `$${number.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function fmtSignedMoney(value) {
  const number = Number(value || 0);
  return `${number >= 0 ? '+' : '-'}$${Math.abs(number).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function fmtPct(value) {
  const number = Number(value || 0);
  return `${number >= 0 ? '+' : ''}${(number * 100).toFixed(2)}%`;
}

function shortTime(value) {
  if (!value) return '--';
  try {
    return new Date(value).toLocaleTimeString(getLocale(), {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  } catch {
    return String(value);
  }
}

function statusClass(status) {
  if (status === 'filled') return 'filled';
  if (status === 'failed') return 'failed';
  if (status === 'cancelled' || status === 'canceled') return 'neutral';
  return 'pending';
}

function humanMode(value) {
  return String(value || '').trim().toLowerCase() === 'live' ? c('liveMode') : c('paperMode');
}

function yesNo(value) {
  return value ? 'Yes' : 'No';
}

function humanReason(value) {
  const normalized = String(value || '').trim().toLowerCase();
  const isZh = getLang() === 'zh';
  const map = {
    live_credentials_missing: isZh ? '尚未配置 Live 专属 Alpaca 凭证。' : 'Live-specific Alpaca credentials are missing.',
    live_trading_disabled: isZh ? '服务端仍关闭了 Live 提交。' : 'Live routing is still disabled in server settings.',
    live_account_unavailable: isZh ? 'Live 账户尚未接通，或当前密钥没有实盘权限。' : 'Live account is unavailable or current keys do not have live permission.',
    live_not_ready: isZh ? '实盘门禁还没有全部通过。' : 'Live readiness has not passed yet.',
    paper_credentials_missing: isZh ? 'Paper 凭证未配置。' : 'Paper credentials are missing.',
    live_confirmation_required: isZh ? 'Live 提交需要明确的人工确认。' : 'Live submission requires explicit operator confirmation.',
  };
  return map[normalized] || (value ? String(value) : c('unknown'));
}

function humanNextAction(value) {
  const normalized = String(value || '').trim().toLowerCase();
  const isZh = getLang() === 'zh';
  const map = {
    add_live_alpaca_keys: isZh ? '补充 ALPACA_LIVE_API_KEY / ALPACA_LIVE_API_SECRET。' : 'Add ALPACA_LIVE_API_KEY / ALPACA_LIVE_API_SECRET.',
    keep_using_paper_mode: isZh ? '继续使用 Paper 路径完成验证。' : 'Keep validating on the Paper path.',
    enable_live_trading_after_paper_stabilizes: isZh ? '等 Paper 路径稳定后，再打开 Live 提交。' : 'Enable live trading only after the paper path stabilizes.',
    enable_live_trading_when_ready: isZh ? '准备完成后再开启 Live 提交。' : 'Enable live trading only after readiness passes.',
    verify_live_account_and_permissions: isZh ? '确认 Live account 已开通，且密钥具备实盘权限。' : 'Verify the live account and confirm the keys have live permission.',
    verify_live_account_permissions: isZh ? '确认 Live 账户和密钥权限都已打通。' : 'Verify live account and key permissions.',
    verify_live_broker_readiness: isZh ? '检查 broker readiness、预算门禁与风控门禁。' : 'Verify broker readiness and execution gates.',
    configure_paper_credentials: isZh ? '补充 Paper 凭证，恢复主执行路径。' : 'Configure paper credentials to restore the primary route.',
    switch_to_paper_mode: isZh ? '切回 Paper 继续验证。' : 'Switch back to Paper and keep validating.',
    confirm_live_submit_or_switch_to_paper: isZh ? '确认 Live 提交，或切回 Paper。' : 'Confirm live submit or switch back to Paper.',
  };
  return map[normalized] || (value ? String(value) : c('unknown'));
}

function applyPrefill(container) {
  try {
    const payload = getVersionedStorageValue(
      window.sessionStorage,
      EXECUTION_PREFILL_STORAGE_KEY,
      EXECUTION_PREFILL_SCHEMA_VERSION,
    );
    if (!payload) return;
    if (payload.universe) container.querySelector('#ex-universe').value = payload.universe;
    if (payload.capital) container.querySelector('#ex-capital').value = payload.capital;
    if (payload.broker) container.querySelector('#ex-broker').value = payload.broker;
    window.sessionStorage.removeItem(EXECUTION_PREFILL_STORAGE_KEY);
  } catch {
    window.sessionStorage.removeItem(EXECUTION_PREFILL_STORAGE_KEY);
  }
}

function readWorkflowShortcut() {
  return getVersionedStorageValue(window.localStorage, WORKFLOW_LATEST_STORAGE_KEY, WORKFLOW_LATEST_SCHEMA_VERSION);
}

function renderWorkflowShortcut(container, shortcut = readWorkflowShortcut()) {
  const target = container.querySelector('#workflow-shortcut-summary');
  const button = container.querySelector('#btn-open-workflow-execution');
  if (!target) return;
  if (!shortcut || !shortcut.workflow_id) {
    target.innerHTML = `<div>${c('noWorkflowExecution')}</div>`;
    if (button) button.disabled = true;
    return;
  }
  if (button) button.disabled = false;
  target.innerHTML = `
    <div><span class="text-muted">Workflow:</span> <span class="font-mono">${shortcut.workflow_id || '--'}</span></div>
    <div><span class="text-muted">Status:</span> <span class="font-mono">${shortcut.status || '--'}</span></div>
    <div><span class="text-muted">Execution:</span> <span class="font-mono">${shortcut.execution_id || '--'}</span></div>
    <div><span class="text-muted">Submitted:</span> <span class="font-mono">${shortcut.submitted_count || 0}</span></div>
  `;
}

async function openLatestWorkflowExecution(container) {
  let shortcut = readWorkflowShortcut();
  if (!shortcut?.workflow_id) {
    toast.warning(c('latestWorkflow'), c('noWorkflowExecution'));
    renderWorkflowShortcut(container, shortcut);
    return;
  }

  try {
    const workflow = await api.workflows.getPaperStrategy(shortcut.workflow_id);
    shortcut = {
      workflow_id: workflow.workflow_id || shortcut.workflow_id,
      status: workflow.status || shortcut.status,
      execution_id: workflow.execution_id || shortcut.execution_id,
      submitted_count: workflow.submitted_count ?? shortcut.submitted_count ?? 0,
      generated_at: workflow.generated_at || shortcut.generated_at,
    };
    setVersionedStorageValue(window.localStorage, WORKFLOW_LATEST_STORAGE_KEY, shortcut, WORKFLOW_LATEST_SCHEMA_VERSION);
    renderWorkflowShortcut(container, shortcut);
  } catch (_ignore) {
    renderWorkflowShortcut(container, shortcut);
  }

  if (!shortcut.execution_id) {
    toast.warning(c('latestWorkflow'), 'Workflow has no execution id yet.');
    return;
  }

  await loadWorkflowExecution(container, shortcut.execution_id);
}

function buildShell() {
  return `
    <div class="execution-monitor">
      <div class="execution-monitor__title-wrap">
        <div class="execution-monitor__title">${c('title')}</div>
        <div class="execution-monitor__sub" id="execution-monitor-sub">${c('subtitle')}</div>
      </div>
      <div class="execution-monitor__stats">
        <span id="ws-pill" class="live-pill live-pill--off">${c('accountOffline')}</span>
        <span id="monitor-mode" class="badge badge-neutral">PAPER</span>
        <span id="session-pnl" class="execution-monitor__value">$0.00</span>
      </div>
      <div class="execution-monitor__meta">
        <span id="execution-clock">--</span>
        <span id="execution-broker-meta">Alpaca / paper</span>
      </div>
    </div>

    <div class="grid-sidebar execution-grid">
      <div class="execution-left">
        <div class="run-panel">
          <div class="run-panel__header">
            <div class="run-panel__title">${c('planTitle')}</div>
            <div class="run-panel__sub">${c('planHint')}</div>
          </div>
          <div class="run-panel__body">
            <div class="form-group">
              <label class="form-label">${c('universe')}</label>
              <input class="form-input" id="ex-universe" placeholder="AAPL, MSFT, NVDA, SPY">
            </div>

            <div class="form-row">
              <div class="form-group">
                <label class="form-label">${c('capital')}</label>
                <input class="form-input" id="ex-capital" type="number" value="1000000">
              </div>
              <div class="form-group">
                <label class="form-label">${c('broker')}</label>
                <select class="form-select" id="ex-broker">
                  <option value="alpaca">Alpaca</option>
                </select>
              </div>
            </div>

            <div class="form-row">
              <div class="form-group">
                <label class="form-label">${c('mode')}</label>
                <select class="form-select" id="ex-mode" disabled>
                  <option value="paper">${c('paperMode')}</option>
                  <option value="live">${c('liveMode')}</option>
                </select>
              </div>
              <div class="form-group">
                <label class="form-label">${c('submitOrders')}</label>
                <label class="toggle execution-toggle">
                  <input type="checkbox" id="ex-submit" checked>
                  <span class="toggle-track"></span>
                </label>
              </div>
            </div>

            <div class="broker-status-card" id="broker-status-card">
              <div class="broker-status-card__title">${c('brokerStatus')}</div>
              <div class="broker-status-card__body">
                <div><span class="text-muted">${c('requestedMode')}:</span> <span id="execution-requested-mode">--</span></div>
                <div><span class="text-muted">${c('effectiveMode')}:</span> <span id="execution-effective-mode">--</span></div>
                <div><span class="text-muted">${c('paperReady')}:</span> <span id="execution-paper-ready">--</span></div>
                <div><span class="text-muted">${c('liveReady')}:</span> <span id="execution-live-ready">--</span></div>
                <div><span class="text-muted">${c('blockReason')}:</span> <span id="execution-block-reason">--</span></div>
              </div>
              <div class="broker-status-card__note" id="broker-status-note">${c('note')}</div>
            </div>
          </div>
          <div class="run-panel__foot">
            <button class="btn workbench-action-btn workbench-action-btn--primary btn-lg" id="btn-run-exec" style="flex:1">${c('runPlan')}</button>
          </div>
        </div>

        <div class="card" id="workflow-shortcut-card">
          <div class="card-header">
            <span class="card-title">${c('latestWorkflow')}</span>
            <button class="btn btn-ghost btn-sm" id="btn-open-workflow-execution">${c('openWorkflowExecution')}</button>
          </div>
          <div class="card-body">
            <div class="text-muted text-sm">${c('workflowHint')}</div>
            <div class="broker-status-card__body" id="workflow-shortcut-summary" style="margin-top:8px">
              <div>${c('noWorkflowExecution')}</div>
            </div>
          </div>
        </div>

        <div class="card" id="paper-performance-shortcut-card">
          <div class="card-header">
            <span class="card-title">${c('paperPerformance')}</span>
            <button class="btn btn-ghost btn-sm" id="btn-open-paper-performance">${c('openPaperPerformance')}</button>
          </div>
          <div class="card-body">
            <div class="text-muted text-sm">90-day paper metrics, N+1/N+3/N+5 outcomes, and live canary gates.</div>
          </div>
        </div>

        <div class="card">
          <div class="card-header">
            <span class="card-title">${c('accountCapital')}</span>
            <button class="btn btn-ghost btn-sm" id="btn-refresh-account">${c('refresh')}</button>
          </div>
          <div class="card-body">
            <div class="execution-account-grid">
              <div class="execution-account-card"><span>Equity</span><strong id="account-equity">$0.00</strong></div>
              <div class="execution-account-card"><span>Buying Power</span><strong id="account-buying-power">$0.00</strong></div>
              <div class="execution-account-card"><span>Cash</span><strong id="account-cash">$0.00</strong></div>
              <div class="execution-account-card"><span>Daily Change</span><strong id="account-daily-change">$0.00</strong></div>
            </div>
          </div>
        </div>

        <div class="card" style="border-color:rgba(255,64,96,0.22)">
          <div class="card-header" style="background:rgba(255,61,87,0.05)">
            <span class="card-title" style="color:var(--red)">${c('killSwitch')}</span>
          </div>
          <div class="card-body" style="display:flex;flex-direction:column;gap:12px">
            <div class="text-muted text-sm">${c('killHint')}</div>
            <button class="kill-switch" id="btn-kill" style="width:100%;padding:10px" disabled>${c('killEnable')}</button>
            <div id="kill-confirm" style="display:none;flex-direction:column;gap:8px">
              <div style="font-family:var(--f-mono);font-size:11px;color:var(--red);text-align:center;padding:4px 0">${c('killConfirm')}</div>
              <div style="display:flex;gap:8px">
                <button class="btn btn-ghost btn-sm" id="btn-kill-cancel" style="flex:1">${c('killCancel')}</button>
                <button class="btn btn-sm" id="btn-kill-confirm" style="flex:1;background:var(--red);color:#fff;border:none">${c('killDo')}</button>
              </div>
            </div>
            <div id="kill-activated" style="display:none;padding:12px;border-radius:8px;background:rgba(255,61,87,0.12);border:1px solid rgba(255,61,87,0.4);text-align:center">
              <div style="font-family:var(--f-display);font-size:11px;font-weight:700;color:var(--red)">${c('killActive')}</div>
              <div style="font-family:var(--f-mono);font-size:10px;color:var(--red);opacity:0.7;margin-top:4px">${c('killActiveHint')}</div>
            </div>
          </div>
        </div>

        <div class="card">
          <div class="card-header">
            <span class="card-title">${c('positions')}</span>
            <button class="btn btn-ghost btn-sm" id="btn-refresh-pos">${c('refresh')}</button>
          </div>
          <div id="positions-body" class="card-body">
            <div class="text-muted text-sm">Loading...</div>
          </div>
        </div>
      </div>

      <div class="execution-right">
        <div class="results-panel">
          <div class="results-panel__header">
            <span class="card-title">${c('orderFeed')}</span>
            <div style="display:flex;gap:10px;align-items:center">
              <span id="order-count" class="text-xs text-muted font-mono">0 orders</span>
              <select class="form-select" id="filter-status" style="padding:3px 8px;font-size:11px;height:auto;width:auto">
                <option value="all">All</option>
                <option value="filled">Filled</option>
                <option value="pending">Pending</option>
                <option value="failed">Failed</option>
                <option value="cancelled">Cancelled</option>
                <option value="canceled">Canceled</option>
              </select>
              <button class="btn btn-ghost btn-sm" id="btn-refresh-orders">${c('refresh')}</button>
            </div>
          </div>
          <div class="results-panel__body" id="orders-body">
            <div class="loading-overlay" style="min-height:120px"><div class="spinner"></div><span>Loading orders...</span></div>
          </div>
        </div>

        <div class="card">
          <div class="card-header">
            <span class="card-title">${c('orderFeed')}</span>
            <span id="feed-status" class="text-xs text-muted font-mono">connecting...</span>
          </div>
          <div id="feed-log" style="padding:12px 16px;height:220px;overflow-y:auto;display:flex;flex-direction:column-reverse;gap:0">
            <div class="text-muted text-sm">${c('feedWaiting')}</div>
          </div>
        </div>
      </div>
    </div>

    <div class="live-confirm-modal" id="live-confirm-modal" hidden>
      <div class="live-confirm-modal__backdrop" data-live-close></div>
      <div class="live-confirm-modal__panel">
        <div class="live-confirm-modal__title">${c('liveConfirmTitle')}</div>
        <div class="live-confirm-modal__body" id="live-confirm-body"></div>
        <div class="live-confirm-modal__actions">
          <button class="btn btn-ghost" id="btn-live-cancel">${c('killCancel')}</button>
          <button class="btn workbench-action-btn workbench-action-btn--primary" id="btn-live-confirm">${c('liveConfirm')}</button>
        </div>
      </div>
    </div>
  `;
}

export function render(container) {
  _currentContainer = container;
  _ws?.close();
  _ws = null;
  _orders = [];
  _killArmed = false;
  container.innerHTML = buildShell();
  applyPrefill(container);
  bindEvents(container);
  renderWorkflowShortcut(container);
  loadRuntime(container);
  _langCleanup ||= onLangChange(() => {
    if (_currentContainer?.isConnected) render(_currentContainer);
  });
}

export function destroy() {
  _ws?.close();
  _ws = null;
  _orders = [];
  _killArmed = false;
  _currentContainer = null;
  _policy = null;
  _langCleanup?.();
  _langCleanup = null;
}

function bindEvents(container) {
  container.querySelector('#btn-run-exec')?.addEventListener('click', () => requestExecution(container));
  container.querySelector('#btn-refresh-orders')?.addEventListener('click', () => loadOrders(container));
  container.querySelector('#btn-refresh-pos')?.addEventListener('click', () => loadPositions(container));
  container.querySelector('#btn-refresh-account')?.addEventListener('click', () => loadAccount(container));
  container.querySelector('#filter-status')?.addEventListener('change', () => renderOrders(container));
  container.querySelector('#btn-open-workflow-execution')?.addEventListener('click', () => openLatestWorkflowExecution(container));
  container.querySelector('#btn-open-paper-performance')?.addEventListener('click', () => { window.location.hash = '#/paper-performance'; });

  const killButton = container.querySelector('#btn-kill');
  killButton?.addEventListener('click', () => {
    _killArmed = !_killArmed;
    container.querySelector('#kill-confirm').style.display = _killArmed ? 'flex' : 'none';
    killButton.textContent = _killArmed ? '...' : c('killEnable');
  });
  container.querySelector('#btn-kill-cancel')?.addEventListener('click', () => {
    _killArmed = false;
    container.querySelector('#kill-confirm').style.display = 'none';
    killButton.textContent = c('killEnable');
  });
  container.querySelector('#btn-kill-confirm')?.addEventListener('click', async () => {
    try {
      await api.execution.killSwitch(true, 'Manual operator trigger');
      toast.warning(c('killSwitch'), c('killActiveHint'));
      container.querySelector('#kill-confirm').style.display = 'none';
      container.querySelector('#kill-activated').style.display = '';
      killButton.textContent = c('killActive');
    } catch (error) {
      toast.error(c('killSwitch'), error.message || 'Unknown error');
    }
  });

  container.querySelector('#btn-live-cancel')?.addEventListener('click', hideLiveConfirm);
  container.querySelector('#btn-live-confirm')?.addEventListener('click', async () => {
    hideLiveConfirm();
    await submitExecution(container, true);
  });
  container.querySelectorAll('[data-live-close]').forEach((node) => {
    node.addEventListener('click', hideLiveConfirm);
  });
}

async function loadRuntime(container) {
  try {
    _policy = await api.trading.autopilotPolicy();
  } catch {
    _policy = null;
  }
  updateModeBadge(container);
  connectWS(container);
  await Promise.allSettled([
    loadAccount(container),
    loadOrders(container),
    loadPositions(container),
  ]);
}

async function loadWorkflowExecution(container, executionId) {
  try {
    const monitor = await api.execution.monitor(currentBroker(container), executionId, 100, 'paper');
    _orders = monitor.orders || [];
    syncModeFields(monitor);
    renderOrders(container);
    connectWS(container, executionId, 'paper');
    toast.success(c('latestWorkflow'), executionId);
  } catch (error) {
    toast.error(c('latestWorkflow'), error.message || 'Unknown error');
    connectWS(container, executionId, 'paper');
  }
}

function updateModeBadge(container) {
  const requestedMode = currentMode();
  const effectiveMode = _policy?.effective_mode || requestedMode;
  const modeBadge = container.querySelector('#monitor-mode');
  const brokerMeta = container.querySelector('#execution-broker-meta');
  const modeField = container.querySelector('#ex-mode');
  if (modeField) modeField.value = requestedMode;
  if (modeBadge) {
    modeBadge.textContent = effectiveMode.toUpperCase();
    modeBadge.className = `badge ${effectiveMode === 'live' ? 'badge-failed' : 'badge-neutral'}`;
  }
  if (brokerMeta) {
    brokerMeta.textContent = `Alpaca / ${requestedMode} -> ${effectiveMode}`;
  }
}

function updateAccountPill(container, connected, mode) {
  if (!container?.isConnected) return;
  const pill = container.querySelector('#ws-pill');
  if (!pill) return;
  pill.textContent = connected ? c('accountOnline') : c('accountOffline');
  pill.className = connected ? 'live-pill' : 'live-pill live-pill--off';
  const sub = container.querySelector('#execution-monitor-sub');
  if (sub) {
    sub.textContent = connected
      ? `${c('subtitle')} / ${humanMode(mode)}`
      : `${c('subtitle')} / ${c('accountOffline')}`;
  }
}

function renderAccountFallback(container, reason) {
  if (!container?.isConnected) return;
  updateAccountPill(container, false, currentMode());
  const setText = (selector, value) => {
    const node = container.querySelector(selector);
    if (node) node.textContent = value;
  };
  setText('#account-id', '--');
  setText('#account-clock', '--');
  setText('#account-warning-count', '1');
  setText('#broker-status-note', reason);
  setText('#account-equity', '--');
  setText('#account-buying-power', '--');
  setText('#account-cash', '--');
  setText('#account-daily-change', '--');
  setText('#execution-clock', c('accountOffline'));
  const pnl = container.querySelector('#session-pnl');
  if (pnl) {
    pnl.textContent = '--';
    pnl.style.color = 'var(--text-dim)';
  }
  const kill = container.querySelector('#btn-kill');
  if (kill) kill.disabled = true;
}

function syncModeFields(payload) {
  const requestedMode = payload?.requested_mode || _policy?.requested_mode || _policy?.execution_mode || 'paper';
  const effectiveMode = payload?.effective_mode || _policy?.effective_mode || requestedMode;
  const modeField = _currentContainer?.querySelector('#ex-mode');
  if (modeField) modeField.value = requestedMode;
  const requestedHost = _currentContainer?.querySelector('#execution-requested-mode');
  const effectiveHost = _currentContainer?.querySelector('#execution-effective-mode');
  const paperReadyHost = _currentContainer?.querySelector('#execution-paper-ready');
  const liveReadyHost = _currentContainer?.querySelector('#execution-live-ready');
  const blockReasonHost = _currentContainer?.querySelector('#execution-block-reason');
  if (requestedHost) requestedHost.textContent = humanMode(requestedMode);
  if (effectiveHost) effectiveHost.textContent = humanMode(effectiveMode);
  if (paperReadyHost) paperReadyHost.textContent = yesNo(payload?.paper_ready);
  if (liveReadyHost) liveReadyHost.textContent = yesNo(payload?.live_ready);
  if (blockReasonHost) blockReasonHost.textContent = humanReason(payload?.block_reason || _policy?.block_reason);
  updateModeBadge(_currentContainer);
}

function liveBlockedState() {
  const requestedMode = currentMode();
  if (requestedMode !== 'live') return null;
  const blockReason = _policy?.block_reason;
  if (!blockReason) return null;
  return {
    requestedMode,
    effectiveMode: _policy?.effective_mode || 'paper',
    blockReason,
    nextActions: Array.isArray(_policy?.next_actions) ? _policy.next_actions : [],
  };
}

async function loadAccount(container) {
  if (!container?.isConnected) return;
  const broker = currentBroker(container);
  const mode = currentMode();
  try {
    const payload = await api.execution.account(broker, mode);
    if (!container?.isConnected) return;
    const account = payload.account || {};
    const warnings = payload.warnings || [];
    const clock = payload.market_clock || {};

    syncModeFields(payload);
    container.querySelector('#account-id').textContent = account.account_id || '--';
    container.querySelector('#account-clock').textContent = clock.is_open
      ? c('marketOpen')
      : (clock.next_open ? `${c('marketClosed')} / next ${shortTime(clock.next_open)}` : c('marketClosed'));
    container.querySelector('#account-warning-count').textContent = String(warnings.length);
    container.querySelector('#broker-status-note').textContent = payload.block_reason
      ? `${humanReason(payload.block_reason)} ${(payload.next_actions || []).map(humanNextAction).join(' / ')}`
      : (warnings[0] || c('note'));
    container.querySelector('#account-equity').textContent = fmtMoney(account.equity);
    container.querySelector('#account-buying-power').textContent = fmtMoney(account.buying_power);
    container.querySelector('#account-cash').textContent = fmtMoney(account.cash);
    container.querySelector('#account-daily-change').textContent = `${fmtSignedMoney(account.daily_change)} / ${fmtPct(account.daily_change_pct)}`;
    container.querySelector('#execution-clock').textContent = clock.is_open ? c('marketOpen') : c('marketClosed');
    container.querySelector('#session-pnl').textContent = fmtSignedMoney(account.daily_change);
    container.querySelector('#session-pnl').style.color = Number(account.daily_change || 0) >= 0 ? 'var(--green)' : 'var(--red)';
    container.querySelector('#btn-kill').disabled = !payload.connected;
    updateAccountPill(container, Boolean(payload.connected), payload.effective_mode || payload.mode || mode);
  } catch (error) {
    if (!container?.isConnected) return;
    renderAccountFallback(container, error.message || 'Could not load broker account.');
    toast.error(c('brokerStatus'), error.message || 'Unknown error');
  }
}

async function requestExecution(container) {
  const blocked = liveBlockedState();
  if (blocked) {
    toast.error(c('blockedTitle'), `${humanReason(blocked.blockReason)} ${blocked.nextActions.map(humanNextAction).join(' / ') || c('blockedHint')}`);
    return;
  }
  const mode = currentMode();
  const submitOrders = container.querySelector('#ex-submit').checked;
  if (mode === 'live' && submitOrders) {
    openLiveConfirm(container);
    return;
  }
  await submitExecution(container, false);
}

function openLiveConfirm(container) {
  const modal = container.querySelector('#live-confirm-modal');
  const capital = Number(container.querySelector('#ex-capital').value || 0);
  const universe = container.querySelector('#ex-universe').value.trim() || 'default universe';
  const body = container.querySelector('#live-confirm-body');
  body.innerHTML = `
    <div>${c('requestedMode')}: <strong>${humanMode(currentMode())}</strong></div>
    <div>${c('broker')}: <strong>${currentBroker(container)}</strong></div>
    <div>${c('universe')}: <strong>${universe}</strong></div>
    <div>${c('capital')}: <strong>${fmtMoney(capital)}</strong></div>
    <div>${c('blockReason')}: <strong>${humanReason(_policy?.block_reason)}</strong></div>
    <div style="color:var(--amber)">${c('liveConfirmTitle')}</div>
  `;
  modal.hidden = false;
}

function hideLiveConfirm() {
  _currentContainer?.querySelector('#live-confirm-modal')?.setAttribute('hidden', '');
}

async function submitExecution(container, liveConfirmed) {
  const blocked = liveBlockedState();
  if (blocked && !liveConfirmed) {
    toast.error(c('blockedTitle'), humanReason(blocked.blockReason));
    return;
  }

  const button = container.querySelector('#btn-run-exec');
  button.disabled = true;
  button.textContent = 'Submitting...';

  const universeInput = container.querySelector('#ex-universe').value.trim();
  const payload = {
    universe: universeInput ? universeInput.split(/[,\s]+/).filter(Boolean).map((value) => value.toUpperCase()) : [],
    capital_base: Number(container.querySelector('#ex-capital').value || 1000000),
    broker: currentBroker(container),
    mode: currentMode(),
    submit_orders: container.querySelector('#ex-submit').checked,
    allow_duplicates: true,
    live_confirmed: !!liveConfirmed,
    operator_confirmation: liveConfirmed ? 'front_end_live_confirm_modal' : '',
  };

  try {
    const response = await api.execution.paper(payload);
    syncModeFields(response);
    if (response.block_reason) {
      toast.error(c('blockedTitle'), `${humanReason(response.block_reason)} ${(response.next_actions || []).map(humanNextAction).join(' / ')}`);
    } else {
      toast.success(c('runPlan'), `${response.orders?.length || 0} orders staged`);
    }
    await loadRuntime(container);
    connectWS(container, response.execution_id);
  } catch (error) {
    toast.error(c('runPlan'), error.message || 'Unknown error');
  } finally {
    button.disabled = false;
    button.textContent = c('runPlan');
  }
}

async function loadOrders(container) {
  if (!container?.isConnected) return;
  const broker = currentBroker(container);
  const mode = currentMode();
  try {
    const data = await api.execution.orders(broker, 'all', 100, mode);
    if (!container?.isConnected) return;
    _orders = data.orders || [];
    syncModeFields(data);
    renderOrders(container);
  } catch (error) {
    if (!container?.isConnected) return;
    const body = container.querySelector('#orders-body');
    if (!body) return;
    body.innerHTML = `
      <div class="empty-state" style="min-height:120px">
        <div class="empty-state__title">${c('orderFeed')}</div>
        <div class="empty-state__text">${error.message || 'Unknown error'}</div>
      </div>
    `;
  }
}

function renderOrders(container) {
  if (!container?.isConnected) return;
  const body = container.querySelector('#orders-body');
  if (!body) return;
  const filter = container.querySelector('#filter-status')?.value || 'all';
  const filtered = filter === 'all' ? _orders : _orders.filter((item) => item.status === filter);
  const count = container.querySelector('#order-count');
  if (count) count.textContent = `${filtered.length} orders`;

  if (!filtered.length) {
    body.innerHTML = `
      <div class="empty-state" style="min-height:120px">
        <div class="empty-state__title">${c('noOrders')}</div>
        <div class="empty-state__text">${c('modeManaged')}</div>
      </div>
    `;
    return;
  }

  body.innerHTML = `
    <div class="tbl-wrap"><table>
      <thead>
        <tr><th>Symbol</th><th>Side</th><th>Qty</th><th>Status</th><th>Fill</th><th>Limit</th><th>Type</th><th>Time</th></tr>
      </thead>
      <tbody>
        ${filtered.map((order) => `
          <tr>
            <td class="cell-symbol">${order.symbol || '--'}</td>
            <td><span class="badge badge-${order.side === 'buy' ? 'long' : 'short'}">${String(order.side || '').toUpperCase()}</span></td>
            <td class="cell-num">${order.qty || order.quantity || '--'}</td>
            <td><span class="badge badge-${statusClass(order.status)}">${String(order.status || '').toUpperCase()}</span></td>
            <td class="cell-num">${order.fill_price ? fmtMoney(order.fill_price) : '--'}</td>
            <td class="cell-num">${order.limit_price ? fmtMoney(order.limit_price) : '--'}</td>
            <td class="text-dim text-sm">${order.order_type || order.type || '--'}</td>
            <td class="text-dim text-sm">${shortTime(order.submitted_at || order.created_at)}</td>
          </tr>
        `).join('')}
      </tbody>
    </table></div>
  `;
}

async function loadPositions(container) {
  if (!container?.isConnected) return;
  const broker = currentBroker(container);
  const mode = currentMode();
  const target = container.querySelector('#positions-body');
  if (!target) return;
  try {
    const payload = await api.execution.positions(broker, mode);
    if (!container?.isConnected || !target.isConnected) return;
    const positions = payload.positions || [];
    syncModeFields(payload);
    if (!positions.length) {
      target.innerHTML = `
        <div class="empty-state" style="min-height:100px">
          <div class="empty-state__title">${c('noPositions')}</div>
          <div class="empty-state__text">${c('modeManaged')}</div>
        </div>
      `;
      return;
    }
    target.innerHTML = `
      <div class="tbl-wrap"><table>
        <thead><tr><th>Symbol</th><th>Qty</th><th>Side</th><th>Market Value</th><th>P&L</th></tr></thead>
        <tbody>
          ${positions.map((position) => {
            const pnl = Number(position.unrealized_pl || 0);
            return `
              <tr>
                <td class="cell-symbol">${position.symbol || '--'}</td>
                <td>${position.qty || '--'}</td>
                <td>${position.side || 'long'}</td>
                <td>${position.market_value ? fmtMoney(position.market_value) : '--'}</td>
                <td class="${pnl >= 0 ? 'pos' : 'neg'}">${position.unrealized_pl ? fmtSignedMoney(position.unrealized_pl) : '--'}</td>
              </tr>
            `;
          }).join('')}
        </tbody>
      </table></div>
    `;
  } catch (error) {
    target.innerHTML = `
      <div class="empty-state" style="min-height:100px">
        <div class="empty-state__title">${c('positions')}</div>
        <div class="empty-state__text">${error.message || 'Unknown error'}</div>
      </div>
    `;
  }
}

function connectWS(container, executionId = null, overrideMode = null) {
  const broker = currentBroker(container);
  const mode = overrideMode || currentMode();
  const feedLog = container.querySelector('#feed-log');
  const status = container.querySelector('#feed-status');
  _ws?.close();

  _ws = openExecutionWS(broker, executionId, 20, (msg) => {
    if (status) status.textContent = 'live';
    if (feedLog) {
      const entry = document.createElement('div');
      const eventStatus = String(msg.status || '').toUpperCase();
      entry.style.cssText = 'padding:4px 0;border-bottom:1px solid rgba(255,255,255,0.03);font-family:var(--f-mono);font-size:11px';
      entry.innerHTML = `<span style="color:var(--text-dim)">${shortTime(msg.timestamp)}</span> <span>${msg.symbol || msg.type || '--'}</span> <span style="color:${eventStatus === 'FILLED' ? 'var(--green)' : eventStatus === 'FAILED' ? 'var(--red)' : 'var(--text-secondary)'}">${eventStatus || '--'}</span>`;
      feedLog.prepend(entry);
    }
  }, () => {
    if (status) status.textContent = 'event stream offline';
  }, mode);
}
