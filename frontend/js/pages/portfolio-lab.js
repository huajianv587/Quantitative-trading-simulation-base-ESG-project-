import { api } from '../api.js';
import { toastError, toastSuccess } from '../components/toast.js';

let cleanup = [];
let lastPayload = null;
let lastExecutionResult = null;
let refreshInterval = null;

export async function render(container) {
  container.innerHTML = buildHTML();
  setupEventListeners(container);
  await refreshBrokerPanels(container, { silent: true });

  refreshInterval = window.setInterval(() => {
    refreshBrokerPanels(container, { silent: true }).catch(() => {});
  }, 30000);
  cleanup.push(() => window.clearInterval(refreshInterval));
}

export function destroy() {
  cleanup.forEach((fn) => fn());
  cleanup = [];
  lastPayload = null;
  lastExecutionResult = null;
  refreshInterval = null;
}

function buildHTML() {
  return `
    <div class="page-stack">
      <section class="page-hero">
        <div>
          <h2>Execution Control Center</h2>
          <p>Turn ESG multi-factor research into a broker-aware paper execution workflow with clear guardrails, readiness checks, and artifact tracking.</p>
        </div>
        <div class="text-sm text-[var(--text-secondary)]">Research to Portfolio to Broker to Storage</div>
      </section>

      <section class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4" id="execution-readiness">
        ${buildStatusCard('App Mode', '--', 'Waiting for runtime status', 'neutral')}
        ${buildStatusCard('LLM Backend', '--', 'Waiting for health probe', 'neutral')}
        ${buildStatusCard('Broker Credentials', '--', 'Waiting for broker probe', 'warning')}
        ${buildStatusCard('Artifact Backend', '--', 'Will reflect the latest execution artifact sink', 'neutral')}
      </section>

      <div class="grid grid-cols-1 xl:grid-cols-[1.08fr_0.92fr] gap-4">
        <div class="card">
          <div class="flex items-center justify-between gap-3 mb-4">
            <div>
              <h3 class="text-lg font-semibold">Strategy Input</h3>
              <p class="text-sm text-[var(--text-secondary)] mt-1">Build the portfolio first, then optionally submit a tiny paper order batch once the current runtime can really see broker credentials.</p>
            </div>
            <span class="badge badge-info">Paper First</span>
          </div>

          <div class="space-y-4">
            <div>
              <label class="block text-sm font-medium mb-2">Universe</label>
              <input id="portfolio-universe" type="text" class="w-full" placeholder="AAPL,MSFT,TSLA,NVDA" value="AAPL,MSFT,TSLA" />
            </div>

            <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label class="block text-sm font-medium mb-2">Benchmark</label>
                <input id="portfolio-benchmark" type="text" class="w-full" value="SPY" />
              </div>
              <div>
                <label class="block text-sm font-medium mb-2">Capital Base</label>
                <input id="portfolio-capital" type="number" class="w-full" value="1000000" />
              </div>
              <div>
                <label class="block text-sm font-medium mb-2">Mode</label>
                <select id="portfolio-mode" class="w-full">
                  <option value="paper" selected>paper</option>
                  <option value="live">live (guarded)</option>
                </select>
              </div>
            </div>

            <div>
              <label class="block text-sm font-medium mb-2">Research Intent</label>
              <textarea id="portfolio-intent" rows="4" class="w-full" placeholder="Focus on quality, governance resilience, and ESG momentum while keeping single-name concentration controlled."></textarea>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div class="card-elevated status-card status-card--accent">
                <div class="flex items-center justify-between gap-3">
                  <div>
                    <div class="text-sm font-semibold">Submit to Alpaca</div>
                    <div class="text-xs text-[var(--text-muted)] mt-1">Leave this off to stay in plan mode. Turn it on only after the broker console confirms credentials are loaded in the current process.</div>
                  </div>
                  <label class="inline-flex items-center gap-2 text-sm">
                    <input id="submit-orders" type="checkbox" class="accent-[var(--accent)]" />
                    <span>Enable</span>
                  </label>
                </div>
                <div id="submit-orders-help" class="text-xs text-[var(--text-secondary)] mt-3">Current status unknown. Refresh the broker console to verify runtime readiness.</div>
              </div>

              <div class="card-elevated status-card status-card--warning">
                <div class="flex items-center justify-between gap-3">
                  <div>
                    <div class="text-sm font-semibold">Execution Guardrails</div>
                    <div class="text-xs text-[var(--text-muted)] mt-1">By default the workflow limits order count and keeps notionals tiny so paper validation stays controlled.</div>
                  </div>
                  <span class="badge badge-warning">Safe Test Size</span>
                </div>
              </div>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div>
                <label class="block text-sm font-medium mb-2">Max Orders</label>
                <input id="max-orders" type="number" min="1" max="5" class="w-full" value="2" />
              </div>
              <div>
                <label class="block text-sm font-medium mb-2">Per-Order Notional</label>
                <input id="per-order-notional" type="number" min="1" step="0.01" class="w-full" value="1.00" />
              </div>
              <div>
                <label class="block text-sm font-medium mb-2">Order Type</label>
                <select id="order-type" class="w-full">
                  <option value="market" selected>market</option>
                  <option value="limit">limit</option>
                </select>
              </div>
              <div>
                <label class="block text-sm font-medium mb-2">Time In Force</label>
                <select id="time-in-force" class="w-full">
                  <option value="day" selected>day</option>
                  <option value="gtc">gtc</option>
                </select>
              </div>
            </div>

            <div class="flex flex-col gap-3 md:flex-row">
              <button id="optimize-portfolio-btn" class="btn-secondary flex-1">Optimize Portfolio</button>
              <button id="generate-execution-btn" class="btn-primary flex-1">Build / Submit Execution</button>
              <button id="refresh-broker-btn" class="btn-secondary">Refresh Broker</button>
            </div>
          </div>
        </div>

        <div class="card">
          <div class="flex items-center justify-between gap-3 mb-4">
            <div>
              <h3 class="text-lg font-semibold">Broker Console</h3>
              <p class="text-sm text-[var(--text-secondary)] mt-1">See whether the current runtime can reach Alpaca paper trading, what buying power is available, and whether the market clock is open.</p>
            </div>
            <span id="broker-connection-pill" class="badge badge-warning">Checking</span>
          </div>

          <div id="broker-account-grid" class="grid grid-cols-1 md:grid-cols-2 gap-3">
            ${buildMetricCard('Connection', 'Checking', 'Waiting for account probe')}
            ${buildMetricCard('Buying Power', '--', 'Paper account snapshot')}
            ${buildMetricCard('Equity', '--', 'Latest equity reported by broker')}
            ${buildMetricCard('Market Clock', '--', 'Will show open or closed status')}
          </div>

          <div id="execution-checks" class="space-y-3 mt-4">
            <div class="card-elevated text-sm text-[var(--text-secondary)]">No execution checks yet.</div>
          </div>
        </div>
      </div>

      <div class="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <div class="card">
          <div class="flex items-center justify-between gap-3 mb-4">
            <h3 class="text-lg font-semibold">Execution Snapshot</h3>
            <span class="badge badge-info">Latest Run</span>
          </div>
          <div id="execution-run-summary" class="space-y-3">
            <div class="card-elevated text-sm text-[var(--text-secondary)]">No execution has been generated yet.</div>
          </div>
        </div>

        <div class="card">
          <div class="flex items-center justify-between gap-3 mb-4">
            <h3 class="text-lg font-semibold">Portfolio Preview</h3>
            <span class="badge badge-info">Target Weights</span>
          </div>
          <div id="portfolio-position-list" class="space-y-3">
            <div class="card-elevated text-sm text-[var(--text-secondary)]">Run optimization to populate target positions.</div>
          </div>
        </div>
      </div>

      <div class="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <div class="card">
          <div class="flex items-center justify-between gap-3 mb-4">
            <h3 class="text-lg font-semibold">Execution Orders</h3>
            <span class="badge badge-success">Paper Routing</span>
          </div>
          <div id="execution-order-list" class="space-y-3">
            <div class="card-elevated text-sm text-[var(--text-secondary)]">Generate an execution plan to inspect orders and broker receipts.</div>
          </div>
        </div>

        <div class="card">
          <div class="flex items-center justify-between gap-3 mb-4">
            <h3 class="text-lg font-semibold">Recent Broker Orders</h3>
            <span class="badge badge-info">Live Feed</span>
          </div>
          <div id="recent-broker-orders" class="space-y-3">
            <div class="card-elevated text-sm text-[var(--text-secondary)]">No broker orders loaded yet.</div>
          </div>
        </div>
      </div>

      <div class="card">
        <div class="flex items-center justify-between gap-3 mb-4">
          <h3 class="text-lg font-semibold">Paper Positions</h3>
          <span class="badge badge-warning">Broker Inventory</span>
        </div>
        <div id="paper-positions" class="space-y-3">
          <div class="card-elevated text-sm text-[var(--text-secondary)]">No positions loaded yet.</div>
        </div>
      </div>
    </div>
  `;
}

