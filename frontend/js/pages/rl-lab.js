import { api } from '../qtapi.js?v=8';
import { toast } from '../components/toast.js?v=8';
import { router } from '../router.js?v=8';
import { ensureUiAuditLog, recordUiAuditEvent } from '../modules/ui-audit.js?v=8';

let _container = null;
let _state = null;

function resetState() {
  _state = {
    overview: null,
    lastPayload: null,
    lastDataset: null,
    lastTrain: null,
    lastBacktest: null,
    lastSearch: null,
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
  await loadOverview(false);
}

export async function destroy() {
  _container = null;
  resetState();
}

function buildShell() {
  return `
    <div class="page-header">
      <div>
        <div class="page-header__title">RL Agent Lab</div>
        <div class="page-header__sub">Recipe datasets · quick search · full train · backtest artifacts · AutoDL handoff</div>
      </div>
      <div class="page-header__actions">
        <button class="btn btn-ghost btn-sm" id="rl-open-execution">Open Execution</button>
        <button class="btn btn-primary btn-sm" id="rl-refresh">Refresh Lab</button>
      </div>
    </div>

    <section class="card rl-lab-hero">
      <div class="card-body rl-lab-hero__body">
        <div class="rl-lab-hero__copy">
          <span class="badge rl-lab-badge">SCI Experiment Track</span>
          <h2>Turn recipe layers into a repeatable RL training loop.</h2>
          <p>Build datasets from the live market stack, search local best hyper-parameters, launch a full run, archive metrics, and hand the validated policy back into the execution layer.</p>
        </div>
        <div class="rl-lab-hero__channels" id="rl-service-badges"></div>
      </div>
    </section>

    <section class="rl-lab-stats" id="rl-stats"></section>

    <div class="grid-2 rl-lab-main-grid">
      <section class="card">
        <div class="card-header">
          <span class="card-title">Dataset Builder</span>
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
            <button class="btn btn-ghost" id="rl-build-demo">Generate Demo Dataset</button>
            <button class="btn btn-ghost" id="rl-build-market">Build Market Dataset</button>
            <button class="btn btn-ghost" id="rl-build-recipe">Build Recipe Dataset</button>
            <button class="btn btn-primary" id="rl-search-recipe">Search Best Params</button>
          </div>

          <div class="rl-lab-output" id="rl-dataset-output"></div>
        </div>
      </section>

      <section class="card">
        <div class="card-header">
          <span class="card-title">Training + Backtest</span>
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
  `;
}

function bindEvents() {
  query('#rl-refresh')?.addEventListener('click', () => loadOverview(true));
  query('#rl-open-execution')?.addEventListener('click', async () => {
    recordUiAuditEvent('rl_open_execution', '#rl-open-execution', { route: '/rl-lab' }, { route: '/execution' });
    await router.navigate('/execution');
  });
  query('#rl-build-demo')?.addEventListener('click', () => handleBuildDemo());
  query('#rl-build-market')?.addEventListener('click', () => handleBuildMarket());
  query('#rl-build-recipe')?.addEventListener('click', () => handleBuildRecipe());
  query('#rl-search-recipe')?.addEventListener('click', () => handleSearchRecipe());
  query('#rl-run-train')?.addEventListener('click', () => handleTrain());
  query('#rl-run-backtest')?.addEventListener('click', () => handleBacktest());
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
      label: 'Tracked Runs',
      value: String((overview.runs || []).length || 0),
      detail: 'SQLite + Supabase mirrored metadata',
    },
    {
      label: 'Recipe Catalog',
      value: String((overview.recipes || []).length || 0),
      detail: 'Six-stage AutoDL experiment ladder',
    },
    {
      label: 'Dataset Manifests',
      value: String(((overview.output_status || {}).dataset_manifests) || 0),
      detail: 'Experiment manual data lineage',
    },
    {
      label: 'Metrics Files',
      value: String(((overview.output_status || {}).metrics_files) || 0),
      detail: 'Per-run metrics.json archived',
    },
    {
      label: 'Latest Dataset',
      value: latestPath(overview.latest_dataset) || 'Awaiting remote artifact',
      detail: (overview.artifact_health || {}).dataset_ready ? 'Latest recipe/market dataset located' : 'No ready dataset found yet',
    },
    {
      label: 'Latest Checkpoint',
      value: latestPath(overview.latest_checkpoint) || 'Awaiting remote artifact',
      detail: (overview.artifact_health || {}).checkpoint_ready ? 'Checkpoint ready for reload' : 'Training artifact not synced yet',
    },
    {
      label: 'Latest Report',
      value: latestPath(overview.latest_report) || 'Awaiting remote artifact',
      detail: (overview.artifact_health || {}).report_ready ? 'Backtest/report artifact available' : 'Report artifact pending',
    },
    {
      label: 'Paper Execution',
      value: (overview.paper_execution_bridge || {}).route || '#/execution',
      detail: 'Validated models hand off into the main execution stack',
    },
  ];
  const node = query('#rl-stats');
  if (!node) return;
  node.innerHTML = stats.map((item) => `
    <article class="metric-card rl-lab-stat">
      <div class="metric-label">${escapeHtml(item.label)}</div>
      <div class="metric-value">${escapeHtml(item.value)}</div>
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
    node.innerHTML = '<tr><td colspan="5" class="rl-lab-empty">No RL runs yet</td></tr>';
    return;
  }
  node.innerHTML = runs.map((run) => {
    const checkpointPath = ((run.artifacts || {}).checkpoint_path) || '--';
    return `
      <tr>
        <td>${escapeHtml(run.run_id || '')}</td>
        <td>${escapeHtml(run.algorithm || '')}</td>
        <td>${escapeHtml(run.status || '')}</td>
        <td>${escapeHtml(run.phase || '')}</td>
        <td class="rl-lab-path">${escapeHtml(checkpointPath)}</td>
      </tr>
    `;
  }).join('');
}

async function handleBuildDemo() {
  const targetPath = query('#rl-dataset-path')?.value || 'storage/quant/generated/demo/market.csv';
  const before = { dataset_path: targetPath };
  try {
    const payload = await api.quantRL.buildDemoDataset({ target_path: targetPath, seed: 42, length: 1500 });
    _state.lastDataset = payload;
    _state.lastPayload = payload;
    query('#rl-dataset-path').value = payload.dataset_path || targetPath;
    renderActionOutput('#rl-dataset-output', payload);
    renderRecipeState();
    renderLatestPayload();
    updateAuditState();
    toast.success('Demo dataset ready', payload.dataset_path || '');
    recordUiAuditEvent('rl_demo_build', '#rl-build-demo', before, payload);
    await loadOverview(false);
  } catch (error) {
    toast.error('Demo dataset failed', error.message || 'Unknown error');
  }
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
    toast.success('Recipe search complete', `${result.recipe_key} · trial ${result.best_trial}`);
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
    use_demo_if_missing: false,
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
    toast.success('RL backtest complete', result.run_id || '');
    recordUiAuditEvent('rl_backtest', '#rl-run-backtest', payload, { run_id: result.run_id, artifacts: result.artifacts || {} });
    await loadOverview(false);
  } catch (error) {
    toast.error('RL backtest failed', error.message || 'Unknown error');
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
