const fs = require('fs');
const path = require('path');
const { test, expect } = require('@playwright/test');

const OUTPUT_DIR = path.join(process.cwd(), 'test-results', 'product-workbench-visual');

const VIEWPORTS = [
  { name: 'desktop-1440x1100', size: { width: 1440, height: 1100 } },
  { name: 'mobile-390x844', size: { width: 390, height: 844 } },
];

const MODES = [
  { lang: 'zh', theme: 'dark' },
  { lang: 'zh', theme: 'light' },
  { lang: 'en', theme: 'dark' },
  { lang: 'en', theme: 'light' },
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

async function collectPageGuards(page, selectors) {
  const overflow = await page.evaluate((targetSelectors) => {
    const rows = [];
    for (const selector of targetSelectors) {
      document.querySelectorAll(selector).forEach((element, index) => {
        const style = window.getComputedStyle(element);
        const rect = element.getBoundingClientRect();
        if (style.display === 'none' || style.visibility === 'hidden' || rect.width <= 1 || rect.height <= 1) return;
        if (element.scrollWidth > element.clientWidth + 3) {
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

async function attachConsoleGuards(page) {
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

function factorCards() {
  const statuses = ['promoted', 'research_only', 'low_confidence', 'rejected'];
  const families = ['freshness_decay', 'evidence_quality', 'event_risk', 'regime_interaction'];
  return Array.from({ length: 23 }, (_, index) => {
    const n = index + 1;
    const status = statuses[index % statuses.length];
    return {
      name: `factor_${String(n).padStart(2, '0')}_${status}`,
      family: families[index % families.length],
      status,
      definition: `As-of safe factor candidate ${n} with evidence-linked lineage.`,
      ic: status === 'rejected' ? -0.02 * n : 0.018 * n,
      rank_ic: status === 'low_confidence' ? -0.12 : 0.08 + (index % 5) * 0.04,
      stability_score: 0.35 + (index % 7) * 0.06,
      sample_count: 4 + (index % 6),
      turnover_estimate: 0.18 + (index % 4) * 0.09,
      missing_rate: (index % 5) * 0.015,
      transaction_cost_sensitivity: index % 3 === 0 ? 'medium' : 'low',
      failure_modes: status === 'promoted' ? [] : ['weak IC in current shadow sample'],
    };
  });
}

async function mockFactorRoutes(page) {
  const cards = factorCards();
  const payload = {
    factors: cards,
    factor_cards: cards,
    run_id: 'mock-factor-lab-23',
    promotion_policy: 'Only promoted factors can become runtime inputs; research-only factors remain visible but gated.',
    lineage: ['candidate generation', 'as-of feature build', 'IC / RankIC gate', 'cost sensitivity review', 'registry promotion decision'],
  };
  await page.route('**/api/v1/quant/factors/registry**', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(payload),
  }));
  await page.route('**/api/v1/quant/factors/discover', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(payload),
  }));
}

async function mockWorkbenchApiRoutes(page) {
  const evidenceItems = [
    {
      item_id: 'ev-aapl-1',
      title: 'AAPL factor momentum',
      summary: '20/60 MA trend strength; value=66; contribution=0.34',
      item_type: 'model_signal',
      symbol: 'AAPL',
      provider: 'local_shadow',
      quality_score: 0.91,
      leakage_guard: 'as_of_safe',
    },
    {
      item_id: 'ev-aapl-2',
      title: 'AAPL ESG disclosure delta',
      summary: 'Disclosure quality improved while governance risk remains stable.',
      item_type: 'rag_evidence',
      symbol: 'AAPL',
      provider: 'local_esg',
      quality_score: 0.87,
      leakage_guard: 'as_of_safe',
    },
  ];
  const simulation = {
    simulation_id: 'sim-AAPL-visual',
    scenario: { symbol: 'AAPL', scenario_name: 'risk_off_stress', regime: 'risk_off', shock_bps: -125, paths: 512, seed: 42 },
    expected_return: 0.021,
    probability_of_loss: 0.37,
    value_at_risk_95: -0.064,
    max_drawdown_p95: -0.118,
    path_summary: { p05: -0.064, p50: 0.018, p95: 0.092 },
    factor_attribution: { momentum: 0.31, quality: 0.21, esg_delta: 0.16 },
    historical_analogs: [
      { title: 'Risk-off replay with high quality tech', event_type: 'regime_stress', symbol: 'AAPL', reason: 'Similar volatility and factor profile.', quality_score: 0.78 },
    ],
  };
  await page.route('**/api/v1/quant/intelligence/evidence**', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ items: evidenceItems }),
  }));
  await page.route('**/api/v1/quant/intelligence/scan', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ items: evidenceItems }),
  }));
  await page.route('**/api/v1/quant/decision/explain', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({
      decision_id: 'decision-AAPL-visual',
      symbol: 'AAPL',
      action: 'hold',
      expected_return: 0.024,
      confidence: 0.72,
      confidence_interval: { lower: -0.012, center: 0.024, upper: 0.061 },
      position_weight_range: { min: 0.02, max: 0.08 },
      verifier_checks: { verdict: 'review', leakage_pass: true },
      risk_triggers: ['Volatility spike above threshold', 'Evidence source quality drops below 0.7'],
      factor_cards: factorCards().slice(0, 3),
      simulation,
      main_evidence: evidenceItems,
      counter_evidence: [
        { ...evidenceItems[0], item_id: 'counter-1', title: 'Counter: valuation pressure', summary: 'Valuation multiple remains sensitive to rate shocks.' },
      ],
    }),
  }));
  await page.route('**/api/v1/quant/simulate/scenario', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(simulation),
  }));
  await page.route('**/api/v1/quant/research/run', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({
      research_id: 'research-visual',
      generated_at: new Date('2026-04-18T10:00:00Z').toISOString(),
      signals: [
        { symbol: 'AAPL', company_name: 'Apple Inc.', action: 'long', confidence: 0.74, expected_return: 0.035, overall_score: 78.2, e_score: 72.1, g_score: 80.4, sector: 'Technology', thesis: 'Momentum and ESG disclosure quality remain supportive.' },
        { symbol: 'MSFT', company_name: 'Microsoft Corp.', action: 'long', confidence: 0.71, expected_return: 0.028, overall_score: 76.4, e_score: 70.3, g_score: 82.0, sector: 'Technology', thesis: 'Quality factor and governance stability support the rank.' },
        { symbol: 'NEE', company_name: 'NextEra Energy', action: 'neutral', confidence: 0.58, expected_return: 0.006, overall_score: 64.9, e_score: 81.0, g_score: 62.5, sector: 'Utilities', thesis: 'Strong ESG profile is offset by regime pressure.' },
      ],
    }),
  }));
}

