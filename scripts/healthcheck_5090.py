from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")


def _headers_for_ops() -> dict[str, str]:
    api_key = os.getenv("OPS_API_KEY") or os.getenv("ADMIN_API_KEY") or ""
    if not api_key:
        return {}
    return {"x-api-key": api_key, "Authorization": f"Bearer {api_key}"}


def _probe_json(url: str, *, timeout: int, headers: dict[str, str] | None = None) -> dict[str, object]:
    payload: dict[str, object] = {"url": url, "ok": False, "status_code": None}
    try:
        response = requests.get(url, timeout=timeout, headers=headers or {})
        payload["status_code"] = response.status_code
        payload["ok"] = response.ok
        try:
            payload["response"] = response.json()
        except Exception:
            payload["response"] = response.text[:400]
    except Exception as exc:
        payload["error"] = str(exc)
    return payload


def _component_health(base_url: str, remote_llm_url: str, qdrant_url: str, timeout: int) -> dict[str, dict[str, object]]:
    ops_headers = _headers_for_ops()
    api_health = _probe_json(f"{base_url.rstrip('/')}/livez", timeout=timeout)
    ready_health = _probe_json(f"{base_url.rstrip('/')}/ready", timeout=timeout)
    ops_health = _probe_json(f"{base_url.rstrip('/')}/ops/healthcheck", timeout=timeout, headers=ops_headers)
    paper_preflight = _probe_json(
        f"{base_url.rstrip('/')}/api/v1/quant/deployment/preflight?profile=paper_cloud&dry_run=true",
        timeout=timeout,
        headers=ops_headers,
    )
    paper_observability = _probe_json(
        f"{base_url.rstrip('/')}/api/v1/quant/observability/paper-workflow?window_days=30",
        timeout=timeout,
        headers=ops_headers,
    )
    if isinstance(paper_preflight.get("response"), dict):
        paper_preflight["ok"] = bool(paper_preflight["response"].get("ready"))
    if isinstance(paper_observability.get("response"), dict):
        paper_observability["ok"] = "summary" in paper_observability["response"]
    remote_health = _probe_json(f"{remote_llm_url.rstrip('/')}/health", timeout=timeout)
    qdrant_health = _probe_json(f"{qdrant_url.rstrip('/')}/healthz", timeout=timeout)
    scheduler_meta = {}
    if isinstance(ops_health.get("response"), dict):
        scheduler_meta = (
            ops_health["response"].get("components", {}).get("quant_scheduler", {}).get("meta", {})  # type: ignore[index]
        )
    scheduler_health = {
        "url": "ops://quant_scheduler",
        "ok": bool(scheduler_meta.get("exists")) and not bool(scheduler_meta.get("stale")),
        "response": scheduler_meta,
    }
    model_registry_health = {"ok": False, "response": {}}
    if isinstance(ops_health.get("response"), dict):
        registry_component = ops_health["response"].get("components", {}).get("model_registry", {})  # type: ignore[index]
        model_registry_health = {
            "ok": bool(registry_component.get("ok")),
            "response": registry_component,
        }
    return {
        "api": api_health,
        "ready": ready_health,
        "ops_healthcheck": ops_health,
        "paper_cloud_preflight": paper_preflight,
        "paper_observability": paper_observability,
        "remote_llm": remote_health,
        "qdrant": qdrant_health,
        "quant_scheduler": scheduler_health,
        "model_registry": model_registry_health,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Cloud 5090 healthcheck for the ESG Quant stack.")
    parser.add_argument("--base-url", default=os.getenv("LOCAL_API_URL") or "http://127.0.0.1:8012")
    parser.add_argument("--remote-llm-url", default=os.getenv("REMOTE_LLM_URL") or "http://127.0.0.1:8010")
    parser.add_argument("--qdrant-url", default=os.getenv("QDRANT_URL") or "http://127.0.0.1:6333")
    parser.add_argument("--timeout", type=int, default=5)
    parser.add_argument("--retries", type=int, default=1)
    parser.add_argument("--retry-delay", type=int, default=5)
    parser.add_argument("--json-out", default="")
    args = parser.parse_args()

    snapshot: dict[str, object] = {}
    for attempt in range(max(1, args.retries)):
        components = _component_health(args.base_url, args.remote_llm_url, args.qdrant_url, args.timeout)
        snapshot = {
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "base_url": args.base_url,
            "remote_llm_url": args.remote_llm_url,
            "qdrant_url": args.qdrant_url,
            "components": components,
        }
        required = ["api", "ops_healthcheck", "paper_cloud_preflight", "paper_observability", "remote_llm", "qdrant", "quant_scheduler", "model_registry"]
        snapshot["ready"] = all(bool(components[name].get("ok")) for name in required)
        if snapshot["ready"]:
            break
        if attempt + 1 < max(1, args.retries):
            time.sleep(max(1, args.retry_delay))

    text = json.dumps(snapshot, ensure_ascii=False, indent=2)
    if args.json_out:
        Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json_out).write_text(text, encoding="utf-8")
    print(text)
    return 0 if snapshot.get("ready") else 1


if __name__ == "__main__":
    raise SystemExit(main())
