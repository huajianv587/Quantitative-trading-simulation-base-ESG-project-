import { api, openExecutionWS } from '../qtapi.js?v=8';
import { toast } from '../components/toast.js?v=8';
import { getLocale, onLangChange } from '../i18n.js?v=8';

let _ws = null;
let _orders = [];
let _currentContainer = null;
let _langCleanup = null;
let _killArmed = false;

function currentMode(container = _currentContainer) {
  return container?.querySelector('#ex-mode')?.value || 'paper';
}

function currentBroker(container = _currentContainer) {
  return container?.querySelector('#ex-broker')?.value || 'alpaca';
}

function fmtMoney(value) {
  const number = Number(value || 0);
  return `$${number.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function fmtSignedMoney(value) {
  const number = Number(value || 0);
  return `${number >= 0 ? '+' : '-'}$${Math.abs(number).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function fmtPct(value) {
  const number = Number(value || 0);
  return `${number >= 0 ? '+' : ''}${(number * 100).toFixed(2)}%`;
}

function shortTime(value) {
  if (!value) return '--';
  try {
    return new Date(value).toLocaleTimeString(getLocale(), { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  } catch {
    return String(value);
  }
}

function statusClass(status) {
  if (status === 'filled') return 'filled';
  if (status === 'failed') return 'failed';
  if (status === 'cancelled' || status === 'canceled') return 'neutral';
  return 'pending';
}

function applyPrefill(container) {
  try {
    const raw = window.sessionStorage.getItem('qt.execution.prefill');
    if (!raw) return;
    const payload = JSON.parse(raw);
    if (payload.universe) container.querySelector('#ex-universe').value = payload.universe;
    if (payload.capital) container.querySelector('#ex-capital').value = payload.capital;
    if (payload.broker) container.querySelector('#ex-broker').value = payload.broker;
    window.sessionStorage.removeItem('qt.execution.prefill');
  } catch {
    window.sessionStorage.removeItem('qt.execution.prefill');
  }
}

function buildShell() {
  return `
    <div class="execution-monitor">
      <div class="execution-monitor__title-wrap">
        <div class="execution-monitor__title">执行监控</div>
        <div class="execution-monitor__sub" id="execution-monitor-sub">Real broker account sync</div>
      </div>
      <div class="execution-monitor__stats">
        <span id="ws-pill" class="live-pill live-pill--off">DISCONNECTED</span>
        <span id="monitor-mode" class="badge badge-neutral">PAPER</span>
        <span id="session-pnl" class="execution-monitor__value">$0.00</span>
      </div>
      <div class="execution-monitor__meta">
        <span id="execution-clock">--</span>
        <span id="execution-broker-meta">Alpaca · paper</span>
      </div>
    </div>

    <div class="grid-sidebar execution-grid">
      <div class="execution-left">
        <div class="run-panel">
          <div class="run-panel__header">
            <div class="run-panel__title">提交执行计划</div>
            <div class="run-panel__sub">统一走服务器已配置的 Alpaca 凭证</div>
          </div>
          <div class="run-panel__body">
            <div class="form-group">
              <label class="form-label">股票池</label>
              <input class="form-input" id="ex-universe" placeholder="AAPL, MSFT, NVDA, GOOGL (留空则用默认池)">
            </div>

            <div class="form-row">
              <div class="form-group">
                <label class="form-label">资金规模 ($)</label>
                <input class="form-input" id="ex-capital" type="number" value="1000000">
              </div>
              <div class="form-group">
                <label class="form-label">券商</label>
                <select class="form-select" id="ex-broker">
                  <option value="alpaca">Alpaca</option>
                </select>
              </div>
            </div>

            <div class="form-row">
              <div class="form-group">
                <label class="form-label">模式</label>
                <select class="form-select" id="ex-mode">
                  <option value="paper">Paper</option>
                  <option value="live">Live</option>
                </select>
              </div>
              <div class="form-group">
                <label class="form-label">提交到券商</label>
                <label class="toggle execution-toggle">
                  <input type="checkbox" id="ex-submit" checked>
                  <span class="toggle-track"></span>
                </label>
              </div>
            </div>

            <div class="broker-status-card" id="broker-status-card">
              <div class="broker-status-card__title">Broker Status</div>
              <div class="broker-status-card__body">
                <div><span class="text-muted">Account:</span> <span id="account-id">--</span></div>
                <div><span class="text-muted">Clock:</span> <span id="account-clock">--</span></div>
                <div><span class="text-muted">Warnings:</span> <span id="account-warning-count">0</span></div>
              </div>
              <div class="broker-status-card__note" id="broker-status-note">Server-side broker credentials active.</div>
            </div>
          </div>
          <div class="run-panel__foot">
            <button class="btn btn-primary btn-lg" id="btn-run-exec" style="flex:1">运行执行计划</button>
          </div>
        </div>

        <div class="card">
          <div class="card-header">
            <span class="card-title">账户资金</span>
            <button class="btn btn-ghost btn-sm" id="btn-refresh-account">刷新</button>
          </div>
          <div class="card-body">
            <div class="execution-account-grid">
              <div class="execution-account-card"><span>Equity</span><strong id="account-equity">$0.00</strong></div>
              <div class="execution-account-card"><span>Buying Power</span><strong id="account-buying-power">$0.00</strong></div>
              <div class="execution-account-card"><span>Cash</span><strong id="account-cash">$0.00</strong></div>
              <div class="execution-account-card"><span>Daily Change</span><strong id="account-daily-change">$0.00</strong></div>
            </div>
          </div>
        </div>

        <div class="card" style="border-color:rgba(255,64,96,0.22)">
          <div class="card-header" style="background:rgba(255,61,87,0.05)">
            <span class="card-title" style="color:var(--red)">紧急控制</span>
          </div>
          <div class="card-body" style="display:flex;flex-direction:column;gap:12px">
            <div class="text-muted text-sm">Kill switch 会立即取消当前挂单，并阻止新的券商提交。</div>
            <button class="kill-switch" id="btn-kill" style="width:100%;padding:10px" disabled>启用熔断开关</button>
            <div id="kill-confirm" style="display:none;flex-direction:column;gap:8px">
              <div style="font-family:var(--f-mono);font-size:11px;color:var(--red);text-align:center;padding:4px 0">确认暂停当前执行链路</div>
              <div style="display:flex;gap:8px">
                <button class="btn btn-ghost btn-sm" id="btn-kill-cancel" style="flex:1">取消</button>
                <button class="btn btn-sm" id="btn-kill-confirm" style="flex:1;background:var(--red);color:#fff;border:none">确认熔断</button>
              </div>
            </div>
            <div id="kill-activated" style="display:none;padding:12px;border-radius:8px;background:rgba(255,61,87,0.12);border:1px solid rgba(255,61,87,0.4);text-align:center">
              <div style="font-family:var(--f-display);font-size:11px;font-weight:700;color:var(--red)">KILL SWITCH ACTIVATED</div>
              <div style="font-family:var(--f-mono);font-size:10px;color:var(--red);opacity:0.7;margin-top:4px">All pending orders cancelled · No new orders</div>
            </div>
          </div>
        </div>

        <div class="card">
          <div class="card-header">
            <span class="card-title">实时持仓</span>
            <button class="btn btn-ghost btn-sm" id="btn-refresh-pos">刷新</button>
          </div>
          <div id="positions-body" class="card-body">
            <div class="text-muted text-sm">Loading...</div>
          </div>
        </div>
      </div>

      <div class="execution-right">
        <div class="results-panel">
          <div class="results-panel__header">
            <span class="card-title">订单流</span>
            <div style="display:flex;gap:10px;align-items:center">
              <span id="order-count" class="text-xs text-muted font-mono">0 orders</span>
              <select class="form-select" id="filter-status" style="padding:3px 8px;font-size:11px;height:auto;width:auto">
                <option value="all">All</option>
                <option value="filled">Filled</option>
                <option value="pending">Pending</option>
                <option value="failed">Failed</option>
                <option value="cancelled">Cancelled</option>
                <option value="canceled">Canceled</option>
              </select>
              <button class="btn btn-ghost btn-sm" id="btn-refresh-orders">刷新</button>
            </div>
          </div>
          <div class="results-panel__body" id="orders-body">
            <div class="loading-overlay" style="min-height:120px"><div class="spinner"></div><span>Loading orders...</span></div>
          </div>
        </div>

        <div class="card">
          <div class="card-header">
            <span class="card-title">实时流</span>
            <span id="feed-status" class="text-xs text-muted font-mono">connecting...</span>
          </div>
          <div id="feed-log" style="padding:12px 16px;height:220px;overflow-y:auto;display:flex;flex-direction:column-reverse;gap:0">
            <div class="text-muted text-sm">Waiting for broker events...</div>
          </div>
        </div>
      </div>
    </div>

    <div class="live-confirm-modal" id="live-confirm-modal" hidden>
      <div class="live-confirm-modal__backdrop" data-live-close></div>
      <div class="live-confirm-modal__panel">
        <div class="live-confirm-modal__title">确认 Live 下单</div>
        <div class="live-confirm-modal__body" id="live-confirm-body"></div>
        <div class="live-confirm-modal__actions">
          <button class="btn btn-ghost" id="btn-live-cancel">取消</button>
          <button class="btn btn-primary" id="btn-live-confirm">确认提交 Live</button>
        </div>
      </div>
    </div>
  `;
}

export function render(container) {
  _currentContainer = container;
  _ws?.close();
  _ws = null;
  _orders = [];
  _killArmed = false;
  container.innerHTML = buildShell();
  applyPrefill(container);
  bindEvents(container);
  loadRuntime(container);
  _langCleanup ||= onLangChange(() => {
    if (_currentContainer?.isConnected) render(_currentContainer);
  });
}

export function destroy() {
  _ws?.close();
  _ws = null;
  _orders = [];
  _killArmed = false;
  _currentContainer = null;
  _langCleanup?.();
  _langCleanup = null;
}

function bindEvents(container) {
  container.querySelector('#btn-run-exec')?.addEventListener('click', () => requestExecution(container));
  container.querySelector('#btn-refresh-orders')?.addEventListener('click', () => loadOrders(container));
  container.querySelector('#btn-refresh-pos')?.addEventListener('click', () => loadPositions(container));
  container.querySelector('#btn-refresh-account')?.addEventListener('click', () => loadAccount(container));
  container.querySelector('#filter-status')?.addEventListener('change', () => renderOrders(container));
  container.querySelector('#ex-mode')?.addEventListener('change', async () => {
    updateModeBadge(container);
    await loadRuntime(container);
  });

  const killButton = container.querySelector('#btn-kill');
  killButton?.addEventListener('click', () => {
    _killArmed = !_killArmed;
    container.querySelector('#kill-confirm').style.display = _killArmed ? 'flex' : 'none';
    killButton.textContent = _killArmed ? '等待确认...' : '启用熔断开关';
  });
  container.querySelector('#btn-kill-cancel')?.addEventListener('click', () => {
    _killArmed = false;
    container.querySelector('#kill-confirm').style.display = 'none';
    killButton.textContent = '启用熔断开关';
  });
  container.querySelector('#btn-kill-confirm')?.addEventListener('click', async () => {
    try {
      await api.execution.killSwitch(true, 'Manual operator trigger');
      toast.warning('Kill switch activated', 'All pending broker orders were halted.');
      container.querySelector('#kill-confirm').style.display = 'none';
      container.querySelector('#kill-activated').style.display = '';
      killButton.textContent = '熔断已激活';
    } catch (error) {
      toast.error('Kill switch failed', error.message || 'Unknown error');
    }
  });

  container.querySelector('#btn-live-cancel')?.addEventListener('click', hideLiveConfirm);
  container.querySelector('#btn-live-confirm')?.addEventListener('click', async () => {
    hideLiveConfirm();
    await submitExecution(container, true);
  });
  container.querySelectorAll('[data-live-close]')?.forEach((node) => {
    node.addEventListener('click', hideLiveConfirm);
  });
}

async function loadRuntime(container) {
  updateModeBadge(container);
  await loadAccount(container);
  await loadOrders(container);
  await loadPositions(container);
  connectWS(container);
}

function updateModeBadge(container) {
  const mode = currentMode(container);
  const modeBadge = container.querySelector('#monitor-mode');
  const brokerMeta = container.querySelector('#execution-broker-meta');
  if (modeBadge) {
    modeBadge.textContent = mode.toUpperCase();
    modeBadge.className = `badge ${mode === 'live' ? 'badge-failed' : 'badge-neutral'}`;
  }
  if (brokerMeta) brokerMeta.textContent = `Alpaca · ${mode}`;
}

async function loadAccount(container) {
  const broker = currentBroker(container);
  const mode = currentMode(container);
  try {
    const payload = await api.execution.account(broker, mode);
    const account = payload.account || {};
    const warnings = payload.warnings || [];
    const clock = payload.market_clock || {};

    container.querySelector('#account-id').textContent = account.account_id || '--';
    container.querySelector('#account-clock').textContent = clock.is_open ? 'MARKET OPEN' : (clock.next_open ? `Closed · next ${shortTime(clock.next_open)}` : 'Closed');
    container.querySelector('#account-warning-count').textContent = String(warnings.length);
    container.querySelector('#broker-status-note').textContent = warnings[0] || 'Server-side broker credentials active.';
    container.querySelector('#account-equity').textContent = fmtMoney(account.equity);
    container.querySelector('#account-buying-power').textContent = fmtMoney(account.buying_power);
    container.querySelector('#account-cash').textContent = fmtMoney(account.cash);
    container.querySelector('#account-daily-change').textContent = `${fmtSignedMoney(account.daily_change)} · ${fmtPct(account.daily_change_pct)}`;
    container.querySelector('#execution-clock').textContent = clock.is_open ? 'Market Open' : 'Market Closed';
    container.querySelector('#session-pnl').textContent = fmtSignedMoney(account.daily_change);
    container.querySelector('#session-pnl').style.color = Number(account.daily_change || 0) >= 0 ? 'var(--green)' : 'var(--red)';
    container.querySelector('#execution-monitor-sub').textContent = `${payload.connected ? 'Real broker account sync' : 'Broker unavailable'} · ${payload.mode || mode}`;
    container.querySelector('#btn-kill').disabled = !payload.connected;
  } catch (error) {
    container.querySelector('#broker-status-note').textContent = error.message || 'Could not load broker account.';
    toast.error('Account sync failed', error.message || 'Unknown error');
  }
}

async function requestExecution(container) {
  const mode = currentMode(container);
  const submitOrders = container.querySelector('#ex-submit').checked;
  if (mode === 'live' && submitOrders) {
    openLiveConfirm(container);
    return;
  }
  await submitExecution(container, false);
}

function openLiveConfirm(container) {
  const modal = container.querySelector('#live-confirm-modal');
  const capital = Number(container.querySelector('#ex-capital').value || 0);
  const universe = container.querySelector('#ex-universe').value.trim() || 'default universe';
  const body = container.querySelector('#live-confirm-body');
  body.innerHTML = `
    <div>Mode: <strong>LIVE</strong></div>
    <div>Broker: <strong>${currentBroker(container)}</strong></div>
    <div>Universe: <strong>${universe}</strong></div>
    <div>Capital Base: <strong>${fmtMoney(capital)}</strong></div>
    <div>Guardrail: <strong>Medium gate</strong></div>
    <div style="color:var(--amber)">This submission will require server-side live routing permission and will be fully audited.</div>
  `;
  modal.hidden = false;
}

function hideLiveConfirm() {
  _currentContainer?.querySelector('#live-confirm-modal')?.setAttribute('hidden', '');
}

async function submitExecution(container, liveConfirmed) {
  const button = container.querySelector('#btn-run-exec');
  button.disabled = true;
  button.textContent = 'Submitting...';

  const universeInput = container.querySelector('#ex-universe').value.trim();
  const payload = {
    universe: universeInput ? universeInput.split(/[,\s]+/).filter(Boolean).map((value) => value.toUpperCase()) : [],
    capital_base: Number(container.querySelector('#ex-capital').value || 1000000),
    broker: currentBroker(container),
    mode: currentMode(container),
    submit_orders: container.querySelector('#ex-submit').checked,
    allow_duplicates: true,
    live_confirmed: !!liveConfirmed,
    operator_confirmation: liveConfirmed ? 'front_end_live_confirm_modal' : '',
  };

  try {
    const response = await api.execution.paper(payload);
    toast.success('Execution plan submitted', `${response.orders?.length || 0} orders staged`);
    if (response.mode === 'live' && !response.submitted && response.broker_status === 'awaiting_live_confirmation') {
      toast.warning('Live routing still gated', (response.warnings || [])[0] || 'Confirmation required.');
    }
    await loadRuntime(container);
    connectWS(container, response.execution_id);
  } catch (error) {
    toast.error('Execution failed', error.message || 'Unknown error');
  } finally {
    button.disabled = false;
    button.textContent = '运行执行计划';
  }
}

async function loadOrders(container) {
  const broker = currentBroker(container);
  const mode = currentMode(container);
  try {
    const data = await api.execution.orders(broker, 'all', 100, mode);
    _orders = data.orders || [];
    renderOrders(container);
  } catch (error) {
    container.querySelector('#orders-body').innerHTML = `
      <div class="empty-state" style="min-height:120px">
        <div class="empty-state__title">无法加载订单</div>
        <div class="empty-state__text">${error.message || 'Unknown error'}</div>
      </div>
    `;
  }
}

function renderOrders(container) {
  const body = container.querySelector('#orders-body');
  const filter = container.querySelector('#filter-status')?.value || 'all';
  const filtered = filter === 'all' ? _orders : _orders.filter((item) => item.status === filter);
  container.querySelector('#order-count').textContent = `${filtered.length} orders`;

  if (!filtered.length) {
    body.innerHTML = `
      <div class="empty-state" style="min-height:120px">
        <div class="empty-state__title">当前没有订单</div>
        <div class="empty-state__text">订单为空时显示空状态，不再显示 File not found。</div>
      </div>
    `;
    return;
  }

  body.innerHTML = `
    <div class="tbl-wrap"><table>
      <thead>
        <tr><th>Symbol</th><th>Side</th><th>Qty</th><th>Status</th><th>Fill</th><th>Limit</th><th>Type</th><th>Time</th></tr>
      </thead>
      <tbody>
        ${filtered.map((order) => `
          <tr>
            <td class="cell-symbol">${order.symbol || '--'}</td>
            <td><span class="badge badge-${order.side === 'buy' ? 'long' : 'short'}">${String(order.side || '').toUpperCase()}</span></td>
            <td class="cell-num">${order.qty || order.quantity || '--'}</td>
            <td><span class="badge badge-${statusClass(order.status)}">${String(order.status || '').toUpperCase()}</span></td>
            <td class="cell-num">${order.fill_price ? fmtMoney(order.fill_price) : '--'}</td>
            <td class="cell-num">${order.limit_price ? fmtMoney(order.limit_price) : '--'}</td>
            <td class="text-dim text-sm">${order.order_type || order.type || '--'}</td>
            <td class="text-dim text-sm">${shortTime(order.submitted_at || order.created_at)}</td>
          </tr>
        `).join('')}
      </tbody>
    </table></div>
  `;
}

async function loadPositions(container) {
  const broker = currentBroker(container);
  const mode = currentMode(container);
  const target = container.querySelector('#positions-body');
  try {
    const payload = await api.execution.positions(broker, mode);
    const positions = payload.positions || [];
    if (!positions.length) {
      target.innerHTML = `<div class="empty-state" style="min-height:100px"><div class="empty-state__title">当前无持仓</div><div class="empty-state__text">空仓时显示空状态。</div></div>`;
      return;
    }
    target.innerHTML = `
      <div class="tbl-wrap"><table>
        <thead><tr><th>Symbol</th><th>Qty</th><th>Side</th><th>Market Value</th><th>P&L</th></tr></thead>
        <tbody>
          ${positions.map((position) => {
            const pnl = Number(position.unrealized_pl || 0);
            return `
              <tr>
                <td class="cell-symbol">${position.symbol || '--'}</td>
                <td>${position.qty || '--'}</td>
                <td>${position.side || 'long'}</td>
                <td>${position.market_value ? fmtMoney(position.market_value) : '--'}</td>
                <td class="${pnl >= 0 ? 'pos' : 'neg'}">${position.unrealized_pl ? fmtSignedMoney(position.unrealized_pl) : '--'}</td>
              </tr>
            `;
          }).join('')}
        </tbody>
      </table></div>
    `;
  } catch (error) {
    target.innerHTML = `<div class="empty-state" style="min-height:100px"><div class="empty-state__title">持仓读取失败</div><div class="empty-state__text">${error.message || 'Unknown error'}</div></div>`;
  }
}

function connectWS(container, executionId = null) {
  const broker = currentBroker(container);
  const mode = currentMode(container);
  const pill = container.querySelector('#ws-pill');
  const feedLog = container.querySelector('#feed-log');
  const status = container.querySelector('#feed-status');
  _ws?.close();

  _ws = openExecutionWS(broker, executionId, 20, (msg) => {
    if (pill) {
      pill.textContent = 'LIVE';
      pill.className = 'live-pill';
    }
    if (status) status.textContent = 'live';
    if (feedLog) {
      const entry = document.createElement('div');
      const eventStatus = String(msg.status || '').toUpperCase();
      entry.style.cssText = 'padding:4px 0;border-bottom:1px solid rgba(255,255,255,0.03);font-family:var(--f-mono);font-size:11px';
      entry.innerHTML = `<span style="color:var(--text-dim)">${shortTime(msg.timestamp)}</span> <span>${msg.symbol || msg.type || '--'}</span> <span style="color:${eventStatus === 'FILLED' ? 'var(--green)' : eventStatus === 'FAILED' ? 'var(--red)' : 'var(--text-secondary)'}">${eventStatus || '--'}</span>`;
      feedLog.prepend(entry);
    }
  }, () => {
    if (pill) {
      pill.textContent = 'DISCONNECTED';
      pill.className = 'live-pill live-pill--off';
    }
    if (status) status.textContent = 'disconnected';
  }, mode);
}
