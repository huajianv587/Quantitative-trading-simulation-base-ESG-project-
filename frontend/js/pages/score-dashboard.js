import { api } from '../qtapi.js?v=8';
import { toast } from '../components/toast.js?v=8';
import { getLang, onLangChange } from '../i18n.js?v=8';

const PEERS_DEFAULT = { TSLA: ['F', 'GM', 'NIO'], AAPL: ['MSFT', 'GOOGL', 'META'], NVDA: ['AMD', 'INTC', 'AVGO'] };

const COPY = {
  en: {
    title: 'ESG Score Dashboard',
    subtitle: 'Environmental / Social / Governance / peer benchmark / trend analysis',
    export: 'Export Report',
    scoreCompany: 'Score Company',
    scoreSub: 'ESG agent / peer benchmark / trend',
    company: 'Company Name',
    ticker: 'Ticker',
    peers: 'Peer Companies',
    depth: 'Analysis Depth',
    standard: 'Standard (E+S+G)',
    deep: 'Deep (all sub-dimensions)',
    quick: 'Quick Score',
    run: 'Run ESG Score',
    scoring: 'Scoring...',
    trend: 'Score Trend (12mo)',
    compare: 'Quick Compare',
    overall: 'Overall',
    radar: 'Multi-Dimension Radar',
    peer: 'Peer Comparison',
    rating: 'Rating',
    percentile: 'industry percentile',
    exportPending: 'PDF export is not connected yet',
    apiError: 'API error, showing mock data',
    environment: 'Environment',
    social: 'Social',
    governance: 'Governance',
    descE: 'Carbon emissions, energy efficiency, water usage, waste management, clean energy transition.',
    descS: 'Labor practices, workplace safety, diversity, inclusion, community impact, human rights.',
    descG: 'Board independence, executive pay alignment, audit quality, shareholder rights, transparency.',
    carbon: 'Carbon Intensity',
    renewable: 'Renewable Energy %',
    water: 'Water Efficiency',
    waste: 'Waste Reduction',
    climate: 'Climate Risk',
    workforce: 'Workforce Diversity',
    safety: 'Safety Record',
    community: 'Community Score',
    supply: 'Supply Chain Ethics',
    wellbeing: 'Employee Wellbeing',
    board: 'Board Independence',
    pay: 'CEO Pay Ratio',
    audit: 'Audit Quality',
    rights: 'Shareholder Rights',
    anticorruption: 'Anti-corruption',
    momentum: 'Momentum',
    disclosure: 'Disclosure',
    innovation: 'Innovation',
    thisCompany: 'this',
  },
  zh: {
    title: 'ESG 评分仪表盘',
    subtitle: '环境 / 社会 / 治理 / 同业对比 / 趋势分析',
    export: '导出报告',
    scoreCompany: '公司评分',
    scoreSub: 'ESG 智能体 / 同业基准 / 趋势',
    company: '公司名称',
    ticker: '股票代码',
    peers: '同业公司',
    depth: '分析深度',
    standard: '标准版（E+S+G）',
    deep: '深度版（全部子维度）',
    quick: '快速评分',
    run: '运行 ESG 评分',
    scoring: '评分中...',
    trend: '评分趋势（12个月）',
    compare: '快速对比',
    overall: '综合评分',
    radar: '多维雷达图',
    peer: '同业对比',
    rating: '评级',
    percentile: '行业分位',
    exportPending: 'PDF 导出尚未接入',
    apiError: '接口异常，已展示本地样例数据',
    environment: '环境',
    social: '社会',
    governance: '治理',
    descE: '碳排放、能源效率、水资源使用、废弃物管理与清洁能源转型。',
    descS: '劳工实践、工作安全、多元包容、社区影响与人权议题。',
    descG: '董事会独立性、高管薪酬、审计质量、股东权利与透明度。',
    carbon: '碳强度',
    renewable: '可再生能源占比',
    water: '水资源效率',
    waste: '废弃物减量',
    climate: '气候风险',
    workforce: '员工多元化',
    safety: '安全记录',
    community: '社区评分',
    supply: '供应链伦理',
    wellbeing: '员工福祉',
    board: '董事会独立性',
    pay: 'CEO 薪酬比',
    audit: '审计质量',
    rights: '股东权利',
    anticorruption: '反腐败',
    momentum: '动量',
    disclosure: '披露',
    innovation: '创新',
    thisCompany: '本公司',
  },
};

