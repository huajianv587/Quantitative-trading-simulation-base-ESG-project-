
from gateway.quant.service import get_quant_system


def run_module(payload: dict | None = None) -> dict:
    payload = payload or {}
    result = get_quant_system().run_backtest(
        strategy_name=payload.get("strategy_name", "ESG Multi-Factor Long-Only"),
        universe_symbols=payload.get("universe") or None,
        benchmark=payload.get("benchmark"),
        capital_base=payload.get("capital_base"),
        lookback_days=payload.get("lookback_days", 126),
    )
    return {"status": "completed", "result": result}
