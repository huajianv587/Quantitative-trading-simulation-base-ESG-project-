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
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

from gateway.scheduler.data_sources import DataSourceManager
from gateway.db.supabase_client import get_client
from gateway.quant.alpaca import AlpacaPaperClient
from gateway.quant.storage import QuantStorageGateway


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
    alpaca = AlpacaPaperClient()
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
        "integrations": {
            "training_s3_bucket": os.getenv("TRAINING_S3_BUCKET", ""),
            "sagemaker_role_arn": os.getenv("SAGEMAKER_EXECUTION_ROLE_ARN", ""),
            "data_sources": DataSourceManager().source_status(),
            "quant_storage": QuantStorageGateway(get_client=get_client).status(),
            "alpaca_paper": alpaca.connection_status(),
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

    if alpaca.configured():
        try:
            report["health"]["alpaca_paper"] = {
                "ok": True,
                "payload": {
                    "account": alpaca.get_account().get("status"),
                    "clock_open": bool(alpaca.get_clock().get("is_open")),
                },
            }
        except Exception as exc:
            report["health"]["alpaca_paper"] = {"ok": False, "payload": str(exc)}
    else:
        report["health"]["alpaca_paper"] = {
            "ok": False,
            "payload": "missing ALPACA_API_KEY / ALPACA_API_SECRET (or supported APCA aliases)",
        }

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
