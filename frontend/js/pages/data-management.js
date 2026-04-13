import { api } from '../qtapi.js?v=8';
import { toast } from '../components/toast.js?v=8';

let _pollTimer = null;

const PIPELINE_NODES = [
  { id: 'raw',      label: 'Raw Ingestion',     icon: '⬇',  status: 'live',    x: 40,  y: 120 },
  { id: 'clean',    label: 'Data Cleaning',      icon: '🧹', status: 'live',    x: 160, y: 120 },
  { id: 'enrich',   label: 'ESG Enrichment',     icon: '🌿', status: 'live',    x: 280, y: 120 },
  { id: 'feature',  label: 'Feature Store',      icon: '📐', status: 'live',    x: 400, y: 120 },
  { id: 'model',    label: 'Model Input',         icon: '🧠', status: 'live',    x: 520, y: 120 },
  { id: 'signal',   label: 'Signal Output',       icon: '📡', status: 'live',    x: 640, y: 120 },
];

const SOURCES = [
  { id: 'esg_news',    name: 'ESG News Feed',        type: 'Stream', freshness: '2min',   records: '14.2K', status: 'live',    lag: '< 1min' },
  { id: 'price_data',  name: 'Price / OHLCV',         type: 'Batch',  freshness: '1min',   records: '8.4M',  status: 'live',    lag: '< 30s' },
  { id: 'company_snap',name: 'Company Snapshots',      type: 'Batch',  freshness: '4 hrs',  records: '142K',  status: 'live',    lag: '< 5min' },
  { id: 'esg_scores',  name: 'ESG Scores (Refinitiv)', type: 'Daily',  freshness: '23 hrs', records: '3.1K',  status: 'stale',   lag: '2 hrs' },
  { id: 'filings',     name: 'SEC Filings',            type: 'Event',  freshness: '6 hrs',  records: '287K',  status: 'live',    lag: '< 1hr' },
  { id: 'macro',       name: 'Macro Indicators',       type: 'Daily',  freshness: '18 hrs', records: '12K',   status: 'live',    lag: '< 1hr' },
  { id: 'sentiment',   name: 'Sentiment NLP',          type: 'Stream', freshness: '5min',   records: '91K',   status: 'live',    lag: '< 2min' },
  { id: 'alt_data',    name: 'Alternative Data',        type: 'Batch',  freshness: '2 hrs',  records: '520K',  status: 'warning', lag: '45min' },
];

export function render(container) {
  container.innerHTML = buildShell();
  bindEvents(container);
  drawPipelineFlow(container);
  renderFreshness(container);
}

export function destroy() {
  if (_pollTimer) window.clearInterval(_pollTimer);
  _pollTimer = null;
}

