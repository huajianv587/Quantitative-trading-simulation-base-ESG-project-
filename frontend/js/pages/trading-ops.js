import { api } from '../qtapi.js?v=8';
import { toast } from '../components/toast.js?v=8';
import { getLang, onLangChange } from '../i18n.js?v=8';
import {
  emptyState,
  esc,
  metric,
  renderError,
  renderTokenPreview,
  setLoading,
  splitTokens,
  statusBadge,
} from './workbench-utils.js?v=8';

let _container = null;
let _langCleanup = null;
let _snapshot = null;
const OPS_SNAPSHOT_CACHE_KEY = 'qt.trading.ops.snapshot.v1';
const OPS_SNAPSHOT_CACHE_TTL_MS = 15 * 60 * 1000;

const COPY = {
  en: {
    title: 'Trading Ops',
    subtitle: 'Execution control room for schedule, monitor, watchlist, alerts, reviews, and mode-aware gatekeeping.',
    symbol: 'Symbol',
    universe: 'Universe',
    providers: 'Providers',
    refresh: 'Refresh Ops',
    addWatch: 'Add Watchlist',
    premarket: 'Run Premarket',
    autopilotToggle: 'Arm Autopilot',
    disarm: 'Disarm Autopilot',
    monitorStart: 'Start Monitor',
    monitorStop: 'Stop Monitor',
    cycle: 'Run One Cycle Now',
    schedule: 'Schedule + Monitor',
    watchlist: 'Watchlist',
    alerts: 'Today Alerts',
    review: 'Latest Review',
    loading: 'Loading trading ops...',
    running: 'Running execution cycle...',
    noWatchlist: 'No watchlist rows yet',
    noAlerts: 'No alerts today',
    noAlertsHint: 'Start the monitor or run one cycle to populate today alerts.',
    noReview: 'No review yet',
    noReviewHint: 'Premarket, midday, and review jobs will land here after the schedule runs.',
    requestedMode: 'Requested Mode',
    effectiveMode: 'Effective Mode',
    brokerReadiness: 'Broker Readiness',
    gateStatus: 'Gate Status',
    blockReason: 'Block Reason',
    nextAction: 'Next Action',
    watchCount: 'Watchlist Count',
    alertCount: 'Alerts',
    latestReviewCount: 'Latest Review',
    executionPath: 'Execution Path',
    pathHint: 'Submit only becomes executable when the selected mode is ready and all judge/risk gates pass.',
    lifecycle: 'Lifecycle + Guards',
    lifecycleHint: 'Paper is the active route. Live remains selectable, but stays blocked until the live account and live credentials are ready.',
    autoplay: 'Autopilot Preview',
    systemState: 'System State',
    notifier: 'Notifier',
    monitor: 'Monitor',
    latestRun: 'Latest Run',
    autoSubmit: 'Auto Submit',
    budgetGate: 'Budget Gate',
    strategySlot: 'Strategy Slot',
    allowedUniverse: 'Allowed Universe',
    killSwitch: 'Kill Switch',
    clear: 'clear',
    open: 'open',
    guarded: 'guarded',
    on: 'on',
    off: 'off',
    paperMode: 'Paper (Simulated)',
    liveMode: 'Live (Real)',
    uiOnly: 'ui-only',
    disabled: 'disabled',
    idle: 'idle',
    executionBlocked: 'Live mode is selected, but execution is still blocked.',
    executionBlockedHint: 'Switch back to Paper or finish live readiness before running execution actions.',
    noBlockReason: 'No blocking reason',
    pathScan: 'Scan',
    pathFactor: 'Factors',
    pathDebate: 'Debate',
    pathJudge: 'Judge',
    pathRisk: 'Risk',
    pathSubmit: 'Submit',
    pathMonitor: 'Monitor',
    pathReview: 'Review',
    statusReady: 'ready',
    statusPending: 'pending',
    statusPassed: 'passed',
    statusBlocked: 'blocked',
    statusStandby: 'standby',
    statusGuarded: 'guarded',
  },
  zh: {
    title: '交易运维',
    subtitle: '执行总控台：调度、监控、自选池、告警、复盘，以及与模式一致的执行门禁。',
    symbol: '股票',
    universe: '股票池',
    providers: '数据源',
    refresh: '刷新运维',
    addWatch: '加入自选池',
    premarket: '运行盘前',
    autopilotToggle: '武装自动驾驶',
    disarm: '解除自动驾驶',
    monitorStart: '启动监控',
    monitorStop: '停止监控',
    cycle: '运行一次闭环',
    schedule: '调度与监控',
    watchlist: '自选池',
    alerts: '今日告警',
    review: '最新复盘',
    loading: '正在加载交易运维...',
    running: '正在运行执行闭环...',
    noWatchlist: '暂无自选池条目',
    noAlerts: '今日暂无告警',
    noAlertsHint: '启动监控或运行一次闭环后，这里会出现真实告警。',
    noReview: '暂无复盘',
    noReviewHint: '盘前、盘中和日终复盘任务运行后，结果会展示在这里。',
    requestedMode: '当前选择模式',
    effectiveMode: '当前生效模式',
    brokerReadiness: 'Broker 就绪状态',
    gateStatus: '门禁状态',
    blockReason: '阻断原因',
    nextAction: '下一步动作',
    watchCount: '观察池数量',
    alertCount: '告警数量',
    latestReviewCount: '复盘状态',
    executionPath: '执行链路',
    pathHint: '只有当所选模式已就绪，且 Judge / Risk 门禁全部通过时，Submit 才会真正开放。',
    lifecycle: '生命周期与保护',
    lifecycleHint: '当前主路径仍是 Paper。Live 已经可见可选，但只有在 live account、live keys 与 broker readiness 就绪后才会真正执行。',
    autoplay: 'Autopilot 预览',
    systemState: '系统状态',
    notifier: '通知器',
    monitor: '监控',
    latestRun: '最近运行',
    autoSubmit: '自动提交',
    budgetGate: '预算门禁',
    strategySlot: '策略槽位',
    allowedUniverse: '允许股票池',
    killSwitch: '熔断总开关',
    clear: '清晰',
    open: '开放',
    guarded: '受保护',
    on: '开启',
    off: '关闭',
    paperMode: 'Paper（模拟）',
    liveMode: 'Live（实盘）',
    uiOnly: '仅界面',
    disabled: '关闭',
    idle: '空闲',
    executionBlocked: '当前已选择 Live，但执行仍然受门禁限制。',
    executionBlockedHint: '先切回 Paper 继续验证，或先完成 Live 凭证、账户与 broker readiness。',
    noBlockReason: '当前没有阻断原因',
    pathScan: '扫描',
    pathFactor: '因子',
    pathDebate: '辩论',
    pathJudge: '裁判',
    pathRisk: '风控',
    pathSubmit: '提交',
    pathMonitor: '监控',
    pathReview: '复盘',
    statusReady: '就绪',
    statusPending: '待处理',
    statusPassed: '已通过',
    statusBlocked: '已阻断',
    statusStandby: '待命',
    statusGuarded: '受保护',
  },
};

