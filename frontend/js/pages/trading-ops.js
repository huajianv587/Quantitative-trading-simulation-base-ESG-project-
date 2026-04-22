import { api } from '../qtapi.js?v=8';
import { toast } from '../components/toast.js?v=8';
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
    subtitle: 'Execution control room for schedule, monitor, watchlist, alerts, reviews, and budget gates.',
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
    monitor: 'Monitor',
    jobs: 'Jobs',
    paperMode: 'Execution Mode',
    budgetGate: 'Budget Gate',
    autoSubmit: 'Auto Submit',
    watchEnabled: 'enabled',
    watchDisabled: 'disabled',
    nextDay: 'next day',
    clear: 'clear',
    debateBridge: 'Debate Bridge',
    riskBridge: 'Risk Gate',
    nextJob: 'Next Job',
    status: 'Status',
    armed: 'Armed',
    stream: 'Stream',
    latestRun: 'Latest Run',
    notifier: 'Notifier',
    monitorHealth: 'Monitor Health',
    watchCount: 'Watchlist Count',
    alertCount: 'Alerts',
    latestReviewCount: 'Latest Review',
    pnl: 'PnL',
    trades: 'Trades',
    approved: 'Approved',
    blocked: 'Blocked',
    executionPath: 'Execution Path',
    pathHint: 'Every automatic submission still passes through debate and risk approval.',
    lifecycle: 'Bot Lifecycle + Protections + Notifier',
    lifecycleHint: 'Freqtrade-style protections stay visible here, while the runtime remains judge/risk gated and broker-aware.',
    autoplay: 'Autopilot Preview',
    systemState: 'System State',
    strategyMix: 'Strategy Mix',
    approvalLedger: 'Approval Ledger',
    factorPipeline: 'Factor Pipeline',
    factorDeps: 'Factor Dependencies',
    pipelineWarnings: 'Pipeline Warnings',
    fusionManifest: 'Fusion Reference',
    intentContract: 'ExecutionIntent',
    resultContract: 'ExecutionResult',
    budgetCap: 'Daily Budget Cap',
    tradeCap: 'Per-Trade Cap',
    maxWeight: 'Max Symbol Weight',
    allowedUniverse: 'Allowed Universe',
    strategies: 'Strategy Slot',
    killSwitch: '熔断总开关',
    dailyLoss: 'Daily Loss Limit',
    drawdown: 'Drawdown Limit',
    ttl: 'Signal TTL',
    degradeBroker: 'Broker not configured',
    degradeMonitor: 'Monitor idle',
    degradeSchedule: 'Schedule waiting',
    degradeReview: 'Review not generated yet',
    degradeFallback: 'Storage fallback active',
    pathScan: 'Scan',
    pathFactor: 'Factors',
    pathDebate: 'Debate',
    pathJudge: 'Judge',
    pathRisk: 'Risk',
    pathSubmit: 'Submit',
    pathMonitor: 'Monitor',
    pathReview: 'Review',
    on: 'on',
    off: 'off',
    configured: 'configured',
    paper: 'paper',
    live: 'live',
    uiOnly: 'ui-only',
    watchlistEntry: 'watchlist entry',
    open: 'open',
    guarded: 'guarded',
    nextAction: 'Next Action',
  },
  zh: {
    title: '交易运维',
    subtitle: '执行总控台：调度、监控、自选池、告警、复盘与预算门禁。',
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
    noAlertsHint: '启动监控或运行一次闭环后，这里会出现实时告警。',
    noReview: '暂无复盘',
    noReviewHint: '盘前、盘中和日终复盘任务运行后，结果会展示在这里。',
    monitor: '监控',
    jobs: '任务数',
    paperMode: '执行模式',
    budgetGate: '预算门禁',
    autoSubmit: '自动下单',
    watchEnabled: '已启用',
    watchDisabled: '已停用',
    nextDay: '次日关注',
    clear: '清晰',
    debateBridge: '辩论桥接',
    riskBridge: '风控门禁',
    nextJob: '下一任务',
    status: '状态',
    armed: '已武装',
    stream: '流模式',
    latestRun: '最近运行',
    notifier: '通知器',
    monitorHealth: '监控健康',
    watchCount: '观察池数量',
    alertCount: '告警数',
    latestReviewCount: '复盘状态',
    pnl: '盈亏',
    trades: '成交笔数',
    approved: '已批准',
    blocked: '已阻断',
    executionPath: '执行链路',
    pathHint: '任何自动提交都仍需经过 Debate 与 Risk Manager 双重审批。',
    lifecycle: 'Bot 生命周期 / 保护 / 通知',
    lifecycleHint: '这里会显式展示 freqtrade 风格 protections，运行时继续经过 judge/risk 双门禁，并受券商就绪状态约束。',
    autoplay: 'Autopilot 预览',
    systemState: '系统状态',
    strategyMix: '策略组合',
    approvalLedger: '审批台账',
    factorPipeline: '因子流水线',
    factorDeps: '因子依赖',
    pipelineWarnings: '流水线警告',
    fusionManifest: '融合参考清单',
    intentContract: 'ExecutionIntent',
    resultContract: 'ExecutionResult',
    budgetCap: '每日预算上限',
    tradeCap: '单笔上限',
    maxWeight: '单票权重上限',
    allowedUniverse: '允许股票池',
    strategies: '策略槽位',
    killSwitch: 'Kill Switch',
    dailyLoss: '单日亏损上限',
    drawdown: '回撤上限',
    ttl: '信号 TTL',
    degradeBroker: '券商尚未配置',
    degradeMonitor: '监控尚未启动',
    degradeSchedule: '调度尚未运行',
    degradeReview: '复盘尚未生成',
    degradeFallback: '已切换到降级存储',
    pathScan: '扫描',
    pathFactor: '因子',
    pathDebate: '辩论',
    pathJudge: '裁判',
    pathRisk: '风控',
    pathSubmit: '提交',
    pathMonitor: '盯盘',
    pathReview: '复盘',
    on: '开启',
    off: '关闭',
    configured: '已配置',
    paper: '纸面',
    live: '实盘',
    uiOnly: '仅界面',
    watchlistEntry: '自选池条目',
    open: '开放',
    guarded: '受保护',
    nextAction: '下一步动作',
  },
};

