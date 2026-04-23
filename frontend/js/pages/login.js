import { api } from '../qtapi.js?v=8';
import { toast } from '../components/toast.js?v=8';
import { t, getLang, onLangChange } from '../i18n.js?v=8';

export function render(container) {
  container.innerHTML = buildShell();
  bindEvents(container);
  onLangChange(() => {
    container.innerHTML = buildShell();
    bindEvents(container);
  });
}

function buildShell() {
  const lang = getLang();
  const homeLabel = lang === 'zh' ? '返回首页' : 'Back Home';
  const zhLabel = lang === 'en' ? 'CH' : '中';
  return `
  <div class="auth-split">
    <div class="auth-visual">
      <div class="auth-visual-content">
        <div class="auth-logo">
          <svg width="32" height="32" viewBox="0 0 18 18" fill="none">
            <path d="M2 13 L6 7 L9 10 L13 4 L16 7" stroke="#00FF88" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            <circle cx="16" cy="7" r="2" fill="#00FF88"/>
          </svg>
          <span class="auth-logo-text">Quant Terminal</span>
        </div>
        <div class="auth-headline">${t('auth.headline_login').replace('\n', '<br>')}</div>
        <div class="auth-tagline">${t('auth.tagline_login').replace('\n', '<br>')}</div>
        <canvas id="auth-kline" class="auth-kline-canvas" width="360" height="160"></canvas>
        <div class="auth-stats">
          <div class="auth-stat"><div class="auth-stat-val">1.84</div><div class="auth-stat-label">${t('auth.stat_sharpe')}</div></div>
          <div class="auth-stat"><div class="auth-stat-val">24/7</div><div class="auth-stat-label">${t('auth.stat_signals')}</div></div>
          <div class="auth-stat"><div class="auth-stat-val">S&amp;P500</div><div class="auth-stat-label">${t('auth.stat_universe')}</div></div>
        </div>
      </div>
    </div>

    <div class="auth-form-panel">
      <div class="auth-form-wrap">
        <div class="auth-utility-row">
          <a href="#/dashboard" class="auth-home-btn" id="auth-home-link">
            <span class="auth-home-btn__icon"><-</span>
            <span class="auth-home-btn__label">${homeLabel}</span>
          </a>
          <div style="display:flex;gap:0" data-no-autotranslate="true" translate="no">
            <button class="lang-btn${lang === 'zh' ? ' active' : ''}" data-lang="zh" data-no-autotranslate="true" translate="no">${zhLabel}</button>
            <button class="lang-btn${lang === 'en' ? ' active' : ''}" data-lang="en" data-no-autotranslate="true" translate="no">EN</button>
          </div>
        </div>

        <div class="auth-form-title">${t('auth.welcome')}</div>
        <div class="auth-form-sub">${t('auth.sub_login')}</div>

        <form id="login-form" class="auth-form" autocomplete="on">
          <div class="auth-field">
            <label class="auth-label">${t('auth.email')}</label>
            <input class="auth-input" id="login-email" type="email" autocomplete="email" placeholder="${t('auth.enter_email')}" required>
          </div>
          <div class="auth-field">
            <label class="auth-label" style="display:flex;justify-content:space-between">
              <span>${t('auth.password')}</span>
              <a href="#/reset-password" class="auth-link">${t('auth.forgot_pw')}</a>
            </label>
            <div style="position:relative">
              <input class="auth-input" id="login-password" type="password" autocomplete="current-password" placeholder="${t('auth.enter_password')}" required>
              <button type="button" class="auth-eye-btn" id="toggle-pw" tabindex="-1">Show</button>
            </div>
          </div>
          <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">
            <input type="checkbox" id="remember-me" style="accent-color:var(--green);width:14px;height:14px">
            <label for="remember-me" style="font-size:11px;color:var(--text-dim);cursor:pointer">${t('auth.remember')}</label>
          </div>

          <div id="login-error" class="auth-error" style="display:none"></div>

          <button class="btn btn-primary auth-submit" type="submit" id="login-btn">${t('auth.sign_in')}</button>
        </form>

        <div class="auth-divider"><span>${t('auth.or')}</span></div>

        <div class="auth-switch">
          ${t('auth.no_account')}
          <a href="#/register" class="auth-link">${t('auth.sign_up')}</a>
        </div>

      </div>
    </div>
  </div>`;
}

