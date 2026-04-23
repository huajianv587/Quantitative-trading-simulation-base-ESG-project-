from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException

from gateway.api.schemas import CreatePushRuleRequest, DataSyncRequest, PushRuleTestRequest
from gateway.app_runtime import runtime
from gateway.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


def _latest_report_row_for_push_test() -> dict[str, Any] | None:
    if runtime.get_client is not None:
        try:
            response = (
                runtime.get_client()
                .table("esg_reports")
                .select("id, report_type, title, period_start, period_end, data, generated_at")
                .order("generated_at", desc=True)
                .limit(1)
                .execute()
            )
            if response.data:
                return response.data[0]
        except Exception as exc:
            logger.warning(f"Failed to fetch latest report for push-rule test: {exc}")

    memory_rows: list[dict[str, Any]] = []
    for job_id, job in runtime.report_jobs.items():
        payload = job.get("report") or {}
        if not payload:
            continue
        memory_rows.append(
            {
                "id": payload.get("report_id") or payload.get("id") or job_id,
                "report_type": payload.get("report_type"),
                "title": payload.get("title"),
                "period_start": payload.get("period_start"),
                "period_end": payload.get("period_end"),
                "data": payload,
                "generated_at": payload.get("generated_at"),
            }
        )
    if not memory_rows:
        return None
    memory_rows.sort(key=lambda row: row.get("generated_at") or "", reverse=True)
    return memory_rows[0]


def _resolve_report_row_for_push_test(report_id: str | None) -> dict[str, Any] | None:
    if report_id:
        return runtime.fetch_report_row(report_id)
    return _latest_report_row_for_push_test()


def _build_push_rule_context(report_payload: dict[str, Any]) -> dict[str, Any]:
    report_statistics = report_payload.get("report_statistics") or {}
    company_analyses = report_payload.get("company_analyses") or []
    risk_alerts = report_payload.get("risk_alerts") or []
    return {
        "report_type": report_payload.get("report_type"),
        "overall_score": report_statistics.get(
            "portfolio_average_score",
            report_statistics.get("average_score", report_payload.get("overall_score", 0)),
        ),
        "company_count": len(company_analyses),
        "risk_alert_count": len(risk_alerts),
        "high_performer_count": len([item for item in company_analyses if float(item.get("esg_score") or 0) >= 80]),
        "low_performer_count": len([item for item in company_analyses if float(item.get("esg_score") or 0) < 40]),
    }


@router.post("/admin/data-sources/sync")
def sync_data_sources(req: DataSyncRequest, background_tasks: BackgroundTasks):
    runtime.ensure_optional_services()
    if not runtime.data_source_manager:
        raise HTTPException(status_code=503, detail="Data Source Manager not ready")

    try:
        job_id = f"sync_{datetime.now().timestamp()}"
        runtime.sync_jobs[job_id] = {
            "job_id": job_id,
            "status": "started",
            "companies_total": len(req.companies),
            "companies_synced": 0,
            "companies_failed": 0,
            "total_records": 0,
            "updated_at": datetime.now().isoformat(),
        }

        def sync_task():
            synced = 0
            failed = 0
            for company in req.companies:
                try:
                    success = runtime.data_source_manager.sync_company_snapshot(
                        company,
                        force_refresh=req.force_refresh,
                    )
                    if success:
                        synced += 1
                    else:
                        failed += 1
                except Exception as exc:
                    failed += 1
                    logger.warning(f"Sync error for {company}: {exc}")

            runtime.sync_jobs[job_id] = {
                "job_id": job_id,
                "status": "completed" if failed == 0 else "completed_with_errors",
                "companies_total": len(req.companies),
                "companies_synced": synced,
                "companies_failed": failed,
                "total_records": synced,
                "updated_at": datetime.now().isoformat(),
            }

        background_tasks.add_task(sync_task)

        return {
            "job_id": job_id,
            "status": "started",
            "companies_to_sync": len(req.companies),
            "message": "数据同步已启动",
        }
    except Exception as exc:
        logger.error(f"Sync error: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/admin/data-sources/sync/{job_id}")
def get_sync_status(job_id: str):
    job = runtime.sync_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Sync job not found")
    return job


