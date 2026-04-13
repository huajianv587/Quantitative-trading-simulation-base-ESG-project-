import { api } from '../qtapi.js?v=8';
import { toast } from '../components/toast.js?v=8';
import { getLang, getLocale } from '../i18n.js?v=8';

const CATALOG = [
  {
    id: 'alpha-ranker', category: 'ml', icon: '🧠',
    name: 'Alpha Ranker', type: 'XGBoost Ensemble',
    sharpe: 1.84, maxDD: '-9.2%', holding: '5–20d',
    description: 'Gradient-boosted ranking model combining 47 ESG-adjusted factors. Primary signal generator in P1 stack.',
    tags: ['P1', 'ESG', 'Long-Short'],
    sparkline: [1.2,1.4,1.3,1.6,1.5,1.7,1.8,1.9,1.85,1.84],
    status: 'live', version: 'v2.4.1',
    params: { n_estimators: 1200, max_depth: 6, learning_rate: 0.02, colsample_bytree: 0.7, esg_weight: 0.35 },
    metrics: { 'IS Sharpe': '2.14', 'OOS Sharpe': '1.84', 'Hit Rate': '58.3%', 'Avg Hold': '11.4d', 'Turnover': '34%/mo' }
  },
  {
    id: 'lstm-signal', category: 'ml', icon: '🔮',
    name: 'LSTM Price Signal', type: 'Recurrent Neural Network',
    sharpe: 1.41, maxDD: '-14.1%', holding: '3–10d',
    description: 'Sequence-to-sequence LSTM trained on 10 years of price/volume data with attention mechanism. Feeds into Alpha Ranker.',
    tags: ['P1', 'Deep Learning'],
    sparkline: [0.9,1.1,1.0,1.2,1.3,1.25,1.4,1.35,1.42,1.41],
    status: 'live', version: 'v1.8.0',
    params: { hidden_size: 256, num_layers: 3, dropout: 0.2, seq_len: 60, batch_size: 512 },
    metrics: { 'IS Sharpe': '1.72', 'OOS Sharpe': '1.41', 'Hit Rate': '54.1%', 'Avg Hold': '6.2d', 'Turnover': '58%/mo' }
  },
  {
    id: 'regime-detector', category: 'statistical', icon: '🌡️',
    name: 'Regime Detector', type: 'Hidden Markov Model',
    sharpe: 1.05, maxDD: '-5.8%', holding: 'N/A',
    description: '4-state HMM classifying market regime: Bull / Bear / Sideways / High-Vol. Used to modulate position sizing and factor weights.',
    tags: ['P1', 'P2', 'Overlay'],
    sparkline: [0.8,0.9,1.0,0.95,1.0,1.05,1.02,1.06,1.04,1.05],
    status: 'live', version: 'v3.1.0',
    params: { n_states: 4, lookback: 252, covariance_type: 'full', n_iter: 500 },
    metrics: { 'Accuracy': '71.2%', 'Stability': '0.84', 'Avg Regime': '18.3d', 'Transitions': '2.7/mo', 'Lag': '<1d' }
  },
  {
    id: 'gnn-portfolio', category: 'ml', icon: '🕸️',
    name: 'GNN Portfolio Engine', type: 'Graph Neural Network',
    sharpe: 1.67, maxDD: '-11.3%', holding: '10–30d',
    description: 'Graph-based model encoding sector correlations and supply chain relationships. Powers P2 decision engine for position allocation.',
    tags: ['P2', 'ESG', 'Allocation'],
    sparkline: [1.1,1.2,1.3,1.4,1.45,1.5,1.55,1.62,1.65,1.67],
    status: 'live', version: 'v1.2.3',
    params: { hidden_channels: 128, num_layers: 4, heads: 8, dropout: 0.15, edge_weight: 'correlation' },
    metrics: { 'IS Sharpe': '2.01', 'OOS Sharpe': '1.67', 'Hit Rate': '56.8%', 'Avg Hold': '19.1d', 'Turnover': '21%/mo' }
  },
  {
    id: 'contextual-bandit', category: 'ml', icon: '🎰',
    name: 'Contextual Bandit', type: 'Reinforcement Learning',
    sharpe: 1.52, maxDD: '-12.8%', holding: '1–5d',
    description: 'LinUCB bandit selecting execution strategy (aggressive / neutral / passive) conditioned on regime, liquidity, and urgency.',
    tags: ['P2', 'Execution'],
    sparkline: [0.8,1.0,1.1,1.2,1.3,1.35,1.4,1.48,1.5,1.52],
    status: 'live', version: 'v2.0.1',
    params: { alpha: 1.0, context_dim: 32, exploration: 'linucb', discount: 0.98 },
    metrics: { 'Regret': '0.12', 'Hit Rate': '61.4%', 'Avg Cost': '3.1bps', 'Fill Rate': '94.2%', 'Slippage': '1.8bps' }
  },
  {
    id: 'stat-arb', category: 'statistical', icon: '⚖️',
    name: 'Statistical Arbitrage', type: 'Cointegration Engine',
    sharpe: 1.29, maxDD: '-7.4%', holding: '2–8d',
    description: 'Engle-Granger cointegration scanner across ESG peer groups. Identifies mean-reverting pairs for market-neutral positions.',
    tags: ['Research', 'Market-Neutral'],
    sparkline: [1.0,1.05,1.1,1.15,1.2,1.22,1.25,1.27,1.3,1.29],
    status: 'staging', version: 'v0.9.4',
    params: { lookback: 126, p_value: 0.05, min_halflife: 3, max_halflife: 25, z_entry: 2.0, z_exit: 0.5 },
    metrics: { 'IS Sharpe': '1.58', 'OOS Sharpe': '1.29', 'Pairs Active': '12', 'Avg Hold': '4.7d', 'Beta': '0.03' }
  },
  {
    id: 'factor-model', category: 'factor', icon: '📐',
    name: 'ESG Multi-Factor', type: 'Risk Factor Model',
    sharpe: 1.61, maxDD: '-8.9%', holding: '20–60d',
    description: '9-factor model: Market, Size, Value, Momentum, Quality, Low-Vol, ESG Environmental, ESG Social, ESG Governance. Barra-style.',
    tags: ['P1', 'ESG', 'Factor'],
    sparkline: [1.3,1.35,1.4,1.45,1.5,1.52,1.55,1.58,1.6,1.61],
    status: 'live', version: 'v4.0.0',
    params: { factors: 9, rebalance: 'monthly', neutralize: 'sector+size', esg_tilt: 0.4, max_factor_exp: 2.0 },
    metrics: { 'IS Sharpe': '1.92', 'OOS Sharpe': '1.61', 'IC Mean': '0.048', 'ICIR': '0.81', 'Tracking Error': '4.2%' }
  },
  {
    id: 'sentiment-nlp', category: 'ml', icon: '📰',
    name: 'Sentiment NLP', type: 'Transformer (FinBERT)',
    sharpe: 0.98, maxDD: '-16.2%', holding: '1–3d',
    description: 'Fine-tuned FinBERT on ESG news, earnings calls, and regulatory filings. Generates sentiment scores fed into Alpha Ranker as features.',
    tags: ['P1', 'NLP', 'ESG'],
    sparkline: [0.5,0.6,0.7,0.75,0.8,0.85,0.9,0.92,0.95,0.98],
    status: 'staging', version: 'v1.1.0',
    params: { model: 'ProsusAI/finbert', max_len: 512, batch_size: 32, decay_halflife: '3d', weight_recent: 2.0 },
    metrics: { 'Accuracy': '76.8%', 'F1': '0.74', 'IC Mean': '0.031', 'Avg Lag': '15min', 'Coverage': '94.3%' }
  },
  {
    id: 'momentum-factor', category: 'factor', icon: '🚀',
    name: 'Momentum Alpha', type: 'Cross-Sectional Momentum',
    sharpe: 1.38, maxDD: '-18.5%', holding: '20–60d',
    description: 'Classic 12-1 month cross-sectional momentum with ESG screening. Avoids ESG laggards in top-decile selection.',
    tags: ['Research', 'Momentum'],
    sparkline: [0.9,1.0,1.1,1.2,1.3,1.25,1.3,1.35,1.4,1.38],
    status: 'research', version: 'v2.1.0',
    params: { lookback: 252, skip: 21, decile: 1, esg_screen: 0.2, rebalance: 'monthly' },
    metrics: { 'IS Sharpe': '1.74', 'OOS Sharpe': '1.38', 'Max DD': '-18.5%', 'Win Rate': '52.1%', 'Beta': '0.28' }
  },
];

