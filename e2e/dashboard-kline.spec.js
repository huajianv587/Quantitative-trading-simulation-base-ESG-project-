const fs = require('fs');
const path = require('path');
const { test, expect } = require('@playwright/test');

const OUTPUT_DIR = path.join(process.cwd(), 'test-results', 'dashboard-audit');

function reportPath(filePath) {
  const value = String(filePath || '');
  const relative = path.isAbsolute(value) ? path.relative(process.cwd(), value) : value;
  return relative.split(path.sep).join('/');
}

function mergeScreenshotPaths(current, next) {
  return Array.from(new Set([...(current || []), ...next].map(reportPath)));
}

function readReport() {
  const reportPath = path.join(OUTPUT_DIR, 'report.json');
  if (!fs.existsSync(reportPath)) {
    return {
      generatedAt: new Date().toISOString(),
      chips: [],
      zoomStates: [],
      lowerRightInk: 0,
      screenshots: [],
      scenarios: {},
    };
  }
  return JSON.parse(fs.readFileSync(reportPath, 'utf8'));
}

function writeReport(mutator) {
  fs.mkdirSync(OUTPUT_DIR, { recursive: true });
  const report = readReport();
  mutator(report);
  fs.writeFileSync(path.join(OUTPUT_DIR, 'report.json'), JSON.stringify(report, null, 2), 'utf8');
}

function buildOverview() {
  return {
    platform_name: 'ESG Quant Intelligence System',
    watchlist_signals: [
      {
        symbol: 'NVDA',
        company_name: 'NVIDIA',
        sector: 'Technology',
        thesis: 'Risk-on leadership remains intact and the decision stack keeps the center path positive.',
        action: 'long',
        confidence: 0.86,
        decision_confidence: 0.88,
        expected_return: 0.072,
        predicted_return_5d: 0.058,
        predicted_volatility_10d: 0.118,
        predicted_drawdown_20d: 0.084,
        overall_score: 87.4,
        e_score: 82,
        s_score: 79,
        g_score: 84,
        regime_label: 'risk_on',
        market_data_source: 'yfinance',
        prediction_mode: 'model',
        projection_basis_return: 0.072,
        projection_scenarios: {
          upper: { label: 'Bull Case', expected_return: 0.134, confidence: 0.88, band_source: 'volatility_plus_atr_proxy' },
          center: { label: 'Base Case', expected_return: 0.072, confidence: 0.88, band_source: 'signed_expected_return' },
          lower: { label: 'Risk Floor', expected_return: -0.012, confidence: 0.74, band_source: 'drawdown_plus_atr_proxy' },
        },
        factor_scores: [
          { name: 'momentum', value: 84, contribution: 0.32, description: 'Trend strength remains above peer median.' },
          { name: 'quality', value: 78, contribution: 0.18, description: 'Quality and balance sheet keep the center line positive.' },
          { name: 'regime_fit', value: 81, contribution: 0.15, description: 'Risk-on regime support remains active.' },
        ],
        catalysts: ['Demand cadence remains intact', 'Decision score remains above the paper gate'],
        data_lineage: ['L0: yfinance daily bars', 'L2: P1 suite', 'L3: P2 decision stack'],
      },
      {
        symbol: 'NEE',
        company_name: 'NextEra Energy',
        sector: 'Utilities',
        thesis: 'Short-term rebound exists but the final decision remains neutral-to-defensive.',
        action: 'neutral',
        confidence: 0.74,
        decision_confidence: 0.76,
        expected_return: -0.011,
        predicted_return_5d: 0.031,
        predicted_volatility_10d: 0.094,
        predicted_drawdown_20d: 0.088,
        overall_score: 76.3,
        e_score: 83,
        s_score: 75,
        g_score: 79,
        regime_label: 'risk_off',
        market_data_source: 'yfinance',
        prediction_mode: 'model',
        projection_basis_return: -0.011,
        projection_scenarios: {
          upper: { label: 'Bull Case', expected_return: 0.041, confidence: 0.76, band_source: 'volatility_plus_atr_proxy' },
          center: { label: 'Base Case', expected_return: -0.011, confidence: 0.76, band_source: 'signed_expected_return' },
          lower: { label: 'Risk Floor', expected_return: -0.071, confidence: 0.81, band_source: 'drawdown_plus_atr_proxy' },
        },
        factor_scores: [
          { name: 'drawdown', value: 63, contribution: 0.24, description: 'Drawdown risk keeps the center path muted.' },
          { name: 'regime_fit', value: 58, contribution: 0.18, description: 'Risk-off regime caps upside.' },
          { name: 'esg_delta', value: 80, contribution: 0.14, description: 'ESG strength supports resilience, not aggression.' },
        ],
        catalysts: ['Defensive sector support persists', 'Short-term rebound branch conflicts with final action'],
        data_lineage: ['L0: yfinance daily bars', 'L2: P1 suite', 'L3: P2 decision stack'],
      },
      {
        symbol: 'MSFT',
        company_name: 'Microsoft',
        sector: 'Technology',
        thesis: 'Synthetic feed should disable any prediction overlay.',
        action: 'long',
        confidence: 0.81,
        expected_return: 0.035,
        predicted_return_5d: 0.028,
        predicted_volatility_10d: 0.09,
        predicted_drawdown_20d: 0.07,
        overall_score: 82.2,
        e_score: 80,
        s_score: 82,
        g_score: 85,
        regime_label: 'neutral',
        market_data_source: 'synthetic',
        prediction_mode: 'unavailable',
        projection_basis_return: null,
        projection_scenarios: {},
        factor_scores: [{ name: 'quality', value: 82, contribution: 0.21, description: 'Quality remains strong.' }],
        catalysts: ['Synthetic candle path should not enable projections'],
        data_lineage: ['L0: synthetic fallback factor proxies'],
      },
    ],
    top_signals: [],
    portfolio_preview: { capital_base: 1000000, expected_alpha: 0.084, positions: [] },
    latest_backtest: { metrics: { sharpe: 1.84, max_drawdown: -0.092, annualized_return: 0.214, hit_rate: 0.581 } },
    p1_signal_snapshot: { regime_counts: { risk_on: 1, neutral: 1, risk_off: 1 } },
    universe: { size: 3, benchmark: 'SPY' },
  };
}

