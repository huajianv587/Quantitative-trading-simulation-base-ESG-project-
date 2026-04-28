from __future__ import annotations

from datetime import timedelta

import scripts.quant_signal_scheduler as scheduler_script


def test_extract_actionable_symbols_filters_and_ranks():
    payload = {
        "signals": [
            {"symbol": "AAPL", "action": "neutral", "expected_return": 0.05, "confidence": 0.7, "overall_score": 70},
            {"symbol": "MSFT", "action": "long", "expected_return": 0.03, "confidence": 0.6, "overall_score": 68},
            {"symbol": "NVDA", "action": "long", "expected_return": 0.07, "confidence": 0.8, "overall_score": 72},
            {"symbol": "TSLA", "action": "long", "expected_return": -0.01, "confidence": 0.95, "overall_score": 75},
        ]
    }

    symbols = scheduler_script.extract_actionable_symbols(payload, max_symbols=2)

    assert symbols == ["NVDA", "MSFT"]


def test_filter_fresh_symbols_excludes_only_stale_candidates():
    class _MarketData:
        def get_daily_bars(self, symbol, **_kwargs):
            if symbol == "AAPL":
                return [{"timestamp": "2026-01-03T00:00:00+00:00", "close": 100}]
            return [{"timestamp": "2026-01-02T00:00:00+00:00", "close": 100}]

    class _Service:
        market_data = _MarketData()

    result = scheduler_script.filter_fresh_symbols(_Service(), ["AAPL", "MSFT"], session_date="2026-01-03")

    assert result["symbols"] == ["AAPL"]
    assert result["excluded_symbols"][0]["symbol"] == "MSFT"


def test_filter_fresh_symbols_is_phase_aware_for_open_submit():
    class _MarketData:
        def get_daily_bars(self, symbol, **_kwargs):
            return [{"timestamp": "2026-01-02T00:00:00+00:00", "close": 100}]

    class _Calendar:
        def previous_session(self, _day):
            return "2026-01-02"

    class _Service:
        market_data = _MarketData()
        trading_calendar = _Calendar()

    result = scheduler_script.filter_fresh_symbols(
        _Service(),
        ["AAPL"],
        session_date="2026-01-05",
        phase="submit",
        session_status={"market_clock_status": "open", "effective_market_open": True, "previous_session": "2026-01-02"},
    )

    assert result["symbols"] == ["AAPL"]
    assert result["diagnostics"][0]["fresh_for_submit"] is True


def test_run_execution_cycle_uses_preopen_shortlist_and_persists_state(tmp_path, monkeypatch):
    state_path = tmp_path / "runtime_state.json"
    heartbeat_path = tmp_path / "heartbeat.json"

    monkeypatch.setattr(scheduler_script, "scheduler_state_path", lambda: state_path)
    monkeypatch.setattr(scheduler_script, "scheduler_heartbeat_path", lambda: heartbeat_path)
    monkeypatch.setattr(scheduler_script.settings, "SCHEDULER_AUTO_SUBMIT", True)
    monkeypatch.setattr(scheduler_script.settings, "SCHEDULER_REQUIRE_TRADING_SESSION", False)
    monkeypatch.setattr(scheduler_script.settings, "QUANT_BROKER_DEFAULT", "alpaca")
    monkeypatch.setattr(scheduler_script.settings, "SCHEDULER_REQUIRE_TRADING_SESSION", False)
    monkeypatch.setattr(scheduler_script.settings, "ALPACA_DEFAULT_TEST_NOTIONAL", 1000.0)
    monkeypatch.setattr(scheduler_script.settings, "SCHEDULER_MAX_EXECUTION_SYMBOLS", 2)
    monkeypatch.setattr(scheduler_script.settings, "SCHEDULER_MAX_DAILY_NOTIONAL_USD", 1000.0)
    monkeypatch.setattr(scheduler_script.settings, "SCHEDULER_REQUIRE_TRADING_SESSION", False)

    captured = {}

    class _FakeService:
        default_benchmark = "SPY"
        default_capital = 1_000_000

        def create_execution_plan(self, **kwargs):
            captured.update(kwargs)
            return {
                "execution_id": "execution-test-1",
                "submitted": True,
                "broker_status": "submitted",
                "ready": True,
                "warnings": [],
                "state_machine": {"state": "routed"},
                "orders": [{"symbol": "NEE", "status": "accepted", "client_order_id": "cid-1", "broker_order_id": "bo-1"}],
            }

    state = {
        "trade_date": scheduler_script.now_local().date().isoformat(),
        "preopen": {
            "trade_date": scheduler_script.now_local().date().isoformat(),
            "candidate_symbols": ["NEE", "PG"],
        },
    }

    result = scheduler_script.run_execution_cycle(_FakeService(), state)

    assert captured["universe_symbols"] == ["NEE", "PG"]
    assert captured["per_order_notional"] == 500.0
    assert result["submitted"] is True
    assert result["max_daily_notional_usd"] == 1000.0
    assert state_path.exists()
    assert heartbeat_path.exists()


