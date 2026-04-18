import { api } from '../qtapi.js?v=8';
import { toast } from '../components/toast.js?v=8';
import { getLang, getLocale, onLangChange } from '../i18n.js?v=8';

let _result     = null;
let _watchlist  = ['AAPL','MSFT','NVDA','TSLA','NEE','AMZN','GOOGL','META'];
let _selected   = 'AAPL';
let _disposeLang = null;

const RESEARCH_TEXT = {
  en: {
    title: 'Research Pipeline',
    subtitle: 'Multi-factor ESG · Quant Signal Intelligence · Alpha Generation',
    watchlist: 'MY WATCHLIST',
    addSymbol: '+ Add',
    searchPlaceholder: 'Search ticker or company…',
    presetLeaders: 'ESG Leaders',
    presetMomentum: 'High Momentum',
    presetSp500: 'SP500 Top',
    configTitle: '▸ SIGNAL RESEARCH CONFIGURATION',
    configSubtitle: 'P1 Alpha · ESG Scoring · Fundamentals · Sentiment',
    universeLabel: 'Universe (auto from watchlist, or override)',
    universePlaceholder: 'AAPL, MSFT… (blank = watchlist)',
    benchmarkLabel: 'Benchmark',
    capitalLabel: 'Capital ($)',
    horizonLabel: 'Horizon (days)',
    strategyLabel: 'Strategy',
    strategyDefault: 'Default',
    strategyLongOnly: 'ESG Long-Only',
    strategyLongShort: 'ESG Long-Short',
    strategyMomentum: 'Momentum',
    strategyValue: 'Value',
    questionLabel: 'Research Question',
    questionPlaceholder: 'e.g. Identify ESG leaders with momentum and strong fundamentals',
    suggest1: 'Identify ESG leaders with momentum...',
    suggest2: 'Find undervalued stocks with positive ESG trend...',
    suggest3: 'Screen for low-volatility dividend growers...',
    run: '▶ Run Research Pipeline',
    running: '● Running…',
    pipelineRunning: 'Pipeline Running',
    stepFetch: 'Fetching market data',
    stepScore: 'Running ESG scoring',
    stepSignals: 'Generating signals',
    stepThesis: 'Writing thesis',
    stepComplete: 'Complete',
    resultKline: 'K-LINE',
    results: 'Results',
    sendToPortfolio: '→ Send to Portfolio',
    emptyTitle: 'Run the pipeline',
    emptyText: 'Configure parameters and click Run to generate alpha signals.',
    thesisTitle: 'THESIS',
    addToPortfolio: 'Add to Portfolio',
    marketContext: 'Market Context',
    momentumLeaders: 'ESG Momentum Leaders',
    esgImproving: 'ESG Score improving',
    newsSentiment: 'News Sentiment',
    addTickerPrompt: 'Add ticker symbol:',
    defaultQuestion: 'Run the default ESG quant research pipeline',
    generatingSignals: 'Generating signals…',
    signalsGenerated: 'Signals Generated',
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
    rowHint: 'Click a row to see full thesis',
    noThesis: 'No detailed thesis available. Run research pipeline with a specific question for detailed analysis.',
    momentumTag: 'Momentum ▲',
    weakMomentumTag: 'Weak Momentum ▼',
    esgScore: 'ESG Score',
    expected: 'Expected',
    long: 'LONG',
    short: 'SHORT',
    neutral: 'NEUTRAL',
    hoursAgo2: '2h ago',
    hoursAgo4: '4h ago',
    hoursAgo6: '6h ago',
    hoursAgo8: '8h ago',
    hoursAgo12: '12h ago',
  },
  zh: {
    title: '研究管线',
    subtitle: '多因子 ESG · 量化信号智能 · Alpha 生成',
    watchlist: '我的自选股',
    addSymbol: '+ 添加',
    searchPlaceholder: '搜索代码或公司…',
    presetLeaders: 'ESG 领跑者',
    presetMomentum: '高动量',
    presetSp500: 'SP500 头部',
    configTitle: '▸ 信号研究配置',
    configSubtitle: 'P1 Alpha · ESG 评分 · 基本面 · 情绪',
    universeLabel: '股票池（默认来自自选股，也可手动覆盖）',
    universePlaceholder: 'AAPL, MSFT…（留空则使用自选股）',
    benchmarkLabel: '基准',
    capitalLabel: '资金规模 ($)',
    horizonLabel: '持有周期（天）',
    strategyLabel: '策略',
    strategyDefault: '默认',
    strategyLongOnly: 'ESG 纯多头',
    strategyLongShort: 'ESG 多空',
    strategyMomentum: '动量',
    strategyValue: '价值',
    questionLabel: '研究问题',
    questionPlaceholder: '例如：识别具备动量和稳健基本面的 ESG 龙头',
    suggest1: '找出同时具备 ESG 优势与动量的标的...',
    suggest2: '寻找 ESG 趋势改善且被低估的股票...',
    suggest3: '筛选低波动且稳定分红的成长标的...',
    run: '▶ 运行研究管线',
    running: '● 运行中…',
    pipelineRunning: '管线运行中',
    stepFetch: '拉取市场数据',
    stepScore: '执行 ESG 评分',
    stepSignals: '生成信号',
    stepThesis: '撰写逻辑',
    stepComplete: '完成',
    resultKline: 'K线',
    results: '结果',
    sendToPortfolio: '→ 发送到组合',
    emptyTitle: '运行研究管线',
    emptyText: '配置参数后点击运行，即可生成 Alpha 信号。',
    thesisTitle: '逻辑',
    addToPortfolio: '加入组合',
    marketContext: '市场环境',
    momentumLeaders: 'ESG 动量领先',
    esgImproving: 'ESG 评分改善中',
    newsSentiment: '新闻情绪',
    addTickerPrompt: '添加股票代码：',
    defaultQuestion: '运行默认的 ESG 量化研究管线',
    generatingSignals: '正在生成信号…',
    signalsGenerated: '条信号已生成',
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
    rowHint: '点击表格行可查看完整逻辑',
    noThesis: '暂无详细逻辑。请带着更具体的问题重新运行研究管线。',
    momentumTag: '动量 ▲',
    weakMomentumTag: '弱动量 ▼',
    esgScore: 'ESG 评分',
    expected: '预期',
    long: '看多',
    short: '看空',
    neutral: '中性',
    hoursAgo2: '2小时前',
    hoursAgo4: '4小时前',
    hoursAgo6: '6小时前',
    hoursAgo8: '8小时前',
    hoursAgo12: '12小时前',
  },
};

