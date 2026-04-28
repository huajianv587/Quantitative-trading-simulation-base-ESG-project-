from __future__ import annotations

import ast
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import gateway.main as main_module
from scripts import release_boundary_report
from gateway.api.factory import create_app
from gateway.api.routers import auth
from gateway.auth.repository import reset_auth_repository
from gateway.config import settings
from gateway.ops.security import auth_coverage_for_app
from gateway.quant.models import ResearchSignal
from gateway.quant.storage import QuantStorageGateway
from analysis.factors.multi_factor_scoring import analyze_payload


def _compact_source(source: str) -> str:
    return "".join(source.split())


def _assert_storage_call(source: str, function_name: str, storage_name: str, key_name: str) -> None:
    compact = _compact_source(source)
    assert f"{function_name}({storage_name},{key_name}" in compact


def _assert_no_raw_storage_get_set(source: str, key_name: str) -> None:
    compact = _compact_source(source)
    for storage_name in ("localStorage", "sessionStorage", "window.localStorage", "window.sessionStorage"):
        for function_name in ("getItem", "setItem"):
            assert f"{storage_name}.{function_name}({key_name}" not in compact


def _quant_service_duplicate_methods() -> dict[str, list[int]]:
    module = ast.parse(Path("gateway/quant/service.py").read_text(encoding="utf-8"))
    service_class = next(
        node
        for node in module.body
        if isinstance(node, ast.ClassDef) and node.name == "QuantSystemService"
    )
    methods: dict[str, list[int]] = {}
    for node in service_class.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            methods.setdefault(node.name, []).append(node.lineno)
    return {name: lines for name, lines in methods.items() if len(lines) > 1}


def _quant_service_method_line_count(method_name: str) -> int:
    module = ast.parse(Path("gateway/quant/service.py").read_text(encoding="utf-8"))
    service_class = next(
        node
        for node in module.body
        if isinstance(node, ast.ClassDef) and node.name == "QuantSystemService"
    )
    method = next(
        node
        for node in service_class.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == method_name
    )
    return int((method.end_lineno or method.lineno) - method.lineno + 1)


def test_quant_service_does_not_define_shadowed_duplicate_methods():
    duplicates = _quant_service_duplicate_methods()

    assert duplicates == {}


def test_quant_execution_pipeline_hotspots_do_not_expand():
    budgets = {
        "create_execution_plan": 205,
        "_build_portfolio": 20,
        "_submit_broker_orders": 30,
    }

    over_budget = {
        name: {"actual": _quant_service_method_line_count(name), "budget": budget}
        for name, budget in budgets.items()
        if _quant_service_method_line_count(name) > budget
    }

    assert over_budget == {}


def test_production_fallback_handlers_are_observable():
    target_paths = [
        Path("gateway/quant/service.py"),
        Path("gateway/trading/service.py"),
        Path("scripts/quant_signal_scheduler.py"),
        Path("gateway/scheduler/notifier.py"),
    ]
    violations: list[str] = []
    for path in target_paths:
        module = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(module):
            if not isinstance(node, ast.ExceptHandler):
                continue
            is_broad = node.type is None or (isinstance(node.type, ast.Name) and node.type.id == "Exception")
            if is_broad and any(isinstance(statement, ast.Pass) for statement in node.body):
                violations.append(f"{path.as_posix()}:{node.lineno}")

    quant_source = Path("gateway/quant/service.py").read_text(encoding="utf-8")
    trading_source = Path("gateway/trading/service.py").read_text(encoding="utf-8")
    scheduler_source = Path("scripts/quant_signal_scheduler.py").read_text(encoding="utf-8")
    notifier_source = Path("gateway/scheduler/notifier.py").read_text(encoding="utf-8")

    assert violations == []
    assert "registry_load_error" in quant_source
    assert "load_error" in quant_source
    assert "dashboard_state_unavailable" in trading_source
    assert "service_calendar_error" in scheduler_source
    assert "[Scheduler] event audit write failed" in scheduler_source
    assert "[Notifier]" in notifier_source and "logger.error" in notifier_source


