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
  statusBadge,
} from './workbench-utils.js?v=8';

let _container = null;
let _langCleanup = null;
let _summary = null;
let _latestOutcome = null;
let _latestReview = null;
let _actionState = { tone: 'pending', text: '' };

const COPY = {
  en: {
    title: 'Outcome Center',
    subtitle: 'Track shadow outcomes, calibration quality, regret, and the Stage 2/3 candidate queue.',
    symbol: 'Symbol',
    decision: 'Decision ID',
    realized: 'Realized Return',
    benchmark: 'Benchmark Return',
    refresh: 'Refresh Outcomes',
    record: 'Record Outcome',
    refreshBusy: 'Refreshing...',
    recordBusy: 'Recording...',
    loading: 'Loading outcome tracking...',
    refreshed: 'Outcome summary refreshed',
    recorded: 'Shadow outcome recorded',
    failed: 'Outcome action failed',
    stateHint: 'Action State',
    stateReady: 'Ready to evaluate the next shadow row',
    stateRefresh: 'Refreshing calibration snapshot and latest daily review',
    stateRecord: 'Recording a manual shadow outcome and immediately updating the right-side latest row',
    stateDegraded: 'Running in degraded persistence mode, but the outcome flow remains reproducible',
    summary: 'Calibration Summary',
    records: 'Latest Outcome Row',
    policy: 'Policy',
    recordsLabel: 'Records',
    hitRate: 'Hit Rate',
    brier: 'Brier',
    excess: 'Excess Return',
    breaches: 'Drawdown Breaches',
    shadowMode: 'Shadow Mode',
    calibrationTarget: 'Calibration Target',
    candidatePool: 'Stage 2/3 Candidates',
    curve: 'Calibration Curve',
    regret: 'Regret Tracking',
    intake: 'Failure Intake',
    why: 'Why this matters',
    whyText: 'Each new row improves calibration quality, regret visibility, and the quality of future Stage 2/3 training labels.',
    reviewBridge: 'Daily Review Bridge',
    reviewId: 'Review ID',
    trades: 'Trades',
    approvedBlocked: 'Approved / Blocked',
    noSummary: 'No outcome summary yet',
    noSummaryHint: 'Refresh Outcomes pulls the latest calibration snapshot. Record Outcome appends a new shadow row immediately.',
    noRecordTitle: 'No shadow outcomes yet',
    noRecordText: 'An outcome row stores symbol, decision ID, realized return, benchmark return, excess return, direction hit, and notes.',
    sourceLabel: 'Where data comes from',
    sourceText: 'Decision IDs come from the workbench; realized and benchmark returns come from manual entry or later market-data jobs.',
    valueLabel: 'Why it helps shadow trading',
    valueText: 'This closes the loop between decision quality, regret analysis, and future label curation without sending any broker order.',
    latestRecordTitle: 'Latest recorded row',
    directionHit: 'Direction Hit',
    trackedMode: 'Tracking Mode',
    optional: 'optional',
    tracked: 'tracked',
    watched: 'watched',
    derived: 'derived',
    safe: 'safe',
    tagged: 'tagged',
    yes: 'yes',
    no: 'no',
    pending: 'pending',
    on: 'on',
    off: 'off',
    latestReviewMissing: 'No daily review has landed yet',
    reviewPendingHint: 'Premarket, midday, and review jobs will appear here after the scheduler or a manual trading cycle runs.',
  },
  zh: {
    title: '结果追踪',
    subtitle: '用于追踪 shadow outcome、校准质量、遗憾值，以及 Stage 2/3 候选样本池。',
    symbol: '股票',
    decision: '决策 ID',
    realized: '真实收益',
    benchmark: '基准收益',
    refresh: '刷新结果',
    record: '记录结果',
    refreshBusy: '正在刷新...',
    recordBusy: '正在记录...',
    loading: '正在加载结果追踪...',
    refreshed: '结果摘要已刷新',
    recorded: '影子结果已记录',
    failed: '结果操作失败',
    stateHint: '当前动作',
    stateReady: '已准备好评估下一条影子结果',
    stateRefresh: '正在刷新校准快照与最新日终复盘',
    stateRecord: '正在记录一条手动影子结果，并立即更新右侧最新记录',
    stateDegraded: '当前处于降级持久化模式，但结果链路仍然可复现',
    summary: '校准摘要',
    records: '最新结果行',
    policy: '策略说明',
    recordsLabel: '记录数',
    hitRate: '命中率',
    brier: 'Brier 分数',
    excess: '超额收益',
    breaches: '回撤越界次数',
    shadowMode: '影子模式',
    calibrationTarget: '校准目标',
    candidatePool: 'Stage 2/3 候选池',
    curve: '校准曲线',
    regret: '遗憾跟踪',
    intake: '失败样本接入',
    why: '为什么重要',
    whyText: '每一条新记录都会提升校准质量、遗憾值可见性，以及后续 Stage 2/3 训练标签的质量。',
    reviewBridge: '日终复盘桥接',
    reviewId: '复盘 ID',
    trades: '交易数',
    approvedBlocked: '批准 / 阻断',
    noSummary: '暂无结果摘要',
    noSummaryHint: '“刷新结果”会拉取最新校准快照；“记录结果”会立即追加新的影子结果行。',
    noRecordTitle: '暂无影子结果记录',
    noRecordText: '一条结果记录会保存股票、决策 ID、真实收益、基准收益、超额收益、方向命中与备注。',
    sourceLabel: '数据从哪里来',
    sourceText: '决策 ID 来自工作台；真实收益和基准收益来自当前录入，或之后的市场数据回填任务。',
    valueLabel: '为什么对 shadow trading 有价值',
    valueText: '它把决策质量、遗憾分析和后续标签整理闭环起来，同时不会触发任何券商订单。',
    latestRecordTitle: '最新记录',
    directionHit: '方向命中',
    trackedMode: '跟踪模式',
    optional: '可选',
    tracked: '已跟踪',
    watched: '已观察',
    derived: '自动推导',
    safe: '安全',
    tagged: '已标记',
    yes: '是',
    no: '否',
    pending: '待定',
    on: '开启',
    off: '关闭',
    latestReviewMissing: '暂无日终复盘',
    reviewPendingHint: '盘前、盘中和日终任务运行后，结果会显示在这里。',
  },
};

