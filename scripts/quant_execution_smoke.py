from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import requests
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")


def resolve_python_executable() -> str | None:
    candidates = [
        PROJECT_ROOT / ".venv" / "Scripts" / "python.exe",
        PROJECT_ROOT / ".venv" / "bin" / "python",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)

    current = sys.executable
    if current and Path(current).exists():
        return current

    return shutil.which("python")


def emit_json(payload: dict) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    print(text)


def wait_for_health(base_url: str, timeout: int) -> tuple[bool, dict | str]:
    deadline = time.time() + timeout
    last_error: str = "not started"
    while time.time() < deadline:
        try:
            response = requests.get(f"{base_url}/health/ready", timeout=5)
            response.raise_for_status()
            return True, response.json()
        except Exception as exc:
            last_error = str(exc)
            time.sleep(2)
    return False, last_error


def stop_process(proc: subprocess.Popen) -> None:
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


def request_json(method: str, url: str, *, timeout: int, body: dict | None = None) -> tuple[int, dict | str]:
    response = requests.request(method, url, json=body, timeout=timeout)
    try:
        payload = response.json()
    except Exception:
        payload = response.text
    return response.status_code, payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8006)
    parser.add_argument("--startup-timeout", type=int, default=120)
    parser.add_argument("--request-timeout", type=int, default=180)
    parser.add_argument("--submit-orders", action="store_true")
    parser.add_argument("--max-orders", type=int, default=1)
    parser.add_argument("--per-order-notional", type=float, default=1.00)
    parser.add_argument("--app-mode", default=os.getenv("APP_MODE", "local"))
    parser.add_argument("--llm-backend-mode", default=os.getenv("LLM_BACKEND_MODE", "auto"))
    args = parser.parse_args()

    python_exe = resolve_python_executable()
    if not python_exe:
        emit_json({"ok": False, "error": "python executable not found"})
        return 1

    base_url = f"http://{args.host}:{args.port}"
    temp_dir = Path(tempfile.gettempdir())
    stdout_log = temp_dir / f"esg_quant_execution_{args.port}.log"
    stderr_log = temp_dir / f"esg_quant_execution_{args.port}.err.log"
    stdout_log.write_text("", encoding="utf-8")
    stderr_log.write_text("", encoding="utf-8")

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["APP_MODE"] = args.app_mode
    env["LLM_BACKEND_MODE"] = args.llm_backend_mode

    proc = subprocess.Popen(
        [
            python_exe,
            "-m",
            "uvicorn",
            "gateway.main:app",
            "--host",
            args.host,
            "--port",
            str(args.port),
        ],
        cwd=PROJECT_ROOT,
        env=env,
        stdout=stdout_log.open("w", encoding="utf-8"),
        stderr=stderr_log.open("w", encoding="utf-8"),
        creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
    )

    try:
        ready, health_payload = wait_for_health(base_url, args.startup_timeout)
        if not ready:
            emit_json(
                {
                    "ok": False,
                    "stage": "startup",
                    "health": health_payload,
                    "stdout_tail": tail_log(stdout_log),
                    "stderr_tail": tail_log(stderr_log),
                }
            )
            return 1

        research_status, research_payload = request_json(
            "POST",
            f"{base_url}/api/v1/quant/research/run",
            timeout=args.request_timeout,
            body={
                "universe": ["AAPL", "MSFT", "TSLA"],
                "benchmark": "SPY",
                "research_question": "Generate a concise ESG quant shortlist for paper trading.",
                "capital_base": 1000000,
                "horizon_days": 10,
            },
        )
        account_status, account_payload = request_json(
            "GET",
            f"{base_url}/api/v1/quant/execution/account",
            timeout=args.request_timeout,
        )
        execution_status, execution_payload = request_json(
            "POST",
            f"{base_url}/api/v1/quant/execution/paper",
            timeout=args.request_timeout,
            body={
                "universe": ["AAPL", "MSFT", "TSLA"],
                "benchmark": "SPY",
                "capital_base": 1000000,
                "mode": "paper",
                "submit_orders": args.submit_orders,
                "max_orders": args.max_orders,
                "per_order_notional": args.per_order_notional,
                "order_type": "market",
                "time_in_force": "day",
            },
        )
        orders_status, orders_payload = request_json(
            "GET",
            f"{base_url}/api/v1/quant/execution/orders?status=all&limit=10",
            timeout=args.request_timeout,
        )
        positions_status, positions_payload = request_json(
            "GET",
            f"{base_url}/api/v1/quant/execution/positions",
            timeout=args.request_timeout,
        )

        api_ok = all(status == 200 for status in [research_status, account_status, execution_status, orders_status, positions_status])
        broker_submit_ok = True
        if args.submit_orders:
            broker_submit_ok = bool(
                isinstance(execution_payload, dict)
                and execution_payload.get("submitted") is True
                and execution_payload.get("broker_status") == "submitted"
            )
        ok = api_ok and broker_submit_ok
        emit_json(
            {
                "ok": ok,
                "api_ok": api_ok,
                "broker_submit_ok": broker_submit_ok,
                "submit_orders": args.submit_orders,
                "python_executable": python_exe,
                "health": health_payload,
                "research_status": research_status,
                "account_status": account_status,
                "execution_status": execution_status,
                "orders_status": orders_status,
                "positions_status": positions_status,
                "execution_payload": execution_payload,
                "account_payload": account_payload,
                "orders_payload": orders_payload,
                "positions_payload": positions_payload,
            }
        )
        return 0 if ok else 1
    finally:
        stop_process(proc)


if __name__ == "__main__":
    raise SystemExit(main())
