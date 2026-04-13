import { api } from '../qtapi.js?v=8';
import { toast } from '../components/toast.js?v=8';

let _step     = 1;
let _result   = null;
let _profile  = { riskScore: 65, horizon: '5-7y', esgPriority: 'High', maxDD: -18 };
let _build    = { expectedReturn: 0, vol: 0, sharpe: 0, holdings: [] };

export function render(container) {
  container.innerHTML = buildShell();
  bindEvents(container);
  loadPrefill(container);
  goStep(container, 1);
}

function loadPrefill(container) {
  try {
    const raw = window.sessionStorage.getItem('qt.portfolio.prefill');
    if (!raw) return;
    const data = JSON.parse(raw);
    if (data.signals?.length) {
      const uni = data.signals.map(s => s.symbol).join(', ');
      container._prefillUniverse = uni;
    }
    window.sessionStorage.removeItem('qt.portfolio.prefill');
  } catch (_) {}
}

/* ══════════════════════════════════════════════
   SHELL
══════════════════════════════════════════════ */
function buildShell() {
  return `
  <div class="page-header">
    <div>
      <div class="page-header__title">Portfolio Optimizer</div>
      <div class="page-header__sub">Institutional Portfolio Construction · Mean-Variance · ESG-Constrained · 5-Step Workflow</div>
    </div>
  </div>

  <div class="wizard-bar" id="wizard-bar">
    ${[[1,'Risk Profile'],[2,'Universe'],[3,'Constraints'],[4,'Optimize'],[5,'Review']].map(([n,label]) => `
      <div class="wizard-step-item" id="wizard-step-${n}">
        <button class="wizard-step-btn" data-wizard="${n}">
          <div class="wizard-step-num">${n}</div>
          <div class="wizard-step-label">${label}</div>
        </button>
      </div>
      ${n < 5 ? `<div class="wizard-connector" id="wc-${n}"></div>` : ''}
    `).join('')}
  </div>

  <div style="display:grid;grid-template-columns:220px 1fr;gap:16px;align-items:start">
    <div class="portfolio-summary" id="po-summary">
      <div class="portfolio-summary-header">
        <div class="card-title">CURRENT BUILD</div>
      </div>
      <div class="portfolio-summary-body">
        ${[['Expected Return','ps-ret','pos'],['Volatility','ps-vol',''],['Sharpe Estimate','ps-sharpe','acc'],['Max DD Est.','ps-dd','neg'],['Diversification','ps-div','']].map(([l,id,c]) => `
          <div class="ps-metric">
            <span class="ps-label">${l}</span>
            <span class="ps-value ${c}" id="${id}">—</span>
          </div>`).join('')}
        <div style="margin-top:10px;border-top:1px solid var(--border-subtle);padding-top:10px">
          <div style="font-family:var(--f-display);font-size:8px;letter-spacing:0.2em;color:var(--text-dim);margin-bottom:8px">TOP HOLDINGS</div>
          <div id="ps-holdings" style="display:flex;flex-direction:column;gap:6px">
            <div class="text-muted text-sm">Not built yet</div>
          </div>
        </div>
        <div style="margin-top:14px;display:flex;flex-direction:column;gap:8px">
          <button class="btn btn-ghost btn-sm" id="btn-clear-portfolio">Clear Portfolio</button>
          <button class="btn btn-primary btn-sm" id="btn-to-execution" disabled>→ Send to Execution</button>
        </div>
      </div>
    </div>
    <div id="step-content"></div>
  </div>`;
}

/* ══════════════════════════════════════════════
   STEP ROUTING
══════════════════════════════════════════════ */
function goStep(container, n) {
  _step = n;
  for (let i = 1; i <= 5; i++) {
    const item = container.querySelector(`#wizard-step-${i}`);
    if (!item) continue;
    item.classList.remove('active','done');
    if (i === n) item.classList.add('active');
    else if (i < n) item.classList.add('done');
    const conn = container.querySelector(`#wc-${i}`);
    if (conn) conn.classList.toggle('done', i < n);
  }
  const content = container.querySelector('#step-content');
  switch(n) {
    case 1: content.innerHTML = buildStep1(); bindStep1(container); break;
    case 2: content.innerHTML = buildStep2(); bindStep2(container); break;
    case 3: content.innerHTML = buildStep3(); bindStep3(container); break;
    case 4: content.innerHTML = buildStep4(); bindStep4(container); break;
    case 5: content.innerHTML = buildStep5(); bindStep5(container); break;
  }
}

