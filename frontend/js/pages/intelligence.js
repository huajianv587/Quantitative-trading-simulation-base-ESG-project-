import { api } from '../qtapi.js?v=8';
import { toast } from '../components/toast.js?v=8';
import { router } from '../router.js?v=8';
import { getLang, onLangChange } from '../i18n.js?v=8';
import {
  esc,
  metric,
  num,
  pct,
  readSymbol,
  readUniverse,
  renderError,
  renderEvidenceItems,
  renderFactorCards,
  renderTokenPreview,
  setLoading,
  splitTokens,
} from './workbench-utils.js?v=8';

let _container = null;
let _langCleanup = null;
let _latest = {
  evidence: null,
  decision: null,
  audit: null,
  debate: null,
  risk: null,
};

const COPY = {
  en: {
    title: 'Decision Cockpit',
    subtitle: 'Evidence chain, critic checks, debate verdicts, risk approvals, and shadow-mode decisions.',
    refresh: 'Refresh',
    setupTitle: 'Shadow Decision Setup',
    setupSub: 'Research support only. Broker execution remains gated by debate and risk approval.',
    symbol: 'Symbol',
    horizon: 'Horizon Days',
    universe: 'Universe',
    query: 'Research Question',
    queryValue: 'Explain the current evidence, debate outcome, and risk posture before any action.',
    scan: 'Scan Evidence',
    explain: 'Explain Decision',
    openFactor: 'Open Factor Lab',
    openSimulation: 'Open Simulation',
    decisionSummary: 'Decision Report',
    decisionEmpty: 'No decision report yet',
    decisionHint: 'Run Explain Decision to generate an evidence-backed recommendation and transfer summary.',
    evidence: 'Evidence Feed',
    counter: 'Counter Evidence',
    audit: 'Audit Trail',
    debate: 'Debate Summary',
    risk: 'Risk Approval Summary',
    workbenches: 'Connected Workbenches',
    loadAudit: 'Load Audit',
    scanning: 'Scanning evidence...',
    explaining: 'Building decision report...',
    auditLoading: 'Loading audit trail...',
    noCounter: 'No counter evidence in the latest report.',
    noAudit: 'No audit records yet',
    noAuditHint: 'Generate a decision report to start the shadow log.',
    noDebate: 'No debate run linked yet',
    noDebateHint: 'Run Debate Desk to create a bull vs bear verdict for this symbol.',
    noRisk: 'No risk approval linked yet',
    noRiskHint: 'Open Risk Board after a debate to evaluate position size and hard blocks.',
    ready: 'shadow mode',
    dataMode: 'Data Mode',
    freeProviders: 'Free Providers',
    modeLocal: 'local / frozen-safe',
    modeMixed: 'mixed free-tier live',
    modeLive: 'live connectors only',
    evidenceUnit: 'items',
    action: 'Action',
    expected: 'Expected',
    confidence: 'Confidence',
    weightMax: 'Weight Max',
    verifier: 'Verifier Snapshot',
    triggers: 'Risk Triggers',
    factorView: 'Factor View',
    simulationBridge: 'Simulation Bridge',
    confidenceBand: 'Confidence Band',
    auditStatus: 'Audit Status',
    latestDebate: 'Latest Debate',
    dispute: 'Dispute',
    judge: 'Judge',
    humanReview: 'Human Review',
    latestRisk: 'Latest Risk Gate',
    verdict: 'Verdict',
    kelly: 'Kelly Cap',
    ttl: 'Signal TTL',
    hardBlock: 'Hard Block',
    nextActions: 'Next Actions',
    workbenchHint: 'Move the current thesis into factor review, debate, risk approval, execution monitoring, or outcome tracking.',
    bridgeFactor: 'Go to Factor Lab',
    bridgeSim: 'Go to Simulation',
    bridgeDebate: 'Go to Debate Desk',
    bridgeRisk: 'Go to Risk Board',
    bridgeOps: 'Go to Trading Ops',
    bridgeConnector: 'Go to Connector Center',
    bridgeRadar: 'Go to Market Radar',
    bridgeFactorHint: 'Open factor discovery and review the promoted factor set.',
    bridgeSimHint: 'Replay the thesis with shocks, stress, and Monte Carlo paths.',
    bridgeDebateHint: 'Inspect the latest bull vs bear rounds and judge verdict.',
    bridgeRiskHint: 'Move the current view into position sizing and hard-block review.',
    bridgeOpsHint: 'Check paper mode, schedule, watchlist, alerts, and latest review.',
    bridgeConnectorHint: 'Inspect source health, quota guard, and failure isolation.',
    bridgeRadarHint: 'Review the live evidence stream and its source quality.',
    actionScan: 'Refresh source-linked evidence',
    actionDebate: 'Send thesis into Debate Desk',
    actionRisk: 'Prepare risk approval handoff',
    actionPaper: 'Paper execution remains gated',
    noActiveTrigger: 'No active trigger in the current report.',
    noEmbeddedSimulation: 'No embedded simulation attached yet. Open Simulation to replay the current thesis.',
    actionApprove: 'approve',
    actionReduce: 'reduce',
    actionReject: 'reject',
    actionHalt: 'halt',
    actionLong: 'long',
    actionShort: 'short',
    actionNeutral: 'neutral',
    actionBlock: 'block',
    yes: 'yes',
    no: 'no',
    bullLabel: 'Bull',
    bearLabel: 'Bear',
    notional: 'Notional',
    paperModeValue: 'paper',
    p05Label: 'p05',
    midLabel: 'mid',
    leakage: 'Leakage',
    modeLabel: 'Mode',
    evidenceCount: 'Evidence',
    counterCount: 'Counter',
  },
  zh: {
    title: '决策驾驶舱',
    subtitle: '在这里整合证据链、反方检视、辩论裁决、风控审批与影子模式决策。',
    refresh: '刷新',
    setupTitle: '影子决策设置',
    setupSub: '这里只做研究与解释，券商执行仍然受辩论与风控审批双重门禁控制。',
    symbol: '股票',
    horizon: '预测天数',
    universe: '股票池',
    query: '研究问题',
    queryValue: '解释当前证据、辩论结果与风险姿态，再给出行动建议。',
    scan: '扫描证据',
    explain: '解释决策',
    openFactor: '打开因子实验室',
    openSimulation: '打开情景模拟',
    decisionSummary: '决策报告',
    decisionEmpty: '暂无决策报告',
    decisionHint: '点击“解释决策”后，会生成证据支撑的建议、移交摘要与执行桥接。',
    evidence: '证据流',
    counter: '反方证据',
    audit: '审计轨迹',
    debate: '辩论摘要',
    risk: '风控审批摘要',
    workbenches: '关联工作台',
    loadAudit: '加载审计',
    scanning: '正在扫描证据...',
    explaining: '正在生成决策报告...',
    auditLoading: '正在加载审计轨迹...',
    noCounter: '最新报告中暂无反方证据。',
    noAudit: '暂无审计记录',
    noAuditHint: '生成一次决策报告后，影子日志会从这里开始。',
    noDebate: '还没有关联的辩论结果',
    noDebateHint: '前往辩论台运行多空对抗后，这里会显示裁决摘要。',
    noRisk: '还没有关联的风控审批',
    noRiskHint: '在辩论完成后前往风控板，即可评估仓位大小与硬性阻断。',
    ready: '影子模式',
    dataMode: '数据模式',
    freeProviders: '免费数据源',
    modeLocal: '本地 / 冻结安全',
    modeMixed: '混合免费实时',
    modeLive: '仅实时连接器',
    evidenceUnit: '条',
    action: '动作',
    expected: '预期收益',
    confidence: '置信度',
    weightMax: '权重上限',
    verifier: '验证器快照',
    triggers: '风险触发',
    factorView: '因子视角',
    simulationBridge: '模拟桥接',
    confidenceBand: '置信区间',
    auditStatus: '审计状态',
    latestDebate: '最近一次辩论',
    dispute: '分歧',
    judge: '裁判',
    humanReview: '人工复核',
    latestRisk: '最近一次风控门禁',
    verdict: '结论',
    kelly: 'Kelly 上限',
    ttl: '信号 TTL',
    hardBlock: '硬性阻断',
    nextActions: '下一步动作',
    workbenchHint: '把当前结论继续送往因子复核、辩论、风控审批、执行监控或结果追踪。',
    bridgeFactor: '去因子实验室',
    bridgeSim: '去情景模拟',
    bridgeDebate: '去辩论台',
    bridgeRisk: '去风控板',
    bridgeOps: '去交易运维',
    bridgeConnector: '去数据源中心',
    bridgeRadar: '去市场雷达',
    bridgeFactorHint: '打开因子发现结果，复核已晋升因子与门禁状态。',
    bridgeSimHint: '用冲击、压力与 Monte Carlo 路径回放当前判断。',
    bridgeDebateHint: '检查最近一次多空对抗、裁决结论与争议分数。',
    bridgeRiskHint: '把当前视图送进仓位 sizing 与 hard-block 审批。',
    bridgeOpsHint: '查看纸面模式、调度、观察池、告警与最新复盘。',
    bridgeConnectorHint: '检查数据源健康、额度保护与失败隔离。',
    bridgeRadarHint: '查看实时证据流与来源质量。',
    actionScan: '刷新带来源链路的证据',
    actionDebate: '将当前结论送往辩论台',
    actionRisk: '准备风控审批移交',
    actionPaper: '纸面执行仍受门禁控制',
    noActiveTrigger: '当前报告中没有激活的风险触发。',
    noEmbeddedSimulation: '当前还没有附带内嵌模拟。可打开情景模拟回放本次判断。',
    actionApprove: '批准',
    actionReduce: '缩减',
    actionReject: '拒绝',
    actionHalt: '暂停',
    actionLong: '看多',
    actionShort: '看空',
    actionNeutral: '中性',
    actionBlock: '阻断',
    yes: '是',
    no: '否',
    bullLabel: '多头',
    bearLabel: '空头',
    notional: '名义金额',
    paperModeValue: '纸面',
    p05Label: '下界',
    midLabel: '中值',
    leakage: '泄漏',
    modeLabel: '模式',
    evidenceCount: '证据数',
    counterCount: '反方数',
  },
};

