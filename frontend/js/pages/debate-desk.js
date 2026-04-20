import { api } from '../qtapi.js?v=8';
import { router } from '../router.js?v=8';
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
let _debates = [];
let _current = null;

const COPY = {
  en: {
    title: 'Debate Desk',
    subtitle: 'Bull vs bear structured debate, judge verdict, and executable paper-mode conclusion.',
    symbol: 'Symbol',
    universe: 'Universe',
    providers: 'Providers',
    allProviders: 'All providers',
    query: 'Debate Query',
    queryValue: 'Debate the current thesis with ESG evidence, sentiment, and factor gates.',
    run: 'Run Debate',
    refresh: 'Refresh Ledger',
    triad: 'Debate Triad',
    rounds: 'Rebuttal Rounds',
    ledger: 'Debate Ledger',
    conflict: 'Conflict Map',
    consensus: 'Consensus',
    sentiment: 'Sentiment Overlay',
    handoff: 'Action Bridge',
    noLedger: 'No debate runs yet',
    noLedgerHint: 'Run Debate to create a bull vs bear record.',
    noSelected: 'No debate selected',
    noSelectedHint: 'The triad view will appear here.',
    loadingLedger: 'Loading debate ledger...',
    running: 'Running structured debate...',
    bull: 'Bull',
    bear: 'Bear',
    judge: 'Judge',
    humanReview: 'Human Review',
    polarity: 'Polarity',
    headlines: 'Headlines',
    feature: 'Feature',
    freshness: 'Freshness',
    sources: 'Sources',
    snapshot: 'Snapshot',
    factorCount: 'Factors',
    roundsCount: 'Rounds',
    roundPrefix: 'Round',
    bullLabel: 'Bull',
    bearLabel: 'Bear',
    judgePrefix: 'Judge',
    disputePrefix: 'Dispute',
    noMajorConflict: 'No major conflict',
    clear: 'clear',
    linked: 'linked',
    watch: 'watch',
    yes: 'yes',
    no: 'no',
    openRisk: 'Open Risk Board',
    openOps: 'Open Trading Ops',
    openSimulation: 'Open Simulation',
    openOutcome: 'Open Outcome Center',
    handoffHint: 'Send the current verdict into risk approval, operations, simulation replay, or outcome tracking.',
  },
  zh: {
    title: '辩论台',
    subtitle: '在这里查看多空对抗、裁判结论，以及可执行的纸面交易建议。',
    symbol: '股票',
    universe: '股票池',
    providers: '数据源',
    allProviders: '全部数据源',
    query: '辩论问题',
    queryValue: '结合 ESG 证据、情绪线索与因子门禁，辩论当前交易观点。',
    run: '运行辩论',
    refresh: '刷新台账',
    triad: '辩论三方',
    rounds: '交锋回合',
    ledger: '辩论台账',
    conflict: '冲突图谱',
    consensus: '共识',
    sentiment: '情绪叠层',
    handoff: '行动桥',
    noLedger: '还没有辩论记录',
    noLedgerHint: '运行一次辩论，生成多头与空头的对抗记录。',
    noSelected: '还没有选中的辩论',
    noSelectedHint: '三方观点会显示在这里。',
    loadingLedger: '正在加载辩论台账...',
    running: '正在运行结构化辩论...',
    bull: '多头',
    bear: '空头',
    judge: '裁判',
    humanReview: '人工复核',
    polarity: '情绪方向',
    headlines: '标题数',
    feature: '特征值',
    freshness: '新鲜度',
    sources: '来源',
    snapshot: '快照',
    factorCount: '因子数',
    roundsCount: '回合数',
    roundPrefix: '回合',
    bullLabel: '多头',
    bearLabel: '空头',
    judgePrefix: '裁判',
    disputePrefix: '分歧',
    noMajorConflict: '暂无主要冲突',
    clear: '清晰',
    linked: '已关联',
    watch: '关注',
    yes: '是',
    no: '否',
    openRisk: '打开风控板',
    openOps: '打开交易运维',
    openSimulation: '打开情景模拟',
    openOutcome: '打开结果追踪',
    handoffHint: '把当前 verdict 送往风控审批、交易运维、模拟回放或结果追踪。',
  },
};

function c(key) {
  const lang = getLang() === 'zh' ? 'zh' : 'en';
  return COPY[lang][key] || COPY.en[key] || key;
}

function t(en, zh) {
  return getLang() === 'zh' ? zh : en;
}

