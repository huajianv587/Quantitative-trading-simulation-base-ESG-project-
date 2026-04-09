/**
 * 旗舰总览首页
 * 以 Apple 风格的叙事编排展示 ESG 信号、系统能力和功能入口
 */

import { api } from '../api.js';
import { formatDate, relativeTime, getStorage, setStorage } from '../utils.js';

let cleanup = [];
let refreshTimer = null;

const RECENT_QUERY_KEY = 'esg_recent_queries';
const PENDING_PROMPT_KEY = 'esg_pending_prompt';
const PENDING_PROMPT_AUTOSEND_KEY = 'esg_pending_prompt_autosend';
const PENDING_SCORE_KEY = 'esg_pending_score_lookup';

const DEFAULT_HOT_QUESTIONS = [
  '特斯拉的环保政策评分是多少？',
  '苹果与微软的社会责任对标分析',
  '最近 ESG 相关风险事件有哪些？',
  'SEC 披露规则变化会影响哪些公司？',
];

const COMMAND_SURFACES = [
  {
    route: '/research',
    eyebrow: 'Research',
    title: 'Research Lab',
    description: '把 ESG、质量、估值与另类数据汇总成一轮完整量化研究。',
    accent: 'cyan',
    stat: '信号生产',
  },
  {
    route: '/portfolio',
    eyebrow: 'Portfolio',
    title: 'Portfolio Lab',
    description: '生成组合建议、仓位配置和 Paper Trading 执行清单。',
    accent: 'emerald',
    stat: '组合优化',
  },
  {
    route: '/backtests',
    eyebrow: 'Validation',
    title: 'Backtest Center',
    description: '执行样本内外回测，查看收益、回撤与风险告警。',
    accent: 'amber',
    stat: '策略验证',
  },
  {
    route: '/chat',
    eyebrow: 'Conversation',
    title: 'ESG Copilot',
    description: '在 Agent 对话界面里做企业 ESG 深挖和问答追踪。',
    accent: 'violet',
    stat: 'Agent 研究',
  },
  {
    route: '/score',
    eyebrow: 'Scoring',
    title: 'Score Lab',
    description: '生成结构化评分、维度拆解和可视化，适合深度研判。',
    accent: 'rose',
    stat: '结构评分',
  },
  {
    route: '/reports',
    eyebrow: 'Reporting',
    title: '报告中心',
    description: '集中查看日报、周报和月报，把观察升级成正式输出。',
    accent: 'blue',
    stat: '周期报告',
  },
  {
    route: '/data',
    eyebrow: 'Pipeline',
    title: 'Data Hub',
    description: '管理数据源刷新、调度节奏和底层采集链路健康度。',
    accent: 'blue',
    stat: '数据底座',
  },
  {
    route: '/push-rules',
    eyebrow: 'Automation',
    title: '推送规则',
    description: '配置预警策略，把高风险 ESG 事件主动送到决策面前。',
    accent: 'rose',
    stat: '智能触达',
  },
  {
    route: '/subscriptions',
    eyebrow: 'Follow-up',
    title: '订阅管理',
    description: '针对重点公司建立长期跟踪机制，持续追踪关键变化。',
    accent: 'blue',
    stat: '持续跟踪',
  },
];

export async function render(container) {
  container.innerHTML = buildHTML();
  bindQueryConsole(container);
  await loadOverview(container);

  refreshTimer = window.setInterval(() => {
    loadOverview(container, true);
  }, 90000);
}

export function destroy() {
  cleanup.forEach((fn) => fn());
  cleanup = [];

  if (refreshTimer) {
    window.clearInterval(refreshTimer);
    refreshTimer = null;
  }
}

