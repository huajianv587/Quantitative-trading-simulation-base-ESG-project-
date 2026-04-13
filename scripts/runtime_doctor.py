from __future__ import annotations

import importlib.util
import json
import os
import platform
import sys
from datetime import datetime, timezone
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
from gateway.ops.security import auth_posture
from gateway.quant.alpaca import AlpacaPaperClient
from gateway.quant.alpha_ranker import AlphaRankerRuntime
from gateway.quant.brokers import BrokerRegistry
from gateway.quant.market_data import MarketDataGateway
from gateway.quant.p1_stack import P1ModelSuiteRuntime
from gateway.quant.p2_decision import P2DecisionStackRuntime
from gateway.scheduler.event_classifier_runtime import EventClassifierRuntime
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
    broker_registry = BrokerRegistry(get_alpaca_client=lambda: alpaca)
    market_data = MarketDataGateway()
    alpha_ranker = AlphaRankerRuntime()
    p1_suite = P1ModelSuiteRuntime()
    p2_stack = P2DecisionStackRuntime()
    event_classifier = EventClassifierRuntime()
    scheduler_heartbeat_path = Path(
        os.getenv("SCHEDULER_HEARTBEAT_PATH", str(PROJECT_ROOT / "storage" / "quant" / "scheduler" / "heartbeat.json"))
    )
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
            "market_data": market_data.status(),
            "alpha_ranker": alpha_ranker.status(),
            "p1_suite": p1_suite.status(),
            "p2_stack": p2_stack.status(),
            "event_classifier": event_classifier.status(),
            "scheduler_worker": {
                "heartbeat_path": str(scheduler_heartbeat_path),
                "heartbeat_exists": scheduler_heartbeat_path.exists(),
            },
            "alpaca_paper": alpaca.connection_status(),
            "broker_mesh": [item.model_dump() for item in broker_registry.list_brokers()],
            "auth": auth_posture(),
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

    try:
        bars = market_data.get_daily_bars("AAPL", limit=5)
        report["health"]["market_data"] = {
            "ok": True,
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
            report["health"]["scheduler_worker"] = {"ok": fresh, "payload": heartbeat}
        else:
            report["health"]["scheduler_worker"] = {"ok": False, "payload": "scheduler heartbeat file not found"}
    except Exception as exc:
        report["health"]["scheduler_worker"] = {"ok": False, "payload": str(exc)}

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
