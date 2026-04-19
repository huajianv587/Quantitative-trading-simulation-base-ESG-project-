import { api } from '../qtapi.js?v=8';
import { getLang, onLangChange } from '../i18n.js?v=8';
import {
  esc,
  metric,
  pct,
  renderError,
  renderTokenPreview,
  setLoading,
  splitTokens,
  statusBadge,
} from './workbench-utils.js?v=8';

let _container = null;
let _langCleanup = null;

const COPY = {
  en: {
    title: 'Agent Lab',
    subtitle: 'One-click shadow workflow: scan evidence, discover factors, explain decisions, simulate risk, and track outcomes.',
    run: 'Run Shadow Workflow',
    reset: 'Reset',
    symbol: 'Symbol',
    universe: 'Universe',
    providers: 'Providers',
    timeline: 'Workflow Timeline',
    report: 'Agent Report',
    ready: 'Ready for shadow workflow',
    noRun: 'No workflow has run yet',
    previewText: 'Scan, validate, discover, decide, simulate, then log outcomes without broker execution.',
  },
  zh: {
    title: '智能体实验室',
    subtitle: '一键影子工作流：扫描证据、发现因子、解释决策、模拟风险并追踪结果。',
    run: '运行影子工作流',
    reset: '重置',
    symbol: '股票',
    universe: '股票池',
    providers: '数据源',
    timeline: '工作流时间线',
    report: '智能体报告',
    ready: '可以开始影子工作流',
    noRun: '尚未运行工作流',
    previewText: '扫描、校验、发现、解释、模拟，然后在不触发券商执行的前提下记录后验结果。',
  },
};

const WORKFLOW_PREVIEW = [
  ['Live scan', 'Free-tier source sweep'],
  ['Evidence QA', 'Dedup, freshness, source quality'],
  ['Factor discovery', 'IC / RankIC candidate gates'],
  ['Decision explain', 'Evidence, risks, counter evidence'],
  ['Simulation', 'Monte Carlo and stress replay'],
  ['Outcome shadow log', 'Post-decision tracking'],
];

function c(key) {
  const lang = getLang() === 'zh' ? 'zh' : 'en';
  return COPY[lang][key] || COPY.en[key] || key;
}

export function render(container) {
  _container = container;
  renderShell();
  wire();
  _langCleanup = onLangChange(() => {
    if (_container) {
      renderShell();
      wire();
    }
  });
}

export function unmount() {
  if (_langCleanup) _langCleanup();
  _container = null;
}

function renderShell() {
  _container.innerHTML = `
    <div class="workbench-page live-page" data-no-autotranslate="true">
      <section class="run-panel">
        <div class="run-panel__header">
          <div class="run-panel__title">${c('title')}</div>
          <div class="run-panel__sub">${c('subtitle')}</div>
        </div>
        <div class="run-panel__body">
          <div class="grid-3 compact-control-grid live-control-grid">
            <label class="field field--with-preview">
              <span>${c('symbol')}</span>
              <input id="agent-symbol" value="AAPL">
              <div id="agent-symbol-preview"></div>
            </label>
            <label class="field field--with-preview">
              <span>${c('universe')}</span>
              <input id="agent-universe" value="AAPL, MSFT, NVDA">
              <div id="agent-universe-preview"></div>
            </label>
            <label class="field field--with-preview">
              <span>${c('providers')}</span>
              <input id="agent-providers" value="local_esg, marketaux, twelvedata">
              <div id="agent-providers-preview"></div>
            </label>
          </div>
        </div>
        <div class="run-panel__foot workbench-action-grid">
          <button class="btn btn-primary workbench-action-btn" id="btn-agent-workflow">${c('run')}</button>
          <button class="btn btn-ghost workbench-action-btn" id="btn-agent-reset">${c('reset')}</button>
        </div>
      </section>
      <section class="grid-2 workbench-main-grid agent-lab-grid">
        <article class="run-panel">
          <div class="run-panel__header"><div class="run-panel__title">${c('timeline')}</div></div>
          <div class="run-panel__body" id="agent-timeline">${renderTimelinePreview()}</div>
        </article>
        <article class="run-panel">
          <div class="run-panel__header"><div class="run-panel__title">${c('report')}</div></div>
          <div class="run-panel__body" id="agent-report">${renderReportPreview()}</div>
        </article>
      </section>
    </div>`;
  renderFieldPreviews();
}