function c(key) {
  const current = getLang() === 'zh' ? 'zh' : 'en';
  return COPY[current][key] || COPY.en[key] || key;
}

function localizedCount(value) {
  return `${value} ${c('evidenceUnit')}`;
}

function actionLabel(value) {
  const normalized = String(value || '').trim().toLowerCase();
  const map = {
    approve: c('actionApprove'),
    reduce: c('actionReduce'),
    reject: c('actionReject'),
    halt: c('actionHalt'),
    long: c('actionLong'),
    short: c('actionShort'),
    neutral: c('actionNeutral'),
    block: c('actionBlock'),
  };
  return map[normalized] || String(value || '-');
}

function boolLabel(value) {
  return value ? c('yes') : c('no');
}

function buildShell() {
  return `
    <div class="workbench-page decision-cockpit-page" data-no-autotranslate="true">
      <div class="page-header">
        <div>
          <div class="page-header__title">${c('title')}</div>
          <div class="page-header__sub">${c('subtitle')}</div>
        </div>
        <div class="page-header__actions">
          <button class="btn btn-ghost btn-sm" id="btn-refresh-intelligence">${c('refresh')}</button>
        </div>
      </div>

      <div class="decision-layout">
        <div class="decision-stack decision-stack--left">
          <section class="run-panel">
            <div class="run-panel__header">
              <div class="run-panel__title">${c('setupTitle')}</div>
              <div class="run-panel__sub">${c('setupSub')}</div>
            </div>
            <div class="run-panel__body">
              <div class="form-row">
                <div class="form-group">
                  <label class="form-label">${c('symbol')}</label>
                  <input class="form-input" id="intel-symbol" value="AAPL" autocomplete="off">
                </div>
                <div class="form-group">
                  <label class="form-label">${c('horizon')}</label>
                  <input class="form-input" id="intel-horizon" type="number" value="20" min="1" max="252">
                </div>
              </div>
              <div class="form-group">
                <label class="form-label">${c('universe')}</label>
                <input class="form-input" id="intel-universe" value="AAPL, MSFT, NVDA, NEE">
              </div>
              <div class="form-row">
                <div class="form-group">
                  <label class="form-label">${c('dataMode')}</label>
                  <select class="form-input" id="intel-mode">
                    <option value="local">${c('modeLocal')}</option>
                    <option value="mixed">${c('modeMixed')}</option>
                    <option value="live">${c('modeLive')}</option>
                  </select>
                </div>
                <div class="form-group">
                  <label class="form-label">${c('freeProviders')}</label>
                  <input class="form-input" id="intel-providers" value="local_esg, marketaux, twelvedata">
                </div>
              </div>
              <div id="intel-config-preview" class="config-token-strip"></div>
              <div class="form-group">
                <label class="form-label">${c('query')}</label>
                <textarea class="form-textarea" id="intel-query" rows="3">${c('queryValue')}</textarea>
              </div>
            </div>
            <div class="run-panel__foot workbench-action-grid intelligence-action-grid">
              <button class="btn btn-primary workbench-action-btn intelligence-action-btn" id="btn-intel-scan">${c('scan')}</button>
              <button class="btn btn-primary workbench-action-btn intelligence-action-btn" id="btn-decision-explain">${c('explain')}</button>
              <button class="btn btn-ghost workbench-action-btn intelligence-action-btn" id="btn-open-factor-lab">${c('openFactor')}</button>
              <button class="btn btn-ghost workbench-action-btn intelligence-action-btn" id="btn-open-simulation">${c('openSimulation')}</button>
            </div>
          </section>

          <section class="card">
            <div class="card-header"><span class="card-title">${c('evidence')}</span></div>
            <div class="card-body" id="evidence-panel"></div>
          </section>
        </div>

        <div class="decision-stack decision-stack--right">
          <section class="card">
            <div class="card-header">
              <span class="card-title">${c('decisionSummary')}</span>
              <span class="text-xs text-muted font-mono" id="decision-status">${c('ready')}</span>
            </div>
            <div class="card-body" id="decision-summary">${renderDecisionReadyState()}</div>
          </section>
          <section class="card">
            <div class="card-header"><span class="card-title">${c('counter')}</span></div>
            <div class="card-body" id="counter-panel">${renderCounterReadyState()}</div>
          </section>
          <section class="card">
            <div class="card-header">
              <span class="card-title">${c('audit')}</span>
              <button class="btn btn-ghost btn-sm" id="btn-load-audit">${c('loadAudit')}</button>
            </div>
            <div class="card-body" id="audit-panel">${renderAuditReadyState()}</div>
          </section>
          <section class="card">
            <div class="card-header"><span class="card-title">${c('debate')}</span></div>
            <div class="card-body" id="debate-summary">${renderDebateReadyState()}</div>
          </section>
          <section class="card">
            <div class="card-header"><span class="card-title">${c('risk')}</span></div>
            <div class="card-body" id="risk-summary">${renderRiskReadyState()}</div>
          </section>
          <section class="card">
            <div class="card-header"><span class="card-title">${c('workbenches')}</span></div>
            <div class="card-body">
              ${renderWorkbenchLinks()}
              ${renderConnectedActions()}
            </div>
          </section>
        </div>
      </div>
    </div>
  `;
}

