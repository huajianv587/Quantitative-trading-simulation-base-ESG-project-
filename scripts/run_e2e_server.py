from __future__ import annotations

import os
import sys
import asyncio
from pathlib import Path

import uvicorn

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _set_default_env() -> None:
    os.environ.setdefault("APP_MODE", "local")
    os.environ.setdefault("LLM_BACKEND_MODE", "auto")
    os.environ.setdefault("AUTH_DEFAULT_REQUIRED", "false")
    os.environ.setdefault("CORS_ORIGINS", "*")


def _configure_windows_event_loop() -> None:
    if sys.platform != "win32":
        return
    policy = getattr(asyncio, "WindowsSelectorEventLoopPolicy", None)
    if policy is not None:
        asyncio.set_event_loop_policy(policy())


def _quiet_windows_socket_reset(loop: asyncio.AbstractEventLoop, context: dict) -> None:
    exception = context.get("exception")
    handle = str(context.get("handle") or "")
    if (
        sys.platform == "win32"
        and isinstance(exception, ConnectionResetError)
        and "_ProactorBasePipeTransport._call_connection_lost" in handle
    ):
        return
    loop.default_exception_handler(context)


async def _serve(port: int) -> None:
    loop = asyncio.get_running_loop()
    loop.set_exception_handler(_quiet_windows_socket_reset)
    config = uvicorn.Config("gateway.main:app", host="127.0.0.1", port=port, reload=False)
    server = uvicorn.Server(config)
    await server.serve()


def main() -> None:
    _configure_windows_event_loop()
    _set_default_env()
    port = int(os.environ.get("E2E_PORT", "39123"))
    asyncio.run(_serve(port))


if __name__ == "__main__":
    main()
