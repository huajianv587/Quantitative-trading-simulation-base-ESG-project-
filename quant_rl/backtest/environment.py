from __future__ import annotations

import random
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd

from quant_rl.analysis.observation import ObservationBuilder
from quant_rl.backtest.execution import ExecutionConfig, execution_cost
from quant_rl.backtest.rewards import RewardConfig, RewardEngine
from quant_rl.risk.constraints import RiskLimits, apply_position_constraints
from quant_rl.risk.guards import DrawdownGuard


class DiscreteSpace:
    def __init__(self, n: int) -> None:
        self.n = n

    def sample(self) -> int:
        return random.randrange(self.n)


class BoxSpace:
    def __init__(self, low: float, high: float, shape: tuple[int, ...]) -> None:
        self.low = low
        self.high = high
        self.shape = shape

    def sample(self) -> np.ndarray:
        return np.random.uniform(self.low, self.high, size=self.shape).astype(np.float32)


@dataclass(slots=True)
class TradingEnvConfig:
    initial_equity: float = 100_000.0
    action_type: str = "discrete"  # discrete | continuous
    discrete_positions: tuple[float, ...] = (-1.0, 0.0, 1.0)


class TradingEnv:
    def __init__(
        self,
        df: pd.DataFrame,
        observation_builder: ObservationBuilder,
        env_cfg: TradingEnvConfig | None = None,
        execution_cfg: ExecutionConfig | None = None,
        reward_cfg: RewardConfig | None = None,
        risk_limits: RiskLimits | None = None,
        price_col: str = "close",
    ) -> None:
        self.df = df.reset_index(drop=True).copy()
        self.observation_builder = observation_builder
        self.env_cfg = env_cfg or TradingEnvConfig()
        self.execution_cfg = execution_cfg or ExecutionConfig()
        self.reward_engine = RewardEngine(reward_cfg or RewardConfig())
        self.risk_limits = risk_limits or RiskLimits()
        self.drawdown_guard = DrawdownGuard(self.risk_limits.max_drawdown)
        self.price_col = price_col

        if self.env_cfg.action_type == "discrete":
            self.action_space = DiscreteSpace(len(self.env_cfg.discrete_positions))
        else:
            self.action_space = BoxSpace(-1.0, 1.0, (1,))
        self.state_dim = self.observation_builder.dimension()
        self.reset()

    def reset(self) -> tuple[np.ndarray, dict[str, Any]]:
        self.step_idx = 0
        self.position = 0.0
        self.equity = float(self.env_cfg.initial_equity)
        self.high_watermark = float(self.equity)
        self.history: list[dict[str, Any]] = []
        return self._get_observation(), {"equity": self.equity, "position": self.position}

    def _get_observation(self) -> np.ndarray:
        cash_ratio = max(0.0, min(1.0, 1.0 - abs(self.position)))
        drawdown = 1.0 - self.equity / max(self.high_watermark, 1e-8)
        return self.observation_builder.build(
            df=self.df,
            idx=self.step_idx,
            position=self.position,
            cash_ratio=cash_ratio,
            drawdown=drawdown,
        )

    def _map_action(self, action: Any) -> float:
        if self.env_cfg.action_type == "discrete":
            idx = int(action)
            return float(self.env_cfg.discrete_positions[idx])
        if isinstance(action, np.ndarray):
            return float(action.squeeze())
        return float(action)

    def step(self, action: Any) -> tuple[np.ndarray, float, bool, bool, dict[str, Any]]:
        if self.step_idx >= len(self.df) - 2:
            obs = self._get_observation()
            return obs, 0.0, True, False, {"reason": "end_of_data"}

        price_t = float(self.df.iloc[self.step_idx][self.price_col])
        price_next = float(self.df.iloc[self.step_idx + 1][self.price_col])
        asset_return = price_next / max(price_t, 1e-8) - 1.0

        raw_target = self._map_action(action)
        target_position = apply_position_constraints(raw_target, self.position, self.risk_limits)
        turnover = abs(target_position - self.position)

        cost = execution_cost(notional=self.equity, turnover=turnover, cfg=self.execution_cfg)
        pnl = self.position * asset_return * self.equity
        self.equity = float(max(1e-8, self.equity + pnl - cost))
        self.position = float(target_position)
        self.high_watermark = max(self.high_watermark, self.equity)
        drawdown = max(0.0, 1.0 - self.equity / max(self.high_watermark, 1e-8))

        reward_breakdown = self.reward_engine.compute(
            pnl=pnl,
            transaction_cost=cost,
            turnover=turnover,
            drawdown=drawdown,
            position_abs=abs(self.position),
            equity=self.equity,
            esg_signal=self._esg_alignment_signal(),
        )

        self.history.append(
            {
                "step": self.step_idx,
                "timestamp": self.df.iloc[self.step_idx].get("timestamp", self.step_idx),
                "price": price_t,
                "next_price": price_next,
                "position": self.position,
                "turnover": turnover,
                "equity": self.equity,
                "asset_return": asset_return,
                "pnl_cash": pnl,
                "cost_cash": cost,
                "reward": reward_breakdown.reward,
                "esg_bonus": reward_breakdown.esg_bonus,
                "drawdown": drawdown,
            }
        )

        self.step_idx += 1
        terminated = self.step_idx >= len(self.df) - 1
        truncated = (
            self.equity <= self.env_cfg.initial_equity * self.risk_limits.min_equity_ratio
            or self.drawdown_guard.should_stop(drawdown)
        )
        info = {
            "equity": self.equity,
            "position": self.position,
            "drawdown": drawdown,
            "reward_breakdown": asdict(reward_breakdown),
        }
        return self._get_observation(), reward_breakdown.reward, terminated, truncated, info

    def history_frame(self) -> pd.DataFrame:
        return pd.DataFrame(self.history)

    def _esg_alignment_signal(self) -> float:
        score_column = next((column for column in ("house_score_v2_1", "house_score_v2", "house_score", "esg_score") if column in self.df.columns), None)
        if score_column is None:
            return 0.0
        current = self.df.iloc[self.step_idx]
        esg_score = float(current.get(score_column, 0.5) or 0.5)
        if esg_score > 1.0:
            esg_score = esg_score / 100.0
        centered = esg_score - 0.5
        confidence = float(current.get("esg_confidence", 1.0) or 1.0) if "esg_confidence" in self.df.columns else 1.0
        stale_days = float(current.get("esg_staleness_days", 0.0) or 0.0) if "esg_staleness_days" in self.df.columns else 0.0
        freshness = max(0.35, 1.0 - min(stale_days, 730.0) / 1460.0)
        return float(self.position * centered * confidence * freshness)