function setupEventListeners(container) {
  const optimizeBtn = container.querySelector('#optimize-portfolio-btn');
  const executionBtn = container.querySelector('#generate-execution-btn');
  const refreshBtn = container.querySelector('#refresh-broker-btn');

  const optimize = async () => {
    optimizeBtn.disabled = true;
    optimizeBtn.textContent = 'Optimizing...';

    try {
      lastPayload = getPayload(container);
      const result = await api.quant.optimizePortfolio(lastPayload);
      renderPortfolio(container, result);
      toastSuccess('Portfolio optimization completed.', 'Portfolio Ready');
    } catch (error) {
      toastError(error.message, 'Optimization Failed');
    } finally {
      optimizeBtn.disabled = false;
      optimizeBtn.textContent = 'Optimize Portfolio';
    }
  };

  const execute = async () => {
    executionBtn.disabled = true;
    executionBtn.textContent = 'Submitting...';

    try {
      const payload = { ...(lastPayload || getPayload(container)), ...getExecutionOptions(container) };
      const result = await api.quant.createExecutionPlan(payload);
      renderExecution(container, result);
      await refreshBrokerPanels(container, { silent: true });
      if (result.submitted) {
        toastSuccess('Paper orders submitted to Alpaca.', 'Execution Submitted');
      } else {
        toastSuccess('Execution plan generated successfully.', 'Execution Ready');
      }
    } catch (error) {
      toastError(error.message, 'Execution Failed');
    } finally {
      executionBtn.disabled = false;
      executionBtn.textContent = 'Build / Submit Execution';
    }
  };

  const refresh = async () => {
    refreshBtn.disabled = true;
    refreshBtn.textContent = 'Refreshing...';
    try {
      await refreshBrokerPanels(container, { silent: false });
    } finally {
      refreshBtn.disabled = false;
      refreshBtn.textContent = 'Refresh Broker';
    }
  };

  optimizeBtn.addEventListener('click', optimize);
  executionBtn.addEventListener('click', execute);
  refreshBtn.addEventListener('click', refresh);

  cleanup.push(() => optimizeBtn.removeEventListener('click', optimize));
  cleanup.push(() => executionBtn.removeEventListener('click', execute));
  cleanup.push(() => refreshBtn.removeEventListener('click', refresh));
}

