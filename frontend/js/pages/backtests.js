import { api } from '../api.js';
import { toastError, toastSuccess } from '../components/toast.js';

let cleanup = [];

export async function render(container) {
  container.innerHTML = buildHTML();
  setupEventListeners(container);
  await loadBacktests(container);
}

export function destroy() {
  cleanup.forEach((fn) => fn());
  cleanup = [];
}

function buildHTML() {
  return `
    <div class="page-stack">
      <section class="page-hero">
        <div>
          <h2>Backtest Center</h2>
          <p>对 ESG Quant 策略执行滚动回测，查看绩效、回撤和风险告警。</p>
        </div>
        <div class="text-sm text-[var(--text-secondary)]">Walk-forward · Risk Metrics · Paper-first</div>
      </section>

      <div class="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <div class="card">
          <h3 class="text-lg font-semibold mb-4">运行回测</h3>
          <div class="space-y-4">
            <div>
              <label class="block text-sm font-medium mb-2">策略名称</label>
              <input id="backtest-strategy" type="text" class="w-full" value="ESG Multi-Factor Long-Only" />
            </div>
            <div>
              <label class="block text-sm font-medium mb-2">股票池 (可选)</label>
              <input id="backtest-universe" type="text" class="w-full" placeholder="AAPL,MSFT,TSLA,NVDA" />
            </div>
            <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label class="block text-sm font-medium mb-2">基准</label>
                <input id="backtest-benchmark" type="text" class="w-full" value="SPY" />
              </div>
              <div>
                <label class="block text-sm font-medium mb-2">资本基数</label>
                <input id="backtest-capital" type="number" class="w-full" value="1000000" />
              </div>
              <div>
                <label class="block text-sm font-medium mb-2">回看天数</label>
                <input id="backtest-lookback" type="number" class="w-full" value="126" />
              </div>
            </div>
            <button id="run-backtest-btn" class="btn-primary w-full">运行回测</button>
          </div>
        </div>

        <div class="card">
          <h3 class="text-lg font-semibold mb-4">回测指标</h3>
          <div id="backtest-metrics" class="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div class="card-elevated">
              <div class="text-sm text-[var(--text-muted)]">状态</div>
              <div class="text-2xl font-bold mt-2">等待运行</div>
            </div>
          </div>
          <div id="backtest-alerts" class="space-y-3 mt-4"></div>
        </div>
      </div>

      <div class="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <div class="card">
          <h3 class="text-lg font-semibold mb-4">时间线</h3>
          <div id="backtest-timeline" class="space-y-3"></div>
        </div>
        <div class="card">
          <h3 class="text-lg font-semibold mb-4">历史记录</h3>
          <div id="backtest-history" class="space-y-3"></div>
        </div>
      </div>
    </div>
  `;
}

function setupEventListeners(container) {
  const button = container.querySelector('#run-backtest-btn');

  const handler = async () => {
    button.disabled = true;
    button.textContent = '回测中...';
    try {
      const result = await api.quant.runBacktest({
        strategy_name: container.querySelector('#backtest-strategy').value.trim(),
        universe: splitUniverse(container.querySelector('#backtest-universe').value),
        benchmark: container.querySelector('#backtest-benchmark').value.trim() || 'SPY',
        capital_base: Number(container.querySelector('#backtest-capital').value) || 1000000,
        lookback_days: Number(container.querySelector('#backtest-lookback').value) || 126,
      });

      renderBacktest(container, result);
      await loadBacktests(container);
      toastSuccess('回测完成', 'Backtest Ready');
    } catch (error) {
      toastError(error.message, '回测失败');
    } finally {
      button.disabled = false;
      button.textContent = '运行回测';
    }
  };

  button.addEventListener('click', handler);
  cleanup.push(() => button.removeEventListener('click', handler));
}

async function loadBacktests(container) {
  try {
    const result = await api.quant.listBacktests();
    container.querySelector('#backtest-history').innerHTML = (result.backtests || []).slice(0, 6).map((item) => `
      <article class="card-elevated">
        <div class="flex items-center justify-between gap-3">
          <h3 class="text-lg font-semibold">${item.strategy_name}</h3>
          <span class="badge badge-info">${item.backtest_id}</span>
        </div>
        <div class="grid grid-cols-2 gap-3 mt-4 text-sm">
          <div>累计收益 <strong>${((item.metrics?.cumulative_return || 0) * 100).toFixed(2)}%</strong></div>
          <div>夏普 <strong>${item.metrics?.sharpe || 0}</strong></div>
          <div>最大回撤 <strong>${((item.metrics?.max_drawdown || 0) * 100).toFixed(2)}%</strong></div>
          <div>周期 <strong>${item.period_start || '-'} ~ ${item.period_end || '-'}</strong></div>
        </div>
      </article>
    `).join('') || '<div class="text-sm text-[var(--text-secondary)]">暂无历史记录</div>';
  } catch (error) {
    console.warn('加载回测历史失败', error);
  }
}

function renderBacktest(container, result) {
  const metrics = result.metrics || {};
  container.querySelector('#backtest-metrics').innerHTML = `
    <div class="card-elevated">
      <div class="text-sm text-[var(--text-muted)]">累计收益</div>
      <div class="text-2xl font-bold mt-2">${((metrics.cumulative_return || 0) * 100).toFixed(2)}%</div>
    </div>
    <div class="card-elevated">
      <div class="text-sm text-[var(--text-muted)]">年化收益</div>
      <div class="text-2xl font-bold mt-2">${((metrics.annualized_return || 0) * 100).toFixed(2)}%</div>
    </div>
    <div class="card-elevated">
      <div class="text-sm text-[var(--text-muted)]">夏普</div>
      <div class="text-2xl font-bold mt-2">${metrics.sharpe || 0}</div>
    </div>
    <div class="card-elevated">
      <div class="text-sm text-[var(--text-muted)]">最大回撤</div>
      <div class="text-2xl font-bold mt-2">${((metrics.max_drawdown || 0) * 100).toFixed(2)}%</div>
    </div>
  `;

  container.querySelector('#backtest-alerts').innerHTML = (result.risk_alerts || []).map((alert) => `
    <article class="card-elevated">
      <div class="flex items-center justify-between gap-3">
        <h3 class="text-lg font-semibold">${alert.title}</h3>
        <span class="badge ${alert.level === 'high' ? 'badge-danger' : alert.level === 'medium' ? 'badge-warning' : 'badge-success'}">${alert.level}</span>
      </div>
      <p class="text-sm text-[var(--text-secondary)] mt-3">${alert.description}</p>
      <div class="text-sm mt-3">建议：${alert.recommendation}</div>
    </article>
  `).join('');

  container.querySelector('#backtest-timeline').innerHTML = (result.timeline || []).slice(-8).map((point) => `
    <article class="card-elevated">
      <div class="flex items-center justify-between gap-3">
        <strong>${point.date}</strong>
        <span>DD ${(point.drawdown * 100).toFixed(2)}%</span>
      </div>
      <div class="grid grid-cols-2 gap-3 mt-3 text-sm">
        <div>策略净值 <strong>${point.portfolio_nav}</strong></div>
        <div>基准净值 <strong>${point.benchmark_nav}</strong></div>
      </div>
    </article>
  `).join('');
}

function splitUniverse(raw) {
  return String(raw || '')
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);
}
