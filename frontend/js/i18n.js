const STORAGE_KEY = 'qt-lang';

const STRINGS = {
  en: {
    'app.logo_tag': 'ALPHA ENGINE · LIVE',
    'nav.platform': 'PLATFORM',
    'nav.quant': 'QUANT ENGINE',
    'nav.research': 'RESEARCH TOOLS',
    'nav.ops': 'OPERATIONS',
    'nav.market_intel': 'MARKET INTELLIGENCE',
    'nav.market_intel_summary': 'Research and live information flow',
    'nav.decision_hub': 'DECISION HUB',
    'nav.decision_hub_summary': 'Debate, factor, and risk gates',
    'nav.trading_exec': 'TRADING EXECUTION',
    'nav.trading_exec_summary': 'Paper submit and monitoring',
    'nav.governance': 'GOVERNANCE & REVIEW',
    'nav.governance_summary': 'Audit, outcomes, and model review',
    'nav.system_admin': 'SYSTEM ADMIN',
    'nav.system_admin_summary': 'Rules, access, and settings',
    'nav.status.live': 'live',
    'nav.status.review': 'review',
    'nav.status.paper': 'paper',
    'nav.status.audit': 'audit',
    'nav.status.ops': 'ops',
    'page.login': 'Sign In',
    'page.register_auth': 'Register',
    'page.reset_pw': 'Reset Password',
    'page.dashboard': 'Dashboard',
    'page.research': 'Research',
    'page.intelligence': 'Decision Cockpit',
    'page.factor_lab': 'Factor Lab',
    'page.simulation': 'Simulation',
    'page.connector_center': 'Connector Center',
    'page.market_radar': 'Market Radar',
    'page.agent_lab': 'Agent Lab',
    'page.debate_desk': 'Debate Desk',
    'page.risk_board': 'Risk Board',
    'page.trading_ops': 'Trading Ops',
    'page.outcome_center': 'Outcome Center',
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
    'auth.back_login': 'Back to Login',
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
    'auth.headline_register': 'Join the\nAlpha Network',
    'auth.tagline_register': 'Access professional ESG quantitative tools\ntrusted by analysts and portfolio managers.',
    'auth.terms': 'By creating an account you agree to the Terms of Service.',
    'common.loading': 'Loading...',
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
    'common.connecting': 'Connecting...',
    'common.backend_offline': 'Backend Offline',
    'common.backend_online': 'Backend Connected',
    'common.features_limited': 'Some features may be unavailable',
    'common.no_data': 'No data available',
    'common.market_open': 'MARKET OPEN',
    'common.market_closed': 'MARKET CLOSED',
    'common.page_failed_load': 'Page failed to load',
    'common.page_failed_retry': 'Refresh this page and try again.',
  },
  zh: {
    'app.logo_tag': '量化引擎 · 在线',
    'nav.platform': '平台',
    'nav.quant': '量化引擎',
    'nav.research': '研究工具',
    'nav.ops': '运营管理',
    'nav.market_intel': '市场智能',
    'nav.market_intel_summary': '研究与实时信息流',
    'nav.decision_hub': '决策中枢',
    'nav.decision_hub_summary': '辩论、因子与风控门禁',
    'nav.trading_exec': '交易执行',
    'nav.trading_exec_summary': '纸面提交与监控',
    'nav.governance': '治理与复盘',
    'nav.governance_summary': '审计、结果与模型复核',
    'nav.system_admin': '系统管理',
    'nav.system_admin_summary': '规则、权限与设置',
    'nav.status.live': '在线',
    'nav.status.review': '复核',
    'nav.status.paper': '纸面',
    'nav.status.audit': '审计',
    'nav.status.ops': '运维',
    'page.login': '登录',
    'page.register_auth': '注册',
    'page.reset_pw': '重置密码',
    'page.dashboard': '控制台',
    'page.research': '研究',
    'page.intelligence': '决策驾驶舱',
    'page.factor_lab': '因子实验室',
    'page.simulation': '情景模拟',
    'page.connector_center': '数据源中心',
    'page.market_radar': '市场雷达',
    'page.agent_lab': '智能体实验室',
    'page.debate_desk': '辩论台',
    'page.risk_board': '风控板',
    'page.trading_ops': '交易运维',
    'page.outcome_center': '结果追踪',
    'page.portfolio': '投资组合',
    'page.backtest': '回测',
    'page.execution': '执行',
    'page.validation': '策略验证',
    'page.models': '模型库',
    'page.rl_lab': 'RL 实验室',
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
    'auth.no_account': '还没有账户？',
    'auth.have_account': '已经有账户？',
    'auth.sign_up': '注册',
    'auth.sign_in': '登录',
    'auth.reset_pw': '重置密码',
    'auth.reset_send': '发送重置邮件',
    'auth.back_login': '返回登录',
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
    'auth.headline_register': '加入\nAlpha 网络',
    'auth.tagline_register': '使用面向分析师与投资经理的\n专业 ESG 量化工具。',
    'auth.terms': '创建账户即表示您同意服务条款。',
    'common.loading': '正在加载...',
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
    'common.connecting': '连接中...',
    'common.backend_offline': '后端离线',
    'common.backend_online': '后端已连接',
    'common.features_limited': '部分功能可能暂时不可用',
    'common.no_data': '暂无数据',
    'common.market_open': '市场开市',
    'common.market_closed': '市场休市',
    'common.page_failed_load': '页面加载失败',
    'common.page_failed_retry': '请刷新页面后重试。',
  },
};