function getPayload(container) {
  return {
    universe: splitUniverse(container.querySelector('#portfolio-universe').value),
    benchmark: container.querySelector('#portfolio-benchmark').value.trim() || 'SPY',
    capital_base: Number(container.querySelector('#portfolio-capital').value) || 1000000,
    research_question: container.querySelector('#portfolio-intent').value.trim(),
  };
}

function getExecutionOptions(container) {
  return {
    mode: container.querySelector('#portfolio-mode').value || 'paper',
    submit_orders: Boolean(container.querySelector('#submit-orders').checked),
    max_orders: Number(container.querySelector('#max-orders').value) || 2,
    per_order_notional: Number(container.querySelector('#per-order-notional').value) || 1,
    order_type: container.querySelector('#order-type').value || 'market',
    time_in_force: container.querySelector('#time-in-force').value || 'day',
    extended_hours: false,
  };
}

async function refreshBrokerPanels(container, { silent = false } = {}) {
  try {
    const [health, account, orders, positions] = await Promise.all([
      api.system.health(),
      api.quant.getExecutionAccount(),
      api.quant.listExecutionOrders('all', 10),
      api.quant.listExecutionPositions(),
    ]);

    renderReadiness(container, health, account);
    renderBrokerAccount(container, account);
    renderRecentBrokerOrders(container, orders.orders || []);
    renderBrokerPositions(container, positions.positions || []);
    syncSubmitToggleState(container, account);

    if (!lastExecutionResult) {
      renderExecutionSummary(container, null);
    }

    if (!silent) {
      toastSuccess('Broker console refreshed.', 'Broker Ready');
    }
  } catch (error) {
    renderReadiness(container, null, { connected: false, broker_connection: { configured: false } });
    renderBrokerAccount(container, {
      connected: false,
      warnings: [error.message],
      broker_connection: { configured: false },
    });
    syncSubmitToggleState(container, { connected: false, broker_connection: { configured: false }, warnings: [error.message] });
    if (!silent) {
      toastError(error.message, 'Broker Refresh Failed');
    }
  }
}

