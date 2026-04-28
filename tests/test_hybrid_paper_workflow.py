from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

import gateway.api.routers.quant as quant_router
import gateway.main as main_module
from gateway.quant.service import QuantSystemService


class _FakeRLService:
    def __init__(self, dataset_path: Path, checkpoint_path: Path | None):
        self.dataset_path = dataset_path
        self.checkpoint_path = checkpoint_path
        self.backtest_calls: list[dict[str, object]] = []

    def overview(self):
        return {
            "latest_dataset": {
                "label": "dataset",
                "path": str(self.dataset_path),
                "exists": self.dataset_path.exists(),
                "status": "ready" if self.dataset_path.exists() else "missing",
            },
            "latest_checkpoint": {
                "label": "checkpoint",
                "path": str(self.checkpoint_path or ""),
                "exists": bool(self.checkpoint_path and self.checkpoint_path.exists()),
                "status": "ready" if self.checkpoint_path and self.checkpoint_path.exists() else "missing",
            },
            "latest_report": {"label": "report", "path": "report.json", "exists": True, "status": "ready"},
            "artifact_health": {
                "dataset_ready": self.dataset_path.exists(),
                "checkpoint_ready": bool(self.checkpoint_path and self.checkpoint_path.exists()),
                "report_ready": True,
            },
        }

    def backtest(self, algorithm, dataset_path, checkpoint_path=None, action_type="continuous", notes=None):
        self.backtest_calls.append(
            {
                "algorithm": algorithm,
                "dataset_path": dataset_path,
                "checkpoint_path": checkpoint_path,
                "action_type": action_type,
                "notes": notes,
            }
        )
        return {
            "run_id": "backtest-rl-1",
            "metrics": {"sharpe": 1.1, "max_drawdown": 0.03},
            "artifacts": {"report_path": "rl-report.json"},
            "config": {"checkpoint_path": checkpoint_path, "dataset_path": dataset_path},
        }


def _build_service(
    monkeypatch,
    tmp_path: Path,
    *,
    checkpoint_ready: bool = True,
    p2_promotable: bool = True,
    synthetic_backtest: bool = False,
    alpaca_ready: bool = True,
    kill_switch: bool = False,
):
    tmp_path.mkdir(parents=True, exist_ok=True)
    service = QuantSystemService()
    service.storage.base_dir = tmp_path
    service.alpha_ranker = SimpleNamespace(status=lambda: {"available": True})
    service.p1_suite = SimpleNamespace(status=lambda: {"available": True})
    service.p2_stack = SimpleNamespace(status=lambda: {"available": True})

    dataset = tmp_path / "rl-dataset.csv"
    dataset.write_text("timestamp,symbol,close\n2026-01-01,AAPL,100\n", encoding="utf-8")
    checkpoint = tmp_path / "model.pt"
    if checkpoint_ready:
        checkpoint.write_bytes(b"checkpoint")
    fake_rl = _FakeRLService(dataset, checkpoint if checkpoint_ready else None)
    monkeypatch.setattr(service, "_build_quant_rl_service", lambda: fake_rl)

    monkeypatch.setattr(
        service,
        "build_p1_stack_report",
        lambda **_kwargs: {
            "report_id": "p1-1",
            "deployment_readiness": {"promotable_to_paper": True, "blockers": []},
            "storage": {"local_path": "p1.json"},
        },
    )
    monkeypatch.setattr(
        service,
        "build_p2_decision_report",
        lambda **_kwargs: {
            "report_id": "p2-1",
            "deployment_readiness": {
                "promotable_to_paper": p2_promotable,
                "blockers": [] if p2_promotable else ["unit p2 blocker"],
            },
            "storage": {"local_path": "p2.json"},
        },
    )
    monkeypatch.setattr(
        service,
        "run_backtest",
        lambda **_kwargs: {
            "backtest_id": "backtest-1",
            "tearsheet_report_id": "tearsheet-backtest-1",
            "used_synthetic_fallback": synthetic_backtest,
            "market_data_warnings": ["synthetic fallback"] if synthetic_backtest else [],
            "data_source": "synthetic" if synthetic_backtest else "unit_real",
            "storage": {"local_path": "backtest.json"},
        },
    )
    monkeypatch.setattr(
        service,
        "build_tearsheet",
        lambda backtest_id, persist=True: {
            "report_id": f"tearsheet-{backtest_id}",
            "protection_status": "review" if synthetic_backtest else "pass",
            "storage": {"local_path": "tearsheet.json"},
        },
    )
    monkeypatch.setattr(
        service,
        "build_paper_gate_report",
        lambda persist=False: {
            "report_id": "paper-gate-1",
            "status": "passed",
            "passed": True,
            "blockers": [],
            "storage": {"local_path": "paper-gate.json"},
        },
    )
    monkeypatch.setattr(service, "get_execution_controls", lambda: {"kill_switch_enabled": kill_switch})
    monkeypatch.setattr(
        service,
        "get_execution_account",
        lambda **_kwargs: {
            "connected": alpaca_ready,
            "paper_ready": alpaca_ready,
            "warnings": [] if alpaca_ready else ["paper credentials missing"],
            "next_actions": [] if alpaca_ready else ["configure_paper_credentials"],
        },
    )

    execution_calls: list[dict[str, object]] = []

    def _create_execution_plan(**kwargs):
        execution_calls.append(kwargs)
        return {
            "execution_id": "execution-1",
            "ready": True,
            "submitted": bool(kwargs.get("submit_orders")),
            "broker_status": "submitted" if kwargs.get("submit_orders") else "planned",
            "submitted_orders": [
                {
                    "symbol": "AAPL",
                    "side": "buy",
                    "status": "accepted",
                    "notional": "1.00",
                    "client_order_id": "client-aapl",
                    "broker_order_id": "ord-aapl",
                }
            ]
            if kwargs.get("submit_orders")
            else [],
            "orders": [{"symbol": "AAPL", "side": "buy", "status": "planned", "notional": "1.00"}],
            "warnings": [],
            "next_actions": [],
        }

    monkeypatch.setattr(service, "create_execution_plan", _create_execution_plan)
    return service, fake_rl, execution_calls


