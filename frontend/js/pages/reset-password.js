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
  const subtitle = lang === 'zh'
    ? '输入邮箱，我们会发送重置链接。'
    : "Enter your email and we'll send you a reset link.";
  const devModeText = lang === 'zh'
    ? '开发模式：令牌会在响应中返回。生产环境中将通过邮件发送。'
    : 'DEV MODE: Token returned in response. In production, this would be emailed.';
  const tokenLabel = lang === 'zh' ? '重置令牌' : 'Reset Token';
  const tokenPlaceholder = lang === 'zh' ? '粘贴邮件中的令牌' : 'Paste token from email';
  const newPasswordLabel = lang === 'zh' ? '新密码' : 'New Password';
  const newPasswordPlaceholder = lang === 'zh' ? '新密码（至少 6 位）' : 'New password (min 6 chars)';
  const setPasswordLabel = lang === 'zh' ? '设置新密码' : 'Set New Password';
  return `
  <div class="auth-split" style="justify-content:center">
    <div class="auth-form-panel" style="max-width:480px;margin:auto">
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

        <div style="font-size:24px;margin-bottom:12px">Reset</div>
        <div class="auth-form-title">${t('auth.reset_pw')}</div>
        <div class="auth-form-sub">${subtitle}</div>

        <form id="reset-request-form" class="auth-form">
          <div class="auth-field">
            <label class="auth-label">${t('auth.email')}</label>
            <input class="auth-input" id="reset-email" type="email" placeholder="${t('auth.enter_email')}" required>
          </div>
          <div id="reset-error" class="auth-error" style="display:none"></div>
          <div id="reset-success" class="auth-success" style="display:none"></div>
          <button class="btn btn-primary auth-submit" type="submit" id="reset-btn">${t('auth.reset_send')}</button>
        </form>

        <div id="reset-confirm-section" style="display:none;margin-top:20px">
          <div style="font-size:10px;color:var(--amber);font-family:var(--f-mono);margin-bottom:12px;padding:8px 12px;background:rgba(255,179,0,0.08);border-radius:6px;border:1px solid rgba(255,179,0,0.2)">
            ${devModeText}
          </div>
          <form id="reset-confirm-form" class="auth-form">
            <div class="auth-field">
              <label class="auth-label">${tokenLabel}</label>
              <input class="auth-input" id="reset-token" type="text" placeholder="${tokenPlaceholder}">
            </div>
            <div class="auth-field">
              <label class="auth-label">${newPasswordLabel}</label>
              <input class="auth-input" id="new-password" type="password" placeholder="${newPasswordPlaceholder}" minlength="6">
            </div>
            <div id="confirm-error" class="auth-error" style="display:none"></div>
            <button class="btn btn-primary auth-submit" type="submit" id="confirm-btn">${setPasswordLabel}</button>
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
  container.querySelectorAll('.lang-btn').forEach((button) => {
    button.addEventListener('click', () => {
      import('../i18n.js?v=8').then((module) => module.setLang(button.dataset.lang));
    });
  });

  container.querySelector('#reset-request-form')?.addEventListener('submit', async (event) => {
    event.preventDefault();
    const lang = getLang();
    const button = container.querySelector('#reset-btn');
    const errorEl = container.querySelector('#reset-error');
    const successEl = container.querySelector('#reset-success');
    const email = container.querySelector('#reset-email').value.trim();

    errorEl.style.display = 'none';
    successEl.style.display = 'none';
    button.disabled = true;
    button.textContent = t('common.loading');

    try {
      const response = await api.auth.resetRequest({ email });
      successEl.textContent = response.message || (lang === 'zh' ? '请查收邮件中的重置链接。' : 'Check your email for the reset link.');
      successEl.style.display = 'block';
      if (response._dev_token) {
        container.querySelector('#reset-token').value = response._dev_token;
        container.querySelector('#reset-confirm-section').style.display = 'block';
      }
    } catch (error) {
      errorEl.textContent = error.message;
      errorEl.style.display = 'block';
    } finally {
      button.disabled = false;
      button.textContent = t('auth.reset_send');
    }
  });

  container.querySelector('#reset-confirm-form')?.addEventListener('submit', async (event) => {
    event.preventDefault();
    const lang = getLang();
    const button = container.querySelector('#confirm-btn');
    const errorEl = container.querySelector('#confirm-error');
    const token = container.querySelector('#reset-token').value.trim();
    const newPassword = container.querySelector('#new-password').value;

    errorEl.style.display = 'none';
    button.disabled = true;
    button.textContent = t('common.loading');

    try {
      const response = await api.auth.resetConfirm({ token, new_password: newPassword });
      toast.success(lang === 'zh' ? '密码重置成功' : 'Password reset', response.message);
      setTimeout(() => {
        window.location.hash = '#/login';
      }, 1500);
    } catch (error) {
      errorEl.textContent = error.message;
      errorEl.style.display = 'block';
      button.disabled = false;
      button.textContent = lang === 'zh' ? '设置新密码' : 'Set New Password';
    }
  });
}
