import { api } from '../qtapi.js?v=8';
import { toast } from '../components/toast.js?v=8';
import { getLang, getLocale, onLangChange } from '../i18n.js?v=8';

let _result = null;
let _context = null;
let _watchlist = ['AAPL', 'MSFT', 'NVDA', 'TSLA', 'NEE', 'AMZN', 'GOOGL', 'META'];
let _selected = 'AAPL';
let _resultTimeframe = '1D';
let _disposeLang = null;

const COPY = {
  en: {
    title: 'Research Pipeline',
    subtitle: 'Multi-factor ESG / Quant signal intelligence / Alpha generation',
    watchlist: 'MY WATCHLIST',
    addSymbol: '+ Add',
    searchPlaceholder: 'Search ticker or company...',
    presetLeaders: 'ESG Leaders',
    presetMomentum: 'High Momentum',
    presetSp500: 'SP500 Top',
    configTitle: 'SIGNAL RESEARCH CONFIGURATION',
    configSubtitle: 'Research / ranking / evidence / thesis',
    universeLabel: 'Universe (blank = watchlist)',
    universePlaceholder: 'AAPL, MSFT... (blank = watchlist)',
    benchmarkLabel: 'Benchmark',
    capitalLabel: 'Capital ($)',
    horizonLabel: 'Horizon (days)',
    questionLabel: 'Research Question',
    questionPlaceholder: 'What names currently have the strongest ESG + factor support?',
    defaultQuestion: 'Run the default ESG quant research pipeline',
    run: 'Run Research Pipeline',
    running: 'Running...',
    pipelineRunning: 'Pipeline Running',
    stepFetch: 'Fetching research context',
    stepScore: 'Scoring signals',
    stepSignals: 'Ranking candidates',
    stepThesis: 'Writing thesis',
    stepComplete: 'Complete',
    resultKline: 'K-LINE',
    results: 'Results',
    sendToPortfolio: 'Send to Portfolio',
    emptyTitle: 'Run the pipeline',
    emptyText: 'Configure parameters and click Run to generate real alpha signals.',
    thesisTitle: 'THESIS',
    addToPortfolio: 'Add to Portfolio',
    marketContext: 'Market Context',
    momentumLeaders: 'Momentum Leaders',
    newsSentiment: 'Evidence Feed',
    addTickerPrompt: 'Add ticker symbol:',
    generatingSignals: 'Generating signals...',
    researchComplete: 'Research complete',
    pipelineError: 'Pipeline Error',
    researchFailed: 'Research failed',
    noSignals: 'No signals',
    symbol: 'Symbol',
    company: 'Company',
    action: 'Action',
    conf: 'Conf%',
    expRet: 'Exp.Ret',
    score: 'Score',
    sector: 'Sector',
    thesis: 'Thesis',
    rowHint: 'Click a row to see the full thesis',
    noThesis: 'No detailed thesis was returned by the backend.',
    contextLoading: 'Loading research context...',
    contextEmpty: 'No context is available yet.',
    dataSource: 'Source',
    fallback: 'Fallback',
    nextAction: 'Next Action',
    warning: 'Warning',
    noChart: 'No chart payload was returned for this symbol.',
  },
  zh: {
    title: '研究管线',
    subtitle: '多因子 ESG / 量化信号智能 / Alpha 生成',
    watchlist: '我的自选股',
    addSymbol: '+ 添加',
    searchPlaceholder: '搜索代码或公司...',
    presetLeaders: 'ESG 领先',
    presetMomentum: '高动量',
    presetSp500: 'SP500 头部',
    configTitle: '信号研究配置',
    configSubtitle: '研究 / 排名 / 证据 / 逻辑',
    universeLabel: '股票池（留空即使用自选股）',
    universePlaceholder: 'AAPL, MSFT...（留空即使用自选股）',
    benchmarkLabel: '基准',
    capitalLabel: '资金规模 ($)',
    horizonLabel: '周期（天）',
    questionLabel: '研究问题',
    questionPlaceholder: '当前哪些名字同时具备 ESG 与因子支持？',
    defaultQuestion: '运行默认 ESG 量化研究管线',
    run: '运行研究管线',
    running: '运行中…',
    pipelineRunning: '管线运行中',
    stepFetch: '拉取研究上下文',
    stepScore: '评分信号',
    stepSignals: '排序候选',
    stepThesis: '生成逻辑',
    stepComplete: '完成',
    resultKline: 'K 线',
    results: '结果',
    sendToPortfolio: '发送到组合',
    emptyTitle: '运行研究管线',
    emptyText: '配置参数后点击运行，即可生成真实 Alpha 信号。',
    thesisTitle: '逻辑',
    addToPortfolio: '加入组合',
    marketContext: '市场环境',
    momentumLeaders: '动量领先',
    newsSentiment: '证据流',
    addTickerPrompt: '添加股票代码：',
    generatingSignals: '正在生成信号…',
    researchComplete: '研究完成',
    pipelineError: '管线错误',
    researchFailed: '研究失败',
    noSignals: '暂无信号',
    symbol: '代码',
    company: '公司',
    action: '方向',
    conf: '置信度',
    expRet: '预期收益',
    score: '评分',
    sector: '板块',
    thesis: '逻辑',
    rowHint: '点击表格行查看完整逻辑',
    noThesis: '后端没有返回详细逻辑。',
    contextLoading: '正在加载研究上下文…',
    contextEmpty: '暂时没有可用上下文。',
    dataSource: '来源',
    fallback: '回落',
    nextAction: '下一步',
    warning: '警告',
    noChart: '这个标的暂时没有返回图表载荷。',
  },
};