const CATEGORIES = [
  { key: 'all', label: 'All Models' },
  { key: 'ml', label: 'ML-Based' },
  { key: 'factor', label: 'Factor Models' },
  { key: 'statistical', label: 'Statistical Arb' },
];

const MODEL_TERM_ZH = {
  'XGBoost Ensemble': 'XGBoost 集成',
  'Recurrent Neural Network': '循环神经网络',
  'Hidden Markov Model': '隐马尔可夫模型',
  'Graph Neural Network': '图神经网络',
  'Reinforcement Learning': '强化学习',
  'Cointegration Engine': '协整引擎',
  'Risk Factor Model': '风险因子模型',
  'Transformer (FinBERT)': 'Transformer（FinBERT）',
  'Deep Learning': '深度学习',
  Overlay: '叠加层',
  'Cross-Sectional Momentum': '横截面动量',
};

const MODEL_DESC_ZH = {
  'Gradient-boosted ranking model combining 47 ESG-adjusted factors. Primary signal generator in P1 stack.': '基于梯度提升的排序模型，融合 47 个 ESG 调整因子，是 P1 堆栈的核心信号生成器。',
  'Sequence-to-sequence LSTM trained on 10 years of price/volume data with attention mechanism. Feeds into Alpha Ranker.': '基于注意力机制的序列到序列 LSTM，使用 10 年量价数据训练，并作为 Alpha 排序器的输入。',
  '4-state HMM classifying market regime: Bull / Bear / Sideways / High-Vol. Used to modulate position sizing and factor weights.': '四状态 HMM 用于识别市场状态：牛市 / 熊市 / 震荡 / 高波动，用于调节仓位规模和因子权重。',
  'Graph-based model encoding sector correlations and supply chain relationships. Powers P2 decision engine for position allocation.': '图结构模型编码板块相关性和供应链关系，为 P2 决策引擎提供仓位分配能力。',
  'LinUCB bandit selecting execution strategy (aggressive / neutral / passive) conditioned on regime, liquidity, and urgency.': 'LinUCB 上下文老虎机根据市场状态、流动性和紧迫度选择执行策略（激进 / 中性 / 被动）。',
  'Engle-Granger cointegration scanner across ESG peer groups. Identifies mean-reverting pairs for market-neutral positions.': '基于 Engle-Granger 的协整扫描器覆盖 ESG 同业分组，用于识别适合市场中性的均值回归配对。',
  '9-factor model: Market, Size, Value, Momentum, Quality, Low-Vol, ESG Environmental, ESG Social, ESG Governance. Barra-style.': '九因子模型：市场、规模、价值、动量、质量、低波、ESG 环境、ESG 社会、ESG 治理，采用 Barra 风格框架。',
  'Fine-tuned FinBERT on ESG news, earnings calls, and regulatory filings. Generates sentiment scores fed into Alpha Ranker as features.': '在 ESG 新闻、业绩电话会和监管文件上微调的 FinBERT，会生成情绪分数作为 Alpha 排序器的输入特征。',
  'Classic 12-1 month cross-sectional momentum with ESG screening. Avoids ESG laggards in top-decile selection.': '经典 12-1 月横截面动量策略叠加 ESG 筛选，在高分位选股时规避 ESG 落后者。',
};