function text(key) {
  return RESEARCH_TEXT[getLang()]?.[key] ?? RESEARCH_TEXT.en[key] ?? key;
}

function actionLabel(action) {
  return text(action || 'neutral');
}

export function render(container) {
  _disposeLang?.();
  _disposeLang = onLangChange(() => render(container));
  container.innerHTML = buildShell();
  bindEvents(container);
  renderWatchlist(container);
  restoreResults(container);
}

export function destroy() {
  _disposeLang?.();
  _disposeLang = null;
}

/* ══════════════════════════════════════════════
   SHELL
══════════════════════════════════════════════ */
function buildShell() {
  return `
  <div class="page-header">
    <div>
      <div class="page-header__title">${text('title')}</div>
      <div class="page-header__sub">${text('subtitle')}</div>
    </div>
  </div>

  <div class="grid-3col">
    <!-- LEFT: Watchlist -->
    <div class="watchlist-panel">
      <div class="watchlist-header">
        <span class="chat-panel-title">${text('watchlist')}</span>
        <button class="btn btn-ghost btn-sm" id="btn-add-sym">${text('addSymbol')}</button>
      </div>
      <div class="watchlist-search">
        <input id="wl-search" placeholder="${text('searchPlaceholder')}" autocomplete="off">
      </div>
      <div class="watchlist-list" id="watchlist-items"></div>
      <div class="watchlist-presets">
        ${[
          text('presetLeaders'),
          text('presetMomentum'),
          text('presetSp500'),
        ].map(p =>
          `<button class="preset-btn" data-preset="${p}">${p}</button>`
        ).join('')}
      </div>
    </div>

    <!-- CENTER: Config + Results -->
    <div style="display:flex;flex-direction:column;gap:16px">
      <!-- Config (collapsible) -->
      <div class="run-panel" id="config-panel">
        <div class="run-panel__header" style="cursor:pointer" id="config-toggle">
          <div class="run-panel__title">${text('configTitle')}</div>
          <div class="run-panel__sub">${text('configSubtitle')}</div>
        </div>
        <div id="config-body" class="run-panel__body">
          <div class="form-group">
            <label class="form-label">${text('universeLabel')}</label>
            <input class="form-input" id="r-universe" placeholder="${text('universePlaceholder')}">
          </div>
          <div class="form-row">
            <div class="form-group">
              <label class="form-label">${text('benchmarkLabel')}</label>
              <select class="form-select" id="r-benchmark">
                <option>SPY</option><option>QQQ</option><option>IWM</option>
              </select>
            </div>
            <div class="form-group">
              <label class="form-label">${text('capitalLabel')}</label>
              <input class="form-input" id="r-capital" type="number" value="1000000">
            </div>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label class="form-label">${text('horizonLabel')}</label>
              <input class="form-input" id="r-horizon" type="number" value="20">
            </div>
            <div class="form-group">
              <label class="form-label">${text('strategyLabel')}</label>
              <select class="form-select" id="r-strategy">
                <option value="">${text('strategyDefault')}</option>
                <option value="esg_long_only">${text('strategyLongOnly')}</option>
                <option value="esg_ls">${text('strategyLongShort')}</option>
                <option value="momentum">${text('strategyMomentum')}</option>
                <option value="value">${text('strategyValue')}</option>
              </select>
            </div>
          </div>
          <div class="form-group">
            <label class="form-label">${text('questionLabel')}</label>
            <textarea class="form-textarea" id="r-question" rows="3"
              placeholder="${text('questionPlaceholder')}"></textarea>
          </div>
          <div style="display:flex;flex-wrap:wrap;gap:6px">
            ${[
              text('suggest1'),
              text('suggest2'),
              text('suggest3')
            ].map(q => `<button class="filter-chip" data-q="${q}">${q.substring(0,42)}…</button>`).join('')}
          </div>
        </div>
        <div class="run-panel__foot">
          <button class="btn btn-primary btn-lg" id="btn-run-research" style="flex:1">
            ${text('run')}
          </button>
        </div>
      </div>

      <!-- Run progress (hidden until running) -->
      <div class="card" id="run-progress" style="display:none">
        <div class="card-header"><span class="card-title">${text('pipelineRunning')}</span></div>
        <div class="card-body">
          <div class="run-steps" id="run-steps-list">
            ${[text('stepFetch'), text('stepScore'), text('stepSignals'), text('stepThesis'), text('stepComplete')].map((s,i) =>
              `<div class="run-step" data-step="${i}"><div class="step-dot"></div>${s}</div>`
            ).join('')}
          </div>
        </div>
      </div>

      <!-- Mini K-line for selected result -->
      <div class="kline-wrap" id="result-kline" style="display:none">
        <div class="kline-header">
          <span class="kline-title" id="result-kline-title">${text('resultKline')}: AAPL</span>
          <div class="tf-tabs" id="res-tf-tabs">
            ${['1D','1W','1M'].map(tf =>
              `<div class="tf-tab${tf==='1D'?' active':''}" data-restf="${tf}">${tf}</div>`
            ).join('')}
          </div>
        </div>
        <div class="kline-canvas-wrap">
          <canvas id="result-kline-canvas" height="200"></canvas>
        </div>
      </div>

      <!-- Results -->
      <div class="results-panel research-results-panel" id="results-panel">
        <div class="results-panel__header">
          <span class="card-title" id="results-title">${text('results')}</span>
          <div style="display:flex;gap:8px;align-items:center">
            <span class="text-xs text-muted font-mono" id="results-meta"></span>
            <button class="btn btn-primary btn-sm" id="btn-export-portfolio" style="display:none">
              ${text('sendToPortfolio')}
            </button>
          </div>
        </div>
        <div class="results-panel__body" id="results-body">
          ${buildResearchPreview()}
        </div>
      </div>

      <!-- Expanded thesis panel -->
      <div class="card" id="thesis-panel" style="display:none">
        <div class="card-header">
          <span class="card-title" id="thesis-symbol">${text('thesisTitle')}</span>
          <div style="display:flex;gap:8px">
            <button class="btn btn-ghost btn-sm" id="btn-add-portfolio">${text('addToPortfolio')}</button>
            <button class="btn btn-ghost btn-sm" id="btn-close-thesis">✕</button>
          </div>
        </div>
        <div class="card-body">
          <div id="thesis-content" style="font-family:var(--f-mono);font-size:12px;line-height:1.8;color:var(--text-secondary)"></div>
          <div style="margin-top:14px;display:flex;flex-wrap:wrap;gap:6px" id="thesis-chips"></div>
        </div>
      </div>
    </div>

    <!-- RIGHT: Market context -->
    <div style="display:flex;flex-direction:column;gap:14px">
      <div class="card">
        <div class="card-header"><span class="card-title">${text('marketContext')}</span></div>
        <div class="card-body" style="padding:0">
          ${['SPY','QQQ','VIX','GLD','TLT'].map(sym => `
            <div class="watchlist-item" style="padding:10px 16px">
              <span class="watchlist-item-ticker">${sym}</span>
              <div style="display:flex;flex-direction:column;align-items:flex-end;gap:2px">
                <span style="font-family:var(--f-display);font-size:12px;font-weight:600;color:var(--text-primary)">${mockPrice(sym)}</span>
                <span class="chip-chg ${mockChg(sym) >= 0 ? 'pos' : 'neg'}" style="font-size:10px">
                  ${mockChg(sym) > 0 ? '+' : ''}${mockChg(sym).toFixed(2)}%
                </span>
              </div>
            </div>`).join('')}
        </div>
      </div>

      <div class="card">
        <div class="card-header"><span class="card-title">${text('momentumLeaders')}</span></div>
        <div class="card-body" style="padding:0;display:flex;flex-direction:column">
          ${['TSLA','NEE','MSFT','AAPL','GOOGL'].map(sym => `
            <div class="watchlist-item">
              <div>
                <div class="watchlist-item-ticker">${sym}</div>
                <div class="watchlist-item-name">${text('esgImproving')}</div>
              </div>
              <div style="display:flex;flex-direction:column;align-items:flex-end;gap:4px">
                <span style="font-family:var(--f-display);font-size:11px;font-weight:600;color:var(--green)">ESG +${(Math.random()*8+2).toFixed(1)}</span>
                <span class="badge badge-long" style="font-size:8px">${text('long')}</span>
              </div>
            </div>`).join('')}
        </div>
      </div>

      <div class="card">
        <div class="card-header"><span class="card-title">${text('newsSentiment')}</span></div>
        <div class="card-body" style="padding:0;display:flex;flex-direction:column;gap:0">
          ${mockNews().map(n => `
            <div style="padding:10px 16px;border-bottom:1px solid rgba(255,255,255,0.024)">
              <div style="font-family:var(--f-mono);font-size:11px;color:var(--text-secondary);line-height:1.5;margin-bottom:4px">${n.headline}</div>
              <div style="display:flex;gap:8px;align-items:center">
                <span class="badge badge-${n.sent}" style="font-size:8px">${actionLabel(n.sent)}</span>
                <span style="font-family:var(--f-mono);font-size:9px;color:var(--text-dim)">${n.source} · ${n.time}</span>
              </div>
            </div>`).join('')}
        </div>
      </div>
    </div>
  </div>`;
}

