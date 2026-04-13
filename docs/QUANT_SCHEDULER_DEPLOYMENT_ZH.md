# Quant Scheduler 常驻部署说明

## 目标

这条 worker 负责 3 件事：

1. 开盘前运行研究与信号计算
2. 到点生成执行计划并按配置自动提交 Alpaca Paper 订单
3. 盘中持续同步 execution journal，刷新订单状态机

## 关键文件

- `scripts/quant_signal_scheduler.py`
- `docker-compose.yml`
- `scripts/start_quant_scheduler_windows.bat`

## 关键环境变量

- `SCHEDULER_TIMEZONE`
- `SCHEDULER_SIGNAL_UNIVERSE`
- `SCHEDULER_PREOPEN_SIGNAL_TIME`
- `SCHEDULER_EXECUTION_TIME`
- `SCHEDULER_AUTO_SUBMIT`
- `SCHEDULER_MAX_EXECUTION_SYMBOLS`
- `SCHEDULER_SYNC_INTERVAL_MINUTES`
- `SCHEDULER_SYNC_END_TIME`
- `SCHEDULER_FALLBACK_TO_DEFAULT_UNIVERSE`
- `SCHEDULER_STATE_PATH`
- `SCHEDULER_HEARTBEAT_PATH`
- `SCHEDULER_LOCK_PATH`

## 本地运行

单次预开盘研究：

```bat
python scripts\quant_signal_scheduler.py --once-preopen
```

单次执行：

```bat
python scripts\quant_signal_scheduler.py --once-execute
```

单次盘中同步：

```bat
python scripts\quant_signal_scheduler.py --once-sync
```

常驻运行：

```bat
scripts\start_quant_scheduler_windows.bat
```

查看当前状态：

```bat
python scripts\quant_signal_scheduler.py --print-state
```

## Docker 常驻部署

启动 API、Qdrant、Quant Scheduler：

```bash
docker compose up -d api qdrant quant-scheduler
```

查看 scheduler 日志：

```bash
docker compose logs -f quant-scheduler
```

## 运行产物

默认会写到：

- `storage/quant/scheduler/runtime_state.json`
- `storage/quant/scheduler/heartbeat.json`

其中：

- `runtime_state.json` 保存当日 pre-open shortlist、execution_id 和最近一次 sync 结果
- `heartbeat.json` 可用于健康检查与部署监控

## 当前策略约束

- 当前只启用 `alpaca` 作为常驻执行 broker
- 执行模式默认为 `paper`
- 没有通过 `long-only` 过滤时会保持 `no-trade`
- 如果配置 universe 没有可执行多头，且 `SCHEDULER_FALLBACK_TO_DEFAULT_UNIVERSE=true`，worker 会自动回退到默认量化股票池
