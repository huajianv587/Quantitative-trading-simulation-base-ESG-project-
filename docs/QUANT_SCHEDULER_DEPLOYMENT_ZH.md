# Quant Scheduler 云端无人值守部署说明

## 目标

`quant-scheduler` 是 Hybrid Paper 的生产主入口，负责按 XNYS 交易日历自动完成：

1. 盘前 shortlist 和研究信号
2. Hybrid Paper Workflow
3. Alpaca paper 自动派单
4. Alpaca broker sync
5. N+1/N+3/N+5 outcome settlement
6. paper performance snapshot
7. promotion evaluate
8. observability alert evaluate
9. 盘前和盘后 Telegram + Email digest

live 实盘不会自动打开。60/90 个有效 paper 交易日通过后，系统只生成 live canary recommendation，仍需人工确认。

## 必需环境变量

密钥只写入云端 `.env` 或 secret manager，不要提交到仓库。

- `SCHEDULER_EXECUTION_ENGINE=hybrid_paper_workflow`
- `SCHEDULER_AUTO_SUBMIT=true`
- `SCHEDULER_REQUIRE_TRADING_SESSION=true`
- `SCHEDULER_REQUIRE_MARKET_CLOCK_FOR_SUBMIT=true`
- `SYNTHETIC_EVIDENCE_POLICY=block`
- `UNATTENDED_PAPER_MODE=true`
- `ALERT_NOTIFIER=telegram`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `ALPACA_API_KEY`
- `ALPACA_API_SECRET`
- `ALPACA_PAPER_BASE_URL=https://paper-api.alpaca.markets`
- `MARKET_DATA_PROVIDER=alpaca,yfinance`
- `SEC_EDGAR_EMAIL`
- `SMTP_HOST`
- `SMTP_USER`
- `SMTP_PASSWORD`
- `EMAIL_FROM`
- `QUANT_DAILY_DIGEST_RECIPIENTS=jianghuajian99@gmail.com`
- `QUANT_DAILY_DIGEST_CHANNELS=telegram,email`

默认 paper 风控：

- `SCHEDULER_MAX_EXECUTION_SYMBOLS=2`
- `ALPACA_DEFAULT_TEST_NOTIONAL=100`
- `SCHEDULER_MAX_DAILY_NOTIONAL_USD=200`
- `EXECUTION_PAPER_MAX_NOTIONAL_PER_ORDER=100`
- `ALPACA_ENABLE_LIVE_TRADING=false`

## Docker Compose 部署

```bash
docker compose up -d --build api qdrant quant-scheduler
docker compose ps
docker compose logs -f quant-scheduler
```

5090 训练节点：

```bash
docker compose -f docker-compose.5090.yml up -d --build api qdrant remote-llm quant-scheduler
```

API 容器 healthcheck 只打 `/livez`；业务 readiness 用 `/ready`。`quant-scheduler` healthcheck 必须校验 heartbeat 新鲜度。

## 发布前检查

先生成一次真实 preflight 证据：

```bash
curl -X POST "http://127.0.0.1:8012/api/v1/quant/deployment/preflight/evaluate?profile=paper_cloud"
curl "http://127.0.0.1:8012/ready"
```

本地脚本：

```bash
python scripts/staging_check.py paper-cloud --base-url http://127.0.0.1:8012
python scripts/healthcheck_5090.py --base-url http://127.0.0.1:8012
```

## 日常运维

查看 scheduler state：

```bash
python scripts/quant_signal_scheduler.py --print-state
```

单次补跑非下单恢复步骤：

```bash
python scripts/quant_signal_scheduler.py --once-recover
```

单次观测告警评估：

```bash
python scripts/quant_signal_scheduler.py --once-observability
```

手动发送 digest：

```bash
python scripts/quant_signal_scheduler.py --once-digest --digest-phase preopen
python scripts/quant_signal_scheduler.py --once-digest --digest-phase postclose
```

从 Alpaca paper 回填历史 evidence：

```bash
curl -X POST http://127.0.0.1:8012/api/v1/quant/paper/performance/backfill \
  -H "Content-Type: application/json" \
  -d "{\"days\":120,\"broker\":\"alpaca\",\"mode\":\"paper\"}"
```

## 熔断策略

连续出现 broker submit、broker sync、market data stale、RL checkpoint missing、workflow failure、equity anomaly 时，scheduler 会启用 `paper_submit` circuit breaker。熔断后只阻止新 paper submit，仍继续执行 broker sync、settlement、snapshot、promotion、alert 和 digest。

查看熔断：

```bash
curl http://127.0.0.1:8012/api/v1/quant/observability/paper-workflow?window_days=30
```

后续循环如果所有失败计数恢复为 0，scheduler 会自动释放该熔断；不要直接删除 state 文件。
