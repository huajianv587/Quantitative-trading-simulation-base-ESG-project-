from __future__ import annotations

import importlib.util
import json
import os
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

from gateway.scheduler.data_sources import DataSourceManager
from gateway.db.supabase_client import get_client
from gateway.ops.security import auth_posture
from gateway.quant.alpaca import AlpacaPaperClient
from gateway.quant.alpha_ranker import AlphaRankerRuntime
from gateway.quant.brokers import BrokerRegistry
from gateway.quant.market_data import MarketDataGateway
from gateway.quant.p1_stack import P1ModelSuiteRuntime
from gateway.quant.p2_decision import P2DecisionStackRuntime
from gateway.scheduler.event_classifier_runtime import EventClassifierRuntime
from gateway.quant.storage import QuantStorageGateway
from gateway.utils.llm_client import get_runtime_backend_status


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


def timed_probe_json(url: str, timeout: int = 5) -> dict[str, Any]:
    start = time.perf_counter()
    ok, payload = probe_json(url, timeout=timeout)
    return {
        "ok": ok,
        "elapsed_ms": round((time.perf_counter() - start) * 1000, 2),
        "payload": payload,
    }


def pkg_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def _auth_key_status() -> dict[str, bool]:
    return {
        "execution_api_key_set": bool(os.getenv("EXECUTION_API_KEY", "")),
        "admin_api_key_set": bool(os.getenv("ADMIN_API_KEY", "")),
        "ops_api_key_set": bool(os.getenv("OPS_API_KEY", "")),
    }


