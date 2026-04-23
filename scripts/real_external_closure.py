from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

from scripts.quant_execution_smoke import start_server, stop_process, tail_log


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def emit_json(payload: dict[str, Any]) -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    write_text(path, json.dumps(payload, ensure_ascii=False, indent=2))


def run_json_command(command: list[str], *, cwd: Path) -> tuple[int, dict[str, Any] | str, str]:
    completed = subprocess.run(command, cwd=cwd, capture_output=True, text=True, encoding="utf-8")
    stdout = completed.stdout.strip()
    try:
        payload = json.loads(stdout) if stdout else {}
    except Exception:
        payload = stdout or completed.stderr.strip()
    return completed.returncode, payload, completed.stderr.strip()


def build_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Real External Closure Summary",
        "",
        f"- ok: `{summary.get('ok')}`",
        f"- started_at: `{summary.get('started_at')}`",
        f"- finished_at: `{summary.get('finished_at')}`",
        f"- report_dir: `{summary.get('report_dir')}`",
        "",
        "## Stages",
        "",
    ]
    for step in summary.get("steps", []):
        lines.append(f"- `{step['stage']}`: ok=`{step['ok']}` detail=`{step['detail']}`")
    warnings = summary.get("warnings") or []
    lines.extend(["", "## Warnings", ""])
    if warnings:
        for warning in warnings:
            lines.append(f"- {warning}")
    else:
        lines.append("- none")
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(description="Real external dependency closure orchestrator.")
    parser.add_argument("--auth-only", action="store_true")
    parser.add_argument("--broker-only", action="store_true")
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--skip-live", action="store_true")
    parser.add_argument("--confirm-live", action="store_true")
    parser.add_argument("--write-report-dir", default="")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8006)
    parser.add_argument("--startup-timeout", type=int, default=120)
    parser.add_argument("--base-url", default="")
    parser.add_argument("--reuse-server", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    report_dir = Path(args.write_report_dir) if args.write_report_dir else PROJECT_ROOT / "test-results" / "real-external" / run_id
    if not report_dir.is_absolute():
        report_dir = PROJECT_ROOT / report_dir
    report_dir.mkdir(parents=True, exist_ok=True)

    do_auth = args.full or args.auth_only or not args.broker_only
    do_broker = args.full or args.broker_only or not args.auth_only

    summary: dict[str, Any] = {
        "ok": False,
        "stage": "real_external_closure",
        "started_at": utc_now(),
        "finished_at": None,
        "report_dir": str(report_dir),
        "steps": [],
        "warnings": [],
        "next_actions": [],
        "evidence": {},
    }

    proc = None
    stdout_log = Path()
    stderr_log = Path()
    base_url = args.base_url.rstrip("/") if args.base_url else f"http://{args.host}:{args.port}"
    try:
        if not args.reuse_server:
            proc, base_url, stdout_log, stderr_log, health_payload = start_server(
                args.host,
                args.port,
                args.startup_timeout,
                app_mode=os.getenv("APP_MODE", "local"),
                llm_backend_mode=os.getenv("LLM_BACKEND_MODE", "auto"),
            )
            if proc is None:
                summary["steps"].append({"stage": "startup", "ok": False, "detail": "startup_failed", "payload": health_payload})
                summary["warnings"].append("Shared real-external server failed to start.")
                summary["evidence"]["stdout_tail"] = tail_log(stdout_log)
                summary["evidence"]["stderr_tail"] = tail_log(stderr_log)
                summary["finished_at"] = utc_now()
                write_json(report_dir / "summary.json", summary)
                write_text(report_dir / "summary.md", build_markdown(summary))
                emit_json(summary)
                return 1
            summary["steps"].append({"stage": "startup", "ok": True, "detail": "server_started", "payload": health_payload})

        python_exe = sys.executable

        if do_auth:
            auth_cmd = [
                python_exe,
                str(PROJECT_ROOT / "scripts" / "real_auth_acceptance.py"),
                "--base-url",
                base_url,
                "--email",
                os.getenv("REAL_AUTH_TEST_EMAIL", ""),
                "--password",
                os.getenv("REAL_AUTH_TEST_PASSWORD", ""),
                "--new-password",
                os.getenv("REAL_AUTH_TEST_NEW_PASSWORD", ""),
                "--imap-folder",
                os.getenv("IMAP_FOLDER", "INBOX"),
                "--poll-seconds",
                "120",
                "--write-report",
                str(report_dir / "auth.json"),
            ]
            auth_code, auth_payload, auth_stderr = run_json_command(auth_cmd, cwd=PROJECT_ROOT)
            write_text(report_dir / "auth.stderr.log", auth_stderr)
            summary["evidence"]["auth"] = auth_payload
            summary["steps"].append({"stage": "auth", "ok": auth_code == 0, "detail": "auth_acceptance_complete" if auth_code == 0 else "auth_acceptance_failed"})

            email_cmd = [
                python_exe,
                str(PROJECT_ROOT / "scripts" / "email_roundtrip_check.py"),
                "--recipient",
                os.getenv("EMAIL_TEST_RECIPIENT") or os.getenv("SMTP_USER") or "",
                "--poll-seconds",
                "120",
                "--write-report",
                str(report_dir / "email.json"),
            ]
            email_code, email_payload, email_stderr = run_json_command(email_cmd, cwd=PROJECT_ROOT)
            write_text(report_dir / "email.stderr.log", email_stderr)
            summary["evidence"]["email"] = email_payload
            summary["steps"].append({"stage": "email", "ok": email_code == 0, "detail": "email_roundtrip_complete" if email_code == 0 else "email_roundtrip_failed"})

        if do_broker:
            broker_cmd = [
                python_exe,
                str(PROJECT_ROOT / "scripts" / "live_connector_doctor.py"),
                "--all-configured",
                "--symbol",
                "AAPL",
                "--write-report",
                str(report_dir / "broker.json"),
            ]
            broker_code, broker_payload, broker_stderr = run_json_command(broker_cmd, cwd=PROJECT_ROOT)
            write_text(report_dir / "broker.stderr.log", broker_stderr)
            summary["evidence"]["broker"] = broker_payload
            summary["steps"].append({"stage": "broker", "ok": broker_code == 0, "detail": "connector_doctor_complete" if broker_code == 0 else "connector_doctor_failed"})

            smoke_cmd = [
                python_exe,
                str(PROJECT_ROOT / "scripts" / "quant_execution_smoke.py"),
                "--reuse-server",
                "--base-url",
                base_url,
                "--mode",
                "live",
                "--submit-orders",
                "--journal-sync",
                "--cancel-after-submit",
                "--per-order-notional",
                "5",
                "--max-orders",
                "1",
                "--write-report",
                str(report_dir / "live-canary.json"),
            ]
            if args.skip_live:
                smoke_cmd.append("--dry-run")
            if args.confirm_live:
                smoke_cmd.append("--confirm-live")
            live_code, live_payload, live_stderr = run_json_command(smoke_cmd, cwd=PROJECT_ROOT)
            write_text(report_dir / "live-canary.stderr.log", live_stderr)
            summary["evidence"]["live_canary"] = live_payload
            summary["steps"].append({"stage": "live_canary", "ok": live_code == 0, "detail": "execution_smoke_complete" if live_code == 0 else "execution_smoke_failed"})

        summary["ok"] = all(step["ok"] for step in summary["steps"])
        if not summary["ok"]:
            summary["next_actions"].append("Inspect auth/email/broker stage reports under test-results/real-external before retrying.")
        summary["finished_at"] = utc_now()
        write_json(report_dir / "summary.json", summary)
        write_text(report_dir / "summary.md", build_markdown(summary))
        emit_json(summary)
        return 0 if summary["ok"] else 1
    finally:
        if proc is not None:
            stop_process(proc)


if __name__ == "__main__":
    raise SystemExit(main())
