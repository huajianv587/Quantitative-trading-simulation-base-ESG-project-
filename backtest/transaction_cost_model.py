from blueprint_runtime import run_backtest_blueprint


def run_module(payload: dict | None = None) -> dict:
    return run_backtest_blueprint("transaction_cost_model", payload)
