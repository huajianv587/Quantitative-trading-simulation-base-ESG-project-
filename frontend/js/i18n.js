const STORAGE_KEY = 'qt-lang';

const STRINGS = {
  en: {
    'app.name': 'Quant Terminal',
    'app.tagline': 'ALPHA ENGINE · LIVE',

    'nav.platform': 'Platform',
    'nav.market_intel': 'Market Intelligence',
    'nav.market_intel_hint': 'Research and live information flow',
    'nav.decision_hub': 'Decision Hub',
    'nav.decision_hub_hint': 'Debate, factors, and risk gates',
    'nav.trading_exec': 'Trading Execution',
    'nav.trading_exec_hint': 'Submit, protections, and monitoring',
    'nav.governance': 'Governance & Review',
    'nav.governance_hint': 'Audit, outcomes, and model review',
    'nav.system_admin': 'System Admin',
    'nav.system_admin_hint': 'Rules, access, and settings',
    'nav.status.live': 'live',
    'nav.status.paper': 'exec',
    'nav.status.audit': 'audit',
    'nav.status.ops': 'ops',

    'page.login': 'Sign In',
    'page.register_auth': 'Create Account',
    'page.reset_pw': 'Reset Password',
    'page.dashboard': 'Dashboard',
    'page.research': 'Research',
    'page.market_radar': 'Market Radar',
    'page.connector_center': 'Connector Center',
    'page.agent_lab': 'Agent Lab',
    'page.intelligence': 'Decision Cockpit',
    'page.debate_desk': 'Debate Desk',
    'page.risk_board': 'Risk Board',
    'page.factor_lab': 'Factor Lab',
    'page.simulation': 'Simulation',
    'page.trading_ops': 'Trading Ops',
    'page.autopilot_policy': 'Autopilot Policy',
    'page.strategy_registry': 'Strategy Registry',
    'page.portfolio': 'Portfolio',
    'page.backtest': 'Backtest',
    'page.sweep': 'Parameter Sweep',
    'page.tearsheet': 'Tearsheet',
    'page.dataset': 'Research Datasets',
    'page.execution': 'Execution',
    'page.outcome_center': 'Outcome Center',
    'page.validation': 'Validation',
    'page.models': 'Models',
    'page.reports': 'Reports',
    'page.data_management': 'Data Sync',
    'page.data': 'Data Sync',
    'page.rl_lab': 'RL Lab',
    'page.chat': 'Research Chat',
    'page.score': 'ESG Score',
    'page.push_rules': 'Push Rules',
    'page.push': 'Push Rules',
    'page.subscriptions': 'Subscriptions',
    'page.subs': 'Subscriptions',

    'common.sign_in': 'Sign In',
    'common.create_account': 'Create Account',
    'common.loading': 'Loading',
    'common.refresh': 'Refresh',
    'common.retry': 'Retry',
    'common.save': 'Save',
    'common.cancel': 'Cancel',
    'common.submit': 'Submit',
    'common.enabled': 'Enabled',
    'common.disabled': 'Disabled',
    'common.online': 'online',
    'common.paper': 'paper',
    'common.audit': 'audit',
    'common.ops': 'ops',
    'common.live': 'live',
    'common.safe': 'safe',
    'common.warning': 'warning',
    'common.degraded': 'degraded',
    'common.connecting': 'Connecting',
    'common.backend_online': 'Backend connected',
    'common.backend_offline': 'Backend disconnected',
    'common.market_open': 'Market Open',
    'common.market_closed': 'Market Closed',
    'common.page_failed_load': 'Page failed to load',
    'common.page_failed_retry': 'Try refreshing the page or checking the backend runtime.',
    'common.request_failed': 'Request failed',
    'common.no_data': 'No data yet',
    'common.unknown_source': 'Source unknown',
    'common.features_limited': 'Some features are limited while the backend is unavailable',

    'auth.login': 'Sign In',
    'auth.register': 'Create Account',
    'auth.logout': 'Sign Out',
  },
  zh: {
    'app.name': 'Quant Terminal',
    'app.tagline': '量化引擎 · 在线',

    'nav.platform': '平台',
    'nav.market_intel': '市场智能',
    'nav.market_intel_hint': '研究流与实时信息链路',
    'nav.decision_hub': '决策中枢',
    'nav.decision_hub_hint': '辩论、因子与风控门禁',
    'nav.trading_exec': '交易执行',
    'nav.trading_exec_hint': '提交、保护与监控',
    'nav.governance': '治理与复盘',
    'nav.governance_hint': '审计、结果追踪与模型复盘',
    'nav.system_admin': '系统管理',
    'nav.system_admin_hint': '规则、权限与系统设置',
    'nav.status.live': '实时',
    'nav.status.paper': '纸面',
    'nav.status.audit': '审计',
    'nav.status.ops': '运维',

    'page.login': '登录',
    'page.register_auth': '注册账户',
    'page.reset_pw': '重置密码',
    'page.dashboard': '控制台',
    'page.research': '研究',
    'page.market_radar': '市场雷达',
    'page.connector_center': '连接器中心',
    'page.agent_lab': '智能体实验室',
    'page.intelligence': '智能决策',
    'page.debate_desk': '辩论台',
    'page.risk_board': '风控板',
    'page.factor_lab': '因子实验室',
    'page.simulation': '情景模拟',
    'page.trading_ops': '交易运维',
    'page.autopilot_policy': '自动驾驶策略',
    'page.strategy_registry': '策略注册表',
    'page.portfolio': '投资组合',
    'page.backtest': '回测',
    'page.execution': '执行',
    'page.outcome_center': '结果追踪',
    'page.validation': '策略验证',
    'page.models': '模型库',
    'page.reports': '报告中心',
    'page.data_management': '数据同步',
    'page.data': '数据同步',
    'page.rl_lab': 'RL 实验室',
    'page.chat': '研究对话',
    'page.score': 'ESG 评分',
    'page.push_rules': '推送规则',
    'page.push': '推送规则',
    'page.subscriptions': '订阅管理',
    'page.subs': '订阅管理',

    'common.sign_in': '登录',
    'common.create_account': '注册账户',
    'common.loading': '加载中',
    'common.refresh': '刷新',
    'common.retry': '重试',
    'common.save': '保存',
    'common.cancel': '取消',
    'common.submit': '提交',
    'common.enabled': '已启用',
    'common.disabled': '已停用',
    'common.online': '在线',
    'common.paper': '纸面',
    'common.audit': '审计',
    'common.ops': '运维',
    'common.live': '实时',
    'common.safe': '安全',
    'common.warning': '警告',
    'common.degraded': '降级',
    'common.connecting': '连接中',
    'common.backend_online': '后端已连接',
    'common.backend_offline': '后端未连接',
    'common.market_open': '市场开盘',
    'common.market_closed': '市场休市',
    'common.page_failed_load': '页面加载失败',
    'common.page_failed_retry': '请刷新页面或检查后端运行状态。',
    'common.request_failed': '请求失败',
    'common.no_data': '暂无数据',
    'common.unknown_source': '数据源未知',
    'common.features_limited': '后端不可用时，部分功能会自动降级',

    'auth.login': '登录',
    'auth.register': '注册账户',
    'auth.logout': '退出登录',
  },
};

