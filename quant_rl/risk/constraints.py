from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class RiskLimits:
    max_abs_position: float = 1.0
    max_turnover_per_step: float = 0.35
    min_equity_ratio: float = 0.5
    max_drawdown: float = 0.35


def apply_position_constraints(
    target_position: float,
    current_position: float,
    limits: RiskLimits,
) -> float:
    target_position = max(-limits.max_abs_position, min(limits.max_abs_position, target_position))
    delta = target_position - current_position
    if abs(delta) > limits.max_turnover_per_step:
        delta = limits.max_turnover_per_step if delta > 0 else -limits.max_turnover_per_step
    return current_position + delta
