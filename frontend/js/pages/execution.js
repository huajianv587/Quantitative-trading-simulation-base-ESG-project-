import { api, openExecutionWS } from '../qtapi.js?v=8';
import { toast } from '../components/toast.js?v=8';
import { getLocale, onLangChange, translateLoose } from '../i18n.js?v=8';

let _ws        = null;
let _orders    = [];
let _killArmed = false;
let _currentContainer = null;
let _langCleanup = null;

export function render(container) {
  _currentContainer = container;
  _ws?.close(); _ws = null;
  container.innerHTML = buildShell();
  bindEvents(container);
  applyPrefill(container);
  loadOrders(container);
  loadPositions(container);
  connectWS(container);
  _langCleanup ||= onLangChange(() => {
    if (_currentContainer?.isConnected) render(_currentContainer);
  });
}

export function destroy() {
  _ws?.close(); _ws = null;
  _orders    = [];
  _killArmed = false;
  _currentContainer = null;
  _langCleanup?.();
  _langCleanup = null;
}

function applyPrefill(container) {
  try {
    const raw = window.sessionStorage.getItem('qt.execution.prefill');
    if (!raw) return;
    const p = JSON.parse(raw);
    if (p.universe) container.querySelector('#ex-universe').value = p.universe;
    if (p.capital)  container.querySelector('#ex-capital').value  = p.capital;
    if (p.broker)   container.querySelector('#ex-broker').value   = p.broker;
    window.sessionStorage.removeItem('qt.execution.prefill');
  } catch (_) { window.sessionStorage.removeItem('qt.execution.prefill'); }
}