let _currentContainer = null;
let _lastScoreResponse = null;
let _langCleanup = null;

export function render(container) {
  _currentContainer = container;
  container.innerHTML = buildShell();
  bindEvents(container);
  _langCleanup ||= onLangChange(() => {
    if (_currentContainer?.isConnected) {
      const response = _lastScoreResponse || mockEsgResult('Tesla', 'TSLA');
      _currentContainer.innerHTML = buildShell();
      bindEvents(_currentContainer);
      renderScore(_currentContainer, response);
    }
  });
  renderScore(container, mockEsgResult('Tesla', 'TSLA'));
}

export function destroy() {
  _currentContainer = null;
  _lastScoreResponse = null;
  _langCleanup?.();
  _langCleanup = null;
}

function c(key) {
  const current = getLang() === 'zh' ? 'zh' : 'en';
  return COPY[current][key] || COPY.en[key] || key;
}

function dimensions() {
  return [
    { key: 'environment', label: c('environment'), icon: 'E', color: '#00FF88', desc: c('descE') },
    { key: 'social', label: c('social'), icon: 'S', color: '#00E5FF', desc: c('descS') },
    { key: 'governance', label: c('governance'), icon: 'G', color: '#B44EFF', desc: c('descG') },
  ];
}

function subScores() {
  return {
    environment: [c('carbon'), c('renewable'), c('water'), c('waste'), c('climate')],
    social: [c('workforce'), c('safety'), c('community'), c('supply'), c('wellbeing')],
    governance: [c('board'), c('pay'), c('audit'), c('rights'), c('anticorruption')],
  };
}

function buildShell() {
  return `
  <div class="score-dashboard-page" data-no-autotranslate="true">
    <div class="page-header">
      <div>
        <div class="page-header__title">${c('title')}</div>
        <div class="page-header__sub">${c('subtitle')}</div>
      </div>
      <div class="page-header__actions">
        <button class="btn btn-ghost btn-sm" id="btn-export-esg">${c('export')}</button>
      </div>
    </div>

    <div class="grid-sidebar score-dashboard-grid">
      <aside class="score-sidebar">
        <div class="run-panel">
          <div class="run-panel__header">
            <div class="run-panel__title">${c('scoreCompany')}</div>
            <div class="run-panel__sub">${c('scoreSub')}</div>
          </div>
          <div class="run-panel__body">
            <div class="form-row">
              <div class="form-group">
                <label class="form-label">${c('company')}</label>
                <input class="form-input" id="score-company" value="Tesla">
              </div>
              <div class="form-group">
                <label class="form-label">${c('ticker')}</label>
                <input class="form-input" id="score-ticker" value="TSLA" style="text-transform:uppercase">
              </div>
            </div>
            <div class="form-group">
              <label class="form-label">${c('peers')}</label>
              <input class="form-input" id="score-peers" placeholder="F, GM, NIO">
            </div>
            <div class="form-group">
              <label class="form-label">${c('depth')}</label>
              <select class="form-select" id="score-depth">
                <option value="standard" selected>${c('standard')}</option>
                <option value="deep">${c('deep')}</option>
                <option value="quick">${c('quick')}</option>
              </select>
            </div>
          </div>
          <div class="run-panel__foot">
            <button class="btn btn-primary btn-lg score-run-btn" id="score-btn">${c('run')}</button>
          </div>
        </div>

        <div class="card">
          <div class="card-header"><span class="card-title">${c('trend')}</span></div>
          <div class="card-body score-trend-body">
            <canvas id="esg-trend-canvas"></canvas>
          </div>
        </div>

        <div class="card">
          <div class="card-header"><span class="card-title">${c('compare')}</span></div>
          <div id="quick-compare-list" class="score-compare-list"></div>
        </div>
      </aside>

      <main class="score-results">
        <section class="esg-hero" id="esg-hero">
          <div class="esg-hero-left">
            <div class="esg-hero-company" id="esg-company-name">Tesla</div>
            <div class="esg-hero-ticker" id="esg-ticker-val">TSLA</div>
            <div id="esg-verdict-tag"></div>
          </div>
          <div class="esg-hero-metrics">
            <div class="esg-ring-wrap">
              <canvas id="esg-ring" width="120" height="120"></canvas>
              <div class="esg-ring-label">${c('overall')}</div>
            </div>
            <div class="esg-dim-row" id="esg-dim-row"></div>
          </div>
        </section>

        <section class="score-dim-grid" id="esg-dim-cards"></section>

        <section class="card esg-radar-card">
          <div class="card-header"><span class="card-title">${c('radar')}</span></div>
          <div class="esg-radar-layout">
            <div class="esg-radar-canvas-wrap">
              <canvas id="esg-radar"></canvas>
            </div>
            <div id="radar-legend" class="esg-radar-legend"></div>
          </div>
        </section>

        <section class="card">
          <div class="card-header"><span class="card-title">${c('peer')}</span></div>
          <div class="tbl-wrap" id="peer-table"></div>
        </section>
      </main>
    </div>
  </div>`;
}

