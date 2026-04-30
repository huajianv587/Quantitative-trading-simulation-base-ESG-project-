# AutoDL paper fallback

This deployment mode is for AutoDL-like environments where Docker and systemd are unavailable. It runs only the paper trading API and scheduler in a Python venv managed by supervisord.

## Setup

From the project root on the AutoDL host:

```bash
cp deploy/autodl/env.paper.example .env
chmod 600 .env
vim .env
bash deploy/autodl/start.sh
```

Fill only Alpaca paper credentials in `.env`. Keep `ALPACA_ENABLE_LIVE_TRADING=false` and `PAPER_REWARD_SUBMIT_ENABLED=false`.

## Operations

```bash
bash deploy/autodl/status.sh
bash deploy/autodl/healthcheck.sh
RECOVER=1 bash deploy/autodl/healthcheck.sh
bash deploy/autodl/stop.sh
```

Logs are written to:

- `logs/api.out.log`
- `logs/api.err.log`
- `logs/scheduler.out.log`
- `logs/scheduler.err.log`
- `logs/supervisord.log`

Supervisor runtime files are written to `runtime/supervisor/`.

## Behavior

- API runs at `http://127.0.0.1:8012`.
- Scheduler runs `scripts/quant_signal_scheduler.py --poll-seconds 20`.
- Qdrant is not started in this fallback mode. `API_HEALTHCHECK_REQUIRED_COMPONENTS=api` keeps `/livez` focused on API process health.
- RLVR, scheduler heartbeat, recovery, and paper-only gate remain enabled.

## Limits

AutoDL may stop or restart the instance outside this process manager. After an AutoDL instance restart, run `bash deploy/autodl/start.sh` again.

For production-grade unattended trading, prefer a real Linux VM with systemd and Docker Compose.