/* ════════════════════════════════════════════ SHELL */
function buildShell() {
  return `
  <!-- Header status bar -->
  <div style="display:flex;align-items:center;justify-content:space-between;padding:14px 20px;margin-bottom:16px;background:rgba(7,7,15,0.7);border:1px solid var(--border-subtle);border-radius:12px;backdrop-filter:blur(24px)">
    <div>
      <span style="font-family:var(--f-display);font-size:14px;font-weight:700;letter-spacing:0.06em">EXECUTION MONITOR</span>
    </div>
    <div style="display:flex;align-items:center;gap:16px">
      <span id="ws-pill" class="live-pill live-pill--off">DISCONNECTED</span>
      <span id="session-pnl" style="font-family:var(--f-display);font-size:16px;font-weight:700;color:var(--green)">$0.00</span>
    </div>
    <div style="display:flex;gap:8px;align-items:center">
      <span style="font-family:var(--f-mono);font-size:10px;color:var(--text-dim)">Alpaca Paper · NYSE</span>
      <button class="kill-switch" id="btn-kill-header" style="padding:6px 16px;font-size:8.5px" disabled>⚠ KILL SWITCH</button>
    </div>
  </div>

  <div class="grid-sidebar" style="align-items:start">
    <!-- LEFT -->
    <div style="display:flex;flex-direction:column;gap:14px">
      <!-- Submit panel -->
      <div class="run-panel">
        <div class="run-panel__header">
          <div class="run-panel__title">Submit Execution Plan</div>
          <div class="run-panel__sub">Alpaca Paper Trading</div>
        </div>
        <div class="run-panel__body">
          <div class="form-group">
            <label class="form-label">Universe</label>
            <input class="form-input" id="ex-universe" placeholder="AAPL, MSFT… (blank = default)">
          </div>
          <div class="form-row">
            <div class="form-group">
              <label class="form-label">Capital ($)</label>
              <input class="form-input" id="ex-capital" type="number" value="1000000">
            </div>
            <div class="form-group">
              <label class="form-label">Broker</label>
              <select class="form-select" id="ex-broker">
                <option value="alpaca">Alpaca Paper</option>
                <option value="alpaca_live" disabled>Alpaca Live</option>
              </select>
            </div>
          </div>

          <!-- Alpaca API credentials (stored locally) -->
          <div class="alpaca-key-section">
            <div class="alpaca-key-header">
              <span style="color:var(--amber);font-size:11px">🔑</span>
              <span style="font-family:var(--f-display);font-size:10px;font-weight:600;letter-spacing:0.06em">ALPACA API CREDENTIALS</span>
              <span id="alpaca-key-status" class="alpaca-key-badge" style="display:none">✓ SET</span>
            </div>
            <div class="form-group" style="margin-bottom:8px">
              <label class="form-label">API Key ID</label>
              <input class="form-input" id="ex-alpaca-key" type="password" placeholder="PKXXXXX… (optional, stored locally)" autocomplete="off">
            </div>
            <div class="form-group" style="margin-bottom:0">
              <label class="form-label">Secret Key</label>
              <input class="form-input" id="ex-alpaca-secret" type="password" placeholder="Enter secret key…" autocomplete="off">
            </div>
            <div style="font-family:var(--f-mono);font-size:9px;color:var(--text-dim);margin-top:6px;line-height:1.5">
              Credentials stored in browser only · Never sent to third parties · Used by backend to connect Alpaca Paper Trading
            </div>
          </div>

          <div class="form-group" style="display:flex;align-items:center;gap:10px">
            <label class="form-label" style="margin:0;flex:1">Submit Orders to Broker</label>
            <label class="toggle">
              <input type="checkbox" id="ex-submit" checked>
              <span class="toggle-track"></span>
            </label>
          </div>
        </div>
        <div class="run-panel__foot">
          <button class="btn btn-primary btn-lg" id="btn-run-exec" style="flex:1">▶ Run Execution Plan</button>
        </div>
      </div>

      <!-- Emergency controls -->
      <div class="card" style="border-color:rgba(255,64,96,0.22)">
        <div class="card-header" style="background:rgba(255,61,87,0.05)">
          <span class="card-title" style="color:var(--red)">⚠ Emergency Controls</span>
        </div>
        <div class="card-body" style="display:flex;flex-direction:column;gap:12px">
          <div style="font-family:var(--f-mono);font-size:11px;color:var(--text-dim);line-height:1.6">
            Kill switch immediately cancels all pending orders and halts new submissions for the current execution plan.
          </div>
          <button class="kill-switch" id="btn-kill" style="width:100%;padding:10px" disabled>
            ☠ ARM KILL SWITCH
          </button>
          <div id="kill-confirm" style="display:none;flex-direction:column;gap:8px">
            <div style="font-family:var(--f-mono);font-size:11px;color:var(--red);text-align:center;padding:4px 0">
              ⚠ CONFIRM TO HALT ALL TRADING
            </div>
            <div style="display:flex;gap:8px">
              <button class="btn btn-ghost btn-sm" id="btn-kill-cancel" style="flex:1">Cancel</button>
              <button class="btn btn-sm" id="btn-kill-confirm" style="flex:1;background:var(--red);color:#fff;border:none">⚡ CONFIRM KILL</button>
            </div>
          </div>
          <div id="kill-activated" style="display:none;padding:12px;border-radius:8px;background:rgba(255,61,87,0.12);border:1px solid rgba(255,61,87,0.4);text-align:center">
            <div style="font-family:var(--f-display);font-size:11px;font-weight:700;color:var(--red)">KILL SWITCH ACTIVATED</div>
            <div style="font-family:var(--f-mono);font-size:10px;color:var(--red);opacity:0.7;margin-top:4px">All orders cancelled · No new orders</div>
          </div>
        </div>
      </div>

      <!-- Live positions mini -->
      <div class="card">
        <div class="card-header">
          <span class="card-title">Live Positions</span>
          <button class="btn btn-ghost btn-sm" id="btn-refresh-pos">Refresh</button>
        </div>
        <div id="positions-body" class="card-body">
          <div class="text-muted text-sm">Loading…</div>
        </div>
      </div>
    </div>

    <!-- RIGHT -->
    <div style="display:flex;flex-direction:column;gap:16px">
      <!-- Order stream -->
      <div class="results-panel">
        <div class="results-panel__header">
          <span class="card-title">Order Stream</span>
          <div style="display:flex;gap:10px;align-items:center">
            <span id="order-count" class="text-xs text-muted font-mono">0 orders</span>
            <select class="form-select" id="filter-status" style="padding:3px 8px;font-size:11px;height:auto;width:auto">
              <option value="all">All</option>
              <option value="filled">Filled</option>
              <option value="pending">Pending</option>
              <option value="failed">Failed</option>
              <option value="cancelled">Cancelled</option>
            </select>
            <button class="btn btn-ghost btn-sm" id="btn-refresh-orders">Refresh</button>
          </div>
        </div>
        <div class="results-panel__body" id="orders-body">
          <div class="loading-overlay" style="min-height:100px"><div class="spinner"></div><span>Loading orders…</span></div>
        </div>
      </div>

      <!-- Live feed -->
      <div class="card">
        <div class="card-header">
          <span class="card-title">Live Feed</span>
          <span id="feed-status" class="text-xs text-muted font-mono">connecting…</span>
        </div>
        <div id="feed-log" style="padding:12px 16px;height:200px;overflow-y:auto;display:flex;flex-direction:column-reverse;gap:0">
          <div class="text-muted text-sm">Waiting for events…</div>
        </div>
      </div>
    </div>
  </div>`;
}

