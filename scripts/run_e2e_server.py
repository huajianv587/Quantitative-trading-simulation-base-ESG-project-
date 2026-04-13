from __future__ import annotations

import os
import sys
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


def main() -> None:
    _set_default_env()
    port = int(os.environ.get("E2E_PORT", "39123"))
    uvicorn.run("gateway.main:app", host="127.0.0.1", port=port, reload=False)


if __name__ == "__main__":
    main()
