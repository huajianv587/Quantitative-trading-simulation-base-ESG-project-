from __future__ import annotations

import argparse
import imaplib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from email import message_from_bytes
from email.header import decode_header
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")


RESET_SUBJECT = "Quant Terminal password reset"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def emit_json(payload: dict[str, Any]) -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def write_json(path_value: str, payload: dict[str, Any]) -> Path | None:
    if not path_value:
        return None
    path = Path(path_value)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Real Auth Acceptance",
        "",
        f"- ok: `{report.get('ok')}`",
        f"- started_at: `{report.get('started_at')}`",
        f"- finished_at: `{report.get('finished_at')}`",
        f"- email: `{report.get('email')}`",
        f"- primary_backend: `{report.get('auth_status', {}).get('primary_backend')}`",
        f"- effective_backend: `{report.get('auth_status', {}).get('effective_backend')}`",
        "",
        "## Steps",
        "",
    ]
    for step in report.get("steps", []):
        lines.append(f"- `{step['stage']}`: ok=`{step['ok']}` status=`{step.get('status_code', '-')}` detail=`{step.get('detail', '')}`")
    warnings = report.get("warnings") or []
    lines.extend(["", "## Warnings", ""])
    if warnings:
        for warning in warnings:
            lines.append(f"- {warning}")
    else:
        lines.append("- none")
    path.write_text("\n".join(lines), encoding="utf-8")


def auth_headers() -> dict[str, str]:
    return {"Content-Type": "application/json"}


def request_json(method: str, url: str, *, body: dict[str, Any] | None = None, timeout: int = 30) -> tuple[int, dict[str, Any] | str]:
    response = requests.request(method, url, json=body, timeout=timeout, headers=auth_headers())
    try:
        payload = response.json()
    except Exception:
        payload = response.text
    return response.status_code, payload


def decode_subject(raw_subject: str | None) -> str:
    parts = []
    for value, encoding in decode_header(raw_subject or ""):
        if isinstance(value, bytes):
            parts.append(value.decode(encoding or "utf-8", errors="ignore"))
        else:
            parts.append(str(value))
    return "".join(parts)


def message_text(email_message) -> str:
    if email_message.is_multipart():
        chunks: list[str] = []
        for part in email_message.walk():
            content_type = str(part.get_content_type() or "")
            disposition = str(part.get("Content-Disposition", "") or "")
            if "attachment" in disposition.lower():
                continue
            if content_type in {"text/plain", "text/html"}:
                payload = part.get_payload(decode=True) or b""
                charset = part.get_content_charset() or "utf-8"
                chunks.append(payload.decode(charset, errors="ignore"))
        return "\n".join(chunks)
    payload = email_message.get_payload(decode=True) or b""
    charset = email_message.get_content_charset() or "utf-8"
    return payload.decode(charset, errors="ignore")


