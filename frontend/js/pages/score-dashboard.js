import { api } from '../qtapi.js?v=8';
import { toast } from '../components/toast.js?v=8';
import { getLang, onLangChange, translateLoose } from '../i18n.js?v=8';

const PEERS_DEFAULT = { TSLA: ['F','GM','NIO'], AAPL: ['MSFT','GOOGL','META'], NVDA: ['AMD','INTC','AVGO'] };

const DIMENSIONS = [
  { key: 'environment', label: 'Environment', icon: '🌿', color: '#00FF88', desc: 'Carbon emissions, energy efficiency, water usage, waste management, clean energy transition.' },
  { key: 'social',      label: 'Social',      icon: '🤝', color: '#00E5FF', desc: 'Labor practices, workplace safety, diversity & inclusion, community impact, human rights.' },
  { key: 'governance',  label: 'Governance',  icon: '⚖️', color: '#B44EFF', desc: 'Board independence, executive pay alignment, audit quality, shareholder rights, transparency.' },
];

const SUB_SCORES = {
  environment: ['Carbon Intensity','Renewable Energy %','Water Efficiency','Waste Reduction','Climate Risk'],
  social:      ['Workforce Diversity','Safety Record','Community Score','Supply Chain Ethics','Employee Wellbeing'],
  governance:  ['Board Independence','CEO Pay Ratio','Audit Quality','Shareholder Rights','Anti-corruption'],
};

let _currentContainer = null;
let _lastScoreResponse = null;
let _langCleanup = null;

export function render(container) {
  _currentContainer = container;
  container.innerHTML = buildShell();
  bindEvents(container);
  _langCleanup ||= onLangChange(() => {
    if (_currentContainer?.isConnected && _lastScoreResponse) {
      renderScore(_currentContainer, _lastScoreResponse);
    }
  });
  // Auto-render mock data for the default company
  renderScore(container, mockEsgResult('Tesla', 'TSLA'));
}

export function destroy() {
  _currentContainer = null;
  _lastScoreResponse = null;
  _langCleanup?.();
  _langCleanup = null;
}

/* ── Shell ── */
function buildShell() {
  return `
  <div class="page-header">
    <div>
      <div class="page-header__title">ESG Score Dashboard</div>
      <div class="page-header__sub">Environmental · Social · Governance · Peer Comparison · Trend Analysis</div>
    </div>
    <div class="page-header__actions">
      <button class="btn btn-ghost btn-sm" id="btn-export-esg">⬇ Export Report</button>
    </div>
  </div>

  <div class="grid-sidebar" style="align-items:start">
    <!-- LEFT: Config -->
    <div style="display:flex;flex-direction:column;gap:14px">
      <div class="run-panel">
        <div class="run-panel__header">
          <div class="run-panel__title">Score Company</div>
          <div class="run-panel__sub">ESG agent · Peer benchmark · Trend</div>
        </div>
        <div class="run-panel__body">
          <div class="form-row">
            <div class="form-group">
              <label class="form-label">Company Name</label>
              <input class="form-input" id="score-company" value="Tesla">
            </div>
            <div class="form-group">
              <label class="form-label">Ticker</label>
              <input class="form-input" id="score-ticker" value="TSLA" style="text-transform:uppercase">
            </div>
          </div>
          <div class="form-group">
            <label class="form-label">Peer Companies (for benchmark)</label>
            <input class="form-input" id="score-peers" placeholder="F, GM, NIO (auto-fill on ticker)">
          </div>
          <div class="form-group">
            <label class="form-label">Analysis Depth</label>
            <select class="form-select" id="score-depth">
              <option value="standard" selected>Standard (E+S+G)</option>
              <option value="deep">Deep (All sub-dimensions)</option>
              <option value="quick">Quick Score</option>
            </select>
          </div>
        </div>
        <div class="run-panel__foot">
          <button class="btn btn-primary btn-lg" id="score-btn" style="flex:1">▶ Run ESG Score</button>
        </div>
      </div>

      <!-- Trend Chart -->
      <div class="card">
        <div class="card-header"><span class="card-title">Score Trend (12mo)</span></div>
        <div class="card-body" style="padding:0">
          <canvas id="esg-trend-canvas" height="120" style="width:100%"></canvas>
        </div>
      </div>

      <!-- Quick compare -->
      <div class="card">
        <div class="card-header"><span class="card-title">Quick Compare</span></div>
        <div id="quick-compare-list" style="display:flex;flex-direction:column;gap:0"></div>
      </div>
    </div>

    <!-- RIGHT: Results -->
    <div style="display:flex;flex-direction:column;gap:16px">

      <!-- ESG Hero Banner -->
      <div class="esg-hero" id="esg-hero">
        <div class="esg-hero-left">
          <div class="esg-hero-company" id="esg-company-name">Tesla, Inc.</div>
          <div class="esg-hero-ticker" id="esg-ticker-val">TSLA</div>
          <div id="esg-verdict-tag"></div>
        </div>
        <div style="display:flex;gap:24px;align-items:center">
          <!-- Ring gauge -->
          <div style="text-align:center">
            <canvas id="esg-ring" width="120" height="120"></canvas>
            <div style="font-size:9px;color:var(--text-dim);font-family:var(--f-mono);margin-top:4px">OVERALL</div>
          </div>
          <!-- E S G bars -->
          <div class="esg-dim-row" id="esg-dim-row"></div>
        </div>
      </div>

      <!-- 3 Dimension Cards -->
      <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px" id="esg-dim-cards"></div>

      <!-- Radar Canvas -->
      <div class="card">
        <div class="card-header"><span class="card-title">Multi-Dimension Radar</span></div>
        <div style="display:flex;align-items:center;gap:0">
          <div style="flex:1;display:flex;justify-content:center;padding:16px 0">
            <canvas id="esg-radar" width="280" height="280"></canvas>
          </div>
          <div id="radar-legend" style="padding:0 18px;display:flex;flex-direction:column;gap:6px;min-width:150px"></div>
        </div>
      </div>

      <!-- Peer Comparison Table -->
      <div class="card">
        <div class="card-header"><span class="card-title">Peer Comparison</span></div>
        <div class="tbl-wrap" id="peer-table"></div>
      </div>

    </div>
  </div>`;
}

