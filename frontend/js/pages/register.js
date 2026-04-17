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
  <div class="auth-split auth-split--reversed">
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

        <div class="auth-form-title">${t('auth.register')}</div>
        <div class="auth-form-sub">${t('auth.sub_register')}</div>

        <form id="register-form" class="auth-form" autocomplete="on">
          <div class="auth-field">
            <label class="auth-label">${t('auth.name')}</label>
            <input class="auth-input" id="reg-name" type="text" autocomplete="name" placeholder="${t('auth.enter_name')}">
          </div>
          <div class="auth-field">
            <label class="auth-label">${t('auth.email')}</label>
            <input class="auth-input" id="reg-email" type="email" autocomplete="email" placeholder="${t('auth.enter_email')}" required>
          </div>
          <div class="auth-field">
            <label class="auth-label">${t('auth.password')}</label>
            <div style="position:relative">
              <input class="auth-input" id="reg-password" type="password" placeholder="${t('auth.enter_password')}" required minlength="6">
              <button type="button" class="auth-eye-btn" id="toggle-pw1" tabindex="-1">Show</button>
            </div>
            <div id="pw-strength" style="height:3px;border-radius:2px;margin-top:6px;background:rgba(255,255,255,0.08);overflow:hidden">
              <div id="pw-strength-bar" style="height:100%;width:0;transition:all 0.3s;border-radius:2px"></div>
            </div>
            <div id="pw-strength-label" style="font-size:9px;color:var(--text-dim);font-family:var(--f-mono);margin-top:3px"></div>
          </div>
          <div class="auth-field">
            <label class="auth-label">${t('auth.confirm_pw')}</label>
            <div style="position:relative">
              <input class="auth-input" id="reg-confirm" type="password" placeholder="${t('auth.enter_password')}" required>
              <button type="button" class="auth-eye-btn" id="toggle-pw2" tabindex="-1">Show</button>
            </div>
          </div>

          <div style="font-size:10px;color:var(--text-dim);padding:8px 0;line-height:1.5">
            ${t('auth.terms')}
          </div>

          <div id="reg-error" class="auth-error" style="display:none"></div>

          <button class="btn btn-primary auth-submit" type="submit" id="reg-btn">${t('auth.sign_up')}</button>
        </form>

        <div class="auth-divider"><span>${t('auth.or')}</span></div>

        <div class="auth-switch">
          ${t('auth.have_account')}
          <a href="#/login" class="auth-link">${t('auth.sign_in')}</a>
        </div>

        <div class="auth-benefits">
          ${[
            ['DATA', t('auth.benefit1')],
            ['AI', t('auth.benefit2')],
            ['RISK', t('auth.benefit3')],
          ].map(([icon, text]) => `
            <div class="auth-benefit-item">
              <span>${icon}</span><span>${text}</span>
            </div>`).join('')}
        </div>
      </div>
    </div>

    <div class="auth-visual auth-visual--right">
      <div class="auth-visual-content">
        <div class="auth-logo">
          <svg width="32" height="32" viewBox="0 0 18 18" fill="none">
            <path d="M2 13 L6 7 L9 10 L13 4 L16 7" stroke="#00FF88" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            <circle cx="16" cy="7" r="2" fill="#00FF88"/>
          </svg>
          <span class="auth-logo-text">Quant Terminal</span>
        </div>
        <div class="auth-headline">${t('auth.headline_register').replace('\n', '<br>')}</div>
        <div class="auth-tagline">${t('auth.tagline_register').replace('\n', '<br>')}</div>

        <div class="auth-metric-showcase" id="metric-showcase">
          <div class="auth-showcase-card">
            <div class="auth-showcase-val">1.84</div>
            <div class="auth-showcase-key">${t('auth.showcase_sharpe_key')}</div>
            <div class="auth-showcase-sub">${t('auth.showcase_sharpe_sub')}</div>
          </div>
          <div class="auth-showcase-card" style="opacity:0.6;transform:scale(0.9)">
            <div class="auth-showcase-val">280bps</div>
            <div class="auth-showcase-key">${t('auth.showcase_alpha_key')}</div>
            <div class="auth-showcase-sub">${t('auth.showcase_alpha_sub')}</div>
          </div>
        </div>

        <div class="auth-stats">
          <div class="auth-stat"><div class="auth-stat-val">500+</div><div class="auth-stat-label">${t('auth.stat_companies')}</div></div>
          <div class="auth-stat"><div class="auth-stat-val">9</div><div class="auth-stat-label">${t('auth.stat_esg')}</div></div>
          <div class="auth-stat"><div class="auth-stat-val">Real-time</div><div class="auth-stat-label">${t('auth.stat_market')}</div></div>
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

  container.querySelector('#toggle-pw1')?.addEventListener('click', () => {
    togglePasswordField(container.querySelector('#reg-password'), container.querySelector('#toggle-pw1'));
  });
  container.querySelector('#toggle-pw2')?.addEventListener('click', () => {
    togglePasswordField(container.querySelector('#reg-confirm'), container.querySelector('#toggle-pw2'));
  });

  container.querySelector('#reg-password')?.addEventListener('input', (event) => {
    const value = event.target.value;
    const bar = container.querySelector('#pw-strength-bar');
    const label = container.querySelector('#pw-strength-label');
    const strength = getPasswordStrength(value);
    bar.style.width = `${strength.pct}%`;
    bar.style.background = strength.color;
    label.textContent = value ? strength.label : '';
    label.style.color = strength.color;
  });

  container.querySelector('#register-form')?.addEventListener('submit', async (event) => {
    event.preventDefault();
    await doRegister(container);
  });
}

