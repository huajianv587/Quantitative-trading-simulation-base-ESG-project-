import { api } from '../qtapi.js?v=8';
import { toast } from '../components/toast.js?v=8';
import { router } from '../router.js?v=8';
import { getLang, onLangChange } from '../i18n.js?v=8';
import { ensureUiAuditLog, recordUiAuditEvent } from '../modules/ui-audit.js?v=8';
import { setVersionedStorageValue } from '../utils.js?v=8';

let _container = null;
let _state = null;
let _langCleanup = null;

const WORKFLOW_LATEST_STORAGE_KEY = 'qt.workflow.latest';
const WORKFLOW_LATEST_SCHEMA_VERSION = 1;

const RL_COPY = {
  en: {
    title: 'RL Agent Lab',
    subtitle: 'Real dataset build / quick search / full train / backtest artifacts / execution handoff',
    openExecution: 'Open Execution',
    refresh: 'Refresh Lab',
    badge: 'SCI Experiment Track',
    heroTitle: 'Turn recipe layers into a repeatable RL training loop.',
    heroText: 'Build real datasets from stored market data, search local best hyper-parameters, launch a full run, archive metrics, and hand the validated policy back into the execution layer.',
    datasetBuilderTitle: 'Real Dataset Builder',
    datasetBuilderSub: 'Build recipe and market datasets from stored market data only.',
    trainBacktestTitle: 'Training / Backtest Pipeline',
    trainBacktestSub: 'Train and validate only against real datasets and archived checkpoints.',
    trackedRuns: 'Tracked Runs',
    trackedDetail: 'SQLite + Supabase mirrored metadata',
    recipeCatalog: 'Recipe Catalog',
    recipeDetail: 'Six-stage AutoDL experiment ladder',
    manifests: 'Dataset Manifests',
    manifestsDetail: 'Experiment manual data lineage',
    metrics: 'Metrics Files',
    metricsDetail: 'Per-run metrics.json archived',
    latestDataset: 'Latest Dataset',
    latestDatasetReady: 'Latest real recipe/market dataset located',
    latestDatasetPending: 'No ready real dataset found yet',
    latestCheckpoint: 'Latest Checkpoint',
    latestCheckpointReady: 'Checkpoint ready for reload',
    latestCheckpointPending: 'Training artifact not synced yet',
    latestReport: 'Latest Report',
    latestReportReady: 'Backtest/report artifact available',
    latestReportPending: 'Report artifact pending',
    paperExecution: 'Execution Bridge',
    paperExecutionDetail: 'Validated models hand off into the main execution stack',
    awaiting: 'Awaiting remote artifact',
  },
  zh: {
    title: 'RL 智能体实验室',
    subtitle: '真实数据集构建 / 快速搜索 / 正式训练 / 回测产物 / 执行层交接',
    openExecution: '打开执行层',
    refresh: '刷新实验室',
    badge: 'SCI 实验轨道',
    heroTitle: '把配方层变成可复现的 RL 训练闭环。',
    heroText: '从已落库的市场数据构建真实数据集，搜索本地最优超参数，启动完整训练，归档指标，并把验证后的策略交回执行层。',
    datasetBuilderTitle: '真实数据集构建',
    datasetBuilderSub: '只从已落库的市场数据构建 recipe / market dataset。',
    trainBacktestTitle: '训练 / 回测流水线',
    trainBacktestSub: '训练和回测只接受真实数据集与已归档 checkpoint。',
    trackedRuns: '跟踪运行',
    trackedDetail: 'SQLite + Supabase 镜像元数据',
    recipeCatalog: '配方目录',
    recipeDetail: '六阶段 AutoDL 实验阶梯',
    manifests: '数据清单',
    manifestsDetail: '实验手册数据血缘',
    metrics: '指标文件',
    metricsDetail: '逐运行归档 metrics.json',
    latestDataset: '最新数据集',
    latestDatasetReady: '已定位最新真实配方/市场数据集',
    latestDatasetPending: '暂未找到可用真实数据集',
    latestCheckpoint: '最新检查点',
    latestCheckpointReady: '检查点可重新加载',
    latestCheckpointPending: '训练产物尚未同步',
    latestReport: '最新报告',
    latestReportReady: '回测/报告产物可用',
    latestReportPending: '报告产物待生成',
    paperExecution: '执行层入口',
    paperExecutionDetail: '验证后的模型将交接到主执行栈',
    awaiting: '等待远端产物',
  },
};

function resetState() {
  _state = {
    overview: null,
    lastPayload: null,
    lastDataset: null,
    lastTrain: null,
    lastBacktest: null,
    lastSearch: null,
    lastWorkflow: null,
    selectedRecipeKey: 'L1_price_tech',
  };
}

function updateAuditState() {
  const overview = _state?.overview || {};
  window.__rlAuditState = {
    selectedRecipeKey: _state?.selectedRecipeKey || '',
    lastDatasetPath: (_state?.lastDataset || {}).merged_dataset_path || (_state?.lastDataset || {}).primary_dataset_path || '',
    lastTrainRunId: (_state?.lastTrain || {}).run_id || '',
    lastBacktestRunId: (_state?.lastBacktest || {}).run_id || '',
    lastWorkflowId: (_state?.lastWorkflow || {}).workflow_id || '',
    lastWorkflowStatus: (_state?.lastWorkflow || {}).status || '',
    lastSearchRecipe: (_state?.lastSearch || {}).recipe_key || '',
    lastSearchBackend: (_state?.lastSearch || {}).search_backend || '',
    bestParams: (_state?.lastSearch || {}).best_params || {},
    runCount: (overview.runs || []).length || 0,
  };
}

function activeRecipe() {
  const recipes = _state?.overview?.recipes || [];
  return recipes.find((recipe) => recipe.key === _state.selectedRecipeKey) || recipes[0] || null;
}

function defaultDatasetName(recipeKey) {
  return `${String(recipeKey || 'recipe').toLowerCase()}-pack`;
}

function latestPath(entry) {
  if (!entry || typeof entry !== 'object') return '';
  return entry.path || entry.dataset_path || entry.merged_dataset_path || entry.primary_dataset_path || '';
}

function resolveDatasetPath() {
  const explicit = query('#rl-dataset-path')?.value?.trim();
  if (explicit) return explicit;
  return latestPath(_state.lastDataset)
    || latestPath(_state.overview?.latest_dataset)
    || latestPath(_state.lastTrain?.config)
    || '';
}

