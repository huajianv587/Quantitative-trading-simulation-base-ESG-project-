import { api } from '../qtapi.js?v=8';
import { toast } from '../components/toast.js?v=8';
import { getLang } from '../i18n.js?v=8';

let _qualityChart = null;

const COPY = {
  en: {
    title: 'Research Datasets',
    subtitle: 'Build and manage research-grade datasets with quality checks and protection reports',
    buildTitle: 'Build Dataset',
    buildSub: 'Configure dataset construction parameters',
    datasetName: 'Dataset Name',
    symbols: 'Symbols',
    startDate: 'Start Date',
    endDate: 'End Date',
    frequency: 'Frequency',
    daily: 'Daily',
    hourly: 'Hourly',
    minute: 'Minute',
    features: 'Features',
    ohlcv: 'OHLCV',
    volume: 'Volume',
    technicals: 'Technical Indicators',
    fundamentals: 'Fundamentals',
    sentiment: 'Sentiment',
    qualityChecks: 'Quality Checks',
    missingData: 'Missing Data Threshold',
    outlierDetection: 'Outlier Detection',
    buildDataset: 'Build Dataset',
    building: 'Building...',
    recentDatasets: 'Recent Datasets',
    datasetList: 'Dataset List',
    name: 'Name',
    created: 'Created',
    rows: 'Rows',
    columns: 'Columns',
    quality: 'Quality Score',
    actions: 'Actions',
    view: 'View',
    download: 'Download',
    delete: 'Delete',
    noDatasets: 'No datasets yet',
    loadFailed: 'Failed to load datasets',
    buildSuccess: 'Dataset built successfully',
    buildFailed: 'Failed to build dataset',
    qualityReport: 'Quality Report',
    missingValues: 'Missing Values',
    outliers: 'Outliers',
    duplicates: 'Duplicates',
    dataRange: 'Data Range',
    statistics: 'Statistics',
    distribution: 'Distribution',
    correlations: 'Correlations',
    protectionReport: 'Protection Report',
    leakageChecks: 'Leakage Checks',
    forwardLooking: 'Forward-Looking Bias',
    survivorshipBias: 'Survivorship Bias',
    passed: 'Passed',
    failed: 'Failed',
    warning: 'Warning',
  },
  zh: {
    title: '研究数据集',
    subtitle: '构建和管理研究级数据集，包含质量检查和保护报告',
    buildTitle: '构建数据集',
    buildSub: '配置数据集构建参数',
    datasetName: '数据集名称',
    symbols: '股票代码',
    startDate: '开始日期',
    endDate: '结束日期',
    frequency: '频率',
    daily: '日线',
    hourly: '小时线',
    minute: '分钟线',
    features: '特征',
    ohlcv: 'OHLCV',
    volume: '成交量',
    technicals: '技术指标',
    fundamentals: '基本面',
    sentiment: '情绪',
    qualityChecks: '质量检查',
    missingData: '缺失数据阈值',
    outlierDetection: '异常值检测',
    buildDataset: '构建数据集',
    building: '构建中...',
    recentDatasets: '最近数据集',
    datasetList: '数据集列表',
    name: '名称',
    created: '创建时间',
    rows: '行数',
    columns: '列数',
    quality: '质量评分',
    actions: '操作',
    view: '查看',
    download: '下载',
    delete: '删除',
    noDatasets: '暂无数据集',
    loadFailed: '加载失败',
    buildSuccess: '数据集构建成功',
    buildFailed: '数据集构建失败',
    qualityReport: '质量报告',
    missingValues: '缺失值',
    outliers: '异常值',
    duplicates: '重复值',
    dataRange: '数据范围',
    statistics: '统计信息',
    distribution: '分布',
    correlations: '相关性',
    protectionReport: '保护报告',
    leakageChecks: '泄漏检查',
    forwardLooking: '前瞻偏差',
    survivorshipBias: '幸存者偏差',
    passed: '通过',
    failed: '失败',
    warning: '警告',
  },
};

