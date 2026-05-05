const ZOOM_MIN = 100;
const ZOOM_MAX = 600;
const ZOOM_STEP = 20;
const STAGE_HEIGHT = { desktop: 560, mobile: 420 };
const ZOOM_ANCHORS = [
  { percent: 100, visibleCount: 72, candleBodyRatio: 0.58, projectionWidthRatio: 0.2, pricePaddingRatio: 0.055 },
  { percent: 116, visibleCount: 64, candleBodyRatio: 0.62, projectionWidthRatio: 0.22, pricePaddingRatio: 0.06 },
  { percent: 352, visibleCount: 32, candleBodyRatio: 0.78, projectionWidthRatio: 0.28, pricePaddingRatio: 0.08 },
  { percent: 600, visibleCount: 20, candleBodyRatio: 0.9, projectionWidthRatio: 0.34, pricePaddingRatio: 0.11 },
];

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function parseZoomPercent(label) {
  const value = Number(String(label || '').replace('%', ''));
  return clamp(Number.isFinite(value) ? value : 116, ZOOM_MIN, ZOOM_MAX);
}

function formatZoomLabel(percent) {
  return `${Math.round(clamp(percent, ZOOM_MIN, ZOOM_MAX))}%`;
}

function lerp(left, right, progress) {
  return left + (right - left) * progress;
}

function interpolateZoomPreset(label) {
  const percent = parseZoomPercent(label);
  let lower = ZOOM_ANCHORS[0];
  let upper = ZOOM_ANCHORS[ZOOM_ANCHORS.length - 1];
  for (let index = 1; index < ZOOM_ANCHORS.length; index += 1) {
    if (percent <= ZOOM_ANCHORS[index].percent) {
      lower = ZOOM_ANCHORS[index - 1];
      upper = ZOOM_ANCHORS[index];
      break;
    }
  }
  const span = Math.max(1, upper.percent - lower.percent);
  const progress = clamp((percent - lower.percent) / span, 0, 1);
  return {
    percent,
    visibleCount: Math.round(lerp(lower.visibleCount, upper.visibleCount, progress)),
    candleBodyRatio: lerp(lower.candleBodyRatio, upper.candleBodyRatio, progress),
    projectionWidthRatio: lerp(lower.projectionWidthRatio, upper.projectionWidthRatio, progress),
    pricePaddingRatio: lerp(lower.pricePaddingRatio, upper.pricePaddingRatio, progress),
  };
}

function stepZoomLabel(label, direction) {
  const next = parseZoomPercent(label) + direction * ZOOM_STEP;
  return formatZoomLabel(next);
}

function cssVar(name, fallback, element = document.body) {
  const sources = [element, document.body, document.documentElement].filter(Boolean);
  for (const source of sources) {
    const value = getComputedStyle(source).getPropertyValue(name).trim();
    if (value) return value;
  }
  return fallback;
}

function chartTheme(element) {
  return {
    bg: cssVar('--chart-bg', cssVar('--bg-base', '#07070F', element), element),
    grid: cssVar('--chart-grid', 'rgba(255,255,255,0.05)', element),
    axis: cssVar('--chart-axis', 'rgba(143,164,200,0.50)', element),
    text: cssVar('--text-primary', '#F0F4FF', element),
    muted: cssVar('--text-secondary', 'rgba(200,210,255,0.55)', element),
    dim: cssVar('--text-dim', 'rgba(140,160,220,0.45)', element),
    up: cssVar('--chart-up', '#00FF88', element),
    down: cssVar('--chart-down', '#FF4D6D', element),
    upSoft: cssVar('--chart-up-soft', 'rgba(0,255,136,0.42)', element),
    downSoft: cssVar('--chart-down-soft', 'rgba(255,77,109,0.40)', element),
    tooltipBg: cssVar('--chart-tooltip-bg', 'rgba(8,14,28,0.92)', element),
    tooltipBorder: cssVar('--chart-tooltip-border', 'rgba(0,255,136,0.22)', element),
    tooltipText: cssVar('--chart-tooltip-text', 'rgba(235,245,255,0.92)', element),
    amber: cssVar('--amber', '#FFB300', element),
    cyan: cssVar('--cyan', '#00E5FF', element),
    purple: cssVar('--purple', '#B44EFF', element),
  };
}