export async function render(container) {
  _container = container;
  resetState();
  ensureUiAuditLog();
  container.innerHTML = buildShell();
  bindEvents();
  _langCleanup ||= onLangChange(() => {
    if (_container?.isConnected) {
      const snapshot = _state;
      _container.innerHTML = buildShell();
      bindEvents();
      _state = snapshot;
      renderOverview();
    }
  });
  await loadOverview(false);
}

export async function destroy() {
  _container = null;
  resetState();
  _langCleanup?.();
  _langCleanup = null;
}

function c(key) {
  const current = getLang() === 'zh' ? 'zh' : 'en';
  return RL_COPY[current]?.[key] || RL_COPY.en[key] || key;
}

function buildShell() {
  return `
    <div class="rl-lab-page" data-no-autotranslate="true">
    <div class="page-header">
      <div>
        <div class="page-header__title">${c('title')}</div>
        <div class="page-header__sub">${c('subtitle')}</div>
      </div>
      <div class="page-header__actions">
        <button class="btn btn-ghost btn-sm" id="rl-open-execution">${c('openExecution')}</button>
        <button class="btn btn-primary btn-sm" id="rl-refresh">${c('refresh')}</button>
      </div>
    </div>

    <section class="card rl-lab-hero">
      <div class="card-body rl-lab-hero__body">
        <div class="rl-lab-hero__copy">
          <span class="badge rl-lab-badge">${c('badge')}</span>
          <h2>${c('heroTitle')}</h2>
          <p>${c('heroText')}</p>
        </div>
        <div class="rl-lab-hero__channels" id="rl-service-badges"></div>
      </div>
    </section>

    <section class="rl-lab-stats" id="rl-stats">
      <article class="metric-card rl-lab-stat">
        <div class="metric-label">${c('trackedRuns')}</div>
        <div class="metric-value rl-lab-stat__value">0</div>
        <div class="rl-lab-stat__detail">${c('trackedDetail')}</div>
      </article>
      <article class="metric-card rl-lab-stat">
        <div class="metric-label">${c('recipeCatalog')}</div>
        <div class="metric-value rl-lab-stat__value">0</div>
        <div class="rl-lab-stat__detail">${c('recipeDetail')}</div>
      </article>
      <article class="metric-card rl-lab-stat">
        <div class="metric-label">${c('latestDataset')}</div>
        <div class="metric-value rl-lab-stat__value rl-lab-stat__value--path">${c('awaiting')}</div>
        <div class="rl-lab-stat__detail">${c('latestDatasetPending')}</div>
      </article>
    </section>

    <section class="card" id="hybrid-paper-workflow-panel">
      <div class="card-header">
        <div>
          <span class="card-title">Run Hybrid Paper Workflow</span>
          <div class="run-panel__sub">P1/P2 decision, RL checkpoint validation, backtest, tearsheet, paper gate, and Alpaca paper routing.</div>
        </div>
      </div>
      <div class="card-body rl-lab-form">
        <div class="form-row">
          <div class="form-group">
            <label class="form-label">Universe</label>
            <input class="form-input" id="workflow-universe" placeholder="Blank uses default pool">
          </div>
          <div class="form-group">
            <label class="form-label">Capital</label>
            <input class="form-input" id="workflow-capital" type="number" min="1" value="1000000">
          </div>
        </div>

        <div class="form-row">
          <div class="form-group">
            <label class="form-label">Max Orders</label>
            <input class="form-input" id="workflow-max-orders" type="number" min="1" max="10" value="2">
          </div>
          <div class="form-group">
            <label class="form-label">Per-Order Notional</label>
            <input class="form-input" id="workflow-notional" type="number" min="0.01" step="0.01" value="1.00">
          </div>
        </div>

        <div class="form-row">
          <label class="rl-lab-checkbox">
            <input id="workflow-force-refresh" type="checkbox">
            <span>Force refresh market data</span>
          </label>
          <label class="rl-lab-checkbox">
            <input id="workflow-submit-orders" type="checkbox" checked>
            <span>Submit paper orders</span>
          </label>
        </div>

        <div class="rl-lab-actions">
          <button class="btn btn-primary" id="rl-run-hybrid-workflow">Run Hybrid Paper Workflow</button>
          <button class="btn btn-ghost" id="rl-open-workflow-execution">Open Execution Monitor</button>
        </div>

        <div class="rl-lab-output" id="rl-workflow-output">
          <div class="rl-lab-output__title">Workflow ready</div>
          <div class="rl-lab-output__body">Default route submits at most 2 paper orders with 1.00 USD notional only after gates pass.</div>
        </div>
      </div>
    </section>

    <div class="grid-2 rl-lab-main-grid">
      <section class="card">
        <div class="card-header">
          <div>
            <span class="card-title">${c('datasetBuilderTitle')}</span>
            <div class="run-panel__sub">${c('datasetBuilderSub')}</div>
          </div>
        </div>
        <div class="card-body rl-lab-form">
          <div class="form-row">
            <div class="form-group">
              <label class="form-label">Recipe</label>
              <select class="form-select" id="rl-recipe"></select>
            </div>
            <div class="form-group">
              <label class="form-label">Dataset Name</label>
              <input class="form-input" id="rl-dataset-name" placeholder="l1_price_tech-pack">
            </div>
          </div>

          <div class="form-group">
            <label class="form-label">Symbols</label>
            <input class="form-input" id="rl-symbols" value="NVDA, MSFT, AAPL, NEE" placeholder="NVDA, MSFT, AAPL, NEE">
          </div>

          <div class="form-row">
            <div class="form-group">
              <label class="form-label">Bars / Symbol</label>
              <input class="form-input" id="rl-limit" type="number" min="60" value="240">
            </div>
            <div class="form-group">
              <label class="form-label">Quick Search Trials</label>
              <input class="form-input" id="rl-search-trials" type="number" min="1" value="5">
            </div>
          </div>

          <div class="form-row">
            <div class="form-group">
              <label class="form-label">Quick Search Steps</label>
              <input class="form-input" id="rl-search-steps" type="number" min="20" value="120">
            </div>
            <div class="form-group">
              <label class="form-label">Action Type</label>
              <select class="form-select" id="rl-action-type">
                <option value="continuous">continuous</option>
                <option value="discrete">discrete</option>
              </select>
            </div>
          </div>

          <div class="rl-lab-checkbox">
            <input id="rl-include-esg" type="checkbox" checked>
            <label for="rl-include-esg">Enrich with ESG / house-score features when available</label>
          </div>

          <div class="rl-lab-actions">
            <button class="btn btn-ghost" id="rl-build-market">Build Market Dataset</button>
            <button class="btn btn-ghost" id="rl-build-recipe">Build Recipe Dataset</button>
            <button class="btn btn-primary" id="rl-search-recipe">Search Best Params</button>
          </div>

          <div class="rl-lab-output" id="rl-dataset-output"></div>
        </div>
      </section>

      <section class="card">
        <div class="card-header">
          <div>
            <span class="card-title">${c('trainBacktestTitle')}</span>
            <div class="run-panel__sub">${c('trainBacktestSub')}</div>
          </div>
        </div>
        <div class="card-body rl-lab-form">
          <div class="form-group">
            <label class="form-label">Dataset Path</label>
            <input class="form-input" id="rl-dataset-path" value="" placeholder="Latest real dataset path will appear here">
          </div>

          <div class="form-row">
            <div class="form-group">
              <label class="form-label">Algorithm</label>
              <select class="form-select" id="rl-algorithm">
                <option value="hybrid_frontier">hybrid_frontier</option>
                <option value="sac">sac</option>
                <option value="ppo">ppo</option>
                <option value="dqn">dqn</option>
                <option value="cql">cql</option>
                <option value="iql">iql</option>
                <option value="decision_transformer">decision_transformer</option>
                <option value="world_model">world_model</option>
              </select>
            </div>
            <div class="form-group">
              <label class="form-label">Experiment Group</label>
              <select class="form-select" id="rl-group"></select>
            </div>
          </div>

          <div class="form-row">
            <div class="form-group">
              <label class="form-label">Seed</label>
              <input class="form-input" id="rl-seed" type="number" value="42">
            </div>
            <div class="form-group">
              <label class="form-label">Episodes</label>
              <input class="form-input" id="rl-episodes" type="number" min="1" value="30">
            </div>
            <div class="form-group">
              <label class="form-label">Total Steps</label>
              <input class="form-input" id="rl-total-steps" type="number" min="1" value="100">
            </div>
          </div>

          <div class="rl-lab-param-grid">
            <div class="form-group">
              <label class="form-label">Learning Rate</label>
              <input class="form-input" id="rl-hp-learning-rate" value="3e-4">
            </div>
            <div class="form-group">
              <label class="form-label">Gamma</label>
              <input class="form-input" id="rl-hp-gamma" value="0.99">
            </div>
            <div class="form-group">
              <label class="form-label">Batch Size</label>
              <input class="form-input" id="rl-hp-batch-size" type="number" value="128">
            </div>
            <div class="form-group">
              <label class="form-label">Buffer Size</label>
              <input class="form-input" id="rl-hp-buffer-size" type="number" value="100000">
            </div>
            <div class="form-group">
              <label class="form-label">Learning Starts</label>
              <input class="form-input" id="rl-hp-learning-starts" type="number" value="500">
            </div>
            <div class="form-group">
              <label class="form-label">Hidden Dim</label>
              <input class="form-input" id="rl-hp-hidden-dim" type="number" value="256">
            </div>
            <div class="form-group">
              <label class="form-label">Tau</label>
              <input class="form-input" id="rl-hp-tau" value="0.005">
            </div>
            <div class="form-group">
              <label class="form-label">Window Size</label>
              <input class="form-input" id="rl-hp-window-size" type="number" value="20">
            </div>
          </div>

          <div class="form-group">
            <label class="form-label">Notes</label>
            <textarea class="form-textarea" id="rl-notes" placeholder="Experiment note for paper / ablation / walk-forward context"></textarea>
          </div>

          <div class="rl-lab-actions">
            <button class="btn btn-ghost" id="rl-run-backtest">Backtest Latest</button>
            <button class="btn btn-primary" id="rl-run-train">Train Policy</button>
          </div>

          <div class="rl-lab-output" id="rl-train-output"></div>
        </div>
      </section>
    </div>

    <div class="grid-2 rl-lab-main-grid">
      <section class="card">
        <div class="card-header">
          <span class="card-title">Recipe + Search Status</span>
        </div>
        <div class="card-body">
          <div id="rl-recipe-state"></div>
        </div>
      </section>

      <section class="card">
        <div class="card-header">
          <span class="card-title">Experiment Protocol</span>
        </div>
        <div class="card-body">
          <div id="rl-protocol"></div>
        </div>
      </section>
    </div>

    <div class="grid-2 rl-lab-main-grid">
      <section class="card">
        <div class="card-header">
          <span class="card-title">Recent Runs</span>
        </div>
        <div class="card-body">
          <div class="rl-lab-table-wrap">
            <table class="rl-lab-table">
              <thead>
                <tr>
                  <th>Run</th>
                  <th>Algo</th>
                  <th>Status</th>
                  <th>Phase</th>
                  <th>Checkpoint</th>
                  <th>Promote</th>
                </tr>
              </thead>
              <tbody id="rl-runs-body"></tbody>
            </table>
          </div>
        </div>
      </section>

      <section class="results-panel rl-lab-results">
        <div class="results-panel__header">
          <span class="card-title">Latest Payload</span>
        </div>
        <div class="results-panel__body">
          <pre class="rl-lab-log" id="rl-latest-payload">Waiting for RL actions...</pre>
        </div>
      </section>
    </div>
    </div>
  `;
}