/* ── Shell ── */
function buildShell() {
  return `
  <div class="page-header">
    <div>
      <div class="page-header__title">Data Management</div>
      <div class="page-header__sub">Pipeline Monitor · Data Freshness · Sync Control · Ingestion Logs</div>
    </div>
    <div class="page-header__actions">
      <button class="btn btn-ghost btn-sm" id="btn-refresh-all">↺ Refresh All</button>
    </div>
  </div>

  <!-- Pipeline Flow Visualization -->
  <div class="card" style="margin-bottom:20px">
    <div class="card-header">
      <span class="card-title">Data Pipeline</span>
      <div style="display:flex;align-items:center;gap:8px">
        <div class="live-dot"></div>
        <span style="font-size:10px;font-family:var(--f-mono);color:var(--green)">ALL SYSTEMS NOMINAL</span>
      </div>
    </div>
    <div class="pipeline-canvas-wrap" style="padding:8px 16px 16px">
      <canvas id="pipeline-canvas" height="200" style="width:100%;cursor:pointer"></canvas>
    </div>
  </div>

  <div class="grid-sidebar" style="align-items:start">

    <!-- LEFT: Sync Control -->
    <div style="display:flex;flex-direction:column;gap:14px">

      <div class="run-panel">
        <div class="run-panel__header">
          <div class="run-panel__title">Sync Control</div>
          <div class="run-panel__sub">Trigger company snapshot refresh</div>
        </div>
        <div class="run-panel__body">
          <div class="form-group">
            <label class="form-label">Companies / Tickers</label>
            <textarea class="form-textarea" id="sync-companies" rows="5" placeholder="Tesla&#10;Microsoft&#10;NVIDIA">Tesla
Microsoft
NVIDIA</textarea>
          </div>
          <div class="form-group">
            <label class="form-label">Data Sources</label>
            <div style="display:flex;gap:5px;flex-wrap:wrap;margin-top:4px" id="source-select-chips">
              ${['All Sources','ESG Scores','Price Data','Filings','Sentiment'].map((s, i) => `
                <button class="filter-chip${i===0?' active':''}" data-src="${s}">${s}</button>
              `).join('')}
            </div>
          </div>
          <div class="form-row">
            <div class="form-group" style="flex-direction:row;align-items:center;gap:10px">
              <label class="form-label" style="margin:0;flex:1">Force Refresh</label>
              <label class="toggle">
                <input type="checkbox" id="sync-force">
                <span class="toggle-track"></span>
              </label>
            </div>
            <div class="form-group" style="flex-direction:row;align-items:center;gap:10px">
              <label class="form-label" style="margin:0;flex:1">Priority</label>
              <label class="toggle">
                <input type="checkbox" id="sync-priority">
                <span class="toggle-track"></span>
              </label>
            </div>
          </div>
        </div>
        <div class="run-panel__foot">
          <button class="btn btn-primary btn-lg" id="sync-btn" style="flex:1">▶ Start Sync</button>
        </div>
      </div>

      <!-- Active Jobs -->
      <div class="card">
        <div class="card-header"><span class="card-title">Active Jobs</span>
          <span id="job-count" style="font-size:10px;color:var(--text-dim);font-family:var(--f-mono)"></span>
        </div>
        <div id="sync-body" style="display:flex;flex-direction:column;gap:0">
          <div style="padding:14px 16px;color:var(--text-dim);font-size:11px">No active sync jobs</div>
        </div>
      </div>

      <!-- Logs -->
      <div class="card">
        <div class="card-header"><span class="card-title">Ingestion Log</span>
          <button class="btn btn-ghost btn-sm" id="btn-clear-log">Clear</button>
        </div>
        <div id="ingestion-log" style="font-family:var(--f-mono);font-size:10px;max-height:200px;overflow-y:auto;padding:10px 14px;color:var(--text-dim);line-height:1.6">
          <span style="color:var(--green)">[10:24:01]</span> price_data: 8,412,300 records refreshed<br>
          <span style="color:var(--green)">[10:23:18]</span> esg_news: 142 new articles ingested<br>
          <span style="color:var(--green)">[10:20:44]</span> sentiment_nlp: batch scored 89 documents<br>
          <span style="color:var(--amber)">[10:15:02]</span> alt_data: connector timeout, retrying…<br>
          <span style="color:var(--green)">[10:14:55]</span> company_snapshots: TSLA, MSFT, NVDA refreshed<br>
          <span style="color:var(--green)">[09:58:30]</span> macro_indicators: 12 series updated<br>
        </div>
      </div>
    </div>

    <!-- RIGHT: Freshness & Sources -->
    <div style="display:flex;flex-direction:column;gap:14px">

      <!-- Freshness KPIs -->
      <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px" id="freshness-kpis">
        ${[
          ['Live Feeds', '6/8', 'var(--green)'],
          ['Avg Freshness', '4.2 hrs', 'var(--amber)'],
          ['Records Today', '9.1M', 'var(--cyan)'],
          ['Alerts', '1 warning', 'var(--amber)'],
        ].map(([l,v,c]) => `
          <div class="metric-card">
            <div class="metric-label">${l}</div>
            <div class="metric-value" style="color:${c};font-size:18px">${v}</div>
          </div>`).join('')}
      </div>

      <!-- Data Sources Table -->
      <div class="card">
        <div class="card-header"><span class="card-title">Data Source Freshness</span></div>
        <div class="freshness-row-list" id="freshness-list"></div>
      </div>

      <!-- Throughput chart -->
      <div class="card">
        <div class="card-header"><span class="card-title">Ingestion Throughput (24h)</span></div>
        <div class="card-body" style="padding:0">
          <canvas id="throughput-canvas" height="140" style="width:100%"></canvas>
        </div>
      </div>

    </div>
  </div>`;
}

