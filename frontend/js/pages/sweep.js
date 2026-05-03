import { api } from '../qtapi.js?v=8';
import { toast } from '../components/toast.js?v=8';
import { getLang } from '../i18n.js?v=8';

let _sweepChart = null;
let _currentSweepId = null;

const COPY = {
  en: {
    title: 'Parameter Sweep',
    subtitle: 'Multi-dimensional parameter optimization with vectorbt-style batch execution',
    runTitle: 'Configure Sweep',
    runSub: 'Define parameter ranges and optimization targets',
    strategy: 'Strategy Name',
    baseUniverse: 'Base Universe',
    paramRanges: 'Parameter Ranges',
    addParam: '+ Add Parameter',
    paramName: 'Parameter Name',
    paramMin: 'Min',
    paramMax: 'Max',
    paramStep: 'Step',
    optimizationTarget: 'Optimization Target',
    sharpe: 'Sharpe Ratio',
    returns: 'Total Returns',
    calmar: 'Calmar Ratio',
    sortino: 'Sortino Ratio',
    maxCombos: 'Max Combinations',
    runSweep: 'Run Sweep',
    running: 'Running sweep...',
    recentSweeps: 'Recent Sweeps',
    sweepResults: 'Sweep Results',
    bestCombo: 'Best Combination',
    allCombos: 'All Combinations',
    combo: 'Combo',
    params: 'Parameters',
    performance: 'Performance',
    rank: 'Rank',
    noSweeps: 'No sweeps yet',
    loadFailed: 'Failed to load sweeps',
    complete: 'Sweep complete',
    failed: 'Sweep failed',
    viewDetails: 'View Details',
    heatmap: 'Performance Heatmap',
    convergence: 'Convergence Plot',
    distribution: 'Performance Distribution',
  },
  zh: {
    title: '参数扫描',
    subtitle: '多维参数优化，支持 vectorbt 风格的批量执行',
    runTitle: '配置扫描',
    runSub: '定义参数范围和优化目标',
    strategy: '策略名称',
    baseUniverse: '基础股票池',
    paramRanges: '参数范围',
    addParam: '+ 添加参数',
    paramName: '参数名称',
    paramMin: '最小值',
    paramMax: '最大值',
    paramStep: '步长',
    optimizationTarget: '优化目标',
    sharpe: '夏普比率',
    returns: '总收益',
    calmar: 'Calmar 比率',
    sortino: 'Sortino 比率',
    maxCombos: '最大组合数',
    runSweep: '运行扫描',
    running: '扫描中...',
    recentSweeps: '最近扫描',
    sweepResults: '扫描结果',
    bestCombo: '最佳组合',
    allCombos: '所有组合',
    combo: '组合',
    params: '参数',
    performance: '性能',
    rank: '排名',
    noSweeps: '暂无扫描记录',
    loadFailed: '加载失败',
    complete: '扫描完成',
    failed: '扫描失败',
    viewDetails: '查看详情',
    heatmap: '性能热力图',
    convergence: '收敛曲线',
    distribution: '性能分布',
  },
};

function c(key) {
  const lang = getLang() === 'zh' ? 'zh' : 'en';
  return COPY[lang][key] || COPY.en[key] || key;
}

export function render(container) {
  container.innerHTML = buildShell();
  loadRecentSweeps(container);
  bindEvents(container);
}

export function destroy() {
  _sweepChart = null;
  _currentSweepId = null;
}

