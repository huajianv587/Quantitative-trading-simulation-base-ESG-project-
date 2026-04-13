import { api } from '../qtapi.js?v=8';
import { computeAllIndicators, buildIndicatorsPanel, showIndicatorModal, IND_META } from '../modules/indicators.js?v=8';
import { getLang, getLocale, onLangChange, translateLoose } from '../i18n.js?v=8';

/* ── Module state ── */
let _klineState   = null;
let _heatState    = null;
let _activeSymbol = 'NVDA';
let _activeTF     = '1D';
let _activeInds   = new Set();
let _data         = {};
let _animFrame    = null;
let _clockTimer   = null;
let _disposeLang  = null;

const DASHBOARD_TEXT = {
  en: {
    title: 'Platform Dashboard',
    runResearch: 'Run Research Pipeline',
    executePlan: 'Execute Plan ›',
    marketOpen: '● MARKET OPEN',
    marketClosed: '○ MARKET CLOSED',
    klineTitle: 'WATCHLIST · K-LINE ANALYSIS',
    signalSummary: 'SIGNAL SUMMARY',
    confidence: 'Confidence',
    expectedReturn: 'Exp. Return',
    esgScore: 'ESG Score',
    momentum5d: '5D Momentum',
    riskLabel: 'Risk',
    indicators: 'TECHNICAL INDICATORS',
    indicatorsHint: '19 indicators · click to explore',
    aiAnalysis: '🤖 AI ANALYSIS',
    aiPlaceholder: 'Select a symbol and run research to see AI-generated market analysis.',
    fullResearch: 'Full Research →',
    heatmapTitle: 'MARKET HEATMAP · SECTORS',
    systemStatus: 'System Status · Architecture Layers',
    loadingRuntime: 'Loading runtime data…',
    topSignals: 'Top Signals · AI Generated',
    live: 'LIVE',
    viewFullResearch: 'View Full Research',
    positionsTitle: 'Live Positions · Alpaca Paper',
    refresh: 'Refresh',
    portfolioNav: 'PORTFOLIO NAV',
    capitalBase: 'Capital Base',
    expectedAlpha: 'EXPECTED ALPHA',
    vsBenchmark: 'vs Benchmark',
    activeSignals: 'ACTIVE SIGNALS',
    backtestSharpe: 'BACKTEST SHARPE',
    regime: 'REGIME',
    symbols: 'symbols',
    riskOn: 'RISK-ON',
    riskOff: 'RISK-OFF',
    neutral: 'NEUTRAL',
    livePerformance: 'Live Performance · Session Metrics',
    multiFactor: 'ESG MULTI-FACTOR',
    now: 'NOW',
    aiProjection: 'AI PROJ · 20D',
    noSignalsTitle: 'No signals yet',
    noSignalsText: 'Run the research pipeline to generate alpha signals.',
    signalsSymbol: 'Symbol',
    signalsAction: 'Action',
    signalsConf: 'Conf',
    signalsExpRet: 'Exp.Ret',
    signalsScore: 'Score',
    signalsSector: 'Sector',
    signalsCompany: 'Company',
    signalsTone: 'Tone',
    signalsEvent: 'Event',
    signalsType: 'Type',
    signalsDate: 'Date',
    layerReady: 'ready',
    noLayerData: 'No layer data',
    runtimePlatform: 'Platform',
    runtimeBenchmark: 'Benchmark',
    runtimeUniverse: 'Universe Size',
    runtimeAnnual: 'Annual Return',
    runtimeHitRate: 'Hit Rate',
    runtimeStorage: 'Storage Mode',
    updated: 'Updated',
    noPositionsTitle: 'No open positions',
    noPositionsText: 'Submit an execution plan to open positions.',
    positionsUnavailable: 'Positions unavailable',
    posQty: 'Qty',
    posSide: 'Side',
    posAvgCost: 'Avg Cost',
    posCurrent: 'Current',
    posMarketValue: 'Mkt Value',
    posUnrealized: 'Unrealized P&L',
    posPctChange: '% Chg',
    tooltipChange: 'Chg',
    tooltipMktCap: 'Mkt Cap',
    tooltipWeight: 'Weight',
  },
  zh: {
    title: '平台控制台',
    runResearch: '运行研究管线',
    executePlan: '执行计划 ›',
    marketOpen: '● 市场开盘',
    marketClosed: '○ 市场休市',
    klineTitle: '自选股 · K线分析',
    signalSummary: '信号摘要',
    confidence: '置信度',
    expectedReturn: '预期收益',
    esgScore: 'ESG 评分',
    momentum5d: '5日动量',
    riskLabel: '风险',
    indicators: '技术指标',
    indicatorsHint: '19 个指标 · 点击查看',
    aiAnalysis: '🤖 AI 分析',
    aiPlaceholder: '选择一个标的并运行研究，即可查看 AI 生成的市场分析。',
    fullResearch: '完整研究 →',
    heatmapTitle: '市场热力图 · 板块',
    systemStatus: '系统状态 · 架构层',
    loadingRuntime: '加载运行时数据…',
    topSignals: '顶部信号 · AI 生成',
    live: '实时',
    viewFullResearch: '查看完整研究',
    positionsTitle: '实时持仓 · Alpaca 模拟盘',
    refresh: '刷新',
    portfolioNav: '组合净值',
    capitalBase: '本金规模',
    expectedAlpha: '预期 Alpha',
    vsBenchmark: '相对基准',
    activeSignals: '活跃信号',
    backtestSharpe: '回测夏普',
    regime: '市场状态',
    symbols: '只标的',
    riskOn: '风险偏好',
    riskOff: '风险规避',
    neutral: '中性',
    livePerformance: '实时表现 · 会话指标',
    multiFactor: 'ESG 多因子',
    now: '当前',
    aiProjection: 'AI 预测 · 20日',
    noSignalsTitle: '暂无信号',
    noSignalsText: '运行研究管线后将在这里生成 Alpha 信号。',
    signalsSymbol: '代码',
    signalsAction: '方向',
    signalsConf: '置信度',
    signalsExpRet: '预期收益',
    signalsScore: '评分',
    signalsSector: '板块',
    signalsCompany: '公司',
    signalsTone: '情绪',
    signalsEvent: '事件',
    signalsType: '类型',
    signalsDate: '日期',
    layerReady: '已就绪',
    noLayerData: '暂无架构层数据',
    runtimePlatform: '平台',
    runtimeBenchmark: '基准',
    runtimeUniverse: '股票池规模',
    runtimeAnnual: '年化收益',
    runtimeHitRate: '命中率',
    runtimeStorage: '存储模式',
    updated: '更新时间',
    noPositionsTitle: '暂无持仓',
    noPositionsText: '提交执行计划后，持仓会显示在这里。',
    positionsUnavailable: '持仓暂不可用',
    posQty: '数量',
    posSide: '方向',
    posAvgCost: '持仓成本',
    posCurrent: '当前价格',
    posMarketValue: '市值',
    posUnrealized: '未实现盈亏',
    posPctChange: '涨跌幅',
    tooltipChange: '涨跌',
    tooltipMktCap: '市值',
    tooltipWeight: '权重',
  },
};

const ACTION_LABELS = {
  en: { long: 'LONG', short: 'SHORT', neutral: 'NEUTRAL', positive: 'POSITIVE', alert: 'ALERT' },
  zh: { long: '看多', short: '看空', neutral: '中性', positive: '正向', alert: '预警' },
};