const AUTO_TEXT_ZH = {
  Dashboard: '控制台',
  Research: '研究',
  'Market Radar': '市场雷达',
  'Connector Center': '连接器中心',
  'Agent Lab': '智能体实验室',
  'Decision Cockpit': '智能决策',
  'Debate Desk': '辩论台',
  'Risk Board': '风控台',
  'Factor Lab': '因子实验室',
  Simulation: '情景模拟',
  'Trading Ops': '交易运维',
  'Autopilot Policy': '自动驾驶策略',
  'Strategy Registry': '策略注册表',
  Portfolio: '投资组合',
  Backtest: '回测',
  Execution: '执行',
  'Outcome Center': '结果追踪',
  Validation: '策略验证',
  Models: '模型库',
  Reports: '报告中心',
  'Data Sync': '数据同步',
  'RL Lab': 'RL 实验室',
  'Research Chat': '研究对话',
  'ESG Score': 'ESG 评分',
  'Push Rules': '推送规则',
  Subscriptions: '订阅管理',
  'Sign In': '登录',
  'Create Account': '注册账户',
  Refresh: '刷新',
  Loading: '加载中',
  Retry: '重试',
  Save: '保存',
  Submit: '提交',
  Cancel: '取消',
  'Request failed': '请求失败',
  'Page failed to load': '页面加载失败',
  'No data yet': '暂无数据',
  'Source unknown': '数据源未知',
  'Backend connected': '后端已连接',
  'Backend disconnected': '后端未连接',
  'Market Open': '市场开盘',
  'Market Closed': '市场休市',
  'Paper Auto-Submit': '自动提交',
  'Paper submit and monitoring': '提交与监控',
  'Audit, outcomes, and model review': '审计、结果与模型复盘',
};

const AUTO_PLACEHOLDER_ZH = {
  'optional decision id': '可选决策 ID',
  'symbol or company': '股票代码或公司名称',
  'comma-separated symbols': '请用逗号分隔股票代码',
  'provider list': '数据源列表',
};

function currentLang() {
  const raw = String(localStorage.getItem(STORAGE_KEY) || 'en').toLowerCase();
  return raw === 'zh' ? 'zh' : 'en';
}

function setDocumentLang(lang) {
  document.documentElement.lang = lang === 'zh' ? 'zh-CN' : 'en';
}

function applyAutoTranslation(root) {
  if (!root || currentLang() !== 'zh') return;
  root.querySelectorAll('[placeholder]:not([data-i18n-placeholder])').forEach((node) => {
    if (node.hasAttribute('data-no-autotranslate')) return;
    const translated = AUTO_PLACEHOLDER_ZH[String(node.getAttribute('placeholder') || '').trim()];
    if (translated) node.setAttribute('placeholder', translated);
  });

  root.querySelectorAll('*').forEach((node) => {
    if (node.children.length) return;
    if (node.hasAttribute('data-no-autotranslate')) return;
    const raw = String(node.textContent || '').trim();
    if (!raw) return;
    const translated = AUTO_TEXT_ZH[raw];
    if (translated) node.textContent = translated;
  });
}

const listeners = new Set();

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

export function translateLoose(value) {
  if (!value || currentLang() !== 'zh') return value;
  return AUTO_TEXT_ZH[String(value).trim()] || value;
}

export function applyLangToPage(root = document) {
  setDocumentLang(currentLang());

  root.querySelectorAll('[data-i18n]').forEach((node) => {
    const key = node.getAttribute('data-i18n');
    if (!key) return;
    node.textContent = t(key);
  });

  root.querySelectorAll('[data-i18n-title]').forEach((node) => {
    const key = node.getAttribute('data-i18n-title');
    if (!key) return;
    node.setAttribute('title', t(key));
  });

  root.querySelectorAll('[data-i18n-placeholder]').forEach((node) => {
    const key = node.getAttribute('data-i18n-placeholder');
    if (!key) return;
    node.setAttribute('placeholder', t(key));
  });

  applyAutoTranslation(root);
}

export function onLangChange(callback) {
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
      console.error('Language listener failed', error);
    }
  });
  applyLangToPage();
}

setDocumentLang(currentLang());
