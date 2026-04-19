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
                <label class="form-label">Data Mode</label>
                <select class="form-input" id="intel-mode">
                  <option value="local">local / frozen-safe</option>
                  <option value="mixed">mixed free-tier live</option>
                  <option value="live">live connectors only</option>
                </select>
              </div>
              <div class="form-group">
                <label class="form-label">Free Providers</label>
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
    if (showToast) toast.success(c('refresh'), `${(_latest.evidence?.items || []).length} items`);
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
    toast.success(c('scan'), `${_latest.evidence.items?.length || 0} items`);
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
    : '<li>No active trigger in the current report.</li>';
  const factors = renderFactorCards(report.factor_cards || [], { maxItems: 3, compact: true });
  const simulation = report.simulation
    ? renderSimulationResult(report.simulation)
    : '<div class="workbench-report-text">No embedded simulation attached yet. Open Simulation to replay the current thesis.</div>';
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
      ${metric('Action', String(report.action || '').toUpperCase())}
      ${metric('Expected', pct(report.expected_return), 'positive')}
      ${metric('Confidence', num(report.confidence))}
      ${metric('Weight Max', pct(report.position_weight_range?.max || 0))}
      ${metric('Evidence', evidenceCount || '-', evidenceCount ? 'positive' : '')}
      ${metric('Live Age', liveAge, liveAge === '-' ? '' : 'risk')}
    </div>
    <div class="workbench-kv-list compact-kv-list">
      <div class="workbench-kv-row"><span>Confidence Interval</span><strong>${pct(interval.lower)} / ${pct(interval.center)} / ${pct(interval.upper)}</strong></div>
      <div class="workbench-kv-row"><span>Verifier</span><strong>${esc(verifier.verdict || 'review')} / leakage ${String(!!verifier.leakage_pass)}</strong></div>
      <div class="workbench-kv-row"><span>Execution Guard</span><strong>${esc(verifier.execution_guard || 'shadow_only_no_order_created')}</strong></div>
      <div class="workbench-kv-row"><span>Evidence Quality</span><strong>${num(verifier.as_of_safe_ratio)}</strong></div>
    </div>
    <div class="workbench-section">
      <div class="workbench-section__title">Decision Ledger</div>
      <div class="workbench-kv-list compact-kv-list">
        <div class="workbench-kv-row"><span>Decision ID</span><strong>${esc(report.decision_id || '-')}</strong></div>
        <div class="workbench-kv-row"><span>Decision Time</span><strong>${esc(report.decision_time || report.generated_at || '-')}</strong></div>
        <div class="workbench-kv-row"><span>Evidence Count</span><strong>${esc(evidenceCount || 0)}</strong></div>
        <div class="workbench-kv-row"><span>Live Age</span><strong>${esc(liveAge)}</strong></div>
        <div class="workbench-kv-row"><span>Data Versions</span><strong>${esc(dataVersions)}</strong></div>
        <div class="workbench-kv-row"><span>Model Versions</span><strong>${esc(modelVersions)}</strong></div>
        <div class="workbench-kv-row"><span>Provider Ladder</span><strong>${esc(providerLadder)}</strong></div>
      </div>
    </div>
    <div class="workbench-section">
      <div class="workbench-section__title">Verifier Snapshot</div>
      <div class="preview-step-grid">
        <div class="preview-step"><span>Verdict</span><strong>${esc(verifier.verdict || 'review')}</strong></div>
        <div class="preview-step"><span>Leakage</span><strong>${String(!!verifier.leakage_pass)}</strong></div>
        <div class="preview-step"><span>Conflicts</span><strong>${esc(conflictCount || 0)}</strong></div>
        <div class="preview-step"><span>Quota Mode</span><strong>${esc(String(report.quota_mode ?? 'shadow'))}</strong></div>
      </div>
    </div>
    <div class="workbench-section">
      <div class="workbench-section__title">Risk Triggers</div>
      <div class="workbench-report-text"><ul>${triggers}</ul></div>
    </div>
    <div class="workbench-section">
      <div class="workbench-section__title">Factor Contribution</div>
      ${factors}
    </div>
    <div class="workbench-section">
      <div class="workbench-section__title">Audit Snapshot</div>
      <div class="preview-step-grid">
        ${(auditTrail.length ? auditTrail : ['source linked evidence', 'as-of safe features', 'counter evidence checked', 'shadow log ready']).map((step) => `<div class="preview-step"><span>${esc(step)}</span><strong>ready</strong></div>`).join('')}
      </div>
    </div>
    <div class="workbench-section">
      <div class="workbench-section__title">Embedded Simulation</div>
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
      ${metric('Counter', items.length, 'risk')}
      ${metric('Providers', providers.length || '-')}
      ${metric('Avg Q', num(avgConfidence))}
      ${metric('Critic', 'armed', 'risk')}
    </div>
    ${renderEvidenceItems(items, { maxItems: 6, scroll: true })}
    <div class="workbench-section">
      <div class="workbench-section__title">Critic Focus</div>
      <div class="factor-checklist">
        <div class="factor-check-row"><span>Weak source pressure</span><strong>${esc(providers.join(', ') || '-')}</strong></div>
        <div class="factor-check-row"><span>Freshness check</span><strong class="is-review">active</strong></div>
        <div class="factor-check-row"><span>Contrarian read</span><strong>enabled</strong></div>
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
      ${metric('Records', decisions.length, 'positive')}
      ${metric('Latest', first.status || first.action || 'recorded')}
      ${metric('Feature Time', first.feature_time || first.decision_time || 'as-of safe')}
      ${metric('Model', first.model_version || 'shadow-stack')}
    </div>
    <div class="workbench-kv-list compact-kv-list">
      ${decisions.slice(0, 5).map((decision) => `
        <div class="workbench-kv-row">
          <span>${esc(decision.decision_id || decision.status || 'audit')}</span>
          <strong>${esc(decision.symbol || decision.model_version || '-')}</strong>
        </div>
      `).join('')}
      <div class="workbench-kv-row"><span>Latest Status</span><strong>${esc(first.status || first.action || 'recorded')}</strong></div>
      <div class="workbench-kv-row"><span>Feature Time</span><strong>${esc(first.feature_time || first.decision_time || 'as-of safe')}</strong></div>
      <div class="workbench-kv-row"><span>Model Version</span><strong>${esc(first.model_version || 'shadow-stack')}</strong></div>
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
        <div class="workbench-kv-row"><span>${t('Feature time', '特征时点')}</span><strong>as-of safe</strong></div>
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
      <button class="workbench-link-row" id="link-factor-lab"><strong>Factor Lab</strong><span>Discover candidates, gate IC/RankIC, and review FactorCards.</span></button>
      <button class="workbench-link-row" id="link-simulation"><strong>Simulation</strong><span>Replay shocks, Monte Carlo paths, and historical analogs.</span></button>
      <button class="workbench-link-row" id="link-connector-center"><strong>Connector Center</strong><span>Free-tier source health, quota guard, and sample payloads.</span></button>
      <button class="workbench-link-row" id="link-market-radar"><strong>Market Radar</strong><span>Live evidence stream with provider attribution.</span></button>
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
  return `avg ${avg.toFixed(1)}h / max ${max.toFixed(1)}h`;
}
