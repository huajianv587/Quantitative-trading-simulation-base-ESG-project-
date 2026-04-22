from pathlib import Path


CLICK_TARGETS = {
    "frontend/js/pages/dashboard.js": ["#dashboard-provider-select"],
    "frontend/js/pages/research.js": ["#btn-run-research"],
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
    "frontend/js/pages/debate-desk.js": [
        "#btn-debate-run",
        "#btn-debate-refresh",
        "#btn-debate-open-risk",
        "#btn-debate-open-ops",
    ],
    "frontend/js/pages/risk-board.js": [
        "#btn-risk-evaluate",
        "#btn-risk-refresh",
    ],
    "frontend/js/pages/trading-ops.js": [
        "#btn-trading-ops-refresh",
        "#btn-watchlist-add",
        "#btn-run-premarket",
        "#btn-autopilot-toggle",
        "#btn-monitor-start",
        "#btn-monitor-stop",
        "#btn-trading-cycle",
    ],
    "frontend/js/pages/outcome-center.js": [
        "#btn-outcome-refresh",
        "#btn-outcome-record",
    ],
    "frontend/js/pages/autopilot-policy.js": [
        "#btn-autopilot-refresh",
        "#btn-autopilot-save",
        "#btn-autopilot-arm",
        "#btn-autopilot-disarm",
    ],
    "frontend/js/pages/strategy-registry.js": [
        "#btn-strategy-refresh",
        "data-strategy-toggle",
        "data-strategy-save",
    ],
    "frontend/js/pages/backtest.js": ["#btn-run-bt"],
    "frontend/js/pages/portfolio.js": ["#btn-optimize", "#btn-to-execution", "#s5-execute"],
    "frontend/js/pages/chat.js": ["#send-btn"],
    "frontend/js/pages/score-dashboard.js": ["#score-btn"],
    "frontend/js/pages/reports.js": ["#generate-btn"],
    "frontend/js/pages/data-management.js": ["#sync-btn"],
    "frontend/js/pages/push-rules.js": ["#new-rule-btn"],
    "frontend/js/pages/subscriptions.js": ["#create-sub-btn"],
}


SUSPICIOUS_FRAGMENTS = [
    "缂",
    "閸",
    "閻",
    "鏉",
    "妞",
    "閺",
    "閹",
    "濞",
    "鐠",
    "鈥",
    "锟",
]


def test_click_targets_are_present_in_page_sources():
    for relative_path, selectors in CLICK_TARGETS.items():
        content = Path(relative_path).read_text(encoding="utf-8")
        for selector in selectors:
            assert selector in content, f"{selector} missing from {relative_path}"


def test_router_declares_current_workbench_routes():
    router_source = Path("frontend/js/router.js").read_text(encoding="utf-8")
    for route in [
        "/dashboard",
        "/research",
        "/intelligence",
        "/factor-lab",
        "/simulation",
        "/connector-center",
        "/market-radar",
        "/agent-lab",
        "/debate-desk",
        "/risk-board",
        "/trading-ops",
        "/autopilot-policy",
        "/strategy-registry",
        "/outcome-center",
        "/portfolio",
        "/backtest",
        "/execution",
        "/validation",
        "/models",
        "/rl-lab",
        "/chat",
        "/score",
        "/reports",
        "/data-management",
        "/push-rules",
        "/subscriptions",
    ]:
        assert route in router_source


def test_trading_api_client_declares_public_runtime_methods():
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
        "/api/v1/trading/schedule/status",
        "/api/v1/trading/watchlist",
        "/api/v1/trading/watchlist/add",
        "/api/v1/trading/review/latest",
        "/api/v1/trading/alerts/today",
        "/api/v1/trading/sentiment/run",
        "/api/v1/trading/debate/run",
        "/api/v1/trading/debate/runs",
        "/api/v1/trading/risk/evaluate",
        "/api/v1/trading/risk/board",
        "/api/v1/trading/cycle/run",
        "/api/v1/trading/monitor/status",
        "/api/v1/trading/ops/snapshot",
        "/api/v1/trading/autopilot/policy",
        "/api/v1/trading/autopilot/arm",
        "/api/v1/trading/autopilot/disarm",
        "/api/v1/trading/strategies",
        "/api/v1/trading/execution-path/status",
        "/api/v1/trading/dashboard/state",
        "/api/v1/trading/fusion/status",
    ]:
        assert route in api_source


def test_workbench_layout_css_exposes_dense_product_patterns():
    css_source = Path("frontend/css/app.css").read_text(encoding="utf-8")
    for selector in [
        ".workbench-action-grid",
        ".workbench-main-grid",
        ".nav-group__trigger",
        ".dashboard-degraded-banner",
        ".dashboard-provider-switch",
        ".backtest-layout",
        ".decision-evidence-card",
        ".connector-registry-body",
        ".risk-board-grid",
        ".outcome-top-grid",
        ".trading-ops-grid",
        ".workbench-action-btn--primary",
        ".workbench-action-btn--secondary",
    ]:
        assert selector in css_source


def test_critical_shell_and_workbench_files_do_not_contain_known_mojibake_fragments():
    targets = [
        "frontend/js/i18n.js",
        "frontend/js/app.js",
        "frontend/js/router.js",
        "frontend/js/components/nav.js",
        "frontend/js/pages/workbench-utils.js",
        "frontend/js/pages/intelligence.js",
        "frontend/js/pages/connector-center.js",
        "frontend/js/pages/agent-lab.js",
        "frontend/js/pages/market-radar.js",
        "frontend/js/pages/debate-desk.js",
        "frontend/js/pages/risk-board.js",
        "frontend/js/pages/outcome-center.js",
        "frontend/js/pages/trading-ops.js",
        "frontend/js/pages/autopilot-policy.js",
        "frontend/js/pages/dashboard.js",
        "frontend/js/pages/backtest.js",
    ]
    for relative_path in targets:
        content = Path(relative_path).read_text(encoding="utf-8")
        for fragment in SUSPICIOUS_FRAGMENTS:
            assert fragment not in content, f"{fragment!r} unexpectedly found in {relative_path}"


def test_i18n_declares_clean_chinese_shell_labels():
    content = Path("frontend/js/i18n.js").read_text(encoding="utf-8")
    for expected in [
        "'nav.platform': '平台'",
        "'page.dashboard': '控制台'",
        "'page.market_radar': '市场雷达'",
        "'page.debate_desk': '辩论台'",
        "'page.risk_board': '风控板'",
        "'page.trading_ops': '交易运维'",
        "'page.outcome_center': '结果追踪'",
        "'common.backend_online': '后端已连接'",
        "'common.page_failed_load': '页面加载失败'",
    ]:
        assert expected in content


def test_i18n_declares_required_shell_label_keys():
    content = Path("frontend/js/i18n.js").read_text(encoding="utf-8")
    for expected in [
        "'nav.platform':",
        "'page.dashboard':",
        "'page.market_radar':",
        "'page.debate_desk':",
        "'page.risk_board':",
        "'page.trading_ops':",
        "'page.outcome_center':",
        "'common.backend_online':",
        "'common.page_failed_load':",
    ]:
        assert expected in content
