from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, status

from gateway.api.quant_schemas import (
    QuantBacktestRequest,
    QuantExecutionRequest,
    QuantKillSwitchRequest,
    QuantOrderActionRequest,
    QuantP1StackRequest,
    QuantP2DecisionRequest,
    QuantPortfolioRequest,
    QuantResearchRequest,
    QuantValidationRequest,
)
from gateway.app_runtime import runtime
from gateway.config import settings
from gateway.ops.security import authorize_api_key, is_local_origin

router = APIRouter(prefix="/api/v1/quant", tags=["quant"])


def _quant_service():
    if runtime.quant_system is None:
        raise HTTPException(status_code=503, detail="Quant system not ready")
    return runtime.quant_system


def _run_execution_request(req: QuantExecutionRequest):
    if str(req.mode or "").strip().lower() == "kill":
        return _quant_service().set_execution_kill_switch(
            enabled=True,
            reason="Legacy execution UI requested emergency stop.",
        )

    return _quant_service().create_execution_plan(
        benchmark=req.benchmark,
        capital_base=req.capital_base,
        universe_symbols=req.universe or None,
        broker=req.broker,
        mode=req.mode,
        submit_orders=req.submit_orders,
        max_orders=req.max_orders,
        per_order_notional=req.per_order_notional,
        order_type=req.order_type,
        time_in_force=req.time_in_force,
        extended_hours=req.extended_hours,
        allow_duplicates=req.allow_duplicates,
    )


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
        preset_name=req.preset_name,
        objective=req.objective,
        max_position_weight=req.max_position_weight,
        max_sector_concentration=req.max_sector_concentration,
        esg_floor=req.esg_floor,
    )


@router.get("/p1/status")
def get_p1_suite_status():
    return _quant_service().p1_suite.status()


@router.post("/p1/stack/run")
def run_p1_stack(req: QuantP1StackRequest):
    return _quant_service().build_p1_stack_report(
        universe_symbols=req.universe or None,
        benchmark=req.benchmark,
        capital_base=req.capital_base,
        research_question=req.research_question,
    )


@router.get("/p2/status")
def get_p2_stack_status():
    return _quant_service().p2_stack.status()


@router.post("/p2/decision/run")
def run_p2_decision(req: QuantP2DecisionRequest):
    return _quant_service().build_p2_decision_report(
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
    return _run_execution_request(req)


@router.post("/execution/run")
def create_execution_plan_legacy(req: QuantExecutionRequest):
    return _run_execution_request(req)


@router.get("/execution/brokers")
def list_execution_brokers():
    return {"brokers": _quant_service().list_execution_brokers()}


@router.get("/execution/account")
def get_execution_account(broker: str = "alpaca"):
    return _quant_service().get_execution_account(broker=broker)


@router.get("/execution/controls")
def get_execution_controls():
    return _quant_service().get_execution_controls()


@router.post("/execution/kill-switch")
def set_execution_kill_switch(req: QuantKillSwitchRequest):
    return _quant_service().set_execution_kill_switch(enabled=req.enabled, reason=req.reason)


@router.get("/execution/monitor")
def get_execution_monitor(broker: str = "alpaca", execution_id: str | None = None, limit: int = 20):
    return _quant_service().build_execution_monitor(broker=broker, execution_id=execution_id, order_limit=limit)


@router.websocket("/execution/live/ws")
async def execution_live_stream(
    websocket: WebSocket,
    broker: str = "alpaca",
    execution_id: str | None = None,
    limit: int = 20,
):
    presented = (
        websocket.query_params.get("api_key")
        or websocket.headers.get("x-api-key", "").strip()
        or websocket.headers.get("authorization", "").removeprefix("Bearer ").strip()
    )
    client_host = str(getattr(websocket.client, "host", "") or "")
    request_host = str(websocket.url.hostname or "")
    if (
        not authorize_api_key("execution", presented)
        and not (
            bool(getattr(settings, "AUTH_ALLOW_LOCALHOST_DEV", True))
            and is_local_origin(client_host=client_host, request_host=request_host)
        )
    ):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Missing or invalid execution API key.")
        return

    await websocket.accept()
    refresh_seconds = max(2, int(getattr(settings, "EXECUTION_REALTIME_REFRESH_SECONDS", 5) or 5))
    try:
        while True:
            payload = _quant_service().build_execution_monitor(
                broker=broker,
                execution_id=execution_id,
                order_limit=limit,
            )
            await websocket.send_json(payload)
            await asyncio.sleep(refresh_seconds)
    except WebSocketDisconnect:
        return


@router.get("/execution/orders")
def list_execution_orders(broker: str = "alpaca", status: str = "all", limit: int = 20):
    return _quant_service().list_execution_orders(broker=broker, status=status, limit=limit)


@router.get("/execution/orders/{order_id}")
def get_execution_order(order_id: str, broker: str = "alpaca", execution_id: str | None = None):
    try:
        return _quant_service().get_execution_order(order_id=order_id, broker=broker, execution_id=execution_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/execution/orders/{order_id}/cancel")
def cancel_execution_order(order_id: str, req: QuantOrderActionRequest):
    try:
        return _quant_service().cancel_execution_order(
            order_id=order_id,
            broker=req.broker,
            execution_id=req.execution_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/execution/orders/{order_id}/retry")
def retry_execution_order(order_id: str, req: QuantOrderActionRequest):
    try:
        return _quant_service().retry_execution_order(
            order_id=order_id,
            broker=req.broker,
            execution_id=req.execution_id,
            per_order_notional=req.per_order_notional,
            order_type=req.order_type,
            time_in_force=req.time_in_force,
            extended_hours=req.extended_hours,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/execution/journal/{execution_id}")
def get_execution_journal(execution_id: str):
    try:
        return _quant_service().get_execution_journal(execution_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/execution/journal/{execution_id}/sync")
def sync_execution_journal(execution_id: str, broker: str | None = None):
    try:
        return _quant_service().sync_execution_journal(execution_id=execution_id, broker=broker)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/execution/positions")
def list_execution_positions(broker: str = "alpaca"):
    return _quant_service().list_execution_positions(broker=broker)


@router.post("/validation/run")
def run_alpha_validation(req: QuantValidationRequest):
    return _quant_service().run_alpha_validation(
        strategy_name=req.strategy_name,
        benchmark=req.benchmark,
        universe_symbols=req.universe or None,
        capital_base=req.capital_base,
        in_sample_days=req.in_sample_days,
        out_of_sample_days=req.out_of_sample_days,
        walk_forward_windows=req.walk_forward_windows,
        slippage_bps=req.slippage_bps,
        impact_cost_bps=req.impact_cost_bps,
    )


@router.get("/experiments")
def list_experiments():
    return {"experiments": _quant_service().list_experiments()}
