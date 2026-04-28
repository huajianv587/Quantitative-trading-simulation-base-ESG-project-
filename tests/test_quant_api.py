from pathlib import Path
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
import pandas as pd

import gateway.main as main_module
from gateway.config import settings
from gateway.quant.market_data import MarketBarsResult
from gateway.quant.models import PortfolioSummary, ResearchSignal
from gateway.quant.service import QuantSystemService


EXECUTION_HEADERS = {"x-api-key": settings.EXECUTION_API_KEY}


def _bars_result(symbol: str, closes: list[float], provider: str = "alpaca") -> MarketBarsResult:
    anchor = datetime.now(timezone.utc) - timedelta(days=len(closes))
    frame = pd.DataFrame(
        [
            {
                "timestamp": (anchor + timedelta(days=index)).date().isoformat(),
                "open": value,
                "high": value * 1.01,
                "low": value * 0.99,
                "close": value,
                "volume": 1_000_000 + index * 10_000,
                "provider": provider,
                "timeframe": "1Day",
                "symbol": symbol,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }
            for index, value in enumerate(closes)
        ]
    )
    return MarketBarsResult(
        symbol=symbol,
        provider=provider,
        timeframe="1Day",
        cache_hit=False,
        bars=frame,
        cache_path=":memory:",
    )


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
        assert data["prediction_disabled_reason"] in {"market_data_unavailable", "prediction_mode_unavailable"}


def test_quant_dashboard_summary_contract_is_available():
    client = TestClient(main_module.app)

    response = client.get("/api/v1/quant/platform/dashboard-summary?provider=alpaca")

    assert response.status_code == 200
    payload = response.json()
    assert payload["selected_provider"] == "alpaca"
    assert "watchlist_signals" in payload
    assert "top_signals" in payload
    assert "position_symbols" in payload
    assert "live_account_snapshot" in payload
    assert "kpis" in payload
    assert "provider_status" in payload
    assert "fallback_preview" in payload


def test_quant_dashboard_secondary_contract_is_available():
    client = TestClient(main_module.app)

    response = client.get("/api/v1/quant/platform/dashboard-secondary?provider=alpaca")

    assert response.status_code == 200
    payload = response.json()
    assert payload["selected_provider"] == "alpaca"
    assert "sector_heatmap" in payload
    assert "market_surface" in payload
    assert "heatmap_nodes" in payload
    assert "portfolio_preview" in payload
    assert "latest_backtest" in payload


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


def test_dashboard_summary_skips_secondary_builds(monkeypatch):
    service = QuantSystemService()
    signal = ResearchSignal(
        symbol="AAPL",
        company_name="Apple",
        sector="Technology",
        thesis="Cached watchlist summary.",
        action="long",
        confidence=0.82,
        expected_return=0.031,
        risk_score=28.0,
        overall_score=83.0,
        e_score=77.0,
        s_score=75.0,
        g_score=78.0,
        factor_scores=[],
        catalysts=[],
        data_lineage=[],
        regime_label="risk_on",
    )
    snapshot = {
        "position_symbols": ["AAPL"],
        "universe": service.get_default_universe(["AAPL"]),
        "signals": [signal],
        "watchlist_signals": [service._serialize_watchlist_signal(signal)],
        "_bars_map": {"AAPL": _bars_result("AAPL", [100.0, 101.5, 102.0])},
    }

    monkeypatch.setattr(service, "_build_dashboard_watchlist_snapshot", lambda *args, **kwargs: snapshot)
    monkeypatch.setattr(service, "_get_live_account_snapshot", lambda *args, **kwargs: {"account": {"equity": 1_250_000}})
    monkeypatch.setattr(service, "_build_market_surface", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("secondary path should stay idle")))
    monkeypatch.setattr(service, "_build_portfolio", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("secondary path should stay idle")))
    monkeypatch.setattr(service, "_build_backtest", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("secondary path should stay idle")))

    payload = service.build_dashboard_summary(provider="alpaca")

    assert payload["symbol"] == "AAPL"
    assert payload["watchlist_signals"][0]["symbol"] == "AAPL"
    assert payload["kpis"]["signal_count"] == 1


