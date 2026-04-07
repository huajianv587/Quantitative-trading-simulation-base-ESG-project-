from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from gateway.api.schemas import UserReportSubscribeRequest
from gateway.app_runtime import runtime
from gateway.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.post("/user/reports/subscribe")
def subscribe_reports(req: UserReportSubscribeRequest, user_id: str = "user_123"):
    if not runtime.report_scheduler or runtime.ReportSubscription is None:
        raise HTTPException(status_code=503, detail="Report Scheduler not ready")

    try:
        subscription = runtime.ReportSubscription(
            user_id=user_id,
            report_types=req.report_types,
            companies=req.companies,
            alert_threshold=req.alert_threshold or {},
            push_channels=req.push_channels,
            frequency=req.frequency,
        )

        subscription_id = runtime.report_scheduler.user_subscribe_reports(subscription)
        return {
            "subscription_id": subscription_id or f"sub_{user_id}",
            "user_id": user_id,
            "status": "subscribed",
            "subscribed_to": {
                "report_types": req.report_types,
                "companies": req.companies,
                "channels": req.push_channels,
            },
        }
    except Exception as exc:
        logger.error(f"Subscribe error: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/user/reports/subscriptions")
def get_user_subscriptions(user_id: str = "user_123"):
    if runtime.get_client is None:
        return {
            "user_id": user_id,
            "subscriptions": [],
            "degraded": True,
            "message": "Database module not available",
        }

    try:
        rows = (
            runtime.get_client()
            .table("user_report_subscriptions")
            .select("*")
            .eq("user_id", user_id)
            .order("subscribed_at", desc=True)
            .execute()
            .data
        )

        subscriptions = [
            {
                "subscription_id": row.get("id"),
                "user_id": row.get("user_id"),
                "report_types": row.get("report_types", []),
                "companies": row.get("companies", []),
                "alert_threshold": row.get("alert_threshold", {}),
                "push_channels": row.get("push_channels", []),
                "frequency": row.get("frequency"),
                "subscribed_at": row.get("subscribed_at"),
                "updated_at": row.get("updated_at"),
            }
            for row in rows
        ]

        return {
            "user_id": user_id,
            "subscriptions": subscriptions,
        }
    except Exception as exc:
        logger.error(f"Get subscriptions error: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.put("/user/reports/subscriptions/{subscription_id}")
def update_subscription(subscription_id: str, updates: dict[str, Any]):
    if runtime.get_client is None:
        raise HTTPException(status_code=503, detail="Database module not available")

    try:
        runtime.get_client().table("user_report_subscriptions").update(updates).eq("id", subscription_id).execute()
        return {
            "subscription_id": subscription_id,
            "status": "updated",
        }
    except Exception as exc:
        logger.error(f"Update subscription error: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete("/user/reports/subscriptions/{subscription_id}")
def unsubscribe(subscription_id: str):
    if runtime.get_client is None:
        raise HTTPException(status_code=503, detail="Database module not available")

    try:
        runtime.get_client().table("user_report_subscriptions").delete().eq("id", subscription_id).execute()
        return {
            "subscription_id": subscription_id,
            "status": "deleted",
        }
    except Exception as exc:
        logger.error(f"Delete subscription error: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