function buildShell() {
  return `
    <div class="workbench-page sweep-page">
      <div class="page-header">
        <div>
          <div class="page-header__title">${c('title')}</div>
          <div class="page-header__sub">${c('subtitle')}</div>
        </div>
      </div>

      <div class="grid-sidebar">
        <div class="sidebar-panel">
          <div class="run-panel">
            <div class="run-panel__header">
              <div class="run-panel__title">${c('runTitle')}</div>
              <div class="run-panel__sub">${c('runSub')}</div>
            </div>
            <div class="run-panel__body">
              <div class="form-group">
                <label class="form-label">${c('strategy')}</label>
                <input class="form-input" id="sweep-strategy" value="ESG Multi-Factor">
              </div>
              <div class="form-group">
                <label class="form-label">${c('baseUniverse')}</label>
                <input class="form-input" id="sweep-universe" placeholder="AAPL, MSFT, GOOGL...">
              </div>

              <div class="form-group">
                <label class="form-label">${c('paramRanges')}</label>
                <div id="param-ranges-container">
                  <div class="param-range-row">
                    <input class="form-input form-input--sm" placeholder="${c('paramName')}" value="lookback_days">
                    <input class="form-input form-input--sm form-input--numeric" placeholder="${c('paramMin')}" value="20" type="number">
                    <input class="form-input form-input--sm form-input--numeric" placeholder="${c('paramMax')}" value="120" type="number">
                    <input class="form-input form-input--sm form-input--numeric" placeholder="${c('paramStep')}" value="20" type="number">
                    <button class="btn btn-sm btn-danger remove-param">×</button>
                  </div>
                  <div class="param-range-row">
                    <input class="form-input form-input--sm" placeholder="${c('paramName')}" value="rebalance_freq">
                    <input class="form-input form-input--sm form-input--numeric" placeholder="${c('paramMin')}" value="5" type="number">
                    <input class="form-input form-input--sm form-input--numeric" placeholder="${c('paramMax')}" value="20" type="number">
                    <input class="form-input form-input--sm form-input--numeric" placeholder="${c('paramStep')}" value="5" type="number">
                    <button class="btn btn-sm btn-danger remove-param">×</button>
                  </div>
                </div>
                <button class="btn btn-sm btn-secondary" id="add-param-btn" style="margin-top:8px">${c('addParam')}</button>
              </div>

              <div class="form-group">
                <label class="form-label">${c('optimizationTarget')}</label>
                <select class="form-select" id="sweep-target">
                  <option value="sharpe">${c('sharpe')}</option>
                  <option value="returns">${c('returns')}</option>
                  <option value="calmar">${c('calmar')}</option>
                  <option value="sortino">${c('sortino')}</option>
                </select>
              </div>

              <div class="form-group">
                <label class="form-label">${c('maxCombos')}</label>
                <input class="form-input form-input--numeric" id="sweep-max-combos" type="number" value="100" min="1" max="1000">
              </div>
            </div>
            <div class="run-panel__foot">
              <button class="btn btn-primary btn-lg" id="btn-run-sweep" style="flex:1">${c('runSweep')}</button>
            </div>
          </div>

          <div class="card">
            <div class="card-header"><span class="card-title">${c('recentSweeps')}</span></div>
            <div id="sweep-history" class="sweep-history">
              <div class="loading-overlay"><div class="spinner"></div></div>
            </div>
          </div>
        </div>

        <div class="main-panel">
          <div id="sweep-results-container" style="display:none">
            <div class="card">
              <div class="card-header">
                <span class="card-title">${c('bestCombo')}</span>
              </div>
              <div class="card-body" id="best-combo-display"></div>
            </div>

            <div class="card">
              <div class="card-header">
                <span class="card-title">${c('heatmap')}</span>
              </div>
              <div class="card-body">
                <div id="sweep-heatmap" style="height:400px"></div>
              </div>
            </div>

            <div class="card">
              <div class="card-header">
                <span class="card-title">${c('allCombos')}</span>
              </div>
              <div class="card-body" style="overflow-x:auto">
                <table class="data-table" id="combos-table">
                  <thead>
                    <tr>
                      <th>${c('rank')}</th>
                      <th>${c('params')}</th>
                      <th>${c('performance')}</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody id="combos-tbody"></tbody>
                </table>
              </div>
            </div>
          </div>

          <div id="sweep-placeholder" class="card">
            <div class="card-body" style="text-align:center;padding:60px 20px">
              <div style="font-size:48px;margin-bottom:16px">📊</div>
              <div style="font-size:14px;color:var(--text-secondary);margin-bottom:8px">${c('runTitle')}</div>
              <div style="font-size:12px;color:var(--text-tertiary)">${c('runSub')}</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  `;
}

function bindEvents(container) {
  const btnRun = container.querySelector('#btn-run-sweep');
  const btnAddParam = container.querySelector('#add-param-btn');

  if (btnRun) {
    btnRun.addEventListener('click', () => runSweep(container));
  }

  if (btnAddParam) {
    btnAddParam.addEventListener('click', () => addParamRow(container));
  }

  container.addEventListener('click', (e) => {
    if (e.target.classList.contains('remove-param')) {
      e.target.closest('.param-range-row').remove();
    }
    if (e.target.classList.contains('view-sweep-btn')) {
      const sweepId = e.target.dataset.sweepId;
      loadSweepResults(container, sweepId);
    }
  });
}