def test_dashboard_state_uses_cached_chart_without_rebuilding_watchlist(monkeypatch):
    service = QuantSystemService()
    chart_payload = {
        "symbol": "AAPL",
        "source": "alpaca",
        "selected_provider": "alpaca",
        "data_source_chain": ["alpaca", "cache", "synthetic"],
        "provider_status": {"available": True, "provider": "alpaca", "selected_provider": "alpaca"},
        "candles": [{"date": "2026-04-24", "close": 101.5}],
        "fallback_preview": {"reason": [], "next_actions": ["refresh_dashboard"]},
    }
    service._chart_cache[("AAPL", "1D", "alpaca")] = service._cache_wrap(chart_payload, ttl_seconds=30)
    monkeypatch.setattr(service, "_build_watchlist_snapshot", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("state should not rebuild watchlist")))
    monkeypatch.setattr(service, "_build_dashboard_watchlist_snapshot", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("state should not rebuild dashboard watchlist")))

    payload = service.build_dashboard_state(provider="alpaca", symbol="AAPL")

    assert payload["ready"] is True
    assert payload["symbol"] == "AAPL"
    assert payload["provider_status"]["provider"] == "alpaca"


def test_dashboard_chart_explicit_symbol_skips_watchlist_rebuild(monkeypatch):
    service = QuantSystemService()
    monkeypatch.setattr(service, "_build_watchlist_snapshot", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("chart should not rebuild watchlist")))
    monkeypatch.setattr(service, "_build_dashboard_watchlist_snapshot", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("chart should not rebuild dashboard watchlist")))
    monkeypatch.setattr(service.market_data, "get_daily_bars", lambda *args, **kwargs: _bars_result("AAPL", [100.0, 101.0, 102.0], provider="alpaca"))
    monkeypatch.setattr(service, "_safe_get_clock", lambda *args, **kwargs: None)
    monkeypatch.setattr(service, "_prepare_broker_adapter", lambda *args, **kwargs: (object(), "paper"))

    payload = service.build_dashboard_chart(symbol="AAPL", timeframe="1D", provider="alpaca")

    assert payload["symbol"] == "AAPL"
    assert payload["candles"]
    assert payload["source"] == "alpaca"


def test_dashboard_secondary_reuses_prefetched_watchlist_bars(monkeypatch):
    service = QuantSystemService()
    signal = ResearchSignal(
        symbol="AAPL",
        company_name="Apple",
        sector="Technology",
        thesis="Warm summary bars should be reused.",
        action="long",
        confidence=0.81,
        expected_return=0.024,
        risk_score=25.0,
        overall_score=81.0,
        e_score=76.0,
        s_score=74.0,
        g_score=75.0,
        factor_scores=[],
        catalysts=[],
        data_lineage=[],
    )
    snapshot = {
        "position_symbols": ["AAPL"],
        "universe": service.get_default_universe(["AAPL"]),
        "signals": [signal],
        "watchlist_signals": [service._serialize_watchlist_signal(signal)],
        "_bars_map": {"AAPL": _bars_result("AAPL", [100.0, 101.0, 102.0])},
    }
    calls: list[str] = []

    monkeypatch.setattr(service, "_build_watchlist_snapshot", lambda *args, **kwargs: snapshot)
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
    monkeypatch.setattr(service.storage, "list_records", lambda kind: [{"metrics": {"sharpe": 1.1}, "risk_alerts": []}] if kind == "backtests" else [])

    def _tracked_get_daily_bars(symbol, *args, **kwargs):
        calls.append(symbol)
        return _bars_result(symbol, [100.0, 100.5, 101.0], provider="alpaca")

    monkeypatch.setattr(service.market_data, "get_daily_bars", _tracked_get_daily_bars)

    payload = service.build_dashboard_secondary(provider="alpaca")

    assert payload["market_surface"]
    assert "AAPL" not in calls


def test_dashboard_summary_dedupes_symbols_and_prefers_position_model_coverage(monkeypatch):
    service = QuantSystemService()

    def _signal_for(symbol: str, *, predicted: bool) -> ResearchSignal:
        return ResearchSignal(
            symbol=symbol,
            company_name=symbol,
            sector="Technology",
            thesis=f"{symbol} snapshot",
            action="long" if predicted else "neutral",
            confidence=0.81,
            expected_return=0.024 if predicted else 0.0,
            risk_score=25.0,
            overall_score=81.0 if predicted else 72.0,
            e_score=76.0,
            s_score=74.0,
            g_score=75.0,
            predicted_return_5d=0.031 if predicted else None,
            predicted_volatility_10d=0.102 if predicted else None,
            predicted_drawdown_20d=0.081 if predicted else None,
            market_data_source="alpaca",
            factor_scores=[],
            catalysts=[],
            data_lineage=["alpaca"],
            regime_label="risk_on",
        )

    def _fake_build_signal_bundle(universe, *args, **kwargs):
        symbols = [member.symbol for member in universe]
        return ([_signal_for(symbol, predicted=(symbol == "NEE")) for symbol in symbols], {})

    monkeypatch.setattr(service, "_get_position_symbols", lambda *args, **kwargs: ["NEE", "AAPL"])
    monkeypatch.setattr(service, "_build_signal_bundle", _fake_build_signal_bundle)
    monkeypatch.setattr(service, "_get_live_account_snapshot", lambda *args, **kwargs: {"account": {"equity": 1_100_000}})

    payload = service.build_dashboard_summary(provider="alpaca")

    symbols = [item["symbol"] for item in payload["watchlist_signals"]]
    assert symbols == list(dict.fromkeys(symbols))
    assert payload["symbol"] == "NEE"


