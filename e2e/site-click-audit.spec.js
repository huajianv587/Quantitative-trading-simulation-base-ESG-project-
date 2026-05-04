const fs = require('fs');
const path = require('path');
const { test, expect } = require('@playwright/test');

const OUTPUT_DIR = path.join(process.cwd(), 'test-results', 'site-click-audit');
const PROGRESS_LOG = path.join(OUTPUT_DIR, 'progress.log');

function toReportPath(filePath) {
  const value = String(filePath || '');
  const relative = path.isAbsolute(value) ? path.relative(process.cwd(), value) : value;
  return relative.split(path.sep).join('/');
}

function logProgress(message) {
  fs.mkdirSync(OUTPUT_DIR, { recursive: true });
  fs.appendFileSync(PROGRESS_LOG, `${new Date().toISOString()} ${message}\n`, 'utf8');
}

function buildDashboardOverview() {
  return {
    platform_name: 'ESG Quant Intelligence System',
    watchlist_signals: [
      {
        symbol: 'NVDA',
        company_name: 'NVIDIA',
        sector: 'Technology',
        thesis: 'Risk-on leadership remains intact.',
        action: 'long',
        confidence: 0.86,
        decision_confidence: 0.88,
        expected_return: 0.072,
        predicted_return_5d: 0.058,
        predicted_volatility_10d: 0.118,
        predicted_drawdown_20d: 0.084,
        overall_score: 87.4,
        e_score: 82,
        s_score: 79,
        g_score: 84,
        regime_label: 'risk_on',
        market_data_source: 'yfinance',
        prediction_mode: 'model',
        projection_basis_return: 0.072,
        projection_scenarios: {
          upper: { label: 'Bull Case', expected_return: 0.134, confidence: 0.88 },
          center: { label: 'Base Case', expected_return: 0.072, confidence: 0.88 },
          lower: { label: 'Risk Floor', expected_return: -0.012, confidence: 0.74 },
        },
        factor_scores: [{ name: 'momentum', value: 84, contribution: 0.32, description: 'Trend strength remains above peer median.' }],
        catalysts: ['Decision score remains above the paper gate'],
        data_lineage: ['L0: yfinance daily bars', 'L2: P1 suite', 'L3: P2 decision stack'],
      },
      {
        symbol: 'NEE',
        company_name: 'NextEra Energy',
        sector: 'Utilities',
        thesis: 'Short-term rebound exists but the final decision remains defensive.',
        action: 'neutral',
        confidence: 0.74,
        decision_confidence: 0.76,
        expected_return: -0.011,
        predicted_return_5d: 0.031,
        predicted_volatility_10d: 0.094,
        predicted_drawdown_20d: 0.088,
        overall_score: 76.3,
        e_score: 83,
        s_score: 75,
        g_score: 79,
        regime_label: 'risk_off',
        market_data_source: 'yfinance',
        prediction_mode: 'model',
        projection_basis_return: -0.011,
        projection_scenarios: {
          upper: { label: 'Bull Case', expected_return: 0.041, confidence: 0.76 },
          center: { label: 'Base Case', expected_return: -0.011, confidence: 0.76 },
          lower: { label: 'Risk Floor', expected_return: -0.071, confidence: 0.81 },
        },
        factor_scores: [{ name: 'drawdown', value: 63, contribution: 0.24, description: 'Drawdown risk keeps the center path muted.' }],
        catalysts: ['Short-term rebound branch conflicts with final action'],
        data_lineage: ['L0: yfinance daily bars', 'L2: P1 suite', 'L3: P2 decision stack'],
      },
    ],
    top_signals: [],
    portfolio_preview: { capital_base: 1000000, expected_alpha: 0.084, positions: [] },
    latest_backtest: { metrics: { sharpe: 1.84, max_drawdown: -0.092, annualized_return: 0.214, hit_rate: 0.581 } },
    p1_signal_snapshot: { regime_counts: { risk_on: 1, neutral: 0, risk_off: 1 } },
    universe: { size: 2, benchmark: 'SPY' },
  };
}

function buildResearchSignals() {
  return [
    {
      symbol: 'NVDA',
      company_name: 'NVIDIA',
      action: 'long',
      confidence: 0.88,
      expected_return: 0.072,
      overall_score: 87.4,
      e_score: 82,
      g_score: 84,
      sector: 'Technology',
      thesis: 'Demand cadence and governance quality keep the signal constructive.',
    },
    {
      symbol: 'NEE',
      company_name: 'NextEra Energy',
      action: 'neutral',
      confidence: 0.76,
      expected_return: -0.011,
      overall_score: 76.3,
      e_score: 83,
      g_score: 79,
      sector: 'Utilities',
      thesis: 'Defensive support remains, but the final decision stack stays cautious.',
    },
  ];
}

