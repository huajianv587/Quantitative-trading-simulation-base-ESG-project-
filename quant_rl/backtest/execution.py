from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ExecutionConfig:
    transaction_cost_bps: float = 5.0
    slippage_bps: float = 2.0


def execution_cost(notional: float, turnover: float, cfg: ExecutionConfig) -> float:
    return notional * turnover * (cfg.transaction_cost_bps + cfg.slippage_bps) / 1e4
