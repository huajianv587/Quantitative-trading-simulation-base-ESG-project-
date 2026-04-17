from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np

AlgorithmName = Literal["dqn","ppo","sac","cql","iql","decision_transformer","world_model","hybrid_frontier"]


@dataclass(slots=True)
class PolicyRequest:
    algorithm: AlgorithmName
    dataset_path: str
    action_type: Literal["discrete", "continuous"] = "discrete"
    episodes: int = 50
    total_steps: int = 5000
    use_demo_if_missing: bool = True
    phase: str = "phase_03_offline"
    tags: list[str] = field(default_factory=list)
    notes: str | None = None


@dataclass(slots=True)
class ActionDecision:
    action: int | float | np.ndarray
    safe_action: int | float | np.ndarray
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RiskSignal:
    turnover: float = 0.0
    drawdown: float = 0.0
    gross_exposure: float = 0.0
    cvar_proxy: float = 0.0
    blocked: bool = False
    reason: str | None = None