export async function render(container) {
  _container = container;
  renderShell();
  wire();
  renderFieldPreviews();
  _langCleanup = onLangChange(() => {
    if (_container) {
      renderShell();
      wire();
      renderFieldPreviews();
      renderCurrent();
      renderLedger();
    }
  });
  await refreshLedger();
}

export function destroy() {
  _container = null;
  _debates = [];
  _current = null;
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
          <div class="card-header"><span class="card-title">${c('triad')}</span></div>
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
    emptyLabel: c('allProviders'),
  });
}

async function refreshLedger() {
  setLoading(_container.querySelector('#debate-ledger'), c('loadingLedger'));
  try {
    const payload = await api.trading.debateRuns(symbol(), 12);
    _debates = payload.debates || [];
    _current = _debates[0] || _current;
    renderLedger();
    renderCurrent();
  } catch (err) {
    renderError(_container.querySelector('#debate-ledger'), err);
    renderError(_container.querySelector('#debate-current'), err);
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
    renderLedger();
    renderCurrent();
  } catch (err) {
    renderError(_container.querySelector('#debate-current'), err);
  }
}

function renderLedger() {
  const host = _container.querySelector('#debate-ledger');
  if (!host) return;
  if (!_debates.length) {
    host.innerHTML = emptyState(c('noLedger'), c('noLedgerHint'));
    return;
  }
  host.innerHTML = `
    <div class="workbench-list workbench-scroll-list">
      ${_debates.map((item) => `
        <article class="workbench-item ${_current?.debate_id === item.debate_id ? 'workbench-item--active' : ''}" data-debate-id="${esc(item.debate_id)}">
          <div class="workbench-item__head">
            <strong>${esc(item.symbol)} | ${esc(formatAction(item.recommended_action || item.judge_verdict))}</strong>
            ${statusBadge(item.recommended_action || item.judge_verdict)}
          </div>
          <p>${esc(item.bull_thesis || '')}</p>
          <div class="workbench-item__meta">
            <span>${esc(item.generated_at || '')}</span>
            <span>${c('judgePrefix')}=${num(item.judge_confidence)}</span>
            <span>${c('disputePrefix')}=${num(item.dispute_score)}</span>
          </div>
        </article>
      `).join('')}
    </div>`;
}

