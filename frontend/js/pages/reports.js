import { api } from '../qtapi.js?v=8';
import { toast } from '../components/toast.js?v=8';
import { getLang, getLocale, onLangChange } from '../i18n.js?v=8';
import { emptyState, esc, metric, renderError, setLoading, splitTokens, statusBadge } from './workbench-utils.js?v=8';

const REPORT_TYPES = ['daily', 'weekly', 'monthly'];

let _container = null;
let _langCleanup = null;
let _activeType = 'daily';
let _history = [];
let _currentReport = null;

const COPY = {
  en: {
    title: 'Report Center',
    subtitle: 'Generate, review, and export real ESG research reports.',
    generateTitle: 'Generate Report',
    generateSub: 'Create a real report from the backend report generator.',
    type: 'Report Type',
    companies: 'Companies / Tickers',
    companiesPlaceholder: 'Tesla, Microsoft, NVIDIA',
    generate: 'Generate',
    generating: 'Generating...',
    loadLatest: 'Load Latest',
    archive: 'Latest Archive',
    archiveSub: 'Latest real report per supported report type.',
    bodyTitle: 'Report Workspace',
    bodySub: 'Current report payload, grounding summary, and company analysis table.',
    noReport: 'No report loaded',
    noReportHint: 'Generate a report or load the latest backend report to begin.',
    emptyArchive: 'No saved reports are available yet.',
    generated: 'Report generated',
    latestLoaded: 'Latest report loaded',
    latestMissing: 'No latest report is available for the selected type',
    requestFailed: 'Report request failed',
    summary: 'Executive Summary',
    stats: 'Report Stats',
    findings: 'Key Findings',
    alerts: 'Risk Alerts',
    analyses: 'Company Analyses',
    reportType: 'Type',
    generatedAt: 'Generated',
    grounded: 'Grounded',
    citations: 'Citations',
    totalCompanies: 'Companies',
    confidence: 'Confidence',
    company: 'Company',
    ticker: 'Ticker',
    overall: 'Overall',
    environment: 'E',
    social: 'S',
    governance: 'G',
    recommendation: 'Signal',
    noAnalyses: 'The backend returned no company analyses for this report.',
  },
  zh: {
    title: '报告中心',
    subtitle: '生成、查看并导出真实 ESG 研究报告。',
    generateTitle: '生成报告',
    generateSub: '通过后端报告生成器创建真实报告。',
    type: '报告类型',
    companies: '公司 / 股票代码',
    companiesPlaceholder: 'Tesla, Microsoft, NVIDIA',
    generate: '生成报告',
    generating: '正在生成...',
    loadLatest: '加载最新',
    archive: '最新报告归档',
    archiveSub: '按支持的报告类型显示最近一次真实报告。',
    bodyTitle: '报告工作区',
    bodySub: '当前报告载荷、grounding 摘要与公司分析表。',
    noReport: '还没有加载报告',
    noReportHint: '先生成报告，或加载后端最近一次真实报告。',
    emptyArchive: '还没有可显示的已保存报告。',
    generated: '报告已生成',
    latestLoaded: '已加载最新报告',
    latestMissing: '当前类型还没有最新报告',
    requestFailed: '报告请求失败',
    summary: '执行摘要',
    stats: '报告统计',
    findings: '关键发现',
    alerts: '风险提醒',
    analyses: '公司分析',
    reportType: '类型',
    generatedAt: '生成时间',
    grounded: '已 grounding',
    citations: '引用数',
    totalCompanies: '公司数',
    confidence: '置信度',
    company: '公司',
    ticker: '代码',
    overall: '总分',
    environment: 'E',
    social: 'S',
    governance: 'G',
    recommendation: '信号',
    noAnalyses: '后端这次没有返回公司分析结果。',
  },
};

function c(key) {
  const lang = getLang() === 'zh' ? 'zh' : 'en';
  return COPY[lang][key] || COPY.en[key] || key;
}

function isMounted() {
  return Boolean(_container && _container.isConnected);
}

