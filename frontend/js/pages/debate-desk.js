import { api } from '../qtapi.js?v=8';
import { router } from '../router.js?v=8';
import { getLang, onLangChange } from '../i18n.js?v=8';
import {
  emptyState,
  esc,
  loadPayloadSnapshot,
  metric,
  miniMetric,
  num,
  persistPayloadSnapshot,
  pct,
  renderDegradedNotice,
  renderError,
  renderTokenPreview,
  setLoading,
  splitTokens,
  statusBadge,
} from './workbench-utils.js?v=8';

let _container = null;
let _langCleanup = null;
let _debates = [];
let _current = null;
let _degradedMeta = null;

const DEBATE_CACHE_KEY = 'qt.debate-desk.snapshot.v1';
const DEBATE_CACHE_TTL_MS = 20 * 60 * 1000;

const COPY = {
  en: {
    title: 'Debate Desk',
    subtitle: 'Structured bull vs bear debate with judge verdict, conflict map, and direct handoff into risk approval.',
    symbol: 'Symbol',
    universe: 'Universe',
    providers: 'Providers',
    query: 'Debate Query',
    queryValue: 'Debate the current thesis with ESG evidence, factor gates, sentiment, and regime risk.',
    run: 'Run Debate',
    refresh: 'Refresh Ledger',
    current: 'Current Debate',
    ledger: 'Debate Ledger',
    rounds: 'Rebuttal Rounds',
    conflict: 'Conflict Map',
    consensus: 'Consensus',
    sentiment: 'Sentiment Overlay',
    handoff: 'Action Bridge',
    noLedger: 'No debate runs yet',
    noLedgerHint: 'Run Debate to create a bull vs bear record and judge verdict.',
    noSelected: 'No debate selected',
    noSelectedHint: 'The latest debate, conflict points, and handoff actions will appear here.',
    loadingLedger: 'Loading debate ledger...',
    running: 'Running structured debate...',
    bull: 'Bull',
    bear: 'Bear',
    judge: 'Judge',
    confidence: 'Confidence',
    dispute: 'Dispute',
    review: 'Human Review',
    expected: 'Expected Edge',
    factors: 'Factors',
    roundsCount: 'Rounds',
    noMajorConflict: 'No major conflict logged.',
    noConsensus: 'No consensus points logged.',
    polarity: 'Polarity',
    headlines: 'Headlines',
    freshness: 'Freshness',
    feature: 'Feature',
    sourceMix: 'Source Mix',
    handoffHint: 'Move the current verdict into risk approval, ops monitoring, simulation replay, or outcome tracking.',
    openRisk: 'Go to Risk Board',
    openOps: 'Go to Trading Ops',
    openSimulation: 'Go to Simulation',
    openOutcome: 'Go to Outcome Center',
    latestRun: 'Latest Run',
    generated: 'Generated',
    verdict: 'Verdict',
    reviewYes: 'required',
    reviewNo: 'clear',
    rebuttalTitle: 'Round',
    long: 'long',
    short: 'short',
    neutral: 'neutral',
    block: 'block',
    hold: 'hold',
    confidenceShift: 'Confidence Shift',
    riskHint: 'Open position sizing, hard blocks, and capital caps.',
    opsHint: 'Inspect paper mode, schedule, alerts, and latest review.',
    simulationHint: 'Replay the active thesis with shocks and Monte Carlo.',
    outcomeHint: 'Track outcome rows, calibration, and post-trade review.',
    handoffGate: 'Risk Gate Handoff',
    nextStop: 'Next Stop',
    paperGate: 'Paper Gate',
    gateReady: 'ready for risk',
    gateReview: 'hold for review',
    gatePaper: 'paper eligible',
    gatePaperBlocked: 'paper gated',
    turnsLogged: 'Turns Logged',
  },
  zh: {
    title: '辩论台',
    subtitle: '查看多空结构化辩论、裁判结论、冲突点与风险移交。',
    symbol: '股票',
    universe: '股票池',
    providers: '数据源',
    query: '辩论问题',
    queryValue: '结合 ESG 证据、因子门禁、情绪与宏观 regime 风险，对当前交易观点进行多空辩论。',
    run: '运行辩论',
    refresh: '刷新台账',
    current: '当前辩论',
    ledger: '辩论台账',
    rounds: '交锋回合',
    conflict: '冲突图谱',
    consensus: '共识',
    sentiment: '情绪叠层',
    handoff: '行动桥接',
    noLedger: '暂无辩论记录',
    noLedgerHint: '运行一次辩论后，这里会出现多头、空头与裁判结论。',
    noSelected: '尚未选中辩论',
    noSelectedHint: '最新辩论、冲突点、共识点与风险移交会展示在这里。',
    loadingLedger: '正在加载辩论台账...',
    running: '正在运行结构化辩论...',
    bull: '多头',
    bear: '空头',
    judge: '裁判',
    confidence: '置信度',
    dispute: '分歧度',
    review: '人工复核',
    expected: '预期优势',
    factors: '因子数',
    roundsCount: '回合数',
    noMajorConflict: '暂无主要冲突记录。',
    noConsensus: '暂无共识记录。',
    polarity: '情绪方向',
    headlines: '标题数',
    freshness: '新鲜度',
    feature: '特征值',
    sourceMix: '来源混合',
    handoffHint: '把当前裁决送往风控审批、交易运维、情景模拟或结果追踪。',
    openRisk: '去风控板',
    openOps: '去交易运维',
    openSimulation: '去情景模拟',
    openOutcome: '去结果追踪',
    latestRun: '最近一次运行',
    generated: '生成时间',
    verdict: '结论',
    reviewYes: '需要',
    reviewNo: '无需',
    rebuttalTitle: '回合',
    long: '看多',
    short: '看空',
    neutral: '中性',
    block: '阻断',
    hold: '持有',
    confidenceShift: '置信度变化',
    riskHint: '查看仓位 sizing、硬性阻断与资本上限。',
    opsHint: '查看纸面模式、调度、告警与最新复盘。',
    simulationHint: '用冲击和 Monte Carlo 回放当前论点。',
    outcomeHint: '查看结果记录、校准摘要与事后复盘。',
    handoffGate: '风控移交概览',
    nextStop: '下一步',
    paperGate: '纸面门禁',
    gateReady: '可送风控',
    gateReview: '等待复核',
    gatePaper: '可纸面提交',
    gatePaperBlocked: '纸面受阻',
    turnsLogged: '已记回合',
  },
};