const ARCH_TRANSLATIONS = {
  'Data Ingestion': { zh: '数据接入' },
  'Data Governance': { zh: '数据治理' },
  'Alpha Engine': { zh: 'Alpha 引擎' },
  'Model Training': { zh: '模型训练' },
  'Agent Layer': { zh: '智能体层' },
  'Risk & Compliance': { zh: '风险与合规' },
  'Execution': { zh: '执行层' },
  'Experiment Track': { zh: '实验追踪' },
  'Reports & UI': { zh: '报告与界面' },
  'Market · ESG · Macro · Alt data': { zh: '市场 · ESG · 宏观 · 另类数据' },
  'Alignment · Filtering · Metadata': { zh: '对齐 · 过滤 · 元数据' },
  'XGBoost · LSTM · ESG factors': { zh: 'XGBoost · LSTM · ESG 因子' },
  'XGBoost / LoRA fine-tuning': { zh: 'XGBoost / LoRA 微调' },
  'Research · Risk · Report agents': { zh: '研究 · 风控 · 报告智能体' },
  'CVaR · Drawdown · Stress tests': { zh: 'CVaR · 回撤 · 压力测试' },
  'Backtesting · Paper trading': { zh: '回测 · 模拟交易' },
  'MLflow · Artifact storage': { zh: 'MLflow · 制品存储' },
  'Console · Delivery site': { zh: '控制台 · 交付站点' },
};

const SECTOR_LABELS = {
  Technology: '科技',
  Healthcare: '医疗保健',
  Financials: '金融',
  'Consumer Disc': '可选消费',
  Industrials: '工业',
  'Comm. Svcs': '通信服务',
  Energy: '能源',
  Materials: '材料',
  Utilities: '公用事业',
  'Real Estate': '房地产',
  'Cons. Staples': '必需消费',
};

function copy(key) {
  return DASHBOARD_TEXT[getLang()]?.[key] ?? DASHBOARD_TEXT.en[key] ?? key;
}

const isLight = () => document.body.classList.contains('light');
const BG = () => isLight() ? '#FAFBFF' : '#07070F';
const GRID_CLR = () => isLight() ? 'rgba(0,0,0,0.04)' : 'rgba(255,255,255,0.04)';
const TEXT_DIM_CLR = () => isLight() ? 'rgba(30,50,100,0.40)' : 'rgba(140,160,220,0.45)';

function actionLabel(action) {
  return ACTION_LABELS[getLang()]?.[action] ?? ACTION_LABELS.en[action] ?? String(action || '').toUpperCase();
}

function localizeText(value) {
  if (getLang() !== 'zh' || !value) return value;
  return ARCH_TRANSLATIONS[value]?.zh || value;
}

function localizeSector(name) {
  if (getLang() !== 'zh' || !name) return name;
  return SECTOR_LABELS[name] || name;
}

export async function render(container) {
  if (_clockTimer) clearInterval(_clockTimer);
  if (_animFrame) cancelAnimationFrame(_animFrame);
  _klineState = null;
  _heatState = null;
  _disposeLang?.();
  _disposeLang = onLangChange(() => render(container));
  container.innerHTML = buildShell();
  bindEvents(container);

  // Load platform data (with fallback mock)
  try {
    _data = await api.platform.overview();
  } catch (err) {
    console.warn('Dashboard API error, using mock data:', err.message);
    _data = MOCK_OVERVIEW();
  }
  populateKPIs(container, _data);
  populateSignalsTable(container, _data);
  populatePerformancePanel(container, _data);
  populatePositions(container, _data);

  // Load real K-line data
  initKlineChart(container);
  initHeatmap(container);
}

export function destroy() {
  if (_animFrame) cancelAnimationFrame(_animFrame);
  if (_clockTimer) clearInterval(_clockTimer);
  _disposeLang?.();
  _disposeLang = null;
  _clockTimer = null;
  _klineState = null; _heatState = null;
}

/* ══════════════════════════════════════════════
   SHELL
══════════════════════════════════════════════ */
function buildShell() {
  const now = new Date();
  const hour = now.getHours();
  const isOpen = hour >= 9 && hour < 16;
  const marketBadge = isOpen
    ? `<span style="color:var(--green)">${copy('marketOpen')}</span>`
    : `<span style="color:var(--text-dim)">${copy('marketClosed')}</span>`;

  return `
  <div class="page-header">
    <div>
      <div class="page-header__title">${copy('title')}</div>
      <div class="page-header__sub" style="display:flex;gap:16px;align-items:center">
        <span id="dash-clock" style="font-family:var(--f-mono);font-size:11px"></span>
        <span style="font-family:var(--f-mono);font-size:11px">${marketBadge}</span>
      </div>
    </div>
    <div class="page-header__actions">
      <a href="#/research" class="btn btn-ghost btn-sm">${copy('runResearch')}</a>
      <a href="#/execution" class="btn btn-primary btn-sm">${copy('executePlan')}</a>
    </div>
  </div>

  <!-- ROW 1: KPI cards -->
  <div class="metrics-row-5" id="kpi-row">
    ${kpiSkeleton(5)}
  </div>

  <!-- ROW 2: K-line chart -->
  <div class="kline-wrap" id="kline-section">
    <div class="kline-header">
      <span class="kline-title">${copy('klineTitle')}</span>
      <div class="kline-controls">
        <div class="tf-tabs" id="tf-tabs">
          ${['1D','1W','1M','3M','1Y'].map(tf =>
            `<div class="tf-tab${tf===_activeTF?' active':''}" data-tf="${tf}">${tf}</div>`
          ).join('')}
        </div>
        <div style="display:flex;gap:4px;margin-left:8px" id="ind-btns">
          ${['MA20','MA60','BOLL','VOL'].map(i =>
            `<button class="ind-btn" data-ind="${i}">${i}</button>`
          ).join('')}
        </div>
      </div>
    </div>
    <!-- Symbol chips -->
    <div class="symbol-chips-row" id="symbol-chips">
      ${['NVDA','TSLA','AAPL','MSFT','NEE','AMZN','GOOGL','META'].map(s =>
        `<div class="symbol-chip${s===_activeSymbol?' active':''}" data-sym="${s}">
          <span class="chip-ticker">${s}</span>
          <span class="chip-chg" id="chg-${s}">—</span>
        </div>`
      ).join('')}
    </div>
    <!-- Main K-line canvas -->
    <div class="kline-canvas-wrap">
      <canvas id="kline-canvas" height="340"></canvas>
    </div>
    <!-- Footer: 3-panel analysis -->
    <div class="kline-footer">
      <!-- Signal summary -->
      <div class="kline-panel">
        <div class="kline-panel-title"><span class="live-dot"></span>${copy('signalSummary')}</div>
        <div id="signal-summary">
          <div class="sig-v2-wrap">
            <div class="sig-v2-hero">
              <div class="signal-badge-large neutral" id="signal-badge">${copy('neutral')}</div>
              <div class="sig-v2-sym" id="sig-v2-sym">—</div>
            </div>
            <div class="sig-v2-grid">
              <div class="sig-v2-cell">
                <div class="sig-v2-lbl">${copy('confidence')}</div>
                <div class="sig-v2-val" id="signal-conf" style="color:var(--amber)">—</div>
              </div>
              <div class="sig-v2-cell">
                <div class="sig-v2-lbl">${copy('expectedReturn')}</div>
                <div class="sig-v2-val" id="signal-ret" style="color:var(--green)">—</div>
              </div>
              <div class="sig-v2-cell">
                <div class="sig-v2-lbl">${copy('esgScore')}</div>
                <div class="sig-v2-val" id="sig-v2-esg" style="color:var(--cyan)">—</div>
              </div>
              <div class="sig-v2-cell">
                <div class="sig-v2-lbl">${copy('momentum5d')}</div>
                <div class="sig-v2-val" id="sig-v2-mom">—</div>
              </div>
            </div>
            <div class="sig-v2-gauge-row">
              <span class="sig-v2-gl">${copy('riskLabel')}</span>
              <div class="sig-v2-track">
                <div class="sig-v2-fill" id="sig-v2-gauge" style="width:50%"></div>
              </div>
              <span class="sig-v2-gval" id="sig-v2-gval">—</span>
            </div>
            <div class="sig-v2-tags">
              <span class="sig-v2-tag" id="sig-v2-sector">—</span>
              <span class="sig-v2-tag sig-v2-tag--regime" id="sig-v2-regime">—</span>
            </div>
          </div>
        </div>
      </div>
      <!-- Technical indicators -->
      <div class="kline-panel kline-panel--ind">
        <div class="kline-panel-title" style="display:flex;justify-content:space-between;align-items:center">
          <span>${copy('indicators')}</span>
          <span style="font-size:9px;color:var(--text-dim);font-family:var(--f-mono)">${copy('indicatorsHint')}</span>
        </div>
        <div id="tech-indicators" style="overflow-y:auto;max-height:320px">
          ${buildTechIndicators()}
        </div>
      </div>
      <!-- AI analysis -->
      <div class="kline-panel">
        <div class="kline-panel-title" style="color:var(--purple)">${copy('aiAnalysis')}</div>
        <div id="ai-analysis" style="font-family:var(--f-mono);font-size:11px;line-height:1.8;color:var(--text-secondary)">
          ${copy('aiPlaceholder')}
        </div>
        <div style="margin-top:12px">
          <a href="#/research" class="btn btn-ghost btn-sm" style="width:100%;justify-content:center">${copy('fullResearch')}</a>
        </div>
      </div>
    </div>
  </div>

  <!-- ROW 3: Market heatmap -->
  <div class="heatmap-wrap" id="heatmap-section">
    <div class="heatmap-header">
      <span class="kline-title">${copy('heatmapTitle')}</span>
      <div class="tf-tabs" id="heat-tf-tabs">
        ${['1D','1W','1M'].map(tf =>
          `<div class="tf-tab${tf==='1D'?' active':''}" data-htf="${tf}">${tf}</div>`
        ).join('')}
      </div>
    </div>
    <div class="heatmap-canvas-container" style="padding:8px">
      <canvas id="heatmap-canvas" height="180"></canvas>
      <div class="heatmap-tooltip" id="heat-tooltip"></div>
    </div>
  </div>

  <!-- ROW 4: Performance panel + Top signals -->
  <div class="grid-sidebar-wide" style="margin-bottom:16px">
    <div class="card">
      <div class="card-header">
        <span class="card-title">${copy('livePerformance')}</span>
        <div style="display:flex;align-items:center;gap:8px">
          <div class="live-dot"></div>
          <span style="font-size:10px;font-family:var(--f-mono);color:var(--green)">${copy('multiFactor')}</span>
        </div>
      </div>
      <div id="sparkline-wrap" style="background:#07070F">
        <canvas id="equity-sparkline" height="90" style="width:100%;display:block"></canvas>
      </div>
      <div style="padding:12px 16px;border-top:1px solid var(--border-subtle)">
        <div id="perf-metrics-grid" style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px 20px">
          <div class="text-muted text-sm">Loading…</div>
        </div>
      </div>
    </div>
    <div class="card">
      <div class="card-header">
        <span class="card-title" style="display:flex;align-items:center;gap:8px">
          ${copy('topSignals')}
          <span class="live-pill" style="font-size:8px;padding:2px 8px">${copy('live')}</span>
        </span>
        <a href="#/research" class="btn btn-ghost btn-sm">${copy('viewFullResearch')}</a>
      </div>
      <div id="signals-body">
        <div class="loading-overlay" style="min-height:120px"><div class="spinner"></div></div>
      </div>
    </div>
  </div>

  <!-- ROW 5: Positions table -->
  <div class="card" id="positions-section">
    <div class="card-header">
      <span class="card-title">${copy('positionsTitle')}</span>
      <div style="display:flex;gap:8px;align-items:center">
        <span class="text-xs text-muted font-mono" id="pos-timestamp"></span>
        <button class="btn btn-ghost btn-sm" id="btn-refresh-pos">${copy('refresh')}</button>
      </div>
    </div>
    <div id="positions-body">
      <div class="loading-overlay" style="min-height:80px"><div class="spinner"></div></div>
    </div>
  </div>`;
}

