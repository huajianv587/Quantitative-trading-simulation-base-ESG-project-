/* ── i18n: Chinese / English toggle ──────────────────────────────
   Usage:
     import { t, setLang, getLang, getLocale, onLangChange } from './i18n.js?v=8';
──────────────────────────────────────────────────────────────── */

const STRINGS = {
  en: {
    'app.logo_tag': 'ALPHA ENGINE · LIVE',

    // Nav groups
    'nav.platform': 'PLATFORM',
    'nav.quant': 'QUANT ENGINE',
    'nav.research': 'RESEARCH',
    'nav.ops': 'OPERATIONS',

    // Page labels
    'page.login': 'Sign In',
    'page.register_auth': 'Register',
    'page.reset_pw': 'Reset Password',
    'page.dashboard': 'Dashboard',
    'page.research': 'Research',
    'page.portfolio': 'Portfolio',
    'page.backtest': 'Backtest',
    'page.execution': 'Execution',
    'page.validation': 'Validation',
    'page.models': 'Models',
    'page.chat': 'Research Chat',
    'page.score': 'ESG Score',
    'page.reports': 'Reports',
    'page.data': 'Data Sync',
    'page.push': 'Push Rules',
    'page.subs': 'Subscriptions',

    // Auth
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
    'auth.back_login': '← Back to Login',
    'auth.remember': 'Remember me',
    'auth.logout': 'Log Out',
    'auth.welcome': 'Welcome back',
    'auth.register_success': 'Account created',
    'auth.enter_email': 'Enter your email',
    'auth.enter_password': 'Enter your password',
    'auth.enter_name': 'Your full name',
    'auth.or': 'or',
    'auth.headline_login': 'ESG Alpha\nIntelligence',
    'auth.tagline_login': 'Bloomberg-grade quantitative research\npowered by ESG factor models & AI.',
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
    'auth.benefit1': 'Professional K-line & ESG factor analysis',
    'auth.benefit2': 'AI-powered research chat assistant',
    'auth.benefit3': 'Real-time signals & backtesting engine',
    'auth.pw_too_short': 'Too short',
    'auth.pw_weak': 'Weak',
    'auth.pw_fair': 'Fair',
    'auth.pw_good': 'Good',
    'auth.pw_strong': 'Strong',
    'auth.pw_mismatch': 'Passwords do not match',
    'auth.pw_min_len': 'Password must be at least 6 characters',

    // Common
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

    // Nav groups
    'nav.platform': '平台',
    'nav.quant': '量化引擎',
    'nav.research': '研究工具',
    'nav.ops': '运营管理',

    // Page labels
    'page.login': '登录',
    'page.register_auth': '注册',
    'page.reset_pw': '重置密码',
    'page.dashboard': '控制台',
    'page.research': '研究',
    'page.portfolio': '投资组合',
    'page.backtest': '回测',
    'page.execution': '执行',
    'page.validation': '策略验证',
    'page.models': '模型仓库',
    'page.chat': '研究对话',
    'page.score': 'ESG 评分',
    'page.reports': '报告中心',
    'page.data': '数据同步',
    'page.push': '推送规则',
    'page.subs': '订阅管理',

    // Auth
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
    'auth.back_login': '← 返回登录',
    'auth.remember': '记住我',
    'auth.logout': '退出登录',
    'auth.welcome': '欢迎回来',
    'auth.register_success': '账户创建成功',
    'auth.enter_email': '请输入邮箱',
    'auth.enter_password': '请输入密码',
    'auth.enter_name': '请输入姓名',
    'auth.or': '或',
    'auth.headline_login': 'ESG Alpha\n智能平台',
    'auth.tagline_login': '彭博级量化研究\n基于 ESG 因子模型与 AI 驱动。',
    'auth.sub_login': '登录 · Quant Terminal',
    'auth.demo_title': '演示通道',
    'auth.demo_text': '注册任意邮箱即可立即创建账户，无需验证。',
    'auth.stat_sharpe': '夏普比率',
    'auth.stat_signals': '实时信号',
    'auth.stat_universe': '股票池',
    'auth.headline_register': '加入\nAlpha 网络',
    'auth.tagline_register': '使用专业 ESG 量化工具\n深受分析师和基金经理信赖。',
    'auth.sub_register': 'Quant Terminal · ESG Alpha 平台',
    'auth.terms': '创建账户即表示您同意 <a class="auth-link" href="#">服务条款</a>。无需邮箱验证。',
    'auth.stat_companies': '覆盖企业',
    'auth.stat_esg': 'ESG 因子',
    'auth.stat_market': '实时行情',
    'auth.showcase_sharpe_key': '平均夏普比率',
    'auth.showcase_sharpe_sub': 'ESG 多因子策略',
    'auth.showcase_alpha_key': 'ESG Alpha 超额',
    'auth.showcase_alpha_sub': 'vs 基准 年初至今',
    'auth.benefit1': '专业 K 线与 ESG 因子分析',
    'auth.benefit2': 'AI 驱动的研究对话助手',
    'auth.benefit3': '实时信号与回测引擎',
    'auth.pw_too_short': '太短',
    'auth.pw_weak': '弱',
    'auth.pw_fair': '一般',
    'auth.pw_good': '良好',
    'auth.pw_strong': '强',
    'auth.pw_mismatch': '两次密码不一致',
    'auth.pw_min_len': '密码至少需要 6 位字符',

    // Common
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

const TEXT_NODE_SOURCES = new WeakMap();
const ATTR_SOURCES = new WeakMap();

const AUTO_TEXT_ZH = {
  'Quant Terminal': 'Quant Terminal',
  'Dashboard': '控制台',
  'Research': '研究',
  'Portfolio': '投资组合',
  'Backtest': '回测',
  'Execution': '执行',
  'Validation': '策略验证',
  'Models': '模型仓库',
  'Research Chat': '研究对话',
  'ESG Score': 'ESG 评分',
  'Reports': '报告中心',
  'Data Sync': '数据同步',
  'Push Rules': '推送规则',
  'Subscriptions': '订阅管理',
  'Overview': '总览',
  'Sign In': '登录',
  'Register': '注册',
  'Reset Password': '重置密码',
  'All': '全部',
  'None': '无',
  'Daily': '每日',
  'Weekly': '每周',
  'Monthly': '每月',
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
  'Generate': '生成',
  'Export': '导出',
  'Download': '下载',
  'Close': '关闭',
  'Search': '搜索',
  'Filter': '筛选',
  'Submit': '提交',
  'Create': '创建',
  'Delete': '删除',
  'Test': '测试',
  'Matched': '已命中',
  'Did not match': '未命中',
  'Could not load history': '无法加载历史记录',
  'Load failed': '加载失败',
  'Could not load orders': '无法加载订单',
  'Could not load experiments': '无法加载实验记录',
  'No data available': '暂无数据',
  'N/A': '无',
  'Rule': '规则',
  'Subscription': '订阅',
  'All Systems Nominal': '全部系统正常',
  'ALL SYSTEMS NOMINAL': '全部系统正常',

  // Backtest
  'Backtest Engine': '回测引擎',
  'Strategy Validation Lab · Equity Curve · Risk Attribution · Monthly Returns': '策略验证实验室 · 权益曲线 · 风险归因 · 月度收益',
  'Run Backtest': '运行回测',
  'Configure strategy parameters': '配置策略参数',
  'Strategy Name': '策略名称',
  'Universe': '股票池',
  'Capital ($)': '资金规模 ($)',
  'Benchmark': '基准',
  'Lookback (trading days)': '回看周期（交易日）',
  'ADVANCED SETTINGS': '高级设置',
  'Slippage Model': '滑点模型',
  'Market Impact': '市场冲击',
  'Custom bps': '自定义基点',
  'Position Sizing': '仓位规模',
  'Equal Weight': '等权重',
  'Vol-Scaled': '波动率缩放',
  'Kelly Criterion': '凯利准则',
  'Rebalance Frequency': '再平衡频率',
  'Signal-Triggered': '信号触发',
  'Stop Loss per Position': '单仓止损',
  'Recent Backtests': '最近回测',
  'Equity Curve': '权益曲线',
  'Portfolio': '组合',
  'Monthly Returns Heatmap': '月度收益热力图',
  'Year': '年份',
  'Jan': '1月',
  'Feb': '2月',
  'Mar': '3月',
  'Apr': '4月',
  'May': '5月',
  'Jun': '6月',
  'Jul': '7月',
  'Aug': '8月',
  'Sep': '9月',
  'Oct': '10月',
  'Nov': '11月',
  'Dec': '12月',
  'Total': '总计',
  'Run a backtest': '运行一次回测',
  'Configure strategy parameters and click Run to see equity curve, Sharpe ratio, drawdown, and full risk attribution.': '配置策略参数后点击运行，即可查看权益曲线、夏普比率、回撤和完整风险归因。',
  'No backtests yet': '暂无回测记录',
  'Sharpe': '夏普',
  'Annual Return': '年化收益',
  'Sharpe Ratio': '夏普比率',
  'Max Drawdown': '最大回撤',
  'Win Rate': '胜率',
  'Sortino': '索提诺',
  'Calmar': '卡玛',
  'Full Metrics': '完整指标',
  'Strategy': '策略',
  'Risk Alerts': '风险提醒',
  'Backtest complete': '回测完成',
  'Backtest failed': '回测失败',
  '● Running…': '● 运行中…',
  '▶ Run Backtest': '▶ 运行回测',

  // Execution
  'EXECUTION MONITOR': '执行监控',
  'DISCONNECTED': '未连接',
  'Alpaca Paper · NYSE': 'Alpaca 模拟盘 · NYSE',
  '⚠ KILL SWITCH': '⚠ 熔断开关',
  'Submit Execution Plan': '提交执行计划',
  'Alpaca Paper Trading': 'Alpaca 模拟交易',
  'Broker': '券商',
  'Submit Orders to Broker': '向券商提交订单',
  '▶ Run Execution Plan': '▶ 运行执行计划',
  '⚠ Emergency Controls': '⚠ 紧急控制',
  'Kill switch immediately cancels all pending orders and halts new submissions for the current execution plan.': '熔断开关会立即取消所有待处理订单，并阻止当前执行计划继续提交新订单。',
  '☠ ARM KILL SWITCH': '☠ 启用熔断开关',
  '⚠ CONFIRM TO HALT ALL TRADING': '⚠ 确认停止全部交易',
  '⚡ CONFIRM KILL': '⚡ 确认熔断',
  'KILL SWITCH ACTIVATED': '熔断开关已触发',
  'All orders cancelled · No new orders': '全部订单已取消 · 不再提交新订单',
  'Live Positions': '实时持仓',
  'Order Stream': '订单流',
  'Filled': '已成交',
  'Pending': '待处理',
  'Failed': '失败',
  'Cancelled': '已取消',
  'Loading orders…': '正在加载订单…',
  'Live Feed': '实时动态',
  'connecting…': '连接中…',
  'Waiting for events…': '等待事件中…',
  '⚠ ARMED — confirm below': '⚠ 已就绪，请下方确认',
  'Kill switch activated': '熔断开关已触发',
  'All pending orders cancelled': '所有待处理订单已取消',
  'Kill switch failed': '熔断失败',
  'Submitting…': '提交中…',
  'Execution plan submitted': '执行计划已提交',
  'Execution failed': '执行失败',
  'No orders': '暂无订单',
  'Submit an execution plan to see orders here.': '提交执行计划后，这里会显示订单。',
  'Side': '方向',
  'Status': '状态',
  'Fill $': '成交价 $',
  'Limit $': '限价 $',
  'Type': '类型',
  'Time': '时间',
  'BUY': '买入',
  'SELL': '卖出',

  // Validation
  'Alpha Validation': 'Alpha 验证',
  'Walk-Forward Testing · Overfit Detection · Strategy Robustness Lab': '滚动前推测试 · 过拟合检测 · 策略稳健性实验室',
  'Walk-Forward Validation': '滚动前推验证',
  'Overfit detection · Cost sensitivity': '过拟合检测 · 成本敏感性',
  'In-Sample Days': '样本内天数',
  'Out-of-Sample Days': '样本外天数',
  'Walk-Forward Windows': '滚动窗口数',
  'ADVANCED VALIDATION OPTIONS': '高级验证选项',
  'Deflated Sharpe Threshold': '折减夏普阈值',
  'Multiple Testing Correction': '多重检验修正',
  'Validation History': '验证历史',
  'No prior validations': '暂无历史验证',
  'Run walk-forward validation': '运行滚动前推验证',
  'Configure parameters and run to get GO/NO-GO verdict, walk-forward chart, and overfit analysis.': '配置参数后运行，即可获得 GO/NO-GO 结论、前推图表和过拟合分析。',
  '● Validating…': '● 验证中…',
  'Validation complete': '验证完成',
  'See results': '查看结果',
  'Validation API error': '验证接口错误',
  'GO': '通过',
  'GO — STRATEGY IS ROBUST': '通过 — 策略较稳健',
  'NO-GO — OVERFIT DETECTED': '不通过 — 检测到过拟合',
  'OOS SHARPE': '样本外夏普',
  'PASS — Above 1.0 threshold': '通过 — 高于 1.0 阈值',
  'FAIL — Below 1.0 threshold': '失败 — 低于 1.0 阈值',
  'OVERFIT SCORE': '过拟合分数',
  'PASS — Low overfit risk': '通过 — 过拟合风险低',
  'WARNING': '警告',
  'FAIL — High overfit': '失败 — 过拟合风险高',
  'COST DRAG': '成本拖累',
  'FILL PROB': '成交概率',
  'HIGH — Liquid universe': '高 — 流动性良好',
  'MEDIUM': '中',
  'LOW': '低',
  'Walk-Forward Performance': '滚动前推表现',
  'Regime Performance Analysis': '市场状态表现分析',
  'Regime': '市场状态',
  'Periods': '周期数',
  'Avg Return': '平均收益',
  'Max DD': '最大回撤',
  '📊 Export Validation Report': '📊 导出验证报告',
  '→ Approve for Execution': '→ 批准执行',
  'Robust Zone': '稳健区间',
  'Bull Market': '牛市',
  'Bear Market': '熊市',
  'Sideways': '震荡',
  'High Vol': '高波动',
  '▶ Run Validation': '▶ 运行验证',

  // Data management
  'Data Management': '数据管理',
  'Pipeline Monitor · Data Freshness · Sync Control · Ingestion Logs': '管线监控 · 数据新鲜度 · 同步控制 · 接入日志',
  '↺ Refresh All': '↺ 全部刷新',
  'Data Pipeline': '数据管线',
  'Sync Control': '同步控制',
  'Trigger company snapshot refresh': '触发公司快照刷新',
  'Companies / Tickers': '公司 / 股票代码',
  'Data Sources': '数据源',
  'All Sources': '全部数据源',
  'ESG Scores': 'ESG 评分',
  'Price Data': '价格数据',
  'Filings': '监管文件',
  'Sentiment': '情绪数据',
  'Force Refresh': '强制刷新',
  'Priority': '优先级',
  '▶ Start Sync': '▶ 开始同步',
  'Active Jobs': '活动任务',
  'No active sync jobs': '当前没有同步任务',
  'Ingestion Log': '接入日志',
  'Clear': '清空',
  'Live Feeds': '在线数据源',
  'Avg Freshness': '平均新鲜度',
  'Records Today': '今日记录数',
  'Alerts': '告警',
  '1 warning': '1 条告警',
  'Data Source Freshness': '数据源新鲜度',
  'Ingestion Throughput (24h)': '接入吞吐量（24h）',
  'Raw Ingestion': '原始接入',
  'Data Cleaning': '数据清洗',
  'ESG Enrichment': 'ESG 丰富化',
  'Feature Store': '特征库',
  'Model Input': '模型输入',
  'Signal Output': '信号输出',
  'ESG News Feed': 'ESG 新闻流',
  'Price / OHLCV': '价格 / OHLCV',
  'Company Snapshots': '公司快照',
  'ESG Scores (Refinitiv)': 'ESG 评分（Refinitiv）',
  'SEC Filings': 'SEC 文件',
  'Macro Indicators': '宏观指标',
  'Sentiment NLP': '情绪 NLP',
  'Alternative Data': '另类数据',
  'Stream': '流式',
  'Batch': '批量',
  'Event': '事件',
  'stale': '过期',
  'warning': '告警',
  'live': '在线',

  // Push rules
  'Push Rules': '推送规则',
  'Configure notification rules and test routing conditions': '配置通知规则并测试路由条件',
  'Create Rule': '创建规则',
  'Matches against report payloads': '匹配报告载荷',
  'Rule Name': '规则名称',
  'Condition': '条件',
  'Target Users': '目标用户',
  'Channels': '渠道',
  'Template ID': '模板 ID',
  'Existing Rules': '现有规则',
  'Creating...': '创建中...',
  'Push rule created': '推送规则已创建',
  'Rule creation failed': '规则创建失败',
  'No push rules configured.': '暂无推送规则。',
  'Condition: N/A': '条件：无',
  'Channels: N/A': '渠道：无',
  'Rule tested': '规则测试完成',
  'Rule test failed': '规则测试失败',
  'Rule deleted': '规则已删除',
  'Delete failed': '删除失败',

  // Subscriptions
  'Subscriptions': '订阅管理',
  'Manage report subscriptions for the current user': '管理当前用户的报告订阅',
  'Create Subscription': '创建订阅',
  'Subscribe to report delivery with channel preferences': '按渠道偏好订阅报告投递',
  'Report Types': '报告类型',
  'Frequency': '频率',
  'Companies': '公司',
  'ESG Alert Threshold': 'ESG 告警阈值',
  'Current Subscriptions': '当前订阅',
  'Subscription created': '订阅已创建',
  'Subscription failed': '订阅失败',
  'No subscriptions found.': '未找到订阅。',
  'Companies: N/A': '公司：无',
  'Frequency: N/A': '频率：无',
  'Subscription deleted': '订阅已删除',

  // Reports
  'Report Center': '报告中心',
  'Generate · Schedule · Archive · Export ESG Research Reports': '生成 · 定时 · 归档 · 导出 ESG 研究报告',
  '⏰ Schedule': '⏰ 定时',
  'Generate Report': '生成报告',
  'Choose type, scope and options': '选择类型、范围和配置',
  'Daily Digest': '每日报告',
  'Top signals, score updates, alerts': '顶部信号、评分更新、告警',
  'Weekly Summary': '每周总结',
  'Portfolio review, ESG movers, attribution': '组合复盘、ESG 变化、归因',
  'Monthly Deep-Dive': '月度深度分析',
  'Full factor analysis, peer benchmarks, forecasts': '完整因子分析、同业对标、预测',
  'Ad-Hoc Analysis': '临时分析',
  'Custom companies, custom period': '自定义公司、自定义周期',
  'Companies / Tickers': '公司 / 股票代码',
  'Start Date': '开始日期',
  'End Date': '结束日期',
  'Sections to Include': '包含章节',
  'Factor Analysis': '因子分析',
  'Peer Comparison': '同业对比',
  'Risk Attribution': '风险归因',
  'Signals': '信号',
  'Forecasts': '预测',
  '▶ Generate': '▶ 生成',
  'Load Latest': '加载最新',
  'Report Archive': '报告档案',
  'No report loaded': '尚未加载报告',
  'Generate a new report or click an archive entry to load.': '生成新报告或点击归档记录进行加载。',
  'Scheduling': '定时功能',
  'Report scheduler coming soon': '报告调度功能即将上线',
  'Select a report first': '请先选择报告',
  'PDF Export': 'PDF 导出',
  'Generating PDF…': '正在生成 PDF…',
  'CSV Export': 'CSV 导出',
  'Downloading CSV…': '正在下载 CSV…',
  'JSON Export': 'JSON 导出',
  'Downloading JSON…': '正在下载 JSON…',
  'Report generated': '报告已生成',
  'API error': '接口错误',
  'No report found': '未找到报告',
  'Daily Digest — Apr 12': '每日报告 — 4月12日',
  'Weekly Summary — W14': '每周总结 — 第14周',
  'Monthly Deep-Dive — Mar': '月度深度分析 — 3月',
  'Daily Digest — Apr 11': '每日报告 — 4月11日',
  'Ad-Hoc: NVDA vs AMD': '临时分析：NVDA vs AMD',
  'ESG Report': 'ESG 报告',
  'Generated': '生成时间',
  'Portfolio continues to outperform the ESG benchmark. Technology sector leads on governance and social dimensions. Momentum remains positive across top holdings.': '组合继续跑赢 ESG 基准。科技板块在治理与社会维度上领先，核心持仓的动量仍然保持积极。',
  'NVDA: Governance improvement +4pts': 'NVDA：治理维度提升 +4 分',
  'MSFT: Carbon neutrality milestone achieved': 'MSFT：碳中和里程碑达成',
  'TSLA: Social score dip — supply chain concern flagged': 'TSLA：社会维度分数回落 — 供应链问题被标记',
  'Rising VIX may pressure high-beta ESG growth stocks': 'VIX 上升可能压制高 Beta ESG 成长股',
  'Geopolitical risk elevated for TSLA Taiwan supply chain': 'TSLA 台湾供应链的地缘风险上升',
  'BUY': '买入',
  'HOLD': '持有',
  'SELL': '卖出',
  'pts': '分',

  // Score dashboard
  'ESG Score Dashboard': 'ESG 评分看板',
  'Environmental · Social · Governance · Peer Comparison · Trend Analysis': '环境 · 社会 · 治理 · 同业对比 · 趋势分析',
  '⬇ Export Report': '⬇ 导出报告',
  'Score Company': '评分公司',
  'ESG agent · Peer benchmark · Trend': 'ESG 智能体 · 同业基准 · 趋势',
  'Company Name': '公司名称',
  'Ticker': '股票代码',
  'Peer Companies (for benchmark)': '同行公司（用于对标）',
  'Analysis Depth': '分析深度',
  'Standard (E+S+G)': '标准（E+S+G）',
  'Deep (All sub-dimensions)': '深入（全部子维度）',
  'Quick Score': '快速评分',
  '▶ Run ESG Score': '▶ 运行 ESG 评分',
  'Score Trend (12mo)': '评分趋势（12个月）',
  'Quick Compare': '快速对比',
  'OVERALL': '总分',
  'Multi-Dimension Radar': '多维雷达图',
  'Peer Comparison': '同业对比',
  'Export': '导出',
  'PDF export not yet connected': 'PDF 导出尚未接通',
  '● Scoring…': '● 评分中…',
  'ESG scoring complete': 'ESG 评分完成',
  'Environment': '环境',
  'Social': '社会',
  'Governance': '治理',
  'Carbon Intensity': '碳强度',
  'Renewable Energy %': '可再生能源占比',
  'Water Efficiency': '水资源效率',
  'Waste Reduction': '废弃物减量',
  'Climate Risk': '气候风险',
  'Workforce Diversity': '员工多样性',
  'Safety Record': '安全记录',
  'Community Score': '社区影响',
  'Supply Chain Ethics': '供应链伦理',
  'Employee Wellbeing': '员工福祉',
  'Board Independence': '董事会独立性',
  'CEO Pay Ratio': 'CEO 薪酬比',
  'Audit Quality': '审计质量',
  'Shareholder Rights': '股东权利',
  'Anti-corruption': '反腐治理',
  'Consumer Discretionary / EV': '可选消费 / 电动车',
  'Rating': '评级',
  'RATING': '评级',
  'Top 22th percentile in industry': '行业前 22 百分位',
  'ENVIRON': '环境',
  'SOCIAL': '社会',
  'GOVERN': '治理',

  // Chat
  'SESSIONS': '会话',
  'LIVE CONTEXT': '实时上下文',
  'QUICK PROMPTS': '快捷问题',
  'Session': '会话',
  'Context-aware · Multi-turn': '上下文感知 · 多轮对话',
  'ONLINE': '在线',
  'Clear': '清空',
  'Ctrl+↵ to send': 'Ctrl+↵ 发送',
  '▶ Send': '▶ 发送',
  'New session started': '已开始新会话',
  'Enter a question first': '请先输入问题',
  '● Thinking…': '● 思考中…',
  'No answer returned.': '未返回答案。',
  'Start a conversation': '开始一次对话',
  'Waiting for your first message': '等待你的第一条消息',
  'Mock response': '模拟回复',
  'Why is NVDA ranked highly in the current ESG stack?': '为什么 NVDA 在当前 ESG 堆栈中排名这么高？',
  'Compare ESG scores for MSFT vs AAPL vs GOOGL': '比较 MSFT、AAPL 和 GOOGL 的 ESG 评分',
  "What factors are driving today's top alpha signals?": '今天顶部 Alpha 信号由哪些因子驱动？',
  'Explain the current regime classification and its impact': '解释当前市场状态分类及其影响',
  'Which sectors have the best ESG momentum right now?': '当前哪些板块的 ESG 动量最好？',
  'What is the overfit risk of the current strategy?': '当前策略的过拟合风险如何？',
  'NVDA ESG Deep-Dive': 'NVDA ESG 深度分析',
  'Why is NVDA ranked #1…': '为什么 NVDA 排名第 1…',
  'Tech Sector Momentum': '科技板块动量',
  'Compare MSFT vs AAPL…': '比较 MSFT 与 AAPL…',
  'Portfolio Risk Review': '组合风险复盘',
  'What factors explain…': '是什么因子在解释…',
  'ESG Scoring Changes': 'ESG 评分变化',
  'How did governance…': '治理维度如何变化…',
  'Yesterday': '昨天',
  'Mon': '周一',
  '10:24 AM': '10:24',
  '2 min ago': '2 分钟前',
  '24 active': '24 条活跃',
  'Bull Market': '牛市',
  'API error': '接口错误',
  'showing mock response': '显示模拟回复',

  // Models
  'All Models': '全部模型',
  'ML-Based': '机器学习',
  'Factor Models': '因子模型',
  'Statistical Arb': '统计套利',
  'Model Registry': '模型注册表',
  'Alpha Stack · Decision Engine · Experiments · Catalog': 'Alpha 堆栈 · 决策引擎 · 实验 · 目录',
  '↺ Refresh Status': '↺ 刷新状态',
  'P1 ALPHA STACK': 'P1 Alpha 堆栈',
  'P2 DECISION ENGINE': 'P2 决策引擎',
  'LOADING': '加载中',
  '▶ Run P1': '▶ 运行 P1',
  '▶ Run P2': '▶ 运行 P2',
  'Run P1 Alpha Stack': '运行 P1 Alpha 堆栈',
  'Run P2 Decision Engine': '运行 P2 决策引擎',
  'Universe (blank = default)': '股票池（留空使用默认）',
  'Horizon (days)': '周期（天）',
  '▶ Submit P1 Run': '▶ 提交 P1 运行',
  '▶ Submit P2 Run': '▶ 提交 P2 运行',
  'Search models…': '搜索模型…',
  'Experiment History': '实验历史',
  'Loading experiments…': '加载实验记录中…',
  'Status refreshed': '状态已刷新',
  'P1 stack ran': 'P1 堆栈已运行',
  'P1 run failed': 'P1 运行失败',
  'P2 decision ran': 'P2 决策已运行',
  'P2 run failed': 'P2 运行失败',
  'No experiments yet': '暂无实验记录',
  'Run P1 or P2 stacks to populate the experiment registry.': '运行 P1 或 P2 堆栈后，这里会显示实验记录。',
  'Experiment ID': '实验 ID',
  'Alpha Ranker': 'Alpha 排序器',
  'LSTM Price Signal': 'LSTM 价格信号',
  'Regime Detector': '市场状态检测器',
  'GNN Portfolio Engine': 'GNN 组合引擎',
  'Contextual Bandit': '上下文老虎机',
  'Statistical Arbitrage': '统计套利',
  'ESG Multi-Factor': 'ESG 多因子',
  'Sentiment NLP': '情绪 NLP',
  'Momentum Alpha': '动量 Alpha',
  'Long-Short': '多空',
  'Execution': '执行',
  'Allocation': '配置',
  'Market-Neutral': '市场中性',
  'Factor': '因子',
  'Research': '研究',
  'Momentum': '动量',
  'staging': '预发',
  'research': '研究中',

  // Portfolio
  'Portfolio Optimizer': '组合优化器',
  'Institutional Portfolio Construction · Mean-Variance · ESG-Constrained · 5-Step Workflow': '机构级组合构建 · 均值方差 · ESG 约束 · 五步流程',
  'Risk Profile': '风险画像',
  'Constraints': '约束条件',
  'Optimize': '优化',
  'Review': '复核',
  'CURRENT BUILD': '当前构建',
  'Expected Return': '预期收益',
  'Volatility': '波动率',
  'Sharpe Estimate': '夏普估计',
  'Max DD Est.': '最大回撤估计',
  'Diversification': '分散度',
  'TOP HOLDINGS': '前五持仓',
  'Not built yet': '尚未构建',
  'Clear Portfolio': '清空组合',
  '→ Send to Execution': '→ 发送到执行',
  'Step 1 — Investor Risk Profile': '步骤 1 — 投资者风险画像',
  'If your portfolio dropped 20% in a month, you would:': '如果你的组合在一个月内下跌 20%，你会：',
  'Sell everything': '全部卖出',
  'Sell some': '卖出一部分',
  'Hold position': '继续持有',
  'Buy more': '继续加仓',
  'Investment time horizon': '投资期限',
  '< 1 year': '< 1 年',
  '1–3 years': '1–3 年',
  '3–10 years': '3–10 年',
  '10+ years': '10 年以上',
  'ESG / Sustainability importance': 'ESG / 可持续性重要程度',
  'None': '无',
  'Low': '低',
  'Medium': '中',
  'High': '高',
  'Critical': '关键',
  'Trading style': '交易风格',
  'Index/Passive': '指数 / 被动',
  'Value': '价值',
  'ESG-First': 'ESG 优先',
  'Quant/Systematic': '量化 / 系统化',
  'Growth': '成长',
  'MODERATE GROWTH INVESTOR': '中等成长型投资者',
  'Risk Tolerance': '风险承受',
  'Max DD Tolerance': '最大回撤容忍',
  'Investment Horizon': '投资期限',
  'Equity Allocation': '权益配置',
  'ESG Priority': 'ESG 优先级',
  'Strategy Fit': '策略匹配',
  'Accept & Continue →': '接受并继续 →',
  'Step 2 — Investment Universe': '步骤 2 — 投资范围',
  'Preset Universes': '预设股票池',
  'stocks': '只股票',
  'ESG avg': 'ESG 均值',
  'P/E': '市盈率',
  'Custom Universe Override': '自定义股票池覆盖',
  'Asset Class Allocation': '资产类别配置',
  'US Equities': '美国股票',
  'International': '国际资产',
  'Fixed Income': '固定收益',
  'Commodities': '商品',
  'Alternatives': '另类资产',
  '← Back': '← 返回',
  'Next: Constraints →': '下一步：约束条件 →',

  // Generic report/score/model/chat pieces
  'Current': '当前',
  'Score': '评分',
  'Sector': '板块',
  'Company': '公司',
  'Action': '动作',
  'Condition:': '条件：',
  'Channels:': '渠道：',
  'Frequency:': '频率：',

  // Common calendar / status
  Jan: '1月',
  Feb: '2月',
  Mar: '3月',
  Apr: '4月',
  May: '5月',
  Jun: '6月',
  Jul: '7月',
  Aug: '8月',
  Sep: '9月',
  Oct: '10月',
  Nov: '11月',
  Dec: '12月',
  'Loading…': '加载中…',
  Loading: '加载中',
  Refresh: '刷新',
  Clear: '清空',
  Cancel: '取消',
  All: '全部',
  PDF: 'PDF',
  CSV: 'CSV',
  JSON: 'JSON',
  Filled: '已成交',
  Pending: '处理中',
  Failed: '失败',
  Cancelled: '已取消',
  Status: '状态',
  Side: '方向',
  Qty: '数量',
  Type: '类型',
  Time: '时间',
  Benchmark: '基准',
  'Capital ($)': '资金规模 ($)',
  Ticker: '代码',
  Overall: '总分',
  Generated: '已生成',
  'Generated:': '生成时间：',
  Report: '报告',
  Create: '创建',
  Delete: '删除',
  Test: '测试',
  Priority: '优先级',
  Frequency: '频率',
  Companies: '公司',
  Holdings: '持仓数',
  'Companies / Tickers': '公司 / 代码',
  'Target Users': '目标用户',
  'Template ID': '模板 ID',
  'Rule Name': '规则名称',
  Rule: '规则',
  'Rule Name': '规则名称',
  'No answer returned.': '未返回答案。',
  ERROR: '错误',
  '● Running…': '● 运行中…',
  'Status refreshed': '状态已刷新',
  'See results': '查看结果',
  'Backend Connected': '后端已连接',
  'Expected annual return:': '预期年化收益：',
  'Max acceptable drawdown:': '最大可接受回撤：',
  '5–7 years': '5–7 年',
  'Quant/ESG': '量化 / ESG',
  'S&P 500 Full': '标普 500 全市场',
  'Global ESG Leaders': '全球 ESG 领先者',
  'High Dividend': '高分红',
  'Momentum Leaders': '动量领先者',
  'Custom Watchlist': '自定义自选股',
  'Technology': '科技',
  'Utilities': '公用事业',
  'Consumer Disc': '可选消费',
  'Healthcare': '医疗保健',
  'Financials': '金融',
  'Industrials': '工业',
  'Energy': '能源',
  'Materials': '材料',
  'Real Estate': '房地产',
  'ALPACA API CREDENTIALS': 'ALPACA API 凭据',
  'API Key ID': 'API 密钥 ID',
  'Secret Key': '密钥',
  'Credentials stored in browser only · Never sent to third parties · Used by backend to connect Alpaca Paper Trading': '凭据仅保存在浏览器中 · 不会发送给第三方 · 仅供后端连接 Alpaca 模拟盘使用',
  'ESG Alpha Research Agent': 'ESG Alpha 研究智能体',
  'Context-aware · Multi-turn': '上下文感知 · 多轮',
  "Hello! I'm your ESG Alpha Research Agent. I have access to your current portfolio, live P1/P2 model signals, ESG scores, and market regime data.": '你好，我是你的 ESG Alpha 研究智能体。我可以访问你当前的投资组合、实时 P1/P2 模型信号、ESG 评分和市场状态数据。',
  'You can ask me about:': '你可以问我这些内容：',
  'Specific stocks': '个股分析',
  '— ESG scores, factor exposures, signal rationale': '— ESG 评分、因子暴露和信号逻辑',
  'Portfolio analysis': '组合分析',
  '— Risk attribution, factor breakdown': '— 风险归因和因子拆解',
  'Market regime': '市场状态',
  '— Current state, impact on strategy': '— 当前状态及对策略的影响',
  'Strategy insights': '策略洞察',
  '— Why certain trades are ranked highly': '— 为什么某些交易排名靠前',
  'What would you like to explore?': '你想先看哪一部分？',
  'Alpha Stack · Decision Engine · Experiments · Catalog': 'Alpha 堆栈 · 决策引擎 · 实验 · 目录',
  'Gradient-boosted ranking model combining 47 ESG-adjusted factors. Primary signal generator in P1 stack.': '基于梯度提升的排序模型，融合 47 个 ESG 调整因子，是 P1 堆栈的核心信号生成器。',
  'Sequence-to-sequence LSTM trained on 10 years of price/volume data with attention mechanism. Feeds into Alpha Ranker.': '基于注意力机制的序列到序列 LSTM，使用 10 年量价数据训练，并作为 Alpha 排序器的输入。',
  '4-state HMM classifying market regime: Bull / Bear / Sideways / High-Vol. Used to modulate position sizing and factor weights.': '四状态 HMM 用于识别市场状态：牛市 / 熊市 / 震荡 / 高波动，用于调节仓位规模和因子权重。',
  'Graph-based model encoding sector correlations and supply chain relationships. Powers P2 decision engine for position allocation.': '图结构模型编码板块相关性和供应链关系，为 P2 决策引擎提供仓位分配能力。',
  'LinUCB bandit selecting execution strategy (aggressive / neutral / passive) conditioned on regime, liquidity, and urgency.': 'LinUCB 上下文老虎机根据市场状态、流动性和紧迫度选择执行策略（激进 / 中性 / 被动）。',
  'Engle-Granger cointegration scanner across ESG peer groups. Identifies mean-reverting pairs for market-neutral positions.': '基于 Engle-Granger 的协整扫描器覆盖 ESG 同业分组，用于识别适合市场中性的均值回归配对。',
  '9-factor model: Market, Size, Value, Momentum, Quality, Low-Vol, ESG Environmental, ESG Social, ESG Governance. Barra-style.': '九因子模型：市场、规模、价值、动量、质量、低波、ESG 环境、ESG 社会、ESG 治理，采用 Barra 风格框架。',
  'Fine-tuned FinBERT on ESG news, earnings calls, and regulatory filings. Generates sentiment scores fed into Alpha Ranker as features.': '在 ESG 新闻、业绩电话会和监管文件上微调的 FinBERT，会生成情绪分数作为 Alpha 排序器的输入特征。',
  'Classic 12-1 month cross-sectional momentum with ESG screening. Avoids ESG laggards in top-decile selection.': '经典 12-1 月横截面动量策略叠加 ESG 筛选，在高分位选股时规避 ESG 落后者。',
  'Deep Learning': '深度学习',
  'Overlay': '叠加层',
  'Cross-Sectional Momentum': '横截面动量',
  'Tesla, Inc.': '特斯拉',
  'Ford Motor': '福特汽车',
  'vs This': '相对本公司',
  'ESG News Feed': 'ESG 新闻流',
  'Price / OHLCV': '价格 / OHLCV',
  'Company Snapshots': '公司快照',
  'SEC Filings': 'SEC 文件',
  'Macro Indicators': '宏观指标',
  'Alternative Data': '另类数据',
  'price_data: 8,412,300 records refreshed': 'price_data：已刷新 8,412,300 条记录',
  'esg_news: 142 new articles ingested': 'esg_news：已接入 142 篇新文章',
  'sentiment_nlp: batch scored 89 documents': 'sentiment_nlp：已批量评分 89 份文档',
  'alt_data: connector timeout, retrying…': 'alt_data：连接器超时，正在重试…',
  'company_snapshots: TSLA, MSFT, NVDA refreshed': 'company_snapshots：已刷新 TSLA、MSFT、NVDA',
  'macro_indicators: 12 series updated': 'macro_indicators：已更新 12 条序列',

  // Backtest
  'Backtest Engine': '回测引擎',
  'Strategy Validation Lab · Equity Curve · Risk Attribution · Monthly Returns': '策略验证实验室 · 净值曲线 · 风险归因 · 月度收益',
  'Run Backtest': '运行回测',
  'Configure strategy parameters': '配置策略参数',
  'Strategy Name': '策略名称',
  'Lookback (trading days)': '回看窗口（交易日）',
  'ADVANCED SETTINGS': '高级设置',
  'Slippage Model': '滑点模型',
  'Market Impact': '市场冲击',
  'Custom bps': '自定义 bps',
  'Position Sizing': '仓位分配',
  'Equal Weight': '等权重',
  'Vol-Scaled': '波动率缩放',
  'Kelly Criterion': '凯利准则',
  'Rebalance Frequency': '再平衡频率',
  'Signal-Triggered': '信号触发',
  'Stop Loss per Position': '单持仓止损',
  '▶ Run Backtest': '▶ 运行回测',
  'Recent Backtests': '最近回测',
  'Equity Curve': '净值曲线',
  Portfolio: '组合',
  'Monthly Returns Heatmap': '月度收益热力图',
  Year: '年份',
  'Run a backtest': '运行一次回测',
  'Configure strategy parameters and click Run to see equity curve, Sharpe ratio, drawdown, and full risk attribution.': '配置参数并点击运行，即可查看净值曲线、夏普比率、回撤和完整风险归因。',
  'No backtests yet': '暂无回测记录',
  'Load failed': '加载失败',
  'Could not load history': '无法加载历史记录',
  'Backtest complete': '回测完成',
  'Backtest failed': '回测失败',
  'Annual Return': '年化收益',
  'Sharpe Ratio': '夏普比率',
  'Max Drawdown': '最大回撤',
  'Win Rate': '胜率',
  Sortino: '索提诺',
  Calmar: '卡玛比率',
  Strategy: '策略',
  Period: '区间',
  'Cum. Return': '累计收益',
  'Ann. Volatility': '年化波动率',
  Beta: '贝塔',
  'Info. Ratio': '信息比率',
  'CVaR 95%': 'CVaR 95%',
  'No risk alerts — strategy looks healthy.': '暂无风险告警，策略状态良好。',

  // Validation
  'Alpha Validation': 'Alpha 验证',
  'Walk-Forward Testing · Overfit Detection · Strategy Robustness Lab': '滚动前瞻测试 · 过拟合检测 · 策略稳健性实验室',
  'Walk-Forward Validation': '滚动前瞻验证',
  'Overfit detection · Cost sensitivity': '过拟合检测 · 成本敏感性',
  'In-Sample Days': '样本内天数',
  'Out-of-Sample Days': '样本外天数',
  'Walk-Forward Windows': '滚动窗口数',
  'ADVANCED VALIDATION OPTIONS': '高级验证选项',
  'Deflated Sharpe Threshold': '折损夏普阈值',
  'Multiple Testing Correction': '多重检验修正',
  Bonferroni: 'Bonferroni',
  'Benjamini-Hochberg': 'Benjamini-Hochberg',
  '▶ Run Validation': '▶ 运行验证',
  'Validation History': '验证历史',
  'No prior validations': '暂无历史验证',
  'Run walk-forward validation': '运行滚动前瞻验证',
  'Configure parameters and run to get GO/NO-GO verdict, walk-forward chart, and overfit analysis.': '配置参数并运行后，可获得通过/不通过结论、滚动图表和过拟合分析。',
  '● Validating…': '● 验证中…',
  'Validation complete': '验证完成',
  'Validation API error': '验证接口错误',
  'GO — STRATEGY IS ROBUST': '通过 — 策略较稳健',
  'NO-GO — OVERFIT DETECTED': '不通过 — 检测到过拟合',
  'OOS SHARPE': '样本外夏普',
  'PASS — Above 1.0 threshold': '通过 — 高于 1.0 阈值',
  'FAIL — Below 1.0 threshold': '失败 — 低于 1.0 阈值',
  'OVERFIT SCORE': '过拟合评分',
  'PASS — Low overfit risk': '通过 — 过拟合风险低',
  WARNING: '警告',
  'FAIL — High overfit': '失败 — 过拟合风险高',
  'COST DRAG': '成本拖累',
  'FILL PROB': '成交概率',
  'HIGH — Liquid universe': '高 — 股票池流动性充足',
  MEDIUM: '中等',
  LOW: '低',
  'Walk-Forward Performance': '滚动前瞻表现',
  'Regime Performance Analysis': '市场状态表现分析',
  Regime: '市场状态',
  Periods: '时期数',
  'Avg Return': '平均收益',
  '📊 Export Validation Report': '📊 导出验证报告',
  '→ Approve for Execution': '→ 批准执行',
  'Strategy demonstrates robustness across walk-forward windows. OOS Sharpe remains above 1.0.': '策略在滚动窗口中表现稳健，样本外夏普维持在 1.0 以上。',
  'Robust Zone': '稳健区间',
  'IS Sharpe': '样本内夏普',
  'OOS Sharpe': '样本外夏普',

  // Execution
  'EXECUTION MONITOR': '执行监控',
  DISCONNECTED: '已断开',
  'Alpaca Paper · NYSE': 'Alpaca 模拟盘 · NYSE',
  '⚠ KILL SWITCH': '⚠ 熔断开关',
  'Submit Execution Plan': '提交执行计划',
  'Alpaca Paper Trading': 'Alpaca 模拟交易',
  Broker: '券商',
  'Submit Orders to Broker': '提交订单到券商',
  '▶ Run Execution Plan': '▶ 运行执行计划',
  '⚠ Emergency Controls': '⚠ 紧急控制',
  'Kill switch immediately cancels all pending orders and halts new submissions for the current execution plan.': '熔断开关会立即取消所有待处理订单，并停止当前执行计划的新订单提交。',
  '☠ ARM KILL SWITCH': '☠ 启用熔断开关',
  '⚠ CONFIRM TO HALT ALL TRADING': '⚠ 确认停止全部交易',
  '⚡ CONFIRM KILL': '⚡ 确认熔断',
  'KILL SWITCH ACTIVATED': '熔断开关已触发',
  'All orders cancelled · No new orders': '所有订单已取消 · 不再提交新订单',
  'Live Positions': '实时持仓',
  'Order Stream': '订单流',
  'Loading orders…': '订单加载中…',
  'Live Feed': '实时流',
  'connecting…': '连接中…',
  'Waiting for events…': '等待事件中…',
  'Kill switch activated': '熔断开关已触发',
  'Kill switch failed': '熔断开关触发失败',
  '⚠ ARMED — confirm below': '⚠ 已激活，请在下方确认',
  Submitting: '提交中',
  'Submitting…': '提交中…',
  'Execution plan submitted': '执行计划已提交',
  'Execution failed': '执行失败',
  'Could not load orders': '无法加载订单',
  'No orders': '暂无订单',
  'Submit an execution plan to see orders here.': '提交执行计划后，订单会显示在这里。',
  Symbol: '代码',
  'Fill $': '成交价 $',
  'Limit $': '限价 $',
  'No open positions': '暂无持仓',
  LIVE: '实时',
  live: '实时',
  disconnected: '已断开',

  // Chat
  'Research Chat': '研究对话',
  'ESG Alpha Agent · Multi-turn Analysis · Context-Aware Reasoning': 'ESG Alpha 智能体 · 多轮分析 · 上下文推理',
  '+ New Session': '+ 新会话',
  SESSIONS: '会话',
  'LIVE CONTEXT': '实时上下文',
  'QUICK PROMPTS': '快捷问题',
  'ESG Alpha Research Agent': 'ESG Alpha 研究智能体',
  'Context-aware': '上下文感知',
  'Multi-turn': '多轮',
  ONLINE: '在线',
  'Ask about a stock, factor, sector, regime, or signal rationale… (Ctrl+Enter to send)': '询问股票、因子、板块、市场状态或信号逻辑…（Ctrl+Enter 发送）',
  'Ctrl+↵ to send': 'Ctrl+↵ 发送',
  '▶ Send': '▶ 发送',
  'New session started': '已创建新会话',
  'Enter a question first': '请先输入问题',
  '● Thinking…': '● 思考中…',
  'Start a conversation': '开始一段对话',
  'Ask about stocks, signals, sectors, or strategy rationale.': '可以询问股票、信号、板块或策略逻辑。',
  MOCK: '模拟',
  WELCOME: '欢迎',
  YOU: '你',
  'Why is NVDA ranked highly in the current ESG stack?': '为什么 NVDA 在当前 ESG 堆栈中排名靠前？',
  'Compare ESG scores for MSFT vs AAPL vs GOOGL': '比较 MSFT、AAPL 和 GOOGL 的 ESG 评分',
  "What factors are driving today's top alpha signals?": '哪些因子正在驱动今日最强 Alpha 信号？',
  'Explain the current regime classification and its impact': '解释当前市场状态分类及其影响',
  'Which sectors have the best ESG momentum right now?': '目前哪些板块的 ESG 动量最好？',
  'What is the overfit risk of the current strategy?': '当前策略的过拟合风险如何？',
  'Research Analysis': '研究分析',
  'Active Portfolio': '当前组合',
  'P1 Signals': 'P1 信号',
  'Top Signal': '顶部信号',
  Universe: '股票池',
  'Last Update': '最后更新',
  'Session ID': '会话 ID',

  // Score dashboard
  'ESG Score Dashboard': 'ESG 评分看板',
  'Environmental · Social · Governance · Peer Comparison · Trend Analysis': '环境 · 社会 · 治理 · 同业对比 · 趋势分析',
  '⬇ Export Report': '⬇ 导出报告',
  'Score Company': '评分公司',
  'ESG agent · Peer benchmark · Trend': 'ESG 智能体 · 同业基准 · 趋势',
  'Company Name': '公司名称',
  'Peer Companies (for benchmark)': '同业公司（用于基准）',
  'Analysis Depth': '分析深度',
  'Standard (E+S+G)': '标准（E+S+G）',
  'Deep (All sub-dimensions)': '深度（全部子维度）',
  'Quick Score': '快速评分',
  '▶ Run ESG Score': '▶ 运行 ESG 评分',
  'Score Trend (12mo)': '评分趋势（12个月）',
  'Quick Compare': '快速对比',
  OVERALL: '总分',
  'Multi-Dimension Radar': '多维雷达图',
  'Export Report': '导出报告',
  Export: '导出',
  'PDF export not yet connected': 'PDF 导出尚未接通',
  '● Scoring…': '● 评分中…',
  'ESG scoring complete': 'ESG 评分完成',
  Equity: '股票',
  Environment: '环境',
  Social: '社会',
  Governance: '治理',
  'Carbon emissions, energy efficiency, water usage, waste management, clean energy transition.': '碳排放、能效、用水、废弃物管理和清洁能源转型。',
  'Labor practices, workplace safety, diversity & inclusion, community impact, human rights.': '劳工实践、工作安全、多元包容、社区影响和人权。',
  'Board independence, executive pay alignment, audit quality, shareholder rights, transparency.': '董事会独立性、高管薪酬一致性、审计质量、股东权利与透明度。',
  'Carbon Intensity': '碳强度',
  'Renewable Energy %': '可再生能源占比',
  'Water Efficiency': '用水效率',
  'Waste Reduction': '废弃物减量',
  'Climate Risk': '气候风险',
  'Workforce Diversity': '员工多样性',
  'Safety Record': '安全记录',
  'Community Score': '社区评分',
  'Supply Chain Ethics': '供应链伦理',
  'Employee Wellbeing': '员工福祉',
  'Board Independence': '董事会独立性',
  'CEO Pay Ratio': 'CEO 薪酬比',
  'Audit Quality': '审计质量',
  'Shareholder Rights': '股东权利',
  'Anti-corruption': '反腐败',
  Disclosure: '披露',
  Innovation: '创新',
  ENVIRON: '环境',
  GOVERN: '治理',
  '— (this)': '—（本公司）',

  // Portfolio
  'Step 3 — Portfolio Constraints & Risk Parameters': '步骤 3 — 组合约束与风险参数',
  'Position Constraints': '持仓约束',
  'Max position weight': '单持仓上限',
  'Max sector concentration': '板块集中度上限',
  'Optimization Method': '优化方法',
  'Maximum Diversification': '最大分散化',
  'Minimize correlation between holdings': '最小化持仓之间的相关性',
  'Risk Parity': '风险平价',
  'Equal risk contribution — Recommended': '等风险贡献 — 推荐',
  'Minimum Variance': '最小方差',
  'Lowest possible volatility': '尽可能低的波动率',
  'Maximum Sharpe': '最大夏普',
  'Best risk-adjusted return': '最佳风险调整后收益',
  'Simple 1/N allocation': '简单 1/N 配置',
  'ESG Constraints': 'ESG 约束',
  'Min portfolio ESG score': '组合最低 ESG 评分',
  'Exclude Weapons': '排除武器',
  'Exclude Tobacco': '排除烟草',
  'Exclude Gambling': '排除博彩',
  'Exclude Fossil Fuels': '排除化石燃料',
  'Exclude Private Prisons': '排除私营监狱',
  'Next: Optimize →': '下一步：优化 →',
  'Step 4 — Efficient Frontier Analysis': '步骤 4 — 有效前沿分析',
  '⚡ Optimize Now': '⚡ 立即优化',
  'Efficient Frontier · Risk/Return Tradeoff': '有效前沿 · 风险/收益权衡',
  'Suggested Portfolios': '建议组合',
  'Click Optimize to see suggestions': '点击优化后查看建议',
  'Selected Portfolio — Holdings': '已选组合 — 持仓',
  'Review Portfolio →': '复核组合 →',
  'Step 5 — Portfolio Review & Execution Preparation': '步骤 5 — 组合复核与执行准备',
  Optimizing: '优化中',
  'Optimizing…': '优化中…',
  'Optimization complete': '优化完成',
  'Conservative Blend': '保守组合',
  '★ Optimal Sharpe': '★ 最优夏普',
  'Aggressive Growth': '激进成长',
  Return: '收益',
  Vol: '波动',
  MaxDD: '最大回撤',
  'Top:': '前列：',
  'Select This': '选择该组合',
  'Run optimization first (Step 4)': '请先完成优化（步骤 4）',
  'I acknowledge the investment risks and confirm this portfolio is suitable for my risk profile.': '我已知晓投资风险，并确认该组合适合我的风险承受能力。',
  '📊 Export CSV': '📊 导出 CSV',
  '→ Send to Execution Monitor': '→ 发送到执行监控',
  'Acknowledgment required': '需要确认',
  'Please confirm the risk disclosure': '请确认风险披露',
  Weight: '权重',
  '★ Max Sharpe': '★ 最大夏普',
  '◆ Min Var': '◆ 最小方差',

  // Data management
  'Data Management': '数据管理',
  'Pipeline Monitor · Data Freshness · Sync Control · Ingestion Logs': '管线监控 · 数据新鲜度 · 同步控制 · 接入日志',
  '↺ Refresh All': '↺ 全部刷新',
  'Data Pipeline': '数据管线',
  'ALL SYSTEMS NOMINAL': '系统运行正常',
  'Sync Control': '同步控制',
  'Trigger company snapshot refresh': '触发公司快照刷新',
  'Data Sources': '数据源',
  'All Sources': '全部数据源',
  'Price Data': '价格数据',
  Sentiment: '情绪',
  'Force Refresh': '强制刷新',
  Priority: '优先级',
  '▶ Start Sync': '▶ 开始同步',
  'Active Jobs': '活动任务',
  'No active sync jobs': '暂无活动同步任务',
  'Ingestion Log': '接入日志',
  'Live Feeds': '实时数据源',
  'Avg Freshness': '平均新鲜度',
  'Records Today': '今日记录数',
  Alerts: '告警',
  'Data Source Freshness': '数据源新鲜度',
  'Ingestion Throughput (24h)': '接入吞吐量（24小时）',
  'Raw Ingestion': '原始接入',
  'Data Cleaning': '数据清洗',
  'ESG Enrichment': 'ESG 增强',
  'Feature Store': '特征库',
  'Model Input': '模型输入',
  'Signal Output': '信号输出',
  Stream: '流式',
  Batch: '批处理',
  Event: '事件',
  lag: '延迟',
  Sync: '同步',
  'Sync triggered': '已触发同步',
  'Data sources refreshed': '数据源已刷新',
  'Log cleared.': '日志已清空。',
  '● Starting…': '● 启动中…',
  'Sync started': '同步已开始',
  'Sync complete': '同步完成',
  'running mock sync': '正在运行模拟同步',

  // Reports
  'Report Center': '报告中心',
  'Generate · Schedule · Archive · Export ESG Research Reports': '生成 · 定时 · 归档 · 导出 ESG 研究报告',
  '⏰ Schedule': '⏰ 定时',
  '⬇ Download': '⬇ 下载',
  'Generate Report': '生成报告',
  'Choose type, scope and options': '选择类型、范围和选项',
  'Daily Digest': '每日日报',
  'Weekly Summary': '每周总结',
  'Monthly Deep-Dive': '每月深度分析',
  'Ad-Hoc Analysis': '临时分析',
  'Top signals, score updates, alerts': '顶部信号、评分更新、告警',
  'Portfolio review, ESG movers, attribution': '组合复盘、ESG 变动、归因',
  'Full factor analysis, peer benchmarks, forecasts': '完整因子分析、同业基准、预测',
  'Custom companies, custom period': '自定义公司、自定义区间',
  'Start Date': '开始日期',
  'End Date': '结束日期',
  'Sections to Include': '包含章节',
  'Factor Analysis': '因子分析',
  Signals: '信号',
  Forecasts: '预测',
  '▶ Generate': '▶ 生成',
  'Load Latest': '加载最新',
  'Report Archive': '报告归档',
  'No report loaded': '尚未加载报告',
  'Generate a new report or click an archive entry to load.': '生成新报告，或点击归档记录进行加载。',
  Scheduling: '定时中',
  'Report scheduler coming soon': '报告定时功能即将上线',
  Download: '下载',
  'Select a report first': '请先选择报告',
  'PDF Export': 'PDF 导出',
  'Generating PDF…': 'PDF 生成中…',
  'CSV Export': 'CSV 导出',
  'Downloading CSV…': 'CSV 下载中…',
  'JSON Export': 'JSON 导出',
  'Downloading JSON…': 'JSON 下载中…',
  '● Generating…': '● 生成中…',
  'Report generated': '报告已生成',
  'No report found': '未找到报告',
  'showing mock report': '显示模拟报告',
  'showing mock': '显示模拟数据',
  'EXECUTIVE SUMMARY': '执行摘要',
  'COMPANY ESG SCORECARD': '公司 ESG 评分卡',
  Signal: '信号',
  'TOP SIGNALS': '顶部信号',

  // Push rules / subscriptions
  'Push Rules': '推送规则',
  'Configure notification rules and test routing conditions': '配置通知规则并测试路由条件',
  'Create Rule': '创建规则',
  'Matches against report payloads': '匹配报告载荷内容',
  Condition: '条件',
  'Existing Rules': '现有规则',
  'Creating...': '创建中...',
  'Push rule created': '推送规则已创建',
  'Rule creation failed': '规则创建失败',
  'No push rules configured.': '暂无推送规则。',
  'Rule tested': '规则测试完成',
  Matched: '已匹配',
  'Did not match': '未匹配',
  'Rule test failed': '规则测试失败',
  'Rule deleted': '规则已删除',
  'Delete failed': '删除失败',

  Subscriptions: '订阅',
  'Manage report subscriptions for the current user': '管理当前用户的报告订阅',
  'Create Subscription': '创建订阅',
  'Subscribe to report delivery with channel preferences': '订阅报告分发并设置渠道偏好',
  'Report Types': '报告类型',
  Companies: '公司',
  'ESG Alert Threshold': 'ESG 告警阈值',
  'Create Subscription': '创建订阅',
  'Current Subscriptions': '当前订阅',
  'Subscription created': '订阅已创建',
  'Subscription failed': '订阅创建失败',
  'Create Subscription': '创建订阅',
  'No subscriptions found.': '未找到订阅。',
  Subscription: '订阅',
  'Subscription deleted': '订阅已删除',

  // Models additional
  'XGBoost Ensemble': 'XGBoost 集成',
  'Recurrent Neural Network': '循环神经网络',
  'Hidden Markov Model': '隐马尔可夫模型',
  'Graph Neural Network': '图神经网络',
  'Reinforcement Learning': '强化学习',
  'Cointegration Engine': '协整引擎',
  'Risk Factor Model': '风险因子模型',
  'Transformer (FinBERT)': 'Transformer（FinBERT）',
  'Could not load experiments': '无法加载实验记录',
  '▶ Run in Backtest': '▶ 在回测中运行',
  '⬇ Export Config': '⬇ 导出配置',
};

const AUTO_PLACEHOLDER_ZH = {
  'AAPL, MSFT… (blank = default)': 'AAPL, MSFT…（留空使用默认）',
  'e.g. 8%': '例如 8%',
  'Tesla\nMicrosoft\nNVIDIA': 'Tesla\nMicrosoft\nNVIDIA',
  'Tesla, Apple, NVDA…': 'Tesla、Apple、NVDA…',
  'F, GM, NIO (auto-fill on ticker)': 'F、GM、NIO（根据代码自动填充）',
  'Search models…': '搜索模型…',
  'Search ticker or company…': '搜索代码或公司…',
  'Session ID': '会话 ID',
  'AAPL, MSFT, GOOGL…': 'AAPL、MSFT、GOOGL…',
  'AAPL, MSFT, NVDA… (blank = use preset)': 'AAPL、MSFT、NVDA…（留空使用预设）',
};

const AUTO_REGEX_ZH = [
  [/^(\d+)\s+orders$/, (_, n) => `${n} 笔订单`],
  [/^(\d+)\s+Signals Generated$/, (_, n) => `${n} 条信号已生成`],
  [/^(\d+)\s+signals$/, (_, n) => `${n} 条信号`],
  [/^Sharpe\s+(.+)$/, (_, v) => `夏普 ${v}`],
  [/^Sharpe:\s*(.+)$/, (_, v) => `夏普：${v}`],
  [/^Updated:\s*(.+)$/, (_, v) => `更新时间：${v}`],
  [/^Generated:\s*(.+)$/, (_, v) => `生成时间：${v}`],
  [/^Verdict:\s*(.+)$/, (_, v) => `结论：${v}`],
  [/^Top\s+(\d+)th percentile in industry$/, (_, n) => `行业前 ${n} 百分位`],
  [/^Breakeven at ~(\d+)bps$/, (_, n) => `盈亏平衡约为 ${n} bps`],
  [/^(\d+)\s+warning$/, (_, n) => `${n} 条告警`],
  [/^(\d+)\s+decisions$/, (_, n) => `${n} 个决策`],
  [/^(\d+)\s+runs$/, (_, n) => `${n} 次运行`],
  [/^(\d+)\s+alerts$/, (_, n) => `${n} 条告警`],
  [/^(\d+)\s+active$/, (_, n) => `${n} 条活跃`],
  [/^(.+)\s+ago$/, (_, v) => `${v} 前`],
  [/^lag\s+(.+)$/, (_, v) => `延迟 ${v}`],
  [/^Session:\s*(.+?)\s+·\s+Context-aware\s+·\s+Multi-turn$/, (_, v) => `会话：${v} · 上下文感知 · 多轮`],
  [/^(.+)\s+shares$/, (_, v) => `${v} 股`],
  [/^Top:\s*(.+)$/, (_, v) => `前列：${v}`],
  [/^✓\s+Done\s+·\s+(\d+)\s+signals\s+generated$/, (_, n) => `✓ 完成 · 已生成 ${n} 条信号`],
  [/^✓\s+Done\s+·\s+(\d+)\s+decisions$/, (_, n) => `✓ 完成 · ${n} 个决策`],
  [/^(\d+)\s+companies refreshed$/, (_, n) => `已刷新 ${n} 家公司`],
];

const AUTO_REGEX_EN = [
  [/^(\d+)\s+笔订单$/, (_, n) => `${n} orders`],
  [/^(\d+)\s+条信号已生成$/, (_, n) => `${n} Signals Generated`],
  [/^夏普\s+(.+)$/, (_, v) => `Sharpe ${v}`],
  [/^夏普：\s*(.+)$/, (_, v) => `Sharpe: ${v}`],
  [/^更新时间：\s*(.+)$/, (_, v) => `Updated: ${v}`],
  [/^生成时间：\s*(.+)$/, (_, v) => `Generated: ${v}`],
  [/^结论：\s*(.+)$/, (_, v) => `Verdict: ${v}`],
  [/^行业前\s+(\d+)\s+百分位$/, (_, n) => `Top ${n}th percentile in industry`],
  [/^盈亏平衡约为\s+(\d+)\s+bps$/, (_, n) => `Breakeven at ~${n}bps`],
  [/^(\d+)\s+条告警$/, (_, n) => `${n} alerts`],
  [/^(\d+)\s+条活跃$/, (_, n) => `${n} active`],
  [/^(.+)\s+前$/, (_, v) => `${v} ago`],
  [/^延迟\s+(.+)$/, (_, v) => `lag ${v}`],
  [/^会话：\s*(.+?)\s+·\s+上下文感知\s+·\s+多轮$/, (_, v) => `Session: ${v} · Context-aware · Multi-turn`],
  [/^(.+)\s+股$/, (_, v) => `${v} shares`],
  [/^前列：\s*(.+)$/, (_, v) => `Top: ${v}`],
  [/^✓\s+完成\s+·\s+已生成\s+(\d+)\s+条信号$/, (_, n) => `✓ Done · ${n} signals generated`],
  [/^✓\s+完成\s+·\s+(\d+)\s+个决策$/, (_, n) => `✓ Done · ${n} decisions`],
  [/^已刷新\s+(\d+)\s+家公司$/, (_, n) => `${n} companies refreshed`],
];

let _applying = false;
let _observer = null;

let _lang = localStorage.getItem('qt-lang') || 'zh';
document.documentElement.setAttribute('lang', _lang);

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
  localStorage.setItem('qt-lang', lang);
  document.documentElement.setAttribute('lang', lang);
  window.dispatchEvent(new CustomEvent('lang-change', { detail: { lang } }));
  applyLangToPage();
}

export function t(key) {
  return (STRINGS[_lang] && STRINGS[_lang][key]) || key;
}

export function onLangChange(fn) {
  const handler = (e) => fn(e.detail.lang);
  window.addEventListener('lang-change', handler);
  return () => window.removeEventListener('lang-change', handler);
}

const AUTO_TEXT_EN = Object.fromEntries(
  Object.entries(AUTO_TEXT_ZH).map(([en, zh]) => [zh, en]),
);

const AUTO_PLACEHOLDER_EN = Object.fromEntries(
  Object.entries(AUTO_PLACEHOLDER_ZH).map(([en, zh]) => [zh, en]),
);

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

  if (_lang === 'zh') {
    if (directMap[trimmed]) {
      return preserveOuterWhitespace(source, directMap[trimmed]);
    }

    for (const [pattern, replacer] of AUTO_REGEX_ZH) {
      if (pattern.test(trimmed)) {
        return preserveOuterWhitespace(source, trimmed.replace(pattern, replacer));
      }
    }

    return source;
  }

  if (reverseMap[trimmed]) {
    return preserveOuterWhitespace(source, reverseMap[trimmed]);
  }

  for (const [pattern, replacer] of AUTO_REGEX_EN) {
    if (pattern.test(trimmed)) {
      return preserveOuterWhitespace(source, trimmed.replace(pattern, replacer));
    }
  }

  return source;
}