function bindEvents(container) {
  container.querySelector('#score-btn')?.addEventListener('click', () => runScore(container));
  container.querySelector('#score-ticker')?.addEventListener('change', event => {
    const ticker = event.target.value.trim().toUpperCase();
    const peers = PEERS_DEFAULT[ticker];
    if (peers) container.querySelector('#score-peers').value = peers.join(', ');
  });
  container.querySelector('#btn-export-esg')?.addEventListener('click', () => toast.info(c('export'), c('exportPending')));
}

async function runScore(container) {
  const btn = container.querySelector('#score-btn');
  btn.disabled = true;
  btn.textContent = c('scoring');

  const company = container.querySelector('#score-company').value.trim();
  const ticker = container.querySelector('#score-ticker').value.trim().toUpperCase() || null;
  const peersRaw = container.querySelector('#score-peers').value.trim();
  const peers = peersRaw ? peersRaw.split(/[,\s]+/).filter(Boolean) : null;

  try {
    const response = await api.agent.esgScore({ company, ticker, peers, include_visualization: false });
    renderScore(container, response || {});
    toast.success(c('run'), company);
  } catch (err) {
    renderScore(container, mockEsgResult(company, ticker));
    toast.error(c('apiError'), err.message);
  } finally {
    btn.disabled = false;
    btn.textContent = c('run');
  }
}

function mockEsgResult(company, ticker) {
  return {
    esg_report: {
      company,
      ticker,
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
        { name: 'Ford Motor', ticker: 'F', overall: 61.2, e: 58.3, s: 66.1, g: 59.2 },
        { name: 'GM', ticker: 'GM', overall: 63.8, e: 61.4, s: 67.2, g: 62.8 },
        { name: 'NIO', ticker: 'NIO', overall: 55.1, e: 62.8, s: 51.4, g: 51.1 },
      ],
    },
  };
}

function renderScore(container, response) {
  _lastScoreResponse = response;
  const report = response.esg_report || {};
  const overall = firstDef(report.overall_score, report.overall, 72.4);
  const eScore = firstDef(report.e_score, report.environment_score, 68.1);
  const sScore = firstDef(report.s_score, report.social_score, 74.8);
  const gScore = firstDef(report.g_score, report.governance_score, 74.2);
  const company = report.company || 'Company';
  const ticker = report.ticker || '-';
  const rating = report.rating || ratingFromScore(overall);
  const percentile = report.percentile || Math.round(overall * 1.05);

  container.querySelector('#esg-company-name').textContent = company;
  container.querySelector('#esg-ticker-val').textContent = `${ticker} / ${report.industry || 'Equity'} / ${c('rating')}: ${rating}`;
  container.querySelector('#esg-verdict-tag').innerHTML = `
    <div class="score-verdict-row">
      <span class="score-rating-pill">${rating}</span>
      <span>${Math.max(0, 100 - percentile)}th ${c('percentile')}</span>
    </div>`;

  window.setTimeout(() => {
    drawRingGauge(container.querySelector('#esg-ring'), overall);
    drawRadar(container, eScore, sScore, gScore);
    drawTrendLine(container.querySelector('#esg-trend-canvas'), report.trend);
  }, 40);

  renderDimBars(container, eScore, sScore, gScore);
  renderDimensionCards(container, report, eScore, sScore, gScore);
  renderPeers(container, report.peers || [], overall);
  renderQuickCompare(container, report.peers || []);
}

