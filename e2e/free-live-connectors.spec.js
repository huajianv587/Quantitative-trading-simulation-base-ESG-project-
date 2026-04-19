const fs = require('fs');
const path = require('path');
const { test, expect } = require('@playwright/test');

const OUTPUT_DIR = path.join(process.cwd(), 'test-results', 'v3-free-live-connectors');
const VIEWPORTS = [
  { name: 'desktop-1440x1100', size: { width: 1440, height: 1100 } },
  { name: 'mobile-390x844', size: { width: 390, height: 844 } },
];
const MODES = [
  { lang: 'en', theme: 'dark' },
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

async function guards(page) {
  const consoleErrors = [];
  const failedRequests = [];
  page.on('console', message => {
    if (message.type() === 'error') consoleErrors.push(message.text());
  });
  page.on('pageerror', error => consoleErrors.push(String(error.message || error)));
  page.on('requestfailed', request => {
    const url = request.url();
    if (url.endsWith('/favicon.ico')) return;
    failedRequests.push(`${request.method()} ${url} ${request.failure()?.errorText || ''}`);
  });
  return { consoleErrors, failedRequests };
}

async function assertNoOverflow(page, selectors) {
  const overflow = await page.evaluate((targetSelectors) => {
    const rows = [];
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

function providerRows() {
  return [
    { provider_id: 'local_esg', display_name: 'Local ESG Corpus', configured: true, capabilities: ['esg_reports'], daily_limit: 1000000, scan_budget: 1000000, manual_reserve: 0, priority: 10, free_tier_note: 'Local paper-grade ESG corpus.', quota: { used_today: 2, remaining_estimate: 999998 } },
    { provider_id: 'marketaux', display_name: 'Marketaux Free', configured: false, capabilities: ['news', 'sentiment'], daily_limit: 100, scan_budget: 60, manual_reserve: 40, priority: 30, free_tier_note: '100 requests/day, 3 articles/request.', quota: { used_today: 0, remaining_estimate: 100 } },
    { provider_id: 'twelvedata', display_name: 'Twelve Data Free', configured: true, capabilities: ['prices', 'ohlcv'], daily_limit: 800, scan_budget: 500, manual_reserve: 300, priority: 40, free_tier_note: '800 credits/day budget.', quota: { used_today: 12, remaining_estimate: 788 } },
    { provider_id: 'thenewsapi', display_name: 'TheNewsAPI Free', configured: false, capabilities: ['news'], daily_limit: 100, scan_budget: 40, manual_reserve: 60, priority: 55, free_tier_note: '100 requests/day.', quota: { used_today: 0, remaining_estimate: 100 } },
    { provider_id: 'alpaca_market', display_name: 'Alpaca IEX/Paper', configured: true, capabilities: ['iex_prices'], daily_limit: 5000, scan_budget: 1000, manual_reserve: 4000, priority: 35, free_tier_note: 'IEX-only free market data.', quota: { used_today: 4, remaining_estimate: 4996 } },
    { provider_id: 'alpha_vantage', display_name: 'Alpha Vantage Free', configured: true, capabilities: ['prices'], daily_limit: 25, scan_budget: 10, manual_reserve: 15, priority: 75, free_tier_note: '25 requests/day fallback only.', quota: { used_today: 1, remaining_estimate: 24 } },
  ];
}

function evidenceItems() {
  return [
    { item_id: 'ev-1', item_type: 'news', provider: 'marketaux', title: 'AAPL supplier audit improves', summary: 'Positive supplier audit update with sentiment metadata.', symbol: 'AAPL', confidence: 0.74, quality_score: 0.81, leakage_guard: 'as_of_safe' },
    { item_id: 'ev-2', item_type: 'market_signal', provider: 'twelvedata', title: 'AAPL daily OHLCV', summary: 'close=198.2, volume stable.', symbol: 'AAPL', confidence: 0.71, quality_score: 0.76, leakage_guard: 'as_of_safe' },
    { item_id: 'ev-3', item_type: 'esg_report', provider: 'local_esg', title: 'AAPL local ESG report', summary: 'Local ESG evidence is available.', symbol: 'AAPL', confidence: 0.88, quality_score: 0.91, leakage_guard: 'as_of_safe' },
  ];
}

async function mockRoutes(page) {
  const registry = { generated_at: '2026-04-18T10:00:00Z', mode: 'free_tier_first', providers: providerRows(), defaults: { alpaca_feed: 'iex' } };
  const scan = { bundle_id: 'evidence-free-live-visual', generated_at: '2026-04-18T10:00:00Z', decision_time: '2026-04-18T10:00:00Z', items: evidenceItems(), quality_summary: { item_count: 3 }, summary: { ok_count: 3, failed_count: 0, quota_protected_count: 0 }, lineage: ['free-tier scan', 'normalization', 'as-of guard'] };
  await page.route('**/api/v1/connectors/registry', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(registry) }));
  await page.route('**/api/v1/connectors/health**', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ providers: providerRows().map(row => ({ provider: row.provider_id, display_name: row.display_name, configured: row.configured, status: row.configured ? 'configured' : 'missing_key', quota: row.quota })), summary: { configured: 4, ok: 4, failed: 2, failure_isolation: 'enabled' } }) }));
  await page.route('**/api/v1/connectors/test', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ run_id: 'connector-test-visual', results: providerRows().slice(0, 3).map(row => ({ provider: row.provider_id, status: row.configured ? 'dry_run_ready' : 'missing_key', configured: row.configured, normalized_count: 0, latency_ms: 0 })), summary: { ok_count: 2, failed_count: 1, quota_protected_count: 0, failure_isolation: 'enabled' } }) }));
  await page.route('**/api/v1/connectors/live-scan', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(scan) }));
  await page.route('**/api/v1/connectors/quota**', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ providers: providerRows().map(row => row.quota) }) }));
  await page.route('**/api/v1/connectors/runs**', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ runs: [scan] }) }));
  await page.route('**/api/v1/quant/intelligence/evidence**', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ items: evidenceItems() }) }));
  await page.route('**/api/v1/quant/factors/discover', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ run_id: 'factor-live-visual', factor_cards: [{ name: 'live_news_sentiment', family: 'news', status: 'promoted', definition: 'Free-tier news sentiment factor.', ic: 0.12, rank_ic: 0.22, stability_score: 0.61, sample_count: 4 }] }) }));
  await page.route('**/api/v1/quant/decision/explain', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ decision_id: 'decision-live-visual', symbol: 'AAPL', action: 'long', confidence: 0.72, expected_return: 0.024, main_evidence: evidenceItems(), counter_evidence: [], audit_trail: ['shadow mode'], verifier_checks: { verdict: 'pass' } }) }));
  await page.route('**/api/v1/quant/simulate/scenario', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ simulation_id: 'sim-live-visual', scenario: { symbol: 'AAPL' }, expected_return: 0.018, probability_of_loss: 0.34, value_at_risk_95: -0.052, max_drawdown_p95: 0.09, path_summary: { p05: -0.052, p50: 0.018, p95: 0.071 }, factor_attribution: { news: 0.21 }, historical_analogs: [] }) }));
  await page.route('**/api/v1/quant/outcomes/evaluate', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ record_count: 3, hit_rate: 0.67, mean_brier: 0.21, mean_excess_return: 0.008, drawdown_breaches: 0, shadow_mode: true }) }));
}

