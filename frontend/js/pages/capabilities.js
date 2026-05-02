import { api } from '../qtapi.js?v=8';
import { toast } from '../components/toast.js?v=8';

let _state = null;

function esc(value) {
  return String(value ?? '').replace(/[&<>"']/g, (ch) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  }[ch]));
}

function statusClass(status) {
  if (status === 'ready') return 'positive';
  if (status === 'blocked') return 'risk';
  return 'warn';
}

function moduleCards() {
  const modules = _state?.modules || [];
  if (!modules.length) {
    return '<div class="empty-state"><div class="empty-state__title">No capability report yet</div><div class="empty-state__text">Backend capability status is unavailable.</div></div>';
  }
  return modules.map((item) => {
    const missing = [
      ...((item.dependencies || {}).missing_required || []),
      ...((item.dependencies || {}).missing_optional || []),
      ...(item.config_gaps || []),
    ];
    return `
      <div class="card">
        <div class="card-header">
          <span class="card-title">${esc(item.title || item.module)}</span>
          <span class="badge badge-${statusClass(item.status)}">${esc(String(item.status || '').toUpperCase())}</span>
        </div>
        <div class="card-body" style="display:flex;flex-direction:column;gap:12px">
          <div class="workbench-kv-row"><span>Route</span><strong>${esc(item.web_route)}</strong></div>
          <div class="workbench-kv-row"><span>Production</span><strong>${item.production_ready ? 'ready' : 'blocked'}</strong></div>
          <div>
            <div class="form-label">Capabilities</div>
            <div style="display:flex;gap:6px;flex-wrap:wrap">
              ${(item.capabilities || []).map((cap) => `<span class="mcc-tag">${esc(cap)}</span>`).join('')}
            </div>
          </div>
          <div>
            <div class="form-label">Gaps</div>
            <div style="font-size:11px;color:var(--text-dim);font-family:var(--f-mono)">
              ${missing.length ? missing.map(esc).join(', ') : 'none'}
            </div>
          </div>
        </div>
      </div>
    `;
  }).join('');
}

function resultBox(payload) {
  return `<pre style="white-space:pre-wrap;max-height:360px;overflow:auto;font-size:11px">${esc(JSON.stringify(payload, null, 2))}</pre>`;
}

function shell() {
  return `
    <div class="page-header">
      <div>
        <div class="page-header__title">Blueprint Capabilities</div>
        <div class="page-header__sub">Production readiness, module execution, and degraded-state visibility</div>
      </div>
      <div class="page-header__actions">
        <button class="btn btn-primary btn-sm" id="btn-capabilities-refresh">Refresh Capabilities</button>
      </div>
    </div>

    <div class="metric-grid metrics-row-4">
      <div class="metric-card">
        <div class="metric-label">Overall Status</div>
        <div class="metric-value">${esc((_state?.overall_status || 'loading').toUpperCase())}</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">Modules</div>
        <div class="metric-value">${(_state?.modules || []).length}</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">Ready</div>
        <div class="metric-value">${(_state?.modules || []).filter((item) => item.status === 'ready').length}</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">Degraded</div>
        <div class="metric-value">${(_state?.modules || []).filter((item) => item.status === 'degraded').length}</div>
      </div>
    </div>

    <div class="workbench-action-grid" style="margin:18px 0">
      <button class="workbench-action-btn workbench-action-btn--primary" id="btn-run-blueprint-analysis">Run Analysis</button>
      <button class="workbench-action-btn" id="btn-run-blueprint-model">Train Model</button>
      <button class="workbench-action-btn" id="btn-run-blueprint-data">Run Data Pipeline</button>
      <button class="workbench-action-btn" id="btn-run-blueprint-risk">Evaluate Risk</button>
      <button class="workbench-action-btn" id="btn-run-blueprint-backtest">Advanced Backtest</button>
      <button class="workbench-action-btn" id="btn-run-blueprint-infra">Check Infrastructure</button>
      <button class="workbench-action-btn" id="btn-run-blueprint-reporting">Build Reporting</button>
    </div>

    <div class="grid-2">
      <section>
        <div class="grid-2" id="capability-modules">${moduleCards()}</div>
      </section>
      <section class="card">
        <div class="card-header">
          <span class="card-title">Latest Run Result</span>
          <span class="badge badge-neutral" id="capability-result-status">idle</span>
        </div>
        <div class="card-body" id="capability-result">
          <div class="empty-state">
            <div class="empty-state__title">No run evidence yet</div>
            <div class="empty-state__text">Awaiting latest endpoint result.</div>
          </div>
        </div>
      </section>
    </div>
  `;
}

async function load(container) {
  _state = await api.blueprint.capabilities();
  container.innerHTML = shell();
  bind(container);
}

async function runAction(container, label, fn) {
  const result = container.querySelector('#capability-result');
  const status = container.querySelector('#capability-result-status');
  result.innerHTML = '<div class="empty-state"><div class="empty-state__title">Running</div></div>';
  status.textContent = 'running';
  try {
    const payload = await fn();
    status.textContent = String(payload.status || payload.overall_status || 'completed');
    result.innerHTML = resultBox(payload);
    toast.success(label, 'completed');
  } catch (error) {
    status.textContent = 'failed';
    result.innerHTML = resultBox({ status: 'failed', error: error.message });
    toast.error(label, error.message);
  }
}

function bind(container) {
  container.querySelector('#btn-capabilities-refresh')?.addEventListener('click', () => load(container));
  container.querySelector('#btn-run-blueprint-analysis')?.addEventListener('click', () => runAction(container, 'Analysis', () => api.blueprint.analysisRun({
    family: 'technical',
    symbol: 'AAPL',
    prices: [180, 181.5, 179.2, 183.4, 184.1, 186.2, 185.6, 188.4, 190.1, 191.3, 193.0],
  })));
  container.querySelector('#btn-run-blueprint-model')?.addEventListener('click', () => runAction(container, 'Model training', () => api.blueprint.modelTrain({
    model_key: 'web_linear_alpha',
    X: [[1, 0.2], [0.8, 0.1], [1.2, 0.3], [0.7, -0.1]],
    y: [0.03, 0.018, 0.041, 0.004],
  })));
  container.querySelector('#btn-run-blueprint-data')?.addEventListener('click', () => runAction(container, 'Data pipeline', () => api.blueprint.dataPipelineRun({
    symbols: ['AAPL', 'MSFT', 'NVDA'],
    loader: 'price_loader',
  })));
  container.querySelector('#btn-run-blueprint-risk')?.addEventListener('click', () => runAction(container, 'Risk evaluation', () => api.blueprint.riskEvaluate({
    nav: [1.0, 0.98, 1.02, 0.97, 1.04],
    max_drawdown_limit: 0.08,
    returns: [0.01, -0.02, 0.04, -0.01],
  })));
  container.querySelector('#btn-run-blueprint-backtest')?.addEventListener('click', () => runAction(container, 'Advanced backtest', () => api.blueprint.advancedBacktestRun({
    returns: [0.01, -0.004, 0.006, 0.002, -0.003, 0.012],
    weights: { AAPL: 0.35, MSFT: 0.4, NVDA: 0.25 },
    notional: 100000,
  })));
  container.querySelector('#btn-run-blueprint-infra')?.addEventListener('click', () => runAction(container, 'Infrastructure check', () => api.blueprint.infrastructureCheck({
    metrics: { population_drift: 0.08, run_cost_usd: 12, budget_usd: 100, trial_count: 5, best_score: 0.74 },
  })));
  container.querySelector('#btn-run-blueprint-reporting')?.addEventListener('click', () => runAction(container, 'Reporting', () => api.blueprint.reportingBuild({
    metrics: { sharpe: 1.2, cumulative_return: 0.08 },
  })));
}

export async function render(container) {
  container.innerHTML = shell();
  bind(container);
  await load(container);
}