function buildHTML() {
  return `
    <div class="page-stack overview-page">
      <section class="overview-hero card" data-hover-glow="true">
        <div class="overview-hero__content">
          <div class="overview-kicker">Flagship Experience</div>
          <h1 id="overview-headline" class="overview-title">ESG 智能中枢。</h1>
          <p id="overview-subheadline" class="overview-subheadline">
            把最新 ESG 情报、风险线索和执行入口收束成一个高端总览页面。
          </p>
          <p id="overview-summary" class="overview-summary">
            像旗舰发布页一样编排信息，第一眼看到最新脉搏，第二步进入分析与行动。
          </p>

          <div class="overview-cta">
            <a href="#/chat" class="btn-primary overview-btn" data-hover-glow="true">进入 ESG 对话</a>
            <a href="#/score" class="btn-secondary overview-btn" data-hover-glow="true">查看结构评分</a>
          </div>

          <div id="overview-metrics" class="overview-stat-grid"></div>
        </div>

        <div class="overview-hero__visual" data-hover-glow="true">
          <div class="overview-hero__halo"></div>
          <div class="overview-hero__orbital overview-hero__orbital--a"></div>
          <div class="overview-hero__orbital overview-hero__orbital--b"></div>
          <div class="overview-hero__grid"></div>

          <div class="overview-glass-panel">
            <div class="overview-glass-panel__kicker">Spotlight</div>
            <div id="overview-spotlight"></div>
          </div>

          <div class="overview-hero__foot">
            <span class="overview-source-dot"></span>
            <span id="overview-source-chip">Connecting live feed</span>
          </div>
        </div>
      </section>

      <section class="overview-architecture card" data-hover-glow="true">
        <div class="overview-section-head">
          <div>
            <div class="overview-section-head__kicker">Architecture Fabric</div>
            <h2>把蓝图里的 8 层能力真正映射成可运行产品面</h2>
          </div>
          <p>直接查看数据接入、治理、分析、模型、Agent、风控、回测和交付层的就绪状态，以及当前存储、组合、回测和训练路径。</p>
        </div>
        <div class="overview-architecture__grid">
          <div id="overview-layer-grid" class="overview-layer-grid"></div>
          <div id="overview-runtime-grid" class="overview-runtime-grid"></div>
        </div>
      </section>

      <section class="overview-query-stage card" data-hover-glow="true">
        <div class="overview-section-head">
          <div>
            <div class="overview-section-head__kicker">QueryInterface</div>
            <h2>智能查询界面</h2>
          </div>
          <p>把公司名、问题、热门话题与最近搜索收束成一个真正像旗舰产品的查询入口。</p>
        </div>

        <div class="query-interface-grid">
          <div class="query-console-panel">
            <div class="query-console-panel__eyebrow">智能搜索</div>
            <div class="query-console-shell" data-hover-glow="true">
              <div class="query-console-shell__label">请输入公司名称或 ESG 相关问题</div>
              <div class="query-console-shell__field">
                <span class="query-console-shell__icon">⌕</span>
                <input id="overview-query-input" type="text" placeholder="例如：分析特斯拉的 ESG 表现，或输入 Apple / Microsoft" />
              </div>
              <div class="query-console-shell__actions">
                <button id="overview-query-chat" class="btn-primary">进入 ESG 对话</button>
                <button id="overview-query-score" class="btn-secondary">打开评分看板</button>
              </div>
            </div>

            <div class="query-chip-group">
              <div class="query-chip-group__title">热门问题</div>
              <div id="overview-hot-questions" class="query-chip-list"></div>
            </div>
          </div>

          <div class="query-history-panel">
            <div class="query-history-panel__head">
              <div>
                <div class="query-history-panel__eyebrow">Recent Search</div>
                <h3>上次搜索</h3>
              </div>
              <span class="query-history-panel__hint">支持一键复用</span>
            </div>
            <div id="overview-recent-queries" class="query-history-list"></div>
            <div class="query-history-panel__divider"></div>
            <div>
              <div class="query-history-panel__eyebrow">System Readiness</div>
              <div id="overview-health-grid" class="overview-health-grid overview-health-grid--compact"></div>
            </div>
          </div>
        </div>
      </section>

      <section class="overview-scoreboard card" data-hover-glow="true">
        <div class="overview-section-head">
          <div>
            <div class="overview-section-head__kicker">ScoreBoard</div>
            <h2>ESG 评分看板</h2>
          </div>
          <p>综合评分、三维拆解、雷达图与趋势图在同一屏内形成专业驾驶舱视角。</p>
        </div>
        <div class="overview-scoreboard__grid">
          <div id="overview-score-summary" class="scoreboard-summary"></div>
          <div id="overview-score-visual" class="scoreboard-visual"></div>
          <div id="overview-score-trend" class="scoreboard-trend"></div>
        </div>
      </section>

      <section class="overview-monitor card" data-hover-glow="true">
        <div class="overview-section-head">
          <div>
            <div class="overview-section-head__kicker">EventMonitor</div>
            <h2>ESG 事件监测</h2>
          </div>
          <p>最近 7 天的风险事件、推荐措施和时间线视图统一编排，便于快速判断优先级。</p>
        </div>
        <div id="overview-risk-summary" class="monitor-risk-grid"></div>
        <div class="overview-monitor__grid">
          <div id="overview-event-list" class="monitor-event-list"></div>
          <div id="overview-event-timeline" class="monitor-timeline-shell"></div>
        </div>
      </section>

      <section class="overview-band card" data-hover-glow="true">
        <div class="overview-section-head">
          <div>
            <div class="overview-section-head__kicker">Recent ESG Pulse</div>
            <h2>最近的 ESG 信息流</h2>
          </div>
          <p>以旗舰播片的方式展示最近进入系统视野的 ESG 信号。</p>
        </div>
        <div id="overview-signal-rail" class="signal-rail"></div>
      </section>

      <section class="overview-command-deck">
        <div class="overview-section-head">
          <div>
            <div class="overview-section-head__kicker">Feature Matrix</div>
            <h2>所有能力，一屏直达</h2>
          </div>
          <p>借鉴 Apple 官网的大卡片编排，但服务于 ESG 智能工作流。</p>
        </div>
        <div id="overview-command-grid" class="overview-command-grid"></div>
      </section>
    </div>
  `;
}

async function loadOverview(container, silent = false) {
  try {
    const [dashboardResult, quantResult] = await Promise.allSettled([
      api.dashboard.overview(),
      api.quant.overview(),
    ]);

    const data = mergeOverviewPayload(
      dashboardResult.status === 'fulfilled' ? dashboardResult.value : null,
      quantResult.status === 'fulfilled' ? quantResult.value : null,
    );
    hydrateOverview(container, data || getFallbackOverview());
  } catch (error) {
    console.warn('旗舰页数据加载失败，使用回退数据', error);
    hydrateOverview(container, getFallbackOverview());
  }
}

function hydrateOverview(container, data) {
  container.querySelector('#overview-headline').textContent =
    data.narrative?.headline || 'ESG 智能中枢。';
  container.querySelector('#overview-subheadline').textContent =
    data.narrative?.subheadline || '把最近 ESG 情报做成一套旗舰级的信息体验。';
  container.querySelector('#overview-summary').textContent =
    data.narrative?.summary || '在一个总览页面中掌握最新 ESG 动态与关键操作入口。';

  renderMetrics(container.querySelector('#overview-metrics'), data.metrics || []);
  renderSpotlight(container.querySelector('#overview-spotlight'), data.spotlight);
  renderArchitecture(container, data.quantPlatform || data.quant_platform);
  renderQueryInterface(container, data.query_interface || {});
  renderSignals(container.querySelector('#overview-signal-rail'), data.signals || []);
  renderHealth(container.querySelector('#overview-health-grid'), data.health || {});
  renderScoreboard(container, data.score_snapshot || buildDerivedScoreSnapshot(data));
  renderEventMonitor(container, data.event_monitor || buildDerivedEventMonitor(data));
  renderCommandDeck(container.querySelector('#overview-command-grid'));

  const sourceChip = container.querySelector('#overview-source-chip');
  sourceChip.textContent = buildSourceText(data);
}

