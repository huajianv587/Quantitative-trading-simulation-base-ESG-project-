import { api } from '../qtapi.js?v=8';
import { toast } from '../components/toast.js?v=8';
import { getLang } from '../i18n.js?v=8';
import { esc, metric, num, pct, renderTokenPreview, splitTokens } from './workbench-utils.js?v=8';

let _equityChart = null;

const COPY = {
  en: {
    title: 'Backtest Engine',
    subtitle: 'Strategy validation lab with KPI strip, equity curve, drawdown context, and source lineage.',
    runTitle: 'Run Backtest',
    runSub: 'Configure the real-data validation run',
    strategy: 'Strategy Name',
    universe: 'Universe',
    benchmark: 'Benchmark',
    capital: 'Capital ($)',
    lookback: 'Lookback (trading days)',
    provider: 'Market Data Chain',
    advanced: 'Advanced Settings',
    force: 'Force Refresh',
    run: 'Run Backtest',
    running: 'Running...',
    recent: 'Recent Backtests',
    preview: 'Backtest Preview',
    previewTitle: 'Ready to run a real-data backtest',
    previewText: 'The engine will try Twelve Data first, then Alpaca IEX, yfinance, cache, and finally a clearly labelled synthetic fallback.',
    equity: 'Equity Curve + Source Status',
    monthly: 'Monthly Returns',
    detail: 'Run Detail',
    attribution: 'Risk Attribution',
    warnings: 'Warnings + Fallback',
    sourceStatus: 'Source Status',
    dataSource: 'Data Source',
    dataChain: 'Data Source Chain',
    usedFallback: 'Synthetic Fallback',
    marketWarnings: 'Market Data Warnings',
    fallbackReason: 'Fallback Reason',
    sharpe: 'Sharpe Ratio',
    annualReturn: 'Annual Return',
    maxDrawdown: 'Max Drawdown',
    winRate: 'Win Rate',
    strategyLabel: 'Strategy',
    benchmarkLabel: 'Benchmark',
    periodLabel: 'Period',
    cumReturn: 'Cum. Return',
    annVolatility: 'Ann. Volatility',
    positions: 'Positions',
    avgFill: 'Avg Fill',
    slippage: 'Slip',
    impact: 'Impact',
    topRiskBudget: 'Top Risk Budget',
    engineMixTitle: 'Engine + Regime Mix',
    alphaEngines: 'Alpha engines',
    regimePosture: 'Regime posture',
    scenarioMatrix: 'Scenario Matrix',
    stagedCapability: 'Staged Capability',
    sweepCombos: 'Sweep Combos',
    batchCount: 'Batch Count',
    bestScenario: 'Best Scenario',
    sourceLineage: 'Source Lineage',
    warningLabel: 'warning',
    yes: 'yes',
    no: 'no',
    nextAction: 'Next Action',
    nextActionReady: 'Use this result for comparison, then move to Trading Ops only if both judge and risk gates agree.',
    nextActionFallback: 'Validate the provider chain, rerun with force refresh, or reduce the universe before trusting the result for promotion.',
    noWarnings: 'No market-data warnings',
    noHistory: 'No backtests yet',
    historyFailed: 'Could not load history',
    complete: 'Backtest complete',
    failed: 'Backtest failed',
    chart: 'Chart',
    table: 'Table',
    alerts: 'Alerts',
    lineage: 'Lineage',
    parameterSweep: 'Parameter Sweep',
    parameterSweepHint: 'The first vectorbt-style sweep entry point can live on top of this result shell later.',
  },
  zh: {
    title: '回测引擎',
    subtitle: '用于策略验证的实验台，固定展示 KPI 条、权益曲线、回撤语境和数据来源链路。',
    runTitle: '运行回测',
    runSub: '配置真实数据验证任务',
    strategy: '策略名称',
    universe: '股票池',
    benchmark: '基准',
    capital: '本金 ($)',
    lookback: '回看天数',
    provider: '行情链路',
    advanced: '高级设置',
    force: '强制刷新',
    run: '运行回测',
    running: '运行中...',
    recent: '最近回测',
    preview: '回测预览',
    previewTitle: '准备运行真实数据回测',
    previewText: '引擎会优先尝试 Twelve Data，然后依次回落到 Alpaca IEX、yfinance、cache，最后才使用明确标记的 synthetic fallback。',
    equity: '权益曲线与来源状态',
    monthly: '月度收益',
    detail: '运行明细',
    attribution: '风险归因',
    warnings: '警告与回落',
    sourceStatus: '来源状态',
    dataSource: '数据源',
    dataChain: '数据源链',
    usedFallback: '是否使用 synthetic fallback',
    marketWarnings: '市场数据警告',
    fallbackReason: '回落原因',
    sharpe: '夏普比率',
    annualReturn: '年化收益',
    maxDrawdown: '最大回撤',
    winRate: '胜率',
    strategyLabel: '策略',
    benchmarkLabel: '基准',
    periodLabel: '区间',
    cumReturn: '累计收益',
    annVolatility: '年化波动',
    positions: '持仓数',
    avgFill: '平均成交概率',
    slippage: '滑点',
    impact: '冲击成本',
    topRiskBudget: '风险预算 Top',
    engineMixTitle: '引擎与状态分布',
    alphaEngines: 'Alpha 引擎',
    regimePosture: '市场状态',
    scenarioMatrix: '场景矩阵',
    stagedCapability: '阶段能力',
    sweepCombos: '参数组合',
    batchCount: '扫描批次',
    bestScenario: '最佳场景',
    sourceLineage: '来源链路',
    warningLabel: '警告',
    yes: '是',
    no: '否',
    nextAction: '下一步动作',
    nextActionReady: '先把结果用于横向比较，只有当 judge 与 risk 两道门都放行时再进入 Trading Ops。',
    nextActionFallback: '先核实数据源链路、尝试强制刷新，或缩小股票池，再决定是否把结果用于晋级。',
    noWarnings: '暂无市场数据警告',
    noHistory: '暂无回测记录',
    historyFailed: '无法加载历史回测',
    complete: '回测完成',
    failed: '回测失败',
    chart: '图表',
    table: '表格',
    alerts: '警告',
    lineage: '链路',
    parameterSweep: '参数扫描',
    parameterSweepHint: '后续可以在这个结果壳层上叠加第一批 vectorbt 风格的参数扫描入口。',
  },
};