/* ── Events ── */
function bindEvents(container) {
  container.querySelector('#score-btn').addEventListener('click', () => runScore(container));
  container.querySelector('#score-ticker').addEventListener('change', e => {
    const ticker = e.target.value.trim().toUpperCase();
    const peers = PEERS_DEFAULT[ticker];
    if (peers) container.querySelector('#score-peers').value = peers.join(', ');
  });
  container.querySelector('#btn-export-esg').addEventListener('click', () => toast.info('Export', 'PDF export not yet connected'));
}

/* ── API call ── */
async function runScore(container) {
  const btn = container.querySelector('#score-btn');
  btn.disabled = true; btn.textContent = '● Scoring…';

  const company = container.querySelector('#score-company').value.trim();
  const ticker  = container.querySelector('#score-ticker').value.trim().toUpperCase() || null;
  const peersRaw = container.querySelector('#score-peers').value.trim();
  const peers = peersRaw ? peersRaw.split(/[,\s]+/).filter(Boolean) : null;

  try {
    const response = await api.agent.esgScore({ company, ticker, peers, include_visualization: false });
    renderScore(container, response || {});
    toast.success('ESG scoring complete', company);
  } catch(err) {
    renderScore(container, mockEsgResult(company, ticker));
    toast.error('API error', err.message + ' — showing mock data');
  } finally {
    btn.disabled = false; btn.textContent = '▶ Run ESG Score';
  }
}

/* ── Mock Data ── */
function mockEsgResult(company, ticker) {
  return {
    esg_report: {
      company, ticker,
      overall_score: 72.4,
      e_score: 68.1,
      s_score: 74.8,
      g_score: 74.2,
      percentile: 78,
      industry: 'Consumer Discretionary / EV',
      rating: 'AA',
      sub_scores: {
        environment: [62, 84, 71, 68, 56],
        social: [82, 79, 71, 68, 75],
        governance: [88, 72, 74, 68, 69],
      },
      trend: [61.2, 63.4, 65.1, 67.2, 68.8, 70.1, 71.4, 72.0, 71.8, 72.4, 72.1, 72.4],
      peers: [
        { name: company, ticker, overall: 72.4, e: 68.1, s: 74.8, g: 74.2 },
        { name: 'Ford Motor', ticker: 'F',  overall: 61.2, e: 58.3, s: 66.1, g: 59.2 },
        { name: 'GM',         ticker: 'GM', overall: 63.8, e: 61.4, s: 67.2, g: 62.8 },
        { name: 'NIO',        ticker: 'NIO',overall: 55.1, e: 62.8, s: 51.4, g: 51.1 },
      ],
    }
  };
}