function bindEvents() {
  query('#rl-refresh')?.addEventListener('click', () => loadOverview(true));
  query('#rl-open-execution')?.addEventListener('click', async () => {
    recordUiAuditEvent('rl_open_execution', '#rl-open-execution', { route: '/rl-lab' }, { route: '/execution' });
    await router.navigate('/execution');
  });
  query('#rl-build-market')?.addEventListener('click', () => handleBuildMarket());
  query('#rl-build-recipe')?.addEventListener('click', () => handleBuildRecipe());
  query('#rl-search-recipe')?.addEventListener('click', () => handleSearchRecipe());
  query('#rl-run-train')?.addEventListener('click', () => handleTrain());
  query('#rl-run-backtest')?.addEventListener('click', () => handleBacktest());
  query('#rl-run-hybrid-workflow')?.addEventListener('click', () => handleHybridWorkflow());
  query('#rl-open-workflow-execution')?.addEventListener('click', async () => {
    recordUiAuditEvent('rl_open_workflow_execution', '#rl-open-workflow-execution', { route: '/rl-lab' }, { route: '/execution' });
    await router.navigate('/execution');
  });
  query('#rl-runs-body')?.addEventListener('click', (event) => {
    const button = event.target.closest('[data-promote-run]');
    if (!button) return;
    handlePromote(button.getAttribute('data-promote-run'));
  });
  query('#rl-recipe')?.addEventListener('change', (event) => {
    _state.selectedRecipeKey = event.target.value;
    applyRecipeDefaults();
    renderRecipeState();
    updateAuditState();
    recordUiAuditEvent('rl_recipe_change', '#rl-recipe', {}, { recipe_key: _state.selectedRecipeKey });
  });
}