/* ══════════════════════════════════════════════
   WATCHLIST RENDER
══════════════════════════════════════════════ */
function buildResearchPreview() {
  const zh = getLang() === 'zh';
  const steps = zh
    ? ['读取股票池', '生成 ESG/量价/情绪因子', '排序 Alpha 信号', '输出风险与论证']
    : ['Load universe', 'Build ESG / price / sentiment factors', 'Rank alpha signals', 'Write risk notes and thesis'];
  const columns = zh
    ? ['代码', '方向', '置信度', '预期收益', '主要证据']
    : ['Symbol', 'Action', 'Confidence', 'Expected', 'Primary Evidence'];
  const cards = [
    { label: zh ? '当前股票池' : 'Universe', value: _watchlist.slice(0, 5).join(', ') },
    { label: zh ? '研究周期' : 'Horizon', value: '20d' },
    { label: zh ? '基准' : 'Benchmark', value: 'SPY' },
    { label: zh ? '输出模式' : 'Output', value: zh ? '影子研究' : 'shadow research' },
  ];
  return `
    <div class="research-preview">
      <div class="functional-empty__eyebrow">${zh ? '研究预览' : 'Research Preview'}</div>
      <div class="research-preview__head">
        <div>
          <h3>${text('emptyTitle')}</h3>
          <p>${text('emptyText')}</p>
        </div>
      </div>
      <div class="research-preview__metrics">
        ${cards.map(card => `
          <div class="workbench-mini-metric">
            <span>${card.label}</span>
            <strong>${card.value}</strong>
          </div>
        `).join('')}
      </div>
      <div class="research-preview__grid">
        <section>
          <div class="workbench-section__title">${zh ? '管线步骤' : 'Pipeline Steps'}</div>
          <div class="factor-checklist">
            ${steps.map((step, index) => `
              <div class="factor-check-row"><span>${index + 1}. ${step}</span><strong>${zh ? '就绪' : 'ready'}</strong></div>
            `).join('')}
          </div>
        </section>
        <section>
          <div class="workbench-section__title">${zh ? '结果表结构' : 'Result Columns'}</div>
          <div class="research-preview__columns">
            ${columns.map(col => `<span>${col}</span>`).join('')}
          </div>
          <p class="workbench-report-text">${zh ? '运行后这里会显示 Alpha 信号、排序、风险说明和可点击 thesis。' : 'After the run, this area shows alpha signals, ranking, risk notes, and clickable theses.'}</p>
        </section>
      </div>
    </div>`;
}