function c(key) {
  const lang = getLang() === 'zh' ? 'zh' : 'en';
  return COPY[lang][key] || COPY.en[key] || key;
}

function isMounted() {
  return Boolean(_container && _container.isConnected);
}

function formatReturn(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? pct(parsed) : '--';
}

function setState(tone, text) {
  _actionState = { tone, text };
  const host = _container?.querySelector('#outcome-state-strip');
  if (!host) return;
  const cls = tone === 'error' ? 'is-risk' : tone === 'warning' ? 'is-watch' : tone === 'success' ? 'is-pass' : 'is-review';
  host.innerHTML = `
    <div class="factor-check-row">
      <span>${c('stateHint')}</span>
      <strong class="${cls}">${esc(text)}</strong>
    </div>
  `;
}

function symbolValue() {
  return String(_container?.querySelector('#outcome-symbol')?.value || 'AAPL').trim().toUpperCase();
}

export async function render(container) {
  _container = container;
  renderShell();
  wire();
  renderTopPreview();
  _langCleanup = onLangChange(() => {
    if (!_container?.isConnected) return;
    renderShell();
    wire();
    renderTopPreview();
    renderPanels();
  });
  await refreshOutcomes();
}

export function destroy() {
  _langCleanup?.();
  _langCleanup = null;
  _container = null;
  _summary = null;
  _latestOutcome = null;
  _latestReview = null;
}

function renderShell() {
  if (!_container) return;
  _container.innerHTML = `
    <div class="workbench-page outcome-center-page" data-no-autotranslate="true">
      <section class="run-panel">
        <div class="run-panel__header">
          <div class="run-panel__title">${c('title')}</div>
          <div class="run-panel__sub">${c('subtitle')}</div>
        </div>
        <div class="run-panel__body">
          <div class="grid-2 compact-control-grid outcome-top-grid">
            <label class="field field--with-preview">
              <span>${c('symbol')}</span>
              <input id="outcome-symbol" value="AAPL">
              <div id="outcome-symbol-preview"></div>
            </label>
            <label class="field">
              <span>${c('decision')}</span>
              <input id="outcome-decision" placeholder="${c('optional')} decision id">
            </label>
            <label class="field">
              <span>${c('realized')}</span>
              <input id="outcome-realized" value="0.012">
            </label>
            <label class="field">
              <span>${c('benchmark')}</span>
              <input id="outcome-benchmark" value="0.004">
            </label>
          </div>
          <div id="outcome-state-strip" class="workbench-inline-status"></div>
        </div>
        <div class="run-panel__foot workbench-action-grid">
          <button class="btn btn-primary workbench-action-btn" id="btn-outcome-refresh">${c('refresh')}</button>
          <button class="btn btn-ghost workbench-action-btn" id="btn-outcome-record">${c('record')}</button>
        </div>
      </section>

      <section class="grid-2 workbench-main-grid outcome-grid">
        <article class="run-panel">
          <div class="run-panel__header"><div class="run-panel__title">${c('summary')}</div></div>
          <div class="run-panel__body" id="outcome-summary">${emptyState(c('loading'))}</div>
        </article>
        <article class="run-panel">
          <div class="run-panel__header"><div class="run-panel__title">${c('records')}</div></div>
          <div class="run-panel__body" id="outcome-records">${emptyState(c('loading'))}</div>
        </article>
      </section>
    </div>`;
}