async function loadOverview(withToast = false) {
  try {
    const overview = await api.quantRL.overview();
    _state.overview = overview;
    renderOverview();
    const datasetInput = query('#rl-dataset-path');
    if (datasetInput && !datasetInput.value.trim()) {
      datasetInput.value = latestPath(overview.latest_dataset) || '';
    }
    if (withToast) toast.success('RL lab refreshed', 'Latest overview loaded');
    recordUiAuditEvent('rl_refresh', '#rl-refresh', {}, { run_count: (overview.runs || []).length });
  } catch (error) {
    _state.overview = {
      runs: [],
      recipes: [],
      experiment_groups: [],
      output_status: {},
      artifact_health: {},
      services: {},
      latest_dataset: null,
      latest_checkpoint: null,
      latest_report: null,
      paper_execution_bridge: { route: '#/execution' },
    };
    renderOverview();
    const node = query('#rl-train-output');
    if (node) {
      node.innerHTML = `
        <div class="rl-lab-output__title">RL Lab status unavailable</div>
        <div class="rl-lab-output__body">${escapeHtml(error.message || 'Unknown error')}</div>
      `;
    }
    if (withToast) toast.error('RL lab refresh failed', error.message || 'Unknown error');
  }
}

function renderOverview() {
  const overview = _state.overview || {};
  renderServiceBadges(overview.services || {});
  renderStats(overview);
  renderGroups(overview.experiment_groups || []);
  renderRecipes(overview.recipes || []);
  renderProtocol(overview);
  renderRuns((overview.runs || []).slice(0, 12));
  renderRecipeState();
  updateAuditState();
}

function renderServiceBadges(services) {
  const node = query('#rl-service-badges');
  if (!node) return;
  const market = services.market_data || {};
  node.innerHTML = [
    buildBadge(services.alpaca_ready, 'Alpaca Ready'),
    buildBadge(services.alpha_vantage_ready, 'AlphaVantage Ready'),
    buildBadge(services.esg_scoring_ready, 'House ESG Ready'),
    buildBadge(market.alpaca_market_data_ready, 'Alpaca Market Feed'),
  ].join('');
}

function renderStats(overview) {
  const stats = [
    {
      label: c('trackedRuns'),
      value: String((overview.runs || []).length || 0),
      detail: c('trackedDetail'),
    },
    {
      label: c('recipeCatalog'),
      value: String((overview.recipes || []).length || 0),
      detail: c('recipeDetail'),
    },
    {
      label: c('manifests'),
      value: String(((overview.output_status || {}).dataset_manifests) || 0),
      detail: c('manifestsDetail'),
    },
    {
      label: c('metrics'),
      value: String(((overview.output_status || {}).metrics_files) || 0),
      detail: c('metricsDetail'),
    },
    {
      label: c('latestDataset'),
      value: latestPath(overview.latest_dataset) || c('awaiting'),
      detail: (overview.artifact_health || {}).dataset_ready ? c('latestDatasetReady') : c('latestDatasetPending'),
      path: true,
    },
    {
      label: c('latestCheckpoint'),
      value: latestPath(overview.latest_checkpoint) || c('awaiting'),
      detail: (overview.artifact_health || {}).checkpoint_ready ? c('latestCheckpointReady') : c('latestCheckpointPending'),
      path: true,
    },
    {
      label: c('latestReport'),
      value: latestPath(overview.latest_report) || c('awaiting'),
      detail: (overview.artifact_health || {}).report_ready ? c('latestReportReady') : c('latestReportPending'),
      path: true,
    },
    {
      label: c('paperExecution'),
      value: (overview.paper_execution_bridge || {}).route || '#/execution',
      detail: c('paperExecutionDetail'),
      path: true,
    },
  ];
  const node = query('#rl-stats');
  if (!node) return;
  node.innerHTML = stats.map((item) => `
    <article class="metric-card rl-lab-stat">
      <div class="metric-label">${escapeHtml(item.label)}</div>
      <div class="metric-value rl-lab-stat__value${item.path ? ' rl-lab-stat__value--path' : ''}" title="${escapeHtml(item.value)}">${escapeHtml(item.value)}</div>
      <div class="rl-lab-stat__detail">${escapeHtml(item.detail)}</div>
    </article>
  `).join('');
}

function renderGroups(groups) {
  const select = query('#rl-group');
  if (!select) return;
  const options = ['<option value="">None / ad-hoc run</option>'].concat(
    groups.map((group) => `<option value="${escapeHtml(group.key)}">${escapeHtml(group.label)} · ${escapeHtml(group.algorithm)}</option>`)
  );
  select.innerHTML = options.join('');
  if (!select.value) {
    select.value = 'OURS_full';
  }
}

function renderRecipes(recipes) {
  const select = query('#rl-recipe');
  if (!select) return;
  if (!recipes.length) {
    select.innerHTML = '<option value="">No recipes</option>';
    return;
  }
  if (!recipes.find((recipe) => recipe.key === _state.selectedRecipeKey)) {
    _state.selectedRecipeKey = recipes[0].key;
  }
  select.innerHTML = recipes.map((recipe) => `
    <option value="${escapeHtml(recipe.key)}">${escapeHtml(recipe.key)} · ${escapeHtml(recipe.label)}</option>
  `).join('');
  select.value = _state.selectedRecipeKey;
  applyRecipeDefaults();
}