function togglePasswordField(input, button) {
  const nextType = input.type === 'password' ? 'text' : 'password';
  input.type = nextType;
  button.textContent = nextType === 'text' ? 'Hide' : 'Show';
}

function getPasswordStrength(password) {
  if (!password || password.length < 3) {
    return { pct: 10, color: 'var(--red)', label: t('auth.pw_too_short') };
  }
  let score = 0;
  if (password.length >= 8) score += 1;
  if (password.length >= 12) score += 1;
  if (/[A-Z]/.test(password)) score += 1;
  if (/[0-9]/.test(password)) score += 1;
  if (/[^A-Za-z0-9]/.test(password)) score += 1;
  const levels = [
    { min: 0, pct: 20, color: 'var(--red)', label: t('auth.pw_weak') },
    { min: 2, pct: 45, color: 'var(--amber)', label: t('auth.pw_fair') },
    { min: 3, pct: 70, color: '#F0A500', label: t('auth.pw_good') },
    { min: 4, pct: 100, color: 'var(--green)', label: t('auth.pw_strong') },
  ];
  return levels.filter((item) => score >= item.min).pop() || levels[0];
}

async function doRegister(container) {
  const button = container.querySelector('#reg-btn');
  const errorEl = container.querySelector('#reg-error');
  const name = container.querySelector('#reg-name').value.trim();
  const email = container.querySelector('#reg-email').value.trim();
  const password = container.querySelector('#reg-password').value;
  const confirm = container.querySelector('#reg-confirm').value;

  errorEl.style.display = 'none';

  if (password !== confirm) {
    errorEl.textContent = t('auth.pw_mismatch');
    errorEl.style.display = 'block';
    return;
  }
  if (password.length < 6) {
    errorEl.textContent = t('auth.pw_min_len');
    errorEl.style.display = 'block';
    return;
  }

  button.disabled = true;
  button.textContent = t('common.loading');

  try {
    const response = await api.auth.register({ email, password, name });
    sessionStorage.setItem('qt-token', response.token);
    sessionStorage.setItem('qt-user', JSON.stringify(response.user));
    toast.success(t('auth.register_success'), response.user?.name || email);
    window.location.hash = '#/dashboard';
  } catch (error) {
    errorEl.textContent = error.message;
    errorEl.style.display = 'block';
    button.disabled = false;
    button.textContent = t('auth.sign_up');
  }
}
