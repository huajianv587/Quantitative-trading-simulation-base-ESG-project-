from __future__ import annotations

from typing import Callable

import pandas as pd

from quant_rl.analysis.performance import compute_performance_metrics
from quant_rl.data.split import walk_forward_windows


def run_walk_forward(
    df: pd.DataFrame,
    builder: Callable[[pd.DataFrame], tuple[object, object]],
    train_size: int,
    val_size: int,
    test_size: int,
    step_size: int | None = None,
) -> list[dict]:
    results: list[dict] = []
    for window in walk_forward_windows(
        df=df,
        train_size=train_size,
        val_size=val_size,
        test_size=test_size,
        step_size=step_size,
    ):
        agent, history = builder(window.train)
        metrics = compute_performance_metrics(history)
        metrics["window_index"] = window.index
        results.append(metrics)
    return results
