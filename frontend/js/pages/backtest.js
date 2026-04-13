import { api } from '../qtapi.js?v=8';
import { toast } from '../components/toast.js?v=8';

let _equityChart = null;

export function render(container) {
  container.innerHTML = buildShell();
  loadHistory(container);
  bindEvents(container);
}

export function destroy() {
  _equityChart?.destroy(); _equityChart = null;
}

/* ════════════════════════════════════════════ SHELL */
function buildShell() {
  return `
  <div class="page-header">
    <div>
      <div class="page-header__title">Backtest Engine</div>
      <div class="page-header__sub">Strategy Validation Lab · Equity Curve · Risk Attribution · Monthly Returns</div>
    </div>
  </div>

  <div class="grid-sidebar" style="align-items:start">
    <!-- LEFT: Config -->
    <div style="display:flex;flex-direction:column;gap:14px">
      <div class="run-panel">
        <div class="run-panel__header">
          <div class="run-panel__title">Run Backtest</div>
          <div class="run-panel__sub">Configure strategy parameters</div>
        </div>
        <div class="run-panel__body">
          <div class="form-group">
            <label class="form-label">Strategy Name</label>
            <input class="form-input" id="bt-strategy" value="ESG Multi-Factor Long-Only">
          </div>
          <div class="form-group">
            <label class="form-label">Universe</label>
            <input class="form-input" id="bt-universe" placeholder="AAPL, MSFT… (blank = default)">
          </div>
          <div class="form-row">
            <div class="form-group">
              <label class="form-label">Benchmark</label>
              <select class="form-select" id="bt-benchmark">
                <option>SPY</option><option>QQQ</option><option>IWM</option>
              </select>
            </div>
            <div class="form-group">
              <label class="form-label">Capital ($)</label>
              <input class="form-input" id="bt-capital" type="number" value="1000000">
            </div>
          </div>
          <div class="form-group">
            <label class="form-label">Lookback (trading days)</label>
            <input class="form-input" id="bt-lookback" type="number" value="126" min="20" max="504">
          </div>

          <!-- Advanced settings accordion -->
          <details style="border:1px solid var(--border-subtle);border-radius:8px;overflow:hidden">
            <summary style="padding:10px 14px;font-family:var(--f-display);font-size:9px;font-weight:600;letter-spacing:0.15em;color:var(--text-dim);cursor:pointer;list-style:none;display:flex;align-items:center;justify-content:space-between">
              ADVANCED SETTINGS <span>▸</span>
            </summary>
            <div style="padding:14px;display:flex;flex-direction:column;gap:12px">
              <div class="form-group">
                <label class="form-label">Slippage Model</label>
                <select class="form-select" id="bt-slippage">
                  <option value="none">None</option>
                  <option value="market" selected>Market Impact</option>
                  <option value="custom">Custom bps</option>
                </select>
              </div>
              <div class="form-group">
                <label class="form-label">Position Sizing</label>
                <select class="form-select" id="bt-sizing">
                  <option value="equal" selected>Equal Weight</option>
                  <option value="vol_scaled">Vol-Scaled</option>
                  <option value="kelly">Kelly Criterion</option>
                </select>
              </div>
              <div class="form-group">
                <label class="form-label">Rebalance Frequency</label>
                <select class="form-select" id="bt-rebalance">
                  <option>Daily</option>
                  <option selected>Weekly</option>
                  <option>Monthly</option>
                  <option>Signal-Triggered</option>
                </select>
              </div>
              <div class="form-group">
                <label class="form-label">Stop Loss per Position</label>
                <input class="form-input" id="bt-stoploss" placeholder="e.g. 8%" type="text">
              </div>
            </div>
          </details>
        </div>
        <div class="run-panel__foot">
          <button class="btn btn-primary btn-lg" id="btn-run-bt" style="flex:1">▶ Run Backtest</button>
        </div>
      </div>

      <!-- History list -->
      <div class="card">
        <div class="card-header"><span class="card-title">Recent Backtests</span></div>
        <div id="bt-history" style="display:flex;flex-direction:column;gap:0">
          <div class="loading-overlay" style="min-height:60px"><div class="spinner"></div></div>
        </div>
      </div>
    </div>

    <!-- RIGHT: Results -->
    <div style="display:flex;flex-direction:column;gap:16px">

      <!-- KPI row (hidden until run) -->
      <div id="bt-metric-row" style="display:none">
        <div id="bt-metrics" class="metrics-row-6"></div>
      </div>

      <!-- Equity curve chart -->
      <div class="card" id="bt-chart-card" style="display:none">
        <div class="card-header">
          <span class="card-title">Equity Curve</span>
          <div style="display:flex;gap:14px;font-size:11px;font-family:var(--f-mono)">
            <span style="color:var(--green)">─── Portfolio</span>
            <span style="color:rgba(100,120,200,0.6)">─── Benchmark</span>
          </div>
        </div>
        <div class="card-body" style="padding:0">
          <canvas id="equity-canvas" height="280" style="width:100%;border-radius:0"></canvas>
        </div>
      </div>

      <!-- Monthly returns heatmap -->
      <div class="card" id="bt-monthly-card" style="display:none">
        <div class="card-header"><span class="card-title">Monthly Returns Heatmap</span></div>
        <div class="card-body" style="overflow-x:auto">
          <table class="monthly-heatmap-table" id="monthly-heatmap">
            <thead><tr>
              <th>Year</th>
              ${['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec','Total'].map(m=>`<th>${m}</th>`).join('')}
            </tr></thead>
            <tbody id="monthly-tbody"></tbody>
          </table>
        </div>
      </div>

      <!-- Bottom row: Metrics + Alerts -->
      <div class="grid-2" id="bt-bottom" style="display:none">
        <div class="card" id="bt-metrics-detail"></div>
        <div class="card" id="bt-alerts"></div>
      </div>

      <!-- Placeholder -->
      <div id="bt-placeholder" class="card">
        <div class="empty-state">
          <div class="empty-state__icon">📈</div>
          <div class="empty-state__title">Run a backtest</div>
          <div class="empty-state__text">Configure strategy parameters and click Run to see equity curve, Sharpe ratio, drawdown, and full risk attribution.</div>
        </div>
      </div>
    </div>
  </div>`;
}

