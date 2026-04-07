from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException

from gateway.api.schemas import CreatePushRuleRequest, DataSyncRequest, PushRuleTestRequest
from gateway.app_runtime import runtime
from gateway.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.post("/admin/data-sources/sync")
def sync_data_sources(req: DataSyncRequest, background_tasks: BackgroundTasks):
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
    channels = ["email", "in_app"]
    matched = False

    if runtime.report_scheduler and rule_id in runtime.report_scheduler.push_rules_cache:
        rule = runtime.report_scheduler.push_rules_cache[rule_id]
        channels = rule.push_channels
        try:
            matched = bool(eval(rule.condition, {"__builtins__": {}}, req.mock_report))
        except Exception as exc:
            logger.warning(f"Push rule test failed for {rule_id}: {exc}")

    return {
        "test_id": f"test_{datetime.now().timestamp()}",
        "rule_id": rule_id,
        "status": "success",
        "results": {
            "test_user_id": req.test_user_id,
            "matched": matched,
            "channels_tested": channels,
        },
    }
