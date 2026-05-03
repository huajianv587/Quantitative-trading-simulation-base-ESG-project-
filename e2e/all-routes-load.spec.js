const fs = require('fs');
const path = require('path');
const { test, expect } = require('@playwright/test');

const ROUTER_PATH = path.join(process.cwd(), 'frontend', 'js', 'router.js');
const ROUTE_MATCHER = /'((?:\/)[^']*)':\s*\{/g;
const ROUTES = Array.from(new Set(Array.from(fs.readFileSync(ROUTER_PATH, 'utf8').matchAll(ROUTE_MATCHER), (match) => match[1])));
const OUTPUT_DIR = path.join(process.cwd(), 'test-results', 'all-routes-load');

function screenshotPath(name) {
  fs.mkdirSync(OUTPUT_DIR, { recursive: true });
  return path.join(OUTPUT_DIR, `${name}.png`);
}

function slug(route) {
  return route.replace(/^\//, '').replace(/[^\w-]+/g, '-');
}

async function waitForRouteShell(page) {
  await page.waitForFunction(() => {
    const title = document.querySelector('#page-title');
    const authCard = document.querySelector('.auth-card, .auth-shell');
    const workbench = document.querySelector('.workbench-page, .run-panel, .page-ready');
    const appRoot = document.querySelector('#app-root');
    return Boolean(
      (title && title.textContent && title.textContent.trim().length > 0)
      || authCard
      || workbench
      || (appRoot && appRoot.textContent && appRoot.textContent.trim().length > 0),
    );
  }, { timeout: 30000 });
}

test('all routes load without shell crash (zh dark)', async ({ page, baseURL }) => {
  test.setTimeout(600000);
  const consoleErrors = [];
  const failedRequests = [];

  page.on('console', (message) => {
    if (message.type() === 'error') consoleErrors.push(message.text());
  });
  page.on('pageerror', (error) => {
    consoleErrors.push(String(error.message || error));
  });
  page.on('requestfailed', (request) => {
    const url = request.url();
    if (url.includes('fonts.googleapis.com') || url.includes('fonts.gstatic.com') || url.endsWith('/favicon.ico')) return;
    failedRequests.push(`${request.method()} ${url} ${request.failure()?.errorText || ''}`);
  });

  await page.addInitScript((apiBase) => {
    window.__ESG_API_BASE_URL__ = apiBase;
    localStorage.setItem('qt-lang', 'zh');
    localStorage.setItem('qt-theme', 'dark');
  }, baseURL);

  for (const route of ROUTES) {
    await page.goto(`/app/#${route}`, { waitUntil: 'domcontentloaded' });
    await waitForRouteShell(page);
    await page.waitForTimeout(['/trading-ops', '/autopilot-policy', '/strategy-registry', '/dashboard', '/overview'].includes(route) ? 1400 : 700);
    const bodyText = await page.locator('body').textContent();
    expect(bodyText, `${route} should not show page-level load failure`).not.toMatch(/Page failed to load|页面加载失败/);
    expect(bodyText, `${route} should not be blank`).not.toMatch(/^\s*$/);
    await page.screenshot({ path: screenshotPath(slug(route)), fullPage: true });
  }

  expect(ROUTES).toHaveLength(36);
  expect(consoleErrors).toEqual([]);
  expect(failedRequests).toEqual([]);
});
