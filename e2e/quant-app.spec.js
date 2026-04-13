const { test, expect } = require('@playwright/test');

const ROUTE_SELECTORS = [
  ['/research', '#btn-run-research'],
  ['/portfolio', '#btn-optimize'],
  ['/backtest', '#btn-run-bt'],
  ['/execution', '#btn-run-exec'],
  ['/validation', '#btn-run-val'],
  ['/models', '#btn-refresh-all'],
  ['/chat', '#send-btn'],
  ['/score', '#score-btn'],
  ['/reports', '#generate-btn'],
  ['/data-management', '#sync-btn'],
  ['/push-rules', '#new-rule-btn'],
  ['/subscriptions', '#create-sub-btn'],
];

function attachPageErrorTracking(page) {
  const pageErrors = [];
  page.on('pageerror', (error) => pageErrors.push(error));
  return pageErrors;
}

async function openApp(page, hashPath = '') {
  const url = hashPath ? `/app#${hashPath}` : '/app';
  await page.goto(url, { waitUntil: 'domcontentloaded' });
  await expect(page.locator('#app-root')).toBeVisible();
}

async function waitForPostResponse(page, pathFragment) {
  return page.waitForResponse((response) => {
    return response.url().includes(pathFragment)
      && response.request().method() === 'POST'
      && response.status() === 200;
  });
}

function extractPositions(payload) {
  return payload.positions || payload.portfolio?.positions || [];
}

async function runPortfolioOptimization(page, universeText) {
  await page.fill('#p-universe', universeText);
  const responsePromise = waitForPostResponse(page, '/api/v1/quant/portfolio/optimize');
  await page.locator('#btn-optimize').click();
  const response = await responsePromise;
  const payload = await response.json();
  await expect(page.locator('#btn-optimize')).toBeEnabled();
  return payload;
}

async function findTradablePortfolio(page) {
  const candidates = [
    '',
    'COST, WMT, PG',
    'XOM, CVX, SLB',
    'GE, CAT, ETN',
  ];

  let lastPayload = null;
  for (const universeText of candidates) {
    lastPayload = await runPortfolioOptimization(page, universeText);
    if (extractPositions(lastPayload).length > 0) {
      return lastPayload;
    }
  }

  throw new Error(`Portfolio optimization returned no positions for all candidates: ${candidates.join(' | ')}`);
}