/* ── Render Results ── */
function renderScore(container, response) {
  _lastScoreResponse = response;
  const report = response.esg_report || {};
  const overall = firstDef(report.overall_score, report.overall, 72.4);
  const eScore  = firstDef(report.e_score, report.environment_score, 68.1);
  const sScore  = firstDef(report.s_score, report.social_score, 74.8);
  const gScore  = firstDef(report.g_score, report.governance_score, 74.2);
  const company = report.company || 'Company';
  const ticker  = report.ticker  || '—';
  const rating  = report.rating  || ratingFromScore(overall);
  const pct     = report.percentile || Math.round(overall * 1.05);

  // Update hero
  container.querySelector('#esg-company-name').textContent = company;
  container.querySelector('#esg-ticker-val').textContent =
    getLang() === 'zh'
      ? `${ticker} · ${translateLoose(report.industry || 'Equity')} · 评级：${rating}`
      : `${ticker} · ${report.industry || 'Equity'} · Rating: ${rating}`;

  const verdictEl = container.querySelector('#esg-verdict-tag');
  verdictEl.innerHTML = `
    <div style="display:flex;gap:8px;align-items:center;margin-top:8px;flex-wrap:wrap">
      <span style="background:rgba(0,255,136,0.15);color:var(--green);font-family:var(--f-mono);font-size:10px;padding:3px 10px;border-radius:4px;letter-spacing:0.08em">${rating} RATING</span>
      <span style="font-size:10px;color:var(--text-dim);font-family:var(--f-mono)">${translateLoose(`Top ${100-pct}th percentile in industry`)}</span>
    </div>`;

  // Ring gauge
  setTimeout(() => {
    drawRingGauge(container.querySelector('#esg-ring'), overall);
    drawRadar(container, [eScore, sScore, gScore, ...(Object.values(report.sub_scores || {}).flatMap(a=>a).slice(0,6))], eScore, sScore, gScore);
    drawTrendLine(container.querySelector('#esg-trend-canvas'), report.trend);
  }, 30);

  // E S G bars
  container.querySelector('#esg-dim-row').innerHTML = [
    ['E', eScore, '#00FF88'],
    ['S', sScore, '#00E5FF'],
    ['G', gScore, '#B44EFF'],
  ].map(([l,v,c]) => `
    <div style="text-align:center;min-width:70px">
      <div style="font-family:var(--f-display);font-size:22px;font-weight:800;color:${c}">${Number(v).toFixed(1)}</div>
      <div style="font-size:9px;color:var(--text-dim);letter-spacing:0.1em;font-family:var(--f-mono);margin-top:3px">${l === 'E' ? translateLoose('ENVIRON') : l === 'S' ? translateLoose('SOCIAL') : translateLoose('GOVERN')}</div>
      <div style="margin-top:6px;width:60px;height:4px;border-radius:2px;background:rgba(255,255,255,0.07);overflow:hidden">
        <div style="width:${v}%;height:100%;background:${c};border-radius:2px"></div>
      </div>
    </div>`).join('');

  // Dimension cards
  container.querySelector('#esg-dim-cards').innerHTML = DIMENSIONS.map(d => {
    const score = d.key === 'environment' ? eScore : d.key === 'social' ? sScore : gScore;
    const subs = report.sub_scores?.[d.key] || [];
    const subsHtml = SUB_SCORES[d.key].map((name, i) => {
      const v = subs[i] ?? (score + Math.random()*10 - 5);
      return `
        <div style="display:flex;justify-content:space-between;align-items:center;padding:5px 0;border-bottom:1px solid rgba(255,255,255,0.04)">
          <span style="font-size:10px;color:var(--text-secondary)">${name}</span>
          <div style="display:flex;align-items:center;gap:8px">
            <div style="width:50px;height:3px;border-radius:2px;background:rgba(255,255,255,0.06)">
              <div style="width:${Math.min(v,100)}%;height:100%;background:${d.color};border-radius:2px"></div>
            </div>
            <span style="font-size:10px;font-family:var(--f-mono);color:${d.color};width:28px;text-align:right">${Number(v).toFixed(0)}</span>
          </div>
        </div>`;
    }).join('');
    return `
      <div class="card" style="border-color:${d.color}1a">
        <div class="card-header" style="border-color:${d.color}1a">
          <span style="font-size:16px">${d.icon}</span>
          <span class="card-title">${d.label}</span>
          <span style="font-family:var(--f-mono);font-size:18px;font-weight:700;color:${d.color};margin-left:auto">${Number(score).toFixed(1)}</span>
        </div>
        <div style="padding:10px 14px">
          <div style="font-size:10px;color:var(--text-dim);line-height:1.5;margin-bottom:10px">${d.desc}</div>
          ${subsHtml}
        </div>
      </div>`;
  }).join('');

  // Peer table
  const peers = report.peers || [];
  if (peers.length) {
    container.querySelector('#peer-table').innerHTML = `<table>
      <thead><tr><th>Company</th><th>Ticker</th><th>Overall</th><th>E</th><th>S</th><th>G</th><th>vs This</th></tr></thead>
      <tbody>
        ${peers.map((p, i) => {
          const isSelf = i === 0;
          const diff = p.overall - overall;
          return `<tr style="${isSelf?'background:rgba(0,255,136,0.04)':''}">
            <td style="font-weight:${isSelf?700:400};color:${isSelf?'var(--text-primary)':'var(--text-secondary)'}">${p.name}</td>
            <td style="font-family:var(--f-mono);font-size:11px">${p.ticker}</td>
            <td class="cell-num" style="color:${scoreColor(p.overall)};font-weight:700">${Number(p.overall).toFixed(1)}</td>
            <td class="cell-num" style="color:var(--green)">${Number(p.e).toFixed(1)}</td>
            <td class="cell-num" style="color:var(--cyan)">${Number(p.s).toFixed(1)}</td>
            <td class="cell-num" style="color:var(--purple)">${Number(p.g).toFixed(1)}</td>
            <td class="cell-num ${isSelf?'':''}${!isSelf&&diff>0?'pos':!isSelf&&diff<0?'neg':''}">${isSelf ? '— (this)' : (diff>0?'+':'')+diff.toFixed(1)}</td>
          </tr>`;
        }).join('')}
      </tbody>
    </table>`;
  }

  // Quick compare sidebar
  container.querySelector('#quick-compare-list').innerHTML = (report.peers || []).map(p => `
    <div style="display:flex;align-items:center;gap:10px;padding:9px 14px;border-bottom:1px solid rgba(255,255,255,0.04)">
      <span style="font-family:var(--f-display);font-size:10px;font-weight:700;color:var(--text-primary);width:40px">${p.ticker}</span>
      <div style="flex:1;height:4px;border-radius:2px;background:rgba(255,255,255,0.06)">
        <div style="width:${p.overall}%;height:100%;background:${scoreColor(p.overall)};border-radius:2px"></div>
      </div>
      <span style="font-family:var(--f-mono);font-size:11px;color:${scoreColor(p.overall)};width:32px;text-align:right">${Number(p.overall).toFixed(0)}</span>
    </div>`).join('');
}

