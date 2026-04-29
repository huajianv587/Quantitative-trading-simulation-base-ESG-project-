from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient

import gateway.api.routers.quant as quant_router
import gateway.main as main_module
from scripts.paper_90_session_replay import run_replay
from scripts.paper_chaos_drill import run_drill
from scripts.paper_precloud_local_acceptance import run_local_three_gate
from scripts.restore_quant_backup import run_restore
from gateway.config import settings
from gateway.quant.service import QuantSystemService


class _FakeMarketData:
    def get_daily_bars(self, symbol, **_kwargs):
        anchor = datetime(2026, 1, 2, tzinfo=timezone.utc)
        return [
            {"timestamp": (anchor + timedelta(days=index)).isoformat(), "close": 100.0 + index}
            for index in range(8)
        ]


def _service(tmp_path):
    service = QuantSystemService()
    service.storage.base_dir = tmp_path
    service.market_data = _FakeMarketData()
    return service


def test_paper_performance_report_can_recommend_operator_reviewed_canary(monkeypatch, tmp_path):
    service = _service(tmp_path)
    monkeypatch.setattr(service, "get_execution_account", lambda **_kwargs: {"connected": True, "paper_ready": True, "account": {"equity": 106.0, "cash": 50.0}})
    monkeypatch.setattr(service, "get_execution_controls", lambda: {"kill_switch_enabled": False})
    monkeypatch.setattr(service, "_paper_gate_sync_status", lambda: {"ok": True, "checked_executions": 1, "error_count": 0})

    start = datetime(2026, 1, 2, tzinfo=timezone.utc)
    for index in range(65):
        payload = {
            "snapshot_id": (start + timedelta(days=index)).date().isoformat(),
            "date": (start + timedelta(days=index)).date().isoformat(),
            "generated_at": (start + timedelta(days=index)).isoformat(),
            "portfolio_nav": 100_000 + index * 120,
            "equity": 100_000 + index * 120,
            "benchmark_nav": 100 + index * 0.01,
            "benchmark": "SPY",
            "mode": "paper",
        }
        service.storage.persist_record("paper_performance", payload["snapshot_id"], payload)

    report = service.build_paper_performance_report(window_days=90)

    assert report["metrics"]["valid_days"] == 65
    assert report["metrics"]["net_return"] > 0
    assert report["metrics"]["excess_return"] > 0
    assert report["live_canary_recommendation"]["recommended"] is True


def test_paper_outcome_settlement_updates_n1_n3_n5_and_score(tmp_path):
    service = _service(tmp_path)
    outcome = service._build_paper_outcome_record(
        record_kind="order",
        source_id="client-aapl",
        index=0,
        workflow_id="workflow-test",
        execution_id="execution-test",
        symbol="AAPL",
        action="long",
        entry_at="2026-01-02T14:30:00+00:00",
        entry_price=100.0,
        notional=1.0,
        features={"estimated_slippage_bps": 1, "estimated_impact_bps": 1, "overall_score": 70},
        model_refs={"p2_report_id": "p2-test"},
        market_data_source="alpaca",
        synthetic_used=False,
    )
    service._save_paper_outcome(outcome)

    result = service.settle_paper_outcomes(limit=10)
    saved = service.storage.load_record("paper_outcomes", outcome["outcome_id"])

    assert result["updated_count"] == 1
    assert saved["settlements"]["n1"]["status"] == "settled"
    assert saved["settlements"]["n3"]["status"] == "settled"
    assert saved["settlements"]["n5"]["status"] == "settled"
    assert saved["status"] == "settled"
    assert saved["score"] is not None


def test_deployment_preflight_blocks_missing_cloud_readiness(monkeypatch, tmp_path):
    service = _service(tmp_path)
    monkeypatch.setattr(settings, "ALERT_NOTIFIER", "telegram", raising=False)
    monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", "", raising=False)
    monkeypatch.setattr(settings, "TELEGRAM_CHAT_ID", "", raising=False)
    monkeypatch.setattr(service, "get_execution_account", lambda **_kwargs: {"connected": False, "paper_ready": False})
    monkeypatch.setattr(service, "_market_data_preflight", lambda: {"ok": False, "detail": "market unavailable"})
    monkeypatch.setattr(service, "_storage_preflight", lambda: {"ok": True, "detail": "storage ok"})
    monkeypatch.setattr(service, "_scheduler_heartbeat_status", lambda: {"exists": False, "stale": True})
    monkeypatch.setattr(service, "build_model_registry", lambda: {"models": []})
    monkeypatch.setattr(service, "_rl_checkpoint_preflight", lambda: {"ok": False, "detail": "missing checkpoint"})
    monkeypatch.setattr(service, "get_execution_controls", lambda: {"kill_switch_enabled": True})
    monkeypatch.setattr(service, "_synthetic_trade_preflight", lambda: {"ok": False, "detail": "synthetic present"})

    report = service.build_deployment_preflight(profile="paper_cloud")

    assert report["ready"] is False
    assert "alpaca_paper" in report["blockers"]
    assert "market_data" in report["blockers"]
    assert "scheduler_heartbeat" in report["blockers"]
    assert "rl_checkpoint" in report["blockers"]
    assert "kill_switch" in report["blockers"]
    assert "synthetic_trade_block" in report["blockers"]
    assert "telegram_notifier" in report["blockers"]


