import { api } from '../qtapi.js?v=8';
import { toast } from '../components/toast.js?v=8';

let _result     = null;
let _watchlist  = ['AAPL','MSFT','NVDA','TSLA','NEE','AMZN','GOOGL','META'];
let _selected   = 'AAPL';

export function render(container) {
  container.innerHTML = buildShell();
  bindEvents(container);
  renderWatchlist(container);
}

/* ══════════════════════════════════════════════
   SHELL
══════════════════════════════════════════════ */
function buildShell() {
  return `
  <div class="page-header">
    <div>
      <div class="page-header__title">Research Pipeline</div>
      <div class="page-header__sub">Multi-factor ESG · Quant Signal Intelligence · Alpha Generation</div>
    </div>
  </div>

  <div class="grid-3col">
    <!-- LEFT: Watchlist -->
    <div class="watchlist-panel">
      <div class="watchlist-header">
        <span class="chat-panel-title">MY WATCHLIST</span>
        <button class="btn btn-ghost btn-sm" id="btn-add-sym">+ Add</button>
      </div>
      <div class="watchlist-search">
        <input id="wl-search" placeholder="Search ticker or company…" autocomplete="off">
      </div>
      <div class="watchlist-list" id="watchlist-items"></div>
      <div class="watchlist-presets">
        ${['ESG Leaders','High Momentum','SP500 Top'].map(p =>
          `<button class="preset-btn" data-preset="${p}">${p}</button>`
        ).join('')}
      </div>
    </div>

    <!-- CENTER: Config + Results -->
    <div style="display:flex;flex-direction:column;gap:16px">
      <!-- Config (collapsible) -->
      <div class="run-panel" id="config-panel">
        <div class="run-panel__header" style="cursor:pointer" id="config-toggle">
          <div class="run-panel__title">▸ SIGNAL RESEARCH CONFIGURATION</div>
          <div class="run-panel__sub">P1 Alpha · ESG Scoring · Fundamentals · Sentiment</div>
        </div>
        <div id="config-body" class="run-panel__body">
          <div class="form-group">
            <label class="form-label">Universe (auto from watchlist, or override)</label>
            <input class="form-input" id="r-universe" placeholder="AAPL, MSFT… (blank = watchlist)">
          </div>
          <div class="form-row">
            <div class="form-group">
              <label class="form-label">Benchmark</label>
              <select class="form-select" id="r-benchmark">
                <option>SPY</option><option>QQQ</option><option>IWM</option>
              </select>
            </div>
            <div class="form-group">
              <label class="form-label">Capital ($)</label>
              <input class="form-input" id="r-capital" type="number" value="1000000">
            </div>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label class="form-label">Horizon (days)</label>
              <input class="form-input" id="r-horizon" type="number" value="20">
            </div>
            <div class="form-group">
              <label class="form-label">Strategy</label>
              <select class="form-select" id="r-strategy">
                <option value="">Default</option>
                <option value="esg_long_only">ESG Long-Only</option>
                <option value="esg_ls">ESG Long-Short</option>
                <option value="momentum">Momentum</option>
                <option value="value">Value</option>
              </select>
            </div>
          </div>
          <div class="form-group">
            <label class="form-label">Research Question</label>
            <textarea class="form-textarea" id="r-question" rows="3"
              placeholder="e.g. Identify ESG leaders with momentum and strong fundamentals"></textarea>
          </div>
          <div style="display:flex;flex-wrap:wrap;gap:6px">
            ${[
              'Identify ESG leaders with momentum...',
              'Find undervalued stocks with positive ESG trend...',
              'Screen for low-volatility dividend growers...'
            ].map(q => `<button class="filter-chip" data-q="${q}">${q.substring(0,42)}…</button>`).join('')}
          </div>
        </div>
        <div class="run-panel__foot">
          <button class="btn btn-primary btn-lg" id="btn-run-research" style="flex:1">
            ▶ Run Research Pipeline
          </button>
        </div>
      </div>

      <!-- Run progress (hidden until running) -->
      <div class="card" id="run-progress" style="display:none">
        <div class="card-header"><span class="card-title">Pipeline Running</span></div>
        <div class="card-body">
          <div class="run-steps" id="run-steps-list">
            ${['Fetching market data','Running ESG scoring','Generating signals','Writing thesis','Complete'].map((s,i) =>
              `<div class="run-step" data-step="${i}"><div class="step-dot"></div>${s}</div>`
            ).join('')}
          </div>
        </div>
      </div>

      <!-- Mini K-line for selected result -->
      <div class="kline-wrap" id="result-kline" style="display:none">
        <div class="kline-header">
          <span class="kline-title" id="result-kline-title">K-LINE: AAPL</span>
          <div class="tf-tabs" id="res-tf-tabs">
            ${['1D','1W','1M'].map(tf =>
              `<div class="tf-tab${tf==='1D'?' active':''}" data-restf="${tf}">${tf}</div>`
            ).join('')}
          </div>
        </div>
        <div class="kline-canvas-wrap">
          <canvas id="result-kline-canvas" height="200"></canvas>
        </div>
      </div>

      <!-- Results -->
      <div class="results-panel" id="results-panel">
        <div class="results-panel__header">
          <span class="card-title" id="results-title">Results</span>
          <div style="display:flex;gap:8px;align-items:center">
            <span class="text-xs text-muted font-mono" id="results-meta"></span>
            <button class="btn btn-primary btn-sm" id="btn-export-portfolio" style="display:none">
              → Send to Portfolio
            </button>
          </div>
        </div>
        <div class="results-panel__body" id="results-body">
          <div class="empty-state">
            <div class="empty-state__icon">🔬</div>
            <div class="empty-state__title">Run the pipeline</div>
            <div class="empty-state__text">Configure parameters and click Run to generate alpha signals.</div>
          </div>
        </div>
      </div>

      <!-- Expanded thesis panel -->
      <div class="card" id="thesis-panel" style="display:none">
        <div class="card-header">
          <span class="card-title" id="thesis-symbol">THESIS</span>
          <div style="display:flex;gap:8px">
            <button class="btn btn-ghost btn-sm" id="btn-add-portfolio">Add to Portfolio</button>
            <button class="btn btn-ghost btn-sm" id="btn-close-thesis">✕</button>
          </div>
        </div>
        <div class="card-body">
          <div id="thesis-content" style="font-family:var(--f-mono);font-size:12px;line-height:1.8;color:var(--text-secondary)"></div>
          <div style="margin-top:14px;display:flex;flex-wrap:wrap;gap:6px" id="thesis-chips"></div>
        </div>
      </div>
    </div>

    <!-- RIGHT: Market context -->
    <div style="display:flex;flex-direction:column;gap:14px">
      <div class="card">
        <div class="card-header"><span class="card-title">Market Context</span></div>
        <div class="card-body" style="padding:0">
          ${['SPY','QQQ','VIX','GLD','TLT'].map(sym => `
            <div class="watchlist-item" style="padding:10px 16px">
              <span class="watchlist-item-ticker">${sym}</span>
              <div style="display:flex;flex-direction:column;align-items:flex-end;gap:2px">
                <span style="font-family:var(--f-display);font-size:12px;font-weight:600;color:var(--text-primary)">${mockPrice(sym)}</span>
                <span class="chip-chg ${mockChg(sym) >= 0 ? 'pos' : 'neg'}" style="font-size:10px">
                  ${mockChg(sym) > 0 ? '+' : ''}${mockChg(sym).toFixed(2)}%
                </span>
              </div>
            </div>`).join('')}
        </div>
      </div>

      <div class="card">
        <div class="card-header"><span class="card-title">ESG Momentum Leaders</span></div>
        <div class="card-body" style="padding:0;display:flex;flex-direction:column">
          ${['TSLA','NEE','MSFT','AAPL','GOOGL'].map(sym => `
            <div class="watchlist-item">
              <div>
                <div class="watchlist-item-ticker">${sym}</div>
                <div class="watchlist-item-name">ESG Score improving</div>
              </div>
              <div style="display:flex;flex-direction:column;align-items:flex-end;gap:4px">
                <span style="font-family:var(--f-display);font-size:11px;font-weight:600;color:var(--green)">ESG +${(Math.random()*8+2).toFixed(1)}</span>
                <span class="badge badge-long" style="font-size:8px">LONG</span>
              </div>
            </div>`).join('')}
        </div>
      </div>

      <div class="card">
        <div class="card-header"><span class="card-title">News Sentiment</span></div>
        <div class="card-body" style="padding:0;display:flex;flex-direction:column;gap:0">
          ${mockNews().map(n => `
            <div style="padding:10px 16px;border-bottom:1px solid rgba(255,255,255,0.024)">
              <div style="font-family:var(--f-mono);font-size:11px;color:var(--text-secondary);line-height:1.5;margin-bottom:4px">${n.headline}</div>
              <div style="display:flex;gap:8px;align-items:center">
                <span class="badge badge-${n.sent}" style="font-size:8px">${n.sent.toUpperCase()}</span>
                <span style="font-family:var(--f-mono);font-size:9px;color:var(--text-dim)">${n.source} · ${n.time}</span>
              </div>
            </div>`).join('')}
        </div>
      </div>
    </div>
  </div>`;
}

