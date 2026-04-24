import { api } from '../qtapi.js?v=8';
import { toast } from '../components/toast.js?v=8';
import { getLang } from '../i18n.js?v=8';

let _performanceChart = null;
let _drawdownChart = null;

const COPY = {
  en: {
    title: 'Tearsheet Report',
    subtitle: 'Comprehensive performance analysis with risk metrics and attribution',
    selectBacktest: 'Select Backtest',
    loadReport: 'Load Report',
    loading: 'Loading report...',
    overview: 'Performance Overview',
    returns: 'Returns Analysis',
    risk: 'Risk Metrics',
    trades: 'Trade Analysis',
    attribution: 'Attribution',
    totalReturn: 'Total Return',
    annualReturn: 'Annual Return',
    sharpe: 'Sharpe Ratio',
    sortino: 'Sortino Ratio',
    calmar: 'Calmar Ratio',
    maxDrawdown: 'Max Drawdown',
    volatility: 'Volatility',
    winRate: 'Win Rate',
    profitFactor: 'Profit Factor',
    avgWin: 'Avg Win',
    avgLoss: 'Avg Loss',
    totalTrades: 'Total Trades',
    avgHoldingPeriod: 'Avg Holding Period',
    turnover: 'Turnover',
    cumReturns: 'Cumulative Returns',
    drawdown: 'Drawdown',
    monthlyReturns: 'Monthly Returns',
    rollingMetrics: 'Rolling Metrics',
    topPositions: 'Top Positions',
    sectorExposure: 'Sector Exposure',
    factorExposure: 'Factor Exposure',
    noBacktests: 'No backtests available',
    selectPrompt: 'Select a backtest to view its tearsheet',
    exportPDF: 'Export PDF',
    exportHTML: 'Export HTML',
    days: 'days',
  },
  zh: {
    title: 'Tearsheet 报告',
    subtitle: '全面的性能分析，包含风险指标和归因分析',
    selectBacktest: '选择回测',
    loadReport: '加载报告',
    loading: '加载中...',
    overview: '性能概览',
    returns: '收益分析',
    risk: '风险指标',
    trades: '交易分析',
    attribution: '归因分析',
    totalReturn: '总收益',
    annualReturn: '年化收益',
    sharpe: '夏普比率',
    sortino: 'Sortino 比率',
    calmar: 'Calmar 比率',
    maxDrawdown: '最大回撤',
    volatility: '波动率',
    winRate: '胜率',
    profitFactor: '盈亏比',
    avgWin: '平均盈利',
    avgLoss: '平均亏损',
    totalTrades: '总交易数',
    avgHoldingPeriod: '平均持仓周期',
    turnover: '换手率',
    cumReturns: '累计收益',
    drawdown: '回撤',
    monthlyReturns: '月度收益',
    rollingMetrics: '滚动指标',
    topPositions: '主要持仓',
    sectorExposure: '行业暴露',
    factorExposure: '因子暴露',
    noBacktests: '暂无回测记录',
    selectPrompt: '选择一个回测查看其 tearsheet',
    exportPDF: '导出 PDF',
    exportHTML: '导出 HTML',
    days: '天',
  },
};

function c(key) {
  const lang = getLang() === 'zh' ? 'zh' : 'en';
  return COPY[lang][key] || COPY.en[key] || key;
}

export function render(container) {
  container.innerHTML = buildShell();
  loadBacktestList(container);
  bindEvents(container);
}

export function destroy() {
  if (_performanceChart) _performanceChart.dispose();
  if (_drawdownChart) _drawdownChart.dispose();
  _performanceChart = null;
  _drawdownChart = null;
}