def test_dashboard_chart_and_state_keep_real_chart_ready_when_model_coverage_is_unavailable(monkeypatch):
    service = QuantSystemService()
    signal = ResearchSignal(
        symbol="GOOGL",
        company_name="Alphabet",
        sector="Communication Services",
        thesis="Real candles remain available even when the model does not cover this name.",
        action="neutral",
        confidence=0.5,
        expected_return=0.0,
        risk_score=36.0,
        overall_score=74.0,
        e_score=70.0,
        s_score=71.0,
        g_score=72.0,
        market_data_source="alpaca",
        factor_scores=[],
        catalysts=[],
        data_lineage=["alpaca daily bars"],
        regime_label="neutral",
    )
    snapshot = {
        "position_symbols": ["GOOGL"],
        "universe": service.get_default_universe(["GOOGL"]),
        "signals": [signal],
        "watchlist_signals": [service._serialize_watchlist_signal(signal)],
        "_bars_map": {"GOOGL": _bars_result("GOOGL", [91.0, 92.0, 95.82], provider="alpaca")},
    }
    service._dashboard_watchlist_snapshot_cache["alpaca"] = {
        "payload": snapshot,
        "expires_at": datetime.now(timezone.utc) - timedelta(seconds=1),
    }

    monkeypatch.setattr(service.market_data, "get_daily_bars", lambda *args, **kwargs: _bars_result("GOOGL", [91.0, 92.0, 95.82], provider="alpaca"))
    monkeypatch.setattr(service, "_safe_get_clock", lambda *args, **kwargs: None)
    monkeypatch.setattr(service, "_prepare_broker_adapter", lambda *args, **kwargs: (object(), "paper"))

    chart = service.build_dashboard_chart(symbol="GOOGL", timeframe="1D", provider="alpaca")
    state = service.build_dashboard_state(provider="alpaca", symbol="GOOGL")

    assert chart["source"] == "alpaca"
    assert chart["candles"]
    assert chart["prediction_disabled_reason"] == "prediction_mode_unavailable"
    assert chart["projection_scenarios"] == {}
    assert "prediction_mode_unavailable" not in chart["fallback_preview"]["reason"]
    assert state["ready"] is True
    assert "prediction_mode_unavailable" not in state["fallback_preview"]["reason"]


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
    assert "paper_gate" in controls.json()

    paper_gate = client.get("/api/v1/quant/execution/paper-gate", headers=EXECUTION_HEADERS)
    assert paper_gate.status_code == 200
    assert "live_blocked_until_paper_gate" in paper_gate.json()
    assert "markdown" in paper_gate.json()

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


