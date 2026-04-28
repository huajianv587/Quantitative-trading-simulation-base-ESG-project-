# Hybrid Paper CPU 云端无人值守 Runbook

本文档用于 CPU 云端 Alpaca Paper 自动化部署。目标是让 API、`quant-scheduler`、watchdog、备份、推送和验收形成闭环。默认不在本地 Windows 创建或启动 Docker；本地只做静态验证、代码测试和 pre-cloud smoke。

## 1. 云端目录

默认部署目录：

```bash
/opt/quant-paper
```

必须持久化：

```bash
/opt/quant-paper/storage
/opt/quant-paper/model-serving/checkpoint
/opt/quant-paper/storage/quant/rl
/opt/quant-paper/storage/quant/model_registry
```

## 2. 生产 `.env` 必备项

Paper 自动化必须显式设置：

```bash
TELEGRAM_TOKEN_ROTATION_CONFIRMED=true
ALPACA_ENABLE_LIVE_TRADING=false
SYNTHETIC_EVIDENCE_POLICY=block
UNATTENDED_PAPER_MODE=true
SHADOW_RETRAIN_ENABLED=false
MODEL_RETRAIN_SHADOW_ONLY=true
STORAGE_BACKUP_ENABLED=true
STORAGE_BACKUP_RETENTION_DAYS=30
PUBLIC_EXPOSURE_PROTECTED=false
SCHEDULER_EXECUTION_ENGINE=hybrid_paper_workflow
SCHEDULER_AUTO_SUBMIT=true
SCHEDULER_MAX_EXECUTION_SYMBOLS=2
ALPACA_DEFAULT_TEST_NOTIONAL=100.00
EXECUTION_PAPER_MAX_NOTIONAL_PER_ORDER=100.00
SCHEDULER_MAX_DAILY_NOTIONAL_USD=200.00
QUANT_WEEKLY_DIGEST_ENABLED=true
QUANT_WEEKLY_DIGEST_DAY=friday
QUANT_WEEKLY_DIGEST_WINDOW_DAYS=7
OMP_NUM_THREADS=2
MKL_NUM_THREADS=2
OPENBLAS_NUM_THREADS=2
NUMEXPR_NUM_THREADS=2
TORCH_NUM_THREADS=2
TOKENIZERS_PARALLELISM=false
```

密钥只放云端 `.env` 或 secret manager。不要把 `.env` 提交到 git。

## 3. 本地三项预验收

本地可以先跑 pre-cloud smoke，验证三件事：

1. 配置门禁：live 关闭、synthetic block、CPU-only、backup 开启。
2. API 验收路径：`/livez`、`/ready`、preflight、session evidence、submit locks、digest、performance endpoint 都能按 contract 返回。
3. 首个交易日 evidence 结构：`preopen -> workflow -> paper_submit -> broker_sync -> outcomes -> snapshot -> promotion -> digest -> backup` 全阶段齐全。

命令：

```bash
python scripts/paper_precloud_local_acceptance.py --env-file .env
```

如果已经在云端完成访问保护，并希望把本地 smoke 改成严格门禁：

```bash
python scripts/paper_precloud_local_acceptance.py \
  --env-file .env \
  --require-public-exposure-protected
```

注意：本地 pre-cloud smoke 不是云端真实 ready。真实 ready 必须在云端跑 `paper_cloud_acceptance.py`，并通过首个真实 XNYS 交易日验收。

## 4. 访问保护

不要把 `8012` 裸露到公网。上线前必须选择一种保护方式，然后把 `PUBLIC_EXPOSURE_PROTECTED=true` 写入云端 `.env`。

### 方案 A：SSH Tunnel

云端只监听本机或内网，本地访问：

```bash
ssh -L 8012:127.0.0.1:8012 user@your-cloud-host
```

浏览器打开：

```text
http://127.0.0.1:8012
```

### 方案 B：Nginx Basic Auth + IP 白名单

Nginx 只转发到本机 API：

