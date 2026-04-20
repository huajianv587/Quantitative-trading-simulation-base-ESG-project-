const fs = require('fs');
const path = require('path');
const { test, expect } = require('@playwright/test');

const OUTPUT_DIR = path.join(process.cwd(), 'test-results', 'v3-workbench-layout-fixes');

const VIEWPORTS = [
  { name: 'desktop-1440x1100', size: { width: 1440, height: 1100 } },
  { name: 'mobile-390x844', size: { width: 390, height: 844 } },
];

const MODES = [
  { lang: 'en', theme: 'dark' },
  { lang: 'en', theme: 'light' },
  { lang: 'zh', theme: 'dark' },
  { lang: 'zh', theme: 'light' },
];

function screenshotPath(routeName, viewportName, lang, theme, state = 'ready') {
  const dir = path.join(OUTPUT_DIR, routeName);
  fs.mkdirSync(dir, { recursive: true });
  return path.join(dir, `${viewportName}-${lang}-${theme}-${state}.png`);
}

async function configure(page, baseURL, lang, theme) {
  await page.addInitScript(({ apiBase, targetLang, targetTheme }) => {
    window.__ESG_API_BASE_URL__ = apiBase;
    localStorage.setItem('qt-lang', targetLang);
    localStorage.setItem('qt-theme', targetTheme);
  }, { apiBase: baseURL, targetLang: lang, targetTheme: theme });
}

async function attachGuards(page) {
  const consoleErrors = [];
  const failedRequests = [];
  page.on('console', (message) => {
    if (message.type() === 'error') consoleErrors.push(message.text());
  });
  page.on('pageerror', (error) => consoleErrors.push(String(error.message || error)));
  page.on('requestfailed', (request) => {
    const url = request.url();
    if (url.endsWith('/favicon.ico')) return;
    failedRequests.push(`${request.method()} ${url} ${request.failure()?.errorText || ''}`);
  });
  return { consoleErrors, failedRequests };
}

async function assertNoHorizontalOverflow(page, selectors) {
  const overflow = await page.evaluate((targetSelectors) => {
    const rows = [];
    const root = document.documentElement;
    if (root.scrollWidth > root.clientWidth + 4) {
      rows.push({ selector: 'document', scrollWidth: root.scrollWidth, clientWidth: root.clientWidth });
    }
    for (const selector of targetSelectors) {
      document.querySelectorAll(selector).forEach((element, index) => {
        const style = window.getComputedStyle(element);
        const rect = element.getBoundingClientRect();
        if (style.display === 'none' || style.visibility === 'hidden' || rect.width <= 1 || rect.height <= 1) return;
        if (element.scrollWidth > element.clientWidth + 4) {
          rows.push({ selector, index, text: (element.innerText || '').slice(0, 120), scrollWidth: element.scrollWidth, clientWidth: element.clientWidth });
        }
      });
    }
    return rows;
  }, selectors);
  expect(overflow).toEqual([]);
  await expect(page.locator('body')).not.toContainText('Request failed');
}

async function assertNoWhiteInputsInDarkMode(page, enabled) {
  if (!enabled) return;
  const whiteInputs = await page.evaluate(() => {
    const rows = [];
    document.querySelectorAll('input, select, textarea').forEach((element, index) => {
      const rect = element.getBoundingClientRect();
      const style = window.getComputedStyle(element);
      if (rect.width <= 1 || rect.height <= 1 || style.display === 'none' || style.visibility === 'hidden') return;
      const bg = style.backgroundColor.replace(/\s+/g, '');
      if (bg === 'rgb(255,255,255)' || bg === 'rgba(255,255,255,1)') rows.push({ index, id: element.id, bg });
    });
    return rows;
  });
  expect(whiteInputs).toEqual([]);
}