function mergeOverviewPayload(dashboardData, quantData) {
  const base = dashboardData || getFallbackOverview();
  const quantPlatform = quantData || getFallbackQuantOverview();

  return {
    ...base,
    quantPlatform,
  };
}

function bindQueryConsole(container) {
  const input = container.querySelector('#overview-query-input');
  const chatBtn = container.querySelector('#overview-query-chat');
  const scoreBtn = container.querySelector('#overview-query-score');
  const hotList = container.querySelector('#overview-hot-questions');
  const recentList = container.querySelector('#overview-recent-queries');

  const openChat = () => {
    const prompt = input.value.trim();
    if (!prompt) return;
    queuePromptForChat(prompt);
  };

  const openScore = () => {
    const prompt = input.value.trim();
    if (!prompt) return;
    const company = extractCompanyName(prompt);
    recordRecentQuery(prompt, 'score');
    setStorage(PENDING_SCORE_KEY, {
      company,
      rawPrompt: prompt,
      createdAt: new Date().toISOString(),
    });
    window.location.hash = '#/score';
  };

  const onKeydown = (event) => {
    if (event.key === 'Enter') {
      event.preventDefault();
      openChat();
    }
  };

  const onHotClick = (event) => {
    const button = event.target.closest('[data-prompt]');
    if (!button) return;
    queuePromptForChat(button.dataset.prompt || '');
  };

  const onRecentClick = (event) => {
    const button = event.target.closest('[data-recent-query]');
    if (!button) return;
    const prompt = button.dataset.recentQuery || '';
    const mode = button.dataset.mode || 'chat';
    if (mode === 'score') {
      input.value = prompt;
      openScore();
      return;
    }
    queuePromptForChat(prompt);
  };

  chatBtn.addEventListener('click', openChat);
  scoreBtn.addEventListener('click', openScore);
  input.addEventListener('keydown', onKeydown);
  hotList.addEventListener('click', onHotClick);
  recentList.addEventListener('click', onRecentClick);

  cleanup.push(() => chatBtn.removeEventListener('click', openChat));
  cleanup.push(() => scoreBtn.removeEventListener('click', openScore));
  cleanup.push(() => input.removeEventListener('keydown', onKeydown));
  cleanup.push(() => hotList.removeEventListener('click', onHotClick));
  cleanup.push(() => recentList.removeEventListener('click', onRecentClick));
}

function renderQueryInterface(container, queryData) {
  const hotQuestions = queryData.hot_questions?.length
    ? queryData.hot_questions
    : DEFAULT_HOT_QUESTIONS;

  const hotList = container.querySelector('#overview-hot-questions');
  hotList.innerHTML = hotQuestions.map((question) => `
    <button class="query-chip" type="button" data-prompt="${escapeHtml(question)}">
      ${escapeHtml(question)}
    </button>
  `).join('');

  renderRecentQueries(container.querySelector('#overview-recent-queries'));
}

function renderRecentQueries(target) {
  if (!target) return;
  const items = getRecentQueries();

  if (items.length === 0) {
    target.innerHTML = `
      <div class="query-history-empty">
        这里会记录你最近发起过的 ESG 查询和评分动作。
      </div>
    `;
    return;
  }

  target.innerHTML = items.map((item) => `
    <button
      class="query-history-item"
      type="button"
      data-recent-query="${escapeHtml(item.query)}"
      data-mode="${escapeHtml(item.mode || 'chat')}"
    >
      <div class="query-history-item__icon">${item.mode === 'score' ? '★' : '✓'}</div>
      <div class="query-history-item__body">
        <div class="query-history-item__title">${escapeHtml(item.query)}</div>
        <div class="query-history-item__meta">
          <span>${item.mode === 'score' ? '评分看板' : 'ESG 对话'}</span>
          <span>${escapeHtml(formatDate(item.createdAt, 'YYYY-MM-DD HH:mm'))}</span>
        </div>
      </div>
    </button>
  `).join('');
}

function renderMetrics(target, metrics) {
  target.innerHTML = metrics.map((metric) => `
    <div class="overview-stat" data-hover-glow="true">
      <div class="overview-stat__label">${escapeHtml(metric.label || '')}</div>
      <div class="overview-stat__value">
        ${escapeHtml(String(metric.value ?? 0))}
        <span class="overview-stat__suffix">${escapeHtml(metric.suffix || '')}</span>
      </div>
      <div class="overview-stat__hint">${escapeHtml(metric.hint || '')}</div>
    </div>
  `).join('');
}

function renderSpotlight(target, spotlight) {
  const item = spotlight || getFallbackOverview().spotlight;
  target.innerHTML = `
    <div class="overview-spotlight__company">${escapeHtml(item.company || 'ESG Pulse')}</div>
    <h3 class="overview-spotlight__title">${escapeHtml(item.title || '最新 ESG 信号已进入视野')}</h3>
    <p class="overview-spotlight__description">${escapeHtml(item.description || '')}</p>
    <div class="overview-spotlight__meta">
      <span class="overview-pill overview-pill--${escapeHtml((item.tone || 'neutral'))}">
        ${escapeHtml(toneLabel(item.tone))}
      </span>
      <span>${escapeHtml(item.event_type || 'UPDATE')}</span>
      <span>${escapeHtml(relativeTime(item.detected_at || new Date().toISOString()))}</span>
    </div>
  `;
}

function renderSignals(target, signals) {
  const items = signals.length > 0 ? signals : getFallbackOverview().signals;
  const cards = [...items, ...items].map((item, index) => `
    <article class="signal-card" data-hover-glow="true">
      <div class="signal-card__top">
        <span class="overview-pill overview-pill--${escapeHtml(item.tone || 'neutral')}">${escapeHtml(toneLabel(item.tone))}</span>
        <span class="signal-card__time">${escapeHtml(relativeTime(item.detected_at || new Date().toISOString()))}</span>
      </div>
      <div class="signal-card__company">${escapeHtml(item.company || 'ESG Pulse')}</div>
      <h3 class="signal-card__title">${escapeHtml(item.title || '最新 ESG 事件')}</h3>
      <p class="signal-card__description">${escapeHtml(item.description || '')}</p>
      <div class="signal-card__meta">
        <span>${escapeHtml(item.event_type || 'UPDATE')}</span>
        <span>${escapeHtml(item.source || 'live')}</span>
      </div>
    </article>
  `).join('');

  target.innerHTML = `
    <div class="signal-rail__fade signal-rail__fade--left"></div>
    <div class="signal-rail__fade signal-rail__fade--right"></div>
    <div class="signal-rail__viewport">
      <div class="signal-rail__track">
        ${cards}
      </div>
    </div>
  `;
}

