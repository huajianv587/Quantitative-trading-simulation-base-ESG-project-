import { api } from '../qtapi.js?v=8';
import { toast } from '../components/toast.js?v=8';

function esc(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function formatDateTime(value) {
  if (!value) return 'N/A';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString();
}

function humanBlockReason(reason) {
  if (!reason) return 'N/A';
  const mapping = {
    real_report_required: 'No real report is available yet. Generate a report before testing routing rules.',
    rule_evaluation_failed: 'The rule condition could not be evaluated against the selected real report.',
  };
  return mapping[reason] || reason;
}

function renderTestResult(container, payload) {
  const body = container.querySelector('#push-rule-test-body');
  if (!body) return;
  if (!payload) {
    body.innerHTML = `
      <div class="text-muted text-sm">
        Test a rule against the latest real report stored in <code>esg_reports</code>.
      </div>
    `;
    return;
  }

  const result = payload.results || {};
  const nextActions = Array.isArray(payload.next_actions) ? payload.next_actions : [];
  const matched = result.matched === true;
  const toneClass = payload.status === 'blocked'
    ? 'workbench-status--warning'
    : matched
      ? 'workbench-status--ok'
      : 'workbench-status--neutral';

  body.innerHTML = `
    <div class="workbench-status-card ${toneClass}">
      <div class="workbench-status-card__title">Latest test result</div>
      <div class="workbench-kv">
        <div class="workbench-kv__row"><span>Status</span><strong>${esc(payload.status || 'unknown')}</strong></div>
        <div class="workbench-kv__row"><span>Report ID</span><strong>${esc(payload.report_id || 'N/A')}</strong></div>
        <div class="workbench-kv__row"><span>Report Type</span><strong>${esc(payload.report_type || 'N/A')}</strong></div>
        <div class="workbench-kv__row"><span>Generated</span><strong>${esc(formatDateTime(payload.generated_at))}</strong></div>
        <div class="workbench-kv__row"><span>Matched</span><strong>${matched ? 'Yes' : 'No'}</strong></div>
        <div class="workbench-kv__row"><span>Channels</span><strong>${esc((result.channels_tested || []).join(', ') || 'N/A')}</strong></div>
      </div>
      ${payload.block_reason ? `<div class="text-sm text-muted">Block: ${esc(humanBlockReason(payload.block_reason))}</div>` : ''}
      ${payload.warning ? `<div class="text-sm text-muted">Warning: ${esc(payload.warning)}</div>` : ''}
      ${nextActions.length ? `<div class="text-sm text-muted">Next: ${esc(nextActions.join(' · '))}</div>` : ''}
    </div>
  `;
}

export async function render(container) {
  container.innerHTML = buildShell();
  bindEvents(container);
  renderTestResult(container, null);
  await loadRules(container);
}

function buildShell() {
  return `
  <div class="page-header">
    <div>
      <div class="page-header__title">Push Rules</div>
      <div class="page-header__sub">Route notifications using real stored reports instead of temporary mock payloads</div>
    </div>
  </div>

  <div class="grid-sidebar" style="align-items:start">
    <div style="display:flex;flex-direction:column;gap:16px">
      <div class="run-panel">
        <div class="run-panel__header">
          <div class="run-panel__title">Create Rule</div>
          <div class="run-panel__sub">Conditions are evaluated against real report metrics</div>
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
          <span class="card-title">Rule Test Result</span>
        </div>
        <div class="results-panel__body" id="push-rule-test-body"></div>
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

async function testRule(container, button) {
  const original = button.textContent;
  button.disabled = true;
  button.textContent = 'Testing...';
  try {
    const response = await api.admin.pushRules.test(button.dataset.ruleId, {
      test_user_id: window.__ESG_USER_ID__ || 'ops-test-user',
      report_id: null,
    });
    renderTestResult(container, response);
    if (response.status === 'blocked') {
      toast.warning('Rule test blocked', humanBlockReason(response.block_reason));
      return;
    }
    toast.success('Rule tested', response?.results?.matched ? 'Matched latest real report' : 'Did not match latest real report');
  } catch (err) {
    toast.error('Rule test failed', err.message);
  } finally {
    button.disabled = false;
    button.textContent = original;
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
          <span class="card-title">${esc(rule.rule_name || rule.name || rule.rule_id || 'Rule')}</span>
          <span class="text-xs text-muted font-mono">${esc(rule.rule_id || rule.id || '')}</span>
        </div>
        <div class="card-body" style="display:flex;flex-direction:column;gap:8px">
          <div class="text-sm text-muted">Condition: ${esc(rule.condition || 'N/A')}</div>
          <div class="text-sm text-muted">Channels: ${esc((rule.push_channels || []).join(', ') || 'N/A')}</div>
          <div style="display:flex;gap:8px">
            <button class="btn btn-ghost btn-sm" data-action="test" data-rule-id="${esc(rule.rule_id || rule.id)}">Test Latest Real Report</button>
            <button class="btn btn-ghost btn-sm" data-action="delete" data-rule-id="${esc(rule.rule_id || rule.id)}">Delete</button>
          </div>
        </div>
      </div>`).join('');

    body.querySelectorAll('[data-action="test"]').forEach((button) => {
      button.addEventListener('click', async () => {
        await testRule(container, button);
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
    body.innerHTML = `<div class="text-muted text-sm">${esc(err.message)}</div>`;
  }
}
