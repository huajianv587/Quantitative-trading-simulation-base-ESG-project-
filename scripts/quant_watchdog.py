from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_now() -> str:
    return utc_now().isoformat()


def read_json(path: Path) -> dict[str, Any]:
    try:
        if path.exists():
            payload = json.loads(path.read_text(encoding="utf-8"))
            return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}
    return {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def resolve_path(raw: str | None, fallback: str) -> Path:
    value = (raw or "").strip()
    path = Path(value) if value else PROJECT_ROOT / fallback
    return path if path.is_absolute() else PROJECT_ROOT / path


def parse_timestamp(raw: Any) -> datetime | None:
    text = str(raw or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def check_http(url: str, timeout: float) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        request = Request(url, headers={"User-Agent": "quant-watchdog/1.0"})
        with urlopen(request, timeout=timeout) as response:
            body = response.read(4096).decode("utf-8", errors="replace")
            return {
                "ok": 200 <= int(response.status) < 300,
                "status_code": int(response.status),
                "duration_ms": round((time.perf_counter() - started) * 1000),
                "body": body[:1000],
            }
    except (OSError, URLError, TimeoutError) as exc:
        return {
            "ok": False,
            "status_code": None,
            "duration_ms": round((time.perf_counter() - started) * 1000),
            "error": str(exc),
        }


def check_heartbeat(path: Path, stale_seconds: int) -> dict[str, Any]:
    payload = read_json(path)
    timestamp = parse_timestamp(payload.get("updated_at") or payload.get("generated_at"))
    if timestamp is None:
        return {"ok": False, "exists": path.exists(), "stale": True, "path": str(path), "payload": payload}
    age_seconds = max(0.0, (utc_now() - timestamp).total_seconds())
    return {
        "ok": age_seconds <= stale_seconds,
        "exists": True,
        "stale": age_seconds > stale_seconds,
        "age_seconds": round(age_seconds, 3),
        "path": str(path),
        "payload": payload,
    }


def latest_json_record(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"ok": False, "exists": False, "path": str(path), "reason": "directory_missing"}
    records = sorted(path.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
    if not records:
        return {"ok": False, "exists": True, "path": str(path), "reason": "record_missing"}
    latest = records[0]
    payload = read_json(latest)
    return {
        "ok": True,
        "exists": True,
        "path": str(path),
        "latest_path": str(latest),
        "mtime": datetime.fromtimestamp(latest.stat().st_mtime, timezone.utc).isoformat(),
        "payload": payload,
    }


def latest_backup_record(storage_dir: Path) -> dict[str, Any]:
    backup_dir = storage_dir / "backups"
    if not backup_dir.exists():
        return {"ok": False, "exists": False, "path": str(backup_dir), "reason": "directory_missing"}
    backups = sorted(backup_dir.glob("*.tar.gz"), key=lambda item: item.stat().st_mtime, reverse=True)
    if not backups:
        return {"ok": False, "exists": True, "path": str(backup_dir), "reason": "backup_missing"}
    latest = backups[0]
    return {
        "ok": True,
        "exists": True,
        "path": str(backup_dir),
        "latest_path": str(latest),
        "size_bytes": latest.stat().st_size,
        "mtime": datetime.fromtimestamp(latest.stat().st_mtime, timezone.utc).isoformat(),
    }


def run_command(args: list[str], *, cwd: Path, timeout: int = 30) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            args,
            cwd=str(cwd),
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        return {
            "ok": completed.returncode == 0,
            "returncode": completed.returncode,
            "duration_ms": round((time.perf_counter() - started) * 1000),
            "stdout": completed.stdout[-4000:],
            "stderr": completed.stderr[-4000:],
            "command": args,
        }
    except Exception as exc:
        return {
            "ok": False,
            "returncode": None,
            "duration_ms": round((time.perf_counter() - started) * 1000),
            "error": str(exc),
            "command": args,
        }


def compose_args(compose_file: str | None) -> list[str]:
    args = ["docker", "compose"]
    if compose_file:
        args.extend(["-f", compose_file])
    return args


def collect_diagnostics(project_dir: Path, compose_file: str | None, services: list[str]) -> dict[str, Any]:
    base = compose_args(compose_file)
    return {
        "compose_ps": run_command([*base, "ps"], cwd=project_dir, timeout=20),
        "recent_logs": run_command([*base, "logs", "--tail=80", *services], cwd=project_dir, timeout=30),
    }


def restart_services(project_dir: Path, compose_file: str | None, services: list[str]) -> dict[str, Any]:
    return run_command([*compose_args(compose_file), "restart", *services], cwd=project_dir, timeout=120)


def storage_root() -> Path:
    return resolve_path(os.getenv("QUANT_STORAGE_DIR"), "storage/quant")


def alert_id_for(failures: list[str]) -> str:
    digest = hashlib.sha1("|".join(sorted(failures)).encode("utf-8")).hexdigest()[:16]
    return f"alert-watchdog-{digest}"


def previous_ready_failure_count(root: Path) -> int:
    event_dir = root / "watchdog_events"
    if not event_dir.exists():
        return 0
    count = 0
    for path in sorted(event_dir.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)[:20]:
        payload = read_json(path)
        checks = payload.get("checks") if isinstance(payload.get("checks"), dict) else {}
        ready = checks.get("ready") if isinstance(checks, dict) else {}
        if not isinstance(ready, dict):
            break
        if ready.get("ok"):
            break
        if "ready_unhealthy" in set(payload.get("failures") or []):
            count += 1
        else:
            break
    return count


def non_restartable_ready_failure(ready: dict[str, Any]) -> bool:
    text = json.dumps(ready, ensure_ascii=False).lower()
    markers = (
        "alpaca",
        "telegram",
        "model_registry",
        "rl_checkpoint",
        "market_data",
        "credential",
        "synthetic",
        "live",
        "kill_switch",
    )
    return any(marker in text for marker in markers)


def restart_targets_for(args: argparse.Namespace, failures: list[str], ready: dict[str, Any], root: Path) -> list[str]:
    targets: set[str] = set()
    configured = set(args.restart_services or [])
    if "livez_unhealthy" in failures:
        targets.add("api")
    if "scheduler_heartbeat_stale" in failures:
        targets.add("quant-scheduler")
    if "ready_unhealthy" in failures and not non_restartable_ready_failure(ready):
        threshold = max(1, int(args.ready_restart_threshold))
        if previous_ready_failure_count(root) + 1 >= threshold:
            targets.update(configured)
    return [service for service in (args.restart_services or []) if service in targets]


def deliver_telegram(alert: dict[str, Any], timeout: float) -> dict[str, Any]:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        return {"delivery": "local_ledger", "delivery_status": "skipped", "reason": "telegram_not_configured"}
    text = f"[HIGH] quant_watchdog\n{alert.get('message')}\n{alert.get('alert_id')}"[:3500]
    try:
        import requests

        response = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "disable_web_page_preview": True},
            timeout=timeout,
        )
        return {
            "delivery": "telegram",
            "delivery_status": "sent" if response.ok else "failed",
            "status_code": response.status_code,
            "error": "" if response.ok else response.text[:300],
        }
    except Exception as exc:
        return {"delivery": "telegram", "delivery_status": "failed", "error": str(exc)}


def persist_event(event: dict[str, Any], *, notify: bool, notifier_timeout: float) -> dict[str, Any]:
    root = storage_root()
    event_id = event["event_id"]
    write_json(root / "watchdog_events" / f"{event_id}.json", event)
    if event.get("status") == "ok":
        return event
    failures = list(event.get("failures") or ["watchdog_failure"])
    alert = {
        "alert_id": alert_id_for(failures),
        "generated_at": event["generated_at"],
        "kind": "watchdog_restart" if event.get("restart_attempted") else "watchdog_failure",
        "severity": "high",
        "message": "Quant paper watchdog detected unhealthy runtime checks.",
        "payload": {
            "failures": failures,
            "event_id": event_id,
            "restart_attempted": event.get("restart_attempted", False),
            "restart": event.get("restart"),
        },
        "notifier": {"delivery": "local_ledger", "delivery_status": "skipped"},
    }
    if notify:
        alert["notifier"] = deliver_telegram(alert, timeout=notifier_timeout)
    write_json(root / "alerts" / f"{alert['alert_id']}.json", alert)
    event["alert_id"] = alert["alert_id"]
    write_json(root / "watchdog_events" / f"{event_id}.json", event)
    return event


def evaluate_once(args: argparse.Namespace) -> dict[str, Any]:
    api_url = args.api_url.rstrip("/")
    root = storage_root()
    heartbeat = check_heartbeat(args.heartbeat_path, stale_seconds=args.heartbeat_stale_seconds)
    livez = check_http(f"{api_url}/livez", timeout=args.http_timeout)
    ready = check_http(f"{api_url}/ready", timeout=args.http_timeout)
    session_evidence = latest_json_record(root / "session_evidence")
    latest_backup = latest_backup_record(root)
    failures = []
    if not livez.get("ok"):
        failures.append("livez_unhealthy")
    if not ready.get("ok"):
        failures.append("ready_unhealthy")
    if not heartbeat.get("ok"):
        failures.append("scheduler_heartbeat_stale")

    event = {
        "event_id": f"watchdog-{utc_now().strftime('%Y%m%d%H%M%S%f')}",
        "generated_at": iso_now(),
        "status": "ok" if not failures else "failed",
        "failures": failures,
        "checks": {
            "livez": livez,
            "ready": ready,
            "scheduler_heartbeat": heartbeat,
            "latest_session_evidence": session_evidence,
            "latest_backup": latest_backup,
        },
        "restart_attempted": False,
        "dry_run": bool(args.dry_run),
    }
    if failures:
        targets = restart_targets_for(args, failures, ready, root)
        event["restart_services"] = targets
        event["restart_count"] = len(targets)
        event["diagnostics"] = collect_diagnostics(args.project_dir, args.compose_file, targets or args.restart_services)
        event["recent_logs"] = (event["diagnostics"].get("recent_logs") or {}).get("stdout", "")[-4000:]
        if targets and not args.dry_run:
            event["restart_attempted"] = True
            event["restart_started_at"] = iso_now()
            event["restart"] = restart_services(args.project_dir, args.compose_file, targets)
            event["restart_finished_at"] = iso_now()
    return persist_event(event, notify=bool(args.notify), notifier_timeout=args.http_timeout)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="External watchdog for unattended Hybrid Paper runtime.")
    parser.add_argument("--once", action="store_true", help="Run one check and exit.")
    parser.add_argument("--dry-run", action="store_true", help="Record checks but do not restart services.")
    parser.add_argument("--notify", action="store_true", help="Send Telegram alert when configured.")
    parser.add_argument("--interval-seconds", type=int, default=int(os.getenv("WATCHDOG_INTERVAL_SECONDS", "60")))
    parser.add_argument("--http-timeout", type=float, default=float(os.getenv("WATCHDOG_HTTP_TIMEOUT_SECONDS", "5")))
    parser.add_argument("--api-url", default=os.getenv("WATCHDOG_API_URL", "http://127.0.0.1:8012"))
    parser.add_argument("--compose-file", default=os.getenv("WATCHDOG_COMPOSE_FILE", "docker-compose.yml"))
    parser.add_argument("--project-dir", type=Path, default=Path(os.getenv("WATCHDOG_PROJECT_DIR", str(PROJECT_ROOT))))
    parser.add_argument(
        "--heartbeat-path",
        type=Path,
        default=resolve_path(os.getenv("SCHEDULER_HEARTBEAT_PATH"), "storage/quant/scheduler/heartbeat.json"),
    )
    parser.add_argument(
        "--heartbeat-stale-seconds",
        type=int,
        default=int(os.getenv("WATCHDOG_HEARTBEAT_STALE_SECONDS", "300")),
    )
    parser.add_argument(
        "--restart-services",
        nargs="+",
        default=[item.strip() for item in os.getenv("WATCHDOG_RESTART_SERVICES", "api,quant-scheduler").split(",") if item.strip()],
    )
    parser.add_argument(
        "--ready-restart-threshold",
        type=int,
        default=int(os.getenv("WATCHDOG_READY_RESTART_THRESHOLD", "3")),
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    while True:
        event = evaluate_once(args)
        print(json.dumps(event, ensure_ascii=False))
        if args.once:
            return 0 if event.get("status") == "ok" or args.dry_run else 2
        time.sleep(max(10, int(args.interval_seconds)))


if __name__ == "__main__":
    raise SystemExit(main())