function buildResearchContext(symbol = 'NVDA') {
  return {
    generated_at: new Date().toISOString(),
    symbol,
    provider: 'auto',
    quote_strip: [
      { symbol: 'NVDA', company_name: 'NVIDIA', last_price: 922.14, change_pct: 0.023, source: 'alpaca' },
      { symbol: 'AAPL', company_name: 'Apple', last_price: 187.42, change_pct: 0.011, source: 'alpaca' },
      { symbol: 'MSFT', company_name: 'Microsoft', last_price: 421.18, change_pct: 0.016, source: 'alpaca' },
    ],
    momentum_leaders: buildResearchSignals(),
    feed: [
      {
        item_id: 'ctx-001',
        title: `${symbol} factor momentum`,
        summary: 'Trend strength remains above the peer median and the evidence chain is intact.',
        item_type: 'model_signal',
        provider: 'alpaca',
        quality_score: 0.92,
        published_at: new Date().toISOString(),
      },
      {
        item_id: 'ctx-002',
        title: `${symbol} SEC filing context`,
        summary: 'Recent filing references governance continuity and stable disclosure posture.',
        item_type: 'filing',
        provider: 'sec_edgar',
        quality_score: 0.87,
        published_at: new Date().toISOString(),
      },
    ],
    provider_status: {
      provider: 'alpaca',
      availability: 'ready',
      degraded_from: null,
    },
    source_chain: ['alpaca', 'yfinance', 'sec_edgar', 'cache', 'local_esg'],
    freshness: { quote_strip: 'live', feed: 'recent' },
    degraded: false,
    fallback_preview: null,
    warning: null,
    next_actions: ['Run research', 'Open market radar'],
  };
}

function buildDashboardState() {
  return {
    generated_at: new Date().toISOString(),
    symbol: 'NVDA',
    selected_provider: 'auto',
    source: 'alpaca',
    source_chain: ['alpaca', 'yfinance', 'cache', 'synthetic'],
    provider_status: {
      provider: 'alpaca',
      availability: 'ready',
      degraded_from: null,
    },
    fallback_preview: null,
    degraded: false,
    next_actions: ['Refresh dashboard state'],
  };
}

function buildPortfolioHoldings() {
  return [
    { symbol: 'COST', weight: 0.34, sector: 'Consumer Staples', esg_score: 86 },
    { symbol: 'WMT', weight: 0.33, sector: 'Consumer Staples', esg_score: 80 },
    { symbol: 'PG', weight: 0.33, sector: 'Consumer Staples', esg_score: 84 },
  ];
}

function buildBacktestPayload() {
  const timeline = Array.from({ length: 24 }).map((_, index) => ({
    date: new Date(Date.UTC(2025, 0, 1 + index * 5)).toISOString().slice(0, 10),
    portfolio_nav: 1000000 + index * 8200 + Math.round(Math.sin(index * 0.4) * 6500),
    benchmark_nav: 1000000 + index * 5100 + Math.round(Math.cos(index * 0.3) * 4200),
  }));

  return {
    backtest_id: 'backtest-e2e-001',
    strategy_name: 'ESG Multi-Factor Long-Only',
    benchmark: 'SPY',
    period_start: timeline[0].date,
    period_end: timeline[timeline.length - 1].date,
    metrics: {
      annualized_return: 0.184,
      sharpe: 1.62,
      max_drawdown: -0.091,
      hit_rate: 0.58,
      sortino: 2.11,
      cumulative_return: 0.142,
      annualized_volatility: 0.113,
      beta: 0.82,
      information_ratio: 0.66,
      cvar_95: -0.031,
    },
    timeline,
    risk_alerts: [
      { level: 'medium', title: 'Concentration drift', description: 'Technology weight rose above baseline.', recommendation: 'Monitor active weights weekly.' },
    ],
  };
}

function buildValidationPayload() {
  return {
    validation_id: 'validation-e2e-001',
    recommendation: 'GO',
    summary: 'Walk-forward performance remains robust across validation windows.',
    out_of_sample_sharpe: 1.24,
    in_sample_sharpe: 1.87,
    overfit_score: 0.18,
    fill_probability: 0.91,
    cost_drag_bps: 4.2,
    windows: [
      { window: 1, in_sample_sharpe: 1.95, out_of_sample_sharpe: 1.31 },
      { window: 2, in_sample_sharpe: 1.82, out_of_sample_sharpe: 1.18 },
      { window: 3, in_sample_sharpe: 1.91, out_of_sample_sharpe: 1.28 },
      { window: 4, in_sample_sharpe: 1.75, out_of_sample_sharpe: 1.09 },
      { window: 5, in_sample_sharpe: 1.88, out_of_sample_sharpe: 1.34 },
    ],
    regime_performance: [
      { regime: 'Bull Market', periods: 6, return: '24.2%', sharpe: '1.82', max_dd: '-8.1%' },
      { regime: 'High Vol', periods: 3, return: '12.4%', sharpe: '0.78', max_dd: '-11.8%' },
    ],
  };
}