/* ══════════════════════════════════════════════
   KPI POPULATION
══════════════════════════════════════════════ */
function kpiSkeleton(n) {
  return Array(n).fill(0).map(() => `
    <div class="metric-card">
      <div class="metric-sheen"></div>
      <div class="metric-label skeleton" style="height:10px;width:80px;margin-bottom:12px"></div>
      <div class="metric-value skeleton" style="height:28px;width:100px"></div>
      <div class="metric-sub skeleton" style="height:10px;width:60px;margin-top:8px"></div>
    </div>`).join('');
}

/* ── Mock overview fallback (matches backend /api/v1/quant/platform/overview schema) ── */
function MOCK_OVERVIEW() {
  return {
    platform_name: 'ESG Quant Intelligence System',
    top_signals: [
      { symbol:'NVDA', action:'long',  confidence:0.87, expected_return:0.082, overall_score:0.91, sector:'Technology',     regime_label:'risk_on',  predicted_return_5d:0.042 },
      { symbol:'MSFT', action:'long',  confidence:0.81, expected_return:0.061, overall_score:0.84, sector:'Technology',     regime_label:'risk_on',  predicted_return_5d:0.031 },
      { symbol:'NEE',  action:'long',  confidence:0.74, expected_return:0.044, overall_score:0.79, sector:'Utilities',      regime_label:'neutral',  predicted_return_5d:0.022 },
      { symbol:'AAPL', action:'long',  confidence:0.72, expected_return:0.038, overall_score:0.76, sector:'Technology',     regime_label:'risk_on',  predicted_return_5d:0.019 },
      { symbol:'F',    action:'short', confidence:0.61, expected_return:-0.031,overall_score:0.42, sector:'Consumer Disc',  regime_label:'risk_off', predicted_return_5d:-0.016 },
    ],
    portfolio_preview: {
      capital_base: 1000000,
      expected_alpha: 0.084,
      benchmark: 'SPY',
    },
    latest_backtest: {
      strategy_name: 'ESG Multi-Factor',
      metrics: { sharpe: 1.84, max_drawdown: -0.092, annualized_return: 0.214, hit_rate: 0.581 },
    },
    architecture_layers: [
      { key:'l0', label:'Data Ingestion',  priority:'P1', ready:true,  detail:'Market · ESG · Macro · Alt data' },
      { key:'l1', label:'Data Governance', priority:'P1', ready:true,  detail:'Alignment · Filtering · Metadata' },
      { key:'l2', label:'Alpha Engine',    priority:'P1', ready:true,  detail:'XGBoost · LSTM · ESG factors' },
      { key:'l3', label:'Model Training',  priority:'P2', ready:true,  detail:'XGBoost / LoRA fine-tuning' },
      { key:'l4', label:'Agent Layer',     priority:'P1', ready:true,  detail:'Research · Risk · Report agents' },
      { key:'l5', label:'Risk & Compliance',priority:'P2',ready:true,  detail:'CVaR · Drawdown · Stress tests' },
      { key:'l6', label:'Execution',       priority:'P1', ready:true,  detail:'Backtesting · Paper trading' },
      { key:'l7', label:'Experiment Track',priority:'P2', ready:false, detail:'MLflow · Artifact storage' },
      { key:'l8', label:'Reports & UI',    priority:'P1', ready:true,  detail:'Console · Delivery site' },
    ],
    universe: { name:'ESG S&P500', size:124, benchmark:'SPY', coverage:['NVDA','MSFT','AAPL','GOOGL','AMZN'] },
    storage: { mode:'local_fallback' },
    p1_signal_snapshot: { regime_counts:{ risk_on:3, neutral:1, risk_off:1 }, average_predicted_return_5d:0.019 },
    p2_decision_snapshot: { selected_strategy:'balanced_quality_growth', average_decision_score:0.72 },
  };
}