def test_deployment_preflight_evaluate_persists_cached_readiness(monkeypatch, tmp_path):
    service = _service(tmp_path)
    monkeypatch.setattr(service, "build_deployment_preflight", lambda **_kwargs: {"ready": True, "profile": "paper_cloud", "blockers": [], "warnings": [], "generated_at": datetime.now(timezone.utc).isoformat()})
    monkeypatch.setattr(service, "_scheduler_heartbeat_status", lambda: {"exists": True, "stale": False, "last_seen": datetime.now(timezone.utc).isoformat()})

    evaluated = service.evaluate_deployment_preflight(profile="paper_cloud")
    cached = service.get_cached_deployment_preflight(profile="paper_cloud")
    ready = service.build_cached_readiness()

    assert evaluated["ready"] is True
    assert cached["ready"] is True
    assert ready["components"]["deployment_preflight"]["ok"] is True


def test_paper_performance_backfill_records_alpaca_orders(monkeypatch, tmp_path):
    service = _service(tmp_path)
    order_day = "2026-01-02"
    monkeypatch.setattr(service.trading_calendar, "is_session", lambda _day: True)
    monkeypatch.setattr(service.trading_calendar, "status", lambda: {"is_session": True, "session_date": order_day})
    monkeypatch.setattr(service.trading_calendar, "session_info", lambda day: SimpleNamespace(model_dump=lambda: {"session_date": str(day), "calendar_id": "XNYS"}))
    monkeypatch.setattr(service, "get_execution_account", lambda **_kwargs: {"connected": True, "paper_ready": True, "account": {"equity": 100000.0, "cash": 50000.0, "buying_power": 100000.0}})
    monkeypatch.setattr(service.alpaca, "list_orders", lambda **_kwargs: [{"id": "bo-1", "symbol": "AAPL", "side": "buy", "status": "filled", "filled_avg_price": "100", "notional": "10", "filled_at": f"{order_day}T15:00:00+00:00"}])
    monkeypatch.setattr(service.alpaca, "list_positions", lambda: [{"symbol": "AAPL"}])
    monkeypatch.setattr(
        service.alpaca,
        "list_account_activities",
        lambda **_kwargs: [
            {"activity_type": "FILL", "symbol": "AAPL", "transaction_time": f"{order_day}T15:00:00+00:00"},
            {"activity_type": "CSD", "id": "cash-1", "net_amount": "1000", "date": order_day},
        ],
    )

    result = service.backfill_paper_performance(days=120)

    assert result["backfilled_snapshots"] >= 1
    assert result["backfilled_outcomes"] == 1
    assert service.storage.load_record("paper_performance", order_day)["evidence_source"] == "alpaca_paper_backfill"
    assert service.storage.list_records("paper_cash_flows")


def test_cash_flow_adjusted_performance_uses_alpaca_activities(tmp_path):
    service = _service(tmp_path)
    service.storage.persist_record("paper_performance", "2026-01-02", {"date": "2026-01-02", "portfolio_nav": 100000, "benchmark_nav": 100})
    service.storage.persist_record("paper_performance", "2026-01-05", {"date": "2026-01-05", "portfolio_nav": 102000, "benchmark_nav": 101})
    service.storage.persist_record("paper_cash_flows", "cash-flow-deposit", {"session_date": "2026-01-05", "amount": 1000, "synthetic_used": False})

    report = service.build_paper_performance_report(window_days=30)

    assert report["cash_flows"]["net_cash_flow"] == 1000
    assert report["cash_flow_adjusted_return"] == 0.01