/* ══════════════════════════════════════════════
   WATCHLIST RENDER
══════════════════════════════════════════════ */
function renderWatchlist(container) {
  const el = container.querySelector('#watchlist-items');
  el.innerHTML = _watchlist.map(sym => `
    <div class="watchlist-item${sym === _selected ? ' active' : ''}" data-wl="${sym}">
      <div class="watchlist-item-left">
        <div class="watchlist-item-ticker">${sym}</div>
        <div class="watchlist-item-name">${companyName(sym)}</div>
      </div>
      <div class="watchlist-item-right">
        <div style="font-family:var(--f-display);font-size:11px;font-weight:600;color:var(--text-primary)">${mockPrice(sym)}</div>
        <div class="chip-chg ${mockChg(sym) >= 0 ? 'pos' : 'neg'}" style="font-size:10px">
          ${mockChg(sym) > 0 ? '+' : ''}${mockChg(sym).toFixed(2)}%
        </div>
      </div>
    </div>`).join('');
}

/* ══════════════════════════════════════════════
   EVENTS
══════════════════════════════════════════════ */
function bindEvents(container) {
  container.addEventListener('click', async e => {
    /* Config toggle */
    if (e.target.closest('#config-toggle')) {
      const body = container.querySelector('#config-body');
      const foot = container.querySelector('.run-panel__foot');
      const collapsed = body.style.display === 'none';
      body.style.display = collapsed ? '' : 'none';
      if (foot) foot.style.display = collapsed ? '' : 'none';
    }
    /* Run pipeline */
    if (e.target.closest('#btn-run-research')) {
      await runResearch(container);
    }
    /* Watchlist item select */
    const wlItem = e.target.closest('[data-wl]');
    if (wlItem) {
      _selected = wlItem.dataset.wl;
      container.querySelectorAll('[data-wl]').forEach(el => el.classList.remove('active'));
      wlItem.classList.add('active');
      container.querySelector('#r-universe').value = _watchlist.join(', ');
    }
    /* Suggestion chips */
    const qBtn = e.target.closest('[data-q]');
    if (qBtn) {
      container.querySelector('#r-question').value = qBtn.dataset.q;
    }
    /* Timeframe result kline */
    const restf = e.target.closest('[data-restf]');
    if (restf) {
      container.querySelectorAll('[data-restf]').forEach(t => t.classList.remove('active'));
      restf.classList.add('active');
    }
    /* Close thesis */
    if (e.target.closest('#btn-close-thesis')) {
      container.querySelector('#thesis-panel').style.display = 'none';
    }
    /* Export to portfolio */
    if (e.target.closest('#btn-export-portfolio') && _result) {
      const signals = _result.signals || [];
      window.sessionStorage.setItem('qt.portfolio.prefill', JSON.stringify({
        signals: signals.map(s => ({ symbol: s.symbol, action: s.action, weight: 1/signals.length }))
      }));
      window.location.hash = '#/portfolio';
    }
    /* Add sym */
    if (e.target.closest('#btn-add-sym')) {
      const sym = prompt('Add ticker symbol:');
      if (sym) {
        const s = sym.toUpperCase().trim();
        if (s && !_watchlist.includes(s)) {
          _watchlist.push(s);
          renderWatchlist(container);
        }
      }
    }
  });

  /* Results table row click → thesis */
  container.querySelector('#results-body').addEventListener('click', e => {
    const tr = e.target.closest('[data-sig-idx]');
    if (tr && _result) {
      const idx = parseInt(tr.dataset.sigIdx);
      const sig = (_result.signals || [])[idx];
      if (sig) showThesis(container, sig);
    }
  });
}

