import { api } from '../qtapi.js?v=8';
import { toast } from '../components/toast.js?v=8';
import { getLang } from '../i18n.js?v=8';
import { esc, num, pct, renderTokenPreview, splitTokens, statusBadge } from './workbench-utils.js?v=8';

let _equityChart = null;

const COPY = {
  en: {
    title: 'Backtest Engine',
    subtitle: 'Strategy Validation Lab | Equity Curve | Risk Attribution | Monthly Returns',
    runTitle: 'Run Backtest',
    runSub: 'Configure strategy parameters',
    strategy: 'Strategy Name',
    universe: 'Universe',
    benchmark: 'Benchmark',
    capital: 'Capital ($)',
    lookback: 'Lookback (trading days)',
    provider: 'Market Data Chain',
    advanced: 'Advanced Settings',
    force: 'Force Refresh',
    run: 'Run Backtest',
    recent: 'Recent Backtests',
    preview: 'Backtest Preview',
    previewTitle: 'Ready to run a real-data backtest',
    previewText: 'The engine will try Twelve Data first, then Alpaca IEX, yfinance, cache, and finally a labelled synthetic fallback.',
    equity: 'Equity Curve',
    monthly: 'Monthly Returns Heatmap',
    full: 'Full Metrics',
    alerts: 'Risk Alerts',
  },
  zh: {
    title: '回测引擎',
    subtitle: '策略验证实验室 | 权益曲线 | 风险归因 | 月度收益',
    runTitle: '运行回测',
    runSub: '配置策略参数',
    strategy: '策略名称',
    universe: '股票池',
    benchmark: '基准',
    capital: '本金 ($)',
    lookback: '回看天数',
    provider: '行情链路',
    advanced: '高级设置',
    force: '强制刷新',
    run: '运行回测',
    recent: '最近回测',
    preview: '回测预览',
    previewTitle: '准备运行真实数据回测',
    previewText: '引擎会优先尝试 Twelve Data，然后回落到 Alpaca IEX、yfinance、缓存，最后才使用显式标记的 synthetic fallback。',
    equity: '权益曲线',
    monthly: '月度收益热力图',
    full: '完整指标',
    alerts: '风险提醒',
  },
};

