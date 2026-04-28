from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

from gateway.api.routers import admin, agent, auth, connectors, core, ops, quant, quant_rl, reports, scheduler, trading, user
from gateway.app_runtime import RuntimeContext, runtime
from gateway.ops.security import authorize_request
from gateway.utils.logger import get_logger

logger = get_logger(__name__)
APP_ID = "quant-terminal"
APP_SERVICE_NAME = "Quant Terminal"


def _resolve_frontend_mount_dir() -> tuple[Path | None, str]:
    project_root = Path(__file__).resolve().parents[2]
    dist_frontend_path = project_root / "dist" / "app"
    source_frontend_path = project_root / "frontend"

    if dist_frontend_path.exists():
        return dist_frontend_path, "dist"
    if source_frontend_path.exists():
        return source_frontend_path, "source"
    return None, "missing"


def _parse_cors_origins(raw_value: str) -> list[str]:
    if not raw_value or raw_value == "*":
        return ["*"]

    try:
        parsed = json.loads(raw_value)
        if isinstance(parsed, list):
            origins = [str(item).strip() for item in parsed if str(item).strip()]
            if origins:
                return origins
    except Exception:
        pass

    origins = [item.strip().strip("\"'") for item in raw_value.split(",") if item.strip()]
    return origins or ["*"]


def create_app(app_runtime: RuntimeContext = runtime) -> FastAPI:
    auth.validate_auth_runtime_config()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await app_runtime.startup(app)
        try:
            yield
        finally:
            await app_runtime.shutdown(app)

    app = FastAPI(title="ESG Agentic RAG Copilot", lifespan=lifespan)
    app.state.runtime = app_runtime
    app.state.app_id = APP_ID
    app.state.service_name = APP_SERVICE_NAME
    app.state.landing_entry = "/"
    app.state.ui_entry = "/app/"

    allowed_origins = _parse_cors_origins(os.getenv("CORS_ORIGINS", "*"))
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "X-API-Key", "X-Trace-ID", "x-api-key"],
    )

    @app.middleware("http")
    async def disable_app_static_cache(request: Request, call_next):
        auth_failure = authorize_request(request)
        if auth_failure is not None:
            return auth_failure
        response: Response = await call_next(request)
        if request.url.path.startswith("/app"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

    app.include_router(core.router)
    app.include_router(auth.router)
    app.include_router(auth.router, prefix="/api", include_in_schema=False)
    app.include_router(agent.router)
    app.include_router(reports.router)
    app.include_router(admin.router)
    app.include_router(user.router)
    app.include_router(scheduler.router)
    app.include_router(connectors.router)
    app.include_router(quant.router)
    app.include_router(quant_rl.router)
    app.include_router(trading.router)
    app.include_router(ops.router)

    frontend_path, frontend_source = _resolve_frontend_mount_dir()
    app.state.frontend_source = frontend_source
    app.state.frontend_path = str(frontend_path) if frontend_path else None
    if frontend_path is not None:
        app.mount("/app", StaticFiles(directory=frontend_path, html=True), name="frontend")
        logger.info(f"Frontend mounted at /app from {frontend_path} ({frontend_source})")
    else:
        logger.warning("Frontend directory not found in dist/app or frontend source")

    return app
