from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, status
from typing import Any

from blueprint_runtime import (
    build_capabilities_report,
    build_reporting_production,
    check_infrastructure_production,
    evaluate_risk_suite_production,
    predict_model_production,
    run_advanced_backtest_production,
    run_analysis_production,
    run_data_pipeline_production,
    train_model_production,
)
from gateway.api.quant_schemas import (
    QuantBacktestRequest,
    QuantBacktestSweepRequest,
    QuantAlpacaPaperReconcileRequest,
    QuantDatasetBuildRequest,
    QuantDailyDigestSendRequest,
    QuantDecisionExplainRequest,
    QuantExecutionRequest,
    QuantFactorDiscoveryRequest,
    QuantKillSwitchRequest,
    QuantIntelligenceScanRequest,
    QuantMarketDepthReplayRequest,
    QuantOrderActionRequest,
    QuantOutcomeEvaluateRequest,
    QuantP1StackRequest,
    QuantP2DecisionRequest,
    QuantPaperOutcomesSettleRequest,
    QuantPaperPerformanceBackfillRequest,
    QuantPaperPerformanceSnapshotRequest,
    QuantPortfolioRequest,
    QuantPromotionEvaluateRequest,
    QuantResearchQualityRequest,
    QuantResearchRequest,
    QuantShadowRetrainRequest,
    QuantWorkflowRunRequest,
    ResearchContextResponse,
    QuantSimulationScenarioRequest,
    QuantStorageBackupRequest,
    QuantValidationRequest,
    QuantWeeklyDigestSendRequest,
)
from gateway.app_runtime import runtime
from gateway.config import settings
from gateway.ops.security import authorize_api_key, is_local_origin
from gateway.quant.intelligence import QuantIntelligenceService
from gateway.quant.intelligence_models import SimulationScenario

router = APIRouter(prefix="/api/v1/quant", tags=["quant"])


def _quant_service():
    if runtime.quant_system is None:
        raise HTTPException(status_code=503, detail="Quant system not ready")
    return runtime.quant_system


def _intelligence_service():
    return QuantIntelligenceService(_quant_service())


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
        live_confirmed=req.live_confirmed,
        operator_confirmation=req.operator_confirmation,
        strategy_id=req.strategy_id,
    )


@router.get("/platform/overview")
def get_platform_overview():
    return _quant_service().build_platform_overview()


@router.get("/platform/dashboard-summary")
def get_dashboard_summary(provider: str = "auto"):
    return _quant_service().build_dashboard_summary(provider=provider)


@router.get("/platform/dashboard-secondary")
def get_dashboard_secondary(provider: str = "auto"):
    return _quant_service().build_dashboard_secondary(provider=provider)


@router.get("/dashboard/chart")
def get_dashboard_chart(symbol: str | None = None, timeframe: str = "1D", provider: str = "auto"):
    return _quant_service().build_dashboard_chart(symbol=symbol, timeframe=timeframe, provider=provider)


@router.get("/universe/default")
def get_default_universe():
    service = _quant_service()
    return {
        "universe_name": service.default_universe_name,
        "benchmark": service.default_benchmark,
        "members": [member.model_dump() for member in service.get_default_universe()],
    }


@router.get("/capabilities")
def get_blueprint_capabilities():
    return build_capabilities_report()


@router.post("/analysis/run")
def run_blueprint_analysis(payload: dict[str, Any] | None = None):
    return run_analysis_production(payload or {})


@router.post("/models/train")
def train_blueprint_model(payload: dict[str, Any] | None = None):
    return train_model_production(payload or {})


@router.post("/models/predict")
def predict_blueprint_model(payload: dict[str, Any] | None = None):
    return predict_model_production(payload or {})


@router.post("/data/pipeline/run")
def run_blueprint_data_pipeline(payload: dict[str, Any] | None = None):
    return run_data_pipeline_production(payload or {})


@router.post("/risk/evaluate")
def evaluate_blueprint_risk(payload: dict[str, Any] | None = None):
    return evaluate_risk_suite_production(payload or {})


@router.post("/backtest/advanced/run")
def run_blueprint_advanced_backtest(payload: dict[str, Any] | None = None):
    return run_advanced_backtest_production(payload or {})


@router.post("/infrastructure/check")
def check_blueprint_infrastructure(payload: dict[str, Any] | None = None):
    return check_infrastructure_production(payload or {})


@router.post("/reporting/build")
def build_blueprint_reporting(payload: dict[str, Any] | None = None):
    return build_reporting_production(payload or {})