function populateKPIs(container, data) {
  // Support both backend schemas:
  // Schema A (quant service): portfolio_preview, latest_backtest, top_signals
  // Schema B (core fallback): metrics[] array
  let cards;

  if (Array.isArray(data.metrics) && data.metrics.length) {
    // Schema B — core.py fallback
    cards = data.metrics.slice(0, 5).map(m => ({
      label: getLang() === 'zh' ? (m.label || '') : (m.label || '').toUpperCase(),
      value: String(m.value) + (m.suffix || ''),
      cls: '',
      sub: m.hint || '',
    }));
    // Pad to 5
    while (cards.length < 5) cards.push({ label:'—', value:'—', cls:'', sub:'' });
  } else {
    // Schema A — quant service (or mock)
    const portfolio = data.portfolio_preview || data.portfolio || {};
    const backtest  = data.latest_backtest   || {};
    const bMetrics  = backtest.metrics || {};
    const signals   = data.top_signals || [];
    const longs     = signals.filter(s => s.action === 'long').length;
    const shorts    = signals.filter(s => s.action === 'short').length;
    const capital   = portfolio.capital_base || data.capital_base || 1000000;
    const expAlpha  = portfolio.expected_alpha;
    const sharpe    = bMetrics.sharpe;
    const p1snap    = data.p1_signal_snapshot || {};
    const regime    = p1snap.regime_counts || {};

    cards = [
      { label:copy('portfolioNav'),   value:'$' + Number(capital).toLocaleString(), cls:'',   sub:copy('capitalBase') },
      { label:copy('expectedAlpha'),  value:fmtPct(expAlpha), cls:pctCls(expAlpha), sub:copy('vsBenchmark') },
      { label:'ACTIVE SIGNALS',  value:String(signals.length), cls:'pos',       sub:`${longs}L · ${shorts}S` },
      { label:copy('backtestSharpe'), value:fmtNum(sharpe), cls:sharpe>=1?'pos':'', sub:`MaxDD ${fmtPct(bMetrics.max_drawdown)}` },
      { label:copy('regime'),          value:regime.risk_on>0?copy('riskOn'):copy('neutral'), cls:regime.risk_on>0?'pos':'', sub:`${data.universe?.size||0} ${copy('symbols')}` },
    ];
    cards[2].label = copy('activeSignals');
  }

  container.querySelector('#kpi-row').innerHTML = cards.map(c => `
    <div class="metric-card">
      <div class="metric-sheen"></div>
      <div class="metric-label">${c.label}</div>
      <div class="metric-value ${c.cls}">${c.value}</div>
      <div class="metric-sub">${c.sub}</div>
    </div>`).join('');
}

/* Fix signals table to support both schemas */
function _getSignals(data) {
  // Schema A: top_signals with symbol/action/confidence
  if (data.top_signals?.length) return { type: 'quant', items: data.top_signals };
  // Schema B: signals with company/title/tone
  if (data.signals?.length) return { type: 'esg', items: data.signals };
  return { type: 'empty', items: [] };
}

/* ══════════════════════════════════════════════
   SIGNALS TABLE
══════════════════════════════════════════════ */
function populateSignalsTable(container, data) {
  const el = container.querySelector('#signals-body');
  const { type, items } = _getSignals(data);

  if (!items.length) {
    el.innerHTML = `<div class="empty-state" style="min-height:120px">
      <div class="empty-state__icon">📡</div>
      <div class="empty-state__title">${copy('noSignalsTitle')}</div>
      <div class="empty-state__text">${copy('noSignalsText')}</div>
    </div>`;
    return;
  }

  if (type === 'quant') {
    const signals = items.slice(0, 8);
    const rows = signals.map(s => `
      <tr>
        <td class="cell-symbol">${s.symbol}</td>
        <td><span class="badge badge-${s.action==='long'?'filled':s.action==='short'?'failed':'neutral'}">${actionLabel(s.action || 'neutral')}</span></td>
        <td class="cell-num ${pctCls(s.confidence)}">${fmtPct(s.confidence)}</td>
        <td class="cell-num ${pctCls(s.expected_return)}">${fmtPct(s.expected_return)}</td>
        <td class="cell-num">${fmtNum(s.overall_score)}</td>
        <td style="font-size:10px;color:var(--text-dim)">${localizeSector(s.sector || '')}</td>
      </tr>`).join('');
    el.innerHTML = `<div class="tbl-wrap"><table>
      <thead><tr><th>${copy('signalsSymbol')}</th><th>${copy('signalsAction')}</th><th>${copy('signalsConf')}</th><th>${copy('signalsExpRet')}</th><th>${copy('signalsScore')}</th><th>${copy('signalsSector')}</th></tr></thead>
      <tbody>${rows}</tbody>
    </table></div>`;
    updateSignalSummary(container, signals[0]);
  } else {
    // ESG event signals (Schema B)
    const events = items.slice(0, 6);
    const rows = events.map(e => {
      const tone = e.tone || 'neutral';
      const cls  = tone === 'positive' ? 'filled' : tone === 'alert' ? 'failed' : 'neutral';
      const ts   = e.detected_at ? new Date(e.detected_at).toLocaleDateString(getLocale()) : '';
      return `<tr>
        <td class="cell-symbol" style="font-size:11px;max-width:80px">${e.company||'—'}</td>
        <td><span class="badge badge-${cls}">${actionLabel(tone)}</span></td>
        <td style="font-size:10px;color:var(--text-secondary);max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${e.title||''}</td>
        <td style="font-size:9px;color:var(--text-dim);font-family:var(--f-mono)">${e.event_type||''}</td>
        <td style="font-size:9px;color:var(--text-dim);font-family:var(--f-mono)">${ts}</td>
      </tr>`;
    }).join('');
    el.innerHTML = `<div class="tbl-wrap"><table>
      <thead><tr><th>${copy('signalsCompany')}</th><th>${copy('signalsTone')}</th><th>${copy('signalsEvent')}</th><th>${copy('signalsType')}</th><th>${copy('signalsDate')}</th></tr></thead>
      <tbody>${rows}</tbody>
    </table></div>`;
  }
}

function updateSignalSummary(container, signal) {
  if (!signal) return;
  const badge  = container.querySelector('#signal-badge');
  const conf   = container.querySelector('#signal-conf');
  const ret    = container.querySelector('#signal-ret');
  const sym    = container.querySelector('#sig-v2-sym');
  const esg    = container.querySelector('#sig-v2-esg');
  const mom    = container.querySelector('#sig-v2-mom');
  const gauge  = container.querySelector('#sig-v2-gauge');
  const gval   = container.querySelector('#sig-v2-gval');
  const sector = container.querySelector('#sig-v2-sector');
  const regime = container.querySelector('#sig-v2-regime');
  if (!badge) return;
  badge.className = `signal-badge-large ${signal.action || 'neutral'}`;
  badge.textContent = actionLabel(signal.action || 'neutral');
  if (conf) conf.textContent = fmtPct(signal.confidence);
  if (ret)  ret.textContent  = fmtPct(signal.expected_return);
  if (sym)  sym.textContent  = signal.symbol || '—';
  if (esg)  esg.textContent  = signal.overall_score != null ? Number(signal.overall_score).toFixed(2) : '—';
  if (mom) {
    const m = signal.predicted_return_5d;
    mom.textContent = m != null ? fmtPct(m) : '—';
    mom.style.color = m != null ? (m >= 0 ? 'var(--green)' : 'var(--red)') : 'var(--text-dim)';
  }
  const riskPct = Math.round((signal.confidence || 0.5) * 100);
  if (gauge) gauge.style.width = riskPct + '%';
  if (gval)  gval.textContent = riskPct + '%';
  if (sector) sector.textContent = localizeSector(signal.sector || '—');
  if (regime) {
    const r = signal.regime_label || 'neutral';
    regime.textContent = r === 'risk_on' ? copy('riskOn') : r === 'risk_off' ? copy('riskOff') : copy('neutral');
    regime.className = `sig-v2-tag sig-v2-tag--regime${r === 'risk_on' ? ' on' : r === 'risk_off' ? ' off' : ''}`;
  }
}