test('landing page CTAs route into the dashboard home', async ({ page }) => {
  const pageErrors = attachPageErrorTracking(page);

  await page.goto('/', { waitUntil: 'domcontentloaded' });
  await expect(page.locator('#nav-app-entry')).toHaveAttribute('href', '/app/#/dashboard');
  await expect(page.locator('#hero-app-entry')).toHaveAttribute('href', '/app/#/dashboard');
  await expect(page.locator('#cta-free-start')).toHaveAttribute('href', '/app/#/dashboard');

  await page.locator('#hero-app-entry').click();
  await expect(page).toHaveURL(/\/app\/#\/dashboard$/);
  await expect(page.locator('#app-root')).toBeVisible();

  expect(pageErrors, pageErrors.map((error) => error.message).join('\n')).toEqual([]);
});

test('navigation smoke across primary app routes', async ({ page }) => {
  const pageErrors = attachPageErrorTracking(page);

  await openApp(page);
  await expect(page.locator('#page-title')).toContainText(/Dashboard|Overview/);

  for (const [path, selector] of ROUTE_SELECTORS) {
    await openApp(page, path);
    await expect(page.locator(`a[data-path="${path}"]`)).toBeVisible();
    await expect(page.locator(selector)).toBeVisible();
  }

  expect(pageErrors, pageErrors.map((error) => error.message).join('\n')).toEqual([]);
});

test('research, portfolio, and execution plan workflows succeed', async ({ page }) => {
  const pageErrors = attachPageErrorTracking(page);

  await openApp(page, '/research');
  await page.fill('#r-universe', 'AAPL, MSFT, NVDA');
  const researchResponsePromise = waitForPostResponse(page, '/api/v1/quant/research/run');
  await page.locator('#btn-run-research').click();
  const researchResponse = await researchResponsePromise;
  const researchPayload = await researchResponse.json();
  expect(researchPayload.research_id).toMatch(/^research-/);
  expect(researchPayload.signals.length).toBeGreaterThan(0);
  await expect(page.locator('#results-body table tbody tr').first()).toBeVisible();

  await openApp(page, '/portfolio');
  const portfolioPayload = await findTradablePortfolio(page);
  expect(extractPositions(portfolioPayload).length).toBeGreaterThan(0);
  await expect(page.locator('#generate-execution-btn')).toBeEnabled();
  await page.locator('#generate-execution-btn').click();
  await expect(page).toHaveURL(/#\/execution$/);
  await expect(page.locator('#ex-universe')).not.toHaveValue('');

  const executionResponsePromise = waitForPostResponse(page, '/api/v1/quant/execution/paper');
  await page.locator('#btn-run-exec').click();
  const executionResponse = await executionResponsePromise;
  const executionPayload = await executionResponse.json();
  expect(executionPayload.execution_id).toMatch(/^execution-/);
  expect(executionPayload.orders.length).toBeGreaterThan(0);
  await expect(page.locator('#btn-kill')).toBeEnabled();

  expect(pageErrors, pageErrors.map((error) => error.message).join('\n')).toEqual([]);
});

test('backtest and validation workflows render results', async ({ page }) => {
  const pageErrors = attachPageErrorTracking(page);

  await openApp(page, '/backtest');
  await page.fill('#bt-universe', 'AAPL, MSFT');
  const backtestResponsePromise = waitForPostResponse(page, '/api/v1/quant/backtests/run');
  await page.locator('#btn-run-bt').click();
  const backtestResponse = await backtestResponsePromise;
  const backtestPayload = await backtestResponse.json();
  expect(backtestPayload.backtest_id).toMatch(/^backtest-/);
  expect(Number.isFinite(Number(backtestPayload.metrics?.sharpe))).toBeTruthy();
  expect((backtestPayload.timeline || []).length).toBeGreaterThan(0);
  await expect(page.locator('#bt-chart-card')).toBeVisible();
  await expect(page.locator('#bt-metrics')).toContainText('Sharpe');

  await openApp(page, '/validation');
  await page.fill('#val-universe', 'AAPL, MSFT');
  const validationResponsePromise = waitForPostResponse(page, '/api/v1/quant/validation/run');
  await page.locator('#btn-run-val').click();
  const validationResponse = await validationResponsePromise;
  const validationPayload = await validationResponse.json();
  expect(validationPayload.validation_id).toMatch(/^validation-/);
  await expect(page.locator('#val-report')).toBeVisible();
  await expect(page.locator('#val-report-body')).toContainText(validationPayload.validation_id);

  expect(pageErrors, pageErrors.map((error) => error.message).join('\n')).toEqual([]);
});

test('report generation and data sync admin workflows return success payloads', async ({ page }) => {
  const pageErrors = attachPageErrorTracking(page);

  await openApp(page, '/reports');
  const reportResponsePromise = waitForPostResponse(page, '/admin/reports/generate');
  await page.locator('#generate-btn').click();
  const reportResponse = await reportResponsePromise;
  const reportPayload = await reportResponse.json();
  expect(reportPayload.report_id).toBeTruthy();
  await expect(page.locator('#report-body')).toContainText(/report|daily|weekly|monthly/i);

  await openApp(page, '/data-management');
  const syncResponsePromise = waitForPostResponse(page, '/admin/data-sources/sync');
  await page.locator('#sync-btn').click();
  const syncResponse = await syncResponsePromise;
  const syncPayload = await syncResponse.json();
  expect(syncPayload.job_id).toBeTruthy();
  await expect(page.locator('#sync-body')).toContainText(syncPayload.job_id);

  expect(pageErrors, pageErrors.map((error) => error.message).join('\n')).toEqual([]);
});