function c(key) {
  const lang = getLang() === 'zh' ? 'zh' : 'en';
  return COPY[lang][key] || COPY.en[key] || key;
}

function actionLabel(value) {
  const normalized = String(value || '').trim().toLowerCase();
  const map = {
    long: c('long'),
    short: c('short'),
    neutral: c('neutral'),
    block: c('block'),
    hold: c('hold'),
  };
  return map[normalized] || String(value || '-');
}

function debateDegradedState(savedAt, reason) {
  return {
    tone: 'warning',
    saved_at: savedAt || null,
    title: getLang() === 'zh' ? '辩论台已切换到缓存快照' : 'Debate Desk is showing a cached snapshot',
    reason: reason || (getLang() === 'zh'
      ? '当前继续展示最近一次成功的辩论结果，等待实时链路恢复。'
      : 'The latest successful debate payload is still visible while the live request recovers.'),
    detail: getLang() === 'zh'
      ? '当前结论、冲突点和移交动作都来自最近一次成功结果。'
      : 'Current verdict, conflict map, and handoff actions come from the latest successful run.',
    action: getLang() === 'zh'
      ? '可以继续点击“运行辩论”或“刷新台账”重试。'
      : 'Use Run Debate or Refresh Ledger to retry.',
  };
}

function hydrateDebateSnapshot() {
  const cached = loadPayloadSnapshot(DEBATE_CACHE_KEY, DEBATE_CACHE_TTL_MS);
  if (!cached?.payload) return false;
  _debates = cached.payload.debates || [];
  _current = cached.payload.current || _debates[0] || null;
  _degradedMeta = debateDegradedState(
    cached.saved_at,
    getLang() === 'zh'
      ? '正在回填最近一次成功的辩论快照，并在后台重新连接服务。'
      : 'Rehydrating the latest successful debate snapshot while reconnecting.',
  );
  renderCurrent();
  renderLedger();
  return true;
}