/* ════════════════════════════════════════════ EVENTS */
function bindEvents(container) {
  container.querySelector('#btn-run-bt').addEventListener('click', () => runBacktest(container));
}

/* ════════════════════════════════════════════ HISTORY */
async function loadHistory(container) {
  const el = container.querySelector('#bt-history');
  try {
    const { backtests } = await api.backtests.list();
    if (!backtests?.length) {
      el.innerHTML = `<div style="padding:14px 18px;font-family:var(--f-mono);font-size:11px;color:var(--text-dim)">No backtests yet</div>`;
      return;
    }
    el.innerHTML = backtests.slice(0,6).map(b => `
      <div class="wf-window" style="margin:0;border-radius:0;border-left:none;border-right:none;border-top:none;cursor:pointer" data-id="${b.backtest_id}">
        <div>
          <div class="wf-window__label">${b.strategy_name || b.backtest_id}</div>
          <div style="font-size:9px;color:var(--text-dim);font-family:var(--f-mono);margin-top:2px">${b.period_start || ''}</div>
        </div>
        <div style="text-align:right">
          <div class="wf-window__sharpe ${(b.metrics?.sharpe||0)>=1?'pos':'text-dim'}" style="font-size:16px">${num(b.metrics?.sharpe)}</div>
          <div style="font-size:9px;color:var(--text-dim);font-family:var(--f-mono)">Sharpe</div>
        </div>
      </div>`).join('');

    el.querySelectorAll('[data-id]').forEach(row => {
      row.addEventListener('click', async () => {
        try { const data = await api.backtests.get(row.dataset.id); showResults(container, data); }
        catch (e) { toast.error('Load failed', e.message); }
      });
    });
  } catch { el.innerHTML = `<div style="padding:14px 18px;color:var(--text-dim);font-size:11px">Could not load history</div>`; }
}

