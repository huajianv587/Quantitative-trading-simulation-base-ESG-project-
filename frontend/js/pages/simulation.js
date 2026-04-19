import { api } from '../qtapi.js?v=8';
import { toast } from '../components/toast.js?v=8';
import { getLang, onLangChange } from '../i18n.js?v=8';
import {
  esc,
  metric,
  num,
  pathChip,
  readSymbol,
  readUniverse,
  renderError,
  renderSimulationResult,
  setLoading,
} from './workbench-utils.js?v=8';

let _container = null;
let _langCleanup = null;
let _latest = null;
let _selectedPreset = 'base';

const COPY = {
  en: {
    title: 'Simulation Workbench',
    subtitle: 'Scenario assumptions, shock replay, Monte Carlo paths, and historical analogs',
    setup: 'Scenario Setup',
    setupSub: 'Seeded simulations are reproducible and remain shadow-mode only.',
    symbol: 'Symbol',
    horizon: 'Horizon Days',
    universe: 'Universe',
    scenario: 'Scenario Name',
    regime: 'Regime',
    shock: 'Shock Bps',
    cost: 'Transaction Cost Bps',
    slippage: 'Slippage Bps',
    paths: 'Monte Carlo Paths',
    seed: 'Seed',
    assumption: 'Event Assumption',
    run: 'Run Simulation',
    presets: 'Scenario Presets',
    output: 'Simulation Result',
    manifest: 'Run Manifest',
    loading: 'Running simulation...',
    base: 'Base Case',
    riskOn: 'Risk On',
    riskOff: 'Risk Off',
    negative: 'Negative Event',
    positive: 'Positive Event',
    assumptionValue: 'Replay current evidence with transaction costs and risk guardrails.',
    preview: 'Scenario Preview',
    beforeRun: 'Ready to simulate',
    expectedOutputs: 'Expected Outputs',
    riskChecklist: 'Run Checklist',
    shadowOnly: 'Shadow-mode only',
    seeded: 'Seeded paths',
    costAware: 'Costs included',
    noBroker: 'No broker order',
    afterRun: 'after run',
  },
  zh: {
    title: '情景模拟工作台',
    subtitle: '情景假设、冲击回放、Monte Carlo 路径与历史相似事件',
    setup: '情景设置',
    setupSub: '固定 seed 的模拟可复现，并且只在影子模式下运行。',
    symbol: '股票代码',
    horizon: '预测天数',
    universe: '股票池',
    scenario: '情景名称',
    regime: '市场状态',
    shock: '冲击 Bps',
    cost: '交易成本 Bps',
    slippage: '滑点 Bps',
    paths: 'Monte Carlo 路径数',
    seed: '随机种子',
    assumption: '事件假设',
    run: '运行模拟',
    presets: '情景预设',
    output: '模拟结果',
    manifest: '运行清单',
    loading: '正在运行模拟...',
    base: '基准情景',
    riskOn: '风险偏好',
    riskOff: '风险规避',
    negative: '负面事件',
    positive: '正面事件',
    assumptionValue: '在交易成本和风险门控下回放当前证据。',
    preview: '情景预览',
    beforeRun: '可以开始模拟',
    expectedOutputs: '预计输出',
    riskChecklist: '运行检查',
    shadowOnly: '仅影子模式',
    seeded: '固定随机种子',
    costAware: '包含交易成本',
    noBroker: '不创建订单',
    afterRun: '运行后生成',
  },
};

const PRESETS = {
  base: { scenario_name: 'base_case', regime: 'neutral', shock_bps: 0, event_assumption: 'Base evidence replay.' },
  riskOn: { scenario_name: 'risk_on_growth', regime: 'risk_on', shock_bps: 75, event_assumption: 'Risk-on regime with supportive evidence.' },
  riskOff: { scenario_name: 'risk_off_stress', regime: 'risk_off', shock_bps: -125, event_assumption: 'Risk-off stress with liquidity and volatility pressure.' },
  negative: { scenario_name: 'negative_event_shock', regime: 'risk_off', shock_bps: -180, event_assumption: 'Negative ESG or controversy event shock.' },
  positive: { scenario_name: 'positive_event_replay', regime: 'risk_on', shock_bps: 110, event_assumption: 'Positive disclosure or improving ESG evidence event.' },
};

