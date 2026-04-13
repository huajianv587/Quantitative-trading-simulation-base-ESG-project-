from pathlib import Path

from fastapi.testclient import TestClient

import gateway.main as main_module
from gateway.config import settings


EXECUTION_HEADERS = {"x-api-key": settings.EXECUTION_API_KEY}


def test_quant_platform_overview_is_available():
    client = TestClient(main_module.app)

    response = client.get("/api/v1/quant/platform/overview")

    assert response.status_code == 200
    data = response.json()
    assert data["platform_name"] == "ESG Quant Intelligence System"
    assert data["storage"]["mode"] in {"local_fallback", "hybrid_cloud"}
    assert data["top_signals"]
    assert data["portfolio_preview"]["positions"]
    assert "p1_suite" in data
    assert "p1_signal_snapshot" in data
    assert "p2_stack" in data
    assert "p2_decision_snapshot" in data


def test_quant_research_backtest_and_execution_flow():
    client = TestClient(main_module.app)

    research = client.post(
        "/api/v1/quant/research/run",
        json={
            "universe": [],
            "benchmark": "SPY",
            "research_question": "Generate an ESG quant shortlist.",
            "capital_base": 500000,
            "horizon_days": 15,
        },
    )
    assert research.status_code == 200
    research_payload = research.json()
    assert research_payload["research_id"].startswith("research-")
    assert Path(research_payload["storage"]["local_path"]).exists()
    assert research_payload["signals"][0]["p1_stack_score"] is not None
    execution_universe = [
        signal["symbol"]
        for signal in research_payload["signals"]
        if signal["action"] == "long"
    ][:3]
    assert execution_universe

    backtest = client.post(
        "/api/v1/quant/backtests/run",
        json={
            "strategy_name": "ESG Multi-Factor Long-Only",
            "universe": execution_universe,
            "benchmark": "SPY",
            "capital_base": 500000,
            "lookback_days": 90,
        },
    )
    assert backtest.status_code == 200
    backtest_payload = backtest.json()
    assert backtest_payload["backtest_id"].startswith("backtest-")
    assert backtest_payload["metrics"]["sharpe"] >= 0

    execution = client.post(
        "/api/v1/quant/execution/paper",
        headers=EXECUTION_HEADERS,
        json={
            "universe": execution_universe,
            "benchmark": "SPY",
            "capital_base": 500000,
            "mode": "paper",
            "allow_duplicates": True,
        },
    )
    assert execution.status_code == 200
    execution_payload = execution.json()
    assert execution_payload["ready"] is True
    assert execution_payload["orders"]

    account = client.get("/api/v1/quant/execution/account", headers=EXECUTION_HEADERS)
    assert account.status_code == 200
    assert "broker_connection" in account.json()

    brokers = client.get("/api/v1/quant/execution/brokers", headers=EXECUTION_HEADERS)
    assert brokers.status_code == 200
    assert brokers.json()["brokers"]

    p1_status = client.get("/api/v1/quant/p1/status")
    assert p1_status.status_code == 200
    assert "models" in p1_status.json()
    assert "sequence_forecaster" in p1_status.json()

    p1_stack = client.post(
        "/api/v1/quant/p1/stack/run",
        json={
            "universe": execution_universe,
            "benchmark": "SPY",
            "capital_base": 500000,
            "research_question": "Run the P1 alpha + risk stack.",
        },
    )
    assert p1_stack.status_code == 200
    assert p1_stack.json()["report_id"].startswith("p1-")
    assert "deployment_readiness" in p1_stack.json()

    p2_status = client.get("/api/v1/quant/p2/status")
    assert p2_status.status_code == 200
    assert "selector" in p2_status.json()
    assert "bandit" in p2_status.json()["selector"]

    p2_stack = client.post(
        "/api/v1/quant/p2/decision/run",
        json={
            "universe": execution_universe,
            "benchmark": "SPY",
            "capital_base": 500000,
            "research_question": "Run the P2 graph + strategy selector stack.",
        },
    )
    assert p2_stack.status_code == 200
    assert p2_stack.json()["report_id"].startswith("p2-")
    assert "strategy_selector" in p2_stack.json()

    controls = client.get("/api/v1/quant/execution/controls", headers=EXECUTION_HEADERS)
    assert controls.status_code == 200
    assert "kill_switch_enabled" in controls.json()

    monitor = client.get("/api/v1/quant/execution/monitor", headers=EXECUTION_HEADERS)
    assert monitor.status_code == 200
    assert "orders" in monitor.json()

    orders = client.get("/api/v1/quant/execution/orders", headers=EXECUTION_HEADERS)
    assert orders.status_code == 200
    assert "orders" in orders.json()

    positions = client.get("/api/v1/quant/execution/positions", headers=EXECUTION_HEADERS)
    assert positions.status_code == 200
    assert "positions" in positions.json()

    journal = client.get(
        f"/api/v1/quant/execution/journal/{execution_payload['execution_id']}",
        headers=EXECUTION_HEADERS,
    )
    assert journal.status_code == 200
    assert journal.json()["execution_id"] == execution_payload["execution_id"]

    validation = client.post(
        "/api/v1/quant/validation/run",
        headers=EXECUTION_HEADERS,
        json={
            "strategy_name": "ESG Multi-Factor Long-Only",
            "universe": execution_universe,
            "benchmark": "SPY",
            "capital_base": 500000,
            "in_sample_days": 180,
            "out_of_sample_days": 45,
            "walk_forward_windows": 2,
        },
    )
    assert validation.status_code == 200
    assert validation.json()["validation_id"].startswith("validation-")


def test_quant_execution_websocket_stream_emits_snapshot():
    client = TestClient(main_module.app)
    api_key = EXECUTION_HEADERS["x-api-key"]

    with client.websocket_connect(f"/api/v1/quant/execution/live/ws?api_key={api_key}&broker=alpaca&limit=5") as ws:
        payload = ws.receive_json()

    assert payload["broker_id"] == "alpaca"
    assert "controls" in payload
    assert "orders" in payload
