import { api } from '../qtapi.js?v=8';
import { toast } from '../components/toast.js?v=8';
import { getLang, onLangChange } from '../i18n.js?v=8';
import { emptyState, esc, metric, renderError, setLoading, statusBadge } from './workbench-utils.js?v=8';

let _container = null;
let _langCleanup = null;
let _schema = null;
let _release = null;
let _smoke = null;

const COPY = {
  en: {
    title: 'Release Health',
    subtitle: 'One-screen production readiness for API, UI, schema, job queue, data config, trading safety, and E2E evidence.',
    refresh: 'Refresh Health',
    smoke: 'Run Job Smoke',
    schema: 'Schema Health',
    release: 'Release Checks',
    latest: 'Latest Evidence',
    noEvidence: 'No smoke job has run from this page yet.',
    migration: 'Migration',
    remoteProbe: 'Remote Probe',
    nextActions: 'Next Actions',
  },
  zh: {
    title: '发布健康检查',
    subtitle: '集中查看 API、网页、Schema、Job 队列、数据配置、交易安全和 E2E 验收证据。',
    refresh: '刷新健康状态',
    smoke: '运行 Job 冒烟',
    schema: 'Schema 健康',
    release: '发布检查',
    latest: '最新证据',
    noEvidence: '本页面尚未运行冒烟任务。',
    migration: '迁移文件',
    remoteProbe: '远端探测',
    nextActions: '下一步动作',
  },
};

function c(key) {
  const lang = getLang() === 'zh' ? 'zh' : 'en';
  return COPY[lang][key] || COPY.en[key] || key;
}

function summarizeCheck(value) {
  if (!value || typeof value !== 'object') return { status: 'degraded', reason: 'No check payload returned.' };
  return {
    status: value.status || value.overall_status || 'ready',
    reason: value.reason || value.remote_probe_error || '',
    next_actions: value.next_actions || [],
  };
}

function renderSchemaTables() {
  const tables = _schema?.tables || [];
  if (!tables.length) return emptyState(c('schema'), 'No schema table report returned.');
  return `<div class="workbench-list workbench-scroll-list">
    ${tables.map((row) => `
      <article class="workbench-item">
        <div class="workbench-item__head">
          <strong>${esc(row.table)}</strong>
          ${statusBadge(row.status)}
        </div>
        <p>${esc(row.reason || '')}</p>
        <div class="workbench-item__meta">
          <span>${esc(c('migration'))}: ${esc(row.migration_ready ? row.migration_file : 'missing')}</span>
          <span>${esc(c('remoteProbe'))}: ${esc(row.remote_probe_status || '-')}</span>
        </div>
        ${(row.next_actions || []).length ? `<div class="token-preview">${row.next_actions.map((item) => `<span class="token-chip token-chip--risk">${esc(item)}</span>`).join('')}</div>` : ''}
      </article>
    `).join('')}
  </div>`;
}

function renderReleaseChecks() {
  const checks = _release?.checks || {};
  const entries = Object.entries(checks);
  if (!entries.length) return emptyState(c('release'), 'No release checks returned.');
  return `<div class="workbench-metric-grid">
    ${entries.map(([key, value]) => {
      const check = summarizeCheck(value);
      return `<article class="workbench-metric-card">
        <div class="workbench-metric-card__label">${esc(key.replace(/_/g, ' '))}</div>
        <div class="workbench-metric-card__value">${esc(String(check.status).toUpperCase())}</div>
        <div style="font-size:11px;color:var(--text-dim)">${esc(check.reason || (check.next_actions || [])[0] || 'ok')}</div>
      </article>`;
    }).join('')}
  </div>`;
}

function renderEvidence() {
  if (!_smoke) return emptyState(c('latest'), c('noEvidence'));
  return `<pre style="white-space:pre-wrap;max-height:360px;overflow:auto;font-size:11px">${esc(JSON.stringify(_smoke, null, 2))}</pre>`;
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
          <button class="btn btn-secondary btn-sm" id="btn-ops-health-refresh">${c('refresh')}</button>
          <button class="btn btn-primary btn-sm" id="btn-ops-run-smoke">${c('smoke')}</button>
        </div>
      </div>

      <div class="metric-grid metrics-row-4">
        ${metric('Release', (_release?.status || 'loading').toUpperCase())}
        ${metric('Schema', (_schema?.status || 'loading').toUpperCase())}
        ${metric('Tables', _schema?.summary?.table_count ?? '-')}
        ${metric('Ready', _schema?.summary?.ready ?? '-')}
      </div>

      <div class="grid-2" style="margin-top:18px">
        <section class="card">
          <div class="card-header"><span class="card-title">${c('release')}</span>${statusBadge(_release?.status || 'loading')}</div>
          <div class="card-body">${renderReleaseChecks()}</div>
        </section>
        <section class="card">
          <div class="card-header"><span class="card-title">${c('latest')}</span>${statusBadge(_smoke?.status || 'idle')}</div>
          <div class="card-body" id="ops-health-evidence">${renderEvidence()}</div>
        </section>
      </div>

      <section class="card" style="margin-top:18px">
        <div class="card-header"><span class="card-title">${c('schema')}</span>${statusBadge(_schema?.status || 'loading')}</div>
        <div class="card-body" id="ops-health-schema">${renderSchemaTables()}</div>
      </section>
    </div>
  `;
}

function bind(container) {
  container.querySelector('#btn-ops-health-refresh')?.addEventListener('click', () => load(container));
  container.querySelector('#btn-ops-run-smoke')?.addEventListener('click', async () => {
    const evidence = container.querySelector('#ops-health-evidence');
    setLoading(evidence, getLang() === 'zh' ? '正在运行 Job 冒烟...' : 'Running job smoke...');
    try {
      _smoke = await api.jobs.create({
        job_type: 'release_health_smoke',
        payload: { source: 'ops_health_page' },
      });
      container.innerHTML = shell();
      bind(container);
      toast.success(c('smoke'), String(_smoke.status || 'completed'));
    } catch (error) {
      renderError(evidence, error, { context: 'ops-health-smoke' });
      toast.error(c('smoke'), error.message);
    }
  });
}

async function load(container) {
  setLoading(container, getLang() === 'zh' ? '正在加载发布健康...' : 'Loading release health...');
  try {
    [_schema, _release] = await Promise.all([
      api.platform.schemaHealth(),
      api.platform.releaseHealth(),
    ]);
    container.innerHTML = shell();
    bind(container);
  } catch (error) {
    renderError(container, error, { context: 'ops-health', showRetry: true, onRetry: () => load(container) });
  }
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
