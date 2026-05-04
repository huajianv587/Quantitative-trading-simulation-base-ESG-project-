const { test, expect } = require('@playwright/test');

const ROUTE_SELECTORS = [
  ['/research', '#btn-run-research'],
  ['/intelligence', '#btn-intel-scan'],
  ['/factor-lab', '#btn-factor-discover'],
  ['/simulation', '#btn-simulate-scenario'],
  ['/portfolio', '#wizard-bar'],
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

let openCounter = 0;

function attachPageErrorTracking(page) {
  const pageErrors = [];
  page.on('pageerror', (error) => pageErrors.push(error));
  return pageErrors;
}

async function openApp(page, hashPath = '') {
  openCounter += 1;
  const url = `/app/?e2e=${Date.now()}-${openCounter}#${hashPath || '/dashboard'}`;
  await page.goto(url, { waitUntil: 'domcontentloaded' });
  await expect(page.locator('#app-root')).toBeVisible();
}

async function waitForPostResponse(page, pathFragment) {
  return page.waitForResponse((response) => (
    response.url().includes(pathFragment)
    && response.request().method() === 'POST'
    && response.status() >= 200
    && response.status() < 300
  ));
}

async function waitForJobCreate(page, expectedType) {
  const response = await waitForPostResponse(page, '/api/v1/jobs');
  const payload = await response.json();
  expect(payload.job_id).toBeTruthy();
  expect(payload.job_type).toBe(expectedType);
  expect(['succeeded', 'degraded', 'blocked', 'queued', 'running']).toContain(payload.status);
  return payload;
}

async function navigatePortfolioWizard(page) {
  await expect(page.locator('#wizard-bar')).toBeVisible();
  await page.locator('#s1-next').click();
  await expect(page.locator('#po-universe')).toBeVisible();
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
  await expect(page.locator('#page-title')).toBeVisible();

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
  expect((researchPayload.signals || []).length).toBeGreaterThan(0);
  await expect(page.locator('#results-body table tbody tr').first()).toBeVisible();

  await openApp(page, '/portfolio');
  await navigatePortfolioWizard(page);
  await page.fill('#po-universe', 'COST, WMT, PG');
  await page.locator('#s2-next').click();
  await expect(page.locator('#max-pos')).toBeVisible();
  await page.locator('#s3-next').click();
  await expect(page.locator('#btn-optimize')).toBeVisible();
  const portfolioResponsePromise = waitForPostResponse(page, '/api/v1/quant/portfolio/optimize');
  await page.locator('#btn-optimize').click();
  const portfolioResponse = await portfolioResponsePromise;
  const portfolioPayload = await portfolioResponse.json();
  expect((portfolioPayload.holdings || portfolioPayload.portfolio?.positions || []).length).toBeGreaterThan(0);
  await expect(page.locator('#btn-to-execution')).toBeEnabled();
  await page.locator('#btn-to-execution').click();
  await expect(page).toHaveURL(/#\/execution$/);
  await expect(page.locator('#ex-universe')).not.toHaveValue('');

  await page.locator('#ex-submit').evaluate((node) => {
    node.checked = false;
    node.dispatchEvent(new Event('change', { bubbles: true }));
  });
  const executionResponsePromise = waitForPostResponse(page, '/api/v1/quant/execution/paper');
  await page.locator('#btn-run-exec').click();
  const executionResponse = await executionResponsePromise;
  const executionPayload = await executionResponse.json();
  expect(executionPayload.execution_id).toMatch(/^execution-/);
  expect((executionPayload.orders || []).length).toBeGreaterThan(0);
  const killButton = page.locator('#btn-kill');
  await expect(killButton).toBeVisible();
  if (await killButton.isDisabled()) {
    await expect(page.locator('#broker-status-note')).not.toHaveText('');
    await expect(page.locator('#execution-effective-mode')).not.toHaveText('');
  } else {
    await expect(killButton).toBeEnabled();
  }

  expect(pageErrors, pageErrors.map((error) => error.message).join('\n')).toEqual([]);
});

test('backtest and validation workflows render results', async ({ page }) => {
  const pageErrors = attachPageErrorTracking(page);

  await openApp(page, '/backtest');
  await page.fill('#bt-universe', 'AAPL, MSFT');
  const backtestResponsePromise = waitForJobCreate(page, 'advanced_backtest');
  await page.locator('#btn-run-bt').click();
  const backtestPayload = await backtestResponsePromise;
  const backtestResult = backtestPayload.result || backtestPayload;
  expect(backtestResult.backtest_id || backtestPayload.job_id).toBeTruthy();
  expect(Number.isFinite(Number(backtestResult.metrics?.sharpe))).toBeTruthy();
  expect((backtestResult.timeline || backtestResult.equity_curve || []).length).toBeGreaterThan(0);
  await expect(page.locator('#bt-chart-card')).toBeVisible();
  await expect(page.locator('#bt-metrics')).toBeVisible();

  await openApp(page, '/validation');
  await page.fill('#v-universe', 'AAPL, MSFT');
  const validationResponsePromise = waitForPostResponse(page, '/api/v1/quant/validation/run');
  await page.locator('#btn-run-val').click();
  const validationResponse = await validationResponsePromise;
  const validationPayload = await validationResponse.json();
  expect(validationPayload.validation_id).toMatch(/^validation-/);
  await expect(page.locator('#val-results')).toBeVisible();
  await expect(page.locator('#wf-chart')).toBeVisible();

  expect(pageErrors, pageErrors.map((error) => error.message).join('\n')).toEqual([]);
});

test('report generation and data sync admin workflows return success payloads', async ({ page }) => {
  const pageErrors = attachPageErrorTracking(page);

  await openApp(page, '/reports');
  const reportResponsePromise = waitForJobCreate(page, 'report_generation');
  await page.locator('#generate-btn').click();
  const reportPayload = await reportResponsePromise;
  expect(reportPayload.job_id).toBeTruthy();
  expect(reportPayload.result?.artifact?.report_id || reportPayload.result?.report_id || reportPayload.job_id).toBeTruthy();
  await expect(page.locator('#report-body')).toBeVisible();

  await openApp(page, '/data-management');
  const syncResponsePromise = waitForJobCreate(page, 'data_sync');
  await page.locator('#sync-btn').click();
  const syncPayload = await syncResponsePromise;
  expect(syncPayload.job_id).toBeTruthy();
  expect(syncPayload.result || syncPayload.status).toBeTruthy();
  await expect(page.locator('#sync-body')).toBeVisible();

  expect(pageErrors, pageErrors.map((error) => error.message).join('\n')).toEqual([]);
});