def test_run_hybrid_workflow_cycle_uses_shortlist_and_persists_state(tmp_path, monkeypatch):
    state_path = tmp_path / "runtime_state.json"
    heartbeat_path = tmp_path / "heartbeat.json"

    monkeypatch.setattr(scheduler_script, "scheduler_state_path", lambda: state_path)
    monkeypatch.setattr(scheduler_script, "scheduler_heartbeat_path", lambda: heartbeat_path)
    monkeypatch.setattr(scheduler_script.settings, "SCHEDULER_REQUIRE_TRADING_SESSION", False)
    monkeypatch.setattr(scheduler_script.settings, "QUANT_BROKER_DEFAULT", "alpaca")
    monkeypatch.setattr(scheduler_script.settings, "ALPACA_DEFAULT_TEST_NOTIONAL", 1000.0)
    monkeypatch.setattr(scheduler_script.settings, "SCHEDULER_MAX_EXECUTION_SYMBOLS", 2)
    monkeypatch.setattr(scheduler_script.settings, "SCHEDULER_MAX_DAILY_NOTIONAL_USD", 1000.0)

    captured = {}

    class _FakeService:
        default_benchmark = "SPY"
        default_capital = 1_000_000

        def run_hybrid_paper_strategy_workflow(self, **kwargs):
            captured.update(kwargs)
            return {
                "workflow_id": "workflow-scheduler-1",
                "status": "submitted",
                "execution_id": "execution-scheduler-1",
                "submitted_count": 2,
                "warnings": [],
                "blockers": [],
                "next_actions": [],
                "paper_performance_snapshot_id": scheduler_script.now_local().date().isoformat(),
                "outcome_summary": {"captured_count": 4},
                "order_summary": [{"symbol": "NEE", "status": "accepted"}],
                "steps": {"paper_execution": {"broker_status": "submitted"}},
            }

    state = {
        "trade_date": scheduler_script.now_local().date().isoformat(),
        "preopen": {
            "trade_date": scheduler_script.now_local().date().isoformat(),
            "candidate_symbols": ["NEE", "PG"],
        },
    }

    result = scheduler_script.run_hybrid_workflow_cycle(_FakeService(), state)

    assert captured["universe_symbols"] == ["NEE", "PG"]
    assert captured["submit_orders"] is True
    assert captured["mode"] == "paper"
    assert captured["allow_synthetic_execution"] is False
    assert captured["per_order_notional"] == 500.0
    assert result["workflow_id"] == "workflow-scheduler-1"
    assert state["hybrid_workflow"]["workflow_status"] == "submitted"
    assert state["execution"]["source"] == "hybrid_paper_workflow"
    assert state_path.exists()
    assert heartbeat_path.exists()