def test_hybrid_paper_workflow_happy_path_submits_and_persists(monkeypatch, tmp_path):
    service, fake_rl, execution_calls = _build_service(monkeypatch, tmp_path)

    payload = service.run_hybrid_paper_strategy_workflow(universe_symbols=["AAPL"], submit_orders=True)

    assert payload["status"] == "submitted"
    assert payload["submitted_count"] == 1
    assert payload["execution_id"] == "execution-1"
    assert payload["rl_backtest_run_id"] == "backtest-rl-1"
    assert execution_calls[0]["submit_orders"] is True
    assert execution_calls[0]["mode"] == "paper"
    assert execution_calls[0]["max_orders"] == 2
    assert execution_calls[0]["per_order_notional"] == 1.0
    assert fake_rl.backtest_calls[0]["algorithm"] == "sac"
    assert fake_rl.backtest_calls[0]["action_type"] == "continuous"

    persisted = service.get_hybrid_paper_strategy_workflow(payload["workflow_id"])
    assert persisted is not None
    assert persisted["workflow_id"] == payload["workflow_id"]
    assert persisted["status"] == "submitted"


def test_hybrid_paper_workflow_can_plan_without_submission(monkeypatch, tmp_path):
    service, _fake_rl, execution_calls = _build_service(monkeypatch, tmp_path)

    payload = service.run_hybrid_paper_strategy_workflow(submit_orders=False)

    assert payload["status"] == "planned"
    assert payload["submitted_count"] == 0
    assert execution_calls[0]["submit_orders"] is False


def test_hybrid_paper_workflow_blockers_do_not_submit(monkeypatch, tmp_path):
    cases = [
        {"checkpoint_ready": False, "expected": "RL checkpoint artifact is not available."},
        {"p2_promotable": False, "expected": "P2 decision stack is not promotable to paper."},
        {"synthetic_backtest": True, "expected": "Backtest used synthetic market data fallback."},
        {"alpaca_ready": False, "expected": "Alpaca paper account is not ready."},
        {"kill_switch": True, "expected": "Execution kill switch is enabled."},
    ]

    for index, case in enumerate(cases):
        expected = case.pop("expected")
        service, _fake_rl, execution_calls = _build_service(monkeypatch, tmp_path / f"case-{index}", **case)

        payload = service.run_hybrid_paper_strategy_workflow(submit_orders=True)

        assert payload["status"] == "blocked"
        assert expected in payload["blockers"]
        assert execution_calls == []


def test_hybrid_paper_workflow_api_contract(monkeypatch):
    class _FakeWorkflowService:
        def __init__(self):
            self.saved = {
                "workflow_id": "workflow-api-1",
                "status": "blocked",
                "blockers": ["unit blocker"],
                "warnings": [],
                "model_status": {},
                "artifacts": {},
                "submitted_count": 0,
            }
            self.kwargs = None

        def run_hybrid_paper_strategy_workflow(self, **kwargs):
            self.kwargs = kwargs
            return self.saved

        def get_hybrid_paper_strategy_workflow(self, workflow_id):
            return self.saved if workflow_id == "workflow-api-1" else None

    fake = _FakeWorkflowService()
    monkeypatch.setattr(quant_router, "_quant_service", lambda: fake)
    client = TestClient(main_module.app)

    response = client.post("/api/v1/quant/workflows/paper-strategy/run", json={})

    assert response.status_code == 200
    payload = response.json()
    assert payload["workflow_id"] == "workflow-api-1"
    assert fake.kwargs["benchmark"] == "SPY"
    assert fake.kwargs["capital_base"] == 1_000_000
    assert fake.kwargs["strategy_mode"] == "hybrid_p1_p2_rl"
    assert fake.kwargs["rl_algorithm"] == "sac"
    assert fake.kwargs["submit_orders"] is True
    assert fake.kwargs["mode"] == "paper"
    assert fake.kwargs["broker"] == "alpaca"
    assert fake.kwargs["max_orders"] == 2
    assert fake.kwargs["per_order_notional"] == 1.0
    assert fake.kwargs["allow_synthetic_execution"] is False
    assert fake.kwargs["force_refresh"] is False

    loaded = client.get("/api/v1/quant/workflows/paper-strategy/workflow-api-1")
    assert loaded.status_code == 200
    assert loaded.json()["workflow_id"] == "workflow-api-1"

    missing = client.get("/api/v1/quant/workflows/paper-strategy/missing")
    assert missing.status_code == 404


def test_hybrid_workflow_frontend_contract():
    api_source = Path("frontend/js/qtapi.js").read_text(encoding="utf-8")
    rl_source = Path("frontend/js/pages/rl-lab.js").read_text(encoding="utf-8")
    execution_source = Path("frontend/js/pages/execution.js").read_text(encoding="utf-8")

    assert "/workflows/paper-strategy/run" in api_source
    assert "/workflows/paper-strategy/" in api_source
    assert "#rl-run-hybrid-workflow" in rl_source
    assert "Run Hybrid Paper Workflow" in rl_source
    assert "submitted_count" in rl_source
    assert "qt.workflow.latest" in execution_source
    assert "#btn-open-workflow-execution" in execution_source