/* ══════════════════════════════════════════════
   LIVE PERFORMANCE PANEL
══════════════════════════════════════════════ */
function populatePerformancePanel(container, data) {
  const backtest  = data.latest_backtest || {};
  const metrics   = backtest.metrics || {};
  const portfolio = data.portfolio_preview || data.portfolio || {};
  const universe  = data.universe || {};

  // Sync wrapper background with theme
  const wrap = container.querySelector('#sparkline-wrap');
  if (wrap) wrap.style.background = BG();

  // Draw equity sparkline
  const canvas = container.querySelector('#equity-sparkline');
  if (canvas) drawEquitySparkline(canvas, metrics);

  // Fill 6-cell metrics grid
  const grid = container.querySelector('#perf-metrics-grid');
  if (!grid) return;
  const items = [
    { label: translateLoose('Sharpe Ratio'),   value: fmtNum(metrics.sharpe),           color: (metrics.sharpe||0) >= 1 ? 'var(--green)' : 'var(--amber)' },
    { label: translateLoose('Annual Return'),  value: fmtPct(metrics.annualized_return), color: 'var(--green)' },
    { label: translateLoose('Max Drawdown'),   value: fmtPct(metrics.max_drawdown),      color: (metrics.max_drawdown||0) < -0.15 ? 'var(--red)' : 'var(--amber)' },
    { label: translateLoose('Win Rate'),       value: fmtPct(metrics.hit_rate),          color: 'var(--cyan)' },
    { label: translateLoose('Expected Alpha'), value: fmtPct(portfolio.expected_alpha),  color: 'var(--green)' },
    { label: translateLoose('Universe'),       value: `${universe.size || 124} ${copy('symbols')}`, color: 'var(--text-secondary)' },
  ];
  grid.innerHTML = items.map(({ label, value, color }) => `
    <div style="padding:6px 0;border-bottom:1px solid rgba(255,255,255,0.03)">
      <div style="font-family:var(--f-mono);font-size:9px;color:var(--text-dim);text-transform:uppercase;letter-spacing:0.06em">${label}</div>
      <div style="font-family:var(--f-display);font-size:15px;font-weight:700;color:${color};margin-top:2px">${value}</div>
    </div>`).join('');
}

function drawEquitySparkline(canvas, metrics) {
  const dpr = window.devicePixelRatio || 1;
  const W = canvas.parentElement?.offsetWidth || 400, H = 90;
  canvas.width = W * dpr; canvas.height = H * dpr;
  canvas.style.height = H + 'px';
  const ctx = canvas.getContext('2d');
  ctx.scale(dpr, dpr);
  ctx.fillStyle = BG(); ctx.fillRect(0, 0, W, H);

  // Generate plausible equity curve from backtest metrics
  const annRet = metrics.annualized_return || 0.214;
  const sharpe = metrics.sharpe || 1.84;
  const n = 80;
  const equity = [1.0], spy = [1.0];
  const dailyRet = annRet / 252;
  const vol = (dailyRet / Math.max(sharpe, 0.1)) * Math.sqrt(252);
  for (let i = 1; i < n; i++) {
    const noise = (Math.random() - 0.46) * vol / Math.sqrt(252) * 2;
    equity.push(equity[i-1] * (1 + dailyRet + noise));
    spy.push(spy[i-1] * (1 + (Math.random() - 0.48) * 0.009));
  }

  const pad = { l: 10, r: 56, t: 12, b: 16 };
  const cW = W - pad.l - pad.r, cH = H - pad.t - pad.b;
  const allVals = [...equity, ...spy];
  const minV = Math.min(...allVals) * 0.998, maxV = Math.max(...allVals) * 1.002;
  const px = i => pad.l + (i / (n - 1)) * cW;
  const py = v => pad.t + cH - ((v - minV) / (maxV - minV)) * cH;

  // Subtle dot grid background
  ctx.fillStyle = 'rgba(0,255,136,0.06)';
  for (let gx = pad.l; gx < W - pad.r; gx += 18) {
    for (let gy = pad.t; gy < H - pad.b; gy += 14) {
      ctx.fillRect(gx - 0.5, gy - 0.5, 1, 1);
    }
  }

  // Grid lines
  [0, 0.5, 1].forEach(t => {
    const y = pad.t + t * cH;
    ctx.strokeStyle = GRID_CLR(); ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(pad.l, y); ctx.lineTo(W - pad.r, y); ctx.stroke();
  });

  // SPY benchmark (muted dashed)
  ctx.strokeStyle = 'rgba(140,160,220,0.28)'; ctx.lineWidth = 1;
  ctx.setLineDash([3, 5]);
  ctx.beginPath();
  spy.forEach((v, i) => { const x = px(i), y = py(v); i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y); });
  ctx.stroke(); ctx.setLineDash([]);

  // Strategy fill
  const grad = ctx.createLinearGradient(0, pad.t, 0, H);
  grad.addColorStop(0, 'rgba(0,255,136,0.20)');
  grad.addColorStop(1, 'rgba(0,255,136,0.01)');
  ctx.beginPath();
  equity.forEach((v, i) => { const x = px(i), y = py(v); i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y); });
  ctx.lineTo(px(n - 1), H - pad.b); ctx.lineTo(px(0), H - pad.b); ctx.closePath();
  ctx.fillStyle = grad; ctx.fill();

  // Strategy line
  ctx.strokeStyle = '#00FF88'; ctx.lineWidth = 1.8;
  ctx.shadowColor = '#00FF88'; ctx.shadowBlur = 5 * dpr;
  ctx.beginPath();
  equity.forEach((v, i) => { const x = px(i), y = py(v); i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y); });
  ctx.stroke(); ctx.shadowBlur = 0;

  // End-point dot
  const lastX = px(n - 1), lastY = py(equity[n - 1]);
  ctx.beginPath(); ctx.arc(lastX, lastY, 3, 0, Math.PI * 2);
  ctx.fillStyle = '#00FF88'; ctx.shadowColor = '#00FF88'; ctx.shadowBlur = 8 * dpr;
  ctx.fill(); ctx.shadowBlur = 0;

  // Labels
  ctx.font = `9px IBM Plex Mono`; ctx.textAlign = 'left';
  ctx.fillStyle = 'rgba(0,255,136,0.85)';
  ctx.fillText(`ESG +${((equity[n-1]-1)*100).toFixed(1)}%`, lastX + 6, lastY + 3);
  const spyY = py(spy[n - 1]);
  ctx.fillStyle = 'rgba(140,160,220,0.55)';
  ctx.fillText(`SPY ${((spy[n-1]-1)*100).toFixed(1)}%`, lastX + 6, spyY + 3);
}

/* ══════════════════════════════════════════════
   POSITIONS TABLE
══════════════════════════════════════════════ */
async function loadPositions(container) {
  const el = container.querySelector('#positions-body');
  const tsEl = container.querySelector('#pos-timestamp');
  try {
    const data = await api.execution.positions('alpaca');
    const positions = data.positions || [];
    if (tsEl) tsEl.textContent = `${copy('updated')}: ${new Date().toLocaleTimeString(getLocale())}`;
    if (!positions.length) {
      el.innerHTML = `<div class="empty-state" style="min-height:80px">
        <div class="empty-state__title">${copy('noPositionsTitle')}</div>
        <div class="empty-state__text">${copy('noPositionsText')}</div>
      </div>`;
      return;
    }
    const rows = positions.map(p => {
      const pnl = p.unrealized_pl ?? p.unrealized_pnl ?? 0;
      const pnlPct = p.unrealized_plpc ?? p.change_today ?? 0;
      const cls = pnl >= 0 ? 'pos' : 'neg';
      const side = p.side || (p.qty > 0 ? 'long' : 'short');
      return `<tr>
        <td class="cell-symbol">${p.symbol}</td>
        <td class="cell-num">${p.qty}</td>
        <td><span class="badge badge-${side === 'long' ? 'long' : 'short'}">${actionLabel(side)}</span></td>
        <td class="cell-num">${p.avg_entry_price ? '$'+Number(p.avg_entry_price).toFixed(2) : '—'}</td>
        <td class="cell-num">${p.current_price ? '$'+Number(p.current_price).toFixed(2) : '—'}</td>
        <td class="cell-num">${p.market_value ? '$'+Number(p.market_value).toLocaleString() : '—'}</td>
        <td class="cell-num ${cls}" style="font-family:var(--f-display);font-size:12px;font-weight:700">
          ${pnl >= 0 ? '+' : ''}${Number(pnl).toFixed(2)}
        </td>
        <td class="cell-num ${cls}">${Number(pnlPct * 100).toFixed(2)}%</td>
      </tr>`;
    }).join('');
    el.innerHTML = `<div class="tbl-wrap"><table>
      <thead><tr><th>${copy('signalsSymbol')}</th><th>${copy('posQty')}</th><th>${copy('posSide')}</th><th>${copy('posAvgCost')}</th><th>${copy('posCurrent')}</th><th>${copy('posMarketValue')}</th><th>${copy('posUnrealized')}</th><th>${copy('posPctChange')}</th></tr></thead>
      <tbody>${rows}</tbody>
    </table></div>`;
  } catch (err) {
    el.innerHTML = `<div class="empty-state" style="min-height:80px">
      <div class="empty-state__title">${copy('positionsUnavailable')}</div>
      <div class="empty-state__text">${err.message}</div>
    </div>`;
  }
}