def test_session_evidence_records_complete_stage_shape(tmp_path):
    service = _service(tmp_path)

    evidence = service.record_session_evidence_stage(
        session_date="2026-01-02",
        stage="hybrid_workflow",
        status="submitted",
        payload={
            "session_date": "2026-01-02",
            "workflow_id": "workflow-1",
            "execution_id": "execution-1",
            "submitted_count": 2,
            "duration_seconds": 1.2,
            "warnings": [],
            "blockers": [],
        },
    )

    assert evidence["session_date"] == "2026-01-02"
    assert evidence["stages"]["workflow"]["status"] == "submitted"
    assert evidence["stages"]["paper_submit"]["submitted_count"] == 2
    assert evidence["stages"]["paper_submit"]["blocker_class"] is None


def test_alpaca_reconcile_repairs_submit_lock_and_journal(monkeypatch, tmp_path):
    service = _service(tmp_path)
    session_date = "2026-01-02"
    service.storage.persist_record(
        "submit_locks",
        "2026-01-02-hybrid-aapl-buy",
        {
            "lock_id": "2026-01-02-hybrid-aapl-buy",
            "session_date": session_date,
            "strategy_id": "hybrid",
            "symbol": "AAPL",
            "side": "buy",
            "execution_id": "execution-1",
            "client_order_id": "client-aapl",
            "status": "submit_unknown",
        },
    )
    service.storage.persist_record(
        "execution_journals",
        "execution-1",
        {
            "execution_id": "execution-1",
            "broker_id": "alpaca",
            "mode": "paper",
            "current_state": "ready_to_route",
            "records": [
                {
                    "order_id": "client-aapl",
                    "execution_id": "execution-1",
                    "broker_id": "alpaca",
                    "symbol": "AAPL",
                    "current_state": "validated",
                    "submitted_payload": {"side": "buy"},
                    "last_broker_snapshot": {},
                    "events": [],
                }
            ],
        },
    )
    service.storage.persist_record(
        "executions",
        "execution-1",
        {"execution_id": "execution-1", "mode": "paper", "session_date": session_date, "orders": [{"symbol": "AAPL", "client_order_id": "client-aapl"}]},
    )
    monkeypatch.setattr(service.alpaca, "connection_status", lambda mode=None: {"configured": True, "broker": "alpaca", "mode": "paper", "paper_configured": True})
    monkeypatch.setattr(service.alpaca, "list_orders", lambda **_kwargs: [{"id": "ord-aapl", "client_order_id": "client-aapl", "symbol": "AAPL", "side": "buy", "status": "filled", "filled_qty": "1", "filled_avg_price": "100"}])
    monkeypatch.setattr(service.alpaca, "list_positions", lambda: [{"symbol": "AAPL"}])
    monkeypatch.setattr(service.alpaca, "get_account", lambda: {"equity": "100000", "cash": "100000", "buying_power": "100000"})

    result = service.reconcile_alpaca_paper_orders(session_date=session_date)

    assert result["journal_updates"] == 1
    assert result["submit_lock_updates"] == 1
    assert service.storage.load_record("submit_locks", "2026-01-02-hybrid-aapl-buy")["broker_order_id"] == "ord-aapl"


def test_alpaca_reconcile_keeps_unmatched_submit_unknown_and_alerts(monkeypatch, tmp_path):
    service = _service(tmp_path)
    session_date = "2026-01-02"
    service.storage.persist_record(
        "submit_locks",
        "2026-01-02-hybrid-aapl-buy",
        {
            "lock_id": "2026-01-02-hybrid-aapl-buy",
            "session_date": session_date,
            "strategy_id": "hybrid",
            "symbol": "AAPL",
            "side": "buy",
            "execution_id": "execution-1",
            "client_order_id": "client-aapl",
            "status": "submit_unknown",
        },
    )
    monkeypatch.setattr(service.alpaca, "connection_status", lambda mode=None: {"configured": True, "broker": "alpaca", "mode": "paper", "paper_configured": True})
    monkeypatch.setattr(service.alpaca, "list_orders", lambda **_kwargs: [])
    monkeypatch.setattr(service.alpaca, "list_positions", lambda: [])
    monkeypatch.setattr(service.alpaca, "get_account", lambda: {"equity": "100000", "cash": "100000", "buying_power": "100000"})

    result = service.reconcile_alpaca_paper_orders(session_date=session_date)

    assert result["unresolved_submit_unknown"] == 1
    assert service.storage.load_record("submit_locks", "2026-01-02-hybrid-aapl-buy")["status"] == "submit_unknown"
    assert service.storage.list_records("alerts")[0]["kind"] == "submit_unknown_unresolved"