function detectMobile() {
  return window.matchMedia('(max-width: 920px)').matches;
}

function signedPct(value) {
  if (value == null || Number.isNaN(Number(value))) return 'N/A';
  const number = Number(value);
  return `${number >= 0 ? '+' : ''}${(number * 100).toFixed(2)}%`;
}

function normalizeCandles(candles) {
  return (candles || []).map((item) => ({
    open: Number(item.open),
    high: Number(item.high),
    low: Number(item.low),
    close: Number(item.close),
    volume: Number(item.volume || 0),
    date: item.date || item.t || '',
  })).filter((item) => [item.open, item.high, item.low, item.close].every((value) => Number.isFinite(value)));
}

function distanceToSegment(px, py, ax, ay, bx, by) {
  const dx = bx - ax;
  const dy = by - ay;
  if (dx === 0 && dy === 0) return Math.hypot(px - ax, py - ay);
  const t = clamp(((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy), 0, 1);
  const cx = ax + t * dx;
  const cy = ay + t * dy;
  return Math.hypot(px - cx, py - cy);
}

function distanceToPolyline(point, polyline) {
  let best = Number.POSITIVE_INFINITY;
  for (let index = 1; index < polyline.length; index += 1) {
    const left = polyline[index - 1];
    const right = polyline[index];
    best = Math.min(best, distanceToSegment(point.x, point.y, left.x, left.y, right.x, right.y));
  }
  return best;
}

function buildScenarioBadge(key, theme = chartTheme()) {
  const map = {
    upper: { label: 'Bull Case', color: theme.up },
    center: { label: 'Base Case', color: theme.up },
    lower: { label: 'Risk Floor', color: theme.amber },
  };
  return map[key] || map.center;
}

function writeAuditState(state, viewport, candleWidth) {
  const projectionAnchors = Object.fromEntries(
    Object.entries(state.projectionLines || {}).map(([key, points]) => {
      const mid = points[Math.max(0, Math.floor(points.length * 0.55))] || null;
      const tail = points[points.length - 1] || null;
      return [key, {
        mid: mid ? { x: Number(mid.x.toFixed(2)), y: Number(mid.y.toFixed(2)) } : null,
        tail: tail ? { x: Number(tail.x.toFixed(2)), y: Number(tail.y.toFixed(2)) } : null,
      }];
    }),
  );
  const payload = {
    ...(window.__dashboardAuditState || {}),
    symbol: state.symbol,
    timeframe: state.timeframe,
    zoomLabel: state.zoomLabel,
    zoomPercent: parseZoomPercent(state.zoomLabel),
    visibleCount: viewport.visibleCount,
    candleWidth: Number(candleWidth.toFixed(2)),
    projectionWidth: Number(viewport.projectionWidth.toFixed(2)),
    canvasHeight: Number(viewport.height.toFixed(2)),
    selectedScenario: state.selectedScenario,
    predictionEnabled: state.predictionEnabled,
    marketSource: state.source,
    selectedProvider: state.selectedProvider || 'auto',
    projectionAnchors,
  };
  window.__dashboardAuditState = payload;
  state.canvas.dataset.visibleCount = String(payload.visibleCount);
  state.canvas.dataset.candleWidth = String(payload.candleWidth);
  state.canvas.dataset.zoomLabel = payload.zoomLabel;
  state.canvas.dataset.zoomPercent = String(payload.zoomPercent);
  state.canvas.dataset.selectedScenario = payload.selectedScenario || '';
  state.canvas.dataset.predictionEnabled = payload.predictionEnabled ? 'true' : 'false';
}

export function createDashboardKlineRenderer(options) {
  const state = {
    canvas: options.canvas,
    overlayEl: options.overlayEl,
    legendEl: options.legendEl,
    statusEl: options.statusEl,
    onProjectionSelect: options.onProjectionSelect,
    onBlankClick: options.onBlankClick,
    onZoomChange: options.onZoomChange,
    symbol: '',
    timeframe: '1D',
    zoomLabel: '116%',
    source: 'unknown',
    selectedProvider: 'auto',
    signal: null,
    analysis: null,
    indicators: new Set(['VOL']),
    candles: [],
    hover: null,
    selectedScenario: null,
    predictionEnabled: false,
    projectionLines: {},
    resizeObserver: null,
    resizeQueued: false,
  };

  const pointerPoint = (event) => {
    const rect = state.canvas.getBoundingClientRect();
    return {
      x: event.clientX - rect.left,
      y: event.clientY - rect.top,
    };
  };

  const requestZoomStep = (direction, origin) => {
    const nextLabel = stepZoomLabel(state.zoomLabel, direction);
    if (nextLabel !== state.zoomLabel) state.onZoomChange?.(nextLabel, origin);
  };

  const updateLegend = () => {
    if (!state.legendEl) return;
    const theme = chartTheme(state.canvas);
    if (!state.predictionEnabled) {
      state.legendEl.innerHTML = '';
      return;
    }

    if (state.selectedScenario) {
      const badge = buildScenarioBadge(state.selectedScenario, theme);
      state.legendEl.innerHTML = `
        <div style="display:inline-flex;align-items:center;gap:8px;padding:8px 12px;border-radius:999px;border:1px solid ${theme.tooltipBorder};background:${theme.tooltipBg};color:${badge.color};font:600 11px 'IBM Plex Mono', monospace">
          <span style="display:inline-block;width:8px;height:8px;border-radius:999px;background:${badge.color}"></span>
          <span>${badge.label}</span>
        </div>
      `;
      return;
    }

    const items = ['upper', 'center', 'lower'].map((key) => {
      const badge = buildScenarioBadge(key, theme);
      return `
        <div style="display:flex;align-items:center;gap:8px">
          <span style="display:inline-block;width:18px;height:0;border-top:2px dashed ${badge.color}"></span>
          <span>${badge.label}</span>
        </div>
      `;
    }).join('');

    state.legendEl.innerHTML = `
      <div style="display:grid;gap:6px;padding:10px 12px;border-radius:14px;border:1px solid ${theme.tooltipBorder};background:${theme.tooltipBg};color:${theme.muted};font:500 10px 'IBM Plex Mono', monospace">
        ${items}
      </div>
    `;
  };

  const updateStatus = () => {
    if (!state.statusEl) return;
    const theme = chartTheme(state.canvas);
    if (state.predictionEnabled) {
      state.statusEl.innerHTML = `<span style="color:${theme.up}">Real model projection</span> · ${state.source} candles`;
      return;
    }
    if (state.source === 'synthetic') {
      state.statusEl.innerHTML = `<span style="color:${theme.amber}">Real candles only</span> · degraded feed disables projection`;
      return;
    }
    if (state.source === 'unavailable') {
      state.statusEl.innerHTML = `<span style="color:${theme.amber}">Chart unavailable</span> · waiting for a real provider response`;
      return;
    }
    state.statusEl.innerHTML = `<span style="color:${theme.axis}">Real candles only</span> · model coverage unavailable`;
  };

  const updateOverlay = (viewport) => {
    if (!state.overlayEl) return;
    if (!state.predictionEnabled || !state.selectedScenario || !state.analysis) {
      state.overlayEl.style.display = 'none';
      state.overlayEl.innerHTML = '';
      return;
    }

    const line = state.projectionLines[state.selectedScenario] || [];
    const anchor = line[Math.max(0, Math.floor(line.length * 0.55))] || line[line.length - 1];
    if (!anchor) {
      state.overlayEl.style.display = 'none';
      return;
    }

    const boxWidth = clamp(viewport.width * 0.28, 220, 320);
    const boxHeight = clamp(170, 150, 200);
    let left = anchor.x + 16;
    let top = anchor.y - boxHeight - 16;

    if (left + boxWidth > viewport.width - 12) left = anchor.x - boxWidth - 18;
    if (left < 12) left = 12;
    if (top < 12) top = anchor.y + 16;
    if (left > viewport.width - boxWidth - 150 && top < 120) {
      left = Math.max(12, left - 150);
      top = anchor.y + 18;
    }
    if (top + boxHeight > viewport.height - 12) top = viewport.height - boxHeight - 12;

    const theme = chartTheme(state.canvas);
    const drivers = (state.analysis.drivers || []).slice(0, 3).map((item) => `<div>${item}</div>`).join('');
    state.overlayEl.style.display = 'block';
    state.overlayEl.style.left = `${left}px`;
    state.overlayEl.style.top = `${top}px`;
    state.overlayEl.style.width = `${boxWidth}px`;
    state.overlayEl.innerHTML = `
      <div style="display:grid;gap:6px;padding:12px 14px;border-radius:16px;border:1px solid ${theme.tooltipBorder};background:${theme.tooltipBg};box-shadow:0 18px 48px rgba(25,35,55,0.20);color:${theme.tooltipText};font:500 11px/1.45 'IBM Plex Mono', monospace">
        <div style="display:flex;align-items:center;justify-content:space-between;gap:8px">
          <strong style="font:700 12px Orbitron, 'IBM Plex Sans', sans-serif">${state.analysis.title}</strong>
          <span style="color:${theme.up}">${state.analysis.expectedReturnText}</span>
        </div>
        <div style="color:${theme.muted}">${state.analysis.directionText} · ${state.analysis.confidenceText}</div>
        <div style="color:${theme.axis}">Source: ${state.analysis.sourceText}</div>
        <div style="display:grid;gap:4px;color:${theme.tooltipText}">${drivers}</div>
        <div style="color:${theme.amber}">Why not opposite: ${state.analysis.oppositeReason}</div>
      </div>
    `;
  };

  const render = () => {
    const ctx = state.canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    const preset = interpolateZoomPreset(state.zoomLabel);
    const width = state.canvas.parentElement?.clientWidth || 960;
    const height = detectMobile() ? STAGE_HEIGHT.mobile : STAGE_HEIGHT.desktop;
    const theme = chartTheme(state.canvas);
    state.canvas.width = Math.round(width * dpr);
    state.canvas.height = Math.round(height * dpr);
    state.canvas.style.width = `${width}px`;
    state.canvas.style.height = `${height}px`;

    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, width, height);
    ctx.fillStyle = theme.bg;
    ctx.fillRect(0, 0, width, height);

    const pad = { left: 60, right: 108, top: 24, bottom: 40 };
    const innerWidth = width - pad.left - pad.right;
    const mainHeight = Math.floor((height - pad.top - pad.bottom) * 0.72);
    const volumeGap = 14;
    const volumeHeight = Math.max(76, Math.floor((height - pad.top - pad.bottom) * 0.18));
    const volumeTop = pad.top + mainHeight + volumeGap;
    const candles = state.candles.slice(-preset.visibleCount);
    const predictionScenarios = state.signal?.projection_scenarios || {};
    state.predictionEnabled = Boolean(
      state.signal
      && state.source !== 'synthetic'
      && state.signal.prediction_mode === 'model'
      && predictionScenarios.upper
      && predictionScenarios.center
      && predictionScenarios.lower
    );
    const projectionWidth = state.predictionEnabled ? innerWidth * preset.projectionWidthRatio : 0;
    const candleAreaWidth = innerWidth - projectionWidth;
    const visibleCount = Math.max(1, candles.length);
    const slotWidth = candleAreaWidth / Math.max(visibleCount, 1);
    const candleWidth = Math.max(3.5, slotWidth * preset.candleBodyRatio);
    const projectionStartX = pad.left + candleAreaWidth;
    const projectionEndX = pad.left + candleAreaWidth + projectionWidth;

    if (!candles.length) {
      ctx.fillStyle = theme.axis;
      ctx.font = "600 14px Orbitron, 'IBM Plex Sans', sans-serif";
      ctx.fillText(state.source === 'loading' ? 'Loading market candles...' : 'Market data unavailable', pad.left, height / 2);
      updateStatus();
      updateLegend();
      updateOverlay({ width, height, visibleCount: 0, projectionWidth });
      writeAuditState(state, { width, height, visibleCount: 0, projectionWidth }, 0);
      return;
    }

    const pricePadding = preset.pricePaddingRatio;
    const rawPrices = candles.flatMap((item) => [item.low, item.high]);
    const projectedReturns = state.predictionEnabled
      ? Object.values(predictionScenarios).map((scenario) => candles[candles.length - 1].close * (1 + Number(scenario.expected_return || 0)))
      : [];
    const minPrice = Math.min(...rawPrices, ...projectedReturns);
    const maxPrice = Math.max(...rawPrices, ...projectedReturns);
    const priceRange = Math.max(0.01, maxPrice - minPrice);
    const paddedMin = minPrice - priceRange * pricePadding;
    const paddedMax = maxPrice + priceRange * pricePadding;
    const scaleY = (price) => pad.top + mainHeight - ((price - paddedMin) / (paddedMax - paddedMin)) * mainHeight;
    const scaleX = (index) => pad.left + index * slotWidth + slotWidth / 2;

    for (let lineIndex = 0; lineIndex <= 5; lineIndex += 1) {
      const y = pad.top + (mainHeight / 5) * lineIndex;
      ctx.strokeStyle = theme.grid;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(pad.left, y);
      ctx.lineTo(width - pad.right, y);
      ctx.stroke();
      const price = paddedMax - ((paddedMax - paddedMin) / 5) * lineIndex;
      ctx.fillStyle = theme.axis;
      ctx.font = '10px IBM Plex Mono, monospace';
      ctx.textAlign = 'right';
      ctx.fillText(`$${price.toFixed(2)}`, pad.left - 8, y + 4);
    }

    const labelInterval = Math.max(1, Math.floor(candles.length / 7));
    candles.forEach((candle, index) => {
      const x = scaleX(index);
      const bull = candle.close >= candle.open;
      const color = bull ? theme.up : theme.down;
      ctx.strokeStyle = color;
      ctx.lineWidth = 1.1;
      ctx.beginPath();
      ctx.moveTo(x, scaleY(candle.high));
      ctx.lineTo(x, scaleY(candle.low));
      ctx.stroke();
      const bodyTop = Math.min(scaleY(candle.open), scaleY(candle.close));
      const bodyHeight = Math.max(2, Math.abs(scaleY(candle.open) - scaleY(candle.close)));
      if (bull) {
        ctx.strokeRect(x - candleWidth / 2, bodyTop, candleWidth, bodyHeight);
      } else {
        ctx.fillStyle = color;
        ctx.fillRect(x - candleWidth / 2, bodyTop, candleWidth, bodyHeight);
      }

      if (index % labelInterval === 0) {
        ctx.fillStyle = theme.axis;
        ctx.font = '10px IBM Plex Mono, monospace';
        ctx.textAlign = 'center';
        const label = new Date(candle.date || Date.now()).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
        ctx.fillText(label, x, height - 12);
      }
    });

    if (state.indicators.has('MA20') && candles.length >= 20) {
      ctx.strokeStyle = theme.amber;
      ctx.lineWidth = 1.3;
      ctx.setLineDash([6, 4]);
      ctx.beginPath();
      candles.forEach((_, index) => {
        if (index < 19) return;
        const average = candles.slice(index - 19, index + 1).reduce((sum, item) => sum + item.close, 0) / 20;
        const pointX = scaleX(index);
        const pointY = scaleY(average);
        if (index === 19) ctx.moveTo(pointX, pointY);
        else ctx.lineTo(pointX, pointY);
      });
      ctx.stroke();
      ctx.setLineDash([]);
    }

    if (state.indicators.has('MA60') && candles.length >= 60) {
      ctx.strokeStyle = theme.cyan;
      ctx.lineWidth = 1.3;
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      candles.forEach((_, index) => {
        if (index < 59) return;
        const average = candles.slice(index - 59, index + 1).reduce((sum, item) => sum + item.close, 0) / 60;
        const pointX = scaleX(index);
        const pointY = scaleY(average);
        if (index === 59) ctx.moveTo(pointX, pointY);
        else ctx.lineTo(pointX, pointY);
      });
      ctx.stroke();
      ctx.setLineDash([]);
    }

    if (state.indicators.has('BOLL') && candles.length >= 20) {
      const upper = [];
      const lower = [];
      for (let index = 19; index < candles.length; index += 1) {
        const slice = candles.slice(index - 19, index + 1).map((item) => item.close);
        const mean = slice.reduce((sum, value) => sum + value, 0) / slice.length;
        const variance = slice.reduce((sum, value) => sum + (value - mean) ** 2, 0) / slice.length;
        const std = Math.sqrt(variance);
        upper.push({ x: scaleX(index), y: scaleY(mean + std * 2) });
        lower.push({ x: scaleX(index), y: scaleY(mean - std * 2) });
      }
      ctx.fillStyle = cssVar('--violet-lo', 'rgba(180, 78, 255, 0.06)', state.canvas);
      ctx.beginPath();
      upper.forEach((point, index) => {
        if (!index) ctx.moveTo(point.x, point.y);
        else ctx.lineTo(point.x, point.y);
      });
      lower.slice().reverse().forEach((point) => ctx.lineTo(point.x, point.y));
      ctx.closePath();
      ctx.fill();
      ctx.strokeStyle = theme.purple;
      ctx.setLineDash([3, 5]);
      [upper, lower].forEach((points) => {
        ctx.beginPath();
        points.forEach((point, index) => {
          if (!index) ctx.moveTo(point.x, point.y);
          else ctx.lineTo(point.x, point.y);
        });
        ctx.stroke();
      });
      ctx.setLineDash([]);
    }

    const maxVolume = Math.max(...candles.map((item) => item.volume || 0), 1);
    if (state.indicators.has('VOL')) {
      candles.forEach((candle, index) => {
        const x = scaleX(index);
        const volumeHeightScaled = clamp((candle.volume / maxVolume) * volumeHeight, 4, volumeHeight);
        ctx.fillStyle = candle.close >= candle.open ? theme.upSoft : theme.downSoft;
        ctx.fillRect(x - candleWidth / 2, volumeTop + volumeHeight - volumeHeightScaled, candleWidth, volumeHeightScaled);
      });
    }

    state.projectionLines = {};
    if (state.predictionEnabled) {
      const lastClose = candles[candles.length - 1].close;
      const fillTop = [];
      const fillBottom = [];
      const steps = 14;
      const scenarioColors = {
        upper: theme.up,
        center: theme.up,
        lower: theme.amber,
      };

      ctx.strokeStyle = theme.tooltipBorder;
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.moveTo(projectionStartX, pad.top);
      ctx.lineTo(projectionStartX, volumeTop + volumeHeight);
      ctx.stroke();
      ctx.setLineDash([]);

      ['upper', 'center', 'lower'].forEach((key) => {
        const targetClose = lastClose * (1 + Number(predictionScenarios[key].expected_return || 0));
        const points = [];
        for (let step = 0; step <= steps; step += 1) {
          const progress = step / steps;
          const eased = 1 - (1 - progress) ** 1.6;
          const x = projectionStartX + projectionWidth * progress;
          const y = scaleY(lastClose + (targetClose - lastClose) * eased);
          points.push({ x, y });
        }
        state.projectionLines[key] = points;
        if (key === 'upper') fillTop.push(...points);
        if (key === 'lower') fillBottom.push(...points);

        ctx.strokeStyle = scenarioColors[key];
        ctx.lineWidth = key === 'center' ? 2.4 : 1.8;
        ctx.setLineDash(key === 'center' ? [8, 5] : [6, 6]);
        ctx.beginPath();
        points.forEach((point, index) => {
          if (!index) ctx.moveTo(point.x, point.y);
          else ctx.lineTo(point.x, point.y);
        });
        ctx.stroke();
        ctx.setLineDash([]);
      });

      ctx.fillStyle = theme.upSoft;
      ctx.beginPath();
      fillTop.forEach((point, index) => {
        if (!index) ctx.moveTo(point.x, point.y);
        else ctx.lineTo(point.x, point.y);
      });
      fillBottom.slice().reverse().forEach((point) => ctx.lineTo(point.x, point.y));
      ctx.closePath();
      ctx.fill();

      if (state.indicators.has('VOL')) {
        const volumeSteps = 7;
        const baseProjectedVolume = candles.slice(-8).reduce((sum, item) => sum + item.volume, 0) / Math.min(8, candles.length);
        for (let step = 0; step < volumeSteps; step += 1) {
          const progress = (step + 0.5) / volumeSteps;
          const x = projectionStartX + projectionWidth * progress;
          const scaled = baseProjectedVolume * (1 + Math.abs(Number(predictionScenarios.center.expected_return || 0)) * 2.5 * progress);
          const barHeight = clamp((scaled / maxVolume) * volumeHeight, 8, volumeHeight);
          ctx.fillStyle = theme.upSoft;
          ctx.fillRect(x - Math.max(5, candleWidth * 0.7), volumeTop + volumeHeight - barHeight, Math.max(10, candleWidth * 1.25), barHeight);
        }

        ctx.strokeStyle = theme.tooltipBorder;
        ctx.setLineDash([4, 6]);
        ctx.beginPath();
        ctx.moveTo(projectionStartX, volumeTop + volumeHeight * 0.62);
        ctx.lineTo(projectionEndX, volumeTop + volumeHeight * 0.42);
        ctx.stroke();
        ctx.setLineDash([]);
      }
    }

    if (state.hover) {
      const hoverX = clamp(state.hover.x, pad.left, projectionStartX - 4);
      const candleIndex = clamp(Math.round((hoverX - pad.left - slotWidth / 2) / slotWidth), 0, candles.length - 1);
      const candle = candles[candleIndex];
      const pointX = scaleX(candleIndex);
      const pointY = scaleY(candle.close);
      ctx.strokeStyle = theme.tooltipBorder;
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.moveTo(pointX, pad.top);
      ctx.lineTo(pointX, volumeTop + volumeHeight);
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(pad.left, pointY);
      ctx.lineTo(width - pad.right, pointY);
      ctx.stroke();
      ctx.setLineDash([]);

      const tooltipLines = [
        new Date(candle.date || Date.now()).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }),
        `O ${candle.open.toFixed(2)}  H ${candle.high.toFixed(2)}  L ${candle.low.toFixed(2)}  C ${candle.close.toFixed(2)}`,
        `Vol ${(candle.volume / 1_000_000).toFixed(2)}M`,
      ];
      const tooltipWidth = 208;
      const tooltipHeight = 74;
      const tooltipX = clamp(pointX + 14, 10, projectionStartX - tooltipWidth - 12);
      const tooltipY = clamp(pointY - tooltipHeight - 10, 12, volumeTop - tooltipHeight - 8);
      ctx.fillStyle = theme.tooltipBg;
      ctx.strokeStyle = theme.tooltipBorder;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.roundRect(tooltipX, tooltipY, tooltipWidth, tooltipHeight, 12);
      ctx.fill();
      ctx.stroke();
      tooltipLines.forEach((line, index) => {
        ctx.fillStyle = index === 0 ? theme.axis : theme.tooltipText;
        ctx.font = `${index === 0 ? 10 : 11}px IBM Plex Mono, monospace`;
        ctx.fillText(line, tooltipX + 12, tooltipY + 18 + index * 18);
      });
    }

    const lastClose = candles[candles.length - 1].close;
    const labelY = scaleY(lastClose);
    ctx.fillStyle = theme.upSoft;
    ctx.strokeStyle = theme.up;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.roundRect(width - pad.right + 4, labelY - 12, 66, 24, 10);
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = theme.up;
    ctx.textAlign = 'center';
    ctx.font = '700 11px IBM Plex Mono, monospace';
    ctx.fillText(lastClose.toFixed(2), width - pad.right + 37, labelY + 4);

    updateStatus();
    updateLegend();
    updateOverlay({ width, height, visibleCount, projectionWidth });
    writeAuditState(state, { width, height, visibleCount, projectionWidth }, candleWidth);
  };

  const handleMove = (event) => {
    state.hover = pointerPoint(event);
    render();
  };

  const handleLeave = () => {
    state.hover = null;
    render();
  };

  const handleClick = (event) => {
    if (!state.predictionEnabled) {
      state.onBlankClick?.({ target: 'chart_blank' });
      return;
    }
    const point = pointerPoint(event);
    const candidates = Object.entries(state.projectionLines).map(([key, points]) => ({
      key,
      distance: distanceToPolyline(point, points),
    })).sort((left, right) => left.distance - right.distance);
    const hit = candidates[0];
    if (hit && hit.distance <= 18) {
      const nextSelection = state.selectedScenario === hit.key ? null : hit.key;
      state.onProjectionSelect?.(nextSelection, {
        reason: nextSelection ? 'projection_hit' : 'projection_toggle_clear',
        previous: state.selectedScenario,
      });
      return;
    }
    state.onBlankClick?.({ target: 'projection_blank' });
  };

  const handleWheel = (event) => {
    event.preventDefault();
    if (event.deltaY > 0) requestZoomStep(-1, 'wheel');
    if (event.deltaY < 0) requestZoomStep(1, 'wheel');
  };

  state.canvas.addEventListener('mousemove', handleMove);
  state.canvas.addEventListener('mouseleave', handleLeave);
  state.canvas.addEventListener('click', handleClick);
  state.canvas.addEventListener('wheel', handleWheel, { passive: false });
  state.resizeObserver = new ResizeObserver(() => {
    if (state.resizeQueued) return;
    state.resizeQueued = true;
    requestAnimationFrame(() => {
      state.resizeQueued = false;
      render();
    });
  });
  state.resizeObserver.observe(state.canvas.parentElement);

  return {
    update(nextState) {
      state.symbol = nextState.symbol || state.symbol;
      state.timeframe = nextState.timeframe || state.timeframe;
      state.zoomLabel = nextState.zoomLabel || state.zoomLabel;
      state.source = nextState.source || 'unknown';
      state.selectedProvider = nextState.selectedProvider || state.selectedProvider || 'auto';
      state.signal = nextState.signal || null;
      state.analysis = nextState.analysis || null;
      state.selectedScenario = nextState.selectedScenario || null;
      state.indicators = new Set(nextState.indicators || []);
      state.candles = normalizeCandles(nextState.candles);
      render();
    },
    render,
    destroy() {
      state.resizeObserver?.disconnect();
      state.canvas.removeEventListener('mousemove', handleMove);
      state.canvas.removeEventListener('mouseleave', handleLeave);
      state.canvas.removeEventListener('click', handleClick);
      state.canvas.removeEventListener('wheel', handleWheel);
      if (state.overlayEl) {
        state.overlayEl.style.display = 'none';
        state.overlayEl.innerHTML = '';
      }
    },
  };
}