function t(key) {
  const lang = getLang() === 'zh' ? 'zh' : 'en';
  return COPY[lang][key] || COPY.en[key] || key;
}

export function render(container) {
  _disposeLang?.();
  _disposeLang = onLangChange(() => render(container));
  container.innerHTML = buildShell();
  bindEvents(container);
  renderWatchlist(container);
  restoreResults(container);
  loadResearchContext(container, _selected);
}

export function destroy() {
  _disposeLang?.();
  _disposeLang = null;
}

function buildShell() {
  return `
  <div class="page-header">
    <div>
      <div class="page-header__title">${t('title')}</div>
      <div class="page-header__sub">${t('subtitle')}</div>
    </div>
  </div>

  <div class="grid-3col">
    <div class="watchlist-panel">
      <div class="watchlist-header">
        <span class="chat-panel-title">${t('watchlist')}</span>
        <button class="btn btn-ghost btn-sm" id="btn-add-sym">${t('addSymbol')}</button>
      </div>
      <div class="watchlist-search">
        <input id="wl-search" placeholder="${t('searchPlaceholder')}" autocomplete="off">
      </div>
      <div class="watchlist-list" id="watchlist-items"></div>
      <div class="watchlist-presets">
        ${[t('presetLeaders'), t('presetMomentum'), t('presetSp500')].map((preset) => `<button class="preset-btn" data-preset="${preset}">${preset}</button>`).join('')}
      </div>
    </div>

    <div style="display:flex;flex-direction:column;gap:16px">
      <div class="run-panel" id="config-panel">
        <div class="run-panel__header" style="cursor:pointer" id="config-toggle">
          <div class="run-panel__title">${t('configTitle')}</div>
          <div class="run-panel__sub">${t('configSubtitle')}</div>
        </div>
        <div id="config-body" class="run-panel__body">
          <div class="form-group">
            <label class="form-label">${t('universeLabel')}</label>
            <input class="form-input" id="r-universe" placeholder="${t('universePlaceholder')}">
          </div>
          <div class="form-row">
            <div class="form-group">
              <label class="form-label">${t('benchmarkLabel')}</label>
              <select class="form-select" id="r-benchmark">
                <option>SPY</option><option>QQQ</option><option>IWM</option>
              </select>
            </div>
            <div class="form-group">
              <label class="form-label">${t('capitalLabel')}</label>
              <input class="form-input" id="r-capital" type="number" value="1000000">
            </div>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label class="form-label">${t('horizonLabel')}</label>
              <input class="form-input" id="r-horizon" type="number" value="20">
            </div>
            <div class="form-group">
              <label class="form-label">${t('questionLabel')}</label>
              <textarea class="form-textarea" id="r-question" rows="3" placeholder="${t('questionPlaceholder')}"></textarea>
            </div>
          </div>
        </div>
        <div class="run-panel__foot">
          <button class="btn btn-primary btn-lg" id="btn-run-research" style="flex:1">${t('run')}</button>
          <button class="btn btn-ghost btn-lg" id="btn-open-market-radar">Market Radar</button>
          <button class="btn btn-ghost btn-lg" id="btn-open-agent-lab">Agent Lab</button>
        </div>
      </div>

      <div class="card" id="run-progress" style="display:none">
        <div class="card-header"><span class="card-title">${t('pipelineRunning')}</span></div>
        <div class="card-body">
          <div class="run-steps" id="run-steps-list">
            ${[t('stepFetch'), t('stepScore'), t('stepSignals'), t('stepThesis'), t('stepComplete')].map((step, index) => `<div class="run-step" data-step="${index}"><div class="step-dot"></div>${step}</div>`).join('')}
          </div>
        </div>
      </div>

      <div class="kline-wrap" id="result-kline" style="display:none">
        <div class="kline-header">
          <span class="kline-title" id="result-kline-title">${t('resultKline')}: ${_selected}</span>
          <div class="tf-tabs" id="res-tf-tabs">
            ${['1D', '1W', '1M'].map((tf) => `<div class="tf-tab${tf === _resultTimeframe ? ' active' : ''}" data-restf="${tf}">${tf}</div>`).join('')}
          </div>
        </div>
        <div class="kline-canvas-wrap">
          <canvas id="result-kline-canvas" height="200"></canvas>
        </div>
      </div>

      <div class="results-panel research-results-panel" id="results-panel">
        <div class="results-panel__header">
          <span class="card-title" id="results-title">${t('results')}</span>
          <div style="display:flex;gap:8px;align-items:center">
            <span class="text-xs text-muted font-mono" id="results-meta"></span>
            <button class="btn btn-primary btn-sm" id="btn-export-portfolio" style="display:none">${t('sendToPortfolio')}</button>
          </div>
        </div>
        <div class="results-panel__body" id="results-body">
          ${buildResearchPreview()}
        </div>
      </div>

      <div class="card" id="thesis-panel" style="display:none">
        <div class="card-header">
          <span class="card-title" id="thesis-symbol">${t('thesisTitle')}</span>
          <div style="display:flex;gap:8px">
            <button class="btn btn-ghost btn-sm" id="btn-add-portfolio">${t('addToPortfolio')}</button>
            <button class="btn btn-ghost btn-sm" id="btn-close-thesis">✕</button>
          </div>
        </div>
        <div class="card-body">
          <div id="thesis-content" style="font-family:var(--f-mono);font-size:12px;line-height:1.8;color:var(--text-secondary)"></div>
          <div style="margin-top:14px;display:flex;flex-wrap:wrap;gap:6px" id="thesis-chips"></div>
        </div>
      </div>
    </div>

    <div style="display:flex;flex-direction:column;gap:14px">
      <div class="card">
        <div class="card-header"><span class="card-title">${t('marketContext')}</span></div>
        <div class="card-body" style="padding:0" id="research-market-context">
          <div style="padding:14px 16px;color:var(--text-dim);font-size:11px">${t('contextLoading')}</div>
        </div>
      </div>

      <div class="card">
        <div class="card-header"><span class="card-title">${t('momentumLeaders')}</span></div>
        <div class="card-body" style="padding:0;display:flex;flex-direction:column" id="research-momentum-leaders">
          <div style="padding:14px 16px;color:var(--text-dim);font-size:11px">${t('contextLoading')}</div>
        </div>
      </div>

      <div class="card">
        <div class="card-header"><span class="card-title">${t('newsSentiment')}</span></div>
        <div class="card-body" style="padding:0;display:flex;flex-direction:column;gap:0" id="research-feed">
          <div style="padding:14px 16px;color:var(--text-dim);font-size:11px">${t('contextLoading')}</div>
        </div>
      </div>
    </div>
  </div>`;
}