def test_alpaca_reconcile_repairs_submit_unknown_from_same_session_fill(monkeypatch, tmp_path):
    service = _service(tmp_path)
    session_date = "2026-01-02"
    service.storage.persist_record(
        "submit_locks",
        "2026-01-02-hybrid-aapl-buy",
        {
            "lock_id": "2026-01-02-hybrid-aapl-buy",
            "session_date": session_date,
            "strategy_id": "hybrid",
            "symbol": "AAPL",
            "side": "buy",
            "execution_id": "execution-1",
            "client_order_id": "missing-client-id",
            "status": "submit_unknown",
        },
    )
    monkeypatch.setattr(service.alpaca, "connection_status", lambda mode=None: {"configured": True, "broker": "alpaca", "mode": "paper", "paper_configured": True})
    monkeypatch.setattr(service.alpaca, "list_orders", lambda **_kwargs: [{"id": "ord-aapl", "client_order_id": "different-client", "symbol": "AAPL", "side": "buy", "status": "filled", "filled_qty": "1", "filled_avg_price": "100", "submitted_at": f"{session_date}T15:00:00+00:00"}])
    monkeypatch.setattr(service.alpaca, "list_positions", lambda: [])
    monkeypatch.setattr(service.alpaca, "get_account", lambda: {"equity": "100000", "cash": "100000", "buying_power": "100000"})

    result = service.reconcile_alpaca_paper_orders(session_date=session_date)
    lock = service.storage.load_record("submit_locks", "2026-01-02-hybrid-aapl-buy")

    assert result["submit_lock_updates"] == 1
    assert lock["status"] == "reconciled"
    assert lock["reconcile_rule"] == "symbol_side_session_fill"


def test_quant_daily_digest_persists_local_ledger_and_delivers(monkeypatch, tmp_path):
    service = _service(tmp_path)
    session_date = "2026-01-02"
    sent_email = []
    sent_telegram = []

    service.storage.persist_record(
        "workflow_runs",
        "workflow-digest",
        {
            "workflow_id": "workflow-digest",
            "session_date": session_date,
            "status": "submitted",
            "execution_id": "execution-digest",
            "submitted_count": 2,
            "order_summary": [{"symbol": "AAPL", "side": "buy", "status": "accepted"}],
            "blockers": [],
        },
    )
    monkeypatch.setattr(service, "get_trading_calendar_status", lambda: {"calendar_id": "XNYS", "session_date": session_date})
    monkeypatch.setattr(service, "build_paper_performance_report", lambda **_kwargs: {"metrics": {"valid_days": 3, "net_return": 0.01}})
    monkeypatch.setattr(service, "build_paper_workflow_observability", lambda **_kwargs: {"summary": {"alert_count": 0}, "alerts": []})
    monkeypatch.setattr(service, "get_cached_deployment_preflight", lambda **_kwargs: {"ready": True})
    monkeypatch.setattr(service, "paper_submit_circuit_breaker_status", lambda: {"enabled": False})
    monkeypatch.setattr(service, "_send_telegram_message", lambda text: sent_telegram.append(text) or {"channel": "telegram", "status": "sent"})

    def fake_email(**kwargs):
        sent_email.append(kwargs)
        return {"ok": True, "detail": "sent"}

    monkeypatch.setattr("gateway.quant.service.send_email_message", fake_email)

    result = service.send_quant_daily_digest(
        phase="postclose",
        session_date=session_date,
        recipients=["jianghuajian99@gmail.com"],
        channels=["telegram", "email"],
    )

    assert result["digest_id"] == f"digest-{session_date}-postclose"
    assert result["delivery"]["sent_count"] == 2
    assert sent_telegram
    assert sent_email[0]["recipient"] == "jianghuajian99@gmail.com"
    assert service.storage.load_record("paper_daily_digests", result["digest_id"])["delivery"]["local_ledger"] is True
    assert service.storage.list_records("paper_daily_digest_deliveries")


