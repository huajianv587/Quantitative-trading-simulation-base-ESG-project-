from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = PROJECT_ROOT / "storage" / "quant" / "release_health" / "latest.json"


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _request(method: str, base_url: str, path: str, payload: dict[str, Any] | None = None, timeout: float = 10.0) -> dict[str, Any]:
    url = base_url.rstrip("/") + path
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read().decode("utf-8")
        if not raw:
            return {"status_code": response.status, "body": None}
        try:
            body = json.loads(raw)
        except json.JSONDecodeError:
            body = raw
        return {"status_code": response.status, "body": body}


def run_check(base_url: str, timeout: float) -> dict[str, Any]:
    endpoints = [
        ("livez", "GET", "/livez", None),
        ("ui", "GET", "/app/", None),
        ("schema_health", "GET", "/api/v1/platform/schema-health", None),
        ("release_health", "GET", "/api/v1/platform/release-health", None),
        ("trading_safety", "GET", "/api/v1/trading/safety-center", None),
        ("automation_timeline", "GET", "/api/v1/trading/automation/timeline", None),
        ("data_config", "GET", "/api/v1/data/config-center", None),
        ("job_queue_smoke", "POST", "/api/v1/jobs", {"job_type": "release_health_smoke", "payload": {"source": "release_health_check"}}),
    ]
    checks: dict[str, Any] = {}
    hard_failures: list[str] = []
    for name, method, path, payload in endpoints:
        try:
            checks[name] = _request(method, base_url, path, payload=payload, timeout=timeout)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            checks[name] = {"status_code": None, "error": str(exc), "path": path}
            hard_failures.append(name)

    job_body = ((checks.get("job_queue_smoke") or {}).get("body") or {})
    job_id = job_body.get("job_id") if isinstance(job_body, dict) else None
    if job_id:
        try:
            checks["job_queue_logs"] = _request("GET", base_url, f"/api/v1/jobs/{job_id}/logs", timeout=timeout)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            checks["job_queue_logs"] = {"status_code": None, "error": str(exc)}
            hard_failures.append("job_queue_logs")

    statuses = []
    for item in checks.values():
        body = item.get("body") if isinstance(item, dict) else None
        if isinstance(body, dict) and body.get("status"):
            statuses.append(str(body.get("status")))
    overall = "failed" if hard_failures else "blocked" if "blocked" in statuses else "degraded" if "degraded" in statuses else "ready"
    report = {
        "generated_at": _iso_now(),
        "base_url": base_url,
        "status": overall,
        "hard_failures": hard_failures,
        "checks": checks,
        "next_actions": [] if overall in {"ready", "degraded"} else ["Start the API/UI and rerun the release health check."],
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Run release health checks against a local Quant Terminal API.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8012", help="API base URL.")
    parser.add_argument("--timeout", type=float, default=30.0, help="Per-request timeout in seconds.")
    args = parser.parse_args()

    report = run_check(base_url=args.base_url, timeout=args.timeout)
    print(json.dumps({
        "status": report["status"],
        "base_url": report["base_url"],
        "hard_failures": report["hard_failures"],
        "report_path": str(REPORT_PATH),
    }, ensure_ascii=False, indent=2))
    return 1 if report["status"] == "failed" else 0


if __name__ == "__main__":
    sys.exit(main())