/* ══════════════════════════════════════════════
   RUN RESEARCH
══════════════════════════════════════════════ */
async function runResearch(container) {
  const btn = container.querySelector('#btn-run-research');
  const body = container.querySelector('#results-body');
  const progress = container.querySelector('#run-progress');
  const steps = container.querySelectorAll('.run-step');

  const universeRaw = container.querySelector('#r-universe').value.trim();
  const universe = universeRaw
    ? universeRaw.split(/[,\s]+/).filter(Boolean).map(s => s.toUpperCase())
    : _watchlist;
  const benchmark = container.querySelector('#r-benchmark').value;
  const capital   = Number(container.querySelector('#r-capital').value) || 1000000;
  const horizon   = Number(container.querySelector('#r-horizon').value) || 20;
  const question  = container.querySelector('#r-question').value.trim() ||
                    'Run the default ESG quant research pipeline';

  btn.disabled = true; btn.textContent = '● Running…';
  progress.style.display = '';
  body.innerHTML = `<div class="loading-overlay"><div class="spinner"></div><span>Generating signals…</span></div>`;

  /* Animate steps */
  const stepLabels = ['Fetching market data','Running ESG scoring','Generating signals','Writing thesis'];
  for (let i = 0; i < stepLabels.length; i++) {
    steps[i]?.classList.add('active');
    await new Promise(r => setTimeout(r, 400));
  }

  try {
    const res = await api.research.run({ universe, benchmark, capital_base: capital, horizon_days: horizon, research_question: question });
    _result = res;
    steps.forEach(s => { s.classList.remove('active'); s.classList.add('done'); });
    steps[4]?.classList.add('done');

    const signals = res.signals || [];
    container.querySelector('#results-title').textContent = `${signals.length} Signals Generated`;
    container.querySelector('#results-meta').textContent  = res.generated_at ? new Date(res.generated_at).toLocaleString() : '';
    container.querySelector('#btn-export-portfolio').style.display = signals.length ? '' : 'none';

    body.innerHTML = buildSignalTable(signals);

    /* Show mini kline for first result */
    if (signals.length) {
      showResultKline(container, signals[0].symbol);
      updateSignalSummary(container, signals[0]);
    }

    toast.success('Research complete', `${signals.length} signals generated`);
  } catch (err) {
    body.innerHTML = `<div class="empty-state">
      <div class="empty-state__title">Pipeline Error</div>
      <div class="empty-state__text">${err.message}</div>
    </div>`;
    toast.error('Research failed', err.message);
  } finally {
    btn.disabled = false; btn.textContent = '▶ Run Research Pipeline';
    setTimeout(() => { progress.style.display = 'none'; }, 1500);
  }
}