async function assertRowLimit(page) {
  const rowCount = await page.locator('[data-factor-row]').count();
  expect(rowCount).toBeGreaterThan(0);
  expect(rowCount).toBeLessThanOrEqual(10);
}

async function assertBalancedPanels(page, leftSelector, rightSelector, tolerance = 260) {
  const boxes = await page.evaluate(([left, right]) => {
    const leftBox = document.querySelector(left)?.getBoundingClientRect();
    const rightBox = document.querySelector(right)?.getBoundingClientRect();
    return {
      left: leftBox ? { width: leftBox.width, height: leftBox.height } : null,
      right: rightBox ? { width: rightBox.width, height: rightBox.height } : null,
    };
  }, [leftSelector, rightSelector]);
  expect(boxes.left).toBeTruthy();
  expect(boxes.right).toBeTruthy();
  expect(Math.abs(boxes.left.height - boxes.right.height)).toBeLessThanOrEqual(tolerance);
}

for (const viewport of VIEWPORTS) {
  for (const mode of MODES) {
    test(`Factor Lab pagination/layout ${viewport.name} ${mode.lang} ${mode.theme}`, async ({ page, baseURL }) => {
      test.setTimeout(180000);
      const guards = await attachConsoleGuards(page);
      await page.setViewportSize(viewport.size);
      await configure(page, baseURL, mode.lang, mode.theme);
      await mockFactorRoutes(page);

      await page.goto('/app/#/factor-lab', { waitUntil: 'domcontentloaded' });
      await expect(page.locator('#btn-factor-discover')).toBeVisible();
      await expect(page.locator('.factor-status-tab')).toHaveCount(5);
      await assertRowLimit(page);
      await expect(page.locator('.factor-page-number[data-factor-page="1"]')).toBeVisible();
      await expect(page.locator('.factor-page-number[data-factor-page="2"]')).toBeVisible();
      await expect(page.locator('.factor-page-number[data-factor-page="3"]')).toBeVisible();
      await collectPageGuards(page, [
        '.page-header__title',
        '.page-header__sub',
        '.workbench-action-btn',
        '.factor-summary-block',
        '.factor-card',
        '.factor-status-tab',
        '.factor-gate-row',
        '.factor-pagination',
      ]);
      await page.screenshot({ path: screenshotPath('factor-lab', viewport.name, mode.lang, mode.theme, 'initial'), fullPage: true });

      await page.locator('.factor-status-tab[data-factor-status="promoted"]').click();
      await assertRowLimit(page);
      await expect(page.locator('.factor-status-tab[data-factor-status="promoted"]')).toHaveClass(/active/);
      await page.screenshot({ path: screenshotPath('factor-lab', viewport.name, mode.lang, mode.theme, 'status-promoted'), fullPage: true });

      await page.locator('.factor-status-tab[data-factor-status=""]').click();
      await page.locator('.factor-page-number[data-factor-page="2"]').click();
      await assertRowLimit(page);
      await expect(page.locator('.factor-page-number[data-factor-page="2"]')).toHaveClass(/active/);
      await page.screenshot({ path: screenshotPath('factor-lab', viewport.name, mode.lang, mode.theme, 'page-2'), fullPage: true });

      await page.locator('#btn-factor-discover').click();
      await expect(page.locator('#factor-card-panel')).toContainText(/IC|RankIC/);
      await collectPageGuards(page, ['.factor-card', '.workbench-metric-card', '.factor-gate-row', '.factor-page-btn']);
      await page.screenshot({ path: screenshotPath('factor-lab', viewport.name, mode.lang, mode.theme, 'after-actions'), fullPage: true });
      expect(guards.consoleErrors).toEqual([]);
      expect(guards.failedRequests).toEqual([]);
    });

    test(`Workbench cockpit/simulation/research visual ${viewport.name} ${mode.lang} ${mode.theme}`, async ({ page, baseURL }) => {
      test.setTimeout(240000);
      const guards = await attachConsoleGuards(page);
      await page.setViewportSize(viewport.size);
      await configure(page, baseURL, mode.lang, mode.theme);
      await mockWorkbenchApiRoutes(page);

      await page.goto('/app/#/intelligence', { waitUntil: 'domcontentloaded' });
      await expect(page.locator('#btn-intel-scan')).toBeVisible();
      await expect(page.locator('.functional-empty').first()).toBeVisible();
      await collectPageGuards(page, ['.page-header__title', '.page-header__sub', '.intelligence-action-btn', '.functional-empty', '.factor-check-row']);
      await page.screenshot({ path: screenshotPath('intelligence', viewport.name, mode.lang, mode.theme, 'initial'), fullPage: true });
      await page.locator('#btn-decision-explain').click();
      await page.waitForFunction(() => !document.querySelector('#decision-summary')?.innerText.includes('Building decision report...'), null, { timeout: 90000 });
      await expect(page.locator('#decision-summary')).toContainText(/Verifier|Risk|风险|验证/);
      await collectPageGuards(page, ['#decision-summary .workbench-metric-card', '#counter-panel', '#audit-panel']);
      await page.screenshot({ path: screenshotPath('intelligence', viewport.name, mode.lang, mode.theme, 'after-actions'), fullPage: true });

      await page.goto('/app/#/simulation', { waitUntil: 'domcontentloaded' });
      await expect(page.locator('#btn-simulate-scenario')).toBeVisible();
      await expect(page.locator('.simulation-preview')).toBeVisible();
      await collectPageGuards(page, ['.page-header__title', '.page-header__sub', '.workbench-action-btn', '.simulation-preview', '#simulation-manifest', '.simulation-preset']);
      if (viewport.size.width >= 900) {
        await assertBalancedPanels(page, '.simulation-setup-card', '.simulation-result-card');
        await assertBalancedPanels(page, '.simulation-presets-card', '.simulation-manifest-card');
      }
      await page.screenshot({ path: screenshotPath('simulation', viewport.name, mode.lang, mode.theme, 'initial'), fullPage: true });
      await page.locator('.simulation-preset[data-preset="riskOff"]').click();
      await page.locator('#btn-simulate-scenario').click();
      await page.waitForFunction(() => !document.querySelector('#simulation-panel')?.innerText.includes('Running simulation...'), null, { timeout: 90000 });
      await expect(page.locator('#simulation-panel')).toContainText(/VaR 95|MDD p95|亏损概率|Loss Prob/);
      await collectPageGuards(page, ['#simulation-panel .workbench-metric-card', '#simulation-manifest', '.workbench-kv-row']);
      await page.screenshot({ path: screenshotPath('simulation', viewport.name, mode.lang, mode.theme, 'after-actions'), fullPage: true });

      await page.goto('/app/#/research', { waitUntil: 'domcontentloaded' });
      await expect(page.locator('#btn-run-research')).toBeVisible();
      await expect(page.locator('.research-preview')).toBeVisible();
      await collectPageGuards(page, ['.page-header__title', '.page-header__sub', '.research-preview', '.workbench-mini-metric', '#btn-run-research']);
      await page.screenshot({ path: screenshotPath('research', viewport.name, mode.lang, mode.theme, 'initial'), fullPage: true });
      await page.locator('#btn-run-research').click();
      await page.waitForFunction(() => !!document.querySelector('#results-body table tbody tr') || document.querySelector('#results-body')?.innerText.includes('Pipeline Error'), null, { timeout: 90000 });
      await expect(page.locator('#results-body')).not.toContainText('Pipeline Error');
      await collectPageGuards(page, ['#results-body table', '#results-body tr', '.results-panel']);
      await page.screenshot({ path: screenshotPath('research', viewport.name, mode.lang, mode.theme, 'after-actions'), fullPage: true });

      expect(guards.consoleErrors).toEqual([]);
      expect(guards.failedRequests).toEqual([]);
    });
  }
}

