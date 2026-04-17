from __future__ import annotations

from pathlib import Path

import numpy as np

from quant_rl.agents.base import BaseAgent


class RandomAgent(BaseAgent):
    algorithm = "random"

    def __init__(self, action_space) -> None:
        self.action_space = action_space

    def act(self, state, deterministic: bool = False):
        sample = self.action_space.sample()
        if isinstance(sample, np.ndarray) and sample.size == 1:
            return float(sample.squeeze())
        return sample

    def save(self, path: str | Path) -> None:
        Path(path).write_text("random-agent", encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path, **kwargs):
        return cls(kwargs["action_space"])