function buildShell() {
  return `
    <div class="workbench-page tearsheet-page">
      <div class="page-header">
        <div>
          <div class="page-header__title">${c('title')}</div>
          <div class="page-header__sub">${c('subtitle')}</div>
        </div>
        <div class="page-header__actions">
          <button class="btn btn-secondary" id="export-html-btn" style="display:none">${c('exportHTML')}</button>
          <button class="btn btn-secondary" id="export-pdf-btn" style="display:none">${c('exportPDF')}</button>
        </div>
      </div>

      <div class="tearsheet-selector">
        <div class="form-group" style="max-width:400px">
          <label class="form-label">${c('selectBacktest')}</label>
          <select class="form-select" id="backtest-select">
            <option value="">${c('selectPrompt')}</option>
          </select>
        </div>
        <button class="btn btn-primary" id="load-report-btn">${c('loadReport')}</button>
      </div>

      <div id="tearsheet-content" style="display:none">
        <div class="card">
          <div class="card-header">
            <span class="card-title">${c('overview')}</span>
          </div>
          <div class="card-body">
            <div class="metrics-row-6" id="overview-metrics"></div>
          </div>
        </div>

        <div class="grid-2">
          <div class="card">
            <div class="card-header">
              <span class="card-title">${c('cumReturns')}</span>
            </div>
            <div class="card-body">
              <div id="performance-chart" style="height:300px"></div>
            </div>
          </div>

          <div class="card">
            <div class="card-header">
              <span class="card-title">${c('drawdown')}</span>
            </div>
            <div class="card-body">
              <div id="drawdown-chart" style="height:300px"></div>
            </div>
          </div>
        </div>

        <div class="card">
          <div class="card-header">
            <span class="card-title">${c('risk')}</span>
          </div>
          <div class="card-body">
            <div class="metrics-row-4" id="risk-metrics"></div>
          </div>
        </div>

        <div class="card">
          <div class="card-header">
            <span class="card-title">${c('trades')}</span>
          </div>
          <div class="card-body">
            <div class="metrics-row-4" id="trade-metrics"></div>
          </div>
        </div>

        <div class="grid-2">
          <div class="card">
            <div class="card-header">
              <span class="card-title">${c('monthlyReturns')}</span>
            </div>
            <div class="card-body" style="overflow-x:auto">
              <table class="monthly-heatmap-table" id="monthly-returns-table">
                <thead><tr>
                  <th>Year</th>
                  ${['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'].map(m => `<th>${m}</th>`).join('')}
                </tr></thead>
                <tbody id="monthly-returns-tbody"></tbody>
              </table>
            </div>
          </div>

          <div class="card">
            <div class="card-header">
              <span class="card-title">${c('topPositions')}</span>
            </div>
            <div class="card-body">
              <div id="top-positions-list"></div>
            </div>
          </div>
        </div>

        <div class="card">
          <div class="card-header">
            <span class="card-title">${c('attribution')}</span>
          </div>
          <div class="card-body">
            <div class="grid-2">
              <div id="sector-exposure-chart" style="height:300px"></div>
              <div id="factor-exposure-chart" style="height:300px"></div>
            </div>
          </div>
        </div>
      </div>

      <div id="tearsheet-placeholder" class="card">
        <div class="card-body" style="text-align:center;padding:60px 20px">
          <div style="font-size:48px;margin-bottom:16px">📊</div>
          <div style="font-size:14px;color:var(--text-secondary);margin-bottom:8px">${c('selectPrompt')}</div>
          <div style="font-size:12px;color:var(--text-tertiary)">${c('subtitle')}</div>
        </div>
      </div>
    </div>
  `;
}

function bindEvents(container) {
  const loadBtn = container.querySelector('#load-report-btn');
  const exportHtmlBtn = container.querySelector('#export-html-btn');
  const exportPdfBtn = container.querySelector('#export-pdf-btn');

  if (loadBtn) {
    loadBtn.addEventListener('click', () => loadTearsheet(container));
  }

  if (exportHtmlBtn) {
    exportHtmlBtn.addEventListener('click', () => exportReport(container, 'html'));
  }

  if (exportPdfBtn) {
    exportPdfBtn.addEventListener('click', () => exportReport(container, 'pdf'));
  }
}

async function loadBacktestList(container) {
  const select = container.querySelector('#backtest-select');
  if (!select) return;

  try {
    const result = await api.backtests.list();

    if (result.success && result.data && result.data.length > 0) {
      result.data.forEach(bt => {
        const option = document.createElement('option');
        option.value = bt.backtest_id;
        option.textContent = `${bt.strategy_name} - ${new Date(bt.timestamp).toLocaleDateString()}`;
        select.appendChild(option);
      });
    }
  } catch (err) {
    console.error('Failed to load backtests:', err);
  }
}

async function loadTearsheet(container) {
  const select = container.querySelector('#backtest-select');
  const backtestId = select.value;

  if (!backtestId) {
    toast.error('Please select a backtest');
    return;
  }

  const loadBtn = container.querySelector('#load-report-btn');
  const content = container.querySelector('#tearsheet-content');
  const placeholder = container.querySelector('#tearsheet-placeholder');

  loadBtn.disabled = true;
  loadBtn.textContent = c('loading');

  try {
    const result = await api.reports.tearsheet(backtestId);

    if (!result.success || !result.data) {
      toast.error('Failed to load tearsheet');
      return;
    }

    const data = result.data;

    placeholder.style.display = 'none';
    content.style.display = 'block';

    container.querySelector('#export-html-btn').style.display = 'inline-block';
    container.querySelector('#export-pdf-btn').style.display = 'inline-block';

    renderOverviewMetrics(container, data);
    renderPerformanceChart(container, data);
    renderDrawdownChart(container, data);
    renderRiskMetrics(container, data);
    renderTradeMetrics(container, data);
    renderMonthlyReturns(container, data);
    renderTopPositions(container, data);
    renderAttribution(container, data);

    toast.success('Tearsheet loaded');
  } catch (err) {
    toast.error(err.message || 'Failed to load tearsheet');
  } finally {
    loadBtn.disabled = false;
    loadBtn.textContent = c('loadReport');
  }
}