/* ════════════════════════════════════════════ EVENTS */
function bindEvents(container) {
  container.querySelector('#btn-run-exec').addEventListener('click', () => runExecution(container));
  container.querySelector('#btn-refresh-orders').addEventListener('click', () => loadOrders(container));
  container.querySelector('#btn-refresh-pos').addEventListener('click', () => loadPositions(container));
  container.querySelector('#filter-status').addEventListener('change', () => renderOrders(container));

  /* Alpaca API key persistence */
  const keyEl    = container.querySelector('#ex-alpaca-key');
  const secretEl = container.querySelector('#ex-alpaca-secret');
  const statusEl = container.querySelector('#alpaca-key-status');
  const syncKeyStatus = () => {
    const hasKey = !!(localStorage.getItem('qt.alpaca.key'));
    if (statusEl) statusEl.style.display = hasKey ? 'inline' : 'none';
  };
  if (keyEl) {
    keyEl.value = localStorage.getItem('qt.alpaca.key') || '';
    keyEl.addEventListener('change', () => {
      if (keyEl.value) localStorage.setItem('qt.alpaca.key', keyEl.value);
      else localStorage.removeItem('qt.alpaca.key');
      syncKeyStatus();
      if (keyEl.value) toast.success(translateLoose('API key saved'), translateLoose('Stored locally in browser'));
    });
  }
  if (secretEl) {
    secretEl.value = localStorage.getItem('qt.alpaca.secret') || '';
    secretEl.addEventListener('change', () => {
      if (secretEl.value) localStorage.setItem('qt.alpaca.secret', secretEl.value);
      else localStorage.removeItem('qt.alpaca.secret');
    });
  }
  syncKeyStatus();

  /* Kill switch */
  const killBtn = container.querySelector('#btn-kill');
  const killHeader = container.querySelector('#btn-kill-header');
  [killBtn, killHeader].forEach(btn => {
    if (!btn) return;
    btn.addEventListener('click', () => {
      _killArmed = !_killArmed;
      const cfm = container.querySelector('#kill-confirm');
      if (_killArmed) {
        killBtn.textContent = '⚠ ARMED — confirm below';
        killBtn.classList.add('armed');
        if (cfm) cfm.style.display = 'flex';
      } else { disarmKill(container); }
    });
  });

  container.querySelector('#btn-kill-cancel')?.addEventListener('click', () => disarmKill(container));
  container.querySelector('#btn-kill-confirm')?.addEventListener('click', async () => {
    disarmKill(container);
    try {
      await api.execution.killSwitch(true, 'Manual operator trigger');
      toast.warning(translateLoose('Kill switch activated'), translateLoose('All pending orders cancelled'));
      container.querySelector('#kill-activated').style.display = '';
      loadOrders(container);
    } catch (e) { toast.error('Kill switch failed', e.message); }
  });
}

