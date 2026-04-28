from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Query, Request

from gateway.app_runtime import runtime
from gateway.api.quant_schemas import ModelReleaseRequest
from gateway.config import settings
from gateway.ops.security import auth_coverage_for_app, auth_posture

router = APIRouter(prefix="/ops", tags=["ops"])


def _quant_service():
    return runtime.quant_system


@router.get("/runtime")
def runtime_snapshot(request: Request) -> dict[str, Any]:
    quant_service = _quant_service()
    brokers = quant_service.list_execution_brokers() if quant_service is not None else []
    auth = auth_posture()
    auth["coverage"] = auth_coverage_for_app(request.app)
    storage_status = quant_service.storage.status() if quant_service is not None else {}
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "app_mode": getattr(runtime, "app_mode", None) or settings.APP_MODE,
        "auth": auth,
        "startup": {
            "lazy_components": dict(getattr(runtime, "lazy_components", {}) or {}),
        },
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
        "request_path": request.url.path,
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
