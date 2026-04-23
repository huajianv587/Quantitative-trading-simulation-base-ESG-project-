from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from scripts import real_auth_acceptance, real_external_closure
from scripts.quant_execution_smoke import find_cancel_target, should_run_live_canary


def test_extract_reset_token_from_text_supports_plain_and_link():
    plain = "Reset token: abc123_token\nReset page: http://127.0.0.1/app#/reset-password"
    link = "Click here: http://127.0.0.1/app#/reset-password?token=xyz789_token"

    assert real_auth_acceptance.extract_reset_token_from_text(plain) == "abc123_token"
    assert real_auth_acceptance.extract_reset_token_from_text(link) == "xyz789_token"


def test_real_auth_acceptance_main_requires_credentials(tmp_path, monkeypatch):
    monkeypatch.delenv("REAL_AUTH_TEST_EMAIL", raising=False)
    monkeypatch.delenv("REAL_AUTH_TEST_PASSWORD", raising=False)
    monkeypatch.delenv("REAL_AUTH_TEST_NEW_PASSWORD", raising=False)
    report_path = tmp_path / "auth.json"

    exit_code = real_auth_acceptance.main(["--write-report", str(report_path)])

    assert exit_code == 1
    assert report_path.exists()
    assert "email_or_password_missing" in report_path.read_text(encoding="utf-8")


def test_should_run_live_canary_requires_confirmation():
    args = SimpleNamespace(mode="live", dry_run=False, confirm_live=False)

    allowed, reason = should_run_live_canary(args, {"ready": True, "broker_status": "ready"})

    assert allowed is False
    assert reason == "confirm_live_not_provided"


def test_should_run_live_canary_blocks_when_broker_not_ready():
    args = SimpleNamespace(mode="live", dry_run=False, confirm_live=True)

    allowed, reason = should_run_live_canary(args, {"ready": False, "broker_status": "blocked"})

    assert allowed is False
    assert reason.startswith("broker_not_ready")


def test_find_cancel_target_returns_not_applicable_for_filled_orders():
    order_id, detail = find_cancel_target({"orders": [{"client_order_id": "ord-001", "status": "filled"}]})

    assert order_id is None
    assert detail == "n_a_filled"


def test_real_external_closure_auth_only_writes_summary(tmp_path, monkeypatch):
    monkeypatch.setenv("REAL_AUTH_TEST_EMAIL", "auth@example.com")
    monkeypatch.setenv("REAL_AUTH_TEST_PASSWORD", "Start123!")
    monkeypatch.setenv("REAL_AUTH_TEST_NEW_PASSWORD", "Reset456!")
    monkeypatch.setenv("SMTP_USER", "mailbox@example.com")

    class _DummyProc:
        def poll(self):
            return 0

    monkeypatch.setattr(
        real_external_closure,
        "start_server",
        lambda *args, **kwargs: (_DummyProc(), "http://127.0.0.1:8006", Path(), Path(), {"ok": True}),
    )
    monkeypatch.setattr(real_external_closure, "stop_process", lambda proc: None)

    def fake_run_json_command(command, *, cwd):
        command_text = " ".join(command)
        if "real_auth_acceptance.py" in command_text:
            return 0, {"ok": True, "stage": "auth_acceptance"}, ""
        if "email_roundtrip_check.py" in command_text:
            return 0, {"ok": True, "stage": "email_roundtrip"}, ""
        return 1, {"ok": False}, "unexpected command"

    monkeypatch.setattr(real_external_closure, "run_json_command", fake_run_json_command)

    exit_code = real_external_closure.main(["--auth-only", "--write-report-dir", str(tmp_path)])

    assert exit_code == 0
    assert (tmp_path / "summary.json").exists()
    assert (tmp_path / "summary.md").exists()
    assert "real_external_closure" in (tmp_path / "summary.json").read_text(encoding="utf-8")