function applyRecipeDefaults() {
  const recipe = activeRecipe();
  if (!recipe) return;
  const currentDatasetName = query('#rl-dataset-name')?.value?.trim();
  const currentSymbols = query('#rl-symbols')?.value?.trim();
  if (!currentDatasetName || currentDatasetName === defaultDatasetName(_state.selectedRecipeKey)) {
    query('#rl-dataset-name').value = defaultDatasetName(recipe.key);
  }
  if (!currentSymbols || currentSymbols === 'NVDA, MSFT, AAPL, NEE') {
    query('#rl-symbols').value = (recipe.symbols || []).join(', ');
  }
  if (query('#rl-algorithm')) {
    query('#rl-algorithm').value = recipe.algorithm || 'hybrid_frontier';
  }
  if (query('#rl-action-type')) {
    query('#rl-action-type').value = ['dqn', 'cql'].includes(recipe.algorithm) ? 'discrete' : 'continuous';
  }
  if (query('#rl-include-esg')) {
    query('#rl-include-esg').checked = (recipe.layers || []).includes('house_esg');
  }
}

function renderProtocol(overview) {
  const protocol = overview.protocol || {};
  const output = overview.output_status || {};
  const node = query('#rl-protocol');
  if (!node) return;
  const requirements = (protocol.recording_requirements || [])
    .map((item) => `<li>${escapeHtml(item)}</li>`)
    .join('');
  const groups = (overview.experiment_groups || [])
    .map((group) => `<div class="rl-lab-protocol__chip">${escapeHtml(group.label)} · ${escapeHtml(group.family)}</div>`)
    .join('');

  node.innerHTML = `
    <div class="rl-lab-protocol">
      <div class="rl-lab-protocol__title">${escapeHtml(protocol.paper_title || 'Experiment protocol')}</div>
      <div class="rl-lab-protocol__meta">Target journal: ${escapeHtml(protocol.target_journal || 'N/A')}</div>
      <div class="rl-lab-protocol__meta">Output root: ${escapeHtml(output.output_root || '')}</div>
      <div class="rl-lab-protocol__section">
        <div class="rl-lab-protocol__label">Required outputs</div>
        <ul>${requirements}</ul>
      </div>
      <div class="rl-lab-protocol__section">
        <div class="rl-lab-protocol__label">Experiment groups</div>
        <div class="rl-lab-protocol__chips">${groups}</div>
      </div>
    </div>
  `;
}

function renderRecipeState() {
  const node = query('#rl-recipe-state');
  if (!node) return;
  const recipe = activeRecipe();
  const search = _state.lastSearch || null;
  const dataset = _state.lastDataset || null;
  const latestDataset = _state.overview?.latest_dataset || null;
  const latestCheckpoint = _state.overview?.latest_checkpoint || null;
  const latestReport = _state.overview?.latest_report || null;
  const artifactHealth = _state.overview?.artifact_health || {};
  const remoteSync = _state.overview?.remote_sync_status || {};
  const layers = recipe?.layers || [];
  const bestParams = search?.best_params || {};
  const trials = (search?.trials || []).slice(0, 5);

  const trialRows = trials.length
    ? trials.map((trial) => `
        <div class="rl-lab-kv">
          <span>T${escapeHtml(trial.trial_index)}</span>
          <span>Sharpe ${escapeHtml(Number(trial.sharpe || 0).toFixed(3))}</span>
          <span>DD ${escapeHtml(Number(trial.max_drawdown || 0).toFixed(3))}</span>
        </div>
      `).join('')
    : '<div class="rl-lab-empty">No search trials yet</div>';

  node.innerHTML = `
    <div class="rl-lab-state-card">
      <div class="rl-lab-state-card__row">
        <div>
          <div class="rl-lab-protocol__label">Active recipe</div>
          <div class="rl-lab-state-card__title">${escapeHtml(recipe?.label || 'No recipe')}</div>
        </div>
        <div class="rl-lab-state-pill">${escapeHtml(recipe?.algorithm || '--')}</div>
      </div>

      <div class="rl-lab-chip-list">
        ${layers.map((layer) => `<span class="rl-lab-protocol__chip">${escapeHtml(layer)}</span>`).join('')}
      </div>

      <div class="rl-lab-state-card__grid">
        <div>
          <div class="rl-lab-protocol__label">Dataset path</div>
          <div class="rl-lab-path">${escapeHtml(latestPath(dataset) || latestPath(latestDataset) || query('#rl-dataset-path')?.value || '--')}</div>
        </div>
        <div>
          <div class="rl-lab-protocol__label">Search backend</div>
          <div>${escapeHtml(search?.search_backend || 'not run')}</div>
        </div>
      </div>

      <div class="rl-lab-state-card__grid">
        <div>
          <div class="rl-lab-protocol__label">Latest checkpoint</div>
          <div class="rl-lab-path">${escapeHtml(latestPath(latestCheckpoint) || 'Awaiting remote artifact')}</div>
        </div>
        <div>
          <div class="rl-lab-protocol__label">Latest report</div>
          <div class="rl-lab-path">${escapeHtml(latestPath(latestReport) || 'Awaiting remote artifact')}</div>
        </div>
      </div>

      <div class="rl-lab-state-card__grid">
        <div>
          <div class="rl-lab-protocol__label">Artifact health</div>
          <div>${escapeHtml(JSON.stringify(artifactHealth))}</div>
        </div>
        <div>
          <div class="rl-lab-protocol__label">Remote sync</div>
          <div>${escapeHtml(remoteSync.status || 'unknown')}</div>
        </div>
      </div>

      <div class="rl-lab-protocol__section">
        <div class="rl-lab-protocol__label">Best params</div>
        <pre class="rl-lab-codeblock">${escapeHtml(JSON.stringify(bestParams, null, 2) || '{}')}</pre>
      </div>

      <div class="rl-lab-protocol__section">
        <div class="rl-lab-protocol__label">Top trials</div>
        <div class="rl-lab-kv-list">${trialRows}</div>
      </div>
    </div>
  `;
}

function renderRuns(runs) {
  const node = query('#rl-runs-body');
  if (!node) return;
  if (!runs.length) {
    node.innerHTML = '<tr><td colspan="6" class="rl-lab-empty">No RL runs yet</td></tr>';
    return;
  }
  node.innerHTML = runs.map((run) => {
    const checkpointPath = ((run.artifacts || {}).checkpoint_path) || '--';
    const eligibility = run.eligibility_status || 'review';
    const canPromote = eligibility === 'pass';
    return `
      <tr>
        <td>
          <div>${escapeHtml(run.run_id || '')}</div>
          <div class="rl-lab-path">${escapeHtml(run.dataset_id || '')}</div>
        </td>
        <td>${escapeHtml(run.algorithm || '')}</td>
        <td>${escapeHtml(run.status || '')}<div class="rl-lab-path">${escapeHtml(eligibility)} / ${escapeHtml(run.promotion_status || 'research_only')}</div></td>
        <td>${escapeHtml(run.phase || '')}</td>
        <td class="rl-lab-path">${escapeHtml(checkpointPath)}</td>
        <td>
          <button class="btn btn-ghost btn-sm" data-promote-run="${escapeHtml(run.run_id || '')}" ${canPromote ? '' : 'disabled'}>
            ${escapeHtml(canPromote ? 'Promote' : 'Blocked')}
          </button>
        </td>
      </tr>
    `;
  }).join('');
}