function wire() {
  _container.querySelector('#btn-agent-workflow')?.addEventListener('click', runWorkflow);
  _container.querySelector('#btn-agent-reset')?.addEventListener('click', () => {
    renderFieldPreviews();
    _container.querySelector('#agent-timeline').innerHTML = renderTimelinePreview();
    _container.querySelector('#agent-report').innerHTML = renderReportPreview();
  });
  ['#agent-symbol', '#agent-universe', '#agent-providers'].forEach((selector) => {
    _container.querySelector(selector)?.addEventListener('input', renderFieldPreviews);
  });
}

function symbol() {
  return String(_container.querySelector('#agent-symbol')?.value || 'AAPL').trim().toUpperCase();
}

function universe() {
  return splitTokens(_container.querySelector('#agent-universe')?.value || symbol(), { uppercase: true, delimiters: /[,\s]+/ });
}

function providers() {
  return splitTokens(_container.querySelector('#agent-providers')?.value || '', { delimiters: /[,|\s]+/ });
}

function renderFieldPreviews() {
  _container.querySelector('#agent-symbol-preview').innerHTML = renderTokenPreview([symbol()], {
    tone: 'accent',
    maxItems: 1,
  });
  _container.querySelector('#agent-universe-preview').innerHTML = renderTokenPreview(universe(), {
    uppercase: true,
    tone: 'accent',
    maxItems: 6,
  });
  _container.querySelector('#agent-providers-preview').innerHTML = renderTokenPreview(providers(), {
    tone: 'neutral',
    maxItems: 6,
  });
}

function renderTimelinePreview() {
  return `
    <div class="agent-preview">
      <div>
        <div class="functional-empty__eyebrow">Shadow Workflow</div>
        <h3>${c('ready')}</h3>
        <p>${c('previewText')}</p>
      </div>
      <div class="workbench-metric-grid">
        ${metric('Steps', WORKFLOW_PREVIEW.length, 'positive')}
        ${metric('Mode', 'shadow')}
        ${metric('Broker', 'blocked', 'risk')}
        ${metric('Quota', 'guarded')}
      </div>
      <div class="preview-step-grid">
        ${WORKFLOW_PREVIEW.map(([step, detail]) => `<div class="preview-step"><span>${esc(step)} | ${esc(detail)}</span><strong>queued</strong></div>`).join('')}
      </div>
    </div>`;
}

function renderReportPreview() {
  return `
    <div class="agent-preview">
      <div>
        <div class="functional-empty__eyebrow">Report Preview</div>
        <h3>${c('noRun')}</h3>
        <p>The report will include run IDs, evidence counts, factor cards, decision confidence, loss probability, and outcome log state.</p>
      </div>
      <div class="workbench-metric-grid">
        ${metric('Evidence', 'pending')}
        ${metric('Factors', 'pending')}
        ${metric('Decision', 'shadow')}
        ${metric('Outcome', 'tracked')}
      </div>
      <div class="workbench-kv-list compact-kv-list">
        <div class="workbench-kv-row"><span>Run bundle</span><strong>not started</strong></div>
        <div class="workbench-kv-row"><span>Safety</span><strong>frozen-safe</strong></div>
        <div class="workbench-kv-row"><span>Keys</span><strong>masked</strong></div>
        <div class="workbench-kv-row"><span>Broker</span><strong>blocked</strong></div>
      </div>
    </div>`;
}

function timeline(rows) {
  _container.querySelector('#agent-timeline').innerHTML = `
    <div class="workbench-list workbench-scroll-list">
      ${rows.map((row) => `
        <article class="workbench-item">
          <div class="workbench-item__head"><strong>${esc(row.step)}</strong>${statusBadge(row.status)}</div>
          <p>${esc(row.detail || '')}</p>
          <div class="workbench-item__meta"><span>${esc(row.id || '')}</span></div>
        </article>
      `).join('')}
    </div>`;
}

