# 多券商接入与实盘化清单

## 已接通
- `alpaca`
  - 当前状态：已真实打通 paper trading
  - 必填：
    - `ALPACA_API_KEY`
    - `ALPACA_API_SECRET`
  - 可选：
    - `ALPACA_PAPER_BASE_URL`

## 已搭好接入框架，待你获取 key
- `ibkr`
  - 当前状态：多券商抽象层已留口，适配器为 scaffolded
  - 建议准备：
    - `IBKR_GATEWAY_URL`
    - `IBKR_ACCOUNT_ID`
    - `IBKR_USERNAME`
    - `IBKR_PASSWORD`
    - `IBKR_PAPER_MODE`
    - `IBKR_VALIDATE_SSL`

- `tiger`
  - 当前状态：多券商抽象层已留口，适配器为 scaffolded
  - 建议准备：
    - `TIGER_ID`
    - `TIGER_ACCOUNT`
    - `TIGER_PRIVATE_KEY_PATH`
    - `TIGER_ACCESS_TOKEN`
    - `TIGER_REGION`
    - `TIGER_PAPER_MODE`

- `longbridge`
  - 当前状态：多券商抽象层已留口，适配器为 scaffolded
  - 建议准备：
    - `LONGBRIDGE_APP_KEY`
    - `LONGBRIDGE_APP_SECRET`
    - `LONGBRIDGE_ACCESS_TOKEN`
    - `LONGBRIDGE_REGION`
    - `LONGBRIDGE_PAPER_MODE`

## 新增的执行风控与运维配置
- `QUANT_BROKER_DEFAULT`
- `EXECUTION_REQUIRE_MARKET_OPEN`
- `EXECUTION_MAX_DAILY_ORDERS`
- `EXECUTION_MAX_NOTIONAL_PER_ORDER`
- `EXECUTION_MIN_BUYING_POWER_BUFFER`
- `EXECUTION_SINGLE_NAME_WEIGHT_CAP`
- `EXECUTION_DEFAULT_SLIPPAGE_BPS`
- `EXECUTION_DEFAULT_IMPACT_BPS`

## 新增的 API 鉴权与审计配置
- `EXECUTION_API_KEY`
- `ADMIN_API_KEY`
- `OPS_API_KEY`
- `AUTH_BEARER_ONLY`
- `AUDIT_LOG_ENABLED`
- `AUDIT_LOG_RETENTION_DAYS`
- `METRICS_PUBLIC`

## 当前已经具备的能力
- 统一 broker registry
- 执行计划、broker inventory、账户、订单、持仓接口
- 执行 journal / 状态机 / 撤单 / 重试
- walk-forward 验证、样本外指标、slippage / impact cost
- ops runtime / metrics
- 审计落盘
- CI 工作流
- Docker Compose 本地编排

## 仍属于外部依赖的部分
- IBKR / Tiger / Longbridge 真正的生产 key 与网关
- 远端 `REMOTE_LLM_URL` 服务常驻
- `QDRANT_URL` 服务常驻
- 更高真实性的行情、成交、盘口与微观结构数据
- 真实模型微调与 alpha 生产训练