function c(key) {
  const lang = getLang() === 'zh' ? 'zh' : 'en';
  return COPY[lang][key] || COPY.en[key] || key;
}

function autoSubmitEnabled(policy = _snapshot?.autopilot_policy || {}) {
  return Boolean(policy?.auto_submit_enabled || policy?.paper_auto_submit_enabled);
}

function onOff(value) {
  return value ? c('on') : c('off');
}

function runtimeLabel(value) {
  const normalized = String(value || '').trim().toLowerCase().replace(/[\s-]+/g, '_');
  if (normalized === 'auto_submit_disabled') {
    return getLang() === 'zh' ? '自动提交关闭' : 'Auto submit disabled';
  }
  const map = {
    judge_gate: getLang() === 'zh' ? 'Judge 门禁' : 'Judge gate',
    risk_gate: getLang() === 'zh' ? 'Risk 门禁' : 'Risk gate',
    daily_budget: getLang() === 'zh' ? '日预算保护' : 'Daily budget',
    kill_switch: getLang() === 'zh' ? '总开关' : 'Kill switch',
    duplicate_order_guard: getLang() === 'zh' ? '重复订单保护' : 'Duplicate order guard',
    stale_signal_guard: getLang() === 'zh' ? '过期信号保护' : 'Stale signal guard',
    drawdown_guard: getLang() === 'zh' ? '回撤保护' : 'Drawdown guard',
    notifier_guard: getLang() === 'zh' ? '通知保护' : 'Notifier guard',
    no_strategy_slot: getLang() === 'zh' ? '暂无策略槽位' : 'No strategy slot',
    no_factor_dependencies: getLang() === 'zh' ? '暂无因子依赖' : 'No factor dependencies',
    no_active_strategy_slot: getLang() === 'zh' ? '没有激活的策略槽位' : 'No active strategy slot',
    symbol_outside_allowed_universe: getLang() === 'zh' ? '标的不在允许股票池' : 'Symbol outside allowlist',
    feature_build: getLang() === 'zh' ? '特征构建' : 'Feature build',
    factor_gate: getLang() === 'zh' ? '因子门禁' : 'Factor gate',
    strategy_slot: getLang() === 'zh' ? '策略槽位' : 'Strategy slot',
    paper_shadow_notify: getLang() === 'zh' ? '影子通知' : 'shadow notify',
    shadow_notify: getLang() === 'zh' ? '影子通知' : 'shadow notify',
    submit: getLang() === 'zh' ? '提交' : 'Submit',
    clear: c('clear'),
  };
  return map[normalized] || normalized.replace(/_/g, ' ').trim() || '-';
}