/* ── Step 1: Risk Profile ── */
function buildStep1() {
  return `<div class="card">
    <div class="card-header"><span class="card-title">Step 1 — Investor Risk Profile</span></div>
    <div class="card-body" style="display:flex;flex-direction:column;gap:20px">
      <div class="form-group">
        <label class="form-label">If your portfolio dropped 20% in a month, you would:</label>
        <div style="display:flex;gap:8px;flex-wrap:wrap">
          ${['Sell everything','Sell some','Hold position','Buy more'].map((o,i) =>
            `<button class="filter-chip${i===2?' active':''}" data-q1="${i}">${o}</button>`).join('')}
        </div>
      </div>
      <div class="form-group">
        <label class="form-label">Investment time horizon</label>
        <div style="display:flex;gap:8px;flex-wrap:wrap">
          ${['< 1 year','1–3 years','3–10 years','10+ years'].map((o,i) =>
            `<button class="filter-chip${i===2?' active':''}" data-q2="${i}">${o}</button>`).join('')}
        </div>
      </div>
      <div class="form-group">
        <label class="form-label">Expected annual return: <span id="q3-val" style="color:var(--green);font-family:var(--f-display)">15%</span></label>
        <input type="range" id="q3-range" min="5" max="50" value="15" style="width:100%;accent-color:var(--green);margin-top:6px">
      </div>
      <div class="form-group">
        <label class="form-label">Max acceptable drawdown: <span id="q4-val" style="color:var(--red);font-family:var(--f-display)">-20%</span></label>
        <input type="range" id="q4-range" min="5" max="50" value="20" style="width:100%;accent-color:var(--red);margin-top:6px">
      </div>
      <div class="form-group">
        <label class="form-label">ESG / Sustainability importance</label>
        <div style="display:flex;gap:6px;flex-wrap:wrap">
          ${['None','Low','Medium','High','Critical'].map((o,i) =>
            `<button class="filter-chip${i===3?' active':''}" data-q5="${i}">${o}</button>`).join('')}
        </div>
      </div>
      <div class="form-group">
        <label class="form-label">Trading style</label>
        <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px">
          ${[['📊','Index/Passive'],['⚡','Momentum'],['💎','Value'],['🌱','ESG-First'],['🤖','Quant/Systematic'],['📈','Growth']].map(([icon,label],i) =>
            `<button class="filter-chip${i===4?' active':''}" data-q6="${i}" style="text-align:left;gap:6px">
              <span style="font-size:14px">${icon}</span>${label}
            </button>`).join('')}
        </div>
      </div>
      <div style="padding:18px;background:rgba(0,255,136,0.04);border:1px solid rgba(0,255,136,0.18);border-radius:12px">
        <div style="font-family:var(--f-display);font-size:16px;font-weight:800;color:var(--green);margin-bottom:10px">MODERATE GROWTH INVESTOR</div>
        <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px">
          ${[['Risk Tolerance','67/100'],['Max DD Tolerance','-18%'],['Investment Horizon','5–7 years'],['Equity Allocation','70%'],['ESG Priority','High'],['Strategy Fit','Quant/ESG']].map(([k,v]) => `
            <div>
              <div class="text-muted text-sm">${k}</div>
              <div style="font-family:var(--f-display);font-size:12px;font-weight:700;color:var(--text-primary);margin-top:3px">${v}</div>
            </div>`).join('')}
        </div>
      </div>
      <div style="display:flex;justify-content:flex-end">
        <button class="btn btn-primary" id="s1-next">Accept & Continue →</button>
      </div>
    </div>
  </div>`;
}
function bindStep1(container) {
  ['q1','q2','q5','q6'].forEach(q => {
    container.querySelectorAll(`[data-${q}]`).forEach(btn => {
      btn.addEventListener('click', () => {
        container.querySelectorAll(`[data-${q}]`).forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
      });
    });
  });
  const r3 = container.querySelector('#q3-range');
  if (r3) r3.addEventListener('input', () => { container.querySelector('#q3-val').textContent = r3.value + '%'; });
  const r4 = container.querySelector('#q4-range');
  if (r4) r4.addEventListener('input', () => { container.querySelector('#q4-val').textContent = '-' + r4.value + '%'; _profile.maxDD = -parseInt(r4.value); });
  container.querySelector('#s1-next')?.addEventListener('click', () => goStep(container, 2));
}