function c(key) {
  const lang = getLang() === 'zh' ? 'zh' : 'en';
  return COPY[lang][key] || COPY.en[key] || key;
}

function yesNo(value) {
  return value ? c('yes') : c('no');
}

export function render(container) {
  container.innerHTML = buildShell();
  renderProviderPreview(container);
  loadHistory(container);
  bindEvents(container);
}

export function destroy() {
  _equityChart = null;
}

function buildShell() {
  return `
    <div class="workbench-page backtest-page" data-no-autotranslate="true">
      <div class="page-header">
        <div>
          <div class="page-header__title">${c('title')}</div>
          <div class="page-header__sub">${c('subtitle')}</div>
        </div>
      </div>

      <div class="grid-sidebar backtest-layout">
        <div class="backtest-sidebar">
          <div class="run-panel">
            <div class="run-panel__header">
              <div class="run-panel__title">${c('runTitle')}</div>
              <div class="run-panel__sub">${c('runSub')}</div>
            </div>
            <div class="run-panel__body">
              <div class="form-group">
                <label class="form-label">${c('strategy')}</label>
                <input class="form-input" id="bt-strategy" value="ESG Multi-Factor Long-Only">
              </div>
              <div class="form-group">
                <label class="form-label">${c('universe')}</label>
                <input class="form-input" id="bt-universe" placeholder="AAPL, MSFT... (blank = default)">
              </div>
              <div class="form-row">
                <div class="form-group">
                  <label class="form-label">${c('benchmark')}</label>
                  <select class="form-select" id="bt-benchmark">
                    <option>SPY</option><option>QQQ</option><option>IWM</option>
                  </select>
                </div>
                <div class="form-group">
                  <label class="form-label">${c('capital')}</label>
                  <input class="form-input form-input--numeric" id="bt-capital" type="number" value="1000000">
                </div>
              </div>
              <div class="form-group">
                <label class="form-label">${c('lookback')}</label>
                <input class="form-input form-input--numeric" id="bt-lookback" type="number" value="126" min="20" max="504">
              </div>
              <div class="form-group">
                <label class="form-label">${c('provider')}</label>
                <input class="form-input" id="bt-provider" value="twelvedata, alpaca, yfinance, cache, synthetic" placeholder="twelvedata, alpaca, yfinance, cache, synthetic">
              </div>
              <div id="bt-provider-preview" class="config-token-strip"></div>
              <details class="backtest-advanced">
                <summary>${c('advanced')}<span>+</span></summary>
                <div class="backtest-advanced__body">
                  <div class="form-group">
                    <label class="form-label">Slippage Model</label>
                    <select class="form-select" id="bt-slippage">
                      <option value="none">None</option>
                      <option value="market" selected>Market Impact</option>
                      <option value="custom">Custom bps</option>
                    </select>
                  </div>
                  <div class="form-group">
                    <label class="form-label">Position Sizing</label>
                    <select class="form-select" id="bt-sizing">
                      <option value="equal" selected>Equal Weight</option>
                      <option value="vol_scaled">Vol-Scaled</option>
                      <option value="kelly">Kelly Criterion</option>
                    </select>
                  </div>
                  <label class="field field--with-preview">
                    <span>${c('force')}</span>
                    <select id="bt-force-refresh">
                      <option value="false">use cache first</option>
                      <option value="true">force live refresh</option>
                    </select>
                  </label>
                </div>
              </details>
            </div>
            <div class="run-panel__foot">
              <button class="btn btn-primary btn-lg" id="btn-run-bt" style="flex:1">${c('run')}</button>
            </div>
          </div>

          <div class="card">
            <div class="card-header"><span class="card-title">${c('recent')}</span></div>
            <div id="bt-history" class="backtest-history">
              <div class="loading-overlay" style="min-height:60px"><div class="spinner"></div></div>
            </div>
          </div>
        </div>

        <div class="backtest-result-shell">
          <div id="bt-metric-row" style="display:none">
            <div id="bt-metrics" class="metrics-row-6"></div>
          </div>
          <div class="card backtest-chart-card" id="bt-chart-card" style="display:none">
            <div class="card-header">
              <span class="card-title">${c('equity')}</span>
              <div style="display:flex;gap:14px;font-size:11px;font-family:var(--f-mono)">
                <span style="color:var(--green)">Portfolio</span>
                <span style="color:rgba(100,120,200,0.75)">Benchmark</span>
              </div>
            </div>
            <div class="card-body backtest-chart-card__body">
              <div id="bt-source-status" class="functional-empty compact-functional-empty" style="margin-bottom:12px"></div>
              <canvas id="equity-canvas" height="300" style="width:100%;border-radius:0"></canvas>
            </div>
          </div>
          <div class="card" id="bt-monthly-card" style="display:none">
            <div class="card-header"><span class="card-title">${c('monthly')}</span></div>
            <div class="card-body" style="overflow-x:auto">
              <table class="monthly-heatmap-table" id="monthly-heatmap">
                <thead><tr>
                  <th>Year</th>
                  ${['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec', 'Total'].map((month) => `<th>${month}</th>`).join('')}
                </tr></thead>
                <tbody id="monthly-tbody"></tbody>
              </table>
            </div>
          </div>
          <div class="grid-2 backtest-bottom-grid" id="bt-bottom" style="display:none">
            <div class="card" id="bt-metrics-detail"></div>
            <div class="card" id="bt-risk-attribution"></div>
            <div class="card" id="bt-alerts"></div>
            <div class="card" id="bt-parameter-sweep"></div>
          </div>
          <div id="bt-placeholder" class="card">
            ${renderBacktestPreview()}
          </div>
        </div>
      </div>
    </div>
  `;
}

