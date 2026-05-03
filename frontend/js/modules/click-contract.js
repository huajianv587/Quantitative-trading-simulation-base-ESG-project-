import { api } from '../qtapi.js?v=8';
import { recordUiAuditEvent } from './ui-audit.js?v=8';

const STATUS_ID = 'click-contract-status';
const INTERACTIVE_SELECTOR = [
  'a[href]',
  'button',
  'select',
  'input[type="checkbox"]',
  'input[type="radio"]',
  '[role="button"]',
  '[data-path]',
  '[data-action]',
  '[data-click-contract]',
].join(',');

const IGNORE_SELECTOR = [
  '#click-contract-status',
  '#click-contract-status *',
  '.toast',
  '.toast *',
  '[data-click-contract="off"]',
].join(',');

const POINTER_SELECTOR = [
  '#zoom-in-btn',
  '#zoom-out-btn',
  '[data-click-contract="pointer"]',
].join(',');

const BUSINESS_EVENT_EXCLUDE = new Set([
  '/api/v1/platform/ui-action/evidence',
  '/api/health',
]);

let initialized = false;
let statusTimer = null;
const recentSchedules = new WeakMap();

function ensureStatusNode() {
  let node = document.getElementById(STATUS_ID);
  if (node) return node;
  node = document.createElement('div');
  node.id = STATUS_ID;
  node.className = 'click-contract-status';
  node.setAttribute('role', 'status');
  node.setAttribute('aria-live', 'polite');
  node.innerHTML = `
    <div class="click-contract-status__dot"></div>
    <div>
      <div class="click-contract-status__title">点击合约待命</div>
      <div class="click-contract-status__text">所有可点击控件都会产生业务请求、路由反馈或后端证据。</div>
    </div>
  `;
  document.body.appendChild(node);
  return node;
}

function setStatus(tone, title, message) {
  const node = ensureStatusNode();
  node.className = `click-contract-status click-contract-status--${tone || 'ready'} is-visible`;
  node.querySelector('.click-contract-status__title').textContent = title || '点击已处理';
  node.querySelector('.click-contract-status__text').textContent = message || '';
  clearTimeout(statusTimer);
  statusTimer = setTimeout(() => {
    node.classList.remove('is-visible');
  }, 4200);
}

function apiEvents() {
  if (!Array.isArray(window.__qtApiEvents)) window.__qtApiEvents = [];
  return window.__qtApiEvents;
}

function appendApiEvent(event) {
  const events = apiEvents();
  events.push(event);
  if (events.length > 400) events.splice(0, events.length - 400);
}