function renderWatchlist(container) {
  const el = container.querySelector('#watchlist-items');
  el.innerHTML = _watchlist.map(sym => `
    <div class="watchlist-item${sym === _selected ? ' active' : ''}" data-wl="${sym}">
      <div class="watchlist-item-left">
        <div class="watchlist-item-ticker">${sym}</div>
        <div class="watchlist-item-name">${companyName(sym)}</div>
      </div>
      <div class="watchlist-item-right">
        <div style="font-family:var(--f-display);font-size:11px;font-weight:600;color:var(--text-primary)">${mockPrice(sym)}</div>
        <div class="chip-chg ${mockChg(sym) >= 0 ? 'pos' : 'neg'}" style="font-size:10px">
          ${mockChg(sym) > 0 ? '+' : ''}${mockChg(sym).toFixed(2)}%
        </div>
      </div>
    </div>`).join('');
}

/* ══════════════════════════════════════════════
   EVENTS
══════════════════════════════════════════════ */
function bindEvents(container) {
  container.addEventListener('click', async e => {
    /* Config toggle */
    if (e.target.closest('#config-toggle')) {
      const body = container.querySelector('#config-body');
      const foot = container.querySelector('.run-panel__foot');
      const collapsed = body.style.display === 'none';
      body.style.display = collapsed ? '' : 'none';
      if (foot) foot.style.display = collapsed ? '' : 'none';
    }
    /* Run pipeline */
    if (e.target.closest('#btn-run-research')) {
      await runResearch(container);
    }
    /* Watchlist item select */
    const wlItem = e.target.closest('[data-wl]');
    if (wlItem) {
      _selected = wlItem.dataset.wl;
      container.querySelectorAll('[data-wl]').forEach(el => el.classList.remove('active'));
      wlItem.classList.add('active');
      container.querySelector('#r-universe').value = _watchlist.join(', ');
    }
    /* Suggestion chips */
    const qBtn = e.target.closest('[data-q]');
    if (qBtn) {
      container.querySelector('#r-question').value = qBtn.dataset.q;
    }
    /* Timeframe result kline */
    const restf = e.target.closest('[data-restf]');
    if (restf) {
      container.querySelectorAll('[data-restf]').forEach(t => t.classList.remove('active'));
      restf.classList.add('active');
    }
    /* Close thesis */
    if (e.target.closest('#btn-close-thesis')) {
      container.querySelector('#thesis-panel').style.display = 'none';
    }
    /* Export to portfolio */
    if (e.target.closest('#btn-export-portfolio') && _result) {
      const signals = _result.signals || [];
      window.sessionStorage.setItem('qt.portfolio.prefill', JSON.stringify({
        signals: signals.map(s => ({ symbol: s.symbol, action: s.action, weight: 1/signals.length }))
      }));
      window.location.hash = '#/portfolio';
    }
    /* Add sym */
    if (e.target.closest('#btn-add-sym')) {
      const sym = prompt(text('addTickerPrompt'));
      if (sym) {
        const s = sym.toUpperCase().trim();
        if (s && !_watchlist.includes(s)) {
          _watchlist.push(s);
          renderWatchlist(container);
        }
      }
    }
  });

  /* Results table row click → thesis */
  container.querySelector('#results-body').addEventListener('click', e => {
    const tr = e.target.closest('[data-sig-idx]');
    if (tr && _result) {
      const idx = parseInt(tr.dataset.sigIdx);
      const sig = (_result.signals || [])[idx];
      if (sig) showThesis(container, sig);
    }
  });
}