function buildExecutionOrders() {
  return [
    {
      order_id: 'ord-001',
      symbol: 'AAPL',
      side: 'buy',
      qty: 15,
      status: 'filled',
      fill_price: 189.42,
      limit_price: 189.5,
      order_type: 'limit',
      submitted_at: new Date().toISOString(),
    },
    {
      order_id: 'ord-002',
      symbol: 'MSFT',
      side: 'buy',
      qty: 10,
      status: 'pending',
      fill_price: null,
      limit_price: 421.1,
      order_type: 'limit',
      submitted_at: new Date().toISOString(),
    },
  ];
}

function buildScorePayload() {
  return {
    esg_report: {
      company: 'Tesla',
      ticker: 'TSLA',
      overall_score: 72.4,
      e_score: 68.1,
      s_score: 74.8,
      g_score: 74.2,
      percentile: 78,
      industry: 'Consumer Discretionary / EV',
      rating: 'AA',
      sub_scores: {
        environment: [62, 84, 71, 68, 56],
        social: [82, 79, 71, 68, 75],
        governance: [88, 72, 74, 68, 69],
      },
      trend: [61.2, 63.4, 65.1, 67.2, 68.8, 70.1, 71.4, 72.0, 71.8, 72.4, 72.1, 72.4],
      peers: [
        { name: 'Tesla', ticker: 'TSLA', overall: 72.4, e: 68.1, s: 74.8, g: 74.2 },
        { name: 'Ford Motor', ticker: 'F', overall: 61.2, e: 58.3, s: 66.1, g: 59.2 },
      ],
    },
  };
}

function buildReportPayload() {
  return {
    report_id: 'RPT-e2e-001',
    title: 'Daily ESG Report',
    report_type: 'daily',
    generated_at: new Date().toISOString(),
    company_analyses: [
      { company_name: 'Tesla', ticker: 'TSLA', esg_score: 72.4, environment: 68.1, social: 74.8, governance: 74.2, recommendation: 'BUY', change_3m: '+3.2' },
      { company_name: 'Microsoft', ticker: 'MSFT', esg_score: 81.2, environment: 79.4, social: 83.0, governance: 81.1, recommendation: 'BUY', change_3m: '+1.8' },
    ],
    summary: 'Technology leaders continue to dominate the ESG composite ranking.',
    top_signals: ['NVDA governance improvement +4pts'],
    risk_alerts: ['VIX drift remains the main short-term risk'],
    market_context: { regime: 'Bull Market', spy_ytd: '+18.4%', vix: '14.2', esg_premium: '+280bps' },
  };
}

async function fulfillJson(route, payload, status = 200) {
  await route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(payload) });
}

function generateDashboardCandles(symbol) {
  let close = symbol === 'NEE' ? 70 : 185;
  const candles = [];
  for (let index = 0; index < 120; index += 1) {
    const drift = (symbol === 'NEE' ? -0.0002 : 0.0018) + Math.sin(index * 0.22) * 0.003;
    const open = close;
    close = Math.max(12, close * (1 + drift));
    candles.push({
      t: new Date(Date.UTC(2025, 0, 1 + index)).toISOString().slice(0, 10),
      o: Number(open.toFixed(2)),
      h: Number((Math.max(open, close) * 1.012).toFixed(2)),
      l: Number((Math.min(open, close) * 0.988).toFixed(2)),
      c: Number(close.toFixed(2)),
      v: 7000000 + ((index * 87000) % 2200000),
    });
  }
  return candles;
}