async function mockTradingRoutes(page) {
  const state = {
    monitor: { running: false, mode: 'paper', stream_mode: 'idle', trigger_count: 1, last_event_at: '2026-04-20T14:35:00Z' },
    watchlist: [
      { watchlist_id: 'watch-aapl', symbol: 'AAPL', enabled: true, esg_score: 74.2, last_sentiment: 0.18, added_date: '2026-04-20T08:30:00Z', note: 'default_watchlist_seed' },
      { watchlist_id: 'watch-nvda', symbol: 'NVDA', enabled: true, esg_score: 70.8, last_sentiment: 0.22, added_date: '2026-04-20T08:30:00Z', note: 'default_watchlist_seed' },
    ],
    alerts: [
      { alert_id: 'alert-1', timestamp: '2026-04-20T14:36:00Z', symbol: 'AAPL', trigger_type: 'price_move', trigger_value: 0.024, threshold: 0.02, agent_analysis: 'Bull thesis remains active but risk manager keeps weight capped.', debate_id: 'debate-aapl', risk_decision: 'approve', execution_id: 'paper-aapl-1' },
    ],
    review: {
      review_id: 'review-2026-04-20',
      pnl: 1285.42,
      trades_count: 3,
      approved_decisions: 2,
      blocked_decisions: 1,
      report_text: 'ESG-backed longs outperformed; one block came from elevated drawdown sensitivity.',
      next_day_risk_flags: ['Keep TSLA weight below single-name cap.'],
    },
    debates: [
      {
        debate_id: 'debate-aapl',
        generated_at: '2026-04-20T14:37:00Z',
        symbol: 'AAPL',
        universe: ['AAPL', 'MSFT', 'NVDA', 'TSLA'],
        bull_thesis: 'Bull leans on supportive ESG-linked evidence, promoted factors, and positive sentiment.',
        bear_thesis: 'Bear argues regime risk remains elevated and event-risk factors are unresolved.',
        turns: [
          { round_number: 1, bull_point: 'Bull cites ESG momentum and evidence quality.', bear_point: 'Bear highlights macro fragility and drawdown risk.', evidence_focus: ['AAPL disclosure upgrade', 'macro risk'], confidence_shift: 0.11 },
          { round_number: 2, bull_point: 'Bull leans on sentiment persistence.', bear_point: 'Bear challenges valuation cushion durability.', evidence_focus: ['news sentiment', 'valuation factor'], confidence_shift: 0.07 },
        ],
        conflict_points: ['Sentiment is constructive while regime stress remains elevated.'],
        consensus_points: ['Quant-KB delivered linked ESG evidence.', 'Promoted factor count remains supportive.'],
        judge_verdict: 'long',
        judge_confidence: 0.74,
        dispute_score: 0.21,
        recommended_action: 'long',
        confidence_shift: 0.18,
        requires_human_review: false,
        factor_count: 6,
        sentiment_snapshot_id: 'sent-aapl',
        sentiment_overview: { polarity: 0.24, confidence: 0.76, headline_count: 7, feature_value: 63.2, freshness_score: 0.84, source_mix: { marketaux: 4, yfinance: 3 } },
        expected_edge: 0.032,
      },
    ],
    approvals: [
      {
        approval_id: 'risk-aapl',
        generated_at: '2026-04-20T14:38:00Z',
        symbol: 'AAPL',
        debate_id: 'debate-aapl',
        requested_action: 'long',
        approved_action: 'long',
        verdict: 'approve',
        kelly_fraction: 0.08,
        recommended_weight: 0.05,
        recommended_notional: 5000,
        max_position_weight: 0.26,
        drawdown_estimate: 0.012,
        signal_ttl_minutes: 180,
        hard_blocks: [],
        risk_flags: ['Keep notional within Kelly cap.'],
        rationale: ['Single-name cap respected.', 'No duplicate paper order found.'],
      },
    ],
  };

  await page.route('**/api/v1/trading/debate/runs**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ generated_at: '2026-04-20T14:40:00Z', count: state.debates.length, debates: state.debates }) });
  });

  await page.route('**/api/v1/trading/debate/run', async (route) => {
    const body = route.request().postDataJSON();
    const symbol = String(body.symbol || 'AAPL').toUpperCase();
    const debate = {
      ...state.debates[0],
      debate_id: `debate-${symbol.toLowerCase()}-${state.debates.length + 1}`,
      symbol,
      generated_at: '2026-04-20T14:45:00Z',
      judge_confidence: 0.79,
      confidence_shift: 0.23,
      sentiment_snapshot_id: `sent-${symbol.toLowerCase()}`,
    };
    state.debates.unshift(debate);
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(debate) });
  });

  await page.route('**/api/v1/trading/risk/board**', async (route) => {
    const payload = {
      generated_at: '2026-04-20T14:40:00Z',
      controls: {
        kill_switch_enabled: false,
        default_broker: 'alpaca',
        default_mode: 'paper',
        single_name_weight_cap: 0.26,
        max_daily_orders: 12,
        min_buying_power_buffer: 5000,
        duplicate_order_window_minutes: 15,
        realtime_refresh_seconds: 5,
      },
      approvals: state.approvals,
      latest_approval: state.approvals[0] || null,
      alerts: state.alerts,
    };
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(payload) });
  });

  await page.route('**/api/v1/trading/risk/evaluate', async (route) => {
    const body = route.request().postDataJSON();
    const symbol = String(body.symbol || 'AAPL').toUpperCase();
    const approval = {
      ...state.approvals[0],
      approval_id: `risk-${symbol.toLowerCase()}-${state.approvals.length + 1}`,
      symbol,
      generated_at: '2026-04-20T14:46:00Z',
      recommended_notional: 6200,
    };
    state.approvals.unshift(approval);
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(approval) });
  });

  await page.route('**/api/v1/trading/ops/snapshot', async (route) => {
    const payload = {
      generated_at: '2026-04-20T14:40:00Z',
      schedule: {
        jobs: [
          { job_name: 'premarket_agent', next_run: '2026-04-21T08:30:00-04:00', schedule: 'mon-fri 08:30' },
          { job_name: 'intraday_monitor_start', next_run: '2026-04-21T09:30:00-04:00', schedule: 'mon-fri 09:30' },
          { job_name: 'review_agent', next_run: '2026-04-20T21:30:00-04:00', schedule: 'mon-fri 21:30' },
        ],
        recent_runs: [],
      },
      monitor: state.monitor,
      watchlist: { watchlist: state.watchlist, count: state.watchlist.length },
      today_alerts: { alerts: state.alerts, alert_count: state.alerts.length },
      latest_review: { review: state.review },
      debates: { count: state.debates.length, debates: state.debates.slice(0, 5) },
      risk: { approvals: state.approvals, latest_approval: state.approvals[0] || null },
      notifier: { telegram_configured: false, mode: 'paper_shadow_notify' },
    };
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(payload) });
  });

  await page.route('**/api/v1/trading/watchlist/add', async (route) => {
    const body = route.request().postDataJSON();
    const symbol = String(body.symbol || 'AAPL').toUpperCase();
    if (!state.watchlist.some((row) => row.symbol === symbol)) {
      state.watchlist.unshift({
        watchlist_id: `watch-${symbol.toLowerCase()}`,
        symbol,
        enabled: true,
        esg_score: 68.4,
        last_sentiment: 0.14,
        added_date: '2026-04-20T14:47:00Z',
        note: body.note || 'ui_watchlist_add',
      });
    }
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ watchlist_item: state.watchlist[0], watchlist: state.watchlist }) });
  });

  await page.route('**/api/v1/trading/monitor/start', async (route) => {
    state.monitor = { ...state.monitor, running: true, stream_mode: 'websocket' };
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(state.monitor) });
  });

  await page.route('**/api/v1/trading/monitor/stop', async (route) => {
    state.monitor = { ...state.monitor, running: false, stream_mode: 'idle' };
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(state.monitor) });
  });

  await page.route('**/api/v1/trading/jobs/run/**', async (route) => {
    state.review = {
      ...state.review,
      review_id: 'review-premarket-manual',
      report_text: 'Premarket briefing refreshed, ESG delta queued, and watchlist synced.',
      trades_count: 0,
    };
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ run_id: 'job-premarket-manual', job_name: 'premarket_agent', status: 'completed' }) });
  });

  await page.route('**/api/v1/trading/cycle/run', async (route) => {
    state.alerts.unshift({
      alert_id: `alert-${state.alerts.length + 1}`,
      timestamp: '2026-04-20T14:48:00Z',
      symbol: 'MSFT',
      trigger_type: 'volume_spike',
      trigger_value: 3.5,
      threshold: 3.0,
      agent_analysis: 'Debate approved a reduced paper submission after a fresh sentiment check.',
      debate_id: state.debates[0]?.debate_id || null,
      risk_decision: 'reduce',
      execution_id: `paper-msft-${state.alerts.length + 1}`,
    });
    state.review = {
      ...state.review,
      trades_count: 4,
      approved_decisions: 3,
      blocked_decisions: 1,
      report_text: 'Paper cycle closed with one reduced submission and no hard blocks.',
    };
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ bundle_id: 'bundle-cycle-1', execution: { submitted: true, status: 'submitted' } }) });
  });
}

