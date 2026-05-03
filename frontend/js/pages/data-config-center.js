import { api } from '../qtapi.js?v=8';
import { toast } from '../components/toast.js?v=8';
import { getLang, onLangChange } from '../i18n.js?v=8';
import { emptyState, esc, metric, renderError, setLoading, statusBadge } from './workbench-utils.js?v=8';

let _container = null;
let _langCleanup = null;
let _state = null;
let _saved = null;

const COPY = {
  en: {
    title: 'Data Config Center',
    subtitle: 'Provider readiness, API-key gaps, priority, freshness, lineage, quality score, and local fallback visibility.',
    refresh: 'Refresh Config',
    save: 'Save Provider Config',
    provider: 'Provider',
    priority: 'Priority',
    apiKey: 'API Key',
    providers: 'Providers',
    saved: 'Save Evidence',
    noSaved: 'No provider config has been saved from this page yet.',
    missing: 'Missing Config',
    quality: 'Quality',
    freshness: 'Freshness',
    lineage: 'Lineage',
    mode: 'Mode',
  },
  zh: {
    title: '数据源配置中心',
    subtitle: '查看 provider 就绪状态、API key 缺口、优先级、新鲜度、血缘、质量分和本地 fallback。',
    refresh: '刷新配置',
    save: '保存 Provider 配置',
    provider: 'Provider',
    priority: '优先级',
    apiKey: 'API Key',
    providers: '数据源',
    saved: '保存证据',
    noSaved: '本页面尚未保存 provider 配置。',
    missing: '缺失配置',
    quality: '质量',
    freshness: '新鲜度',
    lineage: '血缘',
    mode: '模式',
  },
};

function c(key) {
  const lang = getLang() === 'zh' ? 'zh' : 'en';
  return COPY[lang][key] || COPY.en[key] || key;
}

function providerOptions() {
  const providers = _state?.providers || [];
  return providers.map((provider) => `<option value="${esc(provider.provider_id)}">${esc(provider.label || provider.provider_id)}</option>`).join('');
}

function renderProviders() {
  const providers = _state?.providers || [];
  if (!providers.length) return emptyState(c('providers'), 'No provider status returned.');
  return `<div class="grid-2">
    ${providers.map((provider) => `
      <article class="card">
        <div class="card-header">
          <span class="card-title">${esc(provider.label || provider.provider_id)}</span>
          ${statusBadge(provider.status)}
        </div>
        <div class="card-body" style="display:flex;flex-direction:column;gap:10px">
          <div class="workbench-kv-row"><span>${c('provider')}</span><strong>${esc(provider.provider_id)}</strong></div>
          <div class="workbench-kv-row"><span>${c('mode')}</span><strong>${esc(provider.source_mode || provider.mode || '-')}</strong></div>
          <div class="workbench-kv-row"><span>${c('freshness')}</span><strong>${esc(provider.freshness || '-')}</strong></div>
          <div class="workbench-kv-row"><span>${c('lineage')}</span><strong>${esc(provider.lineage || '-')}</strong></div>
          <div class="workbench-kv-row"><span>${c('quality')}</span><strong>${esc(provider.quality_score ?? '-')}</strong></div>
          <div class="workbench-kv-row"><span>classification</span><strong>${esc(provider.data_classification || '-')}</strong></div>
          ${(provider.missing_config || []).length ? `<div>
            <div class="form-label">${c('missing')}</div>
            <div class="token-preview">${provider.missing_config.map((item) => `<span class="token-chip token-chip--risk">${esc(item)}</span>`).join('')}</div>
          </div>` : ''}
          ${(provider.next_actions || []).length ? `<div>
            <div class="form-label">next actions</div>
            <div class="token-preview">${provider.next_actions.map((item) => `<span class="token-chip token-chip--muted">${esc(item)}</span>`).join('')}</div>
          </div>` : ''}
        </div>
      </article>
    `).join('')}
  </div>`;
}

