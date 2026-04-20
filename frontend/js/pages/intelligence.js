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
  renderSimulationResult,
  renderTokenPreview,
  setLoading,
  splitTokens,
  statusBadge,
} from './workbench-utils.js?v=8';

let _container = null;
let _langCleanup = null;
let _latest = {
  evidence: null,
  decision: null,
  audit: null,
};

const COPY = {
  en: {
    title: 'Decision Cockpit',
    subtitle: 'Evidence chain, critic checks, risk triggers, and shadow-mode decisions',
    refresh: 'Refresh',
    setupTitle: 'Shadow Decision Setup',
    setupSub: 'Research support only. Broker execution remains gated elsewhere.',
    symbol: 'Symbol',
    horizon: 'Horizon Days',
    universe: 'Universe',
    query: 'Research Question',
    queryValue: 'Explain the current evidence, risk, and model disagreement before any action.',
    scan: 'Scan Evidence',
    explain: 'Explain Decision',
    openFactor: 'Open Factor Lab',
    openSimulation: 'Open Simulation',
    decisionSummary: 'Decision Report',
    decisionEmpty: 'No decision report yet',
    decisionHint: 'Run Explain Decision to generate evidence-backed guidance.',
    evidence: 'Evidence Feed',
    counter: 'Counter Evidence',
    audit: 'Audit Trail',
    workbenches: 'Connected Workbenches',
    loadAudit: 'Load Audit',
    scanning: 'Scanning evidence...',
    explaining: 'Building decision report...',
    auditLoading: 'Loading audit trail...',
    noCounter: 'No counter evidence in the latest report.',
    noAudit: 'No audit records yet',
    noAuditHint: 'Generate a decision report to start the shadow log.',
    ready: 'shadow mode',
    dataMode: 'Data Mode',
    freeProviders: 'Free Providers',
    modeLocal: 'local / frozen-safe',
    modeMixed: 'mixed free-tier live',
    modeLive: 'live connectors only',
    evidenceUnit: 'items',
  },
  zh: {
    title: '智能决策驾驶舱',
    subtitle: '证据链、反方检验、风险触发与影子模式决策',
    refresh: '刷新',
    setupTitle: '影子决策设置',
    setupSub: '仅用于研究支持，实盘执行仍由执行层门控。',
    symbol: '股票代码',
    horizon: '预测天数',
    universe: '股票池',
    query: '研究问题',
    queryValue: '解释当前证据、风险和模型分歧，再给出任何动作建议。',
    scan: '扫描证据',
    explain: '解释决策',
    openFactor: '打开因子实验室',
    openSimulation: '打开情景模拟',
    decisionSummary: '决策报告',
    decisionEmpty: '暂无决策报告',
    decisionHint: '点击解释决策，生成带证据链的建议。',
    evidence: '证据流',
    counter: '反方证据',
    audit: '审计追踪',
    workbenches: '关联工作台',
    loadAudit: '加载审计',
    scanning: '正在扫描证据...',
    explaining: '正在生成决策报告...',
    auditLoading: '正在加载审计追踪...',
    noCounter: '最新报告中暂无反方证据。',
    noAudit: '暂无审计记录',
    noAuditHint: '生成一次决策报告后会进入影子日志。',
    ready: '影子模式',
    dataMode: '数据模式',
    freeProviders: '免费数据源',
    modeLocal: '本地 / 冻结安全',
    modeMixed: '混合免费实时',
    modeLive: '仅实时连接器',
    evidenceUnit: '条',
  },
};

export async function render(container) {
  _container = container;
  container.innerHTML = buildShell();
  bindEvents(container);
  renderConfigPreview();
  _langCleanup ||= onLangChange(() => {
    if (_container?.isConnected) {
      _container.innerHTML = buildShell();
      bindEvents(_container);
      renderConfigPreview();
      renderCached(_container);
    }
  });
  await refreshEvidence(container, false);
}

export function destroy() {
  _container = null;
  _latest = { evidence: null, decision: null, audit: null };
  _langCleanup?.();
  _langCleanup = null;
}

