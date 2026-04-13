import { api } from '../qtapi.js?v=8';
import { toast } from '../components/toast.js?v=8';

const REPORT_TYPES = [
  { value: 'daily',   label: 'Daily Digest',        desc: 'Top signals, score updates, alerts' },
  { value: 'weekly',  label: 'Weekly Summary',       desc: 'Portfolio review, ESG movers, attribution' },
  { value: 'monthly', label: 'Monthly Deep-Dive',    desc: 'Full factor analysis, peer benchmarks, forecasts' },
  { value: 'adhoc',   label: 'Ad-Hoc Analysis',      desc: 'Custom companies, custom period' },
];

const HISTORY = [
  { id: 'RPT-2024-04-12', type: 'daily',   title: 'Daily Digest — Apr 12',    status: 'ready',  ts: '10:00 AM', size: '42 KB' },
  { id: 'RPT-2024-04-07', type: 'weekly',  title: 'Weekly Summary — W14',     status: 'ready',  ts: 'Apr 7',    size: '184 KB' },
  { id: 'RPT-2024-03-31', type: 'monthly', title: 'Monthly Deep-Dive — Mar',  status: 'ready',  ts: 'Apr 1',    size: '614 KB' },
  { id: 'RPT-2024-04-11', type: 'daily',   title: 'Daily Digest — Apr 11',    status: 'ready',  ts: 'Yesterday',size: '38 KB' },
  { id: 'RPT-2024-04-10', type: 'adhoc',   title: 'Ad-Hoc: NVDA vs AMD',      status: 'ready',  ts: 'Apr 10',   size: '91 KB' },
];

export function render(container) {
  container.innerHTML = buildShell();
  bindEvents(container);
  renderHistory(container);
  // Auto-load a mock report for the selected type
  renderReport(container, mockReport('daily', ['Tesla', 'Microsoft']));
}

/* ── Shell ── */
function buildShell() {
  return `
  <div class="page-header">
    <div>
      <div class="page-header__title">Report Center</div>
      <div class="page-header__sub">Generate · Schedule · Archive · Export ESG Research Reports</div>
    </div>
    <div class="page-header__actions">
      <button class="btn btn-ghost btn-sm" id="btn-schedule">⏰ Schedule</button>
      <button class="btn btn-ghost btn-sm" id="btn-download">⬇ Download</button>
    </div>
  </div>

  <div class="grid-sidebar" style="align-items:start">

    <!-- LEFT: Config + History -->
    <div style="display:flex;flex-direction:column;gap:14px">

      <div class="run-panel">
        <div class="run-panel__header">
          <div class="run-panel__title">Generate Report</div>
          <div class="run-panel__sub">Choose type, scope and options</div>
        </div>
        <div class="run-panel__body">
          <!-- Report type cards -->
          <div style="display:flex;flex-direction:column;gap:6px;margin-bottom:14px" id="rtype-list">
            ${REPORT_TYPES.map(rt => `
              <div class="rtype-card${rt.value==='daily'?' active':''}" data-rtype="${rt.value}">
                <div class="rtype-card-title">${rt.label}</div>
                <div class="rtype-card-desc">${rt.desc}</div>
              </div>`).join('')}
          </div>
          <input type="hidden" id="report-type" value="daily">

          <div class="form-group">
            <label class="form-label">Companies / Tickers</label>
            <input class="form-input" id="report-companies" value="Tesla, Microsoft" placeholder="Tesla, Apple, NVDA…">
          </div>
          <div class="form-row">
            <div class="form-group">
              <label class="form-label">Start Date</label>
              <input class="form-input" id="report-start" type="date">
            </div>
            <div class="form-group">
              <label class="form-label">End Date</label>
              <input class="form-input" id="report-end" type="date">
            </div>
          </div>
          <div class="form-group">
            <label class="form-label">Sections to Include</label>
            <div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:6px" id="section-chips">
              ${['ESG Scores','Factor Analysis','Peer Comparison','Risk Attribution','Signals','Forecasts'].map(s =>
                `<button class="filter-chip active" data-section="${s}" style="font-size:9px;padding:3px 8px">${s}</button>`
              ).join('')}
            </div>
          </div>
        </div>
        <div class="run-panel__foot" style="gap:8px">
          <button class="btn btn-primary btn-lg" id="generate-btn" style="flex:1">▶ Generate</button>
          <button class="btn btn-ghost btn-lg" id="load-latest-btn">Load Latest</button>
        </div>
      </div>

      <!-- History -->
      <div class="card">
        <div class="card-header"><span class="card-title">Report Archive</span></div>
        <div id="report-history" style="display:flex;flex-direction:column;gap:0"></div>
      </div>

    </div>

    <!-- RIGHT: Report workspace -->
    <div style="display:flex;flex-direction:column;gap:0;min-height:600px">
      <!-- Toolbar -->
      <div class="report-toolbar" id="report-toolbar" style="display:none">
        <span id="report-toolbar-title" style="font-family:var(--f-display);font-size:11px;font-weight:700;color:var(--text-primary)"></span>
        <div style="display:flex;gap:6px">
          <button class="btn btn-ghost btn-sm" id="btn-toolbar-pdf">PDF</button>
          <button class="btn btn-ghost btn-sm" id="btn-toolbar-csv">CSV</button>
          <button class="btn btn-ghost btn-sm" id="btn-toolbar-json">JSON</button>
        </div>
      </div>

      <!-- Report body -->
      <div class="results-panel" style="flex:1;border-top-left-radius:${0}px">
        <div class="results-panel__body" id="report-body" style="padding:0">
          <div class="empty-state">
            <div class="empty-state__icon">📋</div>
            <div class="empty-state__title">No report loaded</div>
            <div class="empty-state__text">Generate a new report or click an archive entry to load.</div>
          </div>
        </div>
      </div>
    </div>

  </div>`;
}

