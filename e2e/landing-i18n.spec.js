const { test, expect } = require('@playwright/test');

async function stubPublicApis(page) {
  await page.route('**/api/health', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ status: 'ok' }),
    });
  });

  await page.route('**/api/v1/quant/platform/overview', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        platform_name: 'ESG Quant Intelligence System',
        watchlist_signals: [],
        top_signals: [],
        portfolio_preview: { positions: [] },
        latest_backtest: { metrics: {} },
        p1_signal_snapshot: { regime_counts: {} },
        universe: { size: 0, benchmark: 'SPY' },
      }),
    });
  });
}

async function openLandingWithEmptyLanguage(page) {
  await page.goto('/', { waitUntil: 'domcontentloaded' });
  await page.evaluate(() => localStorage.removeItem('qt-lang'));
  await page.reload({ waitUntil: 'domcontentloaded' });
  await expect(page.locator('#hero-app-entry')).toBeVisible();
}

async function expectLandingLanguage(page, lang) {
  const activeSelector = `[data-landing-lang="${lang}"]`;
  await expect(page.locator(activeSelector)).toHaveClass(/active/);
  await expect(page.locator(activeSelector)).toHaveAttribute('aria-pressed', 'true');

  if (lang === 'zh') {
    await expect(page.locator('.hl-1')).toHaveText('研究。验证。');
    await expect(page.locator('#hero-app-entry')).toHaveText('进入控制台 →');
    await expect(page.locator('.prod-hl')).toContainText('你的完整量化工作流');
    await expect(page.locator('html')).toHaveAttribute('lang', 'zh-CN');
  } else {
    await expect(page.locator('.hl-1')).toHaveText('Research. Validate.');
    await expect(page.locator('#hero-app-entry')).toHaveText('Enter Console →');
    await expect(page.locator('.prod-hl')).toContainText('Your full quant workflow');
    await expect(page.locator('html')).toHaveAttribute('lang', 'en');
  }
}

async function expectAppShellLanguage(page, lang) {
  await expect(page.locator('#shell-account-trigger')).toBeVisible();
  await page.locator('#shell-account-trigger').click();
  await expect(page.locator(`[data-shell-lang="${lang}"]`)).toHaveClass(/active/);
}

test('landing language toggle defaults to English and syncs with app language', async ({ page }) => {
  await stubPublicApis(page);

  await openLandingWithEmptyLanguage(page);
  await expectLandingLanguage(page, 'en');
  await expect(page.locator('[data-landing-lang="zh"]')).not.toHaveClass(/active/);
  expect(await page.evaluate(() => localStorage.getItem('qt-lang'))).toBeNull();

  await page.locator('[data-landing-lang="zh"]').click();
  await expectLandingLanguage(page, 'zh');
  await expect.poll(() => page.evaluate(() => localStorage.getItem('qt-lang'))).toBe('zh');

  await page.reload({ waitUntil: 'domcontentloaded' });
  await expectLandingLanguage(page, 'zh');

  await page.goto('/app/#/dashboard', { waitUntil: 'domcontentloaded' });
  await expectAppShellLanguage(page, 'zh');
  await expect.poll(() => page.evaluate(() => localStorage.getItem('qt-lang'))).toBe('zh');

  await page.goto('/', { waitUntil: 'domcontentloaded' });
  await expectLandingLanguage(page, 'zh');
  await page.locator('[data-landing-lang="en"]').click();
  await expectLandingLanguage(page, 'en');
  await expect.poll(() => page.evaluate(() => localStorage.getItem('qt-lang'))).toBe('en');

  await page.reload({ waitUntil: 'domcontentloaded' });
  await expectLandingLanguage(page, 'en');

  await page.goto('/app/#/dashboard', { waitUntil: 'domcontentloaded' });
  await expectAppShellLanguage(page, 'en');
  await expect.poll(() => page.evaluate(() => localStorage.getItem('qt-lang'))).toBe('en');
});