function generateCandles(symbol, timeframe) {
  const countMap = { '1D': 120, '1W': 90, '1M': 72, '3M': 56, '1Y': 90 };
  const count = countMap[timeframe] || 120;
  const seedMap = { NVDA: 184, NEE: 69, MSFT: 322 };
  const driftMap = { NVDA: 0.0021, NEE: -0.00035, MSFT: 0.0012 };
  let close = seedMap[symbol] || 140;
  const candles = [];
  for (let index = 0; index < count; index += 1) {
    const wave = Math.sin(index * 0.22) * 0.0032;
    const drift = driftMap[symbol] + wave + (((index * 13) % 7) - 3) * 0.00045;
    const open = close;
    close = Math.max(12, close * (1 + drift));
    const high = Math.max(open, close) * 1.012;
    const low = Math.min(open, close) * 0.988;
    candles.push({
      t: new Date(Date.UTC(2025, 0, 1 + index)).toISOString().slice(0, 10),
      o: Number(open.toFixed(2)),
      h: Number(high.toFixed(2)),
      l: Number(low.toFixed(2)),
      c: Number(close.toFixed(2)),
      v: 7000000 + ((index * 93000) % 2400000),
    });
  }
  return candles;
}

function providerChainFor(provider) {
  const chainMap = {
    auto: ['alpaca', 'twelvedata', 'yfinance', 'cache', 'synthetic'],
    alpaca: ['alpaca', 'twelvedata', 'yfinance', 'cache', 'synthetic'],
    twelvedata: ['twelvedata', 'alpaca', 'yfinance', 'cache', 'synthetic'],
    yfinance: ['yfinance', 'alpaca', 'twelvedata', 'cache', 'synthetic'],
    cache: ['cache', 'synthetic'],
    synthetic: ['synthetic'],
  };
  return chainMap[provider] || chainMap.auto;
}