function buildResearchPreview() {
  const zh = getLang() === 'zh';
  const steps = zh
    ? ['读取股票池', '构建 ESG / 行情 / 证据上下文', '排序 Alpha 信号', '输出风险与逻辑']
    : ['Load universe', 'Build ESG / market / evidence context', 'Rank alpha signals', 'Write risk notes and thesis'];
  const columns = zh
    ? ['代码', '方向', '置信度', '预期收益', '主要证据']
    : ['Symbol', 'Action', 'Confidence', 'Expected', 'Primary Evidence'];
  const cards = [
    { label: zh ? '当前股票池' : 'Universe', value: _watchlist.slice(0, 5).join(', ') },
    { label: zh ? '研究周期' : 'Horizon', value: '20d' },
    { label: zh ? '基准' : 'Benchmark', value: 'SPY' },
    { label: zh ? '输出模式' : 'Output', value: zh ? '真实研究' : 'live research' },
  ];
  return `
    <div class="research-preview">
      <div class="functional-empty__eyebrow">${zh ? '研究预览' : 'Research Preview'}</div>
      <div class="research-preview__head">
        <div>
          <h3>${t('emptyTitle')}</h3>
          <p>${t('emptyText')}</p>
        </div>
      </div>
      <div class="research-preview__metrics">
        ${cards.map((card) => `
          <div class="workbench-mini-metric">
            <span>${card.label}</span>
            <strong>${card.value}</strong>
          </div>`).join('')}
      </div>
      <div class="research-preview__grid">
        <section>
          <div class="workbench-section__title">${zh ? '管线步骤' : 'Pipeline Steps'}</div>
          <div class="factor-checklist">
            ${steps.map((step, index) => `<div class="factor-check-row"><span>${index + 1}. ${step}</span><strong>${zh ? '就绪' : 'ready'}</strong></div>`).join('')}
          </div>
        </section>
        <section>
          <div class="workbench-section__title">${zh ? '结果列预览' : 'Result Columns'}</div>
          <div class="research-preview__columns">
            ${columns.map((column) => `<span>${column}</span>`).join('')}
          </div>
          <p class="workbench-report-text">${zh ? '运行后这里会显示真实信号、排序、证据和可点击的 thesis。' : 'After the run, this area shows live signals, ranking, evidence, and clickable theses.'}</p>
        </section>
      </div>
    </div>`;
}