for (const viewport of VIEWPORTS) {
  for (const mode of MODES) {
    test(`V3 free live pages ${viewport.name} ${mode.lang} ${mode.theme}`, async ({ page, baseURL }) => {
      test.setTimeout(180000);
      const state = await guards(page);
      await page.setViewportSize(viewport.size);
      await configure(page, baseURL, mode.lang, mode.theme);
      await mockRoutes(page);

      await page.goto('/app/#/connector-center', { waitUntil: 'domcontentloaded' });
      await expect(page.locator('#btn-connector-health')).toBeVisible();
      await page.locator('#btn-connector-health').click();
      await expect(page.locator('#connector-result')).toContainText(/local_esg|configured|missing_key/);
      await page.locator('#btn-connector-test').click();
      await expect(page.locator('#connector-result')).toContainText('connector-test-visual');
      await page.locator('#btn-connector-live-scan').click();
      await expect(page.locator('#connector-result')).toContainText('evidence-free-live-visual');
      await assertNoOverflow(page, ['.live-provider-card', '.workbench-action-btn', '.workbench-metric-card', '.workbench-item']);
      await page.screenshot({ path: screenshotPath('connector-center', viewport.name, mode.lang, mode.theme, 'after-actions'), fullPage: true });

      await page.goto('/app/#/market-radar', { waitUntil: 'domcontentloaded' });
      await expect(page.locator('#btn-market-radar-scan')).toBeVisible();
      await page.locator('#btn-market-radar-scan').click();
      await expect(page.locator('#market-radar-feed')).toContainText(/AAPL|supplier|OHLCV/);
      await assertNoOverflow(page, ['.workbench-item', '.workbench-metric-card', '.workbench-action-btn']);
      await page.screenshot({ path: screenshotPath('market-radar', viewport.name, mode.lang, mode.theme, 'after-actions'), fullPage: true });

      await page.goto('/app/#/agent-lab', { waitUntil: 'domcontentloaded' });
      await expect(page.locator('#btn-agent-workflow')).toBeVisible();
      await page.locator('#btn-agent-workflow').click();
      await expect(page.locator('#agent-timeline')).toContainText(/Simulation|Outcome|Live scan/);
      await expect(page.locator('#agent-report')).toContainText(/Evidence|Loss Prob/);
      await assertNoOverflow(page, ['.workbench-item', '.workbench-metric-card', '.workbench-action-btn']);
      await page.screenshot({ path: screenshotPath('agent-lab', viewport.name, mode.lang, mode.theme, 'after-actions'), fullPage: true });

      await page.goto('/app/#/outcome-center', { waitUntil: 'domcontentloaded' });
      await expect(page.locator('#btn-outcome-refresh')).toBeVisible();
      await page.locator('#btn-outcome-refresh').click();
      await expect(page.locator('#outcome-summary')).toContainText(/Records|Shadow|记录/);
      await page.locator('#btn-outcome-record').click();
      await expect(page.locator('#outcome-summary')).toContainText(/Records|记录/);
      await assertNoOverflow(page, ['.workbench-item', '.workbench-metric-card', '.workbench-action-btn']);
      await page.screenshot({ path: screenshotPath('outcome-center', viewport.name, mode.lang, mode.theme, 'after-actions'), fullPage: true });

      expect(state.consoleErrors).toEqual([]);
      expect(state.failedRequests).toEqual([]);
    });
  }
}
