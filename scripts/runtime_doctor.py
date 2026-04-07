from __future__ import annotations

import importlib.util
import json
import os
import platform
import sys
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")


def probe_json(url: str, timeout: int = 5) -> tuple[bool, dict | str]:
    try:
        request = Request(url, headers={"User-Agent": "runtime-doctor/1.0"})
        with urlopen(request, timeout=timeout) as response:
            payload = response.read().decode("utf-8", errors="ignore")
            try:
                return True, json.loads(payload)
            except json.JSONDecodeError:
                return True, payload
    except URLError as exc:
        return False, str(exc)
    except Exception as exc:  # pragma: no cover - defensive runtime helper
        return False, str(exc)


def pkg_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def main() -> int:
    remote_llm_url = os.getenv("REMOTE_LLM_URL", "").rstrip("/")
    qdrant_url = os.getenv("QDRANT_URL", "http://127.0.0.1:6333").rstrip("/")
    local_api_url = os.getenv("LOCAL_API_URL", "http://127.0.0.1:8000").rstrip("/")
    report = {
        "python": {
            "executable": sys.executable,
            "version": sys.version.split()[0],
            "platform": platform.platform(),
        },
        "env": {
            "app_mode": os.getenv("APP_MODE", "local"),
            "llm_backend_mode": os.getenv("LLM_BACKEND_MODE", "auto"),
            "remote_llm_configured": bool(remote_llm_url),
        },
        "packages": {
            "torch": pkg_available("torch"),
            "supabase": pkg_available("supabase"),
            "langgraph": pkg_available("langgraph"),
            "schedule": pkg_available("schedule"),
        },
        "health": {},
    }

    ok, payload = probe_json(f"{qdrant_url}/collections")
    report["health"]["qdrant"] = {"ok": ok, "payload": payload}

    if remote_llm_url:
        ok, payload = probe_json(f"{remote_llm_url}/health", timeout=10)
        report["health"]["remote_llm"] = {"ok": ok, "payload": payload}

    ok, payload = probe_json(f"{local_api_url}/health", timeout=10)
    report["health"]["local_api"] = {"ok": ok, "payload": payload}

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