function c(key) {
  const lang = getLang() === 'zh' ? 'zh' : 'en';
  return COPY[lang][key] || COPY.en[key] || key;
}

export function render(container) {
  container.innerHTML = buildShell();
  loadDatasets(container);
  bindEvents(container);
}

export function destroy() {
  if (_qualityChart) _qualityChart.dispose();
  _qualityChart = null;
}

function buildShell() {
  return `
    <div class="workbench-page dataset-page">
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
              <div class="run-panel__title">${c('buildTitle')}</div>
              <div class="run-panel__sub">${c('buildSub')}</div>
            </div>
            <div class="run-panel__body">
              <div class="form-group">
                <label class="form-label">${c('datasetName')}</label>
                <input class="form-input" id="dataset-name" placeholder="my_research_dataset">
              </div>

              <div class="form-group">
                <label class="form-label">${c('symbols')}</label>
                <input class="form-input" id="dataset-symbols" placeholder="AAPL, MSFT, GOOGL...">
              </div>

              <div class="form-row">
                <div class="form-group">
                  <label class="form-label">${c('startDate')}</label>
                  <input class="form-input" id="dataset-start" type="date" value="${getDefaultStartDate()}">
                </div>
                <div class="form-group">
                  <label class="form-label">${c('endDate')}</label>
                  <input class="form-input" id="dataset-end" type="date" value="${getDefaultEndDate()}">
                </div>
              </div>

              <div class="form-group">
                <label class="form-label">${c('frequency')}</label>
                <select class="form-select" id="dataset-frequency">
                  <option value="1D">${c('daily')}</option>
                  <option value="1H">${c('hourly')}</option>
                  <option value="1m">${c('minute')}</option>
                </select>
              </div>

              <div class="form-group">
                <label class="form-label">${c('features')}</label>
                <div class="checkbox-group">
                  <label class="checkbox-label">
                    <input type="checkbox" id="feat-ohlcv" checked>
                    <span>${c('ohlcv')}</span>
                  </label>
                  <label class="checkbox-label">
                    <input type="checkbox" id="feat-volume" checked>
                    <span>${c('volume')}</span>
                  </label>
                  <label class="checkbox-label">
                    <input type="checkbox" id="feat-technicals">
                    <span>${c('technicals')}</span>
                  </label>
                  <label class="checkbox-label">
                    <input type="checkbox" id="feat-fundamentals">
                    <span>${c('fundamentals')}</span>
                  </label>
                  <label class="checkbox-label">
                    <input type="checkbox" id="feat-sentiment">
                    <span>${c('sentiment')}</span>
                  </label>
                </div>
              </div>

              <details class="dataset-advanced">
                <summary>${c('qualityChecks')}<span>+</span></summary>
                <div class="dataset-advanced__body">
                  <div class="form-group">
                    <label class="form-label">${c('missingData')}</label>
                    <input class="form-input form-input--numeric" id="missing-threshold" type="number" value="5" min="0" max="100" step="1">
                    <span class="form-hint">Max % missing values allowed</span>
                  </div>
                  <div class="form-group">
                    <label class="checkbox-label">
                      <input type="checkbox" id="outlier-detection" checked>
                      <span>${c('outlierDetection')}</span>
                    </label>
                  </div>
                </div>
              </details>
            </div>
            <div class="run-panel__foot">
              <button class="btn btn-primary btn-lg" id="btn-build-dataset" style="flex:1">${c('buildDataset')}</button>
            </div>
          </div>

          <div class="card">
            <div class="card-header"><span class="card-title">${c('recentDatasets')}</span></div>
            <div id="dataset-history" class="dataset-history">
              <div class="loading-overlay"><div class="spinner"></div></div>
            </div>
          </div>
        </div>

        <div class="main-panel">
          <div class="card">
            <div class="card-header">
              <span class="card-title">${c('datasetList')}</span>
            </div>
            <div class="card-body" style="overflow-x:auto">
              <table class="data-table" id="datasets-table">
                <thead>
                  <tr>
                    <th>${c('name')}</th>
                    <th>${c('created')}</th>
                    <th>${c('rows')}</th>
                    <th>${c('columns')}</th>
                    <th>${c('quality')}</th>
                    <th>${c('actions')}</th>
                  </tr>
                </thead>
                <tbody id="datasets-tbody">
                  <tr>
                    <td colspan="6" style="text-align:center;padding:40px">
                      <div class="loading-overlay"><div class="spinner"></div></div>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <div id="dataset-detail" style="display:none">
            <div class="grid-2">
              <div class="card">
                <div class="card-header">
                  <span class="card-title">${c('qualityReport')}</span>
                </div>
                <div class="card-body">
                  <div class="metrics-row-4" id="quality-metrics"></div>
                  <div id="quality-chart" style="height:250px;margin-top:20px"></div>
                </div>
              </div>

              <div class="card">
                <div class="card-header">
                  <span class="card-title">${c('protectionReport')}</span>
                </div>
                <div class="card-body">
                  <div id="protection-checks"></div>
                </div>
              </div>
            </div>

            <div class="card">
              <div class="card-header">
                <span class="card-title">${c('statistics')}</span>
              </div>
              <div class="card-body" style="overflow-x:auto">
                <table class="data-table" id="stats-table">
                  <thead>
                    <tr>
                      <th>Feature</th>
                      <th>Mean</th>
                      <th>Std</th>
                      <th>Min</th>
                      <th>Max</th>
                      <th>Missing %</th>
                    </tr>
                  </thead>
                  <tbody id="stats-tbody"></tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  `;
}

