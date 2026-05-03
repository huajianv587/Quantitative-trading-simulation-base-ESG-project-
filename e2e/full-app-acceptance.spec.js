const fs = require('fs');
const path = require('path');
const { test, expect } = require('@playwright/test');

const OUTPUT_DIR = path.join(process.cwd(), 'test-results', 'playwright', 'full-app-acceptance');
const REPORT_PATH = path.join(OUTPUT_DIR, 'report.json');

const ROUTES = [
  '/dashboard',
  '/research',
  '/intelligence',
  '/factor-lab',
  '/simulation',
  '/connector-center',
  '/market-radar',
  '/agent-lab',
  '/debate-desk',
  '/risk-board',
  '/trading-ops',
  '/trading-safety',
  '/automation-timeline',
  '/autopilot-policy',
  '/strategy-registry',
  '/outcome-center',
  '/portfolio',
  '/backtest',
  '/sweep',
  '/tearsheet',
  '/dataset',
  '/execution',
  '/paper-performance',
  '/validation',
  '/capabilities',
  '/models',
  '/rl-lab',
  '/chat',
  '/score',
  '/reports',
  '/ops-health',
  '/job-console',
  '/data-management',
  '/data-config-center',
  '/push-rules',
  '/subscriptions',
];

const SAFE_BUTTONS = {
  '/research': ['#btn-run-research'],
  '/intelligence': ['#btn-intel-scan', '#btn-decision-explain'],
  '/factor-lab': ['#btn-factor-refresh'],
  '/connector-center': ['#btn-connector-health'],
  '/market-radar': ['#btn-market-radar-refresh'],
  '/agent-lab': ['#btn-agent-workflow'],
  '/risk-board': ['#btn-risk-refresh'],
  '/trading-ops': ['#btn-trading-ops-refresh'],
  '/trading-safety': ['#btn-safety-refresh'],
  '/automation-timeline': ['#btn-timeline-refresh'],
  '/autopilot-policy': ['#btn-autopilot-refresh'],
  '/strategy-registry': ['#btn-strategy-refresh'],
  '/outcome-center': ['#btn-outcome-refresh'],
  '/backtest': ['#btn-run-bt'],
  '/execution': ['#btn-open-paper-performance'],
  '/paper-performance': ['#btn-paper-performance-refresh'],
  '/capabilities': [
    '#btn-capabilities-refresh',
    '#btn-run-blueprint-analysis',
    '#btn-run-blueprint-data',
    '#btn-run-blueprint-risk',
    '#btn-run-blueprint-infra',
  ],
  '/reports': ['#generate-btn'],
  '/ops-health': ['#btn-ops-health-refresh', '#btn-ops-run-smoke'],
  '/job-console': ['#btn-job-refresh', '#btn-job-smoke'],
  '/data-management': ['#sync-btn'],
  '/data-config-center': ['#btn-data-config-refresh', '#btn-save-provider'],
  '/push-rules': ['#new-rule-btn'],
  '/subscriptions': ['#create-sub-btn'],
};

const MOJIBAKE_PATTERN = new RegExp([
  '\\u9239',
  '\\u951b',
  '\\u6d93',
  '\\u9359',
  '\\u99c3',
  '\\u8133',
  '\\u9241',
  '\\u95bf',
  '\\u7f02',
  '\\u95c1',
  '\\u6fe1',
  '\\u5a75',
  '\\u95bb',
  '\\u93ba',
  '\\u942e',
  '\\u6748',
  '\\u690b',
  '\\u93c6',
  '\\u7487',
  '\\u93c1',
  '\\u9354',
  '\\u93c9',
  '\\u5bb8',
  '\\u5bf0',
  '\\u93c8',
  '\\u7039',
  '\\u6d5c',
  '\\u7edb',
  '\\u59af',
  '\\u752f',
  '\\u6d60',
  '\\u7eef',
  '\\u9477',
].join('|'));
const API_STATUS_PATTERN = /ready|degraded|blocked|succeeded|failed|cancelled|queued|running/i;

