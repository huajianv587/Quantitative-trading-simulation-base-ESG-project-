from __future__ import annotations

import argparse
import json
from pathlib import Path

import scripts.quant_watchdog as watchdog


def _args(tmp_path: Path, *, dry_run: bool = True) -> argparse.Namespace:
    heartbeat = tmp_path / "scheduler" / "heartbeat.json"
    heartbeat.parent.mkdir(parents=True, exist_ok=True)
    heartbeat.write_text(json.dumps({"updated_at": watchdog.iso_now()}), encoding="utf-8")
    return argparse.Namespace(
        api_url="http://127.0.0.1:8012",
        http_timeout=1.0,
        heartbeat_path=heartbeat,
        heartbeat_stale_seconds=300,
        project_dir=tmp_path,
        compose_file="docker-compose.yml",
        restart_services=["api", "quant-scheduler"],
        ready_restart_threshold=3,
        dry_run=dry_run,
        notify=False,
    )


def test_watchdog_ok_does_not_restart_or_alert(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("QUANT_STORAGE_DIR", str(tmp_path / "quant"))
    monkeypatch.setattr(watchdog, "check_http", lambda *_args, **_kwargs: {"ok": True, "status_code": 200})
    monkeypatch.setattr(watchdog, "collect_diagnostics", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("no diagnostics")))
    monkeypatch.setattr(watchdog, "restart_services", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("no restart")))

    event = watchdog.evaluate_once(_args(tmp_path))

    assert event["status"] == "ok"
    assert event["failures"] == []
    assert not (tmp_path / "quant" / "alerts").exists()


def test_watchdog_failure_records_alert_without_restart_in_dry_run(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("QUANT_STORAGE_DIR", str(tmp_path / "quant"))
    monkeypatch.setattr(watchdog, "check_http", lambda *_args, **_kwargs: {"ok": False, "error": "down"})
    monkeypatch.setattr(watchdog, "collect_diagnostics", lambda *_args, **_kwargs: {"compose_ps": {"ok": False}})
    monkeypatch.setattr(watchdog, "restart_services", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("dry-run no restart")))

    event = watchdog.evaluate_once(_args(tmp_path, dry_run=True))

    assert event["status"] == "failed"
    assert "livez_unhealthy" in event["failures"]
    assert "ready_unhealthy" in event["failures"]
    assert event["restart_attempted"] is False
    assert list((tmp_path / "quant" / "watchdog_events").glob("*.json"))
    alerts = list((tmp_path / "quant" / "alerts").glob("*.json"))
    assert len(alerts) == 1
    assert json.loads(alerts[0].read_text(encoding="utf-8"))["kind"] == "watchdog_failure"


def test_watchdog_restarts_scheduler_for_stale_heartbeat(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("QUANT_STORAGE_DIR", str(tmp_path / "quant"))
    args = _args(tmp_path, dry_run=False)
    args.heartbeat_path.write_text(json.dumps({"updated_at": "1970-01-01T00:00:00+00:00"}), encoding="utf-8")
    monkeypatch.setattr(watchdog, "check_http", lambda *_args, **_kwargs: {"ok": True, "status_code": 200})
    monkeypatch.setattr(watchdog, "collect_diagnostics", lambda *_args, **_kwargs: {"compose_ps": {"ok": True}, "recent_logs": {"stdout": "recent"}})
    called: list[list[str]] = []

    def fake_restart(_project_dir, _compose_file, services):
        called.append(list(services))
        return {"ok": True, "services": list(services)}

    monkeypatch.setattr(watchdog, "restart_services", fake_restart)

    event = watchdog.evaluate_once(args)

    assert event["status"] == "failed"
    assert event["restart_attempted"] is True
    assert called == [["quant-scheduler"]]
    assert event["restart_count"] == 1
