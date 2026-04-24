from __future__ import annotations

from typing import Any


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _bounded(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _quantile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = int(round((len(ordered) - 1) * q))
    return float(ordered[max(0, min(index, len(ordered) - 1))])


def run_module(payload: dict | None = None) -> dict:
    payload = payload or {}
    combinations = list(payload.get("combinations") or [])
    if not combinations:
        return {
            "module": "walk_forward",
            "status": "ready",
            "window_count": 0,
            "windows": [],
            "summary": {"robustness_score": 0.0, "stability_band": "insufficient_data"},
        }

    ordered = sorted(
        combinations,
        key=lambda row: (
            -float((row.get("metrics") or {}).get("sharpe") or row.get("sharpe") or 0.0),
            -float((row.get("metrics") or {}).get("cumulative_return") or row.get("cumulative_return") or 0.0),
        ),
    )
    requested_windows = max(1, int(payload.get("window_count") or min(3, len(ordered))))
    bucket_size = max(1, len(ordered) // requested_windows)
    windows: list[dict[str, Any]] = []
    for index in range(requested_windows):
        start = index * bucket_size
        stop = len(ordered) if index == requested_windows - 1 else min(len(ordered), start + bucket_size)
        bucket = ordered[start:stop]
        sharpe_values = [float((row.get("metrics") or {}).get("sharpe") or row.get("sharpe") or 0.0) for row in bucket]
        cumulative_values = [
            float((row.get("metrics") or {}).get("cumulative_return") or row.get("cumulative_return") or 0.0)
            for row in bucket
        ]
        drawdown_values = [
            float((row.get("metrics") or {}).get("max_drawdown") or row.get("max_drawdown") or 0.0)
            for row in bucket
        ]
        best = bucket[0] if bucket else {}
        windows.append(
            {
                "label": f"WF-{index + 1}",
                "sample_count": len(bucket),
                "avg_sharpe": round(_mean(sharpe_values), 6),
                "avg_cumulative_return": round(_mean(cumulative_values), 6),
                "avg_max_drawdown": round(_mean(drawdown_values), 6),
                "best_parameters": dict(best.get("parameters") or {}),
                "best_backtest_id": best.get("backtest_id"),
            }
        )

    sharpe_values = [float(window["avg_sharpe"]) for window in windows]
    drawdown_values = [float(window["avg_max_drawdown"]) for window in windows]
    stability_band = "stable" if _quantile(sharpe_values, 0.25) >= 0.75 else "fragile" if _quantile(sharpe_values, 0.75) < 0.5 else "mixed"
    robustness_score = _bounded(
        50.0
        + _mean(sharpe_values) * 20.0
        - _mean(drawdown_values) * 160.0
        - max(0.0, _quantile(sharpe_values, 0.75) - _quantile(sharpe_values, 0.25)) * 18.0,
        5.0,
        95.0,
    )
    return {
        "module": "walk_forward",
        "status": "ready",
        "window_count": len(windows),
        "windows": windows,
        "summary": {
            "robustness_score": round(robustness_score, 4),
            "stability_band": stability_band,
            "best_window": max(windows, key=lambda row: row["avg_sharpe"]).get("label"),
            "worst_window": min(windows, key=lambda row: row["avg_sharpe"]).get("label"),
        },
    }