function getStoredAttrSources(el) {
  if (!ATTR_SOURCES.has(el)) {
    ATTR_SOURCES.set(el, {});
  }

  return ATTR_SOURCES.get(el);
}

function shouldSkipTextNode(node) {
  const parent = node?.parentElement;
  if (!parent) return true;
  if (parent.closest('[data-i18n]')) return true;
  if (parent.closest('[data-no-autotranslate="true"]')) return true;

  const tagName = parent.tagName;
  return tagName === 'SCRIPT' || tagName === 'STYLE' || tagName === 'TEXTAREA';
}

function translateTextNode(node) {
  if (!node || shouldSkipTextNode(node)) return;

  const current = node.textContent;
  if (!normalizeLooseText(current)) return;

  const stored = TEXT_NODE_SOURCES.get(node);
  if (stored) {
    const currentTranslation = translateLoose(stored, 'text');
    if (current !== stored && current !== currentTranslation) {
      TEXT_NODE_SOURCES.set(node, current);
    }
  } else {
    TEXT_NODE_SOURCES.set(node, current);
  }

  const source = TEXT_NODE_SOURCES.get(node);
  const translated = translateLoose(source, 'text');
  if (translated !== current) {
    node.textContent = translated;
  }
}

function shouldSkipAttribute(el, attr) {
  if (!el) return true;
  if (el.closest('[data-no-autotranslate="true"]')) return true;
  if (attr === 'placeholder' && el.hasAttribute('data-i18n-placeholder')) return true;
  if (attr === 'title' && el.hasAttribute('data-i18n-title')) return true;
  if (attr === 'value' && el.tagName !== 'INPUT') return true;

  return false;
}

