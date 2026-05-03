import { api } from '../qtapi.js?v=8';
import { toast } from '../components/toast.js?v=8';
import { getLang, getLocale, onLangChange } from '../i18n.js?v=8';
import {
  emptyState,
  esc,
  metric,
  miniMetric,
  renderError,
  setLoading,
  splitTokens,
  statusBadge,
} from './workbench-utils.js?v=8';

let _container = null;
let _langCleanup = null;
let _pollTimer = null;
let _activeJobId = '';
let _lastRegistry = null;
let _lastQuota = null;
let _lastRuns = null;
let _lastJob = null;

const COPY = {
  en: {
    title: 'Data Management',
    subtitle: 'Source registry, sync jobs, quota guard, and ingestion runs.',
    syncTitle: 'Sync Control',
    syncSub: 'Start a real company snapshot refresh job and monitor it live.',
    companies: 'Companies / Tickers',
    companiesPlaceholder: 'Tesla\nMicrosoft\nNVIDIA',
    sources: 'Provider focus (optional)',
    sourcesPlaceholder: 'alpaca_market, sec_edgar, local_esg',
    forceRefresh: 'Force refresh',
    startSync: 'Start Sync',
    refreshAll: 'Refresh All',
    syncing: 'Starting...',
    activeJob: 'Active Job',
    noJobs: 'No active sync job yet.',
    registry: 'Source Registry',
    registrySub: 'Real provider configuration, quota posture, and capabilities.',
    runs: 'Recent Ingestion Runs',
    runsSub: 'Latest connector and evidence runs stored by the backend.',
    metrics: 'Source Health',
    metricsSub: 'Live summary of provider readiness and quota guard.',
    configured: 'Configured',
    providers: 'Providers',
    quota: 'Quota Guard',
    runsCount: 'Recent Runs',
    protected: 'protected',
    disabled: 'disabled',
    nextAction: 'Next Action',
    nextActionHint: 'Start a sync job or inspect a provider row to review readiness and fallback posture.',
    warning: 'Warning',
    noRuns: 'No connector runs are available yet.',
    syncStarted: 'Sync started',
    syncComplete: 'Sync complete',
    syncErrors: 'Sync completed with errors',
    syncFailed: 'Sync failed',
    syncErrorTitle: 'Sync request failed',
    syncErrorDetail: 'The backend rejected the sync request. Check service readiness and admin credentials.',
    updatedAt: 'Updated',
    total: 'Total',
    synced: 'Synced',
    failed: 'Failed',
    runId: 'Run ID',
    mode: 'Mode',
    scope: 'Scope',
    symbolCount: 'Symbols',
    items: 'Items',
    status: 'Status',
    sourceChain: 'Capabilities',
    refreshed: 'Data source views refreshed',
    missingCompanies: 'Enter at least one company or ticker',
    staleRefreshing: 'Showing the latest saved state while refreshing...',
  },
  zh: {
    title: '数据管理',
    subtitle: '真实数据源注册表、同步作业、配额保护与摄取运行记录。',
    syncTitle: '同步控制',
    syncSub: '启动真实公司快照刷新作业，并实时查看进度。',
    companies: '公司 / 股票代码',
    companiesPlaceholder: 'Tesla\nMicrosoft\nNVIDIA',
    sources: '数据源焦点（可选）',
    sourcesPlaceholder: 'alpaca_market, sec_edgar, local_esg',
    forceRefresh: '强制刷新',
    startSync: '开始同步',
    refreshAll: '刷新全部',
    syncing: '正在启动...',
    activeJob: '当前作业',
    noJobs: '还没有活动中的同步作业。',
    registry: '数据源注册表',
    registrySub: '真实 provider 配置、配额状态与能力说明。',
    runs: '最近摄取运行',
    runsSub: '后端已保存的连接器与证据运行记录。',
    metrics: '数据源健康概览',
    metricsSub: 'Provider readiness 与配额保护的实时摘要。',
    configured: '已配置',
    providers: '数据源',
    quota: '配额保护',
    runsCount: '最近运行',
    protected: '已保护',
    disabled: '已关闭',
    nextAction: '下一步动作',
    nextActionHint: '启动同步作业，或检查数据源行来确认 readiness 与 fallback 姿态。',
    warning: '警告',
    noRuns: '还没有可显示的连接器运行记录。',
    syncStarted: '同步已启动',
    syncComplete: '同步完成',
    syncErrors: '同步完成，但存在错误',
    syncFailed: '同步失败',
    syncErrorTitle: '同步请求失败',
    syncErrorDetail: '后端拒绝了同步请求。请检查服务 readiness 与管理员凭证。',
    updatedAt: '更新时间',
    total: '总数',
    synced: '成功',
    failed: '失败',
    runId: '运行 ID',
    mode: '模式',
    scope: '范围',
    symbolCount: '标的数',
    items: '条目',
    status: '状态',
    sourceChain: '能力',
    refreshed: '数据源视图已刷新',
    missingCompanies: '请至少输入一个公司或股票代码',
    staleRefreshing: '先展示最近保存的状态，再在后台刷新...',
  },
};

