const STORAGE_KEY = 'qt-lang';

const STRINGS = {
  en: {
    'app.logo_tag': 'ALPHA ENGINE · LIVE',
    'nav.platform': 'PLATFORM',
    'nav.quant': 'QUANT ENGINE',
    'nav.research': 'RESEARCH',
    'nav.ops': 'OPERATIONS',
    'page.login': 'Sign In',
    'page.register_auth': 'Register',
    'page.reset_pw': 'Reset Password',
    'page.dashboard': 'Dashboard',
    'page.research': 'Research',
    'page.intelligence': 'Decision Cockpit',
    'page.factor_lab': 'Factor Lab',
    'page.simulation': 'Simulation',
    'page.portfolio': 'Portfolio',
    'page.backtest': 'Backtest',
    'page.execution': 'Execution',
    'page.validation': 'Validation',
    'page.models': 'Models',
    'page.rl_lab': 'RL Lab',
    'page.chat': 'Research Chat',
    'page.score': 'ESG Score',
    'page.reports': 'Reports',
    'page.data': 'Data Sync',
    'page.push': 'Push Rules',
    'page.subs': 'Subscriptions',
    'auth.login': 'Sign In',
    'auth.register': 'Create Account',
    'auth.email': 'Email Address',
    'auth.password': 'Password',
    'auth.name': 'Full Name',
    'auth.confirm_pw': 'Confirm Password',
    'auth.forgot_pw': 'Forgot password?',
    'auth.no_account': "Don't have an account?",
    'auth.have_account': 'Already have an account?',
    'auth.sign_up': 'Sign Up',
    'auth.sign_in': 'Sign In',
    'auth.reset_pw': 'Reset Password',
    'auth.reset_send': 'Send Reset Email',
    'auth.back_login': '<- Back to Login',
    'auth.remember': 'Remember me',
    'auth.logout': 'Log Out',
    'auth.welcome': 'Welcome back',
    'auth.register_success': 'Account created',
    'auth.enter_email': 'Enter your email',
    'auth.enter_password': 'Enter your password',
    'auth.enter_name': 'Your full name',
    'auth.or': 'or',
    'auth.headline_login': 'ESG Alpha\nIntelligence',
    'auth.tagline_login': 'Bloomberg-grade quantitative research\npowered by ESG factor models and AI.',
    'auth.sub_login': 'Sign In · Quant Terminal',
    'auth.demo_title': 'DEMO ACCESS',
    'auth.demo_text': 'Register any email to create an account instantly. No verification required.',
    'auth.stat_sharpe': 'Sharpe Ratio',
    'auth.stat_signals': 'Live Signals',
    'auth.stat_universe': 'Universe',
    'auth.headline_register': 'Join the\nAlpha Network',
    'auth.tagline_register': 'Access professional ESG quantitative tools\ntrusted by analysts and portfolio managers.',
    'auth.sub_register': 'Quant Terminal · ESG Alpha Platform',
    'auth.terms': 'By creating an account you agree to the <a class="auth-link" href="#">Terms of Service</a>. No email verification required.',
    'auth.stat_companies': 'Companies',
    'auth.stat_esg': 'ESG Factors',
    'auth.stat_market': 'Market Data',
    'auth.showcase_sharpe_key': 'Avg Sharpe Ratio',
    'auth.showcase_sharpe_sub': 'ESG Multi-Factor Strategy',
    'auth.showcase_alpha_key': 'ESG Alpha Premium',
    'auth.showcase_alpha_sub': 'vs Benchmark YTD',
    'auth.benefit1': 'Professional K-line and ESG factor analysis',
    'auth.benefit2': 'AI-powered research chat assistant',
    'auth.benefit3': 'Real-time signals and backtesting engine',
    'auth.pw_too_short': 'Too short',
    'auth.pw_weak': 'Weak',
    'auth.pw_fair': 'Fair',
    'auth.pw_good': 'Good',
    'auth.pw_strong': 'Strong',
    'auth.pw_mismatch': 'Passwords do not match',
    'auth.pw_min_len': 'Password must be at least 6 characters',
    'common.loading': 'Loading…',
    'common.error': 'Error',
    'common.retry': 'Retry',
    'common.save': 'Save',
    'common.cancel': 'Cancel',
    'common.confirm': 'Confirm',
    'common.run': 'Run',
    'common.generate': 'Generate',
    'common.export': 'Export',
    'common.refresh': 'Refresh',
    'common.search': 'Search',
    'common.filter': 'Filter',
    'common.close': 'Close',
    'common.back': 'Back',
    'common.next': 'Next',
    'common.submit': 'Submit',
    'common.online': 'Online',
    'common.offline': 'Offline',
    'common.connecting': 'Connecting…',
    'common.backend_offline': 'Backend Offline',
    'common.backend_online': 'Backend Connected',
    'common.features_limited': 'Some features may be unavailable',
    'common.no_data': 'No data available',
    'common.market_open': 'MARKET OPEN',
    'common.market_closed': 'MARKET CLOSED',
  },
  zh: {
    'app.logo_tag': '量化引擎 · 在线',
    'nav.platform': '平台',
    'nav.quant': '量化引擎',
    'nav.research': '研究工具',
    'nav.ops': '运营管理',
    'page.login': '登录',
    'page.register_auth': '注册',
    'page.reset_pw': '重置密码',
    'page.dashboard': '控制台',
    'page.research': '研究',
    'page.intelligence': '智能决策',
    'page.factor_lab': '因子实验室',
    'page.simulation': '情景模拟',
    'page.portfolio': '投资组合',
    'page.backtest': '回测',
    'page.execution': '执行',
    'page.validation': '策略验证',
    'page.models': '模型仓库',
    'page.rl_lab': 'RL Lab',
    'page.chat': '研究对话',
    'page.score': 'ESG 评分',
    'page.reports': '报告中心',
    'page.data': '数据同步',
    'page.push': '推送规则',
    'page.subs': '订阅管理',
    'auth.login': '登录',
    'auth.register': '注册账户',
    'auth.email': '邮箱地址',
    'auth.password': '密码',
    'auth.name': '姓名',
    'auth.confirm_pw': '确认密码',
    'auth.forgot_pw': '忘记密码？',
    'auth.no_account': '没有账户？',
    'auth.have_account': '已有账户？',
    'auth.sign_up': '注册',
    'auth.sign_in': '登录',
    'auth.reset_pw': '重置密码',
    'auth.reset_send': '发送重置邮件',
    'auth.back_login': '<- 返回登录',
    'auth.remember': '记住我',
    'auth.logout': '退出登录',
    'auth.welcome': '欢迎回来',
    'auth.register_success': '账户创建成功',
    'auth.enter_email': '请输入邮箱',
    'auth.enter_password': '请输入密码',
    'auth.enter_name': '请输入姓名',
    'auth.or': '或',
    'auth.headline_login': 'ESG Alpha\n智能平台',
    'auth.tagline_login': '彭博级量化研究\n由 ESG 因子模型与 AI 驱动。',
    'auth.sub_login': '登录 · Quant Terminal',
    'auth.demo_title': '演示通道',
    'auth.demo_text': '注册任意邮箱即可即时创建账户，无需邮箱验证。',
    'auth.stat_sharpe': '夏普比率',
    'auth.stat_signals': '实时信号',
    'auth.stat_universe': '股票池',
    'auth.headline_register': '加入\nAlpha 网络',
    'auth.tagline_register': '使用专业 ESG 量化工具\n服务分析师与基金经理。',
    'auth.sub_register': 'Quant Terminal · ESG Alpha 平台',
    'auth.terms': '创建账户即表示您同意 <a class="auth-link" href="#">服务条款</a>。无需邮箱验证。',
    'auth.stat_companies': '覆盖企业',
    'auth.stat_esg': 'ESG 因子',
    'auth.stat_market': '市场数据',
    'auth.showcase_sharpe_key': '平均夏普比率',
    'auth.showcase_sharpe_sub': 'ESG 多因子策略',
    'auth.showcase_alpha_key': 'ESG Alpha 超额',
    'auth.showcase_alpha_sub': '相对基准年初至今',
    'auth.benefit1': '专业 K 线与 ESG 因子分析',
    'auth.benefit2': 'AI 驱动的研究助手',
    'auth.benefit3': '实时信号与回测引擎',
    'auth.pw_too_short': '太短',
    'auth.pw_weak': '弱',
    'auth.pw_fair': '一般',
    'auth.pw_good': '良好',
    'auth.pw_strong': '强',
    'auth.pw_mismatch': '两次密码不一致',
    'auth.pw_min_len': '密码至少需要 6 位字符',
    'common.loading': '加载中…',
    'common.error': '错误',
    'common.retry': '重试',
    'common.save': '保存',
    'common.cancel': '取消',
    'common.confirm': '确认',
    'common.run': '运行',
    'common.generate': '生成',
    'common.export': '导出',
    'common.refresh': '刷新',
    'common.search': '搜索',
    'common.filter': '筛选',
    'common.close': '关闭',
    'common.back': '返回',
    'common.next': '下一步',
    'common.submit': '提交',
    'common.online': '在线',
    'common.offline': '离线',
    'common.connecting': '连接中…',
    'common.backend_offline': '后端离线',
    'common.backend_online': '后端已连接',
    'common.features_limited': '部分功能可能暂时不可用',
    'common.no_data': '暂无数据',
    'common.market_open': '市场开盘',
    'common.market_closed': '市场休市',
  },
};