def main() -> int:
    started_at = time.perf_counter()
    remote_llm_url = os.getenv("REMOTE_LLM_URL", "").rstrip("/")
    qdrant_url = os.getenv("QDRANT_URL", "http://127.0.0.1:6333").rstrip("/")
    local_api_url = os.getenv("LOCAL_API_URL", "http://127.0.0.1:8012").rstrip("/")
    alpaca = AlpacaPaperClient()
    broker_registry = BrokerRegistry(get_alpaca_client=lambda: alpaca)
    market_data = MarketDataGateway()
    alpha_ranker = AlphaRankerRuntime()
    p1_suite = P1ModelSuiteRuntime()
    p2_stack = P2DecisionStackRuntime()
    event_classifier = EventClassifierRuntime()
    scheduler_heartbeat_path = Path(
        os.getenv("SCHEDULER_HEARTBEAT_PATH", str(PROJECT_ROOT / "storage" / "quant" / "scheduler" / "heartbeat.json"))
    )
    quant_storage_status = QuantStorageGateway(get_client=get_client).status()
    market_data_status = market_data.status()
    alpha_ranker_status = alpha_ranker.status()
    p1_suite_status = p1_suite.status()
    p2_stack_status = p2_stack.status()
    event_classifier_status = event_classifier.status()
    llm_runtime_status = get_runtime_backend_status()

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
            "remote_llm_api_key_set": bool(os.getenv("REMOTE_LLM_API_KEY", "")),
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
            "quant_storage": quant_storage_status,
            "market_data": market_data_status,
            "alpha_ranker": alpha_ranker_status,
            "p1_suite": p1_suite_status,
            "p2_stack": p2_stack_status,
            "event_classifier": event_classifier_status,
            "scheduler_worker": {
                "heartbeat_path": str(scheduler_heartbeat_path),
                "heartbeat_exists": scheduler_heartbeat_path.exists(),
            },
            "alpaca_paper": alpaca.connection_status(),
            "broker_mesh": [item.model_dump() for item in broker_registry.list_brokers()],
            "auth": auth_posture(),
            "llm_runtime": llm_runtime_status,
        },
        "health": {},
        "diagnostics": {
            "fallbacks": {
                "storage_local_fallback": quant_storage_status.get("mode") == "local_fallback",
                "supabase_ready": bool(quant_storage_status.get("supabase_ready")),
                "r2_ready": bool(quant_storage_status.get("r2_ready")),
                "market_data_provider": market_data_status.get("provider") or market_data_status.get("provider_order"),
                "alpha_ranker_available": bool(alpha_ranker_status.get("available")),
                "p1_suite_available": bool(p1_suite_status.get("available")),
                "p2_stack_available": bool(p2_stack_status.get("available")),
                "event_classifier_available": bool(event_classifier_status.get("available")),
            },
            "checks": {},
        },
    }

    report["health"]["qdrant"] = timed_probe_json(f"{qdrant_url}/collections")

    if remote_llm_url:
        report["health"]["remote_llm"] = timed_probe_json(f"{remote_llm_url}/health", timeout=10)

    report["health"]["local_api"] = timed_probe_json(f"{local_api_url}/health", timeout=10)

    if alpaca.configured():
        try:
            report["health"]["alpaca_paper"] = {
                "ok": True,
                "payload": {
                    "account": alpaca.get_account().get("status"),
                    "clock_open": bool(alpaca.get_clock().get("is_open")),
                },
                "elapsed_ms": 0.0,
            }
        except Exception as exc:
            report["health"]["alpaca_paper"] = {"ok": False, "payload": str(exc)}
    else:
        report["health"]["alpaca_paper"] = {
            "ok": False,
            "payload": "missing ALPACA_API_KEY / ALPACA_API_SECRET (or supported APCA aliases)",
        }

    try:
        bars = market_data.get_daily_bars("AAPL", limit=5)
        report["health"]["market_data"] = {
            "ok": True,
            "elapsed_ms": 0.0,
            "payload": {
                "provider": bars.provider,
                "cache_hit": bars.cache_hit,
                "rows": len(bars.bars),
                "latest_timestamp": None if bars.bars.empty else str(bars.bars.iloc[-1]["timestamp"]),
            },
        }
    except Exception as exc:
        report["health"]["market_data"] = {"ok": False, "payload": str(exc)}

    try:
        if scheduler_heartbeat_path.exists():
            heartbeat = json.loads(scheduler_heartbeat_path.read_text(encoding="utf-8"))
            updated_at = datetime.fromisoformat(str(heartbeat.get("updated_at")).replace("Z", "+00:00"))
            fresh = (datetime.now(timezone.utc) - updated_at).total_seconds() < 300
            report["health"]["scheduler_worker"] = {"ok": fresh, "elapsed_ms": 0.0, "payload": heartbeat}
        else:
            report["health"]["scheduler_worker"] = {"ok": False, "elapsed_ms": 0.0, "payload": "scheduler heartbeat file not found"}
    except Exception as exc:
        report["health"]["scheduler_worker"] = {"ok": False, "payload": str(exc)}

    auth_keys = _auth_key_status()
    local_runtime = report["integrations"]["llm_runtime"]
    cloud_fallback_ready = bool(os.getenv("OPENAI_API_KEY", "") or os.getenv("DEEPSEEK_API_KEY", ""))
    local_auto_ready = bool(
        (local_runtime.get("local_checkpoint_exists") and local_runtime.get("local_llm_cuda_available"))
        or cloud_fallback_ready
    )
    hybrid_remote_ready = bool(
        remote_llm_url
        and os.getenv("REMOTE_LLM_API_KEY", "")
        and report["health"].get("remote_llm", {}).get("ok")
    )
    missing_production_prereqs = [
        name for name, configured in auth_keys.items() if not configured
    ]
    if not local_auto_ready:
        missing_production_prereqs.append("llm_local_auto")
    if not hybrid_remote_ready:
        missing_production_prereqs.append("llm_hybrid_remote")

    report["readiness"] = {
        "auth_keys": auth_keys,
        "llm_modes": {
            "local_auto": {
                "ok": local_auto_ready,
                "detail": "local checkpoint with CUDA or cloud fallback keys available",
            },
            "hybrid_remote": {
                "ok": hybrid_remote_ready,
                "detail": remote_llm_url or "REMOTE_LLM_URL not configured",
            },
        },
        "missing_production_prereqs": missing_production_prereqs,
        "status": "production_ready" if not missing_production_prereqs else "quasi_ready",
    }
    report["diagnostics"]["fallbacks"]["qdrant_reachable"] = bool(report["health"].get("qdrant", {}).get("ok"))
    report["diagnostics"]["fallbacks"]["local_api_reachable"] = bool(report["health"].get("local_api", {}).get("ok"))
    report["diagnostics"]["checks"] = {
        name: {
            "ok": payload.get("ok"),
            "elapsed_ms": payload.get("elapsed_ms"),
        }
        for name, payload in report["health"].items()
        if isinstance(payload, dict)
    }
    report["diagnostics"]["total_elapsed_ms"] = round((time.perf_counter() - started_at) * 1000, 2)

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