function renderHealth(target, health) {
  const modules = [
    { key: 'rag', label: 'RAG 检索' },
    { key: 'esg_scorer', label: 'ESG 评分' },
    { key: 'report_scheduler', label: '调度器' },
    { key: 'data_sources', label: '数据源' },
  ];

  target.innerHTML = modules.map((module) => {
    const ready = Boolean(health[module.key]);
    return `
      <div class="overview-health-card ${ready ? 'is-ready' : 'is-pending'}">
        <span class="overview-health-card__dot"></span>
        <div>
          <div class="overview-health-card__label">${module.label}</div>
          <div class="overview-health-card__value">${ready ? 'Online' : 'Standby'}</div>
        </div>
      </div>
    `;
  }).join('');
}

function renderArchitecture(container, quantPlatform) {
  const fallback = getFallbackQuantOverview();
  const data = quantPlatform || fallback;
  const layers = data.architecture_layers?.length ? data.architecture_layers : fallback.architecture_layers;
  const storage = data.storage || fallback.storage;
  const portfolio = data.portfolio_preview || fallback.portfolio_preview;
  const backtestMetrics = data.latest_backtest?.metrics || fallback.latest_backtest.metrics;
  const training = data.training_plan || fallback.training_plan;

  const layerGrid = container.querySelector('#overview-layer-grid');
  const runtimeGrid = container.querySelector('#overview-runtime-grid');

  layerGrid.innerHTML = layers.map((layer) => `
    <article class="overview-layer-card ${layer.ready ? 'is-ready' : 'is-pending'}" data-hover-glow="true">
      <div class="overview-layer-card__top">
        <span class="overview-layer-card__key">${escapeHtml(String(layer.key || '').toUpperCase())}</span>
        <span class="overview-layer-card__priority">${escapeHtml(layer.priority || 'P1')}</span>
      </div>
      <h3>${escapeHtml(layer.label || '系统层')}</h3>
      <p>${escapeHtml(layer.detail || '')}</p>
      <div class="overview-layer-card__status">
        <span class="overview-layer-card__dot"></span>
        <span>${layer.ready ? 'Ready' : 'Pending'}</span>
      </div>
    </article>
  `).join('');

  runtimeGrid.innerHTML = `
    <article class="overview-runtime-card" data-hover-glow="true">
      <div class="overview-runtime-card__eyebrow">Storage Fabric</div>
      <div class="overview-runtime-card__value">${escapeHtml(storageLabel(storage.mode))}</div>
      <div class="overview-runtime-card__meta">
        <span>${storage.supabase_ready ? 'Supabase DB online' : 'Supabase DB standby'}</span>
        <span>${escapeHtml(artifactBackendLabel(storage))}</span>
      </div>
    </article>

    <article class="overview-runtime-card" data-hover-glow="true">
      <div class="overview-runtime-card__eyebrow">Portfolio Loop</div>
      <div class="overview-runtime-card__value">${portfolio.positions?.length || 0} positions</div>
      <div class="overview-runtime-card__meta">
        <span>Benchmark ${escapeHtml(portfolio.benchmark || 'SPY')}</span>
        <span>Alpha ${formatPercent(portfolio.expected_alpha, 2)}</span>
        <span>Gross ${formatPercent(portfolio.gross_exposure, 1)}</span>
      </div>
    </article>

    <article class="overview-runtime-card" data-hover-glow="true">
      <div class="overview-runtime-card__eyebrow">Validation Kernel</div>
      <div class="overview-runtime-card__value">Sharpe ${escapeHtml(String(backtestMetrics.sharpe ?? 0))}</div>
      <div class="overview-runtime-card__meta">
        <span>MDD ${formatPercent(backtestMetrics.max_drawdown, 2)}</span>
        <span>CVaR ${formatPercent(backtestMetrics.cvar_95, 2)}</span>
        <span>IR ${escapeHtml(String(backtestMetrics.information_ratio ?? 0))}</span>
      </div>
    </article>

    <article class="overview-runtime-card" data-hover-glow="true">
      <div class="overview-runtime-card__eyebrow">Training Roadmap</div>
      <div class="overview-runtime-card__value">${training.remote_ready ? 'Remote Ready' : 'Local First'}</div>
      <div class="overview-runtime-card__detail">${escapeHtml(training.adapter_strategy || '')}</div>
      <div class="overview-runtime-card__meta">
        <span>${escapeHtml(training.target_environment || 'Cloud RTX 5090 Finetune Node')}</span>
      </div>
    </article>
  `;
}

