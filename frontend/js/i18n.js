/* ── i18n: Chinese / English toggle ──────────────────────────────
   Usage:
     import { t, setLang, getLang, onLangChange } from './i18n.js?v=8';
     t('dashboard.title')   → "Dashboard" or "控制台"
     setLang('zh')          → switch to Chinese, fires 'lang-change' event
──────────────────────────────────────────────────────────────── */

const STRINGS = {
  en: {
    // Nav groups
    'nav.platform': 'PLATFORM',
    'nav.quant':    'QUANT ENGINE',
    'nav.research': 'RESEARCH',
    'nav.ops':      'OPERATIONS',

    // Pages
    'page.dashboard':   'Dashboard',
    'page.research':    'Research',
    'page.portfolio':   'Portfolio',
    'page.backtest':    'Backtest',
    'page.execution':   'Execution',
    'page.validation':  'Validation',
    'page.models':      'Models',
    'page.chat':        'Research Chat',
    'page.score':       'ESG Score',
    'page.reports':     'Reports',
    'page.data':        'Data Sync',
    'page.push':        'Push Rules',
    'page.subs':        'Subscriptions',

    // Dashboard
    'dashboard.title':   'Platform Dashboard',
    'dashboard.sub':     'Live signals · Market regime · Portfolio status',
    'dashboard.signals': 'Active Signals',
    'dashboard.run':     'Run Research Pipeline',
    'dashboard.execute': 'Execute Plan ›',
    'dashboard.kline':   'WATCHLIST · K-LINE ANALYSIS',
    'dashboard.signal_summary': 'SIGNAL SUMMARY',
    'dashboard.indicators':     'TECHNICAL INDICATORS',
    'dashboard.ai_analysis':    'AI ANALYSIS',
    'dashboard.full_research':  'FULL RESEARCH →',
    'dashboard.arch_layers':    'Architecture Layers',
    'dashboard.runtime':        'Runtime Config',
    'dashboard.positions':      'Live Positions',
    'dashboard.no_signals':     'No signals yet',
    'dashboard.no_positions':   'No open positions',

    // Auth — form labels
    'auth.login':           'Sign In',
    'auth.register':        'Create Account',
    'auth.email':           'Email Address',
    'auth.password':        'Password',
    'auth.name':            'Full Name',
    'auth.confirm_pw':      'Confirm Password',
    'auth.forgot_pw':       'Forgot password?',
    'auth.no_account':      "Don't have an account?",
    'auth.have_account':    'Already have an account?',
    'auth.sign_up':         'Sign Up',
    'auth.sign_in':         'Sign In',
    'auth.reset_pw':        'Reset Password',
    'auth.reset_send':      'Send Reset Email',
    'auth.back_login':      '← Back to Login',
    'auth.remember':        'Remember me',
    'auth.logout':          'Log Out',
    'auth.welcome':         'Welcome back',
    'auth.register_success':'Account created',
    'auth.enter_email':     'Enter your email',
    'auth.enter_password':  'Enter your password',
    'auth.enter_name':      'Your full name',
    'auth.or':              'or',
    // Auth — visual panel copy
    'auth.headline_login':  'ESG Alpha\nIntelligence',
    'auth.tagline_login':   'Bloomberg-grade quantitative research\npowered by ESG factor models & AI.',
    'auth.sub_login':       'Sign In · Quant Terminal',
    'auth.demo_title':      'DEMO ACCESS',
    'auth.demo_text':       'Register any email to create an account instantly. No verification required.',
    'auth.stat_sharpe':     'Sharpe Ratio',
    'auth.stat_signals':    'Live Signals',
    'auth.stat_universe':   'Universe',
    'auth.headline_register': 'Join the\nAlpha Network',
    'auth.tagline_register':  'Access professional ESG quantitative tools\ntrusted by analysts and portfolio managers.',
    'auth.sub_register':    'Quant Terminal · ESG Alpha Platform',
    'auth.terms':           'By creating an account you agree to the <a class="auth-link" href="#">Terms of Service</a>. No email verification required.',
    'auth.stat_companies':  'Companies',
    'auth.stat_esg':        'ESG Factors',
    'auth.stat_market':     'Market Data',
    'auth.showcase_sharpe_key': 'Avg Sharpe Ratio',
    'auth.showcase_sharpe_sub': 'ESG Multi-Factor Strategy',
    'auth.showcase_alpha_key':  'ESG Alpha Premium',
    'auth.showcase_alpha_sub':  'vs Benchmark YTD',
    'auth.benefit1':        'Professional K-line & ESG factor analysis',
    'auth.benefit2':        'AI-powered research chat assistant',
    'auth.benefit3':        'Real-time signals & backtesting engine',
    // Auth — password strength
    'auth.pw_too_short':    'Too short',
    'auth.pw_weak':         'Weak',
    'auth.pw_fair':         'Fair',
    'auth.pw_good':         'Good',
    'auth.pw_strong':       'Strong',
    // Auth — errors
    'auth.pw_mismatch':     'Passwords do not match',
    'auth.pw_min_len':      'Password must be at least 6 characters',

    // Common
    'common.loading':  'Loading…',
    'common.error':    'Error',
    'common.retry':    'Retry',
    'common.save':     'Save',
    'common.cancel':   'Cancel',
    'common.confirm':  'Confirm',
    'common.run':      'Run',
    'common.generate': 'Generate',
    'common.export':   'Export',
    'common.refresh':  'Refresh',
    'common.search':   'Search',
    'common.filter':   'Filter',
    'common.close':    'Close',
    'common.back':     'Back',
    'common.next':     'Next',
    'common.submit':   'Submit',
    'common.online':   'Online',
    'common.offline':  'Offline',
    'common.backend_offline': 'Backend Offline',
    'common.backend_online':  'Backend Connected',
    'common.no_data':  'No data available',
    'common.market_open':   'MARKET OPEN',
    'common.market_closed': 'MARKET CLOSED',
  },

  zh: {
    // Nav groups
    'nav.platform': '平台',
    'nav.quant':    '量化引擎',
    'nav.research': '研究工具',
    'nav.ops':      '运营管理',

    // Pages
    'page.dashboard':   '控制台',
    'page.research':    '研究',
    'page.portfolio':   '投资组合',
    'page.backtest':    '回测',
    'page.execution':   '执行',
    'page.validation':  '策略验证',
    'page.models':      '模型仓库',
    'page.chat':        '研究对话',
    'page.score':       'ESG 评分',
    'page.reports':     '报告中心',
    'page.data':        '数据同步',
    'page.push':        '推送规则',
    'page.subs':        '订阅管理',

    // Dashboard
    'dashboard.title':   '平台控制台',
    'dashboard.sub':     '实时信号 · 市场状态 · 组合总览',
    'dashboard.signals': '活跃信号',
    'dashboard.run':     '运行研究管线',
    'dashboard.execute': '执行计划 ›',
    'dashboard.kline':   '自选股 · K线分析',
    'dashboard.signal_summary': '信号摘要',
    'dashboard.indicators':     '技术指标',
    'dashboard.ai_analysis':    'AI 分析',
    'dashboard.full_research':  '完整研究 →',
    'dashboard.arch_layers':    '系统架构层',
    'dashboard.runtime':        '运行时配置',
    'dashboard.positions':      '实时持仓',
    'dashboard.no_signals':     '暂无信号',
    'dashboard.no_positions':   '暂无持仓',

    // Auth — form labels
    'auth.login':           '登录',
    'auth.register':        '注册账户',
    'auth.email':           '邮箱地址',
    'auth.password':        '密码',
    'auth.name':            '姓名',
    'auth.confirm_pw':      '确认密码',
    'auth.forgot_pw':       '忘记密码？',
    'auth.no_account':      '没有账户？',
    'auth.have_account':    '已有账户？',
    'auth.sign_up':         '注册',
    'auth.sign_in':         '登录',
    'auth.reset_pw':        '重置密码',
    'auth.reset_send':      '发送重置邮件',
    'auth.back_login':      '← 返回登录',
    'auth.remember':        '记住我',
    'auth.logout':          '退出登录',
    'auth.welcome':         '欢迎回来',
    'auth.register_success':'账户创建成功',
    'auth.enter_email':     '请输入邮箱',
    'auth.enter_password':  '请输入密码',
    'auth.enter_name':      '请输入姓名',
    'auth.or':              '或',
    // Auth — visual panel copy
    'auth.headline_login':  'ESG Alpha\n智能平台',
    'auth.tagline_login':   '彭博级量化研究\n基于 ESG 因子模型与 AI 驱动。',
    'auth.sub_login':       '登录 · Quant Terminal',
    'auth.demo_title':      '演示通道',
    'auth.demo_text':       '注册任意邮箱即可立即创建账户，无需验证。',
    'auth.stat_sharpe':     '夏普比率',
    'auth.stat_signals':    '实时信号',
    'auth.stat_universe':   '股票池',
    'auth.headline_register': '加入\nAlpha 网络',
    'auth.tagline_register':  '使用专业 ESG 量化工具\n深受分析师和基金经理信赖。',
    'auth.sub_register':    'Quant Terminal · ESG Alpha 平台',
    'auth.terms':           '创建账户即表示您同意 <a class="auth-link" href="#">服务条款</a>。无需邮箱验证。',
    'auth.stat_companies':  '覆盖企业',
    'auth.stat_esg':        'ESG 因子',
    'auth.stat_market':     '实时行情',
    'auth.showcase_sharpe_key': '平均夏普比率',
    'auth.showcase_sharpe_sub': 'ESG 多因子策略',
    'auth.showcase_alpha_key':  'ESG Alpha 超额',
    'auth.showcase_alpha_sub':  'vs 基准 年初至今',
    'auth.benefit1':        '专业 K 线与 ESG 因子分析',
    'auth.benefit2':        'AI 驱动的研究对话助手',
    'auth.benefit3':        '实时信号与回测引擎',
    // Auth — password strength
    'auth.pw_too_short':    '太短',
    'auth.pw_weak':         '弱',
    'auth.pw_fair':         '一般',
    'auth.pw_good':         '良好',
    'auth.pw_strong':       '强',
    // Auth — errors
    'auth.pw_mismatch':     '两次密码不一致',
    'auth.pw_min_len':      '密码至少需要 6 位字符',

    // Common
    'common.loading':  '加载中…',
    'common.error':    '错误',
    'common.retry':    '重试',
    'common.save':     '保存',
    'common.cancel':   '取消',
    'common.confirm':  '确认',
    'common.run':      '运行',
    'common.generate': '生成',
    'common.export':   '导出',
    'common.refresh':  '刷新',
    'common.search':   '搜索',
    'common.filter':   '筛选',
    'common.close':    '关闭',
    'common.back':     '返回',
    'common.next':     '下一步',
    'common.submit':   '提交',
    'common.online':   '在线',
    'common.offline':  '离线',
    'common.backend_offline': '后端离线',
    'common.backend_online':  '后端已连接',
    'common.no_data':  '暂无数据',
    'common.market_open':   '市场开盘',
    'common.market_closed': '市场休市',
  },
};

let _lang = localStorage.getItem('qt-lang') || 'zh';

export function getLang() { return _lang; }

export function setLang(lang) {
  if (lang !== 'zh' && lang !== 'en') return;
  _lang = lang;
  localStorage.setItem('qt-lang', lang);
  document.documentElement.setAttribute('lang', lang);
  window.dispatchEvent(new CustomEvent('lang-change', { detail: { lang } }));
  applyLangToPage();
}

export function t(key) {
  // Strict: return only the current lang value — no cross-lang fallback
  return (STRINGS[_lang] && STRINGS[_lang][key]) || key;
}

export function onLangChange(fn) {
  window.addEventListener('lang-change', e => fn(e.detail.lang));
}

/** Apply [data-i18n] attributes across the document */
export function applyLangToPage() {
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.getAttribute('data-i18n');
    if (key) el.textContent = t(key);
  });
  document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
    const key = el.getAttribute('data-i18n-placeholder');
    if (key) el.setAttribute('placeholder', t(key));
  });
}

// Apply on load
applyLangToPage();
