from pathlib import Path

from fastapi.testclient import TestClient

import gateway.main as main_module
from gateway.config import settings


OPS_HEADERS = {"x-api-key": settings.OPS_API_KEY or settings.ADMIN_API_KEY or settings.EXECUTION_API_KEY or "dev"}


def test_ops_endpoints_return_runtime_snapshots():
    client = TestClient(main_module.app)

    runtime_response = client.get("/ops/runtime", headers=OPS_HEADERS)
    assert runtime_response.status_code == 200
    runtime_payload = runtime_response.json()
    assert "auth" in runtime_payload
    assert "modules" in runtime_payload
    assert "diagnostics" in runtime_payload
    assert "component_status" in runtime_payload["diagnostics"]
    assert "fallbacks" in runtime_payload["diagnostics"]

    health_response = client.get("/ops/healthcheck", headers=OPS_HEADERS)
    assert health_response.status_code == 200
    health_payload = health_response.json()
    assert "components" in health_payload
    assert "diagnostics" in health_payload
    assert "api" in health_payload["components"]
    assert "auth_keys" in health_payload["components"]
    assert "llm_local_auto" in health_payload["components"]
    assert "llm_hybrid_remote" in health_payload["components"]

    alerts_response = client.get("/ops/alerts", headers=OPS_HEADERS)
    assert alerts_response.status_code == 200
    alerts_payload = alerts_response.json()
    assert "alerts" in alerts_payload
    assert "count" in alerts_payload

    online_response = client.get("/api/v1/ops/online-status", headers=OPS_HEADERS)
    assert online_response.status_code == 200
    online_payload = online_response.json()
    assert "scheduler" in online_payload
    assert "heartbeat" in online_payload["scheduler"]
    assert "rlvr" in online_payload
    assert "paper_60d_gate" in online_payload

    models_response = client.get("/ops/models", headers=OPS_HEADERS)
    assert models_response.status_code == 200
    models_payload = models_response.json()
    assert "models" in models_payload
    assert any(item["key"] == "alpha_ranker" for item in models_payload["models"])

    audit_response = client.get("/ops/audit/search?limit=5", headers=OPS_HEADERS)
    assert audit_response.status_code == 200
    audit_payload = audit_response.json()
    assert "results" in audit_payload
    assert "count" in audit_payload


def test_model_release_endpoint_updates_registry_and_audit(monkeypatch, tmp_path: Path):
    registry_path = tmp_path / "current_runtime.json"
    release_log_path = tmp_path / "release_log.jsonl"
    monkeypatch.setattr(settings, "MODEL_REGISTRY_PATH", str(registry_path))
    monkeypatch.setattr(settings, "MODEL_RELEASE_LOG_PATH", str(release_log_path))

    client = TestClient(main_module.app)
    release_response = client.post(
        "/ops/models/release",
        headers=OPS_HEADERS,
        json={
            "actor": "pytest",
            "model_key": "alpha_ranker",
            "version": "pytest-canary-v1",
            "action": "canary",
            "notes": "promote through smoke validation",
            "canary_percent": 0.2,
        },
    )
    assert release_response.status_code == 200
    release_payload = release_response.json()
    assert release_payload["ok"] is True
    assert registry_path.exists()
    assert release_log_path.exists()

    models_response = client.get("/ops/models", headers=OPS_HEADERS)
    assert models_response.status_code == 200
    models_payload = models_response.json()
    alpha_ranker = next(item for item in models_payload["models"] if item["key"] == "alpha_ranker")
    assert alpha_ranker["version"] == "pytest-canary-v1"
    assert alpha_ranker["release_action"] == "canary"
    assert alpha_ranker["release_actor"] == "pytest"

    audit_response = client.get("/ops/audit/search?category=model_release&limit=10", headers=OPS_HEADERS)
    assert audit_response.status_code == 200
    audit_payload = audit_response.json()
    assert audit_payload["count"] >= 1
    assert any(item.get("action") == "canary" for item in audit_payload["results"])