function renderScoreboard(container, snapshot) {
  const data = snapshot || getFallbackOverview().score_snapshot;
  const summaryTarget = container.querySelector('#overview-score-summary');
  const visualTarget = container.querySelector('#overview-score-visual');
  const trendTarget = container.querySelector('#overview-score-trend');

  summaryTarget.innerHTML = `
    <div class="scoreboard-summary__card" data-hover-glow="true">
      <div class="scoreboard-summary__eyebrow">${escapeHtml(data.company)} 的 ESG 评分</div>
      <div class="scoreboard-summary__score">
        <span>${escapeHtml(String(data.overall_score ?? 0))}</span>
        <small>/100</small>
      </div>
      <div class="scoreboard-summary__confidence">
        置信度 <strong>${Math.round((data.confidence || 0) * 100)}%</strong>
      </div>
      <div class="scoreboard-dimension-list">
        ${(data.dimensions || []).map((dimension) => `
          <div class="scoreboard-dimension">
            <div class="scoreboard-dimension__head">
              <span>${escapeHtml(dimension.label)} (${escapeHtml(dimension.key)})</span>
              <span>${escapeHtml(String(dimension.score))}/100</span>
            </div>
            <div class="scoreboard-dimension__bar">
              <span class="scoreboard-dimension__fill scoreboard-dimension__fill--${escapeHtml(dimension.key.toLowerCase())}" style="width: ${Math.max(6, Number(dimension.score || 0))}%"></span>
            </div>
          </div>
        `).join('')}
      </div>
    </div>
  `;

  visualTarget.innerHTML = `
    <div class="scoreboard-visual__gauge" data-hover-glow="true">
      <div class="score-orbit" style="--score:${Number(data.overall_score || 0)}">
        <div class="score-orbit__core">
          <span>${escapeHtml(String(data.overall_score || 0))}</span>
          <small>综合评分</small>
        </div>
      </div>
    </div>
    <div class="scoreboard-visual__radar" data-hover-glow="true">
      <div class="scoreboard-visual__title">维度雷达</div>
      ${createRadarMarkup(data.radar || [])}
    </div>
  `;

  trendTarget.innerHTML = `
    <div class="scoreboard-trend__card" data-hover-glow="true">
      <div class="scoreboard-trend__head">
        <div>
          <div class="scoreboard-trend__eyebrow">Trend View</div>
          <h3>评分趋势</h3>
        </div>
        <div class="scoreboard-trend__legend">
          <span><i class="legend-dot legend-dot--e"></i>E 维度</span>
          <span><i class="legend-dot legend-dot--s"></i>S 维度</span>
          <span><i class="legend-dot legend-dot--g"></i>G 维度</span>
        </div>
      </div>
      ${createTrendChart(data.trend || [])}
    </div>
  `;
}

function renderEventMonitor(container, monitorData) {
  const data = monitorData || getFallbackOverview().event_monitor;
  renderRiskSummary(container.querySelector('#overview-risk-summary'), data.risk_counts || {});
  renderEventList(container.querySelector('#overview-event-list'), data.events || []);
  renderEventTimeline(container.querySelector('#overview-event-timeline'), data);
}

function renderRiskSummary(target, riskCounts) {
  const summary = [
    { key: 'high', label: '高风险', value: riskCounts.high ?? 0 },
    { key: 'medium', label: '中风险', value: riskCounts.medium ?? 0 },
    { key: 'low', label: '低风险', value: riskCounts.low ?? 0 },
  ];

  target.innerHTML = summary.map((item) => `
    <div class="monitor-risk-card monitor-risk-card--${item.key}" data-hover-glow="true">
      <div class="monitor-risk-card__label">${item.label}</div>
      <div class="monitor-risk-card__value">${item.value}</div>
    </div>
  `).join('');
}

function renderEventList(target, events) {
  const items = events.length ? events : getFallbackOverview().event_monitor.events;

  target.innerHTML = items.map((item) => `
    <article class="monitor-event-card" data-hover-glow="true">
      <div class="monitor-event-card__head">
        <span class="overview-pill overview-pill--${escapeHtml(levelTone(item.level))}">
          ${escapeHtml(levelLabel(item.level))}
        </span>
        <span class="monitor-event-card__score">${escapeHtml(String(item.risk_score || 0))}/100</span>
      </div>
      <h3>${escapeHtml(item.company || '市场观察')} · ${escapeHtml(item.title || 'ESG 事件')}</h3>
      <p>${escapeHtml(item.description || '')}</p>
      <div class="monitor-event-card__meta">
        <span>${escapeHtml(formatDate(item.published_at || new Date().toISOString(), 'YYYY-MM-DD HH:mm'))}</span>
        <span>${escapeHtml(item.positive ? '正面事件' : '风险跟踪')}</span>
      </div>
      <div class="monitor-event-card__recommendation">
        推荐措施：${escapeHtml(item.recommendation || '持续跟踪后续披露与执行动作。')}
      </div>
    </article>
  `).join('');
}

function renderEventTimeline(target, monitorData) {
  const timeline = monitorData.timeline?.length
    ? monitorData.timeline
    : getFallbackOverview().event_monitor.timeline;

  target.innerHTML = `
    <div class="monitor-timeline-card" data-hover-glow="true">
      <div class="monitor-timeline-card__head">
        <div>
          <div class="scoreboard-trend__eyebrow">Timeline</div>
          <h3>${escapeHtml(monitorData.period_label || '最近 7 天')}</h3>
        </div>
        <div class="monitor-timeline-card__caption">事件时间线视图</div>
      </div>
      <div class="monitor-timeline-line">
        ${timeline.map((item) => `
          <div class="monitor-timeline-node monitor-timeline-node--${escapeHtml(item.level || 'medium')}">
            <span class="monitor-timeline-node__dot"></span>
            <span class="monitor-timeline-node__date">${escapeHtml(item.date_label || '')}</span>
            <span class="monitor-timeline-node__company">${escapeHtml(item.company || '')}</span>
          </div>
        `).join('')}
      </div>
    </div>
  `;
}

function renderCommandDeck(target) {
  target.innerHTML = COMMAND_SURFACES.map((surface, index) => `
    <a href="#${surface.route}" class="overview-command-card overview-command-card--${surface.accent}" data-hover-glow="true">
      <div class="overview-command-card__eyebrow">${surface.eyebrow}</div>
      <div class="overview-command-card__index">0${index + 1}</div>
      <h3>${surface.title}</h3>
      <p>${surface.description}</p>
      <div class="overview-command-card__foot">
        <span>${surface.stat}</span>
        <span>打开</span>
      </div>
    </a>
  `).join('');
}