function buildDashboardChartResponse(overview, symbol, timeframe, provider = 'auto') {
  const selectedProvider = provider || 'auto';
  const signal = (overview.watchlist_signals || []).find((item) => item.symbol === symbol) || overview.watchlist_signals[0];
  const sourceChain = providerChainFor(selectedProvider);
  let source = selectedProvider === 'auto' ? 'alpaca' : selectedProvider;
  let degradedFrom = null;
  let providerStatus = {
    available: selectedProvider !== 'synthetic',
    provider: selectedProvider === 'auto' ? 'alpaca' : selectedProvider,
    selected_provider: selectedProvider,
  };

  if (selectedProvider === 'auto' && symbol === 'NEE') {
    source = 'twelvedata';
    degradedFrom = 'alpaca';
  } else if ((selectedProvider === 'auto' || selectedProvider === 'alpaca') && symbol === 'MSFT') {
    source = 'synthetic';
    degradedFrom = 'alpaca';
    providerStatus = {
      available: true,
      provider: 'alpaca',
      selected_provider: selectedProvider,
    };
  }

  if (selectedProvider === 'cache') {
    source = 'cache';
    providerStatus = {
      available: true,
      provider: 'cache',
      selected_provider: selectedProvider,
    };
  }

  if (selectedProvider === 'synthetic') {
    source = 'synthetic';
    providerStatus = {
      available: false,
      provider: 'synthetic',
      selected_provider: selectedProvider,
    };
  }

  const projectionEnabled = source !== 'synthetic' && signal.prediction_mode === 'model';
  const projectionExplanations = projectionEnabled
    ? Object.fromEntries(Object.entries(signal.projection_scenarios || {}).map(([key, scenario]) => [key, {
        title: scenario.label,
        direction: Number(scenario.expected_return || 0) >= 0 ? 'upside' : 'downside',
        expected_return: scenario.expected_return,
        confidence: scenario.confidence,
        drivers: (signal.factor_scores || []).map((item) => item.description).slice(0, 3),
        why_not_opposite: (signal.catalysts || []).slice(-1)[0] || 'Decision stack rejected the opposite branch.',
        source,
        data_lineage: signal.data_lineage || [],
        house_explanation: `House score proxy for ${symbol} stays constructive.`,
      }]))
    : {};

  return {
    symbol,
    timeframe,
    source,
    selected_provider: selectedProvider,
    data_source_chain: sourceChain,
    provider_status: providerStatus,
    degraded_from: degradedFrom,
    fallback_preview: {
      symbol,
      source,
      source_chain: sourceChain,
      last_snapshot: null,
      reason: degradedFrom ? [`provider_degraded_from_${degradedFrom}`] : (source === 'synthetic' ? ['cache_or_synthetic_fallback'] : []),
      next_actions: ['refresh_dashboard', 'switch_symbol', 'open_market_radar', 'open_backtest'],
    },
    candles: generateCandles(symbol, timeframe).map((candle) => ({
      date: candle.t,
      open: candle.o,
      high: candle.h,
      low: candle.l,
      close: candle.c,
      volume: candle.v,
    })),
    indicators: {},
    projection_scenarios: projectionEnabled ? (signal.projection_scenarios || {}) : {},
    projection_explanations: projectionExplanations,
    projected_volume: [],
    viewport_defaults: {
      '116%': { visibleCount: 64, projectionWidthRatio: 0.22, pricePaddingRatio: 0.06 },
      '352%': { visibleCount: 32, projectionWidthRatio: 0.28, pricePaddingRatio: 0.08 },
      '600%': { visibleCount: 20, projectionWidthRatio: 0.34, pricePaddingRatio: 0.11 },
    },
    click_targets: ['symbol_chip', 'timeframe_tab', 'zoom_control', 'projection_line', 'heatmap_tile'],
    prediction_disabled_reason: projectionEnabled ? null : 'synthetic_market_data',
    signal,
  };
}