function formatTimestamp(value) {
  if (!value) return '-';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return String(value);
  return parsed.toLocaleString(getLocale(), {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function companies() {
  if (!_container) return [];
  return splitTokens(_container.querySelector('#report-companies')?.value || '', { delimiters: /[,\n]+/ });
}

function normalizeReport(payload) {
  const report = payload?.report || payload || {};
  return {
    ...report,
    report_id: report.report_id || payload?.report_id || report.id,
    report_type: report.report_type || payload?.report_type || _activeType,
    generated_at: report.generated_at || payload?.generated_at,
  };
}

function buildShell() {
  return `
    <div class="workbench-page reports-page" data-no-autotranslate="true">
      <div class="page-header">
        <div>
          <div class="page-header__title">${c('title')}</div>
          <div class="page-header__sub">${c('subtitle')}</div>
        </div>
      </div>

      <div class="grid-sidebar reports-layout">
        <div class="reports-sidebar">
          <section class="run-panel reports-run-panel">
          <div class="run-panel__header">
            <div class="run-panel__title">${c('generateTitle')}</div>
            <div class="run-panel__sub">${c('generateSub')}</div>
          </div>
          <div class="run-panel__body">
            <div class="form-group">
              <label class="form-label">${c('type')}</label>
              <div class="workbench-tabs" id="report-type-tabs">
                ${REPORT_TYPES.map((type) => `
                  <button class="workbench-tab${type === _activeType ? ' active' : ''}" data-report-type="${type}" type="button">${esc(type)}</button>
                `).join('')}
              </div>
            </div>
            <div class="form-group">
              <label class="form-label">${c('companies')}</label>
              <textarea class="form-textarea" id="report-companies" rows="4" placeholder="${c('companiesPlaceholder')}">Tesla, Microsoft</textarea>
            </div>
          </div>
          <div class="run-panel__foot workbench-action-grid">
            <button class="btn btn-primary btn-lg workbench-action-btn" id="generate-btn">${c('generate')}</button>
            <button class="btn btn-ghost btn-lg workbench-action-btn" id="load-latest-btn">${c('loadLatest')}</button>
          </div>
        </section>

          <section class="card reports-sidebar-card">
          <div class="card-header">
            <span class="card-title">${c('archive')}</span>
            <span style="font-size:10px;color:var(--text-dim);font-family:var(--f-mono)">${c('archiveSub')}</span>
          </div>
            <div class="card-body reports-archive-body" id="report-history">
            ${emptyState('Loading reports...')}
          </div>
        </section>
        </div>

        <div class="reports-workspace-column">
          <section class="card report-workspace-card">
          <div class="card-header">
            <span class="card-title">${c('bodyTitle')}</span>
            <span style="font-size:10px;color:var(--text-dim);font-family:var(--f-mono)">${c('bodySub')}</span>
          </div>
            <div class="card-body reports-workspace-body" id="report-body">
            ${emptyState(c('noReport'), c('noReportHint'))}
          </div>
        </section>
        </div>
      </div>
    </div>`;
}

export async function render(container) {
  _container = container;
  _container.innerHTML = buildShell();
  bindEvents();
  _langCleanup?.();
  _langCleanup = onLangChange(() => {
    if (!isMounted()) return;
    const rawCompanies = _container.querySelector('#report-companies')?.value || '';
    _container.innerHTML = buildShell();
    bindEvents();
    _container.querySelector('#report-companies').value = rawCompanies;
    renderArchive();
    renderReport();
  });
  await refreshArchive();
}

export function destroy() {
  _container = null;
  _langCleanup?.();
  _langCleanup = null;
}

function bindEvents() {
  if (!_container) return;
  _container.querySelector('#generate-btn')?.addEventListener('click', () => generateReport());
  _container.querySelector('#load-latest-btn')?.addEventListener('click', () => loadLatest());
  _container.querySelector('#report-type-tabs')?.addEventListener('click', (event) => {
    const target = event.target.closest('[data-report-type]');
    if (!target) return;
    _activeType = target.dataset.reportType || 'daily';
    _container.querySelectorAll('[data-report-type]').forEach((node) => node.classList.toggle('active', node === target));
  });
  _container.querySelector('#report-history')?.addEventListener('click', async (event) => {
    const target = event.target.closest('[data-load-report]');
    if (!target) return;
    const reportId = target.dataset.loadReport;
    if (!reportId) return;
    try {
      const payload = await api.reports.get(reportId);
      _currentReport = normalizeReport(payload);
      renderReport();
      toast.success(c('latestLoaded'), reportId);
    } catch (error) {
      toast.error(c('requestFailed'), error.message || c('requestFailed'));
    }
  });
}

async function refreshArchive() {
  if (!isMounted()) return;
  const target = _container.querySelector('#report-history');
  setLoading(target, 'Loading reports...');
  const results = await Promise.allSettled(REPORT_TYPES.map((type) => api.reports.latest(type)));
  if (!isMounted()) return;
  _history = results
    .map((result, index) => (result.status === 'fulfilled' && result.value ? normalizeReport(result.value) : null))
    .filter(Boolean)
    .map((report, index) => ({ ...report, report_type: report.report_type || REPORT_TYPES[index] }));
  renderArchive();
}

function renderArchive() {
  if (!_container) return;
  const target = _container.querySelector('#report-history');
  if (!_history.length) {
    target.innerHTML = emptyState(c('emptyArchive'));
    return;
  }
  target.innerHTML = _history.map((report) => `
    <button
      class="workbench-item report-archive-item${report.report_id && report.report_id === _currentReport?.report_id ? ' workbench-item--active' : ''}"
      data-load-report="${esc(report.report_id || '')}"
      type="button"
    >
      <div class="workbench-item__head">
        <strong>${esc(report.title || report.report_type || '-')}</strong>
        ${statusBadge('ready')}
      </div>
      <div class="workbench-item__summary">${esc(report.report_id || '-')}</div>
      <div class="workbench-mini-grid">
        <div class="workbench-mini-metric"><span>${c('reportType')}</span><strong>${esc(report.report_type || '-')}</strong></div>
        <div class="workbench-mini-metric"><span>${c('generatedAt')}</span><strong>${esc(formatTimestamp(report.generated_at))}</strong></div>
      </div>
    </button>
  `).join('');
}

async function generateReport() {
  if (!isMounted()) return;
  const btn = _container.querySelector('#generate-btn');
  const payload = {
    report_type: _activeType,
    companies: companies(),
    async: false,
  };
  btn.disabled = true;
  btn.textContent = c('generating');
  try {
    const response = await api.reports.generate(payload);
    _currentReport = normalizeReport(response);
    renderReport();
    await refreshArchive();
    toast.success(c('generated'), _currentReport.report_id || _activeType);
  } catch (error) {
    const target = _container.querySelector('#report-body');
    renderError(target, error);
    toast.error(c('requestFailed'), error.message || c('requestFailed'));
  } finally {
    btn.disabled = false;
    btn.textContent = c('generate');
  }
}

async function loadLatest() {
  if (!isMounted()) return;
  try {
    const response = await api.reports.latest(_activeType);
    if (!response) {
      toast.info(c('loadLatest'), c('latestMissing'));
      return;
    }
    _currentReport = normalizeReport(response);
    renderReport();
    toast.success(c('latestLoaded'), _currentReport.report_id || _activeType);
  } catch (error) {
    toast.error(c('requestFailed'), error.message || c('requestFailed'));
  }
}

function renderReport() {
  if (!_container) return;
  const target = _container.querySelector('#report-body');
  if (!_currentReport) {
    target.innerHTML = emptyState(c('noReport'), c('noReportHint'));
    return;
  }

  const report = _currentReport;
  const analyses = Array.isArray(report.company_analyses) ? report.company_analyses : [];
  const evidenceSummary = report.evidence_summary || {};
  const findings = Array.isArray(report.key_findings) ? report.key_findings : [];
  const alerts = Array.isArray(report.risk_alerts) ? report.risk_alerts : [];

  target.innerHTML = `
    <div class="report-workspace">
      <div class="report-workspace__header">
        <div class="report-workspace__title">${esc(report.title || report.report_type || 'Report')}</div>
        <div class="report-workspace__meta">${esc(report.report_id || '-')} / ${c('generatedAt')}: ${esc(formatTimestamp(report.generated_at))}</div>
      </div>

      <div class="workbench-metric-grid">
        ${metric(c('reportType'), report.report_type || '-', 'positive')}
        ${metric(c('grounded'), evidenceSummary.grounded_companies ?? 0, evidenceSummary.grounded_companies ? 'positive' : '')}
        ${metric(c('citations'), evidenceSummary.citation_count ?? 0, evidenceSummary.citation_count ? 'positive' : '')}
        ${metric(c('confidence'), evidenceSummary.average_grounding_confidence ?? report.confidence_score ?? '-', (evidenceSummary.average_grounding_confidence ?? report.confidence_score) ? 'positive' : '')}
      </div>

      ${(report.executive_summary || report.summary) ? `
        <section class="functional-empty report-summary-card" style="padding:14px 16px">
          <div class="functional-empty__eyebrow">${c('summary')}</div>
          <div style="font-size:12px;line-height:1.7;color:var(--text-secondary)">${esc(report.executive_summary || report.summary)}</div>
        </section>
      ` : ''}

      <section class="workbench-kv-list report-kv-list">
        <div class="workbench-kv-row"><span>${c('reportType')}</span><strong>${esc(report.report_type || '-')}</strong></div>
        <div class="workbench-kv-row"><span>${c('generatedAt')}</span><strong>${esc(formatTimestamp(report.generated_at))}</strong></div>
        <div class="workbench-kv-row"><span>${c('totalCompanies')}</span><strong>${esc(String(analyses.length))}</strong></div>
        <div class="workbench-kv-row"><span>${c('confidence')}</span><strong>${esc(String(report.confidence_score ?? evidenceSummary.average_grounding_confidence ?? '-'))}</strong></div>
      </section>

      <section class="report-detail-section">
        <div class="workbench-section__title">${c('findings')}</div>
        <div class="report-note-list">
          ${findings.length ? findings.map((item) => `<div class="workbench-item"><div class="workbench-item__summary">${esc(String(item))}</div></div>`).join('') : emptyState(c('findings'), '-')}
        </div>
      </section>

      <section class="report-detail-section">
        <div class="workbench-section__title">${c('alerts')}</div>
        <div class="report-note-list">
          ${alerts.length ? alerts.map((item) => `<div class="workbench-item"><div class="workbench-item__summary">${esc(String(item))}</div></div>`).join('') : emptyState(c('alerts'), '-')}
        </div>
      </section>

      <section class="report-detail-section">
        <div class="workbench-section__title">${c('analyses')}</div>
        ${analyses.length ? `
          <div class="tbl-wrap report-analyses-wrap">
            <table>
              <thead>
                <tr>
                  <th>${c('company')}</th>
                  <th>${c('ticker')}</th>
                  <th>${c('overall')}</th>
                  <th>${c('environment')}</th>
                  <th>${c('social')}</th>
                  <th>${c('governance')}</th>
                  <th>${c('recommendation')}</th>
                </tr>
              </thead>
              <tbody>
                ${analyses.map((row) => `
                  <tr>
                    <td>${esc(row.company_name || row.company || '-')}</td>
                    <td>${esc(row.ticker || '-')}</td>
                    <td>${esc(String(row.esg_score ?? row.overall_score ?? '-'))}</td>
                    <td>${esc(String(row.environment ?? row.e_score ?? '-'))}</td>
                    <td>${esc(String(row.social ?? row.s_score ?? '-'))}</td>
                    <td>${esc(String(row.governance ?? row.g_score ?? '-'))}</td>
                    <td>${esc(String(row.recommendation || '-'))}</td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          </div>
        ` : emptyState(c('noAnalyses'))}
      </section>
    </div>`;
}