function addParamRow(container) {
  const paramContainer = container.querySelector('#param-ranges-container');
  const row = document.createElement('div');
  row.className = 'param-range-row';
  row.innerHTML = `
    <input class="form-input form-input--sm" placeholder="${c('paramName')}">
    <input class="form-input form-input--sm form-input--numeric" placeholder="${c('paramMin')}" type="number">
    <input class="form-input form-input--sm form-input--numeric" placeholder="${c('paramMax')}" type="number">
    <input class="form-input form-input--sm form-input--numeric" placeholder="${c('paramStep')}" type="number">
    <button class="btn btn-sm btn-danger remove-param">×</button>
  `;
  paramContainer.appendChild(row);
}

async function runSweep(container) {
  const btnRun = container.querySelector('#btn-run-sweep');
  const strategy = container.querySelector('#sweep-strategy').value;
  const universe = container.querySelector('#sweep-universe').value;
  const target = container.querySelector('#sweep-target').value;
  const maxCombos = parseInt(container.querySelector('#sweep-max-combos').value);

  const paramRows = container.querySelectorAll('.param-range-row');
  const paramRanges = {};

  paramRows.forEach(row => {
    const inputs = row.querySelectorAll('input');
    const name = inputs[0].value.trim();
    const min = parseFloat(inputs[1].value);
    const max = parseFloat(inputs[2].value);
    const step = parseFloat(inputs[3].value);

    if (name && !isNaN(min) && !isNaN(max) && !isNaN(step)) {
      paramRanges[name] = { min, max, step };
    }
  });

  if (Object.keys(paramRanges).length === 0) {
    toast.error('Please add at least one parameter range');
    return;
  }

  btnRun.disabled = true;
  btnRun.textContent = c('running');

  try {
    const payload = {
      strategy_name: strategy,
      universe: universe ? universe.split(',').map(s => s.trim()) : undefined,
      param_ranges: paramRanges,
      optimization_target: target,
      max_combinations: maxCombos,
    };

    const result = await api.backtests.sweep(payload);

    if (result.success && result.data) {
      _currentSweepId = result.data.run_id;
      toast.success(c('complete'));
      loadSweepResults(container, result.data.run_id);
      loadRecentSweeps(container);
    } else {
      toast.error(result.error?.message || c('failed'));
    }
  } catch (err) {
    toast.error(err.message || c('failed'));
  } finally {
    btnRun.disabled = false;
    btnRun.textContent = c('runSweep');
  }
}

async function loadRecentSweeps(container) {
  const historyEl = container.querySelector('#sweep-history');
  if (!historyEl) return;

  try {
    historyEl.innerHTML = '<div class="loading-overlay"><div class="spinner"></div></div>';

    const payload = await api.backtests.listSweeps(20);
    const sweeps = payload?.sweeps || [];

    if (sweeps.length === 0) {
      historyEl.innerHTML = `<div class="empty-state">${c('noSweeps')}</div>`;
      return;
    }

    historyEl.innerHTML = sweeps.map(sweep => `
      <div class="history-item">
        <div class="history-item__header">
          <span class="history-item__title">${sweep.strategy_name || sweep.strategy || sweep.run_id}</span>
          <span class="badge badge--${sweep.status === 'completed' || sweep.status === 'ready' ? 'success' : 'warning'}">${sweep.status || sweep.protection_status || payload?.status || 'ready'}</span>
        </div>
        <div class="history-item__meta">
          <span>Sharpe: ${Number(sweep.best_sharpe ?? sweep.best_run?.metrics?.sharpe ?? sweep.best_run?.sharpe ?? 0).toFixed(2)}</span>
          <span>${new Date(sweep.timestamp || sweep.generated_at || Date.now()).toLocaleString()}</span>
        </div>
        <button class="btn btn-sm btn-secondary view-sweep-btn" data-sweep-id="${sweep.run_id}">${c('viewDetails')}</button>
      </div>
    `).join('');
  } catch (err) {
    historyEl.innerHTML = `<div class="empty-state">${c('loadFailed')}</div>`;
  }
}

async function loadSweepResults(container, sweepId) {
  const resultsContainer = container.querySelector('#sweep-results-container');
  const placeholder = container.querySelector('#sweep-placeholder');

  try {
    const result = await api.backtests.getSweep(sweepId);

    if (!result.success || !result.data) {
      toast.error('Failed to load sweep results');
      return;
    }

    const data = result.data;

    placeholder.style.display = 'none';
    resultsContainer.style.display = 'block';

    renderBestCombo(container, data.best_combination);
    renderCombosTable(container, data.all_combinations);
    renderHeatmap(container, data.all_combinations);
  } catch (err) {
    toast.error(err.message || 'Failed to load sweep results');
  }
}

