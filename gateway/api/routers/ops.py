from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Query, Request

from gateway.app_runtime import runtime
from gateway.api.quant_schemas import ModelReleaseRequest
from gateway.config import settings
from gateway.ops.security import auth_coverage_for_app, auth_posture

router = APIRouter(prefix="/ops", tags=["ops"])
api_v1_router = APIRouter(prefix="/api/v1/ops", tags=["ops"])


def _quant_service():
    return runtime.quant_system


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _resolve_runtime_path(raw: str | None, fallback: str) -> Path:
    path = Path(str(raw or "").strip() or fallback)
    if not path.is_absolute():
        path = _project_root() / path
    return path


def _load_json_file(path: Path) -> dict[str, Any]:
    try:
        if not path.exists():
            return {}
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception as exc:
        return {"_load_error": str(exc), "_path": str(path)}


def _parse_timestamp(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _heartbeat_status() -> dict[str, Any]:
    path = _resolve_runtime_path(
        getattr(settings, "SCHEDULER_HEARTBEAT_PATH", ""),
        "storage/quant/scheduler/heartbeat.json",
    )
    payload = _load_json_file(path)
    observed = _parse_timestamp(payload.get("updated_at") or payload.get("generated_at"))
    stale_after = max(30, int(getattr(settings, "WATCHDOG_HEARTBEAT_STALE_SECONDS", 300) or 300))
    age_seconds = None
    stale = True
    if observed is not None:
        age_seconds = max(0.0, (datetime.now(timezone.utc) - observed).total_seconds())
        stale = age_seconds > stale_after
    return {
        "path": str(path),
        "exists": path.exists(),
        "last_seen": observed.isoformat() if observed else None,
        "age_seconds": age_seconds,
        "stale_after_seconds": stale_after,
        "stale": stale,
        "payload": payload,
    }


def _scheduler_runtime_state() -> dict[str, Any]:
    path = _resolve_runtime_path(
        getattr(settings, "SCHEDULER_STATE_PATH", ""),
        "storage/quant/scheduler/runtime_state.json",
    )
    payload = _load_json_file(path)
    payload["_path"] = str(path)
    payload["_exists"] = path.exists()
    return payload


def _paper_broker_status(quant_service: Any) -> dict[str, Any]:
    if quant_service is None or not hasattr(quant_service, "get_execution_account"):
        return {"ready": False, "reason": "quant_service_unavailable"}
    try:
        account = quant_service.get_execution_account(
            broker=getattr(settings, "QUANT_BROKER_DEFAULT", "alpaca"),
            mode="paper",
        )
    except Exception as exc:
        return {"ready": False, "reason": "paper_account_probe_failed", "error": str(exc)}
    ready = bool(account.get("connected")) and bool(account.get("paper_ready", True)) and not account.get("block_reason")
    return {
        "ready": ready,
        "connected": bool(account.get("connected")),
        "paper_ready": bool(account.get("paper_ready", ready)),
        "block_reason": account.get("block_reason"),
        "warnings": account.get("warnings", []),
        "market_clock": account.get("market_clock", {}),
    }


def _latest_rlvr_status(quant_service: Any, limit: int = 100) -> dict[str, Any]:
    if quant_service is None or not hasattr(quant_service, "storage"):
        return {"candidate_count": 0, "settled_count": 0, "partial_count": 0, "latest": None}
    try:
        rows = quant_service.storage.list_records("paper_reward_candidates")[:limit]
    except Exception as exc:
        return {"candidate_count": 0, "settled_count": 0, "partial_count": 0, "latest": None, "error": str(exc)}
    latest = rows[0] if rows else None
    return {
        "candidate_count": len(rows),
        "settled_count": sum(1 for row in rows if (row.get("rlvr") or {}).get("final_score") is not None),
        "partial_count": sum(1 for row in rows if (row.get("rlvr") or {}).get("partial_score") is not None),
        "bandit_updated_count": sum(1 for row in rows if row.get("bandit_updated_at") or (row.get("rlvr") or {}).get("bandit_updated_at")),
        "latest": {
            "candidate_id": latest.get("candidate_id"),
            "symbol": latest.get("symbol"),
            "status": latest.get("status"),
            "rlvr": latest.get("rlvr"),
            "created_at": latest.get("created_at"),
        } if latest else None,
    }


def _promotion_gate_status(quant_service: Any) -> dict[str, Any]:
    if quant_service is None or not hasattr(quant_service, "build_promotion_report"):
        return {"available": False, "reason": "promotion_service_unavailable"}
    try:
        report = quant_service.build_promotion_report(window_days=90, persist=False)
    except Exception as exc:
        return {"available": False, "reason": "promotion_report_failed", "error": str(exc)}
    metrics = ((report.get("performance") or {}).get("metrics") or {})
    return {
        "available": True,
        "promotion_status": report.get("promotion_status"),
        "valid_days": metrics.get("valid_days", 0),
        "required_valid_days": 60,
        "paper_gate": report.get("paper_gate", {}),
        "policy_evaluation": report.get("policy_evaluation", {}),
    }


@router.get("/runtime")
def runtime_snapshot(request: Request) -> dict[str, Any]:
    quant_service = _quant_service()
    brokers = quant_service.list_execution_brokers() if quant_service is not None else []
    auth = auth_posture()
    auth["coverage"] = auth_coverage_for_app(request.app)
    storage_status = quant_service.storage.status() if quant_service is not None else {}
    runtime_state = {
        "lazy_components": dict(getattr(runtime, "lazy_components", {}) or {}),
        "frontend_source": getattr(request.app.state, "frontend_source", None),
        "frontend_path": getattr(request.app.state, "frontend_path", None),
    }
    diagnostics = (
        quant_service.build_runtime_diagnostics(runtime_state=runtime_state)
        if quant_service is not None and hasattr(quant_service, "build_runtime_diagnostics")
        else {}
    )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "app_mode": getattr(runtime, "app_mode", None) or settings.APP_MODE,
        "auth": auth,
        "startup": runtime_state,
        "modules": {
            "rag": runtime.query_engine is not None if hasattr(runtime, "query_engine") else False,
            "esg_scorer": runtime.esg_scorer is not None,
            "report_scheduler": runtime.report_scheduler is not None,
            "quant_system": quant_service is not None,
        },
        "brokers": brokers,
        "storage": {
            **storage_status,
            "backend_status": storage_status,
        },
        "diagnostics": diagnostics,
        "request_path": request.url.path,
    }