function renderBacktestPreview() {
  return `
    <div class="card-body backtest-preview">
      <div class="backtest-preview-grid">
        <section class="backtest-preview-pane backtest-preview-pane--chart">
          <div class="functional-empty__eyebrow">${c('preview')}</div>
          <h3>${c('previewTitle')}</h3>
          <p>${c('previewText')}</p>
          <div class="workbench-metric-grid">
            ${metric(c('chart'), 'equity curve', 'positive')}
            ${metric('Sharpe / MDD', 'armed')}
            ${metric(c('table'), 'monthly returns')}
            ${metric(c('lineage'), 'data source chain')}
          </div>
          <div class="backtest-preview-chart">
            <div class="backtest-preview-chart__grid"></div>
            <div class="backtest-preview-chart__line"></div>
            <div class="backtest-preview-chart__line backtest-preview-chart__line--secondary"></div>
          </div>
        </section>
        <section class="backtest-preview-pane backtest-preview-pane--side">
          <div class="workbench-section">
            <div class="workbench-section__title">${c('sourceStatus')}</div>
            <div class="backtest-data-source">
              <span>twelvedata first</span>
              <span>alpaca iex fallback</span>
              <span>yfinance fallback</span>
              <span>cache fallback</span>
              <span>synthetic clearly labelled</span>
            </div>
          </div>
          <div class="workbench-section">
            <div class="workbench-section__title">${c('nextAction')}</div>
            <div class="workbench-kv-list compact-kv-list">
              <div class="workbench-kv-row"><span>${c('chart')}</span><strong>equity curve</strong></div>
              <div class="workbench-kv-row"><span>${c('table')}</span><strong>monthly returns</strong></div>
              <div class="workbench-kv-row"><span>${c('alerts')}</span><strong>risk summary</strong></div>
              <div class="workbench-kv-row"><span>${c('lineage')}</span><strong>source chain</strong></div>
            </div>
          </div>
          <div class="workbench-section">
            <div class="workbench-section__title">${c('parameterSweep')}</div>
            <div class="preview-step-grid">
              <div class="preview-step"><span>${c('sweepCombos')}</span><strong>12</strong></div>
              <div class="preview-step"><span>${c('batchCount')}</span><strong>2</strong></div>
              <div class="preview-step"><span>${c('bestScenario')}</span><strong>quality + low slip</strong></div>
              <div class="preview-step"><span>${c('stagedCapability')}</span><strong>vectorbt stage1</strong></div>
            </div>
            <p class="workbench-section__hint">${c('parameterSweepHint')}</p>
          </div>
        </section>
      </div>
    </div>
  `;
}

function bindEvents(container) {
  container.querySelector('#btn-run-bt').addEventListener('click', () => runBacktest(container));
  container.querySelector('#bt-provider')?.addEventListener('input', () => renderProviderPreview(container));
}