async function handleBuildMarket() {
  const payload = {
    symbols: readSymbols(query('#rl-symbols')?.value),
    dataset_name: query('#rl-dataset-name')?.value || null,
    limit: Number(query('#rl-limit')?.value || 240),
    include_esg: Boolean(query('#rl-include-esg')?.checked),
    force_refresh: false,
  };
  try {
    const result = await api.quantRL.buildDataset(payload);
    _state.lastDataset = result;
    _state.lastPayload = result;
    query('#rl-dataset-path').value = latestPath(result);
    renderActionOutput('#rl-dataset-output', result);
    renderRecipeState();
    renderLatestPayload();
    updateAuditState();
    toast.success('Market dataset ready', result.primary_dataset_path || '');
    recordUiAuditEvent('rl_market_dataset_build', '#rl-build-market', payload, result);
    await loadOverview(false);
  } catch (error) {
    toast.error('Market dataset failed', error.message || 'Unknown error');
  }
}

async function handleBuildRecipe() {
  const recipe = activeRecipe();
  if (!recipe) {
    toast.warning('Recipe unavailable', 'Refresh the RL lab first.');
    return;
  }
  const payload = {
    recipe_key: recipe.key,
    dataset_name: query('#rl-dataset-name')?.value || null,
    limit: Number(query('#rl-limit')?.value || 240),
    force_refresh: false,
    symbols: readSymbols(query('#rl-symbols')?.value),
  };
  try {
    const result = await api.quantRL.buildRecipeDataset(payload);
    _state.lastDataset = result;
    _state.lastPayload = result;
    query('#rl-dataset-path').value = latestPath(result);
    renderActionOutput('#rl-dataset-output', result);
    renderRecipeState();
    renderLatestPayload();
    updateAuditState();
    toast.success('Recipe dataset ready', result.merged_dataset_path || result.primary_dataset_path || '');
    recordUiAuditEvent('rl_recipe_dataset_build', '#rl-build-recipe', payload, result);
    await loadOverview(false);
  } catch (error) {
    toast.error('Recipe dataset failed', error.message || 'Unknown error');
  }
}

async function handleSearchRecipe() {
  const recipe = activeRecipe();
  if (!recipe) {
    toast.warning('Recipe unavailable', 'Refresh the RL lab first.');
    return;
  }
  const payload = {
    recipe_key: recipe.key,
    dataset_path: query('#rl-dataset-path')?.value || null,
    trials: Number(query('#rl-search-trials')?.value || 5),
    quick_steps: Number(query('#rl-search-steps')?.value || 120),
    action_type: query('#rl-action-type')?.value || 'continuous',
    seed: Number(query('#rl-seed')?.value || 42),
  };
  try {
    const result = await api.quantRL.search(payload);
    _state.lastSearch = result;
    _state.lastPayload = result;
    applySearchResult(result);
    renderActionOutput('#rl-dataset-output', result);
    renderRecipeState();
    renderLatestPayload();
    updateAuditState();
    if (['blocked', 'degraded'].includes(String(result.status || '').toLowerCase())) {
      toast.warning('Recipe search blocked', result.reason || result.recipe_key || '');
    } else {
      toast.success('Recipe search complete', `${result.recipe_key} · trial ${result.best_trial}`);
    }
    recordUiAuditEvent('rl_recipe_search', '#rl-search-recipe', payload, {
      recipe_key: result.recipe_key,
      best_trial: result.best_trial,
      best_val_sharpe: result.best_val_sharpe,
    });
    await loadOverview(false);
  } catch (error) {
    toast.error('Recipe search failed', error.message || 'Unknown error');
  }
}

function applySearchResult(result) {
  if (!result) return;
  const best = result.best_params || {};
  if (query('#rl-algorithm')) query('#rl-algorithm').value = result.algorithm || query('#rl-algorithm').value;
  if (query('#rl-dataset-path') && result.dataset_path) query('#rl-dataset-path').value = result.dataset_path;
  setInputValue('#rl-hp-learning-rate', best.learning_rate);
  setInputValue('#rl-hp-gamma', best.gamma);
  setInputValue('#rl-hp-batch-size', best.batch_size);
  setInputValue('#rl-hp-buffer-size', best.buffer_size);
  setInputValue('#rl-hp-learning-starts', best.learning_starts);
  setInputValue('#rl-hp-hidden-dim', Array.isArray(best.hidden_dims) ? best.hidden_dims[0] : best.hidden_dim);
  setInputValue('#rl-hp-tau', best.tau);
}

async function handleTrain() {
  const datasetPath = resolveDatasetPath();
  if (!datasetPath) {
    toast.warning('Dataset missing', 'Build or sync a real dataset before training.');
    return;
  }
  const payload = {
    algorithm: query('#rl-algorithm')?.value || 'hybrid_frontier',
    dataset_path: datasetPath,
    action_type: query('#rl-action-type')?.value || 'continuous',
    episodes: Number(query('#rl-episodes')?.value || 30),
    total_steps: Number(query('#rl-total-steps')?.value || 100),
    experiment_group: query('#rl-group')?.value || null,
    seed: parseMaybeNumber(query('#rl-seed')?.value),
    notes: query('#rl-notes')?.value || null,
    trainer_hparams: readTrainerHparams(),
  };
  try {
    const result = await api.quantRL.train(payload);
    _state.lastTrain = result;
    _state.lastPayload = result;
    renderActionOutput('#rl-train-output', result);
    renderLatestPayload();
    updateAuditState();
    toast.success('RL training complete', result.run_id || '');
    recordUiAuditEvent('rl_train', '#rl-run-train', payload, { run_id: result.run_id, checkpoint_path: result.checkpoint_path });
    await loadOverview(false);
  } catch (error) {
    toast.error('RL training failed', error.message || 'Unknown error');
  }
}