function renderWatchlist(container) {
  const el = container.querySelector('#watchlist-items');
  if (!el) return;
  const quotes = new Map((_context?.quote_strip || []).map((item) => [item.symbol, item]));
  el.innerHTML = _watchlist.map((symbol) => {
    const quote = quotes.get(symbol);
    const price = quote?.price != null ? `$${Number(quote.price).toFixed(2)}` : '—';
    const change = Number(quote?.change_pct || 0);
    const company = quote?.company_name || companyName(symbol);
    return `
      <div class="watchlist-item${symbol === _selected ? ' active' : ''}" data-wl="${symbol}">
        <div class="watchlist-item-left">
          <div class="watchlist-item-ticker">${symbol}</div>
          <div class="watchlist-item-name">${company}</div>
        </div>
        <div class="watchlist-item-right">
          <div style="font-family:var(--f-display);font-size:11px;font-weight:600;color:var(--text-primary)">${price}</div>
          <div class="chip-chg ${change >= 0 ? 'pos' : 'neg'}" style="font-size:10px">${change > 0 ? '+' : ''}${(change * 100).toFixed(2)}%</div>
        </div>
      </div>`;
  }).join('');
}

function bindEvents(container) {
  container.addEventListener('click', async (event) => {
    if (event.target.closest('#config-toggle')) {
      const body = container.querySelector('#config-body');
      const foot = container.querySelector('.run-panel__foot');
      const collapsed = body.style.display === 'none';
      body.style.display = collapsed ? '' : 'none';
      if (foot) foot.style.display = collapsed ? '' : 'none';
    }
    if (event.target.closest('#btn-run-research')) {
      await runResearch(container);
    }
    if (event.target.closest('#btn-open-market-radar')) window.location.hash = '#/market-radar';
    if (event.target.closest('#btn-open-agent-lab')) window.location.hash = '#/agent-lab';

    const watchlistItem = event.target.closest('[data-wl]');
    if (watchlistItem) {
      _selected = watchlistItem.dataset.wl;
      renderWatchlist(container);
      await loadResearchContext(container, _selected);
    }

    const timeframeItem = event.target.closest('[data-restf]');
    if (timeframeItem) {
      _resultTimeframe = timeframeItem.dataset.restf;
      container.querySelectorAll('[data-restf]').forEach((node) => node.classList.toggle('active', node === timeframeItem));
      await showResultKline(container, _selected);
    }

    if (event.target.closest('#btn-close-thesis')) {
      container.querySelector('#thesis-panel').style.display = 'none';
    }

    if (event.target.closest('#btn-export-portfolio') && _result) {
      const signals = _result.signals || [];
      window.sessionStorage.setItem('qt.portfolio.prefill', JSON.stringify({
        signals: signals.map((signal) => ({ symbol: signal.symbol, action: signal.action, weight: 1 / Math.max(signals.length, 1) })),
      }));
      window.location.hash = '#/portfolio';
    }

    if (event.target.closest('#btn-add-sym')) {
      const symbol = prompt(t('addTickerPrompt'));
      if (symbol) {
        const normalized = symbol.toUpperCase().trim();
        if (normalized && !_watchlist.includes(normalized)) {
          _watchlist.push(normalized);
          renderWatchlist(container);
        }
      }
    }
  });

  container.querySelector('#results-body')?.addEventListener('click', (event) => {
    const row = event.target.closest('[data-sig-idx]');
    if (!row || !_result) return;
    const signal = (_result.signals || [])[Number(row.dataset.sigIdx)];
    if (signal) showThesis(container, signal);
  });
}