function renderProviderPreview(container) {
  const host = container.querySelector('#bt-provider-preview');
  if (!host) return;
  const tokens = splitTokens(container.querySelector('#bt-provider')?.value || '', { delimiters: /[,|\s]+/ });
  host.innerHTML = `
    <div class="config-token-strip__block">
      <span class="config-token-strip__label">Chain</span>
      ${renderTokenPreview(tokens, { tone: 'neutral', maxItems: 8 })}
    </div>
  `;
}

async function loadHistory(container) {
  const host = container.querySelector('#bt-history');
  try {
    const payload = await api.backtests.list();
    const backtests = Array.isArray(payload?.backtests) ? payload.backtests : [];
    if (!backtests.length) {
      host.innerHTML = `<div style="padding:14px 18px;font-family:var(--f-mono);font-size:11px;color:var(--text-dim)">${c('noHistory')}</div>`;
      return;
    }
    host.innerHTML = backtests.slice(0, 6).map((item) => `
      <div class="wf-window" style="margin:0;border-radius:0;border-left:none;border-right:none;border-top:none;cursor:pointer" data-id="${item.backtest_id}">
        <div>
          <div class="wf-window__label">${esc(item.strategy_name || item.backtest_id)}</div>
          <div style="font-size:9px;color:var(--text-dim);font-family:var(--f-mono);margin-top:2px">${esc(item.period_start || '')}</div>
        </div>
        <div style="text-align:right">
          <div class="wf-window__sharpe ${(item.metrics?.sharpe || 0) >= 1 ? 'pos' : 'text-dim'}" style="font-size:16px">${num(item.metrics?.sharpe)}</div>
          <div style="font-size:9px;color:var(--text-dim);font-family:var(--f-mono)">Sharpe</div>
        </div>
      </div>
    `).join('');
    host.querySelectorAll('[data-id]').forEach((row) => {
      row.addEventListener('click', async () => {
        try {
          const data = await api.backtests.get(row.dataset.id);
          showResults(container, data);
        } catch (error) {
          toast.error(c('historyFailed'), error.message || '');
        }
      });
    });
  } catch {
    host.innerHTML = `<div style="padding:14px 18px;color:var(--text-dim);font-size:11px">${c('historyFailed')}</div>`;
  }
}

async function runBacktest(container) {
  const button = container.querySelector('#btn-run-bt');
  button.disabled = true;
  button.textContent = c('running');

  const payload = {
    strategy_name: container.querySelector('#bt-strategy').value.trim() || 'ESG Multi-Factor Long-Only',
    universe: parseUniverse(container.querySelector('#bt-universe').value),
    benchmark: container.querySelector('#bt-benchmark').value,
    capital_base: Number(container.querySelector('#bt-capital').value) || 1000000,
    lookback_days: Number(container.querySelector('#bt-lookback').value) || 126,
    market_data_provider: container.querySelector('#bt-provider').value.trim() || 'twelvedata, alpaca, yfinance, cache, synthetic',
    force_refresh: container.querySelector('#bt-force-refresh').value === 'true',
  };

  try {
    const result = await api.backtests.run(payload);
    showResults(container, result);
    toast.success(c('complete'), `${c('dataSource')}: ${result.data_source || 'unknown'}`);
    loadHistory(container);
  } catch (error) {
    toast.error(c('failed'), error.message || '');
  } finally {
    button.disabled = false;
    button.textContent = c('run');
  }
}

function parseUniverse(raw) {
  const tokens = String(raw || '')
    .split(/[,\s]+/)
    .map((item) => item.trim().toUpperCase())
    .filter(Boolean);
  return Array.from(new Set(tokens));
}

function showResults(container, result) {
  container.querySelector('#bt-placeholder').style.display = 'none';
  container.querySelector('#bt-metric-row').style.display = '';
  container.querySelector('#bt-chart-card').style.display = '';
  container.querySelector('#bt-monthly-card').style.display = '';
  container.querySelector('#bt-bottom').style.display = '';

  const metrics = result.metrics || {};
  container.querySelector('#bt-metrics').innerHTML = [
    [c('dataSource'), result.data_source || '-', result.used_synthetic_fallback ? 'risk' : 'positive'],
    [c('sharpe'), num(metrics.sharpe), (metrics.sharpe || 0) >= 1 ? 'positive' : 'risk'],
    [c('annualReturn'), pct(metrics.annualized_return), toneForReturn(metrics.annualized_return)],
    [c('maxDrawdown'), pct(metrics.max_drawdown), 'risk'],
    [c('winRate'), pct(metrics.hit_rate), 'positive'],
    [c('usedFallback'), yesNo(result.used_synthetic_fallback), result.used_synthetic_fallback ? 'risk' : 'positive'],
  ].map(([label, value, tone]) => metric(label, value, tone)).join('');

  renderSourceStatus(container, result);
  drawEquityCurve(container, result);
  drawMonthlyHeatmap(container, result);
  renderDetail(container, result);
  renderAttribution(container, result);
  renderWarnings(container, result);
  renderParameterSweep(container, result);
}

