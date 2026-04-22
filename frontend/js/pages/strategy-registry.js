import { api } from '../qtapi.js?v=8';
import { toast } from '../components/toast.js?v=8';
import { getLang, onLangChange } from '../i18n.js?v=8';
import {
  emptyState,
  esc,
  metric,
  pct,
  renderError,
  renderTokenPreview,
  setLoading,
  statusBadge,
} from './workbench-utils.js?v=8';

let _container = null;
let _langCleanup = null;
let _strategies = [];
let _policy = null;
let _clickHandler = null;

const COPY = {
  en: {
    title: 'Strategy Registry',
    subtitle: 'Strategy templates, allocation slots, and factor lineage for Trading Ops.',
    refresh: 'Refresh Registry',
    loading: 'Loading strategy registry...',
    activeCount: 'Active Strategies',
    allocation: 'Allocated Capital',
    allowed: 'Policy Allowlist',
    paperReady: 'Runtime Ready',
    saveAllocation: 'Save Allocation',
    pause: 'Pause Strategy',
    activate: 'Activate Strategy',
    maxSymbols: 'Max Symbols',
    riskProfile: 'Risk Profile',
    factorDeps: 'Factor Pipeline',
    allowedSymbols: 'Allowed Symbols',
    notes: 'Notes',
    noStrategies: 'No strategy templates yet',
    noStrategiesHint: 'The registry seeds runtime-ready templates before Trading Ops consumes them.',
    slot: 'Strategy Slot',
    allowlistState: 'Allowlist',
    included: 'included',
    excluded: 'excluded',
    saved: 'Strategy allocation saved',
    toggled: 'Strategy state updated',
    paperHint: 'Only active slots can be consumed by Trading Ops and runtime automation.',
  },
  zh: {
    title: '策略注册表',
    subtitle: '面向 Trading Ops 的策略模板、分配槽位与因子依赖表。',
    refresh: '刷新注册表',
    loading: '正在加载策略注册表...',
    activeCount: '活跃策略数',
    allocation: '已分配资金',
    allowed: '策略白名单',
    paperReady: '运行时就绪',
    saveAllocation: '保存分配',
    pause: '暂停策略',
    activate: '启用策略',
    maxSymbols: '最大标的数',
    riskProfile: '风险画像',
    factorDeps: '因子流水线',
    allowedSymbols: '允许标的',
    notes: '说明',
    noStrategies: '暂无策略模板',
    noStrategiesHint: 'Trading Ops 在消费前，会先从这里读取运行时就绪的策略模板。',
    slot: '策略槽位',
    allowlistState: '白名单状态',
    included: '已纳入',
    excluded: '未纳入',
    saved: '策略分配已保存',
    toggled: '策略状态已更新',
    paperHint: '只有 active 的槽位才会被 Trading Ops 与自动化执行真正读取。',
  },
};

function c(key) {
  const lang = getLang() === 'zh' ? 'zh' : 'en';
  return COPY[lang][key] || COPY.en[key] || key;
}

export async function render(container) {
  _container = container;
  renderShell();
  wire();
  _langCleanup = onLangChange(() => {
    if (!_container?.isConnected) return;
    renderShell();
    wire();
    renderRegistry();
  });
  await refreshRegistry();
}

export function destroy() {
  _langCleanup?.();
  _langCleanup = null;
  if (_container && _clickHandler) {
    _container.removeEventListener('click', _clickHandler);
  }
  _clickHandler = null;
  _container = null;
  _strategies = [];
  _policy = null;
}

function renderShell() {
  _container.innerHTML = `
    <div class="workbench-page strategy-registry-page" data-no-autotranslate="true">
      <section class="run-panel">
        <div class="run-panel__header">
          <div class="run-panel__title">${c('title')}</div>
          <div class="run-panel__sub">${c('subtitle')}</div>
        </div>
        <div class="run-panel__body">
          <div id="strategy-kpis" class="workbench-metric-grid">${emptyState(c('loading'))}</div>
          <div class="workbench-section">
            <div class="workbench-section__title">${c('slot')}</div>
            <p class="workbench-section__hint">${c('paperHint')}</p>
          </div>
        </div>
        <div class="run-panel__foot workbench-action-grid">
          <button class="btn btn-ghost workbench-action-btn" id="btn-strategy-refresh">${c('refresh')}</button>
        </div>
      </section>
      <section class="grid-1 workbench-main-grid">
        <article class="card">
          <div class="card-header"><span class="card-title">${c('title')}</span></div>
          <div class="card-body" id="strategy-registry-list">${emptyState(c('loading'))}</div>
        </article>
      </section>
    </div>
  `;
}

function wire() {
  if (_container && _clickHandler) {
    _container.removeEventListener('click', _clickHandler);
  }
  _container.querySelector('#btn-strategy-refresh')?.addEventListener('click', refreshRegistry);
  _clickHandler = onClick;
  _container.addEventListener('click', _clickHandler);
}

async function refreshRegistry() {
  setLoading(_container.querySelector('#strategy-kpis'), c('loading'));
  setLoading(_container.querySelector('#strategy-registry-list'), c('loading'));
  try {
    const [strategyPayload, policy] = await Promise.all([
      api.trading.strategies(),
      api.trading.autopilotPolicy().catch(() => null),
    ]);
    _strategies = Array.isArray(strategyPayload?.strategies) ? strategyPayload.strategies : [];
    _policy = policy;
    renderRegistry();
  } catch (error) {
    renderError(_container.querySelector('#strategy-kpis'), error);
    renderError(_container.querySelector('#strategy-registry-list'), error);
  }
}

