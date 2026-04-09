
from backtest.backtest_engine import run_module


def test_backtest_engine_runs():
    result = run_module({"strategy_name": "ESG Multi-Factor Long-Only"})
    assert result["status"] == "completed"