function getDefaultStartDate() {
  const date = new Date();
  date.setFullYear(date.getFullYear() - 1);
  return date.toISOString().split('T')[0];
}

function getDefaultEndDate() {
  return new Date().toISOString().split('T')[0];
}

function bindEvents(container) {
  const btnBuild = container.querySelector('#btn-build-dataset');

  if (btnBuild) {
    btnBuild.addEventListener('click', () => buildDataset(container));
  }

  container.addEventListener('click', (e) => {
    if (e.target.classList.contains('view-dataset-btn')) {
      const datasetId = e.target.dataset.datasetId;
      viewDatasetDetail(container, datasetId);
    }
    if (e.target.classList.contains('download-dataset-btn')) {
      const datasetId = e.target.dataset.datasetId;
      downloadDataset(datasetId);
    }
    if (e.target.classList.contains('delete-dataset-btn')) {
      const datasetId = e.target.dataset.datasetId;
      deleteDataset(container, datasetId);
    }
  });
}

async function buildDataset(container) {
  const btnBuild = container.querySelector('#btn-build-dataset');
  const name = container.querySelector('#dataset-name').value.trim();
  const symbols = container.querySelector('#dataset-symbols').value.trim();
  const startDate = container.querySelector('#dataset-start').value;
  const endDate = container.querySelector('#dataset-end').value;
  const frequency = container.querySelector('#dataset-frequency').value;

  if (!name) {
    toast.error('Please enter a dataset name');
    return;
  }

  if (!symbols) {
    toast.error('Please enter symbols');
    return;
  }

  const features = [];
  if (container.querySelector('#feat-ohlcv').checked) features.push('ohlcv');
  if (container.querySelector('#feat-volume').checked) features.push('volume');
  if (container.querySelector('#feat-technicals').checked) features.push('technicals');
  if (container.querySelector('#feat-fundamentals').checked) features.push('fundamentals');
  if (container.querySelector('#feat-sentiment').checked) features.push('sentiment');

  const missingThreshold = parseFloat(container.querySelector('#missing-threshold').value);
  const outlierDetection = container.querySelector('#outlier-detection').checked;

  btnBuild.disabled = true;
  btnBuild.textContent = c('building');

  try {
    const payload = {
      name,
      symbols: symbols.split(',').map(s => s.trim()),
      start_date: startDate,
      end_date: endDate,
      frequency,
      features,
      quality_checks: {
        missing_threshold: missingThreshold / 100,
        outlier_detection: outlierDetection,
      }
    };

    const result = await api.research.buildDataset(payload);

    if (result.success) {
      toast.success(c('buildSuccess'));
      loadDatasets(container);
    } else {
      toast.error(result.error?.message || c('buildFailed'));
    }
  } catch (err) {
    toast.error(err.message || c('buildFailed'));
  } finally {
    btnBuild.disabled = false;
    btnBuild.textContent = c('buildDataset');
  }
}