function c(key) {
  const current = getLang() === 'zh' ? 'zh' : 'en';
  return COPY[current][key] || COPY.en[key] || key;
}

function t(en, zh) {
  return getLang() === 'zh' ? zh : en;
}

function localizedCount(value, singular = 'items', zhUnit = '条') {
  return getLang() === 'zh' ? `${value} ${zhUnit}` : `${value} ${singular}`;
}

function boolLabel(value) {
  return value ? t('yes', '是') : t('no', '否');
}

function actionLabel(value) {
  const normalized = String(value || '').trim().toLowerCase();
  const map = {
    approve: t('approve', '批准'),
    reduce: t('reduce', '缩减'),
    reject: t('reject', '拒绝'),
    halt: t('halt', '暂停'),
    long: t('long', '看多'),
    short: t('short', '看空'),
    neutral: t('neutral', '中性'),
    block: t('block', '阻止'),
    hold: t('hold', '持有'),
    review: t('review', '复核'),
    running: t('running', '运行中'),
    pending: t('pending', '待处理'),
    recorded: t('recorded', '已记录'),
  };
  return map[normalized] || String(value || '-');
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
          <div class="card-header"><span class="card-title">${c('workbenches')}</span></div>
          <div class="card-body">
            ${renderWorkbenchLinks()}
            ${renderConnectedActions()}
          </div>
        </section>
      </div>
    </div>
  </div>`;
}

function bindEvents(container) {
  container.querySelector('#btn-refresh-intelligence')?.addEventListener('click', () => refreshEvidence(container, true));
  container.querySelector('#btn-intel-scan')?.addEventListener('click', () => runEvidence(container));
  container.querySelector('#btn-decision-explain')?.addEventListener('click', () => runDecision(container));
  container.querySelector('#btn-open-factor-lab')?.addEventListener('click', () => router.navigate('/factor-lab'));
  container.querySelector('#btn-open-simulation')?.addEventListener('click', () => router.navigate('/simulation'));
  container.querySelector('#link-factor-lab')?.addEventListener('click', () => router.navigate('/factor-lab'));
  container.querySelector('#link-simulation')?.addEventListener('click', () => router.navigate('/simulation'));
  container.querySelector('#link-debate-desk')?.addEventListener('click', () => router.navigate('/debate-desk'));
  container.querySelector('#link-risk-board')?.addEventListener('click', () => router.navigate('/risk-board'));
  container.querySelector('#link-trading-ops')?.addEventListener('click', () => router.navigate('/trading-ops'));
  container.querySelector('#link-connector-center')?.addEventListener('click', () => router.navigate('/connector-center'));
  container.querySelector('#link-market-radar')?.addEventListener('click', () => router.navigate('/market-radar'));
  container.querySelector('#btn-load-audit')?.addEventListener('click', () => loadAudit(container));
  ['#intel-symbol', '#intel-universe', '#intel-mode', '#intel-providers'].forEach((selector) => {
    container.querySelector(selector)?.addEventListener('input', renderConfigPreview);
    container.querySelector(selector)?.addEventListener('change', renderConfigPreview);
  });
}

function readConfig(container) {
  const symbol = readSymbol(container, '#intel-symbol', 'AAPL');
  const universe = readUniverse(container.querySelector('#intel-universe')?.value, symbol);
  return {
    symbol,
    universe,
    query: container.querySelector('#intel-query')?.value || '',
    horizon_days: Number(container.querySelector('#intel-horizon')?.value) || 20,
    mode: container.querySelector('#intel-mode')?.value || 'local',
    providers: splitTokens(container.querySelector('#intel-providers')?.value || '', { delimiters: /[,|\s]+/ }),
  };
}

function renderConfigPreview() {
  if (!_container) return;
  const cfg = readConfig(_container);
  const host = _container.querySelector('#intel-config-preview');
  if (!host) return;
  host.innerHTML = `
    <div class="config-token-strip__block">
      <span class="config-token-strip__label">${t('Universe', '股票池')}</span>
      ${renderTokenPreview(cfg.universe, { tone: 'accent', maxItems: 6 })}
    </div>
    <div class="config-token-strip__block">
      <span class="config-token-strip__label">${t('Providers', '数据源')}</span>
      ${renderTokenPreview(cfg.providers, { tone: 'neutral', maxItems: 6 })}
    </div>
    <div class="config-token-strip__block">
      <span class="config-token-strip__label">${t('Mode', '模式')}</span>
      ${renderTokenPreview([cfg.mode], { tone: 'neutral', maxItems: 1 })}
    </div>
  `;
}

async function refreshEvidence(container, showToast) {
  const cfg = readConfig(container);
  setLoading(container.querySelector('#evidence-panel'));
  try {
    _latest.evidence = await api.intelligence.evidence(cfg.symbol, 12);
    renderEvidence(container, _latest.evidence?.items || []);
    if (showToast) toast.success(c('refresh'), localizedCount((_latest.evidence?.items || []).length, 'items', c('evidenceUnit')));
  } catch (err) {
    renderError(container.querySelector('#evidence-panel'), err);
  }
}

async function runEvidence(container) {
  const cfg = readConfig(container);
  setLoading(container.querySelector('#evidence-panel'), c('scanning'));
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
    renderEvidence(container, _latest.evidence.items || []);
    toast.success(c('scan'), localizedCount(_latest.evidence.items?.length || 0, 'items', c('evidenceUnit')));
  } catch (err) {
    renderError(container.querySelector('#evidence-panel'), err);
    toast.error(c('scan'), err.message);
  }
}

async function runDecision(container) {
  const cfg = readConfig(container);
  setLoading(container.querySelector('#decision-summary'), c('explaining'));
  try {
    _latest.decision = await api.decision.explain({
      symbol: cfg.symbol,
      universe: cfg.universe,
      query: cfg.query,
      horizon_days: cfg.horizon_days,
      include_simulation: true,
      mode: cfg.mode,
      providers: cfg.providers,
      quota_guard: true,
    });
    renderDecision(container, _latest.decision);
    renderEvidence(container, _latest.decision.main_evidence || []);
    renderCounterEvidence(container, _latest.decision.counter_evidence || []);
    toast.success(c('explain'), (_latest.decision.action || '').toUpperCase());
  } catch (err) {
    renderError(container.querySelector('#decision-summary'), err);
    toast.error(c('explain'), err.message);
  }
}

async function loadAudit(container) {
  const cfg = readConfig(container);
  setLoading(container.querySelector('#audit-panel'), c('auditLoading'));
  try {
    _latest.audit = await api.decision.auditTrail(cfg.symbol, 20);
    renderAudit(container, _latest.audit?.decisions || _latest.audit?.records || []);
  } catch (err) {
    renderError(container.querySelector('#audit-panel'), err);
  }
}

function renderCached(container) {
  if (_latest.decision) renderDecision(container, _latest.decision);
  if (_latest.evidence) renderEvidence(container, _latest.evidence.items || []);
  if (_latest.decision) renderCounterEvidence(container, _latest.decision.counter_evidence || []);
  if (_latest.audit) renderAudit(container, _latest.audit.decisions || _latest.audit.records || []);
}

function renderDecision(container, report) {
  const status = container.querySelector('#decision-status');
  if (status) status.textContent = `${report.symbol || ''} / ${report.action || ''}`;
  const verifier = report.verifier_checks || {};
  const triggers = (report.risk_triggers || []).length
    ? (report.risk_triggers || []).map((item) => `<li>${esc(item)}</li>`).join('')
    : `<li>${esc(t('No active trigger in the current report.', '当前报告中没有激活的风险触发。'))}</li>`;
  const factors = renderFactorCards(report.factor_cards || [], { maxItems: 3, compact: true });
  const simulation = report.simulation
    ? renderSimulationResult(report.simulation)
    : `<div class="workbench-report-text">${esc(t('No embedded simulation attached yet. Open Simulation to replay the current thesis.', '当前还没有附带内嵌模拟。可打开情景模拟来回放本次判断。'))}</div>`;
  const interval = report.confidence_interval || {};
  const auditTrail = Array.isArray(report.audit_trail) ? report.audit_trail.slice(0, 4) : [];
  const evidenceCount = (report.main_evidence || []).length;
  const conflictCount = Number(report.evidence_conflicts?.conflict_count || 0);
  const liveAge = formatLiveAge(report.live_data_age);
  const dataVersions = formatVersionMap(report.data_versions || {});
  const modelVersions = formatVersionMap(report.model_versions || {});
  const providerLadder = formatProviderLadder(report.connector_lineage);
  container.querySelector('#decision-summary').innerHTML = `
    <div class="workbench-metric-grid">
      ${metric(t('Action', '动作'), actionLabel(report.action))}
      ${metric(t('Expected', '预期收益'), pct(report.expected_return), 'positive')}
      ${metric(t('Confidence', '置信度'), num(report.confidence))}
      ${metric(t('Weight Max', '权重上限'), pct(report.position_weight_range?.max || 0))}
      ${metric(t('Evidence', '证据数量'), evidenceCount || '-', evidenceCount ? 'positive' : '')}
      ${metric(t('Live Age', '实时数据时效'), liveAge, liveAge === '-' ? '' : 'risk')}
    </div>
    <div class="workbench-kv-list compact-kv-list">
      <div class="workbench-kv-row"><span>${t('Confidence Interval', '置信区间')}</span><strong>${pct(interval.lower)} / ${pct(interval.center)} / ${pct(interval.upper)}</strong></div>
      <div class="workbench-kv-row"><span>${t('Verifier', '验证器')}</span><strong>${esc(actionLabel(verifier.verdict || 'review'))} / ${t('leakage', '泄漏')} ${boolLabel(!!verifier.leakage_pass)}</strong></div>
      <div class="workbench-kv-row"><span>${t('Execution Guard', '执行门控')}</span><strong>${esc(verifier.execution_guard || t('shadow_only_no_order_created', '仅影子模式，不创建订单'))}</strong></div>
      <div class="workbench-kv-row"><span>${t('Evidence Quality', '证据质量')}</span><strong>${num(verifier.as_of_safe_ratio)}</strong></div>
    </div>
    <div class="workbench-section">
      <div class="workbench-section__title">${t('Decision Ledger', '决策台账')}</div>
      <div class="workbench-kv-list compact-kv-list">
        <div class="workbench-kv-row"><span>${t('Decision ID', '决策 ID')}</span><strong>${esc(report.decision_id || '-')}</strong></div>
        <div class="workbench-kv-row"><span>${t('Decision Time', '决策时间')}</span><strong>${esc(report.decision_time || report.generated_at || '-')}</strong></div>
        <div class="workbench-kv-row"><span>${t('Evidence Count', '证据数量')}</span><strong>${esc(evidenceCount || 0)}</strong></div>
        <div class="workbench-kv-row"><span>${t('Live Age', '实时数据时效')}</span><strong>${esc(liveAge)}</strong></div>
        <div class="workbench-kv-row"><span>${t('Data Versions', '数据版本')}</span><strong>${esc(dataVersions)}</strong></div>
        <div class="workbench-kv-row"><span>${t('Model Versions', '模型版本')}</span><strong>${esc(modelVersions)}</strong></div>
        <div class="workbench-kv-row"><span>${t('Provider Ladder', '来源梯队')}</span><strong>${esc(providerLadder)}</strong></div>
      </div>
    </div>
    <div class="workbench-section">
      <div class="workbench-section__title">${t('Verifier Snapshot', '验证器快照')}</div>
      <div class="preview-step-grid">
        <div class="preview-step"><span>${t('Verdict', '结论')}</span><strong>${esc(actionLabel(verifier.verdict || 'review'))}</strong></div>
        <div class="preview-step"><span>${t('Leakage', '泄漏检查')}</span><strong>${boolLabel(!!verifier.leakage_pass)}</strong></div>
        <div class="preview-step"><span>${t('Conflicts', '冲突数量')}</span><strong>${esc(conflictCount || 0)}</strong></div>
        <div class="preview-step"><span>${t('Quota Mode', '额度模式')}</span><strong>${esc(String(report.quota_mode ?? t('shadow', '影子')))}</strong></div>
      </div>
    </div>
    <div class="workbench-section">
      <div class="workbench-section__title">${t('Risk Triggers', '风险触发')}</div>
      <div class="workbench-report-text"><ul>${triggers}</ul></div>
    </div>
    <div class="workbench-section">
      <div class="workbench-section__title">${t('Factor Contribution', '因子贡献')}</div>
      ${factors}
    </div>
    <div class="workbench-section">
      <div class="workbench-section__title">${t('Audit Snapshot', '审计快照')}</div>
      <div class="preview-step-grid">
        ${(auditTrail.length ? auditTrail : [
          t('source linked evidence', '来源关联证据'),
          t('as-of safe features', '时点安全特征'),
          t('counter evidence checked', '反方证据已检查'),
          t('shadow log ready', '影子日志已就绪'),
        ]).map((step) => `<div class="preview-step"><span>${esc(step)}</span><strong>${t('ready', '就绪')}</strong></div>`).join('')}
      </div>
    </div>
    <div class="workbench-section">
      <div class="workbench-section__title">${t('Embedded Simulation', '内嵌模拟')}</div>
      ${simulation}
    </div>`;
}

function renderEvidence(container, items) {
  container.querySelector('#evidence-panel').innerHTML = renderEvidenceItems(items, { maxItems: 8, scroll: true });
}

function renderCounterEvidence(container, items) {
  if (!items?.length) {
    container.querySelector('#counter-panel').innerHTML = renderCounterReadyState();
    return;
  }
  const providers = Array.from(new Set(items.map((item) => item.provider).filter(Boolean)));
  const avgConfidence = items.reduce((acc, item) => acc + Number(item.confidence || 0), 0) / Math.max(1, items.length);
  container.querySelector('#counter-panel').innerHTML = `
    <div class="workbench-metric-grid">
      ${metric(t('Counter', '反方条目'), items.length, 'risk')}
      ${metric(t('Providers', '来源数'), providers.length || '-')}
      ${metric(t('Avg Q', '平均质量'), num(avgConfidence))}
      ${metric(t('Critic', '验证器'), t('armed', '已启用'), 'risk')}
    </div>
    ${renderEvidenceItems(items, { maxItems: 6, scroll: true })}
    <div class="workbench-section">
      <div class="workbench-section__title">${t('Critic Focus', '验证器关注点')}</div>
      <div class="factor-checklist">
        <div class="factor-check-row"><span>${t('Weak source pressure', '弱来源压力')}</span><strong>${esc(providers.join(', ') || '-')}</strong></div>
        <div class="factor-check-row"><span>${t('Freshness check', '新鲜度检查')}</span><strong class="is-review">${t('active', '活跃')}</strong></div>
        <div class="factor-check-row"><span>${t('Contrarian read', '反向解读')}</span><strong>${t('enabled', '已启用')}</strong></div>
      </div>
    </div>`;
}

function renderAudit(container, decisions) {
  if (!decisions.length) {
    container.querySelector('#audit-panel').innerHTML = renderAuditReadyState();
    return;
  }
  const first = decisions[0] || {};
  container.querySelector('#audit-panel').innerHTML = `
    <div class="workbench-metric-grid">
      ${metric(t('Records', '记录数'), decisions.length, 'positive')}
      ${metric(t('Latest', '最新状态'), actionLabel(first.status || first.action || 'recorded'))}
      ${metric(t('Feature Time', '特征时点'), first.feature_time || first.decision_time || t('as-of safe', '时点安全'))}
      ${metric(t('Model', '模型'), first.model_version || 'shadow-stack')}
    </div>
    <div class="workbench-kv-list compact-kv-list">
      ${decisions.slice(0, 5).map((decision) => `
        <div class="workbench-kv-row">
          <span>${esc(decision.decision_id || decision.status || t('audit', '审计'))}</span>
          <strong>${esc(decision.symbol || decision.model_version || '-')}</strong>
        </div>
      `).join('')}
      <div class="workbench-kv-row"><span>${t('Latest Status', '最新状态')}</span><strong>${esc(actionLabel(first.status || first.action || 'recorded'))}</strong></div>
      <div class="workbench-kv-row"><span>${t('Feature Time', '特征时点')}</span><strong>${esc(first.feature_time || first.decision_time || t('as-of safe', '时点安全'))}</strong></div>
      <div class="workbench-kv-row"><span>${t('Model Version', '模型版本')}</span><strong>${esc(first.model_version || 'shadow-stack')}</strong></div>
    </div>`;
}

function renderDecisionReadyState() {
  return `
    <div class="functional-empty decision-ready-state">
      <div>
        <div class="functional-empty__eyebrow">${t('Decision Readiness', '决策准备度')}</div>
        <h3>${c('decisionEmpty')}</h3>
        <p>${c('decisionHint')}</p>
      </div>
      <div class="workbench-metric-grid functional-empty__metrics">
        ${metric(t('Evidence', '证据'), t('pending', '待扫描'))}
        ${metric(t('Verifier', '验证器'), t('armed', '已启用'), 'positive')}
        ${metric(t('Leakage', '泄漏检查'), t('as-of', '时点安全'))}
        ${metric(t('Mode', '模式'), t('shadow', '影子'))}
      </div>
      <div class="factor-checklist">
        <div class="factor-check-row"><span>${t('Scan source-linked evidence', '扫描带来源证据')}</span><strong>${t('next', '下一步')}</strong></div>
        <div class="factor-check-row"><span>${t('Generate factor and risk explanation', '生成因子与风险解释')}</span><strong>${t('ready', '就绪')}</strong></div>
        <div class="factor-check-row"><span>${t('No broker execution from this page', '本页不触发券商执行')}</span><strong class="is-pass">${t('pass', '通过')}</strong></div>
      </div>
    </div>`;
}

function renderCounterReadyState() {
  return `
    <div class="functional-empty compact-functional-empty">
      <div>
        <div class="functional-empty__eyebrow">${t('Counter Evidence', '反方证据')}</div>
        <h3>${c('noCounter')}</h3>
        <p>${t('The critic will list model disagreement, weak sources, stale signals, and risk conflicts after a decision report is generated.', '生成决策报告后，验证器会列出模型分歧、弱来源、旧信号和风险冲突。')}</p>
      </div>
      <div class="factor-checklist">
        <div class="factor-check-row"><span>${t('Source reliability', '来源可靠性')}</span><strong>${t('watch', '观察')}</strong></div>
        <div class="factor-check-row"><span>${t('Future leakage', '未来信息泄漏')}</span><strong class="is-pass">${t('guarded', '已防护')}</strong></div>
        <div class="factor-check-row"><span>${t('Overconfidence', '过度置信')}</span><strong>${t('critic', '验证器')}</strong></div>
        <div class="factor-check-row"><span>${t('Regime conflict', '市场状态冲突')}</span><strong>${t('pending', '待检查')}</strong></div>
      </div>
    </div>`;
}

function renderAuditReadyState() {
  return `
    <div class="functional-empty compact-functional-empty">
      <div>
        <div class="functional-empty__eyebrow">${t('Audit Trail', '审计追踪')}</div>
        <h3>${c('noAudit')}</h3>
        <p>${c('noAuditHint')}</p>
      </div>
      <div class="workbench-kv-list compact-kv-list">
        <div class="workbench-kv-row"><span>${t('Data snapshot', '数据快照')}</span><strong>${t('waiting', '等待生成')}</strong></div>
        <div class="workbench-kv-row"><span>${t('Model version', '模型版本')}</span><strong>shadow-stack</strong></div>
        <div class="workbench-kv-row"><span>${t('Feature time', '特征时点')}</span><strong>${t('as-of safe', '时点安全')}</strong></div>
        <div class="workbench-kv-row"><span>${t('Outcome log', '结果复盘')}</span><strong>${t('after decision', '决策后记录')}</strong></div>
      </div>
    </div>`;
}

function renderConnectedActions() {
  return `
    <div class="workbench-section connected-actions">
      <div class="workbench-section__title">${t('Connected Actions', '关联动作')}</div>
      <div class="factor-checklist">
        <div class="factor-check-row"><span>${t('Promote validated factors in Factor Lab', '在因子实验室升格通过门禁的因子')}</span><strong>${t('research', '研究')}</strong></div>
        <div class="factor-check-row"><span>${t('Replay the current thesis in Simulation', '在模拟工作台回放当前判断')}</span><strong>${t('what-if', '推演')}</strong></div>
        <div class="factor-check-row"><span>${t('Keep every recommendation in shadow log', '所有建议进入影子日志')}</span><strong class="is-pass">${t('on', '开启')}</strong></div>
      </div>
    </div>`;
}

function renderWorkbenchLinks() {
  return `
    <div class="workbench-link-list">
      <button class="workbench-link-row" id="link-factor-lab"><strong>${t('Factor Lab', '因子实验室')}</strong><span>${t('Discover candidates, gate IC/RankIC, and review FactorCards.', '发现候选因子、执行 IC/RankIC 门禁，并检查因子卡。')}</span></button>
      <button class="workbench-link-row" id="link-simulation"><strong>${t('Simulation', '情景模拟')}</strong><span>${t('Replay shocks, Monte Carlo paths, and historical analogs.', '回放冲击、Monte Carlo 路径与历史相似事件。')}</span></button>
      <button class="workbench-link-row" id="link-debate-desk"><strong>${t('Debate Desk', '辩论台')}</strong><span>${t('Run bull vs bear rounds, judge verdicts, and confidence shifts.', '查看多空辩论回合、裁判结论与置信度变化。')}</span></button>
      <button class="workbench-link-row" id="link-risk-board"><strong>${t('Risk Board', '风控板')}</strong><span>${t('Review risk approvals, Kelly caps, drawdown gates, and blockers.', '查看风控审批、Kelly 上限、回撤门禁与阻断项。')}</span></button>
      <button class="workbench-link-row" id="link-trading-ops"><strong>${t('Trading Ops', '交易运维')}</strong><span>${t('Manage schedules, watchlist state, alerts, and latest review status.', '管理调度、自选池、告警与最新复盘状态。')}</span></button>
      <button class="workbench-link-row" id="link-connector-center"><strong>${t('Connector Center', '数据源中心')}</strong><span>${t('Free-tier source health, quota guard, and sample payloads.', '查看免费数据源健康状态、额度保护与样例载荷。')}</span></button>
      <button class="workbench-link-row" id="link-market-radar"><strong>${t('Market Radar', '市场雷达')}</strong><span>${t('Live evidence stream with provider attribution.', '浏览带来源归因的实时证据流。')}</span></button>
    </div>`;
}

function formatVersionMap(map) {
  const entries = Object.entries(map || {}).filter(([, value]) => value != null && String(value).trim());
  if (!entries.length) return '-';
  return entries.slice(0, 3).map(([key, value]) => `${key}:${String(value)}`).join(' | ');
}

function formatProviderLadder(lineage) {
  const providers = lineage?.free_tier_registry?.providers || [];
  if (!providers.length) return '-';
  return providers.slice(0, 4).map((row) => row.provider || row.provider_id || row.display_name || 'source').join(' -> ');
}

function formatLiveAge(liveAge) {
  if (!liveAge || liveAge.avg_age_hours == null) return '-';
  const avg = Number(liveAge.avg_age_hours || 0);
  const max = Number(liveAge.max_age_hours || 0);
  return getLang() === 'zh'
    ? `平均 ${avg.toFixed(1)}h / 最大 ${max.toFixed(1)}h`
    : `avg ${avg.toFixed(1)}h / max ${max.toFixed(1)}h`;
}