async function handleBacktest() {
  const algorithm = query('#rl-algorithm')?.value || 'hybrid_frontier';
  if (['cql', 'decision_transformer'].includes(algorithm)) {
    toast.warning('Backtest not wired for this algorithm yet', `${algorithm} can train, but use hybrid_frontier / iql / world_model / sac / ppo / dqn for backtest.`);
    return;
  }
  const datasetPath = resolveDatasetPath();
  if (!datasetPath) {
    toast.warning('Dataset missing', 'Build or sync a real dataset before backtesting.');
    return;
  }
  const payload = {
    algorithm,
    dataset_path: datasetPath,
    action_type: query('#rl-action-type')?.value || 'continuous',
    checkpoint_path: (_state.lastTrain || {}).checkpoint_path || null,
    experiment_group: query('#rl-group')?.value || null,
    seed: parseMaybeNumber(query('#rl-seed')?.value),
    notes: query('#rl-notes')?.value || null,
  };
  try {
    const result = await api.quantRL.backtest(payload);
    _state.lastBacktest = result;
    _state.lastPayload = result;
    renderActionOutput('#rl-train-output', result);
    renderLatestPayload();
    updateAuditState();
    const resultStatus = result.metrics?.status || result.config?.status || 'ready';
    if (['blocked', 'degraded'].includes(String(resultStatus).toLowerCase())) {
      toast.warning('RL backtest blocked', result.metrics?.reason || result.config?.reason || result.run_id || '');
    } else {
      toast.success('RL backtest complete', result.run_id || '');
    }
    recordUiAuditEvent('rl_backtest', '#rl-run-backtest', payload, { run_id: result.run_id, artifacts: result.artifacts || {} });
    await loadOverview(false);
  } catch (error) {
    toast.error('RL backtest failed', error.message || 'Unknown error');
  }
}

async function handleHybridWorkflow() {
  const button = query('#rl-run-hybrid-workflow');
  const universe = readSymbols(query('#workflow-universe')?.value);
  const payload = {
    universe,
    benchmark: 'SPY',
    capital_base: Number(query('#workflow-capital')?.value || 1000000),
    strategy_mode: 'hybrid_p1_p2_rl',
    rl_algorithm: 'sac',
    rl_action_type: 'continuous',
    submit_orders: Boolean(query('#workflow-submit-orders')?.checked),
    mode: 'paper',
    broker: 'alpaca',
    max_orders: Number(query('#workflow-max-orders')?.value || 2),
    per_order_notional: parseMaybeNumber(query('#workflow-notional')?.value) ?? 1.0,
    allow_synthetic_execution: false,
    force_refresh: Boolean(query('#workflow-force-refresh')?.checked),
  };

  if (button) {
    button.disabled = true;
    button.textContent = 'Running...';
  }
  renderWorkflowOutput({ status: 'running', workflow_id: 'pending', steps: {}, blockers: [], warnings: ['Workflow is running.'] });

  try {
    const result = await api.workflows.runPaperStrategy(payload);
    _state.lastWorkflow = result;
    _state.lastPayload = result;
    persistWorkflowShortcut(result);
    renderWorkflowOutput(result);
    renderLatestPayload();
    updateAuditState();
    const submitted = Number(result.submitted_count || 0);
    if (result.status === 'submitted') {
      toast.success('Hybrid workflow submitted', `${submitted} paper orders routed`);
    } else if (result.status === 'blocked') {
      toast.warning('Hybrid workflow blocked', (result.blockers || [])[0] || 'Review workflow blockers');
    } else {
      toast.success('Hybrid workflow planned', result.workflow_id || '');
    }
    recordUiAuditEvent('rl_hybrid_paper_workflow', '#rl-run-hybrid-workflow', payload, {
      workflow_id: result.workflow_id,
      status: result.status,
      execution_id: result.execution_id,
      submitted_count: result.submitted_count,
    });
  } catch (error) {
    renderWorkflowOutput({ status: 'failed', workflow_id: 'request_failed', blockers: [error.message || 'Unknown error'], steps: {} });
    toast.error('Hybrid workflow failed', error.message || 'Unknown error');
  } finally {
    if (button) {
      button.disabled = false;
      button.textContent = 'Run Hybrid Paper Workflow';
    }
  }
}

async function handlePromote(runId) {
  if (!runId) return;
  const payload = {
    run_id: runId,
    strategy_id: 'rl_timing_overlay',
    required_data_tier: 'l2',
  };
  try {
    const result = await api.quantRL.promote(payload);
    _state.lastPayload = result;
    renderActionOutput('#rl-train-output', result);
    renderLatestPayload();
    toast.success('RL promotion evaluated', `${result.promotion_status} / ${result.eligibility_status}`);
    recordUiAuditEvent('rl_promote', '[data-promote-run]', payload, result);
    await loadOverview(false);
  } catch (error) {
    toast.error('RL promotion failed', error.message || 'Unknown error');
  }
}

function readTrainerHparams() {
  const payload = {};
  appendMaybeNumber(payload, 'learning_rate', query('#rl-hp-learning-rate')?.value);
  appendMaybeNumber(payload, 'gamma', query('#rl-hp-gamma')?.value);
  appendMaybeNumber(payload, 'batch_size', query('#rl-hp-batch-size')?.value, true);
  appendMaybeNumber(payload, 'buffer_size', query('#rl-hp-buffer-size')?.value, true);
  appendMaybeNumber(payload, 'learning_starts', query('#rl-hp-learning-starts')?.value, true);
  appendMaybeNumber(payload, 'hidden_dim', query('#rl-hp-hidden-dim')?.value, true);
  appendMaybeNumber(payload, 'tau', query('#rl-hp-tau')?.value);
  appendMaybeNumber(payload, 'window_size', query('#rl-hp-window-size')?.value, true);
  if (_state.lastSearch?.best_trial != null) {
    payload.best_trial_index = _state.lastSearch.best_trial;
  }
  if (_state.lastSearch?.best_val_sharpe != null) {
    payload.best_val_sharpe = _state.lastSearch.best_val_sharpe;
  }
  return payload;
}

function appendMaybeNumber(target, key, value, integer = false) {
  if (value === null || value === undefined || value === '') return;
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return;
  target[key] = integer ? Math.round(numeric) : numeric;
}

function setInputValue(selector, value) {
  if (value === null || value === undefined || value === '') return;
  const input = query(selector);
  if (input) input.value = String(value);
}