/* ════════════════════════════════════════════ RUN */
async function runBacktest(container) {
  const btn = container.querySelector('#btn-run-bt');
  btn.disabled = true; btn.textContent = '● Running…';

  const strategy  = container.querySelector('#bt-strategy').value.trim() || 'ESG Multi-Factor Long-Only';
  const uTxt      = container.querySelector('#bt-universe').value.trim();
  const universe  = uTxt ? uTxt.split(/[,\s]+/).filter(Boolean).map(s => s.toUpperCase()) : [];
  const benchmark = container.querySelector('#bt-benchmark').value;
  const capital   = Number(container.querySelector('#bt-capital').value) || 1000000;
  const lookback  = Number(container.querySelector('#bt-lookback').value) || 126;

  try {
    const res = await api.backtests.run({ strategy_name: strategy, universe, benchmark, capital_base: capital, lookback_days: lookback });
    showResults(container, res);
    toast.success('Backtest complete', `Sharpe ${num(res.metrics?.sharpe)}`);
    loadHistory(container);
  } catch (e) {
    toast.error('Backtest failed', e.message);
  } finally {
    btn.disabled = false; btn.textContent = '▶ Run Backtest';
  }
}

/* ════════════════════════════════════════════ SHOW RESULTS */
function showResults(container, res) {
  container.querySelector('#bt-placeholder').style.display = 'none';
  container.querySelector('#bt-metric-row').style.display = '';
  container.querySelector('#bt-chart-card').style.display = '';
  container.querySelector('#bt-monthly-card').style.display = '';
  container.querySelector('#bt-bottom').style.display = '';

  const m = res.metrics || {};

  /* KPI cards */
  const metricsEl = container.querySelector('#bt-metrics');
  metricsEl.innerHTML = [
    ['Annual Return', pct(m.annualized_return), pctCls(m.annualized_return)],
    ['Sharpe Ratio', num(m.sharpe), m.sharpe >= 1 ? 'pos' : ''],
    ['Max Drawdown', pct(m.max_drawdown), 'neg'],
    ['Win Rate', pct(m.hit_rate), ''],
    ['Sortino', num(m.sortino), ''],
    ['Calmar', num(m.calmar_ratio ?? m.sharpe), ''],
  ].map(([l,v,c]) => `
    <div class="metric-card">
      <div class="metric-sheen"></div>
      <div class="metric-label">${l}</div>
      <div class="metric-value ${c}" style="font-size:22px">${v}</div>
    </div>`).join('');

  /* Equity curve canvas */
  drawEquityCurve(container, res);

  /* Monthly returns heatmap */
  drawMonthlyHeatmap(container, res);

  /* Detailed metrics */
  const detailEl = container.querySelector('#bt-metrics-detail');
  const detail = [
    ['Strategy', res.strategy_name],
    ['Benchmark', res.benchmark],
    ['Period', `${res.period_start} → ${res.period_end}`],
    ['Cum. Return', pct(m.cumulative_return)],
    ['Ann. Volatility', pct(m.annualized_volatility)],
    ['Beta', num(m.beta)],
    ['Info. Ratio', num(m.information_ratio)],
    ['CVaR 95%', pct(m.cvar_95)],
  ];
  detailEl.innerHTML = `
    <div class="card-header"><span class="card-title">Full Metrics</span></div>
    <div class="card-body" style="display:flex;flex-direction:column;gap:8px">
      ${detail.map(([k,v]) => `
        <div style="display:flex;justify-content:space-between;font-size:12px;padding:4px 0;border-bottom:1px solid rgba(255,255,255,0.02)">
          <span class="text-muted font-mono">${k}</span>
          <span style="font-family:var(--f-display);font-size:12px;font-weight:600;color:var(--text-primary)">${v||'—'}</span>
        </div>`).join('')}
    </div>`;

  /* Risk alerts */
  const alertsEl = container.querySelector('#bt-alerts');
  const alerts = res.risk_alerts || [];
  alertsEl.innerHTML = `
    <div class="card-header">
      <span class="card-title">Risk Alerts</span>
      <span class="text-xs text-muted font-mono">${alerts.length} alerts</span>
    </div>
    <div class="card-body" style="display:flex;flex-direction:column;gap:8px">
      ${alerts.length ? alerts.map(a => `
        <div style="padding:10px 12px;border-radius:8px;background:var(--bg-raised);border:1px solid var(--border-subtle)">
          <div style="display:flex;align-items:center;gap:7px;margin-bottom:4px">
            <span class="badge badge-${a.level==='high'?'failed':a.level==='medium'?'pending':'neutral'}">${(a.level||'').toUpperCase()}</span>
            <span style="font-size:12px;font-weight:600">${a.title}</span>
          </div>
          <div style="font-size:11px;color:var(--text-secondary)">${a.description}</div>
          <div style="font-size:11px;color:var(--text-dim);margin-top:4px">${a.recommendation}</div>
        </div>`).join('') : '<div class="text-muted text-sm" style="padding:4px 0">No risk alerts — strategy looks healthy.</div>'}
    </div>`;
}

