/**
 * ESG 评分仪表盘页面
 */

import { api } from '../api.js';
import { store } from '../store.js';
import { createGaugeRow } from '../components/gauge-chart.js';
import { createScoreCard } from '../components/score-card.js';
import { toastError, toastSuccess } from '../components/toast.js';
import { showFormModal } from '../components/modal.js';
import { getStorage, setStorage, removeStorage } from '../utils.js';

let cleanup = [];

const RECENT_QUERY_KEY = 'esg_recent_queries';
const PENDING_SCORE_KEY = 'esg_pending_score_lookup';

export async function render(container) {
  container.innerHTML = buildHTML();
  setupEventListeners(container);
  renderFlagshipPreview(container, buildFallbackPreview());
  await applyPendingScoreLookup(container);
}

export function destroy() {
  cleanup.forEach(fn => fn());
  cleanup = [];
}

function buildHTML() {
  return `
    <div class="page-stack">
      <section class="page-hero">
        <div>
          <h2>ESG 评分仪表盘</h2>
          <p>输入企业名称后生成综合评分、三维拆解和关键指标明细。</p>
        </div>
        <div class="text-sm text-[var(--text-secondary)]">支持对标企业和历史数据分析</div>
      </section>

      <section id="score-flagship-preview" class="score-flagship-preview card" data-hover-glow="true"></section>

      <!-- 查询表单 -->
      <div class="card">
        <h2 class="text-lg font-semibold mb-4">查询企业ESG评分</h2>
        <div id="query-form" class="space-y-4">
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label class="block text-sm font-medium mb-2">公司名称</label>
              <input id="company-input" type="text" class="w-full" placeholder="例如：Tesla" />
            </div>
            <div>
              <label class="block text-sm font-medium mb-2">股票代码 (可选)</label>
              <input id="ticker-input" type="text" class="w-full" placeholder="例如：TSLA" />
            </div>
          </div>
          <div>
            <label class="block text-sm font-medium mb-2">对标公司 (可选)</label>
            <input id="peers-input" type="text" class="w-full" placeholder="以逗号分隔，例如：Ford,GM" />
          </div>
          <div class="flex flex-col items-start gap-3 sm:flex-row sm:items-center">
            <button id="score-btn" class="btn-primary w-full sm:w-auto">生成评分</button>
            <label class="flex items-center gap-2 cursor-pointer">
              <input id="historical-cb" type="checkbox" />
              <span class="text-sm">包含历史数据</span>
            </label>
          </div>
        </div>
      </div>

      <!-- 加载状态 -->
      <div id="loading-state" class="hidden">
        <div class="card text-center">
          <div class="text-4xl mb-4">⏳</div>
          <p class="text-[#94A3B8]">分析中... (这可能需要 10-30 秒)</p>
        </div>
      </div>

      <!-- 结果区域 -->
      <div id="results-area" class="hidden space-y-6">
        <!-- 仪表盘行 -->
        <div id="gauges-area"></div>

        <!-- 雷达图 -->
        <div class="card">
          <h3 class="text-lg font-semibold mb-4">ESG 三维评分</h3>
          <div class="chart-container">
            <canvas id="radar-chart"></canvas>
          </div>
        </div>

        <!-- 柱状图 -->
        <div class="card">
          <h3 class="text-lg font-semibold mb-4">维度详情</h3>
          <div id="dimension-charts" class="space-y-6"></div>
        </div>

        <!-- 指标表格 -->
        <div class="card">
          <h3 class="text-lg font-semibold mb-4">详细指标</h3>
          <div class="overflow-x-auto">
            <table>
              <thead>
                <tr>
                  <th>维度</th>
                  <th>指标名称</th>
                  <th>得分</th>
                  <th>权重</th>
                  <th>趋势</th>
                  <th>评级</th>
                  <th>说明</th>
                </tr>
              </thead>
              <tbody id="metrics-tbody"></tbody>
            </table>
          </div>
        </div>

        <!-- 优势和劣势 -->
        <div class="grid grid-cols-1 xl:grid-cols-2 gap-4">
          <div class="card">
            <h3 class="text-lg font-semibold mb-4">✅ 主要优势</h3>
            <ul id="strengths-list" class="space-y-2"></ul>
          </div>
          <div class="card">
            <h3 class="text-lg font-semibold mb-4">⚠️ 主要劣势</h3>
            <ul id="weaknesses-list" class="space-y-2"></ul>
          </div>
        </div>

        <!-- 建议 -->
        <div class="card">
          <h3 class="text-lg font-semibold mb-4">💡 改进建议</h3>
          <ul id="recommendations-list" class="space-y-2"></ul>
        </div>
      </div>
    </div>
  `;
}