async function loadResearchContext(container, symbol) {
  try {
    _context = await api.research.context(symbol || _selected, 'auto', 6);
    renderWatchlist(container);
    renderResearchContext(container, _context);
  } catch (error) {
    _context = null;
    renderResearchContext(container, null, error.message || t('contextEmpty'));
  }
}

function renderResearchContext(container, context, errorMessage) {
  const marketEl = container.querySelector('#research-market-context');
  const leadersEl = container.querySelector('#research-momentum-leaders');
  const feedEl = container.querySelector('#research-feed');
  if (!marketEl || !leadersEl || !feedEl) return;

  if (!context) {
    const message = errorMessage || t('contextEmpty');
    marketEl.innerHTML = `<div style="padding:14px 16px;color:var(--text-dim);font-size:11px">${message}</div>`;
    leadersEl.innerHTML = `<div style="padding:14px 16px;color:var(--text-dim);font-size:11px">${message}</div>`;
    feedEl.innerHTML = `<div style="padding:14px 16px;color:var(--text-dim);font-size:11px">${message}</div>`;
    return;
  }

  marketEl.innerHTML = (context.quote_strip || []).slice(0, 5).map((quote) => `
    <div class="watchlist-item" style="padding:10px 16px">
      <div>
        <span class="watchlist-item-ticker">${quote.symbol}</span>
        <div class="watchlist-item-name">${quote.company_name || ''}</div>
      </div>
      <div style="display:flex;flex-direction:column;align-items:flex-end;gap:2px">
        <span style="font-family:var(--f-display);font-size:12px;font-weight:600;color:var(--text-primary)">${quote.price != null ? `$${Number(quote.price).toFixed(2)}` : '—'}</span>
        <span class="chip-chg ${(quote.change_pct || 0) >= 0 ? 'pos' : 'neg'}" style="font-size:10px">${(quote.change_pct || 0) > 0 ? '+' : ''}${((quote.change_pct || 0) * 100).toFixed(2)}%</span>
      </div>
    </div>`).join('') || `<div style="padding:14px 16px;color:var(--text-dim);font-size:11px">${t('contextEmpty')}</div>`;

  leadersEl.innerHTML = (context.momentum_leaders || []).slice(0, 5).map((leader) => `
    <div class="watchlist-item">
      <div>
        <div class="watchlist-item-ticker">${leader.symbol}</div>
        <div class="watchlist-item-name">${leader.company_name || ''}</div>
      </div>
      <div style="display:flex;flex-direction:column;align-items:flex-end;gap:4px">
        <span style="font-family:var(--f-display);font-size:11px;font-weight:600;color:var(--green)">ESG ${num(leader.house_score)}</span>
        <span class="badge badge-long" style="font-size:8px">${pct(leader.expected_return)}</span>
      </div>
    </div>`).join('') || `<div style="padding:14px 16px;color:var(--text-dim);font-size:11px">${t('contextEmpty')}</div>`;

  feedEl.innerHTML = (context.feed || []).map((item) => `
    <div style="padding:10px 16px;border-bottom:1px solid rgba(255,255,255,0.024)">
      <div style="font-family:var(--f-mono);font-size:11px;color:var(--text-secondary);line-height:1.5;margin-bottom:4px">${item.title}</div>
      <div style="font-family:var(--f-mono);font-size:10px;color:var(--text-dim);margin-bottom:6px">${item.summary || ''}</div>
      <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
        <span class="badge badge-${item.sentiment === 'short' ? 'short' : item.sentiment === 'long' ? 'long' : 'neutral'}" style="font-size:8px">${item.item_type}</span>
        <span style="font-family:var(--f-mono);font-size:9px;color:var(--text-dim)">${item.source || item.provider || 'unknown'}</span>
      </div>
    </div>`).join('') || `<div style="padding:14px 16px;color:var(--text-dim);font-size:11px">${t('contextEmpty')}</div>`;
}

