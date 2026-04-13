import { api } from '../qtapi.js?v=8';
import { toast } from '../components/toast.js?v=8';
import { t, getLang, onLangChange } from '../i18n.js?v=8';

export function render(container) {
  container.innerHTML = buildShell();
  bindEvents(container);
  onLangChange(() => { container.innerHTML = buildShell(); bindEvents(container); });
}

function buildShell() {
  const lang = getLang();
  const zhLabel = lang === 'en' ? 'CH' : '中';
  return `
  <div class="auth-split">
    <!-- LEFT: Visual panel -->
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

        <!-- Mini K-line visual -->
        <canvas id="auth-kline" class="auth-kline-canvas" width="360" height="160"></canvas>

        <!-- Stats -->
        <div class="auth-stats">
          <div class="auth-stat"><div class="auth-stat-val">1.84</div><div class="auth-stat-label">${t('auth.stat_sharpe')}</div></div>
          <div class="auth-stat"><div class="auth-stat-val">24/7</div><div class="auth-stat-label">${t('auth.stat_signals')}</div></div>
          <div class="auth-stat"><div class="auth-stat-val">S&amp;P500</div><div class="auth-stat-label">${t('auth.stat_universe')}</div></div>
        </div>
      </div>
    </div>

    <!-- RIGHT: Form -->
    <div class="auth-form-panel">
      <div class="auth-form-wrap">
        <!-- Lang toggle -->
        <div style="position:absolute;top:20px;right:24px;display:flex;gap:0" data-no-autotranslate="true" translate="no">
          <button class="lang-btn${lang==='zh'?' active':''}" data-lang="zh" data-no-autotranslate="true" translate="no">${zhLabel}</button>
          <button class="lang-btn${lang==='en'?' active':''}" data-lang="en" data-no-autotranslate="true" translate="no">EN</button>
        </div>

        <div class="auth-form-title">${t('auth.welcome')}</div>
        <div class="auth-form-sub">${t('auth.sub_login')}</div>

        <form id="login-form" class="auth-form" autocomplete="on">
          <div class="auth-field">
            <label class="auth-label">${t('auth.email')}</label>
            <input class="auth-input" id="login-email" type="email" autocomplete="email"
              placeholder="${t('auth.enter_email')}" required>
          </div>
          <div class="auth-field">
            <label class="auth-label" style="display:flex;justify-content:space-between">
              <span>${t('auth.password')}</span>
              <a href="#/reset-password" class="auth-link">${t('auth.forgot_pw')}</a>
            </label>
            <div style="position:relative">
              <input class="auth-input" id="login-password" type="password" autocomplete="current-password"
                placeholder="${t('auth.enter_password')}" required>
              <button type="button" class="auth-eye-btn" id="toggle-pw" tabindex="-1">👁</button>
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

        <!-- Demo credentials note -->
        <div style="margin-top:24px;padding:12px 14px;background:rgba(0,255,136,0.05);border:1px solid rgba(0,255,136,0.15);border-radius:8px;font-size:10px;color:var(--text-dim);font-family:var(--f-mono)">
          <div style="color:var(--green);margin-bottom:4px">${t('auth.demo_title')}</div>
          ${t('auth.demo_text')}
        </div>
      </div>
    </div>
  </div>`;
}

function bindEvents(container) {
  // Lang toggle
  container.querySelectorAll('.lang-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      import('../i18n.js?v=8').then(m => m.setLang(btn.dataset.lang));
    });
  });

  // Password toggle
  container.querySelector('#toggle-pw')?.addEventListener('click', () => {
    const pw = container.querySelector('#login-password');
    pw.type = pw.type === 'password' ? 'text' : 'password';
  });

  // Form submit
  container.querySelector('#login-form').addEventListener('submit', async e => {
    e.preventDefault();
    await doLogin(container);
  });

  // Draw decorative K-line
  setTimeout(() => drawAuthKline(container.querySelector('#auth-kline')), 50);
}