def test_hybrid_workflow_respects_paper_submit_circuit_breaker(tmp_path, monkeypatch):
    state_path = tmp_path / "runtime_state.json"
    heartbeat_path = tmp_path / "heartbeat.json"

    monkeypatch.setattr(scheduler_script, "scheduler_state_path", lambda: state_path)
    monkeypatch.setattr(scheduler_script, "scheduler_heartbeat_path", lambda: heartbeat_path)
    monkeypatch.setattr(scheduler_script.settings, "SCHEDULER_REQUIRE_TRADING_SESSION", False)
    monkeypatch.setattr(scheduler_script.settings, "QUANT_BROKER_DEFAULT", "alpaca")
    monkeypatch.setattr(scheduler_script.settings, "ALPACA_DEFAULT_TEST_NOTIONAL", 1.0)
    captured = {}

    class _FakeService:
        default_benchmark = "SPY"
        default_capital = 1_000_000

        def run_hybrid_paper_strategy_workflow(self, **kwargs):
            captured.update(kwargs)
            return {
                "workflow_id": "workflow-circuit",
                "status": "planned",
                "execution_id": "execution-circuit",
                "submitted_count": 0,
                "warnings": [],
                "blockers": [],
                "next_actions": [],
                "steps": {"paper_execution": {"broker_status": "circuit_blocked"}},
            }

        def set_paper_submit_circuit_breaker(self, **kwargs):
            return {"enabled": kwargs["enabled"], "reason": kwargs["reason"]}

    state = {
        "circuit_breakers": {"paper_submit": {"enabled": True, "reason": "test"}},
        "preopen": {"trade_date": scheduler_script.now_local().date().isoformat(), "candidate_symbols": ["AAPL"]},
    }

    result = scheduler_script.run_hybrid_workflow_cycle(_FakeService(), state)

    assert captured["submit_orders"] is False
    assert result["paper_submit_circuit_breaker"]["enabled"] is True


def test_failure_counter_enables_and_recovers_paper_submit_circuit_breaker():
    state = {}
    persisted = []

    class _FakeService:
        def set_paper_submit_circuit_breaker(self, **kwargs):
            persisted.append(kwargs)
            return {"enabled": kwargs["enabled"], "reason": kwargs["reason"]}

    service = _FakeService()
    for _ in range(scheduler_script.failure_threshold()):
        scheduler_script.update_failure_counter(service, state, key="broker_submit_error", failed=True, detail="boom")

    assert state["circuit_breakers"]["paper_submit"]["enabled"] is True
    scheduler_script.update_failure_counter(service, state, key="broker_submit_error", failed=False, detail="recovered")
    scheduler_script.maybe_release_paper_submit_circuit_breaker(service, state)
    assert state["circuit_breakers"]["paper_submit"]["enabled"] is False
    assert persisted[-1]["enabled"] is False


def test_recovery_cycle_backfills_missing_non_submit_steps(tmp_path, monkeypatch):
    state_path = tmp_path / "runtime_state.json"
    heartbeat_path = tmp_path / "heartbeat.json"

    monkeypatch.setattr(scheduler_script, "scheduler_state_path", lambda: state_path)
    monkeypatch.setattr(scheduler_script, "scheduler_heartbeat_path", lambda: heartbeat_path)
    monkeypatch.setattr(scheduler_script.settings, "SCHEDULER_REQUIRE_TRADING_SESSION", False)
    calls = []

    class _FakeService:
        def settle_paper_outcomes(self, **kwargs):
            calls.append("settle")
            return {"updated_count": 0}

        def capture_paper_performance_snapshot(self, **kwargs):
            calls.append("snapshot")
            return {"snapshot_id": "today"}

        def backfill_paper_performance(self, **kwargs):
            calls.append("backfill")
            return {"backfilled_snapshots": 1}

        def evaluate_promotion(self, **kwargs):
            calls.append("promotion")
            return {"promotion_status": "paper_candidate"}

        def evaluate_paper_workflow_observability(self, **kwargs):
            calls.append("observability")
            return {"summary": {"alert_count": 0}}

        def reconcile_alpaca_paper_orders(self, **kwargs):
            calls.append("reconcile")
            return {"status": "completed"}

        def retry_failed_daily_digest_deliveries(self, **kwargs):
            calls.append("digest_retry")
            return {"attempted_count": 0}

        def backup_quant_storage(self, **kwargs):
            calls.append("backup")
            return {"status": "completed_local_only"}

    today = scheduler_script.now_local().date().isoformat()
    state = {"trade_date": today, "execution": {"execution_id": "execution-1", "trade_date": today}}

    result = scheduler_script.run_recovery_cycle(_FakeService(), state)

    assert result["stage"] == "recovery"
    assert set(calls) == {"settle", "reconcile", "backfill", "snapshot", "promotion", "digest_retry", "backup", "observability"}
    assert state_path.exists()


