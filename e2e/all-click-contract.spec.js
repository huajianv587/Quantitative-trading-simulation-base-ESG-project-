const fs = require('fs');
const path = require('path');
const { test, expect } = require('@playwright/test');

const OUTPUT_DIR = process.env.CLICK_CONTRACT_DIR
  || path.join(process.cwd(), 'storage', 'quant', 'acceptance', 'click-contract', 'latest');
const REPORT_PATH = path.join(OUTPUT_DIR, 'report.json');
const PROGRESS_PATH = path.join(OUTPUT_DIR, 'progress.log');

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

const PUBLIC_ROUTES = ['/login', '/register', '/reset-password'];

const TARGET_SELECTOR = [
  '#app-root button',
  '#app-root a[href]',
  '#app-root select',
  '#app-root input[type="checkbox"]',
  '#app-root input[type="radio"]',
  '#app-root [role="button"]',
].join(', ');

const SHELL_SELECTOR = [
  '#theme-toggle-btn',
  '#nav-links button',
].join(', ');

function slug(value) {
  return String(value || 'root').replace(/^\//, '').replace(/[^\w-]+/g, '-') || 'root';
}

function prepareOutputDir() {
  fs.rmSync(OUTPUT_DIR, { recursive: true, force: true });
  fs.mkdirSync(OUTPUT_DIR, { recursive: true });
  fs.writeFileSync(PROGRESS_PATH, '', 'utf8');
}

function logProgress(message) {
  fs.appendFileSync(PROGRESS_PATH, `${new Date().toISOString()} ${message}\n`, 'utf8');
}

async function waitForRouteReady(page, route) {
  await page.waitForFunction((expectedRoute) => {
    const root = document.querySelector('#app-root');
    const auth = document.querySelector('.auth-card, .auth-shell');
    const errorState = document.querySelector('.error-state');
    const dataRoute = root?.dataset?.route || '';
    const hashRoute = window.location.hash.replace(/^#/, '') || '/dashboard';
    const routeMatches = !expectedRoute || dataRoute === expectedRoute || (!dataRoute && hashRoute === expectedRoute);
    const interactiveReady = Boolean(root?.querySelector('button, a[href], select, input[type="checkbox"], input[type="radio"], [role="button"]'));
    return Boolean(
      routeMatches && (
        (root && (root.classList.contains('page-ready') || interactiveReady) && root.children && root.children.length > 0)
        || auth
        || errorState
      ),
    );
  }, route, { timeout: 30000 });
  await page.waitForTimeout(500);
}

async function gotoRoute(page, route, forceReload = false) {
  const url = `/app/index.html?acceptance=${Date.now()}#${route}`;
  await page.goto(url, { waitUntil: 'domcontentloaded' });
  try {
    await waitForRouteReady(page, route);
  } catch (error) {
    if (forceReload) throw error;
    await gotoRoute(page, route, true);
  }
}

async function collectTargets(page, selector) {
  return page.evaluate((targetSelector) => {
    const all = Array.from(document.querySelectorAll(targetSelector));
    return all.map((el, nth) => {
      const rect = el.getBoundingClientRect();
      const style = window.getComputedStyle(el);
      const text = String(el.getAttribute('aria-label') || el.getAttribute('title') || el.textContent || el.value || el.id || el.tagName || '')
        .replace(/\s+/g, ' ')
        .trim()
        .slice(0, 120);
      const visible = rect.width > 0
        && rect.height > 0
        && style.display !== 'none'
        && style.visibility !== 'hidden'
        && style.pointerEvents !== 'none'
        && !el.disabled
        && el.getAttribute('aria-disabled') !== 'true';
      return {
        nth,
        visible,
        tag: String(el.tagName || '').toLowerCase(),
        id: el.id || '',
        text,
        href: el.getAttribute('href') || '',
        type: el.getAttribute('type') || '',
        signature: [
          String(el.tagName || '').toLowerCase(),
          el.id || '',
          el.getAttribute('href') || '',
          String(el.getAttribute('aria-label') || el.getAttribute('title') || el.textContent || el.value || el.id || el.tagName || '').replace(/\s+/g, ' ').trim().slice(0, 120),
          el.getAttribute('type') || '',
        ].join('|'),
      };
    }).filter((item) => item.visible);
  }, selector);
}

async function performTargetAction(page, selector, nth) {
  const locator = page.locator(selector).nth(nth);
  if (!(await locator.isVisible().catch(() => false))) {
    return false;
  }
  const tag = await locator.evaluate((el) => String(el.tagName || '').toLowerCase());
  if (tag === 'select') {
    const options = await locator.locator('option').evaluateAll((items) => items.map((item) => item.value || item.textContent || '').filter(Boolean));
    if (options.length > 1) {
      const current = await locator.inputValue().catch(() => '');
      const next = options.find((value) => value !== current) || options[0];
      await locator.selectOption(next);
      return true;
    }
  }
  const popupPromise = page.waitForEvent('popup', { timeout: 200 }).catch(() => null);
  const downloadPromise = page.waitForEvent('download', { timeout: 200 }).catch(() => null);
  await locator.click({ timeout: 15000 });
  const popup = await popupPromise;
  if (popup) await popup.close().catch(() => {});
  await downloadPromise.catch(() => {});
  return true;
}

async function assertClickContract(page, beforeAuditCount, label) {
  await page.waitForFunction((count) => {
    return Array.isArray(window.__uiAuditLog)
      && window.__uiAuditLog.length > count
      && window.__lastClickContract;
  }, beforeAuditCount, { timeout: 6000 });
  const contract = await page.evaluate(() => window.__lastClickContract);
  expect(contract, `${label} should produce click contract audit`).toBeTruthy();
  expect(contract.type).toBe('click_contract');
  expect(['business_api', 'pending_backend_evidence', 'ready', 'degraded', 'blocked']).toContain(contract.evidence_status);
  const statusText = await page.locator('#click-contract-status').textContent();
  expect(statusText, `${label} should show visible feedback copy`).toMatch(/点击|后端|业务|记录|处理|审计/);
}

async function exerciseRouteTargets(page, route, selector) {
  await gotoRoute(page, route);
  const initialTargets = await collectTargets(page, selector);
  const results = [];
  const maxTargets = 60;

  for (const initialTarget of initialTargets.slice(0, maxTargets)) {
    if (!page.url().includes(`#${route}`)) {
      await gotoRoute(page, route, true);
    }
    let targets = await collectTargets(page, selector);
    let target = targets.find((item) => item.signature === initialTarget.signature);
    if (!target) {
      await gotoRoute(page, route, true);
      targets = await collectTargets(page, selector);
      target = targets.find((item) => item.signature === initialTarget.signature);
    }
    if (!target) {
      results.push({ ...initialTarget, status: 'skipped_not_visible_after_state_change' });
      continue;
    }
    logProgress(`target ${route} ${target.id || target.text || target.tag}`);
    const beforeAuditCount = await page.evaluate(() => Array.isArray(window.__uiAuditLog) ? window.__uiAuditLog.length : 0);
    const performed = await performTargetAction(page, selector, target.nth);
    if (!performed) {
      results.push({ ...target, status: 'skipped_not_visible_after_state_change' });
      continue;
    }
    await assertClickContract(page, beforeAuditCount, `${route} ${target.id || target.text || target.tag}`);
    const contract = await page.evaluate(() => window.__lastClickContract);
    results.push({
      ...target,
      status: 'contracted',
      evidence_status: contract.evidence_status,
      request_paths: contract.request_paths || [],
    });
  }
  if (initialTargets.length > maxTargets) {
    results.push({ status: 'capped', reason: `Reached maxTargets=${maxTargets}` });
  }

  await gotoRoute(page, route, true);
  await page.screenshot({
    path: path.join(OUTPUT_DIR, `${slug(route)}__click-contract.png`),
    fullPage: true,
    animations: 'disabled',
  });
  return results;
}

test.describe('all visible click contract', () => {
  test('all visible app and shell clicks produce backend or UI feedback contracts', async ({ page, baseURL }) => {
    test.setTimeout(60 * 60 * 1000);
    prepareOutputDir();
    const pageErrors = [];
    page.on('pageerror', (error) => pageErrors.push(error.stack || error.message));
    page.on('response', (response) => {
      const status = response.status();
      if (status < 400) return;
      pageErrors.push(`${status} ${response.url()}`);
    });
    page.on('console', (message) => {
      if (message.type() === 'error' && !/Failed to load resource/i.test(message.text())) {
        pageErrors.push(message.text());
      }
    });

    await page.addInitScript((apiBase) => {
      window.__ESG_API_BASE_URL__ = apiBase;
      localStorage.setItem('qt-lang', 'zh');
      localStorage.setItem('qt-theme', 'dark');
    }, baseURL);

    const report = {
      generatedAt: new Date().toISOString(),
      outputDir: OUTPUT_DIR,
      routes: [],
      shell: [],
      publicRoutes: [],
      pageErrors,
    };

    await gotoRoute(page, '/dashboard');
    const shellTargets = await collectTargets(page, SHELL_SELECTOR);
    logProgress(`shell targets ${shellTargets.length}`);
    for (const target of shellTargets) {
      logProgress(`shell ${target.id || target.text || target.tag}`);
      const latestShellTargets = await collectTargets(page, SHELL_SELECTOR);
      const latestTarget = latestShellTargets.find((item) => item.signature === target.signature);
      if (!latestTarget) {
        report.shell.push({ ...target, status: 'skipped_not_visible_after_state_change' });
        continue;
      }
      const beforeAuditCount = await page.evaluate(() => Array.isArray(window.__uiAuditLog) ? window.__uiAuditLog.length : 0);
      const performed = await performTargetAction(page, SHELL_SELECTOR, latestTarget.nth);
      if (!performed) {
        report.shell.push({ ...target, status: 'skipped_not_visible_after_state_change' });
        continue;
      }
      await assertClickContract(page, beforeAuditCount, `shell ${target.id || target.text || target.tag}`);
      const contract = await page.evaluate(() => window.__lastClickContract);
      report.shell.push({ ...target, status: 'contracted', evidence_status: contract.evidence_status, request_paths: contract.request_paths || [] });
      await gotoRoute(page, '/dashboard', true);
    }

    for (const route of ROUTES) {
      logProgress(`route ${route} start`);
      const results = await exerciseRouteTargets(page, route, TARGET_SELECTOR);
      report.routes.push({ route, targetCount: results.length, targets: results });
      logProgress(`route ${route} targets ${results.length}`);
    }

    for (const route of PUBLIC_ROUTES) {
      logProgress(`public ${route} start`);
      const results = await exerciseRouteTargets(page, route, TARGET_SELECTOR);
      report.publicRoutes.push({ route, targetCount: results.length, targets: results });
      logProgress(`public ${route} targets ${results.length}`);
    }

    fs.writeFileSync(REPORT_PATH, JSON.stringify(report, null, 2), 'utf8');
    expect(fs.existsSync(REPORT_PATH)).toBeTruthy();
    expect(pageErrors).toEqual([]);
    const totalTargets = [
      ...report.shell,
      ...report.routes.flatMap((item) => item.targets),
      ...report.publicRoutes.flatMap((item) => item.targets),
    ];
    const zeroTargetRoutes = report.routes
      .filter((item) => item.targetCount === 0)
      .map((item) => item.route);
    expect(zeroTargetRoutes).toEqual([]);
    expect(totalTargets.length).toBeGreaterThan(80);
    expect(totalTargets.every((item) => (
      item.status === 'contracted'
      || item.status === 'capped'
      || item.status === 'skipped_not_visible_after_state_change'
    ))).toBeTruthy();
  });
});