def test_quant_service_exposes_component_boundaries():
    service = main_module.runtime.quant_system

    assert service.components.execution.owner is service
    assert service.components.portfolio.owner is service
    assert service.components.market_data.owner is service
    assert service.components.dashboard.owner is service
    assert service.components.paper_workflow.owner is service
    assert callable(service.components.execution.build_orders)
    assert callable(service.components.execution.build_broker_order_payload)
    assert callable(service.components.execution.plan_order_limits)
    assert callable(service.components.execution.submit_broker_orders)


def test_quant_execution_submit_facade_remains_monkeypatchable():
    source = Path("gateway/quant/service.py").read_text(encoding="utf-8")
    assert "self._submit_broker_orders(" in source
    assert "self.components.execution.submit_broker_orders(" in source


def test_quant_portfolio_component_matches_service_facade():
    service = main_module.runtime.quant_system
    signals = [
        ResearchSignal(
            symbol="AAPL",
            company_name="Apple",
            sector="Technology",
            thesis="Quality compounder",
            action="long",
            confidence=0.82,
            expected_return=0.04,
            risk_score=35,
            overall_score=76,
            e_score=75,
            s_score=74,
            g_score=77,
            decision_score=0.78,
        ),
        ResearchSignal(
            symbol="MSFT",
            company_name="Microsoft",
            sector="Technology",
            thesis="Durable cash flow",
            action="long",
            confidence=0.79,
            expected_return=0.035,
            risk_score=38,
            overall_score=73,
            e_score=72,
            s_score=71,
            g_score=75,
            decision_score=0.74,
        ),
    ]

    facade = service._build_portfolio(signals, 1_000_000, "SPY")
    component = service.components.portfolio.build(signals, 1_000_000, "SPY")

    assert facade.model_dump() == component.model_dump()


def test_blueprint_outputs_are_marked_as_compatibility_adapters():
    result = analyze_payload({"records": [{"symbol": "AAPL", "score": 80}]})

    assert result["adapter_kind"] == "compatibility_adapter"
    assert result["production_ready"] is False
    assert result["implementation_source"] == "blueprint_runtime"


def test_api_auth_alias_matches_primary_auth_status():
    client = TestClient(main_module.app)

    primary = client.get("/auth/status")
    alias = client.get("/api/auth/status")

    assert primary.status_code == 200
    assert alias.status_code == 200
    assert alias.json()["primary_backend"] == primary.json()["primary_backend"]


def test_frontend_auth_contract_and_scoped_key_injection_are_aligned():
    client_source = Path("frontend/js/qtapi.js").read_text(encoding="utf-8")

    assert "/api/auth/register" in client_source
    assert "/api/auth/login" in client_source
    assert "function _scopeForRequest" in client_source
    assert "if (!scope || scope === 'public') return '';" in client_source
    assert "__ESG_RESEARCH_API_KEY__" in client_source
    assert "__ESG_TRADING_API_KEY__" in client_source