/* ══════════════════════════════════════════════
   SIGNAL TABLE
══════════════════════════════════════════════ */
function buildSignalTable(signals) {
  if (!signals.length) return `<div class="empty-state"><div class="empty-state__title">No signals</div></div>`;
  const rows = signals.map((s, i) => `
    <tr data-sig-idx="${i}" style="cursor:pointer">
      <td class="cell-symbol">${s.symbol}</td>
      <td class="text-dim" style="max-width:120px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${s.company_name || ''}</td>
      <td><span class="badge badge-${s.action}">${(s.action||'').toUpperCase()}</span></td>
      <td class="cell-num ${pctCls(s.confidence)}">${pct(s.confidence)}</td>
      <td class="cell-num ${pctCls(s.expected_return)}">${pct(s.expected_return)}</td>
      <td class="cell-num">${num(s.overall_score)}</td>
      <td class="cell-num">${num(s.e_score)}</td>
      <td class="cell-num">${num(s.g_score)}</td>
      <td class="text-dim text-sm">${(s.sector||'').substring(0,14)}</td>
      <td style="max-width:160px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-family:var(--f-mono);font-size:10px;color:var(--text-dim)">
        ${(s.thesis||'').substring(0,50)}${s.thesis?.length > 50 ? '…' : ''}
      </td>
    </tr>`).join('');
  return `
    <div class="tbl-wrap">
      <table>
        <thead><tr>
          <th>Symbol</th><th>Company</th><th>Action</th>
          <th>Conf%</th><th>Exp.Ret</th><th>Score</th><th>E</th><th>G</th><th>Sector</th><th>Thesis</th>
        </tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
    <div class="card-footer">
      ${signals.filter(s=>s.action==='long').length} long ·
      ${signals.filter(s=>s.action==='short').length} short ·
      ${signals.filter(s=>s.action==='neutral').length} neutral
      &nbsp;—&nbsp;Click a row to see full thesis
    </div>`;
}

