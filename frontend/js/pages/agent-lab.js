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
    subtitle: '一键影子工作流：扫描证据、发现因子、解释决策、模拟风险，并追踪结果。',
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

const WORKFLOW_PREVIEW = {
  en: [
    ['Live scan', 'Free-tier source sweep'],
    ['Evidence QA', 'Dedup, freshness, source quality'],
    ['Factor discovery', 'IC / RankIC candidate gates'],
    ['Decision explain', 'Evidence, risks, counter evidence'],
    ['Simulation', 'Monte Carlo and stress replay'],
    ['Outcome shadow log', 'Post-decision tracking'],
  ],
  zh: [
    ['实时扫描', '免费数据源快速扫描'],
    ['证据质检', '去重、新鲜度与来源质量'],
    ['因子发现', 'IC / RankIC 候选门禁'],
    ['决策解释', '证据、风险与反方观点'],
    ['情景模拟', 'Monte Carlo 与压力回放'],
    ['结果影子日志', '决策后的结果追踪'],
  ],
};

function c(key) {
  const lang = getLang() === 'zh' ? 'zh' : 'en';
  return COPY[lang][key] || COPY.en[key] || key;
}

function isMounted() {
  return Boolean(_container && _container.isConnected);
}

function t(en, zh) {
  return getLang() === 'zh' ? zh : en;
}

function actionLabel(value) {
  const normalized = String(value || '').trim().toLowerCase();
  const map = {
    hold: t('hold', '持有'),
    long: t('long', '看多'),
    short: t('short', '看空'),
    neutral: t('neutral', '中性'),
  };
  return map[normalized] || String(value || '-');
}

function workflowPreview() {
  return getLang() === 'zh' ? WORKFLOW_PREVIEW.zh : WORKFLOW_PREVIEW.en;
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
  const preview = workflowPreview();
  return `
    <div class="agent-preview">
      <div>
        <div class="functional-empty__eyebrow">${t('Shadow Workflow', '影子工作流')}</div>
        <h3>${c('ready')}</h3>
        <p>${c('previewText')}</p>
      </div>
      <div class="workbench-metric-grid">
        ${metric(t('Steps', '步骤'), preview.length, 'positive')}
        ${metric(t('Mode', '模式'), t('shadow', '影子'))}
        ${metric(t('Broker', '券商执行'), t('blocked', '已阻止'), 'risk')}
        ${metric(t('Quota', '额度保护'), t('guarded', '已防护'))}
      </div>
      <div class="preview-step-grid">
        ${preview.map(([step, detail]) => `<div class="preview-step"><span>${esc(step)} | ${esc(detail)}</span><strong>${t('queued', '排队中')}</strong></div>`).join('')}
      </div>
      <div class="workbench-section">
        <div class="workbench-section__title">${t('Workflow Guarantees', '工作流保障')}</div>
        <div class="factor-checklist">
          <div class="factor-check-row"><span>${t('Provider failures stay isolated', '单个数据源失败不会拖垮整条链路')}</span><strong class="is-pass">${t('yes', '是')}</strong></div>
          <div class="factor-check-row"><span>${t('Broker execution remains blocked', '券商执行保持阻止')}</span><strong class="is-pass">${t('shadow', '影子')}</strong></div>
          <div class="factor-check-row"><span>${t('All outputs are run-addressable', '所有输出都可按 run 定位')}</span><strong>${t('ledger', '台账')}</strong></div>
        </div>
      </div>
    </div>`;
}