/* ── Pipeline Flow Canvas ── */
function drawPipelineFlow(container) {
  const canvas = container.querySelector('#pipeline-canvas');
  if (!canvas) return;
  const dpr = window.devicePixelRatio || 1;
  const W = canvas.parentElement?.offsetWidth || 760, H = 200;
  canvas.width = W * dpr; canvas.height = H * dpr;
  canvas.style.height = H + 'px';
  const ctx = canvas.getContext('2d');
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, W, H);
  ctx.fillStyle = 'var(--bg-surface)'; ctx.fillRect(0, 0, W, H);

  const N = PIPELINE_NODES.length;
  const nodeW = 90, nodeH = 50, gapX = (W - N * nodeW) / (N + 1);
  const nodeY = H / 2 - nodeH / 2;

  PIPELINE_NODES.forEach((node, i) => {
    const x = gapX + i * (nodeW + gapX);
    node._x = x; node._y = nodeY;

    // Connector line
    if (i < N - 1) {
      const nx = gapX + (i + 1) * (nodeW + gapX);
      const mid = x + nodeW;

      // Animated dashes
      ctx.setLineDash([6, 4]);
      ctx.strokeStyle = 'rgba(0,255,136,0.3)';
      ctx.lineWidth = 1.5;
      ctx.beginPath(); ctx.moveTo(mid, H/2); ctx.lineTo(nx, H/2); ctx.stroke();
      ctx.setLineDash([]);

      // Arrow head
      ctx.fillStyle = 'rgba(0,255,136,0.5)';
      ctx.beginPath();
      ctx.moveTo(nx - 8, H/2 - 4);
      ctx.lineTo(nx, H/2);
      ctx.lineTo(nx - 8, H/2 + 4);
      ctx.closePath(); ctx.fill();
    }

    // Node box
    const isWarn = node.status === 'warning';
    const borderColor = isWarn ? 'rgba(255,179,0,0.5)' : 'rgba(0,255,136,0.35)';
    const bgColor = isWarn ? 'rgba(255,179,0,0.06)' : 'rgba(0,255,136,0.05)';

    ctx.fillStyle = bgColor;
    ctx.beginPath();
    roundRect(ctx, x, nodeY, nodeW, nodeH, 8);
    ctx.fill();
    ctx.strokeStyle = borderColor; ctx.lineWidth = 1.5;
    ctx.beginPath();
    roundRect(ctx, x, nodeY, nodeW, nodeH, 8);
    ctx.stroke();

    // Glow on live nodes
    if (!isWarn) {
      ctx.shadowColor = '#00FF88'; ctx.shadowBlur = 12 * dpr;
      ctx.strokeStyle = 'rgba(0,255,136,0.15)'; ctx.lineWidth = 4;
      ctx.beginPath(); roundRect(ctx, x, nodeY, nodeW, nodeH, 8); ctx.stroke();
      ctx.shadowBlur = 0;
    }

    // Icon
    ctx.font = `16px serif`; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillText(node.icon, x + nodeW/2, nodeY + 16);

    // Label
    ctx.fillStyle = 'rgba(200,210,255,0.7)'; ctx.font = `${9}px IBM Plex Mono`;
    ctx.textAlign = 'center'; ctx.textBaseline = 'top';
    ctx.fillText(node.label, x + nodeW/2, nodeY + 32);

    // Status dot
    ctx.beginPath(); ctx.arc(x + nodeW - 10, nodeY + 10, 4, 0, Math.PI * 2);
    ctx.fillStyle = isWarn ? '#FFB300' : '#00FF88';
    ctx.shadowColor = isWarn ? '#FFB300' : '#00FF88'; ctx.shadowBlur = 6 * dpr;
    ctx.fill(); ctx.shadowBlur = 0;
  });
}

function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + w - r, y);
  ctx.arcTo(x + w, y, x + w, y + r, r);
  ctx.lineTo(x + w, y + h - r);
  ctx.arcTo(x + w, y + h, x + w - r, y + h, r);
  ctx.lineTo(x + r, y + h);
  ctx.arcTo(x, y + h, x, y + h - r, r);
  ctx.lineTo(x, y + r);
  ctx.arcTo(x, y, x + r, y, r);
  ctx.closePath();
}