function renderBestCombo(container, bestCombo) {
  const bestComboEl = container.querySelector('#best-combo-display');
  if (!bestCombo || !bestComboEl) return;

  bestComboEl.innerHTML = `
    <div class="metrics-row-4">
      ${Object.entries(bestCombo.params || {}).map(([key, value]) => `
        <div class="metric-card">
          <div class="metric-card__label">${key}</div>
          <div class="metric-card__value">${value}</div>
        </div>
      `).join('')}
    </div>
    <div class="metrics-row-4" style="margin-top:16px">
      <div class="metric-card">
        <div class="metric-card__label">Sharpe Ratio</div>
        <div class="metric-card__value">${bestCombo.metrics?.sharpe?.toFixed(2) || 'N/A'}</div>
      </div>
      <div class="metric-card">
        <div class="metric-card__label">Total Return</div>
        <div class="metric-card__value">${bestCombo.metrics?.total_return ? (bestCombo.metrics.total_return * 100).toFixed(1) + '%' : 'N/A'}</div>
      </div>
      <div class="metric-card">
        <div class="metric-card__label">Max Drawdown</div>
        <div class="metric-card__value">${bestCombo.metrics?.max_drawdown ? (bestCombo.metrics.max_drawdown * 100).toFixed(1) + '%' : 'N/A'}</div>
      </div>
      <div class="metric-card">
        <div class="metric-card__label">Win Rate</div>
        <div class="metric-card__value">${bestCombo.metrics?.win_rate ? (bestCombo.metrics.win_rate * 100).toFixed(1) + '%' : 'N/A'}</div>
      </div>
    </div>
  `;
}

function renderCombosTable(container, combos) {
  const tbody = container.querySelector('#combos-tbody');
  if (!combos || !tbody) return;

  tbody.innerHTML = combos.slice(0, 20).map((combo, idx) => `
    <tr>
      <td>${idx + 1}</td>
      <td>${Object.entries(combo.params || {}).map(([k, v]) => `${k}=${v}`).join(', ')}</td>
      <td>
        <div style="display:flex;gap:12px;font-size:11px">
          <span>Sharpe: ${combo.metrics?.sharpe?.toFixed(2) || 'N/A'}</span>
          <span>Return: ${combo.metrics?.total_return ? (combo.metrics.total_return * 100).toFixed(1) + '%' : 'N/A'}</span>
        </div>
      </td>
      <td><button class="btn btn-sm btn-secondary">View</button></td>
    </tr>
  `).join('');
}

function renderHeatmap(container, combos) {
  const heatmapEl = container.querySelector('#sweep-heatmap');
  if (!combos || !heatmapEl || typeof echarts === 'undefined') return;

  if (_sweepChart) {
    _sweepChart.dispose();
  }

  _sweepChart = echarts.init(heatmapEl);

  const data = combos.map((combo, idx) => [
    idx,
    combo.metrics?.sharpe || 0,
    combo.metrics?.total_return || 0,
  ]);

  const option = {
    tooltip: {
      position: 'top',
      formatter: (params) => {
        const combo = combos[params.value[0]];
        return `Combo ${params.value[0] + 1}<br/>Sharpe: ${params.value[1].toFixed(2)}<br/>Return: ${(params.value[2] * 100).toFixed(1)}%`;
      }
    },
    grid: {
      left: 60,
      right: 40,
      top: 40,
      bottom: 60,
    },
    xAxis: {
      type: 'value',
      name: 'Combination Index',
      nameLocation: 'middle',
      nameGap: 30,
    },
    yAxis: {
      type: 'value',
      name: 'Sharpe Ratio',
      nameLocation: 'middle',
      nameGap: 40,
    },
    visualMap: {
      min: 0,
      max: Math.max(...data.map(d => d[2])),
      dimension: 2,
      orient: 'vertical',
      right: 10,
      top: 'center',
      text: ['HIGH', 'LOW'],
      calculable: true,
      inRange: {
        color: ['#313695', '#4575b4', '#74add1', '#abd9e9', '#e0f3f8', '#ffffbf', '#fee090', '#fdae61', '#f46d43', '#d73027', '#a50026']
      }
    },
    series: [{
      type: 'scatter',
      symbolSize: 8,
      data: data,
    }]
  };

  _sweepChart.setOption(option);
}
