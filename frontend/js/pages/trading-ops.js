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
  },
  zh: {
    title: '交易运维',
    subtitle: 'Paper Auto-Submit 运维面板：调度状态、自选池、今日告警和最新复盘。',
    symbol: '股票',
    universe: '股票池',
    providers: '数据源',
    refresh: '刷新运维',
    addWatch: '加入自选',
    premarket: '运行盘前',
    monitorStart: '启动监控',
    monitorStop: '停止监控',
    cycle: '运行交易闭环',
    schedule: '调度与监控',
    watchlist: '自选池',
    alerts: '今日告警',
    review: '最新复盘',
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
          <div class="card-body" id="ops-schedule">${emptyState('Loading trading ops')}</div>
        </article>
        <article class="card">
          <div class="card-header"><span class="card-title">${c('watchlist')}</span></div>
          <div class="card-body" id="ops-watchlist">${emptyState('Loading trading ops')}</div>
        </article>
        <article class="card">
          <div class="card-header"><span class="card-title">${c('alerts')}</span></div>
          <div class="card-body" id="ops-alerts">${emptyState('Loading trading ops')}</div>
        </article>
        <article class="card">
          <div class="card-header"><span class="card-title">${c('review')}</span></div>
          <div class="card-body" id="ops-review">${emptyState('Loading trading ops')}</div>
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
    setLoading(_container.querySelector(selector), 'Loading trading ops...');
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
  setLoading(_container.querySelector('#ops-alerts'), 'Running paper trading cycle...');
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

  _container.querySelector('#ops-schedule').innerHTML = `
    <div class="workbench-metric-grid">
      ${metric('Jobs', (schedule.jobs || []).length || 0, 'positive')}
      ${metric('Monitor', monitor.running ? 'on' : 'off', monitor.running ? 'positive' : 'risk')}
      ${metric('Triggers', monitor.trigger_count || 0)}
      ${metric('Notifier', notifier.telegram_configured ? 'telegram' : 'ui-only')}
      ${metric('Debates', debateCount)}
      ${metric('Approvals', approvalCount)}
    </div>
    <div class="workbench-kv-list compact-kv-list">
      ${(schedule.jobs || []).map((job) => `<div class="workbench-kv-row"><span>${esc(job.job_name)}</span><strong>${esc(job.next_run || job.schedule || '-')}</strong></div>`).join('')}
    </div>
    <div class="preview-step-grid">
      <div class="preview-step"><span>Mode</span><strong>${esc(monitor.mode || 'paper')}</strong></div>
      <div class="preview-step"><span>Stream</span><strong>${esc(monitor.stream_mode || 'idle')}</strong></div>
      <div class="preview-step"><span>Last event</span><strong>${esc(monitor.last_event_at || 'none')}</strong></div>
      <div class="preview-step"><span>Notifier</span><strong>${esc(notifier.mode || 'ui-only')}</strong></div>
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
            <span>${esc(item.added_date || '')}</span>
          </div>
        </article>
      `).join('')}
    </div>` : emptyState('No watchlist rows yet');

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
            <span>debate=${esc(item.debate_id || '-')}</span>
            <span>exec=${esc(item.execution_id || '-')}</span>
          </div>
        </article>
      `).join('')}
    </div>` : emptyState('No alerts today', 'Run a paper trading cycle or start the live monitor.');

  _container.querySelector('#ops-review').innerHTML = review ? `
    <div class="workbench-metric-grid">
      ${metric('PnL', esc(review.pnl ?? '-'), review.pnl >= 0 ? 'positive' : 'risk')}
      ${metric('Trades', review.trades_count || 0)}
      ${metric('Approved', review.approved_decisions || 0, 'positive')}
      ${metric('Blocked', review.blocked_decisions || 0, 'risk')}
    </div>
    <div class="workbench-report-text">${esc(review.report_text || '')}</div>
    <div class="factor-checklist">
      ${(review.next_day_risk_flags || []).map((flag) => `<div class="factor-check-row"><span>${esc(flag)}</span><strong class="is-watch">next day</strong></div>`).join('') || '<div class="factor-check-row"><span>No next-day risk flag</span><strong class="is-pass">clear</strong></div>'}
    </div>
  ` : emptyState('No review yet', 'Premarket, intraday monitor, and daily review jobs will land here.');
}
