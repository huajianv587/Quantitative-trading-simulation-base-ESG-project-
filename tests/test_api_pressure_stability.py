from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

import gateway.main as main_module
from gateway.api.routers import platform as platform_router
import gateway.platform.production_ops as production_ops
from gateway.quant.storage import QuantStorageGateway


ALLOWED_STATUSES = {
    "ready",
    "degraded",
    "blocked",
    "queued",
    "running",
    "succeeded",
    "failed",
    "cancelled",
    "completed",
    "ok",
    "pass",
}

RUNTIME_MOJIBAKE_FRAGMENTS = [
    "鎿",
    "璇",
    "妫",
    "鍦",
    "濡",
    "鍚",
    "绔",
    "帴",
    "佹",
    "撅",
    "缁",
    "鈥",
    "锟",
]


def _client() -> TestClient:
    return TestClient(main_module.app)


def _json(response) -> dict[str, Any]:
    try:
        payload = response.json()
    except Exception:
        payload = {}
    return payload if isinstance(payload, dict) else {"payload": payload}


def _assert_clean_runtime_copy(payload: dict[str, Any]) -> None:
    rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    for fragment in RUNTIME_MOJIBAKE_FRAGMENTS:
        assert fragment not in rendered


def test_ui_action_evidence_returns_clean_chinese_feedback(tmp_path, monkeypatch):
    evidence_path = tmp_path / "ui_action_evidence" / "events.jsonl"
    monkeypatch.setattr(platform_router, "_ui_action_path", lambda: evidence_path)

    client = _client()
    response = client.post(
        "/api/v1/platform/ui-action/evidence",
        json={
            "event_type": "click",
            "route": "/dashboard",
            "target": {"tag": "button", "label": "刷新", "contract": "ui_only"},
            "outcome": {"dom_changed": True, "business_request_count": 0},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["display"]["title"] == "操作已连接"
    assert "证据链" in payload["display"]["message"]
    _assert_clean_runtime_copy(payload)

    latest = client.get("/api/v1/platform/ui-action/evidence/latest?limit=5")
    latest_payload = latest.json()
    assert latest.status_code == 200
    assert latest_payload["status"] == "ready"
    assert latest_payload["count"] == 1
    _assert_clean_runtime_copy(latest_payload)


def test_core_runtime_apis_survive_parallel_pressure(tmp_path, monkeypatch):
    evidence_path = tmp_path / "ui_action_evidence" / "events.jsonl"
    monkeypatch.setattr(platform_router, "_ui_action_path", lambda: evidence_path)

    class TempQuantStorageGateway(QuantStorageGateway):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.base_dir = tmp_path / "quant"

        def _mirror_to_supabase(self, *args, **kwargs):
            return False

    monkeypatch.setattr(production_ops, "QuantStorageGateway", TempQuantStorageGateway)
    monkeypatch.setattr(production_ops, "_remote_enabled", lambda name: False)

    calls: list[tuple[str, str, dict[str, Any] | None]] = []
    for index in range(8):
        calls.extend(
            [
                ("get", "/livez", None),
                ("get", "/api/v1/platform/schema-health", None),
                ("get", "/api/v1/platform/release-health", None),
                ("get", "/api/v1/quant/capabilities", None),
                ("get", "/api/v1/trading/safety-center", None),
                ("get", "/api/v1/trading/automation/timeline", None),
                ("get", "/api/v1/jobs?limit=5", None),
                (
                    "post",
                    "/api/v1/platform/ui-action/evidence",
                    {
                        "event_type": "click",
                        "route": f"/pressure/{index}",
                        "target": {"tag": "button", "label": f"pressure-{index}", "contract": "ui_only"},
                        "outcome": {"dom_changed": True, "business_request_count": 0},
                    },
                ),
                (
                    "post",
                    "/api/v1/jobs",
                    {
                        "job_id": f"pressure-noop-{index}",
                        "job_type": "release_health_smoke",
                        "run_immediately": True,
                    },
                ),
            ]
        )

    def request(call: tuple[str, str, dict[str, Any] | None]) -> dict[str, Any]:
        method, path, body = call
        client = _client()
        response = client.get(path) if method == "get" else client.post(path, json=body)
        return {
            "method": method,
            "path": path,
            "status_code": response.status_code,
            "payload": _json(response),
        }

    with ThreadPoolExecutor(max_workers=12) as pool:
        results = [future.result() for future in as_completed(pool.submit(request, call) for call in calls)]

    failures = [item for item in results if item["status_code"] >= 500]
    assert failures == []

    bad_statuses: list[dict[str, Any]] = []
    for item in results:
        payload = item["payload"]
        _assert_clean_runtime_copy(payload)
        status = str(payload.get("status") or payload.get("overall_status") or "").lower()
        if status and status not in ALLOWED_STATUSES:
            bad_statuses.append({"path": item["path"], "status": status, "payload": payload})
        if status in {"degraded", "blocked", "failed"}:
            assert payload.get("reason") or payload.get("next_actions") or payload.get("missing_config") is not None

    assert bad_statuses == []

    job_payloads = [item["payload"] for item in results if item["path"] == "/api/v1/jobs"]
    assert len(job_payloads) == 8
    assert {payload["status"] for payload in job_payloads} == {"succeeded"}

    latest = _client().get("/api/v1/platform/ui-action/evidence/latest?limit=20")
    assert latest.status_code == 200
    assert latest.json()["count"] == 8

    for path in (tmp_path / "quant").rglob("*.tmp"):
        raise AssertionError(f"temporary file leaked after pressure run: {path}")