async function stubDashboard(page) {
  const overview = buildDashboardOverview();
  await page.route('**/api/v1/quant/platform/overview', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(overview) });
  });
  await page.route('**/api/v1/quant/execution/positions**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ positions: [] }) });
  });
  await page.route('**/api/v1/quant/dashboard/chart?*', async (route) => {
    const url = new URL(route.request().url());
    const symbol = url.searchParams.get('symbol') || 'NVDA';
    const timeframe = url.searchParams.get('timeframe') || '1D';
    const signal = (overview.watchlist_signals || []).find((item) => item.symbol === symbol) || overview.watchlist_signals[0];
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        symbol,
        timeframe,
        source: 'yfinance',
        candles: generateDashboardCandles(symbol).map((candle) => ({
          date: candle.t,
          open: candle.o,
          high: candle.h,
          low: candle.l,
          close: candle.c,
          volume: candle.v,
        })),
        indicators: {},
        projection_scenarios: signal.projection_scenarios || {},
        projection_explanations: Object.fromEntries(Object.entries(signal.projection_scenarios || {}).map(([key, scenario]) => [key, {
          title: scenario.label,
          direction: Number(scenario.expected_return || 0) >= 0 ? 'upside' : 'downside',
          expected_return: scenario.expected_return,
          confidence: scenario.confidence,
          drivers: (signal.factor_scores || []).map((item) => item.description).slice(0, 3),
          why_not_opposite: (signal.catalysts || []).slice(-1)[0] || 'Decision stack rejected the opposite branch.',
          source: 'yfinance',
          data_lineage: signal.data_lineage || [],
          house_explanation: `House score proxy for ${symbol} stays constructive.`,
        }])),
        projected_volume: [],
        viewport_defaults: {
          '116%': { visibleCount: 64, projectionWidthRatio: 0.22, pricePaddingRatio: 0.06 },
          '352%': { visibleCount: 32, projectionWidthRatio: 0.28, pricePaddingRatio: 0.08 },
          '600%': { visibleCount: 20, projectionWidthRatio: 0.34, pricePaddingRatio: 0.11 },
        },
        click_targets: ['symbol_chip', 'timeframe_tab', 'zoom_control', 'projection_line', 'heatmap_tile'],
        prediction_disabled_reason: null,
        signal,
      }),
    });
  });
}