def test_frontend_cache_records_are_schema_versioned():
    utils_source = Path("frontend/js/utils.js").read_text(encoding="utf-8")
    dashboard_source = Path("frontend/js/pages/dashboard.js").read_text(encoding="utf-8")
    trading_ops_source = Path("frontend/js/pages/trading-ops.js").read_text(encoding="utf-8")
    workbench_source = Path("frontend/js/pages/workbench-utils.js").read_text(encoding="utf-8")
    execution_source = Path("frontend/js/pages/execution.js").read_text(encoding="utf-8")
    rl_source = Path("frontend/js/pages/rl-lab.js").read_text(encoding="utf-8")
    portfolio_source = Path("frontend/js/pages/portfolio.js").read_text(encoding="utf-8")
    portfolio_lab_source = Path("frontend/js/pages/portfolio-lab.js").read_text(encoding="utf-8")
    research_source = Path("frontend/js/pages/research.js").read_text(encoding="utf-8")

    assert "DASHBOARD_CACHE_SCHEMA_VERSION" in dashboard_source
    assert "OPS_SNAPSHOT_CACHE_SCHEMA_VERSION" in trading_ops_source
    assert "schema_version" in workbench_source
    assert "parsed.schema_version !== expectedSchemaVersion" in workbench_source
    assert "export function setVersionedStorageValue" in utils_source
    assert "export function getVersionedStorageValue" in utils_source
    assert "storage.removeItem(key)" in utils_source

    assert "WORKFLOW_LATEST_STORAGE_KEY" in execution_source
    assert "WORKFLOW_LATEST_SCHEMA_VERSION" in execution_source
    _assert_storage_call(execution_source, "getVersionedStorageValue", "window.localStorage", "WORKFLOW_LATEST_STORAGE_KEY")
    _assert_storage_call(execution_source, "setVersionedStorageValue", "window.localStorage", "WORKFLOW_LATEST_STORAGE_KEY")
    _assert_no_raw_storage_get_set(execution_source, "WORKFLOW_LATEST_STORAGE_KEY")
    assert "WORKFLOW_LATEST_STORAGE_KEY" in rl_source
    _assert_storage_call(rl_source, "setVersionedStorageValue", "window.localStorage", "WORKFLOW_LATEST_STORAGE_KEY")
    _assert_no_raw_storage_get_set(rl_source, "WORKFLOW_LATEST_STORAGE_KEY")

    assert "EXECUTION_PREFILL_STORAGE_KEY" in portfolio_source
    assert "EXECUTION_PREFILL_SCHEMA_VERSION" in portfolio_source
    assert "PORTFOLIO_PREFILL_STORAGE_KEY" in portfolio_source
    assert "PORTFOLIO_PREFILL_SCHEMA_VERSION" in portfolio_source
    _assert_storage_call(portfolio_source, "getVersionedStorageValue", "window.sessionStorage", "PORTFOLIO_PREFILL_STORAGE_KEY")
    _assert_storage_call(portfolio_source, "setVersionedStorageValue", "window.sessionStorage", "EXECUTION_PREFILL_STORAGE_KEY")
    _assert_no_raw_storage_get_set(portfolio_source, "PORTFOLIO_PREFILL_STORAGE_KEY")
    _assert_no_raw_storage_get_set(portfolio_source, "EXECUTION_PREFILL_STORAGE_KEY")

    assert "EXECUTION_PREFILL_STORAGE_KEY" in portfolio_lab_source
    _assert_storage_call(portfolio_lab_source, "setVersionedStorageValue", "window.sessionStorage", "EXECUTION_PREFILL_STORAGE_KEY")
    _assert_no_raw_storage_get_set(portfolio_lab_source, "EXECUTION_PREFILL_STORAGE_KEY")

    assert "PORTFOLIO_PREFILL_STORAGE_KEY" in research_source
    _assert_storage_call(research_source, "setVersionedStorageValue", "window.sessionStorage", "PORTFOLIO_PREFILL_STORAGE_KEY")
    _assert_no_raw_storage_get_set(research_source, "PORTFOLIO_PREFILL_STORAGE_KEY")

    assert "EXECUTION_PREFILL_STORAGE_KEY" in dashboard_source
    _assert_storage_call(dashboard_source, "setVersionedStorageValue", "window.sessionStorage", "EXECUTION_PREFILL_STORAGE_KEY")
    _assert_no_raw_storage_get_set(dashboard_source, "EXECUTION_PREFILL_STORAGE_KEY")


def test_large_artifact_governance_patterns_are_configured():
    dockerignore = Path(".dockerignore").read_text(encoding="utf-8")
    gitignore = Path(".gitignore").read_text(encoding="utf-8")

    assert ".env" in gitignore
    assert ".env.*" in gitignore
    for pattern in [
        "model-serving/checkpoint/",
        "delivery/",
        "outputs_*/",
        "paper_exports/",
        "checkpoint_fromntu/",
        "deploy/tc2/",
        "config/paper5_*_stock_universe.csv",
        "scripts/build_paper5_*.py",
        "scripts/export_sci_paper_data*.py",
    ]:
        assert pattern in dockerignore or pattern in gitignore
    assert "data/raw_big_doc_data" in dockerignore
    assert ".env.example" in gitignore


