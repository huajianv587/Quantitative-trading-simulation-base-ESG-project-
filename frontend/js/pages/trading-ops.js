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
  splitTokens,
  statusBadge,
} from './workbench-utils.js?v=8';

let _container = null;
let _langCleanup = null;
let _snapshot = null;

const COPY = {
  en: {
    title: 'Trading Ops',
    subtitle: 'Paper auto-submit control room for schedule, monitor, watchlist, alerts, reviews, and budget gates.',
    symbol: 'Symbol',
    universe: 'Universe',
    providers: 'Providers',
    refresh: 'Refresh Ops',
    addWatch: 'Add Watchlist',
    premarket: 'Run Premarket',
    monitorStart: 'Start Monitor',
    monitorStop: 'Stop Monitor',
    cycle: 'Run Trading Cycle',
    schedule: 'Schedule + Monitor',
    watchlist: 'Watchlist',
    alerts: 'Today Alerts',
    review: 'Latest Review',
    loading: 'Loading trading ops...',
    running: 'Running paper trading cycle...',
    noWatchlist: 'No watchlist rows yet',
    noAlerts: 'No alerts today',
    noAlertsHint: 'Start the monitor or run the paper cycle to populate today alerts.',
    noReview: 'No review yet',
    noReviewHint: 'Premarket, midday, and review jobs will land here after the schedule runs.',
    monitor: 'Monitor',
    jobs: 'Jobs',
    paperMode: 'Paper Mode',
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
    pathHint: 'Every automatic paper submission still passes through debate and risk approval.',
    autoplay: 'Autopilot Preview',
    systemState: 'System State',
    strategyMix: 'Strategy Mix',
    approvalLedger: 'Approval Ledger',
    budgetCap: 'Daily Budget Cap',
    tradeCap: 'Per-Trade Cap',
    maxWeight: 'Max Symbol Weight',
    allowedUniverse: 'Allowed Universe',
    strategies: 'Strategy Slot',
    killSwitch: 'Kill Switch',
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
    pathSubmit: 'Paper Submit',
    pathMonitor: 'Monitor',
    pathReview: 'Review',
    on: 'on',
    off: 'off',
    configured: 'configured',
    paper: 'paper',
    uiOnly: 'ui-only',
    watchlistEntry: 'watchlist entry',
  },
  zh: {
    title: '交易运维',
    subtitle: 'Paper Auto-Submit 交易总控台：调度、监控、自选池、告警、复盘与预算门禁。',
    symbol: '股票',
    universe: '股票池',
    providers: '数据源',
    refresh: '刷新运维',
    addWatch: '加入自选池',
    premarket: '运行盘前',
    monitorStart: '启动监控',
    monitorStop: '停止监控',
    cycle: '运行交易闭环',
    schedule: '调度与监控',
    watchlist: '自选池',
    alerts: '今日告警',
    review: '最新复盘',
    loading: '正在加载交易运维...',
    running: '正在运行纸面交易闭环...',
    noWatchlist: '暂无自选池条目',
    noAlerts: '今日暂无告警',
    noAlertsHint: '启动监控或运行一次纸面交易闭环后，这里会出现实时告警。',
    noReview: '暂无复盘',
    noReviewHint: '盘前、盘中和日终复盘任务运行后，结果会展示在这里。',
    monitor: '监控',
    jobs: '任务数',
    paperMode: '纸面模式',
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
    pathHint: '任何自动纸面提交都仍需经过 Debate 与 Risk Manager 双重审批。',
    autoplay: 'Autopilot 预览',
    systemState: '系统状态',
    strategyMix: '策略组合',
    approvalLedger: '审批台账',
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
    pathSubmit: '纸面提交',
    pathMonitor: '盯盘',
    pathReview: '复盘',
    on: '开启',
    off: '关闭',
    configured: '已配置',
    paper: '纸面',
    uiOnly: '仅界面',
    watchlistEntry: '自选池条目',
  },
};

function c(key) {
  const lang = getLang() === 'zh' ? 'zh' : 'en';
  return COPY[lang][key] || COPY.en[key] || key;
}

