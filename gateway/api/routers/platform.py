from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from gateway.app_runtime import runtime
from gateway.platform.production_ops import build_release_health, build_schema_health

router = APIRouter(prefix="/api/v1/platform", tags=["platform"])


@router.get("/schema-health")
def schema_health() -> dict[str, Any]:
    return build_schema_health(get_client=runtime.get_client)


@router.get("/release-health")
def release_health() -> dict[str, Any]:
    return build_release_health(
        get_client=runtime.get_client,
        quant_service=runtime.quant_system,
        trading_service=runtime.trading_service,
    )

