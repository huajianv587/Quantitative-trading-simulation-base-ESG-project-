# Quant Terminal

Quant Terminal 是一个量化研究、Paper 交易、风控审批、数据治理、模型实验和报告运维一体化的网页端产品。当前默认支持本地/验收环境降级运行：缺少 Supabase、R2 或外部 API key 时，接口必须返回 `degraded` 或 `blocked`，并说明原因与下一步，不允许静态假成功。

## 启动

1. 复制环境变量：

```bash
cp .env.example .env
```

2. 安装依赖：

```bash
pip install -r requirements.txt
npm ci
```

3. 构建前端并启动 API：

```bash
npm run build:static
python -m gateway.main
```

默认网页入口：

```text
http://127.0.0.1:8012/app/
```

关键生产化页面：
- `/app/#/trading-safety`：交易安全中心，证明 Live 永不自动提交，Paper 提交必须通过门禁。
- `/app/#/automation-timeline`：自动分析/自动下单证据时间线。
- `/app/#/data-config-center`：数据源配置中心，展示 provider、API key 缺口、优先级、质量和 fallback。
- `/app/#/job-console`：长任务队列控制台，支持创建、取消、重试和查看日志。
- `/app/#/ops-health`：发布健康检查，汇总 Schema、Job、数据、交易安全和 E2E 验收状态。

## 运行模式

- `APP_MODE=local`：本地开发，缺 Supabase 时写入 `storage/quant/`。
- `APP_MODE=acceptance`：验收环境，建议设置 `ACCEPTANCE_NAMESPACE` 隔离测试数据。
- `APP_MODE=production`：生产环境，应先执行 `database/migrations/*.sql`，配置真实 Supabase、R2、broker 和数据源密钥。

## 关键健康检查

```bash
python scripts/release_health_check.py --base-url http://127.0.0.1:8012
```

核心接口：

- `GET /api/v1/platform/schema-health`
- `GET /api/v1/platform/release-health`
- `GET /api/v1/trading/safety-center`
- `GET /api/v1/trading/automation/timeline`
- `GET /api/v1/data/config-center`
- `POST /api/v1/jobs`

## 验收测试

清理验收 namespace：

```bash
python scripts/reset_acceptance_state.py --namespace local
```

跑全站截图验收：

```bash
npx playwright test e2e/full-app-acceptance.spec.js
```

截图和 JSON 报告保存在：

```text
test-results/playwright/full-app-acceptance
```

## Supabase Schema

生产化表结构位于：

```text
database/migrations/006_create_production_ops.sql
```

覆盖 strategy registry、autopilot policy、daily review、paper evidence、scheduler events、submit locks、job queue、data config 和 data quality。迁移是非破坏性的 `create table if not exists`，不会删除已有表。

## 交易安全边界

- 自动提交只允许 Alpaca Paper。
- Live 永远只展示计划或建议，不自动下单。
- Paper 自动提交必须同时满足：`SCHEDULER_AUTO_SUBMIT=true`、`UNATTENDED_PAPER_MODE=true`、broker ready、交易时段、风控门禁通过、kill switch 关闭。
- `GET /api/v1/trading/safety-center` 会返回 hard rule 证明：`live_auto_submit.allowed=false`。

## 降级语义

- `ready`：远端依赖或本地能力可用。
- `degraded`：功能可运行但使用本地 fallback、缓存或缺少部分外部配置。
- `blocked`：缺少必要配置或运行时服务，不能执行该动作。

所有 `degraded` / `blocked` 响应都应包含 `reason`、`missing_config` 或 `next_actions`。