/* ── Ring Gauge ── */
function drawRingGauge(canvas, value) {
  if (!canvas) return;
  const dpr = window.devicePixelRatio || 1;
  canvas.width = 120 * dpr; canvas.height = 120 * dpr;
  canvas.style.width = '120px'; canvas.style.height = '120px';
  const ctx = canvas.getContext('2d');
  ctx.scale(dpr, dpr);
  const cx = 60, cy = 60, r = 46, lw = 10;
  const start = -Math.PI * 0.75, sweep = Math.PI * 1.5;
  const end = start + sweep * (value / 100);

  ctx.clearRect(0, 0, 120, 120);

  // Track
  ctx.beginPath(); ctx.arc(cx, cy, r, start, start + sweep);
  ctx.strokeStyle = 'rgba(255,255,255,0.07)'; ctx.lineWidth = lw;
  ctx.lineCap = 'round'; ctx.stroke();

  // Arc gradient
  const grad = ctx.createLinearGradient(cx-r, cy, cx+r, cy);
  grad.addColorStop(0, value > 60 ? '#00E5FF' : '#FF3D57');
  grad.addColorStop(1, '#00FF88');
  ctx.beginPath(); ctx.arc(cx, cy, r, start, end);
  ctx.strokeStyle = grad; ctx.lineWidth = lw;
  ctx.lineCap = 'round';
  ctx.shadowColor = '#00FF88'; ctx.shadowBlur = 12 * dpr;
  ctx.stroke(); ctx.shadowBlur = 0;

  // Center text
  ctx.fillStyle = '#F0F4FF'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
  ctx.font = `bold ${18}px "IBM Plex Mono"`;
  ctx.fillText(Number(value).toFixed(0), cx, cy - 4);
  ctx.font = `${8}px "IBM Plex Mono"`;
  ctx.fillStyle = 'rgba(140,160,220,0.6)';
  ctx.fillText('/ 100', cx, cy + 12);
}

