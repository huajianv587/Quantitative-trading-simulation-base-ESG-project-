import { api } from '../qtapi.js?v=8';
import { getLang, onLangChange } from '../i18n.js?v=8';
import { metric, pct, renderError, renderTokenPreview, setLoading, splitTokens, statusBadge } from './workbench-utils.js?v=8';

let _container = null;
let _langCleanup = null;

const COPY = {
  en: {
    title: 'Outcome Center',
    subtitle: 'Shadow decision tracking, calibration, regret, and failure-case mining.',
    refresh: 'Refresh Outcomes',
    record: 'Record Demo Outcome',
    symbol: 'Symbol',
    decision: 'Decision ID',
    realized: 'Realized Return',
    benchmark: 'Benchmark Return',
    summary: 'Calibration Summary',
    records: 'Outcome Records',
  },
  zh: {
    title: '结果追踪',
    subtitle: '影子决策后验表现、校准、遗憾值与失败案例挖掘。',
    refresh: '刷新结果',
    record: '记录演示结果',
    symbol: '股票',
    decision: '决策 ID',
    realized: '真实收益',
    benchmark: '基准收益',
    summary: '校准摘要',
    records: '结果记录',
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
  renderTopPreview();
  _langCleanup = onLangChange(() => {
    if (_container) {
      renderShell();
      wire();
      renderTopPreview();
      refreshOutcomes();
    }
  });
  await refreshOutcomes();
}

export function unmount() {
  if (_langCleanup) _langCleanup();
  _container = null;
}

function renderShell() {
  _container.innerHTML = `
    <div class="workbench-page live-page outcome-center-page">
      <section class="run-panel">
        <div class="run-panel__header">
          <div class="run-panel__title">${c('title')}</div>
          <div class="run-panel__sub">${c('subtitle')}</div>
        </div>
        <div class="run-panel__body">
          <div class="grid-2 compact-control-grid outcome-top-grid">
            <label class="field field--with-preview">
              <span>${c('symbol')}</span>
              <input id="outcome-symbol" value="AAPL">
              <div id="outcome-symbol-preview"></div>
            </label>
            <label class="field">
              <span>${c('decision')}</span>
              <input id="outcome-decision" placeholder="optional decision id">
            </label>
            <label class="field">
              <span>${c('realized')}</span>
              <input id="outcome-realized" value="0.012">
            </label>
            <label class="field">
              <span>${c('benchmark')}</span>
              <input id="outcome-benchmark" value="0.004">
            </label>
          </div>
        </div>
        <div class="run-panel__foot workbench-action-grid">
          <button class="btn btn-primary workbench-action-btn" id="btn-outcome-refresh">${c('refresh')}</button>
          <button class="btn btn-ghost workbench-action-btn" id="btn-outcome-record">${c('record')}</button>
        </div>
      </section>
      <section class="grid-2 workbench-main-grid outcome-grid">
        <article class="run-panel">
          <div class="run-panel__header"><div class="run-panel__title">${c('summary')}</div></div>
          <div class="run-panel__body" id="outcome-summary">${renderSummaryPreview()}</div>
        </article>
        <article class="run-panel">
          <div class="run-panel__header"><div class="run-panel__title">${c('records')}</div></div>
          <div class="run-panel__body" id="outcome-records">${renderRecordsPreview()}</div>
        </article>
      </section>
    </div>`;
}

function wire() {
  _container.querySelector('#btn-outcome-refresh')?.addEventListener('click', refreshOutcomes);
  _container.querySelector('#btn-outcome-record')?.addEventListener('click', recordOutcome);
  _container.querySelector('#outcome-symbol')?.addEventListener('input', renderTopPreview);
}

function renderTopPreview() {
  const symbol = String(_container.querySelector('#outcome-symbol')?.value || 'AAPL').trim().toUpperCase();
  _container.querySelector('#outcome-symbol-preview').innerHTML = renderTokenPreview(symbol ? [symbol] : [], {
    tone: 'accent',
    maxItems: 1,
  });
}

function renderSummaryPreview() {
  return `
    <div class="agent-preview">
      <div>
        <div class="functional-empty__eyebrow">Shadow Tracking</div>
        <h3>Calibration is waiting for records</h3>
        <p>No live order is created. Outcomes are used for calibration, regret tracking, and Stage 2/3 failure mining.</p>
      </div>
      <div class="workbench-metric-grid">
        ${metric('Records', 0, 'positive')}
        ${metric('Hit rate', '-')}
        ${metric('Brier', '-')}
        ${metric('Excess', '-')}
      </div>
      <div class="workbench-kv-list compact-kv-list">
        <div class="workbench-kv-row"><span>Direction hit</span><strong>after return</strong></div>
        <div class="workbench-kv-row"><span>Calibration curve</span><strong>after samples</strong></div>
        <div class="workbench-kv-row"><span>Failure case pool</span><strong>Stage 2/3</strong></div>
        <div class="workbench-kv-row"><span>Broker</span><strong>shadow only</strong></div>
      </div>
      <div class="preview-step-grid">
        <div class="preview-step"><span>Hit rate becomes stable after repeated rows</span><strong>queued</strong></div>
        <div class="preview-step"><span>Brier score tracks confidence calibration</span><strong>armed</strong></div>
        <div class="preview-step"><span>Drawdown breaches are forwarded to failure mining</span><strong>watch</strong></div>
      </div>
    </div>`;
}

function renderRecordsPreview() {
  return `
    <div class="agent-preview">
      <div>
        <div class="functional-empty__eyebrow">Record Preview</div>
        <h3>No newly recorded outcome</h3>
        <p>Use Record Demo Outcome to add a shadow row with symbol, decision id, realized return, benchmark return, and excess return.</p>
      </div>
      <div class="workbench-kv-list compact-kv-list">
        <div class="workbench-kv-row"><span>Decision ID</span><strong>optional</strong></div>
        <div class="workbench-kv-row"><span>Realized vs benchmark</span><strong>tracked</strong></div>
        <div class="workbench-kv-row"><span>Drawdown breach</span><strong>watched</strong></div>
        <div class="workbench-kv-row"><span>Direction hit</span><strong>derived</strong></div>
      </div>
      <div class="preview-step-grid">
        <div class="preview-step"><span>Latest row remains shadow-only and reproducible</span><strong>safe</strong></div>
        <div class="preview-step"><span>Excess return becomes a Stage 2 label candidate</span><strong>tagged</strong></div>
      </div>
    </div>`;
}

async function refreshOutcomes() {
  const summary = _container.querySelector('#outcome-summary');
  setLoading(summary, 'Loading outcome tracking...');
  try {
    const payload = await api.outcomes.evaluate({ symbol: _container.querySelector('#outcome-symbol')?.value || 'AAPL' });
    renderOutcomes(payload.summary || payload);
  } catch (err) {
    renderError(summary, err);
  }
}

async function recordOutcome() {
  const summary = _container.querySelector('#outcome-summary');
  setLoading(summary, 'Recording shadow outcome...');
  try {
    const payload = await api.outcomes.evaluate({
      symbol: _container.querySelector('#outcome-symbol')?.value || 'AAPL',
      decision_id: _container.querySelector('#outcome-decision')?.value || null,
      realized_return: Number(_container.querySelector('#outcome-realized')?.value || 0),
      benchmark_return: Number(_container.querySelector('#outcome-benchmark')?.value || 0),
      drawdown: -0.02,
      notes: 'UI demo shadow outcome; not a broker execution.',
    });
    renderOutcomes(payload.summary || payload, payload.record || payload.latest_record || null);
  } catch (err) {
    renderError(summary, err);
  }
}

function renderOutcomes(summary, latest = null) {
  _container.querySelector('#outcome-summary').innerHTML = `
    <div class="workbench-metric-grid">
      ${metric('Records', summary.record_count ?? 0, 'positive')}
      ${metric('Hit rate', summary.hit_rate == null ? '-' : pct(summary.hit_rate))}
      ${metric('Brier', summary.mean_brier == null ? '-' : Number(summary.mean_brier).toFixed(3))}
      ${metric('Excess', summary.mean_excess_return == null ? '-' : pct(summary.mean_excess_return))}
    </div>
    <div class="workbench-kv-list compact-kv-list">
      <div class="workbench-kv-row"><span>Shadow mode</span><strong>${summary.shadow_mode ? 'on' : 'off'}</strong></div>
      <div class="workbench-kv-row"><span>Drawdown breaches</span><strong>${summary.drawdown_breaches ?? 0}</strong></div>
      <div class="workbench-kv-row"><span>Calibration target</span><strong>direction + brier</strong></div>
      <div class="workbench-kv-row"><span>Failure mining</span><strong>Stage 2/3 candidate pool</strong></div>
    </div>
    <div class="preview-step-grid">
      <div class="preview-step"><span>Calibration curve</span><strong>${summary.record_count >= 10 ? 'forming' : 'waiting'}</strong></div>
      <div class="preview-step"><span>Regret tracking</span><strong>${summary.mean_excess_return == null ? 'queued' : 'active'}</strong></div>
      <div class="preview-step"><span>Failure intake</span><strong>${(summary.drawdown_breaches ?? 0) > 0 ? 'flagged' : 'clean'}</strong></div>
    </div>
  `;
  const record = latest
    ? {
        ...latest,
        excess_return: latest.excess_return ?? ((Number(latest.realized_return || 0) - Number(latest.benchmark_return || 0)) || 0),
      }
    : null;
  _container.querySelector('#outcome-records').innerHTML = record ? `
    <div class="workbench-list">
      <article class="workbench-item">
        <div class="workbench-item__head">
          <strong>${record.decision_id || record.outcome_id || 'latest outcome'}</strong>
          ${statusBadge(record.direction_hit ? 'promoted' : 'research_only')}
        </div>
        <p>${record.notes || 'Latest outcome row recorded in shadow mode.'}</p>
        <div class="workbench-item__meta">
          <span>${record.symbol || ''}</span>
          <span>realized=${pct(record.realized_return)}</span>
          <span>benchmark=${pct(record.benchmark_return)}</span>
          <span>excess=${pct(record.excess_return)}</span>
        </div>
      </article>
      <div class="workbench-kv-list compact-kv-list">
        <div class="workbench-kv-row"><span>Direction hit</span><strong>${record.direction_hit == null ? 'pending' : record.direction_hit ? 'yes' : 'no'}</strong></div>
        <div class="workbench-kv-row"><span>Decision ID</span><strong>${record.decision_id || 'optional'}</strong></div>
        <div class="workbench-kv-row"><span>Tracking mode</span><strong>shadow</strong></div>
      </div>
      <div class="preview-step-grid">
        <div class="preview-step"><span>Realized return captured</span><strong>${pct(record.realized_return)}</strong></div>
        <div class="preview-step"><span>Benchmark return captured</span><strong>${pct(record.benchmark_return)}</strong></div>
        <div class="preview-step"><span>Excess return delta</span><strong>${pct(record.excess_return)}</strong></div>
      </div>
    </div>` : renderRecordsPreview();
}