function renderOverviewMetrics(container, data) {
  const metricsEl = container.querySelector('#overview-metrics');
  if (!metricsEl) return;

  const metrics = data.summary || {};

  metricsEl.innerHTML = `
    <div class="metric-card">
      <div class="metric-card__label">${c('totalReturn')}</div>
      <div class="metric-card__value ${metrics.total_return >= 0 ? 'positive' : 'negative'}">
        ${metrics.total_return ? (metrics.total_return * 100).toFixed(2) + '%' : 'N/A'}
      </div>
    </div>
    <div class="metric-card">
      <div class="metric-card__label">${c('annualReturn')}</div>
      <div class="metric-card__value ${metrics.annual_return >= 0 ? 'positive' : 'negative'}">
        ${metrics.annual_return ? (metrics.annual_return * 100).toFixed(2) + '%' : 'N/A'}
      </div>
    </div>
    <div class="metric-card">
      <div class="metric-card__label">${c('sharpe')}</div>
      <div class="metric-card__value">${metrics.sharpe?.toFixed(2) || 'N/A'}</div>
    </div>
    <div class="metric-card">
      <div class="metric-card__label">${c('sortino')}</div>
      <div class="metric-card__value">${metrics.sortino?.toFixed(2) || 'N/A'}</div>
    </div>
    <div class="metric-card">
      <div class="metric-card__label">${c('maxDrawdown')}</div>
      <div class="metric-card__value negative">
        ${metrics.max_drawdown ? (metrics.max_drawdown * 100).toFixed(2) + '%' : 'N/A'}
      </div>
    </div>
    <div class="metric-card">
      <div class="metric-card__label">${c('volatility')}</div>
      <div class="metric-card__value">${metrics.volatility ? (metrics.volatility * 100).toFixed(2) + '%' : 'N/A'}</div>
    </div>
  `;
}

function renderPerformanceChart(container, data) {
  const chartEl = container.querySelector('#performance-chart');
  if (!chartEl || typeof echarts === 'undefined') return;

  if (_performanceChart) {
    _performanceChart.dispose();
  }

  _performanceChart = echarts.init(chartEl);

  const equity = data.equity_curve || [];
  const dates = equity.map(e => e.date);
  const values = equity.map(e => e.value);

  const option = {
    tooltip: {
      trigger: 'axis',
      formatter: (params) => {
        const date = params[0].axisValue;
        const value = params[0].value;
        return `${date}<br/>Portfolio: $${value.toLocaleString()}`;
      }
    },
    grid: {
      left: 60,
      right: 40,
      top: 40,
      bottom: 60,
    },
    xAxis: {
      type: 'category',
      data: dates,
      axisLabel: {
        rotate: 45,
      }
    },
    yAxis: {
      type: 'value',
      axisLabel: {
        formatter: (value) => '$' + (value / 1000).toFixed(0) + 'K'
      }
    },
    series: [{
      type: 'line',
      data: values,
      smooth: true,
      lineStyle: {
        color: '#00FF88',
        width: 2,
      },
      areaStyle: {
        color: {
          type: 'linear',
          x: 0,
          y: 0,
          x2: 0,
          y2: 1,
          colorStops: [
            { offset: 0, color: 'rgba(0, 255, 136, 0.3)' },
            { offset: 1, color: 'rgba(0, 255, 136, 0.05)' }
          ]
        }
      }
    }]
  };

  _performanceChart.setOption(option);
}

