from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

from gateway.api.routers import admin, agent, auth, core, ops, quant, quant_rl, reports, scheduler, user
from gateway.app_runtime import RuntimeContext, runtime
from gateway.ops.security import authorize_request
from gateway.utils.logger import get_logger

logger = get_logger(__name__)


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
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await app_runtime.startup(app)
        yield

    app = FastAPI(title="ESG Agentic RAG Copilot", lifespan=lifespan)
    app.state.runtime = app_runtime

    allowed_origins = _parse_cors_origins(os.getenv("CORS_ORIGINS", "*"))
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "X-API-Key"],
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
    app.include_router(agent.router)
    app.include_router(reports.router)
    app.include_router(admin.router)
    app.include_router(user.router)
    app.include_router(scheduler.router)
    app.include_router(quant.router)
    app.include_router(quant_rl.router)
    app.include_router(ops.router)

    frontend_path = Path(__file__).resolve().parents[2] / "frontend"
    if frontend_path.exists():
        app.mount("/app", StaticFiles(directory=frontend_path, html=True), name="frontend")
        logger.info(f"Frontend mounted at /app from {frontend_path}")
    else:
        logger.warning(f"Frontend directory not found at {frontend_path}")

    return app