def test_quant_daily_digest_failed_delivery_records_retry(monkeypatch, tmp_path):
    service = _service(tmp_path)
    session_date = "2026-01-02"
    monkeypatch.setattr(service, "get_trading_calendar_status", lambda: {"calendar_id": "XNYS", "session_date": session_date})
    monkeypatch.setattr(service, "_send_telegram_message", lambda text: {"channel": "telegram", "status": "failed", "detail": "network"})
    monkeypatch.setattr("gateway.quant.service.send_email_message", lambda **_kwargs: {"ok": False, "detail": "smtp_down"})

    result = service.send_quant_daily_digest(
        phase="postclose",
        session_date=session_date,
        recipients=["jianghuajian99@gmail.com"],
        channels=["telegram", "email"],
    )

    assert result["delivery"]["failed_count"] == 2
    assert result["delivery"]["retry_after"]
    deliveries = service.storage.list_records("paper_daily_digest_deliveries")
    assert {row["status"] for row in deliveries} == {"failed"}
    assert all(row.get("next_retry_at") for row in deliveries)


def test_quant_daily_digest_retry_queue_recovers_failed_delivery(monkeypatch, tmp_path):
    service = _service(tmp_path)
    session_date = "2026-01-02"
    monkeypatch.setattr(service, "get_trading_calendar_status", lambda: {"calendar_id": "XNYS", "session_date": session_date})
    monkeypatch.setattr(service, "_send_telegram_message", lambda text: {"channel": "telegram", "status": "failed", "detail": "network"})

    failed = service.send_quant_daily_digest(
        phase="postclose",
        session_date=session_date,
        channels=["telegram"],
    )
    assert failed["delivery"]["failed_count"] == 1
    delivery = service.storage.list_records("paper_daily_digest_deliveries")[0]
    delivery["next_retry_at"] = "2026-01-01T00:00:00+00:00"
    service.storage.persist_record("paper_daily_digest_deliveries", delivery["delivery_id"], delivery)

    monkeypatch.setattr(service, "_send_telegram_message", lambda text: {"channel": "telegram", "status": "sent"})
    retry = service.retry_failed_daily_digest_deliveries()

    assert retry["sent_count"] == 1
    assert service.storage.list_records("paper_daily_digest_deliveries")[0]["status"] == "sent"


def test_storage_backup_creates_local_archive(tmp_path):
    service = _service(tmp_path)
    service.storage.persist_record("session_evidence", "2026-01-02", {"session_date": "2026-01-02"})
    service.storage.upload_artifact_file = lambda *args, **kwargs: {
        "artifact_backend": "local",
        "artifact_uri": None,
        "uploaded": False,
    }

    result = service.backup_quant_storage(session_date="2026-01-02")

    assert result["status"] in {"completed", "completed_local_only"}
    assert result["size_bytes"] > 0
    assert result["warning"] == "remote_backup_unavailable"


def test_paper_workflow_slo_and_promotion_timeline(tmp_path):
    service = _service(tmp_path)
    service.storage.persist_record(
        "session_evidence",
        "2026-01-02",
        {
            "session_date": "2026-01-02",
            "stages": {name: {"status": "completed"} for name in ["preopen", "workflow", "paper_submit", "broker_sync", "outcomes", "snapshot", "promotion", "digest", "backup"]},
        },
    )
    service.storage.persist_record("workflow_runs", "workflow-1", {"workflow_id": "workflow-1", "status": "submitted"})
    service.storage.persist_record("paper_daily_digest_deliveries", "delivery-1", {"delivery_id": "delivery-1", "status": "sent"})
    service.storage.persist_record("storage_backups", "backup-1", {"backup_id": "backup-1", "status": "completed"})
    service.storage.persist_record("promotion_evidence", "promotion-1", {"evidence_id": "promotion-1", "generated_at": "2026-01-02T00:00:00+00:00", "promotion_status": "paper_candidate"})

    slo = service.build_paper_workflow_slo(window_days=30)
    timeline = service.build_promotion_timeline()

    assert slo["workflow"]["success_rate"] == 1.0
    assert slo["digest"]["success_rate"] == 1.0
    assert timeline["current_status"] == "paper_candidate"


def test_shadow_retrain_stays_shadow_only(tmp_path):
    service = _service(tmp_path)

    result = service.run_shadow_retrain(force=True)

    assert result["shadow_only"] is True
    assert result["metrics"]["paper_checkpoint_replaced"] is False
    assert result["metrics"]["live_release_changed"] is False