function renderDimBars(container, eScore, sScore, gScore) {
  container.querySelector('#esg-dim-row').innerHTML = [
    ['E', eScore, '#00FF88'],
    ['S', sScore, '#00E5FF'],
    ['G', gScore, '#B44EFF'],
  ].map(([label, value, color]) => `
    <div class="esg-dim-pill">
      <strong style="color:${color}">${Number(value).toFixed(1)}</strong>
      <span>${label}</span>
      <div><i style="width:${Math.max(0, Math.min(100, value))}%;background:${color}"></i></div>
    </div>`).join('');
}

function renderDimensionCards(container, report, eScore, sScore, gScore) {
  const scores = { environment: eScore, social: sScore, governance: gScore };
  const subs = subScores();
  container.querySelector('#esg-dim-cards').innerHTML = dimensions().map(dimension => {
    const score = scores[dimension.key];
    const values = report.sub_scores?.[dimension.key] || [];
    const rows = subs[dimension.key].map((name, index) => {
      const value = values[index] ?? score;
      return `
        <div class="score-sub-row">
          <span>${name}</span>
          <div><i style="width:${Math.max(0, Math.min(100, value))}%;background:${dimension.color}"></i></div>
          <strong style="color:${dimension.color}">${Number(value).toFixed(0)}</strong>
        </div>`;
    }).join('');
    return `
      <article class="card score-dim-card" style="border-color:${dimension.color}33">
        <div class="score-dim-card__head">
          <span class="score-dim-card__icon" style="color:${dimension.color}">${dimension.icon}</span>
          <strong>${dimension.label}</strong>
          <em style="color:${dimension.color}">${Number(score).toFixed(1)}</em>
        </div>
        <p>${dimension.desc}</p>
        ${rows}
      </article>`;
  }).join('');
}

function renderPeers(container, peers, overall) {
  if (!peers.length) {
    container.querySelector('#peer-table').innerHTML = '';
    return;
  }
  container.querySelector('#peer-table').innerHTML = `<table>
    <thead><tr><th>Company</th><th>Ticker</th><th>Overall</th><th>E</th><th>S</th><th>G</th><th>vs This</th></tr></thead>
    <tbody>
      ${peers.map((peer, index) => {
        const isSelf = index === 0;
        const diff = Number(peer.overall || 0) - Number(overall || 0);
        return `<tr class="${isSelf ? 'score-self-row' : ''}">
          <td>${escapeHtml(peer.name)}</td>
          <td>${escapeHtml(peer.ticker)}</td>
          <td class="cell-num" style="color:${scoreColor(peer.overall)}">${Number(peer.overall).toFixed(1)}</td>
          <td class="cell-num">${Number(peer.e).toFixed(1)}</td>
          <td class="cell-num">${Number(peer.s).toFixed(1)}</td>
          <td class="cell-num">${Number(peer.g).toFixed(1)}</td>
          <td class="cell-num ${!isSelf && diff < 0 ? 'neg' : !isSelf && diff > 0 ? 'pos' : ''}">${isSelf ? c('thisCompany') : `${diff > 0 ? '+' : ''}${diff.toFixed(1)}`}</td>
        </tr>`;
      }).join('')}
    </tbody>
  </table>`;
}

function renderQuickCompare(container, peers) {
  container.querySelector('#quick-compare-list').innerHTML = peers.map(peer => `
    <div class="score-compare-row">
      <span>${escapeHtml(peer.ticker)}</span>
      <div><i style="width:${Math.max(0, Math.min(100, peer.overall))}%;background:${scoreColor(peer.overall)}"></i></div>
      <strong style="color:${scoreColor(peer.overall)}">${Number(peer.overall).toFixed(0)}</strong>
    </div>`).join('');
}

