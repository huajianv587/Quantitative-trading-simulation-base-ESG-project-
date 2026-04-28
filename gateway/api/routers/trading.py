from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from gateway.api.trading_schemas import (
    AutopilotArmRequest,
    AutopilotDisarmRequest,
    AutopilotPolicyUpdateRequest,
    PaperRewardCandidateRunRequest,
    PaperRewardSettleRequest,
    StrategyAllocationRequest,
    StrategyToggleRequest,
    TradingCycleRunRequest,
    TradingDebateRunRequest,
    TradingJobRunRequest,
    TradingRiskEvaluateRequest,
    TradingSentimentRunRequest,
    TradingWatchlistAddRequest,
)
from gateway.app_runtime import runtime
from gateway.trading.service import get_trading_service

router = APIRouter(tags=["trading"])


def _trading_service():
    if runtime.trading_service is not None:
        return runtime.trading_service
    if runtime.quant_system is None:
        raise HTTPException(status_code=503, detail="Trading service not ready")
    try:
        runtime.trading_service = get_trading_service(
            quant_system=runtime.quant_system,
            get_client=runtime.get_client,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Trading service init failed: {exc}") from exc
    return runtime.trading_service


@router.get("/api/v1/trading/schedule/status")
@router.get("/schedule/status", include_in_schema=False)
def trading_schedule_status() -> dict[str, Any]:
    return _trading_service().schedule_status()


@router.get("/api/v1/trading/watchlist")
def trading_watchlist() -> dict[str, Any]:
    return _trading_service().list_watchlist()


@router.post("/api/v1/trading/watchlist/add")
@router.post("/watchlist/add", include_in_schema=False)
def trading_watchlist_add(req: TradingWatchlistAddRequest) -> dict[str, Any]:
    return _trading_service().add_watchlist_symbol(
        symbol=req.symbol,
        esg_score=req.esg_score,
        last_sentiment=req.last_sentiment,
        note=req.note,
        enabled=req.enabled,
    )


@router.get("/api/v1/trading/review/latest")
@router.get("/review/latest", include_in_schema=False)
def trading_review_latest() -> dict[str, Any]:
    return _trading_service().latest_review()


@router.get("/api/v1/trading/alerts/today")
@router.get("/alerts/today", include_in_schema=False)
def trading_alerts_today() -> dict[str, Any]:
    return _trading_service().alerts_today()


@router.post("/api/v1/trading/sentiment/run")
def trading_sentiment_run(req: TradingSentimentRunRequest) -> dict[str, Any]:
    return _trading_service().run_sentiment(
        universe=req.universe or None,
        providers=req.providers or None,
        quota_guard=req.quota_guard,
    )


@router.post("/api/v1/trading/debate/run")
def trading_debate_run(req: TradingDebateRunRequest) -> dict[str, Any]:
    return _trading_service().run_debate(
        symbol=req.symbol,
        universe=req.universe or None,
        query=req.query,
        mode=req.mode,
        providers=req.providers or None,
        quota_guard=req.quota_guard,
        rebuttal_rounds=req.rebuttal_rounds,
    )


@router.get("/api/v1/trading/debate/runs")
def trading_debate_runs(symbol: str | None = None, limit: int = 20) -> dict[str, Any]:
    return _trading_service().debate_runs(symbol=symbol, limit=limit)


@router.post("/api/v1/trading/risk/evaluate")
def trading_risk_evaluate(req: TradingRiskEvaluateRequest) -> dict[str, Any]:
    try:
        return _trading_service().evaluate_risk(
            symbol=req.symbol,
            debate_payload=req.debate_payload,
            signal_ttl_minutes=req.signal_ttl_minutes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/api/v1/trading/risk/board")
def trading_risk_board(symbol: str | None = None, limit: int = 20) -> dict[str, Any]:
    return _trading_service().risk_board(symbol=symbol, limit=limit)


@router.post("/api/v1/trading/cycle/run")
def trading_cycle_run(req: TradingCycleRunRequest) -> dict[str, Any]:
    return _trading_service().run_trading_cycle(
        symbol=req.symbol,
        universe=req.universe or None,
        query=req.query,
        mode=req.mode,
        providers=req.providers or None,
        quota_guard=req.quota_guard,
        auto_submit=req.auto_submit,
    )


@router.post("/api/v1/trading/reward/candidates/run")
def trading_reward_candidates_run(req: PaperRewardCandidateRunRequest) -> dict[str, Any]:
    try:
        return _trading_service().run_paper_reward_candidates(
            universe=req.universe or None,
            max_candidates=req.max_candidates,
            per_order_notional=req.per_order_notional,
            benchmark=req.benchmark,
            allow_duplicates=req.allow_duplicates,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/v1/trading/reward/settle")
def trading_reward_settle(req: PaperRewardSettleRequest | None = None) -> dict[str, Any]:
    payload = req or PaperRewardSettleRequest()
    try:
        return _trading_service().settle_paper_reward_candidates(
            candidate_id=payload.candidate_id,
            force_refresh=payload.force_refresh,
            limit=payload.limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/v1/trading/reward/leaderboard")
def trading_reward_leaderboard(limit: int = 100) -> dict[str, Any]:
    return _trading_service().paper_reward_leaderboard(limit=limit)


@router.get("/api/v1/trading/monitor/status")
def trading_monitor_status() -> dict[str, Any]:
    return _trading_service().monitor_status()


@router.post("/api/v1/trading/monitor/start")
async def trading_monitor_start() -> dict[str, Any]:
    return await _trading_service().start_intraday_monitor()


@router.post("/api/v1/trading/monitor/stop")
async def trading_monitor_stop() -> dict[str, Any]:
    return await _trading_service().stop_intraday_monitor()


@router.post("/api/v1/trading/jobs/run/{job_name}")
async def trading_job_run(job_name: str, req: TradingJobRunRequest | None = None) -> dict[str, Any]:
    scheduled_for = req.scheduled_for if req else None
    return await _trading_service().run_scheduled_job(job_name, scheduled_for)


@router.get("/api/v1/trading/ops/snapshot")
def trading_ops_snapshot() -> dict[str, Any]:
    return _trading_service().trading_ops_snapshot()


@router.get("/api/v1/trading/autopilot/policy")
def trading_autopilot_policy() -> dict[str, Any]:
    return _trading_service().get_autopilot_policy()


@router.post("/api/v1/trading/autopilot/policy")
def trading_autopilot_policy_save(req: AutopilotPolicyUpdateRequest) -> dict[str, Any]:
    return _trading_service().save_autopilot_policy(req.model_dump())


@router.post("/api/v1/trading/autopilot/arm")
def trading_autopilot_arm(req: AutopilotArmRequest | None = None) -> dict[str, Any]:
    return _trading_service().arm_autopilot(armed=True if req is None else req.armed)


@router.post("/api/v1/trading/autopilot/disarm")
def trading_autopilot_disarm(req: AutopilotDisarmRequest | None = None) -> dict[str, Any]:
    return _trading_service().arm_autopilot(armed=False if req is None else req.armed)


@router.get("/api/v1/trading/strategies")
def trading_strategies() -> dict[str, Any]:
    return _trading_service().list_strategies()


@router.get("/api/v1/trading/strategies/eligibility")
def trading_strategy_eligibility(symbol: str | None = None) -> dict[str, Any]:
    return _trading_service().list_strategy_eligibility(symbol=symbol)


@router.post("/api/v1/trading/strategies/{strategy_id}/toggle")
def trading_strategy_toggle(strategy_id: str, req: StrategyToggleRequest) -> dict[str, Any]:
    return _trading_service().toggle_strategy(strategy_id=strategy_id, status=req.status)


@router.post("/api/v1/trading/strategies/{strategy_id}/allocation")
def trading_strategy_allocate(strategy_id: str, req: StrategyAllocationRequest) -> dict[str, Any]:
    return _trading_service().allocate_strategy(
        strategy_id=strategy_id,
        capital_allocation=req.capital_allocation,
        max_symbols=req.max_symbols,
        status=req.status,
    )


@router.get("/api/v1/trading/execution-path/status")
def trading_execution_path_status() -> dict[str, Any]:
    return _trading_service().execution_path_status()


@router.get("/api/v1/trading/dashboard/state")
def trading_dashboard_state(provider: str = "auto") -> dict[str, Any]:
    return _trading_service().dashboard_state(provider=provider)


@router.get("/api/v1/trading/fusion/status")
def trading_fusion_status() -> dict[str, Any]:
    return _trading_service().fusion_reference_manifest()