/* ── Radar Chart ── */
function drawRadar(container, allScores, e, s, g) {
  const canvas = container.querySelector('#esg-radar');
  if (!canvas) return;
  const legendEl = container.querySelector('#radar-legend');
  const dpr = window.devicePixelRatio || 1;
  const SIZE = 280;
  canvas.width = SIZE * dpr; canvas.height = SIZE * dpr;
  canvas.style.width = SIZE + 'px'; canvas.style.height = SIZE + 'px';
  const ctx = canvas.getContext('2d');
  ctx.scale(dpr, dpr);
  const cx = SIZE / 2, cy = SIZE / 2, maxR = 100;

  const axes = [
    { label: 'Environment', val: e },
    { label: 'Social',      val: s },
    { label: 'Governance',  val: g },
    { label: 'Momentum',    val: 71 },
    { label: 'Disclosure',  val: 68 },
    { label: 'Innovation',  val: 74 },
  ];
  const N = axes.length;
  const angle = i => (Math.PI * 2 * i / N) - Math.PI / 2;

  ctx.clearRect(0, 0, SIZE, SIZE);

  // Grid circles
  [20,40,60,80,100].forEach(v => {
    ctx.beginPath();
    axes.forEach((_, i) => {
      const a = angle(i), r2 = v / 100 * maxR;
      if (i === 0) ctx.moveTo(cx + Math.cos(a)*r2, cy + Math.sin(a)*r2);
      else ctx.lineTo(cx + Math.cos(a)*r2, cy + Math.sin(a)*r2);
    });
    ctx.closePath();
    ctx.strokeStyle = 'rgba(255,255,255,0.06)'; ctx.lineWidth = 1; ctx.stroke();
    if (v === 40 || v === 80) {
      ctx.fillStyle = 'rgba(140,160,220,0.3)'; ctx.font = `9px IBM Plex Mono`; ctx.textAlign = 'center';
      ctx.fillText(v, cx + 4, cy - v/100*maxR + 3);
    }
  });

  // Spokes
  axes.forEach((_, i) => {
    const a = angle(i);
    ctx.beginPath(); ctx.moveTo(cx, cy);
    ctx.lineTo(cx + Math.cos(a)*maxR, cy + Math.sin(a)*maxR);
    ctx.strokeStyle = 'rgba(255,255,255,0.08)'; ctx.lineWidth = 1; ctx.stroke();
  });

  // Data polygon
  ctx.beginPath();
  axes.forEach((ax, i) => {
    const a = angle(i), r2 = ax.val / 100 * maxR;
    if (i === 0) ctx.moveTo(cx + Math.cos(a)*r2, cy + Math.sin(a)*r2);
    else ctx.lineTo(cx + Math.cos(a)*r2, cy + Math.sin(a)*r2);
  });
  ctx.closePath();
  ctx.fillStyle = 'rgba(0,255,136,0.12)'; ctx.fill();
  ctx.strokeStyle = '#00FF88'; ctx.lineWidth = 2;
  ctx.shadowColor = '#00FF88'; ctx.shadowBlur = 8*dpr; ctx.stroke(); ctx.shadowBlur = 0;

  // Dots + labels
  axes.forEach((ax, i) => {
    const a = angle(i), r2 = ax.val / 100 * maxR;
    ctx.beginPath(); ctx.arc(cx + Math.cos(a)*r2, cy + Math.sin(a)*r2, 4, 0, Math.PI*2);
    ctx.fillStyle = '#00FF88'; ctx.fill();

    // Axis label
    const lr = maxR + 16;
    const lx = cx + Math.cos(a)*lr, ly = cy + Math.sin(a)*lr;
    ctx.fillStyle = 'rgba(200,210,255,0.65)'; ctx.font = `9px IBM Plex Mono`;
    ctx.textAlign = Math.cos(a) > 0.2 ? 'left' : Math.cos(a) < -0.2 ? 'right' : 'center';
    ctx.fillText(translateLoose(ax.label), lx, ly);
  });

  // Legend
  if (legendEl) {
    legendEl.innerHTML = axes.map(ax => `
      <div style="display:flex;justify-content:space-between;align-items:center;gap:12px">
        <span style="font-size:10px;color:var(--text-dim)">${translateLoose(ax.label)}</span>
        <span style="font-family:var(--f-mono);font-size:11px;color:${scoreColor(ax.val)}">${Number(ax.val).toFixed(1)}</span>
      </div>`).join('');
  }
}

