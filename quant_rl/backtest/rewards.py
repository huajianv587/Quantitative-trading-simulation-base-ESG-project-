from __future__ import annotations

from dataclasses import dataclass

from quant_rl.data.contracts import RewardBreakdown


@dataclass(slots=True)
class RewardConfig:
    turnover_penalty: float = 0.001
    drawdown_penalty: float = 0.2
    position_penalty: float = 0.0005
    esg_bonus_scale: float = 0.0


class RewardEngine:
    def __init__(self, cfg: RewardConfig) -> None:
        self.cfg = cfg

    def compute(
        self,
        pnl: float,
        transaction_cost: float,
        turnover: float,
        drawdown: float,
        position_abs: float,
        equity: float,
        esg_signal: float = 0.0,
    ) -> RewardBreakdown:
        pnl_component = pnl / max(equity, 1e-8)
        cost_component = transaction_cost / max(equity, 1e-8)
        turnover_penalty = self.cfg.turnover_penalty * turnover
        drawdown_penalty = self.cfg.drawdown_penalty * drawdown
        position_penalty = self.cfg.position_penalty * position_abs
        esg_bonus = self.cfg.esg_bonus_scale * esg_signal
        reward = pnl_component - cost_component - turnover_penalty - drawdown_penalty - position_penalty + esg_bonus
        return RewardBreakdown(
            pnl=float(pnl_component),
            transaction_cost=float(cost_component),
            turnover_penalty=float(turnover_penalty),
            drawdown_penalty=float(drawdown_penalty),
            position_penalty=float(position_penalty),
            reward=float(reward),
            esg_bonus=float(esg_bonus),
        )