function wire() {
  if (!_container) return;
  _container.querySelector('#btn-outcome-refresh')?.addEventListener('click', refreshOutcomes);
  _container.querySelector('#btn-outcome-record')?.addEventListener('click', recordOutcome);
  _container.querySelector('#outcome-symbol')?.addEventListener('input', renderTopPreview);
}

function renderTopPreview() {
  const host = _container?.querySelector('#outcome-symbol-preview');
  if (!host) return;
  host.innerHTML = renderTokenPreview([symbolValue()], { tone: 'accent', maxItems: 1 });
  setState(_actionState.tone, _actionState.text || c('stateReady'));
}

async function refreshOutcomes() {
  if (!isMounted()) return;
  const refreshButton = _container?.querySelector('#btn-outcome-refresh');
  if (refreshButton) {
    refreshButton.disabled = true;
    refreshButton.textContent = c('refreshBusy');
  }
  setState('pending', c('stateRefresh'));
  setLoading(_container?.querySelector('#outcome-summary'), c('loading'));
  setLoading(_container?.querySelector('#outcome-records'), c('loading'));
  try {
    const [outcomePayload, latestReviewResult] = await Promise.all([
      api.outcomes.evaluate({ symbol: symbolValue() }),
      api.trading.latestReview().catch(() => ({ review: null })),
    ]);
    if (!isMounted()) return;
    _summary = outcomePayload.summary || outcomePayload;
    _latestReview = latestReviewResult?.review || null;
    setState(_summary?.degraded ? 'warning' : 'success', _summary?.degraded ? c('stateDegraded') : c('refreshed'));
    renderPanels();
    toast.success(c('refreshed'));
  } catch (error) {
    if (!isMounted()) return;
    setState('error', error.message || c('failed'));
    renderError(_container?.querySelector('#outcome-summary'), error);
    renderError(_container?.querySelector('#outcome-records'), error);
  } finally {
    if (refreshButton) {
      refreshButton.disabled = false;
      refreshButton.textContent = c('refresh');
    }
  }
}

async function recordOutcome() {
  if (!isMounted()) return;
  const recordButton = _container?.querySelector('#btn-outcome-record');
  if (recordButton) {
    recordButton.disabled = true;
    recordButton.textContent = c('recordBusy');
  }
  setState('pending', c('stateRecord'));
  setLoading(_container?.querySelector('#outcome-records'), c('recordBusy'));
  try {
    const symbol = symbolValue();
    const decisionId = String(_container?.querySelector('#outcome-decision')?.value || '').trim() || `manual-${symbol.toLowerCase()}-${Date.now()}`;
    const realizedReturn = Number(_container?.querySelector('#outcome-realized')?.value || 0);
    const benchmarkReturn = Number(_container?.querySelector('#outcome-benchmark')?.value || 0);
    const payload = await api.outcomes.evaluate({
      symbol,
      decision_id: decisionId,
      realized_return: realizedReturn,
      benchmark_return: benchmarkReturn,
      drawdown: -0.02,
      notes: getLang() === 'zh'
        ? '界面手动录入的影子结果，不会触发任何券商执行。'
        : 'Manual shadow outcome entry; no broker execution is triggered.',
    });
    if (!isMounted()) return;
    _summary = payload.summary || payload;
    _latestOutcome = payload.record || payload.latest_record || payload.latest_outcome || {
      symbol,
      decision_id: decisionId,
      realized_return: realizedReturn,
      benchmark_return: benchmarkReturn,
      excess_return: realizedReturn - benchmarkReturn,
      direction_hit: realizedReturn >= benchmarkReturn,
      notes: getLang() === 'zh' ? '最新手动写入的影子结果。' : 'Latest manually recorded shadow outcome.',
    };
    _latestReview = (await api.trading.latestReview().catch(() => ({ review: null })))?.review || null;
    setState(_summary?.degraded ? 'warning' : 'success', _summary?.degraded ? c('stateDegraded') : c('recorded'));
    renderPanels();
    toast.success(c('recorded'));
  } catch (error) {
    if (!isMounted()) return;
    setState('error', error.message || c('failed'));
    renderError(_container?.querySelector('#outcome-records'), error);
    toast.error(c('failed'), error.message || '');
  } finally {
    if (recordButton) {
      recordButton.disabled = false;
      recordButton.textContent = c('record');
    }
  }
}

