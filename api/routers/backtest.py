
from fastapi import APIRouter

from gateway.quant.service import get_quant_system

router = APIRouter(prefix="/backtest", tags=["backtest"])


@router.post("/run")
def run_backtest(payload: dict):
    return get_quant_system().run_backtest(
        strategy_name=payload.get("strategy_name", "ESG Multi-Factor Long-Only"),
        universe_symbols=payload.get("universe") or None,
        benchmark=payload.get("benchmark"),
        capital_base=payload.get("capital_base"),
        lookback_days=payload.get("lookback_days", 126),
    )


@router.get("/history")
def list_backtests():
    return {"backtests": get_quant_system().list_backtests()}
