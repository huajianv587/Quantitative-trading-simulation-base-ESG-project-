/**
 * 数据管理页面 - 数据源同步
 */

import { api } from '../api.js';
import { store } from '../store.js';
import { toastSuccess, toastError } from '../components/toast.js';
import { formatDate, relativeTime } from '../utils.js';

let cleanup = [];
const SOURCES = ['alpha_vantage', 'hyfinnan', 'sec_edgar', 'newsapi'];

export async function render(container) {
  container.innerHTML = buildHTML();
  setupEventListeners(container);
}

export function destroy() {
  cleanup.forEach(fn => fn());
  cleanup = [];
}

function buildHTML() {
  return `
    <div class="page-stack">
      <section class="page-hero">
        <div>
          <h2>数据同步</h2>
          <p>选择数据源并发起同步任务，跟踪执行进度与调度统计。</p>
        </div>
        <div class="text-sm text-[var(--text-secondary)]">适合批量刷新公司 ESG 数据</div>
      </section>

      <!-- 同步控制面板 -->
      <div class="card">
        <h2 class="text-lg font-semibold mb-4">数据同步</h2>
        <div class="space-y-4">
          <div>
            <label class="block text-sm font-medium mb-2">选择数据源</label>
            <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-2">
              ${SOURCES.map(source => `
                <label class="flex items-center gap-2 cursor-pointer">
                  <input type="checkbox" class="source-cb" value="${source}" checked />
                  <span class="text-sm">${source}</span>
                </label>
              `).join('')}
            </div>
          </div>

          <div>
            <label class="block text-sm font-medium mb-2">公司代码或名称 (逗号分隔)</label>
            <input id="companies-input" type="text" class="w-full" placeholder="例如：TSLA,AAPL,MSFT" />
          </div>

          <div class="flex flex-col items-start gap-3 sm:flex-row sm:items-center">
            <label class="flex items-center gap-2 cursor-pointer">
              <input id="force-refresh-cb" type="checkbox" />
              <span class="text-sm">强制刷新缓存</span>
            </label>
            <button id="sync-btn" class="btn-primary w-full sm:w-auto">开始同步</button>
          </div>
        </div>
      </div>

      <!-- 同步任务列表 -->
      <div class="card">
        <h2 class="text-lg font-semibold mb-4">进行中的任务</h2>
        <div id="jobs-list" class="space-y-3"></div>
      </div>

      <!-- 调度统计 -->
      <div class="card">
        <h2 class="text-lg font-semibold mb-4">调度统计</h2>
        <div id="stats-area" class="grid grid-cols-1 md:grid-cols-3 gap-4"></div>
      </div>
    </div>
  `;
}

function setupEventListeners(container) {
  const syncBtn = container.querySelector('#sync-btn');

  syncBtn.addEventListener('click', async () => {
    const sources = Array.from(container.querySelectorAll('.source-cb:checked'))
      .map(cb => cb.value);
    const companiesStr = container.querySelector('#companies-input').value.trim();
    const forceRefresh = container.querySelector('#force-refresh-cb').checked;

    if (!companiesStr) {
      toastError('请输入公司代码', '验证失败');
      return;
    }

    const companies = companiesStr.split(',').map(c => c.trim()).filter(c => c);

    syncBtn.disabled = true;
    syncBtn.textContent = '同步中...';

    try {
      const result = await api.dataSources.sync({
        sources: sources.length > 0 ? sources : undefined,
        companies,
        force_refresh: forceRefresh,
      });

      toastSuccess('同步任务已启动', '成功');

      // 开始轮询此任务
      pollSyncJob(container, result.job_id);

    } catch (error) {
      toastError(error.message, '启动失败');
    } finally {
      syncBtn.disabled = false;
      syncBtn.textContent = '开始同步';
    }
  });

  // 加载初始统计
  loadStats(container);
}

