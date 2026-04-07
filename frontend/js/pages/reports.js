/**
 * 报告中心页面
 */

import { api } from '../api.js';
import { store } from '../store.js';
import { showFormModal, showLoading } from '../components/modal.js';
import { toastSuccess, toastError } from '../components/toast.js';
import { formatDate } from '../utils.js';

let cleanup = [];
let currentReportId = null;

export async function render(container) {
  container.innerHTML = buildHTML();
  setupEventListeners(container);
  await loadReports(container);
}

export function destroy() {
  cleanup.forEach(fn => fn());
  cleanup = [];
}

function buildHTML() {
  return `
    <div class="page-stack h-full">
      <section class="page-hero">
        <div>
          <h2>报告中心</h2>
          <p>集中查看日报、周报和月报，支持异步生成与导出。</p>
        </div>
        <div class="text-sm text-[var(--text-secondary)]">生成后会自动轮询刷新状态</div>
      </section>

      <div class="grid grid-cols-1 xl:grid-cols-2 gap-5 h-full">
      <!-- 左侧：报告列表 -->
      <div class="card overflow-hidden flex flex-col">
        <div class="border-b border-[#2D3748] p-4">
          <div class="flex gap-2 mb-3">
            <button id="daily-tab" class="tab-btn active" data-type="daily">📅 日报</button>
            <button id="weekly-tab" class="tab-btn" data-type="weekly">📊 周报</button>
            <button id="monthly-tab" class="tab-btn" data-type="monthly">📈 月报</button>
          </div>
          <button id="generate-btn" class="btn-primary w-full">+ 生成新报告</button>
        </div>
        <div id="reports-list" class="overflow-y-auto flex-1 p-4 space-y-2"></div>
      </div>

      <!-- 右侧：报告详情 -->
      <div id="report-detail-area" class="card overflow-hidden flex flex-col">
        <div class="text-center py-12 text-[#64748B]">
          <p>选择一份报告查看详情</p>
        </div>
      </div>
      </div>
    </div>
  `;
}

function setupEventListeners(container) {
  // 标签页切换
  ['daily', 'weekly', 'monthly'].forEach(type => {
    const btn = container.querySelector(`#${type}-tab`);
    btn.addEventListener('click', () => {
      container.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      loadReports(container, type);
    });
  });

  // 生成报告
  container.querySelector('#generate-btn').addEventListener('click', async () => {
    const values = await showFormModal({
      title: '生成新报告',
      fields: [
        { name: 'report_type', label: '报告类型', type: 'select',
          options: [
            { label: '日报', value: 'daily' },
            { label: '周报', value: 'weekly' },
            { label: '月报', value: 'monthly' },
          ], required: true },
        { name: 'companies', label: '公司列表 (逗号分隔)', type: 'text', required: true },
        { name: 'include_peer', label: '包含对标分析', type: 'checkbox', value: true },
      ],
      onSubmit: async (values) => {
        const close = showLoading('生成报告中...');
        try {
          const companies = values.companies.split(',').map(c => c.trim()).filter(c => c);
          const result = await api.reports.generate({
            report_type: values.report_type,
            companies,
            include_peer_comparison: values.include_peer,
            async: true,
          });

          close();
          toastSuccess('报告已提交生成', '成功');

          // 开始轮询
          pollReportStatus(container, result.report_id);

        } catch (error) {
          close();
          toastError(error.message, '生成失败');
        }
      }
    });
  });
}

async function loadReports(container, type = 'daily') {
  try {
    store.setLoading('reports', true);

    // 获取最新报告 (这里使用 latest 接口，实际应该有列表接口)
    const report = await api.reports.getLatest(type).catch(() => null);

    const listEl = container.querySelector('#reports-list');
    listEl.innerHTML = '';

    if (!report) {
      listEl.innerHTML = '<p class="text-[#64748B] text-sm">暂无报告</p>';
      return;
    }

    // 显示单个报告
    const reportEl = document.createElement('div');
    reportEl.className = 'p-4 bg-[#162132] rounded-2xl border border-[var(--bg-border)] cursor-pointer hover:bg-[#1b2a40] transition-colors';
    reportEl.innerHTML = `
      <div class="font-semibold text-sm">${report.title || `${type} 报告`}</div>
      <div class="text-xs text-[#64748B] mt-1">${formatDate(report.generated_at || report.period_start)}</div>
      <div class="flex gap-2 mt-2">
        <span class="badge badge-info">${report.company_analyses?.length || 0} 家公司</span>
        <span class="badge badge-warning">平均分: ${(report.esg_report?.overall_score || 0).toFixed(1)}</span>
      </div>
    `;

    reportEl.addEventListener('click', () => {
      currentReportId = report.report_id || report.id;
      renderReportDetail(container, report);
    });

    listEl.appendChild(reportEl);

  } catch (error) {
    console.error('加载报告失败:', error);
  } finally {
    store.setLoading('reports', false);
  }
}

