from __future__ import annotations

from pathlib import Path

import numpy as np

from quant_rl.agents.base import BaseAgent


class RuleBasedMomentumAgent(BaseAgent):
    algorithm = "rule_based"

    def __init__(self, discrete_positions: tuple[float, ...] = (-1.0, 0.0, 1.0), continuous: bool = False):
        self.discrete_positions = discrete_positions
        self.continuous = continuous

    def act(self, state, deterministic: bool = False):
        signal = float(state[0]) if len(state) > 0 else 0.0
        if self.continuous:
            return max(-1.0, min(1.0, signal * 5.0))
        if signal > 0.001:
            return self.discrete_positions.index(1.0) if 1.0 in self.discrete_positions else len(self.discrete_positions) - 1
        if signal < -0.001:
            return self.discrete_positions.index(-1.0) if -1.0 in self.discrete_positions else 0
        return self.discrete_positions.index(0.0) if 0.0 in self.discrete_positions else len(self.discrete_positions) // 2

    def save(self, path: str | Path) -> None:
        Path(path).write_text("rule-based-agent", encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path, **kwargs):
        return cls(
            discrete_positions=tuple(kwargs.get("discrete_positions", (-1.0, 0.0, 1.0))),
            continuous=kwargs.get("continuous", False),
        )