function renderSaved() {
  if (!_saved) return emptyState(c('saved'), c('noSaved'));
  return `<pre style="white-space:pre-wrap;max-height:320px;overflow:auto;font-size:11px">${esc(JSON.stringify(_saved, null, 2))}</pre>`;
}

function shell() {
  return `
    <div class="workbench-page" data-no-autotranslate="true">
      <div class="page-header">
        <div>
          <div class="page-header__title">${c('title')}</div>
          <div class="page-header__sub">${c('subtitle')}</div>
        </div>
        <div class="page-header__actions">
          <button class="btn btn-secondary btn-sm" id="btn-data-config-refresh">${c('refresh')}</button>
          <button class="btn btn-primary btn-sm" id="btn-save-provider">${c('save')}</button>
        </div>
      </div>

      <div class="metric-grid metrics-row-4">
        ${metric('Status', (_state?.status || 'loading').toUpperCase())}
        ${metric('Providers', _state?.provider_count ?? '-')}
        ${metric('Storage', _state?.storage?.mode || '-')}
        ${metric('Backend', _state?.storage?.preferred_artifact_backend || '-')}
      </div>

      <div class="grid-2" style="margin-top:18px">
        <section class="card">
          <div class="card-header"><span class="card-title">${c('save')}</span>${statusBadge(_saved?.status || 'idle')}</div>
          <div class="card-body" style="display:grid;gap:12px">
            <label class="form-label" for="provider-id">${c('provider')}</label>
            <select class="form-input" id="provider-id">${providerOptions()}</select>
            <label class="form-label" for="provider-priority">${c('priority')}</label>
            <input class="form-input" id="provider-priority" type="number" min="1" max="999" value="50">
            <label class="form-label" for="provider-api-key">${c('apiKey')}</label>
            <input class="form-input" id="provider-api-key" type="password" placeholder="optional local acceptance key">
          </div>
        </section>
        <section class="card">
          <div class="card-header"><span class="card-title">${c('saved')}</span>${statusBadge(_saved?.status || 'idle')}</div>
          <div class="card-body" id="data-config-saved">${renderSaved()}</div>
        </section>
      </div>

      <section style="margin-top:18px">
        <div class="card-header"><span class="card-title">${c('providers')}</span>${statusBadge(_state?.status || 'loading')}</div>
        <div id="data-config-providers">${renderProviders()}</div>
      </section>
    </div>
  `;
}

async function load(container) {
  setLoading(container, getLang() === 'zh' ? '正在加载数据源配置...' : 'Loading data config center...');
  try {
    _state = await api.dataConfig.center();
    container.innerHTML = shell();
    bind(container);
  } catch (error) {
    renderError(container, error, { context: 'data-config-center', showRetry: true, onRetry: () => load(container) });
  }
}

async function saveProvider(container) {
  const target = container.querySelector('#data-config-saved');
  setLoading(target, getLang() === 'zh' ? '正在保存配置...' : 'Saving provider config...');
  try {
    _saved = await api.dataConfig.saveProvider({
      provider_id: container.querySelector('#provider-id')?.value || 'yfinance',
      priority: Number(container.querySelector('#provider-priority')?.value || 50),
      api_key: container.querySelector('#provider-api-key')?.value || undefined,
      acceptance_namespace: 'ui_data_config_center',
    });
    toast.success(c('save'), String(_saved.status || 'saved'));
    await load(container);
  } catch (error) {
    renderError(target, error, { context: 'save-provider-config' });
    toast.error(c('save'), error.message);
  }
}

function bind(container) {
  container.querySelector('#btn-data-config-refresh')?.addEventListener('click', () => load(container));
  container.querySelector('#btn-save-provider')?.addEventListener('click', () => saveProvider(container));
}

export async function render(container) {
  _container = container;
  _langCleanup?.();
  _langCleanup = onLangChange(() => {
    if (_container?.isConnected) {
      _container.innerHTML = shell();
      bind(_container);
    }
  });
  await load(container);
}

export function destroy() {
  _langCleanup?.();
  _langCleanup = null;
  _container = null;
}