function renderCurrent() {
  const host = _container.querySelector('#debate-current');
  if (!host) return;
  if (!_current) {
    host.innerHTML = emptyState(c('noSelected'), c('noSelectedHint'));
    return;
  }

  const triad = [
    [c('bull'), _current.bull_thesis || '-', 'promoted'],
    [c('bear'), _current.bear_thesis || '-', 'research_only'],
    [c('judge'), `${formatAction(_current.judge_verdict)} | q=${num(_current.judge_confidence)}`, _current.judge_verdict || 'neutral'],
  ];
  const sentiment = _current.sentiment_overview || {};
  const sourceMix = Object.entries(sentiment.source_mix || {})
    .map(([key, value]) => `${key}:${value}`)
    .join(' | ') || '-';
  const rounds = _current.turns || [];

  host.innerHTML = `
    <div class="workbench-metric-grid">
      ${metric(c('judge'), formatAction(_current.recommended_action || '-').toUpperCase(), 'positive')}
      ${metric('Confidence', pct(_current.judge_confidence || 0))}
      ${metric('Dispute', pct(_current.dispute_score || 0), 'risk')}
      ${metric('Edge', num(_current.expected_edge || 0), 'positive')}
      ${metric(c('factorCount'), _current.factor_count || 0)}
      ${metric(c('roundsCount'), rounds.length || 0)}
      ${metric(c('humanReview'), _current.requires_human_review ? c('yes') : c('no'), _current.requires_human_review ? 'risk' : 'positive')}
    </div>
    <div class="debate-triad-grid">
      ${triad.map(([label, value, status]) => `
        <article class="debate-triad-card">
          <div class="debate-triad-card__head">
            <strong>${esc(label)}</strong>
            ${statusBadge(status)}
          </div>
          <p>${esc(value)}</p>
        </article>
      `).join('')}
    </div>
    <section class="workbench-section">
      <div class="workbench-section__title">${c('sentiment')}</div>
      <div class="workbench-metric-grid">
        ${metric(c('polarity'), num(sentiment.polarity || 0), (Number(sentiment.polarity || 0) || 0) >= 0 ? 'positive' : 'risk')}
        ${metric('Confidence', pct(sentiment.confidence || 0))}
        ${metric(c('headlines'), sentiment.headline_count || 0)}
        ${metric(c('feature'), num(sentiment.feature_value || 50), 'positive')}
      </div>
      <div class="workbench-kv-list compact-kv-list">
        <div class="workbench-kv-row"><span>${c('freshness')}</span><strong>${pct(sentiment.freshness_score || 0)}</strong></div>
        <div class="workbench-kv-row"><span>${c('sources')}</span><strong>${esc(sourceMix)}</strong></div>
        <div class="workbench-kv-row"><span>${c('snapshot')}</span><strong>${esc(_current.sentiment_snapshot_id || '-')}</strong></div>
      </div>
    </section>
    <section class="workbench-section">
      <div class="workbench-section__title">${c('rounds')}</div>
      <div class="workbench-list">
        ${rounds.map((turn) => `
          <article class="workbench-item">
            <div class="workbench-item__head">
              <strong>${c('roundPrefix')} ${esc(turn.round_number)}</strong>
              <span>${esc(num(turn.confidence_shift))}</span>
            </div>
            <p><strong>${c('bullLabel')}：</strong>${esc(turn.bull_point)}</p>
            <p><strong>${c('bearLabel')}：</strong>${esc(turn.bear_point)}</p>
            <div class="token-preview token-preview--dense">
              ${(turn.evidence_focus || []).map((item) => `<span class="token-chip token-chip--neutral">${esc(item)}</span>`).join('')}
            </div>
          </article>
        `).join('')}
      </div>
    </section>
    <div class="grid-2 compact-control-grid">
      <section class="workbench-section">
        <div class="workbench-section__title">${c('conflict')}</div>
        <div class="factor-checklist">
          ${(_current.conflict_points || []).map((item) => `<div class="factor-check-row"><span>${esc(item)}</span><strong class="is-watch">${c('watch')}</strong></div>`).join('') || `<div class="factor-check-row"><span>${c('noMajorConflict')}</span><strong class="is-pass">${c('clear')}</strong></div>`}
        </div>
      </section>
      <section class="workbench-section">
        <div class="workbench-section__title">${c('consensus')}</div>
        <div class="factor-checklist">
          ${(_current.consensus_points || []).map((item) => `<div class="factor-check-row"><span>${esc(item)}</span><strong class="is-pass">${c('linked')}</strong></div>`).join('') || `<div class="factor-check-row"><span>-</span><strong class="is-pass">${c('linked')}</strong></div>`}
        </div>
      </section>
    </div>
    <section class="workbench-section">
      <div class="workbench-section__title">${c('handoff')}</div>
      <div class="workbench-report-text">${c('handoffHint')}</div>
      <div class="workbench-link-list">
        <button class="workbench-link-row" id="link-debate-risk"><strong>${c('openRisk')}</strong><span>${t('Send this verdict into risk approval and single-name caps.', '把当前 verdict 送入风控审批与单票上限。')}</span></button>
        <button class="workbench-link-row" id="link-debate-ops"><strong>${c('openOps')}</strong><span>${t('Review schedule, watchlist, alerts, and paper auto-submit status.', '查看调度、自选池、告警和纸面自动下单状态。')}</span></button>
        <button class="workbench-link-row" id="link-debate-sim"><strong>${c('openSimulation')}</strong><span>${t('Replay the current thesis in scenario simulation.', '在情景模拟中回放当前判断。')}</span></button>
        <button class="workbench-link-row" id="link-debate-outcome"><strong>${c('openOutcome')}</strong><span>${t('Keep the judge verdict in the outcome and review loop.', '把裁判结论送入结果追踪与复盘闭环。')}</span></button>
      </div>
    </section>`;

  host.querySelector('#link-debate-risk')?.addEventListener('click', () => router.navigate('/risk-board'));
  host.querySelector('#link-debate-ops')?.addEventListener('click', () => router.navigate('/trading-ops'));
  host.querySelector('#link-debate-sim')?.addEventListener('click', () => router.navigate('/simulation'));
  host.querySelector('#link-debate-outcome')?.addEventListener('click', () => router.navigate('/outcome-center'));
}

function formatAction(value) {
  const normalized = String(value || '').trim().toLowerCase();
  const map = {
    long: t('Long', '看多'),
    short: t('Short', '看空'),
    neutral: t('Neutral', '中性'),
    block: t('Block', '阻止'),
    approve: t('Approve', '批准'),
    reduce: t('Reduce', '缩减'),
    reject: t('Reject', '拒绝'),
    halt: t('Halt', '暂停'),
  };
  return map[normalized] || String(value || '-');
}