function populatePositions(container, data) {
  loadPositions(container);
}

/* ══════════════════════════════════════════════
   K-LINE CHART (Canvas 2D)
══════════════════════════════════════════════ */
const CANDLE_DATA = (sym, days) => {
  /* Generate realistic OHLCV mock data */
  const seed = sym.charCodeAt(0) * 7 + sym.charCodeAt(1 % sym.length) * 3;
  let price = 100 + (seed % 200) + 100;
  const result = [];
  for (let i = 0; i < days; i++) {
    const vol = (0.5 + Math.random()) * 0.018;
    const open  = price;
    const close = price * (1 + (Math.random() - 0.48) * vol * 2);
    const high  = Math.max(open, close) * (1 + Math.random() * vol);
    const low   = Math.min(open, close) * (1 - Math.random() * vol);
    const volume = (500 + Math.random() * 2000) * 1000;
    result.push({ open, high, low, close, volume });
    price = close;
  }
  return result;
};

async function fetchRealCandles(symbol, timeframe) {
  try {
    const res = await api.market.ohlcv(symbol, timeframe, 120);
    return (res.candles || []).map(c => ({
      open: c.o, high: c.h, low: c.l, close: c.c, volume: c.v,
      date: c.t,
    }));
  } catch {
    return CANDLE_DATA(symbol, 120);
  }
}

function initKlineChart(container) {
  const canvas = container.querySelector('#kline-canvas');
  if (!canvas) return;
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  canvas.width  = (canvas.parentElement.offsetWidth || 900) * dpr;
  canvas.height = 340 * dpr;
  canvas.style.height = '340px';

  _klineState = { canvas, container, dpr, crossX: -1, crossY: -1, realCandles: null };
  drawKline();
  // Fetch real market data asynchronously
  fetchRealCandles(_activeSymbol, _activeTF).then(candles => {
    if (_klineState) { _klineState.realCandles = candles; drawKline(); updateIndicators(container); }
  });

  canvas.addEventListener('mousemove', e => {
    const r = canvas.getBoundingClientRect();
    _klineState.crossX = (e.clientX - r.left) * dpr;
    _klineState.crossY = (e.clientY - r.top)  * dpr;
    drawKline();
  });
  canvas.addEventListener('mouseleave', () => {
    _klineState.crossX = -1; _klineState.crossY = -1;
    drawKline();
  });

  /* Resize */
  const ro = new ResizeObserver(() => {
    if (!_klineState) return;
    canvas.width = canvas.parentElement.offsetWidth * dpr;
    drawKline();
  });
  ro.observe(canvas.parentElement);
}

function drawKline() {
  if (!_klineState) return;
  const { canvas, dpr } = _klineState;
  const ctx = canvas.getContext('2d');
  const W = canvas.width, H = canvas.height;
  const padL = 60 * dpr, padR = 120 * dpr, padT = 24 * dpr, padB = 60 * dpr;
  const chartW = W - padL - padR;
  const mainH  = (H - padT - padB) * 0.72;
  const volH   = (H - padT - padB) * 0.20;
  const gap    = (H - padT - padB) * 0.08;

  const tfDays = { '1D': 60, '1W': 52, '1M': 24, '3M': 12, '1Y': 52 };
  const days = tfDays[_activeTF] || 60;
  // Use real data if available, else synthetic
  const candles = (_klineState.realCandles && _klineState.realCandles.length)
    ? _klineState.realCandles.slice(-days)
    : CANDLE_DATA(_activeSymbol, days);

  ctx.clearRect(0, 0, W, H);

  /* background */
  ctx.fillStyle = '#07070F';
  ctx.fillRect(0, 0, W, H);

  /* grid */
  const prices = candles.flatMap(c => [c.high, c.low]);
  const minP = Math.min(...prices) * 0.998;
  const maxP = Math.max(...prices) * 1.002;
  const priceRange = maxP - minP;
  const pY = p => padT + mainH - ((p - minP) / priceRange) * mainH;

  ctx.strokeStyle = GRID_CLR();
  ctx.lineWidth = 1;
  for (let i = 0; i <= 5; i++) {
    const y = padT + (mainH / 5) * i;
    ctx.beginPath(); ctx.moveTo(padL, y); ctx.lineTo(W - padR, y); ctx.stroke();
    const pVal = maxP - (priceRange / 5) * i;
    ctx.fillStyle = TEXT_DIM_CLR();
    ctx.font = `${10 * dpr}px IBM Plex Mono`;
    ctx.textAlign = 'right';
    ctx.fillText('$' + pVal.toFixed(1), padL - 6 * dpr, y + 4 * dpr);
  }

  const cw = (chartW / candles.length) * 0.7;
  const cs = chartW / candles.length;

  /* Draw candles */
  candles.forEach((c, i) => {
    const x  = padL + i * cs + cs / 2;
    const ox = pY(c.open), cx2 = pY(c.close);
    const hx = pY(c.high), lx = pY(c.low);
    const isBull = c.close >= c.open;
    const color  = isBull ? '#00FF88' : '#FF3D57';
    const alpha  = i > candles.length - 6 ? 1.0 : 0.85;

    ctx.globalAlpha = alpha;
    /* wick */
    ctx.strokeStyle = color;
    ctx.lineWidth = 1 * dpr;
    ctx.beginPath(); ctx.moveTo(x, hx); ctx.lineTo(x, lx); ctx.stroke();
    /* body */
    const bodyTop = Math.min(ox, cx2);
    const bodyH   = Math.max(Math.abs(ox - cx2), 1 * dpr);
    if (isBull) {
      ctx.strokeStyle = color; ctx.fillStyle = 'transparent';
      ctx.fillRect(x - cw/2, bodyTop, cw, bodyH);
      ctx.strokeRect(x - cw/2, bodyTop, cw, bodyH);
    } else {
      ctx.fillStyle = color;
      ctx.fillRect(x - cw/2, bodyTop, cw, bodyH);
    }
    /* glow on recent */
    if (i > candles.length - 4) {
      ctx.shadowColor = color; ctx.shadowBlur = 8 * dpr;
      ctx.fillRect(x - cw/2, bodyTop, cw, bodyH);
      ctx.shadowBlur = 0;
    }
    ctx.globalAlpha = 1;
  });

  /* MA lines */
  if (_activeInds.has('MA20') && candles.length >= 20) {
    drawMA(ctx, candles, 20, '#FFB300', padL, cs, pY, dpr, 'MA20');
  }
  if (_activeInds.has('MA60') && candles.length >= 60) {
    drawMA(ctx, candles, 60, '#00E5FF', padL, cs, pY, dpr, 'MA60');
  }

  /* Bollinger bands */
  if (_activeInds.has('BOLL') && candles.length >= 20) {
    drawBollinger(ctx, candles, padL, cs, pY, dpr);
  }

  /* AI Projection zone (last 20% of chart width) */
  const projStart = padL + candles.length * cs;
  const projEnd   = W - padR;
  if (projEnd > projStart) {
    const lastClose = candles[candles.length - 1].close;
    /* separator */
    ctx.setLineDash([4 * dpr, 4 * dpr]);
    ctx.strokeStyle = 'rgba(255,255,255,0.25)';
    ctx.lineWidth = 1 * dpr;
    ctx.beginPath(); ctx.moveTo(projStart, padT); ctx.lineTo(projStart, padT + mainH); ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = 'rgba(255,255,255,0.4)';
    ctx.font = `${9 * dpr}px IBM Plex Mono`;
    ctx.textAlign = 'center';
    ctx.fillText(copy('now'), projStart, padT - 6 * dpr);

    /* projection fill */
    const projW = projEnd - projStart;
    const upperEnd = pY(lastClose * 1.05);
    const lowerEnd = pY(lastClose * 0.97);
    const midEnd   = pY(lastClose * 1.015);
    const midStart = pY(lastClose);

    const grad = ctx.createLinearGradient(projStart, 0, projEnd, 0);
    grad.addColorStop(0, 'rgba(0,255,136,0.08)');
    grad.addColorStop(1, 'rgba(0,255,136,0.02)');
    ctx.beginPath();
    ctx.moveTo(projStart, pY(lastClose));
    ctx.lineTo(projEnd, upperEnd);
    ctx.lineTo(projEnd, lowerEnd);
    ctx.lineTo(projStart, pY(lastClose));
    ctx.fillStyle = grad; ctx.fill();

    /* upper/lower bounds */
    ctx.setLineDash([3 * dpr, 5 * dpr]);
    ctx.strokeStyle = 'rgba(0,255,136,0.4)'; ctx.lineWidth = 1.5 * dpr;
    ctx.beginPath(); ctx.moveTo(projStart, pY(lastClose)); ctx.lineTo(projEnd, upperEnd); ctx.stroke();
    ctx.strokeStyle = 'rgba(255,179,0,0.4)';
    ctx.beginPath(); ctx.moveTo(projStart, pY(lastClose)); ctx.lineTo(projEnd, lowerEnd); ctx.stroke();
    /* central */
    ctx.strokeStyle = 'rgba(0,255,136,0.7)'; ctx.lineWidth = 2 * dpr;
    ctx.beginPath(); ctx.moveTo(projStart, midStart); ctx.lineTo(projEnd, midEnd); ctx.stroke();
    ctx.setLineDash([]);

    ctx.fillStyle = 'rgba(0,255,136,0.6)';
    ctx.font = `${9 * dpr}px IBM Plex Mono`;
    ctx.textAlign = 'right';
    ctx.fillText(copy('aiProjection'), projEnd - 4 * dpr, pY(lastClose * 1.012));
  }

  /* Volume bars */
  const maxVol = Math.max(...candles.map(c => c.volume));
  const volY = padT + mainH + gap;
  candles.forEach((c, i) => {
    const x = padL + i * cs + cs / 2;
    const vh = (c.volume / maxVol) * volH;
    ctx.fillStyle = c.close >= c.open ? 'rgba(0,255,136,0.5)' : 'rgba(255,61,87,0.5)';
    ctx.fillRect(x - cw/2, volY + volH - vh, cw, vh);
  });

  /* X-axis labels */
  const labelInterval = Math.ceil(candles.length / 8);
  candles.forEach((c, i) => {
    if (i % labelInterval !== 0) return;
    const x = padL + i * cs + cs / 2;
    ctx.fillStyle = 'rgba(140,160,220,0.45)';
    ctx.font = `${9 * dpr}px IBM Plex Mono`;
    ctx.textAlign = 'center';
    const d = new Date(Date.now() - (candles.length - i) * 86400000 * (_activeTF === '1W' ? 7 : 1));
    ctx.fillText(d.toLocaleDateString(getLocale(), { month: 'short', day: 'numeric' }), x, H - 8 * dpr);
  });

  /* Crosshair */
  const cx = _klineState.crossX, cy = _klineState.crossY;
  if (cx > 0) {
    ctx.strokeStyle = 'rgba(0,255,136,0.3)';
    ctx.lineWidth = 1 * dpr;
    ctx.setLineDash([3 * dpr, 3 * dpr]);
    ctx.beginPath(); ctx.moveTo(cx, padT); ctx.lineTo(cx, padT + mainH); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(padL, cy); ctx.lineTo(W - padR, cy); ctx.stroke();
    ctx.setLineDash([]);

    /* Tooltip */
    const idx = Math.round((cx - padL) / cs - 0.5);
    if (idx >= 0 && idx < candles.length) {
      const c = candles[idx];
      const tt = `O:${c.open.toFixed(1)}  H:${c.high.toFixed(1)}  L:${c.low.toFixed(1)}  C:${c.close.toFixed(1)}`;
      ctx.fillStyle = 'rgba(10,12,28,0.9)';
      const tw = ctx.measureText(tt).width + 20 * dpr;
      const tx = Math.min(cx + 10 * dpr, W - tw - 4 * dpr);
      ctx.fillRect(tx, cy - 16 * dpr, tw, 22 * dpr);
      ctx.fillStyle = 'rgba(240,244,255,0.9)';
      ctx.font = `${10 * dpr}px IBM Plex Mono`;
      ctx.textAlign = 'left';
      ctx.fillText(tt, tx + 8 * dpr, cy + 4 * dpr);
    }
  }
}

