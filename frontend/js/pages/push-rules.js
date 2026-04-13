import { api } from '../qtapi.js?v=8';
import { toast } from '../components/toast.js?v=8';

export async function render(container) {
  container.innerHTML = buildShell();
  bindEvents(container);
  await loadRules(container);
}

function buildShell() {
  return `
  <div class="page-header">
    <div>
      <div class="page-header__title">Push Rules</div>
      <div class="page-header__sub">Configure notification rules and test routing conditions</div>
    </div>
  </div>

  <div class="grid-sidebar" style="align-items:start">
    <div class="run-panel">
      <div class="run-panel__header">
        <div class="run-panel__title">Create Rule</div>
        <div class="run-panel__sub">Matches against report payloads</div>
      </div>
      <div class="run-panel__body">
        <div class="form-group">
          <label class="form-label">Rule Name</label>
          <input class="form-input" id="rule-name" value="Low ESG Alert">
        </div>
        <div class="form-group">
          <label class="form-label">Condition</label>
          <input class="form-input" id="rule-condition" value="overall_score < 40">
        </div>
        <div class="form-row">
          <div class="form-group">
            <label class="form-label">Target Users</label>
            <input class="form-input" id="rule-target-users" value="ops-team">
          </div>
          <div class="form-group">
            <label class="form-label">Priority</label>
            <input class="form-input" id="rule-priority" type="number" value="1" min="1">
          </div>
        </div>
        <div class="form-row">
          <div class="form-group">
            <label class="form-label">Channels</label>
            <input class="form-input" id="rule-channels" value="email, in_app">
          </div>
          <div class="form-group">
            <label class="form-label">Template ID</label>
            <input class="form-input" id="rule-template-id" value="default-alert">
          </div>
        </div>
      </div>
      <div class="run-panel__foot">
        <button class="btn btn-primary btn-lg" id="new-rule-btn" style="flex:1">Create Rule</button>
      </div>
    </div>

    <div class="results-panel">
      <div class="results-panel__header">
        <span class="card-title">Existing Rules</span>
      </div>
      <div class="results-panel__body" id="rules-body"></div>
    </div>
  </div>`;
}

function bindEvents(container) {
  container.querySelector('#new-rule-btn').addEventListener('click', () => createRule(container));
}

async function createRule(container) {
  const button = container.querySelector('#new-rule-btn');
  button.disabled = true;
  button.textContent = 'Creating...';
  try {
    await api.admin.pushRules.create({
      rule_name: container.querySelector('#rule-name').value.trim(),
      condition: container.querySelector('#rule-condition').value.trim(),
      target_users: container.querySelector('#rule-target-users').value.trim(),
      push_channels: container.querySelector('#rule-channels').value.split(/[,\s]+/).filter(Boolean),
      priority: Number(container.querySelector('#rule-priority').value) || 1,
      template_id: container.querySelector('#rule-template-id').value.trim(),
    });
    toast.success('Push rule created');
    await loadRules(container);
  } catch (err) {
    toast.error('Rule creation failed', err.message);
  } finally {
    button.disabled = false;
    button.textContent = 'Create Rule';
  }
}

async function loadRules(container) {
  const body = container.querySelector('#rules-body');
  try {
    const response = await api.admin.pushRules.list();
    const rules = response?.rules || [];
    if (!rules.length) {
      body.innerHTML = '<div class="text-muted text-sm">No push rules configured.</div>';
      return;
    }

    body.innerHTML = rules.map((rule) => `
      <div class="card" style="margin-bottom:12px">
        <div class="card-header">
          <span class="card-title">${rule.rule_name || rule.name || rule.rule_id || 'Rule'}</span>
          <span class="text-xs text-muted font-mono">${rule.rule_id || rule.id || ''}</span>
        </div>
        <div class="card-body" style="display:flex;flex-direction:column;gap:8px">
          <div class="text-sm text-muted">Condition: ${rule.condition || 'N/A'}</div>
          <div class="text-sm text-muted">Channels: ${(rule.push_channels || []).join(', ') || 'N/A'}</div>
          <div style="display:flex;gap:8px">
            <button class="btn btn-ghost btn-sm" data-action="test" data-rule-id="${rule.rule_id || rule.id}">Test</button>
            <button class="btn btn-ghost btn-sm" data-action="delete" data-rule-id="${rule.rule_id || rule.id}">Delete</button>
          </div>
        </div>
      </div>`).join('');

    body.querySelectorAll('[data-action="test"]').forEach((button) => {
      button.addEventListener('click', async () => {
        try {
          const response = await api.admin.pushRules.test(button.dataset.ruleId, {
            test_user_id: window.__ESG_USER_ID__ || 'user_123',
            mock_report: { overall_score: 35, company_name: 'Tesla' },
          });
          toast.success('Rule tested', response?.results?.matched ? 'Matched' : 'Did not match');
        } catch (err) {
          toast.error('Rule test failed', err.message);
        }
      });
    });

    body.querySelectorAll('[data-action="delete"]').forEach((button) => {
      button.addEventListener('click', async () => {
        try {
          await api.admin.pushRules.remove(button.dataset.ruleId);
          toast.success('Rule deleted');
          await loadRules(container);
        } catch (err) {
          toast.error('Delete failed', err.message);
        }
      });
    });
  } catch (err) {
    body.innerHTML = `<div class="text-muted text-sm">${err.message}</div>`;
  }
}
