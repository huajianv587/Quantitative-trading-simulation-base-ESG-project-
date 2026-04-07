/**
 * 用户订阅管理页面
 */

import { api } from '../api.js';
import { store } from '../store.js';
import { showFormModal, showConfirm } from '../components/modal.js';
import { toastSuccess, toastError } from '../components/toast.js';

let cleanup = [];

export async function render(container) {
  container.innerHTML = buildHTML();
  setupEventListeners(container);
  await loadSubscriptions(container);
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
          <h2>订阅管理</h2>
          <p>为关注企业配置报告类型、推送频率与告警阈值。</p>
        </div>
        <div class="text-sm text-[var(--text-secondary)]">适合个人持续追踪 ESG 变化</div>
      </section>

      <!-- 新建订阅表单 -->
      <div class="card">
        <h2 class="text-lg font-semibold mb-4">+ 新建订阅</h2>
        <div id="new-sub-form" class="space-y-4">
          <div>
            <label class="block text-sm font-medium mb-2">关注的公司 (逗号分隔或标签输入)</label>
            <input id="companies-input" type="text" class="w-full" placeholder="例如：Apple,Tesla,Microsoft" />
          </div>

          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label class="block text-sm font-medium mb-2">报告类型</label>
              <div class="space-y-2">
                <label class="flex items-center gap-2 cursor-pointer">
                  <input type="checkbox" name="report_type" value="daily" checked />
                  <span class="text-sm">日报</span>
                </label>
                <label class="flex items-center gap-2 cursor-pointer">
                  <input type="checkbox" name="report_type" value="weekly" checked />
                  <span class="text-sm">周报</span>
                </label>
                <label class="flex items-center gap-2 cursor-pointer">
                  <input type="checkbox" name="report_type" value="monthly" />
                  <span class="text-sm">月报</span>
                </label>
              </div>
            </div>

            <div>
              <label class="block text-sm font-medium mb-2">推送渠道</label>
              <div class="space-y-2">
                <label class="flex items-center gap-2 cursor-pointer">
                  <input type="checkbox" name="channel" value="email" checked />
                  <span class="text-sm">📧 邮件</span>
                </label>
                <label class="flex items-center gap-2 cursor-pointer">
                  <input type="checkbox" name="channel" value="in_app" checked />
                  <span class="text-sm">🔔 应用内</span>
                </label>
                <label class="flex items-center gap-2 cursor-pointer">
                  <input type="checkbox" name="channel" value="webhook" />
                  <span class="text-sm">🪝 Webhook</span>
                </label>
              </div>
            </div>
          </div>

          <div>
            <label class="block text-sm font-medium mb-2">推送频率</label>
            <select id="frequency-select" class="w-full">
              <option value="immediate">实时</option>
              <option value="daily">每日</option>
              <option value="weekly">每周</option>
            </select>
          </div>

          <div>
            <label class="block text-sm font-medium mb-2">告警阈值 (可选)</label>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label class="text-xs text-[#64748B]">最低分数</label>
                <input id="min-score" type="number" class="w-full" min="0" max="100" placeholder="默认: 40" />
              </div>
              <div>
                <label class="text-xs text-[#64748B]">最大下跌幅度</label>
                <input id="max-drop" type="number" class="w-full" min="0" placeholder="默认: 5" />
              </div>
            </div>
          </div>

          <button id="create-sub-btn" class="btn-primary w-full">创建订阅</button>
        </div>
      </div>

      <!-- 订阅列表 -->
      <div>
        <h2 class="text-lg font-semibold mb-4">我的订阅</h2>
        <div id="subscriptions-grid" class="grid grid-cols-1 xl:grid-cols-2 gap-4"></div>
      </div>
    </div>
  `;
}

function setupEventListeners(container) {
  container.querySelector('#create-sub-btn').addEventListener('click', async () => {
    const companies = container.querySelector('#companies-input').value.trim();
    const reportTypes = Array.from(container.querySelectorAll('input[name="report_type"]:checked'))
      .map(cb => cb.value);
    const channels = Array.from(container.querySelectorAll('input[name="channel"]:checked'))
      .map(cb => cb.value);
    const frequency = container.querySelector('#frequency-select').value;
    const minScore = parseInt(container.querySelector('#min-score').value) || 40;
    const maxDrop = parseInt(container.querySelector('#max-drop').value) || 5;

    if (!companies) {
      toastError('请输入至少一个公司', '验证失败');
      return;
    }

    if (reportTypes.length === 0) {
      toastError('请选择至少一个报告类型', '验证失败');
      return;
    }

    if (channels.length === 0) {
      toastError('请选择至少一个推送渠道', '验证失败');
      return;
    }

    try {
      const companyList = companies.split(',').map(c => c.trim()).filter(c => c);

      await api.subscriptions.create({
        report_types: reportTypes,
        companies: companyList,
        alert_threshold: {
          esg_score: minScore,
          score_change: -maxDrop,
        },
        push_channels: channels,
        frequency,
      });

      toastSuccess('订阅已创建', '成功');

      // 清空表单
      container.querySelector('#companies-input').value = '';
      container.querySelector('#min-score').value = '';
      container.querySelector('#max-drop').value = '';

      // 重新加载
      await loadSubscriptions(container);

    } catch (error) {
      toastError(error.message, '创建失败');
    }
  });
}

async function loadSubscriptions(container) {
  try {
    store.setLoading('subscriptions', true);
    const result = await api.subscriptions.getAll();
    const subs = result.subscriptions || [];

    store.setSubscriptions(subs);
    renderSubscriptions(container, subs);

  } catch (error) {
    console.error('加载订阅失败:', error);
  } finally {
    store.setLoading('subscriptions', false);
  }
}

function renderSubscriptions(container, subs) {
  const grid = container.querySelector('#subscriptions-grid');

  if (subs.length === 0) {
    grid.innerHTML = '<div class="col-span-2 text-center py-12 text-[#64748B]"><p>暂无订阅</p></div>';
    return;
  }

  grid.innerHTML = subs.map(sub => `
    <div class="card">
      <div class="flex justify-between items-start mb-3">
        <h3 class="font-semibold">订阅</h3>
        <button class="btn-sm btn-danger" onclick="window.__ESG_DEBUG__.deleteSub('${sub.subscription_id}')">删除</button>
      </div>

      <div class="space-y-3 text-sm">
        <!-- 公司列表 -->
        <div>
          <div class="text-xs text-[#64748B] mb-1">关注公司</div>
          <div class="flex flex-wrap gap-1">
            ${(sub.companies || []).map(co => `<span class="badge badge-s">${co}</span>`).join('')}
          </div>
        </div>

        <!-- 报告类型 -->
        <div>
          <div class="text-xs text-[#64748B] mb-1">报告类型</div>
          <div class="flex flex-wrap gap-1">
            ${(sub.report_types || []).map(type => {
              const labels = { daily: '日报', weekly: '周报', monthly: '月报' };
              return `<span class="badge badge-info">${labels[type]}</span>`;
            }).join('')}
          </div>
        </div>

        <!-- 推送渠道 -->
        <div>
          <div class="text-xs text-[#64748B] mb-1">推送渠道</div>
          <div class="flex flex-wrap gap-1">
            ${(sub.push_channels || []).map(ch => {
              const icons = { email: '📧', in_app: '🔔', webhook: '🪝' };
              return `<span class="badge badge-e">${icons[ch]} ${ch}</span>`;
            }).join('')}
          </div>
        </div>

        <!-- 频率 -->
        <div>
          <div class="text-xs text-[#64748B] mb-1">推送频率</div>
          <span class="badge badge-warning">
            ${{ immediate: '实时', daily: '每日', weekly: '每周' }[sub.frequency] || sub.frequency}
          </span>
        </div>

        <!-- 告警阈值 -->
        ${sub.alert_threshold ? `
          <div>
            <div class="text-xs text-[#64748B] mb-1">告警阈值</div>
            <div class="text-xs text-[#94A3B8]">
              • ESG 分数: ${sub.alert_threshold.esg_score}
              <br />
              • 下跌幅度: ${Math.abs(sub.alert_threshold.score_change)}
            </div>
          </div>
        ` : ''}

        <div class="text-xs text-[#64748B] border-t border-[#2D3748] pt-2 mt-2">
          订阅于 ${new Date(sub.subscribed_at).toLocaleDateString()}
        </div>
      </div>

      <button class="btn-secondary w-full mt-3 text-xs" onclick="window.__ESG_DEBUG__.editSub('${sub.subscription_id}')">编辑</button>
    </div>
  `).join('');

  // 添加全局函数
  if (!window.__ESG_DEBUG__.deleteSub) {
    window.__ESG_DEBUG__.deleteSub = async (subId) => {
      const confirmed = await showConfirm({
        title: '确认删除',
        message: '确定要删除此订阅吗？',
      });

      if (confirmed) {
        try {
          await api.subscriptions.delete(subId);
          toastSuccess('已删除', '成功');
          await loadSubscriptions(container);
        } catch (error) {
          toastError(error.message, '删除失败');
        }
      }
    };
  }

  if (!window.__ESG_DEBUG__.editSub) {
    window.__ESG_DEBUG__.editSub = async (subId) => {
      const sub = subs.find(s => s.subscription_id === subId);
      if (!sub) return;

      // 简化编辑（实际可做完整表单）
      toastError('编辑功能开发中', '提示');
    };
  }
}