def test_recovery_cycle_runs_non_submit_backfill_without_execution_id(tmp_path, monkeypatch):
    state_path = tmp_path / "runtime_state.json"
    heartbeat_path = tmp_path / "heartbeat.json"

    monkeypatch.setattr(scheduler_script, "scheduler_state_path", lambda: state_path)
    monkeypatch.setattr(scheduler_script, "scheduler_heartbeat_path", lambda: heartbeat_path)
    monkeypatch.setattr(scheduler_script.settings, "SCHEDULER_REQUIRE_TRADING_SESSION", False)
    calls = []

    class _FakeService:
        def settle_paper_outcomes(self, **kwargs):
            calls.append("settle")
            return {"updated_count": 0}

        def backfill_paper_performance(self, **kwargs):
            calls.append("backfill")
            return {"backfilled_snapshots": 1}

        def evaluate_promotion(self, **kwargs):
            calls.append("promotion")
            return {"promotion_status": "paper_candidate"}

        def evaluate_paper_workflow_observability(self, **kwargs):
            calls.append("observability")
            return {"summary": {"alert_count": 0}}

        def reconcile_alpaca_paper_orders(self, **kwargs):
            calls.append("reconcile")
            return {"status": "completed"}

        def retry_failed_daily_digest_deliveries(self, **kwargs):
            calls.append("digest_retry")
            return {"attempted_count": 0}

        def backup_quant_storage(self, **kwargs):
            calls.append("backup")
            return {"status": "completed_local_only"}

    result = scheduler_script.run_recovery_cycle(_FakeService(), {})

    assert result["stage"] == "recovery"
    assert result["warning"] == "missing_execution_id_non_submit_recovery_only"
    assert set(calls) == {"settle", "reconcile", "backfill", "promotion", "digest_retry", "backup", "observability"}
    assert "paper_performance_snapshot" not in result["automation"]["ran"]


def test_shadow_retrain_cycle_records_shadow_only_state(tmp_path, monkeypatch):
    state_path = tmp_path / "runtime_state.json"
    heartbeat_path = tmp_path / "heartbeat.json"

    monkeypatch.setattr(scheduler_script, "scheduler_state_path", lambda: state_path)
    monkeypatch.setattr(scheduler_script, "scheduler_heartbeat_path", lambda: heartbeat_path)

    class _FakeService:
        def run_shadow_retrain(self, **kwargs):
            return {"run_id": "shadow-1", "status": "skipped", "blockers": ["shadow_retrain_disabled"], "kwargs": kwargs}

    state = {}
    result = scheduler_script.run_shadow_retrain_cycle(_FakeService(), state)

    assert result["stage"] == "shadow_retrain"
    assert result["run_id"] == "shadow-1"
    assert state["shadow_retrain"]["latest"]["status"] == "skipped"
    assert state_path.exists()


def test_daily_digest_cycle_is_idempotent_per_session(tmp_path, monkeypatch):
    state_path = tmp_path / "runtime_state.json"
    heartbeat_path = tmp_path / "heartbeat.json"

    monkeypatch.setattr(scheduler_script, "scheduler_state_path", lambda: state_path)
    monkeypatch.setattr(scheduler_script, "scheduler_heartbeat_path", lambda: heartbeat_path)
    monkeypatch.setattr(scheduler_script.settings, "SCHEDULER_REQUIRE_TRADING_SESSION", False)
    monkeypatch.setattr(scheduler_script.settings, "QUANT_DAILY_DIGEST_PREOPEN_ENABLED", True)
    calls = []

    class _FakeService:
        def get_trading_calendar_status(self):
            today = scheduler_script.now_local().date().isoformat()
            return {"is_session": True, "session_date": today, "calendar_id": "XNYS"}

        def send_quant_daily_digest(self, **kwargs):
            calls.append(kwargs)
            return {
                "digest_id": f"digest-{kwargs['session_date']}-{kwargs['phase']}",
                "delivery": {"sent_count": 2, "failed_count": 0, "channels": ["telegram", "email"]},
                "storage": {"record_type": "paper_daily_digests"},
            }

    state = {}
    first = scheduler_script.run_daily_digest_cycle(_FakeService(), state, phase="preopen")
    second = scheduler_script.run_daily_digest_cycle(_FakeService(), state, phase="preopen")

    assert first["sent_count"] == 2
    assert second["skipped"] is True
    assert second["reason"] == "daily_digest_already_sent_for_session"
    assert len(calls) == 1
    assert state_path.exists()
    assert heartbeat_path.exists()


