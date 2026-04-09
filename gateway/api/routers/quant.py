from __future__ import annotations

from fastapi import APIRouter, HTTPException

from gateway.api.quant_schemas import (
    QuantBacktestRequest,
    QuantExecutionRequest,
    QuantPortfolioRequest,
    QuantResearchRequest,
)
from gateway.app_runtime import runtime

router = APIRouter(prefix="/api/v1/quant", tags=["quant"])


def _quant_service():
    if runtime.quant_system is None:
        raise HTTPException(status_code=503, detail="Quant system not ready")
    return runtime.quant_system


@router.get("/platform/overview")
def get_platform_overview():
    return _quant_service().build_platform_overview()


@router.get("/universe/default")
def get_default_universe():
    service = _quant_service()
    return {
        "universe_name": service.default_universe_name,
        "benchmark": service.default_benchmark,
        "members": [member.model_dump() for member in service.get_default_universe()],
    }


@router.post("/research/run")
def run_research_pipeline(req: QuantResearchRequest):
    return _quant_service().run_research_pipeline(
        universe_symbols=req.universe or None,
        benchmark=req.benchmark,
        research_question=req.research_question,
        capital_base=req.capital_base,
        horizon_days=req.horizon_days,
    )


@router.post("/portfolio/optimize")
def optimize_portfolio(req: QuantPortfolioRequest):
    return _quant_service().optimize_portfolio(
        universe_symbols=req.universe or None,
        benchmark=req.benchmark,
        capital_base=req.capital_base,
        research_question=req.research_question,
    )


@router.post("/backtests/run")
def run_backtest(req: QuantBacktestRequest):
    return _quant_service().run_backtest(
        strategy_name=req.strategy_name,
        universe_symbols=req.universe or None,
        benchmark=req.benchmark,
        capital_base=req.capital_base,
        lookback_days=req.lookback_days,
    )


@router.get("/backtests")
def list_backtests():
    return {"backtests": _quant_service().list_backtests()}


@router.get("/backtests/{backtest_id}")
def get_backtest(backtest_id: str):
    payload = _quant_service().get_backtest(backtest_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Backtest not found")
    return payload


@router.post("/execution/paper")
def create_execution_plan(req: QuantExecutionRequest):
    return _quant_service().create_execution_plan(
        benchmark=req.benchmark,
        capital_base=req.capital_base,
        universe_symbols=req.universe or None,
        mode=req.mode,
        submit_orders=req.submit_orders,
        max_orders=req.max_orders,
        per_order_notional=req.per_order_notional,
        order_type=req.order_type,
        time_in_force=req.time_in_force,
        extended_hours=req.extended_hours,
    )


@router.get("/execution/account")
def get_execution_account():
    return _quant_service().get_execution_account()


@router.get("/execution/orders")
def list_execution_orders(status: str = "all", limit: int = 20):
    return _quant_service().list_execution_orders(status=status, limit=limit)


@router.get("/execution/positions")
def list_execution_positions():
    return _quant_service().list_execution_positions()


@router.get("/experiments")
def list_experiments():
    return {"experiments": _quant_service().list_experiments()}