let _activeCategory = 'all';
let _activeModelId   = null;

function localizeTerm(value) {
  if (getLang() !== 'zh' || !value) return value;
  return MODEL_TERM_ZH[value] || value;
}

function localizeDescription(value) {
  if (getLang() !== 'zh' || !value) return value;
  return MODEL_DESC_ZH[value] || value;
}

export async function render(container) {
  container.innerHTML = buildShell();
  bindEvents(container);
  renderCatalog(container);
  await Promise.all([loadP1Status(container), loadP2Status(container), loadExperiments(container)]);
}

/* ── Shell ── */
function buildShell() {
  return `
  <div class="page-header">
    <div>
      <div class="page-header__title">Model Registry</div>
      <div class="page-header__sub">Alpha Stack · Decision Engine · Experiments · Catalog</div>
    </div>
    <div class="page-header__actions">
      <button class="btn btn-ghost btn-sm" id="btn-refresh-all">↺ Refresh Status</button>
    </div>
  </div>

  <!-- Stack Status Bar -->
  <div class="model-stack-bar">
    <div class="model-stack-section" id="p1-stack-section">
      <div class="model-stack-label">P1 ALPHA STACK</div>
      <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
        <span id="p1-status-pill" class="live-pill live-pill--off">LOADING</span>
        <div id="p1-components" style="display:flex;gap:8px;flex-wrap:wrap"></div>
        <button class="btn btn-ghost btn-sm" id="btn-run-p1">▶ Run P1</button>
      </div>
    </div>
    <div class="model-stack-divider"></div>
    <div class="model-stack-section" id="p2-stack-section">
      <div class="model-stack-label">P2 DECISION ENGINE</div>
      <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
        <span id="p2-status-pill" class="live-pill live-pill--off">LOADING</span>
        <div id="p2-components" style="display:flex;gap:8px;flex-wrap:wrap"></div>
        <button class="btn btn-ghost btn-sm" id="btn-run-p2">▶ Run P2</button>
      </div>
    </div>
  </div>

  <!-- Run Panels (hidden by default) -->
  <div id="run-panels" class="grid-2" style="display:none;margin-bottom:20px">
    <div class="card" id="p1-run-card" style="display:none">
      <div class="card-header"><span class="card-title">Run P1 Alpha Stack</span>
        <button class="btn btn-ghost btn-sm" id="btn-close-p1">✕</button>
      </div>
      <div class="card-body" style="display:flex;flex-direction:column;gap:12px">
        <div class="form-group">
          <label class="form-label">Universe (blank = default)</label>
          <input class="form-input" id="p1-universe" placeholder="AAPL, MSFT, GOOGL…">
        </div>
        <div class="form-row">
          <div class="form-group">
            <label class="form-label">Horizon (days)</label>
            <input class="form-input" id="p1-horizon" type="number" value="20" min="1">
          </div>
          <div class="form-group">
            <label class="form-label">Capital ($)</label>
            <input class="form-input" id="p1-capital" type="number" value="1000000">
          </div>
        </div>
        <button class="btn btn-primary" id="btn-submit-p1">▶ Submit P1 Run</button>
        <div id="p1-run-result"></div>
      </div>
    </div>
    <div class="card" id="p2-run-card" style="display:none">
      <div class="card-header"><span class="card-title">Run P2 Decision Engine</span>
        <button class="btn btn-ghost btn-sm" id="btn-close-p2">✕</button>
      </div>
      <div class="card-body" style="display:flex;flex-direction:column;gap:12px">
        <div class="form-group">
          <label class="form-label">Universe (blank = default)</label>
          <input class="form-input" id="p2-universe" placeholder="AAPL, MSFT, GOOGL…">
        </div>
        <div class="form-group">
          <label class="form-label">Capital ($)</label>
          <input class="form-input" id="p2-capital" type="number" value="1000000">
        </div>
        <button class="btn btn-primary" id="btn-submit-p2">▶ Submit P2 Run</button>
        <div id="p2-run-result"></div>
      </div>
    </div>
  </div>

  <!-- Catalog Section -->
  <div style="display:flex;gap:20px;align-items:start">
    <!-- Left: Catalog -->
    <div style="flex:1;min-width:0">
      <!-- Filter Bar -->
      <div class="filter-bar" id="filter-bar">
        ${CATEGORIES.map(c => `
          <button class="filter-chip${c.key==='all'?' active':''}" data-cat="${c.key}">${c.label}</button>
        `).join('')}
        <div style="margin-left:auto;display:flex;gap:8px;align-items:center">
          <input class="form-input" id="model-search" placeholder="Search models…" style="width:180px;height:28px;font-size:11px">
        </div>
      </div>

      <!-- Model Grid -->
      <div class="model-catalog-grid" id="model-grid"></div>
    </div>

    <!-- Right: Detail Panel -->
    <div id="model-detail-panel" style="width:0;overflow:hidden;transition:width 0.25s ease;flex-shrink:0"></div>
  </div>

  <!-- Experiments -->
  <div class="results-panel" style="margin-top:24px">
    <div class="results-panel__header">
      <span class="card-title">Experiment History</span>
      <span id="exp-count" style="font-size:10px;color:var(--text-dim);font-family:var(--f-mono)"></span>
    </div>
    <div class="results-panel__body" id="exp-body">
      <div style="padding:24px;text-align:center;color:var(--text-dim);font-size:11px">Loading experiments…</div>
    </div>
  </div>`;
}