async function pollSyncJob(container, jobId) {
  const pollFn = setInterval(async () => {
    try {
      const status = await api.dataSources.getSyncStatus(jobId);

      // 更新 store
      store.updateSyncJob(jobId, status);

      // 渲染任务列表
      renderJobsList(container);

      // 如果完成，停止轮询
      if (['completed', 'failed'].includes(status.status)) {
        clearInterval(pollFn);
        loadStats(container);
        toastSuccess('同步任务完成', '成功');
      }

    } catch (error) {
      console.warn('轮询失败:', error);
    }
  }, 2000);

  cleanup.push(() => clearInterval(pollFn));

  // 立即渲染一次
  renderJobsList(container);
}

function renderJobsList(container) {
  const jobs = store.get('syncJobs') || {};
  const list = container.querySelector('#jobs-list');

  if (Object.keys(jobs).length === 0) {
    list.innerHTML = '<p class="text-[#64748B] text-sm">暂无进行中的任务</p>';
    return;
  }

  list.innerHTML = Object.entries(jobs).map(([jobId, job]) => `
    <div class="bg-[#1C2333] p-3 rounded border border-[#2D3748]">
      <div class="flex justify-between items-start mb-2">
        <span class="font-mono text-xs text-[#94A3B8]">${jobId.substring(0, 12)}...</span>
        <span class="badge ${getStatusBadgeClass(job.status)}">${job.status.toUpperCase()}</span>
      </div>

      <div class="mb-2">
        <div class="flex justify-between text-xs mb-1">
          <span class="text-[#64748B]">进度</span>
          <span class="text-[#F0F4F8]">${job.companies_synced || 0}/${job.companies_to_sync || 0}</span>
        </div>
        <div class="w-full h-2 bg-[#0B0F1A] rounded-full overflow-hidden">
          <div class="h-full bg-[#6366F1]" style="width: ${job.companies_synced && job.companies_to_sync ? (job.companies_synced / job.companies_to_sync * 100) : 0}%"></div>
        </div>
      </div>

      <div class="text-xs text-[#64748B]">
        ${job.completion_time ? `完成: ${relativeTime(job.completion_time)}` : '进行中...'}
      </div>

      ${job.errors?.length ? `
        <div class="mt-2 text-xs text-[#EF4444]">
          ❌ ${job.errors.length} 个错误
        </div>
      ` : ''}
    </div>
  `).join('');
}

async function loadStats(container) {
  try {
    const stats = await api.system.schedulerStats(7);

    const statsArea = container.querySelector('#stats-area');
    statsArea.innerHTML = `
      ${stats.degraded ? `
        <div class="md:col-span-3 rounded-2xl border border-[rgba(245,158,11,0.24)] bg-[rgba(245,158,11,0.08)] px-4 py-3 text-[0.95rem] text-[#FCD34D]">
          调度器当前未完全就绪，以下统计为占位数据。基础页面可正常使用，相关后台任务可稍后再试。
        </div>
      ` : ''}
      <div class="bg-[#1C2333] p-4 rounded">
        <div class="text-[#64748B] text-sm">总扫描次数</div>
        <div class="text-2xl font-bold text-[#F0F4F8]">${stats.total_scans || 0}</div>
      </div>
      <div class="bg-[#1C2333] p-4 rounded">
        <div class="text-[#64748B] text-sm">成功率</div>
        <div class="text-2xl font-bold" style="color: #10B981;">${((stats.success_rate || 0) * 100).toFixed(1)}%</div>
      </div>
      <div class="bg-[#1C2333] p-4 rounded">
        <div class="text-[#64748B] text-sm">最后同步</div>
        <div class="text-sm text-[#F0F4F8]">${stats.last_sync_time ? relativeTime(stats.last_sync_time) : '未同步'}</div>
      </div>
    `;

  } catch (error) {
    console.warn('加载统计失败:', error);
  }
}

function getStatusBadgeClass(status) {
  const classes = {
    'started': 'badge-info',
    'in_progress': 'badge-warning',
    'completed': 'badge-success',
    'failed': 'badge-danger',
  };
  return classes[status] || 'badge-info';
}