export async function render(container) {
  _container = container;
  renderShell();
  wire();
  renderFieldPreviews();
  hydrateDebateSnapshot();
  _langCleanup = onLangChange(() => {
    if (!_container?.isConnected) return;
    renderShell();
    wire();
    renderFieldPreviews();
    renderCurrent();
    renderLedger();
  });
  await refreshLedger();
}

export function destroy() {
  _container = null;
  _debates = [];
  _current = null;
  _degradedMeta = null;
  _langCleanup?.();
  _langCleanup = null;
}

function renderShell() {
  _container.innerHTML = `
    <div class="workbench-page trading-debate-page" data-no-autotranslate="true">
      <section class="run-panel">
        <div class="run-panel__header">
          <div class="run-panel__title">${c('title')}</div>
          <div class="run-panel__sub">${c('subtitle')}</div>
        </div>
        <div class="run-panel__body">
          <div class="grid-3 compact-control-grid live-control-grid">
            <label class="field field--with-preview">
              <span>${c('symbol')}</span>
              <input id="debate-symbol" value="AAPL">
              <div id="debate-symbol-preview"></div>
            </label>
            <label class="field field--with-preview">
              <span>${c('universe')}</span>
              <input id="debate-universe" value="AAPL, MSFT, NVDA, TSLA">
              <div id="debate-universe-preview"></div>
            </label>
            <label class="field field--with-preview">
              <span>${c('providers')}</span>
              <input id="debate-providers" value="local_esg, marketaux, thenewsapi">
              <div id="debate-provider-preview"></div>
            </label>
          </div>
          <label class="field">
            <span>${c('query')}</span>
            <textarea id="debate-query" class="form-textarea" rows="3">${c('queryValue')}</textarea>
          </label>
        </div>
        <div class="run-panel__foot workbench-action-grid">
          <button class="btn btn-primary workbench-action-btn" id="btn-debate-run">${c('run')}</button>
          <button class="btn btn-ghost workbench-action-btn" id="btn-debate-refresh">${c('refresh')}</button>
          <button class="btn btn-ghost workbench-action-btn" id="btn-debate-open-risk">${c('openRisk')}</button>
          <button class="btn btn-ghost workbench-action-btn" id="btn-debate-open-ops">${c('openOps')}</button>
        </div>
      </section>
      <section class="grid-2 workbench-main-grid trading-debate-grid">
        <article class="card">
          <div class="card-header"><span class="card-title">${c('current')}</span></div>
          <div class="card-body" id="debate-current">${emptyState(c('loadingLedger'))}</div>
        </article>
        <article class="card">
          <div class="card-header"><span class="card-title">${c('ledger')}</span></div>
          <div class="card-body" id="debate-ledger">${emptyState(c('loadingLedger'))}</div>
        </article>
      </section>
    </div>`;
}

function wire() {
  _container.querySelector('#btn-debate-run')?.addEventListener('click', runDebate);
  _container.querySelector('#btn-debate-refresh')?.addEventListener('click', refreshLedger);
  _container.querySelector('#btn-debate-open-risk')?.addEventListener('click', () => router.navigate('/risk-board'));
  _container.querySelector('#btn-debate-open-ops')?.addEventListener('click', () => router.navigate('/trading-ops'));
  ['#debate-symbol', '#debate-universe', '#debate-providers'].forEach((selector) => {
    _container.querySelector(selector)?.addEventListener('input', renderFieldPreviews);
  });
  _container.querySelector('#debate-ledger')?.addEventListener('click', (event) => {
    const row = event.target.closest('[data-debate-id]');
    if (!row) return;
    const debateId = row.getAttribute('data-debate-id');
    _current = _debates.find((item) => String(item.debate_id) === String(debateId)) || _current;
    renderCurrent();
    renderLedger();
  });
  _container.querySelector('#debate-current')?.addEventListener('click', (event) => {
    const button = event.target.closest('[data-debate-link]');
    if (!button) return;
    const routeMap = {
      risk: '/risk-board',
      ops: '/trading-ops',
      simulation: '/simulation',
      outcome: '/outcome-center',
    };
    const route = routeMap[button.getAttribute('data-debate-link')];
    if (route) router.navigate(route);
  });
}

function symbol() {
  return String(_container.querySelector('#debate-symbol')?.value || 'AAPL').trim().toUpperCase();
}