function queuePromptForChat(prompt) {
  const cleanPrompt = prompt.trim();
  if (!cleanPrompt) return;

  recordRecentQuery(cleanPrompt, 'chat');
  setStorage(PENDING_PROMPT_KEY, cleanPrompt);
  setStorage(PENDING_PROMPT_AUTOSEND_KEY, true);
  window.location.hash = '#/chat';
}

function recordRecentQuery(query, mode = 'chat') {
  const items = getRecentQueries().filter((item) => item.query !== query);
  items.unshift({
    query,
    mode,
    createdAt: new Date().toISOString(),
  });
  setStorage(RECENT_QUERY_KEY, items.slice(0, 6));
}

function getRecentQueries() {
  return getStorage(RECENT_QUERY_KEY, []);
}

function extractCompanyName(prompt) {
  const knownCompanies = ['Tesla', 'Apple', 'Microsoft', 'NVIDIA', 'Google', 'Meta', 'Amazon', 'SEC'];
  const found = knownCompanies.find((company) => prompt.toLowerCase().includes(company.toLowerCase()));
  if (found) return found;

  return prompt
    .replace(/[?？。！!]/g, '')
    .split(/[\s,，]/)
    .find(Boolean) || prompt;
}

function levelLabel(level) {
  return {
    high: '高风险',
    medium: '中风险',
    low: '低风险',
  }[level] || '观察中';
}

function levelTone(level) {
  return {
    high: 'alert',
    medium: 'neutral',
    low: 'positive',
  }[level] || 'neutral';
}

function createRadarMarkup(metrics) {
  const items = metrics.length ? metrics : getFallbackOverview().score_snapshot.radar;
  const size = 280;
  const center = 140;
  const radius = 78;
  const labelRadius = 114;
  const angleStep = (Math.PI * 2) / items.length;

  const gridPolygons = [0.33, 0.66, 1].map((ratio) => {
    const points = items.map((_, index) => {
      const angle = -Math.PI / 2 + index * angleStep;
      const x = center + Math.cos(angle) * radius * ratio;
      const y = center + Math.sin(angle) * radius * ratio;
      return `${x},${y}`;
    }).join(' ');
    return `<polygon points="${points}" class="score-radar__grid" />`;
  }).join('');

  const axisLines = items.map((item, index) => {
    const angle = -Math.PI / 2 + index * angleStep;
    const x = center + Math.cos(angle) * radius;
    const y = center + Math.sin(angle) * radius;
    const labelX = center + Math.cos(angle) * labelRadius;
    const labelY = center + Math.sin(angle) * labelRadius;
    return `
      <line x1="${center}" y1="${center}" x2="${x}" y2="${y}" class="score-radar__axis" />
      <text x="${labelX}" y="${labelY}" class="score-radar__label">${escapeHtml(item.label)}</text>
    `;
  }).join('');

  const valuePoints = items.map((item, index) => {
    const angle = -Math.PI / 2 + index * angleStep;
    const distance = radius * (Math.max(0, Math.min(100, Number(item.value || 0))) / 100);
    const x = center + Math.cos(angle) * distance;
    const y = center + Math.sin(angle) * distance;
    return `${x},${y}`;
  }).join(' ');

  const dots = items.map((item, index) => {
    const angle = -Math.PI / 2 + index * angleStep;
    const distance = radius * (Math.max(0, Math.min(100, Number(item.value || 0))) / 100);
    const x = center + Math.cos(angle) * distance;
    const y = center + Math.sin(angle) * distance;
    return `<circle cx="${x}" cy="${y}" r="4" class="score-radar__dot" />`;
  }).join('');

  return `
    <svg viewBox="0 0 ${size} ${size}" class="score-radar" aria-hidden="true">
      ${gridPolygons}
      ${axisLines}
      <polygon points="${valuePoints}" class="score-radar__shape" />
      ${dots}
    </svg>
  `;
}

function createTrendChart(trend) {
  const items = trend.length ? trend : getFallbackOverview().score_snapshot.trend;
  const width = 520;
  const height = 200;
  const paddingX = 24;
  const paddingY = 22;
  const minScore = 40;
  const maxScore = 100;

  const xFor = (index) => {
    if (items.length === 1) return width / 2;
    return paddingX + (index / (items.length - 1)) * (width - paddingX * 2);
  };

  const yFor = (value) => paddingY + ((maxScore - value) / (maxScore - minScore)) * (height - paddingY * 2);
  const polyline = (key) => items.map((item, index) => `${xFor(index)},${yFor(Number(item[key] || 0))}`).join(' ');

  return `
    <svg viewBox="0 0 ${width} ${height}" class="score-trend-chart" aria-hidden="true">
      <line x1="${paddingX}" y1="${height - paddingY}" x2="${width - paddingX}" y2="${height - paddingY}" class="score-trend-chart__axis"></line>
      <line x1="${paddingX}" y1="${paddingY}" x2="${paddingX}" y2="${height - paddingY}" class="score-trend-chart__axis"></line>
      <polyline points="${polyline('E')}" class="score-trend-chart__line score-trend-chart__line--e"></polyline>
      <polyline points="${polyline('S')}" class="score-trend-chart__line score-trend-chart__line--s"></polyline>
      <polyline points="${polyline('G')}" class="score-trend-chart__line score-trend-chart__line--g"></polyline>
      ${items.map((item, index) => `
        <text x="${xFor(index)}" y="${height - 6}" class="score-trend-chart__label">${escapeHtml(item.month)}</text>
      `).join('')}
    </svg>
  `;
}