const AUTO_TEXT_ZH = {
  'Quant Terminal': 'Quant Terminal',
  'Dashboard': '控制台',
  'Research': '研究',
  'Portfolio': '投资组合',
  'Backtest': '回测',
  'Execution': '执行',
  'Validation': '策略验证',
  'Models': '模型仓库',
  'RL Lab': 'RL Lab',
  'Research Chat': '研究对话',
  'ESG Score': 'ESG 评分',
  'Reports': '报告中心',
  'Data Sync': '数据同步',
  'Push Rules': '推送规则',
  'Subscriptions': '订阅管理',
  'Overview': '总览',
  'Online': '在线',
  'Offline': '离线',
  'Loading…': '加载中…',
  'Connecting…': '连接中…',
  'Error': '错误',
  'Retry': '重试',
  'Save': '保存',
  'Cancel': '取消',
  'Confirm': '确认',
  'Refresh': '刷新',
  'Search': '搜索',
  'Filter': '筛选',
  'Close': '关闭',
  'Back': '返回',
  'Next': '下一步',
  'Submit': '提交',
  'Run': '运行',
  'Generate': '生成',
  'Export': '导出',
  'Sync': '同步',
  'Sync triggered': '已触发同步',
  'Sync complete': '同步完成',
  'Data sources refreshed': '数据源已刷新',
  'Log cleared.': '日志已清空。',
  'Start Sync': '开始同步',
  'Starting…': '启动中…',
  'Portfolio Optimizer': '投资组合优化器',
  'Clear Portfolio': '清空组合',
  'Not built yet': '尚未生成',
  'No data available': '暂无数据',
  'Search best params': '搜索最佳参数',
  'Train Policy': '训练策略',
  'Backtest Latest': '回测最新结果',
};