function renderPanels() {
  if (!_container) return;
  renderSummaryPanel();
  renderRecordsPanel();
}

function renderSummaryPanel() {
  const host = _container?.querySelector('#outcome-summary');
  if (!host) return;
  if (!_summary) {
    host.innerHTML = emptyState(c('noSummary'), c('noSummaryHint'));
    return;
  }

  const reviewBlock = _latestReview
    ? `
      <div class="workbench-section">
        <div class="workbench-section__title">${c('reviewBridge')}</div>
        <div class="workbench-kv-list compact-kv-list">
          <div class="workbench-kv-row"><span>${c('reviewId')}</span><strong>${esc(_latestReview.review_id || '-')}</strong></div>
          <div class="workbench-kv-row"><span>PnL</span><strong>${esc(_latestReview.pnl ?? '-')}</strong></div>
          <div class="workbench-kv-row"><span>${c('trades')}</span><strong>${esc(_latestReview.trades_count ?? 0)}</strong></div>
          <div class="workbench-kv-row"><span>${c('approvedBlocked')}</span><strong>${esc(_latestReview.approved_decisions ?? 0)} / ${esc(_latestReview.blocked_decisions ?? 0)}</strong></div>
        </div>
        ${_latestReview.report_text ? `<div class="workbench-report-text">${_latestReview.report_text}</div>` : ''}
      </div>
    `
    : `
      <div class="workbench-section">
        <div class="workbench-section__title">${c('reviewBridge')}</div>
        <p class="workbench-section__hint">${c('latestReviewMissing')}</p>
        <div class="preview-step-grid">
          <div class="preview-step"><span>${c('reviewBridge')}</span><strong>${c('pending')}</strong></div>
          <div class="preview-step"><span>${c('stateHint')}</span><strong>${c('reviewPendingHint')}</strong></div>
        </div>
      </div>
    `;

  host.innerHTML = `
    <div class="workbench-metric-grid">
      ${metric(c('recordsLabel'), _summary.record_count ?? 0, 'positive')}
      ${metric(c('hitRate'), _summary.hit_rate == null ? '--' : pct(_summary.hit_rate))}
      ${metric(c('brier'), _summary.mean_brier == null ? '--' : Number(_summary.mean_brier).toFixed(3))}
      ${metric(c('excess'), _summary.mean_excess_return == null ? '--' : pct(_summary.mean_excess_return))}
    </div>
    <div class="workbench-kv-list compact-kv-list">
      <div class="workbench-kv-row"><span>${c('shadowMode')}</span><strong>${_summary.shadow_mode ? c('on') : c('off')}</strong></div>
      <div class="workbench-kv-row"><span>${c('breaches')}</span><strong>${esc(_summary.drawdown_breaches ?? 0)}</strong></div>
      <div class="workbench-kv-row"><span>${c('calibrationTarget')}</span><strong>direction + brier</strong></div>
      <div class="workbench-kv-row"><span>${c('candidatePool')}</span><strong>${(_summary.record_count ?? 0) >= 5 ? 'warming' : 'building'}</strong></div>
    </div>
    <div class="preview-step-grid">
      <div class="preview-step"><span>${c('curve')}</span><strong>${(_summary.record_count ?? 0) >= 10 ? 'active' : 'waiting'}</strong></div>
      <div class="preview-step"><span>${c('regret')}</span><strong>${_summary.mean_excess_return == null ? 'waiting' : 'active'}</strong></div>
      <div class="preview-step"><span>${c('intake')}</span><strong>${(_summary.drawdown_breaches ?? 0) > 0 ? 'flagged' : 'clean'}</strong></div>
    </div>
    <div class="workbench-section">
      <div class="workbench-section__title">${c('why')}</div>
      <p class="workbench-section__hint">${c('whyText')}</p>
    </div>
    <div class="workbench-section">
      <div class="workbench-section__title">${c('policy')}</div>
      <p class="workbench-section__hint">${esc(_summary.policy || c('valueText'))}</p>
    </div>
    ${reviewBlock}
  `;
}

