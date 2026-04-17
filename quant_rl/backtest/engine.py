from __future__ import annotations

from typing import Any

from quant_rl.data.contracts import BacktestResult
from quant_rl.analysis.performance import compute_performance_metrics


class BacktestEngine:
    def run(self, agent, env, deterministic: bool = True) -> BacktestResult:
        state, _ = env.reset()
        done = False
        while not done:
            action = agent.act(state, deterministic=deterministic)
            if isinstance(action, tuple):
                action = action[0]
            state, _, terminated, truncated, _ = env.step(action)
            done = terminated or truncated
        history = env.history_frame()
        metrics = compute_performance_metrics(history)
        return BacktestResult(metrics=metrics, history=history.to_dict(orient="records"))