function verdictLabel(value) {
  const normalized = String(value || '').trim().toLowerCase();
  const map = {
    approve: getLang() === 'zh' ? '批准' : 'approve',
    reduce: getLang() === 'zh' ? '缩减' : 'reduce',
    reject: getLang() === 'zh' ? '拒绝' : 'reject',
    halt: getLang() === 'zh' ? '暂停' : 'halt',
    configured: c('configured'),
    guarded: getLang() === 'zh' ? '已守护' : 'guarded',
    running: getLang() === 'zh' ? '运行中' : 'running',
    logged: getLang() === 'zh' ? '已记录' : 'logged',
    review: getLang() === 'zh' ? '待复核' : 'review',
    paper: c('paper'),
  };
  return map[normalized] || String(value || '-');
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
              <input id="ops-providers" value="local_esg, marketaux, twelvedata">
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
    </div>`;
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

function symbol() {
  return String(_container.querySelector('#ops-symbol')?.value || 'AAPL').trim().toUpperCase();
}

function universe() {
  return splitTokens(_container.querySelector('#ops-universe')?.value || symbol(), { uppercase: true, delimiters: /[,\s]+/ });
}

function providers() {
  return splitTokens(_container.querySelector('#ops-providers')?.value || '', { delimiters: /[,|\s]+/ });
}

function renderPreviews() {
  _container.querySelector('#ops-symbol-preview').innerHTML = renderTokenPreview([symbol()], { tone: 'accent', maxItems: 1 });
  _container.querySelector('#ops-universe-preview').innerHTML = renderTokenPreview(universe(), { tone: 'accent', maxItems: 6 });
  _container.querySelector('#ops-provider-preview').innerHTML = renderTokenPreview(providers(), { tone: 'neutral', maxItems: 6 });
}

async function refreshOps() {
  const hadSnapshot = Boolean(_snapshot);
  if (!hadSnapshot) {
    renderBootstrapState();
  }
  setRefreshState(true);
  try {
    _snapshot = await api.trading.opsSnapshot();
    persistSnapshot(_snapshot);
    renderSnapshot();
  } catch (err) {
    if (!hadSnapshot) {
      ['#ops-kpi', '#ops-schedule', '#ops-watchlist', '#ops-alerts', '#ops-review'].forEach((selector) => {
        renderError(_container.querySelector(selector), err);
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
    renderError(_container.querySelector('#ops-watchlist'), err);
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
    ${metric(c('paperMode'), '--')}
    ${metric(c('nextJob'), '--')}
    ${metric(c('monitorHealth'), '--')}
    ${metric(c('watchCount'), '--')}
    ${metric(c('alertCount'), '--')}
    ${metric(c('latestReviewCount'), '--')}
    ${metric(c('budgetGate'), '--')}
  `;
}

function renderBootstrapPanelLegacy() {
  const detail = getLang() === 'zh'
    ? '顶部控制区已就绪，详细状态正在后台刷新。'
    : 'Top controls are ready. Detailed runtime status is refreshing in the background.';
  return emptyState(c('loading'), detail);
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
    // Ignore storage failures on private/incognito contexts.
  }
}

function setRefreshState(refreshing) {
  const refreshButton = _container?.querySelector('#btn-trading-ops-refresh');
  if (refreshButton) {
    refreshButton.disabled = refreshing;
    refreshButton.classList.toggle('is-busy', refreshing);
  }
  const cycleButton = _container?.querySelector('#btn-trading-cycle');
  if (cycleButton) {
    cycleButton.disabled = refreshing;
    cycleButton.classList.toggle('is-busy', refreshing);
  }
}