function slug(route) {
  return route.replace(/^\//, '').replace(/[^\w-]+/g, '-') || 'root';
}

function screenshotPath(route, suffix = 'default') {
  fs.mkdirSync(OUTPUT_DIR, { recursive: true });
  return path.join(OUTPUT_DIR, `${slug(route)}__${suffix}.png`);
}

async function waitForRouteReady(page) {
  await page.waitForFunction(() => {
    const root = document.querySelector('#app-root');
    const title = document.querySelector('#page-title');
    const auth = document.querySelector('.auth-card, .auth-shell');
    return Boolean(
      (root && root.textContent && root.textContent.trim().length > 0)
      || (title && title.textContent && title.textContent.trim().length > 0)
      || auth,
    );
  }, { timeout: 30000 });
  await page.waitForTimeout(500);
}

async function readJson(response) {
  expect(response.ok(), `${response.url()} should return 2xx`).toBeTruthy();
  return response.json();
}

async function assertStatusPayload(payload, label) {
  const text = JSON.stringify(payload);
  expect(text, `${label} should include an allowed status`).toMatch(API_STATUS_PATTERN);
  if (/"status":"(degraded|blocked)"/i.test(text)) {
    expect(text, `${label} degraded/blocked should include reason or next action`).toMatch(/reason|missing_config|next_actions/i);
  }
}

test.describe('full app acceptance', () => {
  test('all workbench routes render, respond, and keep screenshots', async ({ page, request, baseURL }) => {
    test.setTimeout(45 * 60 * 1000);
    fs.mkdirSync(OUTPUT_DIR, { recursive: true });

    const pageErrors = [];
    const failedRequests = [];
    const routeReports = [];
    page.on('pageerror', (error) => pageErrors.push(error.stack || error.message));
    page.on('console', (message) => {
      if (message.type() === 'error') pageErrors.push(message.text());
    });
    page.on('requestfailed', (req) => {
      const url = req.url();
      if (url.includes('fonts.googleapis.com') || url.includes('fonts.gstatic.com') || url.endsWith('/favicon.ico')) return;
      failedRequests.push(`${req.method()} ${url} ${req.failure()?.errorText || ''}`);
    });

    await page.addInitScript((apiBase) => {
      window.__ESG_API_BASE_URL__ = apiBase;
      localStorage.setItem('qt-lang', 'zh');
      localStorage.setItem('qt-theme', 'dark');
    }, baseURL);

    const apiChecks = {
      schemaHealth: await readJson(await request.get('/api/v1/platform/schema-health')),
      releaseHealth: await readJson(await request.get('/api/v1/platform/release-health')),
      tradingSafety: await readJson(await request.get('/api/v1/trading/safety-center')),
      automationTimeline: await readJson(await request.get('/api/v1/trading/automation/timeline')),
      dataConfig: await readJson(await request.get('/api/v1/data/config-center')),
      jobList: await readJson(await request.get('/api/v1/jobs?limit=20')),
      jobQueue: await readJson(await request.post('/api/v1/jobs', {
        data: { job_type: 'release_health_smoke', payload: { source: 'full_app_acceptance' } },
      })),
    };
    for (const [label, payload] of Object.entries(apiChecks)) {
      await assertStatusPayload(payload, label);
    }
    expect(apiChecks.tradingSafety.live_auto_submit.allowed).toBe(false);
    expect(apiChecks.tradingSafety.live_auto_submit.reason).toMatch(/Live auto-submit disabled by hard rule/);

    for (const route of ROUTES) {
      await page.goto(`/app/#${route}`, { waitUntil: 'domcontentloaded' });
      await waitForRouteReady(page);
      const beforeText = await page.locator('body').textContent();
      expect(beforeText, `${route} should not be blank`).not.toMatch(/^\s*$/);
      expect(beforeText, `${route} should not show page load failure`).not.toMatch(/Page failed to load|页面加载失败/);
      expect(beforeText, `${route} should not show mojibake`).not.toMatch(MOJIBAKE_PATTERN);
      const defaultShot = screenshotPath(route, 'default');
      await page.screenshot({ path: defaultShot, fullPage: true, animations: 'disabled' });

      const buttonResults = [];
      for (const selector of SAFE_BUTTONS[route] || []) {
        const target = page.locator(selector).first();
        if (!(await target.count())) {
          buttonResults.push({ selector, status: 'missing' });
          continue;
        }
        if (!(await target.isVisible())) {
          buttonResults.push({ selector, status: 'hidden' });
          continue;
        }
        await target.click();
        await page.waitForTimeout(900);
        const afterText = await page.locator('body').textContent();
        expect(afterText, `${route} ${selector} should not create page failure`).not.toMatch(/Page failed to load|页面加载失败/);
        expect(afterText, `${route} ${selector} should not show mojibake`).not.toMatch(MOJIBAKE_PATTERN);
        buttonResults.push({ selector, status: 'clicked' });
      }

      const actionShot = screenshotPath(route, 'after-actions');
      await page.screenshot({ path: actionShot, fullPage: true, animations: 'disabled' });
      routeReports.push({
        route,
        defaultScreenshot: defaultShot,
        actionScreenshot: actionShot,
        buttons: buttonResults,
      });
    }

    const report = {
      generatedAt: new Date().toISOString(),
      outputDir: OUTPUT_DIR,
      routeCount: ROUTES.length,
      apiChecks,
      routes: routeReports,
      pageErrors,
      failedRequests,
    };
    fs.writeFileSync(REPORT_PATH, JSON.stringify(report, null, 2), 'utf8');
    expect(fs.existsSync(REPORT_PATH)).toBeTruthy();
    expect(pageErrors).toEqual([]);
    expect(failedRequests).toEqual([]);
  });
});
