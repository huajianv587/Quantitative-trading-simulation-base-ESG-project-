const fs = require('fs');
const path = require('path');
const { test, expect } = require('@playwright/test');

const OUTPUT_DIR = path.join(process.cwd(), 'test-results', 'intelligence-cockpit');

const VIEWPORTS = [
  { name: 'desktop-1440x1100', viewport: { width: 1440, height: 1100 } },
  { name: 'mobile-390x844', viewport: { width: 390, height: 844 } },
];

function screenshotPath(viewportName, state) {
  fs.mkdirSync(OUTPUT_DIR, { recursive: true });
  return path.join(OUTPUT_DIR, `${viewportName}-${state}.png`);
}

async function waitUntilPanelSettles(page, panelSelector, loadingText) {
  await page.waitForFunction(
    ([selector, text]) => {
      const element = document.querySelector(selector);
      return !!element && !element.innerText.includes(text);
    },
    [panelSelector, loadingText],
    { timeout: 90000 },
  );
  await expect(page.locator(panelSelector)).not.toContainText('Request failed');
}

async function assertNoCriticalOverflow(page) {
  const overflow = await page.evaluate(() => {
    const selectors = [
      '.page-header__title',
      '.page-header__sub',
      '.intelligence-action-grid',
      '#btn-intel-scan',
      '#btn-decision-explain',
      '#btn-open-factor-lab',
      '#btn-open-simulation',
      '#decision-summary .workbench-metric-card',
      '.workbench-link-card',
    ];
    const rows = [];
    for (const selector of selectors) {
      document.querySelectorAll(selector).forEach((element, index) => {
        const style = window.getComputedStyle(element);
        const box = element.getBoundingClientRect();
        if (style.display === 'none' || style.visibility === 'hidden' || box.width <= 1 || box.height <= 1) return;
        if (element.scrollWidth > element.clientWidth + 3) {
          rows.push({
            selector,
            index,
            tag: element.tagName,
            text: (element.innerText || element.value || '').slice(0, 120),
            scrollWidth: element.scrollWidth,
            clientWidth: element.clientWidth,
          });
        }
      });
    }
    return rows;
  });
  expect(overflow).toEqual([]);
}

for (const { name, viewport } of VIEWPORTS) {
  test(`Decision Cockpit visual and buttons: ${name}`, async ({ page, baseURL }) => {
    test.setTimeout(180000);
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

    await page.setViewportSize(viewport);
    await page.addInitScript((apiBase) => {
      window.__ESG_API_BASE_URL__ = apiBase;
    }, baseURL);

    await page.goto('/app/#/intelligence', { waitUntil: 'domcontentloaded' });
    await expect(page.locator('#page-title')).toBeVisible();
    await expect(page.locator('#page-title')).not.toHaveText('');
    await waitUntilPanelSettles(page, '#evidence-panel', 'Loading...');
    await assertNoCriticalOverflow(page);
    await page.screenshot({ path: screenshotPath(name, 'initial'), fullPage: true });

    const actions = [
      {
        key: 'scan',
        selector: '#btn-intel-scan',
        panel: '#evidence-panel',
        loading: 'Scanning evidence...',
        result: /q=|local_esg|quant_signal|AAPL|NVDA/i,
      },
      {
        key: 'decision',
        selector: '#btn-decision-explain',
        panel: '#decision-summary',
        loading: 'Building decision report...',
        result: /Verifier|Risk triggers|shadow mode|纸面|受控|approve|reduce|reject|halt/i,
      },
    ];

    for (const action of actions) {
      const button = page.locator(action.selector);
      await expect(button, `${action.key} button visible`).toBeVisible();
      await expect(button, `${action.key} button enabled`).toBeEnabled();
      await button.click();
      await waitUntilPanelSettles(page, action.panel, action.loading);
      await expect(page.locator(action.panel)).toContainText(action.result);
      await assertNoCriticalOverflow(page);
    }

    await expect(page.locator('#btn-open-factor-lab')).toBeVisible();
    await expect(page.locator('#btn-open-simulation')).toBeVisible();
    await expect(page.locator('body')).not.toContainText('Request failed');
    await expect(page.locator('#decision-summary')).not.toContainText(/No decision report yet|暂无决策报告/);
    await page.screenshot({ path: screenshotPath(name, 'after-actions'), fullPage: true });

    expect(consoleErrors).toEqual([]);
    expect(failedRequests).toEqual([]);
  });
}
