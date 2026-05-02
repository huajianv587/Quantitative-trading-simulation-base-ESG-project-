from fastapi.testclient import TestClient

import blueprint_runtime
import gateway.main as main_module


def _client() -> TestClient:
    return TestClient(main_module.app)


def test_quant_capabilities_endpoint_reports_module_status():
    response = _client().get("/api/v1/quant/capabilities")

    assert response.status_code == 200
    payload = response.json()
    assert payload["overall_status"] in {"ready", "degraded", "blocked"}
    modules = {item["module"]: item for item in payload["modules"]}
    for name in ["analysis", "models", "agents", "data", "risk", "backtest", "infrastructure", "reporting", "rag"]:
        assert name in modules
        assert modules[name]["status"] in {"ready", "degraded", "blocked"}
        assert modules[name]["web_route"].startswith("/")
        assert isinstance(modules[name]["config_gaps"], list)


def test_blueprint_analysis_endpoint_returns_real_technical_metrics():
    response = _client().post(
        "/api/v1/quant/analysis/run",
        json={
            "family": "technical",
            "symbol": "AAPL",
            "prices": [180, 181.5, 179.2, 183.4, 184.1, 186.2, 185.6, 188.4, 190.1, 191.3, 193.0],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["technical_metrics"]["last_close"] == 193.0
    assert payload["technical_metrics"]["trend_regime"] in {"uptrend", "downtrend", "mixed"}
    assert payload["contract"]["outputs"]


def test_blueprint_model_train_and_predict_endpoints_share_fit_predict_contract():
    train = _client().post(
        "/api/v1/quant/models/train",
        json={
            "model_key": "contract_linear_alpha",
            "X": [[1, 0.2], [0.8, 0.1], [1.2, 0.3], [0.7, -0.1]],
            "y": [0.03, 0.018, 0.041, 0.004],
        },
    )
    assert train.status_code == 200
    train_payload = train.json()
    assert train_payload["training"]["status"] == "fit_complete"
    assert train_payload["evaluation"]["status"] == "evaluated"

    predict = _client().post(
        "/api/v1/quant/models/predict",
        json={"model_key": "contract_linear_alpha", "X": [[1.1, 0.25], [0.6, -0.05]]},
    )
    assert predict.status_code == 200
    predict_payload = predict.json()
    assert predict_payload["status"] == "completed"
    assert predict_payload["prediction_count"] == 2
    assert len(predict_payload["predictions"]) == 2


def test_blueprint_data_pipeline_exposes_governance_contract():
    response = _client().post(
        "/api/v1/quant/data/pipeline/run",
        json={"symbols": ["AAPL", "MSFT"], "loader": "price_loader"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] in {"completed", "degraded"}
    assert payload["dataset"]["record_count"] >= 1
    assert payload["governance"]["status"] == "processed"
    assert payload["contract"]["primary_key"] == ["symbol", "timestamp"]


def test_blueprint_risk_endpoint_returns_execution_gate():
    response = _client().post(
        "/api/v1/quant/risk/evaluate",
        json={
            "nav": [1.0, 1.01, 1.02, 1.025, 1.03],
            "returns": [0.01, 0.009, 0.004, 0.005],
            "max_drawdown_limit": 0.08,
            "sharpe_floor": 0.0,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["gate"] in {"pass", "blocked"}
    assert payload["results"]
    assert "recommendations" in payload


def test_blueprint_backtest_infrastructure_and_reporting_endpoints_are_callable():
    client = _client()

    backtest = client.post(
        "/api/v1/quant/backtest/advanced/run",
        json={"returns": [0.01, -0.004, 0.006, 0.002], "weights": {"AAPL": 0.5, "MSFT": 0.5}},
    )
    assert backtest.status_code == 200
    assert backtest.json()["summary"]["total_cost"] >= 0

    infrastructure = client.post(
        "/api/v1/quant/infrastructure/check",
        json={"metrics": {"population_drift": 0.03, "run_cost_usd": 12, "budget_usd": 100}},
    )
    assert infrastructure.status_code == 200
    assert infrastructure.json()["status"] in {"ready", "degraded"}

    reporting = client.post("/api/v1/quant/reporting/build", json={"metrics": {"sharpe": 1.2}})
    assert reporting.status_code == 200
    report_payload = reporting.json()
    assert report_payload["status"] == "ready"
    assert report_payload["reports"]


def test_blueprint_runtime_reports_empty_invalid_and_missing_dependency_states(monkeypatch, tmp_path):
    empty_analysis = blueprint_runtime.run_analysis_production({"family": "technical"})
    assert empty_analysis["status"] == "degraded"
    assert "empty_input" in empty_analysis["degraded_reasons"]
    assert empty_analysis["record_count"] == 0

    invalid_risk = blueprint_runtime.evaluate_risk_suite_production(
        {"nav": ["bad", None, 1.0], "returns": ["bad"], "restricted_symbols": ["AAPL"], "orders": [{"symbol": "AAPL"}]}
    )
    assert invalid_risk["gate"] == "blocked"
    assert invalid_risk["results"]

    monkeypatch.setenv("SCHEDULER_HEARTBEAT_PATH", str(tmp_path / "missing-heartbeat.json"))
    scheduler_check = blueprint_runtime.check_infrastructure_production({"modules": ["scheduler"]})
    assert scheduler_check["status"] == "degraded"
    assert scheduler_check["checks"][0]["metrics"]["heartbeat_exists"] == 0.0

    monkeypatch.setattr(blueprint_runtime, "_dependency_available", lambda name: name != "numpy")
    capabilities = blueprint_runtime.build_capabilities_report()
    modules = {item["module"]: item for item in capabilities["modules"]}
    assert modules["models"]["status"] == "blocked"
    assert "numpy" in modules["models"]["dependencies"]["missing_required"]