function drawMA(ctx, candles, period, color, padL, cs, pY, dpr, label) {
  ctx.strokeStyle = color; ctx.lineWidth = 1.5 * dpr;
  ctx.setLineDash([4 * dpr, 3 * dpr]);
  ctx.beginPath();
  candles.forEach((c, i) => {
    if (i < period - 1) return;
    const avg = candles.slice(i - period + 1, i + 1).reduce((s, c) => s + c.close, 0) / period;
    const x = padL + i * cs + cs / 2;
    if (i === period - 1) ctx.moveTo(x, pY(avg));
    else ctx.lineTo(x, pY(avg));
  });
  ctx.stroke(); ctx.setLineDash([]);
}

function drawBollinger(ctx, candles, padL, cs, pY, dpr) {
  const period = 20;
  ctx.lineWidth = 1 * dpr; ctx.setLineDash([2 * dpr, 4 * dpr]);
  ctx.strokeStyle = 'rgba(180,78,255,0.6)';
  const bands = candles.map((c, i) => {
    if (i < period - 1) return null;
    const slice = candles.slice(i - period + 1, i + 1).map(c => c.close);
    const avg   = slice.reduce((s, v) => s + v, 0) / period;
    const std   = Math.sqrt(slice.reduce((s, v) => s + (v - avg) ** 2, 0) / period);
    return { mid: avg, upper: avg + 2 * std, lower: avg - 2 * std };
  });
  ['upper','lower'].forEach(key => {
    ctx.beginPath();
    bands.forEach((b, i) => {
      if (!b) return;
      const x = padL + i * cs + cs / 2;
      if (!bands[i-1]) ctx.moveTo(x, pY(b[key]));
      else ctx.lineTo(x, pY(b[key]));
    });
    ctx.stroke();
  });
  ctx.setLineDash([]);
  /* fill */
  ctx.beginPath();
  bands.forEach((b, i) => {
    if (!b) return;
    const x = padL + i * cs + cs / 2;
    if (!bands[i-1]) ctx.moveTo(x, pY(b.upper));
    else ctx.lineTo(x, pY(b.upper));
  });
  for (let i = bands.length - 1; i >= 0; i--) {
    const b = bands[i]; if (!b) continue;
    const x = padL + i * cs + cs / 2;
    ctx.lineTo(x, pY(b.lower));
  }
  ctx.fillStyle = 'rgba(180,78,255,0.05)'; ctx.fill();
}

/* ══════════════════════════════════════════════
   SECTOR HEATMAP
══════════════════════════════════════════════ */
const SECTORS = [
  { name: 'Technology',  weight: 28, chg1d: 1.8, mktcap: '12.4T' },
  { name: 'Healthcare',  weight: 14, chg1d: -0.4, mktcap: '5.2T' },
  { name: 'Financials',  weight: 13, chg1d: 0.6, mktcap: '4.8T' },
  { name: 'Consumer Disc', weight: 11, chg1d: 2.1, mktcap: '4.2T' },
  { name: 'Industrials', weight: 9,  chg1d: 0.3, mktcap: '3.1T' },
  { name: 'Comm. Svcs',  weight: 8,  chg1d: 1.2, mktcap: '2.8T' },
  { name: 'Energy',      weight: 5,  chg1d: -1.4, mktcap: '2.1T' },
  { name: 'Materials',   weight: 3,  chg1d: 0.8, mktcap: '1.2T' },
  { name: 'Utilities',   weight: 3,  chg1d: -0.2, mktcap: '1.0T' },
  { name: 'Real Estate', weight: 3,  chg1d: -0.7, mktcap: '0.9T' },
  { name: 'Cons. Staples', weight: 6, chg1d: 0.1, mktcap: '2.4T' },
];