export async function render(container) {
  _container = container;
  container.innerHTML = buildShell();
  bindEvents(container);
  _langCleanup ||= onLangChange(() => {
    if (_container?.isConnected) {
      _container.innerHTML = buildShell();
      bindEvents(_container);
      renderResult(_container, _latest);
    }
  });
  renderResult(container, _latest);
}

export function destroy() {
  _container = null;
  _latest = null;
  _selectedPreset = 'base';
  _langCleanup?.();
  _langCleanup = null;
}

function c(key) {
  const current = getLang() === 'zh' ? 'zh' : 'en';
  return COPY[current][key] || COPY.en[key] || key;
}

function buildShell() {
  return `
  <div class="workbench-page simulation-page" data-no-autotranslate="true">
    <div class="page-header">
      <div>
        <div class="page-header__title">${c('title')}</div>
        <div class="page-header__sub">${c('subtitle')}</div>
      </div>
    </div>

    <div class="grid-2 workbench-top-grid simulation-balanced-grid">
      <section class="run-panel simulation-setup-card">
        <div class="run-panel__header">
          <div class="run-panel__title">${c('setup')}</div>
          <div class="run-panel__sub">${c('setupSub')}</div>
        </div>
        <div class="run-panel__body">
          <div class="form-row">
            <div class="form-group">
              <label class="form-label">${c('symbol')}</label>
              <input class="form-input" id="sim-symbol" value="AAPL" autocomplete="off">
            </div>
            <div class="form-group">
              <label class="form-label">${c('horizon')}</label>
              <input class="form-input" id="sim-horizon" type="number" value="20" min="1" max="252">
            </div>
          </div>
          <div class="form-group">
            <label class="form-label">${c('universe')}</label>
            <input class="form-input" id="sim-universe" value="AAPL, MSFT, NVDA, NEE">
          </div>
          <div class="form-row">
            <div class="form-group">
              <label class="form-label">${c('scenario')}</label>
              <input class="form-input" id="sim-scenario" value="base_case">
            </div>
            <div class="form-group">
              <label class="form-label">${c('regime')}</label>
              <select class="form-select" id="sim-regime">
                <option value="neutral">neutral</option>
                <option value="risk_on">risk_on</option>
                <option value="risk_off">risk_off</option>
              </select>
            </div>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label class="form-label">${c('shock')}</label>
              <input class="form-input" id="sim-shock" type="number" value="0">
            </div>
            <div class="form-group">
              <label class="form-label">${c('cost')}</label>
              <input class="form-input" id="sim-cost" type="number" value="8" min="0">
            </div>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label class="form-label">${c('slippage')}</label>
              <input class="form-input" id="sim-slippage" type="number" value="5" min="0">
            </div>
            <div class="form-group">
              <label class="form-label">${c('paths')}</label>
              <input class="form-input" id="sim-paths" type="number" value="512" min="32" max="5000">
            </div>
          </div>
          <div class="form-group">
            <label class="form-label">${c('seed')}</label>
            <input class="form-input" id="sim-seed" type="number" value="42">
          </div>
          <div class="form-row">
            <div class="form-group">
              <label class="form-label">Evidence Run ID</label>
              <input class="form-input" id="sim-evidence-run" placeholder="optional evidence bundle id">
            </div>
            <div class="form-group">
              <label class="form-label">Event ID</label>
              <input class="form-input" id="sim-event-id" placeholder="optional event id">
            </div>
          </div>
          <div class="form-group">
            <label class="form-label">${c('assumption')}</label>
            <textarea class="form-textarea" id="sim-assumption" rows="3">${c('assumptionValue')}</textarea>
          </div>
        </div>
        <div class="run-panel__foot workbench-action-grid">
          <button class="btn btn-primary workbench-action-btn" id="btn-simulate-scenario">${c('run')}</button>
        </div>
      </section>

      <section class="card simulation-result-card">
        <div class="card-header"><span class="card-title">${c('output')}</span></div>
        <div class="card-body" id="simulation-panel"></div>
      </section>
    </div>

    <div class="grid-2 workbench-main-grid simulation-bottom-grid">
      <section class="card simulation-presets-card">
        <div class="card-header"><span class="card-title">${c('presets')}</span></div>
        <div class="card-body">
          <div class="workbench-link-grid simulation-preset-grid">
            ${presetButton('base', c('base'))}
            ${presetButton('riskOn', c('riskOn'))}
            ${presetButton('riskOff', c('riskOff'))}
            ${presetButton('negative', c('negative'))}
            ${presetButton('positive', c('positive'))}
          </div>
        </div>
      </section>
      <section class="card simulation-manifest-card">
        <div class="card-header"><span class="card-title">${c('manifest')}</span></div>
        <div class="card-body" id="simulation-manifest"></div>
      </section>
    </div>
  </div>`;
}