/* ── Trend Line ── */
function drawTrendLine(canvas, trend) {
  if (!canvas) return;
  const data = trend || Array.from({length:12}, (_,i) => 60 + i * 1.2 + (Math.random()-0.5)*3);
  const dpr = window.devicePixelRatio || 1;
  const W = canvas.parentElement?.offsetWidth || 260, H = 120;
  canvas.width = W * dpr; canvas.height = H * dpr;
  canvas.style.height = H + 'px';
  const ctx = canvas.getContext('2d');
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, W, H);
  ctx.fillStyle = '#07070F'; ctx.fillRect(0, 0, W, H);

  const padL=36, padR=12, padT=10, padB=24;
  const cW=W-padL-padR, cH=H-padT-padB;
  const minV = Math.min(...data)*0.97, maxV = Math.max(...data)*1.02;
  const px = i => padL + (i/(data.length-1))*cW;
  const py = v => padT + cH - ((v-minV)/(maxV-minV))*cH;

  // Grid
  [0,0.5,1].forEach(t => {
    const y = padT + cH*(1-t);
    ctx.beginPath(); ctx.moveTo(padL,y); ctx.lineTo(W-padR,y);
    ctx.strokeStyle='rgba(255,255,255,0.04)'; ctx.lineWidth=1; ctx.stroke();
    ctx.fillStyle='rgba(140,160,220,0.4)'; ctx.font=`8px IBM Plex Mono`; ctx.textAlign='right';
    ctx.fillText((minV+(maxV-minV)*t).toFixed(0), padL-3, y+3);
  });

  // Area
  const grad = ctx.createLinearGradient(0,padT,0,padT+cH);
  grad.addColorStop(0,'rgba(0,255,136,0.2)'); grad.addColorStop(1,'transparent');
  ctx.beginPath();
  data.forEach((v,i) => i===0 ? ctx.moveTo(px(i),py(v)) : ctx.lineTo(px(i),py(v)));
  ctx.lineTo(px(data.length-1),padT+cH); ctx.lineTo(px(0),padT+cH); ctx.closePath();
  ctx.fillStyle=grad; ctx.fill();

  // Line
  ctx.beginPath();
  data.forEach((v,i) => i===0 ? ctx.moveTo(px(i),py(v)) : ctx.lineTo(px(i),py(v)));
  ctx.strokeStyle='#00FF88'; ctx.lineWidth=2;
  ctx.shadowColor='#00FF88'; ctx.shadowBlur=6*dpr; ctx.stroke(); ctx.shadowBlur=0;

  // Month labels
  const months=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  data.forEach((_,i) => {
    if (i%3===0) {
      ctx.fillStyle='rgba(140,160,220,0.35)'; ctx.font=`8px IBM Plex Mono`; ctx.textAlign='center';
      ctx.fillText(translateLoose(months[i] || ''), px(i), H-padB+12);
    }
  });
}

/* ── Helpers ── */
function scoreColor(v) {
  return v >= 70 ? 'var(--green)' : v >= 50 ? 'var(--amber)' : 'var(--red)';
}

function ratingFromScore(v) {
  return v >= 80 ? 'AAA' : v >= 70 ? 'AA' : v >= 60 ? 'A' : v >= 50 ? 'BBB' : 'BB';
}

function firstDef(...vals) { return vals.find(v => v != null); }
