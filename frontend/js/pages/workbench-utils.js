import { getLang } from '../i18n.js?v=8';

const COPY = {
  en: {
    loading: 'Loading...',
    empty: 'No data yet',
    requestFailed: 'Request failed',
    shadowOnly: 'Shadow mode only. No broker order will be created.',
    source: 'Source',
    quality: 'Quality',
    safe: 'As-of safe',
  },
  zh: {
    loading: '加载中...',
    empty: '暂无数据',
    requestFailed: '请求失败',
    shadowOnly: '仅用于影子研究模式，不会创建券商订单。',
    source: '来源',
    quality: '质量',
    safe: '时点安全',
  },
};

export function lang() {
  return getLang() === 'zh' ? 'zh' : 'en';
}

export function text(key) {
  const current = lang();
  return COPY[current]?.[key] || COPY.en[key] || key;
}

export function esc(value) {
  return String(value ?? '').replace(/[&<>"']/g, ch => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  }[ch]));
}

export function num(value, digits = 3) {
  const n = Number(value);
  if (!Number.isFinite(n)) return '-';
  return n.toFixed(digits);
}

export function pct(value, digits = 2) {
  const n = Number(value);
  if (!Number.isFinite(n)) return '-';
  return `${(n * 100).toFixed(digits)}%`;
}

export function readSymbol(container, selector, fallback = 'AAPL') {
  return (container.querySelector(selector)?.value || fallback).trim().toUpperCase();
}

export function readUniverse(raw, symbol) {
  const values = String(raw || symbol || '')
    .split(/[,\s]+/)
    .map(item => item.trim().toUpperCase())
    .filter(Boolean);
  if (symbol && !values.includes(symbol)) values.unshift(symbol);
  return Array.from(new Set(values));
}

export function setLoading(el, message = text('loading')) {
  if (!el) return;
  el.innerHTML = `<div class="empty-state"><div class="empty-state__title">${esc(message)}</div></div>`;
}

export function renderError(el, err) {
  if (!el) return;
  el.innerHTML = emptyState(text('requestFailed'), err?.message || String(err || ''));
}

export function emptyState(title = text('empty'), detail = '') {
  return `<div class="empty-state">
    <div class="empty-state__title">${esc(title)}</div>
    ${detail ? `<div class="empty-state__text">${esc(detail)}</div>` : ''}
  </div>`;
}

export function metric(label, value, tone = '') {
  const toneClass = tone ? ` workbench-metric-card--${tone}` : '';
  return `<article class="workbench-metric-card${toneClass}">
    <div class="workbench-metric-card__label">${esc(label)}</div>
    <div class="workbench-metric-card__value">${esc(value)}</div>
  </article>`;
}

export function miniMetric(label, value) {
  return `<div class="workbench-mini-metric">
    <span>${esc(label)}</span>
    <strong>${esc(value)}</strong>
  </div>`;
}

export function badge(label, status = 'neutral') {
  const safeStatus = ['filled', 'failed', 'neutral'].includes(status) ? status : 'neutral';
  return `<span class="badge badge-${safeStatus}">${esc(label)}</span>`;
}

export function statusBadge(status) {
  const value = String(status || 'research_only');
  const tone = value === 'promoted' ? 'filled' : value === 'rejected' ? 'failed' : 'neutral';
  return badge(value.replace(/_/g, ' '), tone);
}

export function pathChip(value, empty = '-') {
  const raw = String(value || empty);
  return `<span class="path-chip" title="${esc(raw)}">${esc(raw)}</span>`;
}

export function renderEvidenceItems(items, options = {}) {
  const current = lang();
  const maxItems = options.maxItems || 8;
  const noData = current === 'zh' ? '暂无证据' : 'No evidence';
  const hint = current === 'zh' ? '点击扫描证据来加载来源链。' : 'Scan evidence to load source-linked items.';
  if (!items?.length) return emptyState(noData, hint);
  return `<div class="workbench-list">${items.slice(0, maxItems).map(item => `
    <article class="workbench-item">
      <div class="workbench-item__head">
        <strong>${esc(item.title || item.item_id || '')}</strong>
        ${badge(item.item_type || 'evidence', 'neutral')}
      </div>
      <p>${esc(item.summary || '')}</p>
      <div class="workbench-item__meta">
        <span>${esc(item.symbol || '')}</span>
        <span>${esc(item.provider || '')}</span>
        <span>q=${num(item.quality_score)}</span>
        <span>${esc(item.leakage_guard || '')}</span>
      </div>
    </article>
  `).join('')}</div>`;
}

export function renderFactorCards(cards, options = {}) {
  const current = lang();
  const maxItems = options.maxItems || 12;
  const noData = current === 'zh' ? '暂无因子卡' : 'No factor cards';
  const hint = current === 'zh' ? '运行因子发现后会生成 IC、RankIC 与门禁结果。' : 'Run discovery to generate IC, RankIC, and gate results.';
  if (!cards?.length) return emptyState(noData, hint);
  return `<div class="factor-card-grid">${cards.slice(0, maxItems).map(card => `
    <article class="factor-card">
      <div class="factor-card__head">
        <div>
          <strong>${esc(card.name || '')}</strong>
          <span>${esc(card.family || '')}</span>
        </div>
        ${statusBadge(card.status)}
      </div>
      <p>${esc(card.definition || card.description || '')}</p>
      <div class="workbench-mini-grid">
        ${miniMetric('IC', num(card.ic))}
        ${miniMetric('RankIC', num(card.rank_ic))}
        ${miniMetric(current === 'zh' ? '稳定性' : 'Stability', num(card.stability_score))}
        ${miniMetric(current === 'zh' ? '样本' : 'Samples', num(card.sample_count, 0))}
      </div>
      <div class="factor-card__foot">
        <span>${esc(card.transaction_cost_sensitivity || 'cost')}</span>
        <span>${esc((card.failure_modes || [])[0] || (current === 'zh' ? '门禁通过或待复核' : 'Gate passed or pending review'))}</span>
      </div>
    </article>
  `).join('')}</div>`;
}

export function renderSimulationResult(sim) {
  const current = lang();
  if (!sim) {
    return emptyState(
      current === 'zh' ? '暂无模拟结果' : 'No simulation result',
      current === 'zh' ? '选择情景后运行 Monte Carlo。' : 'Choose a scenario and run Monte Carlo.',
    );
  }
  const pathRows = Object.entries(sim.path_summary || {}).map(([key, value]) => `
    <div class="workbench-kv-row"><span>${esc(key)}</span><strong>${pct(value)}</strong></div>
  `).join('');
  const factorRows = Object.entries(sim.factor_attribution || {}).map(([key, value]) => `
    <div class="workbench-kv-row"><span>${esc(key)}</span><strong>${num(value)}</strong></div>
  `).join('');
  const analogs = (sim.historical_analogs || []).slice(0, 5).map(item => `
    <article class="workbench-item">
      <div class="workbench-item__head">
        <strong>${esc(item.title || item.event_type || '')}</strong>
        ${badge(item.symbol || sim.scenario?.symbol || '', 'neutral')}
      </div>
      <p>${esc(item.reason || '')}</p>
      <div class="workbench-item__meta"><span>${esc(item.event_type || '')}</span><span>q=${num(item.quality_score)}</span></div>
    </article>
  `).join('');

  return `
    <div class="workbench-metric-grid">
      ${metric(current === 'zh' ? '期望收益' : 'Expected', pct(sim.expected_return), 'positive')}
      ${metric(current === 'zh' ? '亏损概率' : 'Loss Prob', pct(sim.probability_of_loss))}
      ${metric('VaR 95', pct(sim.value_at_risk_95), 'risk')}
      ${metric('MDD p95', pct(sim.max_drawdown_p95), 'risk')}
    </div>
    <div class="grid-2 workbench-two-col">
      <section class="workbench-section">
        <div class="workbench-section__title">${current === 'zh' ? '路径分布' : 'Path Summary'}</div>
        <div class="workbench-kv-list">${pathRows || emptyState()}</div>
      </section>
      <section class="workbench-section">
        <div class="workbench-section__title">${current === 'zh' ? '因子归因' : 'Factor Attribution'}</div>
        <div class="workbench-kv-list">${factorRows || emptyState()}</div>
      </section>
    </div>
    <section class="workbench-section">
      <div class="workbench-section__title">${current === 'zh' ? '历史相似事件' : 'Historical Analogs'}</div>
      <div class="workbench-list">${analogs || emptyState()}</div>
    </section>
  `;
}
