import { api } from '../qtapi.js?v=8';
import { getLang, onLangChange } from '../i18n.js?v=8';
import { metric, pct, renderError, renderTokenPreview, setLoading, statusBadge } from './workbench-utils.js?v=8';

let _container = null;
let _langCleanup = null;
let _latestReview = null;

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
    subtitle: '用于跟踪影子决策表现、校准质量、遗憾值与失败案例回流。',
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

function t(en, zh) {
  return getLang() === 'zh' ? zh : en;
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

export function destroy() {
  _langCleanup?.();
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
              <input id="outcome-decision" placeholder="${t('optional decision id', '可选决策 ID')}">
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
        <div class="functional-empty__eyebrow">${t('Shadow Tracking', '影子追踪')}</div>
        <h3>${t('Calibration is waiting for records', '校准正在等待记录')}</h3>
        <p>${t('No live order is created. Outcomes are used for calibration, regret tracking, and Stage 2/3 failure mining.', '这里不会创建实盘订单。结果记录用于校准、遗憾值跟踪，以及 Stage 2/3 失败案例挖掘。')}</p>
      </div>
      <div class="workbench-metric-grid">
        ${metric(t('Records', '记录数'), 0, 'positive')}
        ${metric(t('Hit rate', '命中率'), '-')}
        ${metric('Brier', '-')}
        ${metric(t('Excess', '超额收益'), '-')}
      </div>
      <div class="workbench-kv-list compact-kv-list">
        <div class="workbench-kv-row"><span>${t('Direction hit', '方向命中')}</span><strong>${t('after return', '回报落地后计算')}</strong></div>
        <div class="workbench-kv-row"><span>${t('Calibration curve', '校准曲线')}</span><strong>${t('after samples', '样本积累后形成')}</strong></div>
        <div class="workbench-kv-row"><span>${t('Failure case pool', '失败案例池')}</span><strong>Stage 2/3</strong></div>
        <div class="workbench-kv-row"><span>${t('Broker', '券商执行')}</span><strong>${t('shadow only', '仅影子模式')}</strong></div>
      </div>
      <div class="preview-step-grid">
        <div class="preview-step"><span>${t('Hit rate becomes stable after repeated rows', '重复记录累积后，命中率会逐渐稳定')}</span><strong>${t('queued', '排队中')}</strong></div>
        <div class="preview-step"><span>${t('Brier score tracks confidence calibration', 'Brier 分数用于追踪置信度校准')}</span><strong>${t('armed', '已启用')}</strong></div>
        <div class="preview-step"><span>${t('Drawdown breaches are forwarded to failure mining', '回撤越界会进入失败案例挖掘')}</span><strong>${t('watch', '观察')}</strong></div>
      </div>
    </div>`;
}

function renderRecordsPreview() {
  return `
    <div class="agent-preview">
      <div>
        <div class="functional-empty__eyebrow">${t('Record Preview', '记录预览')}</div>
        <h3>${t('No newly recorded outcome', '暂无新记录结果')}</h3>
        <p>${t('Use Record Demo Outcome to add a shadow row with symbol, decision id, realized return, benchmark return, and excess return.', '点击记录演示结果，可新增一条包含股票、决策 ID、真实收益、基准收益和超额收益的影子记录。')}</p>
      </div>
      <div class="workbench-kv-list compact-kv-list">
        <div class="workbench-kv-row"><span>${t('Decision ID', '决策 ID')}</span><strong>${t('optional', '可选')}</strong></div>
        <div class="workbench-kv-row"><span>${t('Realized vs benchmark', '真实收益与基准')}</span><strong>${t('tracked', '已跟踪')}</strong></div>
        <div class="workbench-kv-row"><span>${t('Drawdown breach', '回撤越界')}</span><strong>${t('watched', '观察中')}</strong></div>
        <div class="workbench-kv-row"><span>${t('Direction hit', '方向命中')}</span><strong>${t('derived', '自动推导')}</strong></div>
      </div>
      <div class="preview-step-grid">
        <div class="preview-step"><span>${t('Latest row remains shadow-only and reproducible', '最新一行保持影子模式且可复现')}</span><strong>${t('safe', '安全')}</strong></div>
        <div class="preview-step"><span>${t('Excess return becomes a Stage 2 label candidate', '超额收益可进入 Stage 2 标签候选')}</span><strong>${t('tagged', '已标注')}</strong></div>
      </div>
    </div>`;
}

async function refreshOutcomes() {
  const summary = _container.querySelector('#outcome-summary');
  setLoading(summary, t('Loading outcome tracking...', '正在加载结果追踪...'));
  try {
    const [outcomePayload, latestReviewResult] = await Promise.all([
      api.outcomes.evaluate({ symbol: _container.querySelector('#outcome-symbol')?.value || 'AAPL' }),
      api.trading.latestReview().catch(() => ({ review: null })),
    ]);
    _latestReview = latestReviewResult?.review || null;
    renderOutcomes(outcomePayload.summary || outcomePayload);
  } catch (err) {
    renderError(summary, err);
  }
}

async function recordOutcome() {
  const summary = _container.querySelector('#outcome-summary');
  setLoading(summary, t('Recording shadow outcome...', '正在记录影子结果...'));
  try {
    const symbol = _container.querySelector('#outcome-symbol')?.value || 'AAPL';
    const decisionId = _container.querySelector('#outcome-decision')?.value || 'demo-decision';
    const realizedReturn = Number(_container.querySelector('#outcome-realized')?.value || 0);
    const benchmarkReturn = Number(_container.querySelector('#outcome-benchmark')?.value || 0);
    const payload = await api.outcomes.evaluate({
      symbol,
      decision_id: decisionId || null,
      realized_return: realizedReturn,
      benchmark_return: benchmarkReturn,
      drawdown: -0.02,
      notes: t('UI demo shadow outcome; not a broker execution.', '界面演示用影子结果，不触发券商执行。'),
    });
    const latestReviewResult = await api.trading.latestReview().catch(() => ({ review: null }));
    _latestReview = latestReviewResult?.review || null;
    const localFallbackRecord = {
      symbol: String(symbol).toUpperCase(),
      decision_id: decisionId,
      realized_return: realizedReturn,
      benchmark_return: benchmarkReturn,
      excess_return: realizedReturn - benchmarkReturn,
      direction_hit: realizedReturn >= benchmarkReturn,
      notes: t('UI demo shadow outcome; not a broker execution.', '界面演示用影子结果，不触发券商执行。'),
    };
    renderOutcomes(
      payload.summary || payload,
      payload.record || payload.latest_record || payload.latest_outcome || localFallbackRecord,
    );
  } catch (err) {
    renderError(summary, err);
  }
}

function renderOutcomes(summary, latest = null) {
  const reviewBlock = _latestReview ? `
    <div class="workbench-section">
      <div class="workbench-section__title">${t('Daily Review Bridge', '每日复盘桥接')}</div>
      <div class="workbench-kv-list compact-kv-list">
        <div class="workbench-kv-row"><span>${t('Review ID', '复盘 ID')}</span><strong>${_latestReview.review_id || '-'}</strong></div>
        <div class="workbench-kv-row"><span>PnL</span><strong>${_latestReview.pnl ?? '-'}</strong></div>
        <div class="workbench-kv-row"><span>${t('Trades', '交易数')}</span><strong>${_latestReview.trades_count ?? 0}</strong></div>
        <div class="workbench-kv-row"><span>${t('Approved vs blocked', '批准 / 阻止')}</span><strong>${_latestReview.approved_decisions ?? 0} / ${_latestReview.blocked_decisions ?? 0}</strong></div>
      </div>
      <div class="workbench-report-text">${_latestReview.report_text || ''}</div>
    </div>
  ` : '';
  _container.querySelector('#outcome-summary').innerHTML = `
    <div class="workbench-metric-grid">
      ${metric(t('Records', '记录数'), summary.record_count ?? 0, 'positive')}
      ${metric(t('Hit rate', '命中率'), summary.hit_rate == null ? '-' : pct(summary.hit_rate))}
      ${metric('Brier', summary.mean_brier == null ? '-' : Number(summary.mean_brier).toFixed(3))}
      ${metric(t('Excess', '超额收益'), summary.mean_excess_return == null ? '-' : pct(summary.mean_excess_return))}
    </div>
    <div class="workbench-kv-list compact-kv-list">
      <div class="workbench-kv-row"><span>${t('Shadow mode', '影子模式')}</span><strong>${summary.shadow_mode ? t('on', '开启') : t('off', '关闭')}</strong></div>
      <div class="workbench-kv-row"><span>${t('Drawdown breaches', '回撤越界次数')}</span><strong>${summary.drawdown_breaches ?? 0}</strong></div>
      <div class="workbench-kv-row"><span>${t('Calibration target', '校准目标')}</span><strong>${t('direction + brier', '方向 + Brier')}</strong></div>
      <div class="workbench-kv-row"><span>${t('Failure mining', '失败案例挖掘')}</span><strong>Stage 2/3 ${t('candidate pool', '候选池')}</strong></div>
    </div>
    <div class="preview-step-grid">
      <div class="preview-step"><span>${t('Calibration curve', '校准曲线')}</span><strong>${summary.record_count >= 10 ? t('forming', '形成中') : t('waiting', '等待中')}</strong></div>
      <div class="preview-step"><span>${t('Regret tracking', '遗憾值跟踪')}</span><strong>${summary.mean_excess_return == null ? t('queued', '排队中') : t('active', '活跃')}</strong></div>
      <div class="preview-step"><span>${t('Failure intake', '失败案例接入')}</span><strong>${(summary.drawdown_breaches ?? 0) > 0 ? t('flagged', '已标记') : t('clean', '干净')}</strong></div>
    </div>
    ${reviewBlock}
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
          <strong>${record.decision_id || record.outcome_id || t('latest outcome', '最新结果')}</strong>
          ${statusBadge(record.direction_hit ? 'promoted' : 'research_only')}
        </div>
        <p>${record.notes || t('Latest outcome row recorded in shadow mode.', '最新结果已在影子模式下记录。')}</p>
        <div class="workbench-item__meta">
          <span>${record.symbol || ''}</span>
          <span>${t('realized', '真实')}=${pct(record.realized_return)}</span>
          <span>${t('benchmark', '基准')}=${pct(record.benchmark_return)}</span>
          <span>${t('excess', '超额')}=${pct(record.excess_return)}</span>
        </div>
      </article>
      <div class="workbench-kv-list compact-kv-list">
        <div class="workbench-kv-row"><span>${t('Direction hit', '方向命中')}</span><strong>${record.direction_hit == null ? t('pending', '待处理') : record.direction_hit ? t('yes', '是') : t('no', '否')}</strong></div>
        <div class="workbench-kv-row"><span>${t('Decision ID', '决策 ID')}</span><strong>${record.decision_id || t('optional', '可选')}</strong></div>
        <div class="workbench-kv-row"><span>${t('Tracking mode', '跟踪模式')}</span><strong>${t('shadow', '影子')}</strong></div>
      </div>
      <div class="preview-step-grid">
        <div class="preview-step"><span>${t('Realized return captured', '真实收益已记录')}</span><strong>${pct(record.realized_return)}</strong></div>
        <div class="preview-step"><span>${t('Benchmark return captured', '基准收益已记录')}</span><strong>${pct(record.benchmark_return)}</strong></div>
        <div class="preview-step"><span>${t('Excess return delta', '超额收益差值')}</span><strong>${pct(record.excess_return)}</strong></div>
      </div>
    </div>` : renderRecordsPreview();
}
