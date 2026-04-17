from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class BaseAgent(ABC):
    algorithm: str = "base"

    @abstractmethod
    def act(self, state, deterministic: bool = False):
        raise NotImplementedError

    def remember(self, *args, **kwargs) -> None:
        return None

    def update(self):
        return {}

    @abstractmethod
    def save(self, path: str | Path) -> None:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def load(cls, path: str | Path, **kwargs):
        raise NotImplementedError

    def describe(self) -> dict[str, Any]:
        return {"algorithm": self.algorithm}