function renderReadiness(container, healthPayload, accountPayload) {
  const runtime = healthPayload?.runtime || {};
  const brokerConnection = accountPayload?.broker_connection || {};
  const brokerConfigured = Boolean(brokerConnection.configured);
  const artifactBackend = lastExecutionResult?.storage?.artifact_backend || 'pending';

  container.querySelector('#execution-readiness').innerHTML = [
    buildStatusCard('App Mode', healthPayload?.app_mode || '--', 'Current backend deployment mode', healthPayload?.ready ? 'success' : 'warning'),
    buildStatusCard(
      'LLM Backend',
      runtime.llm_backend_mode || '--',
      runtime.remote_llm_configured ? 'Remote pipeline configured' : 'Running on fallback or local mode',
      runtime.remote_llm_configured ? 'success' : 'warning',
    ),
    buildStatusCard(
      'Broker Credentials',
      brokerConfigured ? 'Loaded' : 'Missing',
      brokerConfigured ? 'Runtime can attempt Alpaca paper calls' : 'Current process cannot see Alpaca credentials',
      brokerConfigured ? 'success' : 'danger',
    ),
    buildStatusCard(
      'Artifact Backend',
      artifactBackend,
      lastExecutionResult?.storage?.artifact_uri || 'Will populate after the next execution run',
      artifactBackend === 'supabase_storage' ? 'success' : artifactBackend === 'pending' ? 'neutral' : 'warning',
    ),
  ].join('');
}

function renderPortfolio(container, result) {
  const portfolio = result.portfolio || {};
  container.querySelector('#portfolio-position-list').innerHTML = (portfolio.positions || []).map((position) => `
    <article class="card-elevated status-card status-card--accent">
      <div class="flex items-center justify-between gap-3">
        <h3 class="text-lg font-semibold">${position.symbol} / ${position.company_name}</h3>
        <span class="badge badge-info">${formatPercent(position.weight)}</span>
      </div>
      <p class="text-sm text-[var(--text-secondary)] mt-3">${position.thesis}</p>
      <div class="grid grid-cols-2 gap-3 mt-4 text-sm">
        <div>Expected Return <strong>${formatPercent(position.expected_return)}</strong></div>
        <div>Risk Budget <strong>${formatPercent(position.risk_budget)}</strong></div>
        <div>Score <strong>${Number(position.score || 0).toFixed(1)}</strong></div>
        <div>Side <strong>${position.side}</strong></div>
      </div>
    </article>
  `).join('') || `
    <div class="card-elevated text-sm text-[var(--text-secondary)]">No optimized positions returned.</div>
  `;
}

function renderExecution(container, result) {
  lastExecutionResult = result;
  renderExecutionChecks(container, result);
  renderExecutionSummary(container, result);
  syncSubmitToggleState(container, {
    connected: Boolean(result?.broker_connection?.configured),
    broker_connection: result?.broker_connection || {},
    warnings: result?.warnings || [],
  });

  container.querySelector('#execution-order-list').innerHTML = (result.orders || []).map((order) => `
    <article class="card-elevated status-card ${order.status === 'planned' ? 'status-card--warning' : 'status-card--success'}">
      <div class="flex items-center justify-between gap-3">
        <h3 class="text-lg font-semibold">${order.symbol}</h3>
        <span class="badge ${order.side === 'buy' ? 'badge-success' : 'badge-danger'}">${order.side}</span>
      </div>
      <div class="grid grid-cols-2 gap-3 mt-4 text-sm">
        <div>Qty <strong>${order.quantity}</strong></div>
        <div>Target <strong>${formatPercent(order.target_weight)}</strong></div>
        <div>Ref Price <strong>${formatCurrency(order.limit_price)}</strong></div>
        <div>Type <strong>${order.order_type || 'market'}</strong></div>
        <div>Notional <strong>${order.notional ? formatCurrency(order.notional) : '--'}</strong></div>
        <div>Status <strong>${order.status || 'planned'}</strong></div>
      </div>
      ${order.client_order_id ? `<div class="text-xs text-[var(--text-muted)] mt-3">Client Order ID: ${order.client_order_id}</div>` : ''}
      ${order.broker_order_id ? `<div class="text-xs text-[var(--text-muted)] mt-1">Broker Order ID: ${order.broker_order_id}</div>` : ''}
      <p class="text-sm text-[var(--text-secondary)] mt-3">${order.rationale}</p>
    </article>
  `).join('') || `
    <div class="card-elevated text-sm text-[var(--text-secondary)]">No execution orders generated.</div>
  `;
}

