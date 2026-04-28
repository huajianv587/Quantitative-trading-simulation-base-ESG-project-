from __future__ import annotations

from pathlib import Path

import requests

from gateway.quant.service import QuantSystemService


def test_paper_observability_records_scheduler_events_and_alerts(tmp_path: Path, monkeypatch):
    service = QuantSystemService()
    service.storage.base_dir = tmp_path
    heartbeat_calls = {"count": 0}

    def heartbeat_status():
        heartbeat_calls["count"] += 1
        return {"exists": False, "stale": True, "age_minutes": heartbeat_calls["count"]}

    monkeypatch.setattr(service, "_scheduler_heartbeat_status", heartbeat_status)
    monkeypatch.setattr(service, "get_execution_controls", lambda: {"kill_switch_enabled": True, "kill_switch_reason": "test"})
    monkeypatch.setattr(service, "get_trading_calendar_status", lambda: {"calendar_id": "XNYS", "is_session": True})
    monkeypatch.setattr("gateway.quant.service.settings.TELEGRAM_BOT_TOKEN", "", raising=False)
    monkeypatch.setattr("gateway.quant.service.settings.TELEGRAM_CHAT_ID", "", raising=False)

    event = service.record_scheduler_event(stage="hybrid_workflow", status="blocked", payload={"workflow_id": "wf"})
    report = service.build_paper_workflow_observability(window_days=30)

    assert event["storage"]["record_type"] == "scheduler_events"
    assert event["duration_seconds"] is None
    assert event["submitted_count"] == 0
    assert report["summary"]["scheduler_event_count"] == 1
    assert report["workflow_success_rate"] == 0.0
    assert report["heartbeat_stale"] is True
    assert report["circuit_breaker"]["enabled"] is False
    assert {alert["kind"] for alert in report["alerts"]} >= {"stale_heartbeat", "missing_workflow", "kill_switch"}
    assert service.storage.list_records("alerts") == []

    evaluated = service.evaluate_paper_workflow_observability(window_days=30)
    assert {alert["kind"] for alert in evaluated["alerts"]} >= {"stale_heartbeat", "missing_workflow", "kill_switch"}
    alert_count = len(service.storage.list_records("alerts"))
    assert alert_count >= 3

    evaluated_again = service.evaluate_paper_workflow_observability(window_days=30)
    assert len(service.storage.list_records("alerts")) == alert_count
    assert all(alert.get("deduped") for alert in evaluated_again["alerts"])


def test_paper_observability_delivers_telegram_alerts(tmp_path: Path, monkeypatch):
    service = QuantSystemService()
    service.storage.base_dir = tmp_path
    sent = []

    class _Response:
        ok = True
        status_code = 200
        text = "ok"

    def fake_post(url, json=None, timeout=0):
        sent.append({"url": url, "json": json, "timeout": timeout})
        return _Response()

    monkeypatch.setattr(service, "_scheduler_heartbeat_status", lambda: {"exists": False, "stale": True})
    monkeypatch.setattr(service, "get_execution_controls", lambda: {"kill_switch_enabled": False})
    monkeypatch.setattr(service, "_rl_checkpoint_preflight", lambda: {"ok": True})
    monkeypatch.setattr(service, "_market_data_preflight", lambda: {"ok": True})
    monkeypatch.setattr(service.storage, "status", lambda: {"supabase_ready": True, "r2_ready": False, "supabase_storage_ready": False})
    monkeypatch.setattr(requests, "post", fake_post)
    monkeypatch.setattr("gateway.quant.service.settings.ALERT_NOTIFIER", "telegram", raising=False)
    monkeypatch.setattr("gateway.quant.service.settings.TELEGRAM_BOT_TOKEN", "token", raising=False)
    monkeypatch.setattr("gateway.quant.service.settings.TELEGRAM_CHAT_ID", "chat", raising=False)

    evaluated = service.evaluate_paper_workflow_observability(window_days=30)

    assert evaluated["alerts"]
    assert sent
    assert sent[0]["url"].startswith("https://api.telegram.org/bottoken/sendMessage")


def test_quant_system_exposes_internal_paper_services(tmp_path: Path):
    service = QuantSystemService()
    service.storage.base_dir = tmp_path

    assert service.paper_workflow_service.facade is service
    assert service.paper_performance_service.facade is service
    assert service.outcome_ledger_service.facade is service
    assert service.promotion_service.facade is service
    assert service.deployment_preflight_service.facade is service