/* ── Freshness Table ── */
function renderFreshness(container) {
  container.querySelector('#freshness-list').innerHTML = SOURCES.map(s => {
    const statusColor = s.status === 'live' ? 'var(--green)' : s.status === 'stale' ? 'var(--red)' : 'var(--amber)';
    const statusLabel = s.status.toUpperCase();
    return `
    <div class="freshness-row">
      <div style="display:flex;align-items:center;gap:8px;flex:1">
        <span style="width:6px;height:6px;border-radius:50%;background:${statusColor};flex-shrink:0"></span>
        <div>
          <div style="font-size:11px;color:var(--text-primary);font-weight:500">${s.name}</div>
          <div style="font-size:9px;color:var(--text-dim);font-family:var(--f-mono)">${s.type} · ${s.records} records</div>
        </div>
      </div>
      <div style="text-align:right">
        <div style="font-size:10px;font-family:var(--f-mono);color:${statusColor}">${s.freshness} ago</div>
        <div style="font-size:9px;color:var(--text-dim)">lag ${s.lag}</div>
      </div>
      <button class="btn btn-ghost btn-sm freshness-sync-btn" data-sid="${s.id}" style="padding:3px 8px;font-size:9px;margin-left:8px">Sync</button>
    </div>`;
  }).join('');

  // Draw throughput chart after freshness renders
  setTimeout(() => drawThroughput(container), 50);

  container.querySelector('#freshness-list').addEventListener('click', e => {
    const btn = e.target.closest('.freshness-sync-btn');
    if (!btn) return;
    const src = SOURCES.find(s => s.id === btn.dataset.sid);
    if (src) toast.info('Sync triggered', src.name);
  });
}

/* ── Throughput Chart ── */
function drawThroughput(container) {
  const canvas = container.querySelector('#throughput-canvas');
  if (!canvas) return;
  const dpr = window.devicePixelRatio || 1;
  const W = canvas.parentElement?.offsetWidth || 400, H = 140;
  canvas.width = W * dpr; canvas.height = H * dpr;
  canvas.style.height = H + 'px';
  const ctx = canvas.getContext('2d');
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, W, H);
  ctx.fillStyle = '#07070F'; ctx.fillRect(0, 0, W, H);

  const hours = 24;
  const data = Array.from({length: hours}, (_, i) => {
    const base = 300 + Math.sin(i * 0.4) * 100;
    return Math.max(50, base + (Math.random() - 0.5) * 80);
  });

  const padL=36, padR=12, padT=10, padB=24;
  const cW=W-padL-padR, cH=H-padT-padB;
  const maxV = Math.max(...data) * 1.1;
  const px = i => padL + (i/(data.length-1))*cW;
  const py = v => padT + cH - (v/maxV)*cH;

  // Grid
  [0,0.5,1].forEach(t => {
    const y = padT + cH*(1-t);
    ctx.beginPath(); ctx.moveTo(padL,y); ctx.lineTo(W-padR,y);
    ctx.strokeStyle='rgba(255,255,255,0.04)'; ctx.lineWidth=1; ctx.stroke();
    ctx.fillStyle='rgba(140,160,220,0.35)'; ctx.font=`8px IBM Plex Mono`; ctx.textAlign='right';
    ctx.fillText(Math.round(maxV*t)+'K', padL-3, y+3);
  });

  // Bar chart
  const barW = cW / hours * 0.6;
  data.forEach((v, i) => {
    const x = padL + (i/(hours-1))*cW - barW/2;
    const barH = (v/maxV)*cH;
    const grad = ctx.createLinearGradient(0, py(v), 0, padT+cH);
    grad.addColorStop(0, 'rgba(0,255,136,0.6)');
    grad.addColorStop(1, 'rgba(0,255,136,0.1)');
    ctx.fillStyle = grad;
    ctx.fillRect(x, py(v), barW, barH);
  });

  // Hour labels
  [0,6,12,18,23].forEach(i => {
    ctx.fillStyle='rgba(140,160,220,0.4)'; ctx.font=`8px IBM Plex Mono`; ctx.textAlign='center';
    ctx.fillText(`${i}:00`, px(i), H-padB+12);
  });
}