/* ── Filter & Catalog ── */
function renderCatalog(container, search = '') {
  const grid = container.querySelector('#model-grid');
  if (!grid) return;

  const filtered = CATALOG.filter(m => {
    const catOk = _activeCategory === 'all' || m.category === _activeCategory;
    const q = search.toLowerCase();
    const searchOk = !q || m.name.toLowerCase().includes(q) || m.type.toLowerCase().includes(q) || m.description.toLowerCase().includes(q);
    return catOk && searchOk;
  });

  grid.innerHTML = filtered.map(m => buildModelCard(m)).join('');

  // Bind card clicks
  grid.querySelectorAll('.model-catalog-card').forEach(card => {
    card.addEventListener('click', () => {
      const id = card.dataset.id;
      _activeModelId = _activeModelId === id ? null : id;
      grid.querySelectorAll('.model-catalog-card').forEach(c => c.classList.toggle('active', c.dataset.id === _activeModelId));
      showDetailPanel(container, _activeModelId ? CATALOG.find(m => m.id === _activeModelId) : null);
    });
  });

  // Draw sparklines after DOM settles
  setTimeout(() => {
    filtered.forEach(m => {
      const canvas = container.querySelector(`#spark-${m.id}`);
      if (canvas) drawSparkline(canvas, m.sparkline, m.sharpe >= 1.5 ? '#00FF88' : m.sharpe >= 1.0 ? '#F0A500' : '#FF4466');
    });
  }, 30);
}