async function stubDashboard(page, requests, options = {}) {
  const overview = buildOverview();
  const delayMs = Number(options.delayMs || 0);
  const maybeDelay = async () => {
    if (delayMs > 0) {
      await new Promise((resolve) => setTimeout(resolve, delayMs));
    }
  };
  await page.route('**/api/v1/quant/platform/overview', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(overview) });
  });
  await page.route('**/api/v1/quant/execution/positions**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ positions: [] }) });
  });
  await page.route('**/api/v1/trading/dashboard/state**', async (route) => {
    const url = new URL(route.request().url());
    const provider = url.searchParams.get('provider') || 'auto';
    const chart = buildDashboardChartResponse(overview, 'NVDA', '1D', provider);
    await maybeDelay();
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        generated_at: '2026-04-21T12:00:00Z',
        phase: chart.source === 'unknown' ? 'degraded' : 'ready',
        ready: chart.source !== 'unknown',
        symbol: chart.symbol,
        source: chart.source,
        selected_provider: provider,
        source_chain: chart.data_source_chain,
        provider_status: chart.provider_status,
        degraded_from: chart.degraded_from,
        fallback_preview: chart.fallback_preview,
      }),
    });
  });
  await page.route('**/api/v1/quant/dashboard/chart?*', async (route) => {
    const url = new URL(route.request().url());
    const symbol = url.searchParams.get('symbol') || 'NVDA';
    const timeframe = url.searchParams.get('timeframe') || '1D';
    const provider = url.searchParams.get('provider') || 'auto';
    requests.push({ symbol, timeframe, provider });
    const payload = buildDashboardChartResponse(overview, symbol, timeframe, provider);
    await maybeDelay();
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(payload),
    });
  });
}

async function openDashboard(page, options = {}) {
  const storage = options.storage || {};
  const lang = options.lang || 'en';
  await page.addInitScript(({ initialLang, initialStorage }) => {
    localStorage.setItem('qt-lang', initialLang);
    document.documentElement.setAttribute('lang', initialLang);
    Object.entries(initialStorage).forEach(([key, value]) => {
      localStorage.setItem(key, typeof value === 'string' ? value : JSON.stringify(value));
    });
  }, { initialLang: lang, initialStorage: storage });
  await page.goto('/app/#/dashboard', { waitUntil: 'domcontentloaded' });
  if (Object.keys(storage).length) {
    await page.evaluate(({ initialLang, initialStorage }) => {
      localStorage.setItem('qt-lang', initialLang);
      Object.entries(initialStorage).forEach(([key, value]) => {
        localStorage.setItem(key, typeof value === 'string' ? value : JSON.stringify(value));
      });
    }, { initialLang: lang, initialStorage: storage });
    await page.reload({ waitUntil: 'domcontentloaded' });
  }
  await expect(page.locator('.page-header__title')).toBeVisible();
  await page.waitForFunction(() => Boolean(window.__dashboardAuditState?.visibleCount));
}

async function getDashboardState(page) {
  return page.evaluate(() => ({
    audit: window.__dashboardAuditState,
    uiAuditLogLength: (window.__uiAuditLog || []).length,
    aiText: document.querySelector('#ai-analysis')?.innerText || '',
    legendText: document.querySelector('#kline-legend')?.innerText || '',
  }));
}

async function clickScenarioLine(page, key) {
  const anchor = await page.evaluate((scenarioKey) => window.__dashboardAuditState?.projectionAnchors?.[scenarioKey]?.mid, key);
  expect(anchor, `anchor missing for ${key}`).toBeTruthy();
  await page.evaluate((point) => {
    const canvas = document.querySelector('#kline-canvas');
    const scroller = document.querySelector('.app-content') || document.scrollingElement;
    if (!canvas || !scroller) return;
    const rect = canvas.getBoundingClientRect();
    const targetY = rect.top + point.y;
    const safeTop = 120;
    const safeBottom = window.innerHeight - 120;
    if (targetY < safeTop || targetY > safeBottom) {
      scroller.scrollTop += targetY - window.innerHeight * 0.55;
    }
  }, anchor);
  await page.waitForTimeout(60);
  const canvasBox = await page.locator('#kline-canvas').boundingBox();
  await page.mouse.click(canvasBox.x + anchor.x, canvasBox.y + anchor.y);
}