function c(key) {
  const lang = getLang() === 'zh' ? 'zh' : 'en';
  return COPY[lang][key] || COPY.en[key] || key;
}

function isMounted() {
  return Boolean(_container && _container.isConnected);
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
    paper_credentials_missing: isZh ? 'Paper 凭证未配置。' : 'Paper credentials are missing.',
    auto_submit_disabled: isZh ? '自动提交已关闭。' : 'Auto submit is disabled.',
    autopilot_disarmed: isZh ? '自动驾驶尚未武装。' : 'Autopilot is disarmed.',
    kill_switch_enabled: isZh ? '熔断总开关已开启。' : 'Kill switch is enabled.',
    judge_gate: isZh ? 'Judge 门禁' : 'Judge gate',
    risk_gate: isZh ? 'Risk 门禁' : 'Risk gate',
    budget_gate: isZh ? '预算门禁' : 'Budget gate',
    clear: c('noBlockReason'),
  };
  return map[normalized] || (value ? String(value) : c('noBlockReason'));
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
  };
  return map[normalized] || (value ? String(value) : c('noBlockReason'));
}

function runtimeLabel(value) {
  const normalized = String(value || '').trim().toLowerCase().replace(/[\s-]+/g, '_');
  const isZh = getLang() === 'zh';
  const map = {
    judge_gate: isZh ? 'Judge 门禁' : 'Judge gate',
    risk_gate: isZh ? 'Risk 门禁' : 'Risk gate',
    daily_budget: isZh ? '每日预算' : 'Daily budget',
    kill_switch: isZh ? '熔断开关' : 'Kill switch',
    duplicate_order_guard: isZh ? '重复订单保护' : 'Duplicate order guard',
    stale_signal_guard: isZh ? '过期信号保护' : 'Stale signal guard',
    drawdown_guard: isZh ? '回撤保护' : 'Drawdown guard',
    notifier_guard: isZh ? '通知保护' : 'Notifier guard',
    no_strategy_slot: isZh ? '暂无策略槽位' : 'No strategy slot',
    no_factor_dependencies: isZh ? '暂无因子依赖' : 'No factor dependencies',
    no_active_strategy_slot: isZh ? '没有激活的策略槽位' : 'No active strategy slot',
    symbol_outside_allowed_universe: isZh ? '标的不在允许股票池' : 'Symbol outside allowlist',
    feature_build: isZh ? '特征构建' : 'Feature build',
    factor_gate: isZh ? '因子门禁' : 'Factor gate',
    strategy_slot: isZh ? '策略槽位' : 'Strategy slot',
    paper_shadow_notify: isZh ? '影子通知' : 'Shadow notify',
    shadow_notify: isZh ? '影子通知' : 'Shadow notify',
    submit: isZh ? '提交' : 'Submit',
    clear: c('clear'),
  };
  return map[normalized] || normalized.replace(/_/g, ' ').trim() || '-';
}