function buildModelCard(m) {
  const statusColor = m.status === 'live' ? 'var(--green)' : m.status === 'staging' ? 'var(--amber)' : 'var(--text-dim)';
  const statusLabel = m.status.toUpperCase();
  const type = localizeTerm(m.type);
  const description = localizeDescription(m.description);
  const tags = m.tags.map(localizeTerm);
  return `
  <div class="model-catalog-card${_activeModelId === m.id ? ' active' : ''}" data-id="${m.id}">
    <div class="mcc-header">
      <div class="mcc-icon">${m.icon}</div>
      <div style="flex:1;min-width:0">
        <div class="mcc-name">${m.name}</div>
        <div class="mcc-type">${type}</div>
      </div>
      <div style="display:flex;flex-direction:column;align-items:flex-end;gap:4px">
        <span style="font-size:9px;font-family:var(--f-mono);color:${statusColor};letter-spacing:0.08em">${statusLabel}</span>
        <span style="font-size:9px;color:var(--text-dim);font-family:var(--f-mono)">${m.version}</span>
      </div>
    </div>
    <div class="mcc-desc">${description}</div>
    <div class="mcc-metrics">
      <div class="mcc-metric">
        <div class="mcc-metric-val" style="color:${m.sharpe>=1.5?'var(--green)':m.sharpe>=1.0?'var(--amber)':'var(--red)'}">${m.sharpe.toFixed(2)}</div>
        <div class="mcc-metric-label">SHARPE</div>
      </div>
      <div class="mcc-metric">
        <div class="mcc-metric-val" style="color:var(--red)">${m.maxDD}</div>
        <div class="mcc-metric-label">MAX DD</div>
      </div>
      <div class="mcc-metric">
        <div class="mcc-metric-val">${m.holding}</div>
        <div class="mcc-metric-label">HOLD</div>
      </div>
      <div style="flex:1;min-width:60px;max-width:80px">
        <canvas id="spark-${m.id}" height="32" style="width:100%;display:block"></canvas>
      </div>
    </div>
    <div class="mcc-tags">
      ${tags.map(t => `<span class="mcc-tag">${t}</span>`).join('')}
    </div>
  </div>`;
}

function showDetailPanel(container, model) {
  const panel = container.querySelector('#model-detail-panel');
  if (!model) {
    panel.style.width = '0';
    setTimeout(() => { panel.innerHTML = ''; }, 250);
    return;
  }
  panel.style.width = '340px';
  panel.innerHTML = buildDetailPanel(model);

  // Performance sparkline in detail
  setTimeout(() => {
    const c = panel.querySelector('#detail-spark');
    if (c) drawSparkline(c, model.sparkline, '#00FF88', true);
  }, 50);

  panel.querySelector('#btn-detail-close')?.addEventListener('click', () => {
    _activeModelId = null;
    container.querySelectorAll('.model-catalog-card').forEach(c => c.classList.remove('active'));
    panel.style.width = '0';
    setTimeout(() => { panel.innerHTML = ''; }, 250);
  });
}

function buildDetailPanel(m) {
  const type = localizeTerm(m.type);
  const description = localizeDescription(m.description);
  const tags = m.tags.map(localizeTerm);
  const paramRows = Object.entries(m.params).map(([k,v]) => `
    <div style="display:flex;justify-content:space-between;padding:5px 0;border-bottom:1px solid var(--border-subtle)">
      <span style="font-size:10px;color:var(--text-dim)">${k}</span>
      <span style="font-size:10px;font-family:var(--f-mono);color:var(--text-primary)">${v}</span>
    </div>`).join('');

  const metricCards = Object.entries(m.metrics).map(([k,v]) => `
    <div style="background:rgba(255,255,255,0.03);border-radius:6px;padding:8px 10px;text-align:center">
      <div style="font-size:13px;font-weight:700;font-family:var(--f-mono);color:var(--green)">${v}</div>
      <div style="font-size:9px;color:var(--text-dim);letter-spacing:0.05em;margin-top:2px">${k}</div>
    </div>`).join('');

  return `
  <div style="background:var(--bg-card);border:1px solid var(--border-subtle);border-radius:12px;height:100%;overflow-y:auto;padding:0">
    <div style="padding:16px 18px;border-bottom:1px solid var(--border-subtle);display:flex;justify-content:space-between;align-items:start;position:sticky;top:0;background:var(--bg-card);z-index:1">
      <div>
        <div style="font-size:20px;margin-bottom:4px">${m.icon}</div>
        <div style="font-family:var(--f-display);font-size:13px;font-weight:700;color:var(--text-primary)">${m.name}</div>
        <div style="font-size:10px;color:var(--text-dim);font-family:var(--f-mono);margin-top:2px">${type} · ${m.version}</div>
      </div>
      <button class="btn btn-ghost btn-sm" id="btn-detail-close" style="padding:4px 8px">✕</button>
    </div>

    <div style="padding:16px 18px;display:flex;flex-direction:column;gap:16px">

      <!-- Sparkline -->
      <div>
        <div style="font-size:9px;color:var(--text-dim);letter-spacing:0.1em;margin-bottom:6px">SHARPE TREND (10 PERIODS)</div>
        <canvas id="detail-spark" height="60" style="width:100%;display:block"></canvas>
      </div>

      <!-- Key Metrics Grid -->
      <div>
        <div style="font-size:9px;color:var(--text-dim);letter-spacing:0.1em;margin-bottom:8px">PERFORMANCE METRICS</div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px">${metricCards}</div>
      </div>

      <!-- Description -->
      <div>
        <div style="font-size:9px;color:var(--text-dim);letter-spacing:0.1em;margin-bottom:6px">DESCRIPTION</div>
        <div style="font-size:11px;color:var(--text-secondary);line-height:1.6">${description}</div>
      </div>

      <!-- Tags -->
      <div style="display:flex;gap:6px;flex-wrap:wrap">
        ${tags.map(t => `<span class="mcc-tag">${t}</span>`).join('')}
      </div>

      <!-- Hyperparameters -->
      <div>
        <div style="font-size:9px;color:var(--text-dim);letter-spacing:0.1em;margin-bottom:8px">HYPERPARAMETERS</div>
        <div>${paramRows}</div>
      </div>

      <!-- Actions -->
      <div style="display:flex;gap:8px;padding-top:8px">
        <button class="btn btn-primary" style="flex:1;font-size:11px">▶ Run in Backtest</button>
        <button class="btn btn-ghost" style="font-size:11px">⬇ Export Config</button>
      </div>

    </div>
  </div>`;
}