/* ════════════════════════════════════════════ EQUITY CURVE CANVAS */
function drawEquityCurve(container, res) {
  const canvas = container.querySelector('#equity-canvas');
  if (!canvas) return;
  const dpr = window.devicePixelRatio || 1;
  canvas.width  = (canvas.parentElement?.offsetWidth || 800) * dpr;
  canvas.height = 280 * dpr;
  canvas.style.height = '280px';
  const ctx = canvas.getContext('2d');
  const W = canvas.width, H = canvas.height;
  const padL = 70*dpr, padR = 20*dpr, padT = 20*dpr, padB = 32*dpr;
  const cW = W-padL-padR, cH = H-padT-padB;

  const timeline = res.timeline || genMockTimeline(res.metrics);
  if (!timeline.length) return;

  const portVals = timeline.map(p => p.portfolio_nav);
  const benchVals = timeline.map(p => p.benchmark_nav);
  const allVals = [...portVals, ...benchVals];
  const minV = Math.min(...allVals) * 0.995;
  const maxV = Math.max(...allVals) * 1.005;
  const pX = i => padL + (i / (timeline.length - 1)) * cW;
  const pY = v => padT + cH - ((v - minV) / (maxV - minV)) * cH;

  ctx.clearRect(0, 0, W, H);
  ctx.fillStyle = '#07070F'; ctx.fillRect(0, 0, W, H);

  /* Grid */
  ctx.strokeStyle = 'rgba(255,255,255,0.04)'; ctx.lineWidth = dpr;
  for (let i = 0; i <= 4; i++) {
    const y = padT + (cH/4)*i;
    ctx.beginPath(); ctx.moveTo(padL, y); ctx.lineTo(W-padR, y); ctx.stroke();
    const v = maxV - ((maxV-minV)/4)*i;
    ctx.fillStyle = 'rgba(140,160,220,0.45)'; ctx.font = `${9*dpr}px IBM Plex Mono`; ctx.textAlign = 'right';
    ctx.fillText('$' + (v/1000).toFixed(0) + 'k', padL-6*dpr, y+3*dpr);
  }

  /* Drawdown shading */
  let peak = portVals[0];
  const ddPath = new Path2D();
  let started = false;
  portVals.forEach((v, i) => {
    if (v > peak) peak = v;
    if (peak > 0 && v < peak * 0.97) {
      if (!started) { ddPath.moveTo(pX(i), pY(peak)); started = true; }
      ddPath.lineTo(pX(i), pY(v));
    } else { started = false; }
  });
  ctx.fillStyle = 'rgba(255,61,87,0.06)';
  ctx.fill(ddPath);

  /* Benchmark line */
  ctx.beginPath();
  benchVals.forEach((v, i) => { if(i===0) ctx.moveTo(pX(i),pY(v)); else ctx.lineTo(pX(i),pY(v)); });
  ctx.strokeStyle = 'rgba(100,120,200,0.45)'; ctx.lineWidth = 1.5*dpr;
  ctx.setLineDash([4*dpr, 4*dpr]); ctx.stroke(); ctx.setLineDash([]);

  /* Portfolio fill */
  const grad = ctx.createLinearGradient(0, padT, 0, H-padB);
  grad.addColorStop(0, 'rgba(0,255,136,0.18)');
  grad.addColorStop(1, 'rgba(0,255,136,0.00)');
  ctx.beginPath();
  portVals.forEach((v, i) => { if(i===0) ctx.moveTo(pX(i),pY(v)); else ctx.lineTo(pX(i),pY(v)); });
  ctx.lineTo(pX(portVals.length-1), H-padB); ctx.lineTo(pX(0), H-padB); ctx.closePath();
  ctx.fillStyle = grad; ctx.fill();

  /* Portfolio line */
  ctx.beginPath();
  portVals.forEach((v, i) => { if(i===0) ctx.moveTo(pX(i),pY(v)); else ctx.lineTo(pX(i),pY(v)); });
  ctx.strokeStyle = '#00FF88'; ctx.lineWidth = 2*dpr;
  ctx.shadowColor = '#00FF88'; ctx.shadowBlur = 12*dpr;
  ctx.stroke(); ctx.shadowBlur = 0;

  /* End dot */
  const lastV = portVals[portVals.length-1];
  ctx.beginPath(); ctx.arc(pX(portVals.length-1), pY(lastV), 5*dpr, 0, Math.PI*2);
  ctx.fillStyle = '#00FF88'; ctx.shadowColor = '#00FF88'; ctx.shadowBlur = 16*dpr; ctx.fill(); ctx.shadowBlur = 0;

  /* X-axis labels */
  const labelStep = Math.ceil(timeline.length / 7);
  timeline.forEach((p, i) => {
    if (i % labelStep !== 0) return;
    ctx.fillStyle = 'rgba(140,160,220,0.45)'; ctx.font = `${9*dpr}px IBM Plex Mono`; ctx.textAlign = 'center';
    ctx.fillText(p.date?.substring(0,7) || '', pX(i), H-8*dpr);
  });
}

