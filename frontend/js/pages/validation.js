import { api } from '../qtapi.js?v=8';
import { toast } from '../components/toast.js?v=8';
import { onLangChange, translateLoose } from '../i18n.js?v=8';

let _currentContainer = null;
let _lastValidation = null;
let _langCleanup = null;

export function render(container) {
  _currentContainer = container;
  container.innerHTML = buildShell();
  bindEvents(container);
  _langCleanup ||= onLangChange(() => {
    if (_currentContainer?.isConnected && _lastValidation) {
      showValidationResults(_currentContainer, _lastValidation);
    }
  });
}

export function destroy() {
  _currentContainer = null;
  _lastValidation = null;
  _langCleanup?.();
  _langCleanup = null;
}

function buildShell() {
  return `
  <div class="page-header">
    <div>
      <div class="page-header__title">Alpha Validation</div>
      <div class="page-header__sub">Walk-Forward Testing · Overfit Detection · Strategy Robustness Lab</div>
    </div>
  </div>

  <div class="grid-sidebar" style="align-items:start">
    <!-- LEFT: Config -->
    <div style="display:flex;flex-direction:column;gap:14px">
      <div class="run-panel">
        <div class="run-panel__header">
          <div class="run-panel__title">Walk-Forward Validation</div>
          <div class="run-panel__sub">Overfit detection · Cost sensitivity</div>
        </div>
        <div class="run-panel__body">
          <div class="form-group">
            <label class="form-label">Strategy Name</label>
            <input class="form-input" id="v-strategy" value="ESG Multi-Factor Long-Only">
          </div>
          <div class="form-group">
            <label class="form-label">Universe</label>
            <input class="form-input" id="v-universe" placeholder="AAPL, MSFT… (blank = default)">
          </div>
          <div class="form-row">
            <div class="form-group">
              <label class="form-label">In-Sample Days</label>
              <input class="form-input" id="v-is" type="number" value="126">
            </div>
            <div class="form-group">
              <label class="form-label">Out-of-Sample Days</label>
              <input class="form-input" id="v-oos" type="number" value="21">
            </div>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label class="form-label">Walk-Forward Windows</label>
              <input class="form-input" id="v-windows" type="number" value="5">
            </div>
            <div class="form-group">
              <label class="form-label">Capital ($)</label>
              <input class="form-input" id="v-capital" type="number" value="1000000">
            </div>
          </div>
          <details style="border:1px solid var(--border-subtle);border-radius:8px;overflow:hidden">
            <summary style="padding:9px 13px;font-family:var(--f-display);font-size:9px;font-weight:600;letter-spacing:0.15em;color:var(--text-dim);cursor:pointer;list-style:none">
              ADVANCED VALIDATION OPTIONS
            </summary>
            <div style="padding:12px;display:flex;flex-direction:column;gap:10px">
              <div class="form-group">
                <label class="form-label">Deflated Sharpe Threshold</label>
                <input class="form-input" id="v-dsr" type="number" step="0.01" value="0.5">
              </div>
              <div class="form-group">
                <label class="form-label">Multiple Testing Correction</label>
                <select class="form-select" id="v-mtc">
                  <option>Bonferroni</option>
                  <option selected>Benjamini-Hochberg</option>
                </select>
              </div>
            </div>
          </details>
        </div>
        <div class="run-panel__foot">
          <button class="btn btn-primary btn-lg" id="btn-run-val" style="flex:1">▶ Run Validation</button>
        </div>
      </div>

      <!-- History -->
      <div class="card">
        <div class="card-header"><span class="card-title">Validation History</span></div>
        <div id="val-history" style="display:flex;flex-direction:column;gap:0">
          <div style="padding:14px 18px;color:var(--text-dim);font-size:11px">No prior validations</div>
        </div>
      </div>
    </div>

    <!-- RIGHT: Results -->
    <div id="val-results">
      <div class="empty-state">
        <div class="empty-state__icon">🔬</div>
        <div class="empty-state__title">Run walk-forward validation</div>
        <div class="empty-state__text">Configure parameters and run to get GO/NO-GO verdict, walk-forward chart, and overfit analysis.</div>
      </div>
    </div>
  </div>`;
}