def test_weekly_digest_cycle_is_idempotent_per_week(tmp_path, monkeypatch):
    state_path = tmp_path / "runtime_state.json"
    heartbeat_path = tmp_path / "heartbeat.json"

    monkeypatch.setattr(scheduler_script, "scheduler_state_path", lambda: state_path)
    monkeypatch.setattr(scheduler_script, "scheduler_heartbeat_path", lambda: heartbeat_path)
    monkeypatch.setattr(scheduler_script.settings, "SCHEDULER_REQUIRE_TRADING_SESSION", False)
    monkeypatch.setattr(scheduler_script.settings, "QUANT_WEEKLY_DIGEST_ENABLED", True)
    monkeypatch.setattr(scheduler_script.settings, "QUANT_WEEKLY_DIGEST_DAY", scheduler_script.now_local().strftime("%A").lower())
    calls = []

    class _FakeService:
        def get_trading_calendar_status(self):
            today = scheduler_script.now_local().date().isoformat()
            return {"is_session": True, "session_date": today, "calendar_id": "XNYS"}

        def send_quant_weekly_digest(self, **kwargs):
            calls.append(kwargs)
            return {
                "digest_id": f"weekly-digest-{kwargs['session_date']}",
                "delivery": {"sent_count": 2, "failed_count": 0, "channels": ["telegram", "email"]},
                "storage": {"record_type": "paper_weekly_digests"},
            }

    state = {}
    first = scheduler_script.run_weekly_digest_cycle(_FakeService(), state)
    second = scheduler_script.run_weekly_digest_cycle(_FakeService(), state)

    assert first["sent_count"] == 2
    assert second["skipped"] is True
    assert second["reason"] == "weekly_digest_already_sent_for_week"
    assert len(calls) == 1
    assert state_path.exists()
    assert heartbeat_path.exists()


def test_legacy_execution_cycle_skips_after_hybrid_workflow_for_trade_date(tmp_path, monkeypatch):
    heartbeat_path = tmp_path / "heartbeat.json"
    monkeypatch.setattr(scheduler_script, "scheduler_heartbeat_path", lambda: heartbeat_path)
    monkeypatch.setattr(scheduler_script.settings, "SCHEDULER_REQUIRE_TRADING_SESSION", False)
    today = scheduler_script.now_local().date().isoformat()

    class _FakeService:
        default_benchmark = "SPY"
        default_capital = 1_000_000

        def create_execution_plan(self, **_kwargs):
            raise AssertionError("legacy execution should not run after hybrid workflow")

    result = scheduler_script.run_execution_cycle(
        _FakeService(),
        {"hybrid_workflow": {"trade_date": today, "workflow_id": "workflow-1", "execution_id": "execution-1"}},
    )

    assert result["skipped"] is True
    assert result["reason"] == "hybrid_workflow_already_ran_for_trade_date"