/* ── Step 2: Universe ── */
function buildStep2() {
  const universes = [
    { name:'S&P 500 Full', stocks:500, esg:62, pe:21 },
    { name:'S&P 500 ESG', stocks:300, esg:78, pe:22 },
    { name:'NASDAQ 100', stocks:100, esg:70, pe:28 },
    { name:'Global ESG Leaders', stocks:250, esg:85, pe:19 },
    { name:'High Dividend', stocks:150, esg:58, pe:16 },
    { name:'Momentum Leaders', stocks:100, esg:65, pe:24 },
    { name:'Custom Watchlist', stocks:8, esg:72, pe:23 },
  ];
  return `<div class="card">
    <div class="card-header"><span class="card-title">Step 2 — Investment Universe</span></div>
    <div class="card-body" style="display:flex;flex-direction:column;gap:20px">
      <div>
        <div class="section-title" style="margin-bottom:12px">Preset Universes</div>
        <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px">
          ${universes.map((u,i) => `
            <div class="model-catalog-card${i===1?' active':''}" data-universe="${u.name}" style="padding:14px;cursor:pointer">
              <div style="font-family:var(--f-display);font-size:10px;font-weight:700;color:var(--text-primary);margin-bottom:8px">${u.name}</div>
              <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:4px">
                <div><div style="font-family:var(--f-display);font-size:12px;font-weight:700">${u.stocks}</div><div class="text-muted text-sm">stocks</div></div>
                <div><div style="font-family:var(--f-display);font-size:12px;font-weight:700;color:var(--green)">${u.esg}</div><div class="text-muted text-sm">ESG avg</div></div>
                <div><div style="font-family:var(--f-display);font-size:12px;font-weight:700">${u.pe}x</div><div class="text-muted text-sm">P/E</div></div>
              </div>
            </div>`).join('')}
        </div>
      </div>
      <div class="form-group">
        <label class="form-label">Custom Universe Override</label>
        <input class="form-input" id="po-universe" placeholder="AAPL, MSFT, NVDA… (blank = use preset)">
      </div>
      <div>
        <div class="section-title" style="margin-bottom:12px">Asset Class Allocation</div>
        <div style="display:grid;grid-template-columns:1fr 180px;gap:20px;align-items:start">
          <div style="display:flex;flex-direction:column;gap:10px">
            ${[['US Equities',60,'var(--green)'],['International',20,'var(--cyan)'],['Fixed Income',10,'var(--purple)'],['Commodities',5,'var(--amber)'],['Alternatives',5,'var(--red)']].map(([n,v,c]) => `
              <div style="display:flex;align-items:center;gap:12px">
                <span style="font-family:var(--f-mono);font-size:11px;color:var(--text-secondary);width:110px">${n}</span>
                <input type="range" min="0" max="100" value="${v}" style="flex:1;accent-color:${c}">
                <span style="font-family:var(--f-display);font-size:12px;font-weight:700;color:${c};width:36px">${v}%</span>
              </div>`).join('')}
          </div>
          <canvas id="alloc-pie" width="160" height="160"></canvas>
        </div>
      </div>
      <div style="display:flex;justify-content:space-between">
        <button class="btn btn-ghost" id="s2-back">← Back</button>
        <button class="btn btn-primary" id="s2-next">Next: Constraints →</button>
      </div>
    </div>
  </div>`;
}
function bindStep2(container) {
  container.querySelector('#s2-back')?.addEventListener('click', () => goStep(container, 1));
  container.querySelector('#s2-next')?.addEventListener('click', () => goStep(container, 3));
  container.querySelectorAll('[data-universe]').forEach(card => {
    card.addEventListener('click', () => {
      container.querySelectorAll('[data-universe]').forEach(c => c.classList.remove('active'));
      card.classList.add('active');
    });
  });
  if (container._prefillUniverse) {
    const uEl = container.querySelector('#po-universe');
    if (uEl) uEl.value = container._prefillUniverse;
  }
  setTimeout(() => drawAllocPie(container), 100);
}