@router.post("/admin/push-rules")
def create_push_rule(req: CreatePushRuleRequest):
    runtime.ensure_optional_services(start_scheduler=True)
    if not runtime.report_scheduler or runtime.PushRule is None:
        raise HTTPException(status_code=503, detail="Report Scheduler not ready")

    try:
        rule = runtime.PushRule(
            rule_name=req.rule_name,
            condition=req.condition,
            target_users=req.target_users,
            push_channels=req.push_channels,
            priority=req.priority,
            template_id=req.template_id,
        )

        rule_id = runtime.report_scheduler.create_push_rule(rule)
        return {
            "rule_id": rule_id,
            "rule_name": req.rule_name,
            "status": "created",
        }
    except Exception as exc:
        logger.error(f"Create rule error: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/admin/push-rules")
def get_push_rules():
    runtime.ensure_optional_services(start_scheduler=True)
    if not runtime.report_scheduler:
        return {
            "total": 0,
            "rules": [],
            "degraded": True,
            "message": "Report Scheduler not ready",
        }

    try:
        rules = list(runtime.report_scheduler.push_rules_cache.values())
        return {
            "total": len(rules),
            "rules": [runtime.serialize_model(rule) for rule in rules],
        }
    except Exception as exc:
        logger.error(f"Get rules error: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.put("/admin/push-rules/{rule_id}")
def update_push_rule(rule_id: str, updates: dict[str, Any]):
    runtime.ensure_optional_services(start_scheduler=True)
    if not runtime.report_scheduler:
        raise HTTPException(status_code=503, detail="Report Scheduler not ready")

    try:
        runtime.report_scheduler.update_push_rule(rule_id, updates)
        return {
            "rule_id": rule_id,
            "status": "updated",
        }
    except Exception as exc:
        logger.error(f"Update rule error: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete("/admin/push-rules/{rule_id}")
def delete_push_rule(rule_id: str):
    runtime.ensure_optional_services(start_scheduler=True)
    if not runtime.report_scheduler:
        raise HTTPException(status_code=503, detail="Report Scheduler not ready")

    try:
        runtime.report_scheduler.delete_push_rule(rule_id)
        return {
            "rule_id": rule_id,
            "status": "deleted",
        }
    except Exception as exc:
        logger.error(f"Delete rule error: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/admin/push-rules/{rule_id}/test")
def test_push_rule(rule_id: str, req: PushRuleTestRequest):
    runtime.ensure_optional_services(start_scheduler=True)
    if not runtime.report_scheduler:
        raise HTTPException(status_code=503, detail="Report Scheduler not ready")

    rule = runtime.report_scheduler.push_rules_cache.get(rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Push rule not found")

    report_row = _resolve_report_row_for_push_test(req.report_id)
    channels = list(rule.push_channels or ["email", "in_app"])
    base_payload = {
        "test_id": f"test_{datetime.now().timestamp()}",
        "rule_id": rule_id,
        "results": {
            "test_user_id": req.test_user_id,
            "matched": False,
            "channels_tested": channels,
        },
    }

    if report_row is None:
        return {
            **base_payload,
            "status": "blocked",
            "report_id": None,
            "report_type": None,
            "generated_at": None,
            "block_reason": "real_report_required",
            "next_actions": ["Generate a real report", "Refresh reports", "Retry push-rule test"],
        }

    report_payload = runtime.flatten_report_row(report_row)
    try:
        matched = bool(eval(rule.condition, {"__builtins__": {}}, _build_push_rule_context(report_payload)))
    except Exception as exc:
        logger.warning(f"Push rule test failed for {rule_id}: {exc}")
        return {
            **base_payload,
            "status": "error",
            "report_id": report_payload.get("report_id"),
            "report_type": report_payload.get("report_type"),
            "generated_at": report_payload.get("generated_at"),
            "block_reason": "rule_evaluation_failed",
            "next_actions": ["Review rule condition", "Retry with a valid report"],
            "warning": str(exc),
        }

    return {
        **base_payload,
        "status": "success",
        "report_id": report_payload.get("report_id"),
        "report_type": report_payload.get("report_type"),
        "generated_at": report_payload.get("generated_at"),
        "results": {
            "test_user_id": req.test_user_id,
            "matched": matched,
            "channels_tested": channels,
        },
    }