function translateAttribute(el, attr, kind = 'text') {
  if (!el || shouldSkipAttribute(el, attr) || !el.hasAttribute(attr)) return;

  const current = el.getAttribute(attr);
  if (!normalizeLooseText(current)) return;

  const sources = getStoredAttrSources(el);
  const stored = sources[attr];
  if (stored) {
    const currentTranslation = translateLoose(stored, kind);
    if (current !== stored && current !== currentTranslation) {
      sources[attr] = current;
    }
  } else {
    sources[attr] = current;
  }

  const translated = translateLoose(sources[attr], kind);
  if (translated !== current) {
    el.setAttribute(attr, translated);
  }
}

function autoTranslate(root = document) {
  const target = root?.nodeType === Node.TEXT_NODE ? root.parentNode : root;
  if (!target) return;

  if (root?.nodeType === Node.TEXT_NODE) {
    translateTextNode(root);
  }

  const walker = document.createTreeWalker(target, NodeFilter.SHOW_TEXT);
  let textNode = walker.nextNode();
  while (textNode) {
    translateTextNode(textNode);
    textNode = walker.nextNode();
  }

  const elements = target.querySelectorAll ? [target, ...target.querySelectorAll('*')] : [];
  elements.forEach((el) => {
    if (!(el instanceof Element)) return;
    translateAttribute(el, 'placeholder', 'placeholder');
    translateAttribute(el, 'title', 'text');

    if (el.tagName === 'INPUT') {
      const type = (el.getAttribute('type') || '').toLowerCase();
      if (['button', 'submit', 'reset'].includes(type)) {
        translateAttribute(el, 'value', 'text');
      }
    }
  });
}

export function applyLangToPage(root = document) {
  _applying = true;
  try {
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

    autoTranslate(root);
  } finally {
    _applying = false;
  }
}

function ensureObserver() {
  if (_observer) return;

  _observer = new MutationObserver((mutations) => {
    if (_applying) return;

    for (const mutation of mutations) {
      if (mutation.type === 'childList') {
        mutation.addedNodes.forEach((node) => {
          if (node.nodeType === Node.TEXT_NODE) {
            applyLangToPage(node);
          } else if (node.nodeType === Node.ELEMENT_NODE) {
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

applyLangToPage();
ensureObserver();