def test_release_boundary_classifies_excluded_research_artifacts():
    expected = {
        "checkpoint_fromntu/": "checkpoint_fromntu",
        "deploy/tc2/README.md": "tc2_research_deploy",
        "config/paper5_200_stock_universe.csv": "paper5_universe_exports",
        "scripts/build_paper5_publication_package.py": "paper5_offline_scripts",
        "scripts/export_sci_paper_data_v2.py": "paper5_offline_scripts",
        "scripts/paper_cloud_acceptance.py": "paper5_offline_scripts",
    }

    for path, category in expected.items():
        assert release_boundary_report.classify_excluded_research_artifact(path) == category

    assert "excluded_research_artifacts" in release_boundary_report.build_report(None)


def test_mutating_routes_are_scoped_except_public_auth():
    coverage = auth_coverage_for_app(main_module.app)

    assert coverage["mutating_routes_total"] > 0
    assert coverage["unscoped_mutating_count"] == 0
    assert coverage["mutating_routes_scoped"] == coverage["mutating_routes_total"]


def test_remote_mutating_route_requires_key_but_local_dev_still_reaches_validation(monkeypatch):
    monkeypatch.setattr(settings, "OPS_API_KEY", "ops-test-key")
    monkeypatch.setattr(settings, "AUTH_DEFAULT_REQUIRED", True)
    monkeypatch.setattr(settings, "AUTH_ALLOW_LOCALHOST_DEV", True)
    path = "/api/v1/trading/watchlist/add"

    remote = TestClient(main_module.app, base_url="https://remote.example")
    blocked = remote.post(path, json={})
    authorized = remote.post(path, headers={"x-api-key": "ops-test-key"}, json={})

    local = TestClient(main_module.app)
    local_response = local.post(path, json={})

    assert blocked.status_code == 401
    assert authorized.status_code != 401
    assert local_response.status_code != 401


def test_reset_dev_token_is_local_only(monkeypatch):
    reset_auth_repository()
    monkeypatch.setattr(settings, "APP_MODE", "local")
    local = TestClient(main_module.app)
    remote = TestClient(main_module.app, base_url="https://remote.example")
    email = "reset-local-only@example.com"

    register = local.post("/auth/register", json={"email": email, "password": "Start123!", "name": "Reset User"})
    assert register.status_code in {200, 409}

    local_reset = local.post("/auth/reset-password/request", json={"email": email})
    remote_reset = remote.post("/auth/reset-password/request", json={"email": email})

    assert local_reset.status_code == 200
    assert local_reset.json().get("_dev_token")
    assert remote_reset.status_code == 200
    assert "_dev_token" not in remote_reset.json()


def test_prod_auth_secret_is_required(monkeypatch):
    monkeypatch.setattr(settings, "APP_MODE", "prod")
    monkeypatch.setattr(settings, "AUTH_SECRET_KEY", "")

    with pytest.raises(RuntimeError, match="AUTH_SECRET_KEY"):
        auth.validate_auth_runtime_config()


def test_gateway_import_does_not_eager_load_heavy_runtime_stack():
    forbidden = (
        "llama_index",
        "sentence_transformers",
        "gateway.rag.rag_main",
        "gateway.rag.embeddings",
        "torch",
        "transformers",
    )
    code = (
        "import sys; import gateway.main; "
        f"forbidden={forbidden!r}; "
        "print('\\n'.join(str(any(name == prefix or name.startswith(prefix + '.') for name in sys.modules)) for prefix in forbidden))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=".",
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )

    lines = [line.strip() for line in result.stdout.splitlines() if line.strip() in {"True", "False"}]
    assert lines[-len(forbidden):] == ["False"] * len(forbidden)