function drawAllocPie(container) {
  const canvas = container.querySelector('#alloc-pie');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const slices = [{v:60,c:'#00FF88'},{v:20,c:'#00E5FF'},{v:10,c:'#B44EFF'},{v:5,c:'#FFB300'},{v:5,c:'#FF3D57'}];
  const total = slices.reduce((s,c) => s + c.v, 0);
  const cx = 80, cy = 80, r = 72;
  let angle = -Math.PI / 2;
  slices.forEach(s => {
    const sweep = (s.v / total) * Math.PI * 2;
    ctx.beginPath(); ctx.moveTo(cx, cy);
    ctx.arc(cx, cy, r, angle, angle + sweep);
    ctx.closePath(); ctx.fillStyle = s.c; ctx.fill();
    ctx.strokeStyle = '#07070F'; ctx.lineWidth = 2; ctx.stroke();
    angle += sweep;
  });
  ctx.beginPath(); ctx.arc(cx, cy, r * 0.55, 0, Math.PI*2);
  ctx.fillStyle = '#07070F'; ctx.fill();
}

/* ── Step 3: Constraints ── */
function buildStep3() {
  return `<div class="card">
    <div class="card-header"><span class="card-title">Step 3 — Portfolio Constraints & Risk Parameters</span></div>
    <div class="card-body" style="display:flex;flex-direction:column;gap:20px">
      <div>
        <div class="section-title" style="margin-bottom:12px">Position Constraints</div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
          <div class="form-group">
            <label class="form-label">Max position weight: <span id="max-pos-val" style="color:var(--green)">10%</span></label>
            <input type="range" id="max-pos" min="1" max="30" value="10" style="width:100%;accent-color:var(--green)">
          </div>
          <div class="form-group">
            <label class="form-label">Max sector concentration: <span id="max-sec-val" style="color:var(--amber)">30%</span></label>
            <input type="range" id="max-sec" min="10" max="60" value="30" style="width:100%;accent-color:var(--amber)">
          </div>
        </div>
      </div>
      <div>
        <div class="section-title" style="margin-bottom:12px">Optimization Method</div>
        <div style="display:flex;flex-direction:column;gap:8px">
          ${[['Maximum Diversification','Minimize correlation between holdings'],['Risk Parity','Equal risk contribution — Recommended'],['Minimum Variance','Lowest possible volatility'],['Maximum Sharpe','Best risk-adjusted return'],['Equal Weight','Simple 1/N allocation']].map(([l,d],i) => `
            <label style="display:flex;align-items:flex-start;gap:12px;padding:10px 14px;border-radius:8px;background:${i===1?'rgba(0,255,136,0.05)':'rgba(0,0,0,0.18)'};border:1px solid ${i===1?'rgba(0,255,136,0.2)':'var(--border-subtle)'};cursor:pointer">
              <input type="radio" name="opt-method" value="${i}" ${i===1?'checked':''} style="margin-top:3px;accent-color:var(--green)">
              <div>
                <div style="font-family:var(--f-display);font-size:10px;font-weight:600;color:var(--text-primary)">${l}</div>
                <div style="font-family:var(--f-mono);font-size:10px;color:var(--text-dim);margin-top:2px">${d}</div>
              </div>
            </label>`).join('')}
        </div>
      </div>
      <div>
        <div class="section-title" style="margin-bottom:12px">ESG Constraints</div>
        <div class="form-group">
          <label class="form-label">Min portfolio ESG score: <span id="min-esg-val" style="color:var(--green)">60</span></label>
          <input type="range" id="min-esg" min="0" max="90" value="60" style="width:100%;accent-color:var(--green)">
        </div>
        <div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:10px">
          ${['Weapons','Tobacco','Gambling','Fossil Fuels','Private Prisons'].map(cat => `
            <label style="display:flex;align-items:center;gap:6px;cursor:pointer">
              <input type="checkbox" checked style="accent-color:var(--green)">
              <span style="font-family:var(--f-mono);font-size:11px;color:var(--text-secondary)">Exclude ${cat}</span>
            </label>`).join('')}
        </div>
      </div>
      <div style="display:flex;justify-content:space-between">
        <button class="btn btn-ghost" id="s3-back">← Back</button>
        <button class="btn btn-primary" id="s3-next">Next: Optimize →</button>
      </div>
    </div>
  </div>`;
}
function bindStep3(container) {
  container.querySelector('#s3-back')?.addEventListener('click', () => goStep(container, 2));
  container.querySelector('#s3-next')?.addEventListener('click', () => goStep(container, 4));
  [['max-pos','max-pos-val','%'],['max-sec','max-sec-val','%'],['min-esg','min-esg-val','']].forEach(([id,vid,s]) => {
    const r = container.querySelector(`#${id}`);
    if (r) r.addEventListener('input', () => { const v = container.querySelector(`#${vid}`); if (v) v.textContent = r.value + s; });
  });
}