function buildDerivedScoreSnapshot(data) {
  const company = data.spotlight?.company || data.signals?.[0]?.company || 'Tesla';
  const profiles = {
    Tesla: { overall: 72, confidence: 0.85, E: 78, S: 65, G: 73 },
    Apple: { overall: 79, confidence: 0.87, E: 82, S: 74, G: 79 },
    Microsoft: { overall: 81, confidence: 0.89, E: 84, S: 77, G: 82 },
    SEC: { overall: 68, confidence: 0.8, E: 62, S: 66, G: 76 },
  };
  const profile = profiles[company] || { overall: 74, confidence: 0.83, E: 77, S: 69, G: 75 };

  return {
    company,
    overall_score: profile.overall,
    confidence: profile.confidence,
    dimensions: [
      { key: 'E', label: '环保', score: profile.E, trend: 'up' },
      { key: 'S', label: '社会', score: profile.S, trend: 'stable' },
      { key: 'G', label: '治理', score: profile.G, trend: 'up' },
    ],
    radar: [
      { label: '碳排放', value: Math.min(95, profile.E + 6) },
      { label: '员工满意度', value: Math.min(95, profile.S + 4) },
      { label: '供应链伦理', value: Math.max(50, profile.S - 3) },
      { label: '能源效率', value: Math.min(95, profile.E + 2) },
      { label: '成本竞争力', value: Math.min(95, profile.G + 1) },
    ],
    trend: [
      { month: 'Jan', E: profile.E - 14, S: profile.S - 9, G: profile.G - 10 },
      { month: 'Feb', E: profile.E - 11, S: profile.S - 8, G: profile.G - 8 },
      { month: 'Mar', E: profile.E - 9, S: profile.S - 6, G: profile.G - 7 },
      { month: 'Apr', E: profile.E - 7, S: profile.S - 4, G: profile.G - 6 },
      { month: 'May', E: profile.E - 6, S: profile.S - 3, G: profile.G - 5 },
      { month: 'Jun', E: profile.E - 5, S: profile.S - 2, G: profile.G - 4 },
      { month: 'Jul', E: profile.E - 4, S: profile.S - 2, G: profile.G - 3 },
      { month: 'Aug', E: profile.E - 2, S: profile.S - 1, G: profile.G - 2 },
      { month: 'Sep', E: profile.E - 1, S: profile.S, G: profile.G - 1 },
      { month: 'Oct', E: profile.E, S: profile.S, G: profile.G },
    ],
  };
}

function buildDerivedEventMonitor(data) {
  const signals = data.signals?.length ? data.signals : getFallbackOverview().signals;
  const riskCounts = { high: 0, medium: 0, low: 0 };
  const events = signals.slice(0, 4).map((signal, index) => {
    const level = signal.tone === 'alert'
      ? (index === 0 ? 'high' : 'medium')
      : signal.tone === 'positive'
        ? 'low'
        : 'medium';

    riskCounts[level] += 1;

    return {
      company: signal.company,
      title: signal.title,
      description: signal.description,
      level,
      risk_score: level === 'high' ? 89 : level === 'medium' ? 62 - index : 48 + index,
      published_at: signal.detected_at,
      recommendation: level === 'high'
        ? '优先补充正式回应，并排查治理与劳工风险。'
        : level === 'medium'
          ? '持续观察后续披露，并加入行业对标。'
          : '作为正面案例继续跟踪，提炼可复用亮点。',
      positive: signal.tone === 'positive',
    };
  });

  const timeline = signals.slice(0, 5).map((signal, index) => ({
    date_label: formatDate(signal.detected_at || new Date().toISOString(), 'MM-DD'),
    company: signal.company || '市场观察',
    level: events[index]?.level || 'medium',
  }));

  return {
    period_label: '最近 7 天',
    risk_counts: riskCounts,
    events,
    timeline,
  };
}

function buildSourceText(data) {
  const source = data.source === 'database'
    ? 'Database-backed ESG pulse'
    : data.source === 'scanner_fallback'
      ? 'Scanner-simulated flagship feed'
      : 'Curated fallback signal stream';

  return `${source} · ${formatDate(data.generated_at || new Date().toISOString(), 'YYYY-MM-DD HH:mm')}`;
}

function toneLabel(tone) {
  return {
    positive: 'Positive',
    alert: 'Alert',
    neutral: 'Neutral',
  }[tone] || 'Live';
}

function storageLabel(mode) {
  return {
    hybrid_cloud: 'Hybrid Cloud',
    local_fallback: 'Local Ready',
  }[mode] || 'Runtime Ready';
}

function artifactBackendLabel(storage) {
  if (storage?.r2_ready) {
    return 'R2 active';
  }
  if (storage?.supabase_storage_ready) {
    return 'Supabase Storage active';
  }
  return 'Local artifact fallback';
}

function formatPercent(value, digits = 1) {
  const numeric = Number(value || 0);
  return `${(numeric * 100).toFixed(digits)}%`;
}

function getFallbackQuantOverview() {
  return {
    platform_name: 'ESG Quant Intelligence System',
    tagline: '从数据接入到因子研究、回测执行与产品交付的一体化 ESG Quant 平台',
    architecture_layers: [
      { key: 'l0', label: '数据接入层', priority: 'P1', ready: true, detail: '市场、宏观、ESG 与另类数据入口' },
      { key: 'l1', label: '数据治理层', priority: 'P1', ready: true, detail: '时间对齐、异常过滤、血缘记录' },
      { key: 'l2', label: '分析引擎层', priority: 'P1', ready: true, detail: '技术、因子、ESG 与另类数据分析' },
      { key: 'l3', label: '模型训练层', priority: 'P2', ready: true, detail: 'XGBoost、LSTM、LoRA 与训练规划' },
      { key: 'l4', label: 'Agent 编排层', priority: 'P1', ready: true, detail: 'Research、Strategy、Risk、Report Agent' },
      { key: 'l5', label: '风控合规层', priority: 'P2', ready: true, detail: '回撤、CVaR、压力测试与规则引擎' },
      { key: 'l6', label: '执行回测层', priority: 'P1', ready: true, detail: '回测、Paper Trading 与绩效归因' },
      { key: 'l7+', label: '实验与交付层', priority: 'P1', ready: true, detail: '实验记录、站点交付与报告沉淀' },
    ],
    storage: {
      mode: 'local_fallback',
      supabase_ready: false,
      supabase_storage_ready: false,
      r2_ready: false,
      preferred_artifact_backend: 'local',
    },
    portfolio_preview: {
      benchmark: 'SPY',
      expected_alpha: 0.084,
      gross_exposure: 1,
      positions: [
        { symbol: 'AAPL' },
        { symbol: 'MSFT' },
        { symbol: 'TSLA' },
        { symbol: 'NVDA' },
      ],
    },
    latest_backtest: {
      metrics: {
        sharpe: 1.42,
        max_drawdown: 0.082,
        cvar_95: 0.024,
        information_ratio: 0.88,
      },
    },
    training_plan: {
      remote_ready: false,
      adapter_strategy: 'Qwen2.5 / ESG domain LoRA continuation training',
      target_environment: 'Cloud RTX 5090 Finetune Node',
    },
  };
}