for (const viewport of VIEWPORTS) {
  for (const mode of MODES) {
    test(`trading agent workbench ${viewport.name} ${mode.lang} ${mode.theme}`, async ({ page, baseURL }) => {
      test.setTimeout(180000);
      const guards = await attachGuards(page);
      await page.setViewportSize(viewport.size);
      await configure(page, baseURL, mode.lang, mode.theme);
      await mockTradingRoutes(page);

      await page.goto('/app/#/debate-desk', { waitUntil: 'domcontentloaded' });
      await expect(page.locator('#btn-debate-run')).toBeVisible();
      await page.locator('#btn-debate-run').click();
      await expect(page.locator('#debate-current')).toContainText(/Bull|Judge|Sentiment Overlay|情绪叠层/);
      await assertNoWhiteInputsInDarkMode(page, mode.theme === 'dark');
      await assertNoHorizontalOverflow(page, ['.workbench-item', '.workbench-action-btn', '.workbench-metric-card', '.workbench-kv-row']);
      await page.screenshot({ path: screenshotPath('debate-desk', viewport.name, mode.lang, mode.theme, 'after-actions'), fullPage: true });

      await page.goto('/app/#/risk-board', { waitUntil: 'domcontentloaded' });
      await expect(page.locator('#btn-risk-evaluate')).toBeVisible();
      await page.locator('#btn-risk-evaluate').click();
      await expect(page.locator('#risk-latest')).toContainText(/approve|Approve|APPROVE|审批|批准/);
      await assertNoWhiteInputsInDarkMode(page, mode.theme === 'dark');
      await assertNoHorizontalOverflow(page, ['.workbench-item', '.workbench-action-btn', '.workbench-metric-card', '.workbench-kv-row']);
      await page.screenshot({ path: screenshotPath('risk-board', viewport.name, mode.lang, mode.theme, 'after-actions'), fullPage: true });

      await page.goto('/app/#/trading-ops', { waitUntil: 'domcontentloaded' });
      await expect(page.locator('#btn-trading-ops-refresh')).toBeVisible();
      await page.locator('#ops-symbol').fill('MSFT');
      await page.locator('#btn-watchlist-add').click();
      await expect(page.locator('#ops-watchlist')).toContainText('MSFT');
      await page.locator('#btn-monitor-start').click();
      await expect(page.locator('#ops-schedule')).toContainText(/websocket|stream/);
      await page.locator('#btn-run-premarket').click();
      await page.locator('#btn-trading-cycle').click();
      await expect(page.locator('#ops-alerts')).toContainText(/MSFT|volume_spike|Debate/);
      await expect(page.locator('#ops-review')).toContainText(/Paper cycle|Premarket|review/);
      await assertNoWhiteInputsInDarkMode(page, mode.theme === 'dark');
      await assertNoHorizontalOverflow(page, ['.workbench-item', '.workbench-action-btn', '.workbench-metric-card', '.workbench-kv-row']);
      await page.screenshot({ path: screenshotPath('trading-ops', viewport.name, mode.lang, mode.theme, 'after-actions'), fullPage: true });

      expect(guards.consoleErrors).toEqual([]);
      expect(guards.failedRequests).toEqual([]);
    });
  }
}