function c(key) {
  const lang = getLang() === 'zh' ? 'zh' : 'en';
  return COPY[lang][key] || COPY.en[key] || key;
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
            <canvas id="equity-canvas" height="300" style="width:100%;border-radius:0"></canvas>
          </div>
        </div>
        <div class="card" id="bt-monthly-card" style="display:none">
          <div class="card-header"><span class="card-title">${c('monthly')}</span></div>
          <div class="card-body" style="overflow-x:auto">
            <table class="monthly-heatmap-table" id="monthly-heatmap">
              <thead><tr>
                <th>Year</th>
                ${['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec','Total'].map((m) => `<th>${m}</th>`).join('')}
              </tr></thead>
              <tbody id="monthly-tbody"></tbody>
            </table>
          </div>
        </div>
        <div class="grid-2 backtest-bottom-grid" id="bt-bottom" style="display:none">
          <div class="card" id="bt-metrics-detail"></div>
          <div class="card" id="bt-risk-attribution"></div>
          <div class="card" id="bt-alerts"></div>
        </div>
        <div id="bt-placeholder" class="card">
          ${renderBacktestPreview()}
        </div>
      </div>
    </div>
  </div>`;
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
            <article class="workbench-metric-card"><div class="workbench-metric-card__label">Equity Curve</div><div class="workbench-metric-card__value">pending</div></article>
            <article class="workbench-metric-card"><div class="workbench-metric-card__label">Sharpe / MDD</div><div class="workbench-metric-card__value">armed</div></article>
            <article class="workbench-metric-card"><div class="workbench-metric-card__label">Monthly Heatmap</div><div class="workbench-metric-card__value">ready</div></article>
            <article class="workbench-metric-card"><div class="workbench-metric-card__label">Risk Attribution</div><div class="workbench-metric-card__value">waiting</div></article>
          </div>
          <div class="backtest-preview-chart">
            <div class="backtest-preview-chart__grid"></div>
            <div class="backtest-preview-chart__line"></div>
            <div class="backtest-preview-chart__line backtest-preview-chart__line--secondary"></div>
          </div>
        </section>
        <section class="backtest-preview-pane backtest-preview-pane--side">
          <div class="workbench-section">
            <div class="workbench-section__title">Data Source Chain</div>
            <div class="backtest-data-source">
              <span>twelvedata first</span>
              <span>alpaca iex fallback</span>
              <span>yfinance fallback</span>
              <span>cache fallback</span>
              <span>synthetic clearly labelled</span>
            </div>
          </div>
          <div class="workbench-section">
            <div class="workbench-section__title">Planned Outputs</div>
            <div class="workbench-kv-list compact-kv-list">
              <div class="workbench-kv-row"><span>Chart</span><strong>equity curve</strong></div>
              <div class="workbench-kv-row"><span>Table</span><strong>monthly returns</strong></div>
              <div class="workbench-kv-row"><span>Alerts</span><strong>risk summary</strong></div>
              <div class="workbench-kv-row"><span>Lineage</span><strong>data source chain</strong></div>
            </div>
          </div>
          <div class="workbench-section">
            <div class="workbench-section__title">Preview Heatmap</div>
            <div class="backtest-preview-heatmap">
              ${Array.from({ length: 12 }, (_, index) => `<span class="backtest-preview-heatmap__cell backtest-preview-heatmap__cell--${index % 4}"></span>`).join('')}
            </div>
          </div>
        </section>
      </div>
    </div>`;
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
  const el = container.querySelector('#bt-history');
  try {
    const { backtests } = await api.backtests.list();
    if (!backtests?.length) {
      el.innerHTML = `<div style="padding:14px 18px;font-family:var(--f-mono);font-size:11px;color:var(--text-dim)">No backtests yet</div>`;
      return;
    }
    el.innerHTML = backtests.slice(0, 6).map((b) => `
      <div class="wf-window" style="margin:0;border-radius:0;border-left:none;border-right:none;border-top:none;cursor:pointer" data-id="${b.backtest_id}">
        <div>
          <div class="wf-window__label">${esc(b.strategy_name || b.backtest_id)}</div>
          <div style="font-size:9px;color:var(--text-dim);font-family:var(--f-mono);margin-top:2px">${esc(b.period_start || '')}</div>
        </div>
        <div style="text-align:right">
          <div class="wf-window__sharpe ${(b.metrics?.sharpe || 0) >= 1 ? 'pos' : 'text-dim'}" style="font-size:16px">${num(b.metrics?.sharpe)}</div>
          <div style="font-size:9px;color:var(--text-dim);font-family:var(--f-mono)">Sharpe</div>
        </div>
      </div>`).join('');

    el.querySelectorAll('[data-id]').forEach((row) => {
      row.addEventListener('click', async () => {
        try {
          const data = await api.backtests.get(row.dataset.id);
          showResults(container, data);
        } catch (error) {
          toast.error('Load failed', error.message);
        }
      });
    });
  } catch {
    el.innerHTML = `<div style="padding:14px 18px;color:var(--text-dim);font-size:11px">Could not load history</div>`;
  }
}

async function runBacktest(container) {
  const btn = container.querySelector('#btn-run-bt');
  btn.disabled = true;
  btn.textContent = 'Running...';

  const strategy = container.querySelector('#bt-strategy').value.trim() || 'ESG Multi-Factor Long-Only';
  const universeText = container.querySelector('#bt-universe').value.trim();
  const universe = universeText ? universeText.split(/[,\s]+/).filter(Boolean).map((item) => item.toUpperCase()) : [];
  const benchmark = container.querySelector('#bt-benchmark').value;
  const capital = Number(container.querySelector('#bt-capital').value) || 1000000;
  const lookback = Number(container.querySelector('#bt-lookback').value) || 126;
  const marketDataProvider = container.querySelector('#bt-provider').value.trim() || 'twelvedata, alpaca, yfinance, cache, synthetic';
  const forceRefresh = container.querySelector('#bt-force-refresh').value === 'true';

  try {
    const res = await api.backtests.run({
      strategy_name: strategy,
      universe,
      benchmark,
      capital_base: capital,
      lookback_days: lookback,
      market_data_provider: marketDataProvider,
      force_refresh: forceRefresh,
    });
    showResults(container, res);
    toast.success('Backtest complete', `Sharpe ${num(res.metrics?.sharpe)} | ${res.data_source || 'source unknown'}`);
    loadHistory(container);
  } catch (error) {
    toast.error('Backtest failed', error.message);
  } finally {
    btn.disabled = false;
    btn.textContent = c('run');
  }
}

