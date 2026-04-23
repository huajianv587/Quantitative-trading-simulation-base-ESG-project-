from pathlib import Path

from fastapi.testclient import TestClient

import gateway.main as main_module
from gateway.config import settings
from gateway.quant.models import PortfolioSummary, ResearchSignal
from gateway.quant.service import QuantSystemService


EXECUTION_HEADERS = {"x-api-key": settings.EXECUTION_API_KEY}


def test_quant_platform_overview_is_available():
    client = TestClient(main_module.app)

    response = client.get("/api/v1/quant/platform/overview")

    assert response.status_code == 200
    data = response.json()
    assert data["platform_name"] == "ESG Quant Intelligence System"
    assert data["storage"]["mode"] in {"local_fallback", "hybrid_cloud"}
    assert data["top_signals"]
    assert data["watchlist_signals"]
    assert data["portfolio_preview"]["positions"]
    assert "p1_suite" in data
    assert "p1_signal_snapshot" in data
    assert "p2_stack" in data
    assert "p2_decision_snapshot" in data
    first_signal = data["watchlist_signals"][0]
    assert "market_data_source" in first_signal
    assert first_signal["prediction_mode"] in {"model", "unavailable"}
    assert "projection_scenarios" in first_signal
    assert "factor_scores" in first_signal
    assert "catalysts" in first_signal
    assert "data_lineage" in first_signal
    assert "house_score" in first_signal
    assert "house_grade" in first_signal
    assert "house_explanation" in first_signal
    assert data["sector_heatmap"]
    if first_signal["market_data_source"] == "synthetic":
        assert first_signal["prediction_mode"] == "unavailable"


def test_quant_dashboard_chart_contract_is_available():
    client = TestClient(main_module.app)

    response = client.get("/api/v1/quant/dashboard/chart?symbol=NVDA&timeframe=1D&provider=alpaca")

    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "NVDA"
    assert data["timeframe"] == "1D"
    assert data["selected_provider"] == "alpaca"
    assert "candles" in data
    assert "indicators" in data
    assert "viewport_defaults" in data
    assert "click_targets" in data
    assert "signal" in data
    assert "data_source_chain" in data
    if data["source"] == "synthetic" or data["signal"].get("prediction_mode") != "model":
        assert data["projection_scenarios"] == {}
        assert data["prediction_disabled_reason"] in {"synthetic_market_data", "prediction_mode_unavailable"}


def test_quant_research_context_contract_is_available():
    client = TestClient(main_module.app)

    response = client.get("/api/v1/quant/research/context?symbol=NVDA&provider=auto&limit=4")

    assert response.status_code == 200
    payload = response.json()
    assert payload["symbol"] == "NVDA"
    assert payload["provider"] == "auto"
    assert "quote_strip" in payload
    assert "feed" in payload
    assert "provider_status" in payload
    assert "source_chain" in payload
    assert "next_actions" in payload
    assert isinstance(payload["quote_strip"], list)
    assert isinstance(payload["feed"], list)


def test_platform_overview_watchlist_projection_respects_signed_decision(monkeypatch):
    service = QuantSystemService()
    signals = [
        ResearchSignal(
            symbol="NEE",
            company_name="NextEra Energy",
            sector="Utilities",
            thesis="Risk-off and drawdown filters keep the name in a cautious regime.",
            action="neutral",
            confidence=0.78,
            expected_return=-0.012,
            risk_score=41.0,
            overall_score=74.0,
            e_score=79.0,
            s_score=72.0,
            g_score=77.0,
            predicted_return_5d=0.064,
            predicted_volatility_10d=0.118,
            predicted_drawdown_20d=0.094,
            regime_label="risk_off",
            regime_probability=0.83,
            decision_confidence=0.76,
            market_data_source="yfinance",
            factor_scores=[],
            catalysts=["Short-term rebound branch exists but regime remains defensive."],
            data_lineage=["L0: yfinance daily bars", "L2: P1/P2 stacked decision"],
        )
    ]

    monkeypatch.setattr(service, "_build_signals", lambda *args, **kwargs: signals)
    monkeypatch.setattr(
        service,
        "_build_portfolio",
        lambda *args, **kwargs: PortfolioSummary(
            strategy_name="Test",
            benchmark="SPY",
            capital_base=1_000_000,
            gross_exposure=0.0,
            net_exposure=0.0,
            turnover_estimate=0.0,
            expected_alpha=0.0,
            positions=[],
            constraints={},
        ),
    )
    monkeypatch.setattr(
        service.storage,
        "list_records",
        lambda kind: [{"metrics": {"sharpe": 1.0}, "risk_alerts": []}] if kind == "backtests" else [],
    )

    overview = service.build_platform_overview()
    signal = overview["watchlist_signals"][0]

    assert signal["prediction_mode"] == "model"
    assert set(signal["projection_scenarios"]) == {"upper", "center", "lower"}
    assert signal["projection_basis_return"] < 0
    assert signal["projection_scenarios"]["center"]["expected_return"] < 0
    assert signal["projection_scenarios"]["upper"]["expected_return"] > signal["projection_scenarios"]["center"]["expected_return"]
    assert signal["projection_scenarios"]["lower"]["expected_return"] < signal["projection_scenarios"]["center"]["expected_return"]