def test_quant_research_extensions_cover_sweep_tearsheet_and_dataset_quality():
    client = TestClient(main_module.app)

    backtest = client.post(
        "/api/v1/quant/backtests/run",
        json={
            "strategy_name": "ESG Multi-Factor Long-Only",
            "universe": ["AAPL", "MSFT", "NVDA"],
            "benchmark": "SPY",
            "capital_base": 500000,
            "lookback_days": 90,
        },
    )
    assert backtest.status_code == 200
    backtest_payload = backtest.json()
    assert backtest_payload["tearsheet_report_id"].startswith("tearsheet-")
    assert backtest_payload["sweep_preview"]["run_id"].startswith("sweep-")
    assert backtest_payload["data_tier"] == "l1"
    assert backtest_payload["market_depth_status"]["data_tier"] == "l1"

    sweep = client.post(
        "/api/v1/quant/backtests/sweep",
        json={
            "strategy_name": "ESG Multi-Factor Long-Only",
            "universe": ["AAPL", "MSFT", "NVDA"],
            "benchmark": "SPY",
            "capital_base": 500000,
            "lookback_days": 90,
            "parameter_grid": {
                "lookback_days": [90],
                "position_scale": [1.0],
                "position_cap": [1.0],
                "signal_return_scale": [1.0],
                "transaction_cost_bps": [0.0],
            },
            "top_k": 1,
        },
    )
    assert sweep.status_code == 200
    sweep_payload = sweep.json()
    assert sweep_payload["best_run"]["parameters"]["lookback_days"] == 90
    assert sweep_payload["best_run"]["metrics"]["cumulative_return"] == backtest_payload["metrics"]["cumulative_return"]

    stored_sweep = client.get(f"/api/v1/quant/backtests/sweep/{sweep_payload['run_id']}")
    assert stored_sweep.status_code == 200
    assert stored_sweep.json()["run_id"] == sweep_payload["run_id"]

    tearsheet = client.get(f"/api/v1/quant/reports/tearsheet/{backtest_payload['backtest_id']}")
    assert tearsheet.status_code == 200
    tearsheet_payload = tearsheet.json()
    assert tearsheet_payload["report_id"] == backtest_payload["tearsheet_report_id"]
    assert "<html" in tearsheet_payload["html"].lower()
    assert "cost_sensitivity" in tearsheet_payload["sections"]
    assert tearsheet_payload["data_tier"] == "l1"

    dataset = client.post(
        "/api/v1/quant/research/datasets/build",
        json={"universe": ["AAPL", "MSFT"], "mode": "local", "include_intraday": True},
    )
    assert dataset.status_code == 200
    dataset_payload = dataset.json()
    assert dataset_payload["dataset_id"].startswith("dataset-")
    assert dataset_payload["instruments"]
    assert dataset_payload["provider_chain"]
    assert "market_depth_status" in dataset_payload

    datasets = client.get("/api/v1/quant/research/datasets?limit=5")
    assert datasets.status_code == 200
    assert datasets.json()["dataset_count"] >= 1

    quality = client.post(
        "/api/v1/quant/research/quality/checks",
        json={
            "universe": ["AAPL", "MSFT"],
            "mode": "local",
            "formulas": ["lead(close, 1)", "rolling_mean(close, 20)"],
            "timestamps": ["2099-01-01T00:00:00+00:00"],
            "current_constituents_only": True,
        },
    )
    assert quality.status_code == 200
    quality_payload = quality.json()
    assert quality_payload["protection_status"] == "blocked"
    assert quality_payload["checks"]["recursive_formula"]["passed"] is False
    assert quality_payload["checks"]["lookahead"]["passed"] is False
    assert "l2_availability" in quality_payload["checks"]

    depth_status = client.get("/api/v1/quant/market-depth/status?symbols=AAPL&require_l2=true")
    assert depth_status.status_code == 200
    depth_status_payload = depth_status.json()
    assert "provider_capabilities" in depth_status_payload
    assert depth_status_payload["eligibility_status"] in {"blocked", "pass", "review"}

    depth_latest = client.get("/api/v1/quant/market-depth/latest?symbol=AAPL")
    assert depth_latest.status_code == 200
    assert depth_latest.json()["symbol"] == "AAPL"

    depth_replay = client.post(
        "/api/v1/quant/market-depth/replay",
        json={"symbol": "AAPL", "limit": 5, "required_data_tier": "l2", "persist": True},
    )
    assert depth_replay.status_code == 200
    replay_payload = depth_replay.json()
    assert replay_payload["session_id"].startswith("depth-aapl-")
    assert replay_payload["summary"]["snapshot_count"] == 5

    stored_replay = client.get(f"/api/v1/quant/market-depth/replay/{replay_payload['session_id']}")
    assert stored_replay.status_code == 200
    assert stored_replay.json()["session_id"] == replay_payload["session_id"]


def test_quant_execution_websocket_stream_emits_snapshot():
    client = TestClient(main_module.app)
    api_key = EXECUTION_HEADERS["x-api-key"]

    with client.websocket_connect(f"/api/v1/quant/execution/live/ws?api_key={api_key}&broker=alpaca&limit=5") as ws:
        payload = ws.receive_json()

    assert payload["broker_id"] == "alpaca"
    assert "controls" in payload
    assert "orders" in payload


def test_quant_market_depth_websocket_stream_emits_snapshot():
    client = TestClient(main_module.app)

    with client.websocket_connect("/api/v1/quant/market-depth/live/ws?symbols=AAPL&require_l2=false") as ws:
        payload = ws.receive_json()

    assert payload["event"] == "market_depth_tick"
    assert payload["symbols"] == ["AAPL"]
    assert "latest" in payload


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