function showResults(container, res) {
  container.querySelector('#bt-placeholder').style.display = 'none';
  container.querySelector('#bt-metric-row').style.display = '';
  container.querySelector('#bt-chart-card').style.display = '';
  container.querySelector('#bt-monthly-card').style.display = '';
  container.querySelector('#bt-bottom').style.display = '';

  const metrics = res.metrics || {};
  container.querySelector('#bt-metrics').innerHTML = [
    ['Annual Return', pct(metrics.annualized_return), pctCls(metrics.annualized_return)],
    ['Sharpe Ratio', num(metrics.sharpe), metrics.sharpe >= 1 ? 'pos' : ''],
    ['Max Drawdown', pct(metrics.max_drawdown), 'neg'],
    ['Win Rate', pct(metrics.hit_rate), ''],
    ['Data Source', res.data_source || '-', res.used_synthetic_fallback ? 'neg' : 'pos'],
    ['Info Ratio', num(metrics.information_ratio), ''],
  ].map(([label, value, klass]) => `
    <div class="metric-card">
      <div class="metric-sheen"></div>
      <div class="metric-label">${esc(label)}</div>
      <div class="metric-value ${klass}" style="font-size:20px">${esc(value)}</div>
    </div>`).join('');

  drawEquityCurve(container, res);
  drawMonthlyHeatmap(container, res);

  const detail = [
    ['Strategy', res.strategy_name],
    ['Benchmark', res.benchmark],
    ['Period', `${res.period_start} -> ${res.period_end}`],
    ['Cum. Return', pct(metrics.cumulative_return)],
    ['Ann. Volatility', pct(metrics.annualized_volatility)],
    ['Beta', num(metrics.beta)],
    ['Data Chain', (res.data_source_chain || []).join(' -> ')],
    ['Warnings', (res.market_data_warnings || []).join('; ') || 'none'],
  ];
  const positions = Array.isArray(res.positions) ? res.positions : [];
  const topRiskRows = [...positions]
    .sort((left, right) => Number(right.risk_budget || 0) - Number(left.risk_budget || 0))
    .slice(0, 4);
  const avgFill = average(positions.map((position) => Number(position.expected_fill_probability || 0)).filter((value) => value > 0));
  const avgSlippage = average(positions.map((position) => Number(position.estimated_slippage_bps || 0)).filter((value) => value > 0));
  const avgImpact = average(positions.map((position) => Number(position.estimated_impact_bps || 0)).filter((value) => value > 0));
  const engineMix = summarizeCounts(positions.map((position) => position.alpha_engine || position.strategy_bucket || 'runtime'));
  const postureMix = summarizeCounts(positions.map((position) => position.regime_posture || 'neutral'));
  container.querySelector('#bt-metrics-detail').innerHTML = `
    <div class="card-header"><span class="card-title">${c('full')}</span></div>
    <div class="card-body" style="display:flex;flex-direction:column;gap:8px">
      ${detail.map(([label, value]) => `
        <div class="workbench-kv-row">
          <span>${esc(label)}</span>
          <strong>${esc(value || '-')}</strong>
        </div>`).join('')}
    </div>`;

  container.querySelector('#bt-risk-attribution').innerHTML = `
    <div class="card-header"><span class="card-title">Risk Attribution</span></div>
    <div class="card-body" style="display:flex;flex-direction:column;gap:12px">
      <div class="workbench-metric-grid">
        ${metric('Positions', positions.length || '-')}
        ${metric('Avg Fill', avgFill ? pct(avgFill) : '-')}
        ${metric('Slip', avgSlippage ? `${avgSlippage.toFixed(1)} bps` : '-')}
        ${metric('Impact', avgImpact ? `${avgImpact.toFixed(1)} bps` : '-')}
      </div>
      <div class="workbench-section">
        <div class="workbench-section__title">Top Risk Budget</div>
        <div class="workbench-kv-list compact-kv-list">
          ${(topRiskRows.length ? topRiskRows : [{ symbol: 'n/a', risk_budget: 0, weight: 0 }]).map((position) => `
            <div class="workbench-kv-row">
              <span>${esc(position.symbol || '-')} / ${esc(position.side || 'long')}</span>
              <strong>${pct(position.risk_budget || 0)} | w ${pct(position.weight || 0)}</strong>
            </div>
          `).join('')}
        </div>
      </div>
      <div class="workbench-section">
        <div class="workbench-section__title">Engine + Regime Mix</div>
        <div class="preview-step-grid">
          <div class="preview-step"><span>Alpha engines</span><strong>${esc(engineMix)}</strong></div>
          <div class="preview-step"><span>Regime posture</span><strong>${esc(postureMix)}</strong></div>
        </div>
      </div>
    </div>`;

  const alerts = res.risk_alerts || [];
  container.querySelector('#bt-alerts').innerHTML = `
    <div class="card-header">
      <span class="card-title">${c('alerts')}</span>
      <span class="text-xs text-muted font-mono">${alerts.length} alerts</span>
    </div>
    <div class="card-body" style="display:flex;flex-direction:column;gap:8px">
      <div class="workbench-section">
        <div class="workbench-section__title">Source Guard</div>
        <div class="factor-checklist">
          <div class="factor-check-row"><span>data_source</span><strong>${esc(res.data_source || '-')}</strong></div>
          <div class="factor-check-row"><span>fallback used</span><strong>${res.used_synthetic_fallback ? 'yes' : 'no'}</strong></div>
          <div class="factor-check-row"><span>data chain</span><strong>${esc((res.data_source_chain || []).join(' -> ') || '-')}</strong></div>
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
        </div>`).join('') : '<div class="text-muted text-sm" style="padding:4px 0">No risk alerts. Strategy remains inside the current guardrails.</div>'}
      ${(res.market_data_warnings || []).length ? `
        <div class="workbench-section">
          <div class="workbench-section__title">Market Data Warnings</div>
          <div class="workbench-kv-list compact-kv-list">
            ${(res.market_data_warnings || []).map((warning) => `<div class="workbench-kv-row"><span>warning</span><strong>${esc(warning)}</strong></div>`).join('')}
          </div>
        </div>` : ''}
    </div>`;
}

function drawEquityCurve(container, res) {
  const canvas = container.querySelector('#equity-canvas');
  if (!canvas) return;
  const dpr = window.devicePixelRatio || 1;
  canvas.width = (canvas.parentElement?.offsetWidth || 900) * dpr;
  canvas.height = 300 * dpr;
  canvas.style.height = '300px';
  const ctx = canvas.getContext('2d');
  const W = canvas.width;
  const H = canvas.height;
  const padL = 70 * dpr;
  const padR = 24 * dpr;
  const padT = 24 * dpr;
  const padB = 34 * dpr;
  const chartW = W - padL - padR;
  const chartH = H - padT - padB;
  const timeline = res.timeline || [];
  if (!timeline.length) return;
  const portVals = timeline.map((point) => Number(point.portfolio_nav || 1));
  const benchVals = timeline.map((point) => Number(point.benchmark_nav || 1));
  const allVals = [...portVals, ...benchVals];
  const minV = Math.min(...allVals) * 0.995;
  const maxV = Math.max(...allVals) * 1.005;
  const pX = (index) => padL + (index / Math.max(1, timeline.length - 1)) * chartW;
  const pY = (value) => padT + chartH - ((value - minV) / Math.max(0.000001, maxV - minV)) * chartH;

  ctx.clearRect(0, 0, W, H);
  ctx.fillStyle = getComputedStyle(document.body).getPropertyValue('--bg-surface') || '#07070F';
  ctx.fillRect(0, 0, W, H);
  ctx.strokeStyle = 'rgba(140,160,220,0.12)';
  ctx.lineWidth = dpr;
  for (let i = 0; i <= 4; i += 1) {
    const y = padT + (chartH / 4) * i;
    ctx.beginPath();
    ctx.moveTo(padL, y);
    ctx.lineTo(W - padR, y);
    ctx.stroke();
    const value = maxV - ((maxV - minV) / 4) * i;
    ctx.fillStyle = 'rgba(140,160,220,0.55)';
    ctx.font = `${9 * dpr}px IBM Plex Mono`;
    ctx.textAlign = 'right';
    ctx.fillText(value.toFixed(2), padL - 8 * dpr, y + 3 * dpr);
  }

  drawLine(ctx, benchVals, pX, pY, 'rgba(100,120,200,0.6)', dpr, true);
  const grad = ctx.createLinearGradient(0, padT, 0, H - padB);
  grad.addColorStop(0, 'rgba(0,255,136,0.18)');
  grad.addColorStop(1, 'rgba(0,255,136,0.00)');
  ctx.beginPath();
  portVals.forEach((value, index) => {
    if (index === 0) ctx.moveTo(pX(index), pY(value));
    else ctx.lineTo(pX(index), pY(value));
  });
  ctx.lineTo(pX(portVals.length - 1), H - padB);
  ctx.lineTo(pX(0), H - padB);
  ctx.closePath();
  ctx.fillStyle = grad;
  ctx.fill();
  drawLine(ctx, portVals, pX, pY, '#00FF88', dpr, false);

  const labelStep = Math.ceil(timeline.length / 6);
  timeline.forEach((point, index) => {
    if (index % labelStep !== 0) return;
    ctx.fillStyle = 'rgba(140,160,220,0.55)';
    ctx.font = `${9 * dpr}px IBM Plex Mono`;
    ctx.textAlign = 'center';
    ctx.fillText(String(point.date || '').substring(0, 7), pX(index), H - 10 * dpr);
  });
}

function drawLine(ctx, values, pX, pY, color, dpr, dashed) {
  ctx.beginPath();
  values.forEach((value, index) => {
    if (index === 0) ctx.moveTo(pX(index), pY(value));
    else ctx.lineTo(pX(index), pY(value));
  });
  ctx.strokeStyle = color;
  ctx.lineWidth = dashed ? 1.5 * dpr : 2 * dpr;
  if (dashed) ctx.setLineDash([4 * dpr, 4 * dpr]);
  ctx.stroke();
  ctx.setLineDash([]);
}

function drawMonthlyHeatmap(container, res) {
  const tbody = container.querySelector('#monthly-tbody');
  if (!tbody) return;
  const grouped = {};
  const timeline = res.timeline || [];
  for (let i = 1; i < timeline.length; i += 1) {
    const date = String(timeline[i].date || '');
    const year = date.slice(0, 4);
    const month = Number(date.slice(5, 7)) - 1;
    const prev = Number(timeline[i - 1].portfolio_nav || 1);
    const curr = Number(timeline[i].portfolio_nav || prev);
    if (!grouped[year]) grouped[year] = Array(12).fill(null).map(() => []);
    if (month >= 0 && month < 12 && prev) grouped[year][month].push(curr / prev - 1);
  }
  const years = Object.keys(grouped).sort();
  tbody.innerHTML = years.map((year) => {
    const monthly = grouped[year].map((values) => values.reduce((acc, value) => (1 + acc) * (1 + value) - 1, 0));
    const total = monthly.reduce((acc, value) => (1 + acc) * (1 + value) - 1, 0);
    return `<tr>
      <td style="font-family:var(--f-display);font-size:10px;font-weight:700;color:var(--text-dim)">${year}</td>
      ${monthly.map((value) => {
        const pctText = Number.isFinite(value) ? (value * 100).toFixed(1) : '-';
        const color = value > 0.04 ? '#006633' : value > 0.01 ? '#00AA55' : value > 0 ? '#004422' : value > -0.02 ? '#661111' : '#AA2222';
        return `<td class="mh-cell" style="background:${color};color:rgba(255,255,255,0.85)" title="${pctText}%">${pctText}%</td>`;
      }).join('')}
      <td style="font-family:var(--f-display);font-size:11px;font-weight:700;color:${total > 0 ? 'var(--green)' : 'var(--red)'}">${(total * 100).toFixed(1)}%</td>
    </tr>`;
  }).join('');
}

const pctCls = (value) => value > 0 ? 'pos' : value < 0 ? 'neg' : '';

function average(values) {
  if (!values.length) return 0;
  return values.reduce((acc, value) => acc + value, 0) / values.length;
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