/* ══════════════════════════════════════════════
   RUN RESEARCH
══════════════════════════════════════════════ */
async function runResearch(container) {
  const btn = container.querySelector('#btn-run-research');
  const body = container.querySelector('#results-body');
  const progress = container.querySelector('#run-progress');
  const steps = container.querySelectorAll('.run-step');

  const universeRaw = container.querySelector('#r-universe').value.trim();
  const universe = universeRaw
    ? universeRaw.split(/[,\s]+/).filter(Boolean).map(s => s.toUpperCase())
    : _watchlist;
  const benchmark = container.querySelector('#r-benchmark').value;
  const capital   = Number(container.querySelector('#r-capital').value) || 1000000;
  const horizon   = Number(container.querySelector('#r-horizon').value) || 20;
  const question  = container.querySelector('#r-question').value.trim() ||
                    text('defaultQuestion');

  btn.disabled = true; btn.textContent = text('running');
  progress.style.display = '';
  body.innerHTML = `<div class="loading-overlay"><div class="spinner"></div><span>${text('generatingSignals')}</span></div>`;

  /* Animate steps */
  const stepLabels = [text('stepFetch'), text('stepScore'), text('stepSignals'), text('stepThesis')];
  for (let i = 0; i < stepLabels.length; i++) {
    steps[i]?.classList.add('active');
    await new Promise(r => setTimeout(r, 400));
  }

  try {
    const res = await api.research.run({ universe, benchmark, capital_base: capital, horizon_days: horizon, research_question: question });
    _result = res;
    steps.forEach(s => { s.classList.remove('active'); s.classList.add('done'); });
    steps[4]?.classList.add('done');

    const signals = res.signals || [];
    container.querySelector('#results-title').textContent = formatSignalsGenerated(signals.length);
    container.querySelector('#results-meta').textContent  = res.generated_at ? new Date(res.generated_at).toLocaleString(getLocale()) : '';
    container.querySelector('#btn-export-portfolio').style.display = signals.length ? '' : 'none';

    body.innerHTML = buildSignalTable(signals);

    /* Show mini kline for first result */
    if (signals.length) {
      showResultKline(container, signals[0].symbol);
      updateSignalSummary(container, signals[0]);
    }

    toast.success(text('researchComplete'), formatSignalsGenerated(signals.length));
  } catch (err) {
    body.innerHTML = `<div class="empty-state">
      <div class="empty-state__title">${text('pipelineError')}</div>
      <div class="empty-state__text">${err.message}</div>
    </div>`;
    toast.error(text('researchFailed'), err.message);
  } finally {
    btn.disabled = false; btn.textContent = text('run');
    setTimeout(() => { progress.style.display = 'none'; }, 1500);
  }
}