def extract_reset_token_from_text(text: str) -> str | None:
    patterns = [
        r"Reset token:\s*([A-Za-z0-9_\-]+)",
        r"token=([A-Za-z0-9_\-]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return str(match.group(1)).strip()
    return None


def imap_config(folder_override: str = "") -> dict[str, Any]:
    return {
        "host": os.getenv("IMAP_HOST", ""),
        "port": int(os.getenv("IMAP_PORT", "993") or 993),
        "user": os.getenv("IMAP_USER", ""),
        "password": os.getenv("IMAP_PASSWORD", ""),
        "folder": folder_override or os.getenv("IMAP_FOLDER", "INBOX") or "INBOX",
        "use_ssl": str(os.getenv("IMAP_USE_SSL", "true")).strip().lower() in {"1", "true", "yes", "on"},
    }


def poll_reset_email(*, recipient: str, subject_fragment: str, folder: str, poll_seconds: int) -> dict[str, Any]:
    config = imap_config(folder)
    if not (config["host"] and config["user"] and config["password"]):
        return {"ok": False, "detail": "imap_not_configured", "config": {**config, "password": bool(config["password"])}}

    deadline = time.time() + max(10, poll_seconds)
    last_error = ""
    while time.time() < deadline:
        try:
            if config["use_ssl"]:
                client = imaplib.IMAP4_SSL(config["host"], int(config["port"]))
            else:
                client = imaplib.IMAP4(config["host"], int(config["port"]))
            with client:
                client.login(str(config["user"]), str(config["password"]))
                client.select(str(config["folder"]))
                status, data = client.search(None, "ALL")
                if status != "OK":
                    last_error = f"imap_search_failed:{status}"
                    time.sleep(5)
                    continue
                ids = [item for item in data[0].split() if item][-30:]
                for msg_id in reversed(ids):
                    fetch_status, fetch_data = client.fetch(msg_id, "(RFC822)")
                    if fetch_status != "OK" or not fetch_data:
                        continue
                    raw_email = fetch_data[0][1]
                    parsed = message_from_bytes(raw_email)
                    subject = decode_subject(parsed.get("Subject", ""))
                    delivered_to = str(parsed.get("To", "") or "")
                    if subject_fragment not in subject:
                        continue
                    if recipient.lower() not in delivered_to.lower() and recipient.lower() not in message_text(parsed).lower():
                        continue
                    text = message_text(parsed)
                    reset_token = extract_reset_token_from_text(text)
                    if reset_token:
                        return {
                            "ok": True,
                            "detail": "reset_email_found",
                            "subject": subject,
                            "from": str(parsed.get("From", "")),
                            "to": delivered_to,
                            "date": str(parsed.get("Date", "")),
                            "reset_token": reset_token,
                        }
        except Exception as exc:  # pragma: no cover - real mailbox runtime
            last_error = str(exc)
        time.sleep(5)
    return {"ok": False, "detail": last_error or "reset_email_not_found_before_timeout"}


def add_step(report: dict[str, Any], stage: str, *, ok: bool, detail: str, status_code: int | None = None, payload: Any = None) -> None:
    report["steps"].append(
        {
            "stage": stage,
            "ok": bool(ok),
            "detail": detail,
            "status_code": status_code,
            "payload_preview": json.dumps(payload, ensure_ascii=False)[:1200] if isinstance(payload, (dict, list)) else str(payload or "")[:1200],
        }
    )


def run_acceptance(*, base_url: str, email: str, password: str, new_password: str, imap_folder: str, poll_seconds: int, timeout: int = 30) -> dict[str, Any]:
    report: dict[str, Any] = {
        "ok": False,
        "stage": "auth_acceptance",
        "started_at": utc_now(),
        "finished_at": None,
        "email": email,
        "steps": [],
        "warnings": [],
        "next_actions": [],
        "evidence": {},
    }

    status_code, status_payload = request_json("GET", f"{base_url}/auth/status", timeout=timeout)
    report["auth_status"] = status_payload if isinstance(status_payload, dict) else {"raw": status_payload}
    add_step(report, "auth_status", ok=status_code == 200, detail="status_loaded" if status_code == 200 else "status_failed", status_code=status_code, payload=status_payload)
    if status_code != 200:
        report["warnings"].append("Auth status endpoint failed; real acceptance cannot continue safely.")
        report["finished_at"] = utc_now()
        return report
    if report["auth_status"].get("primary_backend") != "supabase":
        report["warnings"].append("AUTH primary backend is not set to supabase.")
    if report["auth_status"].get("effective_backend") != "supabase":
        report["warnings"].append("Auth runtime is not executing on Supabase yet; sqlite fallback is still active.")
    if not report["auth_status"].get("supabase_ready"):
        report["warnings"].append("Supabase is not ready; real auth closure is not yet satisfied.")
    if not report["auth_status"].get("smtp_ready"):
        report["warnings"].append("SMTP is not ready; reset email delivery will fail.")
    if not report["auth_status"].get("imap_ready"):
        report["warnings"].append("IMAP is not ready; mailbox verification will fail.")

    register_code, register_payload = request_json(
        "POST",
        f"{base_url}/auth/register",
        body={"email": email, "password": password, "name": "Real External Auth"},
        timeout=timeout,
    )
    register_ok = register_code in {200, 409}
    add_step(report, "register", ok=register_ok, detail="registered" if register_code == 200 else "already_registered" if register_code == 409 else "register_failed", status_code=register_code, payload=register_payload)

    login_token: str | None = None
    for label, candidate in (("password", password), ("new_password", new_password)):
        login_code, login_payload = request_json(
            "POST",
            f"{base_url}/auth/login",
            body={"email": email, "password": candidate},
            timeout=timeout,
        )
        add_step(report, f"login_{label}", ok=login_code == 200, detail="login_ok" if login_code == 200 else "login_failed", status_code=login_code, payload=login_payload)
        if login_code == 200 and isinstance(login_payload, dict):
            login_token = str(login_payload.get("token") or "")
            break
    if login_token:
        verify_code, verify_payload = request_json("GET", f"{base_url}/auth/verify?token={login_token}", timeout=timeout)
        add_step(report, "verify_initial_session", ok=verify_code == 200, detail="verify_ok" if verify_code == 200 else "verify_failed", status_code=verify_code, payload=verify_payload)
    else:
        report["warnings"].append("No valid login token was issued before reset.")

    reset_code, reset_payload = request_json(
        "POST",
        f"{base_url}/auth/reset-password/request",
        body={"email": email},
        timeout=timeout,
    )
    add_step(report, "reset_request", ok=reset_code == 200, detail="reset_requested" if reset_code == 200 else "reset_request_failed", status_code=reset_code, payload=reset_payload)

    mailbox_payload = poll_reset_email(
        recipient=email,
        subject_fragment=RESET_SUBJECT,
        folder=imap_folder,
        poll_seconds=poll_seconds,
    )
    report["evidence"]["mailbox"] = mailbox_payload
    add_step(report, "mailbox_poll", ok=bool(mailbox_payload.get("ok")), detail=str(mailbox_payload.get("detail", "")), payload=mailbox_payload)

    reset_token = str(mailbox_payload.get("reset_token") or "")
    if reset_token:
        confirm_code, confirm_payload = request_json(
            "POST",
            f"{base_url}/auth/reset-password/confirm",
            body={"token": reset_token, "new_password": new_password},
            timeout=timeout,
        )
        add_step(report, "reset_confirm", ok=confirm_code == 200, detail="reset_confirmed" if confirm_code == 200 else "reset_confirm_failed", status_code=confirm_code, payload=confirm_payload)
    else:
        add_step(report, "reset_confirm", ok=False, detail="reset_token_missing", payload={"mailbox": mailbox_payload})

    login_after_code, login_after_payload = request_json(
        "POST",
        f"{base_url}/auth/login",
        body={"email": email, "password": new_password},
        timeout=timeout,
    )
    add_step(report, "login_after_reset", ok=login_after_code == 200, detail="login_after_reset_ok" if login_after_code == 200 else "login_after_reset_failed", status_code=login_after_code, payload=login_after_payload)
    final_token = login_after_payload.get("token") if isinstance(login_after_payload, dict) else None
    if final_token:
        verify_after_code, verify_after_payload = request_json("GET", f"{base_url}/auth/verify?token={final_token}", timeout=timeout)
        add_step(report, "session_restore", ok=verify_after_code == 200, detail="session_restore_ok" if verify_after_code == 200 else "session_restore_failed", status_code=verify_after_code, payload=verify_after_payload)

    report["ok"] = (
        report["auth_status"].get("primary_backend") == "supabase"
        and report["auth_status"].get("effective_backend") == "supabase"
        and bool(report["auth_status"].get("supabase_ready"))
        and bool(mailbox_payload.get("ok"))
        and any(step["stage"] == "login_after_reset" and step["ok"] for step in report["steps"])
        and any(step["stage"] == "session_restore" and step["ok"] for step in report["steps"])
    )
    if not report["ok"]:
        report["next_actions"].append("Check Supabase readiness, SMTP/IMAP configuration, and reset token delivery before retrying.")
    report["finished_at"] = utc_now()
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Real auth acceptance runner against live auth endpoints.")
    parser.add_argument("--base-url", default=os.getenv("REAL_EXTERNAL_BASE_URL", "http://127.0.0.1:8006"))
    parser.add_argument("--email", default=os.getenv("REAL_AUTH_TEST_EMAIL", ""))
    parser.add_argument("--password", default=os.getenv("REAL_AUTH_TEST_PASSWORD", ""))
    parser.add_argument("--new-password", default=os.getenv("REAL_AUTH_TEST_NEW_PASSWORD", ""))
    parser.add_argument("--imap-folder", default=os.getenv("IMAP_FOLDER", "INBOX"))
    parser.add_argument("--poll-seconds", type=int, default=120)
    parser.add_argument("--write-report", default="")
    args = parser.parse_args(argv)

    if not (args.email and args.password and args.new_password):
        payload = {
            "ok": False,
            "stage": "config",
            "detail": "email_or_password_missing",
            "required": ["--email", "--password", "--new-password"],
        }
        write_json(args.write_report, payload)
        emit_json(payload)
        return 1

    report = run_acceptance(
        base_url=args.base_url.rstrip("/"),
        email=args.email,
        password=args.password,
        new_password=args.new_password,
        imap_folder=args.imap_folder,
        poll_seconds=args.poll_seconds,
    )
    json_path = write_json(args.write_report, report)
    if json_path is not None:
        write_markdown(json_path.with_suffix(".md"), report)
    emit_json(report)
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