function universe() {
  return splitTokens(_container.querySelector('#debate-universe')?.value || symbol(), {
    uppercase: true,
    delimiters: /[,\s]+/,
  });
}

function providers() {
  return splitTokens(_container.querySelector('#debate-providers')?.value || '', {
    delimiters: /[,|\s]+/,
  });
}

function renderFieldPreviews() {
  _container.querySelector('#debate-symbol-preview').innerHTML = renderTokenPreview([symbol()], {
    tone: 'accent',
    maxItems: 1,
  });
  _container.querySelector('#debate-universe-preview').innerHTML = renderTokenPreview(universe(), {
    tone: 'accent',
    maxItems: 6,
  });
  _container.querySelector('#debate-provider-preview').innerHTML = renderTokenPreview(providers(), {
    tone: 'neutral',
    maxItems: 6,
  });
}

async function refreshLedger() {
  setLoading(_container.querySelector('#debate-ledger'), c('loadingLedger'));
  try {
    const payload = await api.trading.debateRuns(symbol(), 12);
    _debates = payload.debates || [];
    _current = _debates[0] || null;
    persistPayloadSnapshot(DEBATE_CACHE_KEY, { debates: _debates, current: _current }, { symbol: symbol() });
    _degradedMeta = null;
    renderLedger();
    renderCurrent();
  } catch (err) {
    const cached = loadPayloadSnapshot(DEBATE_CACHE_KEY, DEBATE_CACHE_TTL_MS);
    if (cached?.payload) {
      _debates = cached.payload.debates || [];
      _current = cached.payload.current || _debates[0] || null;
      _degradedMeta = debateDegradedState(cached.saved_at, err.message);
      renderLedger();
      renderCurrent();
      return;
    }
    renderError(_container.querySelector('#debate-ledger'), err, { onRetry: refreshLedger });
    renderError(_container.querySelector('#debate-current'), err, { onRetry: refreshLedger });
  }
}

async function runDebate() {
  setLoading(_container.querySelector('#debate-current'), c('running'));
  try {
    const payload = await api.trading.debateRun({
      symbol: symbol(),
      universe: universe(),
      query: _container.querySelector('#debate-query')?.value || '',
      mode: 'mixed',
      providers: providers(),
      quota_guard: true,
      rebuttal_rounds: 2,
    });
    _debates = [payload, ..._debates.filter((item) => item.debate_id !== payload.debate_id)];
    _current = payload;
    persistPayloadSnapshot(DEBATE_CACHE_KEY, { debates: _debates, current: _current }, { symbol: symbol() });
    _degradedMeta = null;
    renderLedger();
    renderCurrent();
  } catch (err) {
    const cached = loadPayloadSnapshot(DEBATE_CACHE_KEY, DEBATE_CACHE_TTL_MS);
    if (cached?.payload) {
      _debates = cached.payload.debates || [];
      _current = cached.payload.current || _debates[0] || null;
      _degradedMeta = debateDegradedState(cached.saved_at, err.message);
      renderLedger();
      renderCurrent();
      return;
    }
    renderError(_container.querySelector('#debate-current'), err, { onRetry: runDebate });
  }
}

function renderLedger() {
  const host = _container.querySelector('#debate-ledger');
  if (!host) return;
  const degradedBanner = _degradedMeta ? renderDegradedNotice(_degradedMeta) : '';
  if (!_debates.length) {
    host.innerHTML = emptyState(c('noLedger'), c('noLedgerHint'));
    return;
  }

  host.innerHTML = `
    ${degradedBanner}
    <div class="workbench-mini-grid">
      ${miniMetric(c('latestRun'), _debates[0]?.symbol || '-')}
      ${miniMetric(c('roundsCount'), String(_debates[0]?.turns?.length || 0))}
      ${miniMetric(c('confidence'), num(_debates[0]?.judge_confidence || 0))}
      ${miniMetric(c('dispute'), num(_debates[0]?.dispute_score || 0))}
    </div>
    <div class="workbench-list workbench-scroll-list debate-ledger-scroll">
      ${_debates.map((item) => `
        <article class="workbench-item ${_current?.debate_id === item.debate_id ? 'workbench-item--active' : ''}" data-debate-id="${esc(item.debate_id)}">
          <div class="workbench-item__head">
            <strong>${esc(item.symbol)} | ${esc(actionLabel(item.recommended_action || item.judge_verdict))}</strong>
            ${statusBadge(item.recommended_action || item.judge_verdict)}
          </div>
          <p>${esc(item.bull_thesis || item.bear_thesis || '')}</p>
          <div class="workbench-item__meta">
            <span>${c('generated')}=${esc(item.generated_at || '')}</span>
            <span>${c('confidence')}=${num(item.judge_confidence || 0)}</span>
            <span>${c('dispute')}=${num(item.dispute_score || 0)}</span>
          </div>
        </article>
      `).join('')}
    </div>`;
}