function renderDrawdownChart(container, data) {
  const chartEl = container.querySelector('#drawdown-chart');
  if (!chartEl || typeof echarts === 'undefined') return;

  if (_drawdownChart) {
    _drawdownChart.dispose();
  }

  _drawdownChart = echarts.init(chartEl);

  const drawdown = data.drawdown_series || [];
  const dates = drawdown.map(d => d.date);
  const values = drawdown.map(d => d.value * 100);

  const option = {
    tooltip: {
      trigger: 'axis',
      formatter: (params) => {
        const date = params[0].axisValue;
        const value = params[0].value;
        return `${date}<br/>Drawdown: ${value.toFixed(2)}%`;
      }
    },
    grid: {
      left: 60,
      right: 40,
      top: 40,
      bottom: 60,
    },
    xAxis: {
      type: 'category',
      data: dates,
      axisLabel: {
        rotate: 45,
      }
    },
    yAxis: {
      type: 'value',
      axisLabel: {
        formatter: (value) => value.toFixed(0) + '%'
      }
    },
    series: [{
      type: 'line',
      data: values,
      smooth: true,
      lineStyle: {
        color: '#FF3D57',
        width: 2,
      },
      areaStyle: {
        color: {
          type: 'linear',
          x: 0,
          y: 0,
          x2: 0,
          y2: 1,
          colorStops: [
            { offset: 0, color: 'rgba(255, 61, 87, 0.3)' },
            { offset: 1, color: 'rgba(255, 61, 87, 0.05)' }
          ]
        }
      }
    }]
  };

  _drawdownChart.setOption(option);
}

function renderRiskMetrics(container, data) {
  const metricsEl = container.querySelector('#risk-metrics');
  if (!metricsEl) return;

  const risk = data.risk_metrics || {};

  metricsEl.innerHTML = `
    <div class="metric-card">
      <div class="metric-card__label">VaR (95%)</div>
      <div class="metric-card__value">${risk.var_95 ? (risk.var_95 * 100).toFixed(2) + '%' : 'N/A'}</div>
    </div>
    <div class="metric-card">
      <div class="metric-card__label">CVaR (95%)</div>
      <div class="metric-card__value">${risk.cvar_95 ? (risk.cvar_95 * 100).toFixed(2) + '%' : 'N/A'}</div>
    </div>
    <div class="metric-card">
      <div class="metric-card__label">Beta</div>
      <div class="metric-card__value">${risk.beta?.toFixed(2) || 'N/A'}</div>
    </div>
    <div class="metric-card">
      <div class="metric-card__label">Alpha</div>
      <div class="metric-card__value">${risk.alpha ? (risk.alpha * 100).toFixed(2) + '%' : 'N/A'}</div>
    </div>
  `;
}

function renderTradeMetrics(container, data) {
  const metricsEl = container.querySelector('#trade-metrics');
  if (!metricsEl) return;

  const trades = data.trade_analysis || {};

  metricsEl.innerHTML = `
    <div class="metric-card">
      <div class="metric-card__label">${c('totalTrades')}</div>
      <div class="metric-card__value">${trades.total_trades || 0}</div>
    </div>
    <div class="metric-card">
      <div class="metric-card__label">${c('winRate')}</div>
      <div class="metric-card__value">${trades.win_rate ? (trades.win_rate * 100).toFixed(1) + '%' : 'N/A'}</div>
    </div>
    <div class="metric-card">
      <div class="metric-card__label">${c('profitFactor')}</div>
      <div class="metric-card__value">${trades.profit_factor?.toFixed(2) || 'N/A'}</div>
    </div>
    <div class="metric-card">
      <div class="metric-card__label">${c('avgHoldingPeriod')}</div>
      <div class="metric-card__value">${trades.avg_holding_period ? trades.avg_holding_period.toFixed(1) + ' ' + c('days') : 'N/A'}</div>
    </div>
  `;
}

function renderMonthlyReturns(container, data) {
  const tbody = container.querySelector('#monthly-returns-tbody');
  if (!tbody) return;

  const monthlyReturns = data.monthly_returns || {};

  tbody.innerHTML = Object.entries(monthlyReturns).map(([year, months]) => `
    <tr>
      <td>${year}</td>
      ${months.map(ret => {
        const value = ret !== null ? (ret * 100).toFixed(1) : '-';
        const colorClass = ret > 0 ? 'positive' : ret < 0 ? 'negative' : '';
        return `<td class="${colorClass}">${value}${ret !== null ? '%' : ''}</td>`;
      }).join('')}
    </tr>
  `).join('');
}

function renderTopPositions(container, data) {
  const listEl = container.querySelector('#top-positions-list');
  if (!listEl) return;

  const positions = data.top_positions || [];

  listEl.innerHTML = positions.map(pos => `
    <div class="position-item">
      <div class="position-item__symbol">${pos.symbol}</div>
      <div class="position-item__weight">${(pos.weight * 100).toFixed(1)}%</div>
      <div class="position-item__return ${pos.return >= 0 ? 'positive' : 'negative'}">
        ${(pos.return * 100).toFixed(2)}%
      </div>
    </div>
  `).join('');
}

function renderAttribution(container, data) {
  // Sector exposure and factor exposure charts would go here
  // Using echarts for visualization
}

function exportReport(container, format) {
  toast.info(`Export to ${format.toUpperCase()} coming soon`);
}