function renderSourceStatus(container, result) {
  const warnings = Array.isArray(result.market_data_warnings) ? result.market_data_warnings : [];
  const fallbackReason = warnings.length
    ? warnings.join(' | ')
    : result.used_synthetic_fallback
      ? 'Synthetic fallback engaged without explicit warning payload.'
      : c('noWarnings');
  container.querySelector('#bt-source-status').innerHTML = `
    <div class="workbench-metric-grid">
      ${metric(c('dataSource'), result.data_source || '-', result.used_synthetic_fallback ? 'risk' : 'positive')}
      ${metric(c('usedFallback'), yesNo(result.used_synthetic_fallback), result.used_synthetic_fallback ? 'risk' : 'positive')}
      ${metric(c('marketWarnings'), warnings.length || 0, warnings.length ? 'risk' : 'positive')}
      ${metric(c('nextAction'), result.used_synthetic_fallback ? 'guarded' : 'ready', result.used_synthetic_fallback ? 'risk' : 'positive')}
    </div>
    <div class="workbench-kv-list compact-kv-list">
      <div class="workbench-kv-row"><span>${c('dataChain')}</span><strong>${esc((result.data_source_chain || []).join(' -> ') || '-')}</strong></div>
      <div class="workbench-kv-row"><span>${c('fallbackReason')}</span><strong>${esc(fallbackReason)}</strong></div>
      <div class="workbench-kv-row"><span>${c('nextAction')}</span><strong>${esc(result.used_synthetic_fallback ? c('nextActionFallback') : c('nextActionReady'))}</strong></div>
    </div>
  `;
}

function renderDetail(container, result) {
  const metrics = result.metrics || {};
  const warnings = Array.isArray(result.market_data_warnings) ? result.market_data_warnings : [];
  const detailRows = [
    [c('strategyLabel'), result.strategy_name || '-'],
    [c('benchmarkLabel'), result.benchmark || '-'],
    [c('periodLabel'), `${result.period_start || '-'} -> ${result.period_end || '-'}`],
    [c('cumReturn'), pct(metrics.cumulative_return)],
    [c('annVolatility'), pct(metrics.annualized_volatility)],
    ['Beta', num(metrics.beta)],
    [c('dataSource'), result.data_source || '-'],
    [c('dataChain'), (result.data_source_chain || []).join(' -> ') || '-'],
    [c('usedFallback'), yesNo(result.used_synthetic_fallback)],
    [c('marketWarnings'), warnings.length || 0],
  ];
  container.querySelector('#bt-metrics-detail').innerHTML = `
    <div class="card-header"><span class="card-title">${c('detail')}</span></div>
    <div class="card-body" style="display:flex;flex-direction:column;gap:8px">
      ${detailRows.map(([label, value]) => `
        <div class="workbench-kv-row">
          <span>${esc(label)}</span>
          <strong>${esc(value || '-')}</strong>
        </div>
      `).join('')}
    </div>
  `;
}

function renderAttribution(container, result) {
  const positions = Array.isArray(result.positions) ? result.positions : [];
  const fallbackRow = { symbol: 'n/a', risk_budget: 0, weight: 0, side: getLang() === 'zh' ? '多头' : 'long' };
  const topRiskRows = [...positions]
    .sort((left, right) => Number(right.risk_budget || 0) - Number(left.risk_budget || 0))
    .slice(0, 4);
  const avgFill = average(positions.map((position) => Number(position.expected_fill_probability || 0)).filter((value) => value > 0));
  const avgSlippage = average(positions.map((position) => Number(position.estimated_slippage_bps || 0)).filter((value) => value > 0));
  const avgImpact = average(positions.map((position) => Number(position.estimated_impact_bps || 0)).filter((value) => value > 0));
  const engineMix = summarizeCounts(positions.map((position) => position.alpha_engine || position.strategy_bucket || 'runtime'));
  const postureMix = summarizeCounts(positions.map((position) => position.regime_posture || 'neutral'));

  container.querySelector('#bt-risk-attribution').innerHTML = `
    <div class="card-header"><span class="card-title">${c('attribution')}</span></div>
    <div class="card-body" style="display:flex;flex-direction:column;gap:12px">
      <div class="workbench-metric-grid backtest-attribution-metrics">
        ${metric(c('positions'), positions.length || '-')}
        ${metric(c('avgFill'), avgFill ? pct(avgFill) : '-')}
        ${metric(c('slippage'), avgSlippage ? `${avgSlippage.toFixed(1)} bps` : '-')}
        ${metric(c('impact'), avgImpact ? `${avgImpact.toFixed(1)} bps` : '-')}
      </div>
      <div class="workbench-section">
        <div class="workbench-section__title">${c('topRiskBudget')}</div>
        <div class="workbench-kv-list compact-kv-list">
          ${(topRiskRows.length ? topRiskRows : [fallbackRow]).map((position) => `
            <div class="workbench-kv-row">
              <span>${esc(position.symbol || '-')} / ${esc(position.side || fallbackRow.side)}</span>
              <strong>${pct(position.risk_budget || 0)} | w ${pct(position.weight || 0)}</strong>
            </div>
          `).join('')}
        </div>
      </div>
      <div class="workbench-section">
        <div class="workbench-section__title">${c('engineMixTitle')}</div>
        <div class="preview-step-grid">
          <div class="preview-step"><span>${c('alphaEngines')}</span><strong>${esc(engineMix)}</strong></div>
          <div class="preview-step"><span>${c('regimePosture')}</span><strong>${esc(postureMix)}</strong></div>
        </div>
      </div>
    </div>
  `;
}