async function doLogin(container) {
  const btn    = container.querySelector('#login-btn');
  const errEl  = container.querySelector('#login-error');
  const email  = container.querySelector('#login-email').value.trim();
  const pw     = container.querySelector('#login-password').value;

  errEl.style.display = 'none';
  btn.disabled = true; btn.textContent = t('common.loading');

  try {
    const res = await api.auth.login({ email, password: pw });
    const remember = container.querySelector('#remember-me')?.checked;
    const storage = remember ? localStorage : sessionStorage;
    storage.setItem('qt-token', res.token);
    storage.setItem('qt-user', JSON.stringify(res.user));
    toast.success(t('auth.welcome'), res.user?.name || email);
    window.location.hash = '#/dashboard';
  } catch(err) {
    errEl.textContent = err.message;
    errEl.style.display = 'block';
    btn.disabled = false;
    btn.textContent = t('auth.sign_in');
  }
}

function drawAuthKline(canvas) {
  if (!canvas) return;
  const dpr = window.devicePixelRatio || 1;
  const W = 360, H = 160;
  canvas.width = W * dpr; canvas.height = H * dpr;
  canvas.style.width = W + 'px'; canvas.style.height = H + 'px';
  const ctx = canvas.getContext('2d');
  ctx.scale(dpr, dpr);

  let price = 180;
  const candles = [];
  for (let i = 0; i < 60; i++) {
    const trend = Math.sin(i * 0.15) * 0.004 + 0.001;
    const vol = 0.012;
    const o = price;
    const c = price * (1 + (Math.random() - 0.45 + trend) * vol * 2);
    const h = Math.max(o, c) * (1 + Math.random() * vol * 0.5);
    const l = Math.min(o, c) * (1 - Math.random() * vol * 0.5);
    candles.push({ o, h, l, c });
    price = c;
  }

  const pad = 10;
  const allPrices = candles.flatMap(c => [c.h, c.l]);
  const minP = Math.min(...allPrices), maxP = Math.max(...allPrices);
  const py = v => pad + (H - 2*pad) * (1 - (v - minP) / (maxP - minP));
  const cW = (W - 2*pad) / candles.length;

  const linePoints = candles.map((c, i) => ({ x: pad + i * cW + cW/2, y: py((c.o+c.c)/2) }));
  const grad = ctx.createLinearGradient(0, pad, 0, H);
  grad.addColorStop(0, 'rgba(0,255,136,0.2)');
  grad.addColorStop(1, 'transparent');
  ctx.beginPath();
  linePoints.forEach((p, i) => i===0 ? ctx.moveTo(p.x, p.y) : ctx.lineTo(p.x, p.y));
  ctx.lineTo(linePoints[linePoints.length-1].x, H);
  ctx.lineTo(linePoints[0].x, H);
  ctx.closePath();
  ctx.fillStyle = grad; ctx.fill();

  candles.forEach((c, i) => {
    const x = pad + i * cW + cW/2;
    const bull = c.c >= c.o;
    const color = bull ? '#00FF88' : '#FF3D57';
    ctx.strokeStyle = color; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(x, py(c.h)); ctx.lineTo(x, py(c.l)); ctx.stroke();
    const bodyH = Math.abs(py(c.c) - py(c.o)) || 1;
    ctx.fillStyle = bull ? 'rgba(0,255,136,0.6)' : color;
    ctx.fillRect(x - cW*0.3, Math.min(py(c.o), py(c.c)), cW*0.6, bodyH);
  });

  ctx.beginPath();
  linePoints.forEach((p, i) => i===0 ? ctx.moveTo(p.x, p.y) : ctx.lineTo(p.x, p.y));
  ctx.strokeStyle = '#00FF88'; ctx.lineWidth = 1.5;
  ctx.shadowColor = '#00FF88'; ctx.shadowBlur = 8*dpr;
  ctx.stroke(); ctx.shadowBlur = 0;
}
