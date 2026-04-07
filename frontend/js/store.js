/**
 * ESG Copilot - 响应式状态管理
 * 基于 EventTarget 模式的轻量级状态库
 */

class Store extends EventTarget {
  constructor() {
    super();

    this.#state = {
      // 当前会话
      currentSession: null,

      // 聊天消息列表
      chatMessages: [],  // { role, content, esg_scores?, timestamp }

      // 当前 ESG 评分报告
      currentESGReport: null,

      // 报告列表
      reports: [],
      reportDetails: {},  // report_id -> report object

      // 同步任务追踪
      syncJobs: {},  // job_id -> { status, progress, ... }

      // 推送规则
      pushRules: [],

      // 用户订阅
      subscriptions: [],

      // 系统状态
      healthStatus: null,  // { status: 'online'/'offline' }

      // 加载状态 (按功能)
      isLoading: {},  // key -> boolean

      // 错误状态
      errors: {},  // key -> error message
    };
  }

  #state;

  /**
   * 获取状态值
   * @param {string} key
   * @returns {any}
   */
  get(key) {
    return this.#state[key];
  }

  /**
   * 设置状态值并触发 change 事件
   * @param {string} key
   * @param {any} value
   */
  set(key, value) {
    const oldValue = this.#state[key];

    // 对象的深度比较（简化实现）
    if (JSON.stringify(oldValue) === JSON.stringify(value)) {
      return; // 值未变，不触发事件
    }

    this.#state[key] = value;

    // 触发 change 事件
    this.dispatchEvent(new CustomEvent('change', {
      detail: {
        key,
        value,
        oldValue,
      }
    }));
  }

  /**
   * 获取整个状态快照
   * @returns {Object}
   */
  getState() {
    return JSON.parse(JSON.stringify(this.#state));
  }

  /**
   * 重置状态
   */
  reset() {
    this.#state = {
      currentSession: null,
      chatMessages: [],
      currentESGReport: null,
      reports: [],
      reportDetails: {},
      syncJobs: {},
      pushRules: [],
      subscriptions: [],
      healthStatus: null,
      isLoading: {},
      errors: {},
    };
    this.dispatchEvent(new CustomEvent('reset'));
  }

  // ============================================
  // 便利方法
  // ============================================

  /**
   * 设置加载状态
   * @param {string} key
   * @param {boolean} isLoading
   */
  setLoading(key, isLoading) {
    const current = this.get('isLoading') || {};
    this.set('isLoading', { ...current, [key]: isLoading });
  }

  /**
   * 设置错误
   * @param {string} key
   * @param {string|null} error
   */
  setError(key, error) {
    const current = this.get('errors') || {};
    this.set('errors', { ...current, [key]: error });
  }

  /**
   * 清空错误
   * @param {string} key
   */
  clearError(key) {
    this.setError(key, null);
  }

  /**
   * 添加聊天消息
   * @param {{ role, content, esg_scores?, timestamp }} message
   */
  addMessage(message) {
    const messages = this.get('chatMessages') || [];
    const timestamp = message.timestamp || new Date().toISOString();
    this.set('chatMessages', [...messages, { ...message, timestamp }]);
  }

  /**
   * 清空聊天消息
   */
  clearMessages() {
    this.set('chatMessages', []);
  }

  /**
   * 设置当前报告
   * @param {Object} report
   */
  setCurrentReport(report) {
    this.set('currentESGReport', report);
  }

  /**
   * 添加或更新报告
   * @param {Object} report
   */
  upsertReport(report) {
    const reports = this.get('reports') || [];
    const existing = reports.findIndex(r => r.report_id === report.report_id);

    if (existing >= 0) {
      reports[existing] = report;
    } else {
      reports.unshift(report);  // 最新的在前
    }

    this.set('reports', [...reports]);
  }

  /**
   * 更新同步任务状态
   * @param {string} jobId
   * @param {Object} status
   */
  updateSyncJob(jobId, status) {
    const jobs = this.get('syncJobs') || {};
    jobs[jobId] = status;
    this.set('syncJobs', { ...jobs });
  }

  /**
   * 移除同步任务
   * @param {string} jobId
   */
  removeSyncJob(jobId) {
    const jobs = this.get('syncJobs') || {};
    delete jobs[jobId];
    this.set('syncJobs', { ...jobs });
  }

  /**
   * 更新推送规则列表
   * @param {Array} rules
   */
  setPushRules(rules) {
    this.set('pushRules', rules || []);
  }

  /**
   * 添加或更新推送规则
   * @param {Object} rule
   */
  upsertPushRule(rule) {
    const rules = this.get('pushRules') || [];
    const existing = rules.findIndex(r => r.id === rule.id);

    if (existing >= 0) {
      rules[existing] = rule;
    } else {
      rules.push(rule);
    }

    this.set('pushRules', [...rules]);
  }

  /**
   * 移除推送规则
   * @param {string} ruleId
   */
  removePushRule(ruleId) {
    const rules = (this.get('pushRules') || [])
      .filter(r => r.id !== ruleId);
    this.set('pushRules', rules);
  }

  /**
   * 更新订阅列表
   * @param {Array} subs
   */
  setSubscriptions(subs) {
    this.set('subscriptions', subs || []);
  }

  /**
   * 添加或更新订阅
   * @param {Object} sub
   */
  upsertSubscription(sub) {
    const subs = this.get('subscriptions') || [];
    const existing = subs.findIndex(s => s.subscription_id === sub.subscription_id);

    if (existing >= 0) {
      subs[existing] = sub;
    } else {
      subs.push(sub);
    }

    this.set('subscriptions', [...subs]);
  }

  /**
   * 移除订阅
   * @param {string} subscriptionId
   */
  removeSubscription(subscriptionId) {
    const subs = (this.get('subscriptions') || [])
      .filter(s => s.subscription_id !== subscriptionId);
    this.set('subscriptions', subs);
  }
}

// 全局单例
export const store = new Store();

export default store;