const AUTO_PLACEHOLDER_ZH = {
  'Search by symbol...': '按股票代码搜索…',
  'AAPL, MSFT, NVDA...': 'AAPL、MSFT、NVDA…',
  'AAPL, MSFT… (blank = use preset)': 'AAPL、MSFT…（留空则使用预设）',
  'Enter your email': '请输入邮箱',
  'Enter your password': '请输入密码',
  'Your full name': '请输入姓名',
};

const AUTO_TEXT_EN = Object.fromEntries(Object.entries(AUTO_TEXT_ZH).map(([en, zh]) => [zh, en]));
const AUTO_PLACEHOLDER_EN = Object.fromEntries(Object.entries(AUTO_PLACEHOLDER_ZH).map(([en, zh]) => [zh, en]));

let _lang = typeof localStorage !== 'undefined' ? (localStorage.getItem(STORAGE_KEY) || 'zh') : 'zh';
let _observer = null;
let _applying = false;

if (_lang !== 'zh' && _lang !== 'en') {
  _lang = 'zh';
}

function syncDocumentLang() {
  if (typeof document !== 'undefined') {
    document.documentElement.setAttribute('lang', _lang);
  }
}

syncDocumentLang();

export function getLang() {
  return _lang;
}

export function getLocale() {
  return _lang === 'zh' ? 'zh-CN' : 'en-US';
}

export function isZh() {
  return _lang === 'zh';
}

export function setLang(lang) {
  if (lang !== 'zh' && lang !== 'en') return;
  _lang = lang;
  if (typeof localStorage !== 'undefined') {
    localStorage.setItem(STORAGE_KEY, lang);
  }
  syncDocumentLang();
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent('lang-change', { detail: { lang } }));
  }
  applyLangToPage();
}

export function t(key) {
  return STRINGS[_lang]?.[key] ?? STRINGS.en[key] ?? key;
}

export function onLangChange(fn) {
  const handler = (event) => fn(event.detail.lang);
  window.addEventListener('lang-change', handler);
  return () => window.removeEventListener('lang-change', handler);
}

function normalizeLooseText(value) {
  return typeof value === 'string' ? value.trim() : '';
}

function preserveOuterWhitespace(source, replacement) {
  if (typeof source !== 'string' || typeof replacement !== 'string') {
    return replacement;
  }
  const leading = source.match(/^\s*/)?.[0] || '';
  const trailing = source.match(/\s*$/)?.[0] || '';
  return `${leading}${replacement}${trailing}`;
}