const AUTO_TEXT_ZH = {
  Dashboard: '控制台',
  Research: '研究',
  'Decision Cockpit': '决策驾驶舱',
  'Factor Lab': '因子实验室',
  Simulation: '情景模拟',
  'Connector Center': '数据源中心',
  'Market Radar': '市场雷达',
  'Agent Lab': '智能体实验室',
  'Debate Desk': '辩论台',
  'Risk Board': '风控板',
  'Trading Ops': '交易运维',
  'Outcome Center': '结果追踪',
  Portfolio: '投资组合',
  Backtest: '回测',
  Execution: '执行',
  Validation: '策略验证',
  Models: '模型库',
  'RL Lab': 'RL 实验室',
  'Research Chat': '研究对话',
  'ESG Score': 'ESG 评分',
  Reports: '报告中心',
  'Data Sync': '数据同步',
  'Push Rules': '推送规则',
  Subscriptions: '订阅管理',
  'Sign In': '登录',
  'Create Account': '注册账户',
  Online: '在线',
  Offline: '离线',
  'Backend Connected': '后端已连接',
  'Backend Offline': '后端离线',
  'Loading...': '正在加载...',
  'Connecting...': '连接中...',
  Error: '错误',
  Retry: '重试',
  Refresh: '刷新',
  'No data available': '暂无数据',
  'Page failed to load': '页面加载失败',
  'Refresh this page and try again.': '请刷新页面后重试。',
  'All providers': '全部来源',
  'All symbols': '全部股票',
  'No scan yet': '尚未扫描',
  'Loading evidence': '正在加载证据',
  'Loading evidence lake': '正在加载证据湖',
  'Scanning free-tier providers': '正在扫描免费数据源',
  'Loading trading ops': '正在加载交易运维',
  'Loading risk board': '正在加载风控板',
  'Evaluating risk gate': '正在评估风控门禁',
  'No approval yet': '暂无审批结果',
  'No risk approvals yet': '暂无风控审批记录',
  'No risk alerts today': '今日暂无风险告警',
};

const AUTO_PLACEHOLDER_ZH = {
  'optional decision id': '可选 decision id',
  'marketaux, local_esg': 'marketaux, local_esg',
  AAPL: 'AAPL',
};

function currentLang() {
  const raw = localStorage.getItem(STORAGE_KEY);
  return raw === 'zh' ? 'zh' : 'en';
}

function setDocumentLang(lang) {
  document.documentElement.lang = lang === 'zh' ? 'zh-CN' : 'en';
}

export function getLang() {
  return currentLang();
}

export function getLocale() {
  return currentLang() === 'zh' ? 'zh-CN' : 'en-US';
}

export function isZh() {
  return currentLang() === 'zh';
}

export function t(key) {
  const lang = currentLang();
  return STRINGS[lang]?.[key] || STRINGS.en[key] || key;
}

const listeners = new Set();

export function onLangChange(callback) {
  if (typeof callback !== 'function') return () => {};
  listeners.add(callback);
  return () => listeners.delete(callback);
}

export function setLang(lang) {
  const next = lang === 'zh' ? 'zh' : 'en';
  localStorage.setItem(STORAGE_KEY, next);
  setDocumentLang(next);
  listeners.forEach((listener) => {
    try {
      listener(next);
    } catch (error) {
      console.error('onLangChange listener failed', error);
    }
  });
}

function translateText(value) {
  if (!value || currentLang() !== 'zh') return value;
  return AUTO_TEXT_ZH[value.trim()] || value;
}

function translatePlaceholder(value) {
  if (!value || currentLang() !== 'zh') return value;
  return AUTO_PLACEHOLDER_ZH[value.trim()] || value;
}

export function translateLoose(value) {
  return translateText(value);
}

export function applyLangToPage(root = document) {
  setDocumentLang(currentLang());

  root.querySelectorAll('[data-i18n]').forEach((node) => {
    const key = node.getAttribute('data-i18n');
    if (key) node.textContent = t(key);
  });

  root.querySelectorAll('[data-i18n-placeholder]').forEach((node) => {
    const key = node.getAttribute('data-i18n-placeholder');
    if (key && 'placeholder' in node) node.placeholder = t(key);
  });

  if (currentLang() !== 'zh') return;

  root.querySelectorAll('button, a, span, strong, h1, h2, h3, h4, label, option').forEach((node) => {
    if (node.closest('[data-no-autotranslate="true"]')) return;
    if (node.hasAttribute('data-i18n')) return;
    const text = node.textContent?.trim();
    if (!text) return;
    const translated = translateText(text);
    if (translated !== text) node.textContent = translated;
  });

  root.querySelectorAll('input[placeholder], textarea[placeholder]').forEach((node) => {
    if (node.closest('[data-no-autotranslate="true"]')) return;
    if (node.hasAttribute('data-i18n-placeholder')) return;
    const placeholder = node.getAttribute('placeholder');
    if (!placeholder) return;
    const translated = translatePlaceholder(placeholder);
    if (translated !== placeholder) node.setAttribute('placeholder', translated);
  });
}

setDocumentLang(currentLang());
