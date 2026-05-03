from __future__ import annotations

import matplotlib
import pandas as pd

from quant_rl.reporting.plotting import plot_equity_curve


def test_rl_equity_plot_uses_headless_backend(tmp_path):
    output_path = tmp_path / "equity.png"
    history = pd.DataFrame({"timestamp": pd.date_range("2026-01-01", periods=3), "equity": [1.0, 1.1, 1.2]})

    result = plot_equity_curve(history, output_path)

    assert matplotlib.get_backend().lower() == "agg"
    assert result == str(output_path)
    assert output_path.exists()