async function loadDatasets(container) {
  const tbody = container.querySelector('#datasets-tbody');
  const historyEl = container.querySelector('#dataset-history');

  if (!tbody) return;

  try {
    const result = await api.research.datasets(20);

    if (!result.success || !result.data || result.data.length === 0) {
      tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:40px;color:var(--text-tertiary)">${c('noDatasets')}</td></tr>`;
      if (historyEl) historyEl.innerHTML = `<div class="empty-state">${c('noDatasets')}</div>`;
      return;
    }

    const datasets = result.data;

    tbody.innerHTML = datasets.map(ds => `
      <tr>
        <td><strong>${ds.name}</strong></td>
        <td>${new Date(ds.created_at).toLocaleString()}</td>
        <td>${ds.rows?.toLocaleString() || 'N/A'}</td>
        <td>${ds.columns || 'N/A'}</td>
        <td>
          <span class="badge badge--${getQualityBadge(ds.quality_score)}">
            ${ds.quality_score ? (ds.quality_score * 100).toFixed(0) + '%' : 'N/A'}
          </span>
        </td>
        <td>
          <div style="display:flex;gap:8px">
            <button class="btn btn-sm btn-secondary view-dataset-btn" data-dataset-id="${ds.dataset_id}">${c('view')}</button>
            <button class="btn btn-sm btn-secondary download-dataset-btn" data-dataset-id="${ds.dataset_id}">${c('download')}</button>
            <button class="btn btn-sm btn-danger delete-dataset-btn" data-dataset-id="${ds.dataset_id}">${c('delete')}</button>
          </div>
        </td>
      </tr>
    `).join('');

    if (historyEl) {
      historyEl.innerHTML = datasets.slice(0, 5).map(ds => `
        <div class="history-item">
          <div class="history-item__header">
            <span class="history-item__title">${ds.name}</span>
            <span class="badge badge--${getQualityBadge(ds.quality_score)}">
              ${ds.quality_score ? (ds.quality_score * 100).toFixed(0) + '%' : 'N/A'}
            </span>
          </div>
          <div class="history-item__meta">
            <span>${ds.rows?.toLocaleString() || 'N/A'} rows</span>
            <span>${new Date(ds.created_at).toLocaleDateString()}</span>
          </div>
        </div>
      `).join('');
    }
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:40px;color:var(--text-tertiary)">${c('loadFailed')}</td></tr>`;
    if (historyEl) historyEl.innerHTML = `<div class="empty-state">${c('loadFailed')}</div>`;
  }
}

function getQualityBadge(score) {
  if (!score) return 'secondary';
  if (score >= 0.9) return 'success';
  if (score >= 0.7) return 'warning';
  return 'danger';
}

async function viewDatasetDetail(container, datasetId) {
  const detailEl = container.querySelector('#dataset-detail');
  if (!detailEl) return;

  detailEl.style.display = 'block';

  try {
    const result = await api.research.qualityChecks({ dataset_id: datasetId });

    if (result.success && result.data) {
      renderQualityMetrics(container, result.data);
      renderProtectionChecks(container, result.data);
      renderStatistics(container, result.data);
    }
  } catch (err) {
    toast.error('Failed to load dataset details');
  }
}