/* ══════════════════════════════════════════════
   THESIS PANEL
══════════════════════════════════════════════ */
function showThesis(container, signal) {
  const panel = container.querySelector('#thesis-panel');
  container.querySelector('#thesis-symbol').textContent = `${signal.symbol} · ${(signal.action||'').toUpperCase()} THESIS`;
  container.querySelector('#thesis-content').innerHTML = signal.thesis
    ? signal.thesis.replace(/\n/g, '<br>')
    : `<span style="color:var(--text-dim)">No detailed thesis available. Run research pipeline with a specific question for detailed analysis.</span>`;

  const chips = container.querySelector('#thesis-chips');
  const tags = [
    signal.action === 'long' ? 'Momentum ▲' : 'Weak Momentum ▼',
    `ESG Score ${num(signal.overall_score)}`,
    signal.expected_return > 0 ? `Expected +${pct(signal.expected_return)}` : `Expected ${pct(signal.expected_return)}`,
    signal.sector || '',
  ].filter(Boolean);
  chips.innerHTML = tags.map(t => `<span class="context-chip">${t}</span>`).join('');
  panel.style.display = '';
  panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  showResultKline(container, signal.symbol);
}

/* ══════════════════════════════════════════════
   MINI K-LINE FOR RESULTS
══════════════════════════════════════════════ */
function showResultKline(container, symbol) {
  const wrap = container.querySelector('#result-kline');
  const titleEl = container.querySelector('#result-kline-title');
  const canvas = container.querySelector('#result-kline-canvas');
  if (!wrap || !canvas) return;
  wrap.style.display = '';
  if (titleEl) titleEl.textContent = `K-LINE: ${symbol}`;

  const dpr = window.devicePixelRatio || 1;
  canvas.width  = (canvas.parentElement.offsetWidth || 700) * dpr;
  canvas.height = 200 * dpr;
  canvas.style.height = '200px';
  const ctx = canvas.getContext('2d');
  const W = canvas.width, H = canvas.height;
  const candles = genCandles(symbol, 40);
  const padL = 50 * dpr, padR = 20 * dpr, padT = 14 * dpr, padB = 24 * dpr;
  const cw = ((W - padL - padR) / candles.length) * 0.65;
  const cs = (W - padL - padR) / candles.length;
  const prices = candles.flatMap(c => [c.high, c.low]);
  const minP = Math.min(...prices) * 0.999;
  const maxP = Math.max(...prices) * 1.001;
  const pY = p => padT + (H - padT - padB) - ((p - minP) / (maxP - minP)) * (H - padT - padB);

  ctx.clearRect(0, 0, W, H);
  ctx.fillStyle = '#07070F'; ctx.fillRect(0, 0, W, H);

  candles.forEach((c, i) => {
    const x = padL + i * cs + cs / 2;
    const ox = pY(c.open), cx2 = pY(c.close), hx = pY(c.high), lx = pY(c.low);
    const color = c.close >= c.open ? '#00FF88' : '#FF3D57';
    ctx.strokeStyle = color; ctx.lineWidth = dpr;
    ctx.beginPath(); ctx.moveTo(x, hx); ctx.lineTo(x, lx); ctx.stroke();
    const bodyTop = Math.min(ox, cx2);
    const bodyH   = Math.max(Math.abs(ox - cx2), dpr);
    ctx.fillStyle = c.close >= c.open ? 'transparent' : color;
    ctx.strokeStyle = color; ctx.lineWidth = dpr;
    ctx.fillRect(x - cw/2, bodyTop, cw, bodyH);
    ctx.strokeRect(x - cw/2, bodyTop, cw, bodyH);
  });
}

