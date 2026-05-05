const { test, expect } = require('@playwright/test');

async function stubShellApis(page) {
  if (page.__shellApisStubbed) return;
  page.__shellApisStubbed = true;
  await page.route('**/api/**', async (route) => {
    const url = route.request().url();
    if (url.includes('/api/health')) {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ status: 'ok' }) });
      return;
    }

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: [],
        items: [],
        rows: [],
        metrics: {},
        candles: [],
      }),
    });
  });
}

async function seedShellStorage(page, storage = {}) {
  await page.evaluate((values) => {
    localStorage.removeItem('qt-token');
    localStorage.removeItem('qt-user');
    localStorage.removeItem('qt-lang');
    localStorage.removeItem('qt-theme');
    sessionStorage.removeItem('qt-token');
    sessionStorage.removeItem('qt-user');
    sessionStorage.removeItem('__shell_account_seeded');

    Object.entries(values).forEach(([key, value]) => {
      if (value !== null && value !== undefined) {
        localStorage.setItem(key, value);
      }
    });
  }, storage);
}

async function openDashboard(page, storage = {}) {
  await stubShellApis(page);
  await page.goto('/app/#/dashboard', { waitUntil: 'domcontentloaded' });
  await seedShellStorage(page, storage);
  await page.reload({ waitUntil: 'domcontentloaded' });
  await expect(page.locator('#shell-account-trigger')).toBeVisible();
}

async function activateShellControl(page, selector) {
  await page.locator(selector).click();
}