function renderExecutionChecks(container, result) {
  const checks = [
    ...(result.compliance_checks || []),
    ...(result.warnings || []),
    ...((result.broker_errors || []).map((item) => `Broker error: ${item}`)),
  ];

  container.querySelector('#execution-checks').innerHTML = checks.map((check) => `
    <div class="card-elevated text-sm">${check}</div>
  `).join('') || '<div class="card-elevated text-sm text-[var(--text-secondary)]">No execution checks available.</div>';
}

function renderExecutionSummary(container, result) {
  const target = container.querySelector('#execution-run-summary');
  if (!result) {
    target.innerHTML = '<div class="card-elevated text-sm text-[var(--text-secondary)]">No execution has been generated yet.</div>';
    return;
  }

  const storage = result.storage || {};
  const warnings = result.warnings || [];
  target.innerHTML = `
    <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
      ${buildMetricCard('Execution ID', result.execution_id || '--', 'Persisted execution record')}
      ${buildMetricCard('Broker Status', result.broker_status || '--', 'Plan-only or submitted')}
      ${buildMetricCard('Submitted', result.submitted ? 'Yes' : 'No', result.submitted ? 'Orders were routed to broker' : 'Execution remained in planning mode')}
      ${buildMetricCard('Artifact Backend', storage.artifact_backend || '--', storage.artifact_key || 'No artifact key yet')}
    </div>
    <div class="card-elevated mt-3">
      <div class="text-sm font-semibold">Run Notes</div>
      <div class="text-sm text-[var(--text-secondary)] mt-2">
        Generated at <strong>${formatDateTime(result.generated_at)}</strong> via <strong>${result.broker || 'execution engine'}</strong>.
      </div>
      ${storage.artifact_uri ? `<div class="text-xs text-[var(--text-muted)] mt-3 break-all">Artifact URI: ${storage.artifact_uri}</div>` : ''}
      ${warnings.length ? `<div class="text-xs text-[var(--text-muted)] mt-3">${warnings.join(' | ')}</div>` : ''}
    </div>
  `;
}

function renderBrokerAccount(container, accountPayload) {
  const connected = Boolean(accountPayload?.connected);
  const account = accountPayload?.account || {};
  const clock = accountPayload?.market_clock || {};
  const warnings = accountPayload?.warnings || [];
  const pill = container.querySelector('#broker-connection-pill');

  pill.className = `badge ${connected ? 'badge-success' : 'badge-warning'}`;
  pill.textContent = connected ? 'Connected' : 'Plan Mode';

  container.querySelector('#broker-account-grid').innerHTML = `
    ${buildMetricCard('Connection', connected ? 'Connected' : 'Not Ready', connected ? 'Alpaca paper API reachable' : 'Credentials missing or broker probe failed')}
    ${buildMetricCard('Buying Power', account.buying_power ? formatCurrency(account.buying_power) : '--', 'Paper account buying power')}
    ${buildMetricCard('Equity', account.equity ? formatCurrency(account.equity) : '--', 'Latest broker equity snapshot')}
    ${buildMetricCard('Market Clock', clock.is_open === true ? 'Open' : clock.is_open === false ? 'Closed' : '--', clock.timestamp || 'Clock unavailable')}
  `;

  if (!lastExecutionResult) {
    container.querySelector('#execution-checks').innerHTML = warnings.map((warning) => `
      <div class="card-elevated text-sm">${warning}</div>
    `).join('') || '<div class="card-elevated text-sm text-[var(--text-secondary)]">Broker ready. Waiting for the next execution request.</div>';
  }
}

