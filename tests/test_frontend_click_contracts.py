from pathlib import Path
import re


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
    "frontend/js/pages/execution.js": [
        "#btn-open-paper-performance",
    ],
    "frontend/js/pages/paper-performance.js": [
        "#btn-paper-performance-refresh",
        "#btn-paper-performance-snapshot",
        "#btn-paper-outcomes-settle",
        "#btn-paper-promotion-evaluate",
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
        "/paper-performance",
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


def test_router_declares_all_current_routes():
    router_source = Path("frontend/js/router.js").read_text(encoding="utf-8")
    routes = re.findall(r"'((?:/)[^']*)':\s*\{", router_source)
    assert len(routes) == 35


def test_router_redirects_empty_shell_urls_back_to_landing():
    router_source = Path("frontend/js/router.js").read_text(encoding="utf-8")
    assert "resolveLandingEntry" in router_source
    assert "window.location.replace(resolveLandingEntry())" in router_source


def test_trading_api_client_declares_public_runtime_methods():
    api_source = Path("frontend/js/qtapi.js").read_text(encoding="utf-8")
    for route in [
        "/session",
        "/history/",
        "/research/context",
        "/intelligence/scan",
        "/intelligence/evidence",
        "/factors/discover",
        "/factors/registry",
        "/decision/explain",
        "/decision/audit-trail",
        "/simulate/scenario",
        "/outcomes/evaluate",
        "/paper/performance",
        "/paper/outcomes/settle",
        "/promotion/report",
        "/deployment/preflight",
        "/trading-calendar/status",
        "/observability/paper-workflow",
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
        "/platform/dashboard-summary",
        "/platform/dashboard-secondary",
    ]:
        assert route in api_source


def test_real_only_pages_no_longer_reference_mock_or_demo_fallbacks():
    expectations = {
        "frontend/js/pages/chat.js": [
            "mockAgentResponse",
            "showing mock response",
        ],
        "frontend/js/pages/research.js": [
            "mockPrice",
            "mockChg",
            "mockNews",
            "genCandles",
        ],
        "frontend/js/pages/dashboard.js": [
            "mockOverview",
        ],
        "frontend/js/pages/score-dashboard.js": [
            "mockEsgResult",
            "showing mock data",
        ],
        "frontend/js/pages/validation.js": [
            "mockValidationResult",
        ],
        "frontend/js/pages/login.js": [
            "demo_title",
            "demo_text",
        ],
        "frontend/js/pages/data-management.js": [
            "simulateMockSync",
            "running mock sync",
        ],
        "frontend/js/pages/push-rules.js": [
            "mock_report",
        ],
        "frontend/js/pages/outcome-center.js": [
            "Record Demo Outcome",
            "demo shadow outcome",
            "记录演示结果",
            "演示 outcome",
        ],
        "frontend/js/pages/reports.js": [
            "mockReport",
            "showing mock report",
            "showing mock",
        ],
        "frontend/js/pages/rl-lab.js": [
            "#rl-build-demo",
            "Generate Demo Dataset",
            "use_demo_if_missing",
        ],
    }
    for relative_path, forbidden in expectations.items():
        content = Path(relative_path).read_text(encoding="utf-8")
        for fragment in forbidden:
            assert fragment not in content, f"{fragment!r} unexpectedly found in {relative_path}"


def test_workbench_layout_css_exposes_dense_product_patterns():
    css_source = Path("frontend/css/app.css").read_text(encoding="utf-8")
    for selector in [
        ".workbench-action-grid",
        ".workbench-main-grid",
        ".workbench-tabs",
        ".workbench-tab",
        ".nav-group__trigger",
        ".dashboard-degraded-banner",
        ".dashboard-provider-switch",
        ".backtest-layout",
        ".decision-evidence-card",
        ".connector-registry-body",
        ".risk-board-grid",
        ".risk-board-lower-grid",
        ".outcome-top-grid",
        ".reports-layout",
        ".report-archive-item",
        ".trading-ops-grid",
        ".workbench-action-btn--primary",
        ".workbench-action-btn--secondary",
        ".app-content > *",
    ]:
        assert selector in css_source


def test_reports_and_dashboard_keep_runtime_layout_hooks():
    reports_source = Path("frontend/js/pages/reports.js").read_text(encoding="utf-8")
    for hook in [
        "report-type-tabs",
        "reports-archive-body",
        "report-archive-item",
        "reports-workspace-body",
    ]:
        assert hook in reports_source

    dashboard_source = Path("frontend/js/pages/dashboard.js").read_text(encoding="utf-8")
    for hook in [
        "#kline-canvas",
        "#dashboard-health-banner",
        "#kline-status-note",
        "buildCachedSnapshotPayload",
        "renderChartFallbackCard",
        "dashboardSummary",
        "dashboardSecondary",
        "withDeadline",
    ]:
        assert hook in dashboard_source

    intelligence_source = Path("frontend/js/pages/intelligence.js").read_text(encoding="utf-8")
    assert "normalizeEvidencePayload" in intelligence_source


def test_dashboard_prediction_fallbacks_stay_compact_and_projection_width_collapses_without_model_coverage():
    dashboard_source = Path("frontend/js/pages/dashboard.js").read_text(encoding="utf-8")
    renderer_source = Path("frontend/js/modules/dashboard-kline-renderer.js").read_text(encoding="utf-8")

    assert "normalizeDegradedReasons" in dashboard_source
    assert "reason !== 'prediction_mode_unavailable'" in dashboard_source
    assert "const preferredSymbol = [_overview?.symbol, _dashboardState?.symbol, _activeSymbol]" in dashboard_source
    assert "const projectionWidth = state.predictionEnabled ? innerWidth * preset.projectionWidthRatio : 0;" in renderer_source


def test_nav_preserves_multi_group_expansion_and_mobile_defaults():
    nav_source = Path("frontend/js/components/nav.js").read_text(encoding="utf-8")
    assert "defaultGroupState" in nav_source
    assert "const openAllGroups = !isDesktopNavViewport();" in nav_source
    assert "setStoredGroups(openState);" in nav_source


def test_compact_error_and_degraded_patterns_exist():
    error_css = Path("frontend/css/error-ui.css").read_text(encoding="utf-8")
    for selector in [
        ".error-state--compact",
        ".backend-disconnected-banner",
        ".degraded-notice",
    ]:
        assert selector in error_css


def test_app_config_prefers_runtime_origin_over_localhost_hardcode():
    content = Path("frontend/app-config.js").read_text(encoding="utf-8")
    assert "window.__ESG_APP_ORIGIN__" in content
    assert "window.location.origin" in content
    assert "window.__ESG_LANDING_ENTRY__" in content
    assert "http://localhost:8000" not in content


def test_launcher_opens_root_and_verifies_quant_fingerprint():
    content = Path("start.cmd").read_text(encoding="utf-8")
    assert 'set "APP_URL=%API_URL%/"' in content
    assert "app_id -eq 'quant-terminal'" in content
    assert "service_name -eq 'Quant Terminal'" in content
    assert "PORT_CANDIDATES=8012" in content


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
        "frontend/js/pages/rl-lab.js",
    ]
    for relative_path in targets:
        content = Path(relative_path).read_text(encoding="utf-8")
        for fragment in SUSPICIOUS_FRAGMENTS:
            assert fragment not in content, f"{fragment!r} unexpectedly found in {relative_path}"


def test_public_schemas_no_longer_accept_mock_report_inputs():
    content = Path("gateway/api/schemas.py").read_text(encoding="utf-8")
    assert "mock_report" not in content


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