/* ══════════════════════════════════════════════
   HELPERS
══════════════════════════════════════════════ */
function genCandles(sym, n) {
  let price = 80 + (sym.charCodeAt(0) % 120) + 50;
  return Array.from({ length: n }, () => {
    const vol = 0.012 + Math.random() * 0.018;
    const open = price;
    const close = price * (1 + (Math.random() - 0.48) * vol * 2);
    const high = Math.max(open, close) * (1 + Math.random() * vol * 0.5);
    const low  = Math.min(open, close) * (1 - Math.random() * vol * 0.5);
    price = close;
    return { open, high, low, close };
  });
}

function mockPrice(sym) {
  const seed = sym.split('').reduce((s, c) => s + c.charCodeAt(0), 0);
  return '$' + (50 + (seed % 500) + (seed % 200)).toFixed(2);
}

function mockChg(sym) {
  const seed = sym.charCodeAt(0) * 17 % 100;
  return ((seed - 50) / 25).toFixed(2) * 1;
}

function companyName(sym) {
  const names = { AAPL:'Apple Inc.', MSFT:'Microsoft Corp.', NVDA:'NVIDIA Corp.', TSLA:'Tesla Inc.',
    NEE:'NextEra Energy', AMZN:'Amazon.com', GOOGL:'Alphabet Inc.', META:'Meta Platforms' };
  return names[sym] || sym + ' Corp.';
}

function mockNews() {
  return [
    { headline: 'Fed signals steady rates through Q2, markets rally on stability hopes', sent: 'long', source: 'Reuters', time: '2h ago' },
    { headline: 'NVDA earnings beat consensus by 12%, raises guidance on AI demand surge', sent: 'long', source: 'Bloomberg', time: '4h ago' },
    { headline: 'ESG fund flows hit record $45B in Q1, driven by institutional mandates', sent: 'neutral', source: 'FT', time: '6h ago' },
    { headline: 'Energy sector faces headwinds as oil inventory builds unexpectedly', sent: 'short', source: 'WSJ', time: '8h ago' },
    { headline: 'Tech layoffs continue, but AI hiring offsets losses in sector employment', sent: 'neutral', source: 'CNBC', time: '12h ago' },
  ];
}

function updateSignalSummary(container, signal) { /* no-op for research page */ }

const pctCls = v => v > 0 ? 'cell-pos' : v < 0 ? 'cell-neg' : '';
const pct    = v => v == null ? '—' : `${(v * 100).toFixed(1)}%`;
const num    = v => v == null ? '—' : Number(v).toFixed(2);