export async function render(container) {
  _container = container;
  container.innerHTML = buildShell();
  bindEvents();
  renderConfigPreview();
  _langCleanup = onLangChange(() => {
    if (!_container?.isConnected) return;
    _container.innerHTML = buildShell();
    bindEvents();
    renderConfigPreview();
    renderCached();
  });
  await refreshEvidence(false);
}

export function destroy() {
  _container = null;
  _latest = { evidence: null, decision: null, audit: null, debate: null, risk: null };
  _langCleanup?.();
  _langCleanup = null;
}

function bindEvents() {
  _container.querySelector('#btn-refresh-intelligence')?.addEventListener('click', () => refreshEvidence(true));
  _container.querySelector('#btn-intel-scan')?.addEventListener('click', runEvidence);
  _container.querySelector('#btn-decision-explain')?.addEventListener('click', runDecision);
  _container.querySelector('#btn-open-factor-lab')?.addEventListener('click', () => router.navigate('/factor-lab'));
  _container.querySelector('#btn-open-simulation')?.addEventListener('click', () => router.navigate('/simulation'));
  _container.querySelector('#btn-load-audit')?.addEventListener('click', loadAudit);
  _container.querySelector('#link-factor-lab')?.addEventListener('click', () => router.navigate('/factor-lab'));
  _container.querySelector('#link-simulation')?.addEventListener('click', () => router.navigate('/simulation'));
  _container.querySelector('#link-debate-desk')?.addEventListener('click', () => router.navigate('/debate-desk'));
  _container.querySelector('#link-risk-board')?.addEventListener('click', () => router.navigate('/risk-board'));
  _container.querySelector('#link-trading-ops')?.addEventListener('click', () => router.navigate('/trading-ops'));
  _container.querySelector('#link-connector-center')?.addEventListener('click', () => router.navigate('/connector-center'));
  _container.querySelector('#link-market-radar')?.addEventListener('click', () => router.navigate('/market-radar'));
  ['#intel-symbol', '#intel-universe', '#intel-mode', '#intel-providers'].forEach((selector) => {
    _container.querySelector(selector)?.addEventListener('input', renderConfigPreview);
    _container.querySelector(selector)?.addEventListener('change', renderConfigPreview);
  });
}