function renderCurrent() {
  const host = _container.querySelector('#debate-current');
  if (!host) return;
  const degradedBanner = _degradedMeta ? renderDegradedNotice(_degradedMeta) : '';
  if (!_current) {
    host.innerHTML = emptyState(c('noSelected'), c('noSelectedHint'));
    return;
  }

  const turns = Array.isArray(_current.turns) ? _current.turns : [];
  const conflictRows = Array.isArray(_current.conflict_points) ? _current.conflict_points : [];
  const consensusRows = Array.isArray(_current.consensus_points) ? _current.consensus_points : [];
  const sentiment = _current.sentiment_overview || {};
  const sourceMix = Object.entries(sentiment.source_mix || {});
  const recommendedAction = _current.recommended_action || _current.judge_verdict;
  const riskReady = !_current.requires_human_review && !['block', 'neutral'].includes(String(recommendedAction || '').toLowerCase());
  const paperReady = riskReady && Number(_current.dispute_score || 0) < 0.68;

  host.innerHTML = `
    ${degradedBanner}
    <div class="workbench-metric-grid">
      ${metric(c('verdict'), actionLabel(_current.judge_verdict || _current.recommended_action), 'positive')}
      ${metric(c('confidence'), num(_current.judge_confidence || 0))}
      ${metric(c('dispute'), num(_current.dispute_score || 0), Number(_current.dispute_score || 0) > 0.35 ? 'risk' : '')}
      ${metric(c('expected'), pct(_current.expected_edge || _current.confidence_shift || 0), 'positive')}
      ${metric(c('factors'), _current.factor_count || 0)}
      ${metric(c('review'), _current.requires_human_review ? c('reviewYes') : c('reviewNo'), _current.requires_human_review ? 'risk' : 'positive')}
    </div>

    <div class="debate-triad-grid">
      ${triadCard(c('bull'), _current.bull_thesis, statusBadge('long'))}
      ${triadCard(c('bear'), _current.bear_thesis, statusBadge('short'))}
      ${triadCard(c('judge'), summarizeJudge(_current), statusBadge(_current.recommended_action || _current.judge_verdict))}
    </div>

    <div class="debate-current-grid">
      <section class="workbench-section">
        <div class="workbench-section__title">${c('rounds')}</div>
        <div class="workbench-list workbench-scroll-list workbench-scroll-list--short">
          ${turns.length ? turns.map((turn) => `
            <article class="workbench-item">
              <div class="workbench-item__head">
                <strong>${c('rebuttalTitle')} ${esc(turn.round_number || '')}</strong>
                <span class="text-xs text-muted">${esc((turn.evidence_focus || []).join(' / '))}</span>
              </div>
              <p>${esc(turn.bull_point || '')}</p>
              <p>${esc(turn.bear_point || '')}</p>
              <div class="workbench-item__meta">
                <span>${c('confidenceShift')} Δ=${num(turn.confidence_shift || 0)}</span>
              </div>
            </article>
          `).join('') : emptyState(c('rounds'), c('noSelectedHint'))}
        </div>
      </section>

      <section class="workbench-section">
        <div class="workbench-section__title">${c('conflict')}</div>
        <div class="factor-checklist">
          ${(conflictRows.length ? conflictRows : [c('noMajorConflict')]).map((row) => `
            <div class="factor-check-row"><span>${esc(row)}</span><strong class="${conflictRows.length ? 'is-watch' : 'is-pass'}">${conflictRows.length ? c('dispute') : c('reviewNo')}</strong></div>
          `).join('')}
        </div>
        <div class="workbench-section__title">${c('consensus')}</div>
        <div class="factor-checklist">
          ${(consensusRows.length ? consensusRows : [c('noConsensus')]).map((row) => `
            <div class="factor-check-row"><span>${esc(row)}</span><strong class="is-pass">${consensusRows.length ? c('consensus') : c('reviewNo')}</strong></div>
          `).join('')}
        </div>
      </section>
    </div>

    <section class="workbench-section">
      <div class="workbench-section__title">${c('sentiment')}</div>
      <div class="workbench-mini-grid debate-sentiment-grid">
        ${miniMetric(c('polarity'), num(sentiment.polarity || 0))}
        ${miniMetric(c('confidence'), num(sentiment.confidence || 0))}
        ${miniMetric(c('headlines'), sentiment.headline_count || 0)}
        ${miniMetric(c('feature'), num(sentiment.feature_value || 0))}
        ${miniMetric(c('freshness'), num(sentiment.freshness_score || 0))}
        ${miniMetric(c('sourceMix'), sourceMix.length || 0)}
      </div>
      <div class="workbench-kv-list compact-kv-list">
        ${sourceMix.length ? sourceMix.map(([key, value]) => `
          <div class="workbench-kv-row"><span>${esc(key)}</span><strong>${esc(value)}</strong></div>
        `).join('') : `<div class="workbench-kv-row"><span>${c('sourceMix')}</span><strong>-</strong></div>`}
      </div>
    </section>

    <section class="workbench-section">
      <div class="workbench-section__title">${c('handoff')}</div>
      <p class="workbench-section__hint">${c('handoffHint')}</p>
      <div class="workbench-link-grid">
        ${bridgeCard('risk', c('openRisk'), c('riskHint'))}
        ${bridgeCard('ops', c('openOps'), c('opsHint'))}
        ${bridgeCard('simulation', c('openSimulation'), c('simulationHint'))}
        ${bridgeCard('outcome', c('openOutcome'), c('outcomeHint'))}
      </div>
    </section>

    <section class="workbench-section">
      <div class="workbench-section__title">${c('handoffGate')}</div>
      <div class="workbench-kv-list compact-kv-list">
        <div class="workbench-kv-row"><span>${c('nextStop')}</span><strong>${c('openRisk')}</strong></div>
        <div class="workbench-kv-row"><span>${c('paperGate')}</span><strong>${paperReady ? c('gatePaper') : c('gatePaperBlocked')}</strong></div>
        <div class="workbench-kv-row"><span>${c('review')}</span><strong>${_current.requires_human_review ? c('reviewYes') : c('reviewNo')}</strong></div>
        <div class="workbench-kv-row"><span>${c('turnsLogged')}</span><strong>${turns.length}</strong></div>
      </div>
      <div class="factor-checklist">
        <div class="factor-check-row"><span>${c('verdict')}</span><strong class="${riskReady ? 'is-pass' : 'is-watch'}">${actionLabel(recommendedAction)}</strong></div>
        <div class="factor-check-row"><span>${c('dispute')}</span><strong class="${Number(_current.dispute_score || 0) > 0.35 ? 'is-watch' : 'is-pass'}">${num(_current.dispute_score || 0)}</strong></div>
        <div class="factor-check-row"><span>${c('handoffGate')}</span><strong class="${riskReady ? 'is-pass' : 'is-watch'}">${riskReady ? c('gateReady') : c('gateReview')}</strong></div>
      </div>
    </section>
  `;
}

function triadCard(title, body, badgeHtml) {
  return `
    <article class="debate-triad-card">
      <div class="debate-triad-card__head">
        <strong>${esc(title)}</strong>
        ${badgeHtml}
      </div>
      <p>${esc(body || '-')}</p>
    </article>
  `;
}

function summarizeJudge(item) {
  const review = item.requires_human_review ? c('reviewYes') : c('reviewNo');
  return `${c('verdict')}: ${actionLabel(item.recommended_action || item.judge_verdict)} | ${c('confidence')}: ${num(item.judge_confidence || 0)} | ${c('review')}: ${review}`;
}

function bridgeCard(link, title, hint) {
  return `
    <button type="button" class="workbench-link-card workbench-link-card--action" data-debate-link="${esc(link)}">
      <strong>${esc(title)}</strong>
      <span>${esc(hint)}</span>
    </button>
  `;
}