/* ── Events ── */
function bindEvents(container) {
  container.querySelector('#sync-btn').addEventListener('click', () => startSync(container));
  container.querySelector('#btn-refresh-all').addEventListener('click', () => {
    renderFreshness(container);
    toast.info('Data sources refreshed');
  });
  container.querySelector('#btn-clear-log').addEventListener('click', () => {
    container.querySelector('#ingestion-log').innerHTML = '<span style="color:var(--text-dim)">Log cleared.</span>';
  });

  container.querySelector('#source-select-chips').addEventListener('click', e => {
    const chip = e.target.closest('.filter-chip');
    if (!chip) return;
    container.querySelectorAll('#source-select-chips .filter-chip').forEach(c => c.classList.toggle('active', c === chip));
  });
}

/* ── Sync ── */
async function startSync(container) {
  const btn = container.querySelector('#sync-btn');
  btn.disabled = true; btn.textContent = '● Starting…';

  const companies = container.querySelector('#sync-companies').value.split(/[,\n]+/).map(s => s.trim()).filter(Boolean);
  const forceRefresh = container.querySelector('#sync-force').checked;

  try {
    const response = await api.admin.dataSync.start({ companies, force_refresh: forceRefresh });
    toast.success('Sync started', response.job_id);
    renderJobStatus(container, response);
    pollStatus(container, response.job_id);
    appendLog(container, `Sync job ${response.job_id} started for: ${companies.join(', ')}`);
  } catch(err) {
    // Mock sync
    const mockJob = { job_id: 'JOB-' + Date.now(), status: 'running', companies, progress: 0 };
    renderJobStatus(container, mockJob);
    simulateMockSync(container, mockJob, companies);
    toast.error('API error', err.message + ' — running mock sync');
  } finally {
    btn.disabled = false; btn.textContent = '▶ Start Sync';
  }
}

function simulateMockSync(container, job, companies) {
  let progress = 0;
  const timer = setInterval(() => {
    progress += Math.random() * 20 + 5;
    if (progress >= 100) {
      progress = 100;
      job.status = 'completed';
      clearInterval(timer);
      appendLog(container, `✓ Sync ${job.job_id} completed — ${companies.length} companies updated`);
      toast.success('Sync complete', `${companies.length} companies refreshed`);
    }
    job.progress = Math.min(progress, 100);
    renderJobStatus(container, job);
  }, 600);
}

function pollStatus(container, jobId) {
  if (_pollTimer) window.clearInterval(_pollTimer);
  _pollTimer = window.setInterval(async () => {
    try {
      const status = await api.admin.dataSync.status(jobId);
      renderJobStatus(container, status);
      if (status.status?.startsWith('completed')) {
        window.clearInterval(_pollTimer); _pollTimer = null;
        toast.success('Sync complete', jobId);
      }
    } catch {
      window.clearInterval(_pollTimer); _pollTimer = null;
    }
  }, 1500);
}

function renderJobStatus(container, job) {
  const jobsEl = container.querySelector('#sync-body');
  const countEl = container.querySelector('#job-count');
  const progress = Math.round(job.progress || 0);
  const isDone = job.status === 'completed';
  const color = isDone ? 'var(--green)' : 'var(--amber)';
  countEl.textContent = isDone ? '' : '1 active';

  jobsEl.innerHTML = `
  <div style="padding:12px 16px;display:flex;flex-direction:column;gap:10px">
    <div style="display:flex;justify-content:space-between;align-items:center">
      <span style="font-size:11px;font-family:var(--f-mono);color:var(--text-dim)">${job.job_id}</span>
      <span class="badge badge-${isDone?'filled':'pending'}">${(job.status||'').toUpperCase()}</span>
    </div>
    <div style="background:rgba(255,255,255,0.06);border-radius:3px;height:6px;overflow:hidden">
      <div style="width:${progress}%;height:100%;background:${color};border-radius:3px;transition:width 0.4s ease"></div>
    </div>
    <div style="display:flex;justify-content:space-between;font-size:10px;font-family:var(--f-mono);color:var(--text-dim)">
      <span>${(job.companies||[]).join(', ')}</span>
      <span style="color:${color}">${progress}%</span>
    </div>
  </div>`;
}

function appendLog(container, msg) {
  const log = container.querySelector('#ingestion-log');
  const ts = new Date().toLocaleTimeString();
  log.innerHTML = `<span style="color:var(--green)">[${ts}]</span> ${msg}<br>` + log.innerHTML;
}