function readConfig() {
  const symbol = readSymbol(_container, '#intel-symbol', 'AAPL');
  const universe = readUniverse(_container.querySelector('#intel-universe')?.value, symbol);
  return {
    symbol,
    universe,
    query: _container.querySelector('#intel-query')?.value || '',
    horizon_days: Number(_container.querySelector('#intel-horizon')?.value) || 20,
    mode: _container.querySelector('#intel-mode')?.value || 'local',
    providers: splitTokens(_container.querySelector('#intel-providers')?.value || '', { delimiters: /[,|\s]+/ }),
  };
}

function renderConfigPreview() {
  if (!_container) return;
  const cfg = readConfig();
  const host = _container.querySelector('#intel-config-preview');
  if (!host) return;
  host.innerHTML = `
    <div class="config-token-strip__block">
      <span class="config-token-strip__label">${c('universe')}</span>
      ${renderTokenPreview(cfg.universe, { tone: 'accent', maxItems: 6 })}
    </div>
    <div class="config-token-strip__block">
      <span class="config-token-strip__label">${c('freeProviders')}</span>
      ${renderTokenPreview(cfg.providers, { tone: 'neutral', maxItems: 6 })}
    </div>
    <div class="config-token-strip__block">
      <span class="config-token-strip__label">${c('dataMode')}</span>
      ${renderTokenPreview([cfg.mode], { tone: 'neutral', maxItems: 1 })}
    </div>
  `;
}

