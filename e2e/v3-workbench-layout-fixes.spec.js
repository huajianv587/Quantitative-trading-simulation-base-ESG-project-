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
    if (url.includes('fonts.googleapis.com') || url.includes('fonts.gstatic.com') || url.endsWith('/favicon.ico')) return;
    failedRequests.push(`${request.method()} ${url} ${request.failure()?.errorText || ''}`);
  });
  return { consoleErrors, failedRequests };
}

async function assertNoHorizontalOverflow(page, selectors = []) {
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
        if (element.scrollWidth > element.clientWidth + 5) {
          rows.push({
            selector,
            index,
            text: (element.innerText || element.value || '').slice(0, 160),
            scrollWidth: element.scrollWidth,
            clientWidth: element.clientWidth,
          });
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
      if (bg === 'rgb(255,255,255)' || bg === 'rgba(255,255,255,1)') {
        rows.push({ index, id: element.id, bg });
      }
    });
    return rows;
  });
  expect(whiteInputs).toEqual([]);
}

async function assertCardStackTight(page, selector, maxGap = 32) {
  const gaps = await page.evaluate((stackSelector) => {
    const nodes = Array.from(document.querySelectorAll(`${stackSelector} > .card, ${stackSelector} > .run-panel`))
      .map((element) => element.getBoundingClientRect())
      .filter((rect) => rect.width > 1 && rect.height > 1)
      .sort((a, b) => a.top - b.top);
    const values = [];
    for (let i = 1; i < nodes.length; i += 1) {
      values.push(Math.round(nodes[i].top - nodes[i - 1].bottom));
    }
    return values;
  }, selector);
  expect(gaps.every((gap) => gap <= maxGap)).toBeTruthy();
}

async function assertBalancedWidth(page, leftSelector, rightSelector, tolerance = 48) {
  const diff = await page.evaluate(([left, right]) => {
    const a = document.querySelector(left)?.getBoundingClientRect();
    const b = document.querySelector(right)?.getBoundingClientRect();
    if (!a || !b) return null;
    return Math.abs(a.width - b.width);
  }, [leftSelector, rightSelector]);
  expect(diff).not.toBeNull();
  expect(diff).toBeLessThanOrEqual(tolerance);
}

async function assertBottomAligned(page, leftSelector, rightSelector, tolerance = 32) {
  const diff = await page.evaluate(([left, right]) => {
    const a = document.querySelector(left)?.getBoundingClientRect();
    const b = document.querySelector(right)?.getBoundingClientRect();
    if (!a || !b) return null;
    return Math.abs(a.bottom - b.bottom);
  }, [leftSelector, rightSelector]);
  expect(diff).not.toBeNull();
  expect(diff).toBeLessThanOrEqual(tolerance);
}

function providers() {
  return [
    { provider_id: 'local_esg', display_name: 'Local ESG Corpus', configured: true, capabilities: ['esg_reports', 'local_evidence'], daily_limit: 1000000, scan_budget: 1000000, manual_reserve: 0, priority: 10, free_tier_note: 'Local paper-grade ESG corpus and embeddings; no external request.', quota: { used_today: 28, remaining_estimate: 999972 } },
    { provider_id: 'sec_edgar', display_name: 'SEC EDGAR', configured: true, capabilities: ['filings', 'company_facts'], daily_limit: 500, scan_budget: 80, manual_reserve: 420, priority: 20, free_tier_note: 'Public SEC EDGAR access with responsible User-Agent.', quota: { used_today: 0, remaining_estimate: 500 } },
    { provider_id: 'marketaux', display_name: 'Marketaux Free', configured: true, capabilities: ['news', 'sentiment', 'events'], daily_limit: 100, scan_budget: 60, manual_reserve: 40, priority: 30, free_tier_note: '100 requests/day, 3 articles per news request.', quota: { used_today: 3, remaining_estimate: 97 } },
    { provider_id: 'twelvedata', display_name: 'Twelve Data Free', configured: true, capabilities: ['daily_ohlcv', 'indicators'], daily_limit: 800, scan_budget: 500, manual_reserve: 300, priority: 35, free_tier_note: '800 credits/day budget; cache-first for backtests.', quota: { used_today: 9, remaining_estimate: 791 } },
    { provider_id: 'thenewsapi', display_name: 'TheNewsAPI Free', configured: true, capabilities: ['news_fallback'], daily_limit: 100, scan_budget: 40, manual_reserve: 60, priority: 45, free_tier_note: '100 requests/day fallback confirmation source.', quota: { used_today: 0, remaining_estimate: 100 } },
    { provider_id: 'alpaca_market', display_name: 'Alpaca Market/Paper Free', configured: false, capabilities: ['iex_prices', 'paper_execution'], daily_limit: 5000, scan_budget: 1000, manual_reserve: 4000, priority: 55, free_tier_note: 'Free IEX-only market data; paper trading only.', quota: { used_today: 0, remaining_estimate: 5000 } },
    { provider_id: 'alpha_vantage', display_name: 'Alpha Vantage Free', configured: false, capabilities: ['indicator_fallback'], daily_limit: 25, scan_budget: 10, manual_reserve: 15, priority: 70, free_tier_note: '25 requests/day fallback only.', quota: { used_today: 0, remaining_estimate: 25 } },
  ];
}