function setupEventListeners(container) {
  const scoreBtn = container.querySelector('#score-btn');

  scoreBtn.addEventListener('click', async () => {
    const company = container.querySelector('#company-input').value.trim();
    const ticker = container.querySelector('#ticker-input').value.trim();
    const peersStr = container.querySelector('#peers-input').value.trim();
    const hasHistory = container.querySelector('#historical-cb').checked;

    if (!company) {
      toastError('请输入公司名称', '验证失败');
      return;
    }

    const peers = peersStr ? peersStr.split(',').map(p => p.trim()).filter(p => p) : [];

    await generateScore(container, {
      company,
      ticker: ticker || undefined,
      peers: peers.length > 0 ? peers : undefined,
      include_visualization: true,
      historical_data: hasHistory,
    });
  });
}

async function applyPendingScoreLookup(container) {
  const pending = getStorage(PENDING_SCORE_KEY, null);
  if (!pending) return;

  removeStorage(PENDING_SCORE_KEY);

  const companyInput = container.querySelector('#company-input');
  const tickerInput = container.querySelector('#ticker-input');
  companyInput.value = pending.company || pending.rawPrompt || '';

  if (pending.company && pending.company.toUpperCase() === pending.company && pending.company.length <= 5) {
    tickerInput.value = pending.company;
  }

  if (pending.company || pending.rawPrompt) {
    await generateScore(container, {
      company: pending.company || pending.rawPrompt,
      include_visualization: true,
      historical_data: false,
    });
  }
}

function renderFlagshipPreview(container, preview) {
  const target = container.querySelector('#score-flagship-preview');
  if (!target) return;

  target.innerHTML = `
    <div class="overview-section-head">
      <div>
        <div class="overview-section-head__kicker">Executive Snapshot</div>
        <h2>${preview.company} 的评分总览</h2>
      </div>
      <p>在完整图表与明细表之前，先用一屏快速看清整体评分、置信度和三维拆解。</p>
    </div>
    <div class="score-preview-grid">
      <div class="score-preview-card">
        <div class="score-preview-card__eyebrow">Overall Score</div>
        <div class="score-preview-card__value">${preview.overall}</div>
        <div class="score-preview-card__hint">置信度 ${preview.confidence}</div>
      </div>
      <div class="score-preview-bars">
        ${preview.dimensions.map((item) => `
          <div class="score-preview-bar">
            <div class="score-preview-bar__head">
              <span>${item.label}</span>
              <span>${item.value}/100</span>
            </div>
            <div class="score-preview-bar__track">
              <span class="score-preview-bar__fill score-preview-bar__fill--${item.key.toLowerCase()}" style="width:${item.value}%"></span>
            </div>
          </div>
        `).join('')}
      </div>
    </div>
  `;
}

function buildFallbackPreview() {
  return {
    company: 'Tesla',
    overall: '72/100',
    confidence: '85%',
    dimensions: [
      { key: 'E', label: '环保 (E)', value: 78 },
      { key: 'S', label: '社会 (S)', value: 65 },
      { key: 'G', label: '治理 (G)', value: 73 },
    ],
  };
}

function buildPreviewFromReport(report) {
  return {
    company: report.company || '目标企业',
    overall: `${report.overall_score}/100`,
    confidence: `${Math.round((report.confidence || 0.85) * 100)}%`,
    dimensions: [
      { key: 'E', label: '环保 (E)', value: Math.round(report.e_scores?.overall_score || 0) },
      { key: 'S', label: '社会 (S)', value: Math.round(report.s_scores?.overall_score || 0) },
      { key: 'G', label: '治理 (G)', value: Math.round(report.g_scores?.overall_score || 0) },
    ],
  };
}

function recordScoreLookup(query) {
  const items = (getStorage(RECENT_QUERY_KEY, []) || [])
    .filter((item) => item.query !== query);

  items.unshift({
    query,
    mode: 'score',
    createdAt: new Date().toISOString(),
  });

  setStorage(RECENT_QUERY_KEY, items.slice(0, 6));
}

async function generateScore(container, payload) {
  const loading = container.querySelector('#loading-state');
  const results = container.querySelector('#results-area');

  loading.classList.remove('hidden');
  results.classList.add('hidden');

  try {
    store.setLoading('score', true);
    recordScoreLookup(payload.company || payload.ticker || 'ESG 评分请求');
    const response = await api.agent.getESGScore(payload);

    // 保存到 store
    store.setCurrentReport(response.esg_report);
    renderFlagshipPreview(container, buildPreviewFromReport(response.esg_report));

    // 渲染结果
    renderResults(container, response);

    results.classList.remove('hidden');
    toastSuccess('评分生成成功', '成功');

  } catch (error) {
    console.error('生成评分失败:', error);
    toastError(error.message, '生成失败');
  } finally {
    loading.classList.add('hidden');
    store.setLoading('score', false);
  }
}

