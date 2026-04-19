from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from gateway.app_runtime import runtime
from gateway.connectors.free_live import FreeLiveConnectorRegistry
from gateway.quant.intelligence import QuantIntelligenceService

router = APIRouter(prefix="/api/v1/connectors", tags=["connectors"])


class ConnectorTestRequest(BaseModel):
    providers: list[str] = Field(default_factory=list)
    provider: str | None = None
    symbol: str = "AAPL"
    dry_run: bool = True
    quota_guard: bool = True


class ConnectorLiveScanRequest(BaseModel):
    universe: list[str] = Field(default_factory=lambda: ["AAPL"])
    query: str = "Free-tier live evidence scan"
    providers: list[str] = Field(default_factory=list)
    decision_time: str | None = None
    quota_guard: bool = True
    persist: bool = True
    limit: int = 20


def _registry() -> FreeLiveConnectorRegistry:
    return FreeLiveConnectorRegistry()


def _provider_list(req_provider: str | None, providers: list[str]) -> list[str] | None:
    rows = [item for item in providers if item]
    if req_provider:
        rows.insert(0, req_provider)
    return rows or None


def _intelligence_service() -> QuantIntelligenceService:
    if runtime.quant_system is None:
        raise HTTPException(status_code=503, detail="Quant system not ready")
    return QuantIntelligenceService(runtime.quant_system)


@router.get("/registry")
def connector_registry() -> dict[str, Any]:
    return _registry().registry()


@router.get("/health")
def connector_health(providers: str | None = None, live: bool = False) -> dict[str, Any]:
    provider_list = [item.strip() for item in str(providers or "").split(",") if item.strip()] or None
    return _registry().health(providers=provider_list, live=live)


@router.get("/quota")
def connector_quota(providers: str | None = None) -> dict[str, Any]:
    provider_list = [item.strip() for item in str(providers or "").split(",") if item.strip()] or None
    return _registry().quota_status(providers=provider_list)


@router.post("/test")
def connector_test(req: ConnectorTestRequest) -> dict[str, Any]:
    return _registry().test(
        providers=_provider_list(req.provider, req.providers),
        symbol=req.symbol,
        dry_run=req.dry_run,
        quota_guard=req.quota_guard,
    )


@router.post("/live-scan")
def connector_live_scan(req: ConnectorLiveScanRequest) -> dict[str, Any]:
    return _intelligence_service().scan(
        universe_symbols=req.universe or None,
        query=req.query,
        decision_time=req.decision_time,
        live_connectors=True,
        mode="mixed",
        providers=req.providers or None,
        quota_guard=req.quota_guard,
        limit=req.limit,
        persist=req.persist,
    )


@router.get("/runs")
def connector_runs(limit: int = 20) -> dict[str, Any]:
    return _registry().runs(limit=limit)