async function stubSiteAuditApis(page) {
  await page.addInitScript(() => {
    class FakeWebSocket {
      constructor(url) {
        this.url = url;
        this.readyState = 1;
        setTimeout(() => {
          if (typeof this.onclose === 'function') this.onclose({ code: 1000, reason: 'e2e stub' });
        }, 0);
      }

      send() {}

      close() {
        this.readyState = 3;
        if (typeof this.onclose === 'function') this.onclose({ code: 1000, reason: 'closed' });
      }
    }

    window.WebSocket = FakeWebSocket;
  });

  await page.route('**/api/v1/quant/research/run', async (route) => {
      await fulfillJson(route, {
        research_id: 'research-e2e-001',
        generated_at: new Date().toISOString(),
        signals: buildResearchSignals(),
      });
    });
  await page.route('**/api/v1/quant/research/context?*', async (route) => {
      const url = new URL(route.request().url());
      await fulfillJson(route, buildResearchContext(url.searchParams.get('symbol') || 'NVDA'));
    });

  await page.route('**/api/v1/quant/portfolio/optimize', async (route) => {
    await fulfillJson(route, {
      portfolio_id: 'portfolio-e2e-001',
      expected_return: 0.226,
      expected_volatility: 0.123,
      sharpe_estimate: 1.84,
      holdings: buildPortfolioHoldings(),
      portfolio: { positions: buildPortfolioHoldings() },
    });
  });

  await page.route('**/api/v1/quant/backtests', async (route) => {
    if (route.request().method() !== 'GET') return route.fallback();
    await fulfillJson(route, {
      backtests: [
        { backtest_id: 'backtest-e2e-001', strategy_name: 'ESG Multi-Factor Long-Only', period_start: '2025-01-01', metrics: { sharpe: 1.62 } },
      ],
    });
  });

  await page.route('**/api/v1/quant/backtests/run', async (route) => {
    await fulfillJson(route, buildBacktestPayload());
  });

  await page.route('**/api/v1/quant/backtests/*', async (route) => {
    if (route.request().method() !== 'GET') return route.fallback();
    await fulfillJson(route, buildBacktestPayload());
  });

  await page.route('**/api/v1/quant/execution/paper', async (route) => {
    await fulfillJson(route, {
      execution_id: 'execution-e2e-001',
      broker: 'alpaca',
      orders: buildExecutionOrders(),
    });
  });

  await page.route('**/api/v1/quant/execution/orders**', async (route) => {
    await fulfillJson(route, { orders: buildExecutionOrders() });
  });

  await page.route('**/api/v1/quant/execution/positions**', async (route) => {
    await fulfillJson(route, {
      positions: [
        { symbol: 'AAPL', qty: 15, current_price: 189.42, unrealized_pnl: 124.6 },
      ],
    });
  });

  await page.route('**/api/v1/quant/validation/run', async (route) => {
    await fulfillJson(route, buildValidationPayload());
  });

  await page.route('**/api/v1/quant/p1/status', async (route) => {
    await fulfillJson(route, {
      ready: true,
      components: [
        { name: 'Alpha Ranker', ready: true },
        { name: 'LSTM Signal', ready: true },
      ],
    });
  });

  await page.route('**/api/v1/quant/p2/status', async (route) => {
    await fulfillJson(route, {
      ready: true,
      components: [
        { name: 'Decision Stack', ready: true },
        { name: 'Risk Gate', ready: true },
      ],
    });
  });

  await page.route('**/api/v1/quant/experiments', async (route) => {
    await fulfillJson(route, {
      experiments: [
        { experiment_id: 'exp-001', name: 'P2 Decision Stack', status: 'ready', metric: 0.81 },
      ],
    });
  });

  await page.route('**/api/v1/quant/rl/overview', async (route) => {
    await fulfillJson(route, {
      runs: [
        {
          run_id: 'sac-e2e-001',
          algorithm: 'sac',
          phase: 'phase_02_training',
          status: 'completed',
          artifacts: { checkpoint_path: 'storage/quant/rl/checkpoints/sac-e2e-001/model.pt' },
          metrics: { sharpe: 1.24 },
        },
      ],
      protocol: {
        paper_title: 'ESG-Augmented Reinforcement Learning for Quant Equity Trading',
        target_journal: 'Intelligent Systems with Applications',
        recording_requirements: ['metrics.json', 'equity_curve.csv', 'all_results.xlsx'],
      },
      output_status: {
        output_root: 'storage/quant/rl-experiments',
        dataset_manifests: 2,
        metrics_files: 3,
        summary_workbook: 'storage/quant/rl-experiments/summary/all_results.xlsx',
        summary_exists: true,
      },
      services: {
        alpaca_ready: true,
        alpha_vantage_ready: true,
        esg_scoring_ready: true,
        market_data: { alpaca_market_data_ready: true },
      },
      experiment_groups: [
        { key: 'OURS_full', label: 'OURS Full', family: 'main', algorithm: 'hybrid_frontier', seeds: [42] },
        { key: 'B4_sac_esg', label: 'B4 SAC+ESG', family: 'main', algorithm: 'sac', seeds: [42] },
      ],
      recipes: [
        { key: 'L1_price_tech', label: 'L1 Price + Tech Baseline', symbols: ['AAPL'], layers: ['price_tech'], algorithm: 'sac' },
        { key: 'L2_vol_sentiment', label: 'L2 Price + VIX + Put/Call', symbols: ['AAPL'], layers: ['price_tech', 'vol_sentiment'], algorithm: 'sac' },
        { key: 'L5_house_esg', label: 'L5 House ESG', symbols: ['AAPL'], layers: ['price_tech', 'house_esg'], algorithm: 'sac' },
      ],
      paper_execution_bridge: { route: '/app/#/execution', api: '/api/v1/quant/execution/run' },
    });
  });

  await page.route('**/agent/analyze', async (route) => {
      await fulfillJson(route, {
        answer: 'NVDA remains favored because model quality, regime support, and ESG resilience all stay constructive.',
        sources: ['platform.overview', 'signal_stack'],
      });
    });
  await page.route('**/session?*', async (route) => {
      const url = new URL(route.request().url());
      await fulfillJson(route, {
        session_id: url.searchParams.get('session_id') || 'chat-e2e-001',
        created: true,
      });
    });
  await page.route('**/history/*', async (route) => {
      const sessionId = route.request().url().split('/history/')[1]?.split('?')[0] || 'chat-e2e-001';
      await fulfillJson(route, {
        session_id: sessionId,
        messages: [],
      });
    });
  await page.route('**/api/v1/trading/dashboard/state?*', async (route) => {
      await fulfillJson(route, buildDashboardState());
    });

  await page.route('**/agent/esg-score', async (route) => {
    await fulfillJson(route, buildScorePayload());
  });

  await page.route('**/admin/reports/generate', async (route) => {
    await fulfillJson(route, buildReportPayload());
  });

  await page.route('**/admin/reports/latest**', async (route) => {
    await fulfillJson(route, buildReportPayload());
  });

  await page.route('**/admin/data-sources/sync', async (route) => {
    if (route.request().method() !== 'POST') return route.fallback();
    await fulfillJson(route, {
      job_id: 'JOB-e2e-001',
      status: 'running',
      companies: ['Tesla', 'Microsoft'],
      progress: 12,
    });
  });

  await page.route('**/admin/data-sources/sync/*', async (route) => {
    await fulfillJson(route, {
      job_id: 'JOB-e2e-001',
      status: 'completed',
      companies: ['Tesla', 'Microsoft'],
      progress: 100,
    });
  });

  await page.route('**/admin/push-rules', async (route) => {
    if (route.request().method() === 'GET') {
      await fulfillJson(route, {
        rules: [
          { rule_id: 'rule-001', rule_name: 'Low ESG Alert', condition: 'overall_score < 40', push_channels: ['email', 'in_app'] },
        ],
      });
      return;
    }
    if (route.request().method() === 'POST') {
      await fulfillJson(route, { rule_id: 'rule-002', status: 'created' });
      return;
    }
    await route.fallback();
  });

  await page.route('**/admin/push-rules/*/test', async (route) => {
    await fulfillJson(route, { results: { matched: true } });
  });

  await page.route('**/admin/push-rules/*', async (route) => {
    if (route.request().method() === 'DELETE') {
      await route.fulfill({ status: 204, body: '' });
      return;
    }
    await route.fallback();
  });

  await page.route('**/user/reports/subscriptions**', async (route) => {
    if (route.request().method() === 'GET') {
      await fulfillJson(route, {
        subscriptions: [
          {
            subscription_id: 'sub-001',
            report_types: ['daily'],
            companies: ['Tesla', 'Microsoft'],
            push_channels: ['email', 'in_app'],
            frequency: 'daily',
          },
        ],
      });
      return;
    }
    if (route.request().method() === 'DELETE') {
      await route.fulfill({ status: 204, body: '' });
      return;
    }
    await route.fallback();
  });

  await page.route('**/user/reports/subscribe**', async (route) => {
    await fulfillJson(route, { subscription_id: 'sub-002', status: 'created' });
  });
}