async function runResearch(container) {
  const btn = container.querySelector('#btn-run-research');
  const body = container.querySelector('#results-body');
  const progress = container.querySelector('#run-progress');
  const steps = container.querySelectorAll('.run-step');

  const universeRaw = container.querySelector('#r-universe').value.trim();
  const universe = universeRaw ? universeRaw.split(/[,\s]+/).filter(Boolean).map((value) => value.toUpperCase()) : _watchlist;
  const benchmark = container.querySelector('#r-benchmark').value;
  const capital = Number(container.querySelector('#r-capital').value) || 1000000;
  const horizon = Number(container.querySelector('#r-horizon').value) || 20;
  const question = container.querySelector('#r-question').value.trim() || t('defaultQuestion');

  btn.disabled = true;
  btn.textContent = t('running');
  progress.style.display = '';
  body.innerHTML = `<div class="loading-overlay"><div class="spinner"></div><span>${t('generatingSignals')}</span></div>`;

  for (let i = 0; i < 4; i += 1) {
    steps[i]?.classList.add('active');
    await new Promise((resolve) => window.setTimeout(resolve, 220));
  }

  try {
    const result = await api.research.run({
      universe,
      benchmark,
      capital_base: capital,
      horizon_days: horizon,
      research_question: question,
    });
    _result = result;
    steps.forEach((step) => {
      step.classList.remove('active');
      step.classList.add('done');
    });

    const signals = result.signals || [];
    container.querySelector('#results-title').textContent = `${t('results')} / ${signals.length}`;
    container.querySelector('#results-meta').textContent = result.generated_at ? new Date(result.generated_at).toLocaleString(getLocale()) : '';
    container.querySelector('#btn-export-portfolio').style.display = signals.length ? '' : 'none';
    body.innerHTML = buildSignalTable(signals);
    if (signals.length) {
      _selected = signals[0].symbol;
      renderWatchlist(container);
      await showResultKline(container, signals[0].symbol);
      updateSignalSummary(container, signals[0]);
    }
    toast.success(t('researchComplete'), `${signals.length}`);
  } catch (error) {
    body.innerHTML = `<div class="empty-state"><div class="empty-state__title">${t('pipelineError')}</div><div class="empty-state__text">${error.message || t('researchFailed')}</div></div>`;
    toast.error(t('researchFailed'), error.message || t('researchFailed'));
  } finally {
    btn.disabled = false;
    btn.textContent = t('run');
    window.setTimeout(() => { progress.style.display = 'none'; }, 1000);
  }
}