function pathStatusLabel(value) {
  const normalized = String(value || '').trim().toLowerCase();
  const map = {
    ready: c('statusReady'),
    pending: c('statusPending'),
    passed: c('statusPassed'),
    blocked: c('statusBlocked'),
    standby: c('statusStandby'),
    guarded: c('statusGuarded'),
    configured: c('statusReady'),
    approve: getLang() === 'zh' ? '批准' : 'approve',
    reduce: getLang() === 'zh' ? '缩减' : 'reduce',
    reject: getLang() === 'zh' ? '拒绝' : 'reject',
    halt: getLang() === 'zh' ? '暂停' : 'halt',
    running: getLang() === 'zh' ? '运行中' : 'running',
    review: getLang() === 'zh' ? '待复核' : 'review',
  };
  return map[normalized] || String(value || '-');
}

function onOff(value) {
  return value ? c('on') : c('off');
}

function symbol() {
  return String(_container?.querySelector('#ops-symbol')?.value || 'AAPL').trim().toUpperCase();
}

function universe() {
  return splitTokens(_container?.querySelector('#ops-universe')?.value || symbol(), { uppercase: true, delimiters: /[,\s]+/ });
}

function providers() {
  return splitTokens(_container?.querySelector('#ops-providers')?.value || '', { delimiters: /[,|\s]+/ });
}

export async function render(container) {
  _container = container;
  renderShell();
  wire();
  renderPreviews();
  hydrateSnapshotFromCache();
  if (_snapshot) {
    renderSnapshot();
  } else {
    renderBootstrapState();
  }
  _langCleanup = onLangChange(() => {
    if (!_container?.isConnected) return;
    renderShell();
    wire();
    renderPreviews();
    if (_snapshot) renderSnapshot();
    else renderBootstrapState();
  });
  await refreshOps();
}

export function destroy() {
  _container = null;
  _snapshot = null;
  _langCleanup?.();
  _langCleanup = null;
}