async function runWorkflow() {
  const rows = [];
  const report = _container.querySelector('#agent-report');
  setLoading(report, 'Running agentic shadow loop...');
  try {
    rows.push({ step: 'Live scan', status: 'running', detail: 'Free-tier connector scan' });
    timeline(rows);
    const evidence = await api.connectors.liveScan({
      universe: universe(),
      providers: providers(),
      quota_guard: true,
      persist: true,
      limit: 8,
    });

    rows[0] = {
      step: 'Live scan',
      status: 'promoted',
      detail: `${evidence.items?.length || 0} evidence items`,
      id: evidence.bundle_id || evidence.run_id,
    };
    rows.push({
      step: 'Evidence QA',
      status: 'promoted',
      detail: `${evidence.lineage?.length || 0} lineage checks | quota guard on`,
      id: `items=${evidence.items?.length || 0}`,
    });
    rows.push({ step: 'Factor discovery', status: 'running', detail: 'IC / RankIC gate' });
    timeline(rows);
    const factors = await api.factors.discover({
      universe: universe(),
      evidence_run_id: evidence.bundle_id,
      mode: 'mixed',
      providers: providers(),
    });

    rows[2] = {
      step: 'Factor discovery',
      status: 'promoted',
      detail: `${factors.factor_cards?.length || 0} factor cards`,
      id: factors.run_id,
    };
    rows.push({ step: 'Decision explain', status: 'running', detail: 'Multi-expert report' });
    timeline(rows);
    const decision = await api.decision.explain({
      symbol: symbol(),
      universe: universe(),
      evidence_run_id: evidence.bundle_id,
      mode: 'mixed',
      providers: providers(),
    });

    rows[3] = {
      step: 'Decision explain',
      status: 'promoted',
      detail: `${decision.action || 'hold'} | confidence ${decision.confidence || '-'}`,
      id: decision.decision_id,
    };
    rows.push({ step: 'Simulation', status: 'running', detail: 'Monte Carlo and stress test' });
    timeline(rows);
    const simulation = await api.simulate.scenario({
      symbol: symbol(),
      universe: universe(),
      evidence_run_id: evidence.bundle_id,
      paths: 128,
      seed: 42,
    });

    rows[4] = {
      step: 'Simulation',
      status: 'promoted',
      detail: `loss probability ${pct(simulation.probability_of_loss)}`,
      id: simulation.simulation_id,
    };
    rows.push({ step: 'Outcome shadow log', status: 'running', detail: 'Read current calibration summary' });
    timeline(rows);
    const outcomes = await api.outcomes.evaluate({ symbol: symbol(), decision_id: decision.decision_id });

    rows[5] = {
      step: 'Outcome shadow log',
      status: 'promoted',
      detail: `${outcomes.record_count || outcomes.summary?.record_count || 0} records`,
      id: 'shadow-log',
    };
    timeline(rows);
    report.innerHTML = `
      <div class="workbench-metric-grid">
        ${metric('Evidence', evidence.items?.length || 0, 'positive')}
        ${metric('Factors', factors.factor_cards?.length || 0)}
        ${metric('Action', decision.action || '-')}
        ${metric('Loss Prob', pct(simulation.probability_of_loss), 'risk')}
      </div>
      <div class="workbench-kv-list compact-kv-list">
        <div class="workbench-kv-row"><span>Evidence bundle</span><strong>${esc(evidence.bundle_id || evidence.run_id || 'latest')}</strong></div>
        <div class="workbench-kv-row"><span>Factor run</span><strong>${esc(factors.run_id || 'registry')}</strong></div>
        <div class="workbench-kv-row"><span>Decision ID</span><strong>${esc(decision.decision_id || '-')}</strong></div>
        <div class="workbench-kv-row"><span>Simulation ID</span><strong>${esc(simulation.simulation_id || '-')}</strong></div>
      </div>
      <div class="workbench-list workbench-scroll-list">
        <article class="workbench-item">
          <div class="workbench-item__head"><strong>${esc(decision.symbol || symbol())} Decision</strong>${statusBadge(decision.action || 'hold')}</div>
          <p>${esc((decision.main_evidence || [])[0]?.summary || 'Shadow report created.')}</p>
        </article>
        <article class="workbench-item">
          <div class="workbench-item__head"><strong>Simulation</strong>${statusBadge('ready')}</div>
          <p>${esc(`Loss probability ${pct(simulation.probability_of_loss)} | VaR ${pct(simulation.value_at_risk_95)} | MDD ${pct(simulation.max_drawdown_p95)}`)}</p>
        </article>
        <article class="workbench-item">
          <div class="workbench-item__head"><strong>Next actions</strong>${statusBadge('research_only')}</div>
          <p>Promote validated factors, replay the thesis in Simulation, and keep every recommendation in the shadow log.</p>
        </article>
      </div>`;
  } catch (err) {
    rows.push({ step: 'Workflow failed', status: 'rejected', detail: err.message || String(err) });
    timeline(rows);
    renderError(report, err);
  }
}
