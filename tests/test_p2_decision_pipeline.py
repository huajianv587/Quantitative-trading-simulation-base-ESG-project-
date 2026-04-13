from gateway.quant.service import QuantSystemService


def test_p2_stack_enriches_signals_with_graph_and_selector_fields():
    service = QuantSystemService()
    universe = service.get_default_universe(["AAPL", "MSFT", "TSLA", "NEE", "PG"])

    signals = service._build_signals(universe, "Run the P2 decision stack.", "SPY")

    assert signals
    assert all(signal.selector_strategy for signal in signals)
    assert all(signal.bandit_strategy for signal in signals)
    assert all(signal.decision_score is not None for signal in signals)
    assert any(signal.graph_neighbors for signal in signals)


def test_p2_decision_report_contains_graph_selector_and_portfolio():
    service = QuantSystemService()

    payload = service.build_p2_decision_report(
        universe_symbols=["AAPL", "MSFT", "TSLA", "NEE", "PG"],
        benchmark="SPY",
        capital_base=500000,
        research_question="Run the P2 graph + strategy selector report.",
    )

    assert payload["report_id"].startswith("p2-")
    assert "graph_summary" in payload
    assert "strategy_selector" in payload
    assert "bandit" in payload["strategy_selector"]
    assert "deployment_readiness" in payload
    assert payload["portfolio"]["strategy_name"].startswith("ESG P2 Decision Stack")