function renderReportPreview() {
  return `
    <div class="agent-preview">
      <div>
        <div class="functional-empty__eyebrow">${t('Report Preview', '报告预览')}</div>
        <h3>${c('noRun')}</h3>
        <p>${t('The report will include run IDs, evidence counts, factor cards, decision confidence, loss probability, and outcome log state.', '报告会包含 run ID、证据数量、因子卡、决策置信度、亏损概率和结果日志状态。')}</p>
      </div>
      <div class="workbench-metric-grid">
        ${metric(t('Evidence', '证据'), t('pending', '待处理'))}
        ${metric(t('Factors', '因子'), t('pending', '待处理'))}
        ${metric(t('Decision', '决策'), t('shadow', '影子'))}
        ${metric(t('Outcome', '结果'), t('tracked', '已追踪'))}
      </div>
      <div class="workbench-kv-list compact-kv-list">
        <div class="workbench-kv-row"><span>${t('Run bundle', '运行包')}</span><strong>${t('not started', '未开始')}</strong></div>
        <div class="workbench-kv-row"><span>${t('Safety', '安全性')}</span><strong>${t('frozen-safe', '冻结安全')}</strong></div>
        <div class="workbench-kv-row"><span>${t('Keys', '密钥')}</span><strong>${t('masked', '已脱敏')}</strong></div>
        <div class="workbench-kv-row"><span>${t('Broker', '券商执行')}</span><strong>${t('blocked', '已阻止')}</strong></div>
      </div>
      <div class="workbench-section">
        <div class="workbench-section__title">${t('Handoff Manifest', '交接清单')}</div>
        <div class="preview-step-grid">
          <div class="preview-step"><span>${t('Evidence bundle', '证据包')}</span><strong>${t('pending', '待处理')}</strong></div>
          <div class="preview-step"><span>${t('Factor registry', '因子注册表')}</span><strong>${t('pending', '待处理')}</strong></div>
          <div class="preview-step"><span>${t('Decision report', '决策报告')}</span><strong>${t('pending', '待处理')}</strong></div>
          <div class="preview-step"><span>${t('Outcome row', '结果记录')}</span><strong>${t('shadow-only', '仅影子')}</strong></div>
        </div>
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
  if (!isMounted()) return;
  const rows = [];
  const report = _container.querySelector('#agent-report');
  setLoading(report, t('Running agentic shadow loop...', '正在运行智能体影子闭环...'));
  try {
    rows.push({ step: t('Live scan', '实时扫描'), status: 'running', detail: t('Free-tier connector scan', '免费数据源连接器扫描') });
    timeline(rows);
    const evidence = await api.connectors.liveScan({
      universe: universe(),
      providers: providers(),
      quota_guard: true,
      persist: true,
      limit: 8,
    });
    if (!isMounted()) return;

    rows[0] = {
      step: t('Live scan', '实时扫描'),
      status: 'promoted',
      detail: `${evidence.items?.length || 0} ${t('evidence items', '条证据')}`,
      id: evidence.bundle_id || evidence.run_id,
    };
    rows.push({
      step: t('Evidence QA', '证据质检'),
      status: 'promoted',
      detail: `${evidence.lineage?.length || 0} ${t('lineage checks', '项链路检查')} | ${t('quota guard on', '额度保护已启用')}`,
      id: `items=${evidence.items?.length || 0}`,
    });
    rows.push({ step: t('Factor discovery', '因子发现'), status: 'running', detail: t('IC / RankIC gate', 'IC / RankIC 门禁') });
    timeline(rows);
    const factors = await api.factors.discover({
      universe: universe(),
      evidence_run_id: evidence.bundle_id,
      mode: 'mixed',
      providers: providers(),
    });
    if (!isMounted()) return;

    rows[2] = {
      step: t('Factor discovery', '因子发现'),
      status: 'promoted',
      detail: `${factors.factor_cards?.length || 0} ${t('factor cards', '张因子卡')}`,
      id: factors.run_id,
    };
    rows.push({ step: t('Decision explain', '决策解释'), status: 'running', detail: t('Multi-expert report', '多专家报告') });
    timeline(rows);
    const decision = await api.decision.explain({
      symbol: symbol(),
      universe: universe(),
      evidence_run_id: evidence.bundle_id,
      mode: 'mixed',
      providers: providers(),
    });
    if (!isMounted()) return;

    rows[3] = {
      step: t('Decision explain', '决策解释'),
      status: 'promoted',
      detail: `${decision.action || t('hold', '持有')} | ${t('confidence', '置信度')} ${decision.confidence || '-'}`,
      id: decision.decision_id,
    };
    rows.push({ step: t('Simulation', '情景模拟'), status: 'running', detail: t('Monte Carlo and stress test', 'Monte Carlo 与压力测试') });
    timeline(rows);
    const simulation = await api.simulate.scenario({
      symbol: symbol(),
      universe: universe(),
      evidence_run_id: evidence.bundle_id,
      paths: 128,
      seed: 42,
    });
    if (!isMounted()) return;

    rows[4] = {
      step: t('Simulation', '情景模拟'),
      status: 'promoted',
      detail: `${t('loss probability', '亏损概率')} ${pct(simulation.probability_of_loss)}`,
      id: simulation.simulation_id,
    };
    rows.push({ step: t('Outcome shadow log', '结果影子日志'), status: 'running', detail: t('Read current calibration summary', '读取当前校准摘要') });
    timeline(rows);
    const outcomes = await api.outcomes.evaluate({ symbol: symbol(), decision_id: decision.decision_id });
    if (!isMounted()) return;

    rows[5] = {
      step: t('Outcome shadow log', '结果影子日志'),
      status: 'promoted',
      detail: `${outcomes.record_count || outcomes.summary?.record_count || 0} ${t('records', '条记录')}`,
      id: 'shadow-log',
    };
    timeline(rows);
    report.innerHTML = `
      <div class="workbench-metric-grid">
        ${metric(t('Evidence', '证据'), evidence.items?.length || 0, 'positive')}
        ${metric(t('Factors', '因子'), factors.factor_cards?.length || 0)}
        ${metric(t('Action', '动作'), actionLabel(decision.action))}
        ${metric(t('Loss Prob', '亏损概率'), pct(simulation.probability_of_loss), 'risk')}
        ${metric(t('Outcome', '结果'), outcomes.record_count || outcomes.summary?.record_count || 0)}
        ${metric(t('Guard', '门控'), t('shadow', '影子'))}
      </div>
      <div class="workbench-kv-list compact-kv-list">
        <div class="workbench-kv-row"><span>${t('Evidence bundle', '证据包')}</span><strong>${esc(evidence.bundle_id || evidence.run_id || t('latest', '最新'))}</strong></div>
        <div class="workbench-kv-row"><span>${t('Factor run', '因子运行')}</span><strong>${esc(factors.run_id || t('registry', '注册表'))}</strong></div>
        <div class="workbench-kv-row"><span>${t('Decision ID', '决策 ID')}</span><strong>${esc(decision.decision_id || '-')}</strong></div>
        <div class="workbench-kv-row"><span>${t('Simulation ID', '模拟 ID')}</span><strong>${esc(simulation.simulation_id || '-')}</strong></div>
      </div>
      <div class="workbench-section">
        <div class="workbench-section__title">${t('Handoff Manifest', '交接清单')}</div>
        <div class="preview-step-grid">
          <div class="preview-step"><span>${t('Connector lineage', '连接器链路')}</span><strong>${esc((decision.connector_lineage?.free_tier_registry?.providers || []).length || providers().length)}</strong></div>
          <div class="preview-step"><span>${t('Quota mode', '额度模式')}</span><strong>${esc(String(decision.quota_mode || evidence.mode || t('guarded', '已防护')))}</strong></div>
          <div class="preview-step"><span>${t('Confidence', '置信度')}</span><strong>${esc(decision.confidence || '-')}</strong></div>
          <div class="preview-step"><span>${t('Loss guard', '亏损防护')}</span><strong>${pct(simulation.probability_of_loss)}</strong></div>
        </div>
      </div>
      <div class="workbench-section">
        <div class="workbench-section__title">${t('Workflow Guarantees', '工作流保障')}</div>
        <div class="factor-checklist">
          <div class="factor-check-row"><span>${t('Evidence kept in shadow lake', '证据已保存在影子证据湖')}</span><strong class="is-pass">${t('stored', '已存储')}</strong></div>
          <div class="factor-check-row"><span>${t('Decision stayed broker-safe', '决策保持券商安全')}</span><strong class="is-pass">${t('blocked', '已阻止')}</strong></div>
          <div class="factor-check-row"><span>${t('Outcome row linked to decision', '结果记录已关联到决策')}</span><strong>${esc(decision.decision_id ? t('linked', '已关联') : t('pending', '待处理'))}</strong></div>
        </div>
      </div>
      <div class="workbench-list workbench-scroll-list">
        <article class="workbench-item">
          <div class="workbench-item__head"><strong>${esc(decision.symbol || symbol())} ${t('Decision', '决策')}</strong>${statusBadge(decision.action || 'hold')}</div>
          <p>${esc((decision.main_evidence || [])[0]?.summary || t('Shadow report created.', '影子报告已生成。'))}</p>
        </article>
        <article class="workbench-item">
          <div class="workbench-item__head"><strong>${t('Simulation', '情景模拟')}</strong>${statusBadge('ready')}</div>
          <p>${esc(`${t('Loss probability', '亏损概率')} ${pct(simulation.probability_of_loss)} | VaR ${pct(simulation.value_at_risk_95)} | MDD ${pct(simulation.max_drawdown_p95)}`)}</p>
        </article>
        <article class="workbench-item">
          <div class="workbench-item__head"><strong>${t('Next actions', '下一步动作')}</strong>${statusBadge('research_only')}</div>
          <p>${t('Promote validated factors, replay the thesis in Simulation, and keep every recommendation in the shadow log.', '升级已验证因子，在模拟器回放当前判断，并把所有建议保留在影子日志中。')}</p>
        </article>
      </div>`;
  } catch (err) {
    if (!isMounted()) return;
    rows.push({ step: t('Workflow failed', '工作流失败'), status: 'rejected', detail: err.message || String(err) });
    timeline(rows);
    renderError(report, err);
  }
}