function disarmKill(container) {
  _killArmed = false;
  const btn = container.querySelector('#btn-kill');
  const cfm = container.querySelector('#kill-confirm');
  if (btn) { btn.textContent = '☠ ARM KILL SWITCH'; btn.classList.remove('armed'); }
  if (cfm) cfm.style.display = 'none';
}

/* ════════════════════════════════════════════ RUN */
async function runExecution(container) {
  const btn = container.querySelector('#btn-run-exec');
  btn.disabled = true; btn.textContent = 'Submitting…';

  const uTxt         = container.querySelector('#ex-universe').value.trim();
  const universe     = uTxt ? uTxt.split(/[,\s]+/).filter(Boolean).map(s => s.toUpperCase()) : [];
  const capital      = Number(container.querySelector('#ex-capital').value) || 1000000;
  const broker       = container.querySelector('#ex-broker').value;
  const submitOrders = container.querySelector('#ex-submit').checked;

  try {
    const res = await api.execution.paper({ universe, capital_base: capital, broker, mode: 'paper', submit_orders: submitOrders });
    toast.success(translateLoose('Execution plan submitted'), translateLoose(`${res.orders?.length || 0} orders`));
    [container.querySelector('#btn-kill'), container.querySelector('#btn-kill-header')].forEach(b => { if(b) b.disabled = false; });
    await loadOrders(container);
    _ws?.close(); connectWS(container, res.execution_id);
  } catch (e) { toast.error('Execution failed', e.message); }
  finally { btn.disabled = false; btn.textContent = '▶ Run Execution Plan'; }
}

/* ════════════════════════════════════════════ ORDERS */
async function loadOrders(container) {
  const broker = container.querySelector('#ex-broker')?.value || 'alpaca';
  try {
    const data = await api.execution.orders(broker, 'all', 100);
    _orders = data.orders || [];
    renderOrders(container);
  } catch (e) {
    container.querySelector('#orders-body').innerHTML =
      `<div class="empty-state" style="min-height:100px"><div class="empty-state__title">${translateLoose('Could not load orders')}</div><div class="empty-state__text">${e.message}</div></div>`;
  }
}

function renderOrders(container) {
  const body    = container.querySelector('#orders-body');
  const filter  = container.querySelector('#filter-status')?.value || 'all';
  const countEl = container.querySelector('#order-count');
  const filtered = filter === 'all' ? _orders : _orders.filter(o => o.status === filter);
  if (countEl) countEl.textContent = translateLoose(`${filtered.length} orders`);

  if (!filtered.length) {
    body.innerHTML = `<div class="empty-state" style="min-height:100px">
      <div class="empty-state__icon">📋</div>
      <div class="empty-state__title">${translateLoose('No orders')}</div>
      <div class="empty-state__text">${translateLoose('Submit an execution plan to see orders here.')}</div>
    </div>`;
    return;
  }

  const rows = filtered.map(o => `
    <tr>
      <td class="cell-symbol">${o.symbol}</td>
      <td><span class="badge badge-${o.side==='buy'?'long':'short'}">${(o.side||'').toUpperCase()}</span></td>
      <td class="cell-num">${o.qty || o.quantity || '—'}</td>
      <td><span class="badge badge-${statusClass(o.status)}">${(o.status||'').toUpperCase()}</span></td>
      <td class="cell-num">${o.fill_price ? '$'+Number(o.fill_price).toFixed(2) : '—'}</td>
      <td class="cell-num">${o.limit_price ? '$'+Number(o.limit_price).toFixed(2) : '—'}</td>
      <td class="text-dim text-sm">${o.order_type || ''}</td>
      <td class="text-dim text-sm" style="font-size:10px">${shortTime(o.submitted_at || o.created_at)}</td>
    </tr>`).join('');

  body.innerHTML = `<div class="tbl-wrap"><table>
    <thead><tr><th>Symbol</th><th>Side</th><th>Qty</th><th>Status</th><th>Fill $</th><th>Limit $</th><th>Type</th><th>Time</th></tr></thead>
    <tbody>${rows}</tbody>
  </table></div>`;
}