async function openRoute(page, config) {
  await page.goto(config.url, { waitUntil: 'domcontentloaded' });
  await page.locator(config.ready).first().waitFor({ state: 'visible', timeout: 30000 });
  await page.waitForLoadState('networkidle', { timeout: 5000 }).catch(() => {});
  await page.waitForTimeout(100);
}

async function findBlankPoint(page, rootSelector) {
  return page.evaluate((selector) => {
    const root = document.querySelector(selector);
    const rect = root.getBoundingClientRect();
    const interactiveSelector = [
      'a',
      'button',
      'input',
      'select',
      'textarea',
      '[data-path]',
      '[data-sym]',
      '[data-tf]',
      '[data-zoom]',
      '[data-ind]',
      '[data-heat-tf]',
      '[data-ikey]',
    ].join(', ');

    for (let y = rect.bottom - 18; y > rect.top + 18; y -= 18) {
      for (let x = rect.right - 18; x > rect.left + 18; x -= 18) {
        const element = document.elementFromPoint(x, y);
        if (!element) continue;
        if (!root.contains(element)) continue;
        if (!element.closest(interactiveSelector)) {
          return { x, y };
        }
      }
    }

    return { x: rect.right - 18, y: rect.bottom - 18 };
  }, rootSelector);
}

async function measureAction(page, action) {
  const beforeUrl = page.url();
  const beforeUiAudit = await page.evaluate(() => (window.__uiAuditLog || []).length);
  const requests = [];
  const onRequest = (request) => requests.push({ url: request.url(), method: request.method() });
  page.on('request', onRequest);
  try {
    await action();
    await page.waitForTimeout(600);
  } finally {
    page.off('request', onRequest);
  }
  const afterUrl = page.url();
  const afterUiAudit = await page.evaluate(() => (window.__uiAuditLog || []).length);
  return {
    routeChanged: beforeUrl !== afterUrl,
    uiAuditDelta: afterUiAudit - beforeUiAudit,
    requests,
  };
}

function screenshotPath(name) {
  fs.mkdirSync(OUTPUT_DIR, { recursive: true });
  return path.join(OUTPUT_DIR, `${name}.png`);
}