/* ── Events ── */
function bindEvents(container) {
  container.querySelector('#generate-btn').addEventListener('click', () => generateReport(container));
  container.querySelector('#load-latest-btn').addEventListener('click',  () => loadLatest(container));
  container.querySelector('#btn-schedule').addEventListener('click', () => toast.info('Scheduling', 'Report scheduler coming soon'));
  container.querySelector('#btn-download').addEventListener('click', () => toast.info('Download', 'Select a report first'));
  container.querySelector('#btn-toolbar-pdf')?.addEventListener('click', () => toast.info('PDF Export', 'Generating PDF…'));
  container.querySelector('#btn-toolbar-csv')?.addEventListener('click', () => toast.info('CSV Export', 'Downloading CSV…'));
  container.querySelector('#btn-toolbar-json')?.addEventListener('click', () => toast.info('JSON Export', 'Downloading JSON…'));

  // Report type selection
  container.querySelector('#rtype-list').addEventListener('click', e => {
    const card = e.target.closest('.rtype-card');
    if (!card) return;
    container.querySelectorAll('.rtype-card').forEach(c => c.classList.toggle('active', c === card));
    container.querySelector('#report-type').value = card.dataset.rtype;
  });

  // Section chips
  container.querySelector('#section-chips').addEventListener('click', e => {
    const chip = e.target.closest('.filter-chip');
    if (!chip) return;
    chip.classList.toggle('active');
  });
}

function renderHistory(container) {
  container.querySelector('#report-history').innerHTML = HISTORY.map(r => `
    <div class="report-hist-item" data-rid="${r.id}">
      <div style="display:flex;align-items:center;gap:8px;flex:1">
        <span class="badge badge-${r.type==='daily'?'filled':r.type==='weekly'?'pending':'neutral'}" style="font-size:8px">${r.type.toUpperCase()}</span>
        <div>
          <div style="font-size:11px;color:var(--text-primary)">${r.title}</div>
          <div style="font-size:9px;color:var(--text-dim);font-family:var(--f-mono)">${r.id} · ${r.size}</div>
        </div>
      </div>
      <span style="font-size:9px;color:var(--text-dim);font-family:var(--f-mono)">${r.ts}</span>
    </div>`).join('');

  container.querySelector('#report-history').addEventListener('click', e => {
    const item = e.target.closest('.report-hist-item');
    if (!item) return;
    container.querySelectorAll('.report-hist-item').forEach(el => el.classList.toggle('active', el === item));
    const rec = HISTORY.find(r => r.id === item.dataset.rid);
    if (rec) renderReport(container, mockReport(rec.type, ['Tesla', 'Microsoft'], rec.id, rec.title));
  });
}