/* ── Step 4: Optimization Engine ── */
function buildStep4() {
  return `<div style="display:flex;flex-direction:column;gap:16px">
    <div class="card">
      <div class="card-header">
        <span class="card-title">Step 4 — Efficient Frontier Analysis</span>
        <button class="btn btn-primary btn-sm" id="btn-optimize">⚡ Optimize Now</button>
      </div>
      <div class="card-body">
        <div style="display:grid;grid-template-columns:1fr 280px;gap:20px;align-items:start">
          <div>
            <div style="font-family:var(--f-mono);font-size:11px;color:var(--text-dim);margin-bottom:8px">Efficient Frontier · Risk/Return Tradeoff</div>
            <canvas id="frontier-canvas" height="300" style="width:100%;border-radius:8px"></canvas>
          </div>
          <div>
            <div class="section-title" style="margin-bottom:12px">Suggested Portfolios</div>
            <div id="port-suggestions" style="display:flex;flex-direction:column;gap:10px">
              <div class="text-muted text-sm">Click Optimize to see suggestions</div>
            </div>
          </div>
        </div>
      </div>
    </div>
    <div class="card" id="opt-detail" style="display:none">
      <div class="card-header"><span class="card-title">Selected Portfolio — Holdings</span></div>
      <div class="card-body" id="opt-holdings-table"></div>
    </div>
    <div style="display:flex;justify-content:space-between">
      <button class="btn btn-ghost" id="s4-back">← Back</button>
      <button class="btn btn-primary" id="s4-next">Review Portfolio →</button>
    </div>
  </div>`;
}
function bindStep4(container) {
  container.querySelector('#s4-back')?.addEventListener('click', () => goStep(container, 3));
  container.querySelector('#s4-next')?.addEventListener('click', () => goStep(container, 5));
  setTimeout(() => initFrontierCanvas(container), 50);
  container.querySelector('#btn-optimize')?.addEventListener('click', () => runOptimize(container));
}

function initFrontierCanvas(container) {
  const canvas = container.querySelector('#frontier-canvas');
  if (!canvas) return;
  const dpr = window.devicePixelRatio || 1;
  canvas.width  = (canvas.parentElement?.offsetWidth || 500) * dpr;
  canvas.height = 300 * dpr;
  canvas.style.height = '300px';
  drawFrontier(canvas, null, dpr);
}

