from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

from gateway.connectors.free_live import FreeLiveConnectorRegistry


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def resolve_python_executable() -> str | None:
    candidates = [
        PROJECT_ROOT / ".venv" / "Scripts" / "python.exe",
        PROJECT_ROOT / ".venv" / "bin" / "python",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    if sys.executable and Path(sys.executable).exists():
        return sys.executable
    return shutil.which("python")


def emit_json(payload: dict[str, Any]) -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def write_report(path_value: str, payload: dict[str, Any]) -> Path | None:
    if not path_value:
        return None
    path = Path(path_value)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def wait_for_health(base_url: str, timeout: int) -> tuple[bool, dict[str, Any] | str]:
    deadline = time.time() + timeout
    last_error: str = "not started"
    while time.time() < deadline:
        try:
            response = requests.get(f"{base_url}/health/ready", timeout=5)
            response.raise_for_status()
            return True, response.json()
        except Exception as exc:  # pragma: no cover - runtime helper
            last_error = str(exc)
            time.sleep(2)
    return False, last_error


def stop_process(proc: subprocess.Popen[Any]) -> None:
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)


def tail_log(path: Path, limit: int = 120) -> str:
    if not path.exists():
        return ""
    return "\n".join(path.read_text(encoding="utf-8", errors="ignore").splitlines()[-limit:])


def api_key_for_path(path: str) -> str:
    normalized = str(path or "")
    if normalized.startswith("/ops"):
        return os.getenv("OPS_API_KEY") or os.getenv("ADMIN_API_KEY") or ""
    if normalized.startswith("/admin"):
        return os.getenv("ADMIN_API_KEY") or os.getenv("OPS_API_KEY") or ""
    if normalized.startswith("/api/v1/quant/execution") or normalized.startswith("/api/v1/quant/validation"):
        return os.getenv("EXECUTION_API_KEY") or os.getenv("ADMIN_API_KEY") or os.getenv("OPS_API_KEY") or ""
    if normalized.startswith("/api/v1/trading"):
        return os.getenv("OPS_API_KEY") or os.getenv("ADMIN_API_KEY") or os.getenv("EXECUTION_API_KEY") or ""
    return ""


def request_json(method: str, url: str, *, timeout: int, body: dict[str, Any] | None = None, path: str = "") -> tuple[int, dict[str, Any] | str]:
    headers = {}
    api_key = api_key_for_path(path)
    if api_key:
        headers["x-api-key"] = api_key
        headers["Authorization"] = f"Bearer {api_key}"
    response = requests.request(method, url, json=body, timeout=timeout, headers=headers)
    try:
        payload = response.json()
    except Exception:
        payload = response.text
    return response.status_code, payload


def payload_preview(payload: Any) -> str:
    if isinstance(payload, (dict, list)):
        return json.dumps(payload, ensure_ascii=False)[:1200]
    return str(payload)[:1200]


def stage_entry(stage: str, *, ok: bool, detail: str, status_code: int | None = None, payload: Any = None) -> dict[str, Any]:
    return {
        "stage": stage,
        "ok": bool(ok),
        "detail": detail,
        "status_code": status_code,
        "payload_preview": payload_preview(payload),
    }


def select_execution_universe(research_payload: dict[str, Any] | str) -> list[str]:
    if not isinstance(research_payload, dict):
        return []
    signals = research_payload.get("signals") or []
    ranked = [
        item
        for item in signals
        if isinstance(item, dict)
        and str(item.get("action", "")).lower() == "long"
        and float(item.get("expected_return", 0.0) or 0.0) > 0
    ]
    ranked.sort(key=lambda item: (-float(item.get("expected_return", 0.0) or 0.0), -float(item.get("confidence", 0.0) or 0.0)))
    return [str(item.get("symbol", "")).upper() for item in ranked[:3] if item.get("symbol")]


def run_connector_doctor(symbol: str, *, dry_run: bool) -> dict[str, Any]:
    registry = FreeLiveConnectorRegistry()
    providers = registry.provider_ids(configured_only=True)
    return {
        "registry": registry.registry(),
        "health": registry.health(providers=providers, live=False),
        "quota": registry.quota_status(providers=providers),
        "sample": registry.test(providers=providers, symbol=symbol, dry_run=dry_run, quota_guard=True),
    }


