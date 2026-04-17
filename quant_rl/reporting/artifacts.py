from __future__ import annotations

from pathlib import Path

import pandas as pd

from quant_rl.reporting.html_report import render_backtest_report
from quant_rl.reporting.plotting import plot_equity_curve


def create_backtest_artifacts(
    run_id: str,
    history: pd.DataFrame,
    metrics: dict[str, float],
    artifact_store,
) -> dict[str, str]:
    history_csv = artifact_store.save_csv(run_id, "backtest_history.csv", history)
    metrics_json = artifact_store.save_json(run_id, "backtest_metrics.json", metrics)

    report_dir = artifact_store.report_dir(run_id)
    equity_png = plot_equity_curve(history, report_dir / "equity_curve.png")
    html_path = render_backtest_report(
        run_id=run_id,
        metrics=metrics,
        equity_curve_path=equity_png,
        output_path=report_dir / "report.html",
    )
    return {
        "history_csv": history_csv,
        "metrics_json": metrics_json,
        "equity_curve_png": str(equity_png),
        "report_html": str(html_path),
    }
