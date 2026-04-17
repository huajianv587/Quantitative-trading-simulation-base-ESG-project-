from __future__ import annotations

from fastapi import FastAPI

from api.routes_quant_rl import router


def register_quant_rl(app: FastAPI) -> None:
    app.include_router(router)