async function refreshEvidence(showToast) {
  const cfg = readConfig();
  setLoading(_container.querySelector('#evidence-panel'));
  try {
    _latest.evidence = await api.intelligence.evidence(cfg.symbol, 12);
    renderEvidence(_latest.evidence?.items || []);
    if (showToast) toast.success(c('refresh'), localizedCount((_latest.evidence?.items || []).length));
  } catch (err) {
    renderError(_container.querySelector('#evidence-panel'), err);
  }
}

async function runEvidence() {
  const cfg = readConfig();
  setLoading(_container.querySelector('#evidence-panel'), c('scanning'));
  try {
    _latest.evidence = await api.intelligence.scan({
      universe: cfg.universe,
      query: cfg.query,
      live_connectors: cfg.mode !== 'local',
      mode: cfg.mode,
      providers: cfg.providers,
      quota_guard: true,
      limit: 20,
    });
    renderEvidence(_latest.evidence.items || []);
    toast.success(c('scan'), localizedCount(_latest.evidence.items?.length || 0));
  } catch (err) {
    renderError(_container.querySelector('#evidence-panel'), err);
    toast.error(c('scan'), err.message);
  }
}

async function runDecision() {
  const cfg = readConfig();
  setLoading(_container.querySelector('#decision-summary'), c('explaining'));
  setLoading(_container.querySelector('#debate-summary'), c('explaining'));
  setLoading(_container.querySelector('#risk-summary'), c('explaining'));
  try {
    const [decision, debatePayload, riskPayload] = await Promise.all([
      api.decision.explain({
        symbol: cfg.symbol,
        universe: cfg.universe,
        query: cfg.query,
        horizon_days: cfg.horizon_days,
        include_simulation: true,
        mode: cfg.mode,
        providers: cfg.providers,
        quota_guard: true,
      }),
      api.trading.debateRuns(cfg.symbol, 6).catch(() => ({ debates: [] })),
      api.trading.riskBoard(cfg.symbol, 6).catch(() => ({ approvals: [], latest_approval: null })),
    ]);
    _latest.decision = decision;
    _latest.debate = debatePayload?.debates?.[0] || null;
    _latest.risk = riskPayload?.latest_approval || riskPayload?.approvals?.[0] || null;
    renderDecision(decision);
    renderEvidence(decision.main_evidence || []);
    renderCounterEvidence(decision.counter_evidence || []);
    renderDebateSummary(_latest.debate);
    renderRiskSummary(_latest.risk);
    toast.success(c('explain'), actionLabel(decision.action || decision.mode || 'neutral'));
  } catch (err) {
    renderError(_container.querySelector('#decision-summary'), err);
    renderError(_container.querySelector('#debate-summary'), err);
    renderError(_container.querySelector('#risk-summary'), err);
    toast.error(c('explain'), err.message);
  }
}