/* ── API ── */
async function generateReport(container) {
  const btn = container.querySelector('#generate-btn');
  btn.disabled = true; btn.textContent = '● Generating…';
  const type = container.querySelector('#report-type').value;
  const companies = container.querySelector('#report-companies').value.split(/[,\n]+/).map(s => s.trim()).filter(Boolean);
  try {
    const response = await api.reports.generate({ report_type: type, companies, async: false });
    renderReport(container, response?.report || response || {});
    toast.success('Report generated');
  } catch(err) {
    renderReport(container, mockReport(type, companies));
    toast.error('API error', err.message + ' — showing mock report');
  } finally {
    btn.disabled = false; btn.textContent = '▶ Generate';
  }
}

async function loadLatest(container) {
  const type = container.querySelector('#report-type').value;
  try {
    const response = await api.reports.latest(type);
    if (!response) { toast.info('No report found'); return; }
    renderReport(container, response);
  } catch(err) {
    renderReport(container, mockReport(type, ['Tesla', 'Microsoft']));
    toast.error('API error', err.message + ' — showing mock');
  }
}

/* ── Mock ── */
function mockReport(type, companies, id, title) {
  const now = new Date().toLocaleString();
  const analyses = companies.map((c, i) => ({
    company_name: c, ticker: ['TSLA','MSFT','AAPL','NVDA'][i] || 'N/A',
    esg_score: [72.4, 81.2, 78.6, 76.1][i] || 70,
    environment: [68, 79, 75, 72][i] || 68,
    social: [75, 83, 80, 76][i] || 74,
    governance: [74, 81, 79, 80][i] || 73,
    alpha_signal: ['+2.14σ','+1.87σ','+1.62σ','+1.94σ'][i] || '+1.5σ',
    recommendation: ['BUY','BUY','HOLD','BUY'][i] || 'HOLD',
    change_3m: ['+3.2','+1.8','+0.9','+2.4'][i] || '+1.0',
  }));
  return {
    report_id: id || 'RPT-' + Date.now(),
    title: title || `${type.charAt(0).toUpperCase()+type.slice(1)} ESG Report`,
    report_type: type, generated_at: now,
    company_analyses: analyses,
    summary: 'Portfolio continues to outperform the ESG benchmark. Technology sector leads on governance and social dimensions. Momentum remains positive across top holdings.',
    top_signals: ['NVDA: Governance improvement +4pts', 'MSFT: Carbon neutrality milestone achieved', 'TSLA: Social score dip — supply chain concern flagged'],
    risk_alerts: ['Rising VIX may pressure high-beta ESG growth stocks', 'Geopolitical risk elevated for TSLA Taiwan supply chain'],
    market_context: { regime: 'Bull Market', spy_ytd: '+18.4%', vix: '14.2', esg_premium: '+280bps' },
  };
}