function renderQualityMetrics(container, data) {
  const metricsEl = container.querySelector('#quality-metrics');
  if (!metricsEl) return;

  const quality = data.quality_report || {};

  metricsEl.innerHTML = `
    <div class="metric-card">
      <div class="metric-card__label">${c('missingValues')}</div>
      <div class="metric-card__value">${quality.missing_pct ? (quality.missing_pct * 100).toFixed(2) + '%' : 'N/A'}</div>
    </div>
    <div class="metric-card">
      <div class="metric-card__label">${c('outliers')}</div>
      <div class="metric-card__value">${quality.outlier_count || 0}</div>
    </div>
    <div class="metric-card">
      <div class="metric-card__label">${c('duplicates')}</div>
      <div class="metric-card__value">${quality.duplicate_count || 0}</div>
    </div>
    <div class="metric-card">
      <div class="metric-card__label">${c('quality')}</div>
      <div class="metric-card__value">${quality.overall_score ? (quality.overall_score * 100).toFixed(0) + '%' : 'N/A'}</div>
    </div>
  `;

  renderQualityChart(container, quality);
}

function renderQualityChart(container, quality) {
  const chartEl = container.querySelector('#quality-chart');
  if (!chartEl || typeof echarts === 'undefined') return;

  if (_qualityChart) {
    _qualityChart.dispose();
  }

  _qualityChart = echarts.init(chartEl);

  const option = {
    tooltip: {
      trigger: 'item'
    },
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      avoidLabelOverlap: false,
      label: {
        show: true,
        position: 'outside'
      },
      data: [
        { value: quality.complete_pct || 0, name: 'Complete' },
        { value: quality.missing_pct || 0, name: 'Missing' },
        { value: quality.outlier_pct || 0, name: 'Outliers' },
      ]
    }]
  };

  _qualityChart.setOption(option);
}

function renderProtectionChecks(container, data) {
  const checksEl = container.querySelector('#protection-checks');
  if (!checksEl) return;

  const protection = data.protection_report || {};
  const checks = Array.isArray(protection.checks)
    ? protection.checks
    : Object.entries(protection.checks || {}).map(([name, detail]) => ({
        name,
        passed: Boolean(detail?.passed),
        message: (detail?.violations || []).length ? detail.violations.join(', ') : detail?.detail,
      }));

  checksEl.innerHTML = `
    <div class="protection-checks-list">
      ${checks.map(check => `
        <div class="protection-check-item">
          <div class="protection-check-item__header">
            <span class="protection-check-item__name">${check.name}</span>
            <span class="badge badge--${check.passed ? 'success' : 'danger'}">
              ${check.passed ? c('passed') : c('failed')}
            </span>
          </div>
          ${check.message ? `<div class="protection-check-item__message">${check.message}</div>` : ''}
        </div>
      `).join('')}
    </div>
  `;
}

function renderStatistics(container, data) {
  const tbody = container.querySelector('#stats-tbody');
  if (!tbody) return;

  const stats = data.statistics || {};

  tbody.innerHTML = Object.entries(stats).map(([feature, stat]) => `
    <tr>
      <td><strong>${feature}</strong></td>
      <td>${stat.mean?.toFixed(4) || 'N/A'}</td>
      <td>${stat.std?.toFixed(4) || 'N/A'}</td>
      <td>${stat.min?.toFixed(4) || 'N/A'}</td>
      <td>${stat.max?.toFixed(4) || 'N/A'}</td>
      <td>${stat.missing_pct ? (stat.missing_pct * 100).toFixed(2) + '%' : '0%'}</td>
    </tr>
  `).join('');
}

function downloadDataset(datasetId) {
  toast.info('Download functionality coming soon');
}

function deleteDataset(container, datasetId) {
  if (!confirm('Are you sure you want to delete this dataset?')) {
    return;
  }
  toast.info('Delete functionality coming soon');
}