def test_weekly_digest_builds_and_retry_queue_scans_weekly_deliveries(tmp_path):
    service = _service(tmp_path)
    service.storage.persist_record("paper_performance", "2026-01-02", {"date": "2026-01-02", "portfolio_nav": 100.0})
    service.storage.persist_record("workflow_runs", "workflow-1", {"workflow_id": "workflow-1", "status": "blocked", "generated_at": datetime.now(timezone.utc).isoformat()})
    service.storage.persist_record(
        "paper_weekly_digest_deliveries",
        "weekly-digest-2026-01-02-1",
        {
            "delivery_id": "weekly-digest-2026-01-02-1",
            "digest_id": "weekly-digest-2026-01-02",
            "session_date": "2026-01-02",
            "phase": "weekly",
            "channel": "unsupported",
            "status": "failed",
            "next_retry_at": "2026-01-01T00:00:00+00:00",
        },
    )

    digest = service.build_quant_weekly_digest(session_date="2026-01-02", window_days=7)
    retry = service.retry_failed_daily_digest_deliveries(limit=5)

    assert digest["phase"] == "weekly"
    assert digest["summary"]["orders"]["blocked"] == 1
    assert retry["attempted_count"] == 1
    updated = service.storage.load_record("paper_weekly_digest_deliveries", "weekly-digest-2026-01-02-1")
    assert updated["retry_count"] == 1


def test_paper_90_session_replay_has_complete_evidence_and_no_duplicate_submit():
    result = run_replay(datetime(2026, 1, 2, tzinfo=timezone.utc).date(), count=90)

    assert result["status"] == "passed"
    assert result["session_count"] == 90
    assert result["complete_evidence_count"] == 90
    assert result["duplicate_submit_attempts"] == 0
    assert result["duplicate_submit_blocked_count"] > 0


def test_restore_drill_self_test_and_chaos_drill_pass(tmp_path):
    restore = run_restore(SimpleNamespace(self_test=True, archive=None, storage_dir=tmp_path, restore_dir=tmp_path / "restore", clean=True))
    chaos = run_drill()

    assert restore["ready"] is True
    assert chaos["status"] == "passed"