async function loadAudit() {
  const cfg = readConfig();
  setLoading(_container.querySelector('#audit-panel'), c('auditLoading'));
  try {
    _latest.audit = await api.decision.auditTrail(cfg.symbol, 20);
    renderAudit(_latest.audit?.decisions || _latest.audit?.records || []);
  } catch (err) {
    renderError(_container.querySelector('#audit-panel'), err);
  }
}

function renderCached() {
  if (_latest.decision) renderDecision(_latest.decision);
  if (_latest.evidence) renderEvidence(_latest.evidence.items || []);
  if (_latest.decision) renderCounterEvidence(_latest.decision.counter_evidence || []);
  if (_latest.audit) renderAudit(_latest.audit.decisions || _latest.audit.records || []);
  renderDebateSummary(_latest.debate);
  renderRiskSummary(_latest.risk);
}

function renderEvidence(items) {
  _container.querySelector('#evidence-panel').innerHTML = renderEvidenceItems(items, { maxItems: 8, scroll: true });
}

function renderDecision(report) {
  const status = _container.querySelector('#decision-status');
  if (status) status.textContent = `${report.symbol || ''} / ${actionLabel(report.action || report.mode || 'shadow')}`;
  const verifier = report.verifier_checks || {};
  const triggers = (report.risk_triggers || []).length
    ? (report.risk_triggers || []).map((item) => `<li>${esc(item)}</li>`).join('')
    : `<li>${esc(c('noActiveTrigger'))}</li>`;
  const factors = renderFactorCards(report.factor_cards || [], { maxItems: 3, compact: true });
  const interval = report.confidence_interval || {};
  _container.querySelector('#decision-summary').innerHTML = `
    <div class="workbench-metric-grid">
      ${metric(c('action'), actionLabel(report.action), 'positive')}
      ${metric(c('expected'), pct(report.expected_return), 'positive')}
      ${metric(c('confidence'), num(report.confidence))}
      ${metric(c('weightMax'), pct(report.position_weight_range?.max || 0))}
    </div>
    <section class="workbench-section">
      <div class="workbench-section__title">${c('confidenceBand')}</div>
      <div class="workbench-kv-list compact-kv-list">
        <div class="workbench-kv-row"><span>${c('p05Label')}</span><strong>${pct(interval.lower)}</strong></div>
        <div class="workbench-kv-row"><span>${c('midLabel')}</span><strong>${pct(interval.center ?? report.expected_return)}</strong></div>
        <div class="workbench-kv-row"><span>p95</span><strong>${pct(interval.upper)}</strong></div>
        <div class="workbench-kv-row"><span>${c('auditStatus')}</span><strong>${esc(verifier.verdict || c('ready'))}</strong></div>
      </div>
    </section>
    <section class="workbench-section">
      <div class="workbench-section__title">${c('verifier')}</div>
      <div class="factor-checklist">
        <div class="factor-check-row"><span>${c('leakage')}</span><strong class="${verifier.leakage_pass ? 'is-pass' : 'is-watch'}">${boolLabel(verifier.leakage_pass)}</strong></div>
        <div class="factor-check-row"><span>${c('modeLabel')}</span><strong class="is-pass">${esc(report.mode || c('ready'))}</strong></div>
        <div class="factor-check-row"><span>${c('evidenceCount')}</span><strong class="is-pass">${(report.main_evidence || []).length}</strong></div>
        <div class="factor-check-row"><span>${c('counterCount')}</span><strong class="${(report.counter_evidence || []).length ? 'is-watch' : 'is-pass'}">${(report.counter_evidence || []).length}</strong></div>
      </div>
    </section>
    <section class="workbench-section">
      <div class="workbench-section__title">${c('triggers')}</div>
      <div class="workbench-report-text"><ul>${triggers}</ul></div>
    </section>
    <section class="workbench-section">
      <div class="workbench-section__title">${c('factorView')}</div>
      ${factors}
    </section>
    <section class="workbench-section">
      <div class="workbench-section__title">${c('simulationBridge')}</div>
      <div class="workbench-report-text">${esc(report.simulation ? c('bridgeSimHint') : c('noEmbeddedSimulation'))}</div>
    </section>
  `;
}

