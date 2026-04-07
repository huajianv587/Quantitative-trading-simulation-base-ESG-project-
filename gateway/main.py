from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from gateway.api.factory import create_app
from gateway.app_runtime import runtime

app = create_app(runtime)


def __getattr__(name: str):
    if hasattr(runtime, name):
        return getattr(runtime, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("gateway.main:app", host="0.0.0.0", port=8000, reload=False)