function renderRecordsPanel() {
  const host = _container?.querySelector('#outcome-records');
  if (!host) return;
  if (!_latestOutcome) {
    host.innerHTML = `
      <div class="agent-preview">
        <div>
          <div class="functional-empty__eyebrow">${c('latestRecordTitle')}</div>
          <h3>${c('noRecordTitle')}</h3>
          <p>${c('noRecordText')}</p>
        </div>
        <div class="workbench-kv-list compact-kv-list">
          <div class="workbench-kv-row"><span>${c('sourceLabel')}</span><strong>${c('tracked')}</strong></div>
          <div class="workbench-kv-row"><span>${c('valueLabel')}</span><strong>${c('tagged')}</strong></div>
          <div class="workbench-kv-row"><span>${c('directionHit')}</span><strong>${c('derived')}</strong></div>
          <div class="workbench-kv-row"><span>${c('trackedMode')}</span><strong>${c('safe')}</strong></div>
        </div>
        <div class="preview-step-grid">
          <div class="preview-step"><span>${c('sourceLabel')}</span><strong>${c('sourceText')}</strong></div>
          <div class="preview-step"><span>${c('valueLabel')}</span><strong>${c('valueText')}</strong></div>
        </div>
      </div>
    `;
    return;
  }

  const record = {
    ..._latestOutcome,
    excess_return:
      _latestOutcome.excess_return ??
      (Number(_latestOutcome.realized_return || 0) - Number(_latestOutcome.benchmark_return || 0)),
  };

  host.innerHTML = `
    <div class="workbench-list">
      <article class="workbench-item">
        <div class="workbench-item__head">
          <strong>${esc(record.decision_id || record.outcome_id || c('latestRecordTitle'))}</strong>
          ${statusBadge(record.direction_hit ? 'promoted' : 'research_only')}
        </div>
        <p>${esc(record.notes || c('latestRecordTitle'))}</p>
        <div class="workbench-item__meta">
          <span>${esc(record.symbol || '')}</span>
          <span>${c('realized')}=${formatReturn(record.realized_return)}</span>
          <span>${c('benchmark')}=${formatReturn(record.benchmark_return)}</span>
          <span>${c('excess')}=${formatReturn(record.excess_return)}</span>
        </div>
      </article>
      <div class="workbench-kv-list compact-kv-list">
        <div class="workbench-kv-row"><span>${c('directionHit')}</span><strong>${record.direction_hit == null ? c('pending') : record.direction_hit ? c('yes') : c('no')}</strong></div>
        <div class="workbench-kv-row"><span>${c('decision')}</span><strong>${esc(record.decision_id || c('optional'))}</strong></div>
        <div class="workbench-kv-row"><span>${c('trackedMode')}</span><strong>${c('shadowMode')}</strong></div>
        <div class="workbench-kv-row"><span>${c('candidatePool')}</span><strong>${c('tracked')}</strong></div>
      </div>
      <div class="preview-step-grid">
        <div class="preview-step"><span>${c('realized')}</span><strong>${formatReturn(record.realized_return)}</strong></div>
        <div class="preview-step"><span>${c('benchmark')}</span><strong>${formatReturn(record.benchmark_return)}</strong></div>
        <div class="preview-step"><span>${c('excess')}</span><strong>${formatReturn(record.excess_return)}</strong></div>
      </div>
      ${Array.isArray(record.lineage) && record.lineage.length ? `
        <div class="workbench-section">
          <div class="workbench-section__title">${c('sourceLabel')}</div>
          <div class="workbench-kv-list compact-kv-list">
            ${record.lineage.map((item) => `<div class="workbench-kv-row"><span>lineage</span><strong>${esc(item)}</strong></div>`).join('')}
          </div>
        </div>
      ` : ''}
    </div>
  `;
}
