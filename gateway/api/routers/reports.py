from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from fastapi.responses import Response

from gateway.api.schemas import ReportGenerateRequest
from gateway.app_runtime import runtime
from gateway.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.post("/admin/reports/generate")
def generate_report(req: ReportGenerateRequest, background_tasks: BackgroundTasks):
    if not runtime.report_generator:
        raise HTTPException(status_code=503, detail="Report Generator not ready")

    try:
        logger.info(f"[Reports] Generating {req.report_type} report")
        if req.report_type not in {"daily", "weekly", "monthly"}:
            raise HTTPException(status_code=400, detail="Invalid report type")

        if req.async_:
            report_id = f"report_{datetime.now().timestamp()}"
            runtime.report_jobs[report_id] = {
                "status": "generating",
                "report_type": req.report_type,
                "companies_count": len(req.companies),
                "generated_at": None,
            }

            def generate_sync():
                try:
                    report = runtime.generate_report_by_type(req.report_type, req.companies)
                    persisted_id = (
                        runtime.report_scheduler._save_report(report)
                        if runtime.report_scheduler else report_id
                    )
                    runtime.store_report_job(report_id, report, persisted_id=persisted_id)
                    logger.info(f"[Reports] Report {report_id} generated successfully")
                except Exception as exc:
                    runtime.report_jobs[report_id] = {
                        "status": "failed",
                        "report_type": req.report_type,
                        "companies_count": len(req.companies),
                        "error": str(exc),
                        "generated_at": None,
                    }
                    logger.error(f"[Reports] Error generating report: {exc}", exc_info=True)

            background_tasks.add_task(generate_sync)

            return {
                "report_id": report_id,
                "status": "generating",
                "report_type": req.report_type,
                "companies_count": len(req.companies),
                "message": "报告生成中...",
            }

        report = runtime.generate_report_by_type(req.report_type, req.companies)
        report_id = (
            runtime.report_scheduler._save_report(report)
            if runtime.report_scheduler else f"report_{datetime.now().timestamp()}"
        )
        payload = runtime.store_report_job(report_id, report, persisted_id=report_id)

        return {
            "report_id": report_id,
            "status": "completed",
            "report_type": req.report_type,
            "report": payload,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Report generation error: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/admin/reports/statistics")
def get_report_statistics(
    period: str = Query(...),
    group_by: str = Query("report_type"),
):
    try:
        start_date, end_date = period.split(":")
        if runtime.get_client is None:
            raise RuntimeError("Database module not available")

        db = runtime.get_client()
        reports = (
            db.table("esg_reports")
            .select("id, report_type, generated_at")
            .gte("generated_at", start_date)
            .lte("generated_at", end_date)
            .execute()
            .data
        )

        by_type = {"daily": 0, "weekly": 0, "monthly": 0}
        for report in reports:
            report_name = report.get("report_type")
            if report_name in by_type:
                by_type[report_name] += 1

        push_statistics = {
            "total_notifications": 0,
            "delivered": 0,
            "read": 0,
            "click_through_rate": 0,
        }

        try:
            push_rows = (
                db.table("report_push_history")
                .select("push_status, read_at, click_through")
                .gte("created_at", start_date)
                .lte("created_at", end_date)
                .execute()
                .data
            )
            total_pushes = len(push_rows)
            delivered = sum(1 for row in push_rows if row.get("push_status") == "sent")
            read = sum(1 for row in push_rows if row.get("read_at"))
            clicked = sum(1 for row in push_rows if row.get("click_through"))
            push_statistics = {
                "total_notifications": total_pushes,
                "delivered": delivered,
                "read": read,
                "click_through_rate": round((clicked / total_pushes) * 100, 2) if total_pushes else 0,
            }
        except Exception as push_exc:
            logger.warning(f"Push statistics unavailable: {push_exc}")

        return {
            "period": {"start": start_date, "end": end_date},
            "group_by": group_by,
            "total_reports": len(reports),
            "by_type": by_type,
            "push_statistics": push_statistics,
        }
    except Exception as exc:
        logger.error(f"Statistics error: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/admin/reports/{report_id}")
def get_report(report_id: str, report_type: Optional[str] = None):
    try:
        if report_id == "latest":
            row = runtime.fetch_latest_report_row(report_type or "", None)
            if row is None:
                return Response(status_code=204)

            payload = runtime.flatten_report_row(row)
            payload["status"] = "completed"
            return payload

        job = runtime.report_jobs.get(report_id)
        if job:
            if job.get("status") != "completed":
                return {
                    "report_id": report_id,
                    "status": job.get("status"),
                    "report_type": job.get("report_type"),
                    "error": job.get("error"),
                }

            payload = dict(job.get("report") or {})
            payload["status"] = "completed"
            payload["report_id"] = payload.get("report_id") or report_id
            return payload

        row = runtime.fetch_report_row(report_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Report not found")

        payload = runtime.flatten_report_row(row)
        payload["status"] = "completed"
        return payload
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Get report error: {exc}")
        raise HTTPException(status_code=404, detail="Report not found")


@router.get("/admin/reports/latest")
def get_latest_report(report_type: str = Query(...), company: Optional[str] = None):
    try:
        logger.info(f"[Reports] Latest report requested for type={report_type}, company={company}")
        row = runtime.fetch_latest_report_row(report_type, company)
        if row is None:
            return Response(status_code=204)

        payload = runtime.flatten_report_row(row)
        payload["status"] = "completed"
        return payload
    except Exception as exc:
        logger.error(f"Error: {exc}")
        return Response(status_code=204)


@router.get("/admin/reports/export/{report_id}")
def export_report(report_id: str, format: str = Query("pdf")):
    if format not in ["pdf", "xlsx", "json"]:
        raise HTTPException(status_code=400, detail="Invalid format")

    return {
        "report_id": report_id,
        "format": format,
        "message": "Report export",
        "download_url": f"/api/files/report_{report_id}.{format}",
    }