function renderCounterEvidence(items) {
  const host = _container.querySelector('#counter-panel');
  if (!items?.length) {
    host.innerHTML = renderCounterReadyState();
    return;
  }
  host.innerHTML = renderEvidenceItems(items, { maxItems: 5, scroll: true });
}

function renderAudit(records) {
  const host = _container.querySelector('#audit-panel');
  if (!records?.length) {
    host.innerHTML = renderAuditReadyState();
    return;
  }
  host.innerHTML = `
    <div class="workbench-kv-list compact-kv-list">
      ${records.slice(0, 6).map((record) => `
        <div class="workbench-kv-row">
          <span>${esc(record.decision_id || record.symbol || '-')}</span>
          <strong>${esc(record.status || record.model_version || record.feature_time || '-')}</strong>
        </div>
      `).join('')}
    </div>
  `;
}

function renderDebateSummary(debate) {
  const host = _container.querySelector('#debate-summary');
  if (!host) return;
  if (!debate) {
    host.innerHTML = renderDebateReadyState();
    return;
  }
  host.innerHTML = `
    <div class="workbench-metric-grid">
      ${metric(c('judge'), actionLabel(debate.judge_verdict || debate.recommended_action), 'positive')}
      ${metric(c('confidence'), pct(debate.judge_confidence || 0))}
      ${metric(c('dispute'), pct(debate.dispute_score || 0), 'risk')}
      ${metric(c('humanReview'), boolLabel(debate.requires_human_review), debate.requires_human_review ? 'risk' : 'positive')}
    </div>
    <div class="workbench-kv-list compact-kv-list">
      <div class="workbench-kv-row"><span>${c('latestDebate')}</span><strong>${esc(debate.debate_id || '-')}</strong></div>
      <div class="workbench-kv-row"><span>${c('judge')}</span><strong>${actionLabel(debate.judge_verdict || debate.recommended_action)}</strong></div>
      <div class="workbench-kv-row"><span>${c('bullLabel')}</span><strong>${esc((debate.bull_thesis || '-').slice(0, 44))}</strong></div>
      <div class="workbench-kv-row"><span>${c('bearLabel')}</span><strong>${esc((debate.bear_thesis || '-').slice(0, 44))}</strong></div>
    </div>
  `;
}

function renderRiskSummary(approval) {
  const host = _container.querySelector('#risk-summary');
  if (!host) return;
  if (!approval) {
    host.innerHTML = renderRiskReadyState();
    return;
  }
  const blocks = approval.hard_blocks || [];
  host.innerHTML = `
    <div class="workbench-metric-grid">
      ${metric(c('verdict'), actionLabel(approval.verdict), approval.verdict === 'approve' ? 'positive' : 'risk')}
      ${metric(c('kelly'), pct(approval.kelly_fraction || 0))}
      ${metric(c('weightMax'), pct(approval.max_position_weight || approval.recommended_weight || 0))}
      ${metric(c('ttl'), `${approval.signal_ttl_minutes || 0}m`)}
    </div>
    <div class="workbench-kv-list compact-kv-list">
      <div class="workbench-kv-row"><span>${c('latestRisk')}</span><strong>${esc(approval.approval_id || '-')}</strong></div>
      <div class="workbench-kv-row"><span>${c('action')}</span><strong>${actionLabel(approval.approved_action || approval.requested_action)}</strong></div>
      <div class="workbench-kv-row"><span>${c('hardBlock')}</span><strong>${blocks.length ? blocks.length : c('no')}</strong></div>
      <div class="workbench-kv-row"><span>${c('notional')}</span><strong>${esc(approval.recommended_notional ?? '-')}</strong></div>
    </div>
  `;
}