function presetButton(key, label) {
  const active = key === _selectedPreset ? ' active' : '';
  return `<button class="workbench-link-card simulation-preset${active}" data-preset="${esc(key)}">
    <strong>${esc(label)}</strong>
    <span>${esc(PRESETS[key].scenario_name)} / ${esc(PRESETS[key].regime)} / ${esc(PRESETS[key].shock_bps)} bps</span>
  </button>`;
}

function bindEvents(container) {
  container.querySelector('#btn-simulate-scenario')?.addEventListener('click', () => runSimulation(container));
  container.querySelectorAll('.simulation-preset').forEach(button => {
    button.addEventListener('click', () => applyPreset(container, button.getAttribute('data-preset')));
  });
  [
    '#sim-symbol',
    '#sim-horizon',
    '#sim-universe',
    '#sim-scenario',
    '#sim-regime',
    '#sim-shock',
    '#sim-cost',
    '#sim-slippage',
    '#sim-paths',
    '#sim-seed',
    '#sim-evidence-run',
    '#sim-event-id',
    '#sim-assumption',
  ].forEach(selector => container.querySelector(selector)?.addEventListener('input', () => {
    if (!_latest) renderResult(container, null);
  }));
}

function applyPreset(container, key) {
  const preset = PRESETS[key] || PRESETS.base;
  _selectedPreset = PRESETS[key] ? key : 'base';
  container.querySelector('#sim-scenario').value = preset.scenario_name;
  container.querySelector('#sim-regime').value = preset.regime;
  container.querySelector('#sim-shock').value = String(preset.shock_bps);
  container.querySelector('#sim-assumption').value = preset.event_assumption;
  container.querySelectorAll('.simulation-preset').forEach(button => {
    button.classList.toggle('active', button.getAttribute('data-preset') === _selectedPreset);
  });
  if (!_latest) renderResult(container, null);
}

function readScenario(container) {
  const symbol = readSymbol(container, '#sim-symbol', 'AAPL');
  return {
    symbol,
    universe: readUniverse(container.querySelector('#sim-universe')?.value, symbol),
    horizon_days: Number(container.querySelector('#sim-horizon')?.value) || 20,
    shock_bps: Number(container.querySelector('#sim-shock')?.value) || 0,
    transaction_cost_bps: Number(container.querySelector('#sim-cost')?.value) || 0,
    slippage_bps: Number(container.querySelector('#sim-slippage')?.value) || 0,
    paths: Number(container.querySelector('#sim-paths')?.value) || 512,
    seed: Number(container.querySelector('#sim-seed')?.value) || 42,
    scenario_name: container.querySelector('#sim-scenario')?.value || 'base_case',
    regime: container.querySelector('#sim-regime')?.value || 'neutral',
    event_assumption: container.querySelector('#sim-assumption')?.value || '',
    evidence_run_id: container.querySelector('#sim-evidence-run')?.value || null,
    event_id: container.querySelector('#sim-event-id')?.value || null,
  };
}

async function runSimulation(container) {
  const scenario = readScenario(container);
  setLoading(container.querySelector('#simulation-panel'), c('loading'));
  try {
    _latest = await api.simulate.scenario(scenario);
    renderResult(container, _latest);
    toast.success(c('run'), `${scenario.symbol} / ${scenario.scenario_name}`);
  } catch (err) {
    renderError(container.querySelector('#simulation-panel'), err);
    toast.error(c('run'), err.message);
  }
}