function drawSparkline(canvas, data, color = '#00FF88', large = false) {
  const dpr = window.devicePixelRatio || 1;
  const W = canvas.parentElement?.offsetWidth || 80;
  const H = large ? 60 : 32;
  canvas.width = W * dpr;
  canvas.height = H * dpr;
  canvas.style.height = H + 'px';
  const ctx = canvas.getContext('2d');
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, W, H);

  if (!data?.length) return;
  const min = Math.min(...data) * 0.95;
  const max = Math.max(...data) * 1.05;
  const px = i => (i / (data.length - 1)) * (W - 4) + 2;
  const py = v => H - 4 - ((v - min) / (max - min)) * (H - 8);

  // Fill gradient
  const grad = ctx.createLinearGradient(0, 0, 0, H);
  grad.addColorStop(0, color.replace(')', ', 0.25)').replace('rgb', 'rgba').replace('#00FF88', 'rgba(0,255,136,0.25)').replace('#F0A500','rgba(240,165,0,0.25)').replace('#FF4466','rgba(255,68,102,0.25)'));
  grad.addColorStop(1, 'transparent');
  ctx.beginPath();
  data.forEach((v, i) => i === 0 ? ctx.moveTo(px(i), py(v)) : ctx.lineTo(px(i), py(v)));
  ctx.lineTo(px(data.length - 1), H);
  ctx.lineTo(px(0), H);
  ctx.closePath();
  ctx.fillStyle = grad;
  ctx.fill();

  // Line
  ctx.beginPath();
  data.forEach((v, i) => i === 0 ? ctx.moveTo(px(i), py(v)) : ctx.lineTo(px(i), py(v)));
  ctx.strokeStyle = color;
  ctx.lineWidth = large ? 2 : 1.5;
  if (large) { ctx.shadowColor = color; ctx.shadowBlur = 6; }
  ctx.stroke();
  ctx.shadowBlur = 0;

  // End dot
  const lastX = px(data.length - 1), lastY = py(data[data.length - 1]);
  ctx.beginPath();
  ctx.arc(lastX, lastY, large ? 3 : 2, 0, Math.PI * 2);
  ctx.fillStyle = color;
  ctx.fill();
}