export function translateLoose(source, kind = 'text') {
  if (typeof source !== 'string') return source;
  const trimmed = normalizeLooseText(source);
  if (!trimmed) return source;

  const directMap = kind === 'placeholder' ? AUTO_PLACEHOLDER_ZH : AUTO_TEXT_ZH;
  const reverseMap = kind === 'placeholder' ? AUTO_PLACEHOLDER_EN : AUTO_TEXT_EN;
  const translated = _lang === 'zh' ? directMap[trimmed] : reverseMap[trimmed];
  return translated ? preserveOuterWhitespace(source, translated) : source;
}

function applyStaticTranslations(root = document) {
  root.querySelectorAll?.('[data-i18n]').forEach((el) => {
    const key = el.getAttribute('data-i18n');
    if (key) el.textContent = t(key);
  });

  root.querySelectorAll?.('[data-i18n-placeholder]').forEach((el) => {
    const key = el.getAttribute('data-i18n-placeholder');
    if (key) el.setAttribute('placeholder', t(key));
  });

  root.querySelectorAll?.('[data-i18n-title]').forEach((el) => {
    const key = el.getAttribute('data-i18n-title');
    if (key) el.setAttribute('title', t(key));
  });
}

function shouldSkipTextNode(node) {
  const parent = node?.parentElement;
  if (!parent) return true;
  if (parent.closest('[data-i18n]')) return true;
  if (parent.closest('[data-no-autotranslate="true"]')) return true;
  return ['SCRIPT', 'STYLE', 'TEXTAREA'].includes(parent.tagName);
}

function autoTranslate(root = document) {
  if (typeof document === 'undefined' || !root) return;

  const target = root.nodeType === Node.TEXT_NODE ? root.parentNode : root;
  if (!target) return;

  const walker = document.createTreeWalker(target, NodeFilter.SHOW_TEXT);
  let textNode = root.nodeType === Node.TEXT_NODE ? root : walker.nextNode();

  while (textNode) {
    if (!shouldSkipTextNode(textNode)) {
      const current = textNode.textContent;
      const translated = translateLoose(current, 'text');
      if (translated !== current) {
        textNode.textContent = translated;
      }
    }
    textNode = walker.nextNode();
  }

  const elements = target.querySelectorAll ? [target, ...target.querySelectorAll('*')] : [];
  elements.forEach((el) => {
    if (!(el instanceof Element) || el.closest('[data-no-autotranslate="true"]')) return;

    if (el.hasAttribute('placeholder') && !el.hasAttribute('data-i18n-placeholder')) {
      const translated = translateLoose(el.getAttribute('placeholder'), 'placeholder');
      if (translated) el.setAttribute('placeholder', translated);
    }

    if (el.hasAttribute('title') && !el.hasAttribute('data-i18n-title')) {
      const translated = translateLoose(el.getAttribute('title'), 'text');
      if (translated) el.setAttribute('title', translated);
    }

    if (el.tagName === 'INPUT') {
      const type = (el.getAttribute('type') || '').toLowerCase();
      if (['button', 'submit', 'reset'].includes(type) && el.hasAttribute('value')) {
        const translated = translateLoose(el.getAttribute('value'), 'text');
        if (translated) el.setAttribute('value', translated);
      }
    }
  });
}

export function applyLangToPage(root = document) {
  if (typeof document === 'undefined' || !root) return;
  _applying = true;
  try {
    applyStaticTranslations(root);
    autoTranslate(root);
  } finally {
    _applying = false;
  }
}

function ensureObserver() {
  if (typeof MutationObserver === 'undefined' || typeof document === 'undefined' || _observer) return;

  _observer = new MutationObserver((mutations) => {
    if (_applying) return;
    for (const mutation of mutations) {
      if (mutation.type === 'childList') {
        mutation.addedNodes.forEach((node) => {
          if (node.nodeType === Node.TEXT_NODE || node.nodeType === Node.ELEMENT_NODE) {
            applyLangToPage(node);
          }
        });
      }
      if (mutation.type === 'characterData' && mutation.target) {
        applyLangToPage(mutation.target);
      }
    }
  });

  _observer.observe(document.body || document.documentElement, {
    childList: true,
    characterData: true,
    subtree: true,
  });
}

if (typeof document !== 'undefined') {
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      applyLangToPage();
      ensureObserver();
    }, { once: true });
  } else {
    applyLangToPage();
    ensureObserver();
  }
}