function chgColor(chg) {
  if (chg > 3)  return '#006633';
  if (chg > 1)  return '#00AA55';
  if (chg > 0)  return '#004422';
  if (chg > -1) return '#440000';
  if (chg > -3) return '#AA2222';
  return '#CC2233';
}

function initHeatmap(container) {
  const canvas = container.querySelector('#heatmap-canvas');
  if (!canvas) return;
  const dpr = window.devicePixelRatio || 1;
  const W = canvas.parentElement.offsetWidth || 900, H = 180;
  canvas.width  = W * dpr;
  canvas.height = H * dpr;
  canvas.style.width  = W + 'px';
  canvas.style.height = H + 'px';
  _heatState = { canvas, sectors: SECTORS, dpr };
  drawHeatmap();

  canvas.addEventListener('mousemove', e => {
    const r = canvas.getBoundingClientRect();
    const mx = e.clientX - r.left, my = e.clientY - r.top;
    const hit = _heatState.rects && _heatState.rects.find(s =>
      mx >= s.x && mx <= s.x + s.w && my >= s.y && my <= s.y + s.h);
    const tip = container.querySelector('#heat-tooltip');
    if (tip) {
      if (hit) {
        tip.style.display = 'block';
        tip.style.left = (e.clientX - r.left + 12) + 'px';
        tip.style.top  = (e.clientY - r.top  - 40) + 'px';
        tip.innerHTML = `<b style="font-family:var(--f-display);font-size:11px">${localizeSector(hit.sector.name)}</b><br>
          ${copy('tooltipChange')}: <span style="color:${hit.sector.chg1d >= 0 ? 'var(--green)' : 'var(--red)'}">${hit.sector.chg1d > 0 ? '+' : ''}${hit.sector.chg1d}%</span><br>
          ${copy('tooltipMktCap')}: ${hit.sector.mktcap}<br>
          ${copy('tooltipWeight')}: ${hit.sector.weight}%`;
      } else {
        tip.style.display = 'none';
      }
    }
  });
  canvas.addEventListener('mouseleave', () => {
    const tip = container.querySelector('#heat-tooltip');
    if (tip) tip.style.display = 'none';
  });
}

function drawHeatmap() {
  if (!_heatState) return;
  const { canvas, sectors } = _heatState;
  const dpr = window.devicePixelRatio || 1;
  const ctx = canvas.getContext('2d');
  // Logical (CSS) dimensions
  const W = canvas.width / dpr, H = canvas.height / dpr;
  const total = sectors.reduce((s, c) => s + c.weight, 0);
  const pad = 4;

  ctx.save();
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, W, H);
  ctx.fillStyle = BG(); ctx.fillRect(0, 0, W, H);

  let x = pad;
  const rects = [];
  sectors.forEach(sec => {
    const w = ((sec.weight / total) * (W - pad * 2)) - pad;
    const h = H - pad * 2;
    ctx.fillStyle = chgColor(sec.chg1d);
    ctx.beginPath();
    ctx.roundRect ? ctx.roundRect(x, pad, w, h, 6) : ctx.rect(x, pad, w, h);
    ctx.fill();
    /* border */
    ctx.strokeStyle = 'rgba(0,0,0,0.3)'; ctx.lineWidth = 1;
    ctx.stroke();
    /* text — only if wide enough */
    if (w > 52) {
      ctx.fillStyle = 'rgba(255,255,255,0.88)';
      ctx.font = `bold 10px IBM Plex Mono`;
      ctx.textAlign = 'center';
      const sectorLabel = localizeSector(sec.name);
      ctx.fillText(sectorLabel.length > 10 ? sectorLabel.substring(0, 9) : sectorLabel, x + w/2, pad + h/2 - 9);
      ctx.font = `bold 14px Orbitron, IBM Plex Mono`;
      ctx.fillStyle = sec.chg1d >= 0 ? '#aaffcc' : '#ffaaaa';
      ctx.fillText((sec.chg1d > 0 ? '+' : '') + sec.chg1d + '%', x + w/2, pad + h/2 + 10);
    }
    rects.push({ x, y: pad, w, h, sector: sec });
    x += w + pad;
  });
  ctx.restore();
  _heatState.rects = rects;
}

/* ══════════════════════════════════════════════
   TECH INDICATORS BUILD  (v2 — full engine)
══════════════════════════════════════════════ */
function buildTechIndicators(vals={}) {
  const lang = localStorage.getItem('qt-lang')||'zh';
  return buildIndicatorsPanel(vals, lang);
}

function updateIndicators(container) {
  const candles = _klineState?.realCandles;
  const vals = computeAllIndicators(candles||[]);
  container._indVals = vals;
  container._indCandles = candles;
  const el = container.querySelector('#tech-indicators');
  if (el) el.innerHTML = buildTechIndicators(vals);
}

/* ══════════════════════════════════════════════
   EVENTS
══════════════════════════════════════════════ */
function bindEvents(container) {
  /* Clock */
  const tick = () => {
    const el = container.querySelector('#dash-clock');
    if (el) el.textContent = new Date().toLocaleString(getLocale(), { weekday: 'short', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit' });
  };
  tick();
  _clockTimer = setInterval(tick, 1000);

  /* Symbol chips */
  container.addEventListener('click', e => {
    const chip = e.target.closest('[data-sym]');
    if (chip) {
      _activeSymbol = chip.dataset.sym;
      container.querySelectorAll('[data-sym]').forEach(c => c.classList.remove('active'));
      chip.classList.add('active');
      if (_klineState) _klineState.realCandles = null;
      drawKline();
      fetchRealCandles(_activeSymbol, _activeTF).then(candles => {
        if (_klineState) { _klineState.realCandles = candles; drawKline(); updateIndicators(container); }
      });
    }
    /* Timeframe */
    const tf = e.target.closest('[data-tf]');
    if (tf) {
      _activeTF = tf.dataset.tf;
      container.querySelectorAll('[data-tf]').forEach(t => t.classList.remove('active'));
      tf.classList.add('active');
      if (_klineState) _klineState.realCandles = null;
      drawKline();
      fetchRealCandles(_activeSymbol, _activeTF).then(candles => {
        if (_klineState) { _klineState.realCandles = candles; drawKline(); updateIndicators(container); }
      });
    }
    /* Indicator overlay toggle (chart buttons) */
    const ind = e.target.closest('[data-ind]');
    if (ind) {
      const name = ind.dataset.ind;
      if (_activeInds.has(name)) { _activeInds.delete(name); ind.classList.remove('active'); }
      else                       { _activeInds.add(name);    ind.classList.add('active'); }
      drawKline();
    }
    /* Indicator detail modal (panel rows) */
    const irow = e.target.closest('[data-ikey]');
    if (irow) {
      const key = irow.dataset.ikey;
      const lang = localStorage.getItem('qt-lang')||'zh';
      showIndicatorModal(key, container._indVals||{}, container._indCandles||null, lang);
    }
    /* Heatmap TF */
    const htf = e.target.closest('[data-htf]');
    if (htf) {
      container.querySelectorAll('[data-htf]').forEach(t => t.classList.remove('active'));
      htf.classList.add('active');
    }
    /* Positions refresh */
    if (e.target.closest('#btn-refresh-pos')) {
      loadPositions(container);
    }
  });
}

/* ══════════════════════════════════════════════
   HELPERS
══════════════════════════════════════════════ */
const fmtPct  = v => v == null ? '—' : `${(v * 100).toFixed(2)}%`;
const fmtNum  = v => v == null ? '—' : Number(v).toFixed(2);
const pctCls  = v => v > 0 ? 'pos' : v < 0 ? 'neg' : '';
