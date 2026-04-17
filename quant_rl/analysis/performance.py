from __future__ import annotations

import math

import numpy as np
import pandas as pd


def max_drawdown(equity: pd.Series) -> float:
    running_max = equity.cummax()
    drawdowns = equity / running_max - 1.0
    return float(drawdowns.min())


def compute_performance_metrics(history: pd.DataFrame, periods_per_year: int = 252) -> dict[str, float]:
    if history.empty:
        return {}
    equity = history["equity"].astype(float)
    returns = equity.pct_change().fillna(0.0)

    total_return = float(equity.iloc[-1] / equity.iloc[0] - 1.0)
    ann_return = float((1.0 + total_return) ** (periods_per_year / max(len(history), 1)) - 1.0)
    vol = float(returns.std(ddof=0) * math.sqrt(periods_per_year))
    sharpe = float((returns.mean() / (returns.std(ddof=0) + 1e-8)) * math.sqrt(periods_per_year))
    downside = returns.clip(upper=0)
    sortino = float((returns.mean() / (downside.std(ddof=0) + 1e-8)) * math.sqrt(periods_per_year))
    mdd = abs(max_drawdown(equity))
    calmar = float(ann_return / (mdd + 1e-8))
    turnover = float(history["turnover"].mean()) if "turnover" in history else 0.0
    win_rate = float((returns > 0).mean())

    return {
        "total_return": total_return,
        "annualized_return": ann_return,
        "annualized_volatility": vol,
        "sharpe": sharpe,
        "sortino": sortino,
        "max_drawdown": mdd,
        "calmar": calmar,
        "avg_turnover": turnover,
        "win_rate": win_rate,
        "final_equity": float(equity.iloc[-1]),
    }