/* ══════════════════════════════════════════════
   SIGNAL TABLE
══════════════════════════════════════════════ */
function buildSignalTable(signals) {
  if (!signals.length) return `<div class="empty-state"><div class="empty-state__title">${text('noSignals')}</div></div>`;
  const rows = signals.map((s, i) => `
    <tr data-sig-idx="${i}" style="cursor:pointer">
      <td class="cell-symbol">${s.symbol}</td>
      <td class="text-dim" style="max-width:120px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${s.company_name || ''}</td>
      <td><span class="badge badge-${s.action}">${actionLabel(s.action)}</span></td>
      <td class="cell-num ${pctCls(s.confidence)}">${pct(s.confidence)}</td>
      <td class="cell-num ${pctCls(s.expected_return)}">${pct(s.expected_return)}</td>
      <td class="cell-num">${num(s.overall_score)}</td>
      <td class="cell-num">${num(s.e_score)}</td>
      <td class="cell-num">${num(s.g_score)}</td>
      <td class="text-dim text-sm">${(s.sector||'').substring(0,14)}</td>
      <td style="max-width:160px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-family:var(--f-mono);font-size:10px;color:var(--text-dim)">
        ${(s.thesis||'').substring(0,50)}${s.thesis?.length > 50 ? '…' : ''}
      </td>
    </tr>`).join('');
  return `
    <div class="tbl-wrap">
      <table>
        <thead><tr>
          <th>${text('symbol')}</th><th>${text('company')}</th><th>${text('action')}</th>
          <th>${text('conf')}</th><th>${text('expRet')}</th><th>${text('score')}</th><th>E</th><th>G</th><th>${text('sector')}</th><th>${text('thesis')}</th>
        </tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
    <div class="card-footer">
      ${signals.filter(s=>s.action==='long').length} ${text('long')} ·
      ${signals.filter(s=>s.action==='short').length} ${text('short')} ·
      ${signals.filter(s=>s.action==='neutral').length} ${text('neutral')}
      &nbsp;—&nbsp;${text('rowHint')}
    </div>`;
}

