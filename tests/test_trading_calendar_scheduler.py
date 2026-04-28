from __future__ import annotations

from datetime import date

import scripts.quant_signal_scheduler as scheduler_script
from gateway.quant.trading_calendar import TradingCalendarService


def test_xnys_calendar_handles_holiday_and_early_close():
    calendar = TradingCalendarService("XNYS")

    assert calendar.is_session(date(2026, 11, 26)) is False
    assert calendar.next_session(date(2026, 11, 26)) == "2026-11-27"

    early = calendar.session_info(date(2026, 11, 27))
    assert early.is_session is True
    assert early.early_close is True
    assert early.close_at is not None
    assert early.close_at.strftime("%H:%M") == "13:00"


def test_scheduler_skips_non_session_when_required(tmp_path, monkeypatch):
    heartbeat_path = tmp_path / "heartbeat.json"
    monkeypatch.setattr(scheduler_script, "scheduler_heartbeat_path", lambda: heartbeat_path)
    monkeypatch.setattr(scheduler_script.settings, "SCHEDULER_REQUIRE_TRADING_SESSION", True)

    class _FakeService:
        def get_trading_calendar_status(self):
            return {
                "calendar_id": "XNYS",
                "session_date": "2026-11-26",
                "is_session": False,
                "market_clock_status": "closed",
                "next_session": "2026-11-27",
            }

    result = scheduler_script.run_hybrid_workflow_cycle(_FakeService(), {})

    assert result["skipped"] is True
    assert result["skip_reason"] == "not_trading_session"
    assert result["next_session"] == "2026-11-27"