function renderShell() {
  if (!_container) return;
  _container.innerHTML = `
    <div class="workbench-page trading-ops-page" data-no-autotranslate="true">
      <section class="run-panel">
        <div class="run-panel__header">
          <div class="run-panel__title">${c('title')}</div>
          <div class="run-panel__sub">${c('subtitle')}</div>
        </div>
        <div class="run-panel__body">
          <div class="grid-3 compact-control-grid live-control-grid">
            <label class="field field--with-preview">
              <span>${c('symbol')}</span>
              <input id="ops-symbol" value="AAPL">
              <div id="ops-symbol-preview"></div>
            </label>
            <label class="field field--with-preview">
              <span>${c('universe')}</span>
              <input id="ops-universe" value="AAPL, NVDA, TSLA, SPY">
              <div id="ops-universe-preview"></div>
            </label>
            <label class="field field--with-preview">
              <span>${c('providers')}</span>
              <input id="ops-providers" value="local_esg, sec_edgar, alpaca_market">
              <div id="ops-provider-preview"></div>
            </label>
          </div>
        </div>
        <div class="run-panel__foot workbench-action-grid">
          <button class="btn workbench-action-btn workbench-action-btn--primary" id="btn-trading-ops-refresh">${c('refresh')}</button>
          <button class="btn workbench-action-btn workbench-action-btn--secondary" id="btn-watchlist-add">${c('addWatch')}</button>
          <button class="btn workbench-action-btn workbench-action-btn--secondary" id="btn-run-premarket">${c('premarket')}</button>
          <button class="btn workbench-action-btn workbench-action-btn--secondary" id="btn-autopilot-toggle">${c('autopilotToggle')}</button>
          <button class="btn workbench-action-btn workbench-action-btn--secondary" id="btn-monitor-start">${c('monitorStart')}</button>
          <button class="btn workbench-action-btn workbench-action-btn--secondary" id="btn-monitor-stop">${c('monitorStop')}</button>
          <button class="btn workbench-action-btn workbench-action-btn--primary" id="btn-trading-cycle">${c('cycle')}</button>
        </div>
      </section>

      <section class="trading-ops-kpi-grid" id="ops-kpi">${renderBootstrapKpis()}</section>

      <section class="grid-2 workbench-main-grid trading-ops-grid">
        <article class="card">
          <div class="card-header"><span class="card-title">${c('schedule')}</span></div>
          <div class="card-body" id="ops-schedule">${renderBootstrapPanel()}</div>
        </article>
        <article class="card">
          <div class="card-header"><span class="card-title">${c('alerts')}</span></div>
          <div class="card-body" id="ops-alerts">${renderBootstrapPanel()}</div>
        </article>
        <article class="card">
          <div class="card-header"><span class="card-title">${c('watchlist')}</span></div>
          <div class="card-body" id="ops-watchlist">${renderBootstrapPanel()}</div>
        </article>
        <article class="card">
          <div class="card-header"><span class="card-title">${c('review')}</span></div>
          <div class="card-body" id="ops-review">${renderBootstrapPanel()}</div>
        </article>
      </section>
    </div>
  `;
}

function wire() {
  _container.querySelector('#btn-trading-ops-refresh')?.addEventListener('click', refreshOps);
  _container.querySelector('#btn-watchlist-add')?.addEventListener('click', addWatchlistSymbol);
  _container.querySelector('#btn-run-premarket')?.addEventListener('click', () => runJob('premarket_agent'));
  _container.querySelector('#btn-autopilot-toggle')?.addEventListener('click', toggleAutopilot);
  _container.querySelector('#btn-monitor-start')?.addEventListener('click', async () => {
    await api.trading.monitorStart();
    await refreshOps();
  });
  _container.querySelector('#btn-monitor-stop')?.addEventListener('click', async () => {
    await api.trading.monitorStop();
    await refreshOps();
  });
  _container.querySelector('#btn-trading-cycle')?.addEventListener('click', runTradingCycle);
  ['#ops-symbol', '#ops-universe', '#ops-providers'].forEach((selector) => {
    _container.querySelector(selector)?.addEventListener('input', renderPreviews);
  });
}

function renderPreviews() {
  if (!isMounted()) return;
  const symbolHost = _container?.querySelector('#ops-symbol-preview');
  const universeHost = _container?.querySelector('#ops-universe-preview');
  const providerHost = _container?.querySelector('#ops-provider-preview');
  if (symbolHost) symbolHost.innerHTML = renderTokenPreview([symbol()], { tone: 'accent', maxItems: 1 });
  if (universeHost) universeHost.innerHTML = renderTokenPreview(universe(), { tone: 'accent', maxItems: 6 });
  if (providerHost) providerHost.innerHTML = renderTokenPreview(providers(), { tone: 'neutral', maxItems: 6 });
}

