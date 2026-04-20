import { api } from '../qtapi.js?v=8';
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

const COPY = {
  en: {
    title: 'Trading Ops',
    subtitle: 'Paper auto-submit operations, schedule status, watchlist state, alerts, and latest review.',
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
    noAlertsHint: 'Run a paper trading cycle or start the live monitor.',
    noReview: 'No review yet',
    noReviewHint: 'Premarket, intraday monitor, and daily review jobs will land here.',
    uiOnly: 'ui-only',
    mode: 'Mode',
    stream: 'Stream',
    lastEvent: 'Last event',
    notifier: 'Notifier',
    jobs: 'Jobs',
    monitor: 'Monitor',
    triggers: 'Triggers',
    debates: 'Debates',
    approvals: 'Approvals',
    paperMode: 'Paper mode',
    budgetGate: 'Budget gate',
    autoSubmit: 'Auto-submit',
    watchEnabled: 'enabled',
    watchDisabled: 'disabled',
    nextDay: 'next day',
    clear: 'clear',
    debateBridge: 'Debate Bridge',
    riskBridge: 'Risk Gate',
  },
  zh: {
    title: '交易运维',
    subtitle: 'Paper Auto-Submit 运行总控：调度状态、自选池、告警、复盘和自动交易闭环。',
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
    noAlertsHint: '运行一次交易闭环，或先启动实时监控。',
    noReview: '暂无复盘',
    noReviewHint: '盘前、盘中监控和日终复盘的结果会落在这里。',
    uiOnly: '仅界面',
    mode: '模式',
    stream: '流',
    lastEvent: '最近事件',
    notifier: '通知器',
    jobs: '任务数',
    monitor: '监控',
    triggers: '触发数',
    debates: '辩论数',
    approvals: '审批数',
    paperMode: '纸面模式',
    budgetGate: '预算门禁',
    autoSubmit: '自动下单',
    watchEnabled: '已启用',
    watchDisabled: '已停用',
    nextDay: '次日关注',
    clear: '清晰',
    debateBridge: '辩论桥接',
    riskBridge: '风控门禁',
  },
};

function c(key) {
  const lang = getLang() === 'zh' ? 'zh' : 'en';
  return COPY[lang][key] || COPY.en[key] || key;
}

