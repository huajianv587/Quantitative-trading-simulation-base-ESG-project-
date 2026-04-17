from __future__ import annotations

from pathlib import Path

from quant_rl.agents.base import BaseAgent


class BuyHoldAgent(BaseAgent):
    algorithm = "buy_hold"

    def __init__(self, continuous: bool = False, long_position: float = 1.0):
        self.continuous = continuous
        self.long_position = long_position

    def act(self, state, deterministic: bool = False):
        if self.continuous:
            return float(self.long_position)
        return 2

    def save(self, path: str | Path) -> None:
        Path(path).write_text("buy-hold-agent", encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path, **kwargs):
        return cls(
            continuous=kwargs.get("continuous", False),
            long_position=kwargs.get("long_position", 1.0),
        )
