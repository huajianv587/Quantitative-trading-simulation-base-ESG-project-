/**
 * 前端错误码映射
 * 与后端错误码保持一致
 */

export const ErrorCodes = {
  // 1xxx: 认证授权错误
  ERR_AUTH_001: { message: '缺少API密钥', icon: 'lock', color: 'error' },
  ERR_AUTH_002: { message: '无效的API密钥', icon: 'lock', color: 'error' },
  ERR_AUTH_003: { message: '权限不足', icon: 'shield', color: 'error' },
  ERR_AUTH_004: { message: '认证令牌已过期', icon: 'clock', color: 'warning' },

  // 2xxx: 量化系统错误
  ERR_QUANT_001: { message: '量化系统未就绪', icon: 'alert-circle', color: 'warning' },
  ERR_QUANT_002: { message: '策略分析失败', icon: 'x-circle', color: 'error' },
  ERR_QUANT_003: { message: '策略不存在', icon: 'search', color: 'error' },
  ERR_QUANT_004: { message: '无效的策略参数', icon: 'alert-triangle', color: 'warning' },
  ERR_QUANT_005: { message: '回测执行失败', icon: 'x-circle', color: 'error' },
  ERR_QUANT_006: { message: '性能计算失败', icon: 'x-circle', color: 'error' },
  ERR_QUANT_007: { message: '策略代码格式错误', icon: 'code', color: 'warning' },
  ERR_QUANT_008: { message: '策略名称已存在', icon: 'alert-circle', color: 'warning' },

  // 3xxx: ESG系统错误
  ERR_ESG_001: { message: 'ESG数据加载失败', icon: 'database', color: 'error' },
  ERR_ESG_002: { message: 'ESG评分计算失败', icon: 'x-circle', color: 'error' },
  ERR_ESG_003: { message: 'ESG数据不存在', icon: 'search', color: 'error' },
  ERR_ESG_004: { message: '无效的ESG参数', icon: 'alert-triangle', color: 'warning' },
  ERR_ESG_005: { message: 'ESG指标聚合失败', icon: 'x-circle', color: 'error' },
  ERR_ESG_006: { message: 'ESG数据源不可用', icon: 'cloud-off', color: 'warning' },

  // 4xxx: 数据库错误
  ERR_DB_001: { message: '数据库查询失败', icon: 'database', color: 'error' },
  ERR_DB_002: { message: '数据库连接失败', icon: 'link-off', color: 'error' },
  ERR_DB_003: { message: '数据库写入失败', icon: 'save', color: 'error' },
  ERR_DB_004: { message: '记录不存在', icon: 'search', color: 'error' },
  ERR_DB_005: { message: '记录已存在', icon: 'alert-circle', color: 'warning' },
  ERR_DB_006: { message: '事务执行失败', icon: 'x-circle', color: 'error' },

  // 5xxx: 外部服务错误
  ERR_EXT_001: { message: '外部服务不可用', icon: 'cloud-off', color: 'warning' },
  ERR_EXT_002: { message: '外部服务超时', icon: 'clock', color: 'warning' },
  ERR_EXT_003: { message: '外部服务响应异常', icon: 'alert-triangle', color: 'error' },
  ERR_EXT_004: { message: '外部服务请求过多', icon: 'zap', color: 'warning' },
  ERR_EXT_005: { message: '外部服务网关错误', icon: 'server', color: 'error' },

  // 9xxx: 系统级错误
  ERR_SYS_001: { message: '后台任务执行失败', icon: 'x-circle', color: 'error' },
  ERR_SYS_002: { message: '任务执行超时', icon: 'clock', color: 'warning' },
  ERR_SYS_003: { message: '调度任务失败', icon: 'calendar', color: 'error' },
  ERR_SYS_004: { message: '系统内部错误', icon: 'alert-octagon', color: 'error' },
  ERR_SYS_005: { message: '无效的请求参数', icon: 'alert-triangle', color: 'warning' },
  ERR_SYS_006: { message: '数据验证失败', icon: 'check-circle', color: 'warning' },
  ERR_SYS_007: { message: '请求体过大', icon: 'file', color: 'warning' },
  ERR_SYS_008: { message: '不支持的媒体类型', icon: 'file-text', color: 'warning' },
};

/**
 * 获取错误码对应的用户友好消息
 * @param {string} code - 错误码
 * @param {string} fallbackMessage - 后备消息
 * @returns {object} - { message, icon, color }
 */
export function getErrorInfo(code, fallbackMessage) {
  var info = ErrorCodes[code];
  if (info) {
    return {
      message: info.message,
      icon: info.icon,
      color: info.color
    };
  }

  // HTTP错误码
  if (code && code.startsWith('HTTP_')) {
    var status = parseInt(code.replace('HTTP_', ''));
    if (status >= 400 && status < 500) {
      return {
        message: fallbackMessage || '请求错误',
        icon: 'alert-triangle',
        color: 'warning'
      };
    }
    if (status >= 500) {
      return {
        message: fallbackMessage || '服务器错误',
        icon: 'server',
        color: 'error'
      };
    }
  }

  // 默认
  return {
    message: fallbackMessage || '未知错误',
    icon: 'alert-circle',
    color: 'error'
  };
}

/**
 * 判断错误是否可重试
 * @param {object} error - 错误对象
 * @returns {boolean}
 */
export function isRetryable(error) {
  if (error && typeof error.retryable === 'boolean') {
    return error.retryable;
  }

  // 根据错误码判断
  var code = error && error.code;
  if (!code) return false;

  // 可重试的错误码
  var retryableCodes = [
    'ERR_QUANT_001', 'ERR_QUANT_002', 'ERR_QUANT_005', 'ERR_QUANT_006',
    'ERR_ESG_001', 'ERR_ESG_002', 'ERR_ESG_005', 'ERR_ESG_006',
    'ERR_DB_001', 'ERR_DB_002', 'ERR_DB_003', 'ERR_DB_006',
    'ERR_EXT_001', 'ERR_EXT_002', 'ERR_EXT_003', 'ERR_EXT_004', 'ERR_EXT_005',
    'ERR_SYS_001', 'ERR_SYS_002', 'ERR_SYS_003', 'ERR_SYS_004'
  ];

  return retryableCodes.indexOf(code) !== -1;
}
