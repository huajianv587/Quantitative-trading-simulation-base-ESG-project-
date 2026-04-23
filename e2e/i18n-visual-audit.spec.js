const fs = require('fs');
const path = require('path');
const { test, expect } = require('@playwright/test');

const OUTPUT_DIR = path.join(process.cwd(), 'test-results', 'i18n-audit');

const ROUTES = [
  { path: '/dashboard', ready: '#page-title', scenes: [{ name: 'default' }] },
  { path: '/research', ready: '#page-title', scenes: [{ name: 'default' }, { name: 'results', action: runResearch }] },
  { path: '/intelligence', ready: '#page-title', scenes: [{ name: 'default' }] },
  { path: '/portfolio', ready: '#page-title', scenes: [
    { name: 'step-1' },
    { name: 'step-5', action: async (page) => { await page.locator('#s1-next').click(); await page.locator('#s2-next').click(); await page.locator('#s3-next').click(); await page.locator('#btn-optimize').click(); await page.waitForTimeout(1200); await page.locator('#s4-next').click(); } },
  ] },
  { path: '/backtest', ready: '#page-title', scenes: [{ name: 'default' }, { name: 'results', action: runBacktest }] },
  { path: '/validation', ready: '#page-title', scenes: [{ name: 'default' }, { name: 'results', action: runValidation }] },
  { path: '/chat', ready: '#page-title', scenes: [{ name: 'default' }] },
  { path: '/score', ready: '#page-title', scenes: [{ name: 'default' }] },
  { path: '/data-management', ready: '#page-title', scenes: [{ name: 'default' }, { name: 'sync-running', action: runSync }] },
  { path: '/trading-ops', ready: '#page-title', scenes: [{ name: 'default' }] },
  { path: '/autopilot-policy', ready: '#page-title', scenes: [{ name: 'default' }] },
  { path: '/strategy-registry', ready: '#page-title', scenes: [{ name: 'default' }] },
];

test.describe('i18n visual audit', () => {
  test('captures zh/en screenshots and visible text residue report', async ({ page }) => {
    test.setTimeout(35 * 60 * 1000);
    fs.mkdirSync(OUTPUT_DIR, { recursive: true });

    const pageErrors = [];
    page.on('pageerror', (error) => pageErrors.push(error.message));

    const report = {
      generatedAt: new Date().toISOString(),
      pageErrors,
      pages: [],
    };

    for (const route of ROUTES) {
      for (const lang of ['zh', 'en']) {
        for (const scene of route.scenes) {
          const record = {
            route: route.path,
            lang,
            scene: scene.name,
            screenshot: screenshotPath(route.path, lang, scene.name),
            visibleTextCount: 0,
            chineseInEnglish: [],
            englishInChinese: [],
            warning: null,
          };
          try {
            await openRoute(page, route);
            await setLanguage(page, lang);
            await ensureReady(page, route.ready);

            if (scene.action) {
              await scene.action(page);
            }

            await page.waitForTimeout(450);
          } catch (error) {
            record.warning = error.message;
          }

          try {
            const textAudit = await collectTextAudit(page);
            record.visibleTextCount = textAudit.texts.length;
            record.chineseInEnglish = lang === 'en' ? textAudit.texts.filter((t) => /[\u4e00-\u9fff]/.test(t) && t !== '中') : [];
            record.englishInChinese = lang === 'zh' ? textAudit.texts.filter((t) => isUnexpectedEnglish(t)) : [];
            await page.evaluate(() => window.scrollTo(0, 0));
            await page.screenshot({ path: record.screenshot, animations: 'disabled' });
          } catch (error) {
            record.warning = record.warning || error.message;
          }

          report.pages.push(record);
        }
      }
    }

    const reportPath = path.join(OUTPUT_DIR, 'report.json');
    fs.writeFileSync(reportPath, JSON.stringify(report, null, 2), 'utf8');
    expect(fs.existsSync(reportPath)).toBeTruthy();
  });
});