def test_run_sync_cycle_auto_cancels_and_retries_stale_orders(tmp_path, monkeypatch):
    state_path = tmp_path / "runtime_state.json"
    heartbeat_path = tmp_path / "heartbeat.json"

    monkeypatch.setattr(scheduler_script, "scheduler_state_path", lambda: state_path)
    monkeypatch.setattr(scheduler_script, "scheduler_heartbeat_path", lambda: heartbeat_path)
    monkeypatch.setattr(scheduler_script.settings, "QUANT_BROKER_DEFAULT", "alpaca")
    monkeypatch.setattr(scheduler_script.settings, "SCHEDULER_REQUIRE_TRADING_SESSION", False)
    monkeypatch.setattr(scheduler_script.settings, "SCHEDULER_ENABLE_AUTO_CANCEL", True)
    monkeypatch.setattr(scheduler_script.settings, "SCHEDULER_CANCEL_STALE_AFTER_MINUTES", 20)
    monkeypatch.setattr(scheduler_script.settings, "SCHEDULER_ENABLE_AUTO_RETRY", True)
    monkeypatch.setattr(scheduler_script.settings, "SCHEDULER_MAX_RETRY_ATTEMPTS", 1)
    monkeypatch.setattr(scheduler_script.settings, "SCHEDULER_RETRY_DELAY_MINUTES", 0)
    monkeypatch.setattr(scheduler_script.settings, "ALPACA_DEFAULT_TEST_NOTIONAL", 1000.0)
    monkeypatch.setattr(scheduler_script.settings, "SCHEDULER_MAX_EXECUTION_SYMBOLS", 2)
    monkeypatch.setattr(scheduler_script.settings, "SCHEDULER_MAX_DAILY_NOTIONAL_USD", 1000.0)

    stale_timestamp = (scheduler_script.now_utc() - timedelta(minutes=30)).isoformat()
    calls = {"cancel": [], "retry": [], "sync": 0}

    class _FakeService:
        def sync_execution_journal(self, execution_id: str, broker: str | None = None):
            calls["sync"] += 1
            return {
                "records_synced": 1,
                "state_transitions": 0,
                "state_machine": {"state": "routed"},
                "cancelable_order_ids": ["cid-1"] if calls["sync"] == 1 else [],
                "retryable_order_ids": [],
                "warnings": [],
            }

        def get_execution_account(self, broker: str = "alpaca"):
            return {"connected": True, "market_clock": {"is_open": True}, "warnings": []}

        def get_execution_journal(self, execution_id: str):
            return {
                "execution_id": execution_id,
                "broker_id": "alpaca",
                "records": [
                    {
                        "order_id": "cid-1",
                        "symbol": "NEE",
                        "current_state": "accepted",
                        "retry_count": 0,
                        "last_broker_snapshot": {"submitted_at": stale_timestamp},
                        "submitted_payload": {"notional": "500.00"},
                        "events": [],
                    }
                ],
            }

        def cancel_execution_order(self, order_id: str, broker: str | None = None, execution_id: str | None = None):
            calls["cancel"].append(order_id)
            return {
                "journal_record": {
                    "order_id": order_id,
                    "symbol": "NEE",
                    "current_state": "canceled",
                    "retry_count": 0,
                    "last_broker_snapshot": {"submitted_at": stale_timestamp},
                    "submitted_payload": {"notional": "500.00"},
                    "events": [],
                }
            }

        def retry_execution_order(
            self,
            order_id: str,
            broker: str | None = None,
            execution_id: str | None = None,
            per_order_notional: float | None = None,
            order_type: str = "market",
            time_in_force: str = "day",
            extended_hours: bool = False,
        ):
            calls["retry"].append((order_id, per_order_notional))
            return {
                "journal_record": {
                    "order_id": order_id,
                    "symbol": "NEE",
                    "current_state": "accepted",
                    "retry_count": 1,
                    "last_broker_snapshot": {"submitted_at": stale_timestamp},
                    "submitted_payload": {"notional": "500.00"},
                    "events": [],
                }
            }

        def _can_cancel_state(self, state):
            return str(state).lower() in {"accepted", "new", "pending", "partially_filled", "routed"}

        def _can_retry_state(self, state):
            return str(state).lower() in {"failed", "rejected", "canceled", "cancelled", "routing_exception", "expired"}

    state = {
        "trade_date": scheduler_script.now_local().date().isoformat(),
        "execution": {"execution_id": "execution-123", "trade_date": scheduler_script.now_local().date().isoformat()},
    }

    result = scheduler_script.run_sync_cycle(_FakeService(), state)

    assert calls["sync"] == 2
    assert calls["cancel"] == ["cid-1"]
    assert calls["retry"] == [("cid-1", 500.0)]
    assert result["management"]["action_count"] == 2
    assert [item["action"] for item in result["management"]["actions"]] == ["cancel", "retry"]