/* ══════════════════════════════════════════════
   THESIS PANEL
══════════════════════════════════════════════ */
function showThesis(container, signal) {
  const panel = container.querySelector('#thesis-panel');
  container.querySelector('#thesis-symbol').textContent = `${signal.symbol} · ${actionLabel(signal.action)} ${text('thesisTitle')}`;
  container.querySelector('#thesis-content').innerHTML = signal.thesis
    ? signal.thesis.replace(/\n/g, '<br>')
    : `<span style="color:var(--text-dim)">${text('noThesis')}</span>`;

  const chips = container.querySelector('#thesis-chips');
  const tags = [
    signal.action === 'long' ? text('momentumTag') : text('weakMomentumTag'),
    `${text('esgScore')} ${num(signal.overall_score)}`,
    signal.expected_return > 0 ? `${text('expected')} +${pct(signal.expected_return)}` : `${text('expected')} ${pct(signal.expected_return)}`,
    signal.sector || '',
  ].filter(Boolean);
  chips.innerHTML = tags.map(t => `<span class="context-chip">${t}</span>`).join('');
  panel.style.display = '';
  panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  showResultKline(container, signal.symbol);
}

/* ══════════════════════════════════════════════
   MINI K-LINE FOR RESULTS
══════════════════════════════════════════════ */
function showResultKline(container, symbol) {
  const wrap = container.querySelector('#result-kline');
  const titleEl = container.querySelector('#result-kline-title');
  const canvas = container.querySelector('#result-kline-canvas');
  if (!wrap || !canvas) return;
  wrap.style.display = '';
  if (titleEl) titleEl.textContent = `${text('resultKline')}: ${symbol}`;

  const dpr = window.devicePixelRatio || 1;
  canvas.width  = (canvas.parentElement.offsetWidth || 700) * dpr;
  canvas.height = 200 * dpr;
  canvas.style.height = '200px';
  const ctx = canvas.getContext('2d');
  const W = canvas.width, H = canvas.height;
  const candles = genCandles(symbol, 40);
  const padL = 50 * dpr, padR = 20 * dpr, padT = 14 * dpr, padB = 24 * dpr;
  const cw = ((W - padL - padR) / candles.length) * 0.65;
  const cs = (W - padL - padR) / candles.length;
  const prices = candles.flatMap(c => [c.high, c.low]);
  const minP = Math.min(...prices) * 0.999;
  const maxP = Math.max(...prices) * 1.001;
  const pY = p => padT + (H - padT - padB) - ((p - minP) / (maxP - minP)) * (H - padT - padB);

  ctx.clearRect(0, 0, W, H);
  ctx.fillStyle = '#07070F'; ctx.fillRect(0, 0, W, H);

  candles.forEach((c, i) => {
    const x = padL + i * cs + cs / 2;
    const ox = pY(c.open), cx2 = pY(c.close), hx = pY(c.high), lx = pY(c.low);
    const color = c.close >= c.open ? '#00FF88' : '#FF3D57';
    ctx.strokeStyle = color; ctx.lineWidth = dpr;
    ctx.beginPath(); ctx.moveTo(x, hx); ctx.lineTo(x, lx); ctx.stroke();
    const bodyTop = Math.min(ox, cx2);
    const bodyH   = Math.max(Math.abs(ox - cx2), dpr);
    ctx.fillStyle = c.close >= c.open ? 'transparent' : color;
    ctx.strokeStyle = color; ctx.lineWidth = dpr;
    ctx.fillRect(x - cw/2, bodyTop, cw, bodyH);
    ctx.strokeRect(x - cw/2, bodyTop, cw, bodyH);
  });
}