async function runJob(jobName) {
  try {
    await api.trading.jobRun(jobName, {});
    await refreshOps();
  } catch (err) {
    renderError(_container.querySelector('#ops-schedule'), err);
  }
}

async function runTradingCycle() {
  setLoading(_container.querySelector('#ops-alerts'), c('running'));
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
    renderError(_container.querySelector('#ops-alerts'), err);
  }
}

async function toggleAutopilot() {
  const armed = Boolean(_snapshot?.autopilot_policy?.armed);
  try {
    if (armed) {
      await api.trading.autopilotDisarm({ armed: false });
    } else {
      await api.trading.autopilotArm({ armed: true });
    }
    toast.success(armed ? c('disarm') : c('autopilotToggle'));
    await refreshOps();
  } catch (err) {
    renderError(_container.querySelector('#ops-schedule'), err);
  }
}

function renderSnapshot() {
  if (!_snapshot) return;
  const schedule = _snapshot.schedule || {};
  const jobs = Array.isArray(schedule.jobs) ? schedule.jobs : [];
  const monitor = _snapshot.monitor || {};
  const watchlist = _snapshot.watchlist?.watchlist || [];
  const alerts = _snapshot.today_alerts?.alerts || [];
  const review = _snapshot.latest_review?.review || null;
  const debates = _snapshot.debates?.debates || [];
  const debateCount = Number(_snapshot.debates?.count || debates.length || 0);
  const riskApprovals = _snapshot.risk?.approvals || [];
  const latestApproval = _snapshot.risk?.latest_approval || riskApprovals[0] || null;
  const notifier = _snapshot.notifier || {};
  const policy = _snapshot.autopilot_policy || {};
  const executionPath = _snapshot.execution_path || {};
  const factorPipeline = _snapshot.factor_pipeline || {};
  const fusionManifest = _snapshot.fusion_manifest || {};
  const strategiesPayload = _snapshot.strategies || {};
  const strategies = Array.isArray(strategiesPayload.strategies) ? strategiesPayload.strategies : [];
  const fusionItems = Array.isArray(fusionManifest.items) ? fusionManifest.items : [];
  const executionIntentContract = fusionManifest.execution_intent_contract || {};
  const executionResultContract = fusionManifest.execution_result_contract || {};
  const activeStrategies = strategies.filter((item) => {
    const strategyActive = String(item.status || '').toLowerCase() === 'active';
    const allocation = item.allocation || {};
    const allocationActive = !allocation.status || String(allocation.status || '').toLowerCase() === 'active';
    return strategyActive && allocationActive;
  });
  const allowedStrategies = Array.isArray(policy.allowed_strategies) ? policy.allowed_strategies : [];
  const pipelineWarnings = Array.isArray(factorPipeline.warnings) ? factorPipeline.warnings : [];
  const pipelineStages = Array.isArray(factorPipeline.stages) && factorPipeline.stages.length
    ? factorPipeline.stages
    : [
        { stage: 'feature_build', status: 'ready' },
        { stage: 'factor_gate', status: debateCount ? 'ready' : 'review' },
        { stage: 'strategy_slot', status: (activeStrategies.length || allowedStrategies.length) ? 'ready' : 'guarded' },
      ];
  const factorDependencies = Array.isArray(factorPipeline.factor_dependencies) ? factorPipeline.factor_dependencies : [];
  const activeStrategyIds = activeStrategies.map((item) => item.strategy_id);
  const strategySlotSummary = (activeStrategies.length ? activeStrategyIds : allowedStrategies).join(' / ') || '-';
  const pipelineSlotSummary = (Array.isArray(factorPipeline.strategy_slots) ? factorPipeline.strategy_slots : activeStrategyIds).join(' / ') || strategySlotSummary;
  const lifecycleProtections = Array.isArray(policy.protections) ? policy.protections : [];
  const runtimeMode = executionPath.mode || policy.execution_mode || monitor.mode || 'paper';
  const policyReady = Boolean(
    (policy.execution_permission === 'auto_submit' || policy.execution_permission === 'paper_auto_submit')
      && autoSubmitEnabled(policy)
      && policy.armed
      && !policy.kill_switch
  );
  const budgetGateState = policyReady && executionPath.current_stage !== 'blocked' ? c('open') : c('guarded');
  const nextJob = jobs[0] || null;
  const stageLookup = new Map((executionPath.stages || []).map((item) => [item.stage, item.status]));
  const paperArmed = Boolean(policy.armed);
  const autopilotWarnings = Array.isArray(policy.warnings) ? policy.warnings : [];
  const pathWarnings = Array.isArray(executionPath.warnings) ? executionPath.warnings : [];
  const watchlistSymbols = watchlist.map((item) => item.symbol).join(', ');
  const pipelineNextAction = factorPipeline.next_action || (
    getLang() === 'zh'
      ? '先确认活跃策略槽位、因子依赖与 Judge/Risk 双门禁都已对齐。'
      : 'Align strategy slots, factor dependencies, and both gates before promotion.'
  );
  const toggleButton = _container.querySelector('#btn-autopilot-toggle');
  if (toggleButton) {
    toggleButton.textContent = paperArmed ? c('disarm') : c('autopilotToggle');
  }

  _container.querySelector('#ops-kpi').innerHTML = `
    ${metric(c('paperMode'), runtimeMode === 'live' ? c('live') : c('paper'), 'positive')}
    ${metric(c('nextJob'), nextJob?.job_name || '-', nextJob ? '' : 'risk')}
    ${metric(c('monitorHealth'), monitor.running ? onOff(true) : onOff(false), monitor.running ? 'positive' : 'risk')}
    ${metric(c('watchCount'), watchlist.length || 0, watchlist.length ? 'positive' : 'risk')}
    ${metric(c('alertCount'), alerts.length, alerts.length ? 'risk' : 'positive')}
    ${metric(c('latestReviewCount'), review ? c('clear') : c('degradeReview'), review ? 'positive' : 'risk')}
    ${metric(c('budgetGate'), budgetGateState, policyReady ? 'positive' : 'risk')}
  `;

  _container.querySelector('#ops-schedule').innerHTML = `
    <div class="workbench-metric-grid">
      ${metric(c('jobs'), jobs.length || 0, 'positive')}
      ${metric(c('monitor'), monitor.running ? onOff(true) : onOff(false), monitor.running ? 'positive' : 'risk')}
      ${metric(c('stream'), monitor.stream_mode || 'idle')}
      ${metric(c('notifier'), notifier.telegram_configured ? 'telegram' : c('uiOnly'))}
      ${metric(c('latestRun'), monitor.last_event_at || '-', monitor.last_event_at ? '' : 'risk')}
      ${metric(c('autoSubmit'), policyReady ? c('armed') : c('guarded'), policyReady ? 'positive' : 'risk')}
    </div>
    <section class="workbench-section">
      <div class="workbench-section__title">${c('executionPath')}</div>
      <p class="workbench-section__hint">${c('pathHint')}</p>
      <div class="ops-timeline-grid">
        ${timelineStep(c('pathScan'), stageLookup.get('scan') || 'review')}
        ${timelineStep(c('pathFactor'), stageLookup.get('factors') || 'review')}
        ${timelineStep(c('pathDebate'), stageLookup.get('debate') || (debateCount ? 'configured' : 'review'))}
        ${timelineStep(c('pathJudge'), executionPath.judge_passed ? 'approve' : 'review')}
        ${timelineStep(c('pathRisk'), stageLookup.get('risk') || (latestApproval ? latestApproval.verdict : 'review'))}
        ${timelineStep(c('pathSubmit'), stageLookup.get('submit') || stageLookup.get('paper_submit') || (policyReady ? 'approve' : 'guarded'))}
        ${timelineStep(c('pathMonitor'), stageLookup.get('monitor') || (monitor.running ? 'running' : 'review'))}
        ${timelineStep(c('pathReview'), stageLookup.get('review') || (review ? 'configured' : 'review'))}
      </div>
    </section>
    <section class="workbench-section">
      <div class="workbench-section__title">${c('lifecycle')}</div>
      <p class="workbench-section__hint">${c('lifecycleHint')}</p>
      <div class="workbench-kv-list compact-kv-list">
        <div class="workbench-kv-row"><span>${c('autopilotToggle')}</span><strong>${paperArmed ? c('armed') : verdictLabel('review')}</strong></div>
        <div class="workbench-kv-row"><span>${c('cycle')}</span><strong>${esc(executionPath.current_stage || monitor.last_event_at || '-')}</strong></div>
        <div class="workbench-kv-row"><span>${c('budgetGate')}</span><strong>${esc(budgetGateState)}</strong></div>
        <div class="workbench-kv-row"><span>${c('strategies')}</span><strong>${esc(strategySlotSummary)}</strong></div>
        <div class="workbench-kv-row"><span>${c('executionPath')}</span><strong>${esc((executionPath.lineage || ['scan', 'factors', 'debate', 'judge', 'risk', 'submit', 'monitor', 'review']).join(' -> '))}</strong></div>
        <div class="workbench-kv-row"><span>${c('systemState')}</span><strong>${esc(_snapshot.degraded ? c('degradeFallback') : c('clear'))}</strong></div>
      </div>
      <div class="token-preview">
        ${(lifecycleProtections.length ? lifecycleProtections : ['judge_gate', 'risk_gate']).map((item) => `
          <span class="token-chip token-chip--accent">${esc(runtimeLabel(item))}</span>
        `).join('')}
      </div>
      <div class="factor-checklist">
        ${guardRow(c('notifier'), notifier.telegram_configured ? 'is-pass' : 'is-watch', notifier.telegram_configured ? 'telegram' : runtimeLabel(notifier.mode || 'shadow_notify'))}
        ${guardRow(c('monitor'), monitor.running ? 'is-pass' : 'is-watch', monitor.running ? onOff(true) : onOff(false))}
        ${guardRow(c('degradeFallback'), _snapshot.degraded ? 'is-watch' : 'is-pass', _snapshot.degraded ? c('degradeFallback') : c('clear'))}
      </div>
    </section>
    <section class="workbench-section">
      <div class="workbench-section__title">${c('autoplay')}</div>
      <div class="workbench-kv-list compact-kv-list">
        <div class="workbench-kv-row"><span>${c('budgetCap')}</span><strong>$${Number(policy.daily_budget_cap || 0).toLocaleString()}</strong></div>
        <div class="workbench-kv-row"><span>${c('tradeCap')}</span><strong>$${Number(policy.per_trade_cap || 0).toLocaleString()}</strong></div>
        <div class="workbench-kv-row"><span>${c('maxWeight')}</span><strong>${pct(policy.max_symbol_weight || latestApproval?.max_position_weight || 0)}</strong></div>
        <div class="workbench-kv-row"><span>${c('allowedUniverse')}</span><strong>${esc((policy.allowed_universe || []).join(', ') || watchlistSymbols || universe().join(', '))}</strong></div>
        <div class="workbench-kv-row"><span>${c('strategies')}</span><strong>${esc(strategySlotSummary)}</strong></div>
        <div class="workbench-kv-row"><span>${c('killSwitch')}</span><strong>${onOff(policy.kill_switch)}</strong></div>
        <div class="workbench-kv-row"><span>${c('dailyLoss')}</span><strong>$${Number(policy.daily_loss_limit || 0).toLocaleString()}</strong></div>
        <div class="workbench-kv-row"><span>${c('drawdown')}</span><strong>${pct(policy.drawdown_limit || 0)}</strong></div>
        <div class="workbench-kv-row"><span>${c('ttl')}</span><strong>${policy.signal_ttl || latestApproval?.signal_ttl_minutes || 180}m</strong></div>
        <div class="workbench-kv-row"><span>${c('strategyMix')}</span><strong>${esc(activeStrategyIds.join(' / ') || '-')}</strong></div>
        <div class="workbench-kv-row"><span>${c('approvalLedger')}</span><strong>${latestApproval?.approval_id || '-'}</strong></div>
      </div>
    </section>
    <section class="workbench-section">
      <div class="workbench-section__title">${c('factorPipeline')}</div>
      <div class="preview-step-grid">
        ${pipelineStages.map((item) => `
          <div class="preview-step">
            <span>${esc(runtimeLabel(item.stage))}</span>
            <strong>${esc(pathStatusLabel(item.status || 'review'))}</strong>
          </div>
        `).join('')}
      </div>
      <div class="workbench-kv-list compact-kv-list">
        <div class="workbench-kv-row"><span>${c('strategies')}</span><strong>${esc(pipelineSlotSummary)}</strong></div>
        <div class="workbench-kv-row"><span>${c('factorDeps')}</span><strong>${esc(factorDependencies.join(', ') || '-')}</strong></div>
        <div class="workbench-kv-row"><span>${c('pipelineWarnings')}</span><strong>${esc(pipelineWarnings.map(runtimeLabel).join(' | ') || c('clear'))}</strong></div>
        <div class="workbench-kv-row"><span>${c('nextAction')}</span><strong>${esc(pipelineNextAction)}</strong></div>
      </div>
    </section>
    <section class="workbench-section">
      <div class="workbench-section__title">${c('systemState')}</div>
      <div class="factor-checklist">
        ${guardRow(c('degradeBroker'), runtimeMode ? 'is-pass' : 'is-watch', runtimeMode ? (runtimeMode === 'live' ? c('live') : c('paper')) : c('degradeBroker'))}
        ${guardRow(c('degradeMonitor'), monitor.running ? 'is-pass' : 'is-watch', monitor.running ? onOff(true) : onOff(false))}
        ${guardRow(c('degradeSchedule'), jobs.length ? 'is-pass' : 'is-watch', jobs.length ? jobs[0].schedule : c('degradeSchedule'))}
        ${guardRow(c('degradeReview'), review ? 'is-pass' : 'is-watch', review ? c('clear') : c('degradeReview'))}
        ${guardRow(c('notifier'), notifier.telegram_configured ? 'is-pass' : 'is-watch', notifier.telegram_configured ? 'telegram' : c('uiOnly'))}
        ${guardRow(c('degradeFallback'), _snapshot.degraded ? 'is-watch' : 'is-pass', _snapshot.degraded ? c('degradeFallback') : c('clear'))}
        ${(autopilotWarnings.length ? autopilotWarnings : ['clear']).map((warning) => guardRow(`policy:${runtimeLabel(warning)}`, warning === 'clear' ? 'is-pass' : 'is-watch', warning === 'clear' ? c('clear') : runtimeLabel(warning))).join('')}
        ${(pathWarnings.length ? pathWarnings : []).map((warning) => guardRow(`path:${runtimeLabel(warning)}`, 'is-watch', runtimeLabel(warning))).join('')}
      </div>
    </section>
    <section class="workbench-section">
      <div class="workbench-section__title">${c('fusionManifest')}</div>
      <div class="workbench-kv-list compact-kv-list">
        <div class="workbench-kv-row"><span>${c('intentContract')}</span><strong>${esc(executionIntentContract.intent_id ? `${executionIntentContract.requested_action || '-'} / ttl ${executionIntentContract.signal_ttl_minutes || '-'}` : '-')}</strong></div>
        <div class="workbench-kv-row"><span>${c('resultContract')}</span><strong>${esc(executionResultContract.status || '-')}</strong></div>
        <div class="workbench-kv-row"><span>${c('nextAction')}</span><strong>${esc(fusionItems[0]?.notes || pipelineNextAction)}</strong></div>
      </div>
      <div class="workbench-list">
        ${fusionItems.slice(0, 3).map((item) => `
          <article class="workbench-item">
            <div class="workbench-item__head">
              <strong>${esc(item.source_project)} / ${esc(item.capability)}</strong>
              ${statusBadge(item.status || 'watch')}
            </div>
            <p>${esc(item.target_surface || '-')}</p>
            <div class="workbench-item__meta">
              <span>${esc(item.notes || '-')}</span>
            </div>
          </article>
        `).join('') || emptyState(c('loading'))}
      </div>
    </section>
  `;

  _container.querySelector('#ops-watchlist').innerHTML = watchlist.length ? `
    <div class="workbench-metric-grid">
      ${metric(c('watchlist'), watchlist.length, 'positive')}
      ${metric(c('debateBridge'), debateCount)}
      ${metric(c('riskBridge'), riskApprovals.length)}
      ${metric(c('status'), policyReady ? c('armed') : c('guarded'), policyReady ? 'positive' : 'risk')}
    </div>
    <div class="workbench-list workbench-scroll-list ops-watchlist-scroll">
      ${watchlist.map((item) => `
        <article class="workbench-item">
          <div class="workbench-item__head">
            <strong>${esc(item.symbol)}</strong>
            ${statusBadge(item.enabled ? 'configured' : 'rejected')}
          </div>
          <p>${esc(item.note || c('watchlistEntry'))}</p>
          <div class="workbench-item__meta">
            <span>esg=${esc(item.esg_score ?? '-')}</span>
            <span>sent=${esc(item.last_sentiment ?? '-')}</span>
            <span>${esc(item.enabled ? c('watchEnabled') : c('watchDisabled'))}</span>
          </div>
        </article>
      `).join('')}
    </div>` : emptyState(c('noWatchlist'));

  _container.querySelector('#ops-alerts').innerHTML = alerts.length ? `
    <div class="workbench-metric-grid">
      ${metric(c('alertCount'), alerts.length, 'risk')}
      ${metric(c('debateBridge'), debateCount)}
      ${metric(c('riskBridge'), latestApproval ? verdictLabel(latestApproval.verdict) : '-')}
      ${metric(c('monitorHealth'), monitor.running ? onOff(true) : onOff(false), monitor.running ? 'positive' : 'risk')}
    </div>
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
            <span>${c('riskBridge')}=${esc(verdictLabel(item.risk_decision || '-'))}</span>
            <span>exec=${esc(item.execution_id || '-')}</span>
          </div>
        </article>
      `).join('')}
    </div>` : emptyState(c('noAlerts'), c('noAlertsHint'));

  _container.querySelector('#ops-review').innerHTML = review ? `
    <div class="workbench-metric-grid">
      ${metric(c('pnl'), esc(review.pnl ?? '-'), Number(review.pnl || 0) >= 0 ? 'positive' : 'risk')}
      ${metric(c('trades'), review.trades_count || 0)}
      ${metric(c('approved'), review.approved_decisions || 0, 'positive')}
      ${metric(c('blocked'), review.blocked_decisions || 0, 'risk')}
    </div>
    <div class="workbench-report-text">${esc(review.report_text || '')}</div>
    <div class="factor-checklist">
      ${(review.next_day_risk_flags || []).map((flag) => `
        <div class="factor-check-row"><span>${esc(flag)}</span><strong class="is-watch">${c('nextDay')}</strong></div>
      `).join('') || guardRow(c('review'), 'is-pass', c('clear'))}
    </div>
    <div class="workbench-kv-list compact-kv-list">
      <div class="workbench-kv-row"><span>${c('notifier')}</span><strong>${notifier.telegram_configured ? 'telegram' : c('uiOnly')}</strong></div>
      <div class="workbench-kv-row"><span>${c('latestRun')}</span><strong>${esc(review.review_id || '-')}</strong></div>
      <div class="workbench-kv-row"><span>${c('budgetGate')}</span><strong>${latestApproval ? verdictLabel(latestApproval.verdict) : '-'}</strong></div>
      <div class="workbench-kv-row"><span>${c('degradeFallback')}</span><strong>${_snapshot.degraded ? onOff(true) : onOff(false)}</strong></div>
    </div>
  ` : emptyState(c('noReview'), c('noReviewHint'));
}

function timelineStep(label, status) {
  return `<div class="preview-step"><span>${esc(label)}</span><strong>${esc(pathStatusLabel(status))}</strong></div>`;
}

function guardRow(label, klass, value) {
  return `<div class="factor-check-row"><span>${esc(label)}</span><strong class="${klass}">${esc(value)}</strong></div>`;
}

function pathStatusLabel(value) {
  const normalized = String(value || '').trim().toLowerCase();
  const map = {
    ready: getLang() === 'zh' ? '就绪' : 'ready',
    pending: getLang() === 'zh' ? '待处理' : 'pending',
    passed: getLang() === 'zh' ? '已通过' : 'passed',
    blocked: getLang() === 'zh' ? '已阻断' : 'blocked',
    standby: getLang() === 'zh' ? '待命' : 'standby',
    guarded: getLang() === 'zh' ? '受保护' : 'guarded',
  };
  return map[normalized] || verdictLabel(normalized);
}