function bindEvents(container) {
  container.querySelector('#btn-run-val').addEventListener('click', () => runValidation(container));
}

async function runValidation(container) {
  const btn = container.querySelector('#btn-run-val');
  btn.disabled = true; btn.textContent = '● Validating…';
  const strategy  = container.querySelector('#v-strategy').value.trim();
  const uTxt      = container.querySelector('#v-universe').value.trim();
  const universe  = uTxt ? uTxt.split(/[,\s]+/).filter(Boolean).map(s=>s.toUpperCase()) : [];
  const isSample  = Number(container.querySelector('#v-is').value) || 126;
  const oosSample = Number(container.querySelector('#v-oos').value) || 21;
  const windows   = Number(container.querySelector('#v-windows').value) || 5;
  const capital   = Number(container.querySelector('#v-capital').value) || 1000000;

  try {
    const res = await api.validation.run({ strategy_name: strategy, universe, in_sample_days: isSample, out_of_sample_days: oosSample, walk_forward_windows: windows, capital_base: capital });
    showValidationResults(container, res);
    toast.success('Validation complete', `Verdict: ${res.recommendation || 'See results'}`);
  } catch (e) {
    showValidationResults(container, mockValidationResult(strategy));
    toast.error('Validation API error', e.message + ' — showing mock results');
  } finally {
    btn.disabled = false; btn.textContent = '▶ Run Validation';
  }
}

function mockValidationResult(strategy) {
  return {
    strategy_name: strategy,
    recommendation: 'GO',
    summary: 'Strategy demonstrates robustness across walk-forward windows. OOS Sharpe remains above 1.0.',
    out_of_sample_sharpe: 1.24,
    in_sample_sharpe: 1.87,
    overfit_score: 0.18,
    fill_probability: 0.91,
    cost_drag_bps: 4.2,
    windows: [
      { window: 1, in_sample_sharpe: 1.95, out_of_sample_sharpe: 1.31 },
      { window: 2, in_sample_sharpe: 1.82, out_of_sample_sharpe: 1.18 },
      { window: 3, in_sample_sharpe: 1.91, out_of_sample_sharpe: 1.28 },
      { window: 4, in_sample_sharpe: 1.75, out_of_sample_sharpe: 1.09 },
      { window: 5, in_sample_sharpe: 1.88, out_of_sample_sharpe: 1.34 },
    ],
    regime_performance: [
      { regime: 'Bull Market', periods: 6, return: '24.2%', sharpe: '1.82', max_dd: '-8.1%' },
      { regime: 'Bear Market', periods: 2, return: '-3.4%', sharpe: '-0.41', max_dd: '-14.2%' },
      { regime: 'Sideways', periods: 4, return: '8.1%', sharpe: '0.92', max_dd: '-6.3%' },
      { regime: 'High Vol', periods: 3, return: '12.4%', sharpe: '0.78', max_dd: '-11.8%' },
    ],
  };
}

