import { api } from '../qtapi.js?v=8';
import { getLang, onLangChange } from '../i18n.js?v=8';
import { emptyState, esc, metric, renderError, renderTokenPreview, setLoading, statusBadge } from './workbench-utils.js?v=8';

let _container = null;
let _langCleanup = null;
let _timeline = null;

const COPY = {
  en: {
    title: 'Automation Timeline',
    subtitle: 'Stage evidence for automatic analysis and paper-only submit: preopen, workflow, risk gate, paper plan, submit, sync, outcomes, report.',
    refresh: 'Refresh Timeline',
    stages: 'Stages',
    events: 'Scheduler Events',
    noEvents: 'No scheduler events returned.',
    input: 'Input',
    output: 'Output',
    duration: 'Duration',
    artifacts: 'Artifacts',
  },
  zh: {
    title: '自动化时间线',
    subtitle: '展示自动分析与 Paper-only 提交证据：盘前、工作流、风控、Paper 计划、提交、同步、结果和报告。',
    refresh: '刷新时间线',
    stages: '阶段',
    events: '调度事件',
    noEvents: '暂无调度事件。',
    input: '输入',
    output: '输出',
    duration: '耗时',
    artifacts: '证据 artifact',
  },
};

const STAGE_LABELS = {
  preopen: ['Preopen', '盘前分析'],
  workflow: ['Workflow', '工作流'],
  risk_gate: ['Risk Gate', '风控门禁'],
  paper_plan: ['Paper Plan', 'Paper 计划'],
  paper_submit: ['Paper Submit', 'Paper 提交'],
  broker_sync: ['Broker Sync', '券商同步'],
  outcomes: ['Outcomes', '结果归因'],
  report: ['Report', '报告生成'],
};

function c(key) {
  const lang = getLang() === 'zh' ? 'zh' : 'en';
  return COPY[lang][key] || COPY.en[key] || key;
}

function stageLabel(stage) {
  const labels = STAGE_LABELS[stage] || [stage, stage];
  return getLang() === 'zh' ? labels[1] : labels[0];
}

function renderStages() {
  const stages = _timeline?.stages || [];
  if (!stages.length) return emptyState(c('stages'), 'No automation stages returned.');
  return `<div class="workbench-list">
    ${stages.map((stage, index) => `
      <article class="workbench-item">
        <div class="workbench-item__head">
          <strong>${index + 1}. ${esc(stageLabel(stage.stage))}</strong>
          ${statusBadge(stage.status)}
        </div>
        <div class="workbench-kv-list compact-kv-list">
          <div class="workbench-kv-row"><span>${c('input')}</span><strong>${esc(stage.input_summary || stage.reason || '-')}</strong></div>
          <div class="workbench-kv-row"><span>${c('output')}</span><strong>${esc(stage.output_summary || stage.error || '-')}</strong></div>
          <div class="workbench-kv-row"><span>${c('duration')}</span><strong>${stage.duration_seconds == null ? '-' : `${esc(stage.duration_seconds)}s`}</strong></div>
          <div class="workbench-kv-row"><span>last_run_at</span><strong>${esc(stage.last_run_at || '-')}</strong></div>
        </div>
        ${renderTokenPreview([...(stage.blockers || []), ...(stage.warnings || [])], { tone: 'risk', emptyLabel: getLang() === 'zh' ? '无阻断项' : 'no blockers' })}
        ${stage.artifacts && Object.keys(stage.artifacts).length ? `<pre style="white-space:pre-wrap;max-height:120px;overflow:auto;font-size:11px">${esc(JSON.stringify(stage.artifacts, null, 2))}</pre>` : ''}
      </article>
    `).join('')}
  </div>`;
}

function renderEvents() {
  const events = _timeline?.recent_events || [];
  if (!events.length) return emptyState(c('events'), c('noEvents'));
  return `<div class="workbench-list workbench-scroll-list">
    ${events.slice(0, 30).map((event) => `
      <article class="workbench-item">
        <div class="workbench-item__head">
          <strong>${esc(event.event_type || event.stage || event.event_id || '-')}</strong>
          ${statusBadge(event.status || 'tracked')}
        </div>
        <p>${esc(event.reason || event.message || '')}</p>
        <div class="workbench-item__meta">
          <span>${esc(event.created_at || event.timestamp || '-')}</span>
          <span>${esc(event.acceptance_namespace || '')}</span>
        </div>
      </article>
    `).join('')}
  </div>`;
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
          <button class="btn btn-primary btn-sm" id="btn-timeline-refresh">${c('refresh')}</button>
        </div>
      </div>

      <div class="metric-grid metrics-row-4">
        ${metric('Status', (_timeline?.status || 'loading').toUpperCase())}
        ${metric('Stages', (_timeline?.stages || []).length)}
        ${metric('Missing', (_timeline?.missing_stages || []).length)}
        ${metric('Session', _timeline?.session_date || '-')}
      </div>

      <div class="grid-2" style="margin-top:18px">
        <section class="card">
          <div class="card-header"><span class="card-title">${c('stages')}</span>${statusBadge(_timeline?.status || 'loading')}</div>
          <div class="card-body">${renderStages()}</div>
        </section>
        <section class="card">
          <div class="card-header"><span class="card-title">${c('events')}</span>${statusBadge((_timeline?.recent_events || []).length ? 'tracked' : 'degraded')}</div>
          <div class="card-body">${renderEvents()}</div>
        </section>
      </div>
    </div>
  `;
}

async function load(container) {
  setLoading(container, getLang() === 'zh' ? '正在加载自动化时间线...' : 'Loading automation timeline...');
  try {
    _timeline = await api.trading.automationTimeline();
    container.innerHTML = shell();
    bind(container);
  } catch (error) {
    renderError(container, error, { context: 'automation-timeline', showRetry: true, onRetry: () => load(container) });
  }
}

function bind(container) {
  container.querySelector('#btn-timeline-refresh')?.addEventListener('click', () => load(container));
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