```nginx
server {
    listen 443 ssl;
    server_name quant.example.com;

    auth_basic "Quant Paper";
    auth_basic_user_file /etc/nginx/.htpasswd;
    allow YOUR_PUBLIC_IP;
    deny all;

    location / {
        proxy_pass http://127.0.0.1:8012;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
    }
}
```

### 方案 C：Cloudflare Access / Tailscale

把 dashboard/API 放在 Cloudflare Access 或 Tailscale 网络后面，公网不直接访问容器端口。

## 5. systemd 常驻

复制模板：

```bash
sudo cp deploy/systemd/quant-paper-compose.service /etc/systemd/system/
sudo cp deploy/systemd/quant-paper-watchdog.service /etc/systemd/system/
sudo cp deploy/systemd/quant-paper-watchdog.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now quant-paper-compose.service
sudo systemctl enable --now quant-paper-watchdog.timer
```

查看状态：

```bash
systemctl status quant-paper-compose.service
systemctl list-timers | grep quant-paper-watchdog
docker compose ps
```

## 6. Watchdog 行为

watchdog 每分钟检查：

- `/livez`
- `/ready`
- scheduler heartbeat
- latest session evidence
- latest backup

恢复策略：

- `/livez` 失败：重启 `api`
- heartbeat stale：重启 `quant-scheduler`
- `/ready` 失败：写 blocker 诊断；连续失败超过阈值才重启相关服务
- 凭据、模型、RL checkpoint、数据源缺失：只报 blocker，不循环重启

查看 heartbeat：

```bash
cat storage/quant/scheduler/heartbeat.json
```

查看 alerts：

```bash
ls -lt storage/quant/alerts | head
```

## 7. 云端验收

部署后运行：

```bash
python scripts/paper_cloud_acceptance.py \
  --base-url http://127.0.0.1:8012 \
  --env-file .env \
  --send-test-notification
```

必须满足：

- `/livez=200`
- `/ready=200`
- scheduler heartbeat fresh
- Alpaca paper ready
- Telegram 和 Email 可用
- model registry ready
- RL checkpoint ready
- market data ready
- latest backup exists
- synthetic blocked
- live disabled

未通过时，scheduler 可以继续同步、结算和报告，但不能认为无人值守 ready。

## 8. 首次备份与恢复演练

云端首次启动后立即触发一次备份：

```bash
curl -X POST http://127.0.0.1:8012/api/v1/quant/storage/backup
```

从最新真实备份恢复到空目录并验证：

```bash
python scripts/restore_quant_backup.py \
  --storage-dir storage/quant \
  --restore-dir storage/quant_restore_drill \
  --clean
```

恢复演练只验证证据可读，不覆盖当前生产 `storage/quant`。

## 9. 首个真实交易日验收

第一个 XNYS 交易日结束后，latest session evidence 必须包含：

```text
preopen -> workflow -> paper_submit -> broker_sync -> outcomes -> snapshot -> promotion -> digest -> backup
```

每个 stage 必须有：

```text
status, started_at, finished_at, duration_seconds, error, submitted_count, artifacts, warnings, blocker_class
```

如果 `paper_submit` 被阻断，sync、settlement、snapshot、promotion、digest、backup 仍应继续执行。首个真实交易日通过后，再进入“一周查看一次”的节奏。

## 10. 每周查看流程

每周至少看一次：

```bash
curl http://127.0.0.1:8012/ready
curl http://127.0.0.1:8012/api/v1/quant/session-evidence/latest
curl http://127.0.0.1:8012/api/v1/quant/paper/weekly-digest/latest
curl http://127.0.0.1:8012/api/v1/quant/slo/paper-workflow?window_days=30
```

重点看：

- unresolved alerts
- valid paper days 增量
- submit_unknown unresolved
- backup success rate
- broker sync error count
- duplicate submit blocked count
- 60/90 日 evidence 进度

## 11. 绝对不自动实盘

本轮只做 Alpaca Paper。`ALPACA_ENABLE_LIVE_TRADING=false` 是硬门禁。60/90 个真实 paper 交易日通过后，系统只生成 live canary recommendation，不会自动切 live。
