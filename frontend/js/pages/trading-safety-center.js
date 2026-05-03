import { api } from '../qtapi.js?v=8';
import { getLang, onLangChange } from '../i18n.js?v=8';
import { emptyState, esc, metric, renderError, renderTokenPreview, setLoading, statusBadge } from './workbench-utils.js?v=8';

let _container = null;
let _langCleanup = null;
let _safety = null;
let _timeline = null;

const COPY = {
  en: {
    title: 'Trading Safety Center',
    subtitle: 'Hard safety boundary for paper/live mode, kill switch, broker readiness, risk gate, submit locks, and latest decision trace.',
    refresh: 'Refresh Safety',
    timeline: 'Open Timeline',
    paperGate: 'Paper Submit Gate',
    liveRule: 'Live Hard Rule',
    controls: 'Controls',
    locks: 'Submit Locks',
    evidence: 'Latest Evidence',
    blockers: 'Blockers',
    noLocks: 'No submit locks returned.',
    noEvidence: 'No latest session evidence returned.',
  },
  zh: {
    title: '交易安全中心',
    subtitle: '集中展示 paper/live 模式、熔断开关、券商就绪、风控门禁、提交锁和最近一次决策链。',
    refresh: '刷新安全状态',
    timeline: '打开时间线',
    paperGate: 'Paper 提交门禁',
    liveRule: 'Live 硬规则',
    controls: '控制项',
    locks: '提交锁',
    evidence: '最新证据',
    blockers: '阻断项',
    noLocks: '暂无提交锁记录。',
    noEvidence: '暂无最近会话证据。',
  },
};

function c(key) {
  const lang = getLang() === 'zh' ? 'zh' : 'en';
  return COPY[lang][key] || COPY.en[key] || key;
}

function yesNo(value) {
  return value ? (getLang() === 'zh' ? '是' : 'yes') : (getLang() === 'zh' ? '否' : 'no');
}

function renderPaperGate() {
  const gate = _safety?.paper_auto_submit || {};
  return `<div class="workbench-kv-list compact-kv-list">
    <div class="workbench-kv-row"><span>allowed</span><strong>${statusBadge(gate.allowed ? 'ready' : 'blocked')}</strong></div>
    <div class="workbench-kv-row"><span>SCHEDULER_AUTO_SUBMIT</span><strong>${yesNo(gate.scheduler_auto_submit)}</strong></div>
    <div class="workbench-kv-row"><span>UNATTENDED_PAPER_MODE</span><strong>${yesNo(gate.unattended_paper_mode)}</strong></div>
    <div class="workbench-kv-row"><span>broker ready</span><strong>${yesNo(gate.broker_ready)}</strong></div>
    <div class="workbench-kv-row"><span>market open</span><strong>${yesNo(gate.market_open)}</strong></div>
    <div class="workbench-kv-row"><span>risk gate</span><strong>${yesNo(gate.risk_gate_ok)}</strong></div>
    ${renderTokenPreview(gate.blockers || [], { tone: 'risk', emptyLabel: getLang() === 'zh' ? '无阻断项' : 'no blockers' })}
  </div>`;
}

function renderLiveRule() {
  const live = _safety?.live_auto_submit || {};
  return `<div class="workbench-kv-list compact-kv-list">
    <div class="workbench-kv-row"><span>allowed</span><strong>${statusBadge(live.allowed ? 'ready' : 'blocked')}</strong></div>
    <div class="workbench-kv-row"><span>reason</span><strong>${esc(live.reason || '-')}</strong></div>
    <div class="workbench-kv-row"><span>proof</span><strong>${esc(live.proof || '-')}</strong></div>
  </div>`;
}

function renderLocks() {
  const locks = _safety?.submit_locks?.locks || _safety?.submit_locks?.items || [];
  if (!locks.length) return emptyState(c('locks'), c('noLocks'));
  return `<div class="workbench-list workbench-scroll-list">
    ${locks.slice(0, 20).map((lock) => `
      <article class="workbench-item">
        <div class="workbench-item__head"><strong>${esc(lock.symbol || lock.lock_id || lock.id || '-')}</strong>${statusBadge(lock.status || 'tracked')}</div>
        <p>${esc(lock.reason || lock.decision || '')}</p>
        <div class="workbench-item__meta"><span>${esc(lock.session_date || lock.created_at || '-')}</span><span>${esc(lock.workflow_id || '')}</span></div>
      </article>
    `).join('')}
  </div>`;
}

function renderEvidence() {
  const evidence = _safety?.latest_evidence;
  if (!evidence) return emptyState(c('evidence'), c('noEvidence'));
  return `<pre style="white-space:pre-wrap;max-height:380px;overflow:auto;font-size:11px">${esc(JSON.stringify(evidence, null, 2))}</pre>`;
}

function shell() {
  return `
    <div class="workbench-page" data-no-autotranslate="true">
      <div class="page-header">
        <div>
          <div class="page-header__title">${c('title')}</div>
          <div class="page-header__sub">${c('subtitle')}</div>
        </div>
        <div class="page-header__actions">
          <button class="btn btn-secondary btn-sm" id="btn-safety-refresh">${c('refresh')}</button>
          <a class="btn btn-primary btn-sm" href="#/automation-timeline">${c('timeline')}</a>
        </div>
      </div>

      <div class="metric-grid metrics-row-4">
        ${metric('Status', (_safety?.status || 'loading').toUpperCase())}
        ${metric('Mode', _safety?.mode || 'paper')}
        ${metric('Paper allowed', yesNo(_safety?.paper_auto_submit?.allowed))}
        ${metric('Live auto submit', yesNo(_safety?.live_auto_submit?.allowed))}
      </div>

      <div class="grid-2" style="margin-top:18px">
        <section class="card">
          <div class="card-header"><span class="card-title">${c('paperGate')}</span>${statusBadge(_safety?.paper_auto_submit?.allowed ? 'ready' : 'blocked')}</div>
          <div class="card-body">${renderPaperGate()}</div>
        </section>
        <section class="card">
          <div class="card-header"><span class="card-title">${c('liveRule')}</span>${statusBadge('blocked')}</div>
          <div class="card-body">${renderLiveRule()}</div>
        </section>
      </div>

      <div class="grid-2" style="margin-top:18px">
        <section class="card">
          <div class="card-header"><span class="card-title">${c('locks')}</span>${statusBadge(_safety?.status || 'loading')}</div>
          <div class="card-body">${renderLocks()}</div>
        </section>
        <section class="card">
          <div class="card-header"><span class="card-title">${c('evidence')}</span>${statusBadge(_timeline?.status || 'idle')}</div>
          <div class="card-body">${renderEvidence()}</div>
        </section>
      </div>
    </div>
  `;
}

async function load(container) {
  setLoading(container, getLang() === 'zh' ? '正在加载交易安全状态...' : 'Loading trading safety center...');
  try {
    [_safety, _timeline] = await Promise.all([
      api.trading.safetyCenter(),
      api.trading.automationTimeline(),
    ]);
    container.innerHTML = shell();
    bind(container);
  } catch (error) {
    renderError(container, error, { context: 'trading-safety-center', showRetry: true, onRetry: () => load(container) });
  }
}

function bind(container) {
  container.querySelector('#btn-safety-refresh')?.addEventListener('click', () => load(container));
}

export async function render(container) {
  _container = container;
  _langCleanup?.();
  _langCleanup = onLangChange(() => {
    if (_container?.isConnected) {
      _container.innerHTML = shell();
      bind(_container);
    }
  });
  await load(container);
}

export function destroy() {
  _langCleanup?.();
  _langCleanup = null;
  _container = null;
}