function renderRecentBrokerOrders(container, orders) {
  container.querySelector('#recent-broker-orders').innerHTML = orders.map((order) => `
    <article class="card-elevated status-card ${resolveRecentOrderTone(order.status)}">
      <div class="flex items-center justify-between gap-3">
        <h3 class="text-lg font-semibold">${order.symbol || 'Order'}</h3>
        <span class="badge ${resolveOrderBadge(order.status)}">${order.status || 'unknown'}</span>
      </div>
      <div class="grid grid-cols-2 gap-3 mt-4 text-sm">
        <div>Side <strong>${order.side || '--'}</strong></div>
        <div>Type <strong>${order.type || '--'}</strong></div>
        <div>Qty <strong>${order.qty || '--'}</strong></div>
        <div>Notional <strong>${order.notional ? formatCurrency(order.notional) : '--'}</strong></div>
        <div>Filled Qty <strong>${order.filled_qty || '--'}</strong></div>
        <div>Avg Fill <strong>${order.filled_avg_price ? formatCurrency(order.filled_avg_price) : '--'}</strong></div>
      </div>
      <div class="text-xs text-[var(--text-muted)] mt-3">${formatDateTime(order.submitted_at)}</div>
    </article>
  `).join('') || `
    <div class="card-elevated text-sm text-[var(--text-secondary)]">No recent broker orders.</div>
  `;
}

function renderBrokerPositions(container, positions) {
  container.querySelector('#paper-positions').innerHTML = positions.map((position) => `
    <article class="card-elevated status-card status-card--accent">
      <div class="flex items-center justify-between gap-3">
        <h3 class="text-lg font-semibold">${position.symbol}</h3>
        <span class="badge badge-info">${position.side || 'long'}</span>
      </div>
      <div class="grid grid-cols-2 gap-3 mt-4 text-sm">
        <div>Qty <strong>${position.qty || '--'}</strong></div>
        <div>Avg Entry <strong>${position.avg_entry_price ? formatCurrency(position.avg_entry_price) : '--'}</strong></div>
        <div>Market Value <strong>${position.market_value ? formatCurrency(position.market_value) : '--'}</strong></div>
        <div>Unrealized P/L <strong>${position.unrealized_pl || '--'}</strong></div>
      </div>
    </article>
  `).join('') || `
    <div class="card-elevated text-sm text-[var(--text-secondary)]">No paper positions currently open.</div>
  `;
}

function syncSubmitToggleState(container, accountPayload) {
  const submitToggle = container.querySelector('#submit-orders');
  const submitHelp = container.querySelector('#submit-orders-help');
  const brokerConfigured = Boolean(accountPayload?.broker_connection?.configured);
  const warnings = accountPayload?.warnings || [];

  submitToggle.dataset.brokerConfigured = brokerConfigured ? 'true' : 'false';
  submitHelp.textContent = brokerConfigured
    ? 'Broker credentials are visible to the current runtime. Tiny paper submissions are allowed if you keep guardrails on.'
    : (warnings[0] || 'The current runtime cannot see Alpaca credentials, so submission will stay in plan-only mode.');
}

function buildMetricCard(label, value, hint) {
  return `
    <div class="card-elevated">
      <div class="text-sm text-[var(--text-muted)]">${label}</div>
      <div class="text-2xl font-bold mt-2">${value}</div>
      <div class="text-xs text-[var(--text-secondary)] mt-2">${hint}</div>
    </div>
  `;
}

function buildStatusCard(label, value, hint, tone = 'neutral') {
  const toneClass = {
    success: 'status-card--success',
    warning: 'status-card--warning',
    danger: 'status-card--danger',
    accent: 'status-card--accent',
    neutral: '',
  }[tone] || '';

  return `
    <div class="card-elevated status-card ${toneClass}">
      <div class="text-sm text-[var(--text-muted)]">${label}</div>
      <div class="text-2xl font-bold mt-2">${value}</div>
      <div class="text-xs text-[var(--text-secondary)] mt-2 break-all">${hint}</div>
    </div>
  `;
}

function splitUniverse(raw) {
  return String(raw || '')
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);
}

function formatPercent(value) {
  return `${(Number(value || 0) * 100).toFixed(2)}%`;
}

function formatCurrency(value) {
  if (value === null || value === undefined || value === '') return '--';
  return `$${Number(value).toFixed(2)}`;
}

function formatDateTime(value) {
  if (!value) return 'No timestamp reported';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString();
}

function resolveOrderBadge(status) {
  const normalized = String(status || '').toLowerCase();
  if (['filled', 'partially_filled', 'accepted', 'new'].includes(normalized)) return 'badge-success';
  if (['canceled', 'expired', 'rejected', 'suspended'].includes(normalized)) return 'badge-danger';
  return 'badge-warning';
}

function resolveRecentOrderTone(status) {
  const normalized = String(status || '').toLowerCase();
  if (['filled', 'accepted', 'new', 'partially_filled'].includes(normalized)) return 'status-card--success';
  if (['canceled', 'expired', 'rejected', 'suspended'].includes(normalized)) return 'status-card--danger';
  return 'status-card--warning';
}