function showValidationResults(container, res) {
  _lastValidation = res;
  const isGo = (res.recommendation || '').toUpperCase().includes('GO');
  const oosShp = res.out_of_sample_sharpe ?? 1.24;
  const isShp  = res.in_sample_sharpe ?? 1.87;
  const overfit = res.overfit_score ?? 0.18;
  const fillProb = res.fill_probability ?? 0.91;
  const costDrag = res.cost_drag_bps ?? 4.2;

  container.querySelector('#val-results').innerHTML = `
    <!-- Verdict banner -->
    <div class="verdict-banner ${isGo ? 'go' : 'nogo'}">
      <div class="verdict-icon">${isGo ? '✅' : '⛔'}</div>
      <div class="verdict-text">
        <div class="verdict-title">${isGo ? 'GO — STRATEGY IS ROBUST' : 'NO-GO — OVERFIT DETECTED'}</div>
        <div class="verdict-reason">${res.summary || ''}</div>
      </div>
    </div>

    <!-- 4 validation cards -->
    <div class="validation-cards">
      ${[
        ['OOS SHARPE', oosShp.toFixed(2), oosShp >= 1.0 ? 'PASS — Above 1.0 threshold' : 'FAIL — Below 1.0 threshold', oosShp >= 1.0 ? 'pass' : 'fail'],
        ['OVERFIT SCORE', overfit.toFixed(2), overfit < 0.3 ? 'PASS — Low overfit risk' : overfit < 0.7 ? 'WARNING' : 'FAIL — High overfit', overfit < 0.3 ? 'pass' : overfit < 0.7 ? 'warn' : 'fail'],
        ['COST DRAG', costDrag.toFixed(1) + 'bps', `Breakeven at ~${(costDrag * 2.5).toFixed(0)}bps`, 'pass'],
        ['FILL PROB', (fillProb * 100).toFixed(0) + '%', fillProb > 0.85 ? 'HIGH — Liquid universe' : fillProb > 0.65 ? 'MEDIUM' : 'LOW', fillProb > 0.85 ? 'pass' : fillProb > 0.65 ? 'warn' : 'fail'],
      ].map(([l,v,s,cls]) => `
        <div class="val-card">
          <div class="val-card-label">${l}</div>
          <div class="val-card-value" style="color:${cls==='pass'?'var(--green)':cls==='warn'?'var(--amber)':'var(--red)'}">${v}</div>
          <div class="val-card-status ${cls}">${s}</div>
        </div>`).join('')}
    </div>

    <!-- Walk-forward chart -->
    <div class="card" style="margin-bottom:16px">
      <div class="card-header"><span class="card-title">Walk-Forward Performance</span></div>
      <div class="card-body" style="padding:0">
        <canvas id="wf-chart" height="220" style="width:100%"></canvas>
      </div>
    </div>

    <!-- Regime performance -->
    <div class="card">
      <div class="card-header"><span class="card-title">Regime Performance Analysis</span></div>
      <div class="tbl-wrap">
        <table>
          <thead><tr><th>Regime</th><th>Periods</th><th>Avg Return</th><th>Sharpe</th><th>Max DD</th></tr></thead>
          <tbody>
            ${(res.regime_performance||[]).map(r => `
              <tr>
                <td class="cell-symbol" style="font-size:12px">${r.regime}</td>
                <td class="cell-num">${r.periods}</td>
                <td class="cell-num ${r.return?.startsWith('-')?'neg':'pos'}">${r.return}</td>
                <td class="cell-num ${parseFloat(r.sharpe)>=1?'pos':parseFloat(r.sharpe)<0?'neg':''}">${r.sharpe}</td>
                <td class="cell-num neg">${r.max_dd}</td>
              </tr>`).join('')}
          </tbody>
        </table>
      </div>
    </div>

    <div style="display:flex;gap:8px;margin-top:16px">
      <button class="btn btn-ghost">📊 Export Validation Report</button>
      <button class="btn btn-primary" onclick="window.location.hash='#/execution'">→ Approve for Execution</button>
    </div>`;

  setTimeout(() => drawWalkForwardChart(container, res), 50);
}