function getFallbackOverview() {
  const now = new Date().toISOString();

  return {
    generated_at: now,
    source: 'static_fallback',
    health: {
      rag: true,
      esg_scorer: true,
      report_scheduler: false,
      data_sources: true,
    },
    narrative: {
      headline: 'ESG 智能中枢。',
      subheadline: '像旗舰发布页一样展示 ESG 情报、系统能力和核心入口。',
      summary: '让研究、监测和执行不再分散在多个页面里，而是在一个总览视角里建立秩序。',
    },
    spotlight: {
      company: 'Tesla',
      title: 'Tesla 更新碳减排目标，成为当前 ESG 关注焦点。',
      description: '环境目标的重新量化，通常会对供应链执行、资本市场叙事与长期治理预期同时产生影响。',
      event_type: 'EMISSION_REDUCTION',
      source: 'fallback',
      detected_at: now,
      tone: 'positive',
    },
    metrics: [
      { label: '实时信号', value: 3, suffix: '条', hint: '最近进入首页的信息流' },
      { label: '覆盖主体', value: 3, suffix: '个', hint: '当前热点主体数量' },
      { label: '系统模块', value: 3, suffix: '/4', hint: '在线能力概览' },
      { label: '近 7 天扫描', value: 0, suffix: '次', hint: '等待调度器接管' },
    ],
    query_interface: {
      hot_questions: DEFAULT_HOT_QUESTIONS,
    },
    score_snapshot: {
      company: 'Tesla',
      overall_score: 72,
      confidence: 0.85,
      dimensions: [
        { key: 'E', label: '环保', score: 78, trend: 'up' },
        { key: 'S', label: '社会', score: 65, trend: 'stable' },
        { key: 'G', label: '治理', score: 73, trend: 'up' },
      ],
      radar: [
        { label: '碳排放', value: 84 },
        { label: '员工满意度', value: 69 },
        { label: '供应链伦理', value: 62 },
        { label: '能源效率', value: 80 },
        { label: '成本竞争力', value: 74 },
      ],
      trend: [
        { month: 'Jan', E: 61, S: 56, G: 60 },
        { month: 'Feb', E: 65, S: 57, G: 63 },
        { month: 'Mar', E: 67, S: 59, G: 65 },
        { month: 'Apr', E: 69, S: 61, G: 66 },
        { month: 'May', E: 70, S: 62, G: 68 },
        { month: 'Jun', E: 71, S: 63, G: 69 },
        { month: 'Jul', E: 73, S: 64, G: 70 },
        { month: 'Aug', E: 75, S: 64, G: 71 },
        { month: 'Sep', E: 77, S: 65, G: 72 },
        { month: 'Oct', E: 78, S: 65, G: 73 },
      ],
    },
    event_monitor: {
      period_label: '最近 7 天',
      risk_counts: { high: 1, medium: 2, low: 1 },
      events: [
        {
          company: 'Tesla',
          title: '员工劳资纠纷进入舆情高位',
          description: '工人权益议题快速放大，可能影响社会责任评分和治理叙事。',
          level: 'high',
          risk_score: 89,
          published_at: now,
          recommendation: '改善员工薪酬与工作条件，并补充正式披露回应。',
          positive: false,
        },
        {
          company: 'Apple',
          title: '供应链碳排放审计结果发布',
          description: '供应链减排与可再生能源使用比例成为市场关注重点。',
          level: 'medium',
          risk_score: 62,
          published_at: now,
          recommendation: '增加可再生能源使用比例，并强化供应链沟通。',
          positive: false,
        },
        {
          company: 'Microsoft',
          title: '多样性报告公布新的改善指标',
          description: '正面社会责任样本出现，适合持续跟踪并用于横向对标。',
          level: 'low',
          risk_score: 48,
          published_at: now,
          recommendation: '持续观察后续披露，把亮点沉淀成对标样本。',
          positive: true,
        },
      ],
      timeline: [
        { date_label: '03/25', company: 'Apple', level: 'medium' },
        { date_label: '03/27', company: 'Microsoft', level: 'low' },
        { date_label: '03/28', company: 'Apple', level: 'medium' },
        { date_label: '03/29', company: 'Tesla', level: 'high' },
      ],
    },
    signals: [
      {
        company: 'Tesla',
        title: 'Tesla 宣布更激进的碳减排时间表',
        description: '环境目标的提前意味着更高的执行要求，也释放出更积极的转型信号。',
        event_type: 'EMISSION_REDUCTION',
        source: 'fallback',
        detected_at: now,
        tone: 'positive',
      },
      {
        company: 'Microsoft',
        title: 'Microsoft 最新 ESG 报告强化可再生能源路线',
        description: '新报告强调长期治理与能源结构调整，利于稳定市场预期。',
        event_type: 'RENEWABLE_ENERGY',
        source: 'fallback',
        detected_at: now,
        tone: 'positive',
      },
      {
        company: 'SEC',
        title: 'SEC 披露规则变化提升治理合规压力',
        description: '披露要求细化后，企业需要更系统地组织 ESG 证据链和治理响应。',
        event_type: 'GOVERNANCE_CHANGE',
        source: 'fallback',
        detected_at: now,
        tone: 'alert',
      },
    ],
    quantPlatform: getFallbackQuantOverview(),
  };
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}