function buildSignalTable(signals) {
  if (!signals.length) return `<div class="empty-state"><div class="empty-state__title">${t('noSignals')}</div></div>`;
  const rows = signals.map((signal, index) => `
    <tr data-sig-idx="${index}" style="cursor:pointer">
      <td class="cell-symbol">${signal.symbol}</td>
      <td class="text-dim" style="max-width:120px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${signal.company_name || ''}</td>
      <td><span class="badge badge-${signal.action}">${signal.action || 'neutral'}</span></td>
      <td class="cell-num ${pctCls(signal.confidence)}">${pct(signal.confidence)}</td>
      <td class="cell-num ${pctCls(signal.expected_return)}">${pct(signal.expected_return)}</td>
      <td class="cell-num">${num(signal.overall_score)}</td>
      <td class="text-dim text-sm">${(signal.sector || '').substring(0, 14)}</td>
      <td style="max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-family:var(--f-mono);font-size:10px;color:var(--text-dim)">${(signal.thesis || '').substring(0, 56)}${(signal.thesis || '').length > 56 ? '…' : ''}</td>
    </tr>`).join('');
  return `
    <div class="tbl-wrap">
      <table>
        <thead><tr>
          <th>${t('symbol')}</th><th>${t('company')}</th><th>${t('action')}</th>
          <th>${t('conf')}</th><th>${t('expRet')}</th><th>${t('score')}</th><th>${t('sector')}</th><th>${t('thesis')}</th>
        </tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
    <div class="card-footer">${t('rowHint')}</div>`;
}

function showThesis(container, signal) {
  const panel = container.querySelector('#thesis-panel');
  container.querySelector('#thesis-symbol').textContent = `${signal.symbol} / ${signal.action || 'neutral'} / ${t('thesisTitle')}`;
  container.querySelector('#thesis-content').innerHTML = signal.thesis
    ? signal.thesis.replace(/\n/g, '<br>')
    : `<span style="color:var(--text-dim)">${t('noThesis')}</span>`;
  container.querySelector('#thesis-chips').innerHTML = [
    `${t('score')} ${num(signal.overall_score)}`,
    `${t('expRet')} ${pct(signal.expected_return)}`,
    signal.sector || '',
  ].filter(Boolean).map((value) => `<span class="context-chip">${value}</span>`).join('');
  panel.style.display = '';
  panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  showResultKline(container, signal.symbol);
}

async function showResultKline(container, symbol) {
  const wrap = container.querySelector('#result-kline');
  const titleEl = container.querySelector('#result-kline-title');
  const canvas = container.querySelector('#result-kline-canvas');
  if (!wrap || !canvas) return;
  wrap.style.display = '';
  if (titleEl) titleEl.textContent = `${t('resultKline')}: ${symbol}`;

  try {
    const payload = await api.platform.dashboardChart(symbol, _resultTimeframe, 'auto');
    drawCandles(canvas, payload.candles || []);
  } catch (_error) {
    drawCandles(canvas, []);
  }
}

