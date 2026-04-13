import { api } from '../qtapi.js?v=8';
import { toast } from '../components/toast.js?v=8';

export async function render(container) {
  container.innerHTML = buildShell();
  bindEvents(container);
  await loadSubscriptions(container);
}

function buildShell() {
  return `
  <div class="page-header">
    <div>
      <div class="page-header__title">Subscriptions</div>
      <div class="page-header__sub">Manage report subscriptions for the current user</div>
    </div>
  </div>

  <div class="grid-sidebar" style="align-items:start">
    <div class="run-panel">
      <div class="run-panel__header">
        <div class="run-panel__title">Create Subscription</div>
        <div class="run-panel__sub">Subscribe to report delivery with channel preferences</div>
      </div>
      <div class="run-panel__body">
        <div class="form-row">
          <div class="form-group">
            <label class="form-label">Report Types</label>
            <input class="form-input" id="sub-report-types" value="daily">
          </div>
          <div class="form-group">
            <label class="form-label">Frequency</label>
            <select class="form-select" id="sub-frequency">
              <option value="daily">Daily</option>
              <option value="weekly">Weekly</option>
              <option value="monthly">Monthly</option>
            </select>
          </div>
        </div>
        <div class="form-group">
          <label class="form-label">Companies</label>
          <input class="form-input" id="sub-companies" value="Tesla, Microsoft">
        </div>
        <div class="form-row">
          <div class="form-group">
            <label class="form-label">Channels</label>
            <input class="form-input" id="sub-channels" value="email, in_app">
          </div>
          <div class="form-group">
            <label class="form-label">ESG Alert Threshold</label>
            <input class="form-input" id="sub-threshold" type="number" value="40" min="0" max="100">
          </div>
        </div>
      </div>
      <div class="run-panel__foot">
        <button class="btn btn-primary btn-lg" id="create-sub-btn" style="flex:1">Create Subscription</button>
      </div>
    </div>

    <div class="results-panel">
      <div class="results-panel__header">
        <span class="card-title">Current Subscriptions</span>
      </div>
      <div class="results-panel__body" id="subscriptions-body"></div>
    </div>
  </div>`;
}

function bindEvents(container) {
  container.querySelector('#create-sub-btn').addEventListener('click', () => createSubscription(container));
}

async function createSubscription(container) {
  const button = container.querySelector('#create-sub-btn');
  button.disabled = true;
  button.textContent = 'Creating...';
  try {
    await api.user.subscriptions.create({
      report_types: parseList(container.querySelector('#sub-report-types').value),
      companies: parseList(container.querySelector('#sub-companies').value),
      alert_threshold: { esg_score: Number(container.querySelector('#sub-threshold').value) || 40 },
      push_channels: parseList(container.querySelector('#sub-channels').value),
      frequency: container.querySelector('#sub-frequency').value,
    });
    toast.success('Subscription created');
    await loadSubscriptions(container);
  } catch (err) {
    toast.error('Subscription failed', err.message);
  } finally {
    button.disabled = false;
    button.textContent = 'Create Subscription';
  }
}

async function loadSubscriptions(container) {
  const body = container.querySelector('#subscriptions-body');
  try {
    const response = await api.user.subscriptions.list();
    const subscriptions = response?.subscriptions || [];
    if (!subscriptions.length) {
      body.innerHTML = '<div class="text-muted text-sm">No subscriptions found.</div>';
      return;
    }

    body.innerHTML = subscriptions.map((subscription) => `
      <div class="card" style="margin-bottom:12px">
        <div class="card-header">
          <span class="card-title">${(subscription.report_types || []).join(', ') || 'Subscription'}</span>
          <span class="text-xs text-muted font-mono">${subscription.subscription_id}</span>
        </div>
        <div class="card-body" style="display:flex;flex-direction:column;gap:8px">
          <div class="text-sm text-muted">Companies: ${(subscription.companies || []).join(', ') || 'N/A'}</div>
          <div class="text-sm text-muted">Channels: ${(subscription.push_channels || []).join(', ') || 'N/A'}</div>
          <div class="text-sm text-muted">Frequency: ${subscription.frequency || 'N/A'}</div>
          <div>
            <button class="btn btn-ghost btn-sm" data-sub-id="${subscription.subscription_id}">Delete</button>
          </div>
        </div>
      </div>`).join('');

    body.querySelectorAll('[data-sub-id]').forEach((button) => {
      button.addEventListener('click', async () => {
        try {
          await api.user.subscriptions.remove(button.dataset.subId);
          toast.success('Subscription deleted');
          await loadSubscriptions(container);
        } catch (err) {
          toast.error('Delete failed', err.message);
        }
      });
    });
  } catch (err) {
    body.innerHTML = `<div class="text-muted text-sm">${err.message}</div>`;
  }
}

function parseList(value) {
  return value.split(/[,\n]+/).map((item) => item.trim()).filter(Boolean);
}