/* ── Events ── */
function bindEvents(container) {
  container.querySelector('#btn-refresh-all').addEventListener('click', async () => {
    await Promise.all([loadP1Status(container), loadP2Status(container), loadExperiments(container)]);
    toast.info('Status refreshed');
  });

  container.querySelector('#btn-run-p1').addEventListener('click', () => {
    const card = container.querySelector('#p1-run-card');
    const panels = container.querySelector('#run-panels');
    const isHidden = card.style.display === 'none';
    panels.style.display = 'grid';
    card.style.display = isHidden ? '' : 'none';
    if (!isHidden) checkHidePanels(container);
  });

  container.querySelector('#btn-run-p2').addEventListener('click', () => {
    const card = container.querySelector('#p2-run-card');
    const panels = container.querySelector('#run-panels');
    const isHidden = card.style.display === 'none';
    panels.style.display = 'grid';
    card.style.display = isHidden ? '' : 'none';
    if (!isHidden) checkHidePanels(container);
  });

  container.querySelector('#btn-close-p1').addEventListener('click', () => {
    container.querySelector('#p1-run-card').style.display = 'none';
    checkHidePanels(container);
  });

  container.querySelector('#btn-close-p2').addEventListener('click', () => {
    container.querySelector('#p2-run-card').style.display = 'none';
    checkHidePanels(container);
  });

  container.querySelector('#btn-submit-p1').addEventListener('click', () => submitP1(container));
  container.querySelector('#btn-submit-p2').addEventListener('click', () => submitP2(container));

  // Filter chips
  container.querySelector('#filter-bar').addEventListener('click', e => {
    const chip = e.target.closest('.filter-chip');
    if (!chip) return;
    _activeCategory = chip.dataset.cat;
    container.querySelectorAll('.filter-chip').forEach(c => c.classList.toggle('active', c.dataset.cat === _activeCategory));
    renderCatalog(container, container.querySelector('#model-search').value);
  });

  // Search
  container.querySelector('#model-search').addEventListener('input', e => {
    renderCatalog(container, e.target.value);
  });
}

function checkHidePanels(container) {
  const p1 = container.querySelector('#p1-run-card');
  const p2 = container.querySelector('#p2-run-card');
  if (p1.style.display === 'none' && p2.style.display === 'none') {
    container.querySelector('#run-panels').style.display = 'none';
  }
}

/* ── P1 Status ── */
async function loadP1Status(container) {
  const pill = container.querySelector('#p1-status-pill');
  const compEl = container.querySelector('#p1-components');
  try {
    const data = await api.p1.status();
    const ready = data.ready ?? data.status === 'ready';
    pill.textContent = ready ? 'READY' : 'OFFLINE';
    pill.className = `live-pill${ready ? '' : ' live-pill--off'}`;

    const components = data.components || data.models || [];
    const items = components.length ? components : [
      { label: 'Alpha Ranker', ready: data.alpha_ranker_ready ?? ready },
      { label: 'LSTM Signal',  ready: data.lstm_ready ?? ready },
      { label: 'Calibrator',   ready: data.calibrator_ready ?? ready },
      { label: 'Regime',       ready: data.regime_ready ?? ready },
    ];
    compEl.innerHTML = items.map(c => `
      <div style="display:flex;align-items:center;gap:4px;font-size:10px;font-family:var(--f-mono);color:var(--text-dim)">
        <span style="width:6px;height:6px;border-radius:50%;background:${(c.ready||c.status==='ready')?'var(--green)':'rgba(255,255,255,0.2)'};flex-shrink:0"></span>
        ${c.name||c.label||c.model}
      </div>`).join('');
  } catch {
    pill.textContent = 'ERROR'; pill.className = 'live-pill live-pill--off';
    compEl.innerHTML = '';
  }
}

/* ── P2 Status ── */
async function loadP2Status(container) {
  const pill = container.querySelector('#p2-status-pill');
  const compEl = container.querySelector('#p2-components');
  try {
    const data = await api.p2.status();
    const ready = data.ready ?? data.status === 'ready';
    pill.textContent = ready ? 'READY' : 'OFFLINE';
    pill.className = `live-pill${ready ? '' : ' live-pill--off'}`;

    const components = data.components || data.models || [];
    const items = components.length ? components : [
      { label: 'GNN Engine',  ready: data.gnn_ready ?? ready },
      { label: 'Bandit',      ready: data.bandit_ready ?? ready },
      { label: 'Strategy Sel',ready: data.strategy_selector_ready ?? ready },
      { label: 'Tactic Eng',  ready: data.tactic_engine_ready ?? ready },
    ];
    compEl.innerHTML = items.map(c => `
      <div style="display:flex;align-items:center;gap:4px;font-size:10px;font-family:var(--f-mono);color:var(--text-dim)">
        <span style="width:6px;height:6px;border-radius:50%;background:${(c.ready||c.status==='ready')?'var(--green)':'rgba(255,255,255,0.2)'};flex-shrink:0"></span>
        ${c.name||c.label||c.model}
      </div>`).join('');
  } catch {
    pill.textContent = 'ERROR'; pill.className = 'live-pill live-pill--off';
    compEl.innerHTML = '';
  }
}