const ROUTES = [
  {
    name: 'landing',
    url: '/',
    ready: '#hero-app-entry',
    root: 'body',
    expectedChannels: ['route'],
    action: async (page) => {
      await page.locator('#hero-app-entry').click();
      await page.waitForURL(/\/app\/#\/dashboard$/);
    },
  },
  {
    name: 'login',
    url: '/app#/login',
    ready: '#login-btn',
    root: '#app-root',
    expectedChannels: ['route'],
    action: async (page) => {
      await page.locator('#app-root .auth-link[href="#/reset-password"]').click();
      await page.waitForURL(/#\/reset-password$/);
    },
  },
  {
    name: 'register',
    url: '/app#/register',
    ready: '#reg-btn',
    root: '#app-root',
    expectedChannels: ['route'],
    action: async (page) => {
      await page.locator('#app-root .auth-link[href="#/login"]').click();
      await page.waitForURL(/#\/login$/);
    },
  },
  {
    name: 'reset-password',
    url: '/app#/reset-password',
    ready: '#reset-btn',
    root: '#app-root',
    expectedChannels: ['route'],
    action: async (page) => {
      await page.locator('#app-root .auth-link[href="#/login"]').click();
      await page.waitForURL(/#\/login$/);
    },
  },
  {
    name: 'dashboard',
    url: '/app#/dashboard',
    ready: '#symbol-chips [data-sym]',
    root: '#app-root',
    expectedChannels: ['network', 'uiAudit'],
    action: async (page) => {
      await page.click('[data-sym="NEE"]');
      await page.waitForFunction(() => window.__dashboardAuditState?.symbol === 'NEE');
    },
  },
  {
    name: 'research',
    url: '/app#/research',
    ready: '#btn-run-research',
    root: '#app-root',
    expectedChannels: ['network'],
    action: async (page) => {
      await page.fill('#r-universe', 'AAPL, MSFT, NVDA');
      const responsePromise = page.waitForResponse((response) => response.url().includes('/api/v1/quant/research/run') && response.request().method() === 'POST');
      await page.click('#btn-run-research');
      await responsePromise;
      await expect(page.locator('#results-body')).toBeVisible();
    },
  },
  {
    name: 'portfolio',
    url: '/app#/portfolio',
    ready: '#wizard-bar',
    root: '#app-root',
    expectedChannels: ['network'],
    action: async (page) => {
      await page.click('#s1-next');
      await page.fill('#po-universe', 'COST, WMT, PG');
      await page.click('#s2-next');
      await page.click('#s3-next');
      const responsePromise = page.waitForResponse((response) => response.url().includes('/api/v1/quant/portfolio/optimize') && response.request().method() === 'POST');
      await page.click('#btn-optimize');
      await responsePromise;
      await expect(page.locator('#wizard-bar')).toBeVisible();
    },
  },
  {
    name: 'backtest',
    url: '/app#/backtest',
    ready: '#btn-run-bt',
    root: '#app-root',
    expectedChannels: ['network'],
    action: async (page) => {
      await page.fill('#bt-universe', 'AAPL, MSFT');
      const responsePromise = page.waitForResponse((response) => response.url().includes('/api/v1/jobs') && response.request().method() === 'POST');
      await page.click('#btn-run-bt');
      await responsePromise;
      await expect(page.locator('#bt-chart-card')).toBeVisible();
    },
  },
  {
    name: 'execution',
    url: '/app#/execution',
    ready: '#btn-run-exec',
    root: '#app-root',
    expectedChannels: ['network'],
    action: async (page) => {
      await page.fill('#ex-universe', 'AAPL, MSFT');
      const responsePromise = page.waitForResponse((response) => response.url().includes('/api/v1/quant/execution/paper') && response.request().method() === 'POST');
      await page.click('#btn-run-exec');
      await responsePromise;
      await expect(page.locator('#btn-kill')).toBeVisible();
    },
  },
  {
    name: 'validation',
    url: '/app#/validation',
    ready: '#btn-run-val',
    root: '#app-root',
    expectedChannels: ['network'],
    action: async (page) => {
      await page.fill('#v-universe', 'AAPL, MSFT');
      const responsePromise = page.waitForResponse((response) => response.url().includes('/api/v1/quant/validation/run') && response.request().method() === 'POST');
      await page.click('#btn-run-val');
      await responsePromise;
      await expect(page.locator('#val-results')).toBeVisible();
    },
  },
  {
    name: 'models',
    url: '/app#/models',
    ready: '#btn-refresh-all',
    root: '#app-root',
    expectedChannels: ['network'],
    action: async (page) => {
      await page.click('#btn-refresh-all');
      await page.waitForTimeout(1200);
    },
  },
  {
    name: 'rl-lab',
    url: '/app#/rl-lab',
    ready: '#rl-recipe',
    root: '#app-root',
    expectedChannels: ['uiAudit'],
    action: async (page) => {
      await page.selectOption('#rl-recipe', 'L2_vol_sentiment');
      await page.waitForFunction(() => window.__rlAuditState?.selectedRecipeKey === 'L2_vol_sentiment');
    },
  },
  {
    name: 'chat',
    url: '/app#/chat',
    ready: '#send-btn',
    root: '#app-root',
    expectedChannels: ['network'],
    action: async (page) => {
      await page.fill('#chat-question', 'Summarize NVDA signal rationale');
      const responsePromise = page.waitForResponse((response) => response.url().includes('/agent/analyze') && response.request().method() === 'POST');
      await page.click('#send-btn');
      await responsePromise;
      await expect(page.locator('#chat-body')).toBeVisible();
    },
  },
  {
    name: 'score',
    url: '/app#/score',
    ready: '#score-btn',
    root: '#app-root',
    expectedChannels: ['network'],
    action: async (page) => {
      const responsePromise = page.waitForResponse((response) => response.url().includes('/agent/esg-score') && response.request().method() === 'POST');
      await page.click('#score-btn');
      await responsePromise;
      await expect(page.locator('#esg-company-name')).toBeVisible();
    },
  },
  {
    name: 'reports',
    url: '/app#/reports',
    ready: '#generate-btn',
    root: '#app-root',
    expectedChannels: ['network'],
    action: async (page) => {
      const responsePromise = page.waitForResponse((response) => {
        const request = response.request();
        return response.url().includes('/api/v1/jobs')
          && request.method() === 'POST'
          && (request.postData() || '').includes('"job_type":"report_generation"');
      });
      await page.click('#generate-btn');
      await responsePromise;
      await expect(page.locator('#report-body')).toBeVisible();
    },
  },
  {
    name: 'data-management',
    url: '/app#/data-management',
    ready: '#sync-btn',
    root: '#app-root',
    expectedChannels: ['network'],
    action: async (page) => {
      const responsePromise = page.waitForResponse((response) => {
        const request = response.request();
        return response.url().includes('/api/v1/jobs')
          && request.method() === 'POST'
          && (request.postData() || '').includes('"job_type":"data_sync"');
      });
      await page.click('#sync-btn');
      await responsePromise;
      await expect(page.locator('#sync-body')).toBeVisible();
    },
  },
  {
    name: 'push-rules',
    url: '/app#/push-rules',
    ready: '#new-rule-btn',
    root: '#app-root',
    expectedChannels: ['network'],
    action: async (page) => {
      const responsePromise = page.waitForResponse((response) => response.url().includes('/admin/push-rules') && response.request().method() === 'POST');
      await page.click('#new-rule-btn');
      await responsePromise;
      await expect(page.locator('#rules-body')).toBeVisible();
    },
  },
  {
    name: 'subscriptions',
    url: '/app#/subscriptions',
    ready: '#create-sub-btn',
    root: '#app-root',
    expectedChannels: ['network'],
    action: async (page) => {
      const responsePromise = page.waitForResponse((response) => response.url().includes('/user/reports/subscribe') && response.request().method() === 'POST');
      await page.click('#create-sub-btn');
      await responsePromise;
      await expect(page.locator('#subscriptions-body')).toBeVisible();
    },
  },
];

test('site-wide click audit captures screenshots, functional channels, and blank-click silence', async ({ page }) => {
  test.setTimeout(20 * 60 * 1000);
  fs.mkdirSync(OUTPUT_DIR, { recursive: true });
  fs.writeFileSync(PROGRESS_LOG, '', 'utf8');
  await stubDashboard(page);
  await stubSiteAuditApis(page);

  const pageErrors = [];
  page.on('pageerror', (error) => pageErrors.push(error.message));

  const report = {
    generatedAt: new Date().toISOString(),
    pageErrors,
    pages: [],
  };

  for (const config of ROUTES) {
    logProgress(`open ${config.name}`);
    await openRoute(page, config);

    const shotPath = screenshotPath(config.name);
    await page.screenshot({ path: shotPath, fullPage: true });

    logProgress(`blank ${config.name}`);
    const blank = await measureAction(page, async () => {
      const point = await findBlankPoint(page, config.root);
      await page.mouse.click(point.x, point.y);
    });
    expect(blank.routeChanged).toBeFalsy();
    expect(blank.requests.length).toBe(0);
    expect(blank.uiAuditDelta).toBe(0);

    logProgress(`functional ${config.name}`);
    await openRoute(page, config);
    const functional = await measureAction(page, async () => {
      await config.action(page);
    });

    if (config.expectedChannels.includes('network')) {
      expect(functional.requests.length).toBeGreaterThan(0);
    }
    if (config.expectedChannels.includes('route')) {
      expect(functional.routeChanged).toBeTruthy();
    }
    if (config.expectedChannels.includes('uiAudit')) {
      expect(functional.uiAuditDelta).toBeGreaterThan(0);
    }

    report.pages.push({
      name: config.name,
      url: config.url,
      screenshot: toReportPath(shotPath),
      expectedChannels: config.expectedChannels,
      blank: {
        routeChanged: blank.routeChanged,
        requestCount: blank.requests.length,
        uiAuditDelta: blank.uiAuditDelta,
      },
      functional: {
        routeChanged: functional.routeChanged,
        requestCount: functional.requests.length,
        uiAuditDelta: functional.uiAuditDelta,
        requestUrls: functional.requests.slice(0, 5).map((item) => item.url),
      },
    });
    logProgress(`done ${config.name}`);
  }

  const reportPath = path.join(OUTPUT_DIR, 'report.json');
  fs.writeFileSync(reportPath, JSON.stringify(report, null, 2), 'utf8');
  expect(fs.existsSync(reportPath)).toBeTruthy();
});