/* ══════════════════════════════════════════════
   HELPERS
══════════════════════════════════════════════ */
function genCandles(sym, n) {
  let price = 80 + (sym.charCodeAt(0) % 120) + 50;
  return Array.from({ length: n }, () => {
    const vol = 0.012 + Math.random() * 0.018;
    const open = price;
    const close = price * (1 + (Math.random() - 0.48) * vol * 2);
    const high = Math.max(open, close) * (1 + Math.random() * vol * 0.5);
    const low  = Math.min(open, close) * (1 - Math.random() * vol * 0.5);
    price = close;
    return { open, high, low, close };
  });
}

function mockPrice(sym) {
  const seed = sym.split('').reduce((s, c) => s + c.charCodeAt(0), 0);
  return '$' + (50 + (seed % 500) + (seed % 200)).toFixed(2);
}

function mockChg(sym) {
  const seed = sym.charCodeAt(0) * 17 % 100;
  return ((seed - 50) / 25).toFixed(2) * 1;
}

function companyName(sym) {
  const names = { AAPL:'Apple Inc.', MSFT:'Microsoft Corp.', NVDA:'NVIDIA Corp.', TSLA:'Tesla Inc.',
    NEE:'NextEra Energy', AMZN:'Amazon.com', GOOGL:'Alphabet Inc.', META:'Meta Platforms' };
  return names[sym] || sym + ' Corp.';
}

function mockNews() {
  if (getLang() === 'zh') {
    return [
      { headline: '美联储释放二季度维持利率稳定的信号，市场因稳定预期而反弹', sent: 'long', source: 'Reuters', time: text('hoursAgo2') },
      { headline: 'NVDA 财报超预期 12%，并因 AI 需求上调全年指引', sent: 'long', source: 'Bloomberg', time: text('hoursAgo4') },
      { headline: '一季度 ESG 基金净流入创 450 亿美元新高，机构配置需求强劲', sent: 'neutral', source: 'FT', time: text('hoursAgo6') },
      { headline: '原油库存意外上升，能源板块短线承压', sent: 'short', source: 'WSJ', time: text('hoursAgo8') },
      { headline: '科技行业裁员仍在继续，但 AI 招聘抵消了部分就业下滑', sent: 'neutral', source: 'CNBC', time: text('hoursAgo12') },
    ];
  }

  return [
    { headline: 'Fed signals steady rates through Q2, markets rally on stability hopes', sent: 'long', source: 'Reuters', time: text('hoursAgo2') },
    { headline: 'NVDA earnings beat consensus by 12%, raises guidance on AI demand surge', sent: 'long', source: 'Bloomberg', time: text('hoursAgo4') },
    { headline: 'ESG fund flows hit record $45B in Q1, driven by institutional mandates', sent: 'neutral', source: 'FT', time: text('hoursAgo6') },
    { headline: 'Energy sector faces headwinds as oil inventory builds unexpectedly', sent: 'short', source: 'WSJ', time: text('hoursAgo8') },
    { headline: 'Tech layoffs continue, but AI hiring offsets losses in sector employment', sent: 'neutral', source: 'CNBC', time: text('hoursAgo12') },
  ];
}

function updateSignalSummary(container, signal) { /* no-op for research page */ }

function formatSignalsGenerated(count) {
  return getLang() === 'zh' ? `${count} ${text('signalsGenerated')}` : `${count} ${text('signalsGenerated')}`;
}

function restoreResults(container) {
  if (!_result) return;
  const signals = _result.signals || [];
  const meta = container.querySelector('#results-meta');
  container.querySelector('#results-title').textContent = formatSignalsGenerated(signals.length);
  if (meta) meta.textContent = _result.generated_at ? new Date(_result.generated_at).toLocaleString(getLocale()) : '';
  container.querySelector('#btn-export-portfolio').style.display = signals.length ? '' : 'none';
  container.querySelector('#results-body').innerHTML = buildSignalTable(signals);
  if (signals.length) showResultKline(container, signals[0].symbol);
}

const pctCls = v => v > 0 ? 'cell-pos' : v < 0 ? 'cell-neg' : '';
const pct    = v => v == null ? '—' : `${(v * 100).toFixed(1)}%`;
const num    = v => v == null ? '—' : Number(v).toFixed(2);