function drawCandles(canvas, candles) {
  const dpr = window.devicePixelRatio || 1;
  const width = canvas.parentElement?.offsetWidth || 700;
  const height = 200;
  canvas.width = width * dpr;
  canvas.height = height * dpr;
  canvas.style.height = height + 'px';
  const ctx = canvas.getContext('2d');
  const W = canvas.width;
  const H = canvas.height;
  ctx.clearRect(0, 0, W, H);
  ctx.fillStyle = '#07070F';
  ctx.fillRect(0, 0, W, H);

  if (!candles.length) {
    ctx.fillStyle = 'rgba(190,200,255,0.55)';
    ctx.font = `${12 * dpr}px IBM Plex Mono`;
    ctx.textAlign = 'center';
    ctx.fillText(t('noChart'), W / 2, H / 2);
    return;
  }

  const padL = 50 * dpr;
  const padR = 20 * dpr;
  const padT = 14 * dpr;
  const padB = 24 * dpr;
  const candleSpace = (W - padL - padR) / candles.length;
  const candleWidth = candleSpace * 0.65;
  const prices = candles.flatMap((candle) => [Number(candle.high), Number(candle.low)]);
  const minPrice = Math.min(...prices) * 0.999;
  const maxPrice = Math.max(...prices) * 1.001;
  const yOf = (value) => padT + (H - padT - padB) - ((value - minPrice) / (maxPrice - minPrice || 1)) * (H - padT - padB);

  candles.forEach((candle, index) => {
    const x = padL + index * candleSpace + candleSpace / 2;
    const openY = yOf(Number(candle.open));
    const closeY = yOf(Number(candle.close));
    const highY = yOf(Number(candle.high));
    const lowY = yOf(Number(candle.low));
    const color = Number(candle.close) >= Number(candle.open) ? '#00FF88' : '#FF3D57';
    ctx.strokeStyle = color;
    ctx.lineWidth = dpr;
    ctx.beginPath();
    ctx.moveTo(x, highY);
    ctx.lineTo(x, lowY);
    ctx.stroke();
    const bodyTop = Math.min(openY, closeY);
    const bodyHeight = Math.max(Math.abs(openY - closeY), dpr);
    ctx.fillStyle = Number(candle.close) >= Number(candle.open) ? 'transparent' : color;
    ctx.strokeRect(x - candleWidth / 2, bodyTop, candleWidth, bodyHeight);
    ctx.fillRect(x - candleWidth / 2, bodyTop, candleWidth, bodyHeight);
  });
}

function updateSignalSummary(_container, _signal) {}

function restoreResults(container) {
  if (!_result) return;
  const signals = _result.signals || [];
  container.querySelector('#results-title').textContent = `${t('results')} / ${signals.length}`;
  container.querySelector('#results-meta').textContent = _result.generated_at ? new Date(_result.generated_at).toLocaleString(getLocale()) : '';
  container.querySelector('#btn-export-portfolio').style.display = signals.length ? '' : 'none';
  container.querySelector('#results-body').innerHTML = buildSignalTable(signals);
  if (signals.length) showResultKline(container, signals[0].symbol);
}

function companyName(symbol) {
  const map = {
    AAPL: 'Apple Inc.',
    MSFT: 'Microsoft Corp.',
    NVDA: 'NVIDIA Corp.',
    TSLA: 'Tesla Inc.',
    NEE: 'NextEra Energy',
    AMZN: 'Amazon.com',
    GOOGL: 'Alphabet Inc.',
    META: 'Meta Platforms',
  };
  return map[symbol] || `${symbol} Corp.`;
}

function pct(value) {
  if (value == null || Number.isNaN(Number(value))) return '—';
  return `${Number(value * 100).toFixed(1)}%`;
}

function pctCls(value) {
  return Number(value) > 0 ? 'cell-pos' : Number(value) < 0 ? 'cell-neg' : '';
}

function num(value) {
  if (value == null || Number.isNaN(Number(value))) return '—';
  return Number(value).toFixed(2);
}