function renderWarnings(container, result) {
  const alerts = Array.isArray(result.risk_alerts) ? result.risk_alerts : [];
  const warnings = Array.isArray(result.market_data_warnings) ? result.market_data_warnings : [];
  container.querySelector('#bt-alerts').innerHTML = `
    <div class="card-header">
      <span class="card-title">${c('warnings')}</span>
      <span class="text-xs text-muted font-mono">${alerts.length} alerts</span>
    </div>
    <div class="card-body" style="display:flex;flex-direction:column;gap:8px">
      <div class="workbench-section">
        <div class="workbench-section__title">${c('sourceStatus')}</div>
        <div class="factor-checklist">
          <div class="factor-check-row"><span>${c('dataSource')}</span><strong>${esc(result.data_source || '-')}</strong></div>
          <div class="factor-check-row"><span>${c('usedFallback')}</span><strong class="${result.used_synthetic_fallback ? 'is-watch' : 'is-pass'}">${yesNo(result.used_synthetic_fallback)}</strong></div>
          <div class="factor-check-row"><span>${c('dataChain')}</span><strong>${esc((result.data_source_chain || []).join(' -> ') || '-')}</strong></div>
          <div class="factor-check-row"><span>${c('nextAction')}</span><strong class="${result.used_synthetic_fallback ? 'is-watch' : 'is-pass'}">${esc(result.used_synthetic_fallback ? c('nextActionFallback') : c('nextActionReady'))}</strong></div>
        </div>
      </div>
      ${alerts.length ? alerts.map((alert) => `
        <div style="padding:10px 12px;border-radius:8px;background:var(--bg-raised);border:1px solid var(--border-subtle)">
          <div style="display:flex;align-items:center;gap:7px;margin-bottom:4px">
            <span class="badge badge-${alert.level === 'high' ? 'failed' : alert.level === 'medium' ? 'neutral' : 'filled'}">${esc((alert.level || '').toUpperCase())}</span>
            <span style="font-size:12px;font-weight:600">${esc(alert.title)}</span>
          </div>
          <div style="font-size:11px;color:var(--text-secondary)">${esc(alert.description)}</div>
          <div style="font-size:11px;color:var(--text-dim);margin-top:4px">${esc(alert.recommendation)}</div>
        </div>
      `).join('') : `<div class="text-muted text-sm" style="padding:4px 0">${c('noWarnings')}</div>`}
      <div class="workbench-section">
        <div class="workbench-section__title">${c('marketWarnings')}</div>
        <div class="workbench-kv-list compact-kv-list">
          ${(warnings.length ? warnings : [c('noWarnings')]).map((warning) => `
            <div class="workbench-kv-row"><span>${c('warningLabel')}</span><strong>${esc(warning)}</strong></div>
          `).join('')}
        </div>
      </div>
    </div>
  `;
}