/* ── Render Report ── */
function renderReport(container, report) {
  const analyses = report.company_analyses || report.data?.company_analyses || [];
  const toolbar = container.querySelector('#report-toolbar');
  toolbar.style.display = 'flex';
  container.querySelector('#report-toolbar-title').textContent = report.title || 'Report';

  const rows = analyses.map(a => `
    <tr>
      <td style="font-weight:600;color:var(--text-primary)">${a.company_name || a.company || '—'}</td>
      <td style="font-family:var(--f-mono);font-size:11px">${a.ticker || '—'}</td>
      <td class="cell-num" style="color:${scoreColor(a.esg_score)};font-weight:700">${a.esg_score != null ? Number(a.esg_score).toFixed(1) : '—'}</td>
      <td class="cell-num" style="color:var(--green)">${a.environment || '—'}</td>
      <td class="cell-num" style="color:var(--cyan)">${a.social || '—'}</td>
      <td class="cell-num" style="color:var(--purple)">${a.governance || '—'}</td>
      <td class="cell-num ${(a.change_3m||'0').startsWith('-')?'neg':'pos'}">${a.change_3m ? (a.change_3m.startsWith('+')||a.change_3m.startsWith('-')?'':'+') + a.change_3m + ' pts' : '—'}</td>
      <td><span class="badge badge-${a.recommendation==='BUY'?'filled':a.recommendation==='SELL'?'failed':'neutral'}" style="font-size:9px">${a.recommendation||'—'}</span></td>
    </tr>`).join('');

  container.querySelector('#report-body').innerHTML = `
    <div style="padding:20px;display:flex;flex-direction:column;gap:20px">

      <!-- Report header -->
      <div style="display:flex;justify-content:space-between;align-items:flex-start">
        <div>
          <div style="font-family:var(--f-display);font-size:16px;font-weight:800;color:var(--text-primary);margin-bottom:4px">${report.title || 'ESG Report'}</div>
          <div style="font-size:10px;color:var(--text-dim);font-family:var(--f-mono)">${report.report_id || ''} · Generated: ${report.generated_at || 'N/A'}</div>
        </div>
        <div style="text-align:right">
          <span class="badge badge-filled">${(report.report_type||'').toUpperCase()}</span>
        </div>
      </div>

      <!-- Market Context -->
      ${report.market_context ? `
      <div style="display:flex;gap:0;background:var(--bg-surface);border:1px solid var(--border-subtle);border-radius:8px;overflow:hidden">
        ${Object.entries(report.market_context).map(([k,v]) => `
          <div style="flex:1;padding:10px 14px;border-right:1px solid var(--border-subtle);text-align:center">
            <div style="font-size:12px;font-family:var(--f-mono);font-weight:700;color:var(--green)">${v}</div>
            <div style="font-size:9px;color:var(--text-dim);margin-top:3px;text-transform:uppercase;letter-spacing:0.06em">${k.replace(/_/g,' ')}</div>
          </div>`).join('')}
      </div>` : ''}

      <!-- Summary -->
      ${report.summary ? `
      <div style="background:rgba(0,255,136,0.05);border:1px solid rgba(0,255,136,0.15);border-radius:8px;padding:14px 16px">
        <div style="font-size:9px;color:var(--green);font-family:var(--f-mono);letter-spacing:0.1em;margin-bottom:6px">EXECUTIVE SUMMARY</div>
        <div style="font-size:12px;color:var(--text-secondary);line-height:1.65">${report.summary}</div>
      </div>` : ''}

      <!-- Company Analysis Table -->
      ${rows ? `
      <div>
        <div style="font-size:9px;color:var(--text-dim);letter-spacing:0.12em;font-family:var(--f-display);font-weight:700;margin-bottom:8px">COMPANY ESG SCORECARD</div>
        <div class="tbl-wrap"><table>
          <thead><tr><th>Company</th><th>Ticker</th><th>Overall</th><th>E</th><th>S</th><th>G</th><th>3M Δ</th><th>Signal</th></tr></thead>
          <tbody>${rows}</tbody>
        </table></div>
      </div>` : ''}

      <!-- Top Signals -->
      ${report.top_signals?.length ? `
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
        <div>
          <div style="font-size:9px;color:var(--green);font-family:var(--f-mono);letter-spacing:0.1em;margin-bottom:8px">TOP SIGNALS</div>
          ${report.top_signals.map(s => `
            <div style="display:flex;gap:8px;align-items:flex-start;padding:6px 0;border-bottom:1px solid rgba(255,255,255,0.04)">
              <span style="color:var(--green);font-size:12px">●</span>
              <span style="font-size:11px;color:var(--text-secondary)">${s}</span>
            </div>`).join('')}
        </div>
        ${report.risk_alerts?.length ? `
        <div>
          <div style="font-size:9px;color:var(--amber);font-family:var(--f-mono);letter-spacing:0.1em;margin-bottom:8px">RISK ALERTS</div>
          ${report.risk_alerts.map(s => `
            <div style="display:flex;gap:8px;align-items:flex-start;padding:6px 0;border-bottom:1px solid rgba(255,255,255,0.04)">
              <span style="color:var(--amber);font-size:12px">⚠</span>
              <span style="font-size:11px;color:var(--text-secondary)">${s}</span>
            </div>`).join('')}
        </div>` : ''}
      </div>` : ''}

    </div>`;
}

function scoreColor(v) {
  return v >= 70 ? 'var(--green)' : v >= 50 ? 'var(--amber)' : 'var(--red)';
}
