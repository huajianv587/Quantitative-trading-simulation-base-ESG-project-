from __future__ import annotations

import numpy as np
import pandas as pd


def add_technical_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    close = out["close"]
    volume = out["volume"]

    out["ret_1"] = close.pct_change().fillna(0.0)
    out["ret_5"] = close.pct_change(5).fillna(0.0)
    out["ret_20"] = close.pct_change(20).fillna(0.0)

    sma_5 = close.rolling(5, min_periods=1).mean()
    sma_20 = close.rolling(20, min_periods=1).mean()
    ema_10 = close.ewm(span=10, adjust=False).mean()

    out["sma_5_ratio"] = (close / sma_5 - 1.0).fillna(0.0)
    out["sma_20_ratio"] = (close / sma_20 - 1.0).fillna(0.0)
    out["ema_10_ratio"] = (close / ema_10 - 1.0).fillna(0.0)

    out["vol_20"] = out["ret_1"].rolling(20, min_periods=5).std().fillna(0.0)
    out["hl_spread"] = ((out["high"] - out["low"]) / out["close"]).fillna(0.0)
    out["volume_z_20"] = (
        (volume - volume.rolling(20, min_periods=5).mean())
        / volume.rolling(20, min_periods=5).std().replace(0, 1e-8)
    ).fillna(0.0)

    delta = close.diff().fillna(0.0)
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    roll_up = up.rolling(14, min_periods=5).mean()
    roll_down = down.rolling(14, min_periods=5).mean().replace(0, 1e-8)
    rs = roll_up / roll_down
    out["rsi_14"] = (100 - 100 / (1 + rs)).fillna(50.0) / 100.0

    out = out.replace([np.inf, -np.inf], 0.0).fillna(0.0)
    return out


def default_feature_columns(df: pd.DataFrame) -> list[str]:
    candidates = [
        "ret_1",
        "ret_5",
        "ret_20",
        "sma_5_ratio",
        "sma_20_ratio",
        "ema_10_ratio",
        "vol_20",
        "hl_spread",
        "volume_z_20",
        "rsi_14",
        "house_score",
        "house_score_v2",
        "house_score_v2_1",
        "esg_level",
        "esg_score",
        "esg_delta",
        "esg_delta_v2_1",
        "esg_confidence",
        "esg_staleness_days",
        "esg_missing_flag",
        "sector_relative_esg",
        "e_score",
        "s_score",
        "g_score",
        "vix",
        "us10y_yield",
        "credit_spread",
    ]
    return [c for c in candidates if c in df.columns]