function currentRoute() {
  return window.location.hash.replace(/^#/, '') || '/dashboard';
}

function compactText(value, max = 140) {
  return String(value || '').replace(/\s+/g, ' ').trim().slice(0, max);
}

function targetLabel(target) {
  return compactText(
    target.getAttribute('aria-label')
    || target.getAttribute('title')
    || target.textContent
    || target.value
    || target.id
    || target.name
    || target.tagName,
  );
}

function targetPayload(target) {
  const href = target.getAttribute('href') || '';
  return {
    tag: String(target.tagName || '').toLowerCase(),
    id: target.id || '',
    role: target.getAttribute('role') || '',
    label: targetLabel(target),
    href,
    name: target.getAttribute('name') || '',
    type: target.getAttribute('type') || '',
    contract: target.getAttribute('data-click-contract') || '',
  };
}

function isTrackableTarget(target) {
  if (!target || !(target instanceof Element)) return false;
  if (target.closest(IGNORE_SELECTOR)) return false;
  const interactive = target.closest(INTERACTIVE_SELECTOR);
  if (!interactive || interactive.closest(IGNORE_SELECTOR)) return false;
  if (interactive.disabled || interactive.getAttribute('aria-disabled') === 'true') return false;
  return interactive;
}

function businessRequestsSince(startedAt) {
  return apiEvents().filter((event) => (
    (event.type === 'request-start' || event.type === 'request-end' || event.type === 'request-error')
    && event.startedAt >= startedAt
    && !BUSINESS_EVENT_EXCLUDE.has(event.path)
  ));
}

async function recordEvidence(payload) {
  try {
    let timeoutId = null;
    const timeout = new Promise((resolve) => {
      timeoutId = window.setTimeout(() => resolve({
        status: 'blocked',
        reason: 'ui_action_evidence_timeout',
        next_actions: ['检查 /api/v1/platform/ui-action/evidence 是否可用'],
      }), 2500);
    });
    const result = await Promise.race([
      api.platform.recordUiAction(payload),
      timeout,
    ]);
    if (timeoutId) window.clearTimeout(timeoutId);
    const degraded = String(result?.status || '').toLowerCase() !== 'ready';
    setStatus(
      result?.status === 'blocked' ? 'blocked' : (degraded ? 'degraded' : 'ready'),
      result?.status === 'blocked' ? '点击后端记录超时' : (degraded ? '点击已降级记录' : '点击已连接后端'),
      result?.display?.message || result?.reason || '后端已记录该 UI 操作证据。',
    );
    return result;
  } catch (error) {
    setStatus('blocked', '点击后端记录失败', error?.message || String(error || 'request failed'));
    return {
      status: 'blocked',
      reason: error?.message || String(error || 'request failed'),
      next_actions: ['检查 /api/v1/platform/ui-action/evidence'],
    };
  }
}

function writeAudit(interactive, before, afterRoute, outcome, requests, evidenceStatus, evidence = null) {
  const target = targetPayload(interactive);
  const audit = recordUiAuditEvent(
    'click_contract',
    target.id || target.label || target.tag,
    { route: before.route },
    { route: afterRoute, ...outcome },
    {
      target,
      evidence_status: evidenceStatus,
      evidence_action_id: evidence?.action_id || null,
      evidence_result: evidence || null,
      request_paths: requests.map((item) => item.path).slice(0, 8),
    },
  );
  window.__lastClickContract = audit;
  return { audit, target };
}

function finalizeInteraction(interactive, eventType, before) {
  const afterText = document.body ? document.body.innerText || '' : '';
  const afterRoute = currentRoute();
  const requests = businessRequestsSince(before.startedAt);
  const routeChanged = afterRoute !== before.route;
  const domChanged = compactText(afterText, 500) !== compactText(before.text, 500);
  const outcome = {
    route_changed: routeChanged,
    dom_changed: domChanged,
    business_request_count: requests.length,
  };

  if (requests.length) {
    const { target } = writeAudit(interactive, before, afterRoute, outcome, requests, 'business_api');
    setStatus('ready', '业务后端已触发', `${target.label || target.id || target.tag} 已调用 ${requests[0].path}`);
    return;
  }

  const evidencePayload = {
    event_type: eventType,
    route: before.route,
    url_hash: window.location.hash || '',
    target: targetPayload(interactive),
    outcome,
    client: {
      app_id: 'quant-terminal-web',
      viewport: { width: window.innerWidth, height: window.innerHeight },
    },
  };
  const { audit, target } = writeAudit(
    interactive,
    before,
    afterRoute,
    outcome,
    requests,
    'pending_backend_evidence',
  );
  setStatus('pending', '点击证据记录中', `${target.label || target.id || target.tag} 已产生审计反馈，正在异步写入后端证据。`);

  recordEvidence(evidencePayload).then((evidence) => {
    audit.evidence_status = evidence?.status || 'blocked';
    audit.evidence_action_id = evidence?.action_id || null;
    audit.evidence_result = evidence || null;
    window.__lastClickContract = audit;
  });
}

function scheduleInteraction(interactive, eventType) {
  const now = Date.now();
  const previous = recentSchedules.get(interactive) || 0;
  if (now - previous < 300) return;
  recentSchedules.set(interactive, now);
  const before = {
    startedAt: now,
    route: currentRoute(),
    text: document.body ? document.body.innerText || '' : '',
  };
  setStatus('pending', '点击处理中', targetLabel(interactive) || '正在确认后端和页面反馈');
  window.setTimeout(() => finalizeInteraction(interactive, eventType, before), 650);
}

export function initClickContracts() {
  if (initialized) return;
  initialized = true;
  ensureStatusNode();

  window.addEventListener('qtapi:request-start', (event) => {
    appendApiEvent({ type: 'request-start', startedAt: Date.now(), ...(event.detail || {}) });
  });
  window.addEventListener('qtapi:request-end', (event) => {
    appendApiEvent({ type: 'request-end', startedAt: Date.now(), ...(event.detail || {}) });
  });
  window.addEventListener('qtapi:request-error', (event) => {
    appendApiEvent({ type: 'request-error', startedAt: Date.now(), ...(event.detail || {}) });
  });

  document.addEventListener('click', (event) => {
    const interactive = isTrackableTarget(event.target);
    if (!interactive) return;
    scheduleInteraction(interactive, 'click');
  }, true);

  document.addEventListener('pointerdown', (event) => {
    const rawTarget = event.target instanceof Element ? event.target : null;
    const pointerTarget = rawTarget?.closest(POINTER_SELECTOR);
    if (!pointerTarget) return;
    const interactive = isTrackableTarget(pointerTarget);
    if (!interactive) return;
    scheduleInteraction(interactive, 'pointerdown');
  }, true);

  document.addEventListener('change', (event) => {
    const interactive = isTrackableTarget(event.target);
    if (!interactive) return;
    scheduleInteraction(interactive, 'change');
  }, true);
}
