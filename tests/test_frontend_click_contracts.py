from pathlib import Path


CLICK_TARGETS = {
    "frontend/js/pages/research-lab.js": ["#run-research-btn"],
    "frontend/js/pages/intelligence.js": [
        "#btn-intel-scan",
        "#btn-decision-explain",
        "#btn-open-factor-lab",
        "#btn-open-simulation",
    ],
    "frontend/js/pages/factor-lab.js": [
        "#btn-factor-discover",
        "#btn-factor-refresh",
    ],
    "frontend/js/pages/simulation.js": [
        "#btn-simulate-scenario",
    ],
    "frontend/js/pages/connector-center.js": [
        "#btn-connector-health",
        "#btn-connector-test",
        "#btn-connector-live-scan",
    ],
    "frontend/js/pages/market-radar.js": [
        "#btn-market-radar-scan",
        "#btn-market-radar-refresh",
    ],
    "frontend/js/pages/agent-lab.js": [
        "#btn-agent-workflow",
    ],
    "frontend/js/pages/outcome-center.js": [
        "#btn-outcome-refresh",
        "#btn-outcome-record",
    ],
    "frontend/js/pages/portfolio-lab.js": ["#optimize-portfolio-btn", "#generate-execution-btn"],
    "frontend/js/pages/backtests.js": ["#run-backtest-btn"],
    "frontend/js/pages/chat.js": ["#send-btn"],
    "frontend/js/pages/score-dashboard.js": ["#score-btn"],
    "frontend/js/pages/reports.js": ["#generate-btn"],
    "frontend/js/pages/data-management.js": ["#sync-btn"],
    "frontend/js/pages/push-rules.js": ["#new-rule-btn"],
    "frontend/js/pages/subscriptions.js": ["#create-sub-btn"],
}


def test_click_targets_are_present_in_page_sources():
    for relative_path, selectors in CLICK_TARGETS.items():
        content = Path(relative_path).read_text(encoding="utf-8")
        for selector in selectors:
            assert selector in content, f"{selector} missing from {relative_path}"


def test_router_declares_quant_routes():
    router_source = Path("frontend/js/router.js").read_text(encoding="utf-8")
    for route in [
        "/overview",
        "/research",
        "/intelligence",
        "/factor-lab",
        "/simulation",
        "/connector-center",
        "/market-radar",
        "/agent-lab",
        "/outcome-center",
        "/portfolio",
        "/backtests",
        "/chat",
        "/score",
    ]:
        assert route in router_source


def test_intelligence_api_client_declares_public_methods():
    api_source = Path("frontend/js/qtapi.js").read_text(encoding="utf-8")
    for route in [
        "/intelligence/scan",
        "/intelligence/evidence",
        "/factors/discover",
        "/factors/registry",
        "/decision/explain",
        "/decision/audit-trail",
        "/simulate/scenario",
        "/outcomes/evaluate",
        "/api/v1/connectors/registry",
        "/api/v1/connectors/health",
        "/api/v1/connectors/test",
        "/api/v1/connectors/live-scan",
        "/api/v1/connectors/runs",
        "/api/v1/connectors/quota",
    ]:
        assert route in api_source


def test_intelligence_page_uses_responsive_action_layout():
    page_source = Path("frontend/js/pages/intelligence.js").read_text(encoding="utf-8")
    css_source = Path("frontend/css/app.css").read_text(encoding="utf-8")

    assert "intelligence-action-grid" in page_source
    assert "intelligence-action-btn" in page_source
    assert ".intelligence-action-grid" in css_source
    assert ".workbench-action-grid" in css_source
    assert "grid-template-columns: 1fr" in css_source
    assert "white-space: normal" in css_source
    assert "overflow-wrap: anywhere" in css_source


def test_workbench_pages_are_split_by_product_area():
    intelligence = Path("frontend/js/pages/intelligence.js").read_text(encoding="utf-8")
    factor_lab = Path("frontend/js/pages/factor-lab.js").read_text(encoding="utf-8")
    simulation = Path("frontend/js/pages/simulation.js").read_text(encoding="utf-8")

    assert "api.decision.explain" in intelligence
    assert "api.factors.discover" not in intelligence
    assert "api.simulate.scenario" not in intelligence
    assert "api.factors.discover" in factor_lab
    assert "api.simulate.scenario" in simulation
