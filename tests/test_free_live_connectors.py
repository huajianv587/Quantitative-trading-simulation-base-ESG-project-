from __future__ import annotations

import json

from fastapi.testclient import TestClient

import gateway.main as main_module
from gateway.connectors.free_live import FreeLiveConnectorRegistry, MarketauxConnector
from gateway.quant.intelligence import QuantIntelligenceService
from gateway.quant.service import QuantSystemService


def test_free_connector_registry_masks_key_presence_and_reports_quota(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKETAUX_API_KEY", "secret-marketaux-key")
    registry = FreeLiveConnectorRegistry(storage_root=tmp_path)

    payload = registry.registry()
    row = next(item for item in payload["providers"] if item["provider_id"] == "marketaux")

    assert row["configured"] is True
    assert row["env_status"]["MARKETAUX_API_KEY"] is True
    assert "secret-marketaux-key" not in json.dumps(payload, ensure_ascii=False)
    assert row["quota"]["daily_limit"] == 100
    assert row["quota"]["scan_budget"] == 60


def test_connector_normalizes_marketaux_payload_without_leaking_key(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKETAUX_API_KEY", "secret-marketaux-key")

    def fake_fetch(self, symbol):
        return {
            "data": [
                {
                    "title": "Apple supply chain improves",
                    "description": "Positive supplier audit update.",
                    "url": "https://example.test/aapl",
                    "published_at": "2026-04-18T09:00:00Z",
                    "source": "Example",
                    "entities": [{"symbol": symbol, "sentiment_score": 0.42}],
                }
            ]
        }

    monkeypatch.setattr(MarketauxConnector, "_fetch_live", fake_fetch)
    registry = FreeLiveConnectorRegistry(storage_root=tmp_path)

    payload = registry.test(providers=["marketaux"], symbol="AAPL", dry_run=False)

    assert payload["summary"]["normalized_count"] == 1
    item = payload["results"][0]["normalized_items"][0]
    assert item["provider"] == "marketaux"
    assert item["item_type"] == "news"
    assert item["metadata"]["sentiment"] == 0.42
    assert "secret-marketaux-key" not in json.dumps(payload, ensure_ascii=False)


def test_quota_guard_blocks_after_scan_budget(tmp_path, monkeypatch):
    monkeypatch.setenv("ALPHA_VANTAGE_API_KEY", "secret-alpha-key")
    registry = FreeLiveConnectorRegistry(storage_root=tmp_path)
    connector = registry.connectors["alpha_vantage"]
    for _ in range(connector.definition.scan_budget):
        ok, _status = registry.quota.reserve(connector.definition, scan=True)
        assert ok

    result = connector.sample_request("AAPL", dry_run=False, quota_guard=True)

    assert result.status == "quota_protected"
    assert "secret-alpha-key" not in json.dumps(result.payload(), ensure_ascii=False)


def test_intelligence_mixed_scan_uses_free_connector_lineage(tmp_path):
    service = QuantIntelligenceService(QuantSystemService())
    service.storage_root = tmp_path

    payload = service.scan(
        universe_symbols=["AAPL"],
        mode="mixed",
        providers=["local_esg"],
        quota_guard=True,
        persist=False,
    )

    assert payload["items"]
    assert payload["connector_status"]["requested_mode"] == "mixed"
    assert payload["connector_status"]["quota_guard"] is True
    assert payload["connector_status"]["free_tier_registry"]["summary"]["configured"] >= 1


def test_connector_api_contracts_are_available():
    client = TestClient(main_module.app)

    registry = client.get("/api/v1/connectors/registry")
    assert registry.status_code == 200
    assert any(row["provider_id"] == "marketaux" for row in registry.json()["providers"])

    health = client.get("/api/v1/connectors/health")
    assert health.status_code == 200
    assert health.json()["summary"]["failure_isolation"] == "enabled"

    sample = client.post("/api/v1/connectors/test", json={"providers": ["local_esg"], "symbol": "AAPL", "dry_run": True})
    assert sample.status_code == 200
    assert sample.json()["summary"]["failure_isolation"] == "enabled"

    live_scan = client.post(
        "/api/v1/connectors/live-scan",
        json={"universe": ["AAPL"], "providers": ["local_esg"], "quota_guard": True, "persist": False, "limit": 1},
    )
    assert live_scan.status_code == 200
    assert live_scan.json()["connector_status"]["live_connectors_enabled"] is True


def test_quant_api_accepts_live_mode_extensions():
    client = TestClient(main_module.app)

    scan = client.post(
        "/api/v1/quant/intelligence/scan",
        json={"universe": ["AAPL"], "mode": "mixed", "providers": ["local_esg"], "limit": 1, "persist": False},
    )
    assert scan.status_code == 200
    evidence_id = scan.json()["bundle_id"]

    factors = client.post(
        "/api/v1/quant/factors/discover",
        json={"universe": ["AAPL", "MSFT", "NVDA"], "mode": "mixed", "providers": ["local_esg"], "evidence_run_id": evidence_id},
    )
    assert factors.status_code == 200
    assert "connector_lineage" in factors.json()

    decision = client.post(
        "/api/v1/quant/decision/explain",
        json={"symbol": "AAPL", "universe": ["AAPL"], "mode": "mixed", "providers": ["local_esg"]},
    )
    assert decision.status_code == 200
    assert "connector_lineage" in decision.json()
    assert "live_data_age" in decision.json()

    simulation = client.post(
        "/api/v1/quant/simulate/scenario",
        json={"symbol": "AAPL", "universe": ["AAPL"], "evidence_run_id": evidence_id, "paths": 64},
    )
    assert simulation.status_code == 200
    assert simulation.json()["scenario"]["evidence_run_id"] == evidence_id