function renderResult(container, result) {
  const scenario = result?.scenario || readScenario(container);
  container.querySelector('#simulation-panel').innerHTML = result
    ? renderSimulationResult(result)
    : renderSimulationPreview(scenario);
  container.querySelector('#simulation-manifest').innerHTML = `
    <div class="workbench-kv-list simulation-manifest-list">
      <div class="workbench-kv-row"><span>Simulation ID</span><strong>${pathChip(result?.simulation_id || 'not-run')}</strong></div>
      <div class="workbench-kv-row"><span>${c('symbol')}</span><strong>${esc(scenario.symbol || '')}</strong></div>
      <div class="workbench-kv-row"><span>${c('scenario')}</span><strong>${esc(scenario.scenario_name || '')}</strong></div>
      <div class="workbench-kv-row"><span>${c('regime')}</span><strong>${esc(scenario.regime || '')}</strong></div>
      <div class="workbench-kv-row"><span>${c('shock')}</span><strong>${esc(scenario.shock_bps || 0)} bps</strong></div>
      <div class="workbench-kv-row"><span>${c('paths')}</span><strong>${esc(scenario.paths || '')}</strong></div>
      <div class="workbench-kv-row"><span>${c('seed')}</span><strong>${esc(scenario.seed || '')}</strong></div>
    </div>
    <div class="simulation-manifest-state">${result ? c('output') : c('beforeRun')}</div>`;
}

function renderSimulationPreview(scenario) {
  const current = getLang() === 'zh' ? 'zh' : 'en';
  const pass = current === 'zh' ? '通过' : 'pass';
  return `
    <div class="simulation-preview">
      <div class="workbench-metric-grid simulation-preview-metrics">
        ${metric(c('symbol'), scenario.symbol || 'AAPL')}
        ${metric(c('regime'), scenario.regime || 'neutral')}
        ${metric(c('shock'), `${num(scenario.shock_bps, 0)} bps`, Number(scenario.shock_bps) < 0 ? 'risk' : '')}
        ${metric(c('paths'), num(scenario.paths, 0))}
      </div>
      <section class="workbench-section">
        <div class="workbench-section__title">${c('preview')}</div>
        <div class="workbench-kv-list simulation-preview-list">
          <div class="workbench-kv-row"><span>${c('scenario')}</span><strong>${esc(scenario.scenario_name || '')}</strong></div>
          <div class="workbench-kv-row"><span>${c('universe')}</span><strong>${esc((scenario.universe || []).join(', '))}</strong></div>
          <div class="workbench-kv-row"><span>${c('cost')}</span><strong>${esc(scenario.transaction_cost_bps || 0)} bps</strong></div>
          <div class="workbench-kv-row"><span>${c('slippage')}</span><strong>${esc(scenario.slippage_bps || 0)} bps</strong></div>
        </div>
      </section>
      <div class="grid-2 workbench-two-col simulation-preview-two-col">
        <section class="workbench-section">
          <div class="workbench-section__title">${c('expectedOutputs')}</div>
          <div class="factor-checklist">
            <div class="factor-check-row"><span>Expected return</span><strong>${c('afterRun')}</strong></div>
            <div class="factor-check-row"><span>VaR / MDD</span><strong>${c('afterRun')}</strong></div>
            <div class="factor-check-row"><span>Historical analogs</span><strong>${c('afterRun')}</strong></div>
          </div>
        </section>
        <section class="workbench-section">
          <div class="workbench-section__title">${c('riskChecklist')}</div>
          <div class="factor-checklist">
            <div class="factor-check-row"><span>${c('shadowOnly')}</span><strong class="is-pass">${pass}</strong></div>
            <div class="factor-check-row"><span>${c('seeded')}</span><strong class="is-pass">${esc(scenario.seed || 42)}</strong></div>
            <div class="factor-check-row"><span>${c('costAware')}</span><strong class="is-pass">${pass}</strong></div>
            <div class="factor-check-row"><span>${c('noBroker')}</span><strong class="is-pass">${pass}</strong></div>
          </div>
        </section>
      </div>
      <p class="workbench-report-text simulation-assumption-preview">${esc(scenario.event_assumption || '')}</p>
    </div>`;
}