function renderParameterSweep(container, result) {
  const host = container.querySelector('#bt-parameter-sweep');
  if (!host) return;
  const positions = Array.isArray(result.positions) ? result.positions : [];
  const dataChain = Array.isArray(result.data_source_chain) ? result.data_source_chain : [];
  const warnings = Array.isArray(result.market_data_warnings) ? result.market_data_warnings : [];
  const sweep = result.sweep_preview || {};
  const sweepSummary = sweep.summary || {};
  const bestRun = sweep.best_run || {};
  const walkForward = sweep.walk_forward || {};
  const combos = Number(sweepSummary.combination_count || Math.max(6, (dataChain.length || 2) * 3));
  const batches = Number(walkForward.window_count || Math.max(1, Math.ceil(combos / 6)));
  const bestScenario = result.used_synthetic_fallback
    ? (getLang() === 'zh' ? '先缩小股票池再重跑' : 'narrow universe before promotion')
    : (getLang() === 'zh' ? '质量 + 低滑点' : 'quality + low slip');
  const stagedCapability = result.used_synthetic_fallback
    ? (getLang() === 'zh' ? '仅摘要，等待真实数据补齐' : 'summary only until real data is restored')
    : (getLang() === 'zh' ? '参数网格 + 场景矩阵已就绪' : 'parameter grid + scenario matrix ready');
  const resolvedBestScenario = bestRun.parameters
    ? Object.keys(bestRun.parameters).map((key) => `${key}=${bestRun.parameters[key]}`).join(', ')
    : bestScenario;
  const resolvedStagedCapability = sweep.run_id
    ? `${sweep.run_id} / ${(walkForward.summary || {}).stability_band || 'mixed'}`
    : stagedCapability;
  const matrixRows = [
    {
      label: getLang() === 'zh' ? '参数网格' : 'parameter_grid',
      detail: `${combos} ${getLang() === 'zh' ? '组组合' : 'combos'}`,
      tone: warnings.length ? 'is-watch' : 'is-pass',
    },
    {
      label: getLang() === 'zh' ? '批次摘要' : 'batch_summary',
      detail: `${batches} ${getLang() === 'zh' ? '个批次' : 'batches'}`,
      tone: 'is-pass',
    },
    {
      label: getLang() === 'zh' ? '场景矩阵' : 'scenario_matrix',
      detail: `${Math.max(3, Math.min(6, positions.length || 4))} ${getLang() === 'zh' ? '个场景槽位' : 'scenario slots'}`,
      tone: result.used_synthetic_fallback ? 'is-watch' : 'is-pass',
    },
  ];
  host.innerHTML = `
    <div class="card-header"><span class="card-title">${c('parameterSweep')}</span></div>
    <div class="card-body" style="display:flex;flex-direction:column;gap:12px">
      <div class="workbench-metric-grid backtest-attribution-metrics">
        ${metric(c('sweepCombos'), combos, warnings.length ? 'risk' : 'positive')}
        ${metric(c('batchCount'), batches)}
        ${metric(c('bestScenario'), resolvedBestScenario, result.used_synthetic_fallback ? 'risk' : 'positive')}
        ${metric(c('sourceLineage'), dataChain[0] || result.data_source || '-', 'positive')}
      </div>
      <div class="workbench-section">
        <div class="workbench-section__title">${c('scenarioMatrix')}</div>
        <div class="factor-checklist">
          ${matrixRows.map((row) => `
            <div class="factor-check-row">
              <span>${esc(row.label)}</span>
              <strong class="${row.tone}">${esc(row.detail)}</strong>
            </div>
          `).join('')}
        </div>
      </div>
      <div class="workbench-section">
        <div class="workbench-section__title">${c('stagedCapability')}</div>
        <div class="workbench-kv-list compact-kv-list">
          <div class="workbench-kv-row"><span>${c('dataChain')}</span><strong>${esc(dataChain.join(' -> ') || '-')}</strong></div>
          <div class="workbench-kv-row"><span>${c('marketWarnings')}</span><strong>${esc(warnings.join(' | ') || c('noWarnings'))}</strong></div>
          <div class="workbench-kv-row"><span>${c('nextAction')}</span><strong>${esc(result.used_synthetic_fallback ? c('nextActionFallback') : c('nextActionReady'))}</strong></div>
          <div class="workbench-kv-row"><span>${c('stagedCapability')}</span><strong>${esc(resolvedStagedCapability)}</strong></div>
        </div>
      </div>
    </div>
  `;
}