def start_server(host: str, port: int, startup_timeout: int, *, app_mode: str, llm_backend_mode: str) -> tuple[subprocess.Popen[Any] | None, str, Path, Path, dict[str, Any] | str]:
    python_exe = resolve_python_executable()
    if not python_exe:
        return None, "", Path(), Path(), {"detail": "python_executable_not_found"}

    base_url = f"http://{host}:{port}"
    temp_dir = Path(tempfile.gettempdir())
    stdout_log = temp_dir / f"esg_quant_execution_{port}.log"
    stderr_log = temp_dir / f"esg_quant_execution_{port}.err.log"
    stdout_log.write_text("", encoding="utf-8")
    stderr_log.write_text("", encoding="utf-8")

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["APP_MODE"] = app_mode
    env["LLM_BACKEND_MODE"] = llm_backend_mode

    proc = subprocess.Popen(
        [
            python_exe,
            "-m",
            "uvicorn",
            "gateway.main:app",
            "--host",
            host,
            "--port",
            str(port),
        ],
        cwd=PROJECT_ROOT,
        env=env,
        stdout=stdout_log.open("w", encoding="utf-8"),
        stderr=stderr_log.open("w", encoding="utf-8"),
        creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
    )

    ready, health_payload = wait_for_health(base_url, startup_timeout)
    if not ready:
        stop_process(proc)
        return None, base_url, stdout_log, stderr_log, health_payload
    return proc, base_url, stdout_log, stderr_log, health_payload


def should_run_live_canary(args, live_dry_run_payload: dict[str, Any] | str) -> tuple[bool, str]:
    if args.mode != "live":
        return False, "live_mode_not_requested"
    if args.dry_run:
        return False, "dry_run_requested"
    if not args.confirm_live:
        return False, "confirm_live_not_provided"
    if not isinstance(live_dry_run_payload, dict):
        return False, "live_dry_run_failed"
    if live_dry_run_payload.get("live_blocked_until_paper_gate"):
        return False, "paper_gate_not_passed"
    if not live_dry_run_payload.get("ready"):
        return False, f"broker_not_ready:{live_dry_run_payload.get('broker_status', 'unknown')}"
    if str(live_dry_run_payload.get("broker_status", "")).lower() in {"blocked", "kill_switch_engaged", "awaiting_live_confirmation"}:
        return False, str(live_dry_run_payload.get("broker_status", "blocked"))
    return True, "ready_for_live_canary"


def find_cancel_target(execution_payload: dict[str, Any] | str) -> tuple[str | None, str]:
    if not isinstance(execution_payload, dict):
        return None, "execution_payload_missing"
    cancelable = execution_payload.get("cancelable_order_ids") or []
    if cancelable:
        return str(cancelable[0]), "cancelable_order_id"
    orders = execution_payload.get("orders") or []
    for order in orders:
        if str(order.get("status", "")).lower() in {"new", "accepted", "partially_filled", "open"}:
            return str(order.get("client_order_id") or order.get("id") or ""), "open_order"
    if orders:
        return None, "n_a_filled"
    return None, "no_orders"


