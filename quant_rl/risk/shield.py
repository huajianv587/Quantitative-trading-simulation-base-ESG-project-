from __future__ import annotations

from dataclasses import asdict

import numpy as np

from quant_rl.core.contracts import ActionDecision, RiskSignal
from quant_rl.risk.constraints import RiskLimits, apply_position_constraints


class RiskShield:
    def __init__(self, limits: RiskLimits | None = None) -> None:
        self.limits = limits or RiskLimits()

    def sanitize(self, raw_action, current_position: float, drawdown: float = 0.0) -> ActionDecision:
        if drawdown >= self.limits.max_drawdown:
            signal = RiskSignal(drawdown=drawdown, gross_exposure=abs(current_position), blocked=True, reason='max_drawdown')
            return ActionDecision(action=raw_action, safe_action=0.0, metadata={'risk': asdict(signal)})
        if isinstance(raw_action, np.ndarray):
            raw_value = float(raw_action.squeeze())
        else:
            raw_value = float(raw_action)
        safe_value = apply_position_constraints(raw_value, current_position, self.limits)
        signal = RiskSignal(turnover=abs(safe_value-current_position), drawdown=drawdown, gross_exposure=abs(safe_value))
        return ActionDecision(action=raw_action, safe_action=safe_value, metadata={'risk': asdict(signal)})
