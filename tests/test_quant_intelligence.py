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
    assert all("data_tier" in card for card in factors["factor_cards"])
    assert all("registry_gate_status" in card for card in factors["factor_cards"])
    assert factors["dataset_manifest"]["dataset_id"].startswith("dataset-")
    assert "market_depth_status" in factors["dataset_manifest"]
    assert "protection_report" in factors

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
    assert first["intraday_replay"]["frequencies"] == ["1m", "5m", "15m"]
    assert first["microstructure"]["metrics"]["avg_spread_bps"] > 0
    assert "order_book_replay" in first
    assert "dataset_manifest" in first
    assert "protection_report" in first
    assert first["execution_quality_sandbox"]["registry_gate_status"] in {"review", "blocked"}


def test_dataset_manifest_and_protection_report_are_persistable(tmp_path):
    service = _service(tmp_path)

    dataset = service.build_dataset_manifest(universe_symbols=["AAPL", "MSFT"], include_intraday=True, persist=True)
    assert dataset["dataset_id"].startswith("dataset-")
    assert dataset["storage"]["record_type"] == "quant/research_datasets"

    protection = service.run_research_quality_checks(
        universe_symbols=["AAPL", "MSFT"],
        formulas=["shift(-1)", "rolling_mean(close, 20)"],
        timestamps=["2099-01-01T00:00:00+00:00"],
        current_constituents_only=True,
        persist=True,
    )
    assert protection["protection_status"] == "blocked"
    assert protection["storage"]["record_type"] == "quant/research_quality"


def test_market_depth_replay_and_l2_gate_are_exposed(tmp_path):
    service = _service(tmp_path)

    status = service.market_depth_status(symbols=["AAPL"], require_l2=False)
    assert status["selected_provider"] in {"fake_l2", "byo_file", "unavailable"}
    assert "provider_capabilities" in status

    replay = service.market_depth_replay(symbol="AAPL", limit=6, require_l2=True, persist=True)
    assert replay["session_id"].startswith("depth-aapl-")
    assert replay["summary"]["snapshot_count"] == 6
    assert replay["summary"]["proxy_mode"] in {"l1", "none"}
    if replay["data_tier"] != "l2":
        assert "l2_required_but_unavailable" in replay["warnings"]


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