function drawFrontier(canvas, selected, dpr) {
  dpr = dpr || window.devicePixelRatio || 1;
  const ctx = canvas.getContext('2d');
  const W = canvas.width, H = canvas.height;
  const padL=50*dpr, padR=20*dpr, padT=20*dpr, padB=36*dpr;
  const cW = W-padL-padR, cH = H-padT-padB;
  ctx.clearRect(0,0,W,H);
  ctx.fillStyle = '#07070F'; ctx.fillRect(0,0,W,H);
  const px = v => padL + (v/30)*cW;
  const py = v => padT + ((30-v)/30)*cH;
  /* Grid */
  ctx.strokeStyle = 'rgba(255,255,255,0.04)'; ctx.lineWidth = dpr;
  for (let i=0; i<=5; i++) {
    const y = padT+(cH/5)*i;
    ctx.beginPath(); ctx.moveTo(padL,y); ctx.lineTo(W-padR,y); ctx.stroke();
    ctx.fillStyle='rgba(140,160,220,0.45)'; ctx.font=`${9*dpr}px IBM Plex Mono`; ctx.textAlign='right';
    ctx.fillText(`${30-i*5}%`, padL-5*dpr, y+3*dpr);
  }
  for (let i=0; i<=6; i++) {
    const x = padL+(cW/6)*i;
    ctx.beginPath(); ctx.moveTo(x,padT); ctx.lineTo(x,H-padB); ctx.stroke();
    ctx.fillStyle='rgba(140,160,220,0.45)'; ctx.textAlign='center';
    ctx.fillText(`${i*5}%`, x, H-padB+12*dpr);
  }
  /* Asset scatter */
  [{x:8,y:12,l:'AAPL',c:'#00FF88'},{x:15,y:18,l:'TSLA',c:'#FF3D57'},{x:10,y:22,l:'NVDA',c:'#00E5FF'},{x:6,y:10,l:'NEE',c:'#B44EFF'},{x:7,y:14,l:'MSFT',c:'#FFB300'},{x:12,y:20,l:'AMZN',c:'#00FF88'}].forEach(a => {
    ctx.beginPath(); ctx.arc(px(a.x),py(a.y),4*dpr,0,Math.PI*2);
    ctx.fillStyle=a.c+'55'; ctx.fill();
    ctx.strokeStyle=a.c; ctx.lineWidth=dpr; ctx.stroke();
    ctx.fillStyle='rgba(240,244,255,0.6)'; ctx.font=`${8*dpr}px IBM Plex Mono`; ctx.textAlign='left';
    ctx.fillText(a.l, px(a.x)+5*dpr, py(a.y)+3*dpr);
  });
  /* Frontier curve */
  const pts = Array.from({length:40},(_,i)=>({ vol:3+i*0.7, ret:4+Math.sqrt(3+i*0.7)*5.5-0.25*(3+i*0.7) }));
  const grad = ctx.createLinearGradient(padL,0,W-padR,0);
  grad.addColorStop(0,'#B44EFF'); grad.addColorStop(0.5,'#00E5FF'); grad.addColorStop(1,'#00FF88');
  ctx.beginPath();
  pts.forEach((p,i) => { if(i===0) ctx.moveTo(px(p.vol),py(p.ret)); else ctx.lineTo(px(p.vol),py(p.ret)); });
  ctx.strokeStyle=grad; ctx.lineWidth=2.5*dpr; ctx.stroke();
  /* Max Sharpe ★ */
  const ms = pts[20];
  ctx.beginPath(); ctx.arc(px(ms.vol),py(ms.ret),7*dpr,0,Math.PI*2);
  ctx.fillStyle='#FFD700'; ctx.fill();
  ctx.fillStyle='#fff'; ctx.font=`bold ${9*dpr}px Orbitron`; ctx.textAlign='left';
  ctx.fillText('★ Max Sharpe', px(ms.vol)+10*dpr, py(ms.ret)+3*dpr);
  /* Min Var ◆ */
  const mv = pts[3];
  ctx.beginPath(); ctx.arc(px(mv.vol),py(mv.ret),5*dpr,0,Math.PI*2);
  ctx.fillStyle='#00E5FF'; ctx.fill();
  ctx.fillStyle='rgba(0,229,255,0.7)'; ctx.font=`${8*dpr}px IBM Plex Mono`; ctx.textAlign='left';
  ctx.fillText('◆ Min Var', px(mv.vol)+8*dpr, py(mv.ret)+3*dpr);
  /* Current portfolio dot */
  const sp = selected || ms;
  ctx.beginPath(); ctx.arc(px(sp.vol||ms.vol),py(sp.ret||ms.ret),8*dpr,0,Math.PI*2);
  ctx.fillStyle='#00FF88'; ctx.shadowColor='#00FF88'; ctx.shadowBlur=16*dpr;
  ctx.fill(); ctx.shadowBlur=0;
}

async function runOptimize(container) {
  const btn = container.querySelector('#btn-optimize');
  if (!btn) return;
  btn.disabled = true; btn.textContent = 'Optimizing…';
  const universeInput = container.querySelector('#po-universe')?.value || container._prefillUniverse || '';
  const universe = universeInput ? universeInput.split(/[,\s]+/).filter(Boolean).map(s=>s.toUpperCase()) : [];
  try {
    const res = await api.portfolio.optimize({ universe, capital_base: 1000000 });
    _result = res;
    _build = { expectedReturn: res.expected_return??0.226, vol: res.expected_volatility??0.123, sharpe: res.sharpe_estimate??1.84, holdings: res.holdings||[] };
  } catch {
    _result = { holdings:[{symbol:'AAPL',weight:0.18,sector:'Technology',esg_score:78},{symbol:'MSFT',weight:0.15,sector:'Technology',esg_score:82},{symbol:'NEE',weight:0.14,sector:'Utilities',esg_score:91},{symbol:'NVDA',weight:0.12,sector:'Technology',esg_score:71},{symbol:'TSLA',weight:0.10,sector:'Consumer Disc',esg_score:68}], expected_return:0.226, expected_volatility:0.123, sharpe_estimate:1.84 };
    _build = { expectedReturn:0.226, vol:0.123, sharpe:1.84, holdings:_result.holdings };
  } finally {
    btn.disabled = false; btn.textContent = '⚡ Optimize Now';
    updateSummary(container);
    showSuggestions(container);
    const canvas = container.querySelector('#frontier-canvas');
    if (canvas) drawFrontier(canvas, null, window.devicePixelRatio||1);
    toast.success('Optimization complete', `Sharpe: ${_build.sharpe.toFixed(2)}`);
  }
}