function renderRegistry() {
  renderKpis();
  const host = _container.querySelector('#strategy-registry-list');
  if (!_strategies.length) {
    host.innerHTML = emptyState(c('noStrategies'), c('noStrategiesHint'));
    return;
  }
  host.innerHTML = `
    <div class="factor-card-grid">
      ${_strategies.map((strategy) => renderStrategyCard(strategy)).join('')}
    </div>
  `;
}

function renderKpis() {
  const activeStrategies = _strategies.filter((row) => String(row.status || '').toLowerCase() === 'active');
  const activeAllocation = _strategies.reduce((sum, row) => {
    const allocation = row.allocation?.capital_allocation ?? row.capital_allocation ?? 0;
    return sum + Number(allocation || 0);
  }, 0);
  const allowlist = Array.isArray(_policy?.allowed_strategies) ? _policy.allowed_strategies : [];
  const paperReady = _strategies.filter((row) => row.paper_ready).length;
  _container.querySelector('#strategy-kpis').innerHTML = `
    ${metric(c('activeCount'), activeStrategies.length, activeStrategies.length ? 'positive' : 'risk')}
    ${metric(c('allocation'), pct(activeAllocation))}
    ${metric(c('allowed'), allowlist.length, allowlist.length ? 'positive' : 'risk')}
    ${metric(c('paperReady'), paperReady, paperReady ? 'positive' : 'risk')}
  `;
}

function renderStrategyCard(strategy) {
  const allocation = strategy.allocation || {};
  const included = Array.isArray(_policy?.allowed_strategies)
    ? _policy.allowed_strategies.includes(strategy.strategy_id)
    : false;
  return `
    <article class="factor-card" data-strategy-id="${esc(strategy.strategy_id)}">
      <div class="factor-card__head">
        <div>
          <strong>${esc(strategy.display_name || strategy.strategy_id)}</strong>
          <span>${esc(strategy.strategy_id)}</span>
        </div>
        ${statusBadge(strategy.status || 'neutral')}
      </div>
      <p>${esc(strategy.description || '')}</p>
      <div class="workbench-mini-grid">
        ${metric(c('riskProfile'), strategy.risk_profile || '-')}
        ${metric(c('allocation'), pct(allocation.capital_allocation ?? strategy.capital_allocation ?? 0))}
        ${metric(c('allowlistState'), included ? c('included') : c('excluded'), included ? 'positive' : 'risk')}
        ${metric(c('paperReady'), strategy.paper_ready ? 'yes' : 'no', strategy.paper_ready ? 'positive' : 'risk')}
      </div>
      <div class="workbench-section">
        <div class="workbench-section__title">${c('factorDeps')}</div>
        ${renderTokenPreview(strategy.factor_dependencies || [], { tone: 'accent', maxItems: 6 })}
      </div>
      <div class="workbench-section">
        <div class="workbench-section__title">${c('allowedSymbols')}</div>
        ${renderTokenPreview(strategy.allowed_symbols || [], { tone: 'neutral', maxItems: 6 })}
      </div>
      <div class="grid-2 compact-control-grid">
        <label class="field">
          <span>${c('allocation')}</span>
          <input type="number" step="0.01" data-allocation-input value="${esc(allocation.capital_allocation ?? strategy.capital_allocation ?? 0)}">
        </label>
        <label class="field">
          <span>${c('maxSymbols')}</span>
          <input type="number" data-max-symbols-input value="${esc(allocation.max_symbols ?? 10)}">
        </label>
      </div>
      <div class="run-panel__foot workbench-action-grid">
        <button class="btn btn-ghost workbench-action-btn" data-strategy-toggle>
          ${String(strategy.status || '').toLowerCase() === 'active' ? c('pause') : c('activate')}
        </button>
        <button class="btn btn-primary workbench-action-btn" data-strategy-save>${c('saveAllocation')}</button>
      </div>
    </article>
  `;
}

async function onClick(event) {
  const card = event.target.closest('[data-strategy-id]');
  if (!card) return;
  const strategyId = card.getAttribute('data-strategy-id');
  if (event.target.closest('[data-strategy-toggle]')) {
    const current = _strategies.find((row) => row.strategy_id === strategyId);
    const nextStatus = String(current?.status || '').toLowerCase() === 'active' ? 'paused' : 'active';
    try {
      await api.trading.toggleStrategy(strategyId, { status: nextStatus });
      toast.success(c('toggled'));
      await refreshRegistry();
    } catch (error) {
      toast.error(c('toggled'), error.message || '');
    }
    return;
  }
  if (event.target.closest('[data-strategy-save]')) {
    const allocationValue = Number(card.querySelector('[data-allocation-input]')?.value || 0);
    const maxSymbolsValue = Number(card.querySelector('[data-max-symbols-input]')?.value || 10);
    const current = _strategies.find((row) => row.strategy_id === strategyId);
    try {
      await api.trading.allocateStrategy(strategyId, {
        capital_allocation: allocationValue,
        max_symbols: maxSymbolsValue,
        status: String(current?.status || '').toLowerCase() === 'paused' ? 'paused' : 'active',
      });
      toast.success(c('saved'));
      await refreshRegistry();
    } catch (error) {
      toast.error(c('saved'), error.message || '');
    }
  }
}