function evidenceItems(count = 12) {
  const providerPool = ['local_esg', 'marketaux', 'twelvedata', 'thenewsapi'];
  return Array.from({ length: count }, (_, index) => {
    const n = index + 1;
    const provider = providerPool[index % providerPool.length];
    return {
      item_id: `ev-${n}`,
      item_type: index % 4 === 0 ? 'rag_evidence' : index % 4 === 1 ? 'model_signal' : index % 4 === 2 ? 'market_price' : 'news',
      provider,
      title: `AAPL factor ${['momentum', 'quality', 'value', 'alternative_data', 'regime_fit', 'esg_delta'][index % 6]}`,
      summary: `As-of safe evidence ${n}; value=${(70 + index).toFixed(2)}; contribution=${(0.10 + index * 0.01).toFixed(2)}.`,
      symbol: index % 5 === 0 ? 'MSFT' : 'AAPL',
      confidence: 0.72 + (index % 4) * 0.03,
      quality_score: 0.75 + (index % 5) * 0.02,
      leakage_guard: 'as_of_safe',
      published_at: '2026-04-18T08:00:00Z',
      observed_at: '2026-04-18T08:05:00Z',
    };
  });
}

function factorCards(count = 50) {
  const statuses = ['promoted', 'research_only', 'low_confidence', 'rejected', 'promoted'];
  const families = ['freshness_decay', 'evidence_quality', 'event_risk', 'regime_interaction', 'novelty'];
  return Array.from({ length: count }, (_, index) => {
    const status = statuses[index % statuses.length];
    return {
      name: `factor_${String(index + 1).padStart(2, '0')}_${status}`,
      family: families[index % families.length],
      status,
      definition: `As-of safe candidate ${index + 1} with provider lineage and leakage guard.`,
      ic: status === 'rejected' ? -0.02 * (index % 5 + 1) : 0.015 * (index % 7 + 1),
      rank_ic: status === 'low_confidence' ? -0.12 : 0.10 + (index % 5) * 0.05,
      stability_score: 0.34 + (index % 8) * 0.07,
      sample_count: 3 + (index % 9),
      turnover_estimate: 0.08 + (index % 4) * 0.05,
      missing_rate: (index % 5) * 0.01,
      transaction_cost_sensitivity: index % 3 === 0 ? 'medium' : 'low',
      failure_modes: status === 'promoted' ? [] : ['weak IC in current shadow sample'],
    };
  });
}

function simulationResult() {
  return {
    simulation_id: 'sim-layout-001',
    scenario: { symbol: 'AAPL', scenario_name: 'risk_off_stress', regime: 'risk_off', shock_bps: -125, paths: 512, seed: 42 },
    expected_return: 0.018,
    probability_of_loss: 0.34,
    value_at_risk_95: -0.052,
    max_drawdown_p95: -0.09,
    path_summary: { p05: -0.052, p50: 0.018, p95: 0.071 },
    factor_attribution: { momentum: 0.21, quality: 0.17, esg_delta: 0.12 },
    historical_analogs: [
      { title: 'Quality tech in risk-off replay', symbol: 'AAPL', event_type: 'regime_stress', quality_score: 0.78 },
    ],
  };
}