/* ── P1 Submit ── */
async function submitP1(container) {
  const btn = container.querySelector('#btn-submit-p1');
  const out = container.querySelector('#p1-run-result');
  btn.disabled = true; btn.textContent = '● Running…';

  const uTxt = container.querySelector('#p1-universe').value.trim();
  const universe = uTxt ? uTxt.split(/[,\s]+/).filter(Boolean).map(s => s.toUpperCase()) : [];
  const horizon = Number(container.querySelector('#p1-horizon').value) || 20;
  const capital = Number(container.querySelector('#p1-capital').value) || 1000000;

  try {
    const res = await api.p1.run({ universe, horizon_days: horizon, capital_base: capital });
    const n = res.signals?.length || 0;
    out.innerHTML = `<div style="font-size:11px;font-family:var(--f-mono);color:var(--green);padding:8px 0">✓ Done · ${n} signals generated</div>`;
    toast.success('P1 stack ran', `${n} signals`);
    loadP1Status(container);
    loadExperiments(container);
  } catch(e) {
    out.innerHTML = `<div style="font-size:11px;font-family:var(--f-mono);color:var(--red);padding:8px 0">${e.message}</div>`;
    toast.error('P1 run failed', e.message);
  } finally {
    btn.disabled = false; btn.textContent = '▶ Submit P1 Run';
  }
}

/* ── P2 Submit ── */
async function submitP2(container) {
  const btn = container.querySelector('#btn-submit-p2');
  const out = container.querySelector('#p2-run-result');
  btn.disabled = true; btn.textContent = '● Running…';

  const uTxt = container.querySelector('#p2-universe').value.trim();
  const universe = uTxt ? uTxt.split(/[,\s]+/).filter(Boolean).map(s => s.toUpperCase()) : [];
  const capital = Number(container.querySelector('#p2-capital').value) || 1000000;

  try {
    const res = await api.p2.run({ universe, capital_base: capital });
    const n = res.decisions?.length || res.positions?.length || 0;
    out.innerHTML = `<div style="font-size:11px;font-family:var(--f-mono);color:var(--green);padding:8px 0">✓ Done · ${n} decisions</div>`;
    toast.success('P2 decision ran', `${n} decisions`);
    loadP2Status(container);
    loadExperiments(container);
  } catch(e) {
    out.innerHTML = `<div style="font-size:11px;font-family:var(--f-mono);color:var(--red);padding:8px 0">${e.message}</div>`;
    toast.error('P2 run failed', e.message);
  } finally {
    btn.disabled = false; btn.textContent = '▶ Submit P2 Run';
  }
}

/* ── Experiments ── */
async function loadExperiments(container) {
  const body = container.querySelector('#exp-body');
  const countEl = container.querySelector('#exp-count');
  try {
    const data = await api.experiments.list();
    const experiments = data.experiments || data || [];
    countEl.textContent = `${experiments.length} runs`;

    if (!experiments.length) {
      body.innerHTML = `
        <div class="empty-state">
          <div class="empty-state__icon">🧪</div>
          <div class="empty-state__title">No experiments yet</div>
          <div class="empty-state__text">Run P1 or P2 stacks to populate the experiment registry.</div>
        </div>`;
      return;
    }

    const rows = experiments.map(e => {
      const status = e.status || 'unknown';
      const cls = status === 'completed' ? 'filled' : status === 'running' ? 'pending' : status === 'failed' ? 'failed' : 'neutral';
      return `
        <tr>
          <td style="font-family:var(--f-mono);font-size:10px;max-width:130px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${e.experiment_id || e.id || '—'}</td>
          <td style="font-size:11px;color:var(--text-dim)">${e.experiment_type || e.type || '—'}</td>
          <td><span class="badge badge-${cls}">${status.toUpperCase()}</span></td>
          <td class="cell-num">${e.signals_generated ?? e.num_signals ?? '—'}</td>
          <td class="cell-num ${(e.sharpe||0)>=1?'pos':''}">${e.sharpe != null ? Number(e.sharpe).toFixed(2) : '—'}</td>
          <td class="cell-num">${e.alpha_score != null ? Number(e.alpha_score).toFixed(3) : '—'}</td>
          <td style="font-size:10px;font-family:var(--f-mono);color:var(--text-dim)">${shortDate(e.created_at)}</td>
        </tr>`;
    }).join('');

    body.innerHTML = `<div class="tbl-wrap"><table>
      <thead><tr>
        <th>Experiment ID</th><th>Type</th><th>Status</th>
        <th>Signals</th><th>Sharpe</th><th>Alpha</th><th>Created</th>
      </tr></thead>
      <tbody>${rows}</tbody>
    </table></div>`;
  } catch(e) {
    countEl.textContent = '';
    body.innerHTML = `
      <div class="empty-state">
        <div class="empty-state__title">Could not load experiments</div>
        <div class="empty-state__text">${e.message}</div>
      </div>`;
  }
}

function shortDate(iso) {
  if (!iso) return '';
  try { return new Date(iso).toLocaleString(getLocale(), { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }); }
  catch { return iso; }
}
