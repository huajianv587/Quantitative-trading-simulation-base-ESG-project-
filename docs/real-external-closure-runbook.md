# 真实外部依赖闭环验收 Runbook

## 目标
- `Auth`: Supabase primary auth + 真实邮箱收发 + 真实密码重置
- `Trading`: broker readiness + paper 真提交 + live dry-run + 单笔 5 USD canary

## 前置条件检查
- `SUPABASE_URL` / `SUPABASE_API_KEY` 或 `SUPABASE_SERVICE_ROLE_KEY` 已配置
- `AUTH_PRIMARY_BACKEND=supabase`
- `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASSWORD` 已配置
- `IMAP_HOST` / `IMAP_PORT` / `IMAP_USER` / `IMAP_PASSWORD` 已配置
- `REAL_AUTH_TEST_EMAIL` / `REAL_AUTH_TEST_PASSWORD` / `REAL_AUTH_TEST_NEW_PASSWORD` 已配置
- `ALPACA_API_KEY` / `ALPACA_API_SECRET` 已配置
- `EXECUTION_API_KEY`、`OPS_API_KEY`、`ADMIN_API_KEY` 已配置

## 建议环境
- `AUTH_ALLOW_SQLITE_FALLBACK=false`
- `ALPACA_ENABLE_LIVE_TRADING=false` 用于 dry-run
- 真正 live canary 前，再由人工确认是否临时打开 live routing

## 认证闭环步骤
1. 调用 `GET /auth/status`
2. 确认 `primary_backend=supabase`
3. 确认 `supabase_ready=true`
4. 确认 `smtp_ready=true`
5. 确认 `imap_ready=true`
6. 运行：
   - `python scripts/real_auth_acceptance.py --base-url http://127.0.0.1:8006 --email <test mailbox> --password <old> --new-password <new> --write-report test-results/real-external/<run-id>/auth.json`
7. 验收以下步骤：
   - register
   - login
   - verify
   - reset request
   - IMAP mailbox poll
   - reset confirm
   - login after reset
   - session restore

## 交易闭环步骤
1. 运行连接器医生：
   - `python scripts/live_connector_doctor.py --all-configured --symbol AAPL --write-report test-results/real-external/<run-id>/broker.json`
2. 运行 staged smoke：
   - dry-run:
     - `python scripts/quant_execution_smoke.py --mode live --submit-orders --journal-sync --cancel-after-submit --per-order-notional 5 --max-orders 1 --dry-run --write-report test-results/real-external/<run-id>/live-canary.json`
   - live canary:
     - `python scripts/quant_execution_smoke.py --mode live --submit-orders --journal-sync --cancel-after-submit --per-order-notional 5 --max-orders 1 --confirm-live --write-report test-results/real-external/<run-id>/live-canary.json`
3. 验收以下阶段：
   - connector doctor
   - broker readiness
   - paper submit
   - journal sync
   - live dry-run
   - live canary
   - orders sync
   - positions sync
   - cancel-if-open

## 人工签核项
- `auth.json` 与 `auth.md` 已生成
- `email.json` 已生成
- `broker.json` 已生成
- `live-canary.json` 已生成
- `summary.json` 与 `summary.md` 已生成
- reset 邮件可在专用测试邮箱中检索
- live canary 风险包络确认：
  - 单笔
  - 单单
  - 不超过 5 USD

## 异常回滚
- 如果 `broker_readiness` 未通过，停止继续 live canary
- 如果 `kill switch` 已开启，先人工确认是否保持阻断
- 若 live canary 提交后订单仍 open，立即执行 `cancel_if_open`
- 若订单已 fill，则记录为 `n/a_filled` 并继续完成 position/journal 验证

## Windows 一键入口
- `powershell -ExecutionPolicy Bypass -File scripts/run_real_external_closure_windows.ps1 -Full -SkipLive`
- `powershell -ExecutionPolicy Bypass -File scripts/run_real_external_closure_windows.ps1 -Full -ConfirmLive`