function drawRingGauge(canvas, value) {
  if (!canvas) return;
  const dpr = window.devicePixelRatio || 1;
  const size = 120;
  canvas.width = size * dpr;
  canvas.height = size * dpr;
  canvas.style.width = `${size}px`;
  canvas.style.height = `${size}px`;
  const ctx = canvas.getContext('2d');
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, size, size);
  const cx = 60;
  const cy = 60;
  const radius = 46;
  const start = -Math.PI * 0.75;
  const sweep = Math.PI * 1.5;
  const end = start + sweep * (Number(value) / 100);

  ctx.beginPath();
  ctx.arc(cx, cy, radius, start, start + sweep);
  ctx.strokeStyle = ringTrack();
  ctx.lineWidth = 10;
  ctx.lineCap = 'round';
  ctx.stroke();

  const gradient = ctx.createLinearGradient(cx - radius, cy, cx + radius, cy);
  gradient.addColorStop(0, value > 60 ? '#00E5FF' : '#FF3D57');
  gradient.addColorStop(1, '#00FF88');
  ctx.beginPath();
  ctx.arc(cx, cy, radius, start, end);
  ctx.strokeStyle = gradient;
  ctx.lineWidth = 10;
  ctx.lineCap = 'round';
  ctx.stroke();

  ctx.fillStyle = canvasText();
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.font = '700 18px IBM Plex Mono';
  ctx.fillText(Number(value).toFixed(0), cx, cy - 4);
  ctx.font = '10px IBM Plex Mono';
  ctx.fillStyle = canvasMuted();
  ctx.fillText('/ 100', cx, cy + 13);
}

