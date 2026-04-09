from pathlib import Path

from fastapi.testclient import TestClient

import gateway.main as main_module


def test_quant_platform_overview_is_available():
    client = TestClient(main_module.app)

    response = client.get("/api/v1/quant/platform/overview")

    assert response.status_code == 200
    data = response.json()
    assert data["platform_name"] == "ESG Quant Intelligence System"
    assert data["storage"]["mode"] in {"local_fallback", "hybrid_cloud"}
    assert data["top_signals"]
    assert data["portfolio_preview"]["positions"]


def test_quant_research_backtest_and_execution_flow():
    client = TestClient(main_module.app)

    research = client.post(
        "/api/v1/quant/research/run",
        json={
            "universe": ["AAPL", "MSFT", "TSLA"],
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

    backtest = client.post(
        "/api/v1/quant/backtests/run",
        json={
            "strategy_name": "ESG Multi-Factor Long-Only",
            "universe": ["AAPL", "MSFT", "TSLA"],
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
        json={
            "universe": ["AAPL", "MSFT", "TSLA"],
            "benchmark": "SPY",
            "capital_base": 500000,
            "mode": "paper",
        },
    )
    assert execution.status_code == 200
    execution_payload = execution.json()
    assert execution_payload["ready"] is True
    assert execution_payload["orders"]

    account = client.get("/api/v1/quant/execution/account")
    assert account.status_code == 200
    assert "broker_connection" in account.json()

    orders = client.get("/api/v1/quant/execution/orders")
    assert orders.status_code == 200
    assert "orders" in orders.json()

    positions = client.get("/api/v1/quant/execution/positions")
    assert positions.status_code == 200
    assert "positions" in positions.json()