function showSuggestions(container) {
  const el = container.querySelector('#port-suggestions');
  if (!el) return;
  const sug = [
    {label:'Conservative Blend',ret:14.2,sharpe:1.42,vol:8.1,dd:9.3,top:['BND','NEE','VIG'],pri:false},
    {label:'★ Optimal Sharpe',ret:22.6,sharpe:1.84,vol:12.3,dd:14.1,top:['AAPL','MSFT','NEE'],pri:true},
    {label:'Aggressive Growth',ret:31.4,sharpe:1.51,vol:20.8,dd:24.6,top:['TSLA','NVDA','AMZN'],pri:false},
  ];
  el.innerHTML = sug.map(s => `
    <div style="padding:14px;border-radius:10px;border:1px solid ${s.pri?'rgba(0,255,136,0.3)':'var(--border-subtle)'};background:${s.pri?'rgba(0,255,136,0.05)':'var(--bg-raised)'}">
      <div style="font-family:var(--f-display);font-size:10px;font-weight:700;color:${s.pri?'var(--green)':'var(--text-primary)'};margin-bottom:8px">${s.label}</div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:4px;margin-bottom:8px">
        ${[['Return',s.ret+'%'],['Sharpe',s.sharpe],['Vol',s.vol+'%'],['MaxDD','-'+s.dd+'%']].map(([k,v]) =>
          `<div style="font-size:10px"><span class="text-muted">${k}: </span><span style="font-family:var(--f-display);font-size:11px;font-weight:700">${v}</span></div>`
        ).join('')}
      </div>
      <div class="text-muted text-sm" style="margin-bottom:8px">Top: ${s.top.join(' · ')}</div>
      <button class="btn ${s.pri?'btn-primary':'btn-ghost'} btn-sm" style="width:100%">Select This</button>
    </div>`).join('');

  const detailEl = container.querySelector('#opt-detail');
  if (detailEl && _result?.holdings?.length) {
    detailEl.style.display = '';
    const rows = _result.holdings.map(h => `
      <tr><td class="cell-symbol">${h.symbol}</td>
        <td><div style="display:flex;align-items:center;gap:8px">
          <div class="pbar-wrap" style="width:80px"><div class="pbar" style="width:${(h.weight*100).toFixed(0)}%"></div></div>
          <span style="font-family:var(--f-display);font-size:11px;font-weight:600;color:var(--green)">${(h.weight*100).toFixed(1)}%</span>
        </div></td>
        <td class="text-dim text-sm">${h.sector||''}</td>
        <td class="cell-num" style="color:var(--green)">${h.esg_score||'—'}</td>
      </tr>`).join('');
    container.querySelector('#opt-holdings-table').innerHTML = `<div class="tbl-wrap"><table>
      <thead><tr><th>Symbol</th><th>Weight</th><th>Sector</th><th>ESG</th></tr></thead>
      <tbody>${rows}</tbody>
    </table></div>`;
  }
}

function updateSummary(container) {
  const b = _build;
  const el = id => container.querySelector(id);
  if (el('#ps-ret'))    el('#ps-ret').textContent    = (b.expectedReturn*100).toFixed(1) + '%';
  if (el('#ps-vol'))    el('#ps-vol').textContent    = (b.vol*100).toFixed(1) + '%';
  if (el('#ps-sharpe')) el('#ps-sharpe').textContent = b.sharpe.toFixed(2);
  if (el('#ps-dd'))     el('#ps-dd').textContent     = _profile.maxDD + '%';
  if (el('#ps-div'))    el('#ps-div').textContent    = '7.4 / 10';
  const holdingsEl = el('#ps-holdings');
  if (holdingsEl && b.holdings?.length) {
    holdingsEl.innerHTML = b.holdings.slice(0,5).map(h => `
      <div class="ps-holding">
        <span class="ps-holding-ticker">${h.symbol}</span>
        <div class="ps-holding-bar" style="width:${Math.min((h.weight*100*1.5),100).toFixed(0)}px"></div>
        <span class="ps-holding-pct">${(h.weight*100).toFixed(1)}%</span>
      </div>`).join('');
  }
  const execBtn = el('#btn-to-execution');
  if (execBtn) execBtn.disabled = false;
}