function drawRadar(container, e, s, g) {
  const canvas = container.querySelector('#esg-radar');
  const legendEl = container.querySelector('#radar-legend');
  if (!canvas) return;

  const dpr = window.devicePixelRatio || 1;
  const cssWidth = Math.max(330, Math.min(520, canvas.parentElement?.clientWidth || 420));
  const cssHeight = 340;
  canvas.width = cssWidth * dpr;
  canvas.height = cssHeight * dpr;
  canvas.style.width = '100%';
  canvas.style.height = `${cssHeight}px`;

  const ctx = canvas.getContext('2d');
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, cssWidth, cssHeight);

  const axes = [
    { label: c('environment'), val: e },
    { label: c('social'), val: s },
    { label: c('governance'), val: g },
    { label: c('momentum'), val: 71 },
    { label: c('disclosure'), val: 68 },
    { label: c('innovation'), val: 74 },
  ];
  const cx = cssWidth / 2;
  const cy = cssHeight / 2 + 4;
  const maxR = Math.min(108, cssWidth * 0.25);
  const labelR = maxR + 34;
  const angle = i => (Math.PI * 2 * i / axes.length) - Math.PI / 2;

  [20, 40, 60, 80, 100].forEach(value => {
    ctx.beginPath();
    axes.forEach((_, index) => {
      const a = angle(index);
      const r = value / 100 * maxR;
      const x = cx + Math.cos(a) * r;
      const y = cy + Math.sin(a) * r;
      if (index === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.closePath();
    ctx.strokeStyle = gridLine();
    ctx.lineWidth = 1;
    ctx.stroke();
  });

  axes.forEach((_, index) => {
    const a = angle(index);
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.lineTo(cx + Math.cos(a) * maxR, cy + Math.sin(a) * maxR);
    ctx.strokeStyle = gridLine();
    ctx.stroke();
  });

  ctx.beginPath();
  axes.forEach((axis, index) => {
    const a = angle(index);
    const r = Number(axis.val) / 100 * maxR;
    const x = cx + Math.cos(a) * r;
    const y = cy + Math.sin(a) * r;
    if (index === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.closePath();
  ctx.fillStyle = 'rgba(0,255,136,0.13)';
  ctx.fill();
  ctx.strokeStyle = '#00FF88';
  ctx.lineWidth = 2;
  ctx.stroke();

  axes.forEach((axis, index) => {
    const a = angle(index);
    const r = Number(axis.val) / 100 * maxR;
    ctx.beginPath();
    ctx.arc(cx + Math.cos(a) * r, cy + Math.sin(a) * r, 4, 0, Math.PI * 2);
    ctx.fillStyle = '#00FF88';
    ctx.fill();

    ctx.font = `${getLang() === 'zh' ? '12px' : '11px'} IBM Plex Mono`;
    ctx.fillStyle = canvasMutedStrong();
    ctx.textBaseline = 'middle';
    const rawX = cx + Math.cos(a) * labelR;
    const rawY = cy + Math.sin(a) * labelR;
    const labelWidth = ctx.measureText(axis.label).width;
    const x = clamp(rawX, labelWidth / 2 + 10, cssWidth - labelWidth / 2 - 10);
    const y = clamp(rawY, 18, cssHeight - 18);
    ctx.textAlign = 'center';
    ctx.fillText(axis.label, x, y);
  });

  if (legendEl) {
    legendEl.innerHTML = axes.map(axis => `
      <div class="esg-radar-legend__row">
        <span>${axis.label}</span>
        <strong style="color:${scoreColor(axis.val)}">${Number(axis.val).toFixed(1)}</strong>
      </div>`).join('');
  }
}

function drawTrendLine(canvas, trend) {
  if (!canvas) return;
  const data = trend || Array.from({ length: 12 }, (_, index) => 60 + index * 1.2);
  const dpr = window.devicePixelRatio || 1;
  const width = canvas.parentElement?.clientWidth || 280;
  const height = 128;
  canvas.width = width * dpr;
  canvas.height = height * dpr;
  canvas.style.width = '100%';
  canvas.style.height = `${height}px`;
  const ctx = canvas.getContext('2d');
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = canvasBg();
  ctx.fillRect(0, 0, width, height);

  const padL = 36;
  const padR = 14;
  const padT = 12;
  const padB = 26;
  const chartW = width - padL - padR;
  const chartH = height - padT - padB;
  const minV = Math.min(...data) * 0.97;
  const maxV = Math.max(...data) * 1.02;
  const xAt = index => padL + (index / Math.max(data.length - 1, 1)) * chartW;
  const yAt = value => padT + chartH - ((value - minV) / Math.max(maxV - minV, 1)) * chartH;

  [0, 0.5, 1].forEach(step => {
    const y = padT + chartH * (1 - step);
    ctx.beginPath();
    ctx.moveTo(padL, y);
    ctx.lineTo(width - padR, y);
    ctx.strokeStyle = gridLine();
    ctx.stroke();
  });

  const gradient = ctx.createLinearGradient(0, padT, 0, padT + chartH);
  gradient.addColorStop(0, 'rgba(0,255,136,0.2)');
  gradient.addColorStop(1, 'rgba(0,255,136,0)');
  ctx.beginPath();
  data.forEach((value, index) => index === 0 ? ctx.moveTo(xAt(index), yAt(value)) : ctx.lineTo(xAt(index), yAt(value)));
  ctx.lineTo(xAt(data.length - 1), padT + chartH);
  ctx.lineTo(xAt(0), padT + chartH);
  ctx.closePath();
  ctx.fillStyle = gradient;
  ctx.fill();

  ctx.beginPath();
  data.forEach((value, index) => index === 0 ? ctx.moveTo(xAt(index), yAt(value)) : ctx.lineTo(xAt(index), yAt(value)));
  ctx.strokeStyle = '#00FF88';
  ctx.lineWidth = 2;
  ctx.stroke();
}

function scoreColor(value) {
  const n = Number(value);
  return n >= 70 ? 'var(--green)' : n >= 50 ? 'var(--amber)' : 'var(--red)';
}

function ratingFromScore(value) {
  return value >= 80 ? 'AAA' : value >= 70 ? 'AA' : value >= 60 ? 'A' : value >= 50 ? 'BBB' : 'BB';
}

function firstDef(...vals) {
  return vals.find(value => value != null);
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, ch => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  }[ch]));
}

function isLight() {
  return document.body.classList.contains('light');
}

function canvasBg() {
  return isLight() ? '#FFFFFF' : '#07070F';
}

function canvasText() {
  return isLight() ? '#0C1128' : '#F0F4FF';
}

function canvasMuted() {
  return isLight() ? 'rgba(30,50,100,0.45)' : 'rgba(140,160,220,0.55)';
}

function canvasMutedStrong() {
  return isLight() ? 'rgba(12,17,40,0.72)' : 'rgba(220,228,255,0.72)';
}

function gridLine() {
  return isLight() ? 'rgba(0,0,0,0.08)' : 'rgba(255,255,255,0.08)';
}

function ringTrack() {
  return isLight() ? 'rgba(0,0,0,0.08)' : 'rgba(255,255,255,0.08)';
}