export async function render(container) {
  _container = container;
  renderShell();
  wire();
  renderPreviews();
  _langCleanup = onLangChange(() => {
    if (_container) {
      renderShell();
      wire();
      renderPreviews();
      renderSnapshot();
    }
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
      <section class="grid-2 workbench-main-grid trading-ops-grid">
        <article class="card">
          <div class="card-header"><span class="card-title">${c('schedule')}</span></div>
          <div class="card-body" id="ops-schedule">${emptyState(c('loading'))}</div>
        </article>
        <article class="card">
          <div class="card-header"><span class="card-title">${c('watchlist')}</span></div>
          <div class="card-body" id="ops-watchlist">${emptyState(c('loading'))}</div>
        </article>
        <article class="card">
          <div class="card-header"><span class="card-title">${c('alerts')}</span></div>
          <div class="card-body" id="ops-alerts">${emptyState(c('loading'))}</div>
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
  ['#ops-schedule', '#ops-watchlist', '#ops-alerts', '#ops-review'].forEach((selector) => {
    setLoading(_container.querySelector(selector), c('loading'));
  });
  try {
    _snapshot = await api.trading.opsSnapshot();
    renderSnapshot();
  } catch (err) {
    ['#ops-schedule', '#ops-watchlist', '#ops-alerts', '#ops-review'].forEach((selector) => {
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
      query: 'Run the full debate -> risk -> paper cycle.',
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
  const monitor = _snapshot.monitor || {};
  const watchlist = _snapshot.watchlist?.watchlist || [];
  const alerts = _snapshot.today_alerts?.alerts || [];
  const review = _snapshot.latest_review?.review;
  const notifier = _snapshot.notifier || {};
  const debateCount = Number(_snapshot.debates?.count || 0);
  const approvalCount = Number((_snapshot.risk?.approvals || []).length || 0);
  const latestApproval = _snapshot.risk?.latest_approval || null;

  _container.querySelector('#ops-schedule').innerHTML = `
    <div class="workbench-metric-grid">
      ${metric(c('jobs'), (schedule.jobs || []).length || 0, 'positive')}
      ${metric(c('monitor'), monitor.running ? 'on' : 'off', monitor.running ? 'positive' : 'risk')}
      ${metric(c('triggers'), monitor.trigger_count || 0)}
      ${metric(c('debates'), debateCount)}
      ${metric(c('approvals'), approvalCount)}
      ${metric(c('notifier'), notifier.telegram_configured ? 'telegram' : c('uiOnly'))}
    </div>
    <div class="preview-step-grid">
      <div class="preview-step"><span>${c('paperMode')}</span><strong>${esc(monitor.mode || 'paper')}</strong></div>
      <div class="preview-step"><span>${c('stream')}</span><strong>${esc(monitor.stream_mode || 'idle')}</strong></div>
      <div class="preview-step"><span>${c('lastEvent')}</span><strong>${esc(monitor.last_event_at || 'none')}</strong></div>
      <div class="preview-step"><span>${c('budgetGate')}</span><strong>${latestApproval ? esc(latestApproval.verdict || 'review') : '-'}</strong></div>
      <div class="preview-step"><span>${c('autoSubmit')}</span><strong>${latestApproval?.verdict === 'approve' ? 'armed' : 'guarded'}</strong></div>
      <div class="preview-step"><span>${c('debateBridge')}</span><strong>${debateCount ? 'linked' : 'idle'}</strong></div>
    </div>
    <div class="workbench-kv-list compact-kv-list">
      ${(schedule.jobs || []).map((job) => `<div class="workbench-kv-row"><span>${esc(job.job_name)}</span><strong>${esc(job.next_run || job.schedule || '-')}</strong></div>`).join('')}
    </div>`;

  _container.querySelector('#ops-watchlist').innerHTML = watchlist.length ? `
    <div class="workbench-list workbench-scroll-list">
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
            <span>${esc(item.enabled ? c('watchEnabled') : c('watchDisabled'))}</span>
          </div>
        </article>
      `).join('')}
    </div>` : emptyState(c('noWatchlist'));

  _container.querySelector('#ops-alerts').innerHTML = alerts.length ? `
    <div class="workbench-list workbench-scroll-list">
      ${alerts.map((item) => `
        <article class="workbench-item">
          <div class="workbench-item__head">
            <strong>${esc(item.symbol)} | ${esc(item.trigger_type)}</strong>
            ${statusBadge(item.risk_decision || 'watch')}
          </div>
          <p>${esc(item.agent_analysis || '')}</p>
          <div class="workbench-item__meta">
            <span>${esc(item.timestamp || '')}</span>
            <span>${c('riskBridge')}=${esc(item.risk_decision || '-')}</span>
            <span>exec=${esc(item.execution_id || '-')}</span>
          </div>
        </article>
      `).join('')}
    </div>` : emptyState(c('noAlerts'), c('noAlertsHint'));

  _container.querySelector('#ops-review').innerHTML = review ? `
    <div class="workbench-metric-grid">
      ${metric('PnL', esc(review.pnl ?? '-'), Number(review.pnl || 0) >= 0 ? 'positive' : 'risk')}
      ${metric('Trades', review.trades_count || 0)}
      ${metric('Approved', review.approved_decisions || 0, 'positive')}
      ${metric('Blocked', review.blocked_decisions || 0, 'risk')}
    </div>
    <div class="workbench-report-text">${esc(review.report_text || '')}</div>
    <div class="factor-checklist">
      ${(review.next_day_risk_flags || []).map((flag) => `<div class="factor-check-row"><span>${esc(flag)}</span><strong class="is-watch">${c('nextDay')}</strong></div>`).join('') || `<div class="factor-check-row"><span>${c('noReview')}</span><strong class="is-pass">${c('clear')}</strong></div>`}
    </div>
  ` : emptyState(c('noReview'), c('noReviewHint'));
}