def run_smoke(args) -> dict[str, Any]:
    report: dict[str, Any] = {
        "ok": False,
        "stage": "execution_smoke",
        "mode": args.mode,
        "started_at": utc_now(),
        "finished_at": None,
        "steps": [],
        "warnings": [],
        "next_actions": [],
        "evidence": {},
    }

    proc = None
    stdout_log = Path()
    stderr_log = Path()
    base_url = args.base_url.rstrip("/") if args.base_url else f"http://{args.host}:{args.port}"
    health_payload: dict[str, Any] | str = {}
    if args.reuse_server:
        ready, health_payload = wait_for_health(base_url, args.startup_timeout)
        report["steps"].append(stage_entry("startup", ok=ready, detail="reused_existing_server" if ready else "reuse_server_not_ready", payload=health_payload))
        if not ready:
            report["warnings"].append("Shared server was not healthy.")
            report["finished_at"] = utc_now()
            return report
    else:
        proc, base_url, stdout_log, stderr_log, health_payload = start_server(
            args.host,
            args.port,
            args.startup_timeout,
            app_mode=args.app_mode,
            llm_backend_mode=args.llm_backend_mode,
        )
        ready = proc is not None
        report["steps"].append(stage_entry("startup", ok=ready, detail="server_started" if ready else "startup_failed", payload=health_payload))
        if not ready:
            report["evidence"]["stdout_tail"] = tail_log(stdout_log)
            report["evidence"]["stderr_tail"] = tail_log(stderr_log)
            report["finished_at"] = utc_now()
            return report

    try:
        connector_payload = run_connector_doctor(args.symbol, dry_run=args.dry_run or args.mode != "live")
        connector_ok = int(connector_payload["sample"]["summary"].get("failed_count", 0)) == 0 or bool(args.dry_run)
        report["evidence"]["connector_doctor"] = connector_payload
        report["steps"].append(stage_entry("connector_doctor", ok=connector_ok, detail="connector_doctor_complete", payload=connector_payload))

        account_status, account_payload = request_json(
            "GET",
            f"{base_url}/api/v1/quant/execution/account?broker=alpaca&mode={args.mode}",
            timeout=args.request_timeout,
            path="/api/v1/quant/execution/account",
        )
        controls_status, controls_payload = request_json(
            "GET",
            f"{base_url}/api/v1/quant/execution/controls",
            timeout=args.request_timeout,
            path="/api/v1/quant/execution/controls",
        )
        paper_gate_status, paper_gate_payload = request_json(
            "GET",
            f"{base_url}/api/v1/quant/execution/paper-gate",
            timeout=args.request_timeout,
            path="/api/v1/quant/execution/paper-gate",
        )
        policy_status, policy_payload = request_json(
            "GET",
            f"{base_url}/api/v1/trading/autopilot/policy",
            timeout=args.request_timeout,
            path="/api/v1/trading/autopilot/policy",
        )
        execution_path_status, execution_path_payload = request_json(
            "GET",
            f"{base_url}/api/v1/trading/execution-path/status",
            timeout=args.request_timeout,
            path="/api/v1/trading/execution-path/status",
        )
        ops_snapshot_status, ops_snapshot_payload = request_json(
            "GET",
            f"{base_url}/api/v1/trading/ops/snapshot",
            timeout=args.request_timeout,
            path="/api/v1/trading/ops/snapshot",
        )
        readiness_ok = all(
            status == 200
            for status in [
                account_status,
                controls_status,
                paper_gate_status,
                policy_status,
                execution_path_status,
                ops_snapshot_status,
            ]
        )
        broker_connected = bool(isinstance(account_payload, dict) and account_payload.get("connected"))
        report["evidence"]["broker_readiness"] = {
            "account": account_payload,
            "controls": controls_payload,
            "paper_gate": paper_gate_payload,
            "policy": policy_payload,
            "execution_path": execution_path_payload,
            "ops_snapshot": ops_snapshot_payload,
        }
        readiness_detail = "broker_ready" if readiness_ok and broker_connected else "broker_degraded"
        report["steps"].append(stage_entry("broker_readiness", ok=readiness_ok and broker_connected, detail=readiness_detail, payload=report["evidence"]["broker_readiness"]))

        research_status, research_payload = request_json(
            "POST",
            f"{base_url}/api/v1/quant/research/run",
            timeout=args.request_timeout,
            body={
                "universe": [],
                "benchmark": "SPY",
                "research_question": "Generate a concise ESG quant shortlist for external broker acceptance.",
                "capital_base": 1000000,
                "horizon_days": 10,
            },
            path="/api/v1/quant/research/run",
        )
        execution_universe = select_execution_universe(research_payload)
        report["evidence"]["research"] = research_payload
        report["steps"].append(stage_entry("research_seed", ok=research_status == 200, detail="research_loaded" if research_status == 200 else "research_failed", status_code=research_status, payload=research_payload))

        should_submit_paper = bool(args.submit_orders or args.mode == "live")
        paper_status, paper_payload = request_json(
            "POST",
            f"{base_url}/api/v1/quant/execution/paper",
            timeout=args.request_timeout,
            body={
                "universe": execution_universe,
                "benchmark": "SPY",
                "capital_base": 1000000,
                "broker": "alpaca",
                "mode": "paper",
                "submit_orders": should_submit_paper,
                "allow_duplicates": args.allow_duplicates,
                "max_orders": max(1, int(args.max_orders)),
                "per_order_notional": float(args.per_order_notional),
                "order_type": "market",
                "time_in_force": "day",
            },
            path="/api/v1/quant/execution/paper",
        )
        report["evidence"]["paper_submit"] = paper_payload
        paper_ok = paper_status == 200 and (not should_submit_paper or bool(isinstance(paper_payload, dict) and paper_payload.get("submitted")))
        report["steps"].append(stage_entry("paper_submit", ok=paper_ok, detail="paper_submitted" if paper_ok and should_submit_paper else "paper_plan_ready" if paper_ok else "paper_submit_failed", status_code=paper_status, payload=paper_payload))

        paper_journal_payload = None
        if args.journal_sync and isinstance(paper_payload, dict) and paper_payload.get("execution_id"):
            journal_status, paper_journal_payload = request_json(
                "POST",
                f"{base_url}/api/v1/quant/execution/journal/{paper_payload['execution_id']}/sync?broker=alpaca",
                timeout=args.request_timeout,
                path="/api/v1/quant/execution/journal/sync",
            )
            report["evidence"]["paper_journal_sync"] = paper_journal_payload
            report["steps"].append(stage_entry("journal_sync", ok=journal_status == 200, detail="paper_journal_synced" if journal_status == 200 else "paper_journal_sync_failed", status_code=journal_status, payload=paper_journal_payload))

        live_dry_run_status, live_dry_run_payload = request_json(
            "POST",
            f"{base_url}/api/v1/quant/execution/paper",
            timeout=args.request_timeout,
            body={
                "universe": execution_universe,
                "benchmark": "SPY",
                "capital_base": 1000000,
                "broker": "alpaca",
                "mode": "live",
                "submit_orders": False,
                "allow_duplicates": False,
                "max_orders": 1,
                "per_order_notional": min(float(args.per_order_notional), float(args.live_notional_cap)),
                "order_type": "market",
                "time_in_force": "day",
                "live_confirmed": True,
                "operator_confirmation": "dry_run_preflight",
            },
            path="/api/v1/quant/execution/paper",
        )
        report["evidence"]["live_dry_run"] = live_dry_run_payload
        live_dry_ok = live_dry_run_status == 200
        report["steps"].append(stage_entry("live_dry_run", ok=live_dry_ok, detail="live_preflight_complete" if live_dry_ok else "live_preflight_failed", status_code=live_dry_run_status, payload=live_dry_run_payload))

        allow_live_submit, live_reason = should_run_live_canary(args, live_dry_run_payload)
        live_canary_payload: dict[str, Any] | str = {"detail": live_reason}
        if allow_live_submit:
            live_canary_status, live_canary_payload = request_json(
                "POST",
                f"{base_url}/api/v1/quant/execution/paper",
                timeout=args.request_timeout,
                body={
                    "universe": execution_universe,
                    "benchmark": "SPY",
                    "capital_base": 1000000,
                    "broker": "alpaca",
                    "mode": "live",
                    "submit_orders": True,
                    "allow_duplicates": False,
                    "max_orders": 1,
                    "per_order_notional": min(float(args.per_order_notional), float(args.live_notional_cap)),
                    "order_type": "market",
                    "time_in_force": "day",
                    "live_confirmed": True,
                    "operator_confirmation": "real_external_canary",
                },
                path="/api/v1/quant/execution/paper",
            )
            live_ok = live_canary_status == 200 and isinstance(live_canary_payload, dict) and bool(live_canary_payload.get("submitted"))
            report["steps"].append(stage_entry("live_canary", ok=live_ok, detail="live_canary_submitted" if live_ok else "live_canary_failed", status_code=live_canary_status, payload=live_canary_payload))
        else:
            safe_skip = live_reason in {"live_mode_not_requested", "dry_run_requested", "confirm_live_not_provided"}
            report["steps"].append(stage_entry("live_canary", ok=safe_skip, detail=live_reason, payload=live_canary_payload))
        report["evidence"]["live_canary"] = live_canary_payload

        effective_mode = "live" if allow_live_submit else ("live" if args.mode == "live" else "paper")
        execution_reference = live_canary_payload if allow_live_submit else paper_payload
        orders_status, orders_payload = request_json(
            "GET",
            f"{base_url}/api/v1/quant/execution/orders?status=all&limit=10&mode={effective_mode}",
            timeout=args.request_timeout,
            path="/api/v1/quant/execution/orders",
        )
        positions_status, positions_payload = request_json(
            "GET",
            f"{base_url}/api/v1/quant/execution/positions?mode={effective_mode}",
            timeout=args.request_timeout,
            path="/api/v1/quant/execution/positions",
        )
        report["evidence"]["orders_sync"] = orders_payload
        report["evidence"]["positions_sync"] = positions_payload
        report["steps"].append(stage_entry("orders_sync", ok=orders_status == 200, detail="orders_loaded" if orders_status == 200 else "orders_failed", status_code=orders_status, payload=orders_payload))
        report["steps"].append(stage_entry("positions_sync", ok=positions_status == 200, detail="positions_loaded" if positions_status == 200 else "positions_failed", status_code=positions_status, payload=positions_payload))

        if args.journal_sync and isinstance(execution_reference, dict) and execution_reference.get("execution_id"):
            live_journal_status, live_journal_payload = request_json(
                "POST",
                f"{base_url}/api/v1/quant/execution/journal/{execution_reference['execution_id']}/sync?broker=alpaca",
                timeout=args.request_timeout,
                path="/api/v1/quant/execution/journal/sync",
            )
            report["evidence"]["final_journal_sync"] = live_journal_payload
            report["steps"].append(stage_entry("journal_sync_final", ok=live_journal_status == 200, detail="journal_synced" if live_journal_status == 200 else "journal_sync_failed", status_code=live_journal_status, payload=live_journal_payload))

        if args.cancel_after_submit and isinstance(execution_reference, dict) and execution_reference.get("execution_id"):
            cancel_order_id, cancel_reason = find_cancel_target(execution_reference)
            if cancel_order_id:
                cancel_status, cancel_payload = request_json(
                    "POST",
                    f"{base_url}/api/v1/quant/execution/orders/{cancel_order_id}/cancel",
                    timeout=args.request_timeout,
                    body={"broker": "alpaca", "execution_id": execution_reference["execution_id"]},
                    path="/api/v1/quant/execution/orders/cancel",
                )
                report["evidence"]["cancel_if_open"] = cancel_payload
                report["steps"].append(stage_entry("cancel_if_open", ok=cancel_status == 200, detail="cancel_requested" if cancel_status == 200 else "cancel_failed", status_code=cancel_status, payload=cancel_payload))
            else:
                report["steps"].append(stage_entry("cancel_if_open", ok=(cancel_reason == "n_a_filled"), detail=cancel_reason, payload=execution_reference))

        report["ok"] = all(step["ok"] for step in report["steps"] if step["stage"] != "live_canary" or args.mode == "live")
        if not report["ok"]:
            report["next_actions"].append("Inspect broker readiness, journal sync, and live confirmation gates before attempting a new canary.")
        report["finished_at"] = utc_now()
        return report
    finally:
        if proc is not None:
            stop_process(proc)


def parse_args(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(description="Staged external execution smoke runner.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8012)
    parser.add_argument("--base-url", default="")
    parser.add_argument("--reuse-server", action="store_true")
    parser.add_argument("--startup-timeout", type=int, default=120)
    parser.add_argument("--request-timeout", type=int, default=180)
    parser.add_argument("--submit-orders", action="store_true")
    parser.add_argument("--allow-duplicates", action="store_true")
    parser.add_argument("--max-orders", type=int, default=1)
    parser.add_argument("--per-order-notional", type=float, default=1.00)
    parser.add_argument("--live-notional-cap", type=float, default=5.0)
    parser.add_argument("--mode", choices=["paper", "live"], default="paper")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--confirm-live", action="store_true")
    parser.add_argument("--cancel-after-submit", action="store_true")
    parser.add_argument("--journal-sync", action="store_true")
    parser.add_argument("--symbol", default="AAPL")
    parser.add_argument("--write-report", default="")
    parser.add_argument("--app-mode", default=os.getenv("APP_MODE", "local"))
    parser.add_argument("--llm-backend-mode", default=os.getenv("LLM_BACKEND_MODE", "auto"))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = run_smoke(args)
    write_report(args.write_report, report)
    emit_json(report)
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