function c(key) {
  const lang = getLang() === 'zh' ? 'zh' : 'en';
  return COPY[lang][key] || COPY.en[key] || key;
}

function isMounted() {
  return Boolean(_container && _container.isConnected);
}

function parseCompanies(raw) {
  return splitTokens(raw || '', { delimiters: /[\n,]+/ });
}

function parseProviders(raw) {
  return splitTokens(raw || '', { delimiters: /[\n,\s]+/ });
}

function safeArray(value) {
  return Array.isArray(value) ? value : [];
}

function formatTimestamp(value) {
  if (!value) return '-';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return String(value);
  return parsed.toLocaleString(getLocale(), {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function buildShell() {
  return `
    <div class="page-header">
      <div>
        <div class="page-header__title">${c('title')}</div>
        <div class="page-header__sub">${c('subtitle')}</div>
      </div>
      <div class="page-header__actions">
        <button class="btn btn-ghost btn-sm" id="btn-refresh-all">${c('refreshAll')}</button>
      </div>
    </div>

    <div class="grid-sidebar" style="align-items:start">
      <div style="display:flex;flex-direction:column;gap:14px;min-width:0">
        <section class="run-panel">
          <div class="run-panel__header">
            <div class="run-panel__title">${c('syncTitle')}</div>
            <div class="run-panel__sub">${c('syncSub')}</div>
          </div>
          <div class="run-panel__body">
            <div class="form-group">
              <label class="form-label">${c('companies')}</label>
              <textarea class="form-textarea" id="sync-companies" rows="5" placeholder="${c('companiesPlaceholder')}">Tesla
Microsoft
NVIDIA</textarea>
            </div>
            <div class="form-group">
              <label class="form-label">${c('sources')}</label>
              <input class="form-input" id="sync-sources" placeholder="${c('sourcesPlaceholder')}" value="alpaca_market, sec_edgar, local_esg">
            </div>
            <div class="form-group" style="flex-direction:row;align-items:center;justify-content:space-between">
              <label class="form-label" style="margin:0">${c('forceRefresh')}</label>
              <label class="toggle">
                <input type="checkbox" id="sync-force">
                <span class="toggle-track"></span>
              </label>
            </div>
            <div class="workbench-kv-list" style="margin-top:8px">
              <div class="workbench-kv-row">
                <span>${c('nextAction')}</span>
                <strong>${c('nextActionHint')}</strong>
              </div>
            </div>
          </div>
          <div class="run-panel__foot workbench-action-grid">
            <button class="btn btn-primary btn-lg workbench-action-btn" id="sync-btn">${c('startSync')}</button>
          </div>
        </section>

        <section class="card">
          <div class="card-header">
            <span class="card-title">${c('activeJob')}</span>
            <span id="job-count" style="font-size:10px;color:var(--text-dim);font-family:var(--f-mono)"></span>
          </div>
          <div class="card-body" id="sync-body">
            ${emptyState(c('noJobs'))}
          </div>
        </section>

        <section class="card">
          <div class="card-header">
            <span class="card-title">${c('runs')}</span>
            <span style="font-size:10px;color:var(--text-dim);font-family:var(--f-mono)">${c('runsSub')}</span>
          </div>
          <div class="card-body" id="runs-body">
            ${emptyState(c('noRuns'))}
          </div>
        </section>
      </div>

      <div style="display:flex;flex-direction:column;gap:14px;min-width:0">
        <section class="card">
          <div class="card-header">
            <span class="card-title">${c('metrics')}</span>
            <span style="font-size:10px;color:var(--text-dim);font-family:var(--f-mono)">${c('metricsSub')}</span>
          </div>
          <div class="card-body" id="metrics-body">
            <div class="workbench-metric-grid">
              ${metric(c('providers'), '-', '')}
              ${metric(c('configured'), '-', '')}
              ${metric(c('quota'), '-', '')}
              ${metric(c('runsCount'), '-', '')}
            </div>
          </div>
        </section>

        <section class="run-panel connector-registry-panel">
          <div class="run-panel__header">
            <div class="run-panel__title">${c('registry')}</div>
            <div class="run-panel__sub">${c('registrySub')}</div>
          </div>
          <div class="run-panel__body connector-registry-body" id="registry-body">
            ${emptyState('Loading registry...')}
          </div>
        </section>
      </div>
    </div>`;
}

export async function render(container) {
  destroy();
  _container = container;
  _container.innerHTML = buildShell();
  bindEvents();
  _langCleanup = onLangChange(() => {
    if (!isMounted()) return;
    const companies = _container.querySelector('#sync-companies')?.value || '';
    const sources = _container.querySelector('#sync-sources')?.value || '';
    const forceRefresh = Boolean(_container.querySelector('#sync-force')?.checked);
    _container.innerHTML = buildShell();
    bindEvents();
    _container.querySelector('#sync-companies').value = companies;
    _container.querySelector('#sync-sources').value = sources;
    _container.querySelector('#sync-force').checked = forceRefresh;
    renderMetrics();
    renderRegistry();
    renderRuns();
    renderJob();
  });
  await refreshAll({ silent: false });
}

export function destroy() {
  if (_pollTimer) {
    window.clearInterval(_pollTimer);
    _pollTimer = null;
  }
  _container = null;
  _lastJob = null;
  _langCleanup?.();
  _langCleanup = null;
}

function bindEvents() {
  if (!_container) return;
  _container.querySelector('#btn-refresh-all')?.addEventListener('click', () => refreshAll({ silent: false }));
  _container.querySelector('#sync-btn')?.addEventListener('click', () => startSync());
}

async function refreshAll(options = {}) {
  if (!isMounted()) return;
  if (!options.silent) {
    setLoading(_container.querySelector('#registry-body'), 'Loading registry...');
    _container.querySelector('#runs-body').innerHTML = emptyState(c('staleRefreshing'));
  }

  const [registryResult, quotaResult, runsResult] = await Promise.allSettled([
    api.connectors.registry(),
    api.connectors.quota(),
    api.connectors.runs(8),
  ]);

  if (!isMounted()) return;

  _lastRegistry = registryResult.status === 'fulfilled' ? registryResult.value : null;
  _lastQuota = quotaResult.status === 'fulfilled' ? quotaResult.value : null;
  _lastRuns = runsResult.status === 'fulfilled' ? runsResult.value : null;

  renderMetrics();
  renderRegistry();
  renderRuns();

  if (!options.silent) {
    const errors = [registryResult, quotaResult, runsResult].filter((item) => item.status === 'rejected');
    if (errors.length) {
      toast.error(c('warning'), errors.map((item) => item.reason?.message || String(item.reason || '')).join(' / '));
    } else {
      toast.success(c('refreshAll'), c('refreshed'));
    }
  }
}

function renderMetrics() {
  if (!_container) return;
  const target = _container.querySelector('#metrics-body');
  const providers = safeArray(_lastRegistry?.providers);
  const quotaProviders = safeArray(_lastQuota?.providers);
  const configured = providers.filter((item) => item.configured).length;
  const guarded = quotaProviders.every((item) => item.quota_mode === 'free_tier_guarded') && quotaProviders.length > 0;
  const runsCount = safeArray(_lastRuns?.runs).length;
  target.innerHTML = `
    <div class="workbench-metric-grid">
      ${metric(c('providers'), providers.length, providers.length ? 'positive' : '')}
      ${metric(c('configured'), configured, configured ? 'positive' : '')}
      ${metric(c('quota'), guarded ? c('protected') : c('disabled'), guarded ? 'positive' : 'negative')}
      ${metric(c('runsCount'), runsCount, runsCount ? 'positive' : '')}
    </div>`;
}

function renderRegistry() {
  if (!_container) return;
  const target = _container.querySelector('#registry-body');
  if (!_lastRegistry) {
    renderError(target, new Error('Provider registry unavailable'));
    return;
  }

  const quotaMap = new Map(
    safeArray(_lastQuota?.providers).map((row) => [row.provider, row]),
  );

  const rows = safeArray(_lastRegistry.providers).map((row) => {
    const quota = quotaMap.get(row.provider_id) || {};
    const capabilities = safeArray(row.capabilities).slice(0, 4);
    return `
      <article class="live-provider-card">
        <div class="live-provider-card__head">
          <strong>${esc(row.display_name)}</strong>
          ${statusBadge(row.configured ? 'configured' : 'missing_key')}
        </div>
        <p>${esc(row.free_tier_note || '')}</p>
        <div class="workbench-mini-grid">
          ${miniMetric(c('mode'), esc(String(_lastRegistry.mode || 'free_tier_first').replace(/_/g, '-')))}
          ${miniMetric('daily', row.daily_limit ?? '-')}
          ${miniMetric('scan', row.scan_budget ?? '-')}
          ${miniMetric('left', quota.remaining_estimate ?? '-')}
        </div>
        <div class="workbench-kv-list">
          <div class="workbench-kv-row">
            <span>${c('status')}</span>
            <strong>${row.configured ? c('configured') : 'missing key'}</strong>
          </div>
          <div class="workbench-kv-row">
            <span>${c('sourceChain')}</span>
            <strong>${capabilities.length ? esc(capabilities.join(', ')) : '-'}</strong>
          </div>
          <div class="workbench-kv-row">
            <span>${c('updatedAt')}</span>
            <strong>${formatTimestamp(quota.reset_at_utc)}</strong>
          </div>
        </div>
      </article>`;
  }).join('');

  target.innerHTML = `
    <div class="connector-provider-shell">
      <div class="live-provider-grid connector-provider-scroll">${rows || emptyState(c('providers'))}</div>
    </div>`;
}

function renderRuns() {
  if (!_container) return;
  const target = _container.querySelector('#runs-body');
  const runs = safeArray(_lastRuns?.runs);
  if (!runs.length) {
    target.innerHTML = emptyState(c('noRuns'));
    return;
  }

  target.innerHTML = runs.map((run) => {
    const summary = run.summary || {};
    const universe = safeArray(run.universe);
    return `
      <div class="workbench-item">
        <div class="workbench-item__head">
          <strong>${esc(run.run_id || '-')}</strong>
          ${statusBadge(summary.failed ? 'failed' : 'ready')}
        </div>
        <div class="workbench-item__summary">${esc((run.lineage || []).join(' -> ') || 'connector run')}</div>
        <div class="workbench-mini-grid">
          ${miniMetric(c('mode'), run.mode || '-')}
          ${miniMetric(c('symbolCount'), universe.length)}
          ${miniMetric(c('items'), safeArray(run.items).length)}
          ${miniMetric(c('updatedAt'), formatTimestamp(run.generated_at))}
        </div>
      </div>`;
  }).join('');
}

function renderJob() {
  if (!_container) return;
  const target = _container.querySelector('#sync-body');
  const countEl = _container.querySelector('#job-count');
  if (!_activeJobId) {
    countEl.textContent = '';
    target.innerHTML = emptyState(c('noJobs'));
    return;
  }

  const job = _lastJob;
  if (!job) {
    countEl.textContent = _activeJobId;
    target.innerHTML = emptyState(c('activeJob'), _activeJobId);
    return;
  }

  const total = Number(job.companies_total || job.companies_to_sync || 0);
  const synced = Number(job.companies_synced || 0);
  const failed = Number(job.companies_failed || 0);
  const status = String(job.status || '').toLowerCase();
  const terminal = ['completed', 'completed_with_errors', 'succeeded', 'failed', 'degraded', 'blocked', 'cancelled'].includes(status);
  const complete = total > 0 ? Math.min(100, Math.round(((synced + failed) / total) * 100)) : (terminal ? 100 : 5);
  const done = terminal;
  countEl.textContent = done ? '' : _activeJobId;
  target.innerHTML = `
    <div style="display:flex;flex-direction:column;gap:12px">
      <div style="display:flex;justify-content:space-between;align-items:center;gap:8px">
        <strong style="font-family:var(--f-mono);font-size:11px">${esc(job.job_id || _activeJobId)}</strong>
        ${statusBadge(job.status || 'pending')}
      </div>
      <div style="background:rgba(255,255,255,0.06);border-radius:4px;height:8px;overflow:hidden">
        <div style="width:${complete}%;height:100%;background:${done ? 'var(--green)' : 'var(--amber)'};transition:width 0.35s ease"></div>
      </div>
      <div class="workbench-mini-grid">
        ${miniMetric(c('total'), total || '-')}
        ${miniMetric(c('synced'), synced)}
        ${miniMetric(c('failed'), failed)}
        ${miniMetric(c('updatedAt'), formatTimestamp(job.updated_at))}
      </div>
    </div>`;
}

async function startSync() {
  if (!isMounted()) return;
  const btn = _container.querySelector('#sync-btn');
  const companies = parseCompanies(_container.querySelector('#sync-companies')?.value || '');
  const providers = parseProviders(_container.querySelector('#sync-sources')?.value || '');
  const forceRefresh = Boolean(_container.querySelector('#sync-force')?.checked);

  if (!companies.length) {
    toast.error(c('syncErrorTitle'), c('missingCompanies'));
    return;
  }

  btn.disabled = true;
  btn.textContent = c('syncing');
  try {
    const response = await api.jobs.create({
      job_type: 'data_sync',
      payload: {
        symbols: companies,
        providers,
        force_refresh: forceRefresh,
        loader: 'data_management_ui',
      },
    });
    _activeJobId = response.job_id;
    _lastJob = normalizeSyncJob(response, companies.length);
    renderJob();
    toast.success(c('syncStarted'), response.job_id);
    pollStatus(response.job_id);
  } catch (error) {
    _lastJob = null;
    _activeJobId = '';
    renderJob();
    const target = _container.querySelector('#sync-body');
    target.innerHTML = emptyState(c('syncErrorTitle'), `${c('syncErrorDetail')} ${error.message || ''}`.trim());
    toast.error(c('syncFailed'), error.message || c('syncErrorDetail'));
  } finally {
    btn.disabled = false;
    btn.textContent = c('startSync');
  }
}

function pollStatus(jobId) {
  if (_pollTimer) {
    window.clearInterval(_pollTimer);
    _pollTimer = null;
  }

  const handleStatus = (status) => {
    if (!isMounted()) return;
    _lastJob = normalizeSyncJob(status);
    _activeJobId = status.job_id || jobId;
    renderJob();
    const normalized = String(status.status || '').toLowerCase();
    if (['completed', 'completed_with_errors', 'succeeded', 'failed', 'degraded', 'blocked', 'cancelled'].includes(normalized)) {
      window.clearInterval(_pollTimer);
      _pollTimer = null;
      if (['failed', 'degraded', 'blocked', 'cancelled', 'completed_with_errors'].includes(normalized)) {
        toast.error(c('syncErrors'), `${_lastJob.companies_failed || 0} failed`);
      } else {
        toast.success(c('syncComplete'), `${_lastJob.companies_synced || 0}/${_lastJob.companies_total || 0}`);
      }
      refreshAll({ silent: true });
    }
  };

  _pollTimer = window.setInterval(async () => {
    try {
      const status = await api.jobs.get(jobId);
      handleStatus(status);
    } catch (error) {
      window.clearInterval(_pollTimer);
      _pollTimer = null;
      if (!isMounted()) return;
      toast.error(c('syncFailed'), error.message || c('syncErrorDetail'));
    }
  }, 1200);
}

function normalizeSyncJob(job, fallbackTotal = 0) {
  const result = job?.result || {};
  const dataset = result.dataset || {};
  const payload = job?.payload || {};
  const symbols = payload.symbols || payload.companies || [];
  const total = Number(job?.companies_total || dataset.symbol_count || (Array.isArray(symbols) ? symbols.length : fallbackTotal) || fallbackTotal || 0);
  const terminal = ['succeeded', 'completed'].includes(String(job?.status || '').toLowerCase());
  return {
    ...job,
    companies_total: total,
    companies_synced: Number(job?.companies_synced || dataset.record_count || (terminal ? total : 0) || 0),
    companies_failed: Number(job?.companies_failed || (['failed', 'blocked'].includes(String(job?.status || '').toLowerCase()) ? total : 0) || 0),
    updated_at: job?.updated_at || job?.finished_at || new Date().toISOString(),
  };
}
