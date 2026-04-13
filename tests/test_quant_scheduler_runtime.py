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


def test_run_execution_cycle_uses_preopen_shortlist_and_persists_state(tmp_path, monkeypatch):
    state_path = tmp_path / "runtime_state.json"
    heartbeat_path = tmp_path / "heartbeat.json"

    monkeypatch.setattr(scheduler_script, "scheduler_state_path", lambda: state_path)
    monkeypatch.setattr(scheduler_script, "scheduler_heartbeat_path", lambda: heartbeat_path)
    monkeypatch.setattr(scheduler_script.settings, "SCHEDULER_AUTO_SUBMIT", True)
    monkeypatch.setattr(scheduler_script.settings, "QUANT_BROKER_DEFAULT", "alpaca")
    monkeypatch.setattr(scheduler_script.settings, "ALPACA_DEFAULT_TEST_NOTIONAL", 1000.0)
    monkeypatch.setattr(scheduler_script.settings, "SCHEDULER_MAX_EXECUTION_SYMBOLS", 2)
    monkeypatch.setattr(scheduler_script.settings, "SCHEDULER_MAX_DAILY_NOTIONAL_USD", 1000.0)

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


def test_run_sync_cycle_auto_cancels_and_retries_stale_orders(tmp_path, monkeypatch):
    state_path = tmp_path / "runtime_state.json"
    heartbeat_path = tmp_path / "heartbeat.json"

    monkeypatch.setattr(scheduler_script, "scheduler_state_path", lambda: state_path)
    monkeypatch.setattr(scheduler_script, "scheduler_heartbeat_path", lambda: heartbeat_path)
    monkeypatch.setattr(scheduler_script.settings, "QUANT_BROKER_DEFAULT", "alpaca")
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