function renderResults(container, data) {
  const report = data.esg_report;
  const viz = data.visualizations;

  // 渲染仪表盘
  const gaugesArea = container.querySelector('#gauges-area');
  gaugesArea.innerHTML = createGaugeRow({
    e_score: report.e_scores.overall_score,
    s_score: report.s_scores.overall_score,
    g_score: report.g_scores.overall_score,
    overall_score: report.overall_score,
  });

  // 渲染雷达图
  if (viz.radar && window.Chart) {
    const ctx = container.querySelector('#radar-chart');
    new Chart(ctx, {
      type: 'radar',
      data: viz.radar.data,
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { labels: { color: '#F0F4F8' } },
        },
        scales: {
          r: {
            min: 0,
            max: 100,
            grid: { color: '#2D3748' },
            ticks: { color: '#94A3B8' },
            pointLabels: { color: '#F0F4F8' },
          }
        }
      }
    });
  }

  // 渲染柱状图
  const dimChartsArea = container.querySelector('#dimension-charts');
  const dims = [
    { label: '环境 (E)', score: report.e_scores, color: '#10B981' },
    { label: '社会 (S)', score: report.s_scores, color: '#3B82F6' },
    { label: '治理 (G)', score: report.g_scores, color: '#F59E0B' },
  ];

  dimChartsArea.innerHTML = dims.map(dim => `
    <div>
      <h4 class="font-medium mb-2">${dim.label} (${dim.score.overall_score}/100)</h4>
      <div class="space-y-2">
        ${Object.entries(dim.score.metrics || {}).map(([key, metric]) => `
          <div class="flex items-center gap-2">
            <span class="text-xs w-32 truncate">${metric.name}</span>
            <div class="flex-1 h-6 bg-[#1C2333] rounded-lg overflow-hidden">
              <div class="h-full" style="width: ${metric.score}%; background-color: ${dim.color};"></div>
            </div>
            <span class="text-xs font-mono text-[#94A3B8]">${metric.score}</span>
          </div>
        `).join('')}
      </div>
    </div>
  `).join('');

  // 渲染指标表格
  const tbody = container.querySelector('#metrics-tbody');
  tbody.innerHTML = '';

  Object.entries(report.e_scores.metrics || {}).concat(
    Object.entries(report.s_scores.metrics || {}),
    Object.entries(report.g_scores.metrics || {})
  ).forEach(([key, metric], idx) => {
    const dim = idx < 5 ? 'E' : idx < 10 ? 'S' : 'G';
    const row = document.createElement('tr');
    row.innerHTML = `
      <td><span class="badge" style="background-color: var(--esg-${dim.toLowerCase()}-dim); color: var(--esg-${dim.toLowerCase()})">${dim}</span></td>
      <td>${metric.name}</td>
      <td><span class="font-mono font-bold" style="color: ${scoreColor(metric.score)};">${metric.score}</span></td>
      <td>${(metric.weight * 100).toFixed(0)}%</td>
      <td>${trendIcon(metric.trend || 'stable')}</td>
      <td><span class="badge badge-info">${scoreLabel(metric.score)}</span></td>
      <td class="text-xs">${metric.reasoning || '-'}</td>
    `;
    tbody.appendChild(row);
  });

  // 渲染优劣势
  const strengthsList = container.querySelector('#strengths-list');
  strengthsList.innerHTML = (report.key_strengths || [])
    .map(s => `<li class="text-sm text-[#94A3B8]">✓ ${s}</li>`)
    .join('');

  const weaknessesList = container.querySelector('#weaknesses-list');
  weaknessesList.innerHTML = (report.key_weaknesses || [])
    .map(w => `<li class="text-sm text-[#94A3B8]">✗ ${w}</li>`)
    .join('');

  // 渲染建议
  const recommendationsList = container.querySelector('#recommendations-list');
  recommendationsList.innerHTML = (report.recommendations || [])
    .map(r => `<li class="text-sm text-[#94A3B8]">• ${r}</li>`)
    .join('');
}

function scoreColor(score) {
  if (score >= 80) return '#10B981';
  if (score >= 60) return '#84CC16';
  if (score >= 40) return '#F59E0B';
  return '#EF4444';
}

function scoreLabel(score) {
  if (score >= 80) return 'A';
  if (score >= 60) return 'B';
  if (score >= 40) return 'C';
  return 'D';
}

function trendIcon(trend) {
  return { up: '📈', down: '📉', stable: '➡️' }[trend] || '—';
}