function renderDecisionReadyState() {
  return `
    <div class="functional-empty compact-functional-empty">
      <div class="functional-empty__eyebrow">${c('decisionSummary')}</div>
      <h3>${c('decisionEmpty')}</h3>
      <p>${c('decisionHint')}</p>
      <div class="preview-step-grid">
        <div class="preview-step"><span>${c('actionScan')}</span><strong>${c('ready')}</strong></div>
        <div class="preview-step"><span>${c('actionDebate')}</span><strong>${c('nextActions')}</strong></div>
        <div class="preview-step"><span>${c('actionRisk')}</span><strong>${c('latestRisk')}</strong></div>
        <div class="preview-step"><span>${c('actionPaper')}</span><strong>${c('paperModeValue')}</strong></div>
      </div>
    </div>
  `;
}

function renderCounterReadyState() {
  return `
    <div class="functional-empty compact-functional-empty">
      <div class="functional-empty__eyebrow">${c('counter')}</div>
      <h3>${c('noCounter')}</h3>
      <p>${c('decisionHint')}</p>
    </div>
  `;
}

function renderAuditReadyState() {
  return `
    <div class="functional-empty compact-functional-empty">
      <div class="functional-empty__eyebrow">${c('audit')}</div>
      <h3>${c('noAudit')}</h3>
      <p>${c('noAuditHint')}</p>
    </div>
  `;
}

function renderDebateReadyState() {
  return `
    <div class="functional-empty compact-functional-empty">
      <div class="functional-empty__eyebrow">${c('debate')}</div>
      <h3>${c('noDebate')}</h3>
      <p>${c('noDebateHint')}</p>
    </div>
  `;
}

function renderRiskReadyState() {
  return `
    <div class="functional-empty compact-functional-empty">
      <div class="functional-empty__eyebrow">${c('risk')}</div>
      <h3>${c('noRisk')}</h3>
      <p>${c('noRiskHint')}</p>
    </div>
  `;
}

function renderWorkbenchLinks() {
  return `
    <div class="workbench-link-list">
      <button class="workbench-link-row" id="link-factor-lab"><strong>${c('bridgeFactor')}</strong><span>${c('bridgeFactorHint')}</span></button>
      <button class="workbench-link-row" id="link-simulation"><strong>${c('bridgeSim')}</strong><span>${c('bridgeSimHint')}</span></button>
      <button class="workbench-link-row" id="link-debate-desk"><strong>${c('bridgeDebate')}</strong><span>${c('bridgeDebateHint')}</span></button>
      <button class="workbench-link-row" id="link-risk-board"><strong>${c('bridgeRisk')}</strong><span>${c('bridgeRiskHint')}</span></button>
      <button class="workbench-link-row" id="link-trading-ops"><strong>${c('bridgeOps')}</strong><span>${c('bridgeOpsHint')}</span></button>
      <button class="workbench-link-row" id="link-connector-center"><strong>${c('bridgeConnector')}</strong><span>${c('bridgeConnectorHint')}</span></button>
      <button class="workbench-link-row" id="link-market-radar"><strong>${c('bridgeRadar')}</strong><span>${c('bridgeRadarHint')}</span></button>
    </div>
  `;
}

function renderConnectedActions() {
  return `
    <section class="workbench-section">
      <div class="workbench-section__title">${c('nextActions')}</div>
      <div class="factor-checklist">
        <div class="factor-check-row"><span>${c('actionScan')}</span><strong class="is-pass">${c('ready')}</strong></div>
        <div class="factor-check-row"><span>${c('actionDebate')}</span><strong class="is-watch">${c('latestDebate')}</strong></div>
        <div class="factor-check-row"><span>${c('actionRisk')}</span><strong class="is-watch">${c('latestRisk')}</strong></div>
        <div class="factor-check-row"><span>${c('actionPaper')}</span><strong class="is-pass">${c('paperModeValue')}</strong></div>
      </div>
      <div class="workbench-report-text" style="margin-top:10px">${c('workbenchHint')}</div>
    </section>
  `;
}
