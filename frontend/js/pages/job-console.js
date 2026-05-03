import { api } from '../qtapi.js?v=8';
import { toast } from '../components/toast.js?v=8';
import { getLang, onLangChange } from '../i18n.js?v=8';
import { emptyState, esc, metric, renderError, setLoading, statusBadge } from './workbench-utils.js?v=8';

let _container = null;
let _langCleanup = null;
let _jobs = null;
let _selectedJob = null;
let _logs = null;

const COPY = {
  en: {
    title: 'Job Console',
    subtitle: 'Async job queue for backtest, RL, data sync, report generation, and blueprint heavy runs with cancel/retry/log evidence.',
    refresh: 'Refresh Jobs',
    create: 'Create Job',
    cancel: 'Cancel',
    retry: 'Retry',
    logs: 'Logs',
    jobType: 'Job Type',
    recent: 'Recent Jobs',
    detail: 'Job Detail',
    noJobs: 'No jobs yet',
    noJobsHint: 'Create a smoke, data, backtest, report, or RL blocked job to verify queue behavior.',
  },
  zh: {
    title: 'Job 控制台',
    subtitle: '用于回测、RL、数据同步、报告生成和蓝图重任务的异步队列，带取消、重试和日志证据。',
    refresh: '刷新任务',
    create: '创建任务',
    cancel: '取消',
    retry: '重试',
    logs: '日志',
    jobType: '任务类型',
    recent: '最近任务',
    detail: '任务详情',
    noJobs: '暂无任务',
    noJobsHint: '创建冒烟、数据、回测、报告或 RL 阻断任务，验证队列行为。',
  },
};

const JOB_OPTIONS = [
  ['release_health_smoke', 'Release health smoke'],
  ['data_sync', 'Data sync'],
  ['advanced_backtest', 'Advanced backtest'],
  ['report_generation', 'Report generation'],
  ['blueprint_analysis', 'Blueprint analysis'],
  ['rl_train', 'RL train blocked check'],
];

function c(key) {
  const lang = getLang() === 'zh' ? 'zh' : 'en';
  return COPY[lang][key] || COPY.en[key] || key;
}

function payloadFor(jobType) {
  const base = { acceptance_namespace: 'ui_job_console', source: 'job_console_page' };
  const payloads = {
    release_health_smoke: base,
    data_sync: { ...base, symbols: ['AAPL', 'MSFT', 'NVDA'], loader: 'price_loader' },
    advanced_backtest: { ...base, returns: [0.01, -0.004, 0.006, 0.002, -0.003, 0.012], weights: { AAPL: 0.4, MSFT: 0.35, NVDA: 0.25 } },
    report_generation: { ...base, metrics: { sharpe: 1.2, cumulative_return: 0.08 }, report_type: 'acceptance' },
    blueprint_analysis: { ...base, family: 'technical', symbol: 'AAPL', prices: [180, 181.5, 179.2, 183.4, 184.1, 186.2] },
    rl_train: { ...base, model: 'ppo', mode: 'production_worker_required' },
  };
  return payloads[jobType] || base;
}

function renderJobs() {
  const jobs = _jobs?.jobs || [];
  if (!jobs.length) return emptyState(c('noJobs'), c('noJobsHint'));
  return `<div class="workbench-list workbench-scroll-list">
    ${jobs.map((job) => `
      <article class="workbench-item">
        <div class="workbench-item__head">
          <strong>${esc(job.job_type || '-')}</strong>
          ${statusBadge(job.status)}
        </div>
        <p>${esc(job.reason || job.error || job.result?.reason || job.result?.message || '')}</p>
        <div class="workbench-item__meta">
          <span>${esc(job.job_id)}</span>
          <span>${esc(job.updated_at || job.created_at || '-')}</span>
          <span>attempt ${esc(job.attempt || 1)}</span>
        </div>
        <div class="workbench-action-grid" style="margin-top:10px">
          <button class="workbench-action-btn" data-job-action="logs" data-job-id="${esc(job.job_id)}">${c('logs')}</button>
          <button class="workbench-action-btn" data-job-action="retry" data-job-id="${esc(job.job_id)}">${c('retry')}</button>
          <button class="workbench-action-btn" data-job-action="cancel" data-job-id="${esc(job.job_id)}">${c('cancel')}</button>
        </div>
      </article>
    `).join('')}
  </div>`;
}