async function lowerRightInkCount(page) {
  return page.evaluate(() => {
    const canvas = document.querySelector('#kline-canvas');
    const ctx = canvas.getContext('2d');
    const width = canvas.width;
    const height = canvas.height;
    const x = Math.floor(width * 0.76);
    const y = Math.floor(height * 0.68);
    const sw = Math.floor(width * 0.18);
    const sh = Math.floor(height * 0.16);
    const data = ctx.getImageData(x, y, sw, sh).data;
    let changed = 0;
    for (let index = 0; index < data.length; index += 4) {
      const diff = Math.abs(data[index] - 7) + Math.abs(data[index + 1] - 7) + Math.abs(data[index + 2] - 15);
      if (diff > 24) changed += 1;
    }
    return changed;
  });
}

test('dashboard kline audit covers backend projection contract, clicks, zoom, and screenshots', async ({ page }) => {
  test.setTimeout(10 * 60 * 1000);
  fs.mkdirSync(OUTPUT_DIR, { recursive: true });

  const requests = [];

  await stubDashboard(page, requests);
  await openDashboard(page);
  const chipTexts = await page.locator('#symbol-chips [data-sym] .chip-ticker').allInnerTexts();
  expect(chipTexts).toEqual(['NVDA', 'NEE', 'MSFT']);

  const defaultShot = path.join(OUTPUT_DIR, 'dashboard-default.png');
  await page.screenshot({ path: defaultShot, fullPage: true });

  const inkCount = await lowerRightInkCount(page);
  expect(inkCount).toBeGreaterThan(200);

  const zoom116 = await getDashboardState(page);

  await clickScenarioLine(page, 'center');
  await page.waitForFunction(() => window.__dashboardAuditState?.selectedScenario === 'center');
  const centerState = await getDashboardState(page);
  expect(centerState.aiText).toContain('Why not opposite');
  expect(centerState.legendText).toContain('Base Case');
  expect(centerState.legendText).not.toContain('Bull Case');
  const centerShot = path.join(OUTPUT_DIR, 'dashboard-center-selected.png');
  await page.screenshot({ path: centerShot, fullPage: true });

  const floatBox = await page.locator('#kline-projection-float').boundingBox();
  const chartBox = await page.locator('.kline-canvas-wrap').boundingBox();
  expect(floatBox.x).toBeGreaterThanOrEqual(chartBox.x);
  expect(floatBox.y).toBeGreaterThanOrEqual(chartBox.y);
  expect(floatBox.x + floatBox.width).toBeLessThanOrEqual(chartBox.x + chartBox.width);
  expect(floatBox.y + floatBox.height).toBeLessThanOrEqual(chartBox.y + chartBox.height);

  await clickScenarioLine(page, 'upper');
  await page.waitForFunction(() => window.__dashboardAuditState?.selectedScenario === 'upper');
  const upperShot = path.join(OUTPUT_DIR, 'dashboard-upper-selected.png');
  await page.screenshot({ path: upperShot, fullPage: true });

  await clickScenarioLine(page, 'lower');
  await page.waitForFunction(() => window.__dashboardAuditState?.selectedScenario === 'lower');
  const lowerShot = path.join(OUTPUT_DIR, 'dashboard-lower-selected.png');
  await page.screenshot({ path: lowerShot, fullPage: true });

  const beforeBlank = await getDashboardState(page);
  const canvasBox = await page.locator('#kline-canvas').boundingBox();
  await page.mouse.click(canvasBox.x + canvasBox.width - 16, canvasBox.y + canvasBox.height - 16);
  await page.waitForTimeout(150);
  const afterBlank = await getDashboardState(page);
  expect(afterBlank.audit.selectedScenario).toBe(beforeBlank.audit.selectedScenario);
  expect(afterBlank.uiAuditLogLength).toBe(beforeBlank.uiAuditLogLength);

  await page.click('[data-zoom="352%"]');
  await page.waitForFunction(() => window.__dashboardAuditState?.zoomLabel === '352%');
  const zoom352 = await getDashboardState(page);

  await page.click('[data-zoom="600%"]');
  await page.waitForFunction(() => window.__dashboardAuditState?.zoomLabel === '600%');
  const zoom600 = await getDashboardState(page);

  expect(zoom116.audit.visibleCount).toBeGreaterThan(zoom352.audit.visibleCount);
  expect(zoom352.audit.visibleCount).toBeGreaterThan(zoom600.audit.visibleCount);
  expect(zoom116.audit.candleWidth).toBeLessThan(zoom352.audit.candleWidth);
  expect(zoom352.audit.candleWidth).toBeLessThan(zoom600.audit.candleWidth);
  expect(zoom116.audit.canvasHeight).toBe(zoom352.audit.canvasHeight);
  expect(zoom352.audit.canvasHeight).toBe(zoom600.audit.canvasHeight);

  const zoomShot = path.join(OUTPUT_DIR, 'dashboard-zoom-600.png');
  await page.screenshot({ path: zoomShot, fullPage: true });

  await page.click('[data-zoom="116%"]');
  await page.waitForFunction(() => window.__dashboardAuditState?.zoomLabel === '116%');
  await page.click('#zoom-in-btn');
  await page.waitForFunction(() => window.__dashboardAuditState?.zoomLabel === '136%');
  const zoom136 = await getDashboardState(page);
  expect(zoom136.audit.visibleCount).toBeLessThan(zoom116.audit.visibleCount);
  expect(zoom136.audit.candleWidth).toBeGreaterThan(zoom116.audit.candleWidth);
  expect(zoom136.audit.canvasHeight).toBe(zoom116.audit.canvasHeight);

  const wheelBox = await page.locator('#kline-canvas').boundingBox();
  await page.mouse.move(wheelBox.x + wheelBox.width / 2, wheelBox.y + wheelBox.height / 2);
  await page.mouse.wheel(0, -240);
  await page.waitForFunction(() => window.__dashboardAuditState?.zoomLabel === '156%');
  const zoom156 = await getDashboardState(page);
  expect(zoom156.audit.visibleCount).toBeLessThanOrEqual(zoom136.audit.visibleCount);
  expect(zoom156.audit.candleWidth).toBeGreaterThan(zoom136.audit.candleWidth);
  expect(zoom156.audit.canvasHeight).toBe(zoom116.audit.canvasHeight);

  writeReport((report) => {
    report.generatedAt = new Date().toISOString();
    report.chips = chipTexts;
    report.lowerRightInk = inkCount;
    report.zoomStates = [
      { label: '116%', ...zoom116.audit },
      { label: '136%', ...zoom136.audit },
      { label: '156%', ...zoom156.audit },
      { label: '352%', ...zoom352.audit },
      { label: '600%', ...zoom600.audit },
    ];
    report.screenshots = mergeScreenshotPaths(report.screenshots, [
      defaultShot,
      centerShot,
      upperShot,
      lowerShot,
      zoomShot,
    ]);
    report.scenarios.primary = {
      blankClickPreservedSelection: afterBlank.audit.selectedScenario === beforeBlank.audit.selectedScenario,
      blankClickUiAuditDelta: afterBlank.uiAuditLogLength - beforeBlank.uiAuditLogLength,
      requests,
    };
  });
  expect(fs.existsSync(path.join(OUTPUT_DIR, 'report.json'))).toBeTruthy();
});