test.describe('shell account menu', () => {
  test('logged-in dashboard moves account, language, and theme controls to the lower-left menu', async ({ page }) => {
    await openDashboard(page, {
      'qt-token': 'token-for-shell-test',
      'qt-user': JSON.stringify({ name: 'gui', email: 'gui@example.com' }),
      'qt-lang': 'en',
      'qt-theme': 'dark',
    });

    await expect(page.locator('#shell-account-trigger')).toContainText('gui');
    await expect(page.locator('#header-actions')).toHaveText('');
    await expect(page.locator('#theme-toggle-btn')).toHaveCount(0);
    await expect(page.locator('.topbar-lang-toggle')).toHaveCount(0);
    await expect(page.locator('#topbar-user')).toHaveCount(0);

    await page.locator('#shell-account-trigger').click();
    await expect(page.locator('#shell-account-menu')).toBeVisible();
    await expect(page.locator('#shell-theme-toggle')).toBeVisible();
    await expect(page.locator('[data-shell-lang="en"]')).toHaveClass(/active/);
    await expect(page.locator('#shell-logout')).toBeVisible();

    await activateShellControl(page, '[data-shell-lang="zh"]');
    await expect.poll(() => page.evaluate(() => localStorage.getItem('qt-lang'))).toBe('zh');
    await expect.poll(() => page.evaluate(() => document.documentElement.lang)).toBe('zh-CN');
    await expect(page.locator('[data-shell-lang="zh"]')).toHaveClass(/active/);

    await page.reload({ waitUntil: 'domcontentloaded' });
    await expect(page.locator('#shell-account-trigger')).toBeVisible();
    await expect.poll(() => page.evaluate(() => localStorage.getItem('qt-lang'))).toBe('zh');
    await expect.poll(() => page.evaluate(() => document.documentElement.lang)).toBe('zh-CN');
    await page.locator('#shell-account-trigger').click();
    await expect(page.locator('[data-shell-lang="zh"]')).toHaveClass(/active/);

    await activateShellControl(page, '[data-shell-lang="en"]');
    await expect.poll(() => page.evaluate(() => localStorage.getItem('qt-lang'))).toBe('en');
    await expect.poll(() => page.evaluate(() => document.documentElement.lang)).toBe('en');
    await expect(page.locator('[data-shell-lang="en"]')).toHaveClass(/active/);

    await page.locator('#shell-theme-toggle').click();
    await expect.poll(() => page.evaluate(() => localStorage.getItem('qt-theme'))).toBe('light');
    await expect(page.locator('body')).toHaveClass(/light/);

    await page.reload({ waitUntil: 'domcontentloaded' });
    await expect(page.locator('#shell-account-trigger')).toBeVisible();
    await expect.poll(() => page.evaluate(() => localStorage.getItem('qt-theme'))).toBe('light');
    await expect(page.locator('body')).toHaveClass(/light/);

    await page.locator('#shell-account-trigger').click();
    await page.locator('#shell-logout').click();
    await expect.poll(() => page.evaluate(() => localStorage.getItem('qt-token'))).toBeNull();
    await expect.poll(() => page.evaluate(() => localStorage.getItem('qt-user'))).toBeNull();
    await expect(page).toHaveURL(/\/app\/#\/login$/);
  });

  test('guest dashboard shows lower-left sign-in entry with login and register links', async ({ page }) => {
    await openDashboard(page, {
      'qt-lang': 'en',
      'qt-theme': 'dark',
    });

    await expect(page.locator('#shell-account-trigger')).toContainText('Sign In');
    await page.locator('#shell-account-trigger').click();
    await expect(page.locator('#shell-account-menu')).toBeVisible();
    await expect(page.locator('#shell-login')).toHaveAttribute('href', '#/login');
    await expect(page.locator('#shell-register')).toHaveAttribute('href', '#/register');
    await expect(page.locator('#shell-logout')).toHaveCount(0);

    await page.locator('#shell-register').click();
    await expect(page).toHaveURL(/\/app\/#\/register$/);
  });

  test('mobile collapsed account trigger does not cover page bottom actions', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    for (const [index, mode] of [
      { lang: 'en', theme: 'dark', auth: 'guest' },
      { lang: 'en', theme: 'light', auth: 'guest' },
      { lang: 'zh', theme: 'dark', auth: 'guest' },
      { lang: 'zh', theme: 'light', auth: 'guest' },
      { lang: 'en', theme: 'dark', auth: 'signed-in' },
      { lang: 'en', theme: 'light', auth: 'signed-in' },
      { lang: 'zh', theme: 'dark', auth: 'signed-in' },
      { lang: 'zh', theme: 'light', auth: 'signed-in' },
    ].entries()) {
      const authStorage = mode.auth === 'signed-in'
        ? {
            'qt-token': `token-mobile-${index}`,
            'qt-user': JSON.stringify({ name: `Mobile ${index}`, email: `mobile-${index}@example.com` }),
          }
        : {};

      await openDashboard(page, {
        ...authStorage,
        'qt-lang': mode.lang,
        'qt-theme': mode.theme,
      });

      const collapsedBox = await page.locator('#shell-account').boundingBox();
      expect(collapsedBox).not.toBeNull();
      expect(collapsedBox.width).toBeLessThanOrEqual(64);
      expect(collapsedBox.height).toBeLessThanOrEqual(64);
      expect(collapsedBox.x).toBeGreaterThanOrEqual(0);
      expect(collapsedBox.x + collapsedBox.width).toBeLessThanOrEqual(390);
      expect(collapsedBox.y + collapsedBox.height).toBeLessThanOrEqual(844);

      await page.evaluate((targetId) => {
        document.querySelectorAll('[data-mobile-hit-target]').forEach((node) => node.remove());
        window.__mobileBottomActionClicked = null;
        const button = document.createElement('button');
        button.id = targetId;
        button.dataset.mobileHitTarget = 'true';
        button.textContent = 'Bottom action';
        button.style.cssText = [
          'position:fixed',
          'left:86px',
          'bottom:18px',
          'width:132px',
          'height:44px',
          'z-index:139',
        ].join(';');
        button.addEventListener('click', () => {
          window.__mobileBottomActionClicked = targetId;
        });
        document.body.appendChild(button);
      }, `mobile-hit-target-${index}`);

      await page.locator(`#mobile-hit-target-${index}`).click();
      await expect.poll(() => page.evaluate(() => window.__mobileBottomActionClicked)).toBe(`mobile-hit-target-${index}`);

      await page.locator('#shell-account-trigger').click();
      await expect(page.locator('#shell-account-menu')).toBeVisible();
      const openMenuBox = await page.locator('#shell-account-menu').boundingBox();
      expect(openMenuBox).not.toBeNull();
      expect(openMenuBox.width).toBeGreaterThanOrEqual(300);
      expect(openMenuBox.x).toBeGreaterThanOrEqual(0);
      expect(openMenuBox.x + openMenuBox.width).toBeLessThanOrEqual(390);
      expect(openMenuBox.y).toBeGreaterThanOrEqual(0);
      expect(openMenuBox.y + openMenuBox.height).toBeLessThanOrEqual(844);
      await page.goto('about:blank');
    }
  });
});