def test_platform_overview_marks_synthetic_watchlist_items_unavailable(monkeypatch):
    service = QuantSystemService()
    signals = [
        ResearchSignal(
            symbol="AAPL",
            company_name="Apple",
            sector="Technology",
            thesis="Synthetic fallback signal for offline testing.",
            action="long",
            confidence=0.82,
            expected_return=0.034,
            risk_score=31.0,
            overall_score=80.0,
            e_score=79.0,
            s_score=76.0,
            g_score=78.0,
            predicted_return_5d=0.041,
            predicted_volatility_10d=0.102,
            predicted_drawdown_20d=0.086,
            market_data_source="synthetic",
            factor_scores=[],
            catalysts=[],
            data_lineage=["L0: synthetic fallback factor proxies"],
        )
    ]

    monkeypatch.setattr(service, "_build_signals", lambda *args, **kwargs: signals)
    monkeypatch.setattr(
        service,
        "_build_portfolio",
        lambda *args, **kwargs: PortfolioSummary(
            strategy_name="Test",
            benchmark="SPY",
            capital_base=1_000_000,
            gross_exposure=0.0,
            net_exposure=0.0,
            turnover_estimate=0.0,
            expected_alpha=0.0,
            positions=[],
            constraints={},
        ),
    )
    monkeypatch.setattr(
        service.storage,
        "list_records",
        lambda kind: [{"metrics": {"sharpe": 1.0}, "risk_alerts": []}] if kind == "backtests" else [],
    )

    overview = service.build_platform_overview()
    signal = overview["watchlist_signals"][0]

    assert signal["market_data_source"] == "synthetic"
    assert signal["prediction_mode"] == "unavailable"
    assert signal["projection_basis_return"] is None
    assert signal["projection_scenarios"] == {}


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


def test_portfolio_optimize_relaxes_unreachable_esg_floor_with_best_effort_holdings():
    client = TestClient(main_module.app)

    response = client.post(
        "/api/v1/quant/portfolio/optimize",
        json={
            "universe": ["PG", "UNH", "JPM", "MSFT"],
            "benchmark": "SPY",
            "capital_base": 500000,
            "research_question": "Build a resilient ESG-aware quality portfolio.",
            "preset_name": "Quality Core",
            "objective": "maximum_sharpe",
            "max_position_weight": 0.26,
            "max_sector_concentration": 0.2,
            "esg_floor": 60,
        },
    )

    assert response.status_code == 200
    payload = response.json()["portfolio"]
    assert payload["positions"]
    assert payload["constraints"]["status"] != "no_trade"
    assert payload["constraints"]["candidate_mode"] != "request_filter_rejected_all"
    if payload["constraints"].get("candidate_mode") == "request_filter_best_effort":
        assert payload["constraints"]["signal_filter"] == "best_effort_esg_relaxation"
        assert payload["constraints"]["requested_esg_floor"] == 60.0
        assert payload["constraints"]["achieved_min_esg_score"] < 60.0


def test_portfolio_optimize_uses_high_confidence_neutral_fallback_for_large_cap_blend():
    client = TestClient(main_module.app)

    response = client.post(
        "/api/v1/quant/portfolio/optimize",
        json={
            "universe": ["AAPL", "MSFT", "AMZN", "GOOGL", "META", "BRK.B"],
            "benchmark": "SPY",
            "capital_base": 1000000,
            "research_question": "User journey Large Cap Blend",
            "preset_name": "Large Cap Blend",
            "objective": "risk_parity",
            "max_position_weight": 0.25,
            "max_sector_concentration": 0.45,
            "esg_floor": 60,
        },
    )

    assert response.status_code == 200
    payload = response.json()["portfolio"]
    assert payload["positions"]
    assert payload["constraints"]["status"] != "no_trade"
    assert payload["constraints"]["candidate_mode"] in {
        "confidence_fallback",
        "breadth_fallback",
        "watchlist_fallback",
        "request_filter_best_effort",
        "ready",
    }
