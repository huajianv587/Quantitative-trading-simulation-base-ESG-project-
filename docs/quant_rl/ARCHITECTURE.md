# Quant RL Architecture

你的现有仓库 README 说明系统是“两层并行结构”：运行层 `gateway/`, `frontend/`, `training/`, `scripts/`；蓝图层 `config/`, `data/`, `analysis/`, `models/`, `agents/`, `risk/`, `backtest/`, `infrastructure/`, `reporting/`, `rag/`, `api/`, `database/`, `notebooks/`。这个补丁包按同样思路接入，并尽量避免重写你原有服务入口。

Agent loop:

```text
Market Data -> Features -> Observation -> Policy -> Risk Shield
-> Execution -> Reward -> Replay/Offline Dataset -> Update
-> Backtest -> OPE -> Walk-forward -> Paper -> Live Guarded Rollout
```