def test_precloud_local_acceptance_covers_three_final_gates(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "STORAGE_BACKUP_ENABLED=true",
                "ALPACA_ENABLE_LIVE_TRADING=false",
                "SYNTHETIC_EVIDENCE_POLICY=block",
                "UNATTENDED_PAPER_MODE=true",
                "SHADOW_RETRAIN_ENABLED=false",
                "MODEL_RETRAIN_SHADOW_ONLY=true",
                "OMP_NUM_THREADS=2",
                "MKL_NUM_THREADS=2",
                "OPENBLAS_NUM_THREADS=2",
                "NUMEXPR_NUM_THREADS=2",
                "TORCH_NUM_THREADS=2",
                "PUBLIC_EXPOSURE_PROTECTED=true",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = run_local_three_gate(
        SimpleNamespace(env_file=env_file, require_public_exposure_protected=True, json_out="")
    )

    assert result["ready"] is True
    check_names = {row["name"] for row in result["checks"] if row["ok"]}
    assert "env_public_exposure_protected" in check_names
    assert "api_ready" in check_names
    assert "api_preflight" in check_names
    assert "first_session_evidence_complete" in check_names


def test_paper_automation_api_contract(monkeypatch):
    class _FakeService:
        def build_paper_performance_report(self, **kwargs):
            return {"window_days": kwargs["window_days"], "metrics": {"valid_days": 90}}

        def capture_paper_performance_snapshot(self, **kwargs):
            return {"snapshot_id": "2026-01-02", "workflow_id": kwargs["workflow_id"]}

        def backfill_paper_performance(self, **kwargs):
            return {"backfilled_snapshots": 1, "days": kwargs["days"]}

        def build_quant_daily_digest(self, **kwargs):
            return {"digest_id": "digest-1", "phase": kwargs["phase"]}

        def send_quant_daily_digest(self, **kwargs):
            return {"digest_id": "digest-1", "delivery": {"sent_count": 2}, "phase": kwargs["phase"]}

        def build_quant_weekly_digest(self, **kwargs):
            return {"digest_id": "weekly-digest-1", "window_days": kwargs["window_days"]}

        def send_quant_weekly_digest(self, **kwargs):
            return {"digest_id": "weekly-digest-1", "delivery": {"sent_count": 2}, "window_days": kwargs["window_days"]}

        def latest_session_evidence(self):
            return {"session_date": "2026-01-02"}

        def get_session_evidence(self, session_date):
            return {"session_date": session_date}

        def reconcile_alpaca_paper_orders(self, **kwargs):
            return {"session_date": kwargs["session_date"], "status": "completed"}

        def backup_quant_storage(self, **kwargs):
            return {"session_date": kwargs["session_date"], "status": "completed_local_only"}

        def list_submit_locks(self, **kwargs):
            return {"count": 1, "locks": [{"lock_id": "lock-1"}], "limit": kwargs["limit"]}

        def list_paper_outcomes(self, **kwargs):
            return {"count": 1, "outcomes": [{"outcome_id": "outcome-1"}], "limit": kwargs["limit"]}

        def settle_paper_outcomes(self, **kwargs):
            return {"updated_count": 1, "outcome_id": kwargs["outcome_id"]}

        def build_promotion_report(self, **kwargs):
            return {"promotion_status": "paper_candidate", "window_days": kwargs["window_days"]}

        def evaluate_promotion(self, **kwargs):
            return {"promotion_status": "paper_promoted", "persisted": kwargs["persist"]}

        def build_promotion_timeline(self, **kwargs):
            return {"current_status": "paper_candidate", "events": []}

        def run_shadow_retrain(self, **kwargs):
            return {"status": "skipped", "model_key": kwargs["model_key"], "force": kwargs["force"]}

        def latest_shadow_retrain(self):
            return {"status": "missing"}

        def build_deployment_preflight(self, **kwargs):
            return {"ready": True, "profile": kwargs["profile"], "blockers": []}

        def evaluate_deployment_preflight(self, **kwargs):
            return {"ready": True, "profile": kwargs["profile"], "evaluated": True}

        def get_trading_calendar_status(self):
            return {"calendar_id": "XNYS", "is_session": True}

        def build_paper_workflow_observability(self, **kwargs):
            return {"window_days": kwargs["window_days"], "summary": {"workflow_count": 1}}

        def build_paper_workflow_slo(self, **kwargs):
            return {"window_days": kwargs["window_days"], "workflow": {"success_rate": 1.0}}

        def evaluate_paper_workflow_observability(self, **kwargs):
            return {"window_days": kwargs["window_days"], "summary": {"alert_count": 1}}

    monkeypatch.setattr(quant_router, "_quant_service", lambda: _FakeService())
    client = TestClient(main_module.app)

    assert client.get("/api/v1/quant/paper/performance?window_days=90").json()["metrics"]["valid_days"] == 90
    assert client.post("/api/v1/quant/paper/performance/snapshot", json={"workflow_id": "wf"}).json()["workflow_id"] == "wf"
    assert client.post("/api/v1/quant/paper/performance/backfill", json={"days": 120}).json()["backfilled_snapshots"] == 1
    assert client.get("/api/v1/quant/paper/daily-digest/latest?phase=postclose").json()["digest_id"] == "digest-1"
    assert client.post("/api/v1/quant/paper/daily-digest/send", json={"phase": "preopen"}).json()["delivery"]["sent_count"] == 2
    assert client.get("/api/v1/quant/paper/weekly-digest/latest?window_days=7").json()["digest_id"] == "weekly-digest-1"
    assert client.post("/api/v1/quant/paper/weekly-digest/send", json={"window_days": 7}).json()["delivery"]["sent_count"] == 2
    assert client.get("/api/v1/quant/session-evidence/latest").json()["session_date"] == "2026-01-02"
    assert client.get("/api/v1/quant/session-evidence/2026-01-02").json()["session_date"] == "2026-01-02"
    assert client.post("/api/v1/quant/execution/reconcile/alpaca-paper", json={"session_date": "2026-01-02"}).json()["status"] == "completed"
    assert client.post("/api/v1/quant/storage/backup", json={"session_date": "2026-01-02"}).json()["status"] == "completed_local_only"
    assert client.get("/api/v1/quant/submit-locks?limit=5").json()["count"] == 1
    assert client.get("/api/v1/quant/paper/outcomes?limit=5").json()["count"] == 1
    assert client.post("/api/v1/quant/paper/outcomes/settle", json={"outcome_id": "outcome-1"}).json()["updated_count"] == 1
    assert client.get("/api/v1/quant/promotion/report").json()["promotion_status"] == "paper_candidate"
    assert client.post("/api/v1/quant/promotion/evaluate", json={"persist": True}).json()["promotion_status"] == "paper_promoted"
    assert client.get("/api/v1/quant/promotion/timeline").json()["current_status"] == "paper_candidate"
    assert client.post("/api/v1/quant/models/shadow-retrain/run", json={"force": True}).json()["force"] is True
    assert client.get("/api/v1/quant/models/shadow-retrain/latest").json()["status"] == "missing"
    assert client.get("/api/v1/quant/deployment/preflight?profile=paper_cloud").json()["ready"] is True
    assert client.post("/api/v1/quant/deployment/preflight/evaluate?profile=paper_cloud").json()["evaluated"] is True
    assert client.get("/api/v1/quant/trading-calendar/status").json()["calendar_id"] == "XNYS"
    assert client.get("/api/v1/quant/observability/paper-workflow?window_days=30").json()["summary"]["workflow_count"] == 1
    assert client.get("/api/v1/quant/slo/paper-workflow?window_days=30").json()["workflow"]["success_rate"] == 1.0
    assert client.post("/api/v1/quant/observability/paper-workflow/evaluate?window_days=30").json()["summary"]["alert_count"] == 1


def test_paper_performance_frontend_contract():
    page = open("frontend/js/pages/paper-performance.js", encoding="utf-8").read()
    api_source = open("frontend/js/qtapi.js", encoding="utf-8").read()
    router = open("frontend/js/router.js", encoding="utf-8").read()
    trading_ops = open("frontend/js/pages/trading-ops.js", encoding="utf-8").read()

    assert "/paper-performance" in router
    assert "#btn-paper-performance-refresh" in page
    assert "#btn-paper-outcomes-settle" in page
    assert "/paper/performance" in api_source
    assert "/paper/performance/backfill" in api_source
    assert "/paper/daily-digest/latest" in api_source
    assert "/paper/daily-digest/send" in api_source
    assert "/paper/weekly-digest/latest" in api_source
    assert "/paper/weekly-digest/send" in api_source
    assert "/session-evidence/latest" in api_source
    assert "/session-evidence/" in api_source
    assert "/execution/reconcile/alpaca-paper" in api_source
    assert "/storage/backup" in api_source
    assert "/submit-locks" in api_source
    assert "/paper/outcomes/settle" in api_source
    assert "/promotion/report" in api_source
    assert "/promotion/timeline" in api_source
    assert "/models/shadow-retrain/run" in api_source
    assert "/models/shadow-retrain/latest" in api_source
    assert "/deployment/preflight" in api_source
    assert "/deployment/preflight/evaluate" in api_source
    assert "/trading-calendar/status" in api_source
    assert "/observability/paper-workflow" in api_source
    assert "/slo/paper-workflow" in api_source
    assert "evaluatePaperWorkflow" in api_source
    assert "paper-filter-symbol" in page
    assert "paper-preflight-drilldown" in page
    assert "paper-session-evidence" in page
    assert "paper-submit-locks" in page
    assert "paper-attribution-trends" in page
    assert "renderCloudPreflight" in trading_ops


def test_unattended_compose_and_ci_contracts():
    compose = open("docker-compose.yml", encoding="utf-8").read()
    compose_5090 = open("docker-compose.5090.yml", encoding="utf-8").read()
    ci = open(".github/workflows/ci.yml", encoding="utf-8").read()
    integration = open(".github/workflows/integration-ci.yml", encoding="utf-8").read()
    nightly = open(".github/workflows/nightly-deep.yml", encoding="utf-8").read()
    watchdog = open("scripts/quant_watchdog.py", encoding="utf-8").read()
    watchdog_timer = open("deploy/systemd/quant-paper-watchdog.timer", encoding="utf-8").read()
    compose_service = open("deploy/systemd/quant-paper-compose.service", encoding="utf-8").read()
    runbook = open("docs/PAPER_CLOUD_CPU_RUNBOOK_ZH.md", encoding="utf-8").read()

    assert "/livez" in compose
    assert "/livez" in compose_5090
    assert "total_seconds() < 300" in compose
    assert "total_seconds() < 300" in compose_5090
    assert 'cpus: "2.0"' in compose
    assert "mem_limit: 4g" in compose
    assert "max-size: \"50m\"" in compose
    assert "OMP_NUM_THREADS" in compose
    assert "Fast CI" in ci
    assert "Integration CI" in integration
    assert "Nightly Deep Run" in nightly
    assert "paper_90_session_replay.py --count 90" in nightly
    assert "restore_quant_backup.py --self-test" in nightly
    assert "paper_chaos_drill.py" in nightly
    assert "restart_services" in watchdog
    assert "latest_session_evidence" in watchdog
    assert "ready_restart_threshold" in watchdog
    assert "OnUnitActiveSec=60" in watchdog_timer
    assert "docker compose up api qdrant quant-scheduler" in compose_service
    assert "Restart=always" in compose_service
    assert "paper_cloud_acceptance.py" in runbook
    assert "ALPACA_ENABLE_LIVE_TRADING=false" in runbook