@router.get("/online-status")
@api_v1_router.get("/online-status")
def online_status_snapshot() -> dict[str, Any]:
    quant_service = _quant_service()
    state = _scheduler_runtime_state()
    heartbeat = _heartbeat_status()
    paper_broker = _paper_broker_status(quant_service)
    latest_execution_id = (
        (state.get("hybrid_workflow", {}) or {}).get("execution_id")
        or (state.get("execution", {}) or {}).get("execution_id")
    )
    execution_monitor: dict[str, Any] = {}
    if quant_service is not None and latest_execution_id and hasattr(quant_service, "build_execution_monitor"):
        try:
            execution_monitor = quant_service.build_execution_monitor(
                broker=getattr(settings, "QUANT_BROKER_DEFAULT", "alpaca"),
                execution_id=latest_execution_id,
                order_limit=10,
                mode="paper",
            )
        except Exception as exc:
            execution_monitor = {"error": str(exc), "execution_id": latest_execution_id}
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ready": bool(not heartbeat.get("stale") and paper_broker.get("ready")),
        "scheduler": {
            "owner": getattr(settings, "SCHEDULER_OWNER", "quant-scheduler"),
            "execution_engine": getattr(settings, "SCHEDULER_EXECUTION_ENGINE", "hybrid_paper_workflow"),
            "auto_submit": bool(getattr(settings, "SCHEDULER_AUTO_SUBMIT", False)),
            "heartbeat": heartbeat,
            "runtime_state": {
                "path": state.get("_path"),
                "exists": state.get("_exists"),
                "trade_date": state.get("trade_date"),
                "session_date": state.get("session_date"),
                "preopen": state.get("preopen", {}),
                "hybrid_workflow": state.get("hybrid_workflow", {}),
                "execution": state.get("execution", {}),
                "sync": state.get("sync", {}),
                "automation": state.get("automation", {}),
                "circuit_breakers": state.get("circuit_breakers", {}),
                "failure_counters": state.get("failure_counters", {}),
            },
        },
        "paper_broker": paper_broker,
        "latest_execution": execution_monitor,
        "rlvr": _latest_rlvr_status(quant_service),
        "paper_60d_gate": _promotion_gate_status(quant_service),
        "config": {
            "paper_reward_submit_enabled": bool(getattr(settings, "PAPER_REWARD_SUBMIT_ENABLED", False)),
            "rlvr_horizons": getattr(settings, "RLVR_HORIZONS", "1,3,5"),
            "rlvr_weights": getattr(settings, "RLVR_WEIGHTS", "0.30,0.30,0.40"),
            "max_execution_symbols": getattr(settings, "SCHEDULER_MAX_EXECUTION_SYMBOLS", 2),
            "max_daily_notional_usd": getattr(settings, "SCHEDULER_MAX_DAILY_NOTIONAL_USD", 1000.0),
            "live_trading_enabled": bool(getattr(settings, "ALPACA_ENABLE_LIVE_TRADING", False)),
        },
    }