function onOff(value) {
  return value ? c('on') : c('off');
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
  _langCleanup = onLangChange(() => {
    if (!_container?.isConnected) return;
    renderShell();
    wire();
    renderPreviews();
    renderSnapshot();
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
          <button class="btn btn-primary workbench-action-btn" id="btn-trading-ops-refresh">${c('refresh')}</button>
          <button class="btn btn-ghost workbench-action-btn" id="btn-watchlist-add">${c('addWatch')}</button>
          <button class="btn btn-ghost workbench-action-btn" id="btn-run-premarket">${c('premarket')}</button>
          <button class="btn btn-ghost workbench-action-btn" id="btn-monitor-start">${c('monitorStart')}</button>
          <button class="btn btn-ghost workbench-action-btn" id="btn-monitor-stop">${c('monitorStop')}</button>
          <button class="btn btn-primary workbench-action-btn" id="btn-trading-cycle">${c('cycle')}</button>
        </div>
      </section>

      <section class="trading-ops-kpi-grid" id="ops-kpi">${emptyState(c('loading'))}</section>

      <section class="grid-2 workbench-main-grid trading-ops-grid">
        <article class="card">
          <div class="card-header"><span class="card-title">${c('schedule')}</span></div>
          <div class="card-body" id="ops-schedule">${emptyState(c('loading'))}</div>
        </article>
        <article class="card">
          <div class="card-header"><span class="card-title">${c('alerts')}</span></div>
          <div class="card-body" id="ops-alerts">${emptyState(c('loading'))}</div>
        </article>
        <article class="card">
          <div class="card-header"><span class="card-title">${c('watchlist')}</span></div>
          <div class="card-body" id="ops-watchlist">${emptyState(c('loading'))}</div>
        </article>
        <article class="card">
          <div class="card-header"><span class="card-title">${c('review')}</span></div>
          <div class="card-body" id="ops-review">${emptyState(c('loading'))}</div>
        </article>
      </section>
    </div>`;
}

function wire() {
  _container.querySelector('#btn-trading-ops-refresh')?.addEventListener('click', refreshOps);
  _container.querySelector('#btn-watchlist-add')?.addEventListener('click', addWatchlistSymbol);
  _container.querySelector('#btn-run-premarket')?.addEventListener('click', () => runJob('premarket_agent'));
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
  ['#ops-kpi', '#ops-schedule', '#ops-watchlist', '#ops-alerts', '#ops-review'].forEach((selector) => {
    setLoading(_container.querySelector(selector), c('loading'));
  });
  try {
    _snapshot = await api.trading.opsSnapshot();
    renderSnapshot();
  } catch (err) {
    ['#ops-kpi', '#ops-schedule', '#ops-watchlist', '#ops-alerts', '#ops-review'].forEach((selector) => {
      renderError(_container.querySelector(selector), err);
    });
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
      query: 'Run the full scan -> debate -> risk -> paper cycle.',
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
  const nextJob = jobs[0] || null;
  const paperArmed = latestApproval?.verdict === 'approve';

  _container.querySelector('#ops-kpi').innerHTML = `
    ${metric(c('paperMode'), monitor.mode || c('paper'), 'positive')}
    ${metric(c('nextJob'), nextJob?.job_name || '-', nextJob ? '' : 'risk')}
    ${metric(c('monitorHealth'), monitor.running ? onOff(true) : onOff(false), monitor.running ? 'positive' : 'risk')}
    ${metric(c('watchCount'), watchlist.length || 0, watchlist.length ? 'positive' : 'risk')}
    ${metric(c('alertCount'), alerts.length, alerts.length ? 'risk' : 'positive')}
    ${metric(c('latestReviewCount'), review ? c('clear') : c('degradeReview'), review ? 'positive' : 'risk')}
    ${metric(c('budgetGate'), verdictLabel(latestApproval?.verdict || 'review'), paperArmed ? 'positive' : 'risk')}
  `;

  _container.querySelector('#ops-schedule').innerHTML = `
    <div class="workbench-metric-grid">
      ${metric(c('jobs'), jobs.length || 0, 'positive')}
      ${metric(c('monitor'), monitor.running ? onOff(true) : onOff(false), monitor.running ? 'positive' : 'risk')}
      ${metric(c('stream'), monitor.stream_mode || 'idle')}
      ${metric(c('notifier'), notifier.telegram_configured ? 'telegram' : c('uiOnly'))}
      ${metric(c('latestRun'), monitor.last_event_at || '-', monitor.last_event_at ? '' : 'risk')}
      ${metric(c('autoSubmit'), paperArmed ? c('armed') : c('riskBridge'), paperArmed ? 'positive' : 'risk')}
    </div>
    <section class="workbench-section">
      <div class="workbench-section__title">${c('executionPath')}</div>
      <p class="workbench-section__hint">${c('pathHint')}</p>
      <div class="ops-timeline-grid">
        ${timelineStep(c('pathScan'), 'configured')}
        ${timelineStep(c('pathFactor'), 'configured')}
        ${timelineStep(c('pathDebate'), debateCount ? 'configured' : 'review')}
        ${timelineStep(c('pathJudge'), debateCount ? 'configured' : 'review')}
        ${timelineStep(c('pathRisk'), latestApproval ? latestApproval.verdict : 'review')}
        ${timelineStep(c('pathSubmit'), paperArmed ? 'approve' : 'guarded')}
        ${timelineStep(c('pathMonitor'), monitor.running ? 'running' : 'review')}
        ${timelineStep(c('pathReview'), review ? 'configured' : 'review')}
      </div>
    </section>
    <section class="workbench-section">
      <div class="workbench-section__title">${c('autoplay')}</div>
      <div class="workbench-kv-list compact-kv-list">
        <div class="workbench-kv-row"><span>${c('budgetCap')}</span><strong>$10,000</strong></div>
        <div class="workbench-kv-row"><span>${c('tradeCap')}</span><strong>$2,500</strong></div>
        <div class="workbench-kv-row"><span>${c('maxWeight')}</span><strong>${pct(latestApproval?.max_position_weight || 0.26)}</strong></div>
        <div class="workbench-kv-row"><span>${c('allowedUniverse')}</span><strong>${esc(universe().join(', '))}</strong></div>
        <div class="workbench-kv-row"><span>${c('strategies')}</span><strong>multi-factor / debate / ESG overlay</strong></div>
        <div class="workbench-kv-row"><span>${c('killSwitch')}</span><strong>${monitor.mode === 'paper' ? onOff(false) : onOff(true)}</strong></div>
        <div class="workbench-kv-row"><span>${c('dailyLoss')}</span><strong>-2.50%</strong></div>
        <div class="workbench-kv-row"><span>${c('drawdown')}</span><strong>-6.00%</strong></div>
        <div class="workbench-kv-row"><span>${c('ttl')}</span><strong>${latestApproval?.signal_ttl_minutes || 180}m</strong></div>
        <div class="workbench-kv-row"><span>${c('strategyMix')}</span><strong>multi-factor / debate / ESG overlay</strong></div>
        <div class="workbench-kv-row"><span>${c('approvalLedger')}</span><strong>${latestApproval?.approval_id || '-'}</strong></div>
      </div>
    </section>
    <section class="workbench-section">
      <div class="workbench-section__title">${c('systemState')}</div>
      <div class="factor-checklist">
        ${guardRow(c('degradeBroker'), monitor.mode === 'paper' ? 'is-pass' : 'is-watch', monitor.mode === 'paper' ? verdictLabel('configured') : c('degradeBroker'))}
        ${guardRow(c('degradeMonitor'), monitor.running ? 'is-pass' : 'is-watch', monitor.running ? onOff(true) : onOff(false))}
        ${guardRow(c('degradeSchedule'), jobs.length ? 'is-pass' : 'is-watch', jobs.length ? jobs[0].schedule : c('degradeSchedule'))}
        ${guardRow(c('degradeReview'), review ? 'is-pass' : 'is-watch', review ? c('clear') : c('degradeReview'))}
        ${guardRow(c('notifier'), notifier.telegram_configured ? 'is-pass' : 'is-watch', notifier.telegram_configured ? 'telegram' : c('uiOnly'))}
        ${guardRow(c('degradeFallback'), _snapshot.degraded ? 'is-watch' : 'is-pass', _snapshot.degraded ? c('degradeFallback') : c('clear'))}
      </div>
    </section>
  `;

  _container.querySelector('#ops-watchlist').innerHTML = watchlist.length ? `
    <div class="workbench-metric-grid">
      ${metric(c('watchlist'), watchlist.length, 'positive')}
      ${metric(c('debateBridge'), debateCount)}
      ${metric(c('riskBridge'), riskApprovals.length)}
      ${metric(c('status'), paperArmed ? c('armed') : c('riskBridge'), paperArmed ? 'positive' : 'risk')}
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
  return `<div class="preview-step"><span>${esc(label)}</span><strong>${esc(verdictLabel(status))}</strong></div>`;
}

function guardRow(label, klass, value) {
  return `<div class="factor-check-row"><span>${esc(label)}</span><strong class="${klass}">${esc(value)}</strong></div>`;
}