function backtestResult() {
  const timeline = Array.from({ length: 84 }, (_, index) => {
    const date = new Date(Date.UTC(2025, 0, 2 + index));
    const portfolioNav = 1 + index * 0.0018 + Math.sin(index / 5) * 0.006;
    const benchmarkNav = 1 + index * 0.0010 + Math.cos(index / 6) * 0.004;
    return {
      date: date.toISOString().slice(0, 10),
      portfolio_nav: portfolioNav,
      benchmark_nav: benchmarkNav,
    };
  });
  return {
    backtest_id: 'bt-layout-001',
    strategy_name: 'ESG Multi-Factor Long-Only',
    benchmark: 'SPY',
    period_start: timeline[0].date,
    period_end: timeline[timeline.length - 1].date,
    timeline,
    metrics: {
      cumulative_return: 0.146,
      annualized_return: 0.214,
      annualized_volatility: 0.118,
      sharpe: 1.74,
      max_drawdown: -0.061,
      hit_rate: 0.61,
      beta: 0.87,
      information_ratio: 0.54,
    },
    risk_alerts: [
      { level: 'medium', title: 'Regime sensitivity', description: 'Strategy remains exposed to risk-off shocks.', recommendation: 'Keep stress tests active.' },
    ],
    data_source: 'twelvedata',
    data_source_chain: ['twelvedata', 'cache:twelvedata'],
    used_synthetic_fallback: false,
    market_data_warnings: [],
  };
}

async function mockRoutes(page) {
  const registry = {
    mode: 'free_tier_first',
    generated_at: '2026-04-18T10:00:00Z',
    defaults: { alpaca_feed: 'iex' },
    providers: providers(),
  };
  const evidence = evidenceItems(12);
  const factorPayload = {
    run_id: 'factor-layout-50',
    factors: factorCards(50),
    factor_cards: factorCards(50),
    promotion_policy: 'Only promoted factors can become runtime inputs; research-only factors remain visible but gated.',
    lineage: ['candidate generation', 'as-of feature build', 'IC / RankIC gate', 'cost sensitivity review', 'registry promotion decision'],
  };
  const decision = {
    decision_id: 'decision-layout-001',
    symbol: 'AAPL',
    action: 'hold',
    expected_return: 0.024,
    confidence: 0.72,
    confidence_interval: { lower: -0.012, center: 0.024, upper: 0.061 },
    position_weight_range: { min: 0.02, max: 0.08 },
    verifier_checks: { verdict: 'review', leakage_pass: true },
    risk_triggers: ['Volatility spike above threshold', 'Evidence source quality drops below 0.70'],
    factor_cards: factorCards(3),
    main_evidence: evidence.slice(0, 6),
    counter_evidence: [
      { ...evidence[0], item_id: 'counter-1', title: 'Counter: valuation pressure', summary: 'Valuation multiple remains sensitive to rate shocks.' },
    ],
    simulation: simulationResult(),
  };

  await page.route('**/api/v1/connectors/registry', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(registry) }));
  await page.route('**/api/v1/connectors/health**', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ run_id: 'health-layout-001', results: providers().map(row => ({ provider: row.provider_id, status: row.configured ? 'configured' : 'missing_key', configured: row.configured, normalized_count: 0, latency_ms: 0 })), summary: { ok_count: 5, failed_count: 2, quota_protected_count: 0, failure_isolation: 'enabled' } }) }));
  await page.route('**/api/v1/connectors/test', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ run_id: 'dry-test-layout-001', results: providers().slice(0, 5).map(row => ({ provider: row.provider_id, status: row.configured ? 'dry_run_ready' : 'missing_key', configured: row.configured, normalized_count: 1, latency_ms: 0 })), summary: { ok_count: 4, failed_count: 1, quota_protected_count: 0 } }) }));
  await page.route('**/api/v1/connectors/live-scan', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ bundle_id: 'evidence-layout-001', generated_at: '2026-04-18T10:00:00Z', decision_time: '2026-04-18T10:00:00Z', items: evidence, quality_summary: { item_count: evidence.length }, summary: { ok_count: 4, failed_count: 0, quota_protected_count: 0 }, lineage: ['free-tier scan', 'normalization', 'as-of guard', 'decision-ready feed'] }) }));
  await page.route('**/api/v1/connectors/quota**', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ providers: providers().map(row => row.quota) }) }));
  await page.route('**/api/v1/connectors/runs**', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ runs: [] }) }));
  await page.route('**/api/v1/quant/intelligence/evidence**', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ items: evidence, lineage: ['free-tier scan', 'normalization', 'as-of guard', 'decision-ready feed'] }) }));
  await page.route('**/api/v1/quant/intelligence/scan', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ items: evidence, lineage: ['source-linked evidence', 'verifier-ready'] }) }));
  await page.route('**/api/v1/quant/factors/registry**', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(factorPayload) }));
  await page.route('**/api/v1/quant/factors/discover', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(factorPayload) }));
  await page.route('**/api/v1/quant/decision/explain', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(decision) }));
  await page.route('**/api/v1/quant/decision/audit-trail**', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ records: [{ decision_id: 'decision-layout-001', symbol: 'AAPL', data_version: 'mock-v3', model_version: 'shadow-stack', feature_time: '2026-04-18T10:00:00Z', status: 'recorded' }] }) }));
  await page.route('**/api/v1/quant/simulate/scenario', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(simulationResult()) }));
  await page.route('**/api/v1/quant/outcomes/evaluate', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ record_count: 3, hit_rate: 0.67, mean_brier: 0.21, mean_excess_return: 0.008, drawdown_breaches: 0, shadow_mode: true, latest_record: { symbol: 'AAPL', realized_return: 0.012, benchmark_return: 0.004, decision_id: 'demo-decision' } }) }));
  await page.route('**/api/v1/quant/backtests', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ backtests: [{ backtest_id: 'bt-layout-001', strategy_name: 'ESG Multi-Factor Long-Only', period_start: '2025-01-02', metrics: { sharpe: 1.74 } }] }) }));
  await page.route('**/api/v1/quant/backtests/bt-layout-001', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(backtestResult()) }));
  await page.route('**/api/v1/quant/backtests/run', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(backtestResult()) }));
}

