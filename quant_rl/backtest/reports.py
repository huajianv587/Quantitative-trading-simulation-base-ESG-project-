from __future__ import annotations

from pathlib import Path

import pandas as pd

from quant_rl.reporting.artifacts import create_backtest_artifacts


def build_backtest_reports(
    run_id: str,
    history: pd.DataFrame,
    metrics: dict[str, float],
    artifact_store,
) -> dict[str, str]:
    return create_backtest_artifacts(
        run_id=run_id,
        history=history,
        metrics=metrics,
        artifact_store=artifact_store,
    )