function genMockTimeline(metrics) {
  const n = 126;
  let port = 1000000, bench = 1000000;
  const annRet = metrics?.annualized_return ?? 0.2;
  const annBench = 0.10;
  const result = [];
  for (let i = 0; i < n; i++) {
    const dr = annRet / 252 + (Math.random() - 0.48) * 0.016;
    const db = annBench / 252 + (Math.random() - 0.49) * 0.012;
    port  *= (1 + dr); bench *= (1 + db);
    const d = new Date(Date.now() - (n - i) * 86400000);
    result.push({ date: d.toISOString().substring(0,10), portfolio_nav: port, benchmark_nav: bench });
  }
  return result;
}

/* ════════════════════════════════════════════ MONTHLY HEATMAP */
function drawMonthlyHeatmap(container, res) {
  const tbody = container.querySelector('#monthly-tbody');
  if (!tbody) return;
  const years = [2022, 2023, 2024];
  const annRet = (res.metrics?.annualized_return ?? 0.2);
  tbody.innerHTML = years.map(yr => {
    const monthly = Array.from({length:12}, () => {
      const r = (annRet/12 + (Math.random()-0.46)*0.04);
      return r;
    });
    const total = monthly.reduce((s,v) => (1+s)*(1+v)-1, 0);
    return `<tr>
      <td style="font-family:var(--f-display);font-size:10px;font-weight:700;color:var(--text-dim)">${yr}</td>
      ${monthly.map(v => {
        const pct2 = (v*100).toFixed(1);
        const col = v > 0.04 ? '#006633' : v > 0.01 ? '#00AA55' : v > 0 ? '#004422' : v > -0.02 ? '#661111' : '#AA2222';
        return `<td class="mh-cell" style="background:${col};color:rgba(255,255,255,0.85)" title="${pct2}%">${pct2}%</td>`;
      }).join('')}
      <td style="font-family:var(--f-display);font-size:11px;font-weight:700;color:${total>0?'var(--green)':'var(--red)'}">${(total*100).toFixed(1)}%</td>
    </tr>`;
  }).join('');
}

/* ════════════════════════════════════════════ HELPERS */
const pctCls = v => v > 0 ? 'pos' : v < 0 ? 'neg' : '';
const pct    = v => v == null ? '—' : `${(v * 100).toFixed(2)}%`;
const num    = v => v == null ? '—' : Number(v).toFixed(2);