function bindEvents(container) {
  container.querySelectorAll('.lang-btn').forEach((button) => {
    button.addEventListener('click', () => {
      import('../i18n.js?v=8').then((module) => module.setLang(button.dataset.lang));
    });
  });

  container.querySelector('#toggle-pw')?.addEventListener('click', () => {
    const pw = container.querySelector('#login-password');
    const button = container.querySelector('#toggle-pw');
    const nextType = pw.type === 'password' ? 'text' : 'password';
    pw.type = nextType;
    button.textContent = nextType === 'text' ? 'Hide' : 'Show';
  });

  container.querySelector('#login-form')?.addEventListener('submit', async (event) => {
    event.preventDefault();
    await doLogin(container);
  });

  setTimeout(() => drawAuthKline(container.querySelector('#auth-kline')), 50);
}

async function doLogin(container) {
  const button = container.querySelector('#login-btn');
  const errorEl = container.querySelector('#login-error');
  const email = container.querySelector('#login-email').value.trim();
  const password = container.querySelector('#login-password').value;

  errorEl.style.display = 'none';
  button.disabled = true;
  button.textContent = t('common.loading');

  try {
    const response = await api.auth.login({ email, password });
    const remember = container.querySelector('#remember-me')?.checked;
    const storage = remember ? localStorage : sessionStorage;
    storage.setItem('qt-token', response.token);
    storage.setItem('qt-user', JSON.stringify(response.user));
    toast.success(t('auth.welcome'), response.user?.name || email);
    window.location.hash = '#/dashboard';
  } catch (error) {
    errorEl.textContent = error.message;
    errorEl.style.display = 'block';
    button.disabled = false;
    button.textContent = t('auth.sign_in');
  }
}

function drawAuthKline(canvas) {
  if (!canvas) return;
  const dpr = window.devicePixelRatio || 1;
  const width = 360;
  const height = 160;
  canvas.width = width * dpr;
  canvas.height = height * dpr;
  canvas.style.width = `${width}px`;
  canvas.style.height = `${height}px`;
  const ctx = canvas.getContext('2d');
  ctx.scale(dpr, dpr);

  let price = 180;
  const candles = [];
  for (let index = 0; index < 60; index += 1) {
    const trend = Math.sin(index * 0.15) * 0.004 + 0.001;
    const vol = 0.012;
    const open = price;
    const close = price * (1 + (Math.random() - 0.45 + trend) * vol * 2);
    const high = Math.max(open, close) * (1 + Math.random() * vol * 0.5);
    const low = Math.min(open, close) * (1 - Math.random() * vol * 0.5);
    candles.push({ open, high, low, close });
    price = close;
  }

  const pad = 10;
  const allPrices = candles.flatMap((item) => [item.high, item.low]);
  const minPrice = Math.min(...allPrices);
  const maxPrice = Math.max(...allPrices);
  const scaleY = (value) => pad + (height - 2 * pad) * (1 - (value - minPrice) / (maxPrice - minPrice));
  const candleWidth = (width - 2 * pad) / candles.length;

  const linePoints = candles.map((item, index) => ({
    x: pad + index * candleWidth + candleWidth / 2,
    y: scaleY((item.open + item.close) / 2),
  }));
  const gradient = ctx.createLinearGradient(0, pad, 0, height);
  gradient.addColorStop(0, 'rgba(0,255,136,0.2)');
  gradient.addColorStop(1, 'transparent');
  ctx.beginPath();
  linePoints.forEach((point, index) => {
    if (!index) ctx.moveTo(point.x, point.y);
    else ctx.lineTo(point.x, point.y);
  });
  ctx.lineTo(linePoints[linePoints.length - 1].x, height);
  ctx.lineTo(linePoints[0].x, height);
  ctx.closePath();
  ctx.fillStyle = gradient;
  ctx.fill();

  candles.forEach((candle, index) => {
    const x = pad + index * candleWidth + candleWidth / 2;
    const bull = candle.close >= candle.open;
    const color = bull ? '#00FF88' : '#FF3D57';
    ctx.strokeStyle = color;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(x, scaleY(candle.high));
    ctx.lineTo(x, scaleY(candle.low));
    ctx.stroke();
    const bodyHeight = Math.abs(scaleY(candle.close) - scaleY(candle.open)) || 1;
    ctx.fillStyle = bull ? 'rgba(0,255,136,0.6)' : color;
    ctx.fillRect(x - candleWidth * 0.3, Math.min(scaleY(candle.open), scaleY(candle.close)), candleWidth * 0.6, bodyHeight);
  });

  ctx.beginPath();
  linePoints.forEach((point, index) => {
    if (!index) ctx.moveTo(point.x, point.y);
    else ctx.lineTo(point.x, point.y);
  });
  ctx.strokeStyle = '#00FF88';
  ctx.lineWidth = 1.5;
  ctx.shadowColor = '#00FF88';
  ctx.shadowBlur = 8 * dpr;
  ctx.stroke();
  ctx.shadowBlur = 0;
}
