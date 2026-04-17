from __future__ import annotations

import argparse
import imaplib
import json
import os
import sys
import time
from email import message_from_bytes
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

from gateway.utils.email_delivery import send_email_message, smtp_config_snapshot


def emit_json(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def imap_config() -> dict[str, str | int | bool]:
    port = int(os.getenv("IMAP_PORT", "993") or 993)
    return {
        "host": os.getenv("IMAP_HOST", ""),
        "port": port,
        "user": os.getenv("IMAP_USER", ""),
        "password": os.getenv("IMAP_PASSWORD", ""),
        "folder": os.getenv("IMAP_FOLDER", "INBOX") or "INBOX",
        "use_ssl": str(os.getenv("IMAP_USE_SSL", "true")).lower() in {"1", "true", "yes", "on"},
    }


def find_subject(subject: str, poll_seconds: int) -> dict:
    config = imap_config()
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

                ids = [item for item in data[0].split() if item][-20:]
                for msg_id in reversed(ids):
                    fetch_status, fetch_data = client.fetch(msg_id, "(RFC822)")
                    if fetch_status != "OK" or not fetch_data:
                        continue
                    raw_email = fetch_data[0][1]
                    message = message_from_bytes(raw_email)
                    if subject in str(message.get("Subject", "")):
                        return {
                            "ok": True,
                            "detail": "found",
                            "subject": str(message.get("Subject", "")),
                            "from": str(message.get("From", "")),
                            "date": str(message.get("Date", "")),
                        }
        except Exception as exc:  # pragma: no cover - runtime helper
            last_error = str(exc)

        time.sleep(5)

    return {"ok": False, "detail": last_error or "message_not_found_before_timeout"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--recipient", default=os.getenv("EMAIL_TEST_RECIPIENT") or os.getenv("SMTP_USER") or "")
    parser.add_argument("--poll-seconds", type=int, default=90)
    args = parser.parse_args()

    if not args.recipient:
        emit_json({"ok": False, "stage": "config", "detail": "recipient_missing", "smtp": smtp_config_snapshot()})
        return 1

    subject = f"Quant Terminal email roundtrip {int(time.time())}"
    send_result = send_email_message(
        recipient=args.recipient,
        subject=subject,
        text_body=(
            "This is a live SMTP roundtrip test from Quant Terminal.\n\n"
            f"Subject: {subject}\n"
            "If this message appears in IMAP polling, the email channel is working."
        ),
        html_body=(
            "<html><body>"
            "<h2>Quant Terminal email roundtrip</h2>"
            f"<p><strong>{subject}</strong></p>"
            "<p>If this message appears in IMAP polling, the email channel is working.</p>"
            "</body></html>"
        ),
    )
    imap_result = find_subject(subject, args.poll_seconds) if send_result.get("ok") else {"ok": False, "detail": "smtp_failed"}

    ok = bool(send_result.get("ok") and imap_result.get("ok"))
    emit_json(
        {
            "ok": ok,
            "recipient": args.recipient,
            "subject": subject,
            "smtp": send_result,
            "imap": imap_result,
        }
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