async function refreshOps() {
  if (!isMounted()) return;
  const hadSnapshot = Boolean(_snapshot);
  if (!hadSnapshot) {
    renderBootstrapState();
  }
  setRefreshState(true);
  try {
    _snapshot = await api.trading.opsSnapshot();
    if (!isMounted()) return;
    persistSnapshot(_snapshot);
    renderSnapshot();
  } catch (err) {
    if (!isMounted()) return;
    if (!hadSnapshot) {
      ['#ops-kpi', '#ops-schedule', '#ops-watchlist', '#ops-alerts', '#ops-review'].forEach((selector) => {
        const host = _container?.querySelector(selector);
        if (host) renderError(host, err);
      });
    } else {
      toast.error(c('refresh'), err.message || '');
    }
  } finally {
    setRefreshState(false);
  }
}

async function addWatchlistSymbol() {
  try {
    await api.trading.watchlistAdd({ symbol: symbol(), note: 'ui_watchlist_add', enabled: true });
    await refreshOps();
  } catch (err) {
    const host = _container?.querySelector('#ops-watchlist');
    if (host) renderError(host, err);
  }
}

function renderBootstrapState() {
  if (!_container) return;
  _container.querySelector('#ops-kpi').innerHTML = renderBootstrapKpis();
  ['#ops-schedule', '#ops-watchlist', '#ops-alerts', '#ops-review'].forEach((selector) => {
    const host = _container.querySelector(selector);
    if (host) host.innerHTML = renderBootstrapPanel();
  });
}

function renderBootstrapKpis() {
  return `
    ${metric(c('requestedMode'), '--')}
    ${metric(c('effectiveMode'), '--')}
    ${metric(c('brokerReadiness'), '--')}
    ${metric(c('gateStatus'), '--')}
    ${metric(c('watchCount'), '--')}
    ${metric(c('alertCount'), '--')}
    ${metric(c('latestReviewCount'), '--')}
  `;
}

function renderBootstrapPanel() {
  const detail = getLang() === 'zh'
    ? '顶部控制区已经就绪，详细运行状态正在后台刷新。'
    : 'Top controls are ready. Detailed runtime status is refreshing in the background.';
  return emptyState(c('loading'), detail);
}

function hydrateSnapshotFromCache() {
  try {
    const raw = localStorage.getItem(OPS_SNAPSHOT_CACHE_KEY);
    if (!raw) return;
    const parsed = JSON.parse(raw);
    if (!parsed?.payload || !parsed?.saved_at) return;
    if ((Date.now() - Number(parsed.saved_at)) > OPS_SNAPSHOT_CACHE_TTL_MS) return;
    _snapshot = parsed.payload;
  } catch {
    _snapshot = null;
  }
}

function persistSnapshot(snapshot) {
  try {
    localStorage.setItem(OPS_SNAPSHOT_CACHE_KEY, JSON.stringify({
      saved_at: Date.now(),
      payload: snapshot,
    }));
  } catch {
    // Ignore storage failures in private contexts.
  }
}

function setRefreshState(refreshing) {
  const refreshButton = _container?.querySelector('#btn-trading-ops-refresh');
  if (refreshButton) {
    refreshButton.disabled = refreshing;
  }
}

function isLiveBlocked() {
  const policy = _snapshot?.autopilot_policy || {};
  return String(policy.requested_mode || policy.execution_mode || '').toLowerCase() === 'live'
    && Boolean(policy.block_reason);
}

async function runJob(jobName) {
  if (!isMounted()) return;
  const scheduleHost = _container?.querySelector('#ops-schedule');
  try {
    if (scheduleHost) setLoading(scheduleHost, c('loading'));
    await api.trading.jobRun(jobName, {});
    await refreshOps();
  } catch (err) {
    if (scheduleHost) renderError(scheduleHost, err);
  }
}

async function runTradingCycle() {
  const alertsHost = _container?.querySelector('#ops-alerts');
  const policy = _snapshot?.autopilot_policy || {};
  if (isLiveBlocked()) {
    toast.error(c('executionBlocked'), humanReason(policy.block_reason));
    return;
  }
  if (alertsHost) setLoading(alertsHost, c('running'));
  try {
    await api.trading.cycleRun({
      symbol: symbol(),
      universe: universe(),
      query: 'Run the full scan -> factors -> debate -> judge -> risk -> submit cycle.',
      mode: 'mixed',
      providers: providers(),
      quota_guard: true,
      auto_submit: true,
    });
    await refreshOps();
  } catch (err) {
    if (alertsHost) renderError(alertsHost, err);
  }
}