async function openRoute(page, route) {
  await page.goto(`/app#${route.path}`, { waitUntil: 'domcontentloaded' });
  await expect(page.locator('#app-root')).toBeVisible();
  await ensureReady(page, route.ready);
}

async function ensureReady(page, selector) {
  await page.locator(selector).first().waitFor({ state: 'visible', timeout: 30000 });
}

async function setLanguage(page, lang) {
  const current = await page.evaluate(() => document.documentElement.lang || localStorage.getItem('qt-lang') || 'zh');
  if (current === lang) {
    return;
  }

  await page.evaluate((targetLang) => {
    localStorage.setItem('qt-lang', targetLang);
    document.documentElement.setAttribute('lang', targetLang);
  }, lang);
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(250);
}

async function runResearch(page) {
  await ensureReady(page, '#btn-run-research');
  await page.locator('#btn-run-research').click();
  await page.waitForTimeout(2500);
}

async function runBacktest(page) {
  await ensureReady(page, '#btn-run-bt');
  await page.locator('#bt-universe').fill('AAPL, MSFT');
  await page.locator('#btn-run-bt').click();
  await page.locator('#bt-chart-card').waitFor({ state: 'visible', timeout: 30000 });
}

async function runValidation(page) {
  await ensureReady(page, '#btn-run-val');
  await page.locator('#v-universe').fill('AAPL, MSFT');
  await page.locator('#btn-run-val').click();
  await page.locator('#wf-chart').waitFor({ state: 'visible', timeout: 30000 });
}

async function runSync(page) {
  await ensureReady(page, '#sync-btn');
  await page.locator('#sync-btn').click();
  await page.waitForTimeout(1500);
}

function screenshotPath(routePath, lang, scene) {
  const safeRoute = routePath.replace(/^\//, '').replace(/[^\w-]+/g, '-') || 'root';
  const dir = path.join(OUTPUT_DIR, lang);
  fs.mkdirSync(dir, { recursive: true });
  return path.join(dir, `${safeRoute}__${scene}.png`);
}

function isUnexpectedEnglish(text) {
  if (!/[A-Za-z]/.test(text)) return false;

  const normalized = text.trim();
  if (!normalized) return false;

  const allowList = [
    /^(EN|PDF|CSV|JSON|API|ESG|AI|P1|P2|SPY|QQQ|IWM|AAPL|MSFT|NVDA|TSLA|GOOGL|META|AMZN|AMD|INTC|AVGO|F|GM|NIO)$/i,
    /^[A-Z0-9.+/%\-\s]+$/,
    /^\$?[\d.,%+\-: ]+$/,
    /^v\d+/i,
  ];

  if (allowList.some((pattern) => pattern.test(normalized))) {
    return false;
  }

  return /[a-z]{3,}/.test(normalized) || /[A-Za-z]{3,}\s+[A-Za-z]{2,}/.test(normalized);
}

async function collectTextAudit(page) {
  return page.evaluate(() => {
    const texts = [];
    const skipSelector = [
      '.lang-btn',
      '.topbar-lang-toggle',
      '#theme-toggle-btn',
      'script',
      'style',
      'noscript',
      'svg',
      'canvas',
    ].join(', ');

    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    let node = walker.nextNode();

    while (node) {
      const parent = node.parentElement;
      const raw = node.textContent || '';
      const text = raw.replace(/\s+/g, ' ').trim();

      if (parent && text) {
        const rect = parent.getBoundingClientRect();
        const style = window.getComputedStyle(parent);
        const isVisible = rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none' && style.opacity !== '0';

        if (
          isVisible &&
          !parent.closest(skipSelector) &&
          !/^[\d\s.,:%+\-/$()]+$/.test(text)
        ) {
          texts.push(text);
        }
      }

      node = walker.nextNode();
    }

    return { texts: Array.from(new Set(texts)) };
  });
}