function persistWorkflowShortcut(result) {
  try {
    setVersionedStorageValue(window.localStorage, WORKFLOW_LATEST_STORAGE_KEY, {
      workflow_id: result.workflow_id || '',
      status: result.status || '',
      execution_id: result.execution_id || '',
      submitted_count: Number(result.submitted_count || 0),
      generated_at: result.generated_at || new Date().toISOString(),
    }, WORKFLOW_LATEST_SCHEMA_VERSION);
  } catch (_ignore) {
    // Local storage can be unavailable in private contexts.
  }
}

function renderWorkflowOutput(payload) {
  const node = query('#rl-workflow-output');
  if (!node) return;
  const steps = payload.steps || {};
  const blockers = payload.blockers || [];
  const warnings = payload.warnings || [];
  const actions = payload.next_actions || [];
  const gate = payload.gate_snapshot || {};
  const model = payload.model_status || {};
  const orders = payload.order_summary || [];

  const stepRows = [
    ['Model status', 'model_status'],
    ['P1 report', 'p1_report'],
    ['P2 decision', 'p2_report'],
    ['RL backtest', 'rl_backtest'],
    ['Quant backtest', 'quant_backtest'],
    ['Tearsheet', 'tearsheet'],
    ['Paper gate', 'paper_gate'],
    ['Paper execution', 'paper_execution'],
  ].map(([label, key]) => {
    const step = steps[key] || {};
    return `<div class="rl-lab-kv"><span>${escapeHtml(label)}</span><span>${escapeHtml(step.status || 'pending')}</span><span>${escapeHtml(step.report_id || step.run_id || step.backtest_id || step.execution_id || step.broker_status || '')}</span></div>`;
  }).join('');

  const modelRows = [
    ['Alpha Ranker', model.alpha_ranker],
    ['P1 Suite', model.p1_suite],
    ['P2 Stack', model.p2_stack],
  ].map(([label, item]) => `<span class="rl-lab-protocol__chip">${escapeHtml(label)}: ${escapeHtml(modelReadyLabel(item))}</span>`).join('');

  const orderRows = orders.length
    ? orders.map((order) => `<div class="rl-lab-kv"><span>${escapeHtml(order.symbol || '--')}</span><span>${escapeHtml(order.status || '--')}</span><span>${escapeHtml(order.notional || order.qty || '--')}</span></div>`).join('')
    : '<div class="rl-lab-empty">No submitted order summary yet</div>';

  node.innerHTML = `
    <div class="rl-lab-output__title">${escapeHtml(payload.workflow_id || 'Workflow')} / ${escapeHtml(payload.status || 'pending')}</div>
    <div class="rl-lab-output__body">
      <div class="rl-lab-chip-list">${modelRows}</div>
      <div class="rl-lab-kv-list">${stepRows}</div>
      <div class="rl-lab-state-card__grid">
        <div>
          <div class="rl-lab-protocol__label">Gate snapshot</div>
          <pre class="rl-lab-codeblock">${escapeHtml(JSON.stringify(gate, null, 2))}</pre>
        </div>
        <div>
          <div class="rl-lab-protocol__label">Execution</div>
          <div>Submitted: ${escapeHtml(payload.submitted_count || 0)}</div>
          <div class="rl-lab-path">${escapeHtml(payload.execution_id || 'No execution id')}</div>
          <div class="rl-lab-kv-list">${orderRows}</div>
        </div>
      </div>
      ${renderWorkflowList('Blockers', blockers)}
      ${renderWorkflowList('Warnings', warnings)}
      ${renderWorkflowList('Next actions', actions)}
    </div>
  `;
}

function renderWorkflowList(title, items) {
  if (!items || !items.length) return '';
  return `
    <div class="rl-lab-protocol__section">
      <div class="rl-lab-protocol__label">${escapeHtml(title)}</div>
      <ul>${items.map((item) => `<li>${escapeHtml(item)}</li>`).join('')}</ul>
    </div>
  `;
}

function modelReadyLabel(item) {
  if (!item || typeof item !== 'object') return 'unknown';
  if (item.available === true || item.ready === true || item.loaded === true) return 'ready';
  if (item.available === false || item.ready === false) return 'blocked';
  if (item.backend || item.models || item.selector) return 'ready';
  return 'unknown';
}

function renderActionOutput(selector, payload) {
  const node = query(selector);
  if (!node) return;
  node.innerHTML = `
    <div class="rl-lab-output__title">${escapeHtml(payload.run_id || payload.recipe_key || payload.dataset_name || 'Result')}</div>
    <div class="rl-lab-output__body">${escapeHtml(compactSummary(payload))}</div>
  `;
}

function renderLatestPayload() {
  const node = query('#rl-latest-payload');
  if (!node) return;
  node.textContent = JSON.stringify(_state.lastPayload || { message: 'Waiting for RL actions...' }, null, 2);
}

function compactSummary(payload) {
  if (payload.workflow_id) {
    return `${payload.workflow_id} / ${payload.status || 'workflow'} / submitted ${payload.submitted_count || 0}`;
  }
  if (payload.run_id) {
    return `${payload.run_id} · ${payload.algorithm || 'run'} · ${Object.keys(payload.metrics || {}).length} metric fields`;
  }
  if (payload.recipe_key) {
    return `${payload.recipe_key} · ${payload.search_backend || 'recipe'} · best trial ${payload.best_trial ?? '--'} · Sharpe ${Number(payload.best_val_sharpe || 0).toFixed(3)}`;
  }
  if (payload.dataset_name) {
    return `${payload.dataset_name} · ${(payload.symbols || []).length} symbols · ${payload.primary_symbol || ''}`;
  }
  if (payload.dataset_path) {
    return `${payload.dataset_path} · ${payload.rows || 0} rows`;
  }
  return JSON.stringify(payload);
}

function buildBadge(active, label) {
  return `<span class="rl-lab-service ${active ? 'is-ready' : 'is-off'}">${escapeHtml(label)}</span>`;
}

function readSymbols(raw) {
  return String(raw || '')
    .split(/[,\s]+/)
    .map((item) => item.trim().toUpperCase())
    .filter(Boolean);
}

function parseMaybeNumber(value) {
  if (value === null || value === undefined || value === '') return null;
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}

function query(selector) {
  return _container ? _container.querySelector(selector) : null;
}

function escapeHtml(value) {
  const div = document.createElement('div');
  div.textContent = String(value ?? '');
  return div.innerHTML;
}
