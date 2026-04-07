/**
 * 推送规则管理页面
 */

import { api } from '../api.js';
import { store } from '../store.js';
import { showFormModal, showConfirm } from '../components/modal.js';
import { toastSuccess, toastError } from '../components/toast.js';

let cleanup = [];

export async function render(container) {
  container.innerHTML = buildHTML();
  setupEventListeners(container);
  await loadRules(container);
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
          <h2>推送规则</h2>
          <p>管理触发条件、优先级与消息渠道，快速测试规则是否生效。</p>
        </div>
        <div class="text-sm text-[var(--text-secondary)]">支持邮件、应用内和 Webhook</div>
      </section>

      <div class="flex justify-between items-center mb-4">
        <h2 class="text-lg font-semibold">推送规则</h2>
        <button id="new-rule-btn" class="btn-primary">+ 新建规则</button>
      </div>

      <div class="overflow-x-auto">
        <table>
          <thead>
            <tr>
              <th>规则名称</th>
              <th>条件</th>
              <th>目标用户</th>
              <th>推送渠道</th>
              <th>优先级</th>
              <th>状态</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody id="rules-tbody"></tbody>
        </table>
      </div>
    </div>
  `;
}

function setupEventListeners(container) {
  container.querySelector('#new-rule-btn').addEventListener('click', () => {
    showEditRuleModal(null, () => loadRules(container));
  });
}

async function loadRules(container) {
  try {
    store.setLoading('pushRules', true);
    const result = await api.pushRules.getAll();
    const rules = result.rules || [];

    store.setPushRules(rules);
    renderRulesTable(container, rules);

    if (result.degraded) {
      const tbody = container.querySelector('#rules-tbody');
      tbody.innerHTML = `
        <tr>
          <td colspan="7" class="py-8">
            <div class="rounded-2xl border border-[rgba(245,158,11,0.24)] bg-[rgba(245,158,11,0.08)] px-4 py-4 text-[0.95rem] text-[#FCD34D]">
              推送调度器暂未就绪，当前先展示空状态，等后端服务就绪后这里会自动恢复正常。
            </div>
          </td>
        </tr>
      `;
    }

  } catch (error) {
    toastError(error.message, '加载失败');
  } finally {
    store.setLoading('pushRules', false);
  }
}

function renderRulesTable(container, rules) {
  const tbody = container.querySelector('#rules-tbody');
  tbody.innerHTML = '';

  if (rules.length === 0) {
    tbody.innerHTML = '<tr><td colspan="7" class="text-center text-[#64748B] py-6">暂无规则</td></tr>';
    return;
  }

  rules.forEach(rule => {
    const row = document.createElement('tr');
    row.innerHTML = `
      <td class="font-medium">${rule.rule_name}</td>
      <td class="font-mono text-xs">${rule.condition.substring(0, 30)}...</td>
      <td><span class="badge badge-info">${rule.target_users}</span></td>
      <td>
        <div class="flex gap-1">
          ${rule.push_channels.map(ch => `
            <span class="badge badge-success text-xs">${ch}</span>
          `).join('')}
        </div>
      </td>
      <td>
        <div class="w-full bg-[#2D3748] rounded-full h-2">
          <div class="bg-[#6366F1] h-2 rounded-full" style="width: ${rule.priority * 10}%"></div>
        </div>
        <span class="text-xs text-[#64748B]">${rule.priority}/10</span>
      </td>
      <td>
        <label class="flex items-center gap-2">
          <input type="checkbox" class="toggle-cb" ${rule.enabled ? 'checked' : ''} data-rule-id="${rule.id}" />
          <span class="text-xs text-[#64748B]">${rule.enabled ? '启用' : '禁用'}</span>
        </label>
      </td>
      <td class="text-right">
        <button class="btn-sm btn-secondary mr-2" onclick="window.__ESG_DEBUG__.editRule('${rule.id}')">编辑</button>
        <button class="btn-sm btn-secondary mr-2" onclick="window.__ESG_DEBUG__.testRule('${rule.id}')">测试</button>
        <button class="btn-sm btn-danger" onclick="window.__ESG_DEBUG__.deleteRule('${rule.id}')">删除</button>
      </td>
    `;

    // 切换启用状态
    const toggle = row.querySelector('.toggle-cb');
    toggle.addEventListener('change', async () => {
      try {
        await api.pushRules.update(rule.id, { enabled: toggle.checked });
        toastSuccess('已更新', '成功');
      } catch (error) {
        toggle.checked = !toggle.checked;
        toastError(error.message, '更新失败');
      }
    });

    tbody.appendChild(row);
  });

  // 添加全局函数
  if (!window.__ESG_DEBUG__.editRule) {
    window.__ESG_DEBUG__.editRule = (ruleId) => {
      const rule = rules.find(r => r.id === ruleId);
      showEditRuleModal(rule, () => loadRules(container));
    };
  }

  if (!window.__ESG_DEBUG__.testRule) {
    window.__ESG_DEBUG__.testRule = async (ruleId) => {
      try {
        const result = await api.pushRules.test(ruleId, {
          test_user_id: 'test_user_001',
          mock_report: {
            overall_score: 50,
            low_performer_count: 1,
            high_performer_count: 0,
          }
        });
        toastSuccess(`测试成功: ${JSON.stringify(result.results)}`, '成功');
      } catch (error) {
        toastError(error.message, '测试失败');
      }
    };
  }

  if (!window.__ESG_DEBUG__.deleteRule) {
    window.__ESG_DEBUG__.deleteRule = async (ruleId) => {
      const confirmed = await showConfirm({
        title: '确认删除',
        message: '确定要删除此规则吗？',
      });

      if (confirmed) {
        try {
          await api.pushRules.delete(ruleId);
          toastSuccess('已删除', '成功');
          await loadRules(container);
        } catch (error) {
          toastError(error.message, '删除失败');
        }
      }
    };
  }
}

async function showEditRuleModal(rule, onSuccess) {
  const values = await showFormModal({
    title: rule ? '编辑规则' : '新建规则',
    fields: [
      { name: 'rule_name', label: '规则名称', value: rule?.rule_name || '', required: true },
      {
        name: 'condition',
        label: '条件表达式',
        type: 'textarea',
        value: rule?.condition || 'esg_score < 40',
        required: true,
      },
      {
        name: 'target_users',
        label: '目标用户',
        type: 'select',
        value: rule?.target_users || 'holders',
        options: [
          { label: '所有用户', value: 'all' },
          { label: '股东', value: 'holders' },
          { label: '追踪者', value: 'followers' },
          { label: '分析师', value: 'analysts' },
        ],
        required: true,
      },
      {
        name: 'push_channels',
        label: '推送渠道',
        type: 'select',
        value: rule?.push_channels?.[0] || 'email',
        options: [
          { label: '邮件', value: 'email' },
          { label: '应用内消息', value: 'in_app' },
          { label: 'Webhook', value: 'webhook' },
        ],
      },
      {
        name: 'priority',
        label: '优先级 (1-10)',
        type: 'number',
        value: rule?.priority || 5,
        required: true,
      },
      {
        name: 'template_id',
        label: '通知模板',
        type: 'select',
        value: rule?.template_id || 'template_low_esg_warning',
        options: [
          { label: '低分预警', value: 'template_low_esg_warning' },
          { label: '优秀案例', value: 'template_excellence' },
          { label: '关键风险', value: 'template_critical_alert' },
          { label: '每日摘要', value: 'template_daily_digest' },
        ],
      },
    ],
    onSubmit: async (formValues) => {
      try {
        const payload = {
          rule_name: formValues.rule_name,
          condition: formValues.condition,
          target_users: formValues.target_users,
          push_channels: [formValues.push_channels],
          priority: parseInt(formValues.priority),
          template_id: formValues.template_id,
        };

        if (rule) {
          await api.pushRules.update(rule.id, payload);
          toastSuccess('规则已更新', '成功');
        } else {
          await api.pushRules.create(payload);
          toastSuccess('规则已创建', '成功');
        }

        onSuccess?.();
      } catch (error) {
        toastError(error.message, '保存失败');
      }
    }
  });
}