function renderDetail() {
  const payload = _logs || _selectedJob;
  if (!payload) return emptyState(c('detail'), 'Select a job or create a new one.');
  return `<pre style="white-space:pre-wrap;max-height:520px;overflow:auto;font-size:11px">${esc(JSON.stringify(payload, null, 2))}</pre>`;
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
          <button class="btn btn-secondary btn-sm" id="btn-job-refresh">${c('refresh')}</button>
          <button class="btn btn-primary btn-sm" id="btn-job-smoke">${c('create')}</button>
        </div>
      </div>

      <div class="grid-2">
        <section class="card">
          <div class="card-header"><span class="card-title">${c('create')}</span>${statusBadge(_selectedJob?.status || 'idle')}</div>
          <div class="card-body">
            <label class="form-label" for="job-type-select">${c('jobType')}</label>
            <select class="form-input" id="job-type-select">
              ${JOB_OPTIONS.map(([value, label]) => `<option value="${esc(value)}">${esc(label)}</option>`).join('')}
            </select>
          </div>
        </section>
        <section class="card">
          <div class="card-header"><span class="card-title">Queue</span>${statusBadge(_jobs?.status || 'loading')}</div>
          <div class="card-body">
            <div class="workbench-metric-grid">
              ${metric('Backend', _jobs?.queue?.backend || '-')}
              ${metric('Jobs', _jobs?.count ?? '-')}
              ${metric('Worker', _jobs?.queue?.inline_worker_enabled ? 'inline' : 'queue')}
            </div>
          </div>
        </section>
      </div>

      <div class="grid-2" style="margin-top:18px">
        <section class="card">
          <div class="card-header"><span class="card-title">${c('recent')}</span>${statusBadge(_jobs?.status || 'loading')}</div>
          <div class="card-body" id="job-list">${renderJobs()}</div>
        </section>
        <section class="card">
          <div class="card-header"><span class="card-title">${c('detail')}</span>${statusBadge((_logs || _selectedJob)?.status || 'idle')}</div>
          <div class="card-body" id="job-detail">${renderDetail()}</div>
        </section>
      </div>
    </div>
  `;
}

async function load(container) {
  setLoading(container, getLang() === 'zh' ? '正在加载任务队列...' : 'Loading job queue...');
  try {
    _jobs = await api.jobs.list({ limit: 50 });
    container.innerHTML = shell();
    bind(container);
  } catch (error) {
    renderError(container, error, { context: 'job-console', showRetry: true, onRetry: () => load(container) });
  }
}

async function createJob(container) {
  const jobType = container.querySelector('#job-type-select')?.value || 'release_health_smoke';
  const detail = container.querySelector('#job-detail');
  setLoading(detail, getLang() === 'zh' ? '正在创建任务...' : 'Creating job...');
  try {
    _selectedJob = await api.jobs.create({
      job_type: jobType,
      payload: payloadFor(jobType),
    });
    _logs = null;
    toast.success(c('create'), String(_selectedJob.status || 'created'));
    await load(container);
  } catch (error) {
    renderError(detail, error, { context: 'job-create' });
    toast.error(c('create'), error.message);
  }
}

function bind(container) {
  container.querySelector('#btn-job-refresh')?.addEventListener('click', () => load(container));
  container.querySelector('#btn-job-smoke')?.addEventListener('click', () => createJob(container));
  container.querySelector('#job-list')?.addEventListener('click', async (event) => {
    const button = event.target.closest('[data-job-action]');
    if (!button) return;
    const action = button.getAttribute('data-job-action');
    const jobId = button.getAttribute('data-job-id');
    const detail = container.querySelector('#job-detail');
    setLoading(detail, getLang() === 'zh' ? '正在读取任务...' : 'Loading job...');
    try {
      if (action === 'logs') {
        _logs = await api.jobs.logs(jobId);
      } else if (action === 'retry') {
        _selectedJob = await api.jobs.retry(jobId);
        _logs = null;
      } else if (action === 'cancel') {
        _selectedJob = await api.jobs.cancel(jobId);
        _logs = null;
      }
      await load(container);
    } catch (error) {
      renderError(detail, error, { context: `job-${action}` });
      toast.error(c(action), error.message);
    }
  });
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
