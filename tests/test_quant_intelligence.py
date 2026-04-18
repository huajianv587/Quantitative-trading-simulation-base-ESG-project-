from __future__ import annotations

import json

from fastapi.testclient import TestClient

import gateway.main as main_module
from gateway.quant.intelligence import QuantIntelligenceService
from gateway.quant.intelligence_models import EvidenceBundle, SimulationScenario
from gateway.quant.service import QuantSystemService


def _service(tmp_path):
    service = QuantIntelligenceService(QuantSystemService())
    service.storage_root = tmp_path
    return service


def test_evidence_scan_returns_source_linked_as_of_items(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPER_SECRET_TEST_TOKEN", "do-not-leak")
    service = _service(tmp_path)

    payload = service.scan(universe_symbols=["AAPL", "MSFT"], query="shadow scan", persist=False)

    assert payload["bundle_id"].startswith("evidence-")
    assert payload["quality_summary"]["item_count"] > 0
    first = payload["items"][0]
    for key in [
        "provider",
        "source",
        "observed_at",
        "symbol",
        "checksum",
        "content_hash",
        "confidence",
        "quality_score",
        "dedup_id",
        "leakage_guard",
    ]:
        assert key in first
    assert "do-not-leak" not in json.dumps(payload, ensure_ascii=False)


def test_live_connector_failure_isolated_from_local_evidence(tmp_path):
    class FailingManager:
        def source_status(self):
            return {"newsapi": True}

        def fetch_company_data(self, *_args, **_kwargs):
            raise RuntimeError("provider down")

    service = QuantIntelligenceService(QuantSystemService(), data_source_manager=FailingManager())
    service.storage_root = tmp_path

    payload = service.scan(universe_symbols=["AAPL"], live_connectors=True, persist=False)

    assert payload["items"]
    assert payload["connector_status"]["failure_isolation"] == "enabled"
    assert payload["connector_status"]["connector_failures"]


def test_as_of_feature_store_excludes_future_observed_items(tmp_path):
    service = _service(tmp_path)
    safe = service._make_item(
        item_type="news",
        provider="unit",
        source="unit",
        symbol="AAPL",
        company_name="Apple",
        title="AAPL positive update",
        summary="positive evidence",
        published_at="2025-01-01T00:00:00+00:00",
        observed_at="2025-01-02T00:00:00+00:00",
        confidence=0.8,
    )
    future = service._make_item(
        item_type="news",
        provider="unit",
        source="unit",
        symbol="AAPL",
        company_name="Apple",
        title="AAPL future update",
        summary="future evidence",
        published_at="2025-02-01T00:00:00+00:00",
        observed_at="2025-02-02T00:00:00+00:00",
        confidence=0.8,
    )
    bundle = EvidenceBundle(
        bundle_id="evidence-unit",
        generated_at="2025-01-02T00:00:00+00:00",
        decision_time="2025-01-15T00:00:00+00:00",
        universe=["AAPL"],
        items=[safe, future],
    )

    events = service.extract_events(bundle)
    features = service.build_as_of_features(bundle, events, decision_time=bundle.decision_time)

    assert features["AAPL"]["evidence_count"] == 1.0
    assert features["AAPL"]["event_count"] == 1.0


def test_factor_lab_decision_and_simulation_contracts(tmp_path):
    service = _service(tmp_path)

    factors = service.discover_factors(universe_symbols=["AAPL", "MSFT", "NVDA"], persist=False)
    assert len(factors["factor_cards"]) >= 3
    assert all("gate_results" in card for card in factors["factor_cards"])

    decision = service.explain_decision(
        symbol="AAPL",
        universe_symbols=["AAPL", "MSFT", "NVDA"],
        include_simulation=True,
        persist=False,
    )
    assert decision["decision_id"].startswith("decision-AAPL")
    assert decision["main_evidence"]
    assert decision["verifier_checks"]["execution_guard"] == "shadow_only_no_order_created"
    assert decision["simulation"]["simulation_id"].startswith("sim-AAPL")

    first = service.simulate_scenario(
        SimulationScenario(symbol="AAPL", universe=["AAPL"], seed=7, paths=64),
        persist=False,
    )
    second = service.simulate_scenario(
        SimulationScenario(symbol="AAPL", universe=["AAPL"], seed=7, paths=64),
        persist=False,
    )
    assert first["path_summary"] == second["path_summary"]


def test_quant_intelligence_api_endpoints_are_available():
    client = TestClient(main_module.app)

    scan = client.post("/api/v1/quant/intelligence/scan", json={"universe": ["AAPL"], "limit": 1})
    assert scan.status_code == 200
    assert scan.json()["items"]

    factors = client.post("/api/v1/quant/factors/discover", json={"universe": ["AAPL", "MSFT", "NVDA"]})
    assert factors.status_code == 200
    assert factors.json()["factor_cards"]

    decision = client.post("/api/v1/quant/decision/explain", json={"symbol": "AAPL", "universe": ["AAPL"]})
    assert decision.status_code == 200
    assert decision.json()["verifier_checks"]["execution_guard"] == "shadow_only_no_order_created"

    simulation = client.post("/api/v1/quant/simulate/scenario", json={"symbol": "AAPL", "paths": 64, "seed": 11})
    assert simulation.status_code == 200
    assert "probability_of_loss" in simulation.json()
