from __future__ import annotations

from agents.strategy_agent import run_agent_task
from analysis.factors.multi_factor_scoring import analyze_payload
from backtest.monte_carlo import run_module as run_monte_carlo
from data.governance.feature_store import apply_pipeline
from data.ingestion.price_loader import load_dataset
from gateway.quant.models import UniverseMember
from infrastructure.cost_tracker import track
from models.supervised.ensemble_model import ModelAdapter
from reporting.factor_report import build_output


class _FakeService:
    default_benchmark = "SPY"

    def get_default_universe(self, symbols=None):
        base = [
            UniverseMember(symbol="AAPL", company_name="Apple", sector="Technology", industry="Consumer Electronics"),
            UniverseMember(symbol="MSFT", company_name="Microsoft", sector="Technology", industry="Software"),
            UniverseMember(symbol="NEE", company_name="NextEra Energy", sector="Utilities", industry="Regulated Electric"),
        ]
        if not symbols:
            return base
        wanted = {str(symbol).upper() for symbol in symbols}
        return [member for member in base if member.symbol in wanted]

    def build_platform_overview(self):
        return {
            "watchlist_signals": [
                {"symbol": "AAPL", "company_name": "Apple", "sector": "Technology", "score": 82},
                {"symbol": "MSFT", "company_name": "Microsoft", "sector": "Technology", "score": 79},
            ],
            "latest_backtest": {"metrics": {"sharpe": 1.42}},
        }


def test_blueprint_dataset_agent_and_report_outputs_share_runtime(monkeypatch):
    monkeypatch.setattr("gateway.quant.service.get_quant_system", lambda: _FakeService())

    dataset = load_dataset(["AAPL", "MSFT"])
    assert dataset["status"] == "loaded"
    assert dataset["record_count"] == 2
    assert dataset["records"][0]["dataset"] == "price"
    assert dataset["records"][0]["lineage"]

    agent = run_agent_task({"universe": ["AAPL", "MSFT"]})
    assert agent["status"] == "completed"
    assert agent["focus_symbols"] == ["AAPL", "MSFT"]
    assert agent["overview_excerpt"]["top_signals"][0]["symbol"] == "AAPL"

    report = build_output({"report_type": "factor"})
    assert report["status"] == "ready"
    assert report["summary"]["top_symbol"] == "AAPL"
    assert report["sections"][0]["title"] == "Top Signals"


def test_blueprint_analysis_governance_and_backtest_modules_produce_real_outputs():
    analysis = analyze_payload(
        {
            "records": [
                {"symbol": "AAPL", "score": 81.5, "expected_return": 0.023, "confidence": 0.82},
                {"symbol": "MSFT", "score": 76.2, "expected_return": 0.017, "confidence": 0.77},
            ]
        }
    )
    assert analysis["status"] == "completed"
    assert analysis["coverage"]["top_symbols"] == ["AAPL", "MSFT"]
    assert analysis["summary"]["average_expected_return"] > 0

    governance = apply_pipeline(
        [
            {"symbol": "AAPL", "timestamp": "2026-04-01T00:00:00Z", "value": 10.0},
            {"symbol": "AAPL", "timestamp": "2026-04-01T00:00:00Z", "value": 10.0},
            {"symbol": "MSFT", "timestamp": "2026-04-02T00:00:00Z", "value": None},
        ]
    )
    assert governance["status"] == "processed"
    assert governance["stats"]["duplicates_removed"] == 1
    assert governance["stats"]["missing_filled"] >= 1
    assert len(governance["records"]) == 2

    monte_carlo = run_monte_carlo({"path_count": 24, "step_count": 12, "drift": 0.001, "volatility": 0.01})
    assert monte_carlo["status"] == "completed"
    assert monte_carlo["path_count"] == 24
    assert monte_carlo["distribution"]["p95"] >= monte_carlo["distribution"]["p05"]


def test_blueprint_model_and_infrastructure_modules_are_stateful():
    adapter = ModelAdapter()
    fit_result = adapter.fit([[1.0, 2.0], [2.0, 3.0], [3.0, 5.0]], [0.5, 0.9, 1.4])
    predictions = adapter.predict([[4.0, 6.0], [1.0, 1.5]])
    evaluation = adapter.evaluate([[4.0, 6.0], [1.0, 1.5]], [1.8, 0.4])

    assert fit_result["status"] == "fit_complete"
    assert fit_result["feature_count"] == 2
    assert len(predictions) == 2
    assert predictions[0] != predictions[1]
    assert evaluation["status"] == "evaluated"

    runtime = track({"metrics": {"run_cost_usd": 150.0, "budget_usd": 100.0}})
    assert runtime["status"] == "tracked"
    assert runtime["ready"] is False
    assert runtime["warnings"]
