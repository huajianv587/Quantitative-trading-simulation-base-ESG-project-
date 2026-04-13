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
  <div class="auth-split" style="justify-content:center">
    <div class="auth-form-panel" style="max-width:480px;margin:auto">
      <div class="auth-form-wrap">
        <!-- Lang toggle -->
        <div style="position:absolute;top:20px;right:24px;display:flex;gap:0" data-no-autotranslate="true" translate="no">
          <button class="lang-btn${lang==='zh'?' active':''}" data-lang="zh" data-no-autotranslate="true" translate="no">${zhLabel}</button>
          <button class="lang-btn${lang==='en'?' active':''}" data-lang="en" data-no-autotranslate="true" translate="no">EN</button>
        </div>

        <div style="font-size:28px;margin-bottom:12px">🔑</div>
        <div class="auth-form-title">${t('auth.reset_pw')}</div>
        <div class="auth-form-sub">${lang==='zh' ? '输入您的邮箱，我们将发送重置链接。' : "Enter your email and we'll send you a reset link."}</div>

        <!-- Step 1: Request reset -->
        <form id="reset-request-form" class="auth-form">
          <div class="auth-field">
            <label class="auth-label">${t('auth.email')}</label>
            <input class="auth-input" id="reset-email" type="email"
              placeholder="${t('auth.enter_email')}" required>
          </div>
          <div id="reset-error" class="auth-error" style="display:none"></div>
          <div id="reset-success" class="auth-success" style="display:none"></div>
          <button class="btn btn-primary auth-submit" type="submit" id="reset-btn">${t('auth.reset_send')}</button>
        </form>

        <!-- Step 2: Confirm token (shown in dev mode) -->
        <div id="reset-confirm-section" style="display:none;margin-top:20px">
          <div style="font-size:10px;color:var(--amber);font-family:var(--f-mono);margin-bottom:12px;padding:8px 12px;background:rgba(255,179,0,0.08);border-radius:6px;border:1px solid rgba(255,179,0,0.2)">
            ${lang==='zh' ? '开发模式：令牌已在响应中返回。生产环境中将通过邮件发送。' : 'DEV MODE: Token returned in response. In production, this would be emailed.'}
          </div>
          <form id="reset-confirm-form" class="auth-form">
            <div class="auth-field">
              <label class="auth-label">${lang==='zh' ? '重置令牌' : 'Reset Token'}</label>
              <input class="auth-input" id="reset-token" type="text" placeholder="${lang==='zh' ? '粘贴邮件中的令牌' : 'Paste token from email'}">
            </div>
            <div class="auth-field">
              <label class="auth-label">${lang==='zh' ? '新密码' : 'New Password'}</label>
              <input class="auth-input" id="new-password" type="password" placeholder="${lang==='zh' ? '新密码（至少6位）' : 'New password (min 6 chars)'}" minlength="6">
            </div>
            <div id="confirm-error" class="auth-error" style="display:none"></div>
            <button class="btn btn-primary auth-submit" type="submit" id="confirm-btn">${lang==='zh' ? '设置新密码' : 'Set New Password'}</button>
          </form>
        </div>

        <div style="margin-top:20px">
          <a href="#/login" class="auth-link">${t('auth.back_login')}</a>
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

  container.querySelector('#reset-request-form').addEventListener('submit', async e => {
    e.preventDefault();
    const lang  = getLang();
    const btn   = container.querySelector('#reset-btn');
    const errEl = container.querySelector('#reset-error');
    const sucEl = container.querySelector('#reset-success');
    const email = container.querySelector('#reset-email').value.trim();

    errEl.style.display = 'none'; sucEl.style.display = 'none';
    btn.disabled = true; btn.textContent = t('common.loading');

    try {
      const res = await api.auth.resetRequest({ email });
      sucEl.textContent = res.message || (lang==='zh' ? '请查收邮件中的重置链接。' : 'Check your email for the reset link.');
      sucEl.style.display = 'block';

      if (res._dev_token) {
        container.querySelector('#reset-token').value = res._dev_token;
        container.querySelector('#reset-confirm-section').style.display = 'block';
      }
    } catch(err) {
      errEl.textContent = err.message;
      errEl.style.display = 'block';
    } finally {
      btn.disabled = false; btn.textContent = t('auth.reset_send');
    }
  });

  container.querySelector('#reset-confirm-form').addEventListener('submit', async e => {
    e.preventDefault();
    const lang  = getLang();
    const btn   = container.querySelector('#confirm-btn');
    const errEl = container.querySelector('#confirm-error');
    const token = container.querySelector('#reset-token').value.trim();
    const pw    = container.querySelector('#new-password').value;

    errEl.style.display = 'none';
    btn.disabled = true; btn.textContent = t('common.loading');

    try {
      const res = await api.auth.resetConfirm({ token, new_password: pw });
      toast.success(lang==='zh' ? '密码重置成功' : 'Password reset', res.message);
      setTimeout(() => { window.location.hash = '#/login'; }, 1500);
    } catch(err) {
      errEl.textContent = err.message;
      errEl.style.display = 'block';
      btn.disabled = false;
      btn.textContent = lang==='zh' ? '设置新密码' : 'Set New Password';
    }
  });
}