@router.post("/scheduler/recover")
@api_v1_router.post("/scheduler/recover")
def recover_scheduler_workflow() -> dict[str, Any]:
    quant_service = _quant_service()
    if quant_service is None:
        return {
            "ok": False,
            "detail": "Quant service not ready",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
    from scripts import quant_signal_scheduler as scheduler_script

    state = scheduler_script.load_json(scheduler_script.scheduler_state_path(), default={})
    result = scheduler_script.run_recovery_cycle(quant_service, state)
    return {
        "ok": True,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "recovery": result,
    }


@router.get("/metrics")
def metrics_snapshot() -> dict[str, Any]:
    quant_service = _quant_service()
    if quant_service is None:
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "counters": {},
            "gauges": {},
        }

    storage = quant_service.storage
    executions = storage.list_records("executions")
    journals = storage.list_records("execution_journals")
    validations = storage.list_records("validations")
    backtests = storage.list_records("backtests")
    audit_events = storage.list_records("audit_summary")
    controls = quant_service.get_execution_controls()
    latest_execution_id = executions[0].get("execution_id") if executions else None
    latest_monitor = quant_service.build_execution_monitor(
        broker="alpaca",
        execution_id=latest_execution_id,
        order_limit=10,
    )
    broker_count = sum(1 for broker in quant_service.list_execution_brokers() if broker["configured"])
    state_counts: dict[str, int] = {}
    routed_orders = 0
    filled_orders = 0
    for journal in journals:
        state = str(journal.get("current_state") or "unknown")
        state_counts[state] = state_counts.get(state, 0) + 1
        for record in journal.get("records", []):
            if str(record.get("current_state") or "").lower() in {"accepted", "new", "pending", "partially_filled", "filled"}:
                routed_orders += 1
            if str(record.get("current_state") or "").lower() == "filled":
                filled_orders += 1
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "counters": {
            "executions_total": len(executions),
            "execution_journals_total": len(journals),
            "validations_total": len(validations),
            "backtests_total": len(backtests),
            "audit_summary_total": len(audit_events),
        },
        "gauges": {
            "configured_brokers": broker_count,
            "last_execution_submitted": bool(executions and executions[0].get("submitted")),
            "storage_supabase_ready": bool(storage.status().get("supabase_ready")),
            "routed_orders_total": routed_orders,
            "filled_orders_total": filled_orders,
            "kill_switch_enabled": bool(controls.get("kill_switch_enabled")),
            "stale_orders_total": int(latest_monitor.get("stale_order_count", 0)),
        },
        "journal_state_counts": state_counts,
    }


@router.get("/healthcheck")
def healthcheck_snapshot() -> dict[str, Any]:
    runtime.ensure_optional_services(start_scheduler=True)
    quant_service = _quant_service()
    if quant_service is None:
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "ready": False,
            "components": {"api": {"ok": False, "detail": "Quant service not ready"}},
        }
    return quant_service.build_healthcheck()


@router.get("/alerts")
def alerts_snapshot() -> dict[str, Any]:
    quant_service = _quant_service()
    if quant_service is None:
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "alerts": [],
            "count": 0,
        }
    return quant_service.build_ops_alerts()


@router.get("/models")
def model_registry_snapshot() -> dict[str, Any]:
    quant_service = _quant_service()
    if quant_service is None:
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "models": [],
            "registry_path": None,
            "release_log_path": None,
        }
    return quant_service.build_model_registry()


@router.post("/models/release")
def update_model_release(req: ModelReleaseRequest, request: Request) -> dict[str, Any]:
    quant_service = _quant_service()
    if quant_service is None:
        return {
            "ok": False,
            "detail": "Quant service not ready",
        }
    actor = req.actor.strip() or str(getattr(request.client, "host", "") or "operator")
    return quant_service.update_model_release(
        actor=actor,
        model_key=req.model_key,
        version=req.version,
        action=req.action,
        notes=req.notes,
        canary_percent=req.canary_percent,
    )


@router.get("/audit/search")
def search_audit_events(
    q: str = Query(default=""),
    category: str = Query(default=""),
    action: str = Query(default=""),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    quant_service = _quant_service()
    if quant_service is None:
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "results": [],
            "count": 0,
            "query": q,
            "category": category,
            "action": action,
        }
    return quant_service.search_audit_events(
        query=q,
        category=category,
        action=action,
        limit=limit,
    )