/* ════════════════════════════════════════════ POSITIONS */
async function loadPositions(container) {
  const broker = container.querySelector('#ex-broker')?.value || 'alpaca';
  const el = container.querySelector('#positions-body');
  try {
    const data = await api.execution.positions(broker);
    const positions = data.positions || [];
    if (!positions.length) { el.innerHTML = `<div class="text-muted text-sm">${translateLoose('No open positions')}</div>`; return; }
    el.innerHTML = positions.map(p => {
      const pnl = p.unrealized_pl ?? p.unrealized_pnl;
      const cls = (pnl ?? 0) >= 0 ? 'pos' : 'neg';
      return `<div style="display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid rgba(255,255,255,0.02)">
        <div>
          <span class="cell-symbol" style="font-size:12px">${p.symbol}</span>
          <span style="margin-left:8px;color:var(--text-dim);font-family:var(--f-mono);font-size:10px">${translateLoose(`${p.qty} shares`)}</span>
        </div>
        <div style="text-align:right">
          <div style="font-family:var(--f-mono);font-size:11px">${p.current_price ? '$'+Number(p.current_price).toFixed(2) : '—'}</div>
          <div class="${cls}" style="font-family:var(--f-display);font-size:11px;font-weight:700">${pnl != null ? (pnl>=0?'+':'')+Number(pnl).toFixed(2) : '—'}</div>
        </div>
      </div>`;
    }).join('');
  } catch (e) { el.innerHTML = `<div class="text-muted text-sm">${e.message}</div>`; }
}

/* ════════════════════════════════════════════ WS */
function connectWS(container, executionId = null) {
  const pill    = container.querySelector('#ws-pill');
  const feedLog = container.querySelector('#feed-log');
  const status  = container.querySelector('#feed-status');
  _ws?.close();

  _ws = openExecutionWS('alpaca', executionId, 20, (msg) => {
    if (pill) { pill.textContent = 'LIVE'; pill.className = 'live-pill'; }
    if (status) status.textContent = 'live';
    if (feedLog) {
      const entry = document.createElement('div');
      entry.style.cssText = 'padding:4px 0;border-bottom:1px solid rgba(255,255,255,0.03);font-family:var(--f-mono);font-size:11px';
      const t = msg.timestamp ? shortTime(msg.timestamp) : '';
      const st = msg.status || '';
      const col = st === 'filled' ? 'var(--green)' : st === 'failed' ? 'var(--red)' : 'var(--text-secondary)';
      entry.innerHTML = `<span style="color:var(--text-dim)">${t}</span> <span style="color:${col}">${msg.symbol || msg.type || '—'}</span> <span style="color:${col}">${st.toUpperCase()}</span>${msg.fill_price ? ` <span style="color:var(--text-dim)">@ $${Number(msg.fill_price).toFixed(2)}</span>` : ''}`;
      feedLog.prepend(entry);
      if (msg.order_id) {
        const idx = _orders.findIndex(o => o.order_id === msg.order_id);
        if (idx >= 0) _orders[idx] = { ..._orders[idx], ...msg };
        else _orders.unshift(msg);
        renderOrders(container);
      }
    }
    /* Update session P&L display */
    const pnlEl = container.querySelector('#session-pnl');
    if (pnlEl && msg.unrealized_pl != null) {
      const v = Number(msg.unrealized_pl);
      pnlEl.textContent = (v >= 0 ? '+' : '') + '$' + Math.abs(v).toFixed(2);
      pnlEl.style.color = v >= 0 ? 'var(--green)' : 'var(--red)';
    }
  }, () => {
    if (pill) { pill.textContent = 'DISCONNECTED'; pill.className = 'live-pill live-pill--off'; }
    if (status) status.textContent = 'disconnected';
  });
}

/* ════════════════════════════════════════════ HELPERS */
function statusClass(s) {
  if (s === 'filled')    return 'filled';
  if (s === 'failed')    return 'failed';
  if (s === 'cancelled') return 'neutral';
  return 'pending';
}

function shortTime(iso) {
  if (!iso) return '';
  try { return new Date(iso).toLocaleTimeString(getLocale(), { hour: '2-digit', minute: '2-digit', second: '2-digit' }); }
  catch { return iso; }
}