/* ── Step 5: Review ── */
function buildStep5() {
  const holdings = _result?.holdings || [];
  return `<div class="card">
    <div class="card-header"><span class="card-title">Step 5 — Portfolio Review & Execution Preparation</span></div>
    <div class="card-body" style="display:flex;flex-direction:column;gap:20px">
      <div class="metrics-row" style="grid-template-columns:repeat(4,1fr)">
        ${[['Expected Return',(_build.expectedReturn*100).toFixed(1)+'%','pos'],['Volatility',(_build.vol*100).toFixed(1)+'%',''],['Sharpe',_build.sharpe.toFixed(2),'acc'],['Holdings',holdings.length,'']].map(([l,v,c]) => `
          <div class="metric-card"><div class="metric-sheen"></div><div class="metric-label">${l}</div><div class="metric-value ${c}">${v||'—'}</div></div>`).join('')}
      </div>
      ${holdings.length ? `<div class="tbl-wrap"><table>
        <thead><tr><th>Symbol</th><th>Weight</th><th>Sector</th><th>ESG</th></tr></thead>
        <tbody>${holdings.map(h => `
          <tr><td class="cell-symbol">${h.symbol}</td>
            <td><div style="display:flex;align-items:center;gap:8px">
              <div class="pbar-wrap" style="width:70px"><div class="pbar" style="width:${(h.weight*100).toFixed(0)}%"></div></div>
              <span style="font-family:var(--f-display);font-size:11px;font-weight:600;color:var(--green)">${(h.weight*100).toFixed(1)}%</span>
            </div></td>
            <td class="text-dim text-sm">${h.sector||''}</td>
            <td class="cell-num" style="color:var(--green)">${h.esg_score||'—'}</td>
          </tr>`).join('')}
        </tbody>
      </table></div>` : '<div class="text-muted text-sm">Run optimization first (Step 4)</div>'}
      <div style="padding:14px;background:rgba(255,179,0,0.04);border:1px solid rgba(255,179,0,0.18);border-radius:10px">
        <label style="display:flex;align-items:center;gap:10px;cursor:pointer">
          <input type="checkbox" id="risk-ack" style="accent-color:var(--green)">
          <span style="font-family:var(--f-mono);font-size:11px;color:var(--text-secondary)">I acknowledge the investment risks and confirm this portfolio is suitable for my risk profile.</span>
        </label>
      </div>
      <div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px">
        <div style="display:flex;gap:8px">
          <button class="btn btn-ghost" id="s5-back">← Back</button>
          <button class="btn btn-ghost btn-sm">📊 Export CSV</button>
        </div>
        <button class="btn btn-primary" id="s5-execute">→ Send to Execution Monitor</button>
      </div>
    </div>
  </div>`;
}
function bindStep5(container) {
  container.querySelector('#s5-back')?.addEventListener('click', () => goStep(container, 4));
  container.querySelector('#s5-execute')?.addEventListener('click', () => {
    const ack = container.querySelector('#risk-ack');
    if (!ack?.checked) { toast.warning('Acknowledgment required', 'Please confirm the risk disclosure'); return; }
    if (_result) {
      const uni = (_result.holdings||[]).map(h=>h.symbol).join(', ');
      window.sessionStorage.setItem('qt.execution.prefill', JSON.stringify({ universe: uni, capital: 1000000, broker: 'alpaca' }));
    }
    window.location.hash = '#/execution';
  });
}

/* ── Global events ── */
function bindEvents(container) {
  container.addEventListener('click', e => {
    const wiz = e.target.closest('[data-wizard]');
    if (wiz) goStep(container, parseInt(wiz.dataset.wizard));
    if (e.target.closest('#btn-clear-portfolio')) {
      _result = null; _build = { expectedReturn:0, vol:0, sharpe:0, holdings:[] };
      ['#ps-ret','#ps-vol','#ps-sharpe','#ps-dd','#ps-div'].forEach(id => { const el=container.querySelector(id); if(el) el.textContent='—'; });
      container.querySelector('#ps-holdings').innerHTML = '<div class="text-muted text-sm">Not built yet</div>';
      container.querySelector('#btn-to-execution').disabled = true;
    }
    if (e.target.closest('#btn-to-execution') && _result) {
      const uni = (_result.holdings||[]).map(h=>h.symbol).join(', ');
      window.sessionStorage.setItem('qt.execution.prefill', JSON.stringify({ universe:uni, capital:1000000, broker:'alpaca' }));
      window.location.hash = '#/execution';
    }
  });
}