@router.post("/research/run")
def run_research_pipeline(req: QuantResearchRequest):
    return _quant_service().run_research_pipeline(
        universe_symbols=req.universe or None,
        benchmark=req.benchmark,
        research_question=req.research_question,
        capital_base=req.capital_base,
        horizon_days=req.horizon_days,
    )


@router.get("/research/context", response_model=ResearchContextResponse)
def get_research_context(symbol: str | None = None, provider: str = "auto", limit: int = 6):
    return _quant_service().build_research_context(symbol=symbol, provider=provider, limit=limit)


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


@router.post("/workflows/paper-strategy/run")
def run_hybrid_paper_strategy_workflow(req: QuantWorkflowRunRequest):
    return _quant_service().run_hybrid_paper_strategy_workflow(
        universe_symbols=req.universe or None,
        benchmark=req.benchmark,
        capital_base=req.capital_base,
        strategy_mode=req.strategy_mode,
        rl_algorithm=req.rl_algorithm,
        rl_action_type=req.rl_action_type,
        rl_dataset_path=req.rl_dataset_path,
        rl_checkpoint_path=req.rl_checkpoint_path,
        submit_orders=req.submit_orders,
        mode=req.mode,
        broker=req.broker,
        max_orders=req.max_orders,
        per_order_notional=req.per_order_notional,
        allow_synthetic_execution=req.allow_synthetic_execution,
        force_refresh=req.force_refresh,
    )


