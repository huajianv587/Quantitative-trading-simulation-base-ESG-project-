from __future__ import annotations

import pandas as pd


def merge_external_context(
    market_df: pd.DataFrame,
    context_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    if context_df is None or context_df.empty:
        return market_df
    if "timestamp" not in market_df.columns or "timestamp" not in context_df.columns:
        return market_df
    merged = market_df.merge(context_df, on="timestamp", how="left")
    return merged.fillna(method="ffill").fillna(0.0)
