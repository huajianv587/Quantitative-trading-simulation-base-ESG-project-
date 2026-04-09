import { api } from '../api.js';
import { toastError, toastSuccess } from '../components/toast.js';

let cleanup = [];

export async function render(container) {
  container.innerHTML = buildHTML();
  await hydrateUniverse(container);
  setupEventListeners(container);
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
          <h2>Research Lab</h2>
          <p>把 ESG、传统因子与另类数据聚合成一轮完整的量化研究流程。</p>
        </div>
        <div class="text-sm text-[var(--text-secondary)]">Research Agent -> Strategy Agent -> Risk Agent</div>
      </section>

      <div class="card">
        <div class="overview-section-head">
          <div>
            <div class="overview-section-head__kicker">Quant Research</div>
            <h2>运行一轮研究</h2>
          </div>
          <p>默认输出信号排序、组合建议、研究摘要和工件存储信息。</p>
        </div>

        <div class="grid grid-cols-1 xl:grid-cols-2 gap-4">
          <div>
            <label class="block text-sm font-medium mb-2">研究问题</label>
            <textarea id="research-question" rows="5" class="w-full" placeholder="例如：结合 ESG 变化率、质量因子和另类数据，生成未来 20 日增强型组合。">结合 ESG 变化率、质量因子和另类数据，生成未来 20 日增强型组合。</textarea>
          </div>

          <div class="space-y-4">
            <div>
              <label class="block text-sm font-medium mb-2">股票池 (逗号分隔，可留空使用默认)</label>
              <input id="research-universe" type="text" class="w-full" placeholder="AAPL,MSFT,TSLA,NVDA" />
            </div>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label class="block text-sm font-medium mb-2">基准</label>
                <input id="research-benchmark" type="text" class="w-full" value="SPY" />
              </div>
              <div>
                <label class="block text-sm font-medium mb-2">资本基数</label>
                <input id="research-capital" type="number" class="w-full" value="1000000" />
              </div>
            </div>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label class="block text-sm font-medium mb-2">研究周期 (天)</label>
                <input id="research-horizon" type="number" class="w-full" value="20" />
              </div>
              <div class="flex items-end">
                <button id="run-research-btn" class="btn-primary w-full">运行研究</button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="card">
        <div class="overview-section-head">
          <div>
            <div class="overview-section-head__kicker">Universe</div>
            <h2>默认股票池</h2>
          </div>
          <p>当前默认股票池来自 ESG US Large Cap 基线，可按需覆盖。</p>
        </div>
        <div id="research-universe-grid" class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3"></div>
      </div>

      <div id="research-results" class="hidden space-y-4">
        <div class="card">
          <div class="overview-section-head">
            <div>
              <div class="overview-section-head__kicker">Summary</div>
              <h2>研究摘要</h2>
            </div>
            <p id="research-storage"></p>
          </div>
          <p id="research-summary" class="text-[var(--text-secondary)] leading-7"></p>
        </div>

        <div class="grid grid-cols-1 xl:grid-cols-2 gap-4">
          <div class="card">
            <h3 class="text-lg font-semibold mb-4">优先信号</h3>
            <div id="research-signal-list" class="space-y-3"></div>
          </div>

          <div class="card">
            <h3 class="text-lg font-semibold mb-4">组合建议</h3>
            <div id="research-portfolio-list" class="space-y-3"></div>
          </div>
        </div>
      </div>
    </div>
  `;
}

async function hydrateUniverse(container) {
  try {
    const data = await api.quant.getUniverse();
    const target = container.querySelector('#research-universe-grid');
    target.innerHTML = (data.members || []).map((member) => `
      <div class="card-elevated">
        <div class="text-xs uppercase tracking-[0.24em] text-[var(--text-muted)]">${member.sector}</div>
        <div class="text-xl font-bold mt-2">${member.symbol}</div>
        <div class="text-sm text-[var(--text-secondary)] mt-1">${member.company_name}</div>
        <div class="text-xs text-[var(--text-muted)] mt-3">${member.industry}</div>
      </div>
    `).join('');
  } catch (error) {
    console.warn('加载默认股票池失败', error);
  }
}

function setupEventListeners(container) {
  const button = container.querySelector('#run-research-btn');

  const handler = async () => {
    button.disabled = true;
    button.textContent = '运行中...';

    try {
      const result = await api.quant.runResearch({
        research_question: container.querySelector('#research-question').value.trim(),
        benchmark: container.querySelector('#research-benchmark').value.trim() || 'SPY',
        capital_base: Number(container.querySelector('#research-capital').value) || 1000000,
        horizon_days: Number(container.querySelector('#research-horizon').value) || 20,
        universe: splitUniverse(container.querySelector('#research-universe').value),
      });

      renderResults(container, result);
      toastSuccess('量化研究已完成', 'Research Ready');
    } catch (error) {
      toastError(error.message, '研究失败');
    } finally {
      button.disabled = false;
      button.textContent = '运行研究';
    }
  };

  button.addEventListener('click', handler);
  cleanup.push(() => button.removeEventListener('click', handler));
}

function renderResults(container, result) {
  container.querySelector('#research-results').classList.remove('hidden');
  container.querySelector('#research-summary').textContent = result.report_excerpt || '本轮研究已完成。';
  container.querySelector('#research-storage').textContent = formatStorageSummary(result.storage);

  container.querySelector('#research-signal-list').innerHTML = (result.signals || []).slice(0, 5).map((signal) => `
    <article class="card-elevated">
      <div class="flex items-center justify-between gap-3">
        <div>
          <div class="text-sm uppercase tracking-[0.24em] text-[var(--text-muted)]">${signal.sector}</div>
          <h3 class="text-lg font-semibold mt-1">${signal.symbol} · ${signal.company_name}</h3>
        </div>
        <span class="badge ${signal.action === 'long' ? 'badge-success' : signal.action === 'short' ? 'badge-danger' : 'badge-warning'}">${signal.action}</span>
      </div>
      <p class="text-sm text-[var(--text-secondary)] mt-3">${signal.thesis}</p>
      <div class="grid grid-cols-2 gap-3 mt-4 text-sm">
        <div>综合评分 <strong>${signal.overall_score}</strong></div>
        <div>置信度 <strong>${Math.round((signal.confidence || 0) * 100)}%</strong></div>
        <div>预期收益 <strong>${(signal.expected_return * 100).toFixed(2)}%</strong></div>
        <div>风险评分 <strong>${signal.risk_score}</strong></div>
      </div>
    </article>
  `).join('');

  container.querySelector('#research-portfolio-list').innerHTML = (result.portfolio?.positions || []).map((position) => `
    <article class="card-elevated">
      <div class="flex items-center justify-between gap-3">
        <h3 class="text-lg font-semibold">${position.symbol} · ${position.company_name}</h3>
        <span class="badge badge-info">${(position.weight * 100).toFixed(2)}%</span>
      </div>
      <p class="text-sm text-[var(--text-secondary)] mt-3">${position.thesis}</p>
      <div class="grid grid-cols-2 gap-3 mt-4 text-sm">
        <div>风险预算 <strong>${(position.risk_budget * 100).toFixed(1)}%</strong></div>
        <div>预期收益 <strong>${(position.expected_return * 100).toFixed(2)}%</strong></div>
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

function formatStorageSummary(storage) {
  const backend = storage?.artifact_backend === 'r2'
    ? 'R2 Artifact'
    : storage?.artifact_backend === 'supabase_storage'
      ? 'Supabase Storage'
      : 'Local Artifact';
  const location = storage?.artifact_uri || storage?.local_path || 'saved';
  return `${backend}: ${location}`;
}