const overflowSelectors = [
  '.field',
  '.workbench-action-btn',
  '.workbench-item',
  '.workbench-metric-card',
  '.workbench-mini-metric',
  '.workbench-link-card',
  '.factor-gate-row',
  '.factor-status-tab',
  '.factor-page-btn',
  '.live-provider-card',
  '.metric-card',
  '.workbench-kv-row',
];

for (const viewport of VIEWPORTS) {
  for (const mode of MODES) {
    test(`V3 layout fixes ${viewport.name} ${mode.lang} ${mode.theme}`, async ({ page, baseURL }) => {
      test.setTimeout(240000);
      const guards = await attachGuards(page);
      await page.setViewportSize(viewport.size);
      await configure(page, baseURL, mode.lang, mode.theme);
      await mockRoutes(page);
      const isDark = mode.theme === 'dark';
      const isDesktop = viewport.size.width >= 900;

      await page.goto('/app/#/connector-center', { waitUntil: 'domcontentloaded' });
      await expect(page.locator('#btn-connector-health')).toBeVisible();
      if (isDesktop) {
        await expect(page.locator('[data-group-id="market_intel"]')).toHaveClass(/is-open/);
        await page.locator('[data-group-trigger="decision_hub"]').click();
        await expect(page.locator('[data-group-id="decision_hub"]')).toHaveClass(/is-open/);
        await expect(page.locator('[data-group-id="decision_hub"] .nav-item[href="#/debate-desk"]')).toBeVisible();
      }
      await assertNoWhiteInputsInDarkMode(page, isDark);
      await page.locator('#btn-connector-health').click();
      await page.locator('#btn-connector-test').click();
      await page.locator('#btn-connector-live-scan').click();
      await expect(page.locator('#connector-result')).toContainText(/evidence-layout-001|dry-test-layout-001|health-layout-001/);
      await assertNoHorizontalOverflow(page, overflowSelectors);
      await page.screenshot({ path: screenshotPath('connector-center', viewport.name, mode.lang, mode.theme, 'after-actions'), fullPage: true });

      await page.goto('/app/#/market-radar', { waitUntil: 'domcontentloaded' });
      await expect(page.locator('#btn-market-radar-scan')).toBeVisible();
      await assertNoWhiteInputsInDarkMode(page, isDark);
      await expect(page.locator('#market-radar-feed .workbench-item')).toHaveCount(5);
      const radarPageTwo = page.locator('#market-radar-feed .workbench-page-btn').filter({ hasText: /^2$/ });
      await expect(radarPageTwo).toBeVisible();
      await radarPageTwo.click();
      await expect(page.locator('#market-radar-feed .workbench-item')).toHaveCount(5);
      if (isDesktop) await assertBottomAligned(page, '.market-radar-layout > .card:first-child', '.market-radar-layout > .card:last-child', 48);
      await assertNoHorizontalOverflow(page, overflowSelectors);
      await page.screenshot({ path: screenshotPath('market-radar', viewport.name, mode.lang, mode.theme, 'page-2'), fullPage: true });

      await page.goto('/app/#/agent-lab', { waitUntil: 'domcontentloaded' });
      await expect(page.locator('#btn-agent-workflow')).toBeVisible();
      await assertNoWhiteInputsInDarkMode(page, isDark);
      await expect(page.locator('#agent-timeline .preview-step')).toHaveCount(6);
      await page.locator('#btn-agent-workflow').click({ force: true });
      await expect(page.locator('#agent-report')).toContainText(/Loss Prob|VaR|Simulation|Outcome/);
      if (isDesktop) await assertBalancedWidth(page, '#agent-timeline', '#agent-report', 90);
      await assertNoHorizontalOverflow(page, overflowSelectors);
      await page.screenshot({ path: screenshotPath('agent-lab', viewport.name, mode.lang, mode.theme, 'after-actions'), fullPage: true });

      await page.goto('/app/#/intelligence', { waitUntil: 'domcontentloaded' });
      await expect(page.locator('#btn-decision-explain')).toBeVisible();
      await assertNoWhiteInputsInDarkMode(page, isDark);
      await page.locator('#btn-intel-scan').click();
      await page.locator('#btn-decision-explain').click();
      await expect(page.locator('#decision-summary')).toContainText(/Verifier|Risk|Decision|决策|风险|验证/);
      await expect(page.locator('.decision-stack--right > .card')).toHaveCount(6);
      if (isDesktop) await assertCardStackTight(page, '.decision-stack--right', 28);
      await assertNoHorizontalOverflow(page, overflowSelectors);
      await page.screenshot({ path: screenshotPath('intelligence', viewport.name, mode.lang, mode.theme, 'after-actions'), fullPage: true });

      await page.goto('/app/#/factor-lab', { waitUntil: 'domcontentloaded' });
      await expect(page.locator('#btn-factor-discover')).toBeVisible();
      await assertNoWhiteInputsInDarkMode(page, isDark);
      await expect(page.locator('[data-factor-row]')).toHaveCount(10);
      if (isDesktop) {
        const columns = await page.locator('[data-factor-row]').evaluateAll((rows) => {
          return Array.from(new Set(rows.slice(0, 10).map((row) => Math.round(row.getBoundingClientRect().left))));
        });
        expect(columns.length).toBeGreaterThanOrEqual(2);
      }
      await page.locator('.factor-status-tab[data-factor-status="promoted"]').click();
      await expect(page.locator('.factor-status-tab[data-factor-status="promoted"]')).toHaveClass(/active/);
      await expect(page.locator('[data-factor-row]')).toHaveCount(10);
      await page.locator('.factor-status-tab[data-factor-status=""]').click();
      await expect(page.locator('.factor-page-number[data-factor-page="2"]')).toBeVisible();
      await page.locator('.factor-page-number[data-factor-page="2"]').click();
      await expect(page.locator('.factor-page-number[data-factor-page="2"]')).toHaveClass(/active/);
      await expect(page.locator('[data-factor-row]')).toHaveCount(10);
      await page.locator('#btn-factor-discover').click();
      await assertNoHorizontalOverflow(page, overflowSelectors);
      await page.screenshot({ path: screenshotPath('factor-lab', viewport.name, mode.lang, mode.theme, 'after-actions'), fullPage: true });

      await page.goto('/app/#/backtest', { waitUntil: 'domcontentloaded' });
      await expect(page.locator('#run-backtest-btn, #btn-run-bt')).toBeVisible();
      await assertNoWhiteInputsInDarkMode(page, isDark);
      await expect(page.locator('#bt-placeholder')).toContainText(/Backtest Preview|real-data|真实|回测/);
      await page.locator('#run-backtest-btn, #btn-run-bt').click();
      await expect(page.locator('#bt-metrics')).toContainText(/twelvedata|Data Source/);
      await expect(page.locator('#equity-canvas')).toBeVisible();
      await assertNoHorizontalOverflow(page, overflowSelectors);
      await page.screenshot({ path: screenshotPath('backtest', viewport.name, mode.lang, mode.theme, 'after-actions'), fullPage: true });

      await page.goto('/app/#/outcome-center', { waitUntil: 'domcontentloaded' });
      await expect(page.locator('#btn-outcome-record')).toBeVisible();
      await assertNoWhiteInputsInDarkMode(page, isDark);
      await page.locator('#btn-outcome-refresh').click();
      await page.locator('#btn-outcome-record').click();
      await expect(page.locator('#outcome-records')).toContainText(/demo-decision|AAPL|Records|记录/);
      if (isDesktop) await assertBalancedWidth(page, '#outcome-summary', '#outcome-records', 90);
      await assertNoHorizontalOverflow(page, overflowSelectors);
      await page.screenshot({ path: screenshotPath('outcome-center', viewport.name, mode.lang, mode.theme, 'after-actions'), fullPage: true });

      expect(guards.consoleErrors).toEqual([]);
      expect(guards.failedRequests).toEqual([]);
    });
  }
}