async function toggleAutopilot() {
  const policy = _snapshot?.autopilot_policy || {};
  const armed = Boolean(policy.armed);
  if (!armed && isLiveBlocked()) {
    toast.error(c('executionBlocked'), humanReason(policy.block_reason));
    return;
  }
  try {
    if (armed) {
      await api.trading.autopilotDisarm({ armed: false });
    } else {
      await api.trading.autopilotArm({ armed: true });
    }
    toast.success(armed ? c('disarm') : c('autopilotToggle'));
    await refreshOps();
  } catch (err) {
    const host = _container?.querySelector('#ops-schedule');
    if (host) renderError(host, err);
  }
}

function renderSnapshot() {
  if (!_snapshot || !isMounted()) return;
  const schedule = _snapshot.schedule || {};
  const jobs = Array.isArray(schedule.jobs) ? schedule.jobs : [];
  const monitor = _snapshot.monitor || {};
  const watchlist = _snapshot.watchlist?.watchlist || [];
  const alerts = _snapshot.today_alerts?.alerts || [];
  const review = _snapshot.latest_review?.review || null;
  const debates = _snapshot.debates?.debates || [];
  const latestApproval = _snapshot.risk?.latest_approval || null;
  const notifier = _snapshot.notifier || {};
  const policy = _snapshot.autopilot_policy || {};
  const executionPath = _snapshot.execution_path || {};
  const factorPipeline = _snapshot.factor_pipeline || {};
  const strategiesPayload = _snapshot.strategies || {};
  const strategies = Array.isArray(strategiesPayload.strategies) ? strategiesPayload.strategies : [];
  const activeStrategies = strategies.filter((item) => String(item.status || '').toLowerCase() === 'active');
  const requestedMode = policy.requested_mode || policy.execution_mode || executionPath.requested_mode || executionPath.mode || 'paper';
  const effectiveMode = policy.effective_mode || executionPath.effective_mode || executionPath.mode || 'paper';
  const blockReason = policy.block_reason || executionPath.block_reason || '';
  const nextActions = Array.isArray(policy.next_actions) && policy.next_actions.length
    ? policy.next_actions
    : (Array.isArray(executionPath.next_actions) ? executionPath.next_actions : []);
  const brokerReady = requestedMode === 'live' ? Boolean(policy.live_ready) : Boolean(policy.paper_ready);
  const gateStatus = blockReason ? c('guarded') : c('open');
  const strategySlotSummary = activeStrategies.map((item) => item.strategy_id || item.title).join(' / ') || '-';
  const stageLookup = new Map((executionPath.stages || []).map((item) => [item.stage, item.status]));
  const toggleButton = _container?.querySelector('#btn-autopilot-toggle');
  if (toggleButton) {
    toggleButton.textContent = policy.armed ? c('disarm') : c('autopilotToggle');
  }

  const kpiHost = _container?.querySelector('#ops-kpi');
  const scheduleHost = _container?.querySelector('#ops-schedule');
  const watchlistHost = _container?.querySelector('#ops-watchlist');
  const alertsHost = _container?.querySelector('#ops-alerts');
  const reviewHost = _container?.querySelector('#ops-review');
  if (!kpiHost || !scheduleHost || !watchlistHost || !alertsHost || !reviewHost) return;

  kpiHost.innerHTML = `
    ${metric(c('requestedMode'), humanMode(requestedMode))}
    ${metric(c('effectiveMode'), humanMode(effectiveMode), effectiveMode === 'live' ? 'risk' : 'positive')}
    ${metric(c('brokerReadiness'), brokerReady ? c('statusReady') : c('statusBlocked'), brokerReady ? 'positive' : 'risk')}
    ${metric(c('gateStatus'), gateStatus, blockReason ? 'risk' : 'positive')}
    ${metric(c('watchCount'), watchlist.length || 0, watchlist.length ? 'positive' : 'risk')}
    ${metric(c('alertCount'), alerts.length || 0, alerts.length ? 'risk' : 'positive')}
    ${metric(c('latestReviewCount'), review ? c('clear') : c('statusPending'), review ? 'positive' : 'risk')}
  `;

  scheduleHost.innerHTML = `
    <div class="workbench-metric-grid">
      ${metric(c('requestedMode'), humanMode(requestedMode))}
      ${metric(c('effectiveMode'), humanMode(effectiveMode), effectiveMode === 'live' ? 'risk' : 'positive')}
      ${metric(c('brokerReadiness'), brokerReady ? c('statusReady') : c('statusBlocked'), brokerReady ? 'positive' : 'risk')}
      ${metric(c('gateStatus'), gateStatus, blockReason ? 'risk' : 'positive')}
      ${metric(c('monitor'), monitor.running ? (monitor.stream_mode || 'running') : c('idle'), monitor.running ? 'positive' : 'risk')}
      ${metric(c('latestRun'), monitor.last_event_at || '-', monitor.last_event_at ? '' : 'risk')}
    </div>

    <section class="workbench-section">
      <div class="workbench-section__title">${c('executionPath')}</div>
      <p class="workbench-section__hint">${c('pathHint')}</p>
      <div class="ops-timeline-grid">
        ${timelineStep(c('pathScan'), stageLookup.get('scan') || 'pending')}
        ${timelineStep(c('pathFactor'), stageLookup.get('factors') || 'pending')}
        ${timelineStep(c('pathDebate'), stageLookup.get('debate') || 'review')}
        ${timelineStep(c('pathJudge'), stageLookup.get('judge') || (executionPath.judge_passed ? 'passed' : 'review'))}
        ${timelineStep(c('pathRisk'), stageLookup.get('risk') || (latestApproval?.verdict || 'review'))}
        ${timelineStep(c('pathSubmit'), stageLookup.get('submit') || gateStatus)}
        ${timelineStep(c('pathMonitor'), stageLookup.get('monitor') || (monitor.running ? 'running' : 'standby'))}
        ${timelineStep(c('pathReview'), stageLookup.get('review') || (review ? 'configured' : 'review'))}
      </div>
    </section>

    <section class="workbench-section">
      <div class="workbench-section__title">${c('lifecycle')}</div>
      <p class="workbench-section__hint">${c('lifecycleHint')}</p>
      <div class="workbench-kv-list compact-kv-list">
        <div class="workbench-kv-row"><span>${c('requestedMode')}</span><strong>${esc(humanMode(requestedMode))}</strong></div>
        <div class="workbench-kv-row"><span>${c('effectiveMode')}</span><strong>${esc(humanMode(effectiveMode))}</strong></div>
        <div class="workbench-kv-row"><span>${c('blockReason')}</span><strong>${esc(humanReason(blockReason))}</strong></div>
        <div class="workbench-kv-row"><span>${c('nextAction')}</span><strong>${esc(nextActions.map(humanNextAction).join(' / ') || c('clear'))}</strong></div>
        <div class="workbench-kv-row"><span>${c('monitor')}</span><strong>${esc(monitor.stream_mode || c('idle'))}</strong></div>
        <div class="workbench-kv-row"><span>${c('notifier')}</span><strong>${esc(notifier.telegram_configured ? 'telegram' : c('uiOnly'))}</strong></div>
      </div>
      <div class="token-preview">
        ${(policy.protections || ['judge_gate', 'risk_gate']).map((item) => `
          <span class="token-chip token-chip--accent">${esc(runtimeLabel(item))}</span>
        `).join('')}
      </div>
    </section>

    <section class="workbench-section">
      <div class="workbench-section__title">${c('autoplay')}</div>
      <div class="workbench-kv-list compact-kv-list">
        <div class="workbench-kv-row"><span>${c('autoSubmit')}</span><strong>${esc(autoSubmitLabel(policy))}</strong></div>
        <div class="workbench-kv-row"><span>${c('budgetGate')}</span><strong>${esc(gateStatus)}</strong></div>
        <div class="workbench-kv-row"><span>${c('strategySlot')}</span><strong>${esc(strategySlotSummary)}</strong></div>
        <div class="workbench-kv-row"><span>${c('allowedUniverse')}</span><strong>${esc((policy.allowed_universe || watchlist.map((item) => item.symbol)).join(', ') || '-')}</strong></div>
        <div class="workbench-kv-row"><span>${c('killSwitch')}</span><strong>${esc(onOff(policy.kill_switch))}</strong></div>
        <div class="workbench-kv-row"><span>${c('nextAction')}</span><strong>${esc(nextActions.map(humanNextAction).join(' / ') || c('clear'))}</strong></div>
      </div>
    </section>

    <section class="workbench-section">
      <div class="workbench-section__title">${c('systemState')}</div>
      <div class="factor-checklist">
        ${guardRow(c('brokerReadiness'), brokerReady ? 'is-pass' : 'is-watch', brokerReady ? c('statusReady') : humanReason(blockReason))}
        ${guardRow(c('monitor'), monitor.running ? 'is-pass' : 'is-watch', monitor.running ? (monitor.stream_mode || c('on')) : c('off'))}
        ${guardRow(c('blockReason'), blockReason ? 'is-watch' : 'is-pass', humanReason(blockReason))}
        ${guardRow(c('nextAction'), nextActions.length ? 'is-watch' : 'is-pass', nextActions.map(humanNextAction).join(' / ') || c('clear'))}
        ${guardRow(c('notifier'), notifier.telegram_configured ? 'is-pass' : 'is-watch', notifier.telegram_configured ? 'telegram' : c('uiOnly'))}
      </div>
    </section>
  `;

  watchlistHost.innerHTML = watchlist.length ? `
    <div class="workbench-list workbench-scroll-list ops-watchlist-scroll">
      ${watchlist.map((item) => `
        <article class="workbench-item">
          <div class="workbench-item__head">
            <strong>${esc(item.symbol)}</strong>
            ${statusBadge(item.enabled ? 'configured' : 'rejected')}
          </div>
          <p>${esc(item.note || 'watchlist entry')}</p>
          <div class="workbench-item__meta">
            <span>esg=${esc(item.esg_score ?? '-')}</span>
            <span>sent=${esc(item.last_sentiment ?? '-')}</span>
            <span>${esc(item.enabled ? c('on') : c('off'))}</span>
          </div>
        </article>
      `).join('')}
    </div>` : emptyState(c('noWatchlist'));

  alertsHost.innerHTML = alerts.length ? `
    <div class="workbench-list workbench-scroll-list ops-alerts-scroll">
      ${alerts.map((item) => `
        <article class="workbench-item">
          <div class="workbench-item__head">
            <strong>${esc(item.symbol)} | ${esc(item.trigger_type)}</strong>
            ${statusBadge(item.risk_decision || 'watch')}
          </div>
          <p>${esc(item.agent_analysis || '')}</p>
          <div class="workbench-item__meta">
            <span>${esc(item.timestamp || '')}</span>
            <span>risk=${esc(pathStatusLabel(item.risk_decision || '-'))}</span>
            <span>exec=${esc(item.execution_id || '-')}</span>
          </div>
        </article>
      `).join('')}
    </div>` : emptyState(c('noAlerts'), c('noAlertsHint'));

  reviewHost.innerHTML = review ? `
    <div class="workbench-metric-grid">
      ${metric(c('alertCount'), alerts.length || 0, alerts.length ? 'risk' : 'positive')}
      ${metric(c('watchCount'), watchlist.length || 0, watchlist.length ? 'positive' : 'risk')}
      ${metric(c('gateStatus'), gateStatus, blockReason ? 'risk' : 'positive')}
      ${metric(c('latestRun'), review.review_id || '-', review.review_id ? 'positive' : 'risk')}
    </div>
    <div class="workbench-report-text">${esc(review.report_text || '')}</div>
    <div class="factor-checklist">
      ${((review.next_day_risk_flags || []).length ? review.next_day_risk_flags : [c('clear')]).map((flag) => `
        <div class="factor-check-row"><span>${esc(flag)}</span><strong class="${flag === c('clear') ? 'is-pass' : 'is-watch'}">${flag === c('clear') ? c('clear') : c('nextAction')}</strong></div>
      `).join('')}
    </div>
  ` : emptyState(c('noReview'), c('noReviewHint'));
}

function autoSubmitLabel(policy) {
  if (policy.block_reason) return c('guarded');
  if (policy.armed && (policy.auto_submit_enabled || policy.paper_auto_submit_enabled)) return c('open');
  if (policy.auto_submit_enabled || policy.paper_auto_submit_enabled) return c('statusStandby');
  return c('disabled');
}

function timelineStep(label, status) {
  return `<div class="preview-step"><span>${esc(label)}</span><strong>${esc(pathStatusLabel(status))}</strong></div>`;
}

function guardRow(label, klass, value) {
  return `<div class="factor-check-row"><span>${esc(label)}</span><strong class="${klass}">${esc(value)}</strong></div>`;
}
