from pathlib import Path


CLICK_TARGETS = {
    "frontend/js/pages/research-lab.js": ["#run-research-btn"],
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
    for route in ["/overview", "/research", "/portfolio", "/backtests", "/chat", "/score"]:
        assert route in router_source