function pollReportStatus(container, reportId, interval = 3000) {
  const pollFn = setInterval(async () => {
    try {
      const report = await api.reports.getById(reportId);
      if (report.generated_at) {
        clearInterval(pollFn);
        toastSuccess('报告已生成', '成功');
        await loadReports(container);
      }
    } catch (error) {
      console.warn('轮询失败:', error);
    }
  }, interval);

  cleanup.push(() => clearInterval(pollFn));
}

function renderReportDetail(container, report) {
  const detailArea = container.querySelector('#report-detail-area');

  const html = `
    <div class="overflow-y-auto flex-1 p-6 space-y-6">
      <!-- 报告头 -->
      <div class="border-b border-[#2D3748] pb-4">
        <h2 class="text-2xl font-bold mb-2">${report.title || '报告'}</h2>
        <div class="flex gap-4 text-sm text-[#94A3B8]">
          <span>📅 ${formatDate(report.generated_at || report.period_start)}</span>
          <span>📊 ${report.company_analyses?.length || 0} 家企业</span>
        </div>
      </div>

      <!-- 摘要 -->
      ${report.executive_summary ? `
        <div class="bg-[#1C2333] border-l-4 border-[#6366F1] p-4 rounded">
          <h3 class="font-semibold mb-2">执行摘要</h3>
          <p class="text-sm text-[#94A3B8]">${report.executive_summary}</p>
        </div>
      ` : ''}

      <!-- 关键发现 -->
      ${report.key_findings?.length ? `
        <div>
          <h3 class="font-semibold mb-3">关键发现</h3>
          <ul class="space-y-2">
            ${report.key_findings.map(f => `<li class="text-sm text-[#94A3B8]">• ${f}</li>`).join('')}
          </ul>
        </div>
      ` : ''}

      <!-- 企业分析 -->
      ${report.company_analyses?.length ? `
        <div>
          <h3 class="font-semibold mb-3">企业分析</h3>
          <div class="space-y-4">
            ${report.company_analyses.map(co => `
              <div class="bg-[#1C2333] p-4 rounded border border-[#2D3748]">
                <div class="flex justify-between items-start mb-2">
                  <div>
                    <span class="font-semibold">${co.company_name}</span>
                    <span class="text-xs text-[#64748B] ml-2">${co.ticker || ''}</span>
                  </div>
                  <span class="text-lg font-bold" style="color: ${getScoreColor(co.esg_score || 0)};">${(co.esg_score || 0).toFixed(1)}</span>
                </div>
                <p class="text-sm text-[#94A3B8] mb-2">${co.summary || '暂无摘要'}</p>
                <div class="text-xs text-[#64748B]">排名: ${co.peer_rank || '未知'}</div>
              </div>
            `).join('')}
          </div>
        </div>
      ` : ''}

      <!-- 导出按钮 -->
      <div class="flex gap-2 border-t border-[#2D3748] pt-4">
        <button class="btn-secondary text-sm" onclick="window.__ESG_DEBUG__.export('${report.report_id || report.id}', 'pdf')">📥 导出 PDF</button>
        <button class="btn-secondary text-sm" onclick="window.__ESG_DEBUG__.export('${report.report_id || report.id}', 'xlsx')">📊 导出 Excel</button>
      </div>
    </div>
  `;

  detailArea.innerHTML = html;

  // 添加导出函数到全局对象
  if (!window.__ESG_DEBUG__.export) {
    window.__ESG_DEBUG__.export = (reportId, format) => {
      api.reports.export(reportId, format);
      toastSuccess('开始下载', '成功');
    };
  }
}

function getScoreColor(score) {
  if (score >= 80) return '#10B981';
  if (score >= 60) return '#84CC16';
  if (score >= 40) return '#F59E0B';
  return '#EF4444';
}