def test_repo_hygiene_release_boundary_excludes_generated_artifacts():
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=".",
        capture_output=True,
        timeout=30,
        check=True,
    )
    raw_paths = result.stdout.decode("utf-8", errors="replace")
    tracked_paths = [path.replace("\\", "/") for path in raw_paths.split("\0") if path]
    forbidden_exact = {".env"}
    forbidden_prefixes = (
        "__pycache__/",
        "delivery/",
        "paper_exports/",
        "outputs_",
        "storage/",
    )

    violations = [
        path
        for path in tracked_paths
        if path in forbidden_exact
        or path.endswith((".pyc", ".pyo"))
        or "/__pycache__/" in f"/{path}"
        or any(path.startswith(prefix) for prefix in forbidden_prefixes)
    ]

    ci_source = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert violations == []
    assert "scripts/release_boundary_report.py --strict-artifacts" in ci_source


def test_frontend_static_consistency_gate_passes_for_current_bundle():
    result = subprocess.run(
        [sys.executable, "scripts/check_frontend_static_consistency.py"],
        cwd=".",
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )

    assert '"ok": true' in result.stdout
    assert '"failures": []' in result.stdout


def test_ops_runtime_snapshot_is_read_only_for_optional_services(monkeypatch):
    def _fail_optional_start(*args, **kwargs):
        raise AssertionError("/ops/runtime must not initialize optional services")

    monkeypatch.setattr(main_module.runtime, "ensure_optional_services", _fail_optional_start)
    client = TestClient(main_module.app)
    response = client.get("/ops/runtime")

    assert response.status_code == 200
    assert "lazy_components" in response.json()["startup"]


def test_lifespan_startup_shutdown_is_repeatable_without_duplicate_runtime_state():
    class FakeRuntime:
        app_mode = "test"
        lazy_components: dict[str, str] = {}

        def __init__(self):
            self.startups = 0
            self.shutdowns = 0

        async def startup(self, app):
            self.startups += 1
            app.state.fake_runtime_started = self.startups

        async def shutdown(self, app):
            self.shutdowns += 1

    fake_runtime = FakeRuntime()
    app = create_app(fake_runtime)

    for _ in range(2):
        with TestClient(app) as client:
            assert client.get("/health").status_code == 200

    assert fake_runtime.startups == 2
    assert fake_runtime.shutdowns == 2


def test_quant_storage_concurrent_writes_are_atomic(tmp_path):
    gateway = QuantStorageGateway()
    gateway.base_dir = tmp_path

    def write_record(index: int):
        payload = {"generated_at": f"2026-04-28T00:00:{index:02d}Z", "index": index}
        gateway.persist_record("executions", f"execution-{index}", payload)
        gateway.append_audit_event(category="test", action="write", payload=payload)

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(write_record, range(24)))

    rows = gateway.list_records("executions")
    audit_files = list((tmp_path / "audit").glob("audit-*.jsonl"))
    tmp_files = list(tmp_path.rglob("*.tmp"))

    assert len(rows) == 24
    assert not tmp_files
    assert audit_files
    assert sum(1 for _ in audit_files[0].open(encoding="utf-8")) == 24


def test_quant_storage_atomic_write_failure_preserves_old_json_and_removes_tmp(tmp_path, monkeypatch):
    gateway = QuantStorageGateway()
    gateway.base_dir = tmp_path
    record_type = "executions"
    record_id = "execution-atomic"
    old_payload = {"generated_at": "2026-04-28T00:00:00Z", "value": "old"}
    new_payload = {"generated_at": "2026-04-28T00:00:01Z", "value": "new"}

    gateway.persist_record(record_type, record_id, old_payload)
    original_replace = Path.replace

    def _fail_replace(self, target):
        if self.name.startswith(f".{record_id}.json."):
            raise OSError("simulated replace failure")
        return original_replace(self, target)

    monkeypatch.setattr(Path, "replace", _fail_replace)

    with pytest.raises(OSError, match="simulated replace failure"):
        gateway.persist_record(record_type, record_id, new_payload)

    assert gateway.load_record(record_type, record_id)["value"] == "old"
    assert not list((tmp_path / record_type).glob("*.tmp"))