test('ESG score and RL Lab visual regressions are fixed', async ({ page, baseURL }) => {
  test.setTimeout(180000);
  const guards = await attachConsoleGuards(page);
  await page.setViewportSize({ width: 1440, height: 1100 });
  await configure(page, baseURL, 'zh', 'dark');

  await page.goto('/app/#/score', { waitUntil: 'domcontentloaded' });
  await expect(page.locator('#score-btn')).toBeVisible();
  await collectPageGuards(page, ['.esg-radar-card', '.esg-radar-legend__row', '.score-dim-card', '.score-run-btn']);
  const radarBox = await page.locator('#esg-radar').boundingBox();
  expect(radarBox.width).toBeGreaterThan(300);
  expect(radarBox.height).toBeGreaterThan(300);
  await page.screenshot({ path: screenshotPath('score', 'desktop-1440x1100', 'zh', 'dark', 'ready'), fullPage: true });

  await page.goto('/app/#/rl-lab', { waitUntil: 'domcontentloaded' });
  await expect(page.locator('#rl-refresh')).toBeVisible();
  await collectPageGuards(page, ['.rl-lab-stat', '.rl-lab-stat__value', '.rl-lab-path', '.rl-lab-hero__copy']);
  await page.screenshot({ path: screenshotPath('rl-lab', 'desktop-1440x1100', 'zh', 'dark', 'ready'), fullPage: true });

  expect(guards.consoleErrors).toEqual([]);
  expect(guards.failedRequests).toEqual([]);
});
