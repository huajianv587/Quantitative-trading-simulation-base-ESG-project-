from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class DrawdownGuard:
    max_drawdown: float = 0.25

    def should_stop(self, drawdown: float) -> bool:
        return drawdown >= self.max_drawdown


@dataclass(slots=True)
class KillSwitch:
    max_intraday_loss: float = 0.08
    max_abs_position: float = 1.0

    def validate(self, pnl_ratio: float, position: float) -> bool:
        if pnl_ratio <= -abs(self.max_intraday_loss):
            return False
        if abs(position) > self.max_abs_position:
            return False
        return True
