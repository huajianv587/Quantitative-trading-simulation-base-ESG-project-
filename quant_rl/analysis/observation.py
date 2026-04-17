from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(slots=True)
class ObservationBuilder:
    feature_columns: list[str]

    def dimension(self) -> int:
        return len(self.feature_columns) + 3

    def build(
        self,
        df: pd.DataFrame,
        idx: int,
        position: float,
        cash_ratio: float,
        drawdown: float,
    ) -> np.ndarray:
        row = df.iloc[idx]
        features = row[self.feature_columns].astype(float).to_numpy(dtype=np.float32)
        account = np.array([position, cash_ratio, drawdown], dtype=np.float32)
        return np.concatenate([features, account], axis=0)
