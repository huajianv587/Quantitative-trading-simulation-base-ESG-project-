from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, HTTPException

from gateway.app_runtime import runtime
from gateway.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.post("/scheduler/scan")
def trigger_scan(background_tasks: BackgroundTasks):
    if not runtime.get_orchestrator:
        raise HTTPException(status_code=503, detail="Scheduler module not available")

    orchestrator = runtime.get_orchestrator()

    def _run_pipeline():
        try:
            orchestrator.run_full_pipeline()
        except Exception as exc:
            logger.error(f"[Scheduler] Pipeline failed: {exc}", exc_info=True)

    background_tasks.add_task(_run_pipeline)

    return {
        "status": "scanning",
        "message": "ESG scan pipeline started",
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/scheduler/scan/status")
def get_scan_status():
    if not runtime.get_orchestrator:
        raise HTTPException(status_code=503, detail="Scheduler module not available")

    orchestrator = runtime.get_orchestrator()
    status = orchestrator.get_scan_status()

    if status:
        return {"status": "completed", "data": status}
    return {"status": "no_scan_found"}


@router.get("/scheduler/statistics")
def get_scheduler_statistics(days: int = 7):
    return runtime.get_scheduler_statistics(days)
