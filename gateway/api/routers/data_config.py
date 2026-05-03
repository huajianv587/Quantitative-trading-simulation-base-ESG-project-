from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from gateway.app_runtime import runtime
from gateway.platform.production_ops import DataConfigCenterService

router = APIRouter(prefix="/api/v1/data", tags=["data-config"])


def _service() -> DataConfigCenterService:
    return DataConfigCenterService(get_client=runtime.get_client)


@router.get("/config-center")
def config_center() -> dict[str, Any]:
    return _service().get_config_center()


@router.post("/config-center/providers")
def save_provider_config(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return _service().save_provider_config(payload or {})