test('dashboard kline audit covers defensive and unavailable states without reopening the same canvas session', async ({ page }) => {
  test.setTimeout(10 * 60 * 1000);
  fs.mkdirSync(OUTPUT_DIR, { recursive: true });

  const requests = [];
  await stubDashboard(page, requests);
  await openDashboard(page);

  await page.click('[data-sym="NEE"]');
  await page.waitForFunction(() => window.__dashboardAuditState?.symbol === 'NEE');
  const neeState = await getDashboardState(page);
  expect(neeState.audit.predictionEnabled).toBeTruthy();
  expect(neeState.aiText).toContain('No projection line selected');
  expect(requests.some((item) => item.symbol === 'NEE')).toBeTruthy();

  await clickScenarioLine(page, 'center');
  await page.waitForFunction(() => window.__dashboardAuditState?.selectedScenario === 'center');
  const neeCenterState = await getDashboardState(page);
  expect(neeCenterState.aiText).toContain('-1.10%');
  const neeShot = path.join(OUTPUT_DIR, 'dashboard-nee-center-selected.png');
  await page.screenshot({ path: neeShot, fullPage: true });

  await page.click('[data-sym="MSFT"]');
  await page.waitForFunction(() => window.__dashboardAuditState?.symbol === 'MSFT');
  const msftState = await getDashboardState(page);
  expect(msftState.audit.predictionEnabled).toBeFalsy();
  expect(msftState.legendText.trim()).toBe('');
  expect(msftState.aiText).toMatch(/disables projection|已禁用预测/);
  const unavailableShot = path.join(OUTPUT_DIR, 'dashboard-unavailable.png');
  await page.screenshot({ path: unavailableShot, fullPage: true });

  writeReport((report) => {
    report.generatedAt = new Date().toISOString();
    report.screenshots = mergeScreenshotPaths(report.screenshots, [
      neeShot,
      unavailableShot,
    ]);
    report.scenarios.coverage = {
      neePredictionEnabled: neeState.audit.predictionEnabled,
      neeCenterSelected: true,
      neeAiText: neeCenterState.aiText,
      msftPredictionEnabled: msftState.audit.predictionEnabled,
      msftAiText: msftState.aiText,
      requests,
    };
  });
  expect(fs.existsSync(path.join(OUTPUT_DIR, 'report.json'))).toBeTruthy();
});