function drawWalkForwardChart(container, res) {
  const canvas = container.querySelector('#wf-chart');
  if (!canvas) return;
  const windows = res.windows || [];
  if (!windows.length) return;
  const dpr = window.devicePixelRatio || 1;
  canvas.width  = (canvas.parentElement?.offsetWidth || 700) * dpr;
  canvas.height = 220 * dpr;
  canvas.style.height = '220px';
  const ctx = canvas.getContext('2d');
  const W = canvas.width, H = canvas.height;
  const padL=60*dpr, padR=20*dpr, padT=20*dpr, padB=36*dpr;
  const cW=W-padL-padR, cH=H-padT-padB;
  ctx.clearRect(0,0,W,H);
  ctx.fillStyle='#07070F'; ctx.fillRect(0,0,W,H);

  const allVals = windows.flatMap(w => [w.in_sample_sharpe, w.out_of_sample_sharpe]);
  const minV = Math.min(...allVals)*0.9, maxV = Math.max(...allVals)*1.05;
  const px = i => padL + (i / (windows.length-1)) * cW;
  const py = v => padT + cH - ((v-minV)/(maxV-minV))*cH;

  /* Grid */
  ctx.strokeStyle='rgba(255,255,255,0.04)'; ctx.lineWidth=dpr;
  for(let i=0;i<=4;i++){
    const y=padT+(cH/4)*i;
    ctx.beginPath(); ctx.moveTo(padL,y); ctx.lineTo(W-padR,y); ctx.stroke();
    ctx.fillStyle='rgba(140,160,220,0.45)'; ctx.font=`${9*dpr}px IBM Plex Mono`; ctx.textAlign='right';
    ctx.fillText((maxV-(maxV-minV)/4*i).toFixed(1), padL-5*dpr, y+3*dpr);
  }

  /* Robust zone fill */
  ctx.fillStyle='rgba(0,255,136,0.04)';
  ctx.fillRect(padL, py(1.0), cW, padT+cH-py(1.0));
  ctx.strokeStyle='rgba(0,255,136,0.2)'; ctx.lineWidth=dpr; ctx.setLineDash([4*dpr,4*dpr]);
  ctx.beginPath(); ctx.moveTo(padL,py(1.0)); ctx.lineTo(W-padR,py(1.0)); ctx.stroke();
  ctx.setLineDash([]);
  ctx.fillStyle='rgba(0,255,136,0.4)'; ctx.font=`${9*dpr}px IBM Plex Mono`; ctx.textAlign='right';
  ctx.fillText(translateLoose('Robust Zone'), W-padR-6*dpr, py(1.0)-4*dpr);

  /* IS line */
  ctx.beginPath();
  windows.forEach((w,i) => { if(i===0) ctx.moveTo(px(i),py(w.in_sample_sharpe)); else ctx.lineTo(px(i),py(w.in_sample_sharpe)); });
  ctx.strokeStyle='rgba(0,229,255,0.7)'; ctx.lineWidth=2*dpr; ctx.stroke();

  /* OOS line */
  ctx.beginPath();
  windows.forEach((w,i) => { if(i===0) ctx.moveTo(px(i),py(w.out_of_sample_sharpe)); else ctx.lineTo(px(i),py(w.out_of_sample_sharpe)); });
  ctx.strokeStyle='#00FF88'; ctx.lineWidth=2.5*dpr;
  ctx.shadowColor='#00FF88'; ctx.shadowBlur=10*dpr; ctx.stroke(); ctx.shadowBlur=0;

  /* Dots & labels */
  windows.forEach((w,i) => {
    [['#00E5FF',w.in_sample_sharpe],['#00FF88',w.out_of_sample_sharpe]].forEach(([c,v]) => {
      ctx.beginPath(); ctx.arc(px(i),py(v),4*dpr,0,Math.PI*2);
      ctx.fillStyle=c; ctx.fill();
    });
    ctx.fillStyle='rgba(140,160,220,0.45)'; ctx.font=`${9*dpr}px IBM Plex Mono`; ctx.textAlign='center';
    ctx.fillText('W'+w.window, px(i), H-padB+14*dpr);
  });

  /* Legend */
  [[0.5*W,'#00E5FF','IS Sharpe'],[0.7*W,'#00FF88','OOS Sharpe']].forEach(([x,c,label]) => {
    ctx.strokeStyle=c; ctx.lineWidth=2*dpr;
    ctx.beginPath(); ctx.moveTo(x,padT/2); ctx.lineTo(x+20*dpr,padT/2); ctx.stroke();
    ctx.fillStyle='rgba(240,244,255,0.7)'; ctx.font=`${9*dpr}px IBM Plex Mono`; ctx.textAlign='left';
    ctx.fillText(translateLoose(label), x+24*dpr, padT/2+3*dpr);
  });
}