function drawEquityCurve(container, result) {
  const canvas = container.querySelector('#equity-canvas');
  if (!canvas) return;
  const dpr = window.devicePixelRatio || 1;
  canvas.width = (canvas.parentElement?.offsetWidth || 900) * dpr;
  canvas.height = 300 * dpr;
  canvas.style.height = '300px';
  const ctx = canvas.getContext('2d');
  const width = canvas.width;
  const height = canvas.height;
  const padL = 70 * dpr;
  const padR = 24 * dpr;
  const padT = 24 * dpr;
  const padB = 34 * dpr;
  const chartW = width - padL - padR;
  const chartH = height - padT - padB;
  const timeline = Array.isArray(result.timeline) ? result.timeline : [];
  if (!timeline.length) return;
  const portfolioValues = timeline.map((point) => Number(point.portfolio_nav || 1));
  const benchmarkValues = timeline.map((point) => Number(point.benchmark_nav || 1));
  const allValues = [...portfolioValues, ...benchmarkValues];
  const minValue = Math.min(...allValues) * 0.995;
  const maxValue = Math.max(...allValues) * 1.005;
  const scaleX = (index) => padL + (index / Math.max(1, timeline.length - 1)) * chartW;
  const scaleY = (value) => padT + chartH - ((value - minValue) / Math.max(0.000001, maxValue - minValue)) * chartH;

  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = getComputedStyle(document.body).getPropertyValue('--bg-surface') || '#07070F';
  ctx.fillRect(0, 0, width, height);
  ctx.strokeStyle = 'rgba(140,160,220,0.12)';
  ctx.lineWidth = dpr;
  for (let index = 0; index <= 4; index += 1) {
    const y = padT + (chartH / 4) * index;
    ctx.beginPath();
    ctx.moveTo(padL, y);
    ctx.lineTo(width - padR, y);
    ctx.stroke();
    const value = maxValue - ((maxValue - minValue) / 4) * index;
    ctx.fillStyle = 'rgba(140,160,220,0.55)';
    ctx.font = `${9 * dpr}px IBM Plex Mono`;
    ctx.textAlign = 'right';
    ctx.fillText(value.toFixed(2), padL - 8 * dpr, y + 3 * dpr);
  }

  drawLine(ctx, benchmarkValues, scaleX, scaleY, 'rgba(100,120,200,0.6)', dpr, true);
  const gradient = ctx.createLinearGradient(0, padT, 0, height - padB);
  gradient.addColorStop(0, 'rgba(0,255,136,0.18)');
  gradient.addColorStop(1, 'rgba(0,255,136,0.00)');
  ctx.beginPath();
  portfolioValues.forEach((value, index) => {
    if (index === 0) ctx.moveTo(scaleX(index), scaleY(value));
    else ctx.lineTo(scaleX(index), scaleY(value));
  });
  ctx.lineTo(scaleX(portfolioValues.length - 1), height - padB);
  ctx.lineTo(scaleX(0), height - padB);
  ctx.closePath();
  ctx.fillStyle = gradient;
  ctx.fill();
  drawLine(ctx, portfolioValues, scaleX, scaleY, '#00FF88', dpr, false);

  const labelStep = Math.ceil(timeline.length / 6);
  timeline.forEach((point, index) => {
    if (index % labelStep !== 0) return;
    ctx.fillStyle = 'rgba(140,160,220,0.55)';
    ctx.font = `${9 * dpr}px IBM Plex Mono`;
    ctx.textAlign = 'center';
    ctx.fillText(String(point.date || '').substring(0, 7), scaleX(index), height - 10 * dpr);
  });
}

function drawLine(ctx, values, scaleX, scaleY, color, dpr, dashed) {
  ctx.beginPath();
  values.forEach((value, index) => {
    if (index === 0) ctx.moveTo(scaleX(index), scaleY(value));
    else ctx.lineTo(scaleX(index), scaleY(value));
  });
  ctx.strokeStyle = color;
  ctx.lineWidth = dashed ? 1.5 * dpr : 2 * dpr;
  if (dashed) ctx.setLineDash([4 * dpr, 4 * dpr]);
  ctx.stroke();
  ctx.setLineDash([]);
}

function drawMonthlyHeatmap(container, result) {
  const tbody = container.querySelector('#monthly-tbody');
  if (!tbody) return;
  const grouped = {};
  const timeline = Array.isArray(result.timeline) ? result.timeline : [];
  for (let index = 1; index < timeline.length; index += 1) {
    const date = String(timeline[index].date || '');
    const year = date.slice(0, 4);
    const month = Number(date.slice(5, 7)) - 1;
    const prev = Number(timeline[index - 1].portfolio_nav || 1);
    const current = Number(timeline[index].portfolio_nav || prev);
    if (!grouped[year]) grouped[year] = Array(12).fill(null).map(() => []);
    if (month >= 0 && month < 12 && prev) grouped[year][month].push(current / prev - 1);
  }
  const years = Object.keys(grouped).sort();
  tbody.innerHTML = years.map((year) => {
    const monthly = grouped[year].map((values) => values.reduce((acc, value) => (1 + acc) * (1 + value) - 1, 0));
    const total = monthly.reduce((acc, value) => (1 + acc) * (1 + value) - 1, 0);
    return `<tr>
      <td style="font-family:var(--f-display);font-size:10px;font-weight:700;color:var(--text-dim)">${year}</td>
      ${monthly.map((value) => {
        const text = Number.isFinite(value) ? (value * 100).toFixed(1) : '-';
        const color = value > 0.04 ? '#006633' : value > 0.01 ? '#00AA55' : value > 0 ? '#004422' : value > -0.02 ? '#661111' : '#AA2222';
        return `<td class="mh-cell" style="background:${color};color:rgba(255,255,255,0.85)" title="${text}%">${text}%</td>`;
      }).join('')}
      <td style="font-family:var(--f-display);font-size:11px;font-weight:700;color:${total > 0 ? 'var(--green)' : 'var(--red)'}">${(total * 100).toFixed(1)}%</td>
    </tr>`;
  }).join('');
}

function average(values) {
  if (!values.length) return 0;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function summarizeCounts(values) {
  const counts = values.reduce((acc, value) => {
    const key = String(value || 'unknown');
    acc[key] = (acc[key] || 0) + 1;
    return acc;
  }, {});
  const entries = Object.entries(counts);
  if (!entries.length) return '-';
  return entries.slice(0, 3).map(([key, count]) => `${key}:${count}`).join(' | ');
}

function toneForReturn(value) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return '';
  if (parsed > 0) return 'positive';
  if (parsed < 0) return 'risk';
  return '';
}