test('dashboard provider selector keeps chart visible while refreshing and records provider-aware requests', async ({ page }) => {
  test.setTimeout(10 * 60 * 1000);
  fs.mkdirSync(OUTPUT_DIR, { recursive: true });

  const overview = buildOverview();
  const cachedPayload = buildDashboardChartResponse(overview, 'NVDA', '1D', 'alpaca');
  const requests = [];
  await stubDashboard(page, requests, { delayMs: 1200 });
  await openDashboard(page, {
    lang: 'zh',
    storage: {
      'qt.dashboard.provider.v1': 'alpaca',
      'qt.dashboard.state.v1': {
        saved_at: Date.now(),
        payload: {
          generated_at: '2026-04-21T11:59:00Z',
          phase: 'ready',
          ready: true,
          symbol: 'NVDA',
          source: 'alpaca',
          selected_provider: 'alpaca',
          source_chain: ['alpaca', 'twelvedata', 'yfinance', 'cache', 'synthetic'],
          provider_status: { available: true, provider: 'alpaca', selected_provider: 'alpaca' },
          degraded_from: null,
          fallback_preview: cachedPayload.fallback_preview,
        },
      },
      'qt.dashboard.chart.v1:NVDA:1D:alpaca': {
        saved_at: Date.now(),
        payload: cachedPayload,
      },
    },
  });

  await expect(page.locator('#dashboard-provider-select')).toHaveValue('alpaca');
  await expect(page.locator('#kline-canvas')).toBeVisible();
  await expect.poll(() => requests.some((item) => item.provider === 'alpaca')).toBeTruthy();

  await page.locator('#dashboard-provider-select').selectOption('twelvedata');
  await expect(page.locator('#kline-canvas')).toBeVisible();
  await expect.poll(() => page.evaluate(() => window.__dashboardAuditState?.selectedProvider)).toBe('twelvedata');
  await expect.poll(() => requests.some((item) => item.provider === 'twelvedata')).toBeTruthy();

  await page.locator('#dashboard-provider-select').selectOption('synthetic');
  await expect(page.locator('#kline-canvas')).toBeVisible();
  await expect.poll(() => page.evaluate(() => window.__dashboardAuditState?.selectedProvider)).toBe('synthetic');
  await expect.poll(() => requests.some((item) => item.provider === 'synthetic')).toBeTruthy();
  await expect.poll(() => page.evaluate(() => window.__dashboardAuditState?.marketSource)).toBe('synthetic');
  const syntheticState = await getDashboardState(page);
  expect(syntheticState.aiText).toMatch(/disables projection|已禁用预测/);

  const providerShot = path.join(OUTPUT_DIR, 'dashboard-provider-selector.png');
  await page.screenshot({ path: providerShot, fullPage: true });
  writeReport((report) => {
    report.generatedAt = new Date().toISOString();
    report.screenshots = mergeScreenshotPaths(report.screenshots, [providerShot]);
    report.scenarios.providerSelector = {
      requests,
      finalSource: syntheticState.audit.source,
      selectedProvider: syntheticState.audit.selectedProvider,
    };
  });
});
