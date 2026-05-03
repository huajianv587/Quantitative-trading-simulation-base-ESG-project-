from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from gateway.app_runtime import runtime
from gateway.platform.production_ops import JobQueueService

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


def _service() -> JobQueueService:
    return JobQueueService(get_client=runtime.get_client, quant_service=runtime.quant_system)


@router.post("")
@router.post("/")
def create_job(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return _service().create_job(payload or {})


@router.get("")
@router.get("/")
def list_jobs(limit: int = 50, status: str | None = None) -> dict[str, Any]:
    return _service().list_jobs(limit=limit, status=status)


@router.get("/{job_id}")
def get_job(job_id: str) -> dict[str, Any]:
    return _service().get_job(job_id)


@router.post("/{job_id}/cancel")
def cancel_job(job_id: str) -> dict[str, Any]:
    return _service().cancel_job(job_id)


@router.post("/{job_id}/retry")
def retry_job(job_id: str) -> dict[str, Any]:
    return _service().retry_job(job_id)


@router.get("/{job_id}/logs")
def job_logs(job_id: str) -> dict[str, Any]:
    return _service().job_logs(job_id)