@router.get("/workflows/paper-strategy/{workflow_id}")
def get_hybrid_paper_strategy_workflow(workflow_id: str):
    payload = _quant_service().get_hybrid_paper_strategy_workflow(workflow_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Workflow run not found")
    return payload


@router.get("/paper/performance")
def get_paper_performance(window_days: int = 90):
    return _quant_service().build_paper_performance_report(window_days=window_days)


@router.post("/paper/performance/snapshot")
def create_paper_performance_snapshot(req: QuantPaperPerformanceSnapshotRequest | None = None):
    payload = req or QuantPaperPerformanceSnapshotRequest()
    return _quant_service().capture_paper_performance_snapshot(
        workflow_id=payload.workflow_id,
        execution_id=payload.execution_id,
        benchmark=payload.benchmark,
        broker=payload.broker,
        mode=payload.mode,
        force_refresh=payload.force_refresh,
    )


@router.post("/paper/performance/backfill")
def backfill_paper_performance(req: QuantPaperPerformanceBackfillRequest | None = None):
    payload = req or QuantPaperPerformanceBackfillRequest()
    return _quant_service().backfill_paper_performance(
        days=payload.days,
        benchmark=payload.benchmark,
        broker=payload.broker,
        mode=payload.mode,
        force_refresh=payload.force_refresh,
    )


@router.get("/paper/daily-digest/latest")
def get_latest_paper_daily_digest(phase: str = "postclose", session_date: str | None = None):
    return _quant_service().build_quant_daily_digest(phase=phase, session_date=session_date)


@router.post("/paper/daily-digest/send")
def send_paper_daily_digest(req: QuantDailyDigestSendRequest | None = None):
    payload = req or QuantDailyDigestSendRequest()
    return _quant_service().send_quant_daily_digest(
        phase=payload.phase,
        session_date=payload.session_date,
        recipients=payload.recipients or None,
        channels=payload.channels or None,
    )


@router.get("/paper/weekly-digest/latest")
def get_latest_paper_weekly_digest(session_date: str | None = None, window_days: int = 7):
    return _quant_service().build_quant_weekly_digest(session_date=session_date, window_days=window_days)


@router.post("/paper/weekly-digest/send")
def send_paper_weekly_digest(req: QuantWeeklyDigestSendRequest | None = None):
    payload = req or QuantWeeklyDigestSendRequest()
    return _quant_service().send_quant_weekly_digest(
        session_date=payload.session_date,
        window_days=payload.window_days,
        recipients=payload.recipients or None,
        channels=payload.channels or None,
    )


@router.get("/session-evidence/latest")
def get_latest_session_evidence():
    payload = _quant_service().latest_session_evidence()
    if payload is None:
        return {
            "status": "degraded",
            "available": False,
            "reason": "session_evidence_not_found",
            "session_date": None,
            "complete": False,
            "stages": {},
            "stage_order": [],
            "missing_stages": [
                "preopen",
                "workflow",
                "paper_submit",
                "broker_sync",
                "outcomes",
                "snapshot",
                "promotion",
                "digest",
                "backup",
            ],
            "next_actions": ["run_scheduler_session_or_paper_workflow"],
        }
    return payload


@router.get("/session-evidence/{session_date}")
def get_session_evidence(session_date: str):
    payload = _quant_service().get_session_evidence(session_date)
    if payload is None:
        raise HTTPException(status_code=404, detail="Session evidence not found")
    return payload


@router.post("/execution/reconcile/alpaca-paper")
def reconcile_alpaca_paper_orders(req: QuantAlpacaPaperReconcileRequest | None = None):
    payload = req or QuantAlpacaPaperReconcileRequest()
    return _quant_service().reconcile_alpaca_paper_orders(session_date=payload.session_date)


@router.post("/storage/backup")
def backup_quant_storage(req: QuantStorageBackupRequest | None = None):
    payload = req or QuantStorageBackupRequest()
    return _quant_service().backup_quant_storage(session_date=payload.session_date)


@router.get("/submit-locks")
def list_submit_locks(session_date: str | None = None, status: str | None = None, limit: int = 100):
    return _quant_service().list_submit_locks(session_date=session_date, status=status, limit=limit)


@router.get("/paper/outcomes")
def list_paper_outcomes(
    limit: int = 200,
    record_kind: str | None = None,
    status: str | None = None,
    symbol: str | None = None,
):
    return _quant_service().list_paper_outcomes(
        limit=limit,
        record_kind=record_kind,
        status=status,
        symbol=symbol,
    )


@router.post("/paper/outcomes/settle")
def settle_paper_outcomes(req: QuantPaperOutcomesSettleRequest | None = None):
    payload = req or QuantPaperOutcomesSettleRequest()
    return _quant_service().settle_paper_outcomes(
        outcome_id=payload.outcome_id,
        force_refresh=payload.force_refresh,
        limit=payload.limit,
    )


@router.get("/promotion/report")
def get_promotion_report(window_days: int = 90):
    return _quant_service().build_promotion_report(window_days=window_days, persist=False)


@router.post("/promotion/evaluate")
def evaluate_promotion(req: QuantPromotionEvaluateRequest | None = None):
    payload = req or QuantPromotionEvaluateRequest()
    return _quant_service().evaluate_promotion(window_days=payload.window_days, persist=payload.persist)


@router.get("/promotion/timeline")
def get_promotion_timeline(limit: int = 50):
    return _quant_service().build_promotion_timeline(limit=limit)


@router.post("/models/shadow-retrain/run")
def run_shadow_retrain(req: QuantShadowRetrainRequest | None = None):
    payload = req or QuantShadowRetrainRequest()
    return _quant_service().run_shadow_retrain(model_key=payload.model_key, force=payload.force)


@router.get("/models/shadow-retrain/latest")
def get_latest_shadow_retrain():
    return _quant_service().latest_shadow_retrain()


@router.get("/deployment/preflight")
def get_deployment_preflight(profile: str = "paper_cloud", dry_run: bool = False):
    service = _quant_service()
    if dry_run and hasattr(service, "get_cached_deployment_preflight"):
        return service.get_cached_deployment_preflight(profile=profile)
    try:
        return service.build_deployment_preflight(profile=profile, dry_run=dry_run)
    except TypeError:
        return service.build_deployment_preflight(profile=profile)


@router.post("/deployment/preflight/evaluate")
def evaluate_deployment_preflight(profile: str = "paper_cloud"):
    service = _quant_service()
    if hasattr(service, "evaluate_deployment_preflight"):
        return service.evaluate_deployment_preflight(profile=profile)
    return service.build_deployment_preflight(profile=profile)


@router.get("/trading-calendar/status")
def get_trading_calendar_status():
    return _quant_service().get_trading_calendar_status()


@router.get("/observability/paper-workflow")
def get_paper_workflow_observability(window_days: int = 30):
    return _quant_service().build_paper_workflow_observability(window_days=window_days)


@router.get("/slo/paper-workflow")
def get_paper_workflow_slo(window_days: int = 30):
    return _quant_service().build_paper_workflow_slo(window_days=window_days)


@router.post("/observability/paper-workflow/evaluate")
def evaluate_paper_workflow_observability(window_days: int = 30):
    return _quant_service().evaluate_paper_workflow_observability(window_days=window_days)


@router.post("/backtests/run")
def run_backtest(req: QuantBacktestRequest):
    return _quant_service().run_backtest(
        strategy_name=req.strategy_name,
        universe_symbols=req.universe or None,
        benchmark=req.benchmark,
        capital_base=req.capital_base,
        lookback_days=req.lookback_days,
        market_data_provider=req.market_data_provider,
        force_refresh=req.force_refresh,
    )


@router.post("/backtests/sweep")
def run_backtest_sweep(req: QuantBacktestSweepRequest):
    return _quant_service().run_backtest_sweep(
        strategy_name=req.strategy_name,
        universe_symbols=req.universe or None,
        benchmark=req.benchmark,
        capital_base=req.capital_base,
        lookback_days=req.lookback_days,
        market_data_provider=req.market_data_provider,
        force_refresh=req.force_refresh,
        parameter_grid=req.parameter_grid,
        top_k=req.top_k,
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


@router.get("/backtests/sweep/{run_id}")
def get_backtest_sweep(run_id: str):
    payload = _quant_service().get_backtest_sweep(run_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Backtest sweep not found")
    return payload


@router.get("/reports/tearsheet/{backtest_id}")
def get_backtest_tearsheet(backtest_id: str):
    try:
        return _quant_service().build_tearsheet(backtest_id, persist=True)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


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
def get_execution_account(broker: str = "alpaca", mode: str = "paper"):
    return _quant_service().get_execution_account(broker=broker, mode=mode)


@router.get("/execution/controls")
def get_execution_controls():
    return _quant_service().get_execution_controls()


@router.get("/execution/paper-gate")
def get_paper_gate_report(persist: bool = False):
    return _quant_service().build_paper_gate_report(persist=persist)


@router.post("/execution/kill-switch")
def set_execution_kill_switch(req: QuantKillSwitchRequest):
    return _quant_service().set_execution_kill_switch(enabled=req.enabled, reason=req.reason)


@router.get("/execution/monitor")
def get_execution_monitor(broker: str = "alpaca", execution_id: str | None = None, limit: int = 20, mode: str = "paper"):
    return _quant_service().build_execution_monitor(broker=broker, execution_id=execution_id, order_limit=limit, mode=mode)


@router.websocket("/execution/live/ws")
async def execution_live_stream(
    websocket: WebSocket,
    broker: str = "alpaca",
    execution_id: str | None = None,
    limit: int = 20,
    mode: str = "paper",
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
                mode=mode,
            )
            await websocket.send_json(payload)
            await asyncio.sleep(refresh_seconds)
    except WebSocketDisconnect:
        return


@router.get("/execution/orders")
def list_execution_orders(broker: str = "alpaca", status: str = "all", limit: int = 20, mode: str = "paper"):
    return _quant_service().list_execution_orders(broker=broker, status=status, limit=limit, mode=mode)


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
def list_execution_positions(broker: str = "alpaca", mode: str = "paper"):
    return _quant_service().list_execution_positions(broker=broker, mode=mode)


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


@router.post("/intelligence/scan")
def scan_intelligence(req: QuantIntelligenceScanRequest):
    return _intelligence_service().scan(
        universe_symbols=req.universe or None,
        query=req.query,
        decision_time=req.decision_time,
        live_connectors=req.live_connectors,
        mode=req.mode,
        providers=req.providers or None,
        quota_guard=req.quota_guard,
        limit=req.limit,
        persist=req.persist,
    )


@router.get("/intelligence/evidence")
def get_intelligence_evidence(symbol: str | None = None, limit: int = 20):
    return _intelligence_service().list_evidence(symbol=symbol, limit=limit)


@router.post("/factors/discover")
def discover_factors(req: QuantFactorDiscoveryRequest):
    return _intelligence_service().discover_factors(
        universe_symbols=req.universe or None,
        query=req.query,
        horizon_days=req.horizon_days,
        decision_time=req.decision_time,
        evidence_run_id=req.evidence_run_id,
        as_of_time=req.as_of_time,
        mode=req.mode,
        providers=req.providers or None,
        quota_guard=req.quota_guard,
        required_data_tier=req.required_data_tier,
    )


@router.post("/research/datasets/build")
def build_dataset_manifest(req: QuantDatasetBuildRequest):
    return _intelligence_service().build_dataset_manifest(
        universe_symbols=req.universe or None,
        query=req.query,
        as_of_time=req.as_of_time,
        decision_time=req.decision_time,
        mode=req.mode,
        providers=req.providers or None,
        quota_guard=req.quota_guard,
        frequency=req.frequency,
        include_intraday=req.include_intraday,
        required_data_tier=req.required_data_tier,
        persist=req.persist,
    )


@router.get("/research/datasets")
def list_dataset_manifests(limit: int = 20):
    return _intelligence_service().list_dataset_manifests(limit=limit)


@router.post("/research/quality/checks")
def run_research_quality_checks(req: QuantResearchQualityRequest):
    return _intelligence_service().run_research_quality_checks(
        universe_symbols=req.universe or None,
        query=req.query,
        decision_time=req.decision_time,
        as_of_time=req.as_of_time,
        evidence_run_id=req.evidence_run_id,
        mode=req.mode,
        providers=req.providers or None,
        quota_guard=req.quota_guard,
        frequency=req.frequency,
        formulas=req.formulas,
        labels=req.labels,
        timestamps=req.timestamps,
        current_constituents_only=req.current_constituents_only,
        required_data_tier=req.required_data_tier,
        persist=req.persist,
    )


@router.get("/factors/registry")
def get_factor_registry(limit: int = 50):
    return _intelligence_service().factor_registry(limit=limit)


@router.get("/market-depth/status")
def get_market_depth_status(symbols: str | None = None, require_l2: bool = False):
    values = [item.strip().upper() for item in str(symbols or "").split(",") if item.strip()]
    return _intelligence_service().market_depth_status(symbols=values or None, require_l2=require_l2)


@router.post("/market-depth/replay")
def build_market_depth_replay(req: QuantMarketDepthReplayRequest):
    return _intelligence_service().market_depth_replay(
        symbol=req.symbol,
        limit=req.limit,
        timestamps=req.timestamps or None,
        require_l2=str(req.required_data_tier or "l1").lower() == "l2",
        persist=req.persist,
    )


@router.get("/market-depth/replay/{session_id}")
def get_market_depth_replay(session_id: str):
    payload = _intelligence_service().get_market_depth_replay(session_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Market depth replay not found")
    return payload


@router.get("/market-depth/latest")
def get_market_depth_latest(symbol: str = "AAPL"):
    return _intelligence_service().market_depth_latest(symbol=symbol)


@router.websocket("/market-depth/live/ws")
async def market_depth_live_stream(
    websocket: WebSocket,
    symbols: str = "AAPL",
    require_l2: bool = False,
):
    await websocket.accept()
    refresh_seconds = max(1, int(getattr(settings, "EXECUTION_REALTIME_REFRESH_SECONDS", 5) or 5))
    symbol_list = [item.strip().upper() for item in str(symbols or "").split(",") if item.strip()]
    try:
        while True:
            await websocket.send_json(
                _intelligence_service().market_depth_live_payload(symbols=symbol_list or None, require_l2=require_l2)
            )
            await asyncio.sleep(refresh_seconds)
    except WebSocketDisconnect:
        return


@router.post("/simulate/scenario")
def simulate_scenario(req: QuantSimulationScenarioRequest):
    scenario = SimulationScenario(
        symbol=req.symbol,
        universe=req.universe,
        horizon_days=req.horizon_days,
        shock_bps=req.shock_bps,
        transaction_cost_bps=req.transaction_cost_bps,
        slippage_bps=req.slippage_bps,
        paths=req.paths,
        seed=req.seed,
        scenario_name=req.scenario_name,
        event_assumption=req.event_assumption,
        regime=req.regime,
        event_id=req.event_id,
        evidence_run_id=req.evidence_run_id,
        required_data_tier=req.required_data_tier,
    )
    return _intelligence_service().simulate_scenario(scenario)


@router.post("/decision/explain")
def explain_decision(req: QuantDecisionExplainRequest):
    try:
        return _intelligence_service().explain_decision(
            symbol=req.symbol,
            universe_symbols=req.universe or [req.symbol],
            query=req.query,
            horizon_days=req.horizon_days,
            include_simulation=req.include_simulation,
            evidence_run_id=req.evidence_run_id,
            mode=req.mode,
            providers=req.providers or None,
            quota_guard=req.quota_guard,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/decision/audit-trail")
def get_decision_audit_trail(symbol: str | None = None, limit: int = 20):
    return _intelligence_service().audit_trail(symbol=symbol, limit=limit)


@router.post("/outcomes/evaluate")
def evaluate_outcomes(req: QuantOutcomeEvaluateRequest):
    return _intelligence_service().evaluate_outcome(
        symbol=req.symbol,
        decision_id=req.decision_id,
        horizon_days=req.horizon_days,
        realized_return=req.realized_return,
        benchmark_return=req.benchmark_return,
        drawdown=req.drawdown,
        notes=req.notes,
    )
