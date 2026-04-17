export function ensureUiAuditLog() {
  if (!Array.isArray(window.__uiAuditLog)) {
    window.__uiAuditLog = [];
  }
  return window.__uiAuditLog;
}

export function recordUiAuditEvent(type, target, before = {}, after = {}, extra = {}) {
  const entry = {
    type,
    target,
    before,
    after,
    timestamp: new Date().toISOString(),
    ...extra,
  };
  ensureUiAuditLog().push(entry);
  window.__lastUiAuditEvent = entry;
  return entry;
}

export function clearUiAuditLog() {
  window.__uiAuditLog = [];
  window.__lastUiAuditEvent = null;
}
